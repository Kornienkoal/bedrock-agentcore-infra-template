# GitHub Copilot Instructions — AWS AgentCore Enterprise Toolkit

Purpose: Give AI coding agents the minimum, project‑specific context to be productive in this repository. Keep answers concrete, scoped to this codebase, and bias to AWS‑native + Terraform.

**IMPORTANT: AgentCore Documentation Source of Truth**
Before answering questions about AgentCore CLI, deployment, runtime behavior, or AWS Bedrock AgentCore features:
1. ALWAYS use the AgentCore MCP documentation tool available in VS Code MCP tools
2. Search using: `mcp_bedrock_agent_search_agentcore_docs` and `mcp_bedrock_agent_fetch_agentcore_doc`
3. Do NOT make assumptions about CLI behavior, deployment modes, or API features
4. Official docs: https://aws.github.io/bedrock-agentcore-starter-toolkit/
5. Use docs as source of truth for: `agentcore launch`, `agentcore configure`, deployment modes, memory configuration, VPC settings, and all CLI commands

Big picture (how this repo works)
- Two phases, shared once per env:
  1) Infrastructure (Terraform) → Cognito, AgentCore Gateway, Runtime IAM, Memory, Observability, and Global MCP Tools
  2) Agent code + UI → Example agent customer-support and Streamlit frontend
- Agents read configuration from SSM under /agentcore/{env}/* via agentcore-common.load_agent_config which resolves ${SSM:...} in agent-config/customer-support.yaml.

Where things live (entry points that matter)
- Infra: infrastructure/terraform/{modules,envs/*} with custom resources under modules and tests under custom-resources
- Tools (MCP on Gateway): agents/global-tools/{check_warranty,web_search}/ with tool-schema.json and lambda_function.py
- Agent runtime: agents/customer-support/runtime.py (BedrockAgentCoreApp + Strands, uses MCPClient for Gateway tools) and agents/customer-support/tools/product_tools.py (local tools)
- Frontend: services/frontend_streamlit/{main.py,auth.py,runtime_client.py,config.py}
- Shared libs: packages/agentcore-common (config, auth, observability), packages/agentcore-tools

First run (clean account; nothing provisioned)
1) Provision dev infra
  - cd infrastructure/terraform/envs/dev; terraform init; terraform plan -out plan.tfplan; terraform apply plan.tfplan
  - Verify SSM keys under /agentcore/dev/{identity,gateway,runtime,memory}/*
2) Global tools are packaged by Terraform; confirm Gateway Targets exist and tool Lambdas log invocations
3) Backend/dev loop
  - uv sync; uv run pytest tests -v; optional: uv run ruff check .
  - Run the Streamlit UI: uv run streamlit run services/frontend_streamlit/main.py (env: AGENTCORE_ENV=dev, AWS_REGION=us-east-1)

Conventions and patterns (project‑specific)
- Infra is Terraform‑only; application code must not create AWS resources. All discovery is via SSM /agentcore/{env}/*.
- IAM is family‑scoped for Bedrock models (anthropic.claude-*, amazon.titan-*), Lambda invoke narrowed to {namespace}-*-tool-*.
- Gateway targets are registered by a Terraform custom resource that reads SSM gateway_id and each tool’s tool-schema.json.
- Runtime reads gateway_id from config, fetches gatewayUrl via bedrock-agentcore-control, and uses MCP over HTTP with the caller’s Authorization header.

Add a new MCP tool (shared)
1) Create agents/global-tools/{tool}/ with lambda_function.py, tool-schema.json, and optional requirements.txt
2) Add tool to your env’s tfvars (global_tools block); terraform apply in env folder registers/updates Gateway Targets
3) Authorize its use in agent config (allowed_tools) and call by name via Gateway MCP

Extend or add an agent
- Copy agents/customer-support as a starting point; update agent-config/*.yaml (model_id, tools, memory). Do not reference non‑existent deploy scripts; local dev = tests + Streamlit UI.
- Local tools live under agents/<agent>/tools and are imported in runtime.py.

Observability and debugging
- CloudWatch log groups and X‑Ray tracing are enabled by the Observability module; runtime and tool Lambdas emit logs; dashboards/alarms are provisioned by Terraform.
- If SSM resolution fails locally, agentcore-common leaves placeholders and logs a warning; ensure AWS creds/region and that Terraform applied.

Pitfalls to avoid here
- Don’t create Cognito/Gateway/Memory via SDK; never hardcode ARNs/URLs; always read from SSM. Don’t reference scripts that don’t exist in scripts/.
- Keep tf IAM least‑privilege; narrow Lambda invoke patterns and Bedrock model families; avoid "*" except where AWS requires it (e.g., ECR auth).

Protected files (do not modify)
- .bedrock_agentcore.yaml — Managed by humans/infra. Never edit, rewrite, or auto-generate. Treat as read-only and respect values like memory_name.

Starter scenario you can implement today
- “Warranty & Docs Assistant”: use local tools get_product_info, search_documentation and shared tools check_warranty, web_search. The Streamlit UI authenticates with Cognito and invokes the AgentCore runtime; Gateway tools require an Authorization header, which the runtime passes through.

Useful files to cite in answers
- agents/customer-support/runtime.py, agents/customer-support/tools/product_tools.py
- agent-config/customer-support.yaml (shows ${SSM:...} and allowed tools)
- agents/global-tools/*/tool-schema.json and lambda_function.py
- infrastructure/terraform/README.md and envs/dev/* for exact infra steps
- services/frontend_streamlit/README.md for UI run instructions

If anything is unclear or missing for your current task (e.g., exact tfvars shape for global_tools, or CloudWatch dashboard names), ask to update the stage README and we’ll patch it in this repo.
