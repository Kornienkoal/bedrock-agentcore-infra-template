# Memory Module - Bedrock AgentCore Memory via Custom Resource
#
# Provisions native Bedrock AgentCore Memory service with short/long/semantic strategies.
# Implements: FR-001 (memory component), Constitution I (AWS Native Services First)

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
  component       = "memory"
  common_tags     = var.tags
}

# Data sources
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  resolved_embedding_model_arn = var.embedding_model_arn != "" ? var.embedding_model_arn : "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/amazon.titan-embed-*"
}

# ============================================================================
# Lambda Custom Resource Provisioner
# ============================================================================

# Lambda function with automatic dependency bundling
module "memory_provisioner_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 7.0"

  function_name = "${module.shared.name_prefix}-provisioner"
  description   = "Bedrock AgentCore Memory provisioner"
  handler       = "lambda_function.handler"
  runtime       = "python3.13"
  timeout       = 180

  source_path = "${path.module}/../../custom-resources/agentcore-memory"

  # Automatically install requirements.txt during build
  build_in_docker = false

  environment_variables = {
    LOG_LEVEL               = "INFO"
    POWERTOOLS_SERVICE_NAME = "agentcore-memory-provisioner"
  }

  tracing_mode = "Active"

  cloudwatch_logs_retention_in_days = 7

  # Use existing IAM role
  create_role = false
  lambda_role = aws_iam_role.memory_provisioner.arn

  tags = module.shared.common_tags
}

# IAM Role for Lambda provisioner
resource "aws_iam_role" "memory_provisioner" {
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
  role       = aws_iam_role.memory_provisioner.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# IAM policy for provisioner to manage Bedrock Memory
resource "aws_iam_role_policy" "provisioner_bedrock" {
  name = "${module.shared.name_prefix}-bedrock-memory"
  role = aws_iam_role.memory_provisioner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:CreateMemory",
          "bedrock-agentcore:GetMemory",
          "bedrock-agentcore:UpdateMemory",
          "bedrock-agentcore:DeleteMemory",
          "bedrock-agentcore:ListMemories",
          "bedrock-agentcore:TagResource"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = local.resolved_embedding_model_arn
      }
    ]
  })
}

# IAM policy for provisioner to manage SSM parameters
resource "aws_iam_role_policy" "provisioner_ssm" {
  name = "${module.shared.name_prefix}-ssm"
  role = aws_iam_role.memory_provisioner.id

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
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/agentcore/${var.environment}/memory/*"
      }
    ]
  })
}

# IAM policy for X-Ray tracing
resource "aws_iam_role_policy" "provisioner_xray" {
  name = "${module.shared.name_prefix}-xray"
  role = aws_iam_role.memory_provisioner.id

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
# Invoke Custom Resource to Create Bedrock Memory
# ============================================================================

resource "null_resource" "memory_provisioning" {
  triggers = {
    memory_name          = module.shared.agentcore_name_prefix
    environment          = var.environment
    agent_namespace      = var.agent_namespace
    event_expiry_days    = var.event_expiry_days
    short_term_ttl       = tostring(var.short_term_ttl_seconds)
    long_term_retention  = var.long_term_retention
    embedding_model_arn  = local.resolved_embedding_model_arn
    max_tokens           = tostring(var.max_tokens)
    enabled_strategies   = sha1(jsonencode(var.enabled_strategies))
    lambda_version       = module.memory_provisioner_lambda.lambda_function_source_code_hash
    lambda_function_name = module.memory_provisioner_lambda.lambda_function_name
    region               = data.aws_region.current.name
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws lambda invoke \
        --function-name ${module.memory_provisioner_lambda.lambda_function_name} \
        --cli-binary-format raw-in-base64-out \
        --payload '${jsonencode({
    RequestType = "Create"
    ResourceProperties = {
      MemoryName          = module.shared.agentcore_name_prefix
      Environment         = var.environment
      AgentNamespace      = var.agent_namespace
      SSMPrefix           = "/agentcore/${var.environment}/memory"
      EventExpiryDays     = var.event_expiry_days
      ShortTermTTLSeconds = var.short_term_ttl_seconds
      LongTermRetention   = var.long_term_retention
      EnabledStrategies   = var.enabled_strategies
      EmbeddingModelArn   = local.resolved_embedding_model_arn
      MaxTokens           = var.max_tokens
    }
    StackId           = "terraform-${var.agent_namespace}-${var.environment}"
    RequestId         = "terraform-memory-${formatdate("YYYYMMDDhhmmss", timestamp())}"
    LogicalResourceId = "BedrockMemory"
    ResponseURL       = ""
})}' \
        --region ${data.aws_region.current.name} \
        /tmp/memory_response.json
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
  PhysicalResourceId = self.triggers.memory_name
  ResourceProperties = {
    MemoryName     = self.triggers.memory_name
    Environment    = self.triggers.environment
    AgentNamespace = self.triggers.agent_namespace
    SSMPrefix      = "/agentcore/${self.triggers.environment}/memory"
  }
  StackId           = "terraform-${self.triggers.agent_namespace}-${self.triggers.environment}"
  RequestId         = "terraform-memory-delete-${formatdate("YYYYMMDDhhmmss", timestamp())}"
  LogicalResourceId = "BedrockMemory"
  ResponseURL       = ""
})}' \
        --region ${self.triggers.region} \
        /tmp/memory_delete_response.json || true
    EOT
}

depends_on = [
  module.memory_provisioner_lambda
]
}

# ============================================================================
# IAM Policy for Agent Access to Memory
# ============================================================================

# Create IAM policy document for agent roles to access Bedrock Memory
data "aws_iam_policy_document" "memory_access" {
  statement {
    effect = "Allow"
    actions = [
      "bedrock-agentcore:GetMemory",
      "bedrock-agentcore:PutMemory",
      "bedrock-agentcore:DeleteMemory",
      "bedrock-agentcore:QueryMemory"
    ]
    resources = [
      "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:memory/*"
    ]

    # Restrict to specific environment
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Environment"
      values   = [var.environment]
    }
  }

  # Access to embedding models for semantic memory
  dynamic "statement" {
    for_each = contains(var.enabled_strategies, "SEMANTIC") ? [1] : []

    content {
      effect = "Allow"
      actions = [
        "bedrock:InvokeModel"
      ]
      resources = [
        "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/amazon.titan-embed-*"
      ]
    }
  }
}

# Create managed policy
resource "aws_iam_policy" "memory_access" {
  name        = "${module.shared.name_prefix}-access-policy"
  description = "IAM policy for agent access to Bedrock Memory"
  policy      = data.aws_iam_policy_document.memory_access.json

  tags = module.shared.common_tags
}
