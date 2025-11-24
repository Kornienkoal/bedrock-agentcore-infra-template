# Knowledge Module - Amazon Bedrock Knowledge Base (Optional)
#
# Provisions Bedrock Knowledge Base with S3 data source and OpenSearch Serverless.
# Implements: FR-001 (knowledge base component), Constitution VII (optional RAG)
#
# NOTE: AWS S3 Vectors is the preferred vector storage (cost-effective, elastic),
#       but Terraform AWS provider v5.100.0 does not support it yet (S3 Vectors is in preview).
#       Using OpenSearch Serverless as interim solution until Terraform support is added.
#       Supported storage types: opensearch_serverless, pinecone, rds, redis_enterprise_cloud
#       See: https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors.html

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
  component       = "knowledge"
  common_tags     = var.tags
}

# S3 Bucket for Knowledge Base data source
resource "aws_s3_bucket" "data_source" {
  count  = var.enable_knowledge_base ? 1 : 0
  bucket = "${module.shared.name_prefix}-datasource"
  tags   = module.shared.common_tags
}

resource "aws_s3_bucket_versioning" "data_source" {
  count  = var.enable_knowledge_base ? 1 : 0
  bucket = aws_s3_bucket.data_source[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data_source" {
  count  = var.enable_knowledge_base ? 1 : 0
  bucket = aws_s3_bucket.data_source[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# OpenSearch Serverless Collection for vector embeddings
resource "aws_opensearchserverless_security_policy" "encryption" {
  count = var.enable_knowledge_base ? 1 : 0
  name  = "${var.agent_namespace}-${var.environment}-enc"
  type  = "encryption"
  policy = jsonencode({
    Rules = [
      {
        Resource = [
          "collection/${module.shared.name_prefix}-vectors"
        ]
        ResourceType = "collection"
      }
    ]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_security_policy" "network" {
  count = var.enable_knowledge_base ? 1 : 0
  name  = "${var.agent_namespace}-${var.environment}-net"
  type  = "network"
  policy = jsonencode([
    {
      Rules = [
        {
          Resource = [
            "collection/${module.shared.name_prefix}-vectors"
          ]
          ResourceType = "collection"
        }
      ]
      AllowFromPublic = true
    }
  ])
}

resource "aws_opensearchserverless_collection" "vectors" {
  count = var.enable_knowledge_base ? 1 : 0
  name  = "${module.shared.name_prefix}-vectors"
  type  = "VECTORSEARCH"

  depends_on = [
    aws_opensearchserverless_security_policy.encryption[0],
    aws_opensearchserverless_security_policy.network[0]
  ]

  tags = module.shared.common_tags
}

# IAM Role for Bedrock Knowledge Base
resource "aws_iam_role" "knowledge_base" {
  count = var.enable_knowledge_base ? 1 : 0
  name  = "${module.shared.name_prefix}-kb-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = module.shared.common_tags
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  resolved_embedding_model_arn = var.embedding_model_arn != "" ? var.embedding_model_arn : "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/${var.embedding_model}"
}

resource "aws_iam_role_policy" "knowledge_base_s3" {
  count = var.enable_knowledge_base ? 1 : 0
  role  = aws_iam_role.knowledge_base[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data_source[0].arn,
          "${aws_s3_bucket.data_source[0].arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "knowledge_base_opensearch" {
  count = var.enable_knowledge_base ? 1 : 0
  role  = aws_iam_role.knowledge_base[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "aoss:APIAccessAll"
        ]
        Resource = [
          aws_opensearchserverless_collection.vectors[0].arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "knowledge_base_bedrock" {
  count = var.enable_knowledge_base ? 1 : 0
  role  = aws_iam_role.knowledge_base[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          local.resolved_embedding_model_arn
        ]
      }
    ]
  })
}

# Bedrock Knowledge Base
resource "aws_bedrockagent_knowledge_base" "this" {
  count       = var.enable_knowledge_base ? 1 : 0
  name        = "${module.shared.name_prefix}-kb"
  description = "Knowledge base for ${var.agent_namespace} ${var.environment}"
  role_arn    = aws_iam_role.knowledge_base[0].arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = local.resolved_embedding_model_arn
    }
  }

  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"
    opensearch_serverless_configuration {
      collection_arn    = aws_opensearchserverless_collection.vectors[0].arn
      vector_index_name = "${module.shared.name_prefix}-index"
      field_mapping {
        vector_field   = "vector"
        text_field     = "text"
        metadata_field = "metadata"
      }
    }
  }

  tags = module.shared.common_tags
}

# Data Source for Knowledge Base
resource "aws_bedrockagent_data_source" "s3" {
  count             = var.enable_knowledge_base ? 1 : 0
  knowledge_base_id = aws_bedrockagent_knowledge_base.this[0].id
  name              = "${module.shared.name_prefix}-s3-source"

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn = aws_s3_bucket.data_source[0].arn
    }
  }
}
