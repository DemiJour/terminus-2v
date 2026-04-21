Task Name
aws-localstack-event-pipeline
Instructions
You are working inside a single Docker container at /app. Your task is to
provision an AWS-like event ingestion pipeline on LocalStack and verify it
end-to-end.

LocalStack emulates AWS services on:
    http://localstack:4566
in region:
    us-east-1

LocalStack is provided as a separate "localstack" service via docker-compose
and will be started for you by the harness. You do NOT need to run Docker or
docker compose commands yourself. However, you MUST wait until LocalStack is
ready before creating resources. A simple way is to poll an AWS CLI command
against LocalStack until it succeeds, for example:

    aws --endpoint-url http://localstack:4566 --region us-east-1 s3 ls

Very important: all AWS API calls in this task MUST talk to LocalStack, not
real AWS. Every AWS CLI or Terraform call that interacts with S3, SNS, SQS,
or IAM MUST explicitly use this LocalStack endpoint and region:
    - Endpoint:  http://localstack:4566
    - Region:    us-east-1

In AWS CLI, always include:
    --endpoint-url http://localstack:4566 --region us-east-1

In Terraform, configure the provider with endpoints mapping S3, SNS, SQS,
and IAM to http://localstack:4566 and region us-east-1.

You may use AWS CLI, Terraform, or both. The final system state must satisfy
*all* requirements below.

1. Start LocalStack
   -------------------------------------------------
   LocalStack must be running and serving the following services:
     - S3
     - SNS
     - SQS
     - IAM

   All calls must target:
     --endpoint-url http://localstack:4566
     --region us-east-1

   Ensure LocalStack is fully ready (for example by polling "aws s3 ls"
   against the LocalStack endpoint) before you start creating resources.

2. Create the S3 bucket
   -------------------------------------------------
   Create a bucket named:
     tb-events-bucket
   in region us-east-1 with:
     - Versioning enabled
     - Default server-side encryption using SSE-S3 (AES256)

3. Create SNS + SQS resources
   -------------------------------------------------
   Create:
     - SNS topic:  tb-events-topic
     - SQS queue:  tb-main-queue
     - SQS DLQ:    tb-dlq

   Configure tb-main-queue with a redrive policy sending failed messages
   to tb-dlq.

4. Event wiring: S3 → SNS → SQS
   -------------------------------------------------
   Configure the following pipeline:

     S3 bucket "tb-events-bucket"
         (ObjectCreated:* events)
         → SNS topic "tb-events-topic"
         → SQS queue "tb-main-queue"

   A notification published to the SNS topic MUST appear as a message
   in tb-main-queue.

   LocalStack must deliver the *standard SNS notification envelope* to SQS,
   meaning the SQS message Body is a JSON string containing:
     {
       "Type": "Notification",
       "Message": "<S3 Event JSON>",
       ...
     }

5. Create restricted IAM user
   -------------------------------------------------
   Create an IAM user named:
     tb-uploader

   Grant the user ONLY the following permissions:

     Allowed:
       - ListBucket on tb-events-bucket
       - GetObject and PutObject under prefix:
            incoming/*
     Denied:
       - PutObject outside the incoming/ prefix

   Create an access key for this user and save the
   FULL JSON output of:
       aws iam create-access-key
   into:

       /app/uploader-credentials.json

6. Upload an object using only tb-uploader credentials
   -------------------------------------------------
   A file exists at:
       /app/upload_body.txt

   Using ONLY the credentials inside /app/uploader-credentials.json,
   upload a new object:

       bucket: tb-events-bucket
       key: incoming/test-object.txt
       body: exactly the contents of upload_body.txt

   You may use any standard method to feed these credentials to the AWS CLI.
   For example, you can parse /app/uploader-credentials.json and export:

       AWS_ACCESS_KEY_ID=<AccessKey.AccessKeyId>
       AWS_SECRET_ACCESS_KEY=<AccessKey.SecretAccessKey>
       AWS_DEFAULT_REGION=us-east-1

   Before running the S3 upload command. The key requirement is that the
   upload is performed with the tb-uploader identity, not the default test
   credentials.

   This upload must succeed (IAM allows the prefix incoming/).

7. End-to-end validation: must produce a queue message
   -------------------------------------------------
   The above upload MUST trigger:

       S3 → SNS → SQS

   At least one unconsumed message MUST exist in:
       tb-main-queue

   The SQS message MUST contain the SNS notification JSON envelope
   referencing:
     - TopicArn of tb-events-topic
     - S3 event with:
         bucket.name == "tb-events-bucket"
         object.key starts with "incoming/"

   In practice, there may be a short delay between writing the object to S3
   and the message appearing in tb-main-queue. Your solution may need to
   poll the SQS queue for a few seconds (for example using receive-message
   in a loop with a small sleep) to allow the S3 → SNS → SQS pipeline to
   complete.

Final success requires that ALL of the following must be true:
   -------------------------------------------------
   - LocalStack is running and reachable at http://localstack:4566 in region us-east-1.
   - tb-events-bucket exists with versioning + SSE-S3.
   - tb-events-topic, tb-main-queue, tb-dlq all exist and are wired correctly.
   - IAM user tb-uploader exists with correct prefix-restricted permissions.
   - /app/uploader-credentials.json exists with valid access key material.
   - Uploading incoming/test-object.txt via tb-uploader produced an SNS
     message that arrived in tb-main-queue, with a standard SNS envelope
     containing an inner S3 event JSON referencing tb-events-bucket and an
     object key starting with incoming/.
