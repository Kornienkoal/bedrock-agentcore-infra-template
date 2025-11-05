"""ABAC feasibility matrix exporter."""

from __future__ import annotations

from typing import Iterable, Mapping


def export_abac_matrix(records: Iterable[Mapping[str, str]]) -> dict[str, list[Mapping[str, str]]]:
    """Return a serializable representation of the ABAC feasibility matrix."""
    raise NotImplementedError("ABAC matrix exporter not yet implemented")
