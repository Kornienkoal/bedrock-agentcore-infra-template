# Gateway Module - Bedrock AgentCore Gateway via Custom Resource
#
# Provisions native Bedrock AgentCore Gateway via Lambda custom resource.
# Implements: FR-001 (gateway component), Constitution I (AWS Native Services First)

terraform {
  required_version = ">= 1.9.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.62"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

# Import shared locals
module "shared" {
  source          = "../_shared"
  agent_namespace = var.agent_namespace
  environment     = var.environment
  component       = "gateway"
  common_tags     = var.tags
}

# Data sources
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# ============================================================================
# IAM Role for Bedrock Gateway
# ============================================================================

resource "aws_iam_role" "gateway_role" {
  name = "${module.shared.name_prefix}-gateway-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = module.shared.common_tags
}

# IAM policy for Gateway to invoke Lambda tools
resource "aws_iam_role_policy" "gateway_lambda_invoke" {
  name = "${module.shared.name_prefix}-lambda-invoke"
  role = aws_iam_role.gateway_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${var.agent_namespace}-*-tool-*"
        ]
      }
    ]
  })
}

# ============================================================================
# Lambda Custom Resource Provisioner
# ============================================================================

# Lambda function with automatic dependency bundling
module "gateway_provisioner_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 7.0"

  function_name = "${module.shared.name_prefix}-provisioner"
  description   = "Bedrock AgentCore Gateway provisioner"
  handler       = "lambda_function.handler"
  runtime       = "python3.13"
  timeout       = 60

  source_path = "${path.module}/../../custom-resources/agentcore-gateway"

  # Automatically install requirements.txt during build
  build_in_docker = false

  environment_variables = {
    LOG_LEVEL               = "INFO"
    POWERTOOLS_SERVICE_NAME = "agentcore-gateway-provisioner"
  }

  tracing_mode = "Active"

  cloudwatch_logs_retention_in_days = 7

  # Use existing IAM role
  create_role = false
  lambda_role = aws_iam_role.gateway_provisioner.arn

  tags = module.shared.common_tags
}

# IAM Role for Lambda provisioner
resource "aws_iam_role" "gateway_provisioner" {
  name = "${module.shared.name_prefix}-provisioner-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = module.shared.common_tags
}

# Attach basic execution policy
resource "aws_iam_role_policy_attachment" "provisioner_basic" {
  role       = aws_iam_role.gateway_provisioner.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# IAM policy for provisioner to manage Bedrock Gateway
resource "aws_iam_role_policy" "provisioner_bedrock" {
  name = "${module.shared.name_prefix}-bedrock-gateway"
  role = aws_iam_role.gateway_provisioner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:CreateGateway",
          "bedrock-agentcore:GetGateway",
          "bedrock-agentcore:UpdateGateway",
          "bedrock-agentcore:DeleteGateway",
          "bedrock-agentcore:ListGateways",
          "bedrock-agentcore:ListGatewayTargets",
          "bedrock-agentcore:DeleteGatewayTarget",
          "bedrock-agentcore:CreateWorkloadIdentity",
          "bedrock-agentcore:TagResource"
        ]
        Resource = "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = aws_iam_role.gateway_role.arn
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "bedrock-agentcore.amazonaws.com"
          }
        }
      }
    ]
  })
}

# IAM policy for provisioner to manage SSM parameters
resource "aws_iam_role_policy" "provisioner_ssm" {
  name = "${module.shared.name_prefix}-ssm"
  role = aws_iam_role.gateway_provisioner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:PutParameter",
          "ssm:GetParameter",
          "ssm:DeleteParameter",
          "ssm:AddTagsToResource"
        ]
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/agentcore/${var.environment}/gateway/*"
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/agentcore/${var.environment}/identity/*"
      }
    ]
  })
}

# IAM policy for X-Ray tracing
resource "aws_iam_role_policy" "provisioner_xray" {
  name = "${module.shared.name_prefix}-xray"
  role = aws_iam_role.gateway_provisioner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

# ============================================================================
# Invoke Custom Resource to Create Bedrock Gateway
# ============================================================================

resource "null_resource" "gateway_provisioning" {
  triggers = {
    gateway_name         = module.shared.agentcore_name_prefix
    gateway_role_arn     = aws_iam_role.gateway_role.arn
    environment          = var.environment
    agent_namespace      = var.agent_namespace
    lambda_version       = module.gateway_provisioner_lambda.lambda_function_source_code_hash
    lambda_function_name = module.gateway_provisioner_lambda.lambda_function_name
    region               = data.aws_region.current.name
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws lambda invoke \
        --function-name ${module.gateway_provisioner_lambda.lambda_function_name} \
        --cli-binary-format raw-in-base64-out \
        --payload '${jsonencode({
    RequestType = "Create"
    ResourceProperties = {
      GatewayName    = module.shared.agentcore_name_prefix
      GatewayRoleArn = aws_iam_role.gateway_role.arn
      Environment    = var.environment
      AgentNamespace = var.agent_namespace
      SSMPrefix      = "/agentcore/${var.environment}/gateway"
    }
    StackId           = "terraform-${var.agent_namespace}-${var.environment}"
    RequestId         = "terraform-gateway-${formatdate("YYYYMMDDhhmmss", timestamp())}"
    LogicalResourceId = "BedrockGateway"
    ResponseURL       = ""
})}' \
        --region ${data.aws_region.current.name} \
        /tmp/gateway_response.json
    EOT
}

provisioner "local-exec" {
  when = destroy
  command = <<-EOT
      aws lambda invoke \
        --function-name ${self.triggers.lambda_function_name} \
        --cli-binary-format raw-in-base64-out \
        --payload '${jsonencode({
  RequestType        = "Delete"
  PhysicalResourceId = self.triggers.gateway_name
  ResourceProperties = {
    GatewayName    = self.triggers.gateway_name
    Environment    = self.triggers.environment
    AgentNamespace = self.triggers.agent_namespace
    SSMPrefix      = "/agentcore/${self.triggers.environment}/gateway"
  }
  StackId           = "terraform-${self.triggers.agent_namespace}-${self.triggers.environment}"
  RequestId         = "terraform-gateway-delete-${formatdate("YYYYMMDDhhmmss", timestamp())}"
  LogicalResourceId = "BedrockGateway"
  ResponseURL       = ""
})}' \
        --region ${self.triggers.region} \
        /tmp/gateway_delete_response.json || true
    EOT
}

depends_on = [
  module.gateway_provisioner_lambda,
  aws_iam_role.gateway_role
]
}
