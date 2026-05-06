from __future__ import annotations

import math
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    _candidate_ghost_rect,
    _check,
    _display_path,
    _file_hash,
    _load_json_mapping,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
)
from src.search.phase3b_forced_anchor_model_slice import _build_exact_overlay

PROTOCOL_WITNESS_PREFIX_AUDIT_SOURCE = "phase3b_protocol_witness_prefix_audit_v1"
DEFAULT_CANDIDATE = "67x13"
DEFAULT_INDEX_RESTRICT_PATH = Path(
    ".artifacts/phase3b_forced_anchor_proto_reduction_protocol_index_restrict_anchor119_presolve_on_40s/forced_anchor_proto_reduction.json"
)
DEFAULT_PREFIX_THRESHOLD_PATH = Path(
    ".artifacts/phase3b_forced_anchor_proto_reduction_protocol_prefix_threshold_anchor119_presolve_on_40s/forced_anchor_proto_reduction.json"
)
DEFAULT_LOOKUP_INTACT_PREFIX_PATH = Path(
    ".artifacts/phase3b_forced_anchor_proto_reduction_protocol_prefix_lookup_intact_anchor119_presolve_on_40s/forced_anchor_proto_reduction.json"
)
DEFAULT_WINDOW_RESTRICT_PATH = Path(
    ".artifacts/phase3b_forced_anchor_proto_reduction_protocol_index_window256_anchor119_presolve_on_40s/forced_anchor_proto_reduction.json"
)
DEFAULT_ACTIVE_PREFIX_GUARD_PATH = Path(
    ".artifacts/phase3b_forced_anchor_proto_reduction_protocol_active_prefix_guard_anchor119_presolve_on_40s/forced_anchor_proto_reduction.json"
)


def build_phase3b_protocol_witness_prefix_audit(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 1,
    anchor_indices: Optional[Sequence[int]] = None,
    index_restrict_path: Optional[Path] = None,
    prefix_threshold_path: Optional[Path] = None,
    lookup_intact_prefix_path: Optional[Path] = None,
    window_restrict_path: Optional[Path] = None,
    active_prefix_guard_path: Optional[Path] = None,
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
        "recommendation": "Protocol witness-prefix audit has not run.",
    }
    model_error: Optional[str] = None
    overlay_summary: Dict[str, Any] = {}
    evidence: Dict[str, Any] = {}
    analysis: Dict[str, Any] = {}

    artifact_paths = {
        "index_restrict": _resolve_path(
            project_root,
            index_restrict_path if index_restrict_path is not None else DEFAULT_INDEX_RESTRICT_PATH,
        ),
        "prefix_threshold": _resolve_path(
            project_root,
            prefix_threshold_path
            if prefix_threshold_path is not None
            else DEFAULT_PREFIX_THRESHOLD_PATH,
        ),
        "lookup_intact_prefix": _resolve_path(
            project_root,
            lookup_intact_prefix_path
            if lookup_intact_prefix_path is not None
            else DEFAULT_LOOKUP_INTACT_PREFIX_PATH,
        ),
        "window_restrict": _resolve_path(
            project_root,
            window_restrict_path if window_restrict_path is not None else DEFAULT_WINDOW_RESTRICT_PATH,
        ),
        "active_prefix_guard": _resolve_path(
            project_root,
            active_prefix_guard_path
            if active_prefix_guard_path is not None
            else DEFAULT_ACTIVE_PREFIX_GUARD_PATH,
        ),
    }

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before protocol witness-prefix audit.",
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
            overlay_summary = _overlay_summary(model)
            evidence = _load_evidence(project_root, artifact_paths)
            analysis = _analyze_prefix_evidence(evidence, overlay_summary)
            status.update(_status_from_analysis(analysis, evidence))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Protocol witness-prefix audit failed; inspect model_error before using this evidence.",
                }
            )

    after_hash = _file_hash(campaign_path)
    return {
        "metadata": {
            "source": PROTOCOL_WITNESS_PREFIX_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "artifact_join_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
            "index_restrict": _display_path(project_root, artifact_paths["index_restrict"]),
            "prefix_threshold": _display_path(project_root, artifact_paths["prefix_threshold"]),
            "lookup_intact_prefix": _display_path(
                project_root,
                artifact_paths["lookup_intact_prefix"],
            ),
            "window_restrict": _display_path(project_root, artifact_paths["window_restrict"]),
            "active_prefix_guard": _display_path(project_root, artifact_paths["active_prefix_guard"]),
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
        "overlay": overlay_summary,
        "evidence": evidence,
        "analysis": analysis,
        "status": status,
        "model_error": model_error,
        "campaign_state_unchanged": bool(before_hash == after_hash),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            evidence=evidence,
            status=status,
            model_error=model_error,
            campaign_state_unchanged=before_hash == after_hash,
        ),
    }


def render_phase3b_protocol_witness_prefix_audit_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    analysis = _mapping(report.get("analysis"))
    overlay = _mapping(report.get("overlay"))
    lines = [
        "# Phase 3B Protocol Witness Prefix Audit",
        "",
        "- Diagnostic semantics: artifact_join_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Power-pole slots: {overlay.get('power_pole_slot_count')}",
        f"- Protocol slots: {overlay.get('protocol_slot_count')}",
        f"- Best terminal first-prefix limit: {analysis.get('best_terminal_first_limit')}",
        f"- Active-prefix guard outcome: {analysis.get('active_prefix_guard_outcome')}",
        f"- Lookup-intact prefix outcome: {analysis.get('lookup_intact_prefix_outcome')}",
        "",
        "## Family Prefix Capacity",
        "",
        f"- Diagnostic status: {_mapping(analysis.get('family_prefix_capacity_assessment')).get('status')}",
        f"- Detail: {_mapping(analysis.get('family_prefix_capacity_assessment')).get('detail')}",
        f"- First ordered family: {_mapping(_mapping(overlay.get('family_prefix_capacity')).get('first_ordered_family')).get('family')}",
        f"- First-family min slots for all demands: {_mapping(_mapping(overlay.get('family_prefix_capacity')).get('first_ordered_family')).get('minimum_slots_for_all_demands')}",
        "",
        "## Prefix Evidence",
        "",
        "| Mode | Window | Status | Branches | Conflicts | Wall |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for entry in list(analysis.get("prefix_entries", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("mode")),
                    _markdown_cell(entry.get("window_label")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("branches")),
                    _markdown_cell(entry.get("conflicts")),
                    _markdown_cell(entry.get("wall_time")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Proof Safety",
            "",
            "| Candidate | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for item in list(analysis.get("proof_safety", [])):
        if not isinstance(item, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(item.get("candidate")),
                    _markdown_cell(item.get("status")),
                    _markdown_cell(item.get("detail")),
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


def render_phase3b_protocol_witness_prefix_audit_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    analysis = _mapping(report.get("analysis"))
    overlay = _mapping(report.get("overlay"))
    lines = [
        "Phase 3B protocol witness prefix audit",
        "diagnostic_semantics=artifact_join_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"power_pole_slots={overlay.get('power_pole_slot_count')}",
        f"protocol_slots={overlay.get('protocol_slot_count')}",
        f"best_terminal_first_limit={analysis.get('best_terminal_first_limit')}",
        f"active_prefix_guard_outcome={analysis.get('active_prefix_guard_outcome')}",
        f"lookup_intact_prefix_outcome={analysis.get('lookup_intact_prefix_outcome')}",
        f"family_prefix_capacity_status={_mapping(analysis.get('family_prefix_capacity_assessment')).get('status')}",
        f"first_ordered_family={_mapping(_mapping(overlay.get('family_prefix_capacity')).get('first_ordered_family')).get('family')}",
        f"first_family_min_slots_for_all_demands={_mapping(_mapping(overlay.get('family_prefix_capacity')).get('first_ordered_family')).get('minimum_slots_for_all_demands')}",
    ]
    for entry in list(analysis.get("prefix_entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "prefix_entry="
                f"mode={entry.get('mode')} "
                f"window={entry.get('window_label')} "
                f"status={entry.get('status')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')}"
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


def _overlay_summary(model: Any) -> Dict[str, Any]:
    delegate = getattr(model, "_coordinate_delegate", None)
    residual = getattr(delegate, "residual_optional_slots", {}) if delegate is not None else {}
    gvi = _mapping(_mapping(getattr(model, "build_stats", {})).get("global_valid_inequalities"))
    optional = _mapping(gvi.get("optional_cardinality_bounds"))
    power_pole_optional = _mapping(optional.get("power_pole"))
    protocol_optional = _mapping(optional.get("protocol_storage_box"))
    symmetry = _mapping(_mapping(getattr(model, "build_stats", {})).get("coordinate_symmetry"))
    return {
        "power_pole_slot_count": int(len(list(_mapping(residual).get("power_pole", [])))),
        "protocol_slot_count": int(len(list(_mapping(residual).get("protocol_storage_box", [])))),
        "protocol_required_lower_bound": _int_or_none(protocol_optional.get("lower")),
        "protocol_slot_pool_upper_bound": _int_or_none(protocol_optional.get("slot_pool_upper_bound")),
        "power_pole_slot_pool_upper_bound": _int_or_none(power_pole_optional.get("slot_pool_upper_bound")),
        "power_pole_upper_mode": power_pole_optional.get("mode"),
        "prefix_activity_ordering_present": True,
        "power_pole_family_order_constraints": _int_or_none(
            symmetry.get("power_pole_family_order_constraints")
        ),
        "family_prefix_capacity": _family_prefix_capacity_summary(model),
    }


def _family_prefix_capacity_summary(model: Any) -> Dict[str, Any]:
    delegate = getattr(model, "_coordinate_delegate", None)
    if delegate is None:
        return {
            "present": False,
            "reason": "coordinate_delegate_missing",
            "proof_safety": "diagnostic_capacity_explanation_not_proof_source",
        }
    gvi = _mapping(_mapping(getattr(model, "build_stats", {})).get("global_valid_inequalities"))
    demands = {
        str(template): int(demand)
        for template, demand in sorted(dict(gvi.get("powered_template_demands", {})).items())
    }
    family_order = [str(family) for family in list(getattr(delegate, "_power_pole_family_order", []) or [])]
    coefficients_by_family = dict(getattr(delegate, "_power_pole_family_coefficients", {}) or {})
    pose_counts = dict(getattr(delegate, "_power_pole_family_pose_counts", {}) or {})
    if not demands:
        return {
            "present": False,
            "reason": "powered_template_demands_missing",
            "proof_safety": "diagnostic_capacity_explanation_not_proof_source",
        }
    if not family_order:
        return {
            "present": False,
            "reason": "power_pole_family_order_missing",
            "proof_safety": "diagnostic_capacity_explanation_not_proof_source",
        }

    cumulative_capacity = {template: 0 for template in demands}
    cumulative_slot_upper_bound = 0
    first_meeting_by_template: Dict[str, Dict[str, Any]] = {}
    first_meeting_all: Optional[Dict[str, Any]] = None
    sample: list[Dict[str, Any]] = []
    for order_index, family in enumerate(family_order):
        upper_bound = _family_count_upper_bound(delegate, family, pose_counts)
        coefficients = {
            template: int(_mapping(coefficients_by_family.get(family)).get(template, 0))
            for template in demands
        }
        cumulative_slot_upper_bound += int(upper_bound)
        for template, demand in demands.items():
            cumulative_capacity[template] += int(upper_bound) * int(coefficients[template])
            if (
                template not in first_meeting_by_template
                and int(cumulative_capacity[template]) >= int(demand)
            ):
                first_meeting_by_template[template] = {
                    "family_prefix_count": int(order_index) + 1,
                    "slot_prefix_upper_bound": int(cumulative_slot_upper_bound),
                    "family": family,
                    "capacity": int(cumulative_capacity[template]),
                    "demand": int(demand),
                }
        if first_meeting_all is None and all(
            int(cumulative_capacity[template]) >= int(demand)
            for template, demand in demands.items()
        ):
            first_meeting_all = {
                "family_prefix_count": int(order_index) + 1,
                "slot_prefix_upper_bound": int(cumulative_slot_upper_bound),
                "family": family,
                "capacities": dict(cumulative_capacity),
                "demands": dict(demands),
            }
        if len(sample) < 12:
            sample.append(
                {
                    "order_index": int(order_index),
                    "family": family,
                    "pose_count": int(pose_counts.get(family, 0)),
                    "count_var_upper_bound": int(upper_bound),
                    "coefficients": coefficients,
                    "cumulative_slot_upper_bound": int(cumulative_slot_upper_bound),
                    "cumulative_capacity": dict(cumulative_capacity),
                }
            )

    first_family_name = str(family_order[0])
    first_family_coefficients = {
        template: int(_mapping(coefficients_by_family.get(first_family_name)).get(template, 0))
        for template in demands
    }
    first_family_min_slots_by_template = {
        template: _minimum_slots_for_demand(int(demand), int(first_family_coefficients[template]))
        for template, demand in demands.items()
    }
    first_family_min_slots = _max_optional_int(first_family_min_slots_by_template.values())
    first_family = {
        "family": first_family_name,
        "pose_count": int(pose_counts.get(first_family_name, 0)),
        "count_var_upper_bound": int(
            _family_count_upper_bound(delegate, first_family_name, pose_counts)
        ),
        "coefficients": first_family_coefficients,
        "minimum_slots_by_template": first_family_min_slots_by_template,
        "minimum_slots_for_all_demands": first_family_min_slots,
        "can_cover_all_demands_by_coefficients": first_family_min_slots is not None,
    }
    return {
        "present": True,
        "capacity_mode": "ordered_family_count_upper_bound_overapprox",
        "proof_safety": "diagnostic_capacity_explanation_not_proof_source",
        "family_count": int(len(family_order)),
        "demands": demands,
        "first_ordered_family": first_family,
        "first_prefix_meeting_demands_by_template": dict(sorted(first_meeting_by_template.items())),
        "first_prefix_meeting_all_demands_by_upper_bounds": first_meeting_all,
        "family_order_sample": sample,
        "note": (
            "Capacity lower bounds explain why a small first-prefix can stay feasible, "
            "but they do not prove a universal witness-index cap."
        ),
    }


def _family_count_upper_bound(
    delegate: Any,
    family: str,
    pose_counts: Mapping[str, Any],
) -> int:
    upper_bound_fn = getattr(delegate, "_power_pole_family_count_upper_bound", None)
    if callable(upper_bound_fn):
        try:
            return int(upper_bound_fn(str(family)))
        except Exception:
            pass
    return int(pose_counts.get(str(family), 0))


def _minimum_slots_for_demand(demand: int, coefficient: int) -> Optional[int]:
    if int(demand) <= 0:
        return 0
    if int(coefficient) <= 0:
        return None
    return int(math.ceil(int(demand) / int(coefficient)))


def _max_optional_int(values: Sequence[Optional[int]]) -> Optional[int]:
    concrete = [int(value) for value in values if value is not None]
    if len(concrete) != len(list(values)):
        return None
    return max(concrete) if concrete else 0


def _load_evidence(project_root: Path, paths: Mapping[str, Path]) -> Dict[str, Any]:
    evidence: Dict[str, Any] = {}
    for key, path in sorted(paths.items()):
        payload, error = _load_json_mapping(path)
        entries = []
        if payload is not None and error is None:
            entries = _extract_prefix_entries(payload)
        evidence[str(key)] = {
            "path": _display_path(project_root, path),
            "present": payload is not None and error is None,
            "load_error": error,
            "entry_count": int(len(entries)),
            "entries": entries,
            "status": dict(_mapping(_mapping(payload or {}).get("status"))),
        }
    return evidence


def _extract_prefix_entries(payload: Mapping[str, Any]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    reduction = _mapping(payload.get("reduction"))
    for entry in list(reduction.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        variant = str(entry.get("variant"))
        if (
            "restrict_template_index" not in variant
            and "active_prefix_guard" not in variant
            and "except_template_protocol_storage_box_and_family_lookup_table" not in variant
            and "except_template_protocol_storage_box_keep_family_lookup_table" not in variant
        ):
            continue
        replacement = _mapping(entry.get("replacement_payload"))
        variant_restriction = _restriction_from_variant(variant)
        lower_bound = _coalesce_int(
            replacement.get("lower_bound"),
            variant_restriction.get("lower_bound"),
        )
        upper_bound = _coalesce_int(
            replacement.get("upper_bound"),
            variant_restriction.get("upper_bound"),
        )
        window_width = _coalesce_int(
            replacement.get("window_width"),
            variant_restriction.get("window_width"),
        )
        parsed = _mapping(entry.get("response_stats_parsed"))
        result.append(
            {
                "variant": variant,
                "mode": _prefix_mode(variant, replacement, variant_restriction),
                "window_label": _window_label(
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    fallback=str(variant_restriction.get("window_label", "n/a")),
                ),
                "status": str(entry.get("status")),
                "branches": _int_or_zero(entry.get("branches")),
                "conflicts": _int_or_zero(entry.get("conflicts")),
                "wall_time": _float_or_none(entry.get("wall_time")),
                "deterministic_time": _float_or_none(entry.get("deterministic_time")),
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "window_width": window_width,
                "added_constraint_count": _int_or_zero(replacement.get("added_constraint_count")),
                "family_lookup_table_removed": _family_lookup_table_removed_from_variant(variant),
                "parsed_status": parsed.get("status"),
            }
        )
    return result


def _analyze_prefix_evidence(
    evidence: Mapping[str, Any],
    overlay: Mapping[str, Any],
) -> Dict[str, Any]:
    all_entries: list[Dict[str, Any]] = []
    for payload in evidence.values():
        for entry in list(_mapping(payload).get("entries", [])):
            if isinstance(entry, Mapping):
                all_entries.append(dict(entry))
    terminal_first_limits = [
        int(entry["upper_bound"]) + 1
        for entry in all_entries
        if entry.get("mode") == "first"
        and str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"}
        and entry.get("upper_bound") is not None
    ]
    active_guard_entries = [
        entry for entry in all_entries if entry.get("mode") == "active_prefix_guard"
    ]
    lookup_intact_entries = [
        entry
        for entry in all_entries
        if entry.get("family_lookup_table_removed") is False
        and str(entry.get("mode")) in {"first", "last", "window", "unrestricted_protocol_lookup_intact"}
    ]
    unrestricted_zero_branch = any(
        entry.get("mode") == "unrestricted_protocol"
        and str(entry.get("status")) == "UNKNOWN"
        and _int_or_zero(entry.get("branches")) == 0
        and _int_or_zero(entry.get("conflicts")) == 0
        for entry in all_entries
    )
    active_guard_outcome = "missing"
    if active_guard_entries:
        guard = active_guard_entries[0]
        if str(guard.get("status")) == "UNKNOWN" and _int_or_zero(guard.get("branches")) == 0:
            active_guard_outcome = "zero_branch_unknown"
        elif _int_or_zero(guard.get("branches")) > 0 or _int_or_zero(guard.get("conflicts")) > 0:
            active_guard_outcome = "search_progress"
        else:
            active_guard_outcome = str(guard.get("status"))
    status_counts = Counter(str(entry.get("status")) for entry in all_entries)
    proof_safety = [
        {
            "candidate": "fixed_first_n_prefix",
            "status": "diagnostic_only",
            "detail": "First-N unlocks search/terminal behavior, but a fixed prefix is not proof-safe without a semantic derivation.",
        },
        {
            "candidate": "active_prefix_guard",
            "status": "proof_safe_but_ineffective",
            "detail": "The redundant guard is consistent with active-prefix ordering, but current evidence shows it remains zero-branch.",
        },
        {
            "candidate": "semantic_prefix_domain_shrink",
            "status": "next_candidate",
            "detail": "Window sensitivity suggests any production candidate must derive the prefix/domain from ordering, family capacity, or witness support semantics.",
        },
    ]
    family_capacity_assessment = _family_prefix_capacity_assessment(
        overlay,
        best_terminal_first_limit=min(terminal_first_limits) if terminal_first_limits else None,
    )
    proof_safety.append(
        {
            "candidate": "family_order_capacity_prefix",
            "status": str(family_capacity_assessment.get("status")),
            "detail": str(family_capacity_assessment.get("detail")),
        }
    )
    lookup_intact_assessment = _lookup_intact_prefix_assessment(
        lookup_intact_entries,
        best_terminal_first_limit=min(terminal_first_limits) if terminal_first_limits else None,
    )
    proof_safety.append(
        {
            "candidate": "prefix_shrink_with_family_lookup_intact",
            "status": str(lookup_intact_assessment.get("status")),
            "detail": str(lookup_intact_assessment.get("detail")),
        }
    )
    return {
        "prefix_entries": sorted(
            all_entries,
            key=lambda item: (
                str(item.get("mode")),
                _int_or_zero(item.get("lower_bound")),
                _int_or_zero(item.get("upper_bound")),
                str(item.get("variant")),
            ),
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "best_terminal_first_limit": min(terminal_first_limits) if terminal_first_limits else None,
        "unrestricted_protocol_zero_branch": bool(unrestricted_zero_branch),
        "active_prefix_guard_outcome": active_guard_outcome,
        "lookup_intact_prefix_outcome": lookup_intact_assessment.get("outcome"),
        "lookup_intact_prefix_assessment": lookup_intact_assessment,
        "family_prefix_capacity_assessment": family_capacity_assessment,
        "proof_safety": proof_safety,
    }


def _family_prefix_capacity_assessment(
    overlay: Mapping[str, Any],
    *,
    best_terminal_first_limit: Optional[int],
) -> Dict[str, Any]:
    family_capacity = _mapping(overlay.get("family_prefix_capacity"))
    if not bool(family_capacity.get("present")):
        return {
            "status": "missing",
            "detail": str(family_capacity.get("reason", "family prefix capacity unavailable")),
        }
    first_family = _mapping(family_capacity.get("first_ordered_family"))
    minimum_slots = _int_or_none(first_family.get("minimum_slots_for_all_demands"))
    if minimum_slots is None:
        return {
            "status": "inconclusive",
            "detail": "First ordered family cannot cover all demand coefficients by itself.",
        }
    if best_terminal_first_limit is None:
        return {
            "status": "capacity_explains_feasible_prefix_only",
            "detail": (
                f"First ordered family needs at least {minimum_slots} slots by coefficient demand, "
                "but no terminal first-prefix limit is present for comparison."
            ),
        }
    if int(best_terminal_first_limit) >= int(minimum_slots):
        return {
            "status": "capacity_consistent_with_terminal_prefix",
            "detail": (
                f"Best terminal first-prefix limit {int(best_terminal_first_limit)} is above "
                f"the first-family coefficient minimum {int(minimum_slots)}; this explains "
                "feasibility pressure but is not proof-safe as a witness cap."
            ),
        }
    return {
        "status": "capacity_smaller_than_terminal_prefix",
        "detail": (
            f"Best terminal first-prefix limit {int(best_terminal_first_limit)} is below "
            f"the first-family coefficient minimum {int(minimum_slots)}; this points to diagnostic "
            "decoupling such as family-table removal or index-domain simplification, not a "
            "proof-safe capacity rule."
        ),
    }


def _status_from_analysis(
    analysis: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> Dict[str, Any]:
    present_count = sum(1 for item in evidence.values() if bool(_mapping(item).get("present")))
    if present_count <= 0:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "prefix_evidence_missing",
            "recommendation": "Prefix evidence artifacts are missing; run protocol index restriction diagnostics first.",
        }
    if analysis.get("best_terminal_first_limit") is not None:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "semantic_prefix_shrink_candidate",
            "recommendation": "First-prefix shrink is effective but not proof-safe as a fixed N; derive a semantic prefix/domain rule before production use.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "prefix_evidence_inconclusive",
        "recommendation": "Prefix evidence is present but no terminal first-prefix result was found; continue diagnostic matrix before changing formulation.",
    }


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    selected_anchor_count: int,
    evidence: Mapping[str, Any],
    status: Mapping[str, Any],
    model_error: Optional[str],
    campaign_state_unchanged: bool,
) -> list[Dict[str, str]]:
    present_count = sum(1 for item in evidence.values() if bool(_mapping(item).get("present")))
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
            "prefix_evidence_present",
            "pass" if present_count > 0 else "fail",
            f"present_artifact_count={int(present_count)}",
        ),
        _check(
            "prefix_audit_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
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


def _prefix_mode(
    variant: str,
    replacement: Mapping[str, Any],
    variant_restriction: Mapping[str, Any],
) -> str:
    if "add_template_index_active_prefix_guard" in str(variant):
        return "active_prefix_guard"
    if "except_template_protocol_storage_box_keep_family_lookup_table" in str(variant):
        return "unrestricted_protocol_lookup_intact"
    if "except_template_protocol_storage_box_and_family_lookup_table" in str(variant):
        return "unrestricted_protocol"
    mode = replacement.get("restriction_mode")
    if mode is not None:
        return str(mode)
    variant_mode = variant_restriction.get("mode")
    return str(variant_mode) if variant_mode is not None else "other"


def _family_lookup_table_removed_from_variant(variant: str) -> bool:
    return str(variant).endswith("_and_family_lookup_table")


def _lookup_intact_prefix_assessment(
    entries: Sequence[Mapping[str, Any]],
    *,
    best_terminal_first_limit: Optional[int],
) -> Dict[str, Any]:
    if not entries:
        return {
            "status": "missing",
            "outcome": "missing",
            "detail": "No lookup-intact prefix evidence is present.",
        }
    progress_entries = [
        entry
        for entry in entries
        if _int_or_zero(entry.get("branches")) > 0 or _int_or_zero(entry.get("conflicts")) > 0
    ]
    terminal_entries = [
        entry for entry in entries if str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"}
    ]
    zero_branch_entries = [
        entry
        for entry in entries
        if str(entry.get("status")) == "UNKNOWN"
        and _int_or_zero(entry.get("branches")) == 0
        and _int_or_zero(entry.get("conflicts")) == 0
    ]
    if terminal_entries:
        return {
            "status": "prefix_effective_with_lookup_intact",
            "outcome": "terminal",
            "detail": f"{len(terminal_entries)} lookup-intact prefix entries reached terminal status.",
        }
    if progress_entries:
        return {
            "status": "prefix_breaks_zero_branch_with_lookup_intact",
            "outcome": "search_progress",
            "detail": f"{len(progress_entries)} lookup-intact prefix entries reached search progress.",
        }
    if len(zero_branch_entries) == len(list(entries)) and best_terminal_first_limit is not None:
        return {
            "status": "prefix_requires_family_lookup_change",
            "outcome": "zero_branch_unknown",
            "detail": (
                f"All {len(zero_branch_entries)} lookup-intact prefix entries remain zero-branch UNKNOWN, "
                f"while family-lookup-removed evidence reaches terminal first-prefix {int(best_terminal_first_limit)}."
            ),
        }
    if zero_branch_entries:
        return {
            "status": "lookup_intact_zero_branch_remaining",
            "outcome": "zero_branch_unknown",
            "detail": f"{len(zero_branch_entries)} lookup-intact prefix entries remain zero-branch UNKNOWN.",
        }
    return {
        "status": "inconclusive",
        "outcome": "inconclusive",
        "detail": "Lookup-intact prefix entries are present but do not show a clear terminal/progress/zero-branch pattern.",
    }


def _window_label(
    *,
    lower_bound: Optional[int],
    upper_bound: Optional[int],
    fallback: str,
) -> str:
    lower = lower_bound
    upper = upper_bound
    if lower is None or upper is None:
        return str(fallback or "n/a")
    return f"{int(lower)}..{int(upper)}"


def _restriction_from_variant(variant: str) -> Dict[str, Any]:
    first_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"[A-Za-z0-9_]+_and_restrict_template_index_first_(\d+)"
        r"(?:_and_family_lookup_table)?$",
        str(variant),
    )
    if first_match is not None:
        limit = max(1, int(first_match.group(1)))
        return {
            "mode": "first",
            "lower_bound": 0,
            "upper_bound": int(limit) - 1,
            "window_width": int(limit),
            "window_label": f"0..{int(limit) - 1}",
        }
    last_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"[A-Za-z0-9_]+_and_restrict_template_index_last_(\d+)"
        r"(?:_and_family_lookup_table)?$",
        str(variant),
    )
    if last_match is not None:
        limit = max(1, int(last_match.group(1)))
        return {
            "mode": "last",
            "window_width": int(limit),
            "window_label": f"last_{int(limit)}",
        }
    window_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"[A-Za-z0-9_]+_and_restrict_template_index_window_(\d+)_(\d+)"
        r"(?:_and_family_lookup_table)?$",
        str(variant),
    )
    if window_match is not None:
        start = max(0, int(window_match.group(1)))
        count = max(1, int(window_match.group(2)))
        return {
            "mode": "window",
            "lower_bound": int(start),
            "upper_bound": int(start) + int(count) - 1,
            "window_width": int(count),
            "window_label": f"{int(start)}..{int(start) + int(count) - 1}",
        }
    return {}


def _coalesce_int(*values: Any) -> Optional[int]:
    for value in values:
        converted = _int_or_none(value)
        if converted is not None:
            return int(converted)
    return None


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _float_or_none(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _markdown_cell(value: Any) -> str:
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return text
