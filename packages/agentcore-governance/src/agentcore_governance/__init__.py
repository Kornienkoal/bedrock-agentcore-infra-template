"""Governance package namespace for security audit utilities."""

from importlib import metadata

__all__ = ["__version__"]


def __version__() -> str:
    """Return the installed version of the governance package."""
    try:
        return metadata.version("agentcore-governance")
    except metadata.PackageNotFoundError:
        return "0.0.0"
