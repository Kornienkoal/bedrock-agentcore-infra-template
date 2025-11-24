terraform {
  required_version = ">= 1.9.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.62"
    }
  }
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project_name}-frontend-gateway-${var.environment}"
  base_tags = merge(
    var.tags,
    {
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  )
}

# Lambda Function
module "lambda_function" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 7.0"

  function_name = local.name_prefix
  description   = "Frontend Gateway for Bedrock AgentCore"
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.13"
  timeout       = 30
  memory_size   = 256

  # Source path relative to this module
  source_path = "${path.module}/../../../../services/frontend-gateway"

  # Build in Docker to ensure linux-compatible dependencies
  build_in_docker           = true
  docker_additional_options = ["--platform=linux/amd64"]
  hash_extra                = "linux-amd64"

  environment_variables = {
    LOG_LEVEL               = "INFO"
    COGNITO_USER_POOL_ID    = var.cognito_user_pool_id
    COGNITO_CLIENT_ID       = var.cognito_client_id
    POWERTOOLS_SERVICE_NAME = "frontend-gateway"
  }

  tracing_mode          = "Active"
  attach_tracing_policy = true

  attach_policy_json = true
  policy_json = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "bedrock-agentcore:InvokeAgentRuntime",
          "bedrock-agentcore:InvokeAgentRuntimeForUser",
          "bedrock-agentcore:ListAgentRuntimes"
        ],
        # Note: Wildcard resource is required because bedrock-agentcore actions
        # do not support resource-level permissions. ARN-based filtering is not
        # available for these API operations per AWS service limitations.
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ],
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/agentcore/${var.environment}/*"
      }
    ]
  })

  tags = local.base_tags
}

# API Gateway (HTTP API)
resource "aws_apigatewayv2_api" "this" {
  name          = local.name_prefix
  protocol_type = "HTTP"
  tags = merge(local.base_tags, {
    Component = "FrontendGateway"
    AgentCore = "FrontendGateway"
  })
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
  tags = merge(local.base_tags, {
    Component = "FrontendGateway"
    AgentCore = "FrontendGateway"
  })
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = aws_apigatewayv2_api.this.id
  integration_type = "AWS_PROXY"

  connection_type        = "INTERNET"
  description            = "Lambda integration"
  integration_method     = "POST"
  integration_uri        = module.lambda_function.lambda_function_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "any" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_function.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

# SSM Parameter for API Endpoint
resource "aws_ssm_parameter" "api_endpoint" {
  name  = "/agentcore/${var.environment}/frontend-gateway/api_endpoint"
  type  = "String"
  value = aws_apigatewayv2_api.this.api_endpoint
  tags = merge(local.base_tags, {
    Component = "FrontendGateway"
    AgentCore = "FrontendGateway"
  })
}
