# Identity Module - Cognito User Pools and Clients
#
# Provisions authentication and authorization infrastructure for the AgentCore platform.
# Implements: FR-001 (identity component), Constitution III (AuthN/Z discipline)

terraform {
  required_version = ">= 1.9.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.62"
    }
  }
}

# Import shared locals for naming and tagging
module "shared" {
  source          = "../_shared"
  agent_namespace = var.agent_namespace
  environment     = var.environment
  component       = "identity"
  common_tags     = var.tags
}

# Cognito User Pool
resource "aws_cognito_user_pool" "main" {
  name = "${module.shared.name_prefix}-pool"

  # Password policy
  password_policy {
    minimum_length    = 12
    require_uppercase = true
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
  }

  # MFA configuration - OFF for M2M clients, can be enabled per-user
  mfa_configuration = "OFF"

  # User attributes
  schema {
    name                = "email"
    attribute_data_type = "String"
    mutable             = true
    required            = true
  }

  schema {
    name                = "allowed_agents"
    attribute_data_type = "String"
    mutable             = true
    required            = false
    string_attribute_constraints {
      min_length = 0
      max_length = 2048
    }
  }

  # Account recovery
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = merge(
    module.shared.common_tags,
    {
      Name = "${module.shared.name_prefix}-pool"
    }
  )
}

# Machine-to-Machine App Client (client_credentials flow)
resource "aws_cognito_user_pool_client" "machine" {
  name         = "${module.shared.name_prefix}-m2m-client"
  user_pool_id = aws_cognito_user_pool.main.id

  # OAuth2 client_credentials flow
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = aws_cognito_resource_server.agentcore.scope_identifiers

  # Token validity
  access_token_validity  = 1  # 1 hour
  id_token_validity      = 1  # 1 hour
  refresh_token_validity = 30 # 30 days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}

# Frontend App Client (authorization_code + PKCE flow for Streamlit UI)
resource "aws_cognito_user_pool_client" "frontend" {
  name         = "${module.shared.name_prefix}-frontend-client"
  user_pool_id = aws_cognito_user_pool.main.id

  # OAuth2 authorization_code flow with PKCE
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]

  # Callback URLs for local development and production
  callback_urls = [
    "http://localhost:8501",
    "http://localhost:8502",
    "https://${aws_cognito_user_pool_domain.main.domain}.auth.${data.aws_region.current.name}.amazoncognito.com/oauth2/idpresponse"
  ]

  logout_urls = [
    "http://localhost:8501",
    "http://localhost:8502"
  ]

  # Supported identity providers
  supported_identity_providers = ["COGNITO"]

  # Token validity
  access_token_validity  = 1  # 1 hour
  id_token_validity      = 1  # 1 hour
  refresh_token_validity = 30 # 30 days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Enable PKCE
  prevent_user_existence_errors = "ENABLED"

  # Read/write attributes
  read_attributes  = ["email", "email_verified", "custom:allowed_agents"]
  write_attributes = ["email"]
}

# Data source for current region
data "aws_region" "current" {}

# Resource server for OAuth scopes
resource "aws_cognito_resource_server" "agentcore" {
  identifier   = "agentcore"
  name         = "${module.shared.name_prefix}-resource-server"
  user_pool_id = aws_cognito_user_pool.main.id

  scope {
    scope_name        = "invoke"
    scope_description = "Invoke agent capabilities"
  }

  scope {
    scope_name        = "read"
    scope_description = "Read agent data"
  }

  scope {
    scope_name        = "write"
    scope_description = "Write agent data"
  }
}

# User Pool Domain (for Hosted UI if needed)
resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${replace(var.agent_namespace, "/", "-")}-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id
}
