from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b_coordinate_validation_field_channel_delta import (
    FIELD_CHANNEL_VARIANTS,
    _force_fields_for_variant,
)
from src.search.phase3b_coordinate_validation_group_delta import (
    _build_delta_context,
    _candidate_rect,
    _check,
    _mapping,
)

PHASE3B_FULL_FORCED_HINT_FIELD_FAMILY_DELTA_SOURCE = (
    "phase3b_full_forced_hint_field_family_delta_v1"
)

SAME_X_CAPACITY_CONFLICT_REASON = "same_x_strip_fixed_ghost_capacity_conflict"
DEFAULT_FULL_FORCED_HINT_ANCHORS = tuple(range(118, 126))
DEFAULT_KNOWN_TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
    "boundary_storage_port",
    "protocol_core",
    "protocol_storage_box",
    "power_pole",
)


def build_phase3b_full_forced_hint_field_family_delta(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_indices: Optional[Sequence[int]] = None,
    focus_anchor_idx: int = 119,
    field_variants: Optional[Sequence[str]] = None,
    template_filters: Optional[Sequence[str]] = None,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 2.0,
    worker_count: int = 1,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    anchors = _normalize_anchor_indices(anchor_indices or DEFAULT_FULL_FORCED_HINT_ANCHORS)
    normalized_field_variants = _normalize_field_variants(field_variants or FIELD_CHANNEL_VARIANTS)
    normalized_templates = _normalize_templates(template_filters or DEFAULT_KNOWN_TEMPLATES)
    started = time.perf_counter()
    context: Dict[str, Any] = {}
    label_collection: Dict[str, Any] = {}
    field_entries: list[Dict[str, Any]] = []
    template_entries: list[Dict[str, Any]] = []
    model_error: Optional[str] = None

    try:
        artifact_hashes = compute_exact_artifact_hashes(project_root)
        artifact_hash_error = None
    except Exception as exc:
        artifact_hashes = {}
        artifact_hash_error = f"{type(exc).__name__}: {exc}"

    try:
        if not anchors:
            raise ValueError("anchor_indices must not be empty")
        context = _build_delta_context(
            project_root,
            candidate=str(candidate),
            anchor_idx=int(anchors[0]),
            master_search_profile=str(master_search_profile),
        )
        solver_profile = _solver_profile(
            time_limit_seconds=float(time_limit_seconds),
            worker_count=int(worker_count),
        )
        label_collection = _collect_labels_for_anchor(
            context=context,
            anchor_idx=int(focus_anchor_idx),
            time_limit_seconds=float(time_limit_seconds),
            solver_parameter_profile=solver_profile,
        )
        for anchor_idx in anchors:
            for field_variant in normalized_field_variants:
                field_entries.append(
                    _evaluate_field_variant(
                        context=context,
                        anchor_idx=int(anchor_idx),
                        field_variant=str(field_variant),
                        time_limit_seconds=float(time_limit_seconds),
                        solver_parameter_profile=solver_profile,
                    )
                )
        labels = [
            dict(label)
            for label in list(_mapping(label_collection.get("validation")).get("force_equality_labels", []))
            if isinstance(label, Mapping)
        ]
        for template in normalized_templates:
            template_labels = [
                label for label in labels if str(label.get("template")) == str(template)
            ]
            if not template_labels:
                template_entries.append(
                    _skipped_template_entry(
                        anchor_idx=int(focus_anchor_idx),
                        template=str(template),
                        mode="only_template",
                        reason="template_not_present_in_labels",
                    )
                )
                template_entries.append(
                    _skipped_template_entry(
                        anchor_idx=int(focus_anchor_idx),
                        template=str(template),
                        mode="all_except_template",
                        reason="template_not_present_in_labels",
                    )
                )
                continue
            only_keys = {str(label.get("stable_key")) for label in template_labels}
            all_except_keys = {
                str(label.get("stable_key"))
                for label in labels
                if str(label.get("template")) != str(template)
            }
            template_entries.append(
                _evaluate_key_filter(
                    context=context,
                    anchor_idx=int(focus_anchor_idx),
                    case_id=f"only_template:{template}",
                    template=str(template),
                    mode="only_template",
                    force_equality_keys=only_keys,
                    selected_label_count=len(only_keys),
                    total_label_count=len(labels),
                    time_limit_seconds=float(time_limit_seconds),
                    solver_parameter_profile=solver_profile,
                )
            )
            template_entries.append(
                _evaluate_key_filter(
                    context=context,
                    anchor_idx=int(focus_anchor_idx),
                    case_id=f"all_except_template:{template}",
                    template=str(template),
                    mode="all_except_template",
                    force_equality_keys=all_except_keys,
                    selected_label_count=len(all_except_keys),
                    total_label_count=len(labels),
                    time_limit_seconds=float(time_limit_seconds),
                    solver_parameter_profile=solver_profile,
                )
            )
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    labels = [
        dict(label)
        for label in list(_mapping(label_collection.get("validation")).get("force_equality_labels", []))
        if isinstance(label, Mapping)
    ]
    summary = _summary(
        field_entries=field_entries,
        template_entries=template_entries,
        label_collection=label_collection,
        model_error=model_error,
    )
    return {
        "metadata": {
            "source": PHASE3B_FULL_FORCED_HINT_FIELD_FAMILY_DELTA_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "full_forced_hint_field_family_delta_not_proof_source",
        },
        "paths": {"project_root": str(project_root)},
        "candidate": {
            "key": str(candidate),
            "ghost_rect": _candidate_rect(str(candidate)),
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "anchor_indices": list(anchors),
            "focus_anchor_idx": int(focus_anchor_idx),
            "field_variants": list(normalized_field_variants),
            "template_filters": list(normalized_templates),
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
        },
        "artifact_hashes": dict(artifact_hashes),
        "artifact_hash_error": artifact_hash_error,
        "context": _compact_context(context),
        "label_collection": label_collection,
        "label_summary": _label_summary(labels),
        "field_delta": {
            "entries": field_entries,
            "status_counts": _status_counts(field_entries),
            "status_counts_by_field_variant": _status_counts_by_key(field_entries, "field_variant"),
        },
        "template_delta": {
            "entries": template_entries,
            "status_counts": _status_counts(template_entries),
            "status_counts_by_template": _status_counts_by_key(template_entries, "template"),
            "status_counts_by_mode": _status_counts_by_key(template_entries, "mode"),
        },
        "summary": summary,
        "status": _status(summary, model_error=model_error),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(summary=summary, labels=labels, model_error=model_error),
    }


def render_phase3b_full_forced_hint_field_family_delta_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    label_summary = _mapping(report.get("label_summary"))
    lines = [
        "# Phase 3B Full Forced-Hint Field/Family Delta",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: full_forced_hint_field_family_delta_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Field entries: {summary.get('field_entry_count')}",
        f"- Template entries: {summary.get('template_entry_count')}",
        f"- Same-X precheck hits: {summary.get('same_x_precheck_count')}",
        f"- Label count: {label_summary.get('label_count')}",
        "",
        "## Label Summary",
        "",
        f"- By field: {label_summary.get('field_counts')}",
        f"- Top templates: {label_summary.get('template_counts')}",
        f"- Top groups: {label_summary.get('group_counts')}",
        "",
        "## Field Variant Matrix",
        "",
        "| Anchor | Variant | Status | Reason | Accepted | Attempted Solver | Forced Fields | Wall | Branches | Conflicts |",
        "| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for entry in _entries(report, "field_delta"):
        validation = _mapping(entry.get("validation"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("anchor_idx")),
                    _markdown_cell(entry.get("field_variant")),
                    _markdown_cell(validation.get("status")),
                    _markdown_cell(validation.get("reason")),
                    _markdown_cell(validation.get("accepted")),
                    _markdown_cell(validation.get("attempted_solver")),
                    _markdown_cell(validation.get("forced_slot_field_count")),
                    _markdown_cell(validation.get("wall_time")),
                    _markdown_cell(validation.get("branches")),
                    _markdown_cell(validation.get("conflicts")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Template Filter Matrix",
            "",
            "| Mode | Template | Status | Reason | Accepted | Attempted Solver | Selected Labels | Wall | Branches | Conflicts |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for entry in _entries(report, "template_delta"):
        validation = _mapping(entry.get("validation"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("mode")),
                    _markdown_cell(entry.get("template")),
                    _markdown_cell(validation.get("status")),
                    _markdown_cell(validation.get("reason")),
                    _markdown_cell(validation.get("accepted")),
                    _markdown_cell(validation.get("attempted_solver")),
                    _markdown_cell(entry.get("selected_label_count")),
                    _markdown_cell(validation.get("wall_time")),
                    _markdown_cell(validation.get("branches")),
                    _markdown_cell(validation.get("conflicts")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
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


def render_phase3b_full_forced_hint_field_family_delta_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    lines = [
        "Phase 3B full forced-hint field/family delta",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"field_entry_count={summary.get('field_entry_count')}",
        f"template_entry_count={summary.get('template_entry_count')}",
        f"same_x_precheck_count={summary.get('same_x_precheck_count')}",
        f"field_status_counts={_mapping(report.get('field_delta')).get('status_counts')}",
        f"template_status_counts={_mapping(report.get('template_delta')).get('status_counts')}",
    ]
    for entry in _entries(report, "field_delta"):
        validation = _mapping(entry.get("validation"))
        lines.append(
            "field_entry "
            f"anchor={entry.get('anchor_idx')} "
            f"variant={entry.get('field_variant')} "
            f"status={validation.get('status')} "
            f"reason={validation.get('reason')} "
            f"attempted_solver={validation.get('attempted_solver')}"
        )
    return "\n".join(lines) + "\n"


def _collect_labels_for_anchor(
    *,
    context: Mapping[str, Any],
    anchor_idx: int,
    time_limit_seconds: float,
    solver_parameter_profile: Mapping[str, Any],
) -> Dict[str, Any]:
    return _evaluate_validation_case(
        context=context,
        anchor_idx=int(anchor_idx),
        case_id=f"collect_labels:{anchor_idx}",
        force_fields=("x", "y", "mode"),
        time_limit_seconds=float(time_limit_seconds),
        solver_parameter_profile=solver_parameter_profile,
        collect_force_equality_labels=True,
    )


def _evaluate_field_variant(
    *,
    context: Mapping[str, Any],
    anchor_idx: int,
    field_variant: str,
    time_limit_seconds: float,
    solver_parameter_profile: Mapping[str, Any],
) -> Dict[str, Any]:
    return _evaluate_validation_case(
        context=context,
        anchor_idx=int(anchor_idx),
        case_id=f"field:{anchor_idx}:{field_variant}",
        force_fields=_force_fields_for_variant(field_variant),
        time_limit_seconds=float(time_limit_seconds),
        solver_parameter_profile=solver_parameter_profile,
    ) | {"field_variant": str(field_variant)}


def _evaluate_key_filter(
    *,
    context: Mapping[str, Any],
    anchor_idx: int,
    case_id: str,
    template: str,
    mode: str,
    force_equality_keys: set[str],
    selected_label_count: int,
    total_label_count: int,
    time_limit_seconds: float,
    solver_parameter_profile: Mapping[str, Any],
) -> Dict[str, Any]:
    return _evaluate_validation_case(
        context=context,
        anchor_idx=int(anchor_idx),
        case_id=str(case_id),
        force_fields=("x", "y", "mode"),
        force_equality_keys=force_equality_keys,
        time_limit_seconds=float(time_limit_seconds),
        solver_parameter_profile=solver_parameter_profile,
    ) | {
        "template": str(template),
        "mode": str(mode),
        "selected_label_count": int(selected_label_count),
        "total_label_count": int(total_label_count),
    }


def _evaluate_validation_case(
    *,
    context: Mapping[str, Any],
    anchor_idx: int,
    case_id: str,
    force_fields: Sequence[str],
    time_limit_seconds: float,
    solver_parameter_profile: Mapping[str, Any],
    force_equality_keys: Optional[set[str]] = None,
    collect_force_equality_labels: bool = False,
) -> Dict[str, Any]:
    model = context["model"]
    domain = list(getattr(model, "_ghost_domains", []))[int(anchor_idx)]
    blocked_cells = {
        (int(cell[0]), int(cell[1]))
        for cell in list(_mapping(domain).get("cells", []))
    }
    greedy = model._run_mandatory_greedy_pass(
        ordered_groups=list(context.get("ordered_groups", [])),
        candidates_by_group=context.get("candidates_by_group", {}),
        blocked_cells=blocked_cells,
        stop_on_first_failure=True,
    )
    if bool(greedy.get("complete", False)):
        validation = _compact_validation(
            model._validate_coordinate_forced_hint(
                solution_hint=dict(greedy.get("solution_hint", {})),
                ghost_anchor_hint_idx=int(anchor_idx),
                time_limit_seconds=float(time_limit_seconds),
                require_complete=False,
                solver_parameter_profile=solver_parameter_profile,
                force_fields=tuple(force_fields),
                force_equality_keys=force_equality_keys,
                collect_force_equality_labels=bool(collect_force_equality_labels),
            )
        )
    else:
        validation = _compact_validation(
            {
                "attempted": False,
                "attempted_solver": False,
                "status": "SKIPPED",
                "accepted": False,
                "reason": "greedy_anchor_incomplete",
                "forced_slot_field_count": 0,
                "forced_ghost_anchor": True,
                "forced_fields": list(force_fields),
                "require_complete": False,
            }
        )
    return {
        "case_id": str(case_id),
        "anchor_idx": int(anchor_idx),
        "ghost_anchor": dict(_mapping(domain).get("anchor", {})),
        "force_fields": list(force_fields),
        "force_equality_filter_active": force_equality_keys is not None,
        "force_equality_key_count": 0 if force_equality_keys is None else len(force_equality_keys),
        "greedy": _compact_greedy(greedy),
        "validation": validation,
    }


def _skipped_template_entry(
    *,
    anchor_idx: int,
    template: str,
    mode: str,
    reason: str,
) -> Dict[str, Any]:
    return {
        "case_id": f"{mode}:{template}",
        "anchor_idx": int(anchor_idx),
        "template": str(template),
        "mode": str(mode),
        "selected_label_count": 0,
        "total_label_count": 0,
        "force_fields": ["x", "y", "mode"],
        "force_equality_filter_active": True,
        "force_equality_key_count": 0,
        "greedy": {},
        "validation": _compact_validation(
            {
                "attempted": False,
                "attempted_solver": False,
                "status": "SKIPPED",
                "accepted": False,
                "reason": str(reason),
                "forced_slot_field_count": 0,
                "forced_ghost_anchor": True,
            }
        ),
    }


def _compact_validation(payload: Mapping[str, Any]) -> Dict[str, Any]:
    result = {
        "attempted": bool(payload.get("attempted", False)),
        "attempted_solver": bool(payload.get("attempted_solver", payload.get("attempted", False))),
        "status": str(payload.get("status", "")),
        "accepted": bool(payload.get("accepted", False)),
        "reason": payload.get("reason"),
        "missing_hint_count": int(payload.get("missing_hint_count", 0)),
        "missing_pose_tuple_count": int(payload.get("missing_pose_tuple_count", 0)),
        "forced_slot_field_count": int(payload.get("forced_slot_field_count", 0)),
        "forced_ghost_anchor": bool(payload.get("forced_ghost_anchor", False)),
        "forced_fields": list(payload.get("forced_fields", [])),
        "require_complete": bool(payload.get("require_complete", False)),
        "force_equality_filter_active": bool(payload.get("force_equality_filter_active", False)),
        "wall_time": float(payload.get("wall_time", 0.0)),
        "user_time": float(payload.get("user_time", 0.0)),
        "deterministic_time": float(payload.get("deterministic_time", 0.0)),
        "branches": int(payload.get("branches", 0)),
        "conflicts": int(payload.get("conflicts", 0)),
        "solver_parameters": dict(payload.get("solver_parameters", {})),
    }
    if payload.get("capacity_conflict") is not None:
        result["capacity_conflict"] = dict(payload.get("capacity_conflict", {}))
    labels = [
        dict(label)
        for label in list(payload.get("force_equality_labels", []))
        if isinstance(label, Mapping)
    ]
    if labels:
        result["force_equality_labels"] = labels
    return result


def _compact_greedy(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "complete": bool(payload.get("complete", False)),
        "reason": payload.get("reason"),
        "hinted_groups": int(payload.get("hinted_groups", 0)),
        "hinted_instances": int(payload.get("hinted_instances", 0)),
        "first_failed_group_id": payload.get("first_failed_group_id"),
        "first_failed_group_template": payload.get("first_failed_group_template"),
        "first_failure_reason": payload.get("first_failure_reason"),
        "first_failed_group_position": payload.get("first_failed_group_position"),
    }


def _label_summary(labels: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "label_count": int(len(labels)),
        "field_counts": _count_by(labels, "field"),
        "group_counts": _count_by(labels, "group_id"),
        "template_counts": _count_by(labels, "template"),
        "forced_value_counts": _count_by(labels, "forced_value"),
    }


def _summary(
    *,
    field_entries: Sequence[Mapping[str, Any]],
    template_entries: Sequence[Mapping[str, Any]],
    label_collection: Mapping[str, Any],
    model_error: Optional[str],
) -> Dict[str, Any]:
    all_entries = [*field_entries, *template_entries]
    same_x = [
        entry for entry in all_entries
        if str(_mapping(entry.get("validation")).get("reason")) == SAME_X_CAPACITY_CONFLICT_REASON
    ]
    infeasible = [
        entry for entry in all_entries
        if str(_mapping(entry.get("validation")).get("status")) == "INFEASIBLE"
    ]
    accepted = [
        entry for entry in all_entries
        if bool(_mapping(entry.get("validation")).get("accepted", False))
    ]
    unknown = [
        entry for entry in all_entries
        if str(_mapping(entry.get("validation")).get("status")) == "UNKNOWN"
    ]
    return {
        "field_entry_count": int(len(field_entries)),
        "template_entry_count": int(len(template_entries)),
        "same_x_precheck_count": int(len(same_x)),
        "same_x_precheck_cases": [str(entry.get("case_id")) for entry in same_x],
        "infeasible_count": int(len(infeasible)),
        "accepted_count": int(len(accepted)),
        "unknown_count": int(len(unknown)),
        "label_collection_status": _mapping(label_collection.get("validation")).get("status"),
        "label_collection_reason": _mapping(label_collection.get("validation")).get("reason"),
        "model_error": model_error,
    }


def _status(summary: Mapping[str, Any], *, model_error: Optional[str]) -> Dict[str, Any]:
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "recommendation": "Full forced-hint field/family delta failed; inspect model_error.",
        }
    if int(summary.get("same_x_precheck_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "same_x_precheck_present_in_filtered_delta",
            "recommendation": "At least one filtered case hit the same-x precheck; inspect cases before runtime work.",
        }
    if int(summary.get("accepted_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "field_or_template_filter_changes_status",
            "recommendation": "Some filtered cases are accepted; use field/template deltas to narrow the blocker.",
        }
    if int(summary.get("infeasible_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "filtered_cases_remain_infeasible",
            "recommendation": "Filtered cases remain solver-level INFEASIBLE; continue with assumption/core extraction or smaller equality subsets.",
        }
    return {
        "completed": True,
        "evaluated": bool(int(summary.get("field_entry_count", 0)) or int(summary.get("template_entry_count", 0))),
        "outcome": "no_terminal_infeasible_delta",
        "recommendation": "No filtered terminal infeasible case was found; inspect UNKNOWN/SKIPPED cases.",
    }


def _checks(
    *,
    summary: Mapping[str, Any],
    labels: Sequence[Mapping[str, Any]],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        _check("field_entries_present", "pass" if int(summary.get("field_entry_count", 0)) else "fail", str(summary.get("field_entry_count", 0))),
        _check("labels_collected", "pass" if labels else "fail", f"label_count={len(labels)}"),
        _check("model_error_absent", "pass" if model_error is None else "fail", "no model error" if model_error is None else str(model_error)),
    ]


def _status_counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        status = str(_mapping(entry.get("validation")).get("status", "UNKNOWN"))
        counts[status] = int(counts.get(status, 0)) + 1
    return dict(sorted(counts.items()))


def _status_counts_by_key(entries: Sequence[Mapping[str, Any]], key_name: str) -> Dict[str, Dict[str, int]]:
    grouped: Dict[str, Dict[str, int]] = {}
    for entry in entries:
        key = str(entry.get(key_name))
        status = str(_mapping(entry.get("validation")).get("status", "UNKNOWN"))
        bucket = grouped.setdefault(key, {})
        bucket[status] = int(bucket.get(status, 0)) + 1
    return dict(sorted(grouped.items()))


def _count_by(labels: Sequence[Mapping[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for label in labels:
        value = str(label.get(key, ""))
        counts[value] = int(counts.get(value, 0)) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:24])


def _solver_profile(*, time_limit_seconds: float, worker_count: int) -> Dict[str, Any]:
    return {
        "profile_id": "full_forced_hint_field_family_delta",
        "search_branching": "fixed",
        "worker_count": max(1, int(worker_count)),
        "random_seed": 1,
        "randomize_search": False,
        "time_limit_seconds": max(0.001, float(time_limit_seconds)),
    }


def _normalize_anchor_indices(anchor_indices: Sequence[int]) -> tuple[int, ...]:
    result: list[int] = []
    seen: set[int] = set()
    for raw in anchor_indices:
        idx = int(raw)
        if idx in seen:
            continue
        seen.add(idx)
        result.append(idx)
    return tuple(result)


def _normalize_field_variants(field_variants: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in field_variants:
        for part in str(raw).split(","):
            token = str(part).strip()
            if not token:
                continue
            _force_fields_for_variant(token)
            if token in seen:
                continue
            seen.add(token)
            result.append(token)
    return tuple(result)


def _normalize_templates(templates: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in templates:
        for part in str(raw).split(","):
            token = str(part).strip()
            if not token or token in seen:
                continue
            seen.add(token)
            result.append(token)
    return tuple(result)


def _compact_context(context: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "ghost_anchor_count": int(context.get("ghost_anchor_count", 0)),
        "blocked_cell_count": int(context.get("blocked_cell_count", 0)),
        "ordered_group_count": int(context.get("ordered_group_count", 0)),
    }


def _entries(report: Mapping[str, Any], section: str) -> list[Mapping[str, Any]]:
    return [
        entry
        for entry in list(_mapping(report.get(section)).get("entries", []))
        if isinstance(entry, Mapping)
    ]


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
