locals {
  name_prefix = var.name_prefix
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${local.name_prefix}-db-subnet-group"
  }
}

resource "aws_db_instance" "main" {
  identifier             = "${local.name_prefix}-db-${var.unique_suffix}"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = var.instance_class
  allocated_storage      = var.allocated_storage
  max_allocated_storage  = var.max_allocated_storage
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.db_security_group_id]

  multi_az               = var.environment == "production" ? true : false
  storage_encrypted      = true
  storage_type           = "gp3"
  backup_retention_period = var.environment == "production" ? 7 : 1
  skip_final_snapshot    = var.environment != "production"
  final_snapshot_identifier = "${local.name_prefix}-db-final-${var.unique_suffix}"

  enabled_cloudwatch_logs_exports = ["postgresql"]
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn

  tags = {
    Name = "${local.name_prefix}-rds"
  }
}

resource "aws_secretsmanager_secret" "db_password" {
  name_prefix = "${local.name_prefix}-db-password-"
  description = "Database password for ${local.name_prefix}"

  tags = {
    Name = "${local.name_prefix}-db-password"
  }
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = var.db_password
}

resource "aws_iam_role" "rds_monitoring" {
  name = "${local.name_prefix}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

resource "aws_db_parameter_group" "main" {
  family = "postgres16"
  name   = "${local.name_prefix}-db-params"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_statement"
    value = "all"
  }
}

resource "aws_db_option_group" "main" {
  name                 = "${local.name_prefix}-db-options"
  option_group_description = "Option group for PostgreSQL"
  engine_name          = "postgres"
  major_engine_version = "16"
}

output "db_instance_id" {
  value = aws_db_instance.main.id
}

output "db_instance_endpoint" {
  value = aws_db_instance.main.endpoint
}

output "db_instance_address" {
  value = aws_db_instance.main.address
}

output "db_instance_port" {
  value = aws_db_instance.main.port
}

output "db_subnet_group_name" {
  value = aws_db_subnet_group.main.name
}

output "db_password_secret_arn" {
  value = aws_secretsmanager_secret.db_password.arn
}
