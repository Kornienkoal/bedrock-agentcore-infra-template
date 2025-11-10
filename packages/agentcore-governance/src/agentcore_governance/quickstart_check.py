"""Quickstart validation script (T085).

Validates that governance package setup steps from quickstart.md are complete.
Checks for:
- Package installation and imports
- Classification registry file exists
- Core modules are functional
- Test fixtures are available
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def check_imports() -> dict[str, Any]:
    """Verify all core modules can be imported."""
    import_results = {}
    modules = [
        "agentcore_governance.catalog",
        "agentcore_governance.analyzer",
        "agentcore_governance.authorization",
        "agentcore_governance.classification",
        "agentcore_governance.evidence",
        "agentcore_governance.integrations",
        "agentcore_governance.revocation",
        "agentcore_governance.correlation",
        "agentcore_governance.integrity",
        "agentcore_governance.abac_matrix",
    ]

    for module in modules:
        try:
            __import__(module)
            import_results[module] = "✓ OK"
        except ImportError as e:
            import_results[module] = f"✗ FAIL: {e}"

    return import_results


def check_classification_registry() -> dict[str, Any]:
    """Verify tool classification registry file exists."""
    registry_path = Path("security/tool-classification.yaml")
    repo_root = Path(__file__).parents[4]  # Up from src/agentcore_governance/
    full_path = repo_root / registry_path

    if full_path.exists():
        try:
            import yaml

            with full_path.open() as f:
                data = yaml.safe_load(f)

            tool_count = len(data.get("tools", [])) if isinstance(data, dict) else 0
            return {
                "path": str(full_path),
                "status": "✓ OK",
                "tool_count": tool_count,
            }
        except Exception as e:
            return {
                "path": str(full_path),
                "status": f"✗ FAIL (parse error): {e}",
            }
    else:
        return {
            "path": str(full_path),
            "status": "✗ FAIL (file not found)",
        }


def check_test_infrastructure() -> dict[str, Any]:
    """Verify test directories and key test files exist."""
    repo_root = Path(__file__).parents[4]
    test_paths = [
        "tests/unit/governance",
        "tests/integration/governance",
        "tests/functional/governance",
    ]

    test_results = {}
    for test_path_str in test_paths:
        test_path = repo_root / test_path_str
        test_results[test_path_str] = "✓ OK" if test_path.exists() else "✗ FAIL (not found)"

    return test_results


def check_api_handlers() -> dict[str, Any]:
    """Verify API handler modules exist."""
    handlers = [
        "agentcore_governance.api.catalog_handlers",
        "agentcore_governance.api.authorization_handlers",
        "agentcore_governance.api.integration_handlers",
        "agentcore_governance.api.revocation_handlers",
        "agentcore_governance.api.decision_handlers",
        "agentcore_governance.api.analyzer_handlers",
        "agentcore_governance.api.evidence_handlers",
    ]

    handler_results = {}
    for handler in handlers:
        try:
            __import__(handler)
            handler_results[handler] = "✓ OK"
        except ImportError as e:
            handler_results[handler] = f"✗ FAIL: {e}"

    return handler_results


def run_validation() -> int:
    """Run all validation checks and return exit code."""
    print("=" * 80)
    print("AgentCore Governance Quickstart Validation (T085)")
    print("=" * 80)
    print()

    # Check 1: Core module imports
    print("1. Core Module Imports")
    print("-" * 80)
    import_results = check_imports()
    for module, status in import_results.items():
        print(f"  {status:10s} {module}")
    print()

    # Check 2: Classification registry
    print("2. Tool Classification Registry")
    print("-" * 80)
    registry_result = check_classification_registry()
    print(f"  {registry_result['status']:10s} {registry_result['path']}")
    if "tool_count" in registry_result:
        print(f"  {'':10s} ({registry_result['tool_count']} tools registered)")
    print()

    # Check 3: Test infrastructure
    print("3. Test Infrastructure")
    print("-" * 80)
    test_results = check_test_infrastructure()
    for test_path, status in test_results.items():
        print(f"  {status:10s} {test_path}")
    print()

    # Check 4: API handlers
    print("4. API Handler Modules")
    print("-" * 80)
    handler_results = check_api_handlers()
    for handler, status in handler_results.items():
        print(f"  {status:10s} {handler.split('.')[-1]}")
    print()

    # Summary
    print("=" * 80)
    print("Summary")
    print("=" * 80)

    all_results = {
        **import_results,
        **handler_results,
        **{registry_result["path"]: registry_result["status"]},
        **test_results,
    }

    passed = sum(1 for status in all_results.values() if status.startswith("✓"))
    failed = sum(1 for status in all_results.values() if status.startswith("✗"))
    total = passed + failed

    print(f"Passed: {passed}/{total}")
    print(f"Failed: {failed}/{total}")
    print()

    if failed > 0:
        print("⚠️  Some checks failed. Review errors above and consult quickstart.md")
        return 1
    else:
        print("✅ All checks passed! Governance package is ready.")
        return 0


if __name__ == "__main__":
    sys.exit(run_validation())
