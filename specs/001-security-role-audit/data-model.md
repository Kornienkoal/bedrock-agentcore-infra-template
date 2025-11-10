# Data Model: Governance & Security Audit

## Overview
Defines logical (not implementation-specific) entities required to support cataloging, classification, authorization control, audit correlation, and evidence pack generation. All entities are technology-agnostic.

## Entities

### Principal
- id: string (ARN or synthesized identifier)
- type: enum (execution_role, gateway_role, provisioner_role, tool_role, knowledge_role)
- environment: string
- namespace: string
- owner: string (team or individual tag)
- purpose: string (human readable)
- created_at: timestamp
- last_used_at: timestamp | null
- risk_rating: enum (LOW, MODERATE, HIGH)
- tags: map<string,string>
- status: enum (active, deprecated, revoked)
- approvals: list<ApprovalRecord>
- policy_summary: PolicyFootprint

### PolicyFootprint
- attached_policies: list<string>
- action_count: integer
- wildcard_actions: list<string>
- resource_scope_wideness: enum (NARROW, MODERATE, BROAD)
- least_privilege_score: float (0..100)

### Tool
- id: string (tool name)
- lambda_function: string (function identifier)
- classification: enum (LOW, MODERATE, SENSITIVE)
- description: string
- owner: string
- external_connectivity: enum (NONE, LIMITED, INTERNET)
- allowed_agents: list<string>
- status: enum (active, deprecated)
- approval_record: ApprovalRecord | null (required if SENSITIVE)

### Agent
- id: string (agent name)
- namespace: string
- description: string
- authorized_tools: list<string>
- memory_profile: MemoryProfile
- status: enum (active, retired)

### MemoryProfile
- strategies: list<string>
- ttl_days: integer
- enabled: boolean

### Integration (Third-Party Allowlist Entry)
- id: string
- name: string
- justification: string
- approved_targets: list<string>
- approved_by: string
- approved_at: timestamp
- expires_at: timestamp | null
- status: enum (active, expired, revoked, denied)

### PolicyDecision
- id: string (uuid)
- timestamp: timestamp
- subject_type: enum (user, agent, integration)
- subject_id: string
- action: string
- resource: string
- effect: enum (allow, deny)
- policy_reference: string
- correlation_id: string
- reason: string | null

### AuditEvent
- id: string
- event_type: enum (agent_invocation, tool_invocation, memory_access, revocation, classification_change, evidence_pack_request)
- timestamp: timestamp
- correlation_id: string
- principal_chain: list<string>
- outcome: string
- latency_ms: integer
- integrity_hash: string

### Revocation
- id: string
- subject_type: enum (user, integration, tool, agent, principal)
- subject_id: string
- initiated_by: string
- initiated_at: timestamp
- scope: enum (user_access, tool_access, integration_access, principal_assume)
- propagated_at: timestamp | null
- status: enum (pending, complete, failed)

### ApprovalRecord
- id: string
- approved_by: string
- approved_at: timestamp
- justification: string
- scope: enum (tool_sensitive, integration_access, principal_elevation)

### ClassificationGlossaryEntry
- label: string
- criteria: string
- requires_approval: boolean
- review_interval_days: integer

## Relationships
- Principal 1..* PolicyFootprint (snapshot relationship via aggregation)
- Tool *..* Agent (authorized_tools membership)
- Tool 0..1 ApprovalRecord
- Integration *..* Gateway Targets (approved_targets references tool or agent endpoints)
- AuditEvent *..1 PolicyDecision (event may embed decision reference)
- Revocation *..1 Subject (logical reference only)
- ClassificationGlossaryEntry *..* Tool (by label)

## Validation Rules
- Tool.classification = SENSITIVE → approval_record != null
- Principal.least_privilege_score >= 95 for PASS; < 95 flagged
- Integration.expires_at must be > approved_at if status=active
- Revocation.status=complete → propagated_at != null
- PolicyDecision.effect=deny → reason != null
- AuditEvent.integrity_hash must validate against recomputed hash of core fields

## State Transitions
- Principal: active → deprecated (after owner signals retirement) → revoked (after privileges removed)
- Tool: active → deprecated (removed from gateway targets) → retired (lambda removed)
- Integration: active → expired (expires_at passed) → revoked (manual) | denied (initial rejection)
- Revocation: pending → complete | failed

## Derived Metrics
- least_privilege_score = (1 - (wildcard_actions / action_count)) * 100 (adjusted by resource_scope_wideness penalty)
- conformance_score = avg(principal.least_privilege_score)
- orphan_rate = count(principals without owner) / total_principals

## Open Questions (Design)
- Persistent storage escalation threshold (catalog snapshot growth) — address post Phase 1 measurements.
- Standardization of integrity_hash algorithm (likely SHA256 over deterministic concatenation).

## ABAC Feasibility Attributes (Matrix Extract)
| Attribute | Source | Potential Use | Collection Method |
|-----------|--------|---------------|-------------------|
| environment | tags/SSM path | Scope decisions | Parse ARN/SSM hierarchy |
| sensitivity_level | tool registry | Conditional access | Read YAML registry |
| owner | IAM tags | Ownership enforcement | IAM listing API |
| risk_rating | analyzer output | Elevated review | Computed score classification |
| last_used_at | CloudWatch logs | Deactivation triggers | Log query aggregation |

This model intentionally avoids implementation bindings (no specific DB schemas). It supports report generation, API contract design, and future ABAC compatibility.
