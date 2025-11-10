# AgentCore Governance User Guide

Detailed workflows, APIs, advanced features, observability and troubleshooting for the `agentcore-governance` package. This guide extends the high‑level overview in `README.md`.

## Contents
- 1. Workflows
- 2. API Endpoints
- 3. Advanced Features
- 4. Testing Strategy
- 5. Configuration & Classification
- 6. Observability & Metrics
- 7. Troubleshooting
- 8. Operational Maintenance
- 9. ABAC Matrix Export
- 10. Glossary

---
## 1. Workflows

### Inventory & Risk Assessment
```python
from agentcore_governance.catalog import fetch_principal_catalog, flag_inactive_principals
from agentcore_governance.analyzer import enrich_principals_with_scores, detect_orphan_principals

principals = fetch_principal_catalog()
principals = flag_inactive_principals(principals, inactivity_threshold=30)
principals = enrich_principals_with_scores(principals)
orphans = detect_orphan_principals(principals)
high_risk = [p for p in principals if p["risk_rating"] == "HIGH"]
```

### Tool Authorization Lifecycle
```python
from agentcore_governance.authorization import set_authorized_tools, check_tool_authorized
from agentcore_governance.classification import load_classification_registry, check_access_allowed

classification_registry = load_classification_registry("security/tool-classification.yaml")
change_report = set_authorized_tools(
    agent_id="customer-support-agent-v1",
    tools=["get_product_info", "search_documentation", "check_warranty"],
    reason="Initial provisioning"
)
allowed = check_access_allowed(
    tool_id="check_warranty",
    classification_registry=classification_registry,
    approval_record=None
)
```

### Third-Party Integration Approval
```python
from agentcore_governance.integrations import request_integration, approve_integration, check_integration_allowed

request = request_integration(
    integration_name="HubSpot CRM",
    requester="team-lead@company.com",
    scope=["crm:read", "contacts:read"],
    justification="Ticket enrichment"
)
approval = approve_integration(request["integration_id"], "security-admin@company.com", expiry_days=90)
allowed = check_integration_allowed(request["integration_id"], target_endpoint="https://api.hubapi.com")
```

### Emergency Revocation
```python
from agentcore_governance.revocation import initiate_revocation, track_revocation_status
revocation = initiate_revocation(
    principal_id="arn:aws:iam::123456789012:role/CompromisedRole",
    reason="Credential leak detected",
    targets=["bedrock", "lambda", "s3"]
)
status = track_revocation_status(revocation["revocation_id"])
```

### Audit Trace Reconstruction
```python
from agentcore_governance.evidence import reconstruct_correlation_chain, generate_evidence_pack
chain = reconstruct_correlation_chain("req-abc123-def456")
evidence_pack = generate_evidence_pack(hours_back=24, include_metrics=True)
```

---
## 2. API Endpoints

### Catalog
- `GET /catalog/principals` — Paginated principal list with risk flags
- `GET /catalog/principals/{principalId}` — Principal detail
- `POST /catalog/export` — Snapshot export

### Authorization
- `GET /authorization/agents/{agentId}/tools` — Current authorized tools
- `PUT /authorization/agents/{agentId}/tools` — Replace tool set (differential output)
- `GET /authorization/differential/{agentId}` — Historical change log

### Integrations
- `POST /integrations` — Request integration
- `POST /integrations/{integrationId}/approve` — Approve with expiry
- `GET /integrations/{integrationId}` — Detail & status

### Revocation
- `POST /revocations` — Initiate revocation
- `GET /revocations/{revocationId}` — Status/SLA data
- `GET /revocations/active` — Active revocations list

### Decisions & Evidence
- `GET /decisions` — Filtered decision listing
- `GET /decisions?aggregate_by=<dimension>` — Aggregation (subject_id|effect|resource|action)
- `GET /analyzer/least-privilege` — Conformance report
- `GET /analyzer/risk-aggregation` — Enterprise risk metrics
- `POST /evidence-pack` — Generate evidence pack
- `GET /evidence-pack/{correlationId}` — Correlation chain reconstruction

---
## 3. Advanced Features

### Differential Policy Change Report
```python
from agentcore_governance.analyzer import generate_policy_change_report
report = generate_policy_change_report(before_principals, after_principals)
```

### Risk Aggregation
```python
from agentcore_governance.analyzer import aggregate_risk_scores
metrics = aggregate_risk_scores(principals)
```

### Quarterly Attestation Scheduling
```python
from agentcore_governance.catalog import schedule_quarterly_attestation
attestation = schedule_quarterly_attestation(owner="team-lead@company.com", principals=principals)
```

### Deprecated Tool Cleanup
```python
from agentcore_governance.authorization import cleanup_deprecated_tools
summary = cleanup_deprecated_tools(tool_id="legacy_search_v1", deprecation_date="2024-01-01T00:00:00Z", notify_agents=True)
```

### ABAC Feasibility Export
```python
from agentcore_governance.abac_matrix import generate_default_abac_matrix, export_abac_csv_file
matrix = generate_default_abac_matrix()
export_abac_csv_file(matrix["attributes"], "abac-matrix.csv")
```

---
## 4. Testing Strategy

Recommended sequence: unit → integration → coverage.
```bash
uv run pytest tests/unit/governance -v
uv run pytest tests/integration/governance -v
uv run pytest tests/unit/governance tests/integration/governance --cov=src/agentcore_governance --cov-report=term-missing
```

Focus areas:
- Analyzer scoring boundary conditions
- Authorization differential reports
- Revocation latency tracking
- Correlation integrity (hash mismatch scenarios)

---
## 5. Configuration & Classification

Tool sensitivity registry (`security/tool-classification.yaml`):
```yaml
tools:
  - id: get_product_info
    sensitivity: STANDARD
  - id: check_warranty
    sensitivity: SENSITIVE
    requires_approval: true
    approval_ttl_days: 90
  - id: delete_customer_data
    sensitivity: RESTRICTED
    requires_approval: true
    approval_ttl_days: 30
```

Environment variables:
```bash
export AWS_REGION=us-east-1
export LOG_LEVEL=INFO
export LOG_FORMAT=json
```

---
## 6. Observability & Metrics

Emitted metrics examples:
- `governance.decisions.count`
- `governance.decisions.denied`
- `governance.revocations.sla_ms`
- `governance.principals.high_risk_count`
- `governance.conformance.score`

Logs include: correlation ID, integrity hash, timestamp, principal metadata, action outcome.

---
## 7. Troubleshooting

| Issue | Cause | Resolution |
|-------|-------|------------|
| Missing IAM data | Insufficient role perms | Add `iam:List*` permissions (roles, tags, policies) |
| All principals HIGH risk | Policy summary missing | Ensure enrichment run after catalog fetch |
| Slow evidence pack | Large time window | Reduce `hours_back` or use Insights |
| False orphan flags | Tags absent | Add `Owner` and `Purpose` tags |

---
## 8. Operational Maintenance
- Periodically run deprecated tool cleanup to remove retired tools.
- Schedule quarterly attestations for ownership validation.
- Review high-risk principal list weekly.
- Track revocation SLA metrics in dashboards.

---
## 9. ABAC Matrix Export
Use `abac_matrix.py` to evaluate attribute coverage for future policy migration.
```python
from agentcore_governance.abac_matrix import generate_default_abac_matrix
matrix = generate_default_abac_matrix()
print(matrix["attributes"])
```

---
## 10. Glossary
- Principal: IAM role or identity participating in agent workflows.
- Least-Privilege Score: Heuristic measure of policy specificity.
- Risk Rating: Derived categorization (LOW|MEDIUM|HIGH) combining wildcards + inactivity.
- Correlation Chain: Ordered events tied by a correlation ID.
- Evidence Pack: Aggregated decisions + metrics + integrity data for audit.
- Revocation SLA: Time from initiation to confirmed propagation.

---
**End of User Guide**
