# Production Environment Variables

variable "agent_namespace" {
  description = "Agent namespace (e.g., agentcore)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for production deployments"
  type        = string
  default     = "us-east-1"
}

variable "enable_knowledge_base" {
  description = "Provision the optional Bedrock Knowledge Base in production"
  type        = bool
  default     = false
}
