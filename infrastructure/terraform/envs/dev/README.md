# dev

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.9.5 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | ~> 5.62 |

## Providers

No providers.

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_frontend_gateway"></a> [frontend\_gateway](#module\_frontend\_gateway) | ../../modules/frontend-gateway | n/a |
| <a name="module_gateway"></a> [gateway](#module\_gateway) | ../../modules/gateway | n/a |
| <a name="module_identity"></a> [identity](#module\_identity) | ../../modules/identity | n/a |
| <a name="module_knowledge"></a> [knowledge](#module\_knowledge) | ../../modules/knowledge | n/a |
| <a name="module_memory"></a> [memory](#module\_memory) | ../../modules/memory | n/a |
| <a name="module_observability"></a> [observability](#module\_observability) | ../../modules/observability | n/a |
| <a name="module_runtime"></a> [runtime](#module\_runtime) | ../../modules/runtime | n/a |
| <a name="module_tools"></a> [tools](#module\_tools) | ../../modules/tools | n/a |

## Resources

No resources.

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_agent_namespace"></a> [agent\_namespace](#input\_agent\_namespace) | Agent namespace (e.g., agentcore) | `string` | n/a | yes |
| <a name="input_aws_region"></a> [aws\_region](#input\_aws\_region) | AWS region for resource deployment | `string` | `"us-east-1"` | no |
| <a name="input_global_tools"></a> [global\_tools](#input\_global\_tools) | List of global tools (name, source\_dir, optional handler/description/memory\_size/timeout/environment) | <pre>list(object({<br/>    name        = string<br/>    source_dir  = string<br/>    handler     = optional(string)<br/>    description = optional(string)<br/>    memory_size = optional(number)<br/>    timeout     = optional(number)<br/>    environment = optional(map(string))<br/>  }))</pre> | `[]` | no |
| <a name="input_knowledge_enabled"></a> [knowledge\_enabled](#input\_knowledge\_enabled) | Enable Bedrock Knowledge Base (optional) | `bool` | `false` | no |
| <a name="input_log_retention_days"></a> [log\_retention\_days](#input\_log\_retention\_days) | CloudWatch Logs retention in days | `number` | `7` | no |
| <a name="input_xray_tracing"></a> [xray\_tracing](#input\_xray\_tracing) | Enable X-Ray tracing | `bool` | `true` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_cognito_client_id"></a> [cognito\_client\_id](#output\_cognito\_client\_id) | The ID of the Cognito User Pool Client |
| <a name="output_cognito_user_pool_id"></a> [cognito\_user\_pool\_id](#output\_cognito\_user\_pool\_id) | The ID of the Cognito User Pool |
| <a name="output_frontend_gateway_url"></a> [frontend\_gateway\_url](#output\_frontend\_gateway\_url) | The URL of the Frontend Gateway HTTP API |
<!-- END_TF_DOCS -->
