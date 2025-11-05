# AgentCore Governance Package

The `agentcore-governance` package provides catalog aggregation, tool classification, authorization mapping, revocation workflows, and evidence pack utilities for the Enterprise Security Role & Token Audit initiative.

## Layout

```
src/agentcore_governance/
├── __init__.py
├── analyzer.py
├── authorization.py
├── catalog.py
├── classification.py
├── evidence.py
├── integrations.py
├── revocation.py
```

## Getting Started

Install dependencies with `uv sync` or `pip install -e packages/agentcore-governance`. Modules currently expose placeholder implementations and will be filled in during subsequent phases.

## Next Steps

1. Implement catalog aggregation and analyzer scoring.
2. Wire tool classification registry loading.
3. Add governance API handlers aligned with `specs/001-security-role-audit/contracts/openapi.yaml`.
