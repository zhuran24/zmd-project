from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b.coordinate_validation.field_channel_delta import (
    FIELD_CHANNELS_BY_VARIANT,
    FIELD_CHANNEL_VARIANTS,
)
from src.search.phase3b.coordinate_validation.group_delta import (
    _build_delta_context,
    _candidate_rect,
    _check,
    _compact_greedy,
    _compact_validation,
    _mapping,
    _normalize_solver_profile,
)

ACTUAL_PATH_ASSUMPTION_CORE_SOURCE = (
    "phase3b_coordinate_validation_actual_path_assumption_core_v1"
)

DEFAULT_ACTUAL_PATH_FIELD_VARIANT = "x_y_mode"


def build_phase3b_coordinate_validation_actual_path_assumption_core(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 133,
    field_variant: str = DEFAULT_ACTUAL_PATH_FIELD_VARIANT,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 10.0,
    worker_count: int = 1,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
    collect_force_equality_labels: bool = False,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    normalized_field_variant = str(field_variant).strip()
    force_fields = _force_fields_for_variant(normalized_field_variant)
    solver_profile = _normalize_solver_profile(
        solver_parameter_profile,
        time_limit_seconds=float(time_limit_seconds),
        worker_count=int(worker_count),
    )
    started = time.perf_counter()
    context: Dict[str, Any] = {}
    greedy: Dict[str, Any] = {}
    validation: Dict[str, Any] = {}
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
        model = context["model"]
        greedy = model._run_mandatory_greedy_pass(
            ordered_groups=context["ordered_groups"],
            candidates_by_group=context["candidates_by_group"],
            blocked_cells=set(context["blocked_cells"]),
            stop_on_first_failure=True,
        )
        if bool(greedy.get("complete", False)):
            validation = _compact_validation(
                model._validate_coordinate_forced_hint(
                    solution_hint=dict(greedy.get("solution_hint", {})),
                    ghost_anchor_hint_idx=int(anchor_idx),
                    time_limit_seconds=float(time_limit_seconds),
                    require_complete=True,
                    solver_parameter_profile=solver_profile,
                    force_fields=force_fields,
                    use_assumptions=True,
                    collect_force_equality_labels=bool(collect_force_equality_labels),
                )
            )
        else:
            validation = _compact_validation(
                {
                    "attempted": False,
                    "status": "SKIPPED",
                    "accepted": False,
                    "reason": "actual_path_greedy_incomplete",
                    "missing_hint_count": 0,
                    "missing_pose_tuple_count": 0,
                    "forced_slot_field_count": 0,
                    "forced_ghost_anchor": True,
                    "forced_fields": list(force_fields),
                    "use_assumptions": True,
                    "assumption_core_supported": False,
                    "assumption_count": 0,
                    "assumption_labels": [],
                    "infeasible_assumption_core": [],
                    "infeasible_assumption_core_status": "not_evaluated",
                    "force_equality_labels": [],
                    "require_complete": True,
                }
            )
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    status = _status_from_payload(
        context=context,
        greedy=greedy,
        validation=validation,
        model_error=model_error,
    )
    return {
        "metadata": {
            "source": ACTUAL_PATH_ASSUMPTION_CORE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "actual_path_assumption_core_not_proof_source",
        },
        "paths": {"project_root": str(project_root)},
        "candidate": {
            "key": str(candidate),
            "ghost_rect": _candidate_rect(str(candidate)),
            "anchor_idx": int(anchor_idx),
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "field_variant": normalized_field_variant,
            "force_fields": list(force_fields),
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "solver_parameter_profile": dict(solver_profile),
            "collect_force_equality_labels": bool(collect_force_equality_labels),
        },
        "artifact_hashes": dict(artifact_hashes),
        "artifact_hash_error": artifact_hash_error,
        "context": {
            "ghost_anchor_count": int(context.get("ghost_anchor_count", 0)),
            "blocked_cell_count": int(context.get("blocked_cell_count", 0)),
            "ordered_group_count": int(context.get("ordered_group_count", 0)),
        },
        "status": status,
        "actual_path": {
            "include_ghost": True,
            "require_complete": True,
            "greedy": _compact_greedy(greedy),
            "validation": validation,
            "core_size": len(list(validation.get("infeasible_assumption_core", []))),
            "collected_force_equality_label_count": len(
                list(validation.get("force_equality_labels", []))
            ),
            "core_summary": _label_summary(
                list(validation.get("infeasible_assumption_core", []))
            ),
        },
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(status, context, validation, model_error),
    }


def render_phase3b_coordinate_validation_actual_path_assumption_core_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    actual = _mapping(report.get("actual_path"))
    validation = _mapping(actual.get("validation"))
    lines = [
        "# Phase 3B Actual-Path Coordinate Validation Assumption Core",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        "- Diagnostic semantics: actual_path_assumption_core_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Validation status: {validation.get('status')}",
        f"- Core status: {validation.get('infeasible_assumption_core_status')}",
        f"- Core size: {actual.get('core_size')}",
        f"- Forced slots: {validation.get('forced_slot_field_count')}",
        f"- Assumptions: {validation.get('assumption_count')}",
        "",
        "## Extracted Core",
        "",
        "| Slot | Field | Value | Solution | Group | Template | Pose |",
        "| --- | --- | ---: | --- | --- | --- | ---: |",
    ]
    for label in list(validation.get("infeasible_assumption_core", [])):
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
                    _markdown_cell(label.get("group_id")),
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


def render_phase3b_coordinate_validation_actual_path_assumption_core_text(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    actual = _mapping(report.get("actual_path"))
    validation = _mapping(actual.get("validation"))
    lines = [
        "Phase 3B actual-path coordinate validation assumption core",
        f"candidate={candidate.get('key')}",
        f"anchor_idx={candidate.get('anchor_idx')}",
        "diagnostic_semantics=actual_path_assumption_core_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"validation_status={validation.get('status')}",
        f"core_status={validation.get('infeasible_assumption_core_status')}",
        f"core_size={actual.get('core_size')}",
        f"forced_slots={validation.get('forced_slot_field_count')}",
        f"assumptions={validation.get('assumption_count')}",
    ]
    for label in list(validation.get("infeasible_assumption_core", [])):
        if not isinstance(label, Mapping):
            continue
        lines.append(
            "core "
            f"slot={label.get('slot_key')} "
            f"field={label.get('field')} "
            f"value={label.get('forced_value')} "
            f"solution={label.get('solution_id')} "
            f"group={label.get('group_id')} "
            f"pose={label.get('pose_index')}"
        )
    return "\n".join(lines) + "\n"


def _force_fields_for_variant(field_variant: str) -> tuple[str, ...]:
    key = str(field_variant).strip()
    if key not in FIELD_CHANNELS_BY_VARIANT:
        raise ValueError(
            f"Unsupported field-channel variant: {field_variant!r}; "
            "expected one of " + ", ".join(FIELD_CHANNEL_VARIANTS)
        )
    return tuple(FIELD_CHANNELS_BY_VARIANT[key])


def _status_from_payload(
    *,
    context: Mapping[str, Any],
    greedy: Mapping[str, Any],
    validation: Mapping[str, Any],
    model_error: Optional[str],
) -> Dict[str, Any]:
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "recommendation": "Actual-path assumption-core diagnostic failed; inspect model_error.",
        }
    if not context:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "context_missing",
            "recommendation": "Actual-path context was not built.",
        }
    if not bool(greedy.get("complete", False)):
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "actual_path_greedy_incomplete",
            "recommendation": "Full mandatory greedy hint did not complete for this anchor.",
        }
    core_status = str(validation.get("infeasible_assumption_core_status"))
    core_size = len(list(validation.get("infeasible_assumption_core", [])))
    if core_status == "extracted" and core_size > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "actual_path_assumption_core_extracted",
            "recommendation": "Use the extracted actual-path labels as the next diagnostic shrink target only.",
        }
    if str(validation.get("status")) == "INFEASIBLE":
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "actual_path_infeasible_without_extracted_core",
            "recommendation": "Actual path is infeasible but no assumption core was extracted; fall back to bounded equality deletion.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "actual_path_not_terminal_infeasible",
        "recommendation": "Actual path did not prove INFEASIBLE under selected profile; adjust profile or target a different anchor.",
    }


def _checks(
    status: Mapping[str, Any],
    context: Mapping[str, Any],
    validation: Mapping[str, Any],
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
            "actual_path_validation_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "assumption_core_supported",
            "pass"
            if bool(validation.get("assumption_core_supported", False))
            else "fail",
            f"supported={bool(validation.get('assumption_core_supported', False))}",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _label_summary(labels: list[Any]) -> Dict[str, Any]:
    field_counts: Dict[str, int] = {}
    group_counts: Dict[str, int] = {}
    for label in labels:
        if not isinstance(label, Mapping):
            continue
        field = str(label.get("field"))
        group_id = str(label.get("group_id"))
        field_counts[field] = int(field_counts.get(field, 0)) + 1
        group_counts[group_id] = int(group_counts.get(group_id, 0)) + 1
    return {"field_counts": field_counts, "group_counts": group_counts}


def _markdown_cell(value: Any) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")
