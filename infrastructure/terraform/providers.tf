variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
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

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  backend "s3" {
    bucket         = var.terraform_state_bucket
    key            = var.terraform_state_key
    region         = var.terraform_state_region
    encrypt        = true
    dynamodb_table = var.terraform_state_dynamodb_table
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Generate random suffix for unique resource names
resource "random_id" "suffix" {
  byte_length = 2
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  unique_suffix = random_id.suffix.hex
}
