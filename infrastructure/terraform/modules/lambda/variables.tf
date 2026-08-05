data "aws_region" "current" {}

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

variable "lambda_role_arn" {
  type = string
}

variable "lambda_security_group_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "s3_bucket_name" {
  type = string
}

variable "dynamodb_table_arn" {
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

variable "runtime" {
  type    = string
  default = "python3.12"
}

variable "memory_size" {
  type    = number
  default = 128
}

variable "timeout" {
  type    = number
  default = 30
}

variable "log_retention_in_days" {
  type    = number
  default = 30
}
