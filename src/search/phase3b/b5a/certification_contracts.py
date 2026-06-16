from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


CORE_B5A_SAFETY_FALSE_FIELDS = [
    "checkpoint_written",
    "proof_source",
    "runtime_semantics_changed",
    "candidate_elimination_claim",
    "certified_anchor_found",
    "b5a_anchor_found",
]

AUTHORIZATION_SAFETY_FALSE_FIELDS = [
    "runtime_elimination_authorized",
    "final_168h_authorized",
    "checkpoint_write_or_import_back_authorized",
    "release_viewer_frontdoor_status_promoted",
]

PREFLIGHT_MUTATION_FALSE_FIELDS = [
    "preflight_gate_mutated",
]

REVIEW_PAYLOAD_REQUIRED_FALSE_FIELDS = (
    CORE_B5A_SAFETY_FALSE_FIELDS
    + AUTHORIZATION_SAFETY_FALSE_FIELDS
    + PREFLIGHT_MUTATION_FALSE_FIELDS
)

PROMOTION_PACKET_METADATA_REQUIRED_FALSE_FIELDS = (
    ["solver_invoked"]
    + CORE_B5A_SAFETY_FALSE_FIELDS
    + AUTHORIZATION_SAFETY_FALSE_FIELDS
    + PREFLIGHT_MUTATION_FALSE_FIELDS
)

PROMOTION_PACKET_STATUS_REQUIRED_FALSE_FIELDS = (
    CORE_B5A_SAFETY_FALSE_FIELDS
    + AUTHORIZATION_SAFETY_FALSE_FIELDS
    + PREFLIGHT_MUTATION_FALSE_FIELDS
)


def required_false(mapping: Mapping[str, Any], keys: Sequence[str]) -> bool:
    """Return true only when every key is present and literally False."""

    return all(key in mapping and mapping.get(key) is False for key in keys)


def false_field_violations(
    mapping: Mapping[str, Any],
    keys: Sequence[str],
) -> dict[str, str]:
    violations: dict[str, str] = {}
    for key in keys:
        if key not in mapping:
            violations[str(key)] = "missing"
        elif mapping.get(key) is not False:
            violations[str(key)] = repr(mapping.get(key))
    return violations


def false_field_detail(
    mapping: Mapping[str, Any],
    keys: Sequence[str],
    *,
    prefix: str = "",
) -> str:
    parts: list[str] = []
    for key in keys:
        label = f"{prefix}{key}" if prefix else str(key)
        if key not in mapping:
            parts.append(f"{label}=missing")
        else:
            parts.append(f"{label}={mapping.get(key)!r}")
    return " ".join(parts)


def blocking_checks_pass(checks: Any) -> bool:
    if not isinstance(checks, list):
        return False
    for check in checks:
        if not isinstance(check, Mapping):
            return False
        if str(check.get("status")) == "pass":
            continue
        if check.get("blocking") is False:
            continue
        return False
    return True


def blocking_check_detail(checks: Any) -> str:
    if not isinstance(checks, list):
        return "checks=missing_or_not_list"
    failed: list[str] = []
    nonblocking_failed: list[str] = []
    for check in checks:
        if not isinstance(check, Mapping):
            failed.append("malformed_check")
            continue
        if str(check.get("status")) == "pass":
            continue
        check_id = str(check.get("check_id") or check.get("id") or "unknown")
        if check.get("blocking") is False:
            nonblocking_failed.append(check_id)
        else:
            failed.append(check_id)
    return (
        "blocking_failed="
        + str(failed)
        + " nonblocking_failed="
        + str(nonblocking_failed)
    )


def sha256_file(path: Path) -> str | None:
    path = Path(path)
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def chain_fingerprint(records: Sequence[Mapping[str, Any]]) -> str | None:
    material: list[dict[str, str]] = []
    for record in records:
        input_id = str(record.get("input_id") or "")
        path = str(record.get("path") or "")
        sha256 = str(record.get("sha256") or "")
        if not input_id or not path or len(sha256) != 64:
            return None
        material.append({"input_id": input_id, "path": path, "sha256": sha256})
    if not material:
        return None
    return canonical_json_sha256(material)
