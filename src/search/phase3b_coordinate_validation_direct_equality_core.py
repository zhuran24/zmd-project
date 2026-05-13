from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b_coordinate_validation_field_channel_delta import (
    _force_fields_for_variant,
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

COORDINATE_VALIDATION_DIRECT_EQUALITY_CORE_SOURCE = (
    "phase3b_coordinate_validation_direct_equality_core_v1"
)

DEFAULT_DIRECT_EQUALITY_CORE_GROUP_ID = (
    "group::manufacturing_5x5::planter_sandleaf::10"
)
DEFAULT_DIRECT_EQUALITY_CORE_FIELD_VARIANT = "x"


def build_phase3b_coordinate_validation_direct_equality_core(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 119,
    group_id: str = DEFAULT_DIRECT_EQUALITY_CORE_GROUP_ID,
    field_variant: str = DEFAULT_DIRECT_EQUALITY_CORE_FIELD_VARIANT,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 2.0,
    worker_count: int = 1,
    max_delete_tests: int = 64,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    normalized_group_id = str(group_id).strip()
    normalized_field_variant = str(field_variant).strip()
    force_fields = _force_fields_for_variant(normalized_field_variant)
    solver_profile = _normalize_solver_profile(
        solver_parameter_profile,
        time_limit_seconds=float(time_limit_seconds),
        worker_count=int(worker_count),
    )
    started = time.perf_counter()
    context: Dict[str, Any] = {}
    model_error: Optional[str] = None
    greedy: Dict[str, Any] = {}
    full_validation: Dict[str, Any] = {}
    labels: list[Dict[str, Any]] = []
    single_delete_results: list[Dict[str, Any]] = []
    greedy_steps: list[Dict[str, Any]] = []
    final_keys: list[str] = []
    deletion_test_count = 0
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
        group = group_by_id.get(normalized_group_id)
        if group is None:
            raise ValueError(f"Unknown direct-equality group id: {normalized_group_id}")
        model = context["model"]
        greedy = model._run_mandatory_greedy_pass(
            ordered_groups=[group],
            candidates_by_group=context["candidates_by_group"],
            blocked_cells=set(),
            stop_on_first_failure=True,
        )
        if bool(greedy.get("complete", False)):
            full_validation = _compact_validation(
                model._validate_coordinate_forced_hint(
                    solution_hint=dict(greedy.get("solution_hint", {})),
                    ghost_anchor_hint_idx=None,
                    time_limit_seconds=float(time_limit_seconds),
                    require_complete=False,
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
                    "reason": "greedy_group_incomplete",
                    "missing_hint_count": 0,
                    "missing_pose_tuple_count": 0,
                    "forced_slot_field_count": 0,
                    "forced_ghost_anchor": False,
                    "forced_fields": list(force_fields),
                    "force_equality_labels": [],
                    "require_complete": False,
                }
            )
        labels = [
            dict(label)
            for label in list(full_validation.get("force_equality_labels", []))
            if isinstance(label, Mapping)
        ]
        all_keys = [str(label.get("stable_key")) for label in labels]
        final_keys = list(all_keys)
        if str(full_validation.get("status")) == "INFEASIBLE":
            max_tests = max(0, int(max_delete_tests))
            for label in labels:
                if deletion_test_count >= max_tests:
                    break
                key = str(label.get("stable_key"))
                subset_keys = [candidate_key for candidate_key in all_keys if candidate_key != key]
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
                        "preserves_infeasible": str(validation.get("status")) == "INFEASIBLE",
                        "validation": validation,
                    }
                )
            current_keys = list(all_keys)
            for label in labels:
                if deletion_test_count >= max_tests:
                    break
                key = str(label.get("stable_key"))
                if key not in current_keys:
                    continue
                subset_keys = [candidate_key for candidate_key in current_keys if candidate_key != key]
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
        full_validation=full_validation,
        labels=labels,
        model_error=model_error,
        deletion_test_count=deletion_test_count,
        max_delete_tests=max_delete_tests,
    )
    return {
        "metadata": {
            "source": COORDINATE_VALIDATION_DIRECT_EQUALITY_CORE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "coordinate_validation_direct_equality_core_not_proof_source",
        },
        "paths": {"project_root": str(project_root)},
        "candidate": {
            "key": str(candidate),
            "ghost_rect": _candidate_rect(str(candidate)),
            "anchor_idx": int(anchor_idx),
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "group_id": normalized_group_id,
            "field_variant": normalized_field_variant,
            "force_fields": list(force_fields),
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "max_delete_tests": int(max_delete_tests),
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
        "direct_equality_core": {
            "greedy": _compact_greedy(greedy),
            "full_validation": full_validation,
            "equality_label_count": len(labels),
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
            "final_key_count": int(len(final_keys)),
            "final_keys": list(final_keys),
            "remaining_labels": remaining_labels,
            "remaining_summary": _label_summary(remaining_labels),
        },
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(status, model_error, labels),
    }


def render_phase3b_coordinate_validation_direct_equality_core_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    core = _mapping(report.get("direct_equality_core"))
    full = _mapping(core.get("full_validation"))
    lines = [
        "# Phase 3B Coordinate Validation Direct Equality Core",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        "- Diagnostic semantics: coordinate_validation_direct_equality_core_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Full direct equality status: {full.get('status')}",
        f"- Equality labels: {core.get('equality_label_count')}",
        f"- Deletion tests: {core.get('deletion_test_count')}",
        f"- Final key count: {core.get('final_key_count')}",
        "",
        "## Remaining Approximate Core",
        "",
        "| Slot | Field | Value | Solution | Pose | Key |",
        "| --- | --- | ---: | --- | ---: | --- |",
    ]
    for label in list(core.get("remaining_labels", [])):
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
    for result in list(core.get("single_delete_results", [])):
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


def render_phase3b_coordinate_validation_direct_equality_core_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    candidate = _mapping(report.get("candidate"))
    core = _mapping(report.get("direct_equality_core"))
    full = _mapping(core.get("full_validation"))
    lines = [
        "Phase 3B coordinate validation direct equality core",
        f"candidate={candidate.get('key')}",
        f"anchor_idx={candidate.get('anchor_idx')}",
        "diagnostic_semantics=coordinate_validation_direct_equality_core_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"full_status={full.get('status')}",
        f"equality_label_count={core.get('equality_label_count')}",
        f"deletion_test_count={core.get('deletion_test_count')}",
        f"final_key_count={core.get('final_key_count')}",
    ]
    for label in list(core.get("remaining_labels", [])):
        if not isinstance(label, Mapping):
            continue
        lines.append(
            "remaining "
            f"slot={label.get('slot_key')} "
            f"field={label.get('field')} "
            f"value={label.get('forced_value')} "
            f"solution={label.get('solution_id')} "
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
    del anchor_idx
    return _compact_validation(
        model._validate_coordinate_forced_hint(
            solution_hint=dict(greedy.get("solution_hint", {})),
            ghost_anchor_hint_idx=None,
            time_limit_seconds=float(time_limit_seconds),
            require_complete=False,
            solver_parameter_profile=solver_profile,
            force_fields=tuple(force_fields),
            force_equality_keys=set(str(key) for key in subset_keys),
            collect_force_equality_labels=False,
        )
    )


def _status_from_payload(
    *,
    full_validation: Mapping[str, Any],
    labels: Sequence[Mapping[str, Any]],
    model_error: Optional[str],
    deletion_test_count: int,
    max_delete_tests: int,
) -> Dict[str, Any]:
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "recommendation": "Direct equality core diagnostic failed; inspect model_error.",
        }
    if not labels:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "no_equality_labels",
            "recommendation": "No direct equality labels were collected.",
        }
    if str(full_validation.get("status")) != "INFEASIBLE":
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "full_set_not_infeasible",
            "recommendation": "Full direct equality set did not reproduce INFEASIBLE; do not use deletion core.",
        }
    exhausted = int(deletion_test_count) >= max(0, int(max_delete_tests))
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "direct_equality_core_approximated",
        "recommendation": (
            "Direct equality deletion/bisection produced an approximate core; "
            + (
                "delete-test cap was reached, treat as incomplete."
                if exhausted
                else "use remaining labels as diagnostic shrink target only."
            )
        ),
    }


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
    fields: Dict[str, int] = {}
    slots: Dict[str, int] = {}
    values: Dict[str, int] = {}
    poses: Dict[str, int] = {}
    for label in labels:
        field = str(label.get("field"))
        slot = str(label.get("slot_key"))
        value = str(label.get("forced_value"))
        pose = str(label.get("pose_index"))
        fields[field] = int(fields.get(field, 0)) + 1
        slots[slot] = int(slots.get(slot, 0)) + 1
        values[value] = int(values.get(value, 0)) + 1
        poses[pose] = int(poses.get(pose, 0)) + 1
    return {
        "field_counts": fields,
        "slot_counts": slots,
        "forced_value_counts": values,
        "pose_index_counts": poses,
    }


def _checks(
    status: Mapping[str, Any],
    model_error: Optional[str],
    labels: Sequence[Mapping[str, Any]],
) -> list[Dict[str, str]]:
    return [
        _check(
            "direct_core_probe_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "equality_labels_present",
            "pass" if labels else "fail",
            f"label_count={len(labels)}",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
