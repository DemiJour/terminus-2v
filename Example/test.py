# This test file validates that the LocalStack-based AWS-like event ingestion pipeline
# has been provisioned correctly by the agent. It checks:
#   - S3 bucket configuration (versioning + SSE-S3)
#   - SNS topic existence and S3 notifications
#   - SQS queues and DLQ redrive policy
#   - IAM user prefix-restricted policy
#   - SQS message body shape: SNS envelope -> S3 event JSON

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

LOCALSTACK_ENDPOINT = "http://localstack:4566"
REGION = "us-east-1"


def run_aws(args: List[str]) -> Dict[str, Any]:
    """Run an AWS CLI command against LocalStack and return parsed JSON."""
    base_cmd = [
        "aws",
        "--endpoint-url",
        LOCALSTACK_ENDPOINT,
        "--region",
        REGION,
    ]
    full_cmd = base_cmd + args
    proc = subprocess.run(
        full_cmd,
        check=True,
        capture_output=True,
        text=True,
    )
    stdout = proc.stdout.strip()
    return json.loads(stdout) if stdout else {}


def test_uploader_credentials_file_exists():
    """
    Verify that /app/uploader-credentials.json exists and contains an
    AccessKey structure for the tb-uploader IAM user.
    """
    cred_path = Path("/app/uploader-credentials.json")
    assert cred_path.exists(), "Expected /app/uploader-credentials.json to exist"

    data = json.loads(cred_path.read_text())
    assert "AccessKey" in data, "Expected 'AccessKey' field in credentials JSON"
    access_key = data["AccessKey"]
    assert access_key.get("UserName") == "tb-uploader", "AccessKey must belong to tb-uploader"
    assert access_key.get("AccessKeyId"), "AccessKeyId must be present"
    assert access_key.get("SecretAccessKey"), "SecretAccessKey must be present"


def test_bucket_has_versioning_and_sse():
    """
    Verify that tb-events-bucket exists with versioning and SSE-S3 enabled.
    """
    # Versioning
    versioning = run_aws(
        ["s3api", "get-bucket-versioning", "--bucket", "tb-events-bucket"]
    )
    assert versioning.get("Status") == "Enabled", "Bucket versioning must be enabled"

    # Encryption
    encryption = run_aws(
        ["s3api", "get-bucket-encryption", "--bucket", "tb-events-bucket"]
    )
    rules = encryption.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
    assert rules, "Expected at least one SSE rule on the bucket"

    # Find an AES256 rule
    has_aes256 = any(
        rule.get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm") == "AES256"
        for rule in rules
    )
    assert has_aes256, "Expected bucket to use SSE-S3 (AES256) by default"


def test_main_queue_has_redrive_policy_to_dlq():
    """
    Verify that tb-main-queue has a redrive policy pointing to tb-dlq.
    """
    main_url = run_aws(
        ["sqs", "get-queue-url", "--queue-name", "tb-main-queue"]
    )["QueueUrl"]

    attrs = run_aws(
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


def test_pipeline_produces_sns_envelope_in_main_queue():
    """
    Verify that the S3 -> SNS -> SQS pipeline delivered at least one
    SNS notification envelope into tb-main-queue as a result of the
    upload of incoming/test-object.txt.
    """
    # Get queue URL
    main_url = run_aws(
        ["sqs", "get-queue-url", "--queue-name", "tb-main-queue"]
    )["QueueUrl"]

    # Receive a single message (do not delete it)
    result = run_aws(
        [
            "sqs",
            "receive-message",
            "--queue-url",
            main_url,
            "--max-number-of-messages",
            "1",
            "--wait-time-seconds",
            "1",
        ]
    )

    messages = result.get("Messages", [])
    assert messages, "Expected at least one message in tb-main-queue"

    body = messages[0]["Body"]
    # Outer body: SNS envelope
    envelope = json.loads(body)
    assert envelope.get("Type") == "Notification", "SQS body must be an SNS Notification envelope"

    msg_str = envelope.get("Message", "")
    assert msg_str, "SNS envelope must contain a 'Message' field"

    # Inner message: S3 event JSON
    inner = json.loads(msg_str)
    records = inner.get("Records", [])
    assert records, "Inner S3 event must contain at least one record"

    s3_info = records[0]["s3"]
    bucket_name = s3_info["bucket"]["name"]
    object_key = s3_info["object"]["key"]

    assert bucket_name == "tb-events-bucket", "S3 event must reference tb-events-bucket"
    assert object_key.startswith("incoming/"), "Uploaded object key must start with 'incoming/'"
