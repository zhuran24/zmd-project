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
    _compact_validation,
    _mapping,
    _normalize_solver_profile,
)

ACTUAL_PATH_EQUALITY_CORE_SOURCE = (
    "phase3b_coordinate_validation_actual_path_equality_core_v1"
)

DEFAULT_ACTUAL_PATH_EQUALITY_FIELD_VARIANT = "x_y_mode"


def build_phase3b_coordinate_validation_actual_path_equality_core(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 133,
    field_variant: str = DEFAULT_ACTUAL_PATH_EQUALITY_FIELD_VARIANT,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 10.0,
    worker_count: int = 1,
    max_delete_tests: int = 64,
    skip_single_delete: bool = False,
    initial_keys: Optional[Sequence[str]] = None,
    validate_initial_keys: bool = True,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
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
    full_validation: Dict[str, Any] = {}
    labels: list[Dict[str, Any]] = []
    active_labels: list[Dict[str, Any]] = []
    single_delete_results: list[Dict[str, Any]] = []
    greedy_steps: list[Dict[str, Any]] = []
    final_keys: list[str] = []
    initial_key_count = 0
    unknown_initial_keys: list[str] = []
    initial_subset_validation: Dict[str, Any] = {}
    deletion_test_count = 0
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
            full_validation = _compact_validation(
                model._validate_coordinate_forced_hint(
                    solution_hint=dict(greedy.get("solution_hint", {})),
                    ghost_anchor_hint_idx=int(anchor_idx),
                    time_limit_seconds=float(time_limit_seconds),
                    require_complete=True,
                    solver_parameter_profile=solver_profile,
                    force_fields=force_fields,
                    collect_force_equality_labels=True,
                )
            )
        else:
            full_validation = _compact_validation(
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
                    "force_equality_labels": [],
                    "require_complete": True,
                }
            )
        labels = [
            dict(label)
            for label in list(full_validation.get("force_equality_labels", []))
            if isinstance(label, Mapping)
        ]
        all_keys = [str(label.get("stable_key")) for label in labels]
        all_key_set = set(all_keys)
        if initial_keys is None:
            active_keys = list(all_keys)
        else:
            requested_keys = [str(key) for key in initial_keys]
            requested_key_set = set(requested_keys)
            active_keys = [key for key in all_keys if key in requested_key_set]
            unknown_initial_keys = sorted(requested_key_set - all_key_set)
        initial_key_count = len(active_keys)
        active_key_set = set(active_keys)
        active_labels = [
            dict(label)
            for label in labels
            if str(label.get("stable_key")) in active_key_set
        ]
        final_keys = list(active_keys)
        if str(full_validation.get("status")) == "INFEASIBLE":
            max_tests = max(0, int(max_delete_tests))
            if (
                initial_keys is not None
                and bool(validate_initial_keys)
                and active_keys
            ):
                initial_subset_validation = _run_subset_validation(
                    model=model,
                    greedy=greedy,
                    anchor_idx=int(anchor_idx),
                    time_limit_seconds=float(time_limit_seconds),
                    solver_profile=solver_profile,
                    force_fields=force_fields,
                    subset_keys=active_keys,
                )
            if not bool(skip_single_delete):
                for label in active_labels:
                    if deletion_test_count >= max_tests:
                        break
                    key = str(label.get("stable_key"))
                    subset_keys = [
                        candidate_key
                        for candidate_key in active_keys
                        if candidate_key != key
                    ]
                    validation = _run_subset_validation(
                        model=model,
                        greedy=greedy,
                        anchor_idx=int(anchor_idx),
                        time_limit_seconds=float(time_limit_seconds),
                        solver_profile=solver_profile,
                        force_fields=force_fields,
                        subset_keys=subset_keys,
                    )
                    deletion_test_count += 1
                    single_delete_results.append(
                        {
                            "phase": "single_delete",
                            "removed_key": key,
                            "removed_label": dict(label),
                            "remaining_key_count": len(subset_keys),
                            "status": validation.get("status"),
                            "preserves_infeasible": str(validation.get("status"))
                            == "INFEASIBLE",
                            "validation": validation,
                        }
                    )
            current_keys = list(active_keys)
            for label in active_labels:
                if deletion_test_count >= max_tests:
                    break
                key = str(label.get("stable_key"))
                if key not in current_keys:
                    continue
                subset_keys = [
                    candidate_key for candidate_key in current_keys if candidate_key != key
                ]
                validation = _run_subset_validation(
                    model=model,
                    greedy=greedy,
                    anchor_idx=int(anchor_idx),
                    time_limit_seconds=float(time_limit_seconds),
                    solver_profile=solver_profile,
                    force_fields=force_fields,
                    subset_keys=subset_keys,
                )
                deletion_test_count += 1
                removed = str(validation.get("status")) == "INFEASIBLE"
                if removed:
                    current_keys = subset_keys
                greedy_steps.append(
                    {
                        "phase": "greedy_shrink",
                        "candidate_removed_key": key,
                        "candidate_removed_label": dict(label),
                        "removed": bool(removed),
                        "remaining_key_count": len(current_keys),
                        "status": validation.get("status"),
                        "validation": validation,
                    }
                )
            final_keys = list(current_keys)
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    remaining_labels = [
        dict(label)
        for label in labels
        if str(label.get("stable_key")) in set(final_keys)
    ]
    status = _status_from_payload(
        context=context,
        greedy=greedy,
        full_validation=full_validation,
        labels=labels,
        deletion_test_count=deletion_test_count,
        max_delete_tests=max_delete_tests,
        model_error=model_error,
    )
    return {
        "metadata": {
            "source": ACTUAL_PATH_EQUALITY_CORE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "actual_path_equality_core_not_proof_source",
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
            "max_delete_tests": int(max_delete_tests),
            "skip_single_delete": bool(skip_single_delete),
            "initial_keys_supplied": initial_keys is not None,
            "validate_initial_keys": bool(validate_initial_keys),
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
        "actual_path": {
            "include_ghost": True,
            "require_complete": True,
            "greedy": _compact_greedy(greedy),
            "full_validation": full_validation,
            "initial_key_count": int(initial_key_count),
            "unknown_initial_key_count": int(len(unknown_initial_keys)),
            "unknown_initial_keys": list(unknown_initial_keys)[:32],
            "initial_subset_validation": initial_subset_validation,
            "equality_label_count": len(labels),
            "active_equality_label_count": len(active_labels),
            "equality_labels": labels,
            "single_delete_results": single_delete_results,
            "first_single_delete_preserves_infeasible": _first_single_delete(
                single_delete_results,
                preserves=True,
            ),
            "first_single_delete_changes_status": _first_single_delete(
                single_delete_results,
                preserves=False,
            ),
            "greedy_steps": greedy_steps,
            "deletion_test_count": int(deletion_test_count),
            "delete_tests_exhausted": bool(
                deletion_test_count >= max(0, int(max_delete_tests))
            ),
            "final_key_count": len(final_keys),
            "final_keys": list(final_keys),
            "remaining_labels": remaining_labels,
            "remaining_summary": _label_summary(remaining_labels),
        },
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(status, context, full_validation, labels, model_error),
    }


def render_phase3b_coordinate_validation_actual_path_equality_core_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    actual = _mapping(report.get("actual_path"))
    full = _mapping(actual.get("full_validation"))
    lines = [
        "# Phase 3B Actual-Path Coordinate Validation Equality Core",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        "- Diagnostic semantics: actual_path_equality_core_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Full status: {full.get('status')}",
        f"- Equality labels: {actual.get('equality_label_count')}",
        f"- Deletion tests: {actual.get('deletion_test_count')}",
        f"- Final key count: {actual.get('final_key_count')}",
        "",
        "## Remaining Approximate Core",
        "",
        "| Slot | Field | Value | Solution | Group | Pose | Key |",
        "| --- | --- | ---: | --- | --- | ---: | --- |",
    ]
    for label in list(actual.get("remaining_labels", [])):
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
                    _markdown_cell(label.get("pose_index")),
                    _markdown_cell(label.get("stable_key")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Single Delete Results",
            "",
            "| Removed Slot | Field | Status | Preserves INFEASIBLE |",
            "| --- | --- | --- | --- |",
        ]
    )
    for result in list(actual.get("single_delete_results", [])):
        if not isinstance(result, Mapping):
            continue
        label = _mapping(result.get("removed_label"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(label.get("slot_key")),
                    _markdown_cell(label.get("field")),
                    _markdown_cell(result.get("status")),
                    _markdown_cell(result.get("preserves_infeasible")),
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


def render_phase3b_coordinate_validation_actual_path_equality_core_text(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    actual = _mapping(report.get("actual_path"))
    full = _mapping(actual.get("full_validation"))
    lines = [
        "Phase 3B actual-path coordinate validation equality core",
        f"candidate={candidate.get('key')}",
        f"anchor_idx={candidate.get('anchor_idx')}",
        "diagnostic_semantics=actual_path_equality_core_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"full_status={full.get('status')}",
        f"equality_label_count={actual.get('equality_label_count')}",
        f"deletion_test_count={actual.get('deletion_test_count')}",
        f"final_key_count={actual.get('final_key_count')}",
    ]
    for label in list(actual.get("remaining_labels", [])):
        if not isinstance(label, Mapping):
            continue
        lines.append(
            "remaining "
            f"slot={label.get('slot_key')} "
            f"field={label.get('field')} "
            f"value={label.get('forced_value')} "
            f"solution={label.get('solution_id')} "
            f"group={label.get('group_id')} "
            f"pose={label.get('pose_index')}"
        )
    return "\n".join(lines) + "\n"


def _run_subset_validation(
    *,
    model: Any,
    greedy: Mapping[str, Any],
    anchor_idx: int,
    time_limit_seconds: float,
    solver_profile: Mapping[str, Any],
    force_fields: Sequence[str],
    subset_keys: Sequence[str],
) -> Dict[str, Any]:
    return _compact_validation(
        model._validate_coordinate_forced_hint(
            solution_hint=dict(greedy.get("solution_hint", {})),
            ghost_anchor_hint_idx=int(anchor_idx),
            time_limit_seconds=float(time_limit_seconds),
            require_complete=True,
            solver_parameter_profile=solver_profile,
            force_fields=tuple(force_fields),
            force_equality_keys=set(str(key) for key in subset_keys),
            collect_force_equality_labels=False,
        )
    )


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
    full_validation: Mapping[str, Any],
    labels: Sequence[Mapping[str, Any]],
    deletion_test_count: int,
    max_delete_tests: int,
    model_error: Optional[str],
) -> Dict[str, Any]:
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "recommendation": "Actual-path equality-core diagnostic failed; inspect model_error.",
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
    if not labels:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "no_equality_labels",
            "recommendation": "Actual-path validation did not collect equality labels.",
        }
    if str(full_validation.get("status")) != "INFEASIBLE":
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "full_actual_path_not_infeasible",
            "recommendation": "Full actual-path equality set did not reproduce INFEASIBLE.",
        }
    exhausted = int(deletion_test_count) >= max(0, int(max_delete_tests))
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "actual_path_equality_core_approximated",
        "delete_tests_exhausted": bool(exhausted),
        "recommendation": "Use remaining actual-path labels as diagnostic shrink target; increase max-delete-tests if exhausted.",
    }


def _checks(
    status: Mapping[str, Any],
    context: Mapping[str, Any],
    full_validation: Mapping[str, Any],
    labels: Sequence[Mapping[str, Any]],
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
            "actual_path_equality_labels_collected",
            "pass" if labels else "fail",
            f"label_count={len(labels)}",
        ),
        _check(
            "full_actual_path_infeasible",
            "pass" if str(full_validation.get("status")) == "INFEASIBLE" else "fail",
            str(full_validation.get("status")),
        ),
        _check(
            "actual_path_equality_probe_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _first_single_delete(
    results: Sequence[Mapping[str, Any]],
    *,
    preserves: bool,
) -> Optional[Dict[str, Any]]:
    for result in results:
        if bool(result.get("preserves_infeasible", False)) is bool(preserves):
            return dict(result)
    return None


def _label_summary(labels: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
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
