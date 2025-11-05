"""Tool classification registry loader and helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

CLASSIFICATION_REGISTRY_PATH = Path("security/tool-classification.yaml")


def load_tool_classifications(registry_path: Path | None = None) -> dict[str, Any]:
    """Load the tool classification registry from YAML.

    Args:
        registry_path: Optional custom path to registry file

    Returns:
        Dictionary with 'tools' key containing list of tool records

    Raises:
        FileNotFoundError: If registry file doesn't exist
        yaml.YAMLError: If registry file is malformed
    """
    path = registry_path or CLASSIFICATION_REGISTRY_PATH

    if not path.exists():
        logger.warning(f"Classification registry not found at {path}, returning empty registry")
        return {"tools": []}

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Registry must be a dictionary, got {type(data)}")

        tools = data.get("tools", [])
        if not isinstance(tools, list):
            raise ValueError(f"'tools' must be a list, got {type(tools)}")

        # Validate tool entries
        for tool in tools:
            _validate_tool_entry(tool)

        logger.info(f"Loaded {len(tools)} tool classifications from {path}")
        return data

    except yaml.YAMLError as e:
        logger.error(f"Failed to parse classification registry: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load classification registry: {e}")
        raise


def _validate_tool_entry(tool: dict[str, Any]) -> None:
    """Validate a single tool classification entry.

    Args:
        tool: Tool record dictionary

    Raises:
        ValueError: If required fields are missing or invalid
    """
    required_fields = ["id", "classification", "owner"]
    for field in required_fields:
        if field not in tool:
            raise ValueError(f"Tool entry missing required field: {field}")

    valid_classifications = ["LOW", "MODERATE", "SENSITIVE"]
    if tool["classification"] not in valid_classifications:
        raise ValueError(f"Invalid classification: {tool['classification']}")

    # SENSITIVE tools require approval reference
    if tool["classification"] == "SENSITIVE" and not tool.get("approval_reference"):
        logger.warning(f"Tool {tool['id']} is SENSITIVE but missing approval_reference")


def get_tool_classification(
    tool_id: str, registry: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Retrieve classification for a specific tool.

    Args:
        tool_id: Tool identifier
        registry: Optional pre-loaded registry (loads from file if None)

    Returns:
        Tool record or None if not found
    """
    if registry is None:
        registry = load_tool_classifications()

    tools = registry.get("tools", [])
    for tool in tools:
        if isinstance(tool, dict) and tool.get("id") == tool_id:
            return dict(tool)

    return None


def requires_approval(tool_id: str, registry: dict[str, Any] | None = None) -> bool:
    """Check if a tool requires approval for usage.

    Args:
        tool_id: Tool identifier
        registry: Optional pre-loaded registry

    Returns:
        True if tool is SENSITIVE and requires approval
    """
    tool = get_tool_classification(tool_id, registry)
    if not tool:
        return False

    return tool.get("classification") == "SENSITIVE"
