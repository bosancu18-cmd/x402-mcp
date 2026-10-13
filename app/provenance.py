"""Authorship / IP watermark embedded in MCP tool meta envelopes."""

from __future__ import annotations

from app.config import settings


def authorship_meta() -> dict[str, str]:
    """Stable provenance block copied into every commerce ``meta`` response."""
    return {
        "project": "x402-mcp",
        "repository": settings.authorship_repository.rstrip("/"),
        "license": "Apache-2.0",
        "notice": settings.authorship_notice_path,
        "contact": settings.contact_email,
    }
