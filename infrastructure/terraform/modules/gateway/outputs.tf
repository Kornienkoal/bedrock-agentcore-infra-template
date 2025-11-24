# Gateway Module Outputs
#
# Publishes outputs to SSM Parameter Store per constitution paths:
# /agentcore/{env}/gateway/*
#
# NOTE: Bedrock Gateway outputs are published by the Lambda custom resource.
# The custom resource stores the following SSM parameters:
# - /agentcore/{env}/gateway/gateway_id
# - /agentcore/{env}/gateway/gateway_arn
# - /agentcore/{env}/gateway/invoke_url
# - /agentcore/{env}/gateway/role_arn

# Data source to read SSM parameters created by custom resource
data "aws_ssm_parameter" "gateway_id" {
  name = "/agentcore/${var.environment}/gateway/gateway_id"

  depends_on = [null_resource.gateway_provisioning]
}

data "aws_ssm_parameter" "gateway_arn" {
  name = "/agentcore/${var.environment}/gateway/gateway_arn"

  depends_on = [null_resource.gateway_provisioning]
}

data "aws_ssm_parameter" "invoke_url" {
  name = "/agentcore/${var.environment}/gateway/invoke_url"

  depends_on = [null_resource.gateway_provisioning]
}

# Terraform outputs (for module consumers)
output "gateway_id" {
  description = "Bedrock Gateway ID"
  value       = data.aws_ssm_parameter.gateway_id.value
}

output "gateway_arn" {
  description = "Bedrock Gateway ARN"
  value       = data.aws_ssm_parameter.gateway_arn.value
}

output "invoke_url" {
  description = "Bedrock Gateway invoke URL"
  value       = data.aws_ssm_parameter.invoke_url.value
}

output "role_arn" {
  description = "Bedrock Gateway IAM role ARN"
  value       = aws_iam_role.gateway_role.arn
}

output "provisioner_function_name" {
  description = "Lambda provisioner function name"
  value       = module.gateway_provisioner_lambda.lambda_function_name
}

output "gateway_ready_token" {
  description = "Token indicating the gateway provisioning run (used for dependency chaining)"
  value       = null_resource.gateway_provisioning.id
}
