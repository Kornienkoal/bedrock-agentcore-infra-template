# Governance Orchestration Runbook

## Purpose
Coordinate the end-to-end execution of the governance package against an AWS environment, capturing artifacts required for audit and troubleshooting future orchestration issues.

## Prerequisites
- AWS SSO authenticated session for the target account (`aws sso login --profile <profile>`).
- AWS CLI default region aligned with deployment (e.g., `us-east-1`).
- `uv` environment bootstrapped and dependencies installed (`uv sync`).
- Environment variables (examples):
  - `AGENTCORE_ENV=dev`
  - `AWS_PROFILE=<profile>` (optional if using named profile)
- Network access to AWS IAM, SSM, CloudWatch Logs (read-only permissions for catalog functions).

## Execution Steps
1. **Verify AWS Identity**
   ```bash
   aws sts get-caller-identity
   ```
   Confirm the account ID and user match expectations.

2. **Run Test Suite (Optional but Recommended)**
   ```bash
   uv run pytest tests/unit/governance -v
   uv run pytest tests/integration/governance -v
   ```
   Ensures governance modules are behaving before orchestration.

3. **Execute Governance Orchestrator**
    ```bash
    # Preferred wrapper (bundles optional tests + orchestrator)
    scripts/local/governance-end-to-end.sh --skip-tests --environment "${AGENTCORE_ENV:-}"

    # Direct Python entry point (useful for ad-hoc flags)
    uv run python scripts/local/governance_end_to_end.py \
       --environment "${AGENTCORE_ENV:-}" \
       --region "${AWS_REGION:-us-east-1}" \
       --output-dir reports
    ```
    Notes:
    - Passing an empty string (`--environment ""`) or unsetting `AGENTCORE_ENV` captures the full IAM catalog when tags are incomplete.
    - The orchestrator fetches and analyzes principal catalog data, generates risk metrics, runs authorization/integration/revocation workflows, produces the evidence pack, and writes all artifacts under `reports/`.

4. **Review Generated Artifacts**
   - Inspect `reports/governance-orchestrator-<timestamp>.json` for summary output and confirm `principal_count > 0` when the full catalog is expected.
   - Validate that auxiliary registry files (integration, revocation, evidence) exist under `reports/`.
   - Walk through `specs/001-security-role-audit/artifact-checklist.md` to confirm required artifacts were produced.

5. **Capture Troubleshooting Notes**
   - Record any failures, AWS API throttling, or IAM permission issues observed.
   - Note remediation steps alongside the artifact for repeatability.

## Troubleshooting
- **`AccessDenied` when fetching IAM data**: Ensure your AWS SSO session includes `iam:ListRoles`, `iam:ListRoleTags`, and `iam:ListAttachedRolePolicies` permissions.
- **`botocore` credential errors**: Re-run `aws sso login` or export `AWS_PROFILE`/`AWS_REGION` variables.
- **Orchestrator fails to write artifacts**: Confirm `reports/` directory exists and is writable. The `.gitignore` entry prevents accidental commits.
- **Integration or revocation registry persistence**: The orchestrator writes registries under `reports/` to keep state between runs; delete files there to reset.
- **Zero principals returned for environment filter**: Ensure IAM roles include the `Environment` tag matching the `--environment` parameter. If tags are missing, rerun with `--environment ""` (or unset `AGENTCORE_ENV`) to capture the full inventory before prioritizing tagging remediation.

## Next Actions
- After the initial run, schedule periodic executions (e.g., weekly) and archive artifacts in compliance storage.
- Use `scripts/local/governance-end-to-end.sh` for day-to-day runs; fall back to the Python entry point when troubleshooting.
- Feed outcome metrics (risk distribution, SLA compliance) into dashboards for continuous monitoring.
