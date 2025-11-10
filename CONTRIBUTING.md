# Contributing to Amazon Bedrock AgentCore Template

Thank you for your interest in contributing! This guide will help you understand our development workflow, coding standards, and how to submit contributions.

## 🎯 Mission

Build a production-ready, agent-agnostic Amazon Bedrock AgentCore foundation that AWS teams can reuse to spin up **any** proof-of-concept agent in minutes.

## 📋 Table of Contents

- [Development Setup](#-development-setup)
- [Project Structure](#-project-structure)
- [Coding Standards](#-coding-standards)
- [Making Changes](#-making-changes)
- [Testing Guidelines](#-testing-guidelines)
- [Documentation](#-documentation)
- [Pull Request Process](#-pull-request-process)
- [Release Process](#-release-process)

## 🛠️ Development Setup

### Prerequisites

1. **Python 3.13**
   ```bash
   python --version  # Should be 3.12 or higher
   ```

2. **UV Package Manager**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   uv --version
   ```

3. **AWS CLI v2**
   ```bash
   aws --version
   ```

4. **Git**
   ```bash
   git --version
   ```

### Clone and Setup

```bash
# Clone repository
git clone <repository-url>
cd bedrock-agentcore-template

# Install dependencies (creates venv and installs all packages)
uv sync

# Activate virtual environment (optional - uv run handles this)
source .venv/bin/activate

# Verify installation
uv run python -c "from agentcore_common import get_m2m_token; print('✅ Setup successful')"
```

### Development Tools

Install recommended VS Code extensions:
- Python (ms-python.python)
- Ruff (charliermarsh.ruff)
- Pylance (ms-python.vscode-pylance)
- YAML (redhat.vscode-yaml)

## 📁 Project Structure

```
bedrock-agentcore-template/
├── packages/              # Shared workspace packages
│   ├── agentcore-common/  # Auth, config, observability
│   └── agentcore-tools/   # Gateway, Memory, Identity clients
├── agents/                # Agent implementations
├── infrastructure/        # Terraform modules and envs
├── scripts/              # Deployment automation
├── docs/                 # Documentation
└── tests/                # Test suite
```

### Component Responsibilities

**packages/agentcore-common**: Core utilities with no AgentCore SDK dependencies
- Authentication (M2M OAuth2, SSM)
- Configuration (YAML loader, Pydantic models)
- Observability (CloudWatch, X-Ray, metrics)

**packages/agentcore-tools**: AgentCore integrations
- Gateway client (Lambda MCP tools)
- Memory client (user context storage)
- Identity decorator (OAuth2 aware tools)

**agents/**: Individual agent implementations
- `runtime.py`: BedrockAgentCoreApp entrypoint
- `tools/`: Agent-specific local tools
- `pyproject.toml`: Agent dependencies

**infrastructure/**: CloudFormation templates
- `01-cognito.yaml`: User authentication
- `02-gateway.yaml`: API Gateway + Lambda MCP
- `03-runtime.yaml`: Agent execution
- `04-memory.yaml`: User context storage
- `05-knowledge-base.yaml`: RAG (optional)
- `06-identity-providers.yaml`: OAuth2 (optional)

**scripts/**: Developer tooling helpers
- `infra/`: Terraform validation, drift detection, and environment checks
- `local/run-agent-docker.sh`: Lambda-like container smoke test for an agent runtime
- Agent deployments are handled via the Bedrock AgentCore CLI (see `agents/README.md`)

## 🎨 Coding Standards

### Python Style

We follow **PEP 8** with some modifications:

```python
# Line length: 100 characters (not 79)
# Use type hints for all function signatures
# Use docstrings for public APIs

def example_function(param: str, optional: int = 5) -> dict:
    """
    Brief description of function.

    Args:
        param: Description of param
        optional: Description with default value

    Returns:
        Description of return value

    Raises:
        ValueError: When param is invalid

    Example:
        >>> example_function('test')
        {'result': 'value'}
    """
    return {'result': 'value'}
```

### Linting and Formatting

```bash
# Format code with Ruff
uv run ruff format .

# Lint code
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .

# Type checking
uv run mypy packages/ agents/
```

### Code Organization

1. **Imports Order**:
   ```python
   # Standard library
   import os
   from typing import Dict, Any

   # Third-party
   import boto3
   from pydantic import BaseModel

   # Workspace packages
   from agentcore_common import get_m2m_token

   # Local imports
   from .utils import helper_function
   ```

2. **Error Handling**:
   ```python
   # Good: Specific exceptions with logging
   try:
       result = risky_operation()
   except SpecificException as e:
       logger.error(f"Operation failed: {e}", exc_info=True)
       raise

   # Bad: Bare except
   try:
       result = risky_operation()
   except:
       pass
   ```

3. **Configuration**:
   ```python
   # Good: Use config loader with SSM resolution
   from agentcore_common import load_agent_config
   config = load_agent_config(agent_name='my-agent')

   # Bad: Hardcoded values
  MODEL_ID = 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
   ```

### Terraform Standards

```hcl
# Versions and providers
terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# Parameterize names and publish outputs to SSM via modules
module "identity" {
  source       = "../modules/identity"
  environment  = var.environment
  agent_namespace = var.agent_namespace
}

# Least-privilege IAM examples should scope resources precisely
data "aws_iam_policy_document" "bedrock_invoke" {
  statement {
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = ["arn:aws:bedrock:${var.region}::foundation-model/anthropic.claude-*"]
  }
}
```

## 🔄 Making Changes

### Branching Strategy

```bash
# Create feature branch from main
git checkout main
git pull origin main
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-description
```

### Branch Naming Convention

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions/updates
- `infra/` - Infrastructure changes

### Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Format
<type>(<scope>): <subject>

<body>

<footer>

# Types
feat:     New feature
fix:      Bug fix
docs:     Documentation changes
style:    Code style changes (formatting, etc.)
refactor: Code refactoring
test:     Test additions/updates
chore:    Build process or tooling changes
infra:    Infrastructure changes

# Examples
feat(gateway): add retry logic for Lambda MCP invocations

- Implemented exponential backoff
- Added max retry configuration
- Updated tests

Closes #123

fix(config): resolve SSM parameters with encryption

- Fixed decryption for SecureString parameters
- Added error handling for missing parameters

docs(readme): update deployment instructions

- Added VPC configuration steps
- Clarified Cognito setup
```

### Development Workflow

1. **Create branch**:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes**:
   ```bash
   # Edit files
   vim packages/agentcore-common/src/agentcore_common/auth.py

   # Test locally
   uv run pytest packages/agentcore-common/tests/
   ```

3. **Lint and format**:
   ```bash
   uv run ruff format .
   uv run ruff check --fix .
   uv run mypy packages/
   ```

4. **Commit**:
   ```bash
   git add .
   git commit -m "feat(auth): add token caching for M2M OAuth2"
   ```

5. **Push and create PR**:
   ```bash
   git push origin feature/my-feature
   # Open PR on GitHub
   ```

## 🧪 Testing Guidelines

### Test Structure

```
tests/
├── unit/                  # Unit tests (fast, isolated)
│   ├── test_auth.py
│   ├── test_config.py
│   └── test_observability.py
├── integration/           # Integration tests (AWS services)
│   ├── test_gateway.py
│   ├── test_memory.py
│   └── test_runtime.py
└── conftest.py           # Pytest fixtures
```

### Writing Tests

```python
import pytest
from unittest.mock import Mock, patch
from agentcore_common import get_m2m_token

def test_get_m2m_token_success():
    """Test successful M2M token retrieval."""
    # Arrange
    with patch('agentcore_common.auth.requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            'access_token': 'test-token-123',
            'expires_in': 3600
        }

        # Act
        token = get_m2m_token(
            client_id='test-client',
            client_secret='test-secret',
            ssm_prefix='/test'
        )

        # Assert
        assert token == 'test-token-123'
        mock_post.assert_called_once()

def test_get_m2m_token_failure():
    """Test M2M token retrieval with invalid credentials."""
    with patch('agentcore_common.auth.requests.post') as mock_post:
        mock_post.return_value.status_code = 401

        with pytest.raises(ValueError, match="Failed to get M2M token"):
            get_m2m_token(
                client_id='bad-client',
                client_secret='bad-secret',
                ssm_prefix='/test'
            )
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_auth.py

# Run with coverage
uv run pytest --cov=packages --cov-report=html

# Run integration tests (requires AWS credentials)
uv run pytest tests/integration/ --aws-profile=your-profile
```

### Test Coverage Requirements

- **Workspace packages**: Minimum 80% coverage
- **Critical paths**: 100% coverage (auth, config loading)
- **Agent code**: Minimum 60% coverage (demo code)

## 📚 Documentation

### Code Documentation

```python
def store_memory(
    user_id: str,
    content: str,
    category: str = 'conversation',
    metadata: dict = None
) -> dict:
    """
    Store user memory in AgentCore Memory.

    This is a convenience function that creates a MemoryClient
    and stores the provided content with user-scoped access.

    Args:
        user_id: Unique identifier for the user
        content: Memory content to store
        category: Memory category (conversation, preferences, issues)
        metadata: Optional additional metadata

    Returns:
        Response from Memory API containing memory_id

    Raises:
        ValueError: If user_id or content is empty
        ClientError: If AWS API call fails

    Example:
        >>> store_memory(
        ...     user_id='user-123',
        ...     content='User prefers email notifications',
        ...     category='preferences'
        ... )
        {'memory_id': 'mem-abc123', 'status': 'stored'}

    See Also:
        - MemoryClient: For batch operations
        - retrieve_memory: For retrieving memories
    """
```

### README Updates

When adding features:

1. Update main `README.md` with overview
2. Update section-specific README (e.g., `infrastructure/README.md`)
3. Update `CHANGELOG.md` under "Unreleased"
4. Update `.github/template-notes.md` with lessons learned

### Documentation Standards

- Use **Markdown** for all documentation
- Include **code examples** for all APIs
- Add **diagrams** for architecture (ASCII or Mermaid)
- Keep **line length** under 100 characters
- Use **relative links** for internal references

## 🚀 Pull Request Process

### Before Submitting

- [ ] Tests pass: `uv run pytest`
- [ ] Linting passes: `uv run ruff check .`
- [ ] Type checking passes: `uv run mypy packages/`
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Commit messages follow conventions

### PR Description Template

```markdown
## Description
Brief description of changes

## Motivation
Why is this change needed?

## Changes Made
- List of specific changes
- With bullet points

## Testing
How was this tested?
- Unit tests added/updated
- Integration tests passed
- Manual testing performed

## Screenshots (if applicable)
Add screenshots for UI changes

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. **Automated checks** run (tests, linting)
2. **Code review** by maintainer
3. **Address feedback** if needed
4. **Approval** and merge

## 📦 Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

### Creating a Release

1. **Update version** in relevant `pyproject.toml` files
2. **Update CHANGELOG.md**:
   ```markdown
   ## [0.3.0] - 2024-01-XX

   ### Added
   - Infrastructure templates for CloudFormation
   ```

3. **Create git tag**:
   ```bash
   git tag -a v0.3.0 -m "Release v0.3.0: Infrastructure Templates"
   git push origin v0.3.0
   ```

4. **Create GitHub Release** with changelog

## 🤝 Community Guidelines

### Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Welcome newcomers
- Assume good intentions

### Getting Help

- **Documentation**: Check `docs/` first
- **Issues**: Search existing issues
- **Discussions**: For questions and ideas
- **Slack**: AWS internal channels (if applicable)

## 📊 Project Phases

We're following a phased approach:

- **Phase 1**: ✅ Documentation & Design
- **Phase 2**: ✅ UV Workspace Enhancement
- **Phase 3**: 🔄 Infrastructure Templates (current)
- **Phase 4**: ⏳ Testing & CI/CD
- **Phase 5**: ⏳ Additional Sample Agents

See `.github/template-notes.md` for detailed progress.

## 🎯 Good First Issues

New to the project? Look for issues labeled:
- `good-first-issue`: Easy tasks for newcomers
- `documentation`: Documentation improvements
- `help-wanted`: Extra attention needed

## 💡 Questions?

Feel free to:
- Open an issue for bugs/features
- Start a discussion for questions
- Reach out to maintainers

---

## 🏗️ Infrastructure Development (Terraform)

### Prerequisites for IaC Development

1. **Terraform** >= 1.9.5
   ```bash
   terraform version
   ```

2. **AWS CLI** >= 2.x
   ```bash
   aws --version
   aws configure  # Set up credentials
   ```

3. **TFLint** (Terraform linter)
   ```bash
   brew install tflint  # macOS
   # Or: curl -s https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash
   ```

4. **jq** (JSON processor)
   ```bash
   brew install jq  # macOS
   # Or: sudo apt-get install jq  # Linux
   ```

### Infrastructure Setup

1. **Initialize Terraform backend**:
   ```bash
   cd infrastructure/terraform/envs/dev
   terraform init \
     -backend-config=../../globals/backend.tfvars \
     -backend-config="key=agentcore/dev/terraform.tfstate"
   ```

2. **Install pre-commit hooks** (includes Terraform):
   ```bash
   pip install pre-commit
   pre-commit install
   ```

### Terraform Development Workflow

#### 1. Making Infrastructure Changes

**Module development**:
```bash
# Edit module files
vim infrastructure/terraform/modules/identity/main.tf

# Format code
terraform fmt -recursive infrastructure/terraform/

# Validate syntax
cd infrastructure/terraform/envs/dev
terraform init -backend=false
terraform validate
```

**SSM Parameter Pattern** - All module outputs must be published:
```hcl
resource "aws_ssm_parameter" "example" {
  name        = "${module.shared.ssm_prefix}/example_value"
  description = "Example resource identifier"
  type        = "String"  # Use "SecureString" for secrets
  value       = aws_example_resource.this.id
  tags        = module.shared.common_tags
}
```

**IAM Least-Privilege Pattern**:
```hcl
# ✅ CORRECT - Scoped to specific resources
data "aws_iam_policy_document" "example" {
  statement {
    effect = "Allow"
    actions = ["bedrock:InvokeModel"]
    # Scoped to specific model families
    resources = [
      "arn:aws:bedrock:${region}::foundation-model/anthropic.claude-*"
    ]
  }
}

# ❌ WRONG - Overly permissive
resources = ["*"]  # Avoid unless required by AWS service
```

#### 2. Pre-deployment Validation

```bash
# Comprehensive validation
./scripts/infra/terraform-validate.sh dev

# Individual checks
terraform fmt -check -recursive infrastructure/terraform/
tflint --recursive
```

#### 3. Testing Infrastructure Changes

**Preflight checks**:
```bash
./scripts/infra/preflight-checks.sh dev
```

**Plan and review**:
```bash
cd infrastructure/terraform/envs/dev
terraform plan \
  -var-file=../../globals/tagging.tfvars \
  -var-file=terraform.tfvars \
  -out=tfplan

# Review plan carefully before applying
```

**Apply changes** (dev environment only for testing):
```bash
terraform apply tfplan
```

**Post-deployment validation**:
```bash
# Verify all components
./scripts/infra/validate.sh dev

# Check idempotency (should be no-op)
./scripts/infra/noop-check.sh dev

# Detect drift
./scripts/infra/drift-check.sh dev
```

#### 4. Commit Infrastructure Changes

```bash
git add infrastructure/terraform/modules/identity/
git commit -m "feat(identity): Add MFA enforcement for production"
```

### Terraform Code Style

**Module structure**:
```
modules/<component>/
├── main.tf         # Resource definitions
├── variables.tf    # Input variables
├── outputs.tf      # Outputs + SSM parameters
├── README.md       # Module documentation
└── versions.tf     # Optional provider constraints
```

**Naming conventions**:
- Resources: `snake_case` (e.g., `aws_dynamodb_table.memory`)
- Variables: `snake_case` (e.g., `var.environment`)
- Outputs: `snake_case` (e.g., `output "table_name"`)
- SSM parameters: `${module.shared.ssm_prefix}/<key_name>`

**Tagging standard** - All taggable resources:
```hcl
tags = merge(
  module.shared.common_tags,  # Environment, AgentNamespace, Component
  {
    Name = "${module.shared.name_prefix}-resource-name"
  }
)
```

### Pre-commit Hooks for Terraform

Pre-commit automatically runs on `git commit`:
- `terraform_fmt` - Format code
- `terraform_validate` - Validate syntax
- `terraform_tflint` - Lint code
- `terraform_docs` - Generate module docs (if configured)

**Manual execution**:
```bash
# Run all hooks
pre-commit run --all-files

# Run specific hook
pre-commit run terraform_fmt --all-files
```

**Bypass hooks** (use sparingly):
```bash
git commit --no-verify
```

### CI/CD Integration for Infrastructure

#### GitHub Actions Workflow Example

**Validate on PR**:
```yaml
name: Terraform Validate

on:
  pull_request:
    paths:
      - 'infrastructure/terraform/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.9.5

      - name: Terraform Format Check
        run: terraform fmt -check -recursive infrastructure/terraform/

      - name: Terraform Validate
        run: |
          cd infrastructure/terraform/envs/dev
          terraform init -backend=false
          terraform validate

      - name: TFLint
        run: |
          tflint --init
          tflint --recursive
```

**Plan on PR**:
```yaml
plan:
  runs-on: ubuntu-latest
  needs: validate
  steps:
    - name: Configure AWS Credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-east-1

    - name: Terraform Plan
      run: |
        cd infrastructure/terraform/envs/dev
        terraform init -backend-config=../../globals/backend.tfvars
        terraform plan -var-file=../../globals/tagging.tfvars -out=tfplan

    - name: Idempotency Check
      run: ./scripts/infra/noop-check.sh dev --ci
```

### Infrastructure Deployment Guidelines

**Development environment**:
- ✅ Use for testing infrastructure changes
- ✅ Deploy via local Terraform or CI/CD
- ✅ Teardown permitted: `./scripts/infra/teardown.sh dev`

**Staging environment**:
- ⚠️  Mirror production configuration
- ⚠️  Require PR approval before deployment
- ⚠️  Run full validation suite

**Production environment**:
- 🚨 Manual approval required
- 🚨 Require `--force` flag for teardown
- 🚨 Pre-deployment preflight checks mandatory
- 🚨 Post-deployment drift detection required
- 🚨 Rollback plan documented

### Security Checklist for Infrastructure

Before merging infrastructure changes:
- [ ] No hardcoded secrets (use SSM SecureString)
- [ ] IAM policies follow least-privilege
- [ ] Wildcard resources documented with justification
- [ ] All resources tagged consistently
- [ ] SSM parameters published for all outputs
- [ ] Encryption enabled where applicable (KMS)
- [ ] MFA enforced for production Cognito pools
- [ ] X-Ray tracing enabled (staging/prod)
- [ ] CloudWatch log retention configured
- [ ] S3 buckets have versioning enabled

### Troubleshooting Infrastructure Issues

**Terraform state locked**:
```bash
# Force unlock (use with caution!)
terraform force-unlock <LOCK_ID>
```

**Validation failures**:
```bash
# Check formatting
terraform fmt -check -diff infrastructure/terraform/

# Validate all modules
cd infrastructure/terraform/envs/dev
terraform init -backend=false
terraform validate
```

**SSM parameter not found**:
```bash
# List all parameters
aws ssm describe-parameters \
  --parameter-filters "Key=Name,Option=BeginsWith,Values=/agentcore/dev/"

# Get specific parameter
aws ssm get-parameter --name /agentcore/dev/identity/pool_id
```

**Drift detected**:
```bash
# Show drift details
./scripts/infra/drift-check.sh dev

# Remediate by re-applying
cd infrastructure/terraform/envs/dev
terraform apply -var-file=../../globals/tagging.tfvars
```

### Infrastructure Documentation

When adding/modifying modules:
1. Update module README with usage examples
2. Document all variables in `variables.tf`
3. Document all outputs in `outputs.tf`
4. Update `docs/README.md` if agent consumption changes (stage docs index)
5. Reflect operational impacts in stage READMEs (Infrastructure, Global Tools) and `docs/README.md`

### Resources for Infrastructure Development

- **Terraform AWS Provider**: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- **AWS Bedrock Documentation**: https://docs.aws.amazon.com/bedrock/
- **TFLint Rules**: https://github.com/terraform-linters/tflint-ruleset-aws
- **Docs index**: `docs/README.md`
- **Quickstart Guide**: `specs/001-provision-shared-infra/quickstart.md`

---

**Thank you for contributing to the Amazon Bedrock AgentCore Template!** 🙌
