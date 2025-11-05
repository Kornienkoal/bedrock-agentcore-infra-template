"""Least-privilege analyzer utilities."""

from __future__ import annotations

from typing import Iterable, Mapping


def compute_least_privilege_score(policy_documents: Iterable[Mapping[str, object]]) -> float:
    """Compute a placeholder least-privilege score from policy documents."""
    raise NotImplementedError("Least-privilege scoring not yet implemented")


def detect_orphan_principals(principals: Iterable[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Identify principals that lack required ownership metadata."""
    raise NotImplementedError("Orphan principal detection not yet implemented")
