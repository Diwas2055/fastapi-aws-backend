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

variable "private_subnet_ids" {
  type = list(string)
}

variable "cache_security_group_id" {
  type = string
}

variable "node_type" {
  type    = string
  default = "cache.t3.micro"
}

variable "num_cache_nodes" {
  type    = number
  default = 1
}

variable "log_retention_in_days" {
  type    = number
  default = 30
}
