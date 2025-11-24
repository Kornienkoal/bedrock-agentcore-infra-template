# Tools Module - Global MCP Tools (Lambdas) + Gateway Target Registration

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
  component       = "tools"
  common_tags     = var.tags
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# Normalize tools map keyed by name for stable addressing
locals {
  repo_root     = abspath("${path.module}/../../../..")
  tools_by_name = { for t in var.tools : t.name => t }
}

# ============================================================================
# Deploy Tool Lambdas
# ============================================================================

module "tool_lambdas" {
  for_each = local.tools_by_name

  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 7.0"

  function_name = "${var.agent_namespace}-${each.key}-tool-${var.environment}"
  description   = coalesce(lookup(each.value, "description", null), "AgentCore global tool: ${each.key}")
  handler       = coalesce(lookup(each.value, "handler", null), "lambda_function.handler")
  runtime       = "python3.13"
  timeout       = coalesce(lookup(each.value, "timeout", null), 15)
  memory_size   = coalesce(lookup(each.value, "memory_size", null), 256)

  # Source path relative to root module
  source_path = "${local.repo_root}/${each.value.source_dir}"

  environment_variables = merge(
    {
      LOG_LEVEL               = "INFO"
      POWERTOOLS_SERVICE_NAME = "tool-${each.key}"
    },
    lookup(each.value, "environment", {})
  )

  # Observability
  tracing_mode                      = "Active"
  attach_tracing_policy             = true
  cloudwatch_logs_retention_in_days = 7
  attach_cloudwatch_logs_policy     = true

  # IAM role is auto-created with basic perms via module
  create_role = true

  tags = merge(module.shared.common_tags, { "ToolName" = each.key })
}

# ============================================================================
# Gateway Targets Registration - Custom Resource Lambda
# ============================================================================

# IAM role for registration Lambda
resource "aws_iam_role" "targets_provisioner" {
  name = "${module.shared.name_prefix}-targets-provisioner-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect    = "Allow",
        Principal = { Service = "lambda.amazonaws.com" },
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = module.shared.common_tags
}

resource "aws_iam_role_policy_attachment" "targets_basic" {
  role       = aws_iam_role.targets_provisioner.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "targets_bedrock" {
  name = "${module.shared.name_prefix}-targets-bedrock"
  role = aws_iam_role.targets_provisioner.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "bedrock-agentcore:CreateGatewayTarget",
          "bedrock-agentcore:GetGatewayTarget",
          "bedrock-agentcore:UpdateGatewayTarget",
          "bedrock-agentcore:ListGatewayTargets",
          "bedrock-agentcore:DeleteGatewayTarget",
          "bedrock-agentcore:TagResource"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "targets_ssm" {
  name = "${module.shared.name_prefix}-targets-ssm"
  role = aws_iam_role.targets_provisioner.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = ["ssm:GetParameter", "ssm:GetParameters"],
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/agentcore/${var.environment}/gateway/*"
      }
    ]
  })
}

# Registration Lambda from custom-resources source
module "targets_provisioner" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 7.0"

  function_name = "${module.shared.name_prefix}-targets-provisioner"
  description   = "Register/update Bedrock Gateway Targets (MCP tools)"
  handler       = "lambda_function.handler"
  runtime       = "python3.13"
  timeout       = 60

  source_path = "${path.module}/../../custom-resources/agentcore-gateway-targets"

  build_in_docker = false

  environment_variables = {
    LOG_LEVEL               = "INFO"
    POWERTOOLS_SERVICE_NAME = "agentcore-gateway-targets"
  }

  tracing_mode = "Active"

  cloudwatch_logs_retention_in_days = 7

  create_role = false
  lambda_role = aws_iam_role.targets_provisioner.arn

  tags = module.shared.common_tags
}

# ============================================================================
# Invoke Registration Lambda via local-exec
# ============================================================================

locals {
  registration_tools = [
    for t in var.tools : {
      # Use the actual MCP tool name from tool-schema.json instead of directory name
      # Directory names use underscores (check_warranty), but MCP names use hyphens (check-warranty-status)
      # AWS Gateway Target API requires names matching pattern: ([0-9a-zA-Z][-]?){1,100}
      name      = jsondecode(file("${local.repo_root}/${t.source_dir}/tool-schema.json")).name
      lambdaArn = module.tool_lambdas[t.name].lambda_function_arn
      schema    = jsondecode(file("${local.repo_root}/${t.source_dir}/tool-schema.json"))
    }
  ]

  registration_payload = {
    RequestType = "Create"
    ResourceProperties = {
      Environment    = var.environment
      AgentNamespace = var.agent_namespace
      Tools          = local.registration_tools
      SSMPrefix      = "/agentcore/${var.environment}/gateway"
    }
    StackId           = "terraform-${var.agent_namespace}-${var.environment}"
    RequestId         = "terraform-targets-${sha1(jsonencode(local.registration_tools))}"
    LogicalResourceId = "GatewayTargets"
    ResponseURL       = ""
  }
}

resource "null_resource" "register_targets" {
  triggers = {
    payload_hash     = sha1(jsonencode(local.registration_payload))
    lambda_code_hash = module.targets_provisioner.lambda_function_source_code_hash
    gateway_ready    = var.gateway_ready_token
  }

  # Note: Using local-exec as a pragmatic workaround for Terraform's lack of native CloudFormation
  # Custom Resource support. This triggers the Lambda that performs idempotent Gateway Target
  # registration. Future enhancement: migrate to aws_cloudformation_stack for full IaC compliance.
  provisioner "local-exec" {
    command = <<-EOT
      aws lambda invoke \
        --function-name ${module.targets_provisioner.lambda_function_name} \
        --cli-binary-format raw-in-base64-out \
        --payload '${jsonencode(local.registration_payload)}' \
        --region ${data.aws_region.current.name} \
        /tmp/targets_response.json
    EOT
  }

  depends_on = [module.tool_lambdas, module.targets_provisioner]
}
