#!/usr/bin/env bash
set -euo pipefail

ENDPOINT="http://127.0.0.1:4566"
REGION="us-east-1"

BUCKET_NAME="tb-events-bucket"
TOPIC_NAME="tb-events-topic"
MAIN_QUEUE_NAME="tb-main-queue"
DLQ_NAME="tb-dlq"
IAM_USER="tb-uploader"

CREDENTIALS_FILE="/app/uploader-credentials.json"
UPLOAD_BODY_FILE="/app/upload_body.txt"
CPP_ROOT="/app/cpp_upload"
CPP_BUILD="${CPP_ROOT}/build"
S3_PUT="${CPP_BUILD}/s3_put"

echo "=== Waiting for LocalStack at ${ENDPOINT} ==="
for i in $(seq 1 60); do
  if aws --endpoint-url "${ENDPOINT}" --region "${REGION}" s3 ls >/dev/null 2>&1; then
    echo "LocalStack is up."
    break
  fi
  sleep 1
  if [ "$i" -eq 60 ]; then
    echo "LocalStack did not become ready in time."
    exit 1
  fi
done

echo "=== Creating bucket: ${BUCKET_NAME} ==="
aws --endpoint-url "${ENDPOINT}" --region "${REGION}" s3api create-bucket \
  --bucket "${BUCKET_NAME}" >/dev/null 2>&1 || true

aws --endpoint-url "${ENDPOINT}" --region "${REGION}" s3api put-bucket-versioning \
  --bucket "${BUCKET_NAME}" \
  --versioning-configuration Status=Enabled

aws --endpoint-url "${ENDPOINT}" --region "${REGION}" s3api put-bucket-encryption \
  --bucket "${BUCKET_NAME}" \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }
    ]
  }'

echo "=== SNS / SQS ==="
TOPIC_ARN=$(aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sns create-topic \
  --name "${TOPIC_NAME}" \
  --query 'TopicArn' \
  --output text)

DLQ_URL=$(aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sqs create-queue \
  --queue-name "${DLQ_NAME}" \
  --query 'QueueUrl' \
  --output text)

DLQ_ARN=$(aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sqs get-queue-attributes \
  --queue-url "${DLQ_URL}" \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' \
  --output text)

cat >/tmp/main-queue-attributes.json <<EOF
{
  "RedrivePolicy": "{\"deadLetterTargetArn\":\"${DLQ_ARN}\",\"maxReceiveCount\":\"5\"}"
}
EOF

MAIN_QUEUE_URL=$(aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sqs create-queue \
  --queue-name "${MAIN_QUEUE_NAME}" \
  --attributes file:///tmp/main-queue-attributes.json \
  --query 'QueueUrl' \
  --output text)

MAIN_QUEUE_ARN=$(aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sqs get-queue-attributes \
  --queue-url "${MAIN_QUEUE_URL}" \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' \
  --output text)

QUEUE_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": "*",
      "Action": "sqs:SendMessage",
      "Resource": "${MAIN_QUEUE_ARN}",
      "Condition": {
        "ArnEquals": { "aws:SourceArn": "${TOPIC_ARN}" }
      }
    }
  ]
}
EOF
)

QUEUE_POLICY_MINIFIED=$(printf '%s\n' "${QUEUE_POLICY}" | jq -c '.')

cat >/tmp/main-queue-policy.json <<EOF
{
  "Policy": "$(printf '%s' "${QUEUE_POLICY_MINIFIED}" | sed 's/"/\\"/g')"
}
EOF

aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sqs set-queue-attributes \
  --queue-url "${MAIN_QUEUE_URL}" \
  --attributes file:///tmp/main-queue-policy.json

aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sns subscribe \
  --topic-arn "${TOPIC_ARN}" \
  --protocol sqs \
  --notification-endpoint "${MAIN_QUEUE_ARN}" >/dev/null

echo "=== IAM user ${IAM_USER} ==="
aws --endpoint-url "${ENDPOINT}" --region "${REGION}" iam create-user \
  --user-name "${IAM_USER}" >/dev/null 2>&1 || true

POLICY_DOC=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/incoming/*"
    }
  ]
}
EOF
)

aws --endpoint-url "${ENDPOINT}" --region "${REGION}" iam put-user-policy \
  --user-name "${IAM_USER}" \
  --policy-name "${IAM_USER}-policy" \
  --policy-document "${POLICY_DOC}"

aws --endpoint-url "${ENDPOINT}" --region "${REGION}" iam create-access-key \
  --user-name "${IAM_USER}" \
  > "${CREDENTIALS_FILE}"

echo "=== Build C++ s3_put ==="
cmake -S "${CPP_ROOT}" -B "${CPP_BUILD}"
cmake --build "${CPP_BUILD}" -j

test -x "${S3_PUT}"

echo "=== Presigned PUT via s3_put (tb-uploader keys) ==="
UPLOADER_ACCESS_KEY_ID=$(jq -r '.AccessKey.AccessKeyId' "${CREDENTIALS_FILE}")
UPLOADER_SECRET_ACCESS_KEY=$(jq -r '.AccessKey.SecretAccessKey' "${CREDENTIALS_FILE}")

export AWS_ACCESS_KEY_ID="${UPLOADER_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${UPLOADER_SECRET_ACCESS_KEY}"
export AWS_DEFAULT_REGION="${REGION}"

PRESIGN=$(aws --endpoint-url "${ENDPOINT}" --region "${REGION}" s3 presign "s3://${BUCKET_NAME}/incoming/test-object.txt")

unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_DEFAULT_REGION

"${S3_PUT}" "${PRESIGN}" "${UPLOAD_BODY_FILE}"

# Restore default LocalStack credentials for admin API calls.
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION="${REGION}"

echo "=== Publish synthetic S3 event JSON to SNS (pipeline check) ==="
EVENT_JSON=$(cat <<EOF
{
  "Records": [
    {
      "eventVersion": "2.1",
      "eventSource": "aws:s3",
      "s3": {
        "bucket": { "name": "${BUCKET_NAME}" },
        "object": { "key": "incoming/test-object.txt" }
      }
    }
  ]
}
EOF
)

aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sns publish \
  --topic-arn "${TOPIC_ARN}" \
  --message "${EVENT_JSON}" >/dev/null

sleep 3
echo "=== Done ==="
