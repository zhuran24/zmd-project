from __future__ import annotations

import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
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

COVER_LITERAL_SCALE_ESTIMATE_SOURCE = "phase3b_cover_literal_scale_estimate_v1"
DEFAULT_CANDIDATE = "67x13"


def build_phase3b_cover_literal_scale_estimate(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 1,
    anchor_indices: Optional[Sequence[int]] = None,
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
    anchors: list[Dict[str, Any]] = []
    model_power_coverage: Dict[str, Any] = {}
    model_error: Optional[str] = None
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Cover literal scale estimate has not run.",
    }

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before estimating forced-anchor replacement scale.",
            }
        )
    elif not record:
        status.update(
            {
                "completed": True,
                "outcome": "candidate_missing",
                "recommendation": "Candidate is not present in campaign state; choose a recorded blocker candidate.",
            }
        )
    elif not selected_anchor_indices:
        status.update(
            {
                "completed": True,
                "outcome": "forced_anchor_samples_missing",
                "recommendation": "No forced anchors selected; rerun B5A with failed-anchor sampling enabled or pass --anchor-indices.",
            }
        )
    else:
        try:
            model, _base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=str(master_search_profile),
            )
            model_power_coverage = dict(_mapping(_mapping(getattr(model, "build_stats", {})).get("power_coverage")))
            for anchor_idx in selected_anchor_indices:
                anchors.append(_anchor_scale_estimate(model, int(anchor_idx)))
            status.update(_status_from_anchors(anchors))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Cover literal scale estimate failed; inspect model_error before using this evidence.",
                }
            )

    after_hash = _file_hash(campaign_path)
    summary = _summary(anchors)
    return {
        "metadata": {
            "source": COVER_LITERAL_SCALE_ESTIMATE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "static_scale_estimate_not_proof_source",
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
        },
        "current_power_coverage": model_power_coverage,
        "status": status,
        "summary": summary,
        "anchors": anchors,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "campaign_state_unchanged": bool(before_hash == after_hash),
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            anchors=anchors,
            status=status,
            model_error=model_error,
            campaign_state_unchanged=before_hash == after_hash,
        ),
    }


def render_phase3b_cover_literal_scale_estimate_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    lines = [
        "# Phase 3B Cover Literal Scale Estimate",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: static_scale_estimate_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Max static-pruned cover literals: {summary.get('max_static_pruned_pair_count', 0)}",
        f"- Max selected-coordinate constraints: {summary.get('max_selected_coord_total_constraints_estimate', 0)}",
        "",
        "## Anchors",
        "",
        "| Anchor | Risk | Powered | Poles | Naive Pairs | Static-Pruned Pairs | Pair Reduction | Protocol Slot-Pair All-Pairs | Protocol Position-Universal | Powered Without Candidate | Selected-Coord Constraints |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        replacement = _mapping(anchor.get("literal_replacement_estimates"))
        selected = _mapping(replacement.get("selected_coord_channel"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(anchor.get("anchor_idx")),
                    _markdown_cell(_mapping(anchor.get("risk")).get("classification")),
                    _markdown_cell(anchor.get("powered_slot_count")),
                    _markdown_cell(anchor.get("pole_slot_count")),
                    _markdown_cell(anchor.get("naive_pair_count")),
                    _markdown_cell(anchor.get("static_pruned_pair_count")),
                    _markdown_cell(anchor.get("static_pair_reduction_ratio")),
                    _markdown_cell(
                        _mapping(anchor.get("protocol_geometry_redundancy_candidate")).get(
                            "all_pairs_static_cover_valid"
                        )
                    ),
                    _markdown_cell(
                        _mapping(anchor.get("protocol_geometry_redundancy_candidate")).get(
                            "all_pairs_position_universal_valid"
                        )
                    ),
                    _markdown_cell(anchor.get("powered_without_static_cover_candidate_count")),
                    _markdown_cell(selected.get("total_constraints_estimate")),
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


def render_phase3b_cover_literal_scale_estimate_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    lines = [
        "Phase 3B cover literal scale estimate",
        "diagnostic_semantics=static_scale_estimate_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"max_static_pruned_pair_count={summary.get('max_static_pruned_pair_count', 0)}",
        f"risk_counts={summary.get('risk_counts', {})}",
    ]
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        selected = _mapping(_mapping(anchor.get("literal_replacement_estimates")).get("selected_coord_channel"))
        lines.append(
            "anchor "
            f"idx={anchor.get('anchor_idx')} "
            f"risk={_mapping(anchor.get('risk')).get('classification')} "
            f"powered={anchor.get('powered_slot_count')} "
            f"poles={anchor.get('pole_slot_count')} "
            f"naive_pairs={anchor.get('naive_pair_count')} "
            f"static_pruned_pairs={anchor.get('static_pruned_pair_count')} "
            f"protocol_all_pairs={_mapping(anchor.get('protocol_geometry_redundancy_candidate')).get('all_pairs_static_cover_valid')} "
            f"protocol_position_universal={_mapping(anchor.get('protocol_geometry_redundancy_candidate')).get('all_pairs_position_universal_valid')} "
            f"powered_without_candidate={anchor.get('powered_without_static_cover_candidate_count')} "
            f"selected_coord_constraints={selected.get('total_constraints_estimate')}"
        )
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _anchor_scale_estimate(model: Any, anchor_idx: int) -> Dict[str, Any]:
    ghost_domains = list(getattr(model, "_ghost_domains", []))
    if int(anchor_idx) < 0 or int(anchor_idx) >= len(ghost_domains):
        return {
            "anchor_idx": int(anchor_idx),
            "present": False,
            "classification": "anchor_missing",
        }
    delegate = getattr(model, "_coordinate_delegate", None)
    if delegate is None:
        return {
            "anchor_idx": int(anchor_idx),
            "present": False,
            "classification": "coordinate_delegate_missing",
        }
    domain = dict(ghost_domains[int(anchor_idx)])
    blocked_cells = {(int(x), int(y)) for x, y in list(domain.get("cells", []))}
    radius = int(delegate._power_coverage_radius())
    pole_slots = list(getattr(delegate, "residual_optional_slots", {}).get("power_pole", []))
    powered_slots = list(delegate._all_powered_slots())
    pole_entries = [
        _slot_position_entry(model, slot, blocked_cells=blocked_cells)
        for slot in pole_slots
    ]
    powered_entries = [
        _slot_position_entry(model, slot, blocked_cells=blocked_cells)
        for slot in powered_slots
    ]
    pair_stats = _pair_stats(
        pole_entries,
        powered_entries,
        radius=radius,
        grid_w=int(getattr(model, "grid_w", 0)),
        grid_h=int(getattr(model, "grid_h", 0)),
    )
    replacement = _literal_replacement_estimates(pair_stats, powered_entries)
    risk = _risk(pair_stats, replacement)
    current_element_constraints = _number_from_path(
        getattr(model, "build_stats", {}),
        ["power_coverage", "element_constraints"],
    )
    current_witness_indices = _number_from_path(
        getattr(model, "build_stats", {}),
        ["power_coverage", "witness_indices"],
    )
    return {
        "anchor_idx": int(anchor_idx),
        "present": True,
        "anchor": dict(_mapping(domain.get("anchor"))),
        "blocked_cell_count": int(len(blocked_cells)),
        "radius": int(radius),
        "powered_slot_count": int(len(powered_entries)),
        "pole_slot_count": int(len(pole_entries)),
        "current_element_constraints": int(current_element_constraints),
        "current_witness_indices": int(current_witness_indices),
        **pair_stats,
        "protocol_geometry_redundancy_candidate": _protocol_geometry_redundancy_candidate(pair_stats),
        "literal_replacement_estimates": replacement,
        "risk": risk,
    }


def _slot_position_entry(
    model: Any,
    slot: Any,
    *,
    blocked_cells: set[tuple[int, int]],
) -> Dict[str, Any]:
    surviving_positions: set[tuple[int, int]] = set()
    surviving_tuple_count = 0
    raw_items = dict(getattr(slot, "tuple_to_pose_idx", {}) or {}).items()
    for raw_tuple, pose_idx in raw_items:
        if not blocked_cells.isdisjoint(model._pose_cells(str(getattr(slot, "template", "")), int(pose_idx))):
            continue
        xy = _pose_tuple_xy(raw_tuple)
        if xy is None:
            continue
        x_val, y_val = xy
        surviving_tuple_count += 1
        surviving_positions.add((int(x_val), int(y_val)))
    dims = [int(value) for value in list(getattr(slot, "dims", (1, 1)))]
    if not dims:
        dims = [1, 1]
    if len(dims) < 2:
        dims.append(1)
    return {
        "slot_key": str(getattr(slot, "key", "")),
        "slot_kind": str(getattr(slot, "slot_kind", "")),
        "template": str(getattr(slot, "template", "")),
        "support_required": str(getattr(slot, "slot_kind", "")) != "residual_optional",
        "has_active_var": getattr(slot, "active", None) is not None,
        "dims": [int(dims[0]), int(dims[1])],
        "surviving_tuple_count": int(surviving_tuple_count),
        "surviving_position_count": int(len(surviving_positions)),
        "_positions": surviving_positions,
        "_x_min": min((int(pos[0]) for pos in surviving_positions), default=None),
        "_x_max": max((int(pos[0]) for pos in surviving_positions), default=None),
        "_y_min": min((int(pos[1]) for pos in surviving_positions), default=None),
        "_y_max": max((int(pos[1]) for pos in surviving_positions), default=None),
    }


def _pair_stats(
    pole_entries: Sequence[Mapping[str, Any]],
    powered_entries: Sequence[Mapping[str, Any]],
    *,
    radius: int,
    grid_w: int,
    grid_h: int,
) -> Dict[str, Any]:
    naive_pair_count = int(len(pole_entries) * len(powered_entries))
    static_pruned_pair_count = 0
    universal_pair_count = 0
    pair_counts_by_powered: list[int] = []
    universal_counts_by_powered: list[int] = []
    powered_without_candidate_count = 0
    by_template: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {
            "powered_slot_count": 0,
            "naive_pair_count": 0,
            "static_pruned_pair_count": 0,
            "position_universal_pair_count": 0,
            "powered_without_static_cover_candidate_count": 0,
        }
    )
    pole_entries_list = [entry for entry in pole_entries if isinstance(entry, Mapping)]
    pole_position_sets = [set(entry.get("_positions", set())) for entry in pole_entries_list]
    for powered in powered_entries:
        powered_positions = set(powered.get("_positions", set()))
        acceptable_poles = _covering_pole_positions(
            powered_positions,
            dims=powered.get("dims", [1, 1]),
            radius=int(radius),
            grid_w=int(grid_w),
            grid_h=int(grid_h),
        )
        pair_count = 0
        universal_count = 0
        for pole_entry, pole_positions in zip(pole_entries_list, pole_position_sets):
            if pole_positions and acceptable_poles and not pole_positions.isdisjoint(acceptable_poles):
                pair_count += 1
            if _position_universal_cover_pair(
                pole_entry,
                powered,
                radius=int(radius),
            ):
                universal_count += 1
        template = str(powered.get("template", ""))
        bucket = by_template[template]
        bucket["powered_slot_count"] += 1
        bucket["naive_pair_count"] += int(len(pole_entries))
        bucket["static_pruned_pair_count"] += int(pair_count)
        bucket["position_universal_pair_count"] += int(universal_count)
        if pair_count == 0:
            powered_without_candidate_count += 1
            bucket["powered_without_static_cover_candidate_count"] += 1
        pair_counts_by_powered.append(int(pair_count))
        universal_counts_by_powered.append(int(universal_count))
        static_pruned_pair_count += int(pair_count)
        universal_pair_count += int(universal_count)
    reduction_ratio = (
        1.0 - (float(static_pruned_pair_count) / float(naive_pair_count))
        if naive_pair_count > 0
        else 0.0
    )
    by_template_payload: Dict[str, Dict[str, Any]] = {}
    for key, value in sorted(by_template.items()):
        naive = int(value["naive_pair_count"])
        static = int(value["static_pruned_pair_count"])
        template_reduction_ratio = (
            1.0 - (float(static) / float(naive)) if naive > 0 else 0.0
        )
        by_template_payload[str(key)] = {
            **dict(value),
            "static_pair_reduction_ratio": round(float(template_reduction_ratio), 6),
            "all_pairs_static_cover_valid": bool(naive > 0 and static == naive),
            "position_universal_pair_ratio": round(
                float(value["position_universal_pair_count"]) / float(naive),
                6,
            )
            if naive > 0
            else 0.0,
            "all_pairs_position_universal_valid": bool(
                naive > 0 and int(value["position_universal_pair_count"]) == naive
            ),
        }
    all_pair_templates = [
        str(template)
        for template, payload in by_template_payload.items()
        if bool(payload.get("all_pairs_static_cover_valid"))
    ]
    return {
        "naive_pair_count": int(naive_pair_count),
        "static_pruned_pair_count": int(static_pruned_pair_count),
        "position_universal_pair_count": int(universal_pair_count),
        "position_universal_pair_ratio": round(
            float(universal_pair_count) / float(naive_pair_count),
            6,
        )
        if naive_pair_count > 0
        else 0.0,
        "static_pair_reduction_ratio": round(float(reduction_ratio), 6),
        "powered_without_static_cover_candidate_count": int(powered_without_candidate_count),
        "pair_count_distribution": _distribution(pair_counts_by_powered),
        "position_universal_pair_count_distribution": _distribution(universal_counts_by_powered),
        "pairs_by_powered_template": by_template_payload,
        "all_pairs_static_cover_templates": all_pair_templates,
    }


def _position_universal_cover_pair(
    pole: Mapping[str, Any],
    powered: Mapping[str, Any],
    *,
    radius: int,
) -> bool:
    if any(
        value is None
        for value in (
            pole.get("_x_min"),
            pole.get("_x_max"),
            pole.get("_y_min"),
            pole.get("_y_max"),
            powered.get("_x_min"),
            powered.get("_x_max"),
            powered.get("_y_min"),
            powered.get("_y_max"),
        )
    ):
        return False
    dims = [int(value) for value in list(powered.get("dims", [1, 1]))]
    width = int(dims[0]) if dims else 1
    height = int(dims[1]) if len(dims) > 1 else 1
    return bool(
        int(pole["_x_min"]) >= int(powered["_x_max"]) - int(radius) - 1
        and int(pole["_x_max"]) <= int(powered["_x_min"]) + int(width) - 1 + int(radius)
        and int(pole["_y_min"]) >= int(powered["_y_max"]) - int(radius) - 1
        and int(pole["_y_max"]) <= int(powered["_y_min"]) + int(height) - 1 + int(radius)
    )


def _protocol_geometry_redundancy_candidate(pair_stats: Mapping[str, Any]) -> Dict[str, Any]:
    protocol = _mapping(
        _mapping(pair_stats.get("pairs_by_powered_template")).get("protocol_storage_box")
    )
    if not protocol:
        return {
            "present": False,
            "all_pairs_static_cover_valid": False,
            "diagnostic_semantics": "static_support_condition_not_proof_source",
            "reason": "protocol_storage_box_template_missing",
        }
    all_pairs = bool(protocol.get("all_pairs_static_cover_valid"))
    return {
        "present": True,
        "all_pairs_static_cover_valid": all_pairs,
        "all_pairs_position_universal_valid": bool(
            protocol.get("all_pairs_position_universal_valid")
        ),
        "diagnostic_semantics": "static_support_condition_not_proof_source",
        "powered_slot_count": int(protocol.get("powered_slot_count", 0)),
        "naive_pair_count": int(protocol.get("naive_pair_count", 0)),
        "static_pruned_pair_count": int(protocol.get("static_pruned_pair_count", 0)),
        "position_universal_pair_count": int(protocol.get("position_universal_pair_count", 0)),
        "position_universal_pair_ratio": float(protocol.get("position_universal_pair_ratio", 0.0)),
        "static_pair_reduction_ratio": float(protocol.get("static_pair_reduction_ratio", 0.0)),
        "candidate_formulation": (
            "protocol_xy_geometry_can_be_conditionally_redundant"
            if bool(protocol.get("all_pairs_position_universal_valid"))
            else "protocol_xy_geometry_redundancy_candidate_requires_position_universality_proof"
            if all_pairs
            else "protocol_xy_geometry_not_redundant_by_static_support"
        ),
        "proof_safety_note": (
            "All-pairs here means every protocol slot / power-pole slot pair has at least one "
            "static cover candidate. It does not prove every coordinate assignment covers; "
            "a stronger position-universality proof is required before formulation changes."
        ),
    }


def _covering_pole_positions(
    powered_positions: set[tuple[int, int]],
    *,
    dims: Any,
    radius: int,
    grid_w: int,
    grid_h: int,
) -> set[tuple[int, int]]:
    dims_list = [int(value) for value in list(dims or [1, 1])]
    width = int(dims_list[0]) if dims_list else 1
    height = int(dims_list[1]) if len(dims_list) > 1 else 1
    result: set[tuple[int, int]] = set()
    for powered_x, powered_y in powered_positions:
        pole_x_min = max(0, int(powered_x) - int(radius) - 1)
        pole_x_max = min(max(0, int(grid_w) - 1), int(powered_x) + int(width) - 1 + int(radius))
        pole_y_min = max(0, int(powered_y) - int(radius) - 1)
        pole_y_max = min(max(0, int(grid_h) - 1), int(powered_y) + int(height) - 1 + int(radius))
        for pole_x in range(pole_x_min, pole_x_max + 1):
            for pole_y in range(pole_y_min, pole_y_max + 1):
                result.add((int(pole_x), int(pole_y)))
    return result


def _literal_replacement_estimates(
    pair_stats: Mapping[str, Any],
    powered_entries: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    pair_count = int(pair_stats.get("static_pruned_pair_count", 0))
    powered_count = int(len(powered_entries))
    powered_with_candidates = int(
        powered_count - int(pair_stats.get("powered_without_static_cover_candidate_count", 0))
    )
    powered_active_pair_count = _powered_active_pair_count(pair_stats, powered_entries)
    direct_active_constraints = int(pair_count + powered_active_pair_count)
    direct_geometry_constraints = int(pair_count * 4)
    direct_sum_constraints = int(powered_with_candidates)
    direct_total = int(
        direct_active_constraints + direct_geometry_constraints + direct_sum_constraints
    )
    selected_active_constraints = int(pair_count + powered_active_pair_count)
    selected_channel_constraints = int(pair_count * 2)
    selected_geometry_constraints = int(powered_with_candidates * 4)
    selected_sum_constraints = int(powered_with_candidates)
    selected_total = int(
        selected_active_constraints
        + selected_channel_constraints
        + selected_geometry_constraints
        + selected_sum_constraints
    )
    return {
        "direct_pairwise": {
            "cover_literals": int(pair_count),
            "extra_bool_vars_estimate": int(pair_count),
            "active_implication_constraints_estimate": int(direct_active_constraints),
            "geometry_constraints_estimate": int(direct_geometry_constraints),
            "witness_sum_constraints_estimate": int(direct_sum_constraints),
            "total_constraints_estimate": int(direct_total),
        },
        "selected_coord_channel": {
            "cover_literals": int(pair_count),
            "extra_bool_vars_estimate": int(pair_count),
            "extra_int_vars_estimate": int(powered_with_candidates * 2),
            "active_implication_constraints_estimate": int(selected_active_constraints),
            "selected_coordinate_channel_constraints_estimate": int(selected_channel_constraints),
            "geometry_constraints_estimate": int(selected_geometry_constraints),
            "witness_sum_constraints_estimate": int(selected_sum_constraints),
            "total_constraints_estimate": int(selected_total),
        },
    }


def _powered_active_pair_count(
    pair_stats: Mapping[str, Any],
    powered_entries: Sequence[Mapping[str, Any]],
) -> int:
    pair_distribution = list(_mapping(pair_stats.get("pair_count_distribution")).get("raw_counts", []))
    if len(pair_distribution) != len(powered_entries):
        return int(pair_stats.get("static_pruned_pair_count", 0))
    total = 0
    for powered, pair_count in zip(powered_entries, pair_distribution):
        if bool(powered.get("has_active_var", False)):
            total += int(pair_count)
    return int(total)


def _risk(pair_stats: Mapping[str, Any], replacement: Mapping[str, Any]) -> Dict[str, Any]:
    pair_count = int(pair_stats.get("static_pruned_pair_count", 0))
    selected_constraints = int(
        _mapping(replacement.get("selected_coord_channel")).get("total_constraints_estimate", 0)
    )
    direct_constraints = int(
        _mapping(replacement.get("direct_pairwise")).get("total_constraints_estimate", 0)
    )
    reasons: list[str] = []
    if pair_count >= 2_000_000 or selected_constraints >= 10_000_000:
        classification = "extreme"
        reasons.append("static-pruned literal replacement remains multi-million scale")
    elif pair_count >= 500_000 or selected_constraints >= 3_000_000:
        classification = "high"
        reasons.append("static-pruned literal replacement is large enough to require a diagnostic clone first")
    elif pair_count >= 100_000 or selected_constraints >= 750_000:
        classification = "medium"
        reasons.append("static-pruned replacement may be feasible only with selected-coordinate encoding and tight tests")
    else:
        classification = "low"
        reasons.append("static-pruned replacement is small enough for a guarded diagnostic prototype")
    if int(pair_stats.get("powered_without_static_cover_candidate_count", 0)) > 0:
        reasons.append("some powered slots have no static cover candidate under this anchor")
    if direct_constraints > selected_constraints * 2 and selected_constraints > 0:
        reasons.append("selected-coordinate channel is materially smaller than direct pairwise geometry")
    return {"classification": classification, "reasons": reasons}


def _status_from_anchors(anchors: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    present = [anchor for anchor in anchors if bool(anchor.get("present", False))]
    if not anchors:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_anchors_evaluated",
            "recommendation": "No anchors were evaluated.",
        }
    if not present:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "anchors_missing",
            "recommendation": "Selected anchors were not present in the exact overlay.",
        }
    risk_counts = Counter(str(_mapping(anchor.get("risk")).get("classification", "unknown")) for anchor in present)
    if risk_counts.get("extreme", 0) > 0 or risk_counts.get("high", 0) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "literal_replacement_high_scale_risk",
            "risk_counts": dict(sorted(risk_counts.items())),
            "recommendation": "Do not attempt a full cover-literal replacement in production yet; prototype only a diagnostic pruned/selected-coordinate clone.",
        }
    if risk_counts.get("medium", 0) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "literal_replacement_medium_scale_candidate",
            "risk_counts": dict(sorted(risk_counts.items())),
            "recommendation": "A guarded diagnostic selected-coordinate replacement may be reasonable after equivalence tests.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "literal_replacement_low_scale_candidate",
        "risk_counts": dict(sorted(risk_counts.items())),
        "recommendation": "A guarded diagnostic replacement prototype is scale-plausible; keep it out of proof-source semantics.",
    }


def _summary(anchors: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    present = [anchor for anchor in anchors if bool(anchor.get("present", False))]
    risk_counts = Counter(str(_mapping(anchor.get("risk")).get("classification", "unknown")) for anchor in present)
    selected_totals = [
        int(_mapping(_mapping(anchor.get("literal_replacement_estimates")).get("selected_coord_channel")).get("total_constraints_estimate", 0))
        for anchor in present
    ]
    direct_totals = [
        int(_mapping(_mapping(anchor.get("literal_replacement_estimates")).get("direct_pairwise")).get("total_constraints_estimate", 0))
        for anchor in present
    ]
    return {
        "anchor_count": int(len(anchors)),
        "present_anchor_count": int(len(present)),
        "max_naive_pair_count": max([int(anchor.get("naive_pair_count", 0)) for anchor in present], default=0),
        "max_static_pruned_pair_count": max([int(anchor.get("static_pruned_pair_count", 0)) for anchor in present], default=0),
        "max_direct_pairwise_total_constraints_estimate": max(direct_totals, default=0),
        "max_selected_coord_total_constraints_estimate": max(selected_totals, default=0),
        "risk_counts": dict(sorted(risk_counts.items())),
    }


def _distribution(values: Sequence[int]) -> Dict[str, Any]:
    nums = [int(value) for value in values]
    if not nums:
        return {
            "min": 0,
            "max": 0,
            "mean": 0.0,
            "median": 0.0,
            "p95": 0,
            "raw_counts": [],
        }
    sorted_nums = sorted(nums)
    p95_idx = min(len(sorted_nums) - 1, int(round((len(sorted_nums) - 1) * 0.95)))
    return {
        "min": int(min(sorted_nums)),
        "max": int(max(sorted_nums)),
        "mean": round(float(statistics.fmean(sorted_nums)), 6),
        "median": round(float(statistics.median(sorted_nums)), 6),
        "p95": int(sorted_nums[p95_idx]),
        "raw_counts": [int(value) for value in nums],
    }


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    selected_anchor_count: int,
    anchors: Sequence[Mapping[str, Any]],
    status: Mapping[str, Any],
    model_error: Optional[str],
    campaign_state_unchanged: bool,
) -> list[Dict[str, str]]:
    present_anchors = [anchor for anchor in anchors if bool(anchor.get("present", False))]
    missing_cover = sum(
        int(anchor.get("powered_without_static_cover_candidate_count", 0))
        for anchor in present_anchors
    )
    protocol_candidates = [
        _mapping(anchor.get("protocol_geometry_redundancy_candidate"))
        for anchor in present_anchors
        if bool(_mapping(anchor.get("protocol_geometry_redundancy_candidate")).get("present"))
    ]
    protocol_all_pairs = bool(protocol_candidates) and all(
        bool(candidate.get("all_pairs_static_cover_valid")) for candidate in protocol_candidates
    )
    protocol_position_universal = bool(protocol_candidates) and all(
        bool(candidate.get("all_pairs_position_universal_valid"))
        for candidate in protocol_candidates
    )
    return [
        _check(
            "campaign_state_present",
            "pass" if state_present else "fail",
            "campaign state loaded" if state_present else "campaign state missing",
        ),
        _check(
            "candidate_present",
            "pass" if candidate_present else "fail",
            "candidate loaded" if candidate_present else "candidate missing",
        ),
        _check(
            "forced_anchor_samples_present",
            "pass" if selected_anchor_count > 0 else "fail",
            f"selected_anchor_count={int(selected_anchor_count)}",
        ),
        _check(
            "scale_estimate_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "all_powered_slots_have_static_cover_candidate",
            "pass" if missing_cover == 0 and present_anchors else "fail" if present_anchors else "skipped",
            f"powered_without_static_cover_candidate_count={int(missing_cover)}",
        ),
        _check(
            "protocol_storage_box_all_pairs_static_cover_valid",
            "pass" if protocol_all_pairs else "fail" if protocol_candidates else "skipped",
            (
                f"anchor_count={len(protocol_candidates)}"
                if protocol_candidates
                else "protocol_storage_box template not present in evaluated anchors"
            ),
        ),
        _check(
            "protocol_storage_box_all_pairs_position_universal_valid",
            "pass" if protocol_position_universal else "fail" if protocol_candidates else "skipped",
            (
                f"anchor_count={len(protocol_candidates)}"
                if protocol_candidates
                else "protocol_storage_box template not present in evaluated anchors"
            ),
        ),
        _check(
            "campaign_state_unchanged",
            "pass" if campaign_state_unchanged else "fail",
            "campaign state hash unchanged" if campaign_state_unchanged else "campaign state changed during diagnostic",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _number_from_path(payload: Any, path: Sequence[str]) -> int:
    value: Any = payload
    for key in path:
        value = _mapping(value).get(str(key))
    try:
        return int(value)
    except Exception:
        return 0


def _markdown_cell(value: Any) -> str:
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return text


def _pose_tuple_xy(raw_tuple: Any) -> Optional[tuple[int, int]]:
    if not isinstance(raw_tuple, (list, tuple)) or len(raw_tuple) < 3:
        return None
    # CoordinateExactMaster stores pose tuples as (x, y, mode_id).
    return int(raw_tuple[0]), int(raw_tuple[1])
