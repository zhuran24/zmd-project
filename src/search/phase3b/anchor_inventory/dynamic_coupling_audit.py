from __future__ import annotations

import json
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


ANCHOR_DYNAMIC_COUPLING_AUDIT_SOURCE = "phase3b_anchor_dynamic_coupling_audit_v1"
DEFAULT_CANDIDATE = "67x13"


def build_phase3b_anchor_dynamic_coupling_audit(
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
    profile: Dict[str, Any] = {}

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
            profile = _model_profile(model)
            for anchor_idx in selected_anchor_indices:
                anchors.append(_anchor_dynamic_profile(model, int(anchor_idx)))
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
            "source": ANCHOR_DYNAMIC_COUPLING_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_anchor_dynamic_coupling_not_proof_source",
            "solver_invoked": False,
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
            **profile,
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


def render_phase3b_anchor_dynamic_coupling_audit_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    lines = [
        "# Phase 3B Anchor Dynamic Coupling Audit",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: no_solve_anchor_dynamic_coupling_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {report.get('recommendation')}",
        f"- Deficit anchors: {summary.get('deficit_anchor_indices')}",
        f"- Solver invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        "",
        "## Template Coverer-Family Cuts",
        "",
        "| Anchor | Template | Demand | Max coverer capacity | Slack | Deficit | Families |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: |",
    ]
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        for cert in list(anchor.get("template_coverer_family_cuts", [])):
            if not isinstance(cert, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(anchor.get("anchor_idx")),
                        _cell(cert.get("template")),
                        _cell(cert.get("demand")),
                        _cell(cert.get("max_coverer_family_capacity")),
                        _cell(cert.get("slack")),
                        _cell(cert.get("deficit")),
                        _cell(cert.get("coverer_family_count")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Tightest Slots", ""])
    lines.append("| Anchor | Slot | Kind | Template | Surviving positions | Coverer families | Capacity slack |")
    lines.append("| --- | --- | --- | --- | ---: | ---: | ---: |")
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        for slot in list(anchor.get("tightest_slots", []))[:20]:
            if not isinstance(slot, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(anchor.get("anchor_idx")),
                        _cell(slot.get("slot_key")),
                        _cell(slot.get("slot_kind")),
                        _cell(slot.get("template")),
                        _cell(slot.get("surviving_position_count")),
                        _cell(slot.get("coverer_family_count")),
                        _cell(slot.get("coverer_family_capacity_slack")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Block64 Witness Profile", ""])
    lines.append("| Anchor | Template | Slots | Union blocks | Union families | Min blocks/slot | Min families/slot |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        by_template = _mapping(_mapping(anchor.get("block64_witness_profile")).get("by_template"))
        for template, profile in by_template.items():
            if not isinstance(profile, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(anchor.get("anchor_idx")),
                        _cell(template),
                        _cell(profile.get("slot_count")),
                        _cell(profile.get("union_block_count")),
                        _cell(profile.get("union_family_count")),
                        _cell(profile.get("min_coverer_block_count")),
                        _cell(profile.get("min_coverer_family_count")),
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
                        _cell(check.get("check_id")),
                        _cell(check.get("status")),
                        _cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_anchor_dynamic_coupling_audit_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    lines = [
        "Phase 3B anchor dynamic coupling audit",
        "diagnostic_semantics=no_solve_anchor_dynamic_coupling_not_proof_source",
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
            f"template_deficits={anchor.get('template_deficit_count')}"
        )
        for cert in list(anchor.get("template_coverer_family_cuts", [])):
            if isinstance(cert, Mapping):
                lines.append(
                    "  template "
                    f"name={cert.get('template')} demand={cert.get('demand')} "
                    f"max_coverer_capacity={cert.get('max_coverer_family_capacity')} "
                    f"slack={cert.get('slack')} deficit={cert.get('deficit')}"
                )
    return "\n".join(lines) + "\n"


def _model_profile(model: Any) -> Dict[str, Any]:
    delegate = getattr(model, "_coordinate_delegate", None)
    gvi = _mapping(getattr(model, "build_stats", {}).get("global_valid_inequalities"))
    if delegate is None:
        return {}
    return {
        "power_coverage_witness_encoding": str(
            getattr(delegate, "_power_coverage_witness_encoding", "")
        ),
        "power_coverage_witness_block_geometry": str(
            getattr(delegate, "_power_coverage_witness_block_geometry", "")
        ),
        "power_coverage_witness_block_size": int(
            getattr(delegate, "_power_coverage_witness_block_size", 0) or 0
        ),
        "power_coverage_selected_interval_encoding": str(
            getattr(delegate, "_power_coverage_selected_interval_encoding", "")
        ),
        "power_family_lookup_encoding": str(getattr(delegate, "_power_family_lookup_encoding", "")),
        "powered_template_demands": {
            str(tpl): int(demand)
            for tpl, demand in sorted(_mapping(gvi.get("powered_template_demands")).items())
        },
    }


def _anchor_dynamic_profile(model: Any, anchor_idx: int) -> Dict[str, Any]:
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
    radius = int(delegate._power_coverage_radius())
    pole_entries = _surviving_pole_entries(model, delegate, blocked_cells=blocked_cells)
    family_bounds = _family_bounds(delegate, domain)
    slot_entries = [
        _slot_dynamic_entry(
            model,
            delegate,
            slot,
            blocked_cells=blocked_cells,
            pole_entries=pole_entries,
            family_bounds=family_bounds,
            radius=radius,
        )
        for slot in list(delegate._all_powered_slots())
    ]
    template_cuts = _template_coverer_family_cuts(model, delegate, slot_entries, family_bounds)
    template_deficit_count = sum(1 for cut in template_cuts if bool(cut.get("deficit")))
    classification = (
        "coverer_family_cut_deficit"
        if template_deficit_count
        else "dynamic_family_cover_cut_inconclusive"
    )
    return {
        "anchor_idx": int(anchor_idx),
        "present": True,
        "anchor": dict(_mapping(domain.get("anchor"))),
        "blocked_cell_count": int(len(blocked_cells)),
        "radius": int(radius),
        "classification": classification,
        "pole_domain": {
            "surviving_pose_count": int(len(pole_entries)),
            "surviving_family_count": int(len({entry["family_name"] for entry in pole_entries})),
        },
        "family_bounds": family_bounds,
        "template_coverer_family_cuts": template_cuts,
        "template_deficit_count": int(template_deficit_count),
        "block64_witness_profile": _block64_witness_profile(slot_entries),
        "tightest_slots": sorted(
            slot_entries,
            key=lambda entry: (
                int(entry.get("coverer_family_count", 0)),
                int(entry.get("coverer_pole_pose_count", 0)),
                int(entry.get("coverer_family_capacity_slack", 0)),
                str(entry.get("slot_key")),
            ),
        )[:40],
        "slot_summary": _slot_summary(slot_entries),
    }


def _surviving_pole_entries(
    model: Any,
    delegate: Any,
    *,
    blocked_cells: set[tuple[int, int]],
) -> list[Dict[str, Any]]:
    entries: list[Dict[str, Any]] = []
    pose_tuples = dict(getattr(delegate, "_template_pose_tuple_by_idx", {}).get("power_pole", {}))
    family_id_by_pose = dict(getattr(delegate, "_power_pole_family_id_by_pose_idx", {}))
    family_name_by_int = dict(getattr(delegate, "_power_pole_family_name_by_int", {}))
    for pose_idx, pose_tuple in sorted(pose_tuples.items()):
        if not blocked_cells.isdisjoint(model._pose_cells("power_pole", int(pose_idx))):
            continue
        parsed = _parse_pose_tuple(pose_tuple)
        if parsed is None:
            continue
        x_val, y_val, mode_id = parsed
        family_id = family_id_by_pose.get(int(pose_idx))
        family_name = family_name_by_int.get(int(family_id)) if family_id is not None else None
        if family_name is None:
            continue
        entries.append(
            {
                "pose_idx": int(pose_idx),
                "x": int(x_val),
                "y": int(y_val),
                "mode": int(mode_id),
                "family_id": int(family_id),
                "family_name": str(family_name),
            }
        )
    return entries


def _family_bounds(delegate: Any, ghost_domain: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    conditioned = {
        str(family): int(upper)
        for family, upper in _mapping(
            ghost_domain.get("conditioned_power_pole_family_upper_bounds")
        ).items()
    }
    result: Dict[str, Dict[str, Any]] = {}
    family_coefficients = {
        str(name): {
            str(tpl): int(coeff)
            for tpl, coeff in sorted(_mapping(coefficients).items())
        }
        for name, coefficients in sorted(
            dict(getattr(delegate, "_power_pole_family_coefficients", {})).items()
        )
    }
    for family_name, coefficients in family_coefficients.items():
        default_upper = int(delegate._power_pole_family_count_upper_bound(str(family_name)))
        conditioned_upper = conditioned.get(str(family_name))
        effective_upper = (
            int(min(default_upper, max(0, conditioned_upper)))
            if conditioned_upper is not None
            else int(default_upper)
        )
        result[str(family_name)] = {
            "family_name": str(family_name),
            "default_upper": int(default_upper),
            "effective_upper": int(effective_upper),
            "source": "anchor_conditioned_upper" if conditioned_upper is not None else "global_upper",
            "coefficients": coefficients,
        }
    return result


def _slot_dynamic_entry(
    model: Any,
    delegate: Any,
    slot: Any,
    *,
    blocked_cells: set[tuple[int, int]],
    pole_entries: Sequence[Mapping[str, Any]],
    family_bounds: Mapping[str, Mapping[str, Any]],
    radius: int,
) -> Dict[str, Any]:
    surviving_positions: set[tuple[int, int]] = set()
    surviving_tuple_count = 0
    for raw_tuple, pose_idx in dict(getattr(slot, "tuple_to_pose_idx", {}) or {}).items():
        if not blocked_cells.isdisjoint(model._pose_cells(str(slot.template), int(pose_idx))):
            continue
        parsed = _parse_pose_tuple(raw_tuple)
        if parsed is None:
            continue
        x_val, y_val, _mode_id = parsed
        surviving_tuple_count += 1
        surviving_positions.add((int(x_val), int(y_val)))
    dims = (int(slot.dims[0]), int(slot.dims[1]))
    coverer_families: set[str] = set()
    coverer_pose_count = 0
    block_histogram: Dict[str, int] = defaultdict(int)
    block_family_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    block_size = int(getattr(delegate, "_power_coverage_witness_block_size", 0) or 0)
    for pole in pole_entries:
        pole_x = int(pole.get("x", 0))
        pole_y = int(pole.get("y", 0))
        if any(
            _can_cover_position(
                powered_position=pos,
                dims=dims,
                pole_position=(pole_x, pole_y),
                radius=radius,
                grid_w=int(model.grid_w),
                grid_h=int(model.grid_h),
            )
            for pos in surviving_positions
        ):
            coverer_pose_count += 1
            family_name = str(pole.get("family_name"))
            coverer_families.add(family_name)
            if block_size > 0:
                block_index = str(int(pole.get("pose_idx", 0)) // block_size)
                block_histogram[block_index] += 1
                block_family_counts[block_index][family_name] += 1
    capacity_upper = _families_capacity_upper(
        coverer_families,
        template=str(slot.template),
        family_bounds=family_bounds,
    )
    support_required = str(getattr(slot, "slot_kind", "")) != "residual_optional"
    required_count = 1 if support_required else 0
    return {
        "slot_key": str(getattr(slot, "key", "")),
        "slot_kind": str(getattr(slot, "slot_kind", "")),
        "template": str(getattr(slot, "template", "")),
        "dims": [int(dims[0]), int(dims[1])],
        "support_required": bool(support_required),
        "required_count": int(required_count),
        "surviving_tuple_count": int(surviving_tuple_count),
        "surviving_position_count": int(len(surviving_positions)),
        "coverer_pole_pose_count": int(coverer_pose_count),
        "coverer_family_count": int(len(coverer_families)),
        "coverer_family_ids": sorted(coverer_families),
        "coverer_family_capacity_upper": int(capacity_upper),
        "coverer_family_capacity_slack": int(capacity_upper) - int(required_count),
        "coverer_block_count": int(len(block_histogram)),
        "coverer_block_histogram": {str(k): int(v) for k, v in sorted(block_histogram.items())},
        "coverer_block_family_counts": {
            str(block): {str(family): int(count) for family, count in sorted(families.items())}
            for block, families in sorted(block_family_counts.items())
        },
    }


def _block64_witness_profile(slot_entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_template: Dict[str, Dict[str, Any]] = {}
    for entry in slot_entries:
        template = str(entry.get("template"))
        profile = by_template.setdefault(
            template,
            {
                "template": template,
                "slot_count": 0,
                "required_slot_count": 0,
                "union_blocks": set(),
                "union_families": set(),
                "coverer_block_counts": [],
                "coverer_family_counts": [],
                "block_pose_counts": defaultdict(int),
                "block_family_counts": defaultdict(lambda: defaultdict(int)),
            },
        )
        profile["slot_count"] += 1
        if bool(entry.get("support_required")):
            profile["required_slot_count"] += 1
        block_histogram = _mapping(entry.get("coverer_block_histogram"))
        profile["coverer_block_counts"].append(int(len(block_histogram)))
        profile["coverer_family_counts"].append(int(entry.get("coverer_family_count", 0) or 0))
        for block, count in block_histogram.items():
            block_key = str(block)
            profile["union_blocks"].add(block_key)
            profile["block_pose_counts"][block_key] += int(count)
        for block, families in _mapping(entry.get("coverer_block_family_counts")).items():
            block_key = str(block)
            for family, count in _mapping(families).items():
                family_name = str(family)
                profile["union_families"].add(family_name)
                profile["block_family_counts"][block_key][family_name] += int(count)
    rendered: Dict[str, Dict[str, Any]] = {}
    for template, profile in sorted(by_template.items()):
        block_counts = [int(value) for value in list(profile["coverer_block_counts"])]
        family_counts = [int(value) for value in list(profile["coverer_family_counts"])]
        top_blocks = sorted(
            (
                {
                    "block_index": str(block),
                    "pose_reference_count": int(count),
                    "family_count": int(len(profile["block_family_counts"].get(str(block), {}))),
                    "top_families": _top_family_counts(profile["block_family_counts"].get(str(block), {})),
                }
                for block, count in profile["block_pose_counts"].items()
            ),
            key=lambda item: (-int(item["pose_reference_count"]), str(item["block_index"])),
        )[:12]
        rendered[str(template)] = {
            "template": str(template),
            "slot_count": int(profile["slot_count"]),
            "required_slot_count": int(profile["required_slot_count"]),
            "union_block_count": int(len(profile["union_blocks"])),
            "union_family_count": int(len(profile["union_families"])),
            "min_coverer_block_count": min(block_counts) if block_counts else 0,
            "max_coverer_block_count": max(block_counts) if block_counts else 0,
            "min_coverer_family_count": min(family_counts) if family_counts else 0,
            "max_coverer_family_count": max(family_counts) if family_counts else 0,
            "top_blocks": top_blocks,
        }
    return {
        "block_size_semantics": "pose_idx_floor_div_block_size",
        "by_template": rendered,
    }


def _top_family_counts(counts: Mapping[str, Any], *, limit: int = 8) -> list[Dict[str, Any]]:
    return [
        {"family_name": str(family), "count": int(count)}
        for family, count in sorted(
            _mapping(counts).items(),
            key=lambda item: (-int(item[1]), str(item[0])),
        )[:limit]
    ]


def _template_coverer_family_cuts(
    model: Any,
    delegate: Any,
    slot_entries: Sequence[Mapping[str, Any]],
    family_bounds: Mapping[str, Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    gvi = _mapping(getattr(model, "build_stats", {}).get("global_valid_inequalities"))
    demands = {
        str(tpl): int(demand)
        for tpl, demand in sorted(_mapping(gvi.get("powered_template_demands")).items())
    }
    coverer_families_by_template: Dict[str, set[str]] = defaultdict(set)
    required_slot_count_by_template: Dict[str, int] = defaultdict(int)
    for entry in slot_entries:
        tpl = str(entry.get("template"))
        template_has_positive_demand = int(demands.get(tpl, 0) or 0) > 0
        if not bool(entry.get("support_required")) and not template_has_positive_demand:
            continue
        required_slot_count_by_template[tpl] += 1
        coverer_families_by_template[tpl].update(str(fam) for fam in list(entry.get("coverer_family_ids", [])))
    certificates: list[Dict[str, Any]] = []
    for tpl, demand in sorted(demands.items()):
        families = coverer_families_by_template.get(str(tpl), set())
        max_capacity = _families_capacity_upper(families, template=str(tpl), family_bounds=family_bounds)
        contributions = _family_contributions(families, template=str(tpl), family_bounds=family_bounds)
        certificates.append(
            {
                "certificate_type": "coverer_family_cut_deficit",
                "template": str(tpl),
                "demand": int(demand),
                "required_slot_count": int(required_slot_count_by_template.get(str(tpl), 0)),
                "max_coverer_family_capacity": int(max_capacity),
                "slack": int(max_capacity) - int(demand),
                "deficit": int(max_capacity) < int(demand),
                "coverer_family_count": int(len(families)),
                "coverer_families": sorted(families),
                "top_contributions": contributions[:20],
                "relaxations": [
                    "ignores_no_overlap_between_poles",
                    "allows_each_available_family_member_to_contribute independently",
                    "uses_family_union_over_required_slots",
                ],
            }
        )
    return certificates


def _families_capacity_upper(
    family_names: Sequence[str] | set[str],
    *,
    template: str,
    family_bounds: Mapping[str, Mapping[str, Any]],
) -> int:
    total = 0
    for family_name in sorted(str(name) for name in family_names):
        bound = _mapping(family_bounds.get(str(family_name)))
        coeff = int(_mapping(bound.get("coefficients")).get(str(template), 0) or 0)
        if coeff <= 0:
            continue
        total += int(coeff) * int(bound.get("effective_upper", 0) or 0)
    return int(total)


def _family_contributions(
    family_names: Sequence[str] | set[str],
    *,
    template: str,
    family_bounds: Mapping[str, Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for family_name in sorted(str(name) for name in family_names):
        bound = _mapping(family_bounds.get(str(family_name)))
        coeff = int(_mapping(bound.get("coefficients")).get(str(template), 0) or 0)
        if coeff <= 0:
            continue
        upper = int(bound.get("effective_upper", 0) or 0)
        result.append(
            {
                "family_name": str(family_name),
                "coeff": int(coeff),
                "effective_upper": int(upper),
                "source": str(bound.get("source")),
                "max_contribution": int(coeff) * int(upper),
            }
        )
    return sorted(result, key=lambda item: (-int(item["max_contribution"]), str(item["family_name"])))


def _can_cover_position(
    *,
    powered_position: tuple[int, int],
    dims: tuple[int, int],
    pole_position: tuple[int, int],
    radius: int,
    grid_w: int,
    grid_h: int,
) -> bool:
    powered_x, powered_y = (int(powered_position[0]), int(powered_position[1]))
    pole_x, pole_y = (int(pole_position[0]), int(pole_position[1]))
    width, height = int(dims[0]), int(dims[1])
    x_min = max(0, pole_x - int(radius) - width + 1)
    x_max = min(int(grid_w) - 1, pole_x + int(radius) + 1)
    y_min = max(0, pole_y - int(radius) - height + 1)
    y_max = min(int(grid_h) - 1, pole_y + int(radius) + 1)
    return x_min <= powered_x <= x_max and y_min <= powered_y <= y_max


def _parse_pose_tuple(raw_tuple: Any) -> Optional[tuple[int, int, int]]:
    try:
        x_val, y_val, mode_id = raw_tuple
    except Exception:
        return None
    return int(x_val), int(y_val), int(mode_id)


def _slot_summary(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_template: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {
            "slot_count": 0,
            "required_slot_count": 0,
            "min_coverer_family_count": 0,
        }
    )
    for entry in entries:
        tpl = str(entry.get("template"))
        stats = by_template[tpl]
        stats["slot_count"] += 1
        if bool(entry.get("support_required")):
            stats["required_slot_count"] += 1
        current = int(entry.get("coverer_family_count", 0))
        if stats["min_coverer_family_count"] == 0:
            stats["min_coverer_family_count"] = current
        else:
            stats["min_coverer_family_count"] = min(stats["min_coverer_family_count"], current)
    return {"by_template": {str(k): dict(v) for k, v in sorted(by_template.items())}}


def _status_from_anchors(anchors: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not anchors:
        return {"completed": True, "evaluated": False, "outcome": "anchor_samples_missing"}
    present = [anchor for anchor in anchors if bool(anchor.get("present", False))]
    if not present:
        return {"completed": True, "evaluated": False, "outcome": "anchors_missing"}
    deficit_anchors = [
        int(anchor.get("anchor_idx", -1))
        for anchor in present
        if int(anchor.get("template_deficit_count", 0) or 0) > 0
    ]
    if deficit_anchors == [118]:
        outcome = "anchor118_coverer_family_cut_deficit_control_pass"
    elif deficit_anchors:
        outcome = "coverer_family_cut_deficit_present"
    else:
        outcome = "dynamic_family_cover_cut_inconclusive"
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
        if int(anchor.get("template_deficit_count", 0) or 0) > 0
    ]
    return {
        "anchor_count": int(len(anchors)),
        "deficit_anchor_indices": deficit_indices,
        "deficit_anchor_count": int(len(deficit_indices)),
        "classification_counts": dict(Counter(str(anchor.get("classification")) for anchor in anchors)),
    }


def _recommendation(outcome: Any) -> str:
    if outcome == "anchor118_coverer_family_cut_deficit_control_pass":
        return (
            "Anchor118 has a no-solve coverer-family capacity deficit while the control "
            "does not; review the certificate before considering a guarded default-off precheck."
        )
    if outcome == "coverer_family_cut_deficit_present":
        return (
            "At least one inspected anchor has a coverer-family capacity deficit, but the "
            "control rule did not isolate anchor118 cleanly; inspect anchors before promotion."
        )
    if outcome == "dynamic_family_cover_cut_inconclusive":
        return (
            "No coverer-family cut deficit was found. Move to block64 family lookup "
            "witness differentials or packable-pole capacity bounds."
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
