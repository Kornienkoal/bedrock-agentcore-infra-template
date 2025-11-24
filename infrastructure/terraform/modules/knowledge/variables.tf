# Knowledge Module Variables

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "agent_namespace" {
  description = "Agent namespace for resource naming"
  type        = string
}

variable "enable_knowledge_base" {
  description = "Enable knowledge base provisioning"
  type        = bool
  default     = false
}

variable "embedding_model_arn" {
  description = "Optional ARN override for embedding model"
  type        = string
  default     = ""
}

variable "embedding_model" {
  description = "Embedding model ID for knowledge base"
  type        = string
  default     = "amazon.titan-embed-text-v1"
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}
