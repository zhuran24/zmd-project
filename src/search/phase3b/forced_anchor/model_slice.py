from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from ortools.sat.python import cp_model

from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    MasterPlacementModel,
    load_generic_io_requirements_artifact,
    load_project_data,
)
from src.models._cpsat_compat import cp_model_from_proto
from src.models.master_model import _clone_model_proto
from src.search.exact_campaign import now_iso
from src.search.phase3b.forced_anchor.master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
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

FORCED_ANCHOR_MODEL_SLICE_SOURCE = "phase3b_forced_anchor_model_slice_diagnostic_v1"
DEFAULT_SLICE_VARIANTS = (
    "base",
    "residual_all_inactive",
    "protocol_boxes_inactive",
    "power_poles_inactive",
    "skip_power_coverage_core",
)
DEFAULT_SLICE_SOLVER_PARAMETER_PROFILE = {
    "profile_id": "portfolio_probe3_sym3_4w",
    "search_branching": "portfolio",
    "cp_model_probing_level": 3,
    "symmetry_level": 3,
    "worker_count": 4,
    "hint_conflict_limit": 1000,
}
ALLOWED_SLICE_VARIANTS = (
    *DEFAULT_SLICE_VARIANTS,
    "no_protocol_lower_bound_core",
    "skip_power_coverage_no_protocol_lower_bound_core",
    "skip_power_coverage_no_protocol_lower_bound_core_residual_all_inactive",
    "target_power_family_bound_relaxed",
    "target_power_family_bound_relaxed_protocol_boxes_inactive",
    "target_power_family_bound_direct_after_force",
    "target_power_family_bound_direct_after_force_protocol_boxes_inactive",
    "all_conditioned_family_bounds_direct_after_force",
    "all_conditioned_family_bounds_direct_after_force_protocol_boxes_inactive",
    "power_coverage_active_requirement_relaxed",
    "power_coverage_geometry_bounds_relaxed",
    "power_coverage_active_and_geometry_relaxed",
    "power_coverage_witness_element_relaxed",
    "power_coverage_witness_element_and_linear_relaxed",
    "power_pole_no_overlap_relaxed",
    "power_coverage_dynamic_coupling_relaxed",
    "power_coverage_dynamic_and_family_count_relaxed",
    "power_coverage_dynamic_and_family_membership_count_relaxed",
    "power_coverage_dynamic_and_family_table_relaxed",
    "power_coverage_dynamic_and_family_linear_relaxed",
    "power_coverage_dynamic_and_family_sentinel_relaxed",
    "power_coverage_dynamic_and_family_membership_linear_relaxed",
    "power_coverage_dynamic_and_family_ordering_linear_relaxed",
    "power_coverage_dynamic_and_family_other_linear_relaxed",
    "power_coverage_dynamic_and_family_lookup_relaxed",
    "power_coverage_dynamic_and_family_distance_relaxed",
    "power_coverage_dynamic_and_family_lookup_distance_relaxed",
    "power_coverage_dynamic_and_family_assignment_relaxed",
    "power_coverage_dynamic_family_assignment_and_gvi_relaxed",
    "family_active_domain_channeling_added",
    "family_membership_active_channeling_added",
    "family_active_and_membership_channeling_added",
    "family_shell_pair_tables_added",
    "power_coverage_dynamic_and_family_shell_pair_tables_added",
    "family_lookup_rebuilt_channeling",
    "power_coverage_dynamic_and_family_lookup_rebuilt_channeling",
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only",
    "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only",
    "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only",
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_shell_pair",
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_ordering",
    "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_ordering",
    "power_capacity_gvi_protocol_storage_box_relaxed",
    "power_capacity_gvi_mandatory_templates_relaxed",
    "power_capacity_gvi_all_relaxed",
    "power_family_count_constraints_relaxed",
    "power_family_membership_and_count_constraints_relaxed",
    "power_family_assignment_layer_relaxed",
)
TARGET_POWER_FAMILY_BOUND_RELAXED_VARIANTS = {
    "target_power_family_bound_relaxed",
    "target_power_family_bound_relaxed_protocol_boxes_inactive",
}
TARGET_POWER_FAMILY_BOUND_REWRITE_VARIANTS = {
    *TARGET_POWER_FAMILY_BOUND_RELAXED_VARIANTS,
    "target_power_family_bound_direct_after_force",
    "target_power_family_bound_direct_after_force_protocol_boxes_inactive",
}
TARGET_POWER_FAMILY_BOUND_DIRECT_VARIANTS = {
    "target_power_family_bound_direct_after_force",
    "target_power_family_bound_direct_after_force_protocol_boxes_inactive",
}
ALL_CONDITIONED_FAMILY_BOUND_DIRECT_VARIANTS = {
    "all_conditioned_family_bounds_direct_after_force",
    "all_conditioned_family_bounds_direct_after_force_protocol_boxes_inactive",
}
POWER_COVERAGE_LINEAR_RELAXATION_VARIANTS = {
    "power_coverage_active_requirement_relaxed",
    "power_coverage_geometry_bounds_relaxed",
    "power_coverage_active_and_geometry_relaxed",
}
POWER_COVERAGE_DYNAMIC_RELAXATION_VARIANTS = {
    "power_coverage_witness_element_relaxed",
    "power_coverage_witness_element_and_linear_relaxed",
    "power_pole_no_overlap_relaxed",
    "power_coverage_dynamic_coupling_relaxed",
    "power_coverage_dynamic_and_family_count_relaxed",
    "power_coverage_dynamic_and_family_membership_count_relaxed",
    "power_coverage_dynamic_and_family_table_relaxed",
    "power_coverage_dynamic_and_family_linear_relaxed",
    "power_coverage_dynamic_and_family_sentinel_relaxed",
    "power_coverage_dynamic_and_family_membership_linear_relaxed",
    "power_coverage_dynamic_and_family_ordering_linear_relaxed",
    "power_coverage_dynamic_and_family_other_linear_relaxed",
    "power_coverage_dynamic_and_family_lookup_relaxed",
    "power_coverage_dynamic_and_family_distance_relaxed",
    "power_coverage_dynamic_and_family_lookup_distance_relaxed",
    "power_coverage_dynamic_and_family_assignment_relaxed",
    "power_coverage_dynamic_family_assignment_and_gvi_relaxed",
    "power_coverage_dynamic_and_family_shell_pair_tables_added",
    "power_coverage_dynamic_and_family_lookup_rebuilt_channeling",
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only",
    "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only",
    "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only",
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_shell_pair",
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_ordering",
    "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_ordering",
}
POWER_CAPACITY_GVI_RELAXATION_VARIANTS = {
    "power_capacity_gvi_protocol_storage_box_relaxed",
    "power_capacity_gvi_mandatory_templates_relaxed",
    "power_capacity_gvi_all_relaxed",
}
POWER_FAMILY_LAYER_RELAXATION_VARIANTS = {
    "power_family_count_constraints_relaxed",
    "power_family_membership_and_count_constraints_relaxed",
    "power_family_assignment_layer_relaxed",
    "power_coverage_dynamic_and_family_count_relaxed",
    "power_coverage_dynamic_and_family_membership_count_relaxed",
    "power_coverage_dynamic_and_family_table_relaxed",
    "power_coverage_dynamic_and_family_linear_relaxed",
    "power_coverage_dynamic_and_family_sentinel_relaxed",
    "power_coverage_dynamic_and_family_membership_linear_relaxed",
    "power_coverage_dynamic_and_family_ordering_linear_relaxed",
    "power_coverage_dynamic_and_family_other_linear_relaxed",
    "power_coverage_dynamic_and_family_lookup_relaxed",
    "power_coverage_dynamic_and_family_distance_relaxed",
    "power_coverage_dynamic_and_family_lookup_distance_relaxed",
    "power_coverage_dynamic_and_family_assignment_relaxed",
    "power_coverage_dynamic_family_assignment_and_gvi_relaxed",
}
POWER_COVERAGE_DYNAMIC_FAMILY_GVI_RELAXATION_VARIANTS = {
    "power_coverage_dynamic_family_assignment_and_gvi_relaxed",
}
POWER_FAMILY_CHANNELING_ADDITION_VARIANTS = {
    "family_active_domain_channeling_added",
    "family_membership_active_channeling_added",
    "family_active_and_membership_channeling_added",
}
POWER_FAMILY_SHELL_PAIR_TABLE_ADDITION_VARIANTS = {
    "family_shell_pair_tables_added",
    "power_coverage_dynamic_and_family_shell_pair_tables_added",
}
POWER_FAMILY_LOOKUP_REBUILD_VARIANTS = {
    "family_lookup_rebuilt_channeling",
    "power_coverage_dynamic_and_family_lookup_rebuilt_channeling",
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only",
    "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only",
    "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only",
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_shell_pair",
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_ordering",
    "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_ordering",
}
POWER_FAMILY_LOOKUP_REBUILD_COMPONENTS_BY_VARIANT = {
    "family_lookup_rebuilt_channeling": {
        "active_domain",
        "membership_reification",
        "membership_sum",
        "shell_pair_table",
        "ordering",
    },
    "power_coverage_dynamic_and_family_lookup_rebuilt_channeling": {
        "active_domain",
        "membership_reification",
        "membership_sum",
        "shell_pair_table",
        "ordering",
    },
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only": {
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only": {
        "shell_pair_table",
    },
    "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only": {
        "ordering",
    },
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_shell_pair": {
        "active_domain",
        "membership_reification",
        "membership_sum",
        "shell_pair_table",
    },
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_ordering": {
        "active_domain",
        "membership_reification",
        "membership_sum",
        "ordering",
    },
    "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_ordering": {
        "shell_pair_table",
        "ordering",
    },
}


def build_phase3b_forced_anchor_model_slice_diagnostic(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 1,
    anchor_indices: Optional[Sequence[int]] = None,
    time_limit_seconds: float = 20.0,
    worker_count: int = 4,
    variants: Sequence[str] = DEFAULT_SLICE_VARIANTS,
    target_power_family: Optional[str] = None,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    candidate_key = str(candidate)
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    before_hash = _file_hash(campaign_path)
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
    normalized_variants = _normalize_variants(variants)
    normalized_solver_parameter_profile = _normalize_solver_parameter_profile(
        solver_parameter_profile,
        default_worker_count=int(worker_count),
    )
    ghost_rect = _candidate_ghost_rect(candidate_key, record)
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Forced-anchor model-slice diagnostic has not run.",
    }
    entries: list[Dict[str, Any]] = []
    timing: Dict[str, float] = {}
    model_error: Optional[str] = None
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before model-slice diagnostics.",
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
                "recommendation": "No forced anchors selected; rerun B5A with failed-anchor sampling enabled.",
            }
        )
    else:
        try:
            overlay_started = time.perf_counter()
            model, base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=master_search_profile,
            )
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            solve_started = time.perf_counter()
            same_core_variants = tuple(
                variant
                for variant in normalized_variants
                if str(variant)
                not in {
                    "skip_power_coverage_core",
                    "no_protocol_lower_bound_core",
                    "skip_power_coverage_no_protocol_lower_bound_core",
                    "skip_power_coverage_no_protocol_lower_bound_core_residual_all_inactive",
                }
            )
            variant_constraints = _variant_constraints(model, same_core_variants)
            target_family_count_var_index = _target_power_family_count_var_index(
                model,
                target_power_family,
            )
            all_family_count_var_indices = _power_family_count_var_indices(model)
            power_family_channeling_slots = _power_family_channeling_slots(
                model,
                base_proto,
            )
            power_family_shell_pair_table_payload = (
                _power_family_shell_pair_table_payload(model, base_proto)
            )
            power_capacity_gvi_coefficients = _power_capacity_gvi_coefficients(model)
            power_capacity_gvi_demands = _power_capacity_gvi_demands(model)
            for anchor_idx in selected_anchor_indices:
                u_var = model.u_vars.get(int(anchor_idx))
                if u_var is None and same_core_variants:
                    entries.extend(
                        {
                            "anchor_idx": int(anchor_idx),
                            "variant": str(variant),
                            "evaluated": False,
                            "status": "SKIPPED",
                            "skip_reason": "anchor_not_in_model_u_vars",
                        }
                        for variant in same_core_variants
                    )
                elif u_var is not None:
                    for variant in same_core_variants:
                        if (
                            str(variant) in TARGET_POWER_FAMILY_BOUND_REWRITE_VARIANTS
                            and target_family_count_var_index is None
                        ):
                            entries.append(
                                {
                                    "anchor_idx": int(anchor_idx),
                                    "variant": str(variant),
                                    "evaluated": False,
                                    "status": "SKIPPED",
                                    "skip_reason": "target_power_family_missing",
                                    "target_power_family": target_power_family,
                                }
                            )
                            continue
                        entries.append(
                            _solve_slice_clone(
                                base_proto,
                                anchor_idx=int(anchor_idx),
                                u_var_index=int(u_var.Index()),
                                disabled_active_var_indices=variant_constraints[str(variant)],
                                variant=str(variant),
                                time_limit_seconds=float(time_limit_seconds),
                                worker_count=int(worker_count),
                                relaxed_power_family_count_var_index=(
                                    target_family_count_var_index
                                    if str(variant)
                                    in TARGET_POWER_FAMILY_BOUND_REWRITE_VARIANTS
                                    else None
                                ),
                                relaxed_power_family_name=(
                                    str(target_power_family)
                                    if target_power_family is not None
                                    and str(variant)
                                    in TARGET_POWER_FAMILY_BOUND_REWRITE_VARIANTS
                                    else None
                                ),
                                replacement_bound_mode=(
                                    "direct_after_force"
                                    if str(variant)
                                    in TARGET_POWER_FAMILY_BOUND_DIRECT_VARIANTS
                                    else None
                                ),
                                direct_power_family_count_var_indices=(
                                    all_family_count_var_indices
                                    if str(variant)
                                    in ALL_CONDITIONED_FAMILY_BOUND_DIRECT_VARIANTS
                                    else None
                                ),
                                power_coverage_relaxation_mode=(
                                    str(variant)
                                    if str(variant)
                                    in POWER_COVERAGE_LINEAR_RELAXATION_VARIANTS
                                    else None
                                ),
                                power_coverage_dynamic_relaxation_mode=(
                                    str(variant)
                                    if str(variant)
                                    in POWER_COVERAGE_DYNAMIC_RELAXATION_VARIANTS
                                    else None
                                ),
                                power_capacity_gvi_relax_templates=(
                                    _power_capacity_gvi_variant_templates(
                                        str(variant),
                                        power_capacity_gvi_coefficients,
                                    )
                                    if str(variant)
                                    in POWER_CAPACITY_GVI_RELAXATION_VARIANTS
                                    or str(variant)
                                    in POWER_COVERAGE_DYNAMIC_FAMILY_GVI_RELAXATION_VARIANTS
                                    else None
                                ),
                                power_capacity_gvi_coefficients=power_capacity_gvi_coefficients,
                                power_capacity_gvi_demands=power_capacity_gvi_demands,
                                power_family_layer_relaxation_mode=(
                                    (
                                        "power_family_lookup_constraints_relaxed"
                                        if str(variant)
                                        in POWER_FAMILY_LOOKUP_REBUILD_VARIANTS
                                        else _power_family_layer_variant_mode(str(variant))
                                    )
                                    if str(variant)
                                    in POWER_FAMILY_LAYER_RELAXATION_VARIANTS
                                    or str(variant)
                                    in POWER_FAMILY_LOOKUP_REBUILD_VARIANTS
                                    else None
                                ),
                                power_family_channeling_mode=(
                                    str(variant)
                                    if str(variant)
                                    in POWER_FAMILY_CHANNELING_ADDITION_VARIANTS
                                    else None
                                ),
                                power_family_channeling_slots=power_family_channeling_slots,
                                power_family_shell_pair_table_mode=(
                                    str(variant)
                                    if str(variant)
                                    in POWER_FAMILY_SHELL_PAIR_TABLE_ADDITION_VARIANTS
                                    else None
                                ),
                                power_family_shell_pair_table_payload=(
                                    power_family_shell_pair_table_payload
                                ),
                                power_family_lookup_rebuild_mode=(
                                    str(variant)
                                    if str(variant)
                                    in POWER_FAMILY_LOOKUP_REBUILD_VARIANTS
                                    else None
                                ),
                                solver_parameter_profile=normalized_solver_parameter_profile,
                            )
                        )
            custom_core_variants = tuple(
                variant
                for variant in normalized_variants
                if str(variant)
                in {
                    "skip_power_coverage_core",
                    "no_protocol_lower_bound_core",
                    "skip_power_coverage_no_protocol_lower_bound_core",
                    "skip_power_coverage_no_protocol_lower_bound_core_residual_all_inactive",
                }
            )
            for custom_variant in custom_core_variants:
                skip_started = time.perf_counter()
                custom_model, custom_proto = _build_custom_core_overlay(
                    project_root,
                    ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                    master_search_profile=master_search_profile,
                    skip_power_coverage=str(custom_variant).startswith("skip_power_coverage"),
                    clear_required_generic_inputs=(
                        str(custom_variant)
                        in {
                            "no_protocol_lower_bound_core",
                            "skip_power_coverage_no_protocol_lower_bound_core",
                            "skip_power_coverage_no_protocol_lower_bound_core_residual_all_inactive",
                        }
                    ),
                )
                timing[f"{custom_variant}_overlay_build_seconds"] = float(
                    time.perf_counter() - skip_started
                )
                for anchor_idx in selected_anchor_indices:
                    custom_u_var = custom_model.u_vars.get(int(anchor_idx))
                    if custom_u_var is None:
                        entries.append(
                            {
                                "anchor_idx": int(anchor_idx),
                                "variant": str(custom_variant),
                                "evaluated": False,
                                "status": "SKIPPED",
                                "skip_reason": "anchor_not_in_custom_core_model_u_vars",
                            }
                        )
                        continue
                    entries.append(
                        _solve_slice_clone(
                            custom_proto,
                            anchor_idx=int(anchor_idx),
                            u_var_index=int(custom_u_var.Index()),
                                disabled_active_var_indices=_custom_variant_disabled_indices(
                                    custom_model,
                                    str(custom_variant),
                                ),
                                variant=str(custom_variant),
                                time_limit_seconds=float(time_limit_seconds),
                                worker_count=int(worker_count),
                                solver_parameter_profile=normalized_solver_parameter_profile,
                            )
                        )
            timing["slice_solve_seconds"] = float(time.perf_counter() - solve_started)
            status.update(_status_from_entries(entries))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Forced-anchor model-slice diagnostic failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    return {
        "metadata": {
            "source": FORCED_ANCHOR_MODEL_SLICE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "mutated_model_slice_not_proof_source",
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
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "variants": list(normalized_variants),
            "target_power_family": target_power_family,
            "solver_parameter_profile": normalized_solver_parameter_profile,
        },
        "status": status,
        "slice_matrix": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "status_counts_by_variant": _status_counts_by_key(entries, "variant"),
            "status_counts_by_anchor": _status_counts_by_key(entries, "anchor_idx"),
            "diagnostic_findings": _diagnostic_findings(entries),
        },
        "timing": timing,
        "model_error": model_error,
        "campaign_state_unchanged": before_hash == after_hash,
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            status=status,
            campaign_state_unchanged=before_hash == after_hash,
            model_error=model_error,
        ),
    }


def render_phase3b_forced_anchor_model_slice_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    matrix = _mapping(report.get("slice_matrix"))
    lines = [
        "# Phase 3B Forced-Anchor Model-Slice Diagnostic",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "- Diagnostic semantics: mutated_model_slice_not_proof_source",
        f"- Status counts: {matrix.get('status_counts', {})}",
        f"- Diagnostic findings: {matrix.get('diagnostic_findings', [])}",
        "",
        "| Anchor | Variant | Status | Disabled Actives | Wall | Branches |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(matrix.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("anchor_idx")),
                    _markdown_cell(entry.get("variant")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("disabled_active_var_count")),
                    _markdown_cell(entry.get("wall_time")),
                    _markdown_cell(entry.get("branches")),
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


def render_phase3b_forced_anchor_model_slice_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    matrix = _mapping(report.get("slice_matrix"))
    lines = [
        "Phase 3B forced-anchor model-slice diagnostic",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        "diagnostic_semantics=mutated_model_slice_not_proof_source",
        f"status_counts={matrix.get('status_counts', {})}",
        f"diagnostic_findings={matrix.get('diagnostic_findings', [])}",
    ]
    for entry in list(matrix.get("entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "entry "
                f"anchor={entry.get('anchor_idx')} "
                f"variant={entry.get('variant')} "
                f"status={entry.get('status')} "
                f"disabled_actives={entry.get('disabled_active_var_count')} "
                f"wall={entry.get('wall_time')} "
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


def _variant_constraints(model: Any, variants: Sequence[str]) -> Dict[str, list[int]]:
    delegate = getattr(model, "_coordinate_delegate", None)
    residual_slots = getattr(delegate, "residual_optional_slots", {}) if delegate else {}
    protocol_slots = list(residual_slots.get("protocol_storage_box", []))
    pole_slots = list(residual_slots.get("power_pole", []))
    all_residual_slots = [
        slot for slots in residual_slots.values() for slot in list(slots)
    ]
    by_variant = {
        "base": [],
        "residual_all_inactive": _active_var_indices(all_residual_slots),
        "protocol_boxes_inactive": _active_var_indices(protocol_slots),
        "power_poles_inactive": _active_var_indices(pole_slots),
        "target_power_family_bound_relaxed": [],
        "target_power_family_bound_relaxed_protocol_boxes_inactive": _active_var_indices(
            protocol_slots
        ),
        "target_power_family_bound_direct_after_force": [],
        "target_power_family_bound_direct_after_force_protocol_boxes_inactive": _active_var_indices(
            protocol_slots
        ),
        "all_conditioned_family_bounds_direct_after_force": [],
        "all_conditioned_family_bounds_direct_after_force_protocol_boxes_inactive": _active_var_indices(
            protocol_slots
        ),
        "power_coverage_active_requirement_relaxed": [],
        "power_coverage_geometry_bounds_relaxed": [],
        "power_coverage_active_and_geometry_relaxed": [],
        "power_coverage_witness_element_relaxed": [],
        "power_coverage_witness_element_and_linear_relaxed": [],
        "power_pole_no_overlap_relaxed": [],
        "power_coverage_dynamic_coupling_relaxed": [],
        "power_coverage_dynamic_and_family_count_relaxed": [],
        "power_coverage_dynamic_and_family_membership_count_relaxed": [],
        "power_coverage_dynamic_and_family_table_relaxed": [],
        "power_coverage_dynamic_and_family_linear_relaxed": [],
        "power_coverage_dynamic_and_family_sentinel_relaxed": [],
        "power_coverage_dynamic_and_family_membership_linear_relaxed": [],
        "power_coverage_dynamic_and_family_ordering_linear_relaxed": [],
        "power_coverage_dynamic_and_family_other_linear_relaxed": [],
        "power_coverage_dynamic_and_family_lookup_relaxed": [],
        "power_coverage_dynamic_and_family_distance_relaxed": [],
        "power_coverage_dynamic_and_family_lookup_distance_relaxed": [],
        "power_coverage_dynamic_and_family_assignment_relaxed": [],
        "power_coverage_dynamic_family_assignment_and_gvi_relaxed": [],
        "family_active_domain_channeling_added": [],
        "family_membership_active_channeling_added": [],
        "family_active_and_membership_channeling_added": [],
        "family_shell_pair_tables_added": [],
        "power_coverage_dynamic_and_family_shell_pair_tables_added": [],
        "family_lookup_rebuilt_channeling": [],
        "power_coverage_dynamic_and_family_lookup_rebuilt_channeling": [],
        "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only": [],
        "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only": [],
        "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only": [],
        "power_coverage_dynamic_and_family_lookup_rebuilt_membership_shell_pair": [],
        "power_coverage_dynamic_and_family_lookup_rebuilt_membership_ordering": [],
        "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_ordering": [],
        "power_capacity_gvi_protocol_storage_box_relaxed": [],
        "power_capacity_gvi_mandatory_templates_relaxed": [],
        "power_capacity_gvi_all_relaxed": [],
        "power_family_count_constraints_relaxed": [],
        "power_family_membership_and_count_constraints_relaxed": [],
        "power_family_assignment_layer_relaxed": [],
    }
    return {str(variant): list(by_variant[str(variant)]) for variant in variants}


def _target_power_family_count_var_index(
    model: Any,
    target_power_family: Optional[str],
) -> Optional[int]:
    if target_power_family is None or not str(target_power_family).strip():
        return None
    count_vars = getattr(model, "_power_pole_family_count_vars", {})
    var = dict(count_vars).get(str(target_power_family))
    if var is None:
        delegate = getattr(model, "_coordinate_delegate", None)
        var = dict(getattr(delegate, "power_pole_family_count_vars", {}) or {}).get(
            str(target_power_family)
        )
    if var is None:
        return None
    return int(var.Index())


def _power_family_count_var_indices(model: Any) -> Dict[str, int]:
    result: Dict[str, int] = {}
    delegate = getattr(model, "_coordinate_delegate", None)
    count_vars = dict(getattr(delegate, "power_pole_family_count_vars", {}) or {})
    count_vars.update(dict(getattr(model, "_power_pole_family_count_vars", {}) or {}))
    for family_name, var in sorted(count_vars.items()):
        if var is None:
            continue
        result[str(family_name)] = int(var.Index())
    return result


def _power_capacity_gvi_coefficients(model: Any) -> Dict[str, Dict[int, int]]:
    delegate = getattr(model, "_coordinate_delegate", None)
    if delegate is None:
        return {}
    family_count_indices = _power_family_count_var_indices(model)
    coefficients_by_family = getattr(delegate, "_power_pole_family_coefficients", {})
    result: Dict[str, Dict[int, int]] = {}
    for family_name, coefficients in sorted(dict(coefficients_by_family).items()):
        count_var_index = family_count_indices.get(str(family_name))
        if count_var_index is None:
            continue
        for template, coeff in sorted(dict(coefficients).items()):
            coeff_int = int(coeff)
            if coeff_int <= 0:
                continue
            result.setdefault(str(template), {})[int(count_var_index)] = coeff_int
    return result


def _power_capacity_gvi_demands(model: Any) -> Dict[str, int]:
    getter = getattr(model, "_exact_powered_template_demands", None)
    if not callable(getter):
        return {}
    try:
        return {str(tpl): int(demand) for tpl, demand in dict(getter()).items()}
    except Exception:
        return {}


def _power_capacity_gvi_variant_templates(
    variant: str,
    coefficients_by_template: Mapping[str, Mapping[int, int]],
) -> list[str]:
    template_names = sorted(str(template) for template in dict(coefficients_by_template))
    if str(variant) == "power_capacity_gvi_protocol_storage_box_relaxed":
        return [template for template in template_names if template == "protocol_storage_box"]
    if str(variant) == "power_capacity_gvi_mandatory_templates_relaxed":
        return [template for template in template_names if template != "protocol_storage_box"]
    if str(variant) == "power_capacity_gvi_all_relaxed":
        return template_names
    if str(variant) == "power_coverage_dynamic_family_assignment_and_gvi_relaxed":
        return template_names
    raise ValueError(f"Unsupported power-capacity GVI variant: {variant!r}")


def _power_family_layer_variant_mode(variant: str) -> str:
    if str(variant) == "power_coverage_dynamic_and_family_count_relaxed":
        return "power_family_count_constraints_relaxed"
    if str(variant) == "power_coverage_dynamic_and_family_membership_count_relaxed":
        return "power_family_membership_and_count_constraints_relaxed"
    if str(variant) == "power_coverage_dynamic_and_family_table_relaxed":
        return "power_family_lookup_table_constraints_relaxed"
    if str(variant) == "power_coverage_dynamic_and_family_linear_relaxed":
        return "power_family_lookup_linear_constraints_relaxed"
    if str(variant) == "power_coverage_dynamic_and_family_sentinel_relaxed":
        return "power_family_lookup_sentinel_constraints_relaxed"
    if str(variant) == "power_coverage_dynamic_and_family_membership_linear_relaxed":
        return "power_family_lookup_membership_linear_constraints_relaxed"
    if str(variant) == "power_coverage_dynamic_and_family_ordering_linear_relaxed":
        return "power_family_lookup_ordering_linear_constraints_relaxed"
    if str(variant) == "power_coverage_dynamic_and_family_other_linear_relaxed":
        return "power_family_lookup_other_linear_constraints_relaxed"
    if str(variant) == "power_coverage_dynamic_and_family_lookup_relaxed":
        return "power_family_lookup_constraints_relaxed"
    if str(variant) == "power_coverage_dynamic_and_family_distance_relaxed":
        return "power_family_distance_constraints_relaxed"
    if str(variant) == "power_coverage_dynamic_and_family_lookup_distance_relaxed":
        return "power_family_lookup_distance_constraints_relaxed"
    if str(variant) in {
        "power_coverage_dynamic_and_family_assignment_relaxed",
        "power_coverage_dynamic_family_assignment_and_gvi_relaxed",
    }:
        return "power_family_assignment_layer_relaxed"
    return str(variant)


def _power_family_channeling_slots(model: Any, model_proto: Any) -> list[Dict[str, Any]]:
    delegate = getattr(model, "_coordinate_delegate", None)
    if delegate is None:
        return []
    pole_slots = list(getattr(delegate, "residual_optional_slots", {}).get("power_pole", []))
    sentinel_family_id = len(dict(getattr(delegate, "_power_pole_family_name_by_int", {}) or {}))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(list(getattr(model_proto, "variables", [])))
    }
    family_lits_by_slot: Dict[str, list[int]] = {}
    for var_idx, name in sorted(var_names.items()):
        if not name.startswith("is_family__"):
            continue
        try:
            slot_key, _family_name = name[len("is_family__") :].rsplit("__", 1)
        except ValueError:
            continue
        family_lits_by_slot.setdefault(str(slot_key), []).append(int(var_idx))
    payload: list[Dict[str, Any]] = []
    for slot in pole_slots:
        active = getattr(slot, "active", None)
        family = getattr(slot, "family", None)
        if active is None or family is None:
            continue
        slot_key = str(getattr(slot, "key", ""))
        family_lit_indices = sorted(family_lits_by_slot.get(slot_key, []))
        payload.append(
            {
                "slot_key": slot_key,
                "active_var_index": int(active.Index()),
                "family_var_index": int(family.Index()),
                "family_lit_indices": family_lit_indices,
                "sentinel_family_id": int(sentinel_family_id),
            }
        )
    return payload


def _power_family_shell_pair_table_payload(
    model: Any,
    model_proto: Any,
) -> Dict[str, Any]:
    delegate = getattr(model, "_coordinate_delegate", None)
    if delegate is None:
        return {"slots": [], "rows_by_family_id": {}}
    rows_by_family_id: Dict[int, list[tuple[int, int]]] = {}
    for raw_row in list(getattr(delegate, "_power_pole_shell_lookup_rows", []) or []):
        if len(raw_row) != 3:
            continue
        d_lo, d_hi, family_id = (int(raw_row[0]), int(raw_row[1]), int(raw_row[2]))
        rows_by_family_id.setdefault(int(family_id), []).append((int(d_lo), int(d_hi)))

    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(list(getattr(model_proto, "variables", [])))
    }
    indices_by_name = {str(name): int(index) for index, name in var_names.items()}
    family_id_by_name = {
        str(name): int(index)
        for index, name in dict(getattr(delegate, "_power_pole_family_name_by_int", {}) or {}).items()
    }
    family_lits_by_slot: Dict[str, Dict[int, int]] = {}
    for var_idx, name in sorted(var_names.items()):
        if not name.startswith("is_family__"):
            continue
        try:
            slot_key, family_name = name[len("is_family__") :].rsplit("__", 1)
        except ValueError:
            continue
        family_id = family_id_by_name.get(str(family_name))
        if family_id is None:
            continue
        family_lits_by_slot.setdefault(str(slot_key), {})[int(family_id)] = int(var_idx)

    slots: list[Dict[str, Any]] = []
    for slot in list(getattr(delegate, "residual_optional_slots", {}).get("power_pole", [])):
        slot_key = str(getattr(slot, "key", ""))
        d_lo_idx = indices_by_name.get(f"d_lo__{slot_key}")
        d_hi_idx = indices_by_name.get(f"d_hi__{slot_key}")
        if d_lo_idx is None or d_hi_idx is None:
            continue
        active = getattr(slot, "active", None)
        family = getattr(slot, "family", None)
        if active is None or family is None:
            continue
        slots.append(
            {
                "slot_key": slot_key,
                "active_var_index": int(active.Index()),
                "family_var_index": int(family.Index()),
                "d_lo_var_index": int(d_lo_idx),
                "d_hi_var_index": int(d_hi_idx),
                "family_lit_indices_by_family_id": {
                    str(family_id): int(lit_idx)
                    for family_id, lit_idx in sorted(
                        family_lits_by_slot.get(slot_key, {}).items()
                    )
                },
            }
        )
    return {
        "slots": slots,
        "rows_by_family_id": {
            str(family_id): [[int(row[0]), int(row[1])] for row in sorted(rows)]
            for family_id, rows in sorted(rows_by_family_id.items())
        },
    }


def _build_custom_core_overlay(
    project_root: Path,
    *,
    ghost_rect: tuple[int, int],
    master_search_profile: str,
    skip_power_coverage: bool,
    clear_required_generic_inputs: bool,
) -> tuple[MasterPlacementModel, Any]:
    instances, facility_pools, rules = load_project_data(
        project_root,
        solve_mode="certified_exact",
    )
    generic_io_requirements = load_generic_io_requirements_artifact(project_root)
    if bool(clear_required_generic_inputs):
        generic_io_requirements = {
            **dict(generic_io_requirements),
            "required_generic_inputs": {},
        }
    core = MasterPlacementModel.build_exact_core(
        instances,
        facility_pools,
        rules,
        skip_power_coverage=bool(skip_power_coverage),
        generic_io_requirements=generic_io_requirements,
        master_search_profile=master_search_profile,
    )
    model = MasterPlacementModel.from_exact_core(
        core,
        ghost_rect=(int(ghost_rect[0]), int(ghost_rect[1])),
        master_search_profile=master_search_profile,
    )
    model.build()
    return model, _clone_model_proto(model.model.Proto())


def _active_var_indices(slots: Sequence[Any]) -> list[int]:
    indices: list[int] = []
    for slot in slots:
        active = getattr(slot, "active", None)
        if active is None:
            continue
        indices.append(int(active.Index()))
    return indices


def _custom_variant_disabled_indices(model: Any, variant: str) -> list[int]:
    if not str(variant).endswith("_residual_all_inactive"):
        return []
    delegate = getattr(model, "_coordinate_delegate", None)
    residual_slots = getattr(delegate, "residual_optional_slots", {}) if delegate else {}
    return _active_var_indices([slot for slots in residual_slots.values() for slot in list(slots)])


def _solve_slice_clone(
    base_proto: Any,
    *,
    anchor_idx: int,
    u_var_index: int,
    disabled_active_var_indices: Sequence[int],
    variant: str,
    time_limit_seconds: float,
    worker_count: int,
    relaxed_power_family_count_var_index: Optional[int] = None,
    relaxed_power_family_name: Optional[str] = None,
    replacement_bound_mode: Optional[str] = None,
    direct_power_family_count_var_indices: Optional[Mapping[str, int]] = None,
    power_coverage_relaxation_mode: Optional[str] = None,
    power_coverage_dynamic_relaxation_mode: Optional[str] = None,
    power_capacity_gvi_relax_templates: Optional[Sequence[str]] = None,
    power_capacity_gvi_coefficients: Optional[Mapping[str, Mapping[int, int]]] = None,
    power_capacity_gvi_demands: Optional[Mapping[str, int]] = None,
    power_family_layer_relaxation_mode: Optional[str] = None,
    power_family_channeling_mode: Optional[str] = None,
    power_family_channeling_slots: Optional[Sequence[Mapping[str, Any]]] = None,
    power_family_shell_pair_table_mode: Optional[str] = None,
    power_family_shell_pair_table_payload: Optional[Mapping[str, Any]] = None,
    power_family_lookup_rebuild_mode: Optional[str] = None,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
    forced_bool_true_indices: Optional[Sequence[int]] = None,
    forced_bool_false_indices: Optional[Sequence[int]] = None,
    assumption_label: Optional[str] = None,
) -> Dict[str, Any]:
    local_proto = _clone_model_proto(base_proto)
    removal_payload: Dict[str, Any] = {"removed_constraint_count": 0}
    power_coverage_relaxation_payload: Dict[str, Any] = {
        "removed_constraint_count": 0,
    }
    power_coverage_dynamic_relaxation_payload: Dict[str, Any] = {
        "removed_constraint_count": 0,
    }
    power_capacity_gvi_relaxation_payload: Dict[str, Any] = {
        "removed_constraint_count": 0,
    }
    power_family_layer_relaxation_payload: Dict[str, Any] = {
        "removed_constraint_count": 0,
    }
    power_family_channeling_payload: Dict[str, Any] = {
        "added_constraint_count": 0,
    }
    power_family_shell_pair_tables_payload: Dict[str, Any] = {
        "added_constraint_count": 0,
    }
    power_family_lookup_rebuild_payload: Dict[str, Any] = {
        "added_constraint_count": 0,
    }
    direct_bound_payloads: list[Dict[str, Any]] = []
    direct_bound_index_by_family: Dict[str, int] = {}
    if relaxed_power_family_count_var_index is not None:
        removal_payload = _remove_conditioned_power_family_bound_constraints_payload(
            local_proto,
            count_var_index=int(relaxed_power_family_count_var_index),
            u_var_index=int(u_var_index),
        )
    for family_name, count_var_index in sorted(
        dict(direct_power_family_count_var_indices or {}).items()
    ):
        payload = _remove_conditioned_power_family_bound_constraints_payload(
            local_proto,
            count_var_index=int(count_var_index),
            u_var_index=int(u_var_index),
        )
        if int(payload.get("removed_constraint_count", 0)) <= 0:
            continue
        payload["family_name"] = str(family_name)
        payload["count_var_index"] = int(count_var_index)
        direct_bound_payloads.append(payload)
        direct_bound_index_by_family[str(family_name)] = int(count_var_index)
    if power_coverage_relaxation_mode is not None:
        power_coverage_relaxation_payload = (
            _remove_power_coverage_linear_constraints_payload(
                local_proto,
                mode=str(power_coverage_relaxation_mode),
            )
        )
    if power_coverage_dynamic_relaxation_mode is not None:
        power_coverage_dynamic_relaxation_payload = (
            _remove_power_coverage_dynamic_constraints_payload(
                local_proto,
                mode=str(power_coverage_dynamic_relaxation_mode),
            )
        )
    if power_capacity_gvi_relax_templates is not None:
        power_capacity_gvi_relaxation_payload = (
            _remove_power_capacity_gvi_constraints_payload(
                local_proto,
                templates=power_capacity_gvi_relax_templates,
                template_coefficients=power_capacity_gvi_coefficients or {},
                template_demands=power_capacity_gvi_demands or {},
            )
        )
    if power_family_layer_relaxation_mode is not None:
        power_family_layer_relaxation_payload = (
            _remove_power_family_layer_constraints_payload(
                local_proto,
                mode=str(power_family_layer_relaxation_mode),
            )
        )
    local_model = cp_model_from_proto(local_proto)
    if power_family_channeling_mode is not None:
        power_family_channeling_payload = _add_power_family_channeling_constraints(
            local_model,
            mode=str(power_family_channeling_mode),
            slots=power_family_channeling_slots or [],
        )
    if power_family_shell_pair_table_mode is not None:
        power_family_shell_pair_tables_payload = (
            _add_power_family_shell_pair_table_constraints(
                local_model,
                mode=str(power_family_shell_pair_table_mode),
                payload=power_family_shell_pair_table_payload or {},
            )
        )
    if power_family_lookup_rebuild_mode is not None:
        power_family_lookup_rebuild_payload = (
            _add_power_family_lookup_rebuild_constraints(
                local_model,
                mode=str(power_family_lookup_rebuild_mode),
                payload=power_family_shell_pair_table_payload or {},
            )
        )
    local_model.Add(local_model.GetBoolVarFromProtoIndex(int(u_var_index)) == 1)
    replacement_bound_value = None
    if (
        replacement_bound_mode == "direct_after_force"
        and relaxed_power_family_count_var_index is not None
    ):
        replacement_bound_value = removal_payload.get("implied_conditioned_upper_bound")
        if replacement_bound_value is not None:
            local_model.Add(
                local_model.GetIntVarFromProtoIndex(
                    int(relaxed_power_family_count_var_index)
                )
                <= int(replacement_bound_value)
            )
    for payload in direct_bound_payloads:
        bound_value = payload.get("implied_conditioned_upper_bound")
        count_var_index = payload.get("count_var_index")
        if bound_value is None or count_var_index is None:
            continue
        local_model.Add(
            local_model.GetIntVarFromProtoIndex(int(count_var_index)) <= int(bound_value)
        )
    for var_idx in disabled_active_var_indices:
        local_model.Add(local_model.GetBoolVarFromProtoIndex(int(var_idx)) == 0)
    for var_idx in list(forced_bool_true_indices or []):
        local_model.Add(local_model.GetBoolVarFromProtoIndex(int(var_idx)) == 1)
    for var_idx in list(forced_bool_false_indices or []):
        local_model.Add(local_model.GetBoolVarFromProtoIndex(int(var_idx)) == 0)
    solver = cp_model.CpSolver()
    applied_solver_profile = _apply_solver_parameter_profile(
        solver,
        time_limit_seconds=float(time_limit_seconds),
        default_worker_count=int(worker_count),
        profile=solver_parameter_profile,
    )
    started = time.perf_counter()
    status = solver.Solve(local_model)
    elapsed_seconds = float(time.perf_counter() - started)
    response_stats = solver.ResponseStats()
    relaxed_power_family_count_value: Optional[int] = None
    if relaxed_power_family_count_var_index is not None and status in {
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    }:
        try:
            relaxed_power_family_count_value = int(
                solver.Value(
                    local_model.GetIntVarFromProtoIndex(
                        int(relaxed_power_family_count_var_index)
                    )
                )
            )
        except Exception:
            relaxed_power_family_count_value = None
    direct_bound_solution_values: Dict[str, int] = {}
    if direct_bound_payloads and status in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        for family_name, count_var_index in sorted(direct_bound_index_by_family.items()):
            try:
                direct_bound_solution_values[str(family_name)] = int(
                    solver.Value(local_model.GetIntVarFromProtoIndex(int(count_var_index)))
                )
            except Exception:
                continue
    return {
        "anchor_idx": int(anchor_idx),
        "u_var_index": int(u_var_index),
        "variant": str(variant),
        "evaluated": True,
        "status": solver.StatusName(status),
        "elapsed_seconds": float(elapsed_seconds),
        "wall_time": float(solver.WallTime()),
        "user_time": float(solver.UserTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "disabled_active_var_count": len(disabled_active_var_indices),
        "assumption_label": assumption_label,
        "forced_bool_true_indices": [
            int(var_idx) for var_idx in list(forced_bool_true_indices or [])
        ],
        "forced_bool_false_indices": [
            int(var_idx) for var_idx in list(forced_bool_false_indices or [])
        ],
        "forced_bool_assignment_count": int(
            len(list(forced_bool_true_indices or []))
            + len(list(forced_bool_false_indices or []))
        ),
        "relaxed_power_family": relaxed_power_family_name,
        "relaxed_power_family_count_var_index": relaxed_power_family_count_var_index,
        "relaxed_power_family_count_value": relaxed_power_family_count_value,
        "relaxed_conditioned_power_family_bound_constraints_removed": int(
            removal_payload.get("removed_constraint_count", 0)
        ),
        "replacement_bound_mode": replacement_bound_mode,
        "replacement_conditioned_power_family_bound": replacement_bound_value,
        "removed_conditioned_power_family_bound_payload": removal_payload,
        "direct_power_family_bound_replacement_count": int(len(direct_bound_payloads)),
        "direct_power_family_bound_replacements": direct_bound_payloads,
        "direct_power_family_bound_solution_values": direct_bound_solution_values,
        "power_coverage_relaxation_mode": power_coverage_relaxation_mode,
        "relaxed_power_coverage_linear_constraint_count": int(
            power_coverage_relaxation_payload.get("removed_constraint_count", 0)
        ),
        "relaxed_power_coverage_linear_constraints": power_coverage_relaxation_payload,
        "power_coverage_dynamic_relaxation_mode": power_coverage_dynamic_relaxation_mode,
        "relaxed_power_coverage_dynamic_constraint_count": int(
            power_coverage_dynamic_relaxation_payload.get("removed_constraint_count", 0)
        ),
        "relaxed_power_coverage_dynamic_constraints": power_coverage_dynamic_relaxation_payload,
        "power_capacity_gvi_relax_templates": [
            str(template) for template in list(power_capacity_gvi_relax_templates or [])
        ],
        "relaxed_power_capacity_gvi_constraint_count": int(
            power_capacity_gvi_relaxation_payload.get("removed_constraint_count", 0)
        ),
        "relaxed_power_capacity_gvi_constraints": power_capacity_gvi_relaxation_payload,
        "power_family_layer_relaxation_mode": power_family_layer_relaxation_mode,
        "relaxed_power_family_layer_constraint_count": int(
            power_family_layer_relaxation_payload.get("removed_constraint_count", 0)
        ),
        "relaxed_power_family_layer_constraints": power_family_layer_relaxation_payload,
        "power_family_channeling_mode": power_family_channeling_mode,
        "added_power_family_channeling_constraint_count": int(
            power_family_channeling_payload.get("added_constraint_count", 0)
        ),
        "added_power_family_channeling_constraints": power_family_channeling_payload,
        "power_family_shell_pair_table_mode": power_family_shell_pair_table_mode,
        "added_power_family_shell_pair_table_constraint_count": int(
            power_family_shell_pair_tables_payload.get("added_constraint_count", 0)
        ),
        "added_power_family_shell_pair_table_constraints": (
            power_family_shell_pair_tables_payload
        ),
        "power_family_lookup_rebuild_mode": power_family_lookup_rebuild_mode,
        "added_power_family_lookup_rebuild_constraint_count": int(
            power_family_lookup_rebuild_payload.get("added_constraint_count", 0)
        ),
        "added_power_family_lookup_rebuild_constraints": (
            power_family_lookup_rebuild_payload
        ),
        "time_limit_seconds": float(time_limit_seconds),
        "worker_count": int(worker_count),
        "solver_parameter_profile": applied_solver_profile,
        "solver_profile_id": applied_solver_profile.get("profile_id"),
        "search_branching": applied_solver_profile.get("search_branching"),
        "cp_model_probing_level": applied_solver_profile.get("cp_model_probing_level"),
        "symmetry_level": applied_solver_profile.get("symmetry_level"),
        "solver_worker_count": applied_solver_profile.get("worker_count"),
        "response_summary": _first_line(response_stats),
        "response_stats": str(response_stats),
        "response_stats_parsed": _response_stats_payload(response_stats),
    }


def _normalize_solver_parameter_profile(
    profile: Optional[Mapping[str, Any]],
    *,
    default_worker_count: int,
) -> Dict[str, Any]:
    raw = dict(profile or {})
    profile_id = str(
        raw.get("profile_id")
        or DEFAULT_SLICE_SOLVER_PARAMETER_PROFILE["profile_id"]
    ).strip()
    search_branching = str(
        raw.get(
            "search_branching",
            DEFAULT_SLICE_SOLVER_PARAMETER_PROFILE["search_branching"],
        )
    ).strip().lower()
    if search_branching not in {"fixed", "automatic", "portfolio"}:
        raise ValueError(f"Unsupported search_branching: {search_branching!r}")
    normalized: Dict[str, Any] = {
        "profile_id": profile_id or str(DEFAULT_SLICE_SOLVER_PARAMETER_PROFILE["profile_id"]),
        "search_branching": search_branching,
        "cp_model_probing_level": max(
            0,
            int(
                raw.get(
                    "cp_model_probing_level",
                    DEFAULT_SLICE_SOLVER_PARAMETER_PROFILE["cp_model_probing_level"],
                )
            ),
        ),
        "symmetry_level": max(
            0,
            int(
                raw.get(
                    "symmetry_level",
                    DEFAULT_SLICE_SOLVER_PARAMETER_PROFILE["symmetry_level"],
                )
            ),
        ),
        "worker_count": max(
            1,
            int(
                raw.get(
                    "worker_count",
                    default_worker_count
                    if default_worker_count > 0
                    else DEFAULT_SLICE_SOLVER_PARAMETER_PROFILE["worker_count"],
                )
            ),
        ),
        "hint_conflict_limit": max(
            0,
            int(
                raw.get(
                    "hint_conflict_limit",
                    DEFAULT_SLICE_SOLVER_PARAMETER_PROFILE["hint_conflict_limit"],
                )
            ),
        ),
    }
    for integer_key in (
        "linearization_level",
        "random_seed",
        "max_presolve_iterations",
        "boolean_encoding_level",
        "max_domain_size_for_linear2_expansion",
        "max_domain_size_when_encoding_eq_neq_constraints",
        "table_compression_level",
    ):
        if integer_key in raw and raw[integer_key] is not None:
            normalized[integer_key] = int(raw[integer_key])
    for boolean_key in (
        "cp_model_presolve",
        "randomize_search",
        "log_search_progress",
        "log_to_stdout",
        "cp_model_use_sat_presolve",
        "find_clauses_that_are_exactly_one",
        "presolve_use_bva",
        "encode_complex_linear_constraint_with_integer",
    ):
        if boolean_key in raw and raw[boolean_key] is not None:
            normalized[boolean_key] = _bool_value(raw[boolean_key])
    return normalized


def _apply_solver_parameter_profile(
    solver: Any,
    *,
    time_limit_seconds: float,
    default_worker_count: int,
    profile: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    normalized = _normalize_solver_parameter_profile(
        profile,
        default_worker_count=default_worker_count,
    )
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = int(normalized["worker_count"])
    _apply_search_branching(solver, str(normalized["search_branching"]))
    solver.parameters.cp_model_probing_level = int(
        normalized["cp_model_probing_level"]
    )
    solver.parameters.symmetry_level = int(normalized["symmetry_level"])
    solver.parameters.hint_conflict_limit = int(normalized["hint_conflict_limit"])
    for integer_key in (
        "linearization_level",
        "random_seed",
        "max_presolve_iterations",
        "boolean_encoding_level",
        "max_domain_size_for_linear2_expansion",
        "max_domain_size_when_encoding_eq_neq_constraints",
        "table_compression_level",
    ):
        if integer_key in normalized and hasattr(solver.parameters, integer_key):
            setattr(solver.parameters, integer_key, int(normalized[integer_key]))
    for boolean_key in (
        "cp_model_presolve",
        "randomize_search",
        "log_search_progress",
        "log_to_stdout",
        "cp_model_use_sat_presolve",
        "find_clauses_that_are_exactly_one",
        "presolve_use_bva",
        "encode_complex_linear_constraint_with_integer",
    ):
        if boolean_key in normalized and hasattr(solver.parameters, boolean_key):
            setattr(solver.parameters, boolean_key, bool(normalized[boolean_key]))
    return {
        **normalized,
        "time_limit_seconds": float(time_limit_seconds),
    }


def _apply_search_branching(solver: Any, search_branching: str) -> None:
    branching = str(search_branching).strip().lower()
    if branching == "fixed":
        solver.parameters.search_branching = cp_model.FIXED_SEARCH
    elif branching == "automatic":
        solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    elif branching == "portfolio":
        solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
    else:
        raise ValueError(f"Unsupported search_branching: {search_branching}")


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value!r}")


def _remove_conditioned_power_family_bound_constraints(
    model_proto: Any,
    *,
    count_var_index: int,
    u_var_index: int,
) -> int:
    return int(
        _remove_conditioned_power_family_bound_constraints_payload(
            model_proto,
            count_var_index=count_var_index,
            u_var_index=u_var_index,
        ).get("removed_constraint_count", 0)
    )


def _add_power_family_channeling_constraints(
    model: Any,
    *,
    mode: str,
    slots: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    mode_text = str(mode)
    if mode_text not in POWER_FAMILY_CHANNELING_ADDITION_VARIANTS:
        raise ValueError(f"Unsupported power-family channeling mode: {mode!r}")
    add_active_domain = mode_text in {
        "family_active_domain_channeling_added",
        "family_active_and_membership_channeling_added",
    }
    add_membership_sum = mode_text in {
        "family_membership_active_channeling_added",
        "family_active_and_membership_channeling_added",
    }
    active_domain_constraints = 0
    membership_sum_constraints = 0
    slot_count = 0
    family_lit_total = 0
    for slot in list(slots):
        active_idx = slot.get("active_var_index")
        family_idx = slot.get("family_var_index")
        sentinel = slot.get("sentinel_family_id")
        if active_idx is None or family_idx is None or sentinel is None:
            continue
        active_var = model.GetBoolVarFromProtoIndex(int(active_idx))
        family_var = model.GetIntVarFromProtoIndex(int(family_idx))
        if add_active_domain:
            model.Add(family_var <= int(sentinel) - 1).OnlyEnforceIf(active_var)
            model.Add(family_var == int(sentinel)).OnlyEnforceIf(active_var.Not())
            active_domain_constraints += 2
        lit_indices = [int(idx) for idx in list(slot.get("family_lit_indices", []))]
        if add_membership_sum and lit_indices:
            lit_vars = [model.GetBoolVarFromProtoIndex(int(idx)) for idx in lit_indices]
            model.Add(sum(lit_vars) == active_var)
            membership_sum_constraints += 1
            family_lit_total += int(len(lit_indices))
        slot_count += 1
    return {
        "mode": mode_text,
        "slot_count": int(slot_count),
        "family_lit_total": int(family_lit_total),
        "active_domain_constraint_count": int(active_domain_constraints),
        "membership_sum_constraint_count": int(membership_sum_constraints),
        "added_constraint_count": int(active_domain_constraints + membership_sum_constraints),
        "diagnostic_semantics": "redundant_channeling_not_proof_source_until_validated",
    }


def _add_power_family_shell_pair_table_constraints(
    model: Any,
    *,
    mode: str,
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    mode_text = str(mode)
    if mode_text not in POWER_FAMILY_SHELL_PAIR_TABLE_ADDITION_VARIANTS:
        raise ValueError(f"Unsupported power-family shell table mode: {mode!r}")
    rows_by_family_id = {
        str(family_id): [
            [int(row[0]), int(row[1])]
            for row in list(rows)
            if isinstance(row, (list, tuple)) and len(row) == 2
        ]
        for family_id, rows in _mapping(payload.get("rows_by_family_id")).items()
    }
    added_constraints = 0
    enforced_row_total = 0
    slot_count = 0
    family_lit_count = 0
    for slot in list(payload.get("slots", [])):
        if not isinstance(slot, Mapping):
            continue
        d_lo_idx = slot.get("d_lo_var_index")
        d_hi_idx = slot.get("d_hi_var_index")
        if d_lo_idx is None or d_hi_idx is None:
            continue
        d_lo_var = model.GetIntVarFromProtoIndex(int(d_lo_idx))
        d_hi_var = model.GetIntVarFromProtoIndex(int(d_hi_idx))
        slot_count += 1
        for family_id, lit_idx in sorted(
            _mapping(slot.get("family_lit_indices_by_family_id")).items()
        ):
            rows = rows_by_family_id.get(str(family_id), [])
            if not rows:
                continue
            lit_var = model.GetBoolVarFromProtoIndex(int(lit_idx))
            model.AddAllowedAssignments([d_lo_var, d_hi_var], rows).OnlyEnforceIf(
                lit_var
            )
            added_constraints += 1
            family_lit_count += 1
            enforced_row_total += int(len(rows))
    return {
        "mode": mode_text,
        "slot_count": int(slot_count),
        "family_lit_count": int(family_lit_count),
        "added_constraint_count": int(added_constraints),
        "enforced_row_total": int(enforced_row_total),
        "family_count": int(len(rows_by_family_id)),
        "diagnostic_semantics": "redundant_shell_pair_tables_not_proof_source_until_validated",
    }


def _add_power_family_lookup_rebuild_constraints(
    model: Any,
    *,
    mode: str,
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    mode_text = str(mode)
    if mode_text not in POWER_FAMILY_LOOKUP_REBUILD_VARIANTS:
        raise ValueError(f"Unsupported power-family lookup rebuild mode: {mode!r}")
    components = set(POWER_FAMILY_LOOKUP_REBUILD_COMPONENTS_BY_VARIANT[mode_text])
    rows_by_family_id = {
        str(family_id): [
            [int(row[0]), int(row[1])]
            for row in list(rows)
            if isinstance(row, (list, tuple)) and len(row) == 2
        ]
        for family_id, rows in _mapping(payload.get("rows_by_family_id")).items()
    }
    active_domain_constraints = 0
    membership_reification_constraints = 0
    membership_sum_constraints = 0
    shell_pair_table_constraints = 0
    family_ordering_constraints = 0
    family_lit_total = 0
    enforced_row_total = 0
    previous_family_var = None
    slot_count = 0
    family_count = int(len(rows_by_family_id))
    for slot in list(payload.get("slots", [])):
        if not isinstance(slot, Mapping):
            continue
        active_idx = slot.get("active_var_index")
        family_idx = slot.get("family_var_index")
        d_lo_idx = slot.get("d_lo_var_index")
        d_hi_idx = slot.get("d_hi_var_index")
        if None in {active_idx, family_idx, d_lo_idx, d_hi_idx}:
            continue
        active_var = model.GetBoolVarFromProtoIndex(int(active_idx))
        family_var = model.GetIntVarFromProtoIndex(int(family_idx))
        d_lo_var = model.GetIntVarFromProtoIndex(int(d_lo_idx))
        d_hi_var = model.GetIntVarFromProtoIndex(int(d_hi_idx))
        sentinel_family_id = int(family_count)
        if "active_domain" in components:
            model.Add(family_var <= sentinel_family_id - 1).OnlyEnforceIf(active_var)
            model.Add(family_var == sentinel_family_id).OnlyEnforceIf(active_var.Not())
            active_domain_constraints += 2

        lit_vars = []
        for family_id, lit_idx in sorted(
            _mapping(slot.get("family_lit_indices_by_family_id")).items()
        ):
            rows = rows_by_family_id.get(str(family_id), [])
            if not rows:
                continue
            family_id_int = int(family_id)
            lit_var = model.GetBoolVarFromProtoIndex(int(lit_idx))
            lit_vars.append(lit_var)
            if "membership_reification" in components:
                model.Add(family_var == family_id_int).OnlyEnforceIf(lit_var)
                model.Add(family_var != family_id_int).OnlyEnforceIf(lit_var.Not())
                membership_reification_constraints += 2
            if "shell_pair_table" in components:
                model.AddAllowedAssignments([d_lo_var, d_hi_var], rows).OnlyEnforceIf(
                    lit_var
                )
                shell_pair_table_constraints += 1
                enforced_row_total += int(len(rows))
        if lit_vars and "membership_sum" in components:
            model.Add(sum(lit_vars) == active_var)
            membership_sum_constraints += 1
            family_lit_total += int(len(lit_vars))
        elif lit_vars:
            family_lit_total += int(len(lit_vars))
        if previous_family_var is not None and "ordering" in components:
            model.Add(previous_family_var <= family_var)
            family_ordering_constraints += 1
        previous_family_var = family_var
        slot_count += 1
    added_constraints = (
        active_domain_constraints
        + membership_reification_constraints
        + membership_sum_constraints
        + shell_pair_table_constraints
        + family_ordering_constraints
    )
    return {
        "mode": mode_text,
        "components": sorted(components),
        "slot_count": int(slot_count),
        "family_count": int(family_count),
        "family_lit_total": int(family_lit_total),
        "active_domain_constraint_count": int(active_domain_constraints),
        "membership_reification_constraint_count": int(membership_reification_constraints),
        "membership_sum_constraint_count": int(membership_sum_constraints),
        "shell_pair_table_constraint_count": int(shell_pair_table_constraints),
        "family_ordering_constraint_count": int(family_ordering_constraints),
        "enforced_row_total": int(enforced_row_total),
        "added_constraint_count": int(added_constraints),
        "diagnostic_semantics": "rebuilt_family_lookup_channeling_not_proof_source_until_validated",
    }


def _remove_conditioned_power_family_bound_constraints_payload(
    model_proto: Any,
    *,
    count_var_index: int,
    u_var_index: int,
) -> Dict[str, Any]:
    remove_indices: list[int] = []
    removed_bounds: list[int] = []
    removed_global_bounds: list[int] = []
    constraints = getattr(model_proto, "constraints", [])
    for constraint_idx, constraint in enumerate(list(constraints)):
        linear = getattr(constraint, "linear", None) if _constraint_has_field(constraint, "linear") else None
        if linear is None:
            continue
        vars_ = [int(var_idx) for var_idx in list(linear.vars)]
        if sorted(vars_) != sorted([int(count_var_index), int(u_var_index)]):
            continue
        coeff_by_var = {
            int(var_idx): int(coeff)
            for var_idx, coeff in zip(list(linear.vars), list(linear.coeffs))
        }
        if coeff_by_var.get(int(count_var_index)) != 1:
            continue
        if int(coeff_by_var.get(int(u_var_index), 0)) <= 0:
            continue
        if list(getattr(constraint, "enforcement_literal", [])):
            continue
        domain = [int(value) for value in list(linear.domain)]
        if len(domain) != 2 or domain[1] >= 9_000_000_000_000_000_000:
            continue
        removed_global_bounds.append(int(coeff_by_var[int(u_var_index)]))
        removed_bounds.append(int(domain[1] - int(coeff_by_var[int(u_var_index)])))
        remove_indices.append(int(constraint_idx))

    if remove_indices:
        _delete_constraint_indices(model_proto, remove_indices)
    return {
        "removed_constraint_count": int(len(remove_indices)),
        "removed_constraint_indices": [int(index) for index in remove_indices],
        "implied_conditioned_upper_bound": (
            int(removed_bounds[0]) if removed_bounds else None
        ),
        "implied_global_upper_bound": (
            int(removed_global_bounds[0]) if removed_global_bounds else None
        ),
        "removed_conditioned_upper_bounds": [int(value) for value in removed_bounds],
    }


def _remove_power_coverage_linear_constraints_payload(
    model_proto: Any,
    *,
    mode: str,
) -> Dict[str, Any]:
    mode_text = str(mode)
    prefix_by_mode = {
        "power_coverage_active_requirement_relaxed": ("cover_choice_active__",),
        "power_coverage_geometry_bounds_relaxed": (
            "cover_choice_x__",
            "cover_choice_y__",
        ),
        "power_coverage_active_and_geometry_relaxed": (
            "cover_choice_active__",
            "cover_choice_x__",
            "cover_choice_y__",
        ),
    }
    prefixes = prefix_by_mode.get(mode_text)
    if prefixes is None:
        raise ValueError(f"Unsupported power coverage relaxation mode: {mode!r}")

    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
    remove_indices: list[int] = []
    removed_by_prefix: Dict[str, int] = {str(prefix): 0 for prefix in prefixes}
    constraints = getattr(model_proto, "constraints", [])
    for constraint_idx, constraint in enumerate(list(constraints)):
        linear = getattr(constraint, "linear", None) if _constraint_has_field(constraint, "linear") else None
        if linear is None:
            continue
        matched_prefixes: set[str] = set()
        for var_idx in list(getattr(linear, "vars", [])):
            name = var_names.get(int(var_idx), "")
            for prefix in prefixes:
                if name.startswith(str(prefix)):
                    matched_prefixes.add(str(prefix))
        if not matched_prefixes:
            continue
        remove_indices.append(int(constraint_idx))
        for prefix in matched_prefixes:
            removed_by_prefix[str(prefix)] = int(removed_by_prefix.get(str(prefix), 0)) + 1

    if remove_indices:
        _delete_constraint_indices(model_proto, remove_indices)
    return {
        "mode": mode_text,
        "removed_constraint_count": int(len(remove_indices)),
        "removed_constraint_indices": [int(index) for index in remove_indices],
        "var_name_prefixes": [str(prefix) for prefix in prefixes],
        "removed_by_prefix": dict(sorted(removed_by_prefix.items())),
    }


def _remove_power_coverage_dynamic_constraints_payload(
    model_proto: Any,
    *,
    mode: str,
) -> Dict[str, Any]:
    mode_text = str(mode)
    if mode_text not in POWER_COVERAGE_DYNAMIC_RELAXATION_VARIANTS:
        raise ValueError(f"Unsupported power coverage dynamic relaxation mode: {mode!r}")

    element_payload: Dict[str, Any] = {"removed_constraint_count": 0}
    linear_payload: Dict[str, Any] = {"removed_constraint_count": 0}
    no_overlap_payload: Dict[str, Any] = {"removed_interval_pair_count": 0}
    if mode_text in {
        "power_coverage_witness_element_relaxed",
        "power_coverage_witness_element_and_linear_relaxed",
        "power_coverage_dynamic_coupling_relaxed",
        "power_coverage_dynamic_and_family_count_relaxed",
        "power_coverage_dynamic_and_family_membership_count_relaxed",
        "power_coverage_dynamic_and_family_lookup_relaxed",
        "power_coverage_dynamic_and_family_distance_relaxed",
        "power_coverage_dynamic_and_family_lookup_distance_relaxed",
        "power_coverage_dynamic_and_family_assignment_relaxed",
        "power_coverage_dynamic_family_assignment_and_gvi_relaxed",
    }:
        element_payload = _remove_power_coverage_element_constraints_payload(
            model_proto,
        )
    if mode_text in {
        "power_coverage_witness_element_and_linear_relaxed",
        "power_coverage_dynamic_coupling_relaxed",
        "power_coverage_dynamic_and_family_count_relaxed",
        "power_coverage_dynamic_and_family_membership_count_relaxed",
        "power_coverage_dynamic_and_family_lookup_relaxed",
        "power_coverage_dynamic_and_family_distance_relaxed",
        "power_coverage_dynamic_and_family_lookup_distance_relaxed",
        "power_coverage_dynamic_and_family_assignment_relaxed",
        "power_coverage_dynamic_family_assignment_and_gvi_relaxed",
    }:
        linear_payload = _remove_power_coverage_linear_constraints_payload(
            model_proto,
            mode="power_coverage_active_and_geometry_relaxed",
        )
    if mode_text in {
        "power_pole_no_overlap_relaxed",
        "power_coverage_dynamic_coupling_relaxed",
        "power_coverage_dynamic_and_family_count_relaxed",
        "power_coverage_dynamic_and_family_membership_count_relaxed",
        "power_coverage_dynamic_and_family_lookup_relaxed",
        "power_coverage_dynamic_and_family_distance_relaxed",
        "power_coverage_dynamic_and_family_lookup_distance_relaxed",
        "power_coverage_dynamic_and_family_assignment_relaxed",
        "power_coverage_dynamic_family_assignment_and_gvi_relaxed",
    }:
        no_overlap_payload = _remove_power_pole_intervals_from_no_overlap_2d_payload(
            model_proto,
        )
    return {
        "mode": mode_text,
        "removed_constraint_count": int(
            element_payload.get("removed_constraint_count", 0)
        )
        + int(linear_payload.get("removed_constraint_count", 0))
        + int(no_overlap_payload.get("touched_constraint_count", 0)),
        "element_constraints": element_payload,
        "linear_constraints": linear_payload,
        "no_overlap_2d": no_overlap_payload,
    }


def _remove_power_coverage_element_constraints_payload(model_proto: Any) -> Dict[str, Any]:
    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
    prefixes = (
        "cover_choice_idx__",
        "cover_choice_block_idx__",
        "cover_choice_local_idx__",
        "cover_choice_active__",
        "cover_choice_block_active__",
        "cover_choice_x__",
        "cover_choice_block_x__",
        "cover_choice_y__",
        "cover_choice_block_y__",
    )
    remove_indices: list[int] = []
    removed_by_prefix: Dict[str, int] = {str(prefix): 0 for prefix in prefixes}
    constraints = getattr(model_proto, "constraints", [])
    for constraint_idx, constraint in enumerate(list(constraints)):
        element = (
            getattr(constraint, "element", None)
            if _constraint_has_field(constraint, "element")
            else None
        )
        if element is None:
            continue
        matched_prefixes: set[str] = set()
        for var_idx in _element_var_indices(element):
            name = var_names.get(int(var_idx), "")
            for prefix in prefixes:
                if name.startswith(str(prefix)):
                    matched_prefixes.add(str(prefix))
        if not matched_prefixes:
            continue
        remove_indices.append(int(constraint_idx))
        for prefix in matched_prefixes:
            removed_by_prefix[str(prefix)] = int(removed_by_prefix.get(str(prefix), 0)) + 1

    if remove_indices:
        _delete_constraint_indices(model_proto, remove_indices)
    return {
        "removed_constraint_count": int(len(remove_indices)),
        "removed_constraint_indices": [int(index) for index in remove_indices],
        "var_name_prefixes": [str(prefix) for prefix in prefixes],
        "removed_by_prefix": dict(sorted(removed_by_prefix.items())),
    }


def _remove_power_pole_intervals_from_no_overlap_2d_payload(
    model_proto: Any,
) -> Dict[str, Any]:
    constraints = getattr(model_proto, "constraints", [])
    interval_names = {
        int(index): str(getattr(constraint, "name", ""))
        for index, constraint in enumerate(list(constraints))
        if _constraint_has_field(constraint, "interval")
    }
    touched_indices: list[int] = []
    removed_pairs_by_constraint: Dict[str, int] = {}
    for constraint_idx, constraint in enumerate(list(constraints)):
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
        removed = 0
        for x_idx, y_idx in zip(x_intervals, y_intervals):
            x_name = interval_names.get(int(x_idx), "")
            y_name = interval_names.get(int(y_idx), "")
            if x_name.startswith("x_iv__residual_optional::power_pole::") and y_name.startswith(
                "y_iv__residual_optional::power_pole::"
            ):
                removed += 1
                continue
            kept_x.append(int(x_idx))
            kept_y.append(int(y_idx))
        if removed <= 0:
            continue
        _replace_repeated_int64(getattr(no_overlap, "x_intervals"), kept_x)
        _replace_repeated_int64(getattr(no_overlap, "y_intervals"), kept_y)
        touched_indices.append(int(constraint_idx))
        removed_pairs_by_constraint[str(constraint_idx)] = int(removed)
    return {
        "removed_interval_pair_count": int(sum(removed_pairs_by_constraint.values())),
        "touched_constraint_count": int(len(touched_indices)),
        "touched_constraint_indices": [int(index) for index in touched_indices],
        "removed_interval_pairs_by_constraint": dict(sorted(removed_pairs_by_constraint.items())),
    }


def _replace_repeated_int64(repeated: Any, values: Sequence[int]) -> None:
    clearer = getattr(repeated, "clear", None)
    if callable(clearer):
        clearer()
    else:
        del repeated[:]
    extender = getattr(repeated, "extend", None)
    if callable(extender):
        extender([int(value) for value in values])
        return
    for value in values:
        repeated.append(int(value))


def _remove_power_capacity_gvi_constraints_payload(
    model_proto: Any,
    *,
    templates: Sequence[str],
    template_coefficients: Mapping[str, Mapping[int, int]],
    template_demands: Mapping[str, int],
) -> Dict[str, Any]:
    wanted_templates = [str(template) for template in templates]
    wanted = {
        str(template): {
            int(var_idx): int(coeff)
            for var_idx, coeff in dict(template_coefficients.get(str(template), {})).items()
            if int(coeff) > 0
        }
        for template in wanted_templates
    }
    demands = {str(template): int(demand) for template, demand in dict(template_demands).items()}
    remove_indices: list[int] = []
    removed_templates: list[str] = []
    constraints = getattr(model_proto, "constraints", [])
    for constraint_idx, constraint in enumerate(list(constraints)):
        linear = getattr(constraint, "linear", None) if _constraint_has_field(constraint, "linear") else None
        if linear is None:
            continue
        if list(getattr(constraint, "enforcement_literal", [])):
            continue
        vars_ = [int(var_idx) for var_idx in list(getattr(linear, "vars", []))]
        coeff_by_var = {
            int(var_idx): int(coeff)
            for var_idx, coeff in zip(vars_, list(getattr(linear, "coeffs", [])))
        }
        domain = [int(value) for value in list(getattr(linear, "domain", []))]
        if len(domain) != 2 or domain[0] <= 0 or domain[1] < 9_000_000_000_000_000_000:
            continue
        for template, expected_coeffs in sorted(wanted.items()):
            if not expected_coeffs:
                continue
            expected_demand = demands.get(str(template))
            if expected_demand is not None and int(domain[0]) != int(expected_demand):
                continue
            if coeff_by_var == expected_coeffs:
                remove_indices.append(int(constraint_idx))
                removed_templates.append(str(template))
                break

    if remove_indices:
        _delete_constraint_indices(model_proto, remove_indices)
    return {
        "requested_templates": wanted_templates,
        "removed_templates": removed_templates,
        "removed_constraint_count": int(len(remove_indices)),
        "removed_constraint_indices": [int(index) for index in remove_indices],
        "template_coefficients": {
            str(template): {
                str(var_idx): int(coeff)
                for var_idx, coeff in sorted(coeffs.items())
            }
            for template, coeffs in sorted(wanted.items())
        },
        "template_demands": {
            str(template): int(demands.get(str(template), 0))
            for template in wanted_templates
        },
    }


def _remove_power_family_layer_constraints_payload(
    model_proto: Any,
    *,
    mode: str,
) -> Dict[str, Any]:
    mode_text = str(mode)
    prefix_by_mode = {
        "power_family_count_constraints_relaxed": ("power_pole_family_count__",),
        "power_family_membership_and_count_constraints_relaxed": (
            "power_pole_family_count__",
            "is_family__",
        ),
        "power_family_assignment_layer_relaxed": (
            "power_pole_family_count__",
            "is_family__",
            "family__",
            "same_family__",
            "dx__",
            "dy__",
            "d_lo__",
            "d_hi__",
        ),
        "power_family_lookup_constraints_relaxed": ("family__",),
        "power_family_lookup_table_constraints_relaxed": ("family__",),
        "power_family_lookup_linear_constraints_relaxed": ("family__",),
        "power_family_lookup_sentinel_constraints_relaxed": ("family__",),
        "power_family_lookup_membership_linear_constraints_relaxed": ("family__",),
        "power_family_lookup_ordering_linear_constraints_relaxed": ("family__",),
        "power_family_lookup_other_linear_constraints_relaxed": ("family__",),
        "power_family_distance_constraints_relaxed": (
            "dx__",
            "dy__",
            "d_lo__",
            "d_hi__",
        ),
        "power_family_lookup_distance_constraints_relaxed": (
            "family__",
            "dx__",
            "dy__",
            "d_lo__",
            "d_hi__",
        ),
    }
    prefixes = prefix_by_mode.get(mode_text)
    if prefixes is None:
        raise ValueError(f"Unsupported power family layer relaxation mode: {mode!r}")

    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
    var_domains = {
        int(index): [int(value) for value in list(getattr(var, "domain", []))]
        for index, var in enumerate(variables)
    }
    remove_indices: list[int] = []
    removed_by_prefix: Dict[str, int] = {str(prefix): 0 for prefix in prefixes}
    removed_by_family_linear_category: Dict[str, int] = {}
    constraints = getattr(model_proto, "constraints", [])
    for constraint_idx, constraint in enumerate(list(constraints)):
        if mode_text == "power_family_lookup_table_constraints_relaxed" and not _constraint_has_field(
            constraint,
            "table",
        ):
            continue
        if mode_text == "power_family_lookup_linear_constraints_relaxed" and not _constraint_has_field(
            constraint,
            "linear",
        ):
            continue
        if mode_text in {
            "power_family_lookup_sentinel_constraints_relaxed",
            "power_family_lookup_membership_linear_constraints_relaxed",
            "power_family_lookup_ordering_linear_constraints_relaxed",
            "power_family_lookup_other_linear_constraints_relaxed",
        } and not _constraint_has_field(constraint, "linear"):
            continue
        category = _family_lookup_linear_constraint_category(
            constraint,
            var_names=var_names,
            var_domains=var_domains,
        )
        if (
            mode_text == "power_family_lookup_sentinel_constraints_relaxed"
            and category != "sentinel_inactive"
        ):
            continue
        if (
            mode_text == "power_family_lookup_membership_linear_constraints_relaxed"
            and category != "membership_reification"
        ):
            continue
        if (
            mode_text == "power_family_lookup_ordering_linear_constraints_relaxed"
            and category != "family_ordering"
        ):
            continue
        if (
            mode_text == "power_family_lookup_other_linear_constraints_relaxed"
            and category != "other_family_linear"
        ):
            continue
        matched_prefixes: set[str] = set()
        for var_idx in _constraint_var_indices(constraint):
            name = var_names.get(int(var_idx), "")
            for prefix in prefixes:
                if name.startswith(str(prefix)):
                    matched_prefixes.add(str(prefix))
        if not matched_prefixes:
            continue
        remove_indices.append(int(constraint_idx))
        for prefix in matched_prefixes:
            removed_by_prefix[str(prefix)] = int(removed_by_prefix.get(str(prefix), 0)) + 1
        if category is not None:
            removed_by_family_linear_category[str(category)] = (
                int(removed_by_family_linear_category.get(str(category), 0)) + 1
            )

    if remove_indices:
        _delete_constraint_indices(model_proto, remove_indices)
    return {
        "mode": mode_text,
        "removed_constraint_count": int(len(remove_indices)),
        "removed_constraint_indices": [int(index) for index in remove_indices],
        "var_name_prefixes": [str(prefix) for prefix in prefixes],
        "removed_by_prefix": dict(sorted(removed_by_prefix.items())),
        "removed_by_family_linear_category": dict(
            sorted(removed_by_family_linear_category.items())
        ),
    }


def _constraint_var_indices(constraint: Any) -> list[int]:
    indices: set[int] = set()
    linear = getattr(constraint, "linear", None) if _constraint_has_field(constraint, "linear") else None
    if linear is not None and list(getattr(linear, "vars", [])):
        indices.update(int(var_idx) for var_idx in list(getattr(linear, "vars", [])))
    table = getattr(constraint, "table", None) if _constraint_has_field(constraint, "table") else None
    if table is not None and list(getattr(table, "vars", [])):
        indices.update(int(var_idx) for var_idx in list(getattr(table, "vars", [])))
    if table is not None and list(getattr(table, "exprs", [])):
        for expr in list(getattr(table, "exprs", [])):
            indices.update(int(var_idx) for var_idx in list(getattr(expr, "vars", [])))
    element = getattr(constraint, "element", None) if _constraint_has_field(constraint, "element") else None
    if element is not None:
        indices.update(_element_var_indices(element))
    lin_max = getattr(constraint, "lin_max", None) if _constraint_has_field(constraint, "lin_max") else None
    if lin_max is not None:
        target = getattr(lin_max, "target", None)
        vars_ = getattr(target, "vars", None)
        if vars_ is not None:
            indices.update(int(var_idx) for var_idx in list(vars_))
        for expr in list(getattr(lin_max, "exprs", [])):
            indices.update(int(var_idx) for var_idx in list(getattr(expr, "vars", [])))
    return sorted(indices)


def _family_lookup_linear_constraint_category(
    constraint: Any,
    *,
    var_names: Mapping[int, str],
    var_domains: Mapping[int, Sequence[int]],
) -> Optional[str]:
    if not _constraint_has_field(constraint, "linear"):
        return None
    linear = getattr(constraint, "linear", None)
    if linear is None:
        return None
    var_indices = [int(var_idx) for var_idx in list(getattr(linear, "vars", []))]
    family_vars = [
        int(var_idx)
        for var_idx in var_indices
        if str(var_names.get(int(var_idx), "")).startswith("family__")
    ]
    if not family_vars:
        return None
    enforcement_literals = [int(lit) for lit in list(getattr(constraint, "enforcement_literal", []))]
    enforcement_names = [
        str(var_names.get(_literal_var_index(lit), ""))
        for lit in enforcement_literals
    ]
    if any(name.startswith("is_family__") for name in enforcement_names):
        return "membership_reification"
    if len(family_vars) >= 2:
        return "family_ordering"
    if len(family_vars) == 1:
        family_var = int(family_vars[0])
        domain = [int(value) for value in list(getattr(linear, "domain", []))]
        sentinel = _family_var_sentinel_value(var_domains.get(family_var, []))
        if (
            sentinel is not None
            and len(enforcement_literals) == 1
            and enforcement_literals[0] < 0
            and enforcement_names[0].startswith("active__")
            and domain == [int(sentinel), int(sentinel)]
        ):
            return "sentinel_inactive"
    return "other_family_linear"


def _literal_var_index(literal: int) -> int:
    literal = int(literal)
    return literal if literal >= 0 else -literal - 1


def _family_var_sentinel_value(domain: Sequence[int]) -> Optional[int]:
    values = [int(value) for value in list(domain)]
    if not values:
        return None
    return int(values[-1])


def _element_var_indices(element: Any) -> list[int]:
    indices: set[int] = set()
    has_linear_expr = False
    indices.update(int(var_idx) for var_idx in list(getattr(element, "vars", [])))
    for expr_attr in ("linear_index", "linear_target"):
        has_method = getattr(element, f"has_{expr_attr}", None)
        try:
            has_expr = bool(has_method()) if callable(has_method) else False
        except Exception:
            has_expr = False
        if not has_expr:
            continue
        has_linear_expr = True
        expr = getattr(element, expr_attr, None)
        if expr is not None:
            indices.update(int(var_idx) for var_idx in list(getattr(expr, "vars", [])))
    if not has_linear_expr:
        for attr in ("index", "target"):
            value = getattr(element, attr, None)
            try:
                if value is not None and int(value) >= 0:
                    indices.add(int(value))
            except Exception:
                pass
    for expr in list(getattr(element, "exprs", [])):
        indices.update(int(var_idx) for var_idx in list(getattr(expr, "vars", [])))
    return sorted(indices)


def _constraint_has_field(constraint: Any, field_name: str) -> bool:
    has_method = getattr(constraint, f"has_{field_name}", None)
    try:
        if has_method is not None:
            return bool(has_method())
    except Exception:
        pass
    has_field = getattr(constraint, "HasField", None)
    try:
        if has_field is not None:
            return bool(has_field(str(field_name)))
    except Exception:
        pass
    return False


def _delete_constraint_indices(model_proto: Any, remove_indices: Sequence[int]) -> None:
    constraints = getattr(model_proto, "constraints", [])
    remove_set = {int(index) for index in remove_indices}
    for constraint_idx in sorted(remove_set):
        if constraint_idx < 0 or constraint_idx >= len(constraints):
            continue
        _replace_constraint_with_tautology(constraints[int(constraint_idx)])


def _replace_constraint_with_tautology(constraint: Any) -> None:
    empty_constraint = constraint.__class__()
    copier = getattr(constraint, "copy_from", None)
    if callable(copier):
        copier(empty_constraint)
    else:
        copier = getattr(constraint, "CopyFrom", None)
        if callable(copier):
            copier(empty_constraint)
        else:
            clearer = getattr(constraint, "Clear", None)
            if callable(clearer):
                clearer()
            else:
                clearer = getattr(constraint, "clear", None)
                if callable(clearer):
                    clearer()
                else:
                    for field_name in (
                        "bool_or",
                        "bool_and",
                        "at_most_one",
                        "exactly_one",
                        "linear",
                        "all_diff",
                        "element",
                        "circuit",
                        "routes",
                        "table",
                        "automaton",
                        "inverse",
                        "reservoir",
                        "interval",
                        "no_overlap",
                        "no_overlap_2d",
                        "cumulative",
                        "dummy_constraint",
                    ):
                        clear_field = getattr(constraint, "ClearField", None)
                        if callable(clear_field):
                            try:
                                clear_field(field_name)
                            except Exception:
                                continue
    constraint.linear.domain.append(0)
    constraint.linear.domain.append(0)


def _normalize_variants(variants: Sequence[str]) -> tuple[str, ...]:
    allowed = set(ALLOWED_SLICE_VARIANTS)
    result: list[str] = []
    seen: set[str] = set()
    for raw in variants:
        token = str(raw).strip()
        if not token:
            continue
        if token not in allowed:
            raise ValueError(f"Unsupported model-slice variant: {raw!r}")
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
    return tuple(result or DEFAULT_SLICE_VARIANTS)


def _status_from_entries(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    counts = _status_counts(entries)
    findings = _diagnostic_findings(entries)
    if not entries:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_slice_entries",
            "status_counts": counts,
            "recommendation": "No model-slice entries were evaluated.",
        }
    if any(str(entry.get("status")) == "UNKNOWN" for entry in entries):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "slice_unknown_remaining",
            "status_counts": counts,
            "recommendation": (
                "Model-slice findings point at "
                + ", ".join(findings)
                + "; diagnostic only, not proof source."
                if findings
                else "At least one model-slice entry remains UNKNOWN; compare mutated variants with base for diagnostic direction only."
            ),
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "slice_variants_classified",
        "status_counts": counts,
        "recommendation": "All model-slice variants returned terminal statuses; remember these mutated slices are diagnostic only.",
    }


def _status_counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status", "UNKNOWN"))
        counts[status] = int(counts.get(status, 0)) + 1
    return counts


def _status_counts_by_key(
    entries: Sequence[Mapping[str, Any]],
    key_name: str,
) -> Dict[str, Dict[str, int]]:
    grouped: Dict[str, Dict[str, int]] = {}
    for entry in entries:
        key = str(entry.get(key_name))
        status = str(entry.get("status", "UNKNOWN"))
        bucket = grouped.setdefault(key, {})
        bucket[status] = int(bucket.get(status, 0)) + 1
    return grouped


def _diagnostic_findings(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    by_anchor: Dict[int, Dict[str, str]] = {}
    for entry in entries:
        if not bool(entry.get("evaluated", False)):
            continue
        try:
            anchor_idx = int(entry.get("anchor_idx"))
        except Exception:
            continue
        bucket = by_anchor.setdefault(anchor_idx, {})
        bucket[str(entry.get("variant"))] = str(entry.get("status"))
    findings: list[str] = []
    for anchor_idx, statuses in sorted(by_anchor.items()):
        base_status = statuses.get("base")
        if base_status != "UNKNOWN":
            continue
        if statuses.get("residual_all_inactive") == "INFEASIBLE":
            findings.append(f"anchor_{anchor_idx}:residual_optionals_drive_unknown")
        if statuses.get("protocol_boxes_inactive") == "INFEASIBLE":
            findings.append(f"anchor_{anchor_idx}:protocol_boxes_drive_unknown")
        if statuses.get("power_poles_inactive") == "INFEASIBLE":
            findings.append(f"anchor_{anchor_idx}:power_poles_drive_unknown")
        if statuses.get("skip_power_coverage_core") in {"OPTIMAL", "FEASIBLE"}:
            findings.append(f"anchor_{anchor_idx}:power_coverage_core_required_for_blocker")
        active_relaxed_status = statuses.get("power_coverage_active_requirement_relaxed")
        if active_relaxed_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_active_requirement_drives_unknown"
            )
        elif active_relaxed_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_active_requirement_relaxation_still_unknown"
            )
        geometry_relaxed_status = statuses.get("power_coverage_geometry_bounds_relaxed")
        if geometry_relaxed_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_geometry_bounds_drive_unknown"
            )
        elif geometry_relaxed_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_geometry_bounds_relaxation_still_unknown"
            )
        combined_relaxed_status = statuses.get(
            "power_coverage_active_and_geometry_relaxed"
        )
        if combined_relaxed_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_active_and_geometry_relaxation_unlocks_core"
            )
        elif combined_relaxed_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_active_and_geometry_relaxation_still_unknown"
            )
        element_relaxed_status = statuses.get("power_coverage_witness_element_relaxed")
        if element_relaxed_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_witness_element_relaxation_unlocks_core"
            )
        elif element_relaxed_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_witness_element_relaxation_still_unknown"
            )
        element_linear_status = statuses.get(
            "power_coverage_witness_element_and_linear_relaxed"
        )
        if element_linear_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_witness_element_and_linear_relaxation_unlocks_core"
            )
        elif element_linear_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_witness_element_and_linear_relaxation_still_unknown"
            )
        no_overlap_status = statuses.get("power_pole_no_overlap_relaxed")
        if no_overlap_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_pole_no_overlap_relaxation_unlocks_core"
            )
        elif no_overlap_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_pole_no_overlap_relaxation_still_unknown"
            )
        dynamic_status = statuses.get("power_coverage_dynamic_coupling_relaxed")
        if dynamic_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_coupling_relaxation_unlocks_core"
            )
        elif dynamic_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_coupling_relaxation_still_unknown"
            )
        dynamic_count_status = statuses.get(
            "power_coverage_dynamic_and_family_count_relaxed"
        )
        if dynamic_count_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_count_relaxation_unlocks_core"
            )
        elif dynamic_count_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_count_relaxation_still_unknown"
            )
        dynamic_membership_status = statuses.get(
            "power_coverage_dynamic_and_family_membership_count_relaxed"
        )
        if dynamic_membership_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_membership_count_relaxation_unlocks_core"
            )
        elif dynamic_membership_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_membership_count_relaxation_still_unknown"
            )
        dynamic_table_status = statuses.get(
            "power_coverage_dynamic_and_family_table_relaxed"
        )
        if dynamic_table_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_table_relaxation_unlocks_core"
            )
        elif dynamic_table_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_table_relaxation_still_unknown"
            )
        dynamic_linear_status = statuses.get(
            "power_coverage_dynamic_and_family_linear_relaxed"
        )
        if dynamic_linear_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_linear_relaxation_unlocks_core"
            )
        elif dynamic_linear_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_linear_relaxation_still_unknown"
            )
        dynamic_sentinel_status = statuses.get(
            "power_coverage_dynamic_and_family_sentinel_relaxed"
        )
        if dynamic_sentinel_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_sentinel_relaxation_unlocks_core"
            )
        elif dynamic_sentinel_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_sentinel_relaxation_still_unknown"
            )
        dynamic_membership_linear_status = statuses.get(
            "power_coverage_dynamic_and_family_membership_linear_relaxed"
        )
        if dynamic_membership_linear_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_membership_linear_relaxation_unlocks_core"
            )
        elif dynamic_membership_linear_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_membership_linear_relaxation_still_unknown"
            )
        dynamic_ordering_status = statuses.get(
            "power_coverage_dynamic_and_family_ordering_linear_relaxed"
        )
        if dynamic_ordering_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_ordering_linear_relaxation_unlocks_core"
            )
        elif dynamic_ordering_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_ordering_linear_relaxation_still_unknown"
            )
        dynamic_other_linear_status = statuses.get(
            "power_coverage_dynamic_and_family_other_linear_relaxed"
        )
        if dynamic_other_linear_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_other_linear_relaxation_unlocks_core"
            )
        elif dynamic_other_linear_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_other_linear_relaxation_still_unknown"
            )
        dynamic_lookup_status = statuses.get(
            "power_coverage_dynamic_and_family_lookup_relaxed"
        )
        if dynamic_lookup_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core"
            )
        elif dynamic_lookup_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_lookup_relaxation_still_unknown"
            )
        dynamic_distance_status = statuses.get(
            "power_coverage_dynamic_and_family_distance_relaxed"
        )
        if dynamic_distance_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_distance_relaxation_unlocks_core"
            )
        elif dynamic_distance_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_distance_relaxation_still_unknown"
            )
        dynamic_lookup_distance_status = statuses.get(
            "power_coverage_dynamic_and_family_lookup_distance_relaxed"
        )
        if dynamic_lookup_distance_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_lookup_distance_relaxation_unlocks_core"
            )
        elif dynamic_lookup_distance_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_lookup_distance_relaxation_still_unknown"
            )
        dynamic_family_status = statuses.get(
            "power_coverage_dynamic_and_family_assignment_relaxed"
        )
        if dynamic_family_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_assignment_relaxation_unlocks_core"
            )
        elif dynamic_family_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_assignment_relaxation_still_unknown"
            )
        dynamic_family_gvi_status = statuses.get(
            "power_coverage_dynamic_family_assignment_and_gvi_relaxed"
        )
        if dynamic_family_gvi_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_family_assignment_and_gvi_relaxation_unlocks_core"
            )
        elif dynamic_family_gvi_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_family_assignment_and_gvi_relaxation_still_unknown"
            )
        active_channel_status = statuses.get("family_active_domain_channeling_added")
        if active_channel_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:family_active_domain_channeling_unlocks_core"
            )
        elif active_channel_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:family_active_domain_channeling_still_unknown"
            )
        membership_channel_status = statuses.get("family_membership_active_channeling_added")
        if membership_channel_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:family_membership_active_channeling_unlocks_core"
            )
        elif membership_channel_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:family_membership_active_channeling_still_unknown"
            )
        combined_channel_status = statuses.get(
            "family_active_and_membership_channeling_added"
        )
        if combined_channel_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:family_active_and_membership_channeling_unlocks_core"
            )
        elif combined_channel_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:family_active_and_membership_channeling_still_unknown"
            )
        shell_pair_status = statuses.get("family_shell_pair_tables_added")
        if shell_pair_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:family_shell_pair_tables_unlocks_core"
            )
        elif shell_pair_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:family_shell_pair_tables_still_unknown"
            )
        dynamic_shell_pair_status = statuses.get(
            "power_coverage_dynamic_and_family_shell_pair_tables_added"
        )
        if dynamic_shell_pair_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_shell_pair_tables_unlocks_core"
            )
        elif dynamic_shell_pair_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_shell_pair_tables_still_unknown"
            )
        rebuild_status = statuses.get("family_lookup_rebuilt_channeling")
        if rebuild_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:family_lookup_rebuilt_channeling_unlocks_core"
            )
        elif rebuild_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:family_lookup_rebuilt_channeling_still_unknown"
            )
        dynamic_rebuild_status = statuses.get(
            "power_coverage_dynamic_and_family_lookup_rebuilt_channeling"
        )
        if dynamic_rebuild_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_lookup_rebuilt_channeling_unlocks_core"
            )
        elif dynamic_rebuild_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown"
            )
        rebuild_component_variants = {
            "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only": (
                "membership_only"
            ),
            "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only": (
                "shell_pair_only"
            ),
            "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only": (
                "ordering_only"
            ),
            "power_coverage_dynamic_and_family_lookup_rebuilt_membership_shell_pair": (
                "membership_shell_pair"
            ),
            "power_coverage_dynamic_and_family_lookup_rebuilt_membership_ordering": (
                "membership_ordering"
            ),
            "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_ordering": (
                "shell_pair_ordering"
            ),
        }
        for variant_name, finding_label in rebuild_component_variants.items():
            component_status = statuses.get(variant_name)
            if component_status in {"OPTIMAL", "FEASIBLE"}:
                findings.append(
                    f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_lookup_rebuilt_{finding_label}_unlocks_core"
                )
            elif component_status == "UNKNOWN":
                findings.append(
                    f"anchor_{anchor_idx}:power_coverage_dynamic_and_family_lookup_rebuilt_{finding_label}_still_unknown"
                )
        protocol_gvi_status = statuses.get(
            "power_capacity_gvi_protocol_storage_box_relaxed"
        )
        if protocol_gvi_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:protocol_storage_box_power_capacity_gvi_drives_unknown"
            )
        elif protocol_gvi_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:protocol_storage_box_power_capacity_gvi_relaxation_still_unknown"
            )
        mandatory_gvi_status = statuses.get(
            "power_capacity_gvi_mandatory_templates_relaxed"
        )
        if mandatory_gvi_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:mandatory_template_power_capacity_gvi_drives_unknown"
            )
        elif mandatory_gvi_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:mandatory_template_power_capacity_gvi_relaxation_still_unknown"
            )
        all_gvi_status = statuses.get("power_capacity_gvi_all_relaxed")
        if all_gvi_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:all_power_capacity_gvi_relaxation_unlocks_core"
            )
        elif all_gvi_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:all_power_capacity_gvi_relaxation_still_unknown"
            )
        count_layer_status = statuses.get("power_family_count_constraints_relaxed")
        if count_layer_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_family_count_constraints_drive_unknown"
            )
        elif count_layer_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_family_count_constraints_relaxation_still_unknown"
            )
        membership_layer_status = statuses.get(
            "power_family_membership_and_count_constraints_relaxed"
        )
        if membership_layer_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_family_membership_and_count_constraints_drive_unknown"
            )
        elif membership_layer_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_family_membership_and_count_constraints_relaxation_still_unknown"
            )
        assignment_layer_status = statuses.get("power_family_assignment_layer_relaxed")
        if assignment_layer_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:power_family_assignment_layer_drives_unknown"
            )
        elif assignment_layer_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:power_family_assignment_layer_relaxation_still_unknown"
            )
        if statuses.get("no_protocol_lower_bound_core") == "UNKNOWN":
            findings.append(f"anchor_{anchor_idx}:protocol_lower_bound_not_primary")
        if statuses.get("skip_power_coverage_no_protocol_lower_bound_core") in {
            "OPTIMAL",
            "FEASIBLE",
        }:
            findings.append(f"anchor_{anchor_idx}:skip_power_coverage_unlocks_feasible_core")
        relaxed_status = statuses.get("target_power_family_bound_relaxed")
        if relaxed_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:target_power_family_bound_relaxation_unlocks_feasible_core"
            )
        elif relaxed_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:target_power_family_bound_relaxation_still_unknown"
            )
        relaxed_protocol_status = statuses.get(
            "target_power_family_bound_relaxed_protocol_boxes_inactive"
        )
        if relaxed_protocol_status == "INFEASIBLE":
            findings.append(
                f"anchor_{anchor_idx}:target_power_family_relaxed_protocol_boxes_still_infeasible"
            )
        elif relaxed_protocol_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:target_power_family_relaxed_protocol_boxes_unlock_feasible_core"
            )
        direct_status = statuses.get("target_power_family_bound_direct_after_force")
        if direct_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:target_power_family_direct_bound_unlocks_feasible_core"
            )
        elif direct_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:target_power_family_direct_bound_still_unknown"
            )
        direct_protocol_status = statuses.get(
            "target_power_family_bound_direct_after_force_protocol_boxes_inactive"
        )
        if direct_protocol_status == "INFEASIBLE":
            findings.append(
                f"anchor_{anchor_idx}:target_power_family_direct_bound_protocol_boxes_still_infeasible"
            )
        elif direct_protocol_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:target_power_family_direct_bound_protocol_boxes_unlock_feasible_core"
            )
        all_direct_status = statuses.get("all_conditioned_family_bounds_direct_after_force")
        if all_direct_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:all_conditioned_family_direct_bounds_unlock_feasible_core"
            )
        elif all_direct_status == "UNKNOWN":
            findings.append(
                f"anchor_{anchor_idx}:all_conditioned_family_direct_bounds_still_unknown"
            )
        all_direct_protocol_status = statuses.get(
            "all_conditioned_family_bounds_direct_after_force_protocol_boxes_inactive"
        )
        if all_direct_protocol_status == "INFEASIBLE":
            findings.append(
                f"anchor_{anchor_idx}:all_conditioned_family_direct_bounds_protocol_boxes_still_infeasible"
            )
        elif all_direct_protocol_status in {"OPTIMAL", "FEASIBLE"}:
            findings.append(
                f"anchor_{anchor_idx}:all_conditioned_family_direct_bounds_protocol_boxes_unlock_feasible_core"
            )
    return _dedupe(findings)


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        token = str(value)
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    selected_anchor_count: int,
    status: Mapping[str, Any],
    campaign_state_unchanged: bool,
    model_error: Optional[str],
) -> list[Dict[str, str]]:
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
            "model_slice_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "campaign_state_unchanged",
            "pass" if campaign_state_unchanged else "fail",
            "campaign state hash unchanged"
            if campaign_state_unchanged
            else "campaign state changed during diagnostic",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _first_line(text: str) -> str:
    for line in str(text).splitlines():
        if line.strip():
            return line.strip()
    return ""


def _response_stats_payload(text: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for raw_line in str(text).splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().replace(" ", "_").lower()
        value = value.strip()
        if not key:
            continue
        payload[key] = _parse_response_stats_value(value)
    return payload


def _parse_response_stats_value(value: str) -> Any:
    value = str(value).strip()
    if not value:
        return ""
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if any(token in value for token in (".", "e", "E")):
            return float(value)
        return int(value)
    except Exception:
        return value


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
