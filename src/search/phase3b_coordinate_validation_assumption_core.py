from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b_coordinate_validation_field_channel_delta import (
    FIELD_CHANNELS_BY_VARIANT,
    FIELD_CHANNEL_VARIANTS,
)
from src.search.phase3b_coordinate_validation_group_delta import (
    _build_delta_context,
    _candidate_rect,
    _check,
    _compact_greedy,
    _compact_group,
    _compact_validation,
    _mapping,
    _normalize_solver_profile,
)

COORDINATE_VALIDATION_ASSUMPTION_CORE_SOURCE = (
    "phase3b_coordinate_validation_assumption_core_v1"
)

DEFAULT_ASSUMPTION_CORE_CASES = (
    "group::manufacturing_5x5::planter_sandleaf::10:x",
    "group::manufacturing_5x5::planter_sandleaf::10:y",
    "group::manufacturing_5x5::planter_sandleaf::10:x_y",
    "group::manufacturing_6x4::grinder_dense_blue_iron::14:x",
    "group::manufacturing_6x4::grinder_dense_blue_iron::14:y",
    "group::manufacturing_6x4::grinder_dense_blue_iron::14:x_y",
    "group::manufacturing_3x3::crusher_blue_iron::1:x_y",
    "group::manufacturing_3x3::refinery_blue_iron::7:x_y",
)


def build_phase3b_coordinate_validation_assumption_core(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 119,
    cases: Optional[Sequence[str]] = None,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 2.0,
    worker_count: int = 1,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    normalized_cases = _normalize_cases(cases or DEFAULT_ASSUMPTION_CORE_CASES)
    solver_profile = _normalize_solver_profile(
        solver_parameter_profile,
        time_limit_seconds=float(time_limit_seconds),
        worker_count=int(worker_count),
    )
    started = time.perf_counter()
    context: Dict[str, Any] = {}
    entries: list[Dict[str, Any]] = []
    model_error: Optional[str] = None
    try:
        artifact_hashes = compute_exact_artifact_hashes(project_root)
        artifact_hash_error = None
    except Exception as exc:
        artifact_hashes = {}
        artifact_hash_error = f"{type(exc).__name__}: {exc}"

    try:
        context = _build_delta_context(
            project_root,
            candidate=str(candidate),
            anchor_idx=int(anchor_idx),
            master_search_profile=str(master_search_profile),
        )
        group_by_id = {
            str(group.get("group_id", "")): group
            for group in list(context["ordered_groups"])
            if isinstance(group, Mapping)
        }
        for case in normalized_cases:
            group_id = str(case["group_id"])
            group = group_by_id.get(group_id)
            if group is None:
                raise ValueError(f"Unknown assumption-core group id: {group_id}")
            entries.append(
                _evaluate_assumption_core_entry(
                    context=context,
                    group=group,
                    field_variant=str(case["field_variant"]),
                    anchor_idx=int(anchor_idx),
                    time_limit_seconds=float(time_limit_seconds),
                    solver_parameter_profile=solver_profile,
                )
            )
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    status = _status_from_entries(entries, model_error=model_error)
    return {
        "metadata": {
            "source": COORDINATE_VALIDATION_ASSUMPTION_CORE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "coordinate_validation_assumption_core_not_proof_source",
        },
        "paths": {"project_root": str(project_root)},
        "candidate": {
            "key": str(candidate),
            "ghost_rect": _candidate_rect(str(candidate)),
            "anchor_idx": int(anchor_idx),
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "cases": [dict(case) for case in normalized_cases],
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "solver_parameter_profile": dict(solver_profile),
        },
        "artifact_hashes": dict(artifact_hashes),
        "artifact_hash_error": artifact_hash_error,
        "context": {
            "ghost_anchor_count": int(context.get("ghost_anchor_count", 0)),
            "blocked_cell_count": int(context.get("blocked_cell_count", 0)),
            "ordered_group_count": int(context.get("ordered_group_count", 0)),
        },
        "status": status,
        "assumption_core": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "status_counts_by_field_variant": _status_counts_by_key(
                entries,
                "field_variant",
            ),
            "status_counts_by_group_id": _status_counts_by_key(entries, "group_id"),
            "core_status_counts": _core_status_counts(entries),
            "first_extracted_core_entry": _first_entry_with_core_status(
                entries,
                "extracted",
            ),
            "first_infeasible_entry": _first_entry_with_status(entries, "INFEASIBLE"),
        },
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(status, context, entries, model_error),
    }


def render_phase3b_coordinate_validation_assumption_core_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    core = _mapping(report.get("assumption_core"))
    lines = [
        "# Phase 3B Coordinate Validation Assumption Core",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        "- Diagnostic semantics: coordinate_validation_assumption_core_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Status counts: {core.get('status_counts', {})}",
        f"- Core status counts: {core.get('core_status_counts', {})}",
        "",
        "## Case Matrix",
        "",
        "| Group | Field Variant | Status | Core Status | Core Size | Assumptions | Forced Slots | Missing Hints | Wall |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for entry in _entries(report):
        validation = _mapping(entry.get("validation"))
        core_labels = list(validation.get("infeasible_assumption_core", []))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("group_id")),
                    _markdown_cell(entry.get("field_variant")),
                    _markdown_cell(validation.get("status")),
                    _markdown_cell(validation.get("infeasible_assumption_core_status")),
                    _markdown_cell(len(core_labels)),
                    _markdown_cell(validation.get("assumption_count")),
                    _markdown_cell(validation.get("forced_slot_field_count")),
                    _markdown_cell(validation.get("missing_hint_count")),
                    _markdown_cell(validation.get("wall_time")),
                ]
            )
            + " |"
        )
    first_core = _mapping(core.get("first_extracted_core_entry"))
    first_core_labels = list(_mapping(first_core.get("validation")).get("infeasible_assumption_core", []))
    if first_core_labels:
        lines.extend(
            [
                "",
                "## First Extracted Core",
                "",
                f"- Group: {first_core.get('group_id')}",
                f"- Field variant: {first_core.get('field_variant')}",
                "",
                "| Slot | Field | Value | Solution | Template | Pose |",
                "| --- | --- | ---: | --- | --- | ---: |",
            ]
        )
        for label in first_core_labels:
            if not isinstance(label, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(label.get("slot_key")),
                        _markdown_cell(label.get("field")),
                        _markdown_cell(label.get("forced_value")),
                        _markdown_cell(label.get("solution_id")),
                        _markdown_cell(label.get("template")),
                        _markdown_cell(label.get("pose_index")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
        if not isinstance(check, Mapping):
            continue
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


def render_phase3b_coordinate_validation_assumption_core_text(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    core = _mapping(report.get("assumption_core"))
    lines = [
        "Phase 3B coordinate validation assumption core",
        f"candidate={candidate.get('key')}",
        f"anchor_idx={candidate.get('anchor_idx')}",
        "diagnostic_semantics=coordinate_validation_assumption_core_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"status_counts={core.get('status_counts', {})}",
        f"core_status_counts={core.get('core_status_counts', {})}",
    ]
    for entry in _entries(report):
        validation = _mapping(entry.get("validation"))
        lines.append(
            "entry "
            f"group={entry.get('group_id')} "
            f"field_variant={entry.get('field_variant')} "
            f"status={validation.get('status')} "
            f"core_status={validation.get('infeasible_assumption_core_status')} "
            f"core_size={len(list(validation.get('infeasible_assumption_core', [])))} "
            f"assumptions={validation.get('assumption_count')} "
            f"forced_slots={validation.get('forced_slot_field_count')} "
            f"wall={validation.get('wall_time')}"
        )
    return "\n".join(lines) + "\n"


def _evaluate_assumption_core_entry(
    *,
    context: Mapping[str, Any],
    group: Mapping[str, Any],
    field_variant: str,
    anchor_idx: int,
    time_limit_seconds: float,
    solver_parameter_profile: Mapping[str, Any],
) -> Dict[str, Any]:
    model = context["model"]
    force_fields = _force_fields_for_variant(field_variant)
    greedy = model._run_mandatory_greedy_pass(
        ordered_groups=[group],
        candidates_by_group=context["candidates_by_group"],
        blocked_cells=set(),
        stop_on_first_failure=True,
    )
    if bool(greedy.get("complete", False)):
        validation = _compact_validation(
            model._validate_coordinate_forced_hint(
                solution_hint=dict(greedy.get("solution_hint", {})),
                ghost_anchor_hint_idx=None,
                time_limit_seconds=float(time_limit_seconds),
                require_complete=False,
                solver_parameter_profile=solver_parameter_profile,
                force_fields=force_fields,
                use_assumptions=True,
            )
        )
    else:
        validation = _compact_validation(
            {
                "attempted": False,
                "status": "SKIPPED",
                "accepted": False,
                "reason": "greedy_group_incomplete",
                "missing_hint_count": 0,
                "missing_pose_tuple_count": 0,
                "forced_slot_field_count": 0,
                "forced_ghost_anchor": False,
                "forced_fields": list(force_fields),
                "use_assumptions": True,
                "assumption_core_supported": False,
                "assumption_count": 0,
                "assumption_labels": [],
                "infeasible_assumption_core": [],
                "infeasible_assumption_core_status": "not_evaluated",
                "require_complete": False,
            }
        )
    group_id = str(group.get("group_id", ""))
    return {
        "case_id": f"{group_id}:{field_variant}",
        "candidate": "",
        "anchor_idx": int(anchor_idx),
        "group_id": group_id,
        "group": _compact_group(group),
        "field_variant": str(field_variant),
        "force_fields": list(force_fields),
        "include_ghost": False,
        "require_complete": False,
        "greedy": _compact_greedy(greedy),
        "validation": validation,
    }


def _normalize_cases(cases: Sequence[str]) -> tuple[Dict[str, str], ...]:
    result: list[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in cases:
        for part in str(raw).split(","):
            text = part.strip()
            if not text:
                continue
            if ":" not in text:
                raise ValueError(
                    f"Unsupported --case {text!r}; expected group_id:field_variant."
                )
            group_id, field_variant = text.rsplit(":", 1)
            group_id = group_id.strip()
            field_variant = field_variant.strip()
            _force_fields_for_variant(field_variant)
            key = (group_id, field_variant)
            if key in seen:
                continue
            seen.add(key)
            result.append({"group_id": group_id, "field_variant": field_variant})
    if not result:
        raise ValueError("At least one assumption-core case is required.")
    return tuple(result)


def _force_fields_for_variant(field_variant: str) -> tuple[str, ...]:
    key = str(field_variant).strip()
    if key not in FIELD_CHANNELS_BY_VARIANT:
        raise ValueError(
            f"Unsupported field-channel variant: {field_variant!r}; "
            "expected one of " + ", ".join(FIELD_CHANNEL_VARIANTS)
        )
    return tuple(FIELD_CHANNELS_BY_VARIANT[key])


def _status_from_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    model_error: Optional[str],
) -> Dict[str, Any]:
    counts = _status_counts(entries)
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "status_counts": counts,
            "recommendation": "Assumption-core diagnostic failed; inspect model_error.",
        }
    if not entries:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "no_assumption_core_entries",
            "status_counts": counts,
            "recommendation": "No assumption-core entries were generated.",
        }
    extracted = _first_entry_with_core_status(entries, "extracted")
    if extracted is not None:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "assumption_core_extracted",
            "status_counts": counts,
            "recommendation": "At least one infeasible assumption core was extracted; use labels as diagnostic shrink target only.",
        }
    infeasible = _first_entry_with_status(entries, "INFEASIBLE")
    if infeasible is not None:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "infeasible_without_extracted_core",
            "status_counts": counts,
            "recommendation": "Infeasible cases exist but no assumption core was extracted; report core status honestly.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "no_infeasible_assumption_core_case",
        "status_counts": counts,
        "recommendation": "No infeasible assumption-core case was found in selected cases.",
    }


def _checks(
    status: Mapping[str, Any],
    context: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    supported_values = {
        bool(_mapping(entry.get("validation")).get("assumption_core_supported", False))
        for entry in entries
    }
    return [
        _check(
            "context_built",
            "pass" if context else "fail",
            f"ordered_group_count={int(context.get('ordered_group_count', 0))}"
            if context
            else "context missing",
        ),
        _check(
            "assumption_core_entries_present",
            "pass" if entries else "fail",
            f"entry_count={len(entries)}",
        ),
        _check(
            "assumption_core_supported",
            "pass" if True in supported_values else "fail",
            f"supported_values={sorted(str(v) for v in supported_values)}",
        ),
        _check(
            "assumption_core_probe_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _status_counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        status = str(_mapping(entry.get("validation")).get("status", "UNKNOWN"))
        counts[status] = int(counts.get(status, 0)) + 1
    return counts


def _status_counts_by_key(
    entries: Sequence[Mapping[str, Any]],
    key_name: str,
) -> Dict[str, Dict[str, int]]:
    grouped: Dict[str, Dict[str, int]] = {}
    for entry in entries:
        key = str(entry.get(key_name))
        status = str(_mapping(entry.get("validation")).get("status", "UNKNOWN"))
        bucket = grouped.setdefault(key, {})
        bucket[status] = int(bucket.get(status, 0)) + 1
    return grouped


def _core_status_counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        status = str(
            _mapping(entry.get("validation")).get(
                "infeasible_assumption_core_status",
                "unknown",
            )
        )
        counts[status] = int(counts.get(status, 0)) + 1
    return counts


def _first_entry_with_status(
    entries: Sequence[Mapping[str, Any]],
    status: str,
) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if str(_mapping(entry.get("validation")).get("status")) == str(status):
            return dict(entry)
    return None


def _first_entry_with_core_status(
    entries: Sequence[Mapping[str, Any]],
    core_status: str,
) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if (
            str(
                _mapping(entry.get("validation")).get(
                    "infeasible_assumption_core_status"
                )
            )
            == str(core_status)
        ):
            return dict(entry)
    return None


def _entries(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        entry
        for entry in list(_mapping(report.get("assumption_core")).get("entries", []))
        if isinstance(entry, Mapping)
    ]


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
