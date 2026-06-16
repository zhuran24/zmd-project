from __future__ import annotations

import copy
import hashlib
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence

from src.models.exact_coordinate_master import (
    EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_ENV,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES_ENV,
    EXACT_POWER_COVERAGE_WITNESS_ENCODING_BLOCK_ELEMENT,
    EXACT_POWER_COVERAGE_WITNESS_ENCODING_ENV,
    EXACT_POWER_FAMILY_LOOKUP_ENCODING_ENV,
    EXACT_POWER_FAMILY_LOOKUP_ENCODING_LINEAR_SHELL_GUARDS,
    EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ENV,
    EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_LINEAR_MINMAX,
)
from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b.forced_anchor.master import _check, _display_path, _mapping
from src.search.phase3b.forced_anchor.model_slice import _build_exact_overlay
from src.search.phase3b.forced_anchor.proto_reduction import _proto_profile

ACTIVE_GUARD_PROTO_SHAPE_AUDIT_SOURCE = "phase3b_active_guard_proto_shape_audit_v1"
DEFAULT_ACTIVE_GUARD_CANDIDATE = "67x13"


def build_phase3b_active_guard_proto_shape_audit(
    project_root: Path,
    *,
    candidate: str = DEFAULT_ACTIVE_GUARD_CANDIDATE,
    block_size: int = 64,
    block_templates: str = "",
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    ghost_w, ghost_h = _parse_candidate(candidate)
    started = time.perf_counter()
    model_error: Optional[str] = None
    proto_profile: Dict[str, Any] = {}
    power_coverage: Dict[str, Any] = {}
    witness_stats: Dict[str, Any] = {}
    shape: Dict[str, Any] = {}
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "ActiveGuard proto shape audit has not run.",
    }

    env = {
        EXACT_POWER_FAMILY_LOOKUP_ENCODING_ENV: EXACT_POWER_FAMILY_LOOKUP_ENCODING_LINEAR_SHELL_GUARDS,
        EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ENV: EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_LINEAR_MINMAX,
        EXACT_POWER_COVERAGE_WITNESS_ENCODING_ENV: EXACT_POWER_COVERAGE_WITNESS_ENCODING_BLOCK_ELEMENT,
        EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV: "selected_block_active_guard",
        EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV: str(int(block_size)),
        EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES_ENV: str(block_templates),
        EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_ENV: "bounds",
    }
    try:
        with _temporary_env(env):
            model, proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_w), int(ghost_h)),
                master_search_profile=str(master_search_profile),
            )
            proto_profile = _proto_profile(proto)
        power_coverage = copy.deepcopy(
            _mapping(getattr(model, "build_stats", {}).get("power_coverage"))
        )
        witness_stats = copy.deepcopy(_mapping(power_coverage.get("witness_encoding")))
        delegate = getattr(model, "_coordinate_delegate", None)
        independent_index = _build_active_guard_expected_index(
            delegate,
            block_size=int(block_size),
        )
        independent_expected = _public_active_guard_expected_counts(independent_index)
        shape = audit_active_guard_bool_or_clauses(
            proto,
            expected_guard_count=_int_value(
                independent_expected.get("expected_guard_clause_count")
            ),
            expected_signature_to_pole_key=_mapping(
                independent_index.get("signature_to_pole_key")
            ),
        )
        shape["witness_expected_guard_clause_count"] = _int_value(
            witness_stats.get("block_active_guard_clause_count")
        )
        shape["witness_matches_independent_expected"] = bool(
            _int_value(witness_stats.get("block_active_guard_clause_count"))
            == _int_value(independent_expected.get("expected_guard_clause_count"))
        )
        shape["independent_expected"] = independent_expected
        shape["optional_powered_guard_count_matches_independent_expected"] = bool(
            _int_value(shape.get("optional_powered_guard_count"))
            == _int_value(independent_expected.get("optional_powered_guard_count"))
        )
        shape["mandatory_powered_guard_count_matches_independent_expected"] = bool(
            _int_value(shape.get("mandatory_powered_guard_count"))
            == _int_value(independent_expected.get("mandatory_powered_guard_count"))
        )
        shape["template_counts_match_independent_expected"] = bool(
            _mapping(shape.get("template_counts"))
            == _mapping(independent_expected.get("template_counts"))
        )
        shape["expected_signature_hash_matches_independent"] = bool(
            shape.get("actual_signature_hash")
            == independent_expected.get("expected_signature_hash")
        )
        status.update(_status_from_shape(shape))
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"
        status.update(
            {
                "completed": True,
                "evaluated": False,
                "outcome": "active_guard_proto_shape_error",
                "recommendation": (
                    "ActiveGuard proto shape audit failed; inspect model_error "
                    "before using this gate."
                ),
            }
        )

    report = {
        "metadata": {
            "source": ACTIVE_GUARD_PROTO_SHAPE_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_proto_bool_or_shape_audit",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {"project_root": _display_path(project_root, project_root)},
        "candidate": {
            "key": f"{ghost_w}x{ghost_h}",
            "ghost_rect": {"w": int(ghost_w), "h": int(ghost_h)},
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "block_size": int(block_size),
            "block_templates": str(block_templates),
            "environment": env,
        },
        "status": status,
        "proto_profile": proto_profile,
        "power_coverage": power_coverage,
        "witness_stats": witness_stats,
        "active_guard_shape": shape,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
    }
    report["checks"] = _checks(report)
    return report


def audit_active_guard_bool_or_clauses(
    proto: Any,
    *,
    expected_guard_count: Optional[int] = None,
    expected_signature_to_pole_key: Optional[Mapping[str, Any]] = None,
    sample_limit: int = 12,
) -> Dict[str, Any]:
    variable_names = [str(getattr(variable, "name", "")) for variable in proto.variables]
    expected_signatures = (
        {str(key): str(value) for key, value in expected_signature_to_pole_key.items()}
        if expected_signature_to_pole_key is not None
        else None
    )
    total_bool_or_count = 0
    guard_clause_count = 0
    valid_guard_clause_count = 0
    invalid_samples: list[Dict[str, Any]] = []
    valid_samples: list[Dict[str, Any]] = []
    literal_count_distribution: Dict[str, int] = {}
    optional_powered_guard_count = 0
    mandatory_powered_guard_count = 0
    template_counts: Dict[str, int] = {}
    actual_signature_to_pole_key: Dict[str, str] = {}
    expected_signature_match_count = 0
    unexpected_signature_count = 0
    duplicate_signature_count = 0
    pole_key_mismatch_count = 0
    expected_signature_mismatch_samples: list[Dict[str, Any]] = []

    for constraint_index, constraint in enumerate(proto.constraints):
        if not _has_bool_or(constraint):
            continue
        total_bool_or_count += 1
        decoded = [_decode_literal(literal, variable_names) for literal in constraint.bool_or.literals]
        has_local_selected = any(
            item["name"].startswith("cover_choice_local_selected__") for item in decoded
        )
        has_block_selected = any(
            item["name"].startswith("cover_choice_block_selected__") for item in decoded
        )
        if not has_local_selected and not has_block_selected:
            continue
        guard_clause_count += 1
        literal_count_distribution[str(len(decoded))] = (
            int(literal_count_distribution.get(str(len(decoded)), 0)) + 1
        )
        classification = _classify_guard_clause(decoded)
        classification["constraint_index"] = int(constraint_index)
        if classification["valid"]:
            valid_guard_clause_count += 1
            signature = _guard_signature(classification)
            pole_key = str(classification.get("pole_key") or "")
            if expected_signatures is not None and signature:
                expected_pole_key = expected_signatures.get(signature)
                if expected_pole_key is None:
                    unexpected_signature_count += 1
                    if len(expected_signature_mismatch_samples) < int(sample_limit):
                        expected_signature_mismatch_samples.append(
                            {
                                "reason": "unexpected_signature",
                                "signature": signature,
                                "actual_pole_key": pole_key,
                            }
                        )
                elif signature in actual_signature_to_pole_key:
                    duplicate_signature_count += 1
                    if len(expected_signature_mismatch_samples) < int(sample_limit):
                        expected_signature_mismatch_samples.append(
                            {
                                "reason": "duplicate_signature",
                                "signature": signature,
                                "expected_pole_key": expected_pole_key,
                                "actual_pole_key": pole_key,
                            }
                        )
                else:
                    actual_signature_to_pole_key[signature] = pole_key
                    if pole_key == expected_pole_key:
                        expected_signature_match_count += 1
                    else:
                        pole_key_mismatch_count += 1
                        if len(expected_signature_mismatch_samples) < int(sample_limit):
                            expected_signature_mismatch_samples.append(
                                {
                                    "reason": "pole_key_mismatch",
                                    "signature": signature,
                                    "expected_pole_key": expected_pole_key,
                                    "actual_pole_key": pole_key,
                                }
                            )
            if classification["has_powered_active_guard"]:
                optional_powered_guard_count += 1
            else:
                mandatory_powered_guard_count += 1
            template = str(classification.get("powered_template") or "")
            if template:
                template_counts[template] = int(template_counts.get(template, 0)) + 1
            if len(valid_samples) < int(sample_limit):
                valid_samples.append(classification)
        elif len(invalid_samples) < int(sample_limit):
            invalid_samples.append(classification)

    expected = int(expected_guard_count) if expected_guard_count is not None else None
    missing_expected_signature_count = 0
    missing_expected_signature_samples: list[Dict[str, Any]] = []
    if expected_signatures is not None:
        missing_signatures = set(expected_signatures) - set(actual_signature_to_pole_key)
        missing_expected_signature_count = int(len(missing_signatures))
        for signature in sorted(missing_signatures)[: int(sample_limit)]:
            missing_expected_signature_samples.append(
                {
                    "reason": "missing_expected_signature",
                    "signature": signature,
                    "expected_pole_key": expected_signatures[signature],
                }
            )
    expected_signature_bijection_valid = (
        expected_signatures is not None
        and int(missing_expected_signature_count) == 0
        and int(unexpected_signature_count) == 0
        and int(duplicate_signature_count) == 0
        and int(pole_key_mismatch_count) == 0
        and int(expected_signature_match_count) == int(len(expected_signatures))
    )
    return {
        "total_bool_or_count": int(total_bool_or_count),
        "guard_clause_count": int(guard_clause_count),
        "valid_guard_clause_count": int(valid_guard_clause_count),
        "invalid_guard_clause_count": int(guard_clause_count - valid_guard_clause_count),
        "expected_guard_clause_count": expected,
        "matches_expected_guard_clause_count": (
            bool(expected == guard_clause_count) if expected is not None else None
        ),
        "literal_count_distribution": dict(sorted(literal_count_distribution.items())),
        "optional_powered_guard_count": int(optional_powered_guard_count),
        "mandatory_powered_guard_count": int(mandatory_powered_guard_count),
        "template_counts": dict(sorted(template_counts.items())),
        "expected_signature_count": (
            int(len(expected_signatures)) if expected_signatures is not None else None
        ),
        "actual_signature_count": int(len(actual_signature_to_pole_key)),
        "expected_signature_match_count": int(expected_signature_match_count),
        "missing_expected_signature_count": int(missing_expected_signature_count),
        "unexpected_signature_count": int(unexpected_signature_count),
        "duplicate_signature_count": int(duplicate_signature_count),
        "pole_key_mismatch_count": int(pole_key_mismatch_count),
        "expected_signature_bijection_valid": bool(expected_signature_bijection_valid),
        "expected_signature_hash": (
            _hash_signature_mapping(expected_signatures)
            if expected_signatures is not None
            else None
        ),
        "actual_signature_hash": _hash_signature_mapping(actual_signature_to_pole_key),
        "expected_signature_mismatch_samples": expected_signature_mismatch_samples,
        "missing_expected_signature_samples": missing_expected_signature_samples,
        "valid_samples": valid_samples,
        "invalid_samples": invalid_samples,
        "all_guard_clauses_valid": bool(
            guard_clause_count > 0 and guard_clause_count == valid_guard_clause_count
        ),
    }


def independent_active_guard_expected_counts(
    delegate: Any,
    *,
    block_size: int,
) -> Dict[str, Any]:
    return _public_active_guard_expected_counts(
        _build_active_guard_expected_index(delegate, block_size=block_size)
    )


def _build_active_guard_expected_index(
    delegate: Any,
    *,
    block_size: int,
) -> Dict[str, Any]:
    if delegate is None:
        return {
            "status": "missing_delegate",
            "expected_guard_clause_count": 0,
            "optional_powered_guard_count": 0,
            "mandatory_powered_guard_count": 0,
            "template_counts": {},
            "signature_to_pole_key": {},
        }
    block_size = max(2, int(block_size))
    pole_slots = list(getattr(delegate, "residual_optional_slots", {}).get("power_pole", []))
    powered_slots = [
        slot
        for slot in list(delegate._all_powered_slots())
        if bool(delegate._use_block_element_power_coverage_for_template(slot.template))
    ]
    padded_pole_positions = 0
    padded_value_count = 0
    padded_position_entries: list[Dict[str, Any]] = []
    for start in range(0, len(pole_slots), block_size):
        block_index = int(start // block_size)
        block_slots = list(pole_slots[start : start + block_size])
        if not block_slots:
            continue
        padded_slots = list(block_slots)
        if len(padded_slots) < block_size:
            padded_value_count += int(block_size - len(padded_slots))
            padded_slots.extend([padded_slots[-1]] * (block_size - len(padded_slots)))
        for local_index, pole_slot in enumerate(padded_slots):
            if getattr(pole_slot, "active", None) is not None:
                padded_pole_positions += 1
                padded_position_entries.append(
                    {
                        "block_index": int(block_index),
                        "local_index": int(local_index),
                        "pole_key": str(getattr(pole_slot, "key", "")),
                    }
                )
    expected_guard_count = 0
    optional_powered_guard_count = 0
    mandatory_powered_guard_count = 0
    template_counts: Dict[str, int] = {}
    powered_slot_counts: Dict[str, int] = {}
    signature_to_pole_key: Dict[str, str] = {}
    for powered_slot in powered_slots:
        template = str(getattr(powered_slot, "template", ""))
        powered_key = str(getattr(powered_slot, "key", ""))
        powered_slot_counts[template] = int(powered_slot_counts.get(template, 0)) + 1
        expected_guard_count += int(padded_pole_positions)
        template_counts[template] = int(template_counts.get(template, 0)) + int(
            padded_pole_positions
        )
        if getattr(powered_slot, "active", None) is not None:
            optional_powered_guard_count += int(padded_pole_positions)
        else:
            mandatory_powered_guard_count += int(padded_pole_positions)
        for entry in padded_position_entries:
            signature_to_pole_key[
                _make_guard_signature(
                    powered_key,
                    int(entry["block_index"]),
                    int(entry["local_index"]),
                )
            ] = str(entry["pole_key"])
    return {
        "status": "evaluated",
        "block_size": int(block_size),
        "pole_slot_count": int(len(pole_slots)),
        "powered_slot_count": int(len(powered_slots)),
        "padded_pole_position_count": int(padded_pole_positions),
        "padded_block_value_count": int(padded_value_count),
        "expected_guard_clause_count": int(expected_guard_count),
        "optional_powered_guard_count": int(optional_powered_guard_count),
        "mandatory_powered_guard_count": int(mandatory_powered_guard_count),
        "template_counts": dict(sorted(template_counts.items())),
        "powered_slot_counts": dict(sorted(powered_slot_counts.items())),
        "signature_to_pole_key": signature_to_pole_key,
    }


def _public_active_guard_expected_counts(index: Mapping[str, Any]) -> Dict[str, Any]:
    payload = {
        key: value
        for key, value in dict(index).items()
        if key != "signature_to_pole_key"
    }
    signatures = _mapping(index.get("signature_to_pole_key"))
    payload["expected_signature_count"] = int(len(signatures))
    payload["expected_signature_hash"] = _hash_signature_mapping(signatures)
    sample: list[Dict[str, Any]] = []
    for signature, pole_key in sorted(signatures.items())[:12]:
        sample.append({"signature": str(signature), "pole_key": str(pole_key)})
    payload["expected_signature_samples"] = sample
    return payload


def render_phase3b_active_guard_proto_shape_audit_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    shape = _mapping(report.get("active_guard_shape"))
    lines = [
        "# Phase 3B ActiveGuard Proto Shape Audit",
        "",
        "- Diagnostic semantics: no_solve_proto_bool_or_shape_audit",
        f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', False))}",
        f"- proof_source: {bool(_mapping(report.get('metadata')).get('proof_source', False))}",
        f"- candidate_elimination_claim: {bool(_mapping(report.get('metadata')).get('candidate_elimination_claim', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Shape",
        "",
        f"- Total BoolOr: {shape.get('total_bool_or_count')}",
        f"- Guard clauses: {shape.get('guard_clause_count')}",
        f"- Valid guard clauses: {shape.get('valid_guard_clause_count')}",
        f"- Invalid guard clauses: {shape.get('invalid_guard_clause_count')}",
        f"- Matches expected: {shape.get('matches_expected_guard_clause_count')}",
        f"- Witness matches independent expected: {shape.get('witness_matches_independent_expected')}",
        f"- Optional count matches independent expected: {shape.get('optional_powered_guard_count_matches_independent_expected')}",
        f"- Mandatory count matches independent expected: {shape.get('mandatory_powered_guard_count_matches_independent_expected')}",
        f"- Template counts match independent expected: {shape.get('template_counts_match_independent_expected')}",
        f"- Expected signature bijection valid: {shape.get('expected_signature_bijection_valid')}",
        f"- Signature hash matches independent expected: {shape.get('expected_signature_hash_matches_independent')}",
        f"- Signature counts: actual={shape.get('actual_signature_count')} expected={shape.get('expected_signature_count')}",
        f"- Signature gaps: missing={shape.get('missing_expected_signature_count')} unexpected={shape.get('unexpected_signature_count')} duplicate={shape.get('duplicate_signature_count')} pole_mismatch={shape.get('pole_key_mismatch_count')}",
        f"- Optional powered guards: {shape.get('optional_powered_guard_count')}",
        f"- Mandatory powered guards: {shape.get('mandatory_powered_guard_count')}",
        f"- Literal count distribution: {shape.get('literal_count_distribution')}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(check.get("check_id")),
                        _markdown_cell(check.get("status")),
                        _markdown_cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_active_guard_proto_shape_audit_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    shape = _mapping(report.get("active_guard_shape"))
    return "\n".join(
        [
            "phase3b active-guard proto shape audit",
            "diagnostic_semantics=no_solve_proto_bool_or_shape_audit",
            f"solver_invoked={bool(_mapping(report.get('metadata')).get('solver_invoked', False))}",
            f"proof_source={bool(_mapping(report.get('metadata')).get('proof_source', False))}",
            f"candidate_elimination_claim={bool(_mapping(report.get('metadata')).get('candidate_elimination_claim', False))}",
            f"outcome={status.get('outcome')}",
            f"guard_clause_count={shape.get('guard_clause_count')}",
            f"valid_guard_clause_count={shape.get('valid_guard_clause_count')}",
            f"invalid_guard_clause_count={shape.get('invalid_guard_clause_count')}",
            f"matches_expected_guard_clause_count={shape.get('matches_expected_guard_clause_count')}",
            f"witness_matches_independent_expected={shape.get('witness_matches_independent_expected')}",
            f"optional_powered_guard_count_matches_independent_expected={shape.get('optional_powered_guard_count_matches_independent_expected')}",
            f"mandatory_powered_guard_count_matches_independent_expected={shape.get('mandatory_powered_guard_count_matches_independent_expected')}",
            f"template_counts_match_independent_expected={shape.get('template_counts_match_independent_expected')}",
            f"expected_signature_bijection_valid={shape.get('expected_signature_bijection_valid')}",
            f"expected_signature_hash_matches_independent={shape.get('expected_signature_hash_matches_independent')}",
            f"actual_signature_count={shape.get('actual_signature_count')}",
            f"expected_signature_count={shape.get('expected_signature_count')}",
            f"missing_expected_signature_count={shape.get('missing_expected_signature_count')}",
            f"unexpected_signature_count={shape.get('unexpected_signature_count')}",
            f"duplicate_signature_count={shape.get('duplicate_signature_count')}",
            f"pole_key_mismatch_count={shape.get('pole_key_mismatch_count')}",
            f"literal_count_distribution={shape.get('literal_count_distribution')}",
        ]
    ) + "\n"


def _classify_guard_clause(decoded: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    negative_local = [
        item for item in decoded
        if item["negative"] and item["name"].startswith("cover_choice_local_selected__")
    ]
    negative_block = [
        item for item in decoded
        if item["negative"] and item["name"].startswith("cover_choice_block_selected__")
    ]
    positive_pole = [
        item for item in decoded
        if (not item["negative"]) and item["name"].startswith("active__residual_optional::power_pole::slot::")
    ]
    negative_powered = [
        item for item in decoded
        if (
            item["negative"]
            and item["name"].startswith("active__")
            and not item["name"].startswith("active__residual_optional::power_pole::slot::")
        )
    ]
    local_key = _key_between(str(negative_local[0]["name"]), "cover_choice_local_selected__", "__local::") if negative_local else None
    block_key = _key_between(str(negative_block[0]["name"]), "cover_choice_block_selected__", "__block::") if negative_block else None
    powered_key = _key_after_active(str(negative_powered[0]["name"])) if negative_powered else None
    local_index = _index_after_marker(str(negative_local[0]["name"]), "__local::") if negative_local else None
    block_index = _index_after_marker(str(negative_block[0]["name"]), "__block::") if negative_block else None
    pole_key = _key_after_active(str(positive_pole[0]["name"])) if positive_pole else None
    expected_len = 4 if negative_powered else 3
    valid = (
        len(decoded) == expected_len
        and len(negative_local) == 1
        and len(negative_block) == 1
        and len(positive_pole) == 1
        and len(negative_powered) in {0, 1}
        and local_key == block_key
        and (powered_key is None or powered_key == local_key)
        and local_index is not None
        and block_index is not None
        and pole_key is not None
    )
    return {
        "valid": bool(valid),
        "literal_count": int(len(decoded)),
        "has_powered_active_guard": bool(negative_powered),
        "powered_key": local_key,
        "powered_template": _template_from_key(local_key),
        "block_index": block_index,
        "local_index": local_index,
        "pole_key": pole_key,
        "guard_signature": (
            _make_guard_signature(str(local_key), int(block_index), int(local_index))
            if local_key is not None and block_index is not None and local_index is not None
            else None
        ),
        "literals": [dict(item) for item in decoded],
        "reason": "valid_active_guard_clause" if valid else "invalid_active_guard_clause",
    }


def _decode_literal(literal: int, variable_names: Sequence[str]) -> Dict[str, Any]:
    literal = int(literal)
    if literal >= 0:
        variable_index = literal
        negative = False
    else:
        variable_index = -literal - 1
        negative = True
    name = (
        str(variable_names[variable_index])
        if 0 <= int(variable_index) < len(variable_names)
        else ""
    )
    return {
        "literal": int(literal),
        "variable_index": int(variable_index),
        "negative": bool(negative),
        "name": name,
    }


def _has_bool_or(constraint: Any) -> bool:
    method = getattr(constraint, "has_bool_or", None)
    if callable(method):
        return bool(method())
    return bool(getattr(getattr(constraint, "bool_or", None), "literals", []))


def _status_from_shape(shape: Mapping[str, Any]) -> Dict[str, Any]:
    if (
        bool(shape.get("all_guard_clauses_valid", False))
        and bool(shape.get("matches_expected_guard_clause_count", False))
        and bool(shape.get("witness_matches_independent_expected", False))
        and bool(shape.get("optional_powered_guard_count_matches_independent_expected", False))
        and bool(shape.get("mandatory_powered_guard_count_matches_independent_expected", False))
        and bool(shape.get("template_counts_match_independent_expected", False))
        and bool(shape.get("expected_signature_bijection_valid", False))
        and bool(shape.get("expected_signature_hash_matches_independent", False))
    ):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "active_guard_proto_shape_valid",
            "recommendation": (
                "ActiveGuard BoolOr clauses match the expected proto shape; "
                "use as a diagnostic gate, not proof source."
            ),
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "active_guard_proto_shape_gap",
        "recommendation": (
            "ActiveGuard BoolOr clauses did not match the expected shape; inspect "
            "active_guard_shape before running broader probes."
        ),
    }


def _checks(report: Mapping[str, Any]) -> list[Dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    status = _mapping(report.get("status"))
    shape = _mapping(report.get("active_guard_shape"))
    model_error = report.get("model_error")
    return [
        _check(
            "solver_not_invoked",
            "pass" if not bool(metadata.get("solver_invoked", True)) else "fail",
            "solver_invoked=false",
        ),
        _check(
            "proof_source_false",
            "pass" if not bool(metadata.get("proof_source", True)) else "fail",
            "proof_source=false",
        ),
        _check(
            "candidate_elimination_claim_false",
            "pass"
            if not bool(metadata.get("candidate_elimination_claim", True))
            else "fail",
            "candidate_elimination_claim=false",
        ),
        _check(
            "audit_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "fail",
            str(status.get("outcome")),
        ),
        _check(
            "guard_clause_count_matches_expected",
            "pass"
            if bool(shape.get("matches_expected_guard_clause_count", False))
            else "fail",
            f"actual={shape.get('guard_clause_count')} expected={shape.get('expected_guard_clause_count')}",
        ),
        _check(
            "witness_matches_independent_expected",
            "pass"
            if bool(shape.get("witness_matches_independent_expected", False))
            else "fail",
            f"witness={shape.get('witness_expected_guard_clause_count')} independent={shape.get('expected_guard_clause_count')}",
        ),
        _check(
            "optional_powered_guard_count_matches_independent_expected",
            "pass"
            if bool(shape.get("optional_powered_guard_count_matches_independent_expected", False))
            else "fail",
            f"actual={shape.get('optional_powered_guard_count')} expected={_mapping(shape.get('independent_expected')).get('optional_powered_guard_count')}",
        ),
        _check(
            "mandatory_powered_guard_count_matches_independent_expected",
            "pass"
            if bool(shape.get("mandatory_powered_guard_count_matches_independent_expected", False))
            else "fail",
            f"actual={shape.get('mandatory_powered_guard_count')} expected={_mapping(shape.get('independent_expected')).get('mandatory_powered_guard_count')}",
        ),
        _check(
            "template_counts_match_independent_expected",
            "pass"
            if bool(shape.get("template_counts_match_independent_expected", False))
            else "fail",
            f"actual={shape.get('template_counts')} expected={_mapping(shape.get('independent_expected')).get('template_counts')}",
        ),
        _check(
            "expected_signature_bijection_valid",
            "pass"
            if bool(shape.get("expected_signature_bijection_valid", False))
            else "fail",
            (
                f"actual={shape.get('actual_signature_count')} "
                f"expected={shape.get('expected_signature_count')} "
                f"missing={shape.get('missing_expected_signature_count')} "
                f"unexpected={shape.get('unexpected_signature_count')} "
                f"duplicate={shape.get('duplicate_signature_count')} "
                f"pole_mismatch={shape.get('pole_key_mismatch_count')}"
            ),
        ),
        _check(
            "expected_signature_hash_matches_independent",
            "pass"
            if bool(shape.get("expected_signature_hash_matches_independent", False))
            else "fail",
            (
                f"actual={shape.get('actual_signature_hash')} "
                f"expected={_mapping(shape.get('independent_expected')).get('expected_signature_hash')}"
            ),
        ),
        _check(
            "all_guard_clauses_valid",
            "pass" if bool(shape.get("all_guard_clauses_valid", False)) else "fail",
            f"invalid={shape.get('invalid_guard_clause_count')}",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _key_between(text: str, prefix: str, marker: str) -> Optional[str]:
    if not text.startswith(prefix) or marker not in text:
        return None
    return text[len(prefix): text.index(marker)]


def _index_after_marker(text: str, marker: str) -> Optional[int]:
    if marker not in text:
        return None
    try:
        return int(str(text).split(marker, 1)[1])
    except Exception:
        return None


def _key_after_active(text: str) -> Optional[str]:
    prefix = "active__"
    if not text.startswith(prefix):
        return None
    return text[len(prefix):]


def _template_from_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    tokens = str(key).split("::")
    try:
        slot_index = tokens.index("slot")
    except ValueError:
        return None
    if slot_index >= 2:
        return str(tokens[1])
    return None


def _guard_signature(classification: Mapping[str, Any]) -> Optional[str]:
    powered_key = classification.get("powered_key")
    block_index = classification.get("block_index")
    local_index = classification.get("local_index")
    if powered_key is None or block_index is None or local_index is None:
        return None
    return _make_guard_signature(str(powered_key), int(block_index), int(local_index))


def _make_guard_signature(powered_key: str, block_index: int, local_index: int) -> str:
    return f"{str(powered_key)}|block:{int(block_index):03d}|local:{int(local_index):03d}"


def _hash_signature_mapping(mapping: Optional[Mapping[str, Any]]) -> Optional[str]:
    if mapping is None:
        return None
    digest = hashlib.sha256()
    for key, value in sorted(mapping.items()):
        digest.update(str(key).encode("utf-8"))
        digest.update(b"=")
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _parse_candidate(candidate: str) -> tuple[int, int]:
    raw = str(candidate).strip().lower()
    if "x" not in raw:
        raise ValueError(f"candidate must look like WxH, got {candidate!r}")
    left, right = raw.split("x", 1)
    return int(left), int(right)


@contextmanager
def _temporary_env(overrides: Mapping[str, str]) -> Iterator[None]:
    saved = {str(key): os.environ.get(str(key)) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[str(key)] = str(value)
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(str(key), None)
            else:
                os.environ[str(key)] = str(value)


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
