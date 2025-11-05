# Research: Governance & Authorization Decisions

## Decision 1: Endpoint Framework (FastAPI vs. Lightweight Handlers)
- **Decision**: Use lightweight Lambda handlers (no FastAPI) initially.
- **Rationale**: Minimizes new dependencies; governance APIs are internal with low complexity (CRUD/report endpoints). Easier to align with P2 (AWS-native) and P3 (Terraform only infra). Avoids premature abstraction.
- **Alternatives Considered**:
  - FastAPI: Rich feature set but adds dependency and potential cold-start overhead.
  - API Gateway direct integration with existing runtime: Would mix concerns; harder to version governance endpoints.

## Decision 2: Catalog Storage (On-Demand vs. Persistent DB)
- **Decision**: On-demand aggregation from IAM, SSM, CloudWatch logs, tagging metadata.
- **Rationale**: Reduces maintenance, avoids new Terraform modules. Daily snapshot can be generated and optionally persisted later. Start simple until query latency or historical diff needs drive persistence.
- **Alternatives Considered**:
  - DynamoDB persistent store: Adds cost, schema evolution overhead early.
  - S3 object snapshots: Acceptable for archival but not needed for Phase 1.

## Decision 3: Third-Party Onboarding Model
- **Decision**: Static allowlist with manual approval and justification capture.
- **Rationale**: Internal focus; low volume; manual oversight ensures security posture. Aligns with non-goal of broad external exposure.
- **Alternatives Considered**:
  - Dynamic self-service: Overkill, increases attack surface.
  - Workflow engine integration: Adds integration complexity prematurely.

## Decision 4: Authorization Model Evolution (RBAC + ABAC Feasibility)
- **Decision**: Maintain RBAC; produce ABAC feasibility matrix (attributes: environment, tool sensitivity, owner, risk score) as a design artifact.
- **Rationale**: Avoids implementation complexity; informs future roadmap. Keeps initial scope manageable while preparing for context-aware policies.
- **Alternatives Considered**:
  - Immediate ABAC: Requires attribute sources, evaluation engine, broader testing.
  - Remain RBAC with no assessment: Risks future expensive redesign.

## Decision 5: Audit Correlation Strategy
- **Decision**: Standardize correlation ID pattern: `trace=<uuid>;user=<sub>;agent=<agent>;tool=<tool?>` appended in structured logs.
- **Rationale**: Simplifies reconstruction and evidence pack generation. Leverages existing logging foundation.
- **Alternatives Considered**:
  - Distributed trace only (X-Ray): Does not capture semantic entities cleanly.
  - New event bus: Adds infra without clear benefit yet.

## Decision 6: ABAC Feasibility Artifact Format
- **Decision**: Markdown table + CSV export enumerating attributes, source, collection method, candidate use cases.
- **Rationale**: Human-readable + parsable; supports iterative refinement.
- **Alternatives Considered**:
  - JSON schema only: Harder for stakeholder review.
  - Direct policy simulation prototypes: Too early without attribute governance.

## Decision 7: Revocation SLA Testing
- **Decision**: Synthetic scheduled Lambda invoking governance endpoints + invalidated tokens every 4h.
- **Rationale**: Ensures SC-002 monitoring; low overhead.
- **Alternatives Considered**:
  - Continuous stream testing: Unnecessary resource use.
  - Manual periodic testing: Risk of drift and unnoticed failures.

## Decision 8: Least-Privilege Analyzer Implementation
- **Decision**: Python script enumerating IAM role policies, counts non-scoped actions (e.g., `*`, service-wide), flags model family wildcards, emits conformance score.
- **Rationale**: Lightweight; no additional services. Actionable reports for remediation.
- **Alternatives Considered**:
  - External security tooling integration (e.g., AWS IAM Access Analyzer): Useful later; start internal for faster iteration.

## Decision 9: Evidence Pack Generation
- **Decision**: On-demand Lambda packaging catalog snapshot + last 24h audit logs filtered by correlation completeness + conformance score.
- **Rationale**: Meets SC-008; avoids storing redundant artifacts.
- **Alternatives Considered**:
  - Pre-generated daily archives only: Less responsive to ad-hoc audit requests.

## Decision 10: Tool Classification Workflow
- **Decision**: YAML classification registry in repo (`security/tool-classification.yaml`) with required fields; approval PR merges act as audit records.
- **Rationale**: Leverages existing version control; minimal overhead.
- **Alternatives Considered**:
  - Separate UI: Beyond scope.
  - SSM parameters: Harder to review collaboratively.

## Summary Matrix
| Topic | Decision | Future Trigger for Revisit |
|-------|----------|----------------------------|
| Endpoint Framework | Lightweight handlers | >10 governance endpoints or complex routing |
| Catalog Storage | On-demand | Query latency > 2s or need historical diff > 30d |
| Third-Party Onboarding | Static allowlist | External integration volume > 25 apps |
| Authorization Evolution | RBAC + ABAC feasibility | Need dynamic contextual policies (e.g., time-based) |
| Audit Correlation | Unified ID pattern | Cross-account tracing required |
| ABAC Artifact Format | Markdown + CSV | Automated policy simulation tooling added |
| Revocation Testing | Synthetic scheduled | SLA breaches >2 in month |
| Least-Privilege Analyzer | Python script | Need continuous real-time alerts |
| Evidence Pack | On-demand Lambda | Auditor demand for automated daily packs |
| Tool Classification | YAML registry | Scale > 200 tools or multi-team conflicts |

All prior NEEDS CLARIFICATION items resolved; no blockers to Phase 1 design.
