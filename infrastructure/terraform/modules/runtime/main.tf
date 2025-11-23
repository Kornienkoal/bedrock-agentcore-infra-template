# Runtime Module - Execution Environment
#
# Provisions IAM roles, CloudWatch Logs, and X-Ray tracing for agent runtime.
# Implements: FR-001 (runtime component), FR-007 (least privilege), Constitution IV (per-agent role)

terraform {
  required_version = ">= 1.9.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.62"
    }
  }
}

# Import shared locals
module "shared" {
  source          = "../_shared"
  agent_namespace = var.agent_namespace
  environment     = var.environment
  component       = "runtime"
  common_tags     = var.tags
}

# Data: Current AWS region and account
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# Gateway identifier resolved from shared SSM configuration
data "aws_ssm_parameter" "gateway_id" {
  name = "/agentcore/${var.environment}/gateway/gateway_id"
}

# IAM Role for Agent Execution
resource "aws_iam_role" "execution" {
  name               = "${module.shared.name_prefix}-execution-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json

  tags = merge(
    module.shared.common_tags,
    {
      Name = "${module.shared.name_prefix}-execution-role"
    }
  )
}

# Assume role policy for Bedrock Agents, AgentCore, and Lambda
data "aws_iam_policy_document" "assume_role" {
  # Allow Bedrock service to assume this role (for agents deployed via SDK)
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  # Allow Bedrock AgentCore service to assume this role (for containerized agents)
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  # Also allow Lambda for backward compatibility
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

# Bedrock model invocation policy (least privilege)
resource "aws_iam_role_policy" "bedrock_invoke" {
  name   = "bedrock-invoke"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.bedrock_invoke.json
}

data "aws_iam_policy_document" "bedrock_invoke" {
  statement {
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream"
    ]
    # Scoped to specific model families (Claude/Titan)
    # Note: Bedrock foundation model ARNs use wildcards by design since model versions change
    # Pattern "anthropic.claude-*" is the most specific scope AWS allows for model families
    resources = [
      "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/anthropic.claude-*",
      "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/amazon.titan-*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream"
    ]
    # Allow cross-region invocation for inference profiles backed by us-west-2 Claude models
    resources = [
      "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-*",
      "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream"
    ]
    # Allow cross-region invocation when inference profiles route to us-east-2 Claude endpoints
    resources = [
      "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-*",
      "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream"
    ]
    # Allow invocation of approved inference profiles (Claude family only)
    resources = [
      "arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:inference-profile/us.anthropic.claude-*"
    ]
  }
}

# SSM Parameter Store read access (scoped to agentcore paths)
resource "aws_iam_role_policy" "ssm_read" {
  name   = "ssm-read"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.ssm_read.json
}

data "aws_iam_policy_document" "ssm_read" {
  statement {
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath"
    ]
    resources = [
      "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/agentcore/${var.environment}/*"
    ]
  }
}

# CloudWatch Logs permissions
resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# X-Ray tracing permissions (if enabled)
resource "aws_iam_role_policy_attachment" "xray" {
  count      = var.xray_tracing_enabled ? 1 : 0
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# Bedrock Gateway invocation policy
resource "aws_iam_role_policy" "bedrock_gateway" {
  name   = "bedrock-gateway-invoke"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.bedrock_gateway.json
}

data "aws_iam_policy_document" "bedrock_gateway" {
  statement {
    effect = "Allow"
    actions = [
      "bedrock-agent:InvokeAgentGateway",
      "bedrock-agent:GetAgentGateway"
    ]
    resources = [
      "arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:agent-gateway/*"
    ]

    # Restrict to specific environment
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Environment"
      values   = [var.environment]
    }
  }

  statement {
    effect = "Allow"
    actions = [
      "bedrock-agentcore:GetGateway"
    ]
    resources = [
      "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:gateway/${data.aws_ssm_parameter.gateway_id.value}"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "bedrock-agentcore-control:GetGateway"
    ]
    resources = [
      "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:gateway/${data.aws_ssm_parameter.gateway_id.value}"
    ]
  }
}

# Bedrock Memory access policy
resource "aws_iam_role_policy" "bedrock_memory" {
  name   = "bedrock-memory-access"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.bedrock_memory.json
}

data "aws_iam_policy_document" "bedrock_memory" {
  statement {
    effect = "Allow"
    actions = [
      "bedrock-agentcore:CreateEvent",
      "bedrock-agentcore:GetEvent",
      "bedrock-agentcore:GetMemory",
      "bedrock-agentcore:GetMemoryRecord",
      "bedrock-agentcore:ListMemoryRecords",
      "bedrock-agentcore:QueryMemory"
    ]
    resources = [
      "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:memory/*"
    ]
  }
}

# Lambda tool invocation policy (for calling shared tools)
resource "aws_iam_role_policy" "lambda_invoke" {
  name   = "lambda-invoke-tools"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.lambda_invoke.json
}

data "aws_iam_policy_document" "lambda_invoke" {
  statement {
    effect = "Allow"
    actions = [
      "lambda:InvokeFunction"
    ]
    resources = [
      "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${var.agent_namespace}-*-tool-*"
    ]
  }
}

# ECR image pull policy (for containerized AgentCore runtime)
resource "aws_iam_role_policy" "ecr_pull" {
  name   = "ecr-pull-images"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.ecr_pull.json
}

data "aws_iam_policy_document" "ecr_pull" {
  statement {
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken"
    ]
    resources = ["*"] # GetAuthorizationToken doesn't support resource-level permissions
  }

  statement {
    effect = "Allow"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer"
    ]
    resources = [
      "arn:aws:ecr:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:repository/bedrock-agentcore-*"
    ]
  }
}

# CloudWatch Log Group for runtime logs
resource "aws_cloudwatch_log_group" "runtime" {
  name              = "/aws/lambda/${module.shared.name_prefix}"
  retention_in_days = var.log_retention_days

  tags = merge(
    module.shared.common_tags,
    {
      Name = "/aws/lambda/${module.shared.name_prefix}"
    }
  )
}
