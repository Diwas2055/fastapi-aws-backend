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

variable "s3_bucket_arn" {
  type = string
}

variable "dynamodb_table_arn" {
  type = string
}

variable "sqs_queue_arn" {
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
