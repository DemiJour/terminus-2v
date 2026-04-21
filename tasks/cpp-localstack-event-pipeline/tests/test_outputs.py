"""Verify LocalStack S3/SNS/SQS/IAM setup, IAM credentials file, C++ s3_put binary, and queue payload shape."""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

LOCALSTACK_ENDPOINT = "http://127.0.0.1:4566"
REGION = "us-east-1"


def _aws_env() -> dict[str, str]:
    """Environment for AWS CLI against LocalStack (matches image defaults)."""
    env = os.environ.copy()
    env.setdefault("AWS_ACCESS_KEY_ID", "test")
    env.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    env.setdefault("AWS_DEFAULT_REGION", REGION)
    return env


def run_aws_json(args: list[str]) -> dict[str, Any]:
    """Run an AWS CLI command against LocalStack and parse JSON stdout."""
    base_cmd = [
        "aws",
        "--endpoint-url",
        LOCALSTACK_ENDPOINT,
        "--region",
        REGION,
        "--output",
        "json",
    ]
    proc = subprocess.run(
        base_cmd + args,
        check=True,
        capture_output=True,
        text=True,
        env=_aws_env(),
    )
    stdout = proc.stdout.strip()
    return json.loads(stdout) if stdout else {}


def test_uploader_credentials_file_exists() -> None:
    """Verify /app/uploader-credentials.json exists with AccessKey for tb-uploader."""
    cred_path = Path("/app/uploader-credentials.json")
    assert cred_path.is_file(), "Expected /app/uploader-credentials.json to exist"

    raw = cred_path.read_text().strip()
    assert raw, "/app/uploader-credentials.json must be non-empty JSON from create-access-key"
    data = json.loads(raw)
    assert "AccessKey" in data, "Expected 'AccessKey' field in credentials JSON"
    access_key = data["AccessKey"]
    assert access_key.get("UserName") == "tb-uploader", "AccessKey must belong to tb-uploader"
    assert access_key.get("AccessKeyId"), "AccessKeyId must be present"
    assert access_key.get("SecretAccessKey"), "SecretAccessKey must be present"


def test_bucket_has_versioning_and_sse() -> None:
    """Verify tb-events-bucket has versioning and SSE-S3 (AES256)."""
    versioning = run_aws_json(
        ["s3api", "get-bucket-versioning", "--bucket", "tb-events-bucket"]
    )
    assert versioning.get("Status") == "Enabled", "Bucket versioning must be enabled"

    encryption = run_aws_json(
        ["s3api", "get-bucket-encryption", "--bucket", "tb-events-bucket"]
    )
    rules = encryption.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
    assert rules, "Expected at least one SSE rule on the bucket"

    has_aes256 = any(
        rule.get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm") == "AES256"
        for rule in rules
    )
    assert has_aes256, "Expected bucket to use SSE-S3 (AES256) by default"


def test_main_queue_has_redrive_policy_to_dlq() -> None:
    """Verify tb-main-queue redrive policy points at tb-dlq."""
    main_url = run_aws_json(["sqs", "get-queue-url", "--queue-name", "tb-main-queue"])["QueueUrl"]

    attrs = run_aws_json(
        [
            "sqs",
            "get-queue-attributes",
            "--queue-url",
            main_url,
            "--attribute-names",
            "RedrivePolicy",
        ]
    ).get("Attributes", {})

    assert "RedrivePolicy" in attrs, "Expected RedrivePolicy on tb-main-queue"

    policy = json.loads(attrs["RedrivePolicy"])
    dl_arn = policy.get("deadLetterTargetArn", "")
    assert dl_arn, "RedrivePolicy must include deadLetterTargetArn"
    assert "tb-dlq" in dl_arn, "Dead letter target ARN must reference tb-dlq"

    max_rc = int(policy.get("maxReceiveCount", "0"))
    assert max_rc > 0, "maxReceiveCount must be > 0"


def test_s3_object_matches_upload_body() -> None:
    """Uploaded object incoming/test-object.txt must match /app/upload_body.txt bytes."""
    expected = Path("/app/upload_body.txt").read_bytes()
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        path = tmp.name
    try:
        subprocess.run(
            [
                "aws",
                "--endpoint-url",
                LOCALSTACK_ENDPOINT,
                "--region",
                REGION,
                "s3api",
                "get-object",
                "--bucket",
                "tb-events-bucket",
                "--key",
                "incoming/test-object.txt",
                path,
            ],
            check=True,
            env=_aws_env(),
        )
        actual = Path(path).read_bytes()
    finally:
        Path(path).unlink(missing_ok=True)

    assert actual == expected, "S3 object body must match /app/upload_body.txt exactly"


def test_cpp_upload_client_built_at_expected_path() -> None:
    """The C++ upload client must exist as an executable at /app/cpp_upload/build/s3_put."""
    binary = Path("/app/cpp_upload/build/s3_put")
    assert binary.is_file(), f"Expected {binary} to exist"
    assert os.access(binary, os.X_OK), f"Expected {binary} to be executable"


def test_cpp_upload_cmake_requires_cxx17() -> None:
    """Project CMake must request C++17 for the s3_put target."""
    cmake = Path("/app/cpp_upload/CMakeLists.txt").read_text()
    assert "CMAKE_CXX_STANDARD" in cmake
    assert "17" in cmake


def test_pipeline_produces_sns_envelope_in_main_queue() -> None:
    """tb-main-queue must contain an SNS Notification envelope whose inner Message is an S3 event JSON."""
    main_url = run_aws_json(["sqs", "get-queue-url", "--queue-name", "tb-main-queue"])["QueueUrl"]

    # Poll: agents may publish near the verifier deadline; LocalStack can be briefly delayed.
    messages: list[dict[str, Any]] = []
    for _ in range(25):
        result = run_aws_json(
            [
                "sqs",
                "receive-message",
                "--queue-url",
                main_url,
                "--max-number-of-messages",
                "1",
                "--wait-time-seconds",
                "2",
            ]
        )
        messages = result.get("Messages", [])
        if messages:
            break
        time.sleep(1.0)

    assert messages, "Expected at least one message in tb-main-queue"

    body = messages[0]["Body"]
    envelope = json.loads(body)
    assert envelope.get("Type") == "Notification", "SQS body must be an SNS Notification envelope"

    msg_str = envelope.get("Message", "")
    assert msg_str, "SNS envelope must contain a 'Message' field"

    inner = json.loads(msg_str)
    records = inner.get("Records", [])
    assert records, "Inner S3 event must contain at least one record"

    s3_info = records[0]["s3"]
    bucket_name = s3_info["bucket"]["name"]
    object_key = s3_info["object"]["key"]

    assert bucket_name == "tb-events-bucket", "S3 event must reference tb-events-bucket"
    assert object_key.startswith("incoming/"), "Uploaded object key must start with 'incoming/'"
