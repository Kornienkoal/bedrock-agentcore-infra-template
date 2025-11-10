# Quickstart: Governance & Security Audit

## Purpose
Enable security/admin teams to retrieve principal catalog, manage tool classification, authorize tools for agents, initiate revocations, and generate evidence packs.

## Prerequisites
- Deployed template infrastructure (gateway, runtime, memory).
- Admin JWT token with internal governance API access.
- Tagged IAM roles with `Owner` and `Purpose` where possible.

## Steps
1. List Principals:
   - Call `GET /catalog/principals?environment=dev` → review `least_privilege_score`.
2. Classify Tools:
   - For a new tool, commit entry to `security/tool-classification.yaml` (future) and PATCH classification if changes.
3. Authorize Tool for Agent:
   - `PUT /authorization/agents/customer-support/tools` with updated tool list.
4. Onboard Third-Party (if any):
   - `POST /integrations` with justification; approve via `POST /integrations/{id}/approve`.
5. Revoke Access:
   - `POST /revocations` specifying `subjectType=user` for user token emergency.
6. Evidence Pack:
   - `POST /evidence-pack` → returns metadata and retrieval link.
7. Least Privilege Report:
   - `GET /analyzer/least-privilege` → track average score trend.
8. ABAC Feasibility:
   - `GET /abac/feasibility` → review attribute matrix for future.

## Monitoring
- Synthetic revocation tests (scheduled) validate propagation SLA.
- Conformance scores below threshold trigger remediation tasks.

## Next Steps
- Implement catalog generation Lambda.
- Add tool classification registry file & enforcement hook.
- Build analyzer script integration.
