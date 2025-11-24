# Memory Module Variables

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod"
  }
}

variable "agent_namespace" {
  description = "Agent namespace for resource naming (e.g., 'agentcore', 'myorg/team')"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9/-]+$", var.agent_namespace))
    error_message = "Agent namespace must contain only lowercase letters, numbers, and forward slashes"
  }
}

variable "enabled_strategies" {
  description = "List of memory strategies to enable (SHORT_TERM, LONG_TERM, SEMANTIC)"
  type        = list(string)
  default     = ["SHORT_TERM", "LONG_TERM", "SEMANTIC"]

  validation {
    condition = alltrue([
      for strategy in var.enabled_strategies :
      contains(["SHORT_TERM", "LONG_TERM", "SEMANTIC"], strategy)
    ])
    error_message = "Each strategy must be one of: SHORT_TERM, LONG_TERM, SEMANTIC"
  }

  validation {
    condition     = length(var.enabled_strategies) > 0
    error_message = "At least one memory strategy must be enabled"
  }
}

variable "event_expiry_days" {
  description = "Number of days before memory events expire (default: 90 days)"
  type        = number
  default     = 90

  validation {
    condition     = var.event_expiry_days > 0
    error_message = "Event expiry must be positive"
  }
}

variable "short_term_ttl_seconds" {
  description = "Time-to-live (seconds) for short-term memory strategy"
  type        = number
  default     = 3600

  validation {
    condition     = var.short_term_ttl_seconds > 0
    error_message = "Short-term TTL must be positive"
  }
}

variable "long_term_retention" {
  description = "Retention policy for long-term memory (INDEFINITE or custom)"
  type        = string
  default     = "INDEFINITE"
}

variable "embedding_model_arn" {
  description = "ARN of Bedrock embedding model for semantic memory (default: amazon.titan-embed-text-v1)"
  type        = string
  default     = ""
}

variable "max_tokens" {
  description = "Maximum tokens for embeddings in semantic memory"
  type        = number
  default     = 1536

  validation {
    condition     = var.max_tokens > 0
    error_message = "Max tokens must be positive"
  }
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}
