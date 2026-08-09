#!/usr/bin/env python3
"""Pure, fail-closed identity contract for the SMM4 authority join."""

from __future__ import annotations

import posixpath
import re
from typing import Any


FULL_IDENTITY_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
    "mode_octal",
    "device",
    "inode",
    "link_count",
)
PROJECTION_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
    "mode_octal",
)
PHYSICAL_IDENTITY_FIELDS = (
    "device",
    "inode",
    "link_count",
)
LEGACY_MANAGER_IDENTITY_FIELDS = (
    "requested_path",
    "path",
    "size_bytes",
    "mode",
    "mode_octal",
    "sha256",
    "device",
    "inode",
)

_LOWER_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MODE_OCTAL = re.compile(r"[0-7]{4}\Z")


class IdentityContractError(RuntimeError):
    """Raised when an SMM4 file identity is malformed or has drifted."""


def _require_exact_object(value: Any, fields: tuple[str, ...], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IdentityContractError(f"{label}: identity is not an object")

    expected = set(fields)
    missing = [field for field in fields if field not in value]
    extra = sorted((repr(field) for field in value if field not in expected))
    if missing:
        raise IdentityContractError(f"{label}: missing fields {missing!r}")
    if extra:
        raise IdentityContractError(f"{label}: unexpected fields {extra!r}")
    return {field: value[field] for field in fields}


def _require_canonical_path(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise IdentityContractError(f"{label}: path is not a string")
    if "\x00" in value:
        raise IdentityContractError(f"{label}: path contains NUL")
    if not posixpath.isabs(value) or value.startswith("//"):
        raise IdentityContractError(f"{label}: path is not an absolute canonical realpath")
    if posixpath.normpath(value) != value:
        raise IdentityContractError(f"{label}: path is not an absolute canonical realpath")
    return value


def _require_exact_int(value: Any, field: str, label: str, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise IdentityContractError(
            f"{label}: {field} must be an exact int greater than or equal to {minimum}"
        )
    return value


def _validate_content_fields(identity: dict[str, Any], label: str) -> None:
    _require_canonical_path(identity["path"], label)
    _require_exact_int(identity["size_bytes"], "size_bytes", label, minimum=0)

    digest = identity["sha256"]
    if not isinstance(digest, str) or _LOWER_SHA256.fullmatch(digest) is None:
        raise IdentityContractError(f"{label}: sha256 is not lowercase 64-hex")

    mode = identity["mode_octal"]
    if not isinstance(mode, str) or _MODE_OCTAL.fullmatch(mode) is None:
        raise IdentityContractError(f"{label}: mode_octal is not four octal digits")


def validate_full_identity(value: Any, label: str) -> dict[str, Any]:
    """Validate and return an ordered copy of an exact seven-field identity."""

    identity = _require_exact_object(value, FULL_IDENTITY_FIELDS, label)
    _validate_content_fields(identity, label)
    _require_exact_int(identity["device"], "device", label, minimum=0)
    _require_exact_int(identity["inode"], "inode", label, minimum=1)
    link_count = _require_exact_int(identity["link_count"], "link_count", label, minimum=1)
    if link_count != 1:
        raise IdentityContractError(f"{label}: link_count must equal 1")
    return identity


def validate_projection(value: Any, label: str) -> dict[str, Any]:
    """Validate and return an ordered copy of an exact content projection."""

    projection = _require_exact_object(value, PROJECTION_FIELDS, label)
    _validate_content_fields(projection, label)
    return projection


def validate_legacy_manager_identity(value: Any, label: str) -> dict[str, Any]:
    """Validate the manager helper's exact pre-SMM4 eight-field identity."""

    identity = _require_exact_object(value, LEGACY_MANAGER_IDENTITY_FIELDS, label)
    _require_canonical_path(identity["requested_path"], f"{label} requested")
    _require_canonical_path(identity["path"], f"{label} resolved")
    _require_exact_int(identity["size_bytes"], "size_bytes", label, minimum=1)
    mode = _require_exact_int(identity["mode"], "mode", label, minimum=0)
    if mode > 0o7777:
        raise IdentityContractError(f"{label}: mode must be less than or equal to 07777")

    digest = identity["sha256"]
    if not isinstance(digest, str) or _LOWER_SHA256.fullmatch(digest) is None:
        raise IdentityContractError(f"{label}: sha256 is not lowercase 64-hex")

    mode_octal = identity["mode_octal"]
    if (
        not isinstance(mode_octal, str)
        or _MODE_OCTAL.fullmatch(mode_octal) is None
        or mode_octal != f"{mode:04o}"
    ):
        raise IdentityContractError(f"{label}: mode and mode_octal disagree")

    _require_exact_int(identity["device"], "device", label, minimum=0)
    _require_exact_int(identity["inode"], "inode", label, minimum=1)
    return identity


def canonical_content_projection(value: Any, label: str) -> dict[str, Any]:
    """Project one validated full identity onto the exact content fields."""

    identity = validate_full_identity(value, label)
    return {field: identity[field] for field in PROJECTION_FIELDS}


def assert_legacy_manager_identity_join(
    legacy_identity: Any,
    expected_requested_path: Any,
    resolved_requested_path: Any,
    expected_full: Any,
    actual_full: Any,
    label: str,
) -> dict[str, Any]:
    """Join one exact legacy manager identity to a live, authority-pinned full7."""

    legacy = validate_legacy_manager_identity(
        legacy_identity,
        f"{label} legacy identity",
    )
    expected_requested = _require_canonical_path(
        expected_requested_path,
        f"{label} expected requested",
    )
    resolved_requested = _require_canonical_path(
        resolved_requested_path,
        f"{label} live resolved requested",
    )
    pinned_full = validate_full_identity(
        expected_full,
        f"{label} expected full identity",
    )
    observed_full = validate_full_identity(
        actual_full,
        f"{label} actual full identity",
    )

    if legacy["requested_path"] != expected_requested:
        raise IdentityContractError(f"{label}: requested_path drifted")
    if legacy["path"] != resolved_requested:
        raise IdentityContractError(f"{label}: requested path resolution drifted")
    if legacy["path"] != pinned_full["path"]:
        raise IdentityContractError(f"{label}: resolved path drifted")
    for field in (
        "size_bytes",
        "sha256",
        "mode_octal",
        "device",
        "inode",
    ):
        if legacy[field] != pinned_full[field]:
            raise IdentityContractError(f"{label}: legacy {field} drifted")

    projection = canonical_content_projection(
        pinned_full,
        f"{label} expected full identity",
    )
    assert_identity_join(
        pinned_full,
        projection,
        observed_full,
        f"{label} live full identity",
    )
    return {
        "legacy_identity": legacy,
        "expected_requested_path": expected_requested,
        "resolved_requested_path": resolved_requested,
        "expected_full_identity": pinned_full,
        "observed_full_identity": observed_full,
    }


def assert_identity_join(
    expected_full: Any,
    expected_projection: Any,
    actual_full: Any,
    label: str,
) -> dict[str, Any]:
    """Fail closed unless writer, canonical projection, and payload identity join."""

    pinned_full = validate_full_identity(expected_full, f"{label} expected full identity")
    pinned_projection = validate_projection(
        expected_projection,
        f"{label} expected content projection",
    )
    observed_full = validate_full_identity(actual_full, f"{label} actual full identity")

    for field in PROJECTION_FIELDS:
        if pinned_full[field] != pinned_projection[field]:
            raise IdentityContractError(
                f"{label}: expected content projection {field} disagrees with expected full identity"
            )
        if observed_full[field] != pinned_projection[field]:
            raise IdentityContractError(f"{label}: {field} drifted")

    for field in PHYSICAL_IDENTITY_FIELDS:
        if observed_full[field] != pinned_full[field]:
            raise IdentityContractError(f"{label}: {field} drifted")

    return {field: observed_full[field] for field in PROJECTION_FIELDS}


__all__ = [
    "IdentityContractError",
    "assert_legacy_manager_identity_join",
    "assert_identity_join",
    "canonical_content_projection",
    "validate_full_identity",
    "validate_legacy_manager_identity",
    "validate_projection",
]
