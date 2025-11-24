variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "bedrock-agentcore"
}

variable "environment" {
  description = "Deployment environment (e.g., dev, prod)"
  type        = string
}

variable "cognito_user_pool_id" {
  description = "Cognito User Pool ID for token validation"
  type        = string
}

variable "cognito_client_id" {
  description = "Cognito App Client ID for token validation"
  type        = string
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
