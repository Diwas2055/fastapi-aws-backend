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

variable "alb_security_group_id" {
  type = string
}

variable "domain_name" {
  type    = string
  default = ""
}

variable "certificate_arn" {
  type    = string
  default = ""
}

variable "enable_signoz" {
  type    = bool
  default = false
}
