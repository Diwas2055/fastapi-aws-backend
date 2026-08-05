variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "unique_suffix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "app_security_group_id" {
  type = string
}

variable "alb_security_group_id" {
  type = string
}

variable "ecs_task_role_arn" {
  type = string
}

variable "ecs_execution_role_arn" {
  type = string
}

variable "container_image" {
  type = string
}

variable "container_port" {
  type = number
}

variable "rds_endpoint" {
  type = string
}

variable "redis_endpoint" {
  type = string
}

variable "s3_bucket_name" {
  type = string
}

variable "dynamodb_table_name" {
  type = string
}

variable "sqs_queue_url" {
  type = string
}

variable "sns_topic_arn" {
  type = string
}

variable "cloudwatch_log_group_arn" {
  type = string
}

variable "db_password_secret_arn" {
  type = string
}

variable "log_retention_in_days" {
  type    = number
  default = 30
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "alb_target_group_arn" {
  type = string
}
