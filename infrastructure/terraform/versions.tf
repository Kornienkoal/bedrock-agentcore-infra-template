# Terraform Version and Provider Requirements
#
# Defines the minimum Terraform version and required providers for all
# AgentCore infrastructure modules.
#
# Reference: research.md D1 (Terraform and Provider Versions)

terraform {
  required_version = ">= 1.9.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.62"
    }
  }
}
