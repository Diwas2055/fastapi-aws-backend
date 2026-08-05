variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "fastapi-aws-backend"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "container_image" {
  description = "Docker image for ECS task"
  type        = string
  default     = "fastapi-aws-backend:latest"
}

variable "container_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8000
}

variable "domain_name" {
  description = "Domain name for the application (optional)"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS (required if domain_name is set)"
  type        = string
  default     = ""
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "RDS max allocated storage for autoscaling"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "fastapi_app"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "postgres"
}

variable "db_password" {
  description = "PostgreSQL master password"
  type        = string
  sensitive   = true
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 1
}

variable "lambda_runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.12"
}

variable "lambda_memory_size" {
  description = "Lambda memory in MB"
  type        = number
  default     = 128
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 30
}

variable "log_retention_in_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "enable_signoz" {
  description = "Whether to deploy SigNoz infrastructure"
  type        = bool
  default     = true
}

variable "terraform_state_bucket" {
  description = "S3 bucket for Terraform state"
  type        = string
  default     = "fastapi-terraform-state"
}

variable "terraform_state_key" {
  description = "S3 key for Terraform state"
  type        = string
  default     = "terraform/terraform.tfstate"
}

variable "terraform_state_region" {
  description = "AWS region for Terraform state bucket"
  type        = string
  default     = "us-east-1"
}

variable "terraform_state_dynamodb_table" {
  description = "DynamoDB table for Terraform state locking"
  type        = string
  default     = "fastapi-terraform-locks"
}
