variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "unique_suffix" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "availability_zones" {
  type = list(string)
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "enable_signoz" {
  type    = bool
  default = false
}
