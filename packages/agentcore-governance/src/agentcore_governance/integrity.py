"""Integrity hashing utilities."""

from __future__ import annotations

import hashlib
from typing import Iterable


def compute_integrity_hash(fields: Iterable[str]) -> str:
    """Compute a deterministic SHA256 hash from the provided string fields."""
    concatenated = "|".join(fields)
    digest = hashlib.sha256(concatenated.encode("utf-8"))
    return digest.hexdigest()
