"""Exact-status guardrails for non-authoritative IndustrialPlanner delivery surfaces."""

from __future__ import annotations

from typing import Any

_ALLOWED_NON_AUTHORITATIVE_EXACT_STATUSES = frozenset({"open", "unknown"})
_RESERVED_CERTIFIED_TOKEN = "CERTIFIED"


def normalize_non_authoritative_exact_status(raw_status: Any, *, context: str) -> str:
    """Return a canonical non-authoritative exact status or fail closed.

    The single-base delivery/release/viewer surfaces are informational mirrors;
    they are not the canonical certified_surface verifier. They may only publish
    statuses that cannot be mistaken for a certified exact proof verdict.
    """

    if not isinstance(raw_status, str):
        raise ValueError(
            f"{context}.status must be a string from "
            f"{sorted(_ALLOWED_NON_AUTHORITATIVE_EXACT_STATUSES)!r}; got {raw_status!r}"
        )
    normalized = raw_status.strip()
    if not normalized:
        raise ValueError(
            f"{context}.status must be a non-empty string from "
            f"{sorted(_ALLOWED_NON_AUTHORITATIVE_EXACT_STATUSES)!r}"
        )
    if _RESERVED_CERTIFIED_TOKEN in normalized.upper():
        raise ValueError(
            f"{context}.status may not claim 'CERTIFIED' on this non-authoritative "
            "IndustrialPlanner delivery path; exact CERTIFIED publication must be "
            "produced by the canonical certified_delivery_manifest/certified_surface verifier"
        )
    if normalized not in _ALLOWED_NON_AUTHORITATIVE_EXACT_STATUSES:
        raise ValueError(
            f"{context}.status must be one of "
            f"{sorted(_ALLOWED_NON_AUTHORITATIVE_EXACT_STATUSES)!r}; got {normalized!r}"
        )
    return normalized
