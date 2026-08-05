resource "aws_sqs_queue" "main" {
  name                      = "${var.project_name}-${var.environment}-queue-${var.unique_suffix}"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600 # 14 days
  receive_wait_time_seconds  = 20      # Long polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name = "${local.name_prefix}-sqs"
  }
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.project_name}-${var.environment}-queue-dlq-${var.unique_suffix}"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name = "${local.name_prefix}-sqs-dlq"
  }
}

output "queue_url" {
  value = aws_sqs_queue.main.id
}

output "queue_arn" {
  value = aws_sqs_queue.main.arn
}

output "dlq_url" {
  value = aws_sqs_queue.dlq.id
}

output "dlq_arn" {
  value = aws_sqs_queue.dlq.arn
}
