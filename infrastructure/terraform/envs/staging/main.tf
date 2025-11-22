# Staging Environment - AgentCore Platform Composition
#
# Provisions all shared infrastructure components for staging environment.
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
    key = "agentcore/staging/shared/terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "staging"
      Project     = "AWS AgentCore Enterprise Toolkit"
      ManagedBy   = "Terraform"
    }
  }
}

# Local variables
locals {
  environment = "staging"
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

  # Staging-specific overrides
  password_minimum_length = 12
  mfa_configuration       = "ON"
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

  # Staging-specific overrides
  xray_tracing_enabled = true
  log_retention_days   = 30
}

# Memory Module - Bedrock AgentCore Memory
module "memory" {
  source = "../../modules/memory"

  agent_namespace = var.agent_namespace
  environment     = local.environment
  tags            = local.tags

  # Staging-specific overrides
  enabled_strategies     = ["SHORT_TERM", "LONG_TERM", "SEMANTIC"]
  short_term_ttl_seconds = 7200 # 2 hours for staging
  long_term_retention    = "INDEFINITE"
}

# Knowledge Module - Bedrock Knowledge Base (Optional)
module "knowledge" {
  source = "../../modules/knowledge"

  agent_namespace = var.agent_namespace
  environment     = local.environment
  tags            = local.tags

  # Staging-specific overrides
  enable_knowledge_base = var.enable_knowledge_base
  embedding_model       = "amazon.titan-embed-text-v1"
}

# Observability Module - CloudWatch and X-Ray
module "observability" {
  source = "../../modules/observability"

  agent_namespace = var.agent_namespace
  environment     = local.environment
  tags            = local.tags

  # Staging-specific overrides
  log_retention_days    = 30
  enable_log_encryption = true
  xray_sampling_rate    = 0.5 # 50% sampling for staging
  error_rate_threshold  = 5
}
