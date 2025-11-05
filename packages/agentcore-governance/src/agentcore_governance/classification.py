"""Tool classification registry loader and helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


CLASSIFICATION_REGISTRY_PATH = Path("security/tool-classification.yaml")


def load_tool_classifications(registry_path: Path | None = None) -> dict[str, Any]:
    """Load the tool classification registry from YAML.

    Placeholder until YAML schema and parsing rules are implemented.
    """
    raise NotImplementedError("Classification loader not yet implemented")
