#!/usr/bin/env python3
"""Receipt-envelope helpers for the W0 unary-lowering canary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROTOCOL_FREEZE_COMMIT = "57a17a7672cf879fc39e0e67a044590a85cb47a2"
PRELAUNCH_REVISION_COMMIT = "988d1b787778c211f5e8b930b7f6cf093581aed8"
MANIFEST_RELATIVE_PATH = (
    "docs/research/solver_reasoning_outer_loop_reviews_20260815/"
    "experiment_two_w0_unary_lowering_canary_20260816/03_CANARY_MANIFEST.json"
)
SCHEMA_RELATIVE_PATH = (
    "docs/research/solver_reasoning_outer_loop_reviews_20260815/"
    "experiment_two_w0_unary_lowering_canary_20260816/03B_RECEIPT_ENVELOPE_SCHEMA_V1.json"
)
AUTHORITY_SOURCE_PATHS = [
    "docs/research/solver_reasoning_outer_loop_reviews_20260815/"
    "experiment_two_w0_unary_lowering_canary_20260816/00_OWNER_AUTHORIZATION_20260816.md",
    "docs/research/solver_reasoning_outer_loop_reviews_20260815/"
    "experiment_two_w0_unary_lowering_canary_20260816/01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md",
    "docs/research/solver_reasoning_outer_loop_reviews_20260815/"
    "experiment_two_w0_unary_lowering_canary_20260816/03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md",
]
DEFAULT_NON_IMPLICATIONS = [
    "no_generic_D3_or_D4_unlock",
    "no_cross_layout_family_generality",
    "no_rectangle_level_exclusion",
    "no_bound_or_certified_status_update",
    "no_production_or_publication_authority",
    "no_permission_to_modify_certified_src",
]


class ReceiptContractError(RuntimeError):
    """A receipt cannot satisfy the frozen eight-field contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise ReceiptContractError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def contract_identity(
    *,
    judgment_id: str = "J-W0-GHOST-FRONT-BOUNDARY-041-V1",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "prelaunch_revision_commit": PRELAUNCH_REVISION_COMMIT,
        "manifest_path": MANIFEST_RELATIVE_PATH,
        "manifest_sha256": sha256_file(ROOT / MANIFEST_RELATIVE_PATH),
        "receipt_schema_path": SCHEMA_RELATIVE_PATH,
        "receipt_schema_sha256": sha256_file(ROOT / SCHEMA_RELATIVE_PATH),
        "judgment_id": judgment_id,
    }
    if extra:
        identity.update(dict(extra))
    return identity


def make_receipt(
    *,
    result_kind: str,
    outcome: str,
    subject_identity: Mapping[str, Any],
    verified_scope: Mapping[str, Any],
    granted_effects: Sequence[str],
    details: Mapping[str, Any] | None = None,
    non_implications: Sequence[str] = DEFAULT_NON_IMPLICATIONS,
    contract_extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "result_kind": str(result_kind),
        "outcome": str(outcome),
        "subject_identity": dict(subject_identity),
        "verified_scope": dict(verified_scope),
        "authority_basis": {
            "authority_class": "research_only_non_authorizing",
            "source_paths": list(AUTHORITY_SOURCE_PATHS),
        },
        "granted_effects": sorted({str(value) for value in granted_effects}),
        "non_implications": sorted({str(value) for value in non_implications}),
        "contract_identity": contract_identity(extra=contract_extra),
    }
    if details:
        receipt.update(dict(details))
    validate_receipt(receipt)
    return receipt


def validate_receipt(receipt: Mapping[str, Any]) -> None:
    try:
        schema = json.loads((ROOT / SCHEMA_RELATIVE_PATH).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReceiptContractError(f"cannot read receipt schema: {exc}") from exc
    try:
        jsonschema.Draft202012Validator(schema).validate(dict(receipt))
    except jsonschema.ValidationError as exc:
        path = "/".join(str(value) for value in exc.absolute_path)
        raise ReceiptContractError(
            f"receipt envelope validation failed at {path or '<root>'}: {exc.message}"
        ) from exc


def dump_receipt(receipt: Mapping[str, Any], path: Path | None = None) -> str:
    validate_receipt(receipt)
    text = json.dumps(dict(receipt), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return text
