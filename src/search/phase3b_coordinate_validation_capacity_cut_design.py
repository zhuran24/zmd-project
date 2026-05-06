from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b_coordinate_validation_group_delta import (
    _build_delta_context,
    _check,
    _mapping,
)
from src.search.phase3b_coordinate_validation_target_ghost_capacity_repro import (
    DEFAULT_TARGET_GHOST_CAPACITY_GROUP_ID,
    _evaluate_capacity_variant,
    _geometry_payload,
)
from src.search.phase3b_coordinate_validation_x_domain_order_audit import (
    _load_t24_core_labels,
)

COORDINATE_VALIDATION_CAPACITY_CUT_DESIGN_SOURCE = (
    "phase3b_coordinate_validation_capacity_cut_design_v1"
)


def build_phase3b_coordinate_validation_capacity_cut_design(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 119,
    group_id: str = DEFAULT_TARGET_GHOST_CAPACITY_GROUP_ID,
    core_json: Optional[Path] = None,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 1.0,
    worker_count: int = 1,
    max_k: Optional[int] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    normalized_group_id = str(group_id).strip()
    started = time.perf_counter()

    try:
        artifact_hashes = compute_exact_artifact_hashes(project_root)
        artifact_hash_error = None
    except Exception as exc:
        artifact_hashes = {}
        artifact_hash_error = f"{type(exc).__name__}: {exc}"

    core_payload = _load_t24_core_labels(core_json, group_id=normalized_group_id)
    core_labels = list(core_payload.get("labels", []))
    prefix_entries: list[Dict[str, Any]] = []
    baseline_entries: list[Dict[str, Any]] = []
    geometry: Dict[str, Any] = {}
    thresholds: Dict[str, Any] = {}
    cut_design: Dict[str, Any] = {}
    model_error: Optional[str] = None
    context: Dict[str, Any] = {}

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
            raise ValueError(f"Unknown target group id: {normalized_group_id}")
        model = context["model"]
        delegate = getattr(model, "_coordinate_delegate", None)
        if delegate is None:
            raise RuntimeError("Coordinate delegate unavailable")

        geometry = _geometry_payload(
            model=model,
            delegate=delegate,
            group=group,
            group_id=normalized_group_id,
            labels=core_labels,
            anchor_idx=int(anchor_idx),
        )
        thresholds = _capacity_thresholds(
            geometry=geometry,
            grid_h=int(getattr(delegate, "grid_h", 0)),
        )

        if core_labels:
            baseline_entries.append(
                _evaluate_capacity_variant(
                    model=model,
                    delegate=delegate,
                    group=group,
                    group_id=normalized_group_id,
                    labels=core_labels,
                    anchor_idx=int(anchor_idx),
                    variant="target_slots_12_core_only_without_ghost",
                    time_limit_seconds=float(time_limit_seconds),
                    worker_count=int(worker_count),
                )
            )
        limit = min(len(core_labels), int(max_k if max_k is not None else len(core_labels)))
        for k in range(1, limit + 1):
            entry = _evaluate_capacity_variant(
                model=model,
                delegate=delegate,
                group=group,
                group_id=normalized_group_id,
                labels=core_labels[:k],
                anchor_idx=int(anchor_idx),
                variant="target_slots_12_core_only_plus_anchor119_ghost",
                time_limit_seconds=float(time_limit_seconds),
                worker_count=int(worker_count),
            )
            entry = dict(entry)
            entry["variant"] = f"target_slots_core_prefix_{k}_plus_anchor119_ghost"
            entry["source_variant"] = "target_slots_12_core_only_plus_anchor119_ghost"
            entry["k"] = int(k)
            entry["prefix_slot_indices"] = [
                int(label.get("slot_index", -1))
                for label in core_labels[:k]
                if int(label.get("slot_index", -1)) >= 0
            ]
            prefix_entries.append(entry)

        cut_design = _cut_design_payload(
            group_id=normalized_group_id,
            candidate=str(candidate),
            anchor_idx=int(anchor_idx),
            geometry=geometry,
            thresholds=thresholds,
            minimal_infeasible_k=_minimal_infeasible_k(prefix_entries),
        )
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    status = _status_from_design(prefix_entries=prefix_entries, model_error=model_error)
    return {
        "metadata": {
            "source": COORDINATE_VALIDATION_CAPACITY_CUT_DESIGN_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "coordinate_validation_capacity_cut_design_not_proof_source"
            ),
        },
        "paths": {
            "project_root": str(project_root),
            "core_json": str(Path(core_json).resolve()) if core_json is not None else None,
        },
        "profile": {
            "candidate": str(candidate),
            "anchor_idx": int(anchor_idx),
            "group_id": normalized_group_id,
            "master_search_profile": str(master_search_profile),
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "max_k": max_k,
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
        "geometry": geometry,
        "thresholds": thresholds,
        "baseline_entries": baseline_entries,
        "subset_probe": {
            "kind": "deterministic_core_prefix_k",
            "entries": prefix_entries,
            "minimal_infeasible_k": _minimal_infeasible_k(prefix_entries),
            "first_infeasible_entry": _first_infeasible(prefix_entries),
            "status_counts": _status_counts(prefix_entries),
        },
        "cut_design": cut_design,
        "status": status,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(
            status=status,
            prefix_entries=prefix_entries,
            thresholds=thresholds,
            model_error=model_error,
        ),
    }


def render_phase3b_coordinate_validation_capacity_cut_design_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    geometry = _mapping(report.get("geometry"))
    thresholds = _mapping(report.get("thresholds"))
    subset = _mapping(report.get("subset_probe"))
    cut = _mapping(report.get("cut_design"))
    target = _mapping(geometry.get("target_group"))
    ghost = _mapping(geometry.get("anchor119_ghost"))
    lines = [
        "# Phase 3B Capacity Cut Design and Minimal Aggregate Subset",
        "",
        "- Diagnostic semantics: coordinate_validation_capacity_cut_design_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Target group: {target.get('group_id')}",
        f"- Target slots: {target.get('slot_count')}",
        f"- Core label count: {_mapping(geometry.get('core_labels')).get('label_count')}",
        f"- Anchor119 ghost: {dict(ghost)}",
        "",
        "## Thresholds",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Pure aggregate height threshold | {thresholds.get('pure_aggregate_height_threshold_k')} |",
        f"| Fixed-anchor vertical capacity slots | {thresholds.get('fixed_anchor_vertical_capacity_slots')} |",
        f"| Fixed-anchor infeasible threshold | {thresholds.get('fixed_anchor_infeasible_threshold_k')} |",
        f"| CP-SAT minimal infeasible prefix k | {subset.get('minimal_infeasible_k')} |",
        "",
        "## k-Subset Probe",
        "",
        "| k | Status | Branches | Conflicts | Required Strip Height | Capacity Flag |",
        "| ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for entry in list(subset.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        cap = _mapping(entry.get("capacity_summary"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("k")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("branches")),
                    _markdown_cell(entry.get("conflicts")),
                    _markdown_cell(cap.get("required_vertical_height_if_same_x_strip")),
                    _markdown_cell(cap.get("capacity_conflict_possible")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Cut Proposal",
            "",
            f"- Name: {cut.get('name')}",
            f"- Recommended home: {cut.get('recommended_home')}",
            f"- Runtime readiness: {cut.get('runtime_readiness')}",
            f"- Proof semantics: {cut.get('proof_semantics')}",
            "",
            "Premises:",
        ]
    )
    for premise in list(cut.get("premises", [])):
        lines.append(f"- {premise}")
    lines.extend(["", "Required tests before runtime promotion:"])
    for test in list(cut.get("required_tests_before_promotion", [])):
        lines.append(f"- {test}")
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


def render_phase3b_coordinate_validation_capacity_cut_design_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    subset = _mapping(report.get("subset_probe"))
    thresholds = _mapping(report.get("thresholds"))
    lines = [
        "Phase 3B capacity cut design",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"minimal_infeasible_k={subset.get('minimal_infeasible_k')}",
        f"pure_aggregate_threshold={thresholds.get('pure_aggregate_height_threshold_k')}",
        f"fixed_anchor_threshold={thresholds.get('fixed_anchor_infeasible_threshold_k')}",
        f"status_counts={subset.get('status_counts')}",
    ]
    for entry in list(subset.get("entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "entry "
                f"k={entry.get('k')} "
                f"status={entry.get('status')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')}"
            )
    return "\n".join(lines) + "\n"


def _capacity_thresholds(
    *,
    geometry: Mapping[str, Any],
    grid_h: int,
) -> Dict[str, Any]:
    target = _mapping(geometry.get("target_group"))
    dims = _mapping(target.get("dims"))
    ghost = _mapping(geometry.get("anchor119_ghost"))
    slot_h = int(dims.get("h", 0))
    slot_w = int(dims.get("w", 0))
    ghost_y = int(ghost.get("y", 0))
    ghost_h = int(ghost.get("h", 0))
    ghost_x = int(ghost.get("x", 0))
    ghost_w = int(ghost.get("w", 0))
    x_overlap = _intervals_overlap(0, slot_w, ghost_x, ghost_w)
    if slot_h <= 0 or grid_h <= 0:
        return {
            "x_overlap_with_forced_x0_slot": x_overlap,
            "reason": "missing grid or slot height",
        }
    pure_threshold = math.floor(max(0, int(grid_h) - ghost_h) / slot_h) + 1
    lower_height = max(0, min(int(grid_h), ghost_y))
    upper_height = max(0, int(grid_h) - max(0, ghost_y + ghost_h))
    lower_slots = lower_height // slot_h
    upper_slots = upper_height // slot_h
    fixed_capacity = lower_slots + upper_slots
    return {
        "grid_height": int(grid_h),
        "slot_height": slot_h,
        "slot_width": slot_w,
        "ghost_y": ghost_y,
        "ghost_height": ghost_h,
        "ghost_x": ghost_x,
        "ghost_width": ghost_w,
        "x_overlap_with_forced_x0_slot": x_overlap,
        "pure_aggregate_height_threshold_k": int(pure_threshold),
        "pure_aggregate_formula": "floor((grid_h - ghost_h) / slot_h) + 1",
        "lower_segment_height": int(lower_height),
        "upper_segment_height": int(upper_height),
        "lower_segment_slot_capacity": int(lower_slots),
        "upper_segment_slot_capacity": int(upper_slots),
        "fixed_anchor_vertical_capacity_slots": int(fixed_capacity),
        "fixed_anchor_infeasible_threshold_k": int(fixed_capacity + 1),
        "fixed_anchor_formula": "floor(ghost_y / slot_h) + floor((grid_h - (ghost_y + ghost_h)) / slot_h) + 1",
        "threshold_depends_on": (
            "fixed ghost y-position and slot height; total-height alone is weaker"
        ),
    }


def _cut_design_payload(
    *,
    group_id: str,
    candidate: str,
    anchor_idx: int,
    geometry: Mapping[str, Any],
    thresholds: Mapping[str, Any],
    minimal_infeasible_k: Optional[int],
) -> Dict[str, Any]:
    ghost = _mapping(geometry.get("anchor119_ghost"))
    target = _mapping(geometry.get("target_group"))
    threshold = int(minimal_infeasible_k or thresholds.get("fixed_anchor_infeasible_threshold_k", 0))
    return {
        "name": "same_x_strip_fixed_ghost_capacity_cut",
        "candidate": str(candidate),
        "anchor_idx": int(anchor_idx),
        "group_id": str(group_id),
        "recommended_home": (
            "coordinate-validation precheck or Benders cut generation before expensive full validation"
        ),
        "not_recommended_as": (
            "release proof, frontdoor status promotion, or unconditional runtime rejection without tests"
        ),
        "premises": [
            f"ghost anchor {anchor_idx} is active with rect x={ghost.get('x')}, y={ghost.get('y')}, w={ghost.get('w')}, h={ghost.get('h')}",
            "target slots are mandatory rectangles in the same NoOverlap2D relation as the ghost",
            f"at least {threshold} target slots in {group_id} are forced to x=0 and their x-projections overlap the ghost",
            f"each counted target slot has size {_mapping(target.get('dims')).get('w')}x{_mapping(target.get('dims')).get('h')} and y-domain inside the grid",
            "the maximum number of counted slots that can be placed above or below the fixed ghost is lower than the counted slot count",
        ],
        "cut_form": (
            "If the fixed ghost anchor is active and count(overlapping target slots forced into the same x strip) "
            "> fixed_anchor_vertical_capacity_slots, reject that anchor/candidate hint or add a nogood for that active ghost/slot-forcing combination."
        ),
        "proof_semantics": (
            "NoOverlap2D requires rectangles with overlapping x-projections to be vertically disjoint. "
            "The cut only rejects a combination after deriving an upper bound on vertical packing capacity, so it is a proof-preserving infeasibility certificate when all premises are verified from exact model domains."
        ),
        "runtime_readiness": (
            "ready for a narrow runtime patch task, but not for promotion until unit and integration tests cover domain extraction, x-overlap detection, fixed-anchor segment capacity, and no false positives"
        ),
        "required_tests_before_promotion": [
            "unit test: fixed anchor y=3, ghost h=13, slot h=5 gives threshold 11 rather than pure total-height threshold 12",
            "unit test: no x-overlap disables the cut",
            "unit test: varied y-domain or slot-height cases use a conservative upper-bound capacity",
            "integration test: candidate 67x13 anchor119 is rejected by precheck while known non-overlapping anchors are not",
            "regression test: B5A/final preflight remains blocked until a certified anchor exists; diagnostic rejection is not proof promotion",
        ],
    }


def _status_from_design(
    *,
    prefix_entries: Sequence[Mapping[str, Any]],
    model_error: Optional[str],
) -> Dict[str, Any]:
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "recommendation": "Capacity cut design helper failed; inspect model_error.",
        }
    minimal_k = _minimal_infeasible_k(prefix_entries)
    if minimal_k is None:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "minimal_subset_not_found",
            "recommendation": "No k-prefix subset reproduced INFEASIBLE; more diagnostics needed.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "minimal_aggregate_subset_found",
        "recommendation": (
            f"Use k={minimal_k} fixed-anchor strip-capacity threshold for a narrow exact-safe precheck/Benders cut design task."
        ),
    }


def _checks(
    *,
    status: Mapping[str, Any],
    prefix_entries: Sequence[Mapping[str, Any]],
    thresholds: Mapping[str, Any],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    minimal_k = _minimal_infeasible_k(prefix_entries)
    fixed_threshold = thresholds.get("fixed_anchor_infeasible_threshold_k")
    return [
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
        _check(
            "k_prefix_variants_evaluated",
            "pass" if prefix_entries else "fail",
            f"entry_count={len(prefix_entries)}",
        ),
        _check(
            "minimal_infeasible_k_present",
            "pass" if minimal_k is not None else "fail",
            str(minimal_k),
        ),
        _check(
            "formula_matches_solver_threshold",
            "pass" if minimal_k is not None and int(minimal_k) == int(fixed_threshold or -1) else "warn",
            f"solver={minimal_k}; fixed_anchor_formula={fixed_threshold}; outcome={status.get('outcome')}",
        ),
    ]


def _minimal_infeasible_k(entries: Sequence[Mapping[str, Any]]) -> Optional[int]:
    for entry in entries:
        if str(entry.get("status")) == "INFEASIBLE":
            return int(entry.get("k", 0))
    return None


def _first_infeasible(entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if str(entry.get("status")) == "INFEASIBLE":
            return dict(entry)
    return None


def _status_counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status", "UNKNOWN"))
        counts[status] = int(counts.get(status, 0)) + 1
    return dict(sorted(counts.items()))


def _intervals_overlap(left_start: int, left_size: int, right_start: int, right_size: int) -> bool:
    return int(left_start) < int(right_start) + int(right_size) and int(right_start) < int(left_start) + int(left_size)


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
