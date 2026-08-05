# AWS Troubleshooting Guide

Enterprise-grade troubleshooting for AWS service issues encountered in this FastAPI backend.

## Table of Contents

1. [S3 Issues](#s3-issues)
2. [DynamoDB Issues](#dynamodb-issues)
3. [SQS Issues](#sqs-issues)
4. [SNS Issues](#sns-issues)
5. [Lambda Issues](#lambda-issues)
6. [LocalStack Issues](#localstack-issues)
7. [General AWS Issues](#general-aws-issues)

---

## S3 Issues

### BucketAlreadyExists / BucketAlreadyOwnedByYou

**Symptoms**: `BucketAlreadyExists` or `BucketAlreadyOwnedByYou` error when creating bucket.

**Cause**: Bucket names are globally unique across all AWS accounts.

**Fix**:
```bash
# Use a unique bucket name with account/region prefix
aws s3 mb s3://myapp-uploads-123456789012-us-east-1
```

### AccessDenied (ListBucket / PutObject)

**Symptoms**: `AccessDenied` when listing or uploading to S3.

**Cause**: IAM role/policy missing required permissions.

**Fix**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::my-bucket",
        "arn:aws:s3:::my-bucket/*"
      ]
    }
  ]
}
```

### Presigned URL Expired

**Symptoms**: `403 Forbidden` or `AccessDenied` when using presigned URL.

**Cause**: URL exceeded its expiry time (`S3_PRESIGNED_URL_EXPIRY`).

**Fix**:
```python
# Generate new URL with longer expiry for large uploads
url = await s3_service.generate_presigned_upload_url(
    key=key,
    content_type="application/octet-stream",
    expires_in=7200,  # 2 hours
)
```

### EntityTooLarge / Upload Exceeds 5GB

**Symptoms**: `EntityTooLarge` error for files >5GB.

**Cause**: Standard `put_object` has 5GB limit.

**Fix**: Use multipart upload for files >100MB (see S3 Guide).

```python
# Initiate multipart upload
init = await s3_service.initiate_multipart_upload(key, content_type)
upload_id = init["upload_id"]

# Upload parts in parallel (max 10,000 parts, min 5MB each)
# Complete when all parts uploaded
await s3_service.complete_multipart_upload(key, upload_id, parts)
```

### Multipart Upload Stalled / Incomplete

**Symptoms**: Upload never completes, parts remain in bucket.

**Cause**: Client crashed or network interrupted before `complete_multipart_upload`.

**Fix**:
```bash
# List incomplete uploads
aws s3 list-multipart-uploads --bucket my-bucket

# Abort stale uploads
aws s3 abort-multipart-upload --bucket my-bucket --key path/to/object --upload-id <id>
```

**Prevention**: Set lifecycle rule to abort uploads older than 7 days:
```json
{
  "Rules": [
    {
      "ID": "AbortIncompleteMultipartUpload",
      "Status": "Enabled",
      "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
    }
  ]
}
```

### Slow Upload Performance

**Symptoms**: Upload speed much slower than expected.

**Causes & Fixes**:
1. **Single-threaded upload**: Use multipart with concurrent parts
2. **Wrong region**: Ensure bucket and client are in same region
3. **Network throttling**: Check VPC endpoints, NAT gateway bandwidth
4. **Large part size**: Use 50-100MB parts for better throughput

```python
# Increase concurrency for better throughput
S3_MULTIPART_MAX_CONCURRENCY = 8  # Default is 4
```

---

## DynamoDB Issues

### ProvisionedThroughputExceededException

**Symptoms**: `ProvisionedThroughputExceededException` or `ThrottlingException`.

**Cause**: Exceeded read/write capacity units.

**Fix**:
```python
# Option 1: Add exponential backoff retry
# Option 2: Switch to on-demand mode
# Option 3: Increase provisioned capacity
# Option 4: Use DynamoDB Accelerator (DAX)
```

### ItemNotFound / KeyDoesNotExist

**Symptoms**: `ItemNotFound` when getting item.

**Cause**: Wrong partition/sort key, or item was deleted.

**Fix**:
```python
# Verify key format
item = await dynamodb_service.get_item(pk="USER#123", sk="ITEM#456")
if not item:
    # Check if table exists and key is correct
    pass
```

### ValidationException (Empty Key)

**Symptoms**: `ValidationException` when putting item.

**Cause**: Empty string values in key attributes (DynamoDB doesn't allow empty strings).

**Fix**:
```python
# Replace empty strings with None or placeholder
data = {k: (v if v != "" else None) for k, v in data.items()}
```

---

## SQS Issues

### Message Lost / Not Received

**Symptoms**: Messages sent but never received.

**Causes**:
1. Visibility timeout too short — message reappears before processing finishes
2. Consumer crashed before deleting message
3. Wrong queue URL

**Fix**:
```bash
# Check message available count
aws sqs get-queue-attributes \
  --queue-url $SQS_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages
```

```python
# Increase visibility timeout for long-running processing
await sqs_service.send_message(
    message_body={"task": "process"},
    delay_seconds=0,
)
# Set visibility timeout when receiving
messages = await sqs_service.receive_messages(
    max_messages=10,
    wait_time_seconds=20,
)
# Delete after successful processing
await sqs_service.delete_message(receipt_handle)
```

### Message Duplication

**Symptoms**: Same message processed multiple times.

**Fix**: Enable content-based deduplication or use deduplication ID:
```python
await sqs_service.send_message(
    message_body={"id": "unique-id"},
    message_attributes={
        "deduplication_id": {"DataType": "String", "StringValue": "unique-id"}
    },
)
```

### Dead Letter Queue (DLQ) Full

**Symptoms**: Messages going to DLQ after max receives.

**Fix**:
```bash
# Review DLQ messages
aws sqs receive-message --queue-url $DLQ_URL --max-number-of-messages 10

# Fix the root cause and replay
aws sqs purge-queue --queue-url $DLQ_URL
```

---

## SNS Issues

### Message Not Delivered

**Symptoms**: Publish succeeds but subscriber never receives message.

**Causes & Checks**:
1. **Subscription not confirmed**: Check subscription status
2. **Filter policy blocking**: Verify filter policy matches message attributes
3. **Endpoint disabled**: Check SQS/email endpoint status

```bash
# List subscriptions
aws sns list-subscriptions-by-topic --topic-arn $SNS_TOPIC_ARN

# Check subscription status
aws sns get-subscription-attributes --subscription-arn <arn>
```

### Duplicate Notifications

**Symptoms**: Same notification received multiple times.

**Causes**:
1. Multiple subscriptions on topic
2. Multiple SQS consumers processing same message

**Fix**:
```bash
# List all subscriptions
aws sns list-subscriptions-by-topic --topic-arn $SNS_TOPIC_ARN

# Remove duplicate subscriptions
aws sns unsubscribe --subscription-arn <arn>
```

---

## Lambda Issues

### Lambda Timeout

**Symptoms**: Lambda task timed out after X seconds.

**Fix**:
```python
# Increase timeout in terraform or serverless config
resource "aws_lambda_function" "app" {
  timeout = 30  # seconds, max 900
  memory_size = 256  # Also increase memory for CPU-bound tasks
}
```

### Lambda Cold Starts

**Symptoms**: High latency on first invocation or after idle period.

**Fix**:
1. Increase memory (also increases CPU)
2. Use Provisioned Concurrency for critical paths
3. Keep Lambda warm with scheduled invocations
4. Use Lambda SnapStart for Java functions

```python
# Provisioned concurrency
lambda_service.put_function_concurrency(
    function_name="my-function",
    reserved_concurrent_executions=5,
)
```

### Lambda Permission Denied

**Symptoms**: `AccessDeniedException` when Lambda accesses AWS resources.

**Fix**: Ensure Lambda execution role has required permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::my-bucket/*"
    }
  ]
}
```

---

## LocalStack Issues

### Service Not Available

**Symptoms**: `Connection refused` or `Could not connect to endpoint`.

**Fix**:
```bash
# Check LocalStack health
curl http://localhost:4566/_localstack/health

# Restart LocalStack
docker-compose restart localstack

# Check logs
docker-compose logs localstack
```

### LocalStack Docker Socket Mount Error (macOS)

**Symptoms**: `Error mounting /var/run/docker.sock` on macOS.

**Fix**: In `docker-compose.yml`, ensure LocalStack has:
```yaml
environment:
  - DISABLE_MACHINE_CONFIG=1
  - MOUNT_ROOT=/tmp/localstack
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

### LocalStack Auth Token Required

**Symptoms**: `Please configure your LocalStack auth token`.

**Fix**: LocalStack CE 3.6 doesn't require auth token. Pin to this version:
```yaml
# docker-compose.yml
image: localstack/localstack:3.6
```

### Lambda Image Pull Failures

**Symptoms**: Lambda can't pull container image.

**Fix**: Ensure Docker socket is mounted:
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

### Data Persistence Lost

**Symptoms**: S3 buckets, DynamoDB tables disappear after restart.

**Fix**: Mount a volume for LocalStack data:
```yaml
volumes:
  - localstack-data:/var/lib/localstack
  # Or
  - ./volume:/var/lib/localstack
```

---

## General AWS Issues

### SignatureDoesNotMatch

**Symptoms**: `SignatureDoesNotMatch` error.

**Causes**:
1. Incorrect system clock (drift >5 minutes)
2. Wrong AWS credentials
3. Incorrect region

**Fix**:
```bash
# Check system time
date
# Sync if needed (macOS)
sudo sntp -sS time.apple.com

# Verify credentials
aws sts get-caller-identity
```

### RequestExpired

**Symptoms**: `RequestExpired` error.

**Cause**: Request timestamp too far from AWS server time.

**Fix**: Sync system clock or use SigV4 with explicit timestamp.

### Service Quotas Exceeded

**Symptoms**: `LimitExceededException` or `ServiceQuotaExceededException`.

**Fix**:
```bash
# Check current quotas
aws service-quotas get-service-quota --service-code s3 --quota-code L-DC2B2D3D

# Request quota increase via AWS Console
```

### VPC Endpoint Issues

**Symptoms**: Timeouts when accessing AWS services from private subnet.

**Fix**:
1. Ensure VPC endpoint exists for required services (S3, DynamoDB, etc.)
2. Check route tables for endpoint routes
3. Verify security groups allow traffic to endpoint

```bash
# Describe VPC endpoints
aws ec2 describe-vpc-endpoints --filters Name=vpc-id,value=<vpc-id>
```

### IAM Role Propagation Delay

**Symptoms**: `AccessDenied` immediately after creating IAM role.

**Cause**: IAM changes take a few seconds to propagate.

**Fix**: Wait 10-15 seconds after creating/modifying IAM roles before using them.

### CloudWatch Logs Not Appearing

**Symptoms**: Logs not showing up in CloudWatch.

**Fix**:
1. Check log group exists
2. Verify IAM role has `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
3. Check CloudWatch agent configuration
4. Verify region matches

---

## Emergency Debugging Commands

```bash
# AWS CLI quick checks
aws sts get-caller-identity
aws ec2 describe-regions
aws iam list-users --max-items 5

# Check service health
curl https://status.aws.amazon.com/

# Verify network connectivity
nc -zv s3.us-east-1.amazonaws.com 443
nc -zv dynamodb.us-east-1.amazonaws.com 443

# Test with minimal request
aws s3 ls --max-items 1
aws dynamodb list-tables --max-items 1
aws sqs list-queues --max-items 1
```

---

## Getting Help

1. **AWS Support**: Open support case in AWS Console
2. **CloudWatch Logs**: Check application and infrastructure logs
3. **AWS X-Ray**: Trace request paths for latency issues
4. **AWS Health Dashboard**: https://health.aws.amazon.com/
5. **Service Quotas**: https://docs.aws.amazon.com/general/latest/gr/aws-service-information.html
