resource "aws_sns_topic" "main" {
  name = "${var.project_name}-${var.environment}-notifications-${var.unique_suffix}"

  tags = {
    Name = "${local.name_prefix}-sns"
  }
}

resource "aws_sns_topic_subscription" "sqs" {
  count     = var.sqs_queue_arn != null ? 1 : 0
  topic_arn = aws_sns_topic.main.arn
  protocol  = "sqs"
  endpoint  = var.sqs_queue_arn
}

output "topic_arn" {
  value = aws_sns_topic.main.arn
}

output "topic_name" {
  value = aws_sns_topic.main.name
}
