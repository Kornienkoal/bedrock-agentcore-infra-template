# AWS Validation Artifact Checklist

Use this checklist during each governance orchestration run to confirm that required artifacts are captured under `reports/` with timestamped filenames.

- [ ] **Orchestrator Summary** (`reports/governance-orchestrator-<timestamp>.json`)
  - Contains AWS identity, catalog metrics, workflow outputs, and error log (if any).
- [ ] **Principal Catalog Snapshot** (`reports/principal-snapshot-<timestamp>.json`)
  - Includes raw principal records with risk/inactivity flags for audit sampling.
- [ ] **Integration Registry** (`reports/all-integrations-registry.json`)
  - Tracks third-party onboarding requests, approvals, expirations, and revocations across environments.
- [ ] **Revocation Registry** (`reports/all-revocations-registry.json`)
  - Captures revocation lifecycle events and SLA metrics across environments.
- [ ] **Catalog Coverage Check**
  - Confirm the summary file reports the expected principal count; if zero while roles exist, rerun the orchestrator with `--environment ""` and flag missing `Environment` tags for remediation.
- [ ] **Pytest Output (Optional)**
  - Preserve `uv run pytest ...` console logs when defects occur; otherwise note test success in run log.
- [ ] **Troubleshooting Notes**
  - Document IAM permission issues, throttling, or orchestration failures alongside the summary file.

> Tip: Archive the entire `reports/` directory snapshot (or copy required files) to long-term storage after each production validation run.
