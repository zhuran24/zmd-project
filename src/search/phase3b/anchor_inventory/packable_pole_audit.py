from __future__ import annotations

import bisect
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b.anchor_inventory.dynamic_coupling_audit import (
    _family_bounds,
    _parse_pose_tuple,
)
from src.search.phase3b.forced_anchor.master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    _build_exact_overlay,
    _candidate_ghost_rect,
    _check,
    _display_path,
    _file_hash,
    _load_json_mapping,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
)


ANCHOR_PACKABLE_POLE_AUDIT_SOURCE = "phase3b_anchor_packable_pole_audit_v1"
DEFAULT_CANDIDATE = "67x13"


def build_phase3b_anchor_packable_pole_audit(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    anchor_indices: Optional[Sequence[int]] = None,
    sample_limit: int = 2,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    candidate_key = str(candidate)
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    before_hash = _file_hash(campaign_path)
    started = time.perf_counter()
    state, state_error = _load_json_mapping(campaign_path)
    candidates = _mapping(state.get("candidates")) if state else {}
    record = _mapping(candidates.get(candidate_key))
    proof_summary = _mapping(record.get("proof_summary"))
    failure_attribution = _mapping(proof_summary.get("master_start_failure_attribution"))
    failed_anchor_samples = [
        entry
        for entry in list(failure_attribution.get("failed_anchor_samples", []))
        if isinstance(entry, Mapping)
    ]
    selected_anchor_indices = _selected_anchor_indices(
        failed_anchor_samples,
        sample_limit,
        explicit_anchor_indices=anchor_indices,
    )
    ghost_rect = _candidate_ghost_rect(candidate_key, record)
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
    }
    model_error: Optional[str] = None
    anchors: list[Dict[str, Any]] = []
    demand_profile: Dict[str, int] = {}

    if state is None or state_error is not None:
        status.update({"completed": True, "outcome": "campaign_state_missing"})
    elif not record:
        status.update({"completed": True, "outcome": "candidate_missing"})
    elif not selected_anchor_indices:
        status.update({"completed": True, "outcome": "anchor_samples_missing"})
    else:
        try:
            model, _base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=master_search_profile,
            )
            demand_profile = _powered_demands(model)
            for anchor_idx in selected_anchor_indices:
                anchors.append(_anchor_packable_profile(model, int(anchor_idx), demand_profile))
            status.update(_status_from_anchors(anchors))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update({"completed": True, "evaluated": False, "outcome": "diagnostic_error"})

    after_hash = _file_hash(campaign_path)
    campaign_state_unchanged = before_hash == after_hash
    summary = _summary(anchors)
    recommendation = _recommendation(status.get("outcome"))
    return {
        "metadata": {
            "source": ANCHOR_PACKABLE_POLE_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_anchor_packable_pole_not_proof_source",
            "solver_invoked": False,
            "proof_source": False,
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
        },
        "candidate": {
            "key": candidate_key,
            "ghost_rect": ghost_rect,
            "campaign_present": state is not None and state_error is None,
            "campaign_load_error": state_error,
            "candidate_present": bool(record),
            "campaign_status": record.get("status") if record else None,
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "sample_limit": int(sample_limit),
            "selected_anchor_indices": [int(idx) for idx in selected_anchor_indices],
            "tuple_order": "x_y_mode",
            "upper_bound_methods": ["family_cap", "row_interval_relaxation", "column_interval_relaxation"],
            "powered_template_demands": demand_profile,
        },
        "status": {**status, "recommendation": recommendation},
        "anchors": anchors,
        "summary": summary,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "campaign_state_unchanged": bool(campaign_state_unchanged),
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            anchors=anchors,
            status=status,
            campaign_state_unchanged=campaign_state_unchanged,
            model_error=model_error,
        ),
        "recommendation": recommendation,
    }


def render_phase3b_anchor_packable_pole_audit_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    lines = [
        "# Phase 3B Anchor Packable-Pole Audit",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: no_solve_anchor_packable_pole_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Deficit anchors: {summary.get('deficit_anchor_indices')}",
        f"- Recommendation: {report.get('recommendation')}",
        f"- Solver invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        "",
        "## Upper-Bound Certificates",
        "",
        "| Anchor | Combo | Demand | UB | Slack | Deficit | Method | Family UB | Row UB | Column UB |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |",
    ]
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        for cert in list(anchor.get("packable_pole_upper_bounds", [])):
            if not isinstance(cert, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(anchor.get("anchor_idx")),
                        _cell(cert.get("combo_id")),
                        _cell(cert.get("weighted_demand")),
                        _cell(cert.get("upper_bound")),
                        _cell(cert.get("slack")),
                        _cell(cert.get("deficit")),
                        _cell(cert.get("binding_method")),
                        _cell(cert.get("family_cap_upper_bound")),
                        _cell(cert.get("row_interval_upper_bound")),
                        _cell(cert.get("column_interval_upper_bound")),
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
                    [_cell(check.get("check_id")), _cell(check.get("status")), _cell(check.get("detail"))]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_anchor_packable_pole_audit_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    lines = [
        "Phase 3B anchor packable-pole audit",
        "diagnostic_semantics=no_solve_anchor_packable_pole_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"deficit_anchor_indices={summary.get('deficit_anchor_indices')}",
        f"recommendation={report.get('recommendation')}",
    ]
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        lines.append(
            f"anchor idx={anchor.get('anchor_idx')} "
            f"classification={anchor.get('classification')} "
            f"deficits={anchor.get('deficit_count')}"
        )
        for cert in list(anchor.get("packable_pole_upper_bounds", [])):
            if isinstance(cert, Mapping):
                lines.append(
                    "  combo "
                    f"id={cert.get('combo_id')} demand={cert.get('weighted_demand')} "
                    f"ub={cert.get('upper_bound')} slack={cert.get('slack')} "
                    f"deficit={cert.get('deficit')} method={cert.get('binding_method')}"
                )
    return "\n".join(lines) + "\n"


def _anchor_packable_profile(
    model: Any,
    anchor_idx: int,
    demand_profile: Mapping[str, int],
) -> Dict[str, Any]:
    ghost_domains = list(getattr(model, "_ghost_domains", []))
    if int(anchor_idx) < 0 or int(anchor_idx) >= len(ghost_domains):
        return {"anchor_idx": int(anchor_idx), "present": False, "classification": "anchor_missing"}
    delegate = getattr(model, "_coordinate_delegate", None)
    if delegate is None:
        return {
            "anchor_idx": int(anchor_idx),
            "present": False,
            "classification": "coordinate_delegate_missing",
        }
    domain = dict(ghost_domains[int(anchor_idx)])
    blocked_cells = {(int(x), int(y)) for x, y in list(domain.get("cells", []))}
    family_bounds = _family_bounds(delegate, domain)
    poles = _surviving_pole_entries(model, delegate, blocked_cells=blocked_cells)
    combos = _template_combos(demand_profile)
    certificates = [
        _packable_certificate(combo, demand_profile, poles, family_bounds)
        for combo in combos
    ]
    deficit_count = sum(1 for cert in certificates if bool(cert.get("deficit")))
    classification = (
        "packable_pole_no_overlap_capacity_deficit"
        if deficit_count
        else "packable_pole_bound_inconclusive"
    )
    return {
        "anchor_idx": int(anchor_idx),
        "present": True,
        "anchor": dict(_mapping(domain.get("anchor"))),
        "blocked_cell_count": int(len(blocked_cells)),
        "surviving_pole_pose_count": int(len(poles)),
        "surviving_family_count": int(len({str(pole["family_name"]) for pole in poles})),
        "classification": classification,
        "deficit_count": int(deficit_count),
        "packable_pole_upper_bounds": certificates,
    }


def _surviving_pole_entries(
    model: Any,
    delegate: Any,
    *,
    blocked_cells: set[tuple[int, int]],
) -> list[Dict[str, Any]]:
    pose_tuples = dict(getattr(delegate, "_template_pose_tuple_by_idx", {}).get("power_pole", {}))
    family_id_by_pose = dict(getattr(delegate, "_power_pole_family_id_by_pose_idx", {}))
    family_name_by_int = dict(getattr(delegate, "_power_pole_family_name_by_int", {}))
    entries: list[Dict[str, Any]] = []
    for pose_idx, pose_tuple in sorted(pose_tuples.items()):
        cells = {(int(x), int(y)) for x, y in model._pose_cells("power_pole", int(pose_idx))}
        if cells and not blocked_cells.isdisjoint(cells):
            continue
        parsed = _parse_pose_tuple(pose_tuple)
        if parsed is None:
            continue
        family_id = family_id_by_pose.get(int(pose_idx))
        family_name = family_name_by_int.get(int(family_id)) if family_id is not None else None
        if family_name is None:
            continue
        bbox = _bbox(cells, fallback_xy=(parsed[0], parsed[1]))
        entries.append(
            {
                "pose_idx": int(pose_idx),
                "x": int(parsed[0]),
                "y": int(parsed[1]),
                "mode": int(parsed[2]),
                "family_id": int(family_id),
                "family_name": str(family_name),
                "cells": sorted(cells),
                "bbox": bbox,
            }
        )
    return entries


def _packable_certificate(
    combo: Mapping[str, int],
    demand_profile: Mapping[str, int],
    poles: Sequence[Mapping[str, Any]],
    family_bounds: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    weighted_demand = sum(
        int(weight) * int(demand_profile.get(str(template), 0) or 0)
        for template, weight in combo.items()
    )
    weighted_poles = [
        {**dict(pole), "weight": int(_pole_weight(pole, combo, family_bounds))}
        for pole in poles
    ]
    weighted_poles = [pole for pole in weighted_poles if int(pole.get("weight", 0)) > 0]
    family_ub = _family_cap_upper_bound(weighted_poles, family_bounds)
    row_ub = _axis_interval_upper_bound(weighted_poles, group_axis="y", interval_axis="x")
    column_ub = _axis_interval_upper_bound(weighted_poles, group_axis="x", interval_axis="y")
    bounds = {
        "family_cap": int(family_ub),
        "row_interval_relaxation": int(row_ub),
        "column_interval_relaxation": int(column_ub),
    }
    binding_method, upper_bound = min(bounds.items(), key=lambda item: (int(item[1]), item[0]))
    return {
        "certificate_type": "packable_pole_no_overlap_capacity_deficit",
        "combo_id": "+".join(f"{template}x{weight}" for template, weight in sorted(combo.items())),
        "template_weights": {str(k): int(v) for k, v in sorted(combo.items())},
        "weighted_demand": int(weighted_demand),
        "surviving_weighted_pole_count": int(len(weighted_poles)),
        "family_cap_upper_bound": int(family_ub),
        "row_interval_upper_bound": int(row_ub),
        "column_interval_upper_bound": int(column_ub),
        "upper_bound": int(upper_bound),
        "binding_method": str(binding_method),
        "slack": int(upper_bound) - int(weighted_demand),
        "deficit": int(upper_bound) < int(weighted_demand),
        "relaxations": [
            "family_cap ignores pole no-overlap",
            "row_interval_relaxation sums independent top-y row optima",
            "column_interval_relaxation sums independent top-x column optima",
            "ignores non-pole placement conflicts",
            "does not solve CP-SAT",
        ],
    }


def _pole_weight(
    pole: Mapping[str, Any],
    combo: Mapping[str, int],
    family_bounds: Mapping[str, Mapping[str, Any]],
) -> int:
    family_name = str(pole.get("family_name"))
    coefficients = _mapping(_mapping(family_bounds.get(family_name)).get("coefficients"))
    return sum(int(weight) * int(coefficients.get(str(template), 0) or 0) for template, weight in combo.items())


def _family_cap_upper_bound(
    weighted_poles: Sequence[Mapping[str, Any]],
    family_bounds: Mapping[str, Mapping[str, Any]],
) -> int:
    family_weights: Dict[str, int] = {}
    family_counts: Dict[str, int] = defaultdict(int)
    for pole in weighted_poles:
        family_name = str(pole.get("family_name"))
        family_counts[family_name] += 1
        family_weights[family_name] = max(family_weights.get(family_name, 0), int(pole.get("weight", 0)))
    total = 0
    for family_name, count in family_counts.items():
        effective_upper = int(_mapping(family_bounds.get(str(family_name))).get("effective_upper", count) or 0)
        total += min(int(count), max(0, effective_upper)) * int(family_weights.get(family_name, 0))
    return int(total)


def _axis_interval_upper_bound(
    weighted_poles: Sequence[Mapping[str, Any]],
    *,
    group_axis: str,
    interval_axis: str,
) -> int:
    grouped: Dict[int, list[tuple[int, int, int]]] = defaultdict(list)
    group_min_key = f"{group_axis}_min"
    start_key = f"{interval_axis}_min"
    end_key = f"{interval_axis}_max"
    for pole in weighted_poles:
        bbox = _mapping(pole.get("bbox"))
        grouped[int(bbox.get(group_min_key, 0))].append(
            (
                int(bbox.get(start_key, 0)),
                int(bbox.get(end_key, 0)),
                int(pole.get("weight", 0)),
            )
        )
    return int(sum(_weighted_interval_upper_bound(intervals) for intervals in grouped.values()))


def _weighted_interval_upper_bound(intervals: Sequence[tuple[int, int, int]]) -> int:
    ordered = sorted((int(start), int(end), int(weight)) for start, end, weight in intervals)
    if not ordered:
        return 0
    ends = [end for _start, end, _weight in ordered]
    dp = [0] * (len(ordered) + 1)
    for i, (start, _end, weight) in enumerate(ordered, start=1):
        prev = bisect.bisect_left(ends, int(start))  # previous interval must end < start.
        dp[i] = max(dp[i - 1], dp[prev] + int(weight))
    return int(dp[-1])


def _bbox(cells: Iterable[tuple[int, int]], *, fallback_xy: tuple[int, int]) -> Dict[str, int]:
    cells = {(int(x), int(y)) for x, y in cells}
    if not cells:
        x_val, y_val = int(fallback_xy[0]), int(fallback_xy[1])
        return {"x_min": x_val, "x_max": x_val, "y_min": y_val, "y_max": y_val}
    xs = [int(x) for x, _y in cells]
    ys = [int(y) for _x, y in cells]
    return {"x_min": min(xs), "x_max": max(xs), "y_min": min(ys), "y_max": max(ys)}


def _template_combos(demand_profile: Mapping[str, int]) -> list[Dict[str, int]]:
    templates = [str(template) for template, demand in sorted(demand_profile.items()) if int(demand) > 0]
    combos = [{template: 1} for template in templates]
    if len(templates) > 1:
        combos.append({template: 1 for template in templates})
    return combos


def _powered_demands(model: Any) -> Dict[str, int]:
    gvi = _mapping(getattr(model, "build_stats", {}).get("global_valid_inequalities"))
    return {
        str(template): int(demand)
        for template, demand in sorted(_mapping(gvi.get("powered_template_demands")).items())
    }


def _status_from_anchors(anchors: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not anchors:
        return {"completed": True, "evaluated": False, "outcome": "anchor_samples_missing"}
    present = [anchor for anchor in anchors if bool(anchor.get("present", False))]
    if not present:
        return {"completed": True, "evaluated": False, "outcome": "anchors_missing"}
    deficit_anchors = [
        int(anchor.get("anchor_idx", -1))
        for anchor in present
        if int(anchor.get("deficit_count", 0) or 0) > 0
    ]
    if deficit_anchors == [118]:
        outcome = "anchor118_packable_bound_control_pass"
    elif deficit_anchors:
        outcome = "packable_deficit_present_control_failed"
    else:
        outcome = "packable_pole_bound_inconclusive"
    return {
        "completed": True,
        "evaluated": True,
        "outcome": outcome,
        "classification_counts": dict(Counter(str(anchor.get("classification")) for anchor in anchors)),
    }


def _summary(anchors: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    deficit_indices = [
        int(anchor.get("anchor_idx", -1))
        for anchor in anchors
        if int(anchor.get("deficit_count", 0) or 0) > 0
    ]
    return {
        "anchor_count": int(len(anchors)),
        "deficit_anchor_indices": deficit_indices,
        "deficit_anchor_count": int(len(deficit_indices)),
        "classification_counts": dict(Counter(str(anchor.get("classification")) for anchor in anchors)),
    }


def _recommendation(outcome: Any) -> str:
    if outcome == "anchor118_packable_bound_control_pass":
        return (
            "Anchor118 has a no-solve packable-pole upper-bound deficit while the "
            "control does not; inspect certificate details before considering any default-off gate."
        )
    if outcome == "packable_deficit_present_control_failed":
        return (
            "A packable-pole deficit appeared, but it did not isolate anchor118 cleanly; "
            "do not promote this as a precheck."
        )
    if outcome == "packable_pole_bound_inconclusive":
        return (
            "No packable-pole upper-bound deficit was found. The remaining blocker is "
            "likely deeper in exact selector/table propagation rather than a simple no-solve capacity cut."
        )
    if outcome == "campaign_state_missing":
        return "Campaign state is missing or invalid; provide a workspace campaign state."
    if outcome == "candidate_missing":
        return "Candidate is missing from campaign state; choose a recorded blocker candidate."
    return "Inspect model_error and checks before using this diagnostic artifact."


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    selected_anchor_count: int,
    anchors: Sequence[Mapping[str, Any]],
    status: Mapping[str, Any],
    campaign_state_unchanged: bool,
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        _check(
            "campaign_state_present",
            "pass" if state_present else "fail",
            "campaign state loaded" if state_present else "campaign state missing or invalid",
        ),
        _check(
            "candidate_present",
            "pass" if candidate_present else "fail",
            "candidate loaded" if candidate_present else "candidate missing",
        ),
        _check(
            "anchor_samples_present",
            "pass" if selected_anchor_count > 0 else "fail",
            f"selected anchors={selected_anchor_count}",
        ),
        _check(
            "audit_evaluated",
            "pass" if bool(status.get("evaluated")) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "campaign_state_unchanged",
            "pass" if campaign_state_unchanged else "fail",
            "campaign state unchanged" if campaign_state_unchanged else "campaign state hash changed",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
        _check(
            "anchors_present",
            "pass" if any(bool(anchor.get("present", False)) for anchor in anchors) else "skipped",
            f"anchors={len(anchors)}",
        ),
    ]


def _cell(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
