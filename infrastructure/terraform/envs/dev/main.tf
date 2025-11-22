# Development Environment - AgentCore Platform Composition
#
# Provisions all shared infrastructure components for development environment.
# Implements: FR-001 (all components), FR-014 (environment isolation)

terraform {
  required_version = ">= 1.9.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.62"
    }
  }

  backend "s3" {
    # Backend configured via -backend-config=../../globals/backend.tfvars
    key = "agentcore/dev/shared/terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "dev"
      Project     = "AWS AgentCore Enterprise Toolkit"
      ManagedBy   = "Terraform"
    }
  }
}

# Local variables
locals {
  environment = "dev"
  tags = {
    Environment = local.environment
    Project     = "AWS AgentCore Enterprise Toolkit"
    ManagedBy   = "Terraform"
  }
}

# Identity Module - Cognito User Pools
module "identity" {
  source = "../../modules/identity"

  agent_namespace = var.agent_namespace
  environment     = local.environment
  tags            = local.tags
}

# Gateway Module - Bedrock AgentCore Gateway
module "gateway" {
  source = "../../modules/gateway"

  agent_namespace = var.agent_namespace
  environment     = local.environment
  tags            = local.tags
}

# Runtime Module - IAM Execution Role for SDK-based Agents
module "runtime" {
  source = "../../modules/runtime"

  agent_namespace = var.agent_namespace
  environment     = local.environment
  tags            = local.tags

  # Dev-specific overrides
  xray_tracing_enabled = var.xray_tracing
  log_retention_days   = var.log_retention_days
}

# Memory Module - Bedrock AgentCore Memory
module "memory" {
  source = "../../modules/memory"

  agent_namespace = var.agent_namespace
  environment     = local.environment
  tags            = local.tags

  # Dev-specific overrides
  event_expiry_days = 90 # 90 days for event retention
}

# Knowledge Module - Bedrock Knowledge Base (Optional)
module "knowledge" {
  source = "../../modules/knowledge"

  agent_namespace = var.agent_namespace
  environment     = local.environment
  tags            = local.tags

  # Dev-specific overrides
  enable_knowledge_base = var.knowledge_enabled
}

# Observability Module - CloudWatch and X-Ray
module "observability" {
  source = "../../modules/observability"

  agent_namespace = var.agent_namespace
  environment     = local.environment
  tags            = local.tags

  # Dev-specific overrides
  log_retention_days    = var.log_retention_days
  xray_tracing          = var.xray_tracing
  enable_log_encryption = false
  xray_sampling_rate    = 1.0 # 100% sampling for dev
}

# Tools Module - Global MCP tools (Lambda) + Gateway Targets registration
module "tools" {
  source = "../../modules/tools"

  agent_namespace = var.agent_namespace
  environment     = local.environment
  tags            = local.tags

  gateway_ready_token = module.gateway.gateway_ready_token
  tools               = var.global_tools
}

# Frontend Gateway Module
module "frontend_gateway" {
  source = "../../modules/frontend-gateway"

  environment          = local.environment
  aws_region           = var.aws_region
  cognito_user_pool_id = module.identity.pool_id
  cognito_client_id    = module.identity.frontend_client_id
  tags                 = local.tags
}
