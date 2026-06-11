"""Exact-status guardrails for non-authoritative IndustrialPlanner delivery surfaces."""

from __future__ import annotations

from typing import Any

_ALLOWED_NON_AUTHORITATIVE_EXACT_STATUSES = frozenset({"open", "unknown"})
_RESERVED_CERTIFIED_TOKEN = "CERTIFIED"
NON_AUTHORITATIVE_EXACT_OPEN_NOTE = (
    "The full-scale 70×70 exact `CERTIFIED` end-state is still an open item. "
    "This workflow validates the current single-base delivery bundle and checked-in support surfaces only; "
    "it does not claim that the full exact terminal proof artifact has already been checked in."
)
NON_AUTHORITATIVE_EXACT_UNKNOWN_NOTE = (
    "source run summary did not provide exact full-scale certification state"
)
_ALLOWED_NON_AUTHORITATIVE_EXACT_NOTES = {
    "open": frozenset({"", NON_AUTHORITATIVE_EXACT_OPEN_NOTE}),
    "unknown": frozenset({"", NON_AUTHORITATIVE_EXACT_UNKNOWN_NOTE}),
}


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


def normalize_non_authoritative_exact_note(
    raw_note: Any,
    *,
    status: str,
    context: str,
) -> str:
    """Return a canonical non-authoritative exact note or fail closed.

    Release/viewer notes are public prose, but they are still part of the exact
    status capsule.  Keep them on a tiny allowlist so a forged run summary cannot
    smuggle a CERTIFIED-looking proof claim through a status value of ``open``.
    """

    normalized_status = normalize_non_authoritative_exact_status(
        status,
        context=context,
    )
    if raw_note is None:
        normalized_note = ""
    elif isinstance(raw_note, str):
        normalized_note = raw_note.strip()
    else:
        raise ValueError(f"{context}.note must be a string")

    allowed_notes = _ALLOWED_NON_AUTHORITATIVE_EXACT_NOTES.get(normalized_status, frozenset({""}))
    if normalized_note not in allowed_notes:
        raise ValueError(
            f"{context}.note must be a canonical non-authoritative exact-status note "
            f"for status {normalized_status!r}; arbitrary exact-status prose may not be "
            "projected by this delivery path"
        )
    return normalized_note
