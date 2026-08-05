# ──────────────────────────────────────────────────────────────────────────────
# Networking
# ──────────────────────────────────────────────────────────────────────────────
module "vpc" {
  source = "./modules/vpc"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  unique_suffix      = local.unique_suffix
}

# ──────────────────────────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────────────────────────
module "rds" {
  source = "./modules/rds"

  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnet_ids
  db_security_group_id  = module.vpc.db_security_group_id
  instance_class        = var.db_instance_class
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  db_name               = var.db_name
  db_username           = var.db_username
  db_password           = var.db_password
  log_retention_in_days = var.log_retention_in_days
  unique_suffix         = local.unique_suffix
}

# ──────────────────────────────────────────────────────────────────────────────
# Cache
# ──────────────────────────────────────────────────────────────────────────────
module "redis" {
  source = "./modules/redis"

  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnet_ids
  cache_security_group_id = module.vpc.cache_security_group_id
  node_type             = var.redis_node_type
  num_cache_nodes       = var.redis_num_cache_nodes
  log_retention_in_days = var.log_retention_in_days
  unique_suffix         = local.unique_suffix
}

# ──────────────────────────────────────────────────────────────────────────────
# Storage
# ──────────────────────────────────────────────────────────────────────────────
module "s3" {
  source = "./modules/s3"

  project_name = var.project_name
  environment  = var.environment
  unique_suffix = local.unique_suffix
}

# ──────────────────────────────────────────────────────────────────────────────
# NoSQL
# ──────────────────────────────────────────────────────────────────────────────
module "dynamodb" {
  source = "./modules/dynamodb"

  project_name = var.project_name
  environment  = var.environment
  unique_suffix = local.unique_suffix
}

# ──────────────────────────────────────────────────────────────────────────────
# Queues
# ──────────────────────────────────────────────────────────────────────────────
module "sqs" {
  source = "./modules/sqs"

  project_name = var.project_name
  environment  = var.environment
  unique_suffix = local.unique_suffix
}

# ──────────────────────────────────────────────────────────────────────────────
# Notifications
# ──────────────────────────────────────────────────────────────────────────────
module "sns" {
  source = "./modules/sns"

  project_name = var.project_name
  environment  = var.environment
  unique_suffix = local.unique_suffix
  sqs_queue_arn = module.sqs.queue_arn
}

# ──────────────────────────────────────────────────────────────────────────────
# IAM
# ──────────────────────────────────────────────────────────────────────────────
module "iam" {
  source = "./modules/iam"

  project_name = var.project_name
  environment  = var.environment
  unique_suffix = local.unique_suffix

  s3_bucket_arn       = module.s3.bucket_arn
  dynamodb_table_arn  = module.dynamodb.table_arn
  sqs_queue_arn       = module.sqs.queue_arn
  sns_topic_arn       = module.sns.topic_arn
  cloudwatch_log_group_arn = module.cloudwatch.log_group_arn
}

# ──────────────────────────────────────────────────────────────────────────────
# Lambda
# ──────────────────────────────────────────────────────────────────────────────
module "lambda" {
  source = "./modules/lambda"

  project_name           = var.project_name
  environment            = var.environment
  unique_suffix          = local.unique_suffix
  lambda_role_arn        = module.iam.lambda_execution_role_arn
  lambda_security_group_id = module.vpc.lambda_security_group_id
  private_subnet_ids     = module.vpc.private_subnet_ids
  s3_bucket_name         = module.s3.bucket_id
  s3_bucket_arn          = module.s3.bucket_arn
  sqs_queue_arn          = module.sqs.queue_arn
  sqs_queue_url          = module.sqs.queue_url
  sns_topic_arn          = module.sns.topic_arn
  cloudwatch_log_group_arn = module.cloudwatch.log_group_arn
  runtime                = var.lambda_runtime
  memory_size            = var.lambda_memory_size
  timeout                = var.lambda_timeout
  log_retention_in_days  = var.log_retention_in_days
}

# ──────────────────────────────────────────────────────────────────────────────
# ECS / FastAPI App
# ──────────────────────────────────────────────────────────────────────────────
module "ecs" {
  source = "./modules/ecs"

  project_name              = var.project_name
  environment               = var.environment
  unique_suffix             = local.unique_suffix
  vpc_id                    = module.vpc.vpc_id
  public_subnet_ids         = module.vpc.public_subnet_ids
  private_subnet_ids        = module.vpc.private_subnet_ids
  app_security_group_id     = module.vpc.app_security_group_id
  alb_security_group_id     = module.vpc.alb_security_group_id
  ecs_task_role_arn         = module.iam.ecs_task_role_arn
  ecs_execution_role_arn    = module.iam.ecs_execution_role_arn
  container_image           = var.container_image
  container_port            = var.container_port
  rds_endpoint              = module.rds.db_instance_endpoint
  redis_endpoint            = module.redis.redis_endpoint
  s3_bucket_name            = module.s3.bucket_id
  dynamodb_table_name       = module.dynamodb.table_name
  sqs_queue_url             = module.sqs.queue_url
  sns_topic_arn             = module.sns.topic_arn
  cloudwatch_log_group_arn  = module.cloudwatch.log_group_arn
  log_retention_in_days     = var.log_retention_in_days
  desired_count             = var.environment == "production" ? 3 : 1
}

# ──────────────────────────────────────────────────────────────────────────────
# Load Balancer
# ──────────────────────────────────────────────────────────────────────────────
module "alb" {
  source = "./modules/alb"

  project_name           = var.project_name
  environment            = var.environment
  vpc_id                 = module.vpc.vpc_id
  public_subnet_ids      = module.vpc.public_subnet_ids
  alb_security_group_id  = module.vpc.alb_security_group_id
  ecs_target_group_arn   = module.ecs.target_group_arn
  domain_name            = var.domain_name
  certificate_arn        = var.certificate_arn
  unique_suffix          = local.unique_suffix
}

# ──────────────────────────────────────────────────────────────────────────────
# CloudWatch
# ──────────────────────────────────────────────────────────────────────────────
module "cloudwatch" {
  source = "./modules/cloudwatch"

  project_name           = var.project_name
  environment            = var.environment
  unique_suffix          = local.unique_suffix
  alb_arn_suffix         = module.alb.alb_arn_suffix
  ecs_service_name       = module.ecs.service_name
  lambda_function_name   = module.lambda.lambda_function_name
  rds_instance_id        = module.rds.db_instance_id
  redis_cluster_id       = module.redis.redis_cluster_id
}

# ──────────────────────────────────────────────────────────────────────────────
# SigNoz (Optional)
# ──────────────────────────────────────────────────────────────────────────────
module "signoz" {
  count   = var.enable_signoz ? 1 : 0
  source  = "./modules/signoz"

  project_name           = var.project_name
  environment            = var.environment
  vpc_id                 = module.vpc.vpc_id
  private_subnet_ids     = module.vpc.private_subnet_ids
  signoz_security_group_id = module.vpc.signoz_security_group_id
  unique_suffix          = local.unique_suffix
}
