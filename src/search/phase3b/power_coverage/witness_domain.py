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
    DEFAULT_CANDIDATE,
    _build_exact_overlay,
    _candidate_ghost_rect,
    _check,
    _display_path,
    _file_hash,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
)

POWER_COVERAGE_WITNESS_DOMAIN_SOURCE = (
    "phase3b_power_coverage_witness_domain_v1"
)


def build_phase3b_power_coverage_witness_domain(
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
    model_error: Optional[str] = None
    anchors: list[Dict[str, Any]] = []
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
    }

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
            }
        )
    elif not record:
        status.update(
            {
                "completed": True,
                "outcome": "candidate_missing",
            }
        )
    elif not selected_anchor_indices:
        status.update(
            {
                "completed": True,
                "outcome": "anchor_samples_missing",
            }
        )
    else:
        try:
            model, _base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=master_search_profile,
            )
            for anchor_idx in selected_anchor_indices:
                anchors.append(_anchor_witness_domain(model, int(anchor_idx)))
            status.update(_status_from_anchors(anchors))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                }
            )

    after_hash = _file_hash(campaign_path)
    recommendation = _recommendation(status.get("outcome"))
    return {
        "metadata": {
            "source": POWER_COVERAGE_WITNESS_DOMAIN_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "static_domain_probe_not_proof_source",
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
        },
        "status": {**status, "recommendation": recommendation},
        "anchors": anchors,
        "summary": _summary(anchors),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "campaign_state_unchanged": before_hash == after_hash,
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            anchors=anchors,
            status=status,
            model_error=model_error,
            campaign_state_unchanged=before_hash == after_hash,
        ),
        "recommendation": recommendation,
    }


def render_phase3b_power_coverage_witness_domain_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    lines = [
        "# Phase 3B Power Coverage Witness-Domain Probe",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: static_domain_probe_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Required unsupported slots: {summary.get('required_unsupported_slot_count')}",
        f"- Optional unsupported slots: {summary.get('optional_unsupported_slot_count')}",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "## Anchors",
        "",
        "| Anchor | Classification | Pole Positions | Required Unsupported | Optional Unsupported | Tightest Witnessable Positions |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        pole_domain = _mapping(anchor.get("pole_domain"))
        slot_summary = _mapping(anchor.get("powered_slot_summary"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(anchor.get("anchor_idx")),
                    _markdown_cell(anchor.get("classification")),
                    _markdown_cell(pole_domain.get("surviving_position_count")),
                    _markdown_cell(slot_summary.get("required_unsupported_slot_count")),
                    _markdown_cell(slot_summary.get("optional_unsupported_slot_count")),
                    _markdown_cell(slot_summary.get("min_witnessable_position_count")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Tightest Slots", "", "| Anchor | Slot | Kind | Template | Positions | Witnessable |"])
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        for slot in list(anchor.get("tightest_slots", []))[:10]:
            if isinstance(slot, Mapping):
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _markdown_cell(anchor.get("anchor_idx")),
                            _markdown_cell(slot.get("slot_key")),
                            _markdown_cell(slot.get("slot_kind")),
                            _markdown_cell(slot.get("template")),
                            _markdown_cell(slot.get("surviving_position_count")),
                            _markdown_cell(slot.get("witnessable_position_count")),
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


def render_phase3b_power_coverage_witness_domain_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    lines = [
        "Phase 3B power coverage witness-domain probe",
        "diagnostic_semantics=static_domain_probe_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"required_unsupported_slot_count={summary.get('required_unsupported_slot_count')}",
        f"optional_unsupported_slot_count={summary.get('optional_unsupported_slot_count')}",
        f"recommendation={report.get('recommendation')}",
    ]
    for anchor in list(report.get("anchors", [])):
        if isinstance(anchor, Mapping):
            slot_summary = _mapping(anchor.get("powered_slot_summary"))
            pole_domain = _mapping(anchor.get("pole_domain"))
            lines.append(
                "anchor "
                f"idx={anchor.get('anchor_idx')} "
                f"classification={anchor.get('classification')} "
                f"pole_positions={pole_domain.get('surviving_position_count')} "
                f"required_unsupported={slot_summary.get('required_unsupported_slot_count')} "
                f"optional_unsupported={slot_summary.get('optional_unsupported_slot_count')} "
                f"min_witnessable={slot_summary.get('min_witnessable_position_count')}"
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


def _anchor_witness_domain(model: Any, anchor_idx: int) -> Dict[str, Any]:
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
    pole_positions, pole_pose_count = _surviving_template_positions(
        model,
        delegate,
        template="power_pole",
        blocked_cells=blocked_cells,
    )
    cover_cache: Dict[tuple[int, int], set[tuple[int, int]]] = {}
    slot_entries: list[Dict[str, Any]] = []
    for slot in list(delegate._all_powered_slots()):
        slot_entries.append(
            _slot_witness_entry(
                model,
                slot,
                blocked_cells=blocked_cells,
                pole_positions=pole_positions,
                radius=radius,
                cover_cache=cover_cache,
            )
        )
    slot_summary = _slot_summary(slot_entries)
    classification = _anchor_classification(slot_summary, pole_positions)
    return {
        "anchor_idx": int(anchor_idx),
        "present": True,
        "anchor": dict(_mapping(domain.get("anchor"))),
        "blocked_cell_count": int(len(blocked_cells)),
        "radius": int(radius),
        "classification": classification,
        "pole_domain": {
            "slot_count": int(len(pole_slots)),
            "surviving_pose_count": int(pole_pose_count),
            "surviving_position_count": int(len(pole_positions)),
        },
        "powered_slot_summary": slot_summary,
        "unsupported_required_slots": [
            entry
            for entry in slot_entries
            if bool(entry.get("support_required")) and not bool(entry.get("static_supported"))
        ][:25],
        "unsupported_optional_slots": [
            entry
            for entry in slot_entries
            if not bool(entry.get("support_required")) and not bool(entry.get("static_supported"))
        ][:25],
        "tightest_slots": sorted(
            slot_entries,
            key=lambda entry: (
                int(entry.get("witnessable_position_count", 0)),
                int(entry.get("surviving_position_count", 0)),
                str(entry.get("slot_key")),
            ),
        )[:25],
    }


def _slot_witness_entry(
    model: Any,
    slot: Any,
    *,
    blocked_cells: set[tuple[int, int]],
    pole_positions: set[tuple[int, int]],
    radius: int,
    cover_cache: Dict[tuple[int, int], set[tuple[int, int]]],
) -> Dict[str, Any]:
    surviving_positions: set[tuple[int, int]] = set()
    surviving_tuple_count = 0
    for raw_tuple, pose_idx in dict(getattr(slot, "tuple_to_pose_idx", {}) or {}).items():
        if not blocked_cells.isdisjoint(model._pose_cells(str(slot.template), int(pose_idx))):
            continue
        try:
            x_val, y_val, _mode = raw_tuple
        except Exception:
            continue
        surviving_tuple_count += 1
        surviving_positions.add((int(x_val), int(y_val)))
    dims = (int(slot.dims[0]), int(slot.dims[1]))
    coverable_positions = cover_cache.get(dims)
    if coverable_positions is None:
        coverable_positions = _coverable_powered_positions(
            pole_positions,
            dims=dims,
            radius=int(radius),
            grid_w=int(model.grid_w),
            grid_h=int(model.grid_h),
        )
        cover_cache[dims] = coverable_positions
    witnessable_position_count = len(surviving_positions & coverable_positions)
    support_required = str(getattr(slot, "slot_kind", "")) != "residual_optional"
    return {
        "slot_key": str(getattr(slot, "key", "")),
        "slot_kind": str(getattr(slot, "slot_kind", "")),
        "template": str(getattr(slot, "template", "")),
        "dims": [int(dims[0]), int(dims[1])],
        "support_required": bool(support_required),
        "surviving_tuple_count": int(surviving_tuple_count),
        "surviving_position_count": int(len(surviving_positions)),
        "witnessable_position_count": int(witnessable_position_count),
        "unwitnessable_position_count": int(
            max(0, len(surviving_positions) - witnessable_position_count)
        ),
        "static_supported": bool(witnessable_position_count > 0),
    }


def _surviving_template_positions(
    model: Any,
    delegate: Any,
    *,
    template: str,
    blocked_cells: set[tuple[int, int]],
) -> tuple[set[tuple[int, int]], int]:
    positions: set[tuple[int, int]] = set()
    pose_count = 0
    for pose_idx, pose_tuple in sorted(
        dict(getattr(delegate, "_template_pose_tuple_by_idx", {}).get(str(template), {})).items()
    ):
        if not blocked_cells.isdisjoint(model._pose_cells(str(template), int(pose_idx))):
            continue
        try:
            x_val, y_val, _mode = pose_tuple
        except Exception:
            continue
        pose_count += 1
        positions.add((int(x_val), int(y_val)))
    return positions, int(pose_count)


def _coverable_powered_positions(
    pole_positions: set[tuple[int, int]],
    *,
    dims: tuple[int, int],
    radius: int,
    grid_w: int,
    grid_h: int,
) -> set[tuple[int, int]]:
    result: set[tuple[int, int]] = set()
    width, height = int(dims[0]), int(dims[1])
    for pole_x, pole_y in pole_positions:
        x_min = max(0, int(pole_x) - int(radius) - width + 1)
        x_max = min(int(grid_w) - 1, int(pole_x) + int(radius) + 1)
        y_min = max(0, int(pole_y) - int(radius) - height + 1)
        y_max = min(int(grid_h) - 1, int(pole_y) + int(radius) + 1)
        for x_val in range(x_min, x_max + 1):
            for y_val in range(y_min, y_max + 1):
                result.add((int(x_val), int(y_val)))
    return result


def _slot_summary(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_template: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {
            "slot_count": 0,
            "static_supported_slot_count": 0,
            "unsupported_slot_count": 0,
            "required_slot_count": 0,
            "required_unsupported_slot_count": 0,
        }
    )
    required_unsupported = 0
    optional_unsupported = 0
    witnessable_counts: list[int] = []
    for entry in entries:
        template = str(entry.get("template"))
        stats = by_template[template]
        stats["slot_count"] += 1
        if bool(entry.get("static_supported")):
            stats["static_supported_slot_count"] += 1
        else:
            stats["unsupported_slot_count"] += 1
        if bool(entry.get("support_required")):
            stats["required_slot_count"] += 1
            if not bool(entry.get("static_supported")):
                stats["required_unsupported_slot_count"] += 1
                required_unsupported += 1
        elif not bool(entry.get("static_supported")):
            optional_unsupported += 1
        witnessable_counts.append(int(entry.get("witnessable_position_count", 0)))
    return {
        "slot_count": int(len(entries)),
        "required_unsupported_slot_count": int(required_unsupported),
        "optional_unsupported_slot_count": int(optional_unsupported),
        "static_supported_slot_count": int(
            sum(1 for entry in entries if bool(entry.get("static_supported")))
        ),
        "min_witnessable_position_count": min(witnessable_counts) if witnessable_counts else 0,
        "max_witnessable_position_count": max(witnessable_counts) if witnessable_counts else 0,
        "by_template": {key: dict(value) for key, value in sorted(by_template.items())},
    }


def _anchor_classification(
    slot_summary: Mapping[str, Any],
    pole_positions: set[tuple[int, int]],
) -> str:
    if not pole_positions:
        return "pole_domain_empty"
    if int(slot_summary.get("required_unsupported_slot_count", 0)) > 0:
        return "witness_domain_static_support_missing"
    if int(slot_summary.get("optional_unsupported_slot_count", 0)) > 0:
        return "residual_optional_witness_domain_gaps_only"
    return "witness_domain_static_support_pass"


def _status_from_anchors(anchors: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not anchors:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "anchor_samples_missing",
        }
    classifications = {str(anchor.get("classification")) for anchor in anchors}
    if "pole_domain_empty" in classifications:
        outcome = "pole_domain_empty"
    elif "witness_domain_static_support_missing" in classifications:
        outcome = "witness_domain_static_support_missing"
    elif "residual_optional_witness_domain_gaps_only" in classifications:
        outcome = "residual_optional_witness_domain_gaps_only"
    elif classifications == {"witness_domain_static_support_pass"}:
        outcome = "witness_domain_static_support_pass"
    else:
        outcome = "witness_domain_probe_inconclusive"
    return {
        "completed": True,
        "evaluated": True,
        "outcome": outcome,
        "classification_counts": dict(Counter(str(anchor.get("classification")) for anchor in anchors)),
    }


def _summary(anchors: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    required_unsupported = 0
    optional_unsupported = 0
    for anchor in anchors:
        slot_summary = _mapping(anchor.get("powered_slot_summary"))
        required_unsupported += int(slot_summary.get("required_unsupported_slot_count", 0))
        optional_unsupported += int(slot_summary.get("optional_unsupported_slot_count", 0))
    return {
        "anchor_count": int(len(anchors)),
        "required_unsupported_slot_count": int(required_unsupported),
        "optional_unsupported_slot_count": int(optional_unsupported),
        "classification_counts": dict(Counter(str(anchor.get("classification")) for anchor in anchors)),
    }


def _recommendation(outcome: Any) -> str:
    if outcome == "witness_domain_static_support_pass":
        return (
            "Every inspected powered slot has at least one static power-pole witness "
            "domain under the forced anchor. The blocker is not a simple empty "
            "cover-choice domain; next isolate dynamic coupling between active pole "
            "selection, no-overlap, and power-coverage witness choices."
        )
    if outcome == "witness_domain_static_support_missing":
        return (
            "At least one required powered slot has no static witness support under "
            "the forced anchor. Inspect unsupported_required_slots before any runtime promotion."
        )
    if outcome == "residual_optional_witness_domain_gaps_only":
        return (
            "Required powered slots have static support, but some residual optional "
            "powered slots do not. Compare these slots against required optional "
            "cardinality before deciding whether this can block certification."
        )
    if outcome == "pole_domain_empty":
        return "No surviving power-pole positions remain under the forced anchor."
    if outcome == "campaign_state_missing":
        return "Campaign state is missing; run B5A or provide a workspace campaign state."
    if outcome == "candidate_missing":
        return "Candidate is missing from campaign state."
    if outcome == "anchor_samples_missing":
        return "No anchor sample was selected; provide --anchor-indices."
    if outcome == "diagnostic_error":
        return "Witness-domain diagnostic failed; inspect model_error."
    return "Witness-domain diagnostic is inconclusive."


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
    required_unsupported = sum(
        int(_mapping(anchor.get("powered_slot_summary")).get("required_unsupported_slot_count", 0))
        for anchor in anchors
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
            "anchor_selected",
            "pass" if selected_anchor_count > 0 else "fail",
            f"selected_anchor_count={selected_anchor_count}",
        ),
        _check(
            "required_slots_have_static_witness_support",
            "pass" if required_unsupported == 0 and bool(status.get("evaluated")) else "fail",
            f"required_unsupported_slot_count={required_unsupported}",
        ),
        _check(
            "campaign_state_unchanged",
            "pass" if campaign_state_unchanged else "fail",
            f"campaign_state_unchanged={campaign_state_unchanged}",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _load_json_mapping(path: Path) -> tuple[Optional[Mapping[str, Any]], Optional[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except Exception as exc:
        return None, str(exc)
    if not isinstance(payload, Mapping):
        return None, "json root is not an object"
    return payload, None


def _markdown_cell(value: Any) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")
