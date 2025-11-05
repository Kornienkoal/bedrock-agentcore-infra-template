# Pre-Commit Hooks

This repository uses [pre-commit](https://pre-commit.com/) to enforce code quality standards before commits.

## Installation

Pre-commit hooks are **mandatory** for all contributors. Install them once:

```bash
uv run pre-commit install
```

## What Gets Checked

### Always Enforced (Python)
- **trailing-whitespace**: Remove trailing spaces
- **end-of-file-fixer**: Ensure newline at end of files
- **check-yaml**: Validate YAML syntax
- **check-added-large-files**: Block large files (>500KB)
- **check-merge-conflict**: Detect merge conflict markers
- **detect-private-key**: Block private key commits
- **ruff**: Python linting and auto-fixes
- **ruff-format**: Python code formatting
- **mypy**: Python type checking (strict mode)

### Optional (Terraform)
Terraform hooks are set to `stages: [manual]` and won't block commits by default. Run manually:

```bash
# Run terraform checks manually
uv run pre-commit run --hook-stage manual --all-files

# Or run specific terraform hooks
uv run pre-commit run terraform_fmt --all-files
```

To enable terraform hooks in CI/CD, ensure `terraform`, `tflint`, and `terraform-docs` are installed.

## Running Manually

```bash
# Run all hooks on all files
uv run pre-commit run --all-files

# Run specific hook
uv run pre-commit run ruff --all-files
uv run pre-commit run mypy --all-files

# Skip hooks for a specific commit (use sparingly!)
SKIP=ruff,mypy git commit -m "emergency fix"
```

## Fixing Issues

Most issues are auto-fixed by ruff. If pre-commit fails:

1. Review the output to see what failed
2. Run `uv run pre-commit run --all-files` to auto-fix
3. Stage the fixes: `git add -A`
4. Retry your commit

## CI/CD Integration

Pre-commit runs automatically in CI on all pull requests. Commits that fail pre-commit locally will fail in CI.

## Troubleshooting

**Hook fails to run:**
```bash
# Reinstall hooks
uv run pre-commit uninstall
uv run pre-commit install
```

**Terraform hooks fail:**
This is expected if terraform/tflint aren't installed. Terraform hooks are optional for Python-focused work.

**Mypy false positives:**
Update type stubs or add `# type: ignore` comments sparingly. Prefer fixing the root cause.
