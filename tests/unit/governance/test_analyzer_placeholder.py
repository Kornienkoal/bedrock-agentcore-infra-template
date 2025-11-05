"""Placeholder tests for the governance analyzer module."""

import pytest

from agentcore_governance import analyzer


@pytest.mark.skip(reason="Analyzer implementation pending Phase 2 tasks")
def test_compute_least_privilege_score_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        analyzer.compute_least_privilege_score(())
