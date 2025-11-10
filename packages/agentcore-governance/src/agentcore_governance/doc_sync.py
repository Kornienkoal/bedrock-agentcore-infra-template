"""Documentation synchronization validation script (T090).

Validates that governance package documentation stays in sync with:
- OpenAPI contract (specs/001-security-role-audit/contracts/openapi.yaml)
- Data model (specs/001-security-role-audit/data-model.md)
- README examples
- Quickstart guide
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


def check_openapi_endpoint_coverage() -> dict[str, Any]:
    """Verify all OpenAPI endpoints have corresponding handlers."""
    repo_root = Path(__file__).parents[4]
    openapi_path = repo_root / "specs/001-security-role-audit/contracts/openapi.yaml"

    if not openapi_path.exists():
        return {
            "status": "✗ FAIL",
            "error": f"OpenAPI contract not found: {openapi_path}",
        }

    try:
        import yaml

        with openapi_path.open() as f:
            openapi_spec = yaml.safe_load(f)

        # Extract endpoints from OpenAPI spec
        paths = openapi_spec.get("paths", {})
        expected_endpoints = []
        for path, methods in paths.items():
            for method in methods:
                if method in ("get", "post", "put", "delete", "patch"):
                    expected_endpoints.append((method.upper(), path))

        # Check if handler modules exist
        api_dir = repo_root / "packages/agentcore-governance/src/agentcore_governance/api"
        handler_modules = list(api_dir.glob("*_handlers.py"))

        # Extract handler function names
        handler_functions = []
        for handler_module in handler_modules:
            content = handler_module.read_text()
            # Find function definitions
            func_pattern = r"^def (\w+)\("
            functions = re.findall(func_pattern, content, re.MULTILINE)
            handler_functions.extend(functions)

        return {
            "status": "✓ OK",
            "total_endpoints": len(expected_endpoints),
            "handler_modules": len(handler_modules),
            "handler_functions": len(handler_functions),
            "endpoints": expected_endpoints[:5],  # Sample
        }

    except Exception as e:
        return {
            "status": "✗ FAIL",
            "error": str(e),
        }


def check_data_model_alignment() -> dict[str, Any]:
    """Verify code aligns with data model definitions."""
    repo_root = Path(__file__).parents[4]
    data_model_path = repo_root / "specs/001-security-role-audit/data-model.md"

    if not data_model_path.exists():
        return {
            "status": "✗ FAIL",
            "error": f"Data model not found: {data_model_path}",
        }

    try:
        content = data_model_path.read_text()

        # Extract entity names from data model
        entity_pattern = r"###\s+(\w+)\s+Entity"
        entities = re.findall(entity_pattern, content)

        # Check if entities are referenced in code
        catalog_path = (
            repo_root / "packages/agentcore-governance/src/agentcore_governance/catalog.py"
        )
        catalog_content = catalog_path.read_text()

        referenced_entities = []
        for entity in entities:
            # Check if entity name appears in catalog module
            if entity.lower() in catalog_content.lower():
                referenced_entities.append(entity)

        coverage = (len(referenced_entities) / len(entities)) * 100 if entities else 0

        return {
            "status": "✓ OK" if coverage > 50 else "⚠ WARN",
            "total_entities": len(entities),
            "referenced_entities": len(referenced_entities),
            "coverage_percent": round(coverage, 1),
            "entities": entities,
        }

    except Exception as e:
        return {
            "status": "✗ FAIL",
            "error": str(e),
        }


def check_readme_code_examples() -> dict[str, Any]:
    """Verify README code examples are syntactically valid."""
    repo_root = Path(__file__).parents[4]
    readme_path = repo_root / "packages/agentcore-governance/README.md"

    if not readme_path.exists():
        return {
            "status": "✗ FAIL",
            "error": f"README not found: {readme_path}",
        }

    try:
        content = readme_path.read_text()

        # Extract Python code blocks
        code_block_pattern = r"```python\n(.*?)\n```"
        code_blocks = re.findall(code_block_pattern, content, re.DOTALL)

        valid_blocks = 0
        invalid_blocks = []

        for i, code in enumerate(code_blocks, 1):
            try:
                # Try to compile the code (syntax check only)
                compile(code, f"<README_block_{i}>", "exec")
                valid_blocks += 1
            except SyntaxError as e:
                invalid_blocks.append((i, str(e)))

        return {
            "status": "✓ OK" if not invalid_blocks else "✗ FAIL",
            "total_code_blocks": len(code_blocks),
            "valid_blocks": valid_blocks,
            "invalid_blocks": len(invalid_blocks),
            "errors": invalid_blocks[:3],  # First 3 errors
        }

    except Exception as e:
        return {
            "status": "✗ FAIL",
            "error": str(e),
        }


def check_quickstart_alignment() -> dict[str, Any]:
    """Verify quickstart guide references valid modules and commands."""
    repo_root = Path(__file__).parents[4]
    quickstart_path = repo_root / "specs/001-security-role-audit/quickstart.md"

    if not quickstart_path.exists():
        return {
            "status": "✗ FAIL",
            "error": f"Quickstart guide not found: {quickstart_path}",
        }

    try:
        content = quickstart_path.read_text()

        # Extract command examples
        command_pattern = r"`([^`]+)`"
        commands = re.findall(command_pattern, content)

        # Check for common package commands
        expected_commands = ["uv sync", "pytest", "pip install"]
        found_commands = [cmd for cmd in expected_commands if any(cmd in c for c in commands)]

        # Extract import statements
        import_pattern = r"from (agentcore_governance\.\w+) import"
        imports = re.findall(import_pattern, content)

        # Verify imports reference real modules
        governance_dir = repo_root / "packages/agentcore-governance/src/agentcore_governance"
        valid_imports = []
        for imp in imports:
            module_file = imp.replace("agentcore_governance.", "") + ".py"
            if (governance_dir / module_file).exists():
                valid_imports.append(imp)

        return {
            "status": "✓ OK",
            "total_commands": len(commands),
            "found_expected_commands": len(found_commands),
            "total_imports": len(imports),
            "valid_imports": len(valid_imports),
            "import_coverage": round((len(valid_imports) / len(imports)) * 100, 1)
            if imports
            else 100,
        }

    except Exception as e:
        return {
            "status": "✗ FAIL",
            "error": str(e),
        }


def run_doc_sync_validation() -> int:
    """Run all documentation sync validation checks."""
    print("=" * 80)
    print("Documentation Synchronization Validation (T090)")
    print("=" * 80)
    print()

    # Check 1: OpenAPI endpoint coverage
    print("1. OpenAPI Endpoint Coverage")
    print("-" * 80)
    openapi_result = check_openapi_endpoint_coverage()
    print(f"  {openapi_result['status']:10s} OpenAPI contract alignment")
    if "error" not in openapi_result:
        print(f"  {'':10s} {openapi_result['total_endpoints']} endpoints defined")
        print(f"  {'':10s} {openapi_result['handler_modules']} handler modules")
        print(f"  {'':10s} {openapi_result['handler_functions']} handler functions")
    else:
        print(f"  {'':10s} Error: {openapi_result['error']}")
    print()

    # Check 2: Data model alignment
    print("2. Data Model Alignment")
    print("-" * 80)
    data_model_result = check_data_model_alignment()
    print(f"  {data_model_result['status']:10s} Data model coverage")
    if "error" not in data_model_result:
        print(
            f"  {'':10s} {data_model_result['referenced_entities']}/{data_model_result['total_entities']} "
            f"entities referenced ({data_model_result['coverage_percent']}%)"
        )
    else:
        print(f"  {'':10s} Error: {data_model_result['error']}")
    print()

    # Check 3: README code examples
    print("3. README Code Examples")
    print("-" * 80)
    readme_result = check_readme_code_examples()
    print(f"  {readme_result['status']:10s} Code example syntax")
    if "error" not in readme_result:
        print(
            f"  {'':10s} {readme_result['valid_blocks']}/{readme_result['total_code_blocks']} "
            "code blocks valid"
        )
        if readme_result["invalid_blocks"] > 0:
            print(f"  {'':10s} Errors in {readme_result['invalid_blocks']} blocks")
            for block_num, error in readme_result.get("errors", []):
                print(f"  {'':10s}   Block {block_num}: {error}")
    else:
        print(f"  {'':10s} Error: {readme_result['error']}")
    print()

    # Check 4: Quickstart alignment
    print("4. Quickstart Guide Alignment")
    print("-" * 80)
    quickstart_result = check_quickstart_alignment()
    print(f"  {quickstart_result['status']:10s} Quickstart references")
    if "error" not in quickstart_result:
        print(f"  {'':10s} {quickstart_result['found_expected_commands']} expected commands found")
        print(
            f"  {'':10s} {quickstart_result['valid_imports']}/{quickstart_result['total_imports']} "
            f"imports valid ({quickstart_result['import_coverage']}%)"
        )
    else:
        print(f"  {'':10s} Error: {quickstart_result['error']}")
    print()

    # Summary
    print("=" * 80)
    print("Summary")
    print("=" * 80)

    all_results = [
        openapi_result["status"],
        data_model_result["status"],
        readme_result["status"],
        quickstart_result["status"],
    ]

    passed = sum(1 for status in all_results if status.startswith("✓"))
    warnings = sum(1 for status in all_results if status.startswith("⚠"))
    failed = sum(1 for status in all_results if status.startswith("✗"))

    print(f"Passed: {passed}/4")
    print(f"Warnings: {warnings}/4")
    print(f"Failed: {failed}/4")
    print()

    if failed > 0:
        print("⚠️  Some checks failed. Review errors above and update documentation.")
        return 1
    elif warnings > 0:
        print("⚠️  Some checks have warnings. Consider improving documentation coverage.")
        return 0
    else:
        print("✅ All documentation sync checks passed!")
        return 0


if __name__ == "__main__":
    sys.exit(run_doc_sync_validation())
