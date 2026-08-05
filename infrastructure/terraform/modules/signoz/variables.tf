variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "unique_suffix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "signoz_security_group_id" {
  type = string
}
