locals {
  name_prefix = var.name_prefix
}

data "archive_file" "lambda" {
  type        = "zip"
  output_path = "${path.module}/lambda_function.zip"

  source {
    content  = file("${path.module}/lambda_function.py")
    filename = "lambda_function.py"
  }
}

resource "aws_lambda_function" "main" {
  function_name    = "${local.name_prefix}-lambda-${var.unique_suffix}"
  role             = var.lambda_role_arn
  runtime          = var.runtime
  handler          = "lambda_function.handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = var.timeout
  memory_size      = var.memory_size

  vpc_config {
    security_group_ids = [var.lambda_security_group_id]
    subnet_ids         = var.private_subnet_ids
  }

  environment {
    variables = {
      AWS_REGION            = data.aws_region.current.name
      S3_BUCKET            = var.s3_bucket_name
      DYNAMODB_TABLE       = var.dynamodb_table_name
      SQS_QUEUE_URL        = var.sqs_queue_url
      SNS_TOPIC_ARN        = var.sns_topic_arn
      CLOUDWATCH_LOG_GROUP = var.cloudwatch_log_group_arn
    }
  }

  tags = {
    Name = "${local.name_prefix}-lambda"
  }
}

# CloudWatch Logs for Lambda
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.main.function_name}"
  retention_in_days = var.log_retention_in_days

  tags = {
    Name = "${local.name_prefix}-lambda-logs"
  }
}

# API Gateway for Lambda
resource "aws_apigatewayv2_api" "lambda" {
  name          = "${local.name_prefix}-api-${var.unique_suffix}"
  protocol_type = "HTTP"

  tags = {
    Name = "${local.name_prefix}-api"
  }
}

resource "aws_apigatewayv2_stage" "lambda" {
  api_id      = aws_apigatewayv2_api.lambda.id
  name        = var.environment
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = aws_apigatewayv2_api.lambda.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.main.arn
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.lambda.id
  route_key = "POST /"
}

resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.lambda.id
  route_key = "ANY /{proxy+}"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.lambda.execution_arn}/*/*"
}

output "lambda_function_arn" {
  value = aws_lambda_function.main.arn
}

output "lambda_function_name" {
  value = aws_lambda_function.main.function_name
}

output "api_gateway_url" {
  value = "${aws_apigatewayv2_stage.lambda.invoke_url}/"
}
