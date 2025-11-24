# Staging Environment Variables

variable "agent_namespace" {
  description = "Agent namespace (e.g., agentcore)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for staging deployments"
  type        = string
  default     = "us-east-1"
}

variable "enable_knowledge_base" {
  description = "Provision the optional Bedrock Knowledge Base in staging"
  type        = bool
  default     = false
}
