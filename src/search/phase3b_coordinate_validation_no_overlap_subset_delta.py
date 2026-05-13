from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from ortools.sat.python import cp_model

from src.models._cpsat_compat import cp_model_from_proto
from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    _clone_model_proto,
)
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b_coordinate_validation_direct_equality_core import (
    DEFAULT_DIRECT_EQUALITY_CORE_GROUP_ID,
)
from src.search.phase3b_coordinate_validation_global_family_delta import (
    _apply_delta_solver_profile,
    _build_12_key_base_proto,
    _proto_profile,
)
from src.search.phase3b_coordinate_validation_group_delta import (
    _build_delta_context,
    _candidate_rect,
    _check,
    _mapping,
    _normalize_solver_profile,
)
from src.search.phase3b_coordinate_validation_x_domain_order_audit import (
    _load_t24_core_labels,
)
from src.search.phase3b_forced_anchor_model_slice import (
    _constraint_has_field,
    _delete_constraint_indices,
    _first_line,
    _replace_repeated_int64,
    _response_stats_payload,
)

COORDINATE_VALIDATION_NO_OVERLAP_SUBSET_DELTA_SOURCE = (
    "phase3b_coordinate_validation_no_overlap_subset_delta_v1"
)

DEFAULT_NO_OVERLAP_SUBSET_GROUP_ID = DEFAULT_DIRECT_EQUALITY_CORE_GROUP_ID

DEFAULT_NO_OVERLAP_SUBSET_VARIANTS = (
    "base_12_key_full_model",
    "remove_core_no_overlap_only",
    "remove_core_plus_ghost_no_overlap_only",
    "remove_both_no_overlap",
    "remove_target_group_intervals_from_no_overlap",
    "remove_other_mandatory_intervals_from_no_overlap",
    "remove_required_optional_intervals_from_no_overlap",
    "remove_protocol_storage_box_intervals_from_no_overlap",
    "remove_power_pole_intervals_from_no_overlap",
    "remove_ghost_intervals_from_no_overlap",
    "keep_only_target_group_plus_protocol_storage_box",
    "keep_only_target_group_plus_power_pole",
    "keep_only_target_group_plus_ghost",
)

OWNER_TARGET_GROUP = "mandatory_target_group"
OWNER_OTHER_MANDATORY = "other_mandatory"
OWNER_REQUIRED_OPTIONAL = "required_optional"
OWNER_PROTOCOL_STORAGE = "residual_protocol_storage_box"
OWNER_POWER_POLE = "residual_power_pole"
OWNER_GHOST = "ghost"
OWNER_UNKNOWN = "unknown"


def build_phase3b_coordinate_validation_no_overlap_subset_delta(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 119,
    group_id: str = DEFAULT_NO_OVERLAP_SUBSET_GROUP_ID,
    core_json: Optional[Path] = None,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 2.0,
    worker_count: int = 1,
    variants: Optional[Sequence[str]] = None,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    normalized_group_id = str(group_id).strip()
    normalized_variants = _normalize_variants(variants or DEFAULT_NO_OVERLAP_SUBSET_VARIANTS)
    solver_profile = _normalize_solver_profile(
        solver_parameter_profile,
        time_limit_seconds=float(time_limit_seconds),
        worker_count=int(worker_count),
    )
    started = time.perf_counter()

    try:
        artifact_hashes = compute_exact_artifact_hashes(project_root)
        artifact_hash_error = None
    except Exception as exc:
        artifact_hashes = {}
        artifact_hash_error = f"{type(exc).__name__}: {exc}"

    core_payload = _load_t24_core_labels(core_json, group_id=normalized_group_id)
    core_labels = list(core_payload.get("labels", []))
    context: Dict[str, Any] = {}
    base_payload: Dict[str, Any] = {}
    proto_profile: Dict[str, Any] = {}
    no_overlap_inventory: Dict[str, Any] = {}
    entries: list[Dict[str, Any]] = []
    model_error: Optional[str] = None

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
        if normalized_group_id not in group_by_id:
            raise ValueError(f"Unknown no-overlap subset group id: {normalized_group_id}")
        model = context["model"]
        delegate = getattr(model, "_coordinate_delegate", None)
        if delegate is None:
            raise RuntimeError("Coordinate delegate unavailable")
        base_payload = _build_12_key_base_proto(
            model=model,
            delegate=delegate,
            group_id=normalized_group_id,
            labels=core_labels,
        )
        base_proto = base_payload["base_proto"]
        proto_profile = _proto_profile(base_proto)
        no_overlap_inventory = _no_overlap_inventory(base_proto, group_id=normalized_group_id)
        for variant in normalized_variants:
            entries.append(
                _evaluate_no_overlap_subset_variant(
                    base_proto=base_proto,
                    variant=str(variant),
                    group_id=normalized_group_id,
                    time_limit_seconds=float(time_limit_seconds),
                    worker_count=int(worker_count),
                    solver_profile=solver_profile,
                )
            )
        entries = _annotate_status_changes(entries)
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    status = _status_from_entries(entries, model_error=model_error)
    return {
        "metadata": {
            "source": COORDINATE_VALIDATION_NO_OVERLAP_SUBSET_DELTA_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "coordinate_validation_no_overlap_subset_delta_not_proof_source"
            ),
        },
        "paths": {
            "project_root": str(project_root),
            "core_json": str(Path(core_json).resolve()) if core_json is not None else None,
        },
        "candidate": {
            "key": str(candidate),
            "ghost_rect": _candidate_rect(str(candidate)),
            "anchor_idx": int(anchor_idx),
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "group_id": normalized_group_id,
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "variants": list(normalized_variants),
            "solver_parameter_profile": dict(solver_profile),
        },
        "artifact_hashes": dict(artifact_hashes),
        "artifact_hash_error": artifact_hash_error,
        "core_input": {
            key: value
            for key, value in dict(core_payload).items()
            if key != "labels"
        }
        | {"label_count": len(core_labels)},
        "context": {
            "ghost_anchor_count": int(context.get("ghost_anchor_count", 0)),
            "blocked_cell_count": int(context.get("blocked_cell_count", 0)),
            "ordered_group_count": int(context.get("ordered_group_count", 0)),
        },
        "base_model": {
            key: value
            for key, value in dict(base_payload).items()
            if key != "base_proto"
        },
        "proto_profile": proto_profile,
        "no_overlap_inventory": no_overlap_inventory,
        "status": status,
        "delta": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "evaluated_variants": [
                str(entry.get("variant"))
                for entry in entries
                if bool(entry.get("evaluated", False))
            ],
            "skipped_variants": [
                {
                    "variant": str(entry.get("variant")),
                    "skip_reason": entry.get("skip_reason"),
                }
                for entry in entries
                if not bool(entry.get("evaluated", False))
            ],
            "first_status_change": _first_status_change(entries),
            "first_unlocking_variant": _first_unlocking_variant(entries),
            "implicated_variants": _implicated_variants(entries),
        },
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(status=status, entries=entries, model_error=model_error),
    }


def render_phase3b_coordinate_validation_no_overlap_subset_delta_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    delta = _mapping(report.get("delta"))
    inventory = _mapping(report.get("no_overlap_inventory"))
    first_change = _mapping(delta.get("first_status_change"))
    lines = [
        "# Phase 3B Coordinate Validation NoOverlap2D Interval Subset Delta",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        "- Diagnostic semantics: coordinate_validation_no_overlap_subset_delta_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Base status: {status.get('base_status')}",
        f"- NoOverlap2D constraints: {inventory.get('no_overlap_constraint_count')}",
        f"- Owner counts: {inventory.get('owner_bucket_counts')}",
        f"- First status change: {first_change.get('variant')}",
        "",
        "## Variant Matrix",
        "",
        "| Variant | Status | Evaluated | Modified | Removed Pairs | Kept Pairs | Confidence | Changed |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for entry in list(delta.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        selector = _mapping(entry.get("selector_summary"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("variant")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("evaluated")),
                    _markdown_cell(selector.get("modified_no_overlap_constraint_count")),
                    _markdown_cell(selector.get("removed_interval_pair_count")),
                    _markdown_cell(selector.get("kept_interval_pair_count")),
                    _markdown_cell(selector.get("selector_confidence")),
                    _markdown_cell(entry.get("changes_base_status")),
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


def render_phase3b_coordinate_validation_no_overlap_subset_delta_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    delta = _mapping(report.get("delta"))
    lines = [
        "Phase 3B coordinate validation no-overlap subset delta",
        f"outcome={status.get('outcome')}",
        f"base_status={status.get('base_status')}",
        f"recommendation={status.get('recommendation')}",
        f"first_status_change={delta.get('first_status_change')}",
    ]
    for entry in list(delta.get("entries", [])):
        if isinstance(entry, Mapping):
            selector = _mapping(entry.get("selector_summary"))
            lines.append(
                "entry "
                f"variant={entry.get('variant')} "
                f"status={entry.get('status')} "
                f"evaluated={entry.get('evaluated')} "
                f"modified={selector.get('modified_no_overlap_constraint_count')} "
                f"removed_pairs={selector.get('removed_interval_pair_count')} "
                f"changed={entry.get('changes_base_status')}"
            )
    return "\n".join(lines) + "\n"


def _evaluate_no_overlap_subset_variant(
    *,
    base_proto: Any,
    variant: str,
    group_id: str,
    time_limit_seconds: float,
    worker_count: int,
    solver_profile: Mapping[str, Any],
) -> Dict[str, Any]:
    local_proto = _clone_model_proto(base_proto)
    selector = _apply_no_overlap_subset_variant_selector(
        local_proto,
        variant=str(variant),
        group_id=str(group_id),
    )
    if bool(selector.get("skipped", False)):
        return {
            "variant": str(variant),
            "evaluated": False,
            "status": "SKIPPED",
            "skip_reason": selector.get("skip_reason"),
            "selector_summary": selector,
            "semantic_weakening": bool(selector.get("semantic_weakening", True)),
            "proof_evidence": False,
            "changes_base_status": False,
        }
    local_model = cp_model_from_proto(local_proto)
    solver = cp_model.CpSolver()
    applied_profile = _apply_delta_solver_profile(
        solver,
        time_limit_seconds=float(time_limit_seconds),
        worker_count=int(worker_count),
        profile=solver_profile,
    )
    started = time.perf_counter()
    status = solver.Solve(local_model)
    response_stats = solver.ResponseStats()
    return {
        "variant": str(variant),
        "evaluated": True,
        "status": solver.StatusName(status),
        "accepted": status in {cp_model.OPTIMAL, cp_model.FEASIBLE},
        "elapsed_seconds": float(time.perf_counter() - started),
        "wall_time": float(solver.WallTime()),
        "user_time": float(solver.UserTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "deterministic_time": float(
            _response_stats_payload(response_stats).get("deterministic_time", 0.0)
        ),
        "selector_summary": selector,
        "semantic_weakening": bool(selector.get("semantic_weakening", True)),
        "proof_evidence": False,
        "solver_parameter_profile": applied_profile,
        "response_summary": _first_line(response_stats),
        "response_stats_parsed": _response_stats_payload(response_stats),
    }


def _apply_no_overlap_subset_variant_selector(
    model_proto: Any,
    *,
    variant: str,
    group_id: str,
) -> Dict[str, Any]:
    variant_text = str(variant)
    if variant_text == "base_12_key_full_model":
        return _selector_summary(
            variant=variant_text,
            selector_mode="base_no_modification",
            selector_confidence="high",
            semantic_weakening=False,
            skipped=False,
            examples=[],
        )
    if variant_text == "remove_core_no_overlap_only":
        return _remove_no_overlap_constraints_by_kind(
            model_proto,
            variant=variant_text,
            group_id=group_id,
            no_overlap_kind="core_only",
        )
    if variant_text == "remove_core_plus_ghost_no_overlap_only":
        return _remove_no_overlap_constraints_by_kind(
            model_proto,
            variant=variant_text,
            group_id=group_id,
            no_overlap_kind="core_plus_ghost",
        )
    if variant_text == "remove_both_no_overlap":
        return _remove_no_overlap_constraints_by_kind(
            model_proto,
            variant=variant_text,
            group_id=group_id,
            no_overlap_kind="any",
        )
    owner_removal_variants = {
        "remove_target_group_intervals_from_no_overlap": (OWNER_TARGET_GROUP,),
        "remove_other_mandatory_intervals_from_no_overlap": (OWNER_OTHER_MANDATORY,),
        "remove_required_optional_intervals_from_no_overlap": (OWNER_REQUIRED_OPTIONAL,),
        "remove_protocol_storage_box_intervals_from_no_overlap": (OWNER_PROTOCOL_STORAGE,),
        "remove_power_pole_intervals_from_no_overlap": (OWNER_POWER_POLE,),
        "remove_ghost_intervals_from_no_overlap": (OWNER_GHOST,),
    }
    if variant_text in owner_removal_variants:
        return _filter_no_overlap_intervals(
            model_proto,
            variant=variant_text,
            group_id=group_id,
            remove_owners=owner_removal_variants[variant_text],
            keep_owners=None,
            selector_mode=f"remove owners {owner_removal_variants[variant_text]} from all NoOverlap2D constraints",
            selector_confidence="high",
        )
    keep_variants = {
        "keep_only_target_group_plus_protocol_storage_box": (
            OWNER_TARGET_GROUP,
            OWNER_PROTOCOL_STORAGE,
        ),
        "keep_only_target_group_plus_power_pole": (
            OWNER_TARGET_GROUP,
            OWNER_POWER_POLE,
        ),
        "keep_only_target_group_plus_ghost": (
            OWNER_TARGET_GROUP,
            OWNER_GHOST,
        ),
    }
    if variant_text in keep_variants:
        return _filter_no_overlap_intervals(
            model_proto,
            variant=variant_text,
            group_id=group_id,
            remove_owners=None,
            keep_owners=keep_variants[variant_text],
            selector_mode=f"keep only owners {keep_variants[variant_text]} in all NoOverlap2D constraints",
            selector_confidence="medium",
        )
    return _selector_summary(
        variant=variant_text,
        selector_mode="unsupported_variant",
        selector_confidence="none",
        semantic_weakening=True,
        skipped=True,
        skip_reason=f"unsupported variant: {variant_text}",
        examples=[],
    )


def _remove_no_overlap_constraints_by_kind(
    model_proto: Any,
    *,
    variant: str,
    group_id: str,
    no_overlap_kind: str,
) -> Dict[str, Any]:
    inventory = _no_overlap_inventory(model_proto, group_id=group_id)
    selected = [
        item
        for item in list(inventory.get("constraints", []))
        if str(no_overlap_kind) == "any"
        or str(item.get("no_overlap_kind")) == str(no_overlap_kind)
    ]
    removed_indices = [int(item["constraint_idx"]) for item in selected]
    if removed_indices:
        _delete_constraint_indices(model_proto, removed_indices)
    return _selector_summary(
        variant=variant,
        selector_mode=f"remove NoOverlap2D constraint kind={no_overlap_kind}",
        selector_confidence="high",
        semantic_weakening=True,
        skipped=not bool(removed_indices),
        skip_reason="selector_matched_no_no_overlap_constraints" if not removed_indices else None,
        removed_no_overlap_constraint_indices=removed_indices,
        modified_no_overlap_constraint_count=len(removed_indices),
        removed_interval_pair_count=sum(int(item.get("interval_pair_count", 0)) for item in selected),
        kept_interval_pair_count=0,
        removed_owner_bucket_counts=_sum_owner_counts(selected),
        kept_owner_bucket_counts={},
        examples=_examples_from_inventory(selected),
    )


def _filter_no_overlap_intervals(
    model_proto: Any,
    *,
    variant: str,
    group_id: str,
    remove_owners: Optional[Sequence[str]],
    keep_owners: Optional[Sequence[str]],
    selector_mode: str,
    selector_confidence: str,
) -> Dict[str, Any]:
    constraints = list(getattr(model_proto, "constraints", []))
    interval_names = _interval_names(model_proto)
    remove_set = None if remove_owners is None else {str(owner) for owner in remove_owners}
    keep_set = None if keep_owners is None else {str(owner) for owner in keep_owners}
    modified_indices: list[int] = []
    removed_counts: Counter[str] = Counter()
    kept_counts: Counter[str] = Counter()
    removed_pair_count = 0
    kept_pair_count = 0
    examples: list[Dict[str, Any]] = []
    for constraint_idx, constraint in enumerate(constraints):
        no_overlap = (
            getattr(constraint, "no_overlap_2d", None)
            if _constraint_has_field(constraint, "no_overlap_2d")
            else None
        )
        if no_overlap is None:
            continue
        x_intervals = [int(value) for value in list(getattr(no_overlap, "x_intervals", []))]
        y_intervals = [int(value) for value in list(getattr(no_overlap, "y_intervals", []))]
        if len(x_intervals) != len(y_intervals):
            continue
        kept_x: list[int] = []
        kept_y: list[int] = []
        constraint_removed = 0
        constraint_kept = 0
        for x_idx, y_idx in zip(x_intervals, y_intervals):
            x_name = interval_names.get(int(x_idx), "")
            y_name = interval_names.get(int(y_idx), "")
            owner = _owner_bucket_for_interval_pair(x_name, y_name, group_id=group_id)
            should_keep = owner in keep_set if keep_set is not None else owner not in remove_set
            if should_keep:
                kept_x.append(int(x_idx))
                kept_y.append(int(y_idx))
                kept_counts[str(owner)] += 1
                kept_pair_count += 1
                constraint_kept += 1
            else:
                removed_counts[str(owner)] += 1
                removed_pair_count += 1
                constraint_removed += 1
                if len(examples) < 8:
                    examples.append(
                        {
                            "constraint_idx": int(constraint_idx),
                            "x_interval_idx": int(x_idx),
                            "y_interval_idx": int(y_idx),
                            "x_interval_name": str(x_name),
                            "y_interval_name": str(y_name),
                            "owner_bucket": str(owner),
                        }
                    )
        if constraint_removed <= 0:
            continue
        _replace_repeated_int64(getattr(no_overlap, "x_intervals"), kept_x)
        _replace_repeated_int64(getattr(no_overlap, "y_intervals"), kept_y)
        modified_indices.append(int(constraint_idx))
    skipped = removed_pair_count <= 0
    return _selector_summary(
        variant=variant,
        selector_mode=selector_mode,
        selector_confidence=selector_confidence,
        semantic_weakening=True,
        skipped=skipped,
        skip_reason="selector_matched_no_interval_pairs" if skipped else None,
        modified_no_overlap_constraint_count=len(modified_indices),
        modified_no_overlap_constraint_indices=modified_indices,
        removed_interval_pair_count=removed_pair_count,
        kept_interval_pair_count=kept_pair_count,
        removed_owner_bucket_counts=dict(sorted(removed_counts.items())),
        kept_owner_bucket_counts=dict(sorted(kept_counts.items())),
        examples=examples,
    )


def _no_overlap_inventory(model_proto: Any, *, group_id: str) -> Dict[str, Any]:
    interval_names = _interval_names(model_proto)
    constraints_payload: list[Dict[str, Any]] = []
    owner_total: Counter[str] = Counter()
    for constraint_idx, constraint in enumerate(list(getattr(model_proto, "constraints", []))):
        no_overlap = (
            getattr(constraint, "no_overlap_2d", None)
            if _constraint_has_field(constraint, "no_overlap_2d")
            else None
        )
        if no_overlap is None:
            continue
        x_intervals = [int(value) for value in list(getattr(no_overlap, "x_intervals", []))]
        y_intervals = [int(value) for value in list(getattr(no_overlap, "y_intervals", []))]
        owner_counts: Counter[str] = Counter()
        examples: list[Dict[str, Any]] = []
        for x_idx, y_idx in zip(x_intervals, y_intervals):
            x_name = interval_names.get(int(x_idx), "")
            y_name = interval_names.get(int(y_idx), "")
            owner = _owner_bucket_for_interval_pair(x_name, y_name, group_id=group_id)
            owner_counts[str(owner)] += 1
            owner_total[str(owner)] += 1
            if len(examples) < 8:
                examples.append(
                    {
                        "x_interval_idx": int(x_idx),
                        "y_interval_idx": int(y_idx),
                        "x_interval_name": str(x_name),
                        "y_interval_name": str(y_name),
                        "owner_bucket": str(owner),
                    }
                )
        kind = "core_plus_ghost" if owner_counts.get(OWNER_GHOST, 0) > 0 else "core_only"
        constraints_payload.append(
            {
                "constraint_idx": int(constraint_idx),
                "name": str(getattr(constraint, "name", "")),
                "no_overlap_kind": kind,
                "interval_pair_count": min(len(x_intervals), len(y_intervals)),
                "x_interval_count": len(x_intervals),
                "y_interval_count": len(y_intervals),
                "owner_bucket_counts": dict(sorted(owner_counts.items())),
                "examples": examples,
            }
        )
    return {
        "no_overlap_constraint_count": len(constraints_payload),
        "owner_bucket_counts": dict(sorted(owner_total.items())),
        "constraints": constraints_payload,
    }


def _interval_names(model_proto: Any) -> Dict[int, str]:
    return {
        int(index): str(getattr(constraint, "name", ""))
        for index, constraint in enumerate(list(getattr(model_proto, "constraints", [])))
        if _constraint_has_field(constraint, "interval")
    }


def _owner_bucket_for_interval_pair(
    x_interval_name: str,
    y_interval_name: str,
    *,
    group_id: str,
) -> str:
    name = str(x_interval_name) or str(y_interval_name)
    if str(group_id) in name:
        return OWNER_TARGET_GROUP
    if "residual_optional::protocol_storage_box" in name:
        return OWNER_PROTOCOL_STORAGE
    if "residual_optional::power_pole" in name:
        return OWNER_POWER_POLE
    if "required_optional::" in name:
        return OWNER_REQUIRED_OPTIONAL
    if name.startswith("ghost_") or "__ghost" in name or "ghost__" in name:
        return OWNER_GHOST
    if "group::" in name:
        return OWNER_OTHER_MANDATORY
    return OWNER_UNKNOWN


def _selector_summary(
    *,
    variant: str,
    selector_mode: str,
    selector_confidence: str,
    semantic_weakening: bool,
    skipped: bool,
    examples: Sequence[Mapping[str, Any]],
    skip_reason: Optional[str] = None,
    removed_no_overlap_constraint_indices: Sequence[int] = (),
    modified_no_overlap_constraint_indices: Sequence[int] = (),
    modified_no_overlap_constraint_count: int = 0,
    removed_interval_pair_count: int = 0,
    kept_interval_pair_count: int = 0,
    removed_owner_bucket_counts: Optional[Mapping[str, int]] = None,
    kept_owner_bucket_counts: Optional[Mapping[str, int]] = None,
) -> Dict[str, Any]:
    return {
        "variant": str(variant),
        "selector_mode": str(selector_mode),
        "selector_confidence": str(selector_confidence),
        "semantic_weakening": bool(semantic_weakening),
        "proof_evidence": False,
        "skipped": bool(skipped),
        "skip_reason": skip_reason,
        "removed_no_overlap_constraint_indices": [
            int(index) for index in removed_no_overlap_constraint_indices
        ],
        "modified_no_overlap_constraint_indices": [
            int(index) for index in modified_no_overlap_constraint_indices
        ],
        "modified_no_overlap_constraint_count": int(modified_no_overlap_constraint_count),
        "removed_interval_pair_count": int(removed_interval_pair_count),
        "kept_interval_pair_count": int(kept_interval_pair_count),
        "removed_owner_bucket_counts": dict(removed_owner_bucket_counts or {}),
        "kept_owner_bucket_counts": dict(kept_owner_bucket_counts or {}),
        "examples": [dict(example) for example in examples],
    }


def _examples_from_inventory(items: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    examples: list[Dict[str, Any]] = []
    for item in items:
        examples.append(
            {
                "constraint_idx": int(item.get("constraint_idx", -1)),
                "no_overlap_kind": str(item.get("no_overlap_kind")),
                "interval_pair_count": int(item.get("interval_pair_count", 0)),
                "owner_bucket_counts": dict(item.get("owner_bucket_counts", {})),
            }
        )
        if len(examples) >= 5:
            break
    return examples


def _sum_owner_counts(items: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        for owner, value in _mapping(item.get("owner_bucket_counts")).items():
            counts[str(owner)] += int(value)
    return dict(sorted(counts.items()))


def _status_from_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    model_error: Optional[str],
) -> Dict[str, Any]:
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "base_status": None,
            "recommendation": "NoOverlap subset delta failed; inspect model_error.",
        }
    base = _base_entry(entries)
    base_status = None if base is None else str(base.get("status"))
    first_unlocking = _first_unlocking_variant(entries)
    if base is None or not bool(base.get("evaluated", False)):
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "base_not_evaluated",
            "base_status": base_status,
            "recommendation": "Base 12-key full-model variant did not evaluate.",
        }
    if base_status != "INFEASIBLE":
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "base_not_infeasible",
            "base_status": base_status,
            "recommendation": "Base 12-key full-model status was not INFEASIBLE; refresh the T24 core before interpreting variants.",
        }
    if first_unlocking is not None:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_overlap_subset_unlocking_variant_found",
            "base_status": base_status,
            "recommendation": "At least one no-overlap subset variant reached FEASIBLE/OPTIMAL under semantic weakening; inspect selector details.",
        }
    if _first_status_change(entries) is not None:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_overlap_subset_status_changed_nonterminal",
            "base_status": base_status,
            "recommendation": "A no-overlap subset variant changed status away from INFEASIBLE but did not prove feasibility within the bounded run.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "no_overlap_subset_no_status_change",
        "base_status": base_status,
        "recommendation": "No no-overlap subset variant changed the 12-key INFEASIBLE status; refine selectors or shrink further.",
    }


def _checks(
    *,
    status: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    evaluated = [entry for entry in entries if bool(entry.get("evaluated", False))]
    skipped = [entry for entry in entries if not bool(entry.get("evaluated", False))]
    return [
        _check(
            "base_status_infeasible",
            "pass" if status.get("base_status") == "INFEASIBLE" else "fail",
            f"base_status={status.get('base_status')}",
        ),
        _check(
            "variants_evaluated",
            "pass" if evaluated else "fail",
            f"evaluated={len(evaluated)} skipped={len(skipped)}",
        ),
        _check(
            "semantic_weakening_marked",
            "pass"
            if all(
                (str(entry.get("variant")) == "base_12_key_full_model")
                or bool(entry.get("semantic_weakening", False))
                for entry in entries
            )
            else "fail",
            "all non-base entries mark semantic weakening",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _annotate_status_changes(entries: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    base = _base_entry(entries)
    base_status = None if base is None else str(base.get("status"))
    annotated: list[Dict[str, Any]] = []
    for entry in entries:
        payload = dict(entry)
        if not bool(payload.get("evaluated", False)) or base_status is None:
            payload["changes_base_status"] = False
        elif str(payload.get("variant")) == "base_12_key_full_model":
            payload["changes_base_status"] = False
        else:
            payload["changes_base_status"] = str(payload.get("status")) != base_status
        annotated.append(payload)
    return annotated


def _first_status_change(entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    base = _base_entry(entries)
    if base is None:
        return None
    base_status = str(base.get("status"))
    for entry in entries:
        if not bool(entry.get("evaluated", False)):
            continue
        if str(entry.get("variant")) == "base_12_key_full_model":
            continue
        if str(entry.get("status")) != base_status:
            selector = _mapping(entry.get("selector_summary"))
            return {
                "variant": str(entry.get("variant")),
                "status": str(entry.get("status")),
                "base_status": base_status,
                "selector_confidence": selector.get("selector_confidence"),
                "removed_interval_pair_count": selector.get("removed_interval_pair_count"),
                "modified_no_overlap_constraint_count": selector.get("modified_no_overlap_constraint_count"),
            }
    return None


def _first_unlocking_variant(entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    first_change = _first_status_change(entries)
    if first_change is None:
        return None
    if str(first_change.get("status")) not in {"OPTIMAL", "FEASIBLE"}:
        return None
    return dict(first_change)


def _implicated_variants(entries: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    base = _base_entry(entries)
    if base is None or str(base.get("status")) != "INFEASIBLE":
        return []
    result: list[Dict[str, Any]] = []
    for entry in entries:
        if not bool(entry.get("evaluated", False)):
            continue
        if str(entry.get("variant")) == "base_12_key_full_model":
            continue
        if str(entry.get("status")) == "INFEASIBLE":
            continue
        selector = _mapping(entry.get("selector_summary"))
        result.append(
            {
                "variant": str(entry.get("variant")),
                "status": str(entry.get("status")),
                "selector_confidence": selector.get("selector_confidence"),
                "removed_interval_pair_count": selector.get("removed_interval_pair_count"),
                "removed_owner_bucket_counts": selector.get("removed_owner_bucket_counts"),
            }
        )
    return result


def _base_entry(entries: Sequence[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    for entry in entries:
        if str(entry.get("variant")) == "base_12_key_full_model":
            return entry
    return None


def _status_counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status", "UNKNOWN"))
        counts[status] = int(counts.get(status, 0)) + 1
    return dict(sorted(counts.items()))


def _normalize_variants(variants: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in variants:
        token = str(raw).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return tuple(result or DEFAULT_NO_OVERLAP_SUBSET_VARIANTS)


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
