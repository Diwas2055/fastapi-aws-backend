variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "unique_suffix" {
  type = string
}

variable "sqs_queue_arn" {
  type      = string
  default   = null
}
