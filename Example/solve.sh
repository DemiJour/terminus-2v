#!/bin/bash
set -euo pipefail

ENDPOINT="http://localstack:4566"
REGION="us-east-1"

BUCKET_NAME="tb-events-bucket"
TOPIC_NAME="tb-events-topic"
MAIN_QUEUE_NAME="tb-main-queue"
DLQ_NAME="tb-dlq"
IAM_USER="tb-uploader"

CREDENTIALS_FILE="/app/uploader-credentials.json"
UPLOAD_BODY_FILE="/app/upload_body.txt"

echo "=== Setting up LocalStack event pipeline resources ==="

############################################
# WAIT FOR LOCALSTACK
############################################
echo "=== Waiting for LocalStack at ${ENDPOINT} ==="
for i in {1..30}; do
  if aws --endpoint-url "${ENDPOINT}" --region "${REGION}" s3 ls >/dev/null 2>&1; then
    echo "LocalStack is up."
    break
  fi
  sleep 1
  if [ "$i" -eq 30 ]; then
    echo "LocalStack did not become ready in time."
    exit 1
  fi
done

############################################
# 1. CREATE S3 BUCKET (versioning + SSE)
############################################
echo "=== Creating bucket: ${BUCKET_NAME} ==="
aws --endpoint-url "${ENDPOINT}" --region "${REGION}" s3api create-bucket \
  --bucket "${BUCKET_NAME}" >/dev/null 2>&1 || true

echo "=== Enabling versioning on bucket ==="
aws --endpoint-url "${ENDPOINT}" --region "${REGION}" s3api put-bucket-versioning \
  --bucket "${BUCKET_NAME}" \
  --versioning-configuration Status=Enabled

echo "=== Enabling default SSE-S3 (AES256) on bucket ==="
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

############################################
# 2. CREATE SNS + SQS + DLQ
############################################
echo "=== Creating SNS topic: ${TOPIC_NAME} ==="
TOPIC_ARN=$(aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sns create-topic \
  --name "${TOPIC_NAME}" \
  --query 'TopicArn' \
  --output text)

echo "=== Creating SQS DLQ: ${DLQ_NAME} ==="
DLQ_URL=$(aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sqs create-queue \
  --queue-name "${DLQ_NAME}" \
  --query 'QueueUrl' \
  --output text)

DLQ_ARN=$(aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sqs get-queue-attributes \
  --queue-url "${DLQ_URL}" \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' \
  --output text)

echo "=== Creating main queue with redrive policy: ${MAIN_QUEUE_NAME} ==="

echo "=== Creating main queue with redrive policy: ${MAIN_QUEUE_NAME} ==="

# Write attributes JSON to a temporary file to avoid quoting issues
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

############################################
# 3. ALLOW SNS -> SQS
############################################
echo "=== Setting queue policy to allow SNS -> SQS ==="

# Define the queue policy as pretty JSON first
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

# Minify it and escape quotes so it can live as a JSON string value
QUEUE_POLICY_MINIFIED=$(printf '%s\n' "${QUEUE_POLICY}" | jq -c '.')

cat >/tmp/main-queue-policy.json <<EOF
{
  "Policy": "$(printf '%s' "${QUEUE_POLICY_MINIFIED}" | sed 's/"/\\"/g')"
}
EOF

aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sqs set-queue-attributes \
  --queue-url "${MAIN_QUEUE_URL}" \
  --attributes file:///tmp/main-queue-policy.json


############################################
# 4. SNS SUBSCRIBE QUEUE
############################################
echo "=== Subscribing SQS queue to SNS topic ==="
aws --endpoint-url "${ENDPOINT}" --region "${REGION}" sns subscribe \
  --topic-arn "${TOPIC_ARN}" \
  --protocol sqs \
  --notification-endpoint "${MAIN_QUEUE_ARN}" >/dev/null

############################################
# 5. CREATE IAM USER + ACCESS KEY
############################################
echo "=== Creating IAM user: ${IAM_USER} ==="
aws --endpoint-url "${ENDPOINT}" --region "${REGION}" iam create-user \
  --user-name "${IAM_USER}" >/dev/null 2>&1 || true

echo "=== Attaching prefix-restricted S3 policy to ${IAM_USER} ==="
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

echo "=== Creating access key for ${IAM_USER} and saving to ${CREDENTIALS_FILE} ==="

aws --endpoint-url "${ENDPOINT}" --region "${REGION}" iam create-access-key \
  --user-name "${IAM_USER}" \
  > "${CREDENTIALS_FILE}"

############################################
# 6. UPLOAD OBJECT USING tb-uploader KEYS
############################################
echo "=== Uploading object using tb-uploader credentials ==="
UPLOADER_ACCESS_KEY_ID=$(jq -r '.AccessKey.AccessKeyId' "${CREDENTIALS_FILE}")
UPLOADER_SECRET_ACCESS_KEY=$(jq -r '.AccessKey.SecretAccessKey' "${CREDENTIALS_FILE}")

AWS_ACCESS_KEY_ID="${UPLOADER_ACCESS_KEY_ID}" \
AWS_SECRET_ACCESS_KEY="${UPLOADER_SECRET_ACCESS_KEY}" \
AWS_DEFAULT_REGION="${REGION}" \
aws --endpoint-url "${ENDPOINT}" s3 cp \
  "${UPLOAD_BODY_FILE}" \
  "s3://${BUCKET_NAME}/incoming/test-object.txt"

############################################
# 7. PUBLISH SYNTHETIC S3 EVENT TO SNS
############################################
echo "=== Publishing synthetic S3 event JSON to SNS topic ==="
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

echo "=== Waiting briefly for SNS -> SQS delivery ==="
sleep 3

echo "=== Solution completed (tests will verify state using AWS CLI). ==="
