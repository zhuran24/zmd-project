from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ortools.sat.python import cp_model

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b.coordinate_validation.direct_equality_core import (
    DEFAULT_DIRECT_EQUALITY_CORE_GROUP_ID,
)
from src.search.phase3b.coordinate_validation.group_delta import (
    _build_delta_context,
    _candidate_rect,
    _check,
    _mapping,
)
from src.search.phase3b.coordinate_validation.x_domain_order_audit import (
    _load_t24_core_labels,
)

COORDINATE_VALIDATION_TARGET_GHOST_CAPACITY_REPRO_SOURCE = (
    "phase3b_coordinate_validation_target_ghost_capacity_repro_v1"
)

DEFAULT_TARGET_GHOST_CAPACITY_GROUP_ID = DEFAULT_DIRECT_EQUALITY_CORE_GROUP_ID

DEFAULT_TARGET_GHOST_CAPACITY_VARIANTS = (
    "target_group_only_no_overlap",
    "target_group_plus_anchor119_ghost_fixed",
    "target_group_plus_all_ghost_candidates_optional",
    "target_group_plus_anchor119_ghost_without_exactly_one",
    "target_slots_12_core_only_plus_anchor119_ghost",
    "target_slots_12_core_only_without_ghost",
    "target_slots_split_first_half_plus_anchor119_ghost",
    "target_slots_split_second_half_plus_anchor119_ghost",
)


def build_phase3b_coordinate_validation_target_ghost_capacity_repro(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 119,
    group_id: str = DEFAULT_TARGET_GHOST_CAPACITY_GROUP_ID,
    core_json: Optional[Path] = None,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 2.0,
    worker_count: int = 1,
    variants: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    normalized_group_id = str(group_id).strip()
    normalized_variants = _normalize_variants(variants or DEFAULT_TARGET_GHOST_CAPACITY_VARIANTS)
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
    geometry: Dict[str, Any] = {}
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
        for variant in normalized_variants:
            entries.append(
                _evaluate_capacity_variant(
                    model=model,
                    delegate=delegate,
                    group=group,
                    group_id=normalized_group_id,
                    labels=core_labels,
                    anchor_idx=int(anchor_idx),
                    variant=str(variant),
                    time_limit_seconds=float(time_limit_seconds),
                    worker_count=int(worker_count),
                )
            )
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    status = _status_from_entries(entries, model_error=model_error)
    return {
        "metadata": {
            "source": COORDINATE_VALIDATION_TARGET_GHOST_CAPACITY_REPRO_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "coordinate_validation_target_ghost_capacity_repro_not_proof_source"
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
        "status": status,
        "repro": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "first_infeasible_variant": _first_variant_with_status(entries, "INFEASIBLE"),
            "first_feasible_variant": _first_feasible_variant(entries),
            "first_unknown_variant": _first_variant_with_status(entries, "UNKNOWN"),
        },
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(status=status, entries=entries, model_error=model_error),
    }


def render_phase3b_coordinate_validation_target_ghost_capacity_repro_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    repro = _mapping(report.get("repro"))
    geometry = _mapping(report.get("geometry"))
    lines = [
        "# Phase 3B Target Group + Ghost NoOverlap Capacity Repro",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        "- Diagnostic semantics: coordinate_validation_target_ghost_capacity_repro_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Target slots: {_mapping(geometry.get('target_group')).get('slot_count')}",
        f"- Core label count: {_mapping(geometry.get('core_labels')).get('label_count')}",
        f"- Anchor geometry: {geometry.get('anchor119_ghost')}",
        "",
        "## Variant Matrix",
        "",
        "| Variant | Status | Target Slots | Ghosts | X Equalities | ExactlyOne | Anchor Fixed | Capacity Conflict |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for entry in list(repro.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        cap = _mapping(entry.get("capacity_summary"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("variant")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("target_slot_count")),
                    _markdown_cell(entry.get("ghost_interval_count")),
                    _markdown_cell(entry.get("enforced_x_equality_count")),
                    _markdown_cell(entry.get("exactly_one_present")),
                    _markdown_cell(entry.get("anchor119_fixed_or_forced")),
                    _markdown_cell(cap.get("capacity_conflict_possible")),
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


def render_phase3b_coordinate_validation_target_ghost_capacity_repro_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    repro = _mapping(report.get("repro"))
    lines = [
        "Phase 3B target group plus ghost capacity repro",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"status_counts={repro.get('status_counts')}",
    ]
    for entry in list(repro.get("entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "entry "
                f"variant={entry.get('variant')} "
                f"status={entry.get('status')} "
                f"target_slots={entry.get('target_slot_count')} "
                f"ghosts={entry.get('ghost_interval_count')} "
                f"x_equalities={entry.get('enforced_x_equality_count')}"
            )
    return "\n".join(lines) + "\n"


def _evaluate_capacity_variant(
    *,
    model: Any,
    delegate: Any,
    group: Mapping[str, Any],
    group_id: str,
    labels: Sequence[Mapping[str, Any]],
    anchor_idx: int,
    variant: str,
    time_limit_seconds: float,
    worker_count: int,
) -> Dict[str, Any]:
    spec = _variant_spec(variant, labels=labels)
    if spec.get("skipped"):
        return {
            "variant": str(variant),
            "evaluated": False,
            "status": "SKIPPED",
            "skip_reason": spec.get("skip_reason"),
            "diagnostic_semantics": "not_proof_source",
        }
    cp = cp_model.CpModel()
    source_proto = model.model.Proto()
    slot_specs = list(getattr(delegate, "mandatory_slots", {}).get(group_id, []))
    raw_slot_indices = spec["slot_indices"]
    if raw_slot_indices == "all":
        selected_slots = list(range(len(slot_specs)))
    else:
        selected_slots = [int(idx) for idx in raw_slot_indices if 0 <= int(idx) < len(slot_specs)]
    labels_by_slot = {
        int(label.get("slot_index", -1)): dict(label)
        for label in labels
        if str(label.get("field")) == "x"
    }
    slot_vars: Dict[int, Dict[str, Any]] = {}
    x_intervals = []
    y_intervals = []
    enforced_equalities = 0
    allowed_assignment_rows = 0
    for slot_index in selected_slots:
        slot = slot_specs[slot_index]
        x_domain = _var_domain(source_proto, getattr(slot, "x", None)) or [0, 0]
        y_domain = _var_domain(source_proto, getattr(slot, "y", None)) or [0, 0]
        mode_domain = _var_domain(source_proto, getattr(slot, "mode", None)) or [0, 0]
        x = _new_int_var_from_flat_domain(cp, x_domain, f"x_slot_{slot_index}")
        y = _new_int_var_from_flat_domain(cp, y_domain, f"y_slot_{slot_index}")
        mode = _new_int_var_from_flat_domain(cp, mode_domain, f"mode_slot_{slot_index}")
        if bool(getattr(slot, "use_domain_table", False)) and getattr(slot, "allowed_tuples", None):
            rows = [[int(a), int(b), int(c)] for a, b, c in slot.allowed_tuples]
            cp.AddAllowedAssignments([x, y, mode], rows)
            allowed_assignment_rows += len(rows)
        if slot_index in labels_by_slot:
            cp.Add(x == int(labels_by_slot[slot_index].get("forced_value", 0)))
            enforced_equalities += 1
        width, height = [int(v) for v in getattr(slot, "dims", (1, 1))]
        x_end = cp.NewIntVar(0, int(delegate.grid_w) + width, f"x_end_slot_{slot_index}")
        y_end = cp.NewIntVar(0, int(delegate.grid_h) + height, f"y_end_slot_{slot_index}")
        cp.Add(x_end == x + width)
        cp.Add(y_end == y + height)
        x_iv = cp.NewIntervalVar(x, width, x_end, f"x_iv_slot_{slot_index}")
        y_iv = cp.NewIntervalVar(y, height, y_end, f"y_iv_slot_{slot_index}")
        x_intervals.append(x_iv)
        y_intervals.append(y_iv)
        slot_vars[slot_index] = {"x": x, "y": y, "mode": mode}
    _add_slot_order_constraints(cp, delegate=delegate, slot_specs=slot_specs, selected_slots=selected_slots, slot_vars=slot_vars)
    ghost_payload = _add_ghosts_for_variant(
        cp,
        delegate=delegate,
        model=model,
        variant_spec=spec,
        anchor_idx=int(anchor_idx),
        x_intervals=x_intervals,
        y_intervals=y_intervals,
    )
    if x_intervals:
        cp.AddNoOverlap2D(x_intervals, y_intervals)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.001, float(time_limit_seconds))
    solver.parameters.num_search_workers = max(1, int(worker_count))
    status = solver.Solve(cp)
    capacity_summary = _capacity_summary(
        delegate=delegate,
        model=model,
        group_id=group_id,
        labels=labels,
        selected_slots=selected_slots,
        anchor_indices=ghost_payload.get("active_or_possible_anchor_indices", []),
    )
    return {
        "variant": str(variant),
        "evaluated": True,
        "status": solver.StatusName(status),
        "accepted": status in {cp_model.OPTIMAL, cp_model.FEASIBLE},
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "wall_time": float(solver.WallTime()),
        "user_time": float(solver.UserTime()),
        "deterministic_time": _deterministic_time_from_stats(solver.ResponseStats()),
        "target_slot_count": int(len(selected_slots)),
        "selected_slot_indices": [int(idx) for idx in selected_slots],
        "ghost_interval_count": int(ghost_payload.get("ghost_interval_count", 0)),
        "ghost_mode": ghost_payload.get("ghost_mode"),
        "active_or_possible_anchor_indices": list(ghost_payload.get("active_or_possible_anchor_indices", [])),
        "enforced_x_equality_count": int(enforced_equalities),
        "full_12_key_x_subset_enforced": int(enforced_equalities) == int(len(labels)),
        "allowed_assignment_row_count": int(allowed_assignment_rows),
        "exactly_one_present": bool(ghost_payload.get("exactly_one_present", False)),
        "anchor119_fixed_or_forced": bool(ghost_payload.get("anchor119_fixed_or_forced", False)),
        "constraint_count": int(len(cp.Proto().constraints)),
        "variable_count": int(len(cp.Proto().variables)),
        "capacity_summary": capacity_summary,
        "interval_geometry_summary": {
            "target_slot_dims": _target_slot_dims(delegate, group_id),
            "grid": {"w": int(delegate.grid_w), "h": int(delegate.grid_h)},
            "ghost_rect": list(_ghost_rect_tuple(model)),
        },
        "diagnostic_semantics": "standalone_capacity_repro_not_proof_source",
    }


def _variant_spec(variant: str, *, labels: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    core_slots = sorted({int(label.get("slot_index", -1)) for label in labels if int(label.get("slot_index", -1)) >= 0})
    first_half = core_slots[: len(core_slots) // 2]
    second_half = core_slots[len(core_slots) // 2 :]
    if variant == "target_group_only_no_overlap":
        return {"slot_mode": "all_target", "slot_indices": "all", "ghost_mode": "none"}
    if variant == "target_group_plus_anchor119_ghost_fixed":
        return {"slot_mode": "all_target", "slot_indices": "all", "ghost_mode": "anchor_fixed"}
    if variant == "target_group_plus_all_ghost_candidates_optional":
        return {"slot_mode": "all_target", "slot_indices": "all", "ghost_mode": "all_optional_exactly_one"}
    if variant == "target_group_plus_anchor119_ghost_without_exactly_one":
        return {"slot_mode": "all_target", "slot_indices": "all", "ghost_mode": "anchor_optional_forced_no_exactly_one"}
    if variant == "target_slots_12_core_only_plus_anchor119_ghost":
        return {"slot_mode": "core_12", "slot_indices": core_slots, "ghost_mode": "anchor_fixed"}
    if variant == "target_slots_12_core_only_without_ghost":
        return {"slot_mode": "core_12", "slot_indices": core_slots, "ghost_mode": "none"}
    if variant == "target_slots_split_first_half_plus_anchor119_ghost":
        return {"slot_mode": "core_first_half", "slot_indices": first_half, "ghost_mode": "anchor_fixed"}
    if variant == "target_slots_split_second_half_plus_anchor119_ghost":
        return {"slot_mode": "core_second_half", "slot_indices": second_half, "ghost_mode": "anchor_fixed"}
    return {"skipped": True, "skip_reason": f"unsupported variant: {variant}"}


def _add_ghosts_for_variant(
    cp: cp_model.CpModel,
    *,
    delegate: Any,
    model: Any,
    variant_spec: Mapping[str, Any],
    anchor_idx: int,
    x_intervals: list[Any],
    y_intervals: list[Any],
) -> Dict[str, Any]:
    ghost_mode = str(variant_spec.get("ghost_mode", "none"))
    if ghost_mode == "none":
        return {
            "ghost_mode": ghost_mode,
            "ghost_interval_count": 0,
            "active_or_possible_anchor_indices": [],
            "exactly_one_present": False,
            "anchor119_fixed_or_forced": False,
        }
    ghost_rect = _ghost_rect_tuple(model)
    if len(ghost_rect) != 2:
        return {
            "ghost_mode": ghost_mode,
            "ghost_interval_count": 0,
            "active_or_possible_anchor_indices": [],
            "exactly_one_present": False,
            "anchor119_fixed_or_forced": False,
            "skip_reason": "ghost_rect_unavailable",
        }
    ghost_w, ghost_h = ghost_rect
    ghost_domains = list(getattr(model, "_ghost_domains", []))
    if ghost_mode in {"anchor_fixed", "anchor_optional_forced_no_exactly_one"}:
        domain = ghost_domains[int(anchor_idx)]
        anchor = dict(domain.get("anchor", {}))
        x0, y0 = int(anchor.get("x", 0)), int(anchor.get("y", 0))
        if ghost_mode == "anchor_fixed":
            x_intervals.append(cp.NewIntervalVar(x0, ghost_w, x0 + ghost_w, "ghost_x_iv_anchor119_fixed"))
            y_intervals.append(cp.NewIntervalVar(y0, ghost_h, y0 + ghost_h, "ghost_y_iv_anchor119_fixed"))
        else:
            active = cp.NewBoolVar("ghost_anchor119_active")
            cp.Add(active == 1)
            x_intervals.append(cp.NewOptionalIntervalVar(x0, ghost_w, x0 + ghost_w, active, "ghost_x_iv_anchor119_optional_forced"))
            y_intervals.append(cp.NewOptionalIntervalVar(y0, ghost_h, y0 + ghost_h, active, "ghost_y_iv_anchor119_optional_forced"))
        return {
            "ghost_mode": ghost_mode,
            "ghost_interval_count": 1,
            "active_or_possible_anchor_indices": [int(anchor_idx)],
            "exactly_one_present": False,
            "anchor119_fixed_or_forced": True,
        }
    if ghost_mode == "all_optional_exactly_one":
        actives = []
        for idx, domain in enumerate(ghost_domains):
            anchor = dict(domain.get("anchor", {}))
            x0, y0 = int(anchor.get("x", 0)), int(anchor.get("y", 0))
            active = cp.NewBoolVar(f"ghost_active_{idx}")
            actives.append(active)
            x_intervals.append(cp.NewOptionalIntervalVar(x0, ghost_w, x0 + ghost_w, active, f"ghost_x_iv_{idx}"))
            y_intervals.append(cp.NewOptionalIntervalVar(y0, ghost_h, y0 + ghost_h, active, f"ghost_y_iv_{idx}"))
        if actives:
            cp.AddExactlyOne(actives)
        return {
            "ghost_mode": ghost_mode,
            "ghost_interval_count": len(actives),
            "active_or_possible_anchor_indices": [int(idx) for idx in range(len(actives))],
            "exactly_one_present": bool(actives),
            "anchor119_fixed_or_forced": False,
        }
    return {
        "ghost_mode": ghost_mode,
        "ghost_interval_count": 0,
        "active_or_possible_anchor_indices": [],
        "exactly_one_present": False,
        "anchor119_fixed_or_forced": False,
        "skip_reason": f"unsupported ghost mode: {ghost_mode}",
    }


def _add_slot_order_constraints(
    cp: cp_model.CpModel,
    *,
    delegate: Any,
    slot_specs: Sequence[Any],
    selected_slots: Sequence[int],
    slot_vars: Mapping[int, Mapping[str, Any]],
) -> None:
    selected = [int(idx) for idx in selected_slots if int(idx) in slot_vars]
    for left, right in zip(selected, selected[1:]):
        left_slot = slot_specs[left]
        scale_x, scale_y = delegate._slot_order_key_bounds(left_slot)
        cp.Add(
            slot_vars[left]["x"] * int(scale_x)
            + slot_vars[left]["y"] * int(scale_y)
            + slot_vars[left]["mode"]
            <= slot_vars[right]["x"] * int(scale_x)
            + slot_vars[right]["y"] * int(scale_y)
            + slot_vars[right]["mode"]
        )


def _geometry_payload(
    *,
    model: Any,
    delegate: Any,
    group: Mapping[str, Any],
    group_id: str,
    labels: Sequence[Mapping[str, Any]],
    anchor_idx: int,
) -> Dict[str, Any]:
    slot_specs = list(getattr(delegate, "mandatory_slots", {}).get(group_id, []))
    core_slots = sorted({int(label.get("slot_index", -1)) for label in labels if int(label.get("slot_index", -1)) >= 0})
    return {
        "target_group": {
            "group_id": str(group_id),
            "template": str(group.get("facility_type", "")),
            "slot_count": len(slot_specs),
            "dims": _target_slot_dims(delegate, group_id),
        },
        "core_labels": {
            "label_count": len(labels),
            "slot_indices": core_slots,
            "forced_x_values": sorted({int(label.get("forced_value", 0)) for label in labels if str(label.get("field")) == "x"}),
        },
        "anchor119_ghost": _ghost_geometry(model=model, anchor_idx=int(anchor_idx)),
        "pose_overlap_samples": _pose_overlap_samples(delegate=delegate, group_id=group_id, labels=labels, model=model, anchor_idx=int(anchor_idx)),
    }


def _capacity_summary(
    *,
    delegate: Any,
    model: Any,
    group_id: str,
    labels: Sequence[Mapping[str, Any]],
    selected_slots: Sequence[int],
    anchor_indices: Sequence[int],
) -> Dict[str, Any]:
    dims = _target_slot_dims(delegate, group_id)
    slot_h = int(dims.get("h", 0))
    forced_slots = sorted({int(label.get("slot_index", -1)) for label in labels if int(label.get("slot_index", -1)) in set(selected_slots)})
    ghost_rect = _ghost_rect_tuple(model)
    ghost_h = int(ghost_rect[1]) if len(ghost_rect) == 2 and anchor_indices else 0
    required_height = int(len(forced_slots) * slot_h + (ghost_h if anchor_indices else 0))
    grid_h = int(getattr(delegate, "grid_h", 0))
    return {
        "forced_x0_slot_count": len(forced_slots),
        "slot_height": slot_h,
        "ghost_height_counted": ghost_h,
        "required_vertical_height_if_same_x_strip": required_height,
        "grid_height": grid_h,
        "capacity_conflict_possible": bool(anchor_indices and required_height > grid_h),
        "note": "This is a sufficient-looking strip-capacity check, not a proof.",
    }


def _pose_overlap_samples(
    *,
    delegate: Any,
    group_id: str,
    labels: Sequence[Mapping[str, Any]],
    model: Any,
    anchor_idx: int,
) -> list[Dict[str, Any]]:
    slot_specs = list(getattr(delegate, "mandatory_slots", {}).get(group_id, []))
    if not slot_specs:
        return []
    tpl = str(getattr(slot_specs[0], "template", ""))
    dims = _target_slot_dims(delegate, group_id)
    ghost = _ghost_geometry(model=model, anchor_idx=anchor_idx)
    result = []
    for label in labels:
        pose_idx = int(label.get("pose_index", -1))
        pose_tuple = getattr(delegate, "_template_pose_tuple_by_idx", {}).get(tpl, {}).get(pose_idx)
        if pose_tuple is None:
            continue
        rect = {
            "x": int(pose_tuple[0]),
            "y": int(pose_tuple[1]),
            "w": int(dims.get("w", 0)),
            "h": int(dims.get("h", 0)),
        }
        if _rects_overlap(rect, ghost):
            result.append(
                {
                    "slot_index": int(label.get("slot_index", -1)),
                    "solution_id": str(label.get("solution_id", "")),
                    "pose_index": pose_idx,
                    "pose_rect": rect,
                    "ghost_rect": ghost,
                }
            )
        if len(result) >= 8:
            break
    return result


def _ghost_geometry(*, model: Any, anchor_idx: int) -> Dict[str, int]:
    ghost_rect = _ghost_rect_tuple(model)
    domains = list(getattr(model, "_ghost_domains", []))
    domain = domains[int(anchor_idx)] if 0 <= int(anchor_idx) < len(domains) else {}
    anchor = dict(domain.get("anchor", {})) if isinstance(domain, Mapping) else {}
    return {
        "anchor_idx": int(anchor_idx),
        "x": int(anchor.get("x", 0)),
        "y": int(anchor.get("y", 0)),
        "w": int(ghost_rect[0]) if len(ghost_rect) == 2 else 0,
        "h": int(ghost_rect[1]) if len(ghost_rect) == 2 else 0,
    }


def _ghost_rect_tuple(model: Any) -> Tuple[int, ...]:
    raw = getattr(model, "ghost_rect", ()) or ()
    if isinstance(raw, Mapping):
        if "w" in raw and "h" in raw:
            return (int(raw["w"]), int(raw["h"]))
        if "width" in raw and "height" in raw:
            return (int(raw["width"]), int(raw["height"]))
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        values = list(raw)
        if len(values) >= 2:
            return (int(values[0]), int(values[1]))
    return ()


def _target_slot_dims(delegate: Any, group_id: str) -> Dict[str, int]:
    slots = list(getattr(delegate, "mandatory_slots", {}).get(group_id, []))
    if not slots:
        return {"w": 0, "h": 0}
    dims = tuple(getattr(slots[0], "dims", (0, 0)))
    return {"w": int(dims[0]), "h": int(dims[1])}


def _rects_overlap(a: Mapping[str, int], b: Mapping[str, int]) -> bool:
    return (
        int(a.get("x", 0)) < int(b.get("x", 0)) + int(b.get("w", 0))
        and int(b.get("x", 0)) < int(a.get("x", 0)) + int(a.get("w", 0))
        and int(a.get("y", 0)) < int(b.get("y", 0)) + int(b.get("h", 0))
        and int(b.get("y", 0)) < int(a.get("y", 0)) + int(a.get("h", 0))
    )


def _var_domain(proto: Any, var: Any) -> Optional[list[int]]:
    if var is None:
        return None
    try:
        idx = int(var.Index())
    except Exception:
        return None
    if 0 <= idx < len(proto.variables):
        return [int(value) for value in list(proto.variables[idx].domain)]
    return None


def _new_int_var_from_flat_domain(
    model: cp_model.CpModel,
    flat_domain: Sequence[int],
    name: str,
) -> cp_model.IntVar:
    domain_values = [int(value) for value in flat_domain]
    if len(domain_values) == 2:
        return model.NewIntVar(domain_values[0], domain_values[1], name)
    return model.NewIntVarFromDomain(cp_model.Domain.FromFlatIntervals(domain_values), name)


def _deterministic_time_from_stats(response_stats: str) -> float:
    for line in str(response_stats).splitlines():
        if "deterministic_time:" not in line:
            continue
        try:
            return float(line.split("deterministic_time:", 1)[1].strip().split()[0])
        except Exception:
            return 0.0
    return 0.0


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
            "recommendation": "Target+ghost capacity repro failed; inspect model_error.",
        }
    if not entries:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "no_entries",
            "recommendation": "No target+ghost capacity repro variants were evaluated.",
        }
    infeasible = [entry for entry in entries if str(entry.get("status")) == "INFEASIBLE"]
    feasible = [entry for entry in entries if str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"}]
    if infeasible and feasible:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "standalone_capacity_split",
            "recommendation": "Standalone repro found both infeasible and feasible variants; inspect split variants for the smaller capacity conflict.",
        }
    if infeasible:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "standalone_capacity_infeasible_variants_found",
            "recommendation": "At least one standalone target+ghost capacity variant is INFEASIBLE.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "standalone_capacity_no_infeasible_variant",
        "recommendation": "No standalone variant reproduced INFEASIBLE; return to full-model proto subset context.",
    }


def _checks(
    *,
    status: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        _check(
            "variants_evaluated",
            "pass" if any(bool(entry.get("evaluated", False)) for entry in entries) else "fail",
            f"entry_count={len(entries)}",
        ),
        _check(
            "infeasible_variant_present",
            "pass" if any(str(entry.get("status")) == "INFEASIBLE" for entry in entries) else "warn",
            str(status.get("outcome")),
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _first_variant_with_status(
    entries: Sequence[Mapping[str, Any]],
    status: str,
) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if str(entry.get("status")) == str(status):
            return dict(entry)
    return None


def _first_feasible_variant(entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"}:
            return dict(entry)
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
    return tuple(result or DEFAULT_TARGET_GHOST_CAPACITY_VARIANTS)


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
