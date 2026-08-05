# Main application log group
resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/fastapi/${local.name_prefix}"
  retention_in_days = var.log_retention_in_days

  tags = {
    Name = "${local.name_prefix}-app-logs"
  }
}

# ALB access logs
resource "aws_s3_bucket" "alb_logs" {
  bucket = "${var.project_name}-${var.environment}-alb-logs-${var.unique_suffix}"

  tags = {
    Name = "${local.name_prefix}-alb-logs"
  }
}

# CloudWatch Alarms

# High CPU alarm for ECS service
resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  alarm_name          = "${local.name_prefix}-ecs-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "60"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "ECS service CPU utilization is too high"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = "fastapi-aws-backend-dev"
    ServiceName = "fastapi-aws-backend-dev-service"
  }
}

# High memory alarm for ECS service
resource "aws_cloudwatch_metric_alarm" "ecs_memory_high" {
  alarm_name          = "${local.name_prefix}-ecs-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = "60"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "ECS service memory utilization is too high"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = "fastapi-aws-backend-dev"
    ServiceName = "fastapi-aws-backend-dev-service"
  }
}

# ALB target response time
resource "aws_cloudwatch_metric_alarm" "alb_response_time_high" {
  alarm_name          = "${local.name_prefix}-alb-response-time-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = "60"
  statistic           = "Average"
  threshold           = "2"
  alarm_description   = "ALB target response time is too high"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = "fastapi-aws-backend-dev-alb"
  }
}

# RDS CPU alarm
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${local.name_prefix}-rds-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "60"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "RDS CPU utilization is too high"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = "fastapi-aws-backend-dev-db"
  }
}

# Unhealthy host alarm
resource "aws_cloudwatch_metric_alarm" "unhealthy_host" {
  alarm_name          = "${local.name_prefix}-unhealthy-host"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = "60"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "ALB has unhealthy hosts"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = "fastapi-aws-backend-dev-alb"
    TargetGroup  = "fastapi-aws-backend-dev-tg"
  }
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.app.name
}
