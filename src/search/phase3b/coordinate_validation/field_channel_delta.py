from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b.coordinate_validation.group_delta import (
    _build_delta_context,
    _candidate_rect,
    _check,
    _compact_greedy,
    _compact_group,
    _compact_validation,
    _mapping,
    _normalize_solver_profile,
)

COORDINATE_VALIDATION_FIELD_CHANNEL_DELTA_SOURCE = (
    "phase3b_coordinate_validation_field_channel_delta_v1"
)

DEFAULT_FIELD_CHANNEL_GROUP_IDS = (
    "group::manufacturing_5x5::planter_sandleaf::10",
    "group::manufacturing_6x4::grinder_dense_blue_iron::14",
    "group::manufacturing_3x3::crusher_blue_iron::1",
    "group::manufacturing_3x3::refinery_blue_iron::7",
)

FIELD_CHANNEL_VARIANTS = (
    "x",
    "y",
    "mode",
    "x_y",
    "x_mode",
    "y_mode",
    "x_y_mode",
)

FIELD_CHANNELS_BY_VARIANT = {
    "x": ("x",),
    "y": ("y",),
    "mode": ("mode",),
    "x_y": ("x", "y"),
    "x_mode": ("x", "mode"),
    "y_mode": ("y", "mode"),
    "x_y_mode": ("x", "y", "mode"),
}


def build_phase3b_coordinate_validation_field_channel_delta(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 119,
    group_ids: Optional[Sequence[str]] = None,
    field_variants: Optional[Sequence[str]] = None,
    include_ghost: bool = False,
    collect_force_equality_labels: bool = False,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 2.0,
    worker_count: int = 1,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    normalized_group_ids = _normalize_group_ids(group_ids or DEFAULT_FIELD_CHANNEL_GROUP_IDS)
    normalized_field_variants = _normalize_field_variants(
        field_variants or FIELD_CHANNEL_VARIANTS
    )
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
        missing_group_ids = [
            group_id
            for group_id in normalized_group_ids
            if str(group_id) not in group_by_id
        ]
        if missing_group_ids:
            raise ValueError(
                "Unknown field-channel group id(s): " + ", ".join(missing_group_ids)
            )
        for group_id in normalized_group_ids:
            group = group_by_id[str(group_id)]
            for field_variant in normalized_field_variants:
                entries.append(
                    _evaluate_field_channel_entry(
                        context=context,
                        group=group,
                        field_variant=field_variant,
                        include_ghost=bool(include_ghost),
                        collect_force_equality_labels=bool(collect_force_equality_labels),
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
            "source": COORDINATE_VALIDATION_FIELD_CHANNEL_DELTA_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "coordinate_validation_field_channel_delta_not_proof_source",
        },
        "paths": {"project_root": str(project_root)},
        "candidate": {
            "key": str(candidate),
            "ghost_rect": _candidate_rect(str(candidate)),
            "anchor_idx": int(anchor_idx),
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "group_ids": list(normalized_group_ids),
            "field_variants": list(normalized_field_variants),
            "include_ghost": bool(include_ghost),
            "collect_force_equality_labels": bool(collect_force_equality_labels),
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
        "field_channel_delta": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "status_counts_by_field_variant": _status_counts_by_key(
                entries,
                "field_variant",
            ),
            "status_counts_by_group_id": _status_counts_by_key(entries, "group_id"),
            "first_infeasible_entry": _first_entry_with_status(entries, "INFEASIBLE"),
            "first_accepted_entry": _first_accepted_entry(entries),
            "unknown_diagnostics": _unknown_diagnostics(entries),
        },
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(status, context, entries, model_error),
    }


def render_phase3b_coordinate_validation_field_channel_delta_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    delta = _mapping(report.get("field_channel_delta"))
    unknowns = _mapping(delta.get("unknown_diagnostics"))
    lines = [
        "# Phase 3B Coordinate Validation Field-Channel Delta",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        "- Diagnostic semantics: coordinate_validation_field_channel_delta_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Status counts: {delta.get('status_counts', {})}",
        f"- Zero-branch UNKNOWN entries: {unknowns.get('zero_branch_unknown_count', 0)}",
        f"- Search-progress UNKNOWN entries: {unknowns.get('search_progress_unknown_count', 0)}",
        "",
        "## Field Matrix",
        "",
        "| Group | Field Variant | Ghost | Status | Accepted | Reason | Forced Fields | Forced Slots | Missing Hints | Missing Poses | Wall | Branches | Conflicts |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in _entries(report):
        validation = _mapping(entry.get("validation"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("group_id")),
                    _markdown_cell(entry.get("field_variant")),
                    _markdown_cell(entry.get("include_ghost")),
                    _markdown_cell(validation.get("status")),
                    _markdown_cell(validation.get("accepted")),
                    _markdown_cell(validation.get("reason")),
                    _markdown_cell(",".join(entry.get("force_fields", []))),
                    _markdown_cell(validation.get("forced_slot_field_count")),
                    _markdown_cell(validation.get("missing_hint_count")),
                    _markdown_cell(validation.get("missing_pose_tuple_count")),
                    _markdown_cell(validation.get("wall_time")),
                    _markdown_cell(validation.get("branches")),
                    _markdown_cell(validation.get("conflicts")),
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


def render_phase3b_coordinate_validation_field_channel_delta_text(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    delta = _mapping(report.get("field_channel_delta"))
    unknowns = _mapping(delta.get("unknown_diagnostics"))
    lines = [
        "Phase 3B coordinate validation field-channel delta",
        f"candidate={candidate.get('key')}",
        f"anchor_idx={candidate.get('anchor_idx')}",
        "diagnostic_semantics=coordinate_validation_field_channel_delta_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"status_counts={delta.get('status_counts', {})}",
        f"zero_branch_unknown_count={unknowns.get('zero_branch_unknown_count', 0)}",
        f"search_progress_unknown_count={unknowns.get('search_progress_unknown_count', 0)}",
    ]
    for entry in _entries(report):
        validation = _mapping(entry.get("validation"))
        lines.append(
            "entry "
            f"group={entry.get('group_id')} "
            f"field_variant={entry.get('field_variant')} "
            f"ghost={bool(entry.get('include_ghost', False))} "
            f"status={validation.get('status')} "
            f"accepted={validation.get('accepted')} "
            f"reason={validation.get('reason')} "
            f"force_fields={','.join(entry.get('force_fields', []))} "
            f"forced_slots={validation.get('forced_slot_field_count')} "
            f"missing_hints={validation.get('missing_hint_count')} "
            f"missing_poses={validation.get('missing_pose_tuple_count')} "
            f"wall={validation.get('wall_time')} "
            f"branches={validation.get('branches')} "
            f"conflicts={validation.get('conflicts')}"
        )
    return "\n".join(lines) + "\n"


def _evaluate_field_channel_entry(
    *,
    context: Mapping[str, Any],
    group: Mapping[str, Any],
    field_variant: str,
    include_ghost: bool,
    collect_force_equality_labels: bool,
    anchor_idx: int,
    time_limit_seconds: float,
    solver_parameter_profile: Mapping[str, Any],
) -> Dict[str, Any]:
    model = context["model"]
    force_fields = _force_fields_for_variant(field_variant)
    greedy = model._run_mandatory_greedy_pass(
        ordered_groups=[group],
        candidates_by_group=context["candidates_by_group"],
        blocked_cells=set(context["blocked_cells"]) if include_ghost else set(),
        stop_on_first_failure=True,
    )
    if bool(greedy.get("complete", False)):
        validation = _compact_validation(
            model._validate_coordinate_forced_hint(
                solution_hint=dict(greedy.get("solution_hint", {})),
                ghost_anchor_hint_idx=int(anchor_idx) if include_ghost else None,
                time_limit_seconds=float(time_limit_seconds),
                require_complete=False,
                solver_parameter_profile=solver_parameter_profile,
                force_fields=force_fields,
                collect_force_equality_labels=bool(collect_force_equality_labels),
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
                "forced_ghost_anchor": bool(include_ghost),
                "forced_fields": list(force_fields),
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
        "include_ghost": bool(include_ghost),
        "require_complete": False,
        "greedy": _compact_greedy(greedy),
        "validation": validation,
    }


def _normalize_group_ids(group_ids: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in group_ids:
        for part in str(raw).split(","):
            group_id = str(part).strip()
            if not group_id or group_id in seen:
                continue
            seen.add(group_id)
            result.append(group_id)
    if not result:
        raise ValueError("At least one --group-id is required.")
    return tuple(result)


def _normalize_field_variants(field_variants: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in field_variants:
        for part in str(raw).split(","):
            variant = str(part).strip()
            if not variant:
                continue
            _force_fields_for_variant(variant)
            if variant in seen:
                continue
            seen.add(variant)
            result.append(variant)
    if not result:
        raise ValueError("At least one field variant is required.")
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
    evaluated = [
        entry
        for entry in entries
        if bool(_mapping(entry.get("validation")).get("attempted", False))
    ]
    counts = _status_counts(entries)
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "status_counts": counts,
            "recommendation": "Field-channel delta failed; inspect model_error.",
        }
    if not entries:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "no_field_channel_entries",
            "status_counts": counts,
            "recommendation": "No field-channel entries were generated.",
        }
    if not evaluated:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "field_channel_delta_not_evaluated",
            "status_counts": counts,
            "recommendation": "All field-channel entries were skipped.",
        }
    if _first_entry_with_status(evaluated, "INFEASIBLE") is not None:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "field_channel_infeasible_found",
            "status_counts": counts,
            "recommendation": "At least one field-channel variant is infeasible; use it as diagnostic shrink target only.",
        }
    if _first_accepted_entry(evaluated) is not None:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "field_channel_accepted_present",
            "status_counts": counts,
            "recommendation": "At least one field-channel variant is coordinate-compatible; compare against x_y_mode.",
        }
    unknowns = _unknown_diagnostics(evaluated)
    if int(unknowns.get("search_progress_unknown_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "field_channel_progress_without_terminal",
            "status_counts": counts,
            "recommendation": "Field-channel validation remained UNKNOWN with search progress.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "field_channel_zero_branch_unknown",
        "status_counts": counts,
        "recommendation": "Field-channel validation remained zero-branch UNKNOWN.",
    }


def _checks(
    status: Mapping[str, Any],
    context: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        _check(
            "context_built",
            "pass" if context else "fail",
            f"ordered_group_count={int(context.get('ordered_group_count', 0))}"
            if context
            else "context missing",
        ),
        _check(
            "field_channel_entries_present",
            "pass" if entries else "fail",
            f"entry_count={len(entries)}",
        ),
        _check(
            "field_channel_probe_evaluated",
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


def _unknown_diagnostics(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    unknowns = [
        entry
        for entry in entries
        if str(_mapping(entry.get("validation")).get("status")) == "UNKNOWN"
    ]
    zero_branch = [
        entry
        for entry in unknowns
        if _number_or_zero(_mapping(entry.get("validation")).get("branches")) == 0
        and _number_or_zero(_mapping(entry.get("validation")).get("conflicts")) == 0
    ]
    progress = [entry for entry in unknowns if entry not in zero_branch]
    return {
        "unknown_count": int(len(unknowns)),
        "zero_branch_unknown_count": int(len(zero_branch)),
        "search_progress_unknown_count": int(len(progress)),
        "zero_branch_unknown_by_field_variant": _count_entries_by_key(
            zero_branch,
            "field_variant",
        ),
        "search_progress_unknown_by_field_variant": _count_entries_by_key(
            progress,
            "field_variant",
        ),
    }


def _first_entry_with_status(
    entries: Sequence[Mapping[str, Any]],
    status: str,
) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if str(_mapping(entry.get("validation")).get("status")) == str(status):
            return dict(entry)
    return None


def _first_accepted_entry(entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if bool(_mapping(entry.get("validation")).get("accepted", False)):
            return dict(entry)
    return None


def _count_entries_by_key(
    entries: Sequence[Mapping[str, Any]],
    key_name: str,
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        key = str(entry.get(key_name))
        counts[key] = int(counts.get(key, 0)) + 1
    return counts


def _number_or_zero(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _entries(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        entry
        for entry in list(_mapping(report.get("field_channel_delta")).get("entries", []))
        if isinstance(entry, Mapping)
    ]


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
