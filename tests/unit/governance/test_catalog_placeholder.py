"""Placeholder tests for the governance catalog module."""

import pytest

from agentcore_governance import catalog


@pytest.mark.skip(reason="Catalog implementation pending Phase 2 tasks")
def test_fetch_principal_catalog_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        catalog.fetch_principal_catalog()
