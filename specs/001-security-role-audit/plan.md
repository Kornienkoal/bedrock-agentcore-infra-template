# Implementation Plan: Enterprise Security Role & Token Audit and Control Model

**Branch**: `001-security-role-audit` | **Date**: 2025-11-05 | **Spec**: `specs/001-security-role-audit/spec.md`
**Input**: Feature specification from `specs/001-security-role-audit/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Deliver phased governance capabilities over principals (IAM roles), tokens, tool/agent access paths, and audit traces. Phase 0 establishes decisions and clarifies RBAC baseline and static third-party allowlist. Phase 1 designs catalog, classification, authorization enforcement mapping, and API contracts. Phase 2 (future) implements operational automation (outside this planning scope). Technical approach: augment existing Terraform/IAM structure with non-invasive catalog/reporting layer and REST governance APIs; maintain RBAC now, produce ABAC feasibility artifact.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python (repo already Python-based; governance layer will reuse Python 3.13 Lambda / runtime tooling)
**Primary Dependencies**: AWS IAM, SSM, CloudWatch Logs, existing agentcore-common; potential addition of lightweight REST framework (NEEDS CLARIFICATION: adopt FastAPI vs. reuse existing runtime entrypoints for governance API?)
**Storage**: SSM for identifiers; audit logs remain CloudWatch; catalog envisioned as derived (no new persistent DB initially) — may stage to DynamoDB if retention queries become heavy.
**Testing**: pytest (existing harness) + contract tests for governance API; synthetic revocation tests via scheduled test functions.
**Target Platform**: AWS Lambda + existing AgentCore runtime containers.
**Project Type**: Multi-agent backend template extension (no separate frontend initially).
**Performance Goals**: Governance API p95 < 1s; catalog generation batch completes < 5m daily; revocation propagation ≤ SLA (spec defined).
**Constraints**: No infrastructure creation outside Terraform; read-only queries must not cause >10% increase in CloudWatch costs; avoid persistent state until justified.
**Scale/Scope**: Internal enterprise (hundreds of agents, dozens of tools, thousands of users) — design choices anticipate moderate growth, not internet-scale.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Alignment | Notes |
|-----------|-----------|-------|
| P1 Template-First | PASS | Extends template with opinionated governance defaults. |
| P2 AWS-Native | PASS | Leverages IAM, SSM, CloudWatch; no custom infra replacements. |
| P3 Terraform Only | PASS | Any new persistent store deferred; if DynamoDB added later must be Terraform-managed. |
| P4 Two-Phase Model | PASS | Governance service logic treated as agent/tool extension; infra unchanged. |
| P5 Multi-Agent Infra | PASS | Shared catalog; no per-agent infra modifications required. |
| P6 Security & Identity | PASS | Enhances least privilege; no long-lived creds introduced. |
| P7 Observability | PASS | Correlation IDs reused; adds integrity checks. |
| P8 Testing Discipline | PASS (Planned) | Will add contract + synthetic tests. |
| P9 Documentation & Onboarding | PASS (Planned) | Quickstart to be created in Phase 1. |
| P10 Versioning | PASS | Adds features without breaking existing agents. |

No violations; proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: Enhance existing `packages/` with optional `agentcore-governance` package (Python) housing catalog generation and API layer; reuse existing `agents/` and `infrastructure/terraform` untouched. Testing integrated into `tests/unit/packages` and new `tests/integration/governance`. No new frontend directory. Contracts stored under `specs/001-security-role-audit/contracts/`.

## Complexity Tracking

No constitution violations; tracking not required at this stage.

---

## Phase 0: Research Tasks & Resolution

### Extracted Unknowns
- Adoption of FastAPI vs. reuse existing runtime for governance endpoints.
- Need for persistent catalog store vs. on-demand aggregation.
- Approach for ABAC feasibility assessment tooling format.

### Research Decisions (see `research.md` for detailed rationale)
- Choose on-demand aggregation initially (no persistent DB) to reduce infra footprint.
- Defer FastAPI; reuse lightweight Lambda handlers collocated with governance package for minimal complexity.
- ABAC feasibility documented as attribute matrix (CSV/Markdown) with candidate sources (tags, environment, sensitivity).

## Phase 1: Design Outputs
Planned artifacts: `data-model.md`, `contracts/openapi.yaml`, `quickstart.md`.

## Phase 2: (Out of Current Scope)
Implementation tasks will be generated later (`tasks.md`).

## Post-Design Constitution Re-Check (Placeholder)
Will confirm alignment after data model and contracts creation.
