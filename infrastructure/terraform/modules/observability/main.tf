# Observability Module - CloudWatch and X-Ray
#
# Provisions centralized logging and tracing infrastructure.
# Implements: FR-001 (observability component), Constitution VI (CloudWatch/X-Ray)

terraform {
  required_version = ">= 1.9.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.62"
    }
  }
}

# Import shared locals
module "shared" {
  source          = "../_shared"
  agent_namespace = var.agent_namespace
  environment     = var.environment
  component       = "observability"
  common_tags     = var.tags
}

# CloudWatch Log Group for Agent Invocations
resource "aws_cloudwatch_log_group" "agent_invocations" {
  name              = "/aws/agentcore/${var.environment}/invocations"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.enable_log_encryption ? aws_kms_key.logs[0].arn : null

  tags = merge(
    module.shared.common_tags,
    {
      Name = "agent-invocations"
    }
  )
}

# CloudWatch Log Group for Agent Tools
resource "aws_cloudwatch_log_group" "agent_tools" {
  name              = "/aws/agentcore/${var.environment}/tools"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.enable_log_encryption ? aws_kms_key.logs[0].arn : null

  tags = merge(
    module.shared.common_tags,
    {
      Name = "agent-tools"
    }
  )
}

# CloudWatch Log Group for Bedrock Gateway Access Logs
resource "aws_cloudwatch_log_group" "gateway" {
  name              = "/aws/agentcore/${var.environment}/gateway"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.enable_log_encryption ? aws_kms_key.logs[0].arn : null

  tags = merge(
    module.shared.common_tags,
    {
      Name = "api-gateway-access"
    }
  )
}

# KMS Key for CloudWatch Logs encryption (optional)
resource "aws_kms_key" "logs" {
  count               = var.enable_log_encryption ? 1 : 0
  description         = "KMS key for AgentCore CloudWatch Logs encryption"
  enable_key_rotation = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action = "kms:*"
        # Standard AWS KMS key policy pattern - Resource = "*" refers to this key only
        Resource = "*"
      },
      {
        Sid    = "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${data.aws_region.current.name}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:CreateGrant",
          "kms:DescribeKey"
        ]
        # Resource = "*" required by CloudWatch Logs service
        # Scoped by Condition to specific log group paths
        Resource = "*"
        Condition = {
          ArnLike = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/agentcore/${var.environment}/*"
          }
        }
      }
    ]
  })

  tags = merge(
    module.shared.common_tags,
    {
      Name = "agentcore-logs-key"
    }
  )
}

resource "aws_kms_alias" "logs" {
  count         = var.enable_log_encryption ? 1 : 0
  name          = "alias/agentcore-logs-${var.environment}"
  target_key_id = aws_kms_key.logs[0].key_id
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# CloudWatch Metric Filters for Agent Performance
resource "aws_cloudwatch_log_metric_filter" "invocation_errors" {
  name           = "${module.shared.name_prefix}-invocation-errors"
  log_group_name = aws_cloudwatch_log_group.agent_invocations.name
  pattern        = "[timestamp, request_id, level=ERROR*, ...]"

  metric_transformation {
    name      = "InvocationErrors"
    namespace = "AgentCore/${var.environment}"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_log_metric_filter" "invocation_duration" {
  name           = "${module.shared.name_prefix}-invocation-duration"
  log_group_name = aws_cloudwatch_log_group.agent_invocations.name
  pattern        = "[timestamp, request_id, level, msg, duration_ms]"

  metric_transformation {
    name      = "InvocationDuration"
    namespace = "AgentCore/${var.environment}"
    value     = "$duration_ms"
    unit      = "Milliseconds"
  }
}

# CloudWatch Alarms for Critical Errors
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "${module.shared.name_prefix}-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "InvocationErrors"
  namespace           = "AgentCore/${var.environment}"
  period              = 300
  statistic           = "Sum"
  threshold           = var.error_rate_threshold
  alarm_description   = "Agent invocation error rate is too high"
  treat_missing_data  = "notBreaching"

  tags = module.shared.common_tags
}

# X-Ray Sampling Rule for Agent Traces
# Note: Wildcards in sampling rules are standard AWS patterns for matching all requests
# Specificity is achieved via service_name filter
resource "aws_xray_sampling_rule" "agent_traces" {
  rule_name      = "${var.agent_namespace}-${var.environment}"
  priority       = 1000
  version        = 1
  reservoir_size = 1
  fixed_rate     = var.xray_sampling_rate
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = "agentcore-${var.environment}"
  resource_arn   = "*"

  tags = module.shared.common_tags
}

# ============================================================================
# CloudWatch Metrics and Alarms for Bedrock Gateway
# ============================================================================

# Metric for Gateway invocation latency
resource "aws_cloudwatch_metric_alarm" "gateway_latency" {
  alarm_name          = "${module.shared.name_prefix}-gateway-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Latency"
  namespace           = "AWS/BedrockAgent"
  period              = 300
  statistic           = "Average"
  threshold           = var.gateway_latency_threshold_ms
  alarm_description   = "Bedrock Gateway average latency is too high"
  treat_missing_data  = "notBreaching"

  dimensions = {
    Environment = var.environment
    Component   = "gateway"
  }

  tags = module.shared.common_tags
}

# Metric for Gateway error rate
resource "aws_cloudwatch_metric_alarm" "gateway_errors" {
  alarm_name          = "${module.shared.name_prefix}-gateway-high-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/BedrockAgent"
  period              = 300
  statistic           = "Sum"
  threshold           = var.gateway_error_threshold
  alarm_description   = "Bedrock Gateway error count is too high"
  treat_missing_data  = "notBreaching"

  dimensions = {
    Environment = var.environment
    Component   = "gateway"
  }

  tags = module.shared.common_tags
}

# ============================================================================
# CloudWatch Metrics and Alarms for Bedrock Memory
# ============================================================================

# Metric for Memory service throttles
resource "aws_cloudwatch_metric_alarm" "memory_throttles" {
  alarm_name          = "${module.shared.name_prefix}-memory-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ThrottledRequests"
  namespace           = "AWS/BedrockAgent"
  period              = 300
  statistic           = "Sum"
  threshold           = var.memory_throttle_threshold
  alarm_description   = "Bedrock Memory service is experiencing throttling"
  treat_missing_data  = "notBreaching"

  dimensions = {
    Environment = var.environment
    Component   = "memory"
  }

  tags = module.shared.common_tags
}

# Metric for Memory read latency
resource "aws_cloudwatch_metric_alarm" "memory_read_latency" {
  alarm_name          = "${module.shared.name_prefix}-memory-high-read-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ReadLatency"
  namespace           = "AWS/BedrockAgent"
  period              = 300
  statistic           = "Average"
  threshold           = var.memory_latency_threshold_ms
  alarm_description   = "Bedrock Memory read latency is too high"
  treat_missing_data  = "notBreaching"

  dimensions = {
    Environment = var.environment
    Component   = "memory"
  }

  tags = module.shared.common_tags
}

# ============================================================================
# CloudWatch Dashboard for AgentCore Observability
# ============================================================================

resource "aws_cloudwatch_dashboard" "agentcore" {
  dashboard_name = "${module.shared.name_prefix}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      # Gateway metrics row
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/BedrockAgent", "Invocations", { stat = "Sum", label = "Gateway Invocations" }],
            [".", "Errors", { stat = "Sum", label = "Gateway Errors" }],
            [".", "Latency", { stat = "Average", label = "Gateway Latency (avg)" }],
            ["...", { stat = "p99", label = "Gateway Latency (p99)" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "Bedrock Gateway Metrics"
          yAxis = {
            left = {
              label = "Count / ms"
            }
          }
        }
        x      = 0
        y      = 0
        width  = 12
        height = 6
      },
      # Memory metrics row
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/BedrockAgent", "MemoryReads", { stat = "Sum", label = "Memory Reads" }],
            [".", "MemoryWrites", { stat = "Sum", label = "Memory Writes" }],
            [".", "ReadLatency", { stat = "Average", label = "Read Latency (avg)" }],
            [".", "WriteLatency", { stat = "Average", label = "Write Latency (avg)" }],
            [".", "ThrottledRequests", { stat = "Sum", label = "Throttled Requests" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "Bedrock Memory Metrics"
          yAxis = {
            left = {
              label = "Count / ms"
            }
          }
        }
        x      = 12
        y      = 0
        width  = 12
        height = 6
      },
      # Agent invocation errors
      {
        type = "log"
        properties = {
          query  = <<-EOT
            SOURCE '${aws_cloudwatch_log_group.agent_invocations.name}'
            | fields @timestamp, @message
            | filter @message like /ERROR/
            | sort @timestamp desc
            | limit 20
          EOT
          region = data.aws_region.current.name
          title  = "Recent Agent Errors"
        }
        x      = 0
        y      = 6
        width  = 24
        height = 6
      }
    ]
  })
}
