"""Catalog aggregation utilities for governance reporting."""

from __future__ import annotations

from typing import Iterable, Mapping, MutableMapping


def fetch_principal_catalog(*, environments: Iterable[str] | None = None) -> list[dict[str, object]]:
    """Return a normalized catalog of principals.

    Placeholder implementation until IAM/SSM integration lands.
    """
    raise NotImplementedError("Catalog aggregation not yet implemented")


def summarize_policy_footprint(policy_documents: Iterable[Mapping[str, object]]) -> MutableMapping[str, object]:
    """Compute a basic policy footprint summary from raw IAM policy documents."""
    raise NotImplementedError("Policy footprint summarizer not yet implemented")
