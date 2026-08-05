resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-cache-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${local.name_prefix}-cache-subnet-group"
  }
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id         = "${local.name_prefix}-redis-${var.unique_suffix}"
  description                  = "Redis cluster for ${var.project_name}"
  engine                       = "redis"
  engine_version               = "7.1"
  node_type                    = var.node_type
  num_cache_clusters           = var.num_cache_nodes
  subnet_group_name            = aws_elasticache_subnet_group.main.name
  security_group_ids           = [var.cache_security_group_id]
  automatic_failover_enabled   = var.num_cache_nodes > 1
  multi_az_enabled             = var.environment == "production"
  at_rest_encryption_enabled   = true
  transit_encryption_enabled   = true
  auth_token                   = var.environment != "development" ? random_password.redis_auth[0].result : null
  snapshot_retention_limit     = var.environment == "production" ? 7 : 1
  snapshot_window              = "05:00-06:00"
  maintenance_window           = "sun:06:00-sun:07:00"
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis.name
    destination_type = "cloudwatch-logs"
    log_format       = "text"
    log_type         = "slow-log"
  }

  tags = {
    Name = "${local.name_prefix}-redis"
  }
}

resource "random_password" "redis_auth" {
  count   = var.environment != "development" ? 1 : 0
  length  = 32
  special = false
}

resource "aws_cloudwatch_log_group" "redis" {
  name              = "/aws/elasticache/${local.name_prefix}-redis"
  retention_in_days = var.log_retention_in_days

  tags = {
    Name = "${local.name_prefix}-redis-logs"
  }
}

output "redis_cluster_id" {
  value = aws_elasticache_replication_group.main.id
}

output "redis_endpoint" {
  value = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "redis_port" {
  value = aws_elasticache_replication_group.main.port
}

output "redis_auth_token" {
  value     = var.environment != "development" ? random_password.redis_auth[0].result : null
  sensitive = true
}
