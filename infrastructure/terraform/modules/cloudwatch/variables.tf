variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "unique_suffix" {
  type = string
}

variable "alb_arn_suffix" {
  type = string
}

variable "ecs_service_name" {
  type = string
}

variable "lambda_function_name" {
  type = string
}

variable "rds_instance_id" {
  type = string
}

variable "redis_cluster_id" {
  type = string
}

variable "log_retention_in_days" {
  type    = number
  default = 30
}
