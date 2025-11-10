#!/usr/bin/env bash
# Comprehensive governance orchestration wrapper
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

ENVIRONMENT="${AGENTCORE_ENV:-dev}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
PROFILE="${AWS_PROFILE:-}"  # optional
OUTPUT_DIR="reports"
SKIP_TESTS=false
VERBOSE=false

usage() {
  cat <<'EOF'
Usage: governance-end-to-end.sh [options]

Options:
  --environment <env>   AgentCore environment name (default: $AGENTCORE_ENV or dev)
  --region <region>     AWS region for boto3 session (default: $AWS_REGION or us-east-1)
  --profile <profile>   AWS named profile (default: $AWS_PROFILE)
  --output-dir <path>   Directory for generated artifacts (default: reports)
  --skip-tests          Skip pytest execution before orchestrator run
  --verbose             Show debug output from orchestrator
  -h, --help            Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --skip-tests)
      SKIP_TESTS=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

cd "$PROJECT_ROOT"

echo "──────────────────────────────────────────────────────────────"
echo " Governance Orchestration"
echo "──────────────────────────────────────────────────────────────"
echo "Environment : ${ENVIRONMENT}"
echo "Region      : ${REGION}"
echo "Profile     : ${PROFILE:-<default>}"
echo "Output Dir  : ${OUTPUT_DIR}"
echo "Run Tests   : $([[ "$SKIP_TESTS" == true ]] && echo "no" || echo "yes")"
echo "──────────────────────────────────────────────────────────────"

echo "Validating AWS identity..."
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "ERROR: Unable to validate AWS credentials. Run 'aws sso login' or configure credentials." >&2
  exit 1
fi

echo "AWS identity confirmed."

if [[ "$SKIP_TESTS" == false ]]; then
  echo "Running governance unit tests..."
  uv run pytest tests/unit/governance -v
  echo "Running governance integration tests..."
  uv run pytest tests/integration/governance -v
fi

echo "Executing governance orchestrator..."
ORCH_ARGS=(
  "--environment" "$ENVIRONMENT"
  "--region" "$REGION"
  "--output-dir" "$OUTPUT_DIR"
)
if [[ -n "$PROFILE" ]]; then
  ORCH_ARGS+=("--profile" "$PROFILE")
fi
if [[ "$VERBOSE" == true ]]; then
  ORCH_ARGS+=("--verbose")
fi

uv run python "${PROJECT_ROOT}/scripts/local/governance_end_to_end.py" "${ORCH_ARGS[@]}"

echo "Governance orchestration complete. Artifacts available under: ${OUTPUT_DIR}"
