from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from ortools.sat.python import cp_model

from src.models._cpsat_compat import cp_model_from_proto
from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
    _check,
    _display_path,
    _file_hash,
    _load_json_mapping,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
)
from src.search.phase3b_forced_anchor_model_slice import (
    _apply_solver_parameter_profile,
    _build_exact_overlay,
    _candidate_ghost_rect,
    _clone_model_proto,
    _constraint_has_field,
    _constraint_var_indices,
    _delete_constraint_indices,
    _family_lookup_linear_constraint_category,
    _first_line,
    _remove_power_coverage_element_constraints_payload,
    _remove_power_coverage_linear_constraints_payload,
    _remove_power_family_layer_constraints_payload,
    _remove_power_pole_intervals_from_no_overlap_2d_payload,
    _power_family_shell_pair_table_payload,
    _response_stats_payload,
)

FORCED_ANCHOR_PROTO_REDUCTION_SOURCE = "phase3b_forced_anchor_proto_reduction_v1"
POWER_COVERAGE_SELECTED_COORD_LITERAL_REPLACEMENT_VARIANT = (
    "replace_power_coverage_elements_with_selected_coord_literals"
)
FAMILY_LOOKUP_LINEAR_SHELL_GUARD_REPLACEMENT_VARIANT = (
    "replace_family_lookup_table_with_linear_shell_guards"
)
POWER_COVERAGE_AND_FAMILY_LINEAR_GUARD_REPLACEMENT_VARIANT = (
    "replace_power_coverage_elements_and_family_lookup_table_with_linear_shell_guards"
)

DEFAULT_PROTO_REDUCTION_VARIANTS = (
    "base",
    "remove_power_coverage_elements",
    "remove_power_coverage_linear",
    "remove_power_pole_no_overlap",
    "remove_family_lookup_table",
    "remove_family_lookup_sentinel_linear",
    "remove_family_lookup_membership_linear",
    "remove_family_lookup_ordering_linear",
    "remove_family_lookup_all_linear",
    "remove_family_lookup_all",
    "remove_power_coverage_dynamic",
    "remove_power_coverage_dynamic_and_family_lookup_all",
    "remove_power_coverage_dynamic_and_family_lookup_table",
    "remove_power_coverage_dynamic_and_family_lookup_all_linear",
    "remove_power_coverage_elements_and_family_lookup_all",
    "remove_power_coverage_linear_and_family_lookup_all",
    "remove_power_pole_no_overlap_and_family_lookup_all",
    "remove_power_coverage_elements_and_family_lookup_table",
    "remove_power_coverage_elements_and_family_lookup_all_linear",
    "remove_power_coverage_linear_and_family_lookup_table",
    "remove_power_coverage_linear_and_family_lookup_all_linear",
    "remove_power_pole_no_overlap_and_family_lookup_table",
    "remove_power_pole_no_overlap_and_family_lookup_all_linear",
    "remove_power_coverage_element_active_and_family_lookup_table",
    "remove_power_coverage_element_x_and_family_lookup_table",
    "remove_power_coverage_element_y_and_family_lookup_table",
    "remove_power_coverage_element_xy_and_family_lookup_table",
    "remove_power_coverage_element_active_x_and_family_lookup_table",
    "remove_power_coverage_element_active_y_and_family_lookup_table",
    "remove_power_coverage_elements_and_family_lookup_table_first_1",
    "remove_power_coverage_elements_and_family_lookup_table_first_8",
    "remove_power_coverage_elements_and_family_lookup_table_first_32",
    "remove_power_coverage_elements_and_family_lookup_table_first_128",
    "remove_power_coverage_elements_and_family_lookup_table_first_384",
    "remove_power_coverage_elements_and_family_lookup_table_first_512",
    "remove_power_coverage_elements_and_family_lookup_table_first_640",
    "remove_power_coverage_elements_and_family_lookup_table_first_700",
    "remove_power_coverage_elements_and_family_lookup_table_last_384",
    "remove_power_coverage_elements_and_family_lookup_table_last_512",
    "remove_power_coverage_elements_and_family_lookup_table_quarter_0",
    "remove_power_coverage_elements_and_family_lookup_table_quarter_1",
    "remove_power_coverage_elements_and_family_lookup_table_quarter_2",
    "remove_power_coverage_elements_and_family_lookup_table_quarter_3",
    # Sparse/non-contiguous table-slot removals.  These are diagnostic-only
    # variants used to decide whether progress requires removing *all* lookup
    # tables, or merely touching every coarse slot bucket.  Additional dynamic
    # forms are accepted by _is_supported_variant().
    "remove_power_coverage_elements_and_family_lookup_table_every_2",
    "remove_power_coverage_elements_and_family_lookup_table_every_4",
    "remove_power_coverage_elements_and_family_lookup_table_every_8",
    "remove_power_coverage_elements_and_family_lookup_table_mod_2_0",
    "remove_power_coverage_elements_and_family_lookup_table_mod_2_1",
    "remove_power_coverage_elements_and_family_lookup_table_hash_bucket_4_0",
    "remove_power_coverage_elements_and_family_lookup_table_hash_bucket_4_1",
    "remove_power_coverage_elements_and_family_lookup_table_hash_bucket_4_2",
    "remove_power_coverage_elements_and_family_lookup_table_hash_bucket_4_3",
)
TERMINAL_PROTO_REDUCTION_STATUSES = {"OPTIMAL", "FEASIBLE", "INFEASIBLE"}
UNLOCKING_PROTO_REDUCTION_STATUSES = {"OPTIMAL", "FEASIBLE"}

_DYNAMIC_PROTO_REDUCTION_VARIANT_PATTERNS = (
    re.compile(
        r"^remove_power_coverage_elements_and_family_lookup_table_every_(?P<step>\d+)"
        r"(?:_offset_(?P<offset>\d+))?$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_and_family_lookup_table_mod_"
        r"(?P<modulus>\d+)_(?P<remainder>\d+)$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_and_family_lookup_table_hash_bucket_"
        r"(?P<bucket_count>\d+)_(?P<bucket>\d+)$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_and_family_lookup_table_rows_family_mod_"
        r"(?P<modulus>\d+)_(?P<remainder>\d+)$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_template_"
        r"(?P<template>[A-Za-z0-9_]+)_and_family_lookup_table$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_template_"
        r"(?P<template>[A-Za-z0-9_]+?)_target_(?P<targets>[A-Za-z0-9_]+)"
        r"(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_template_"
        r"(?P<template>[A-Za-z0-9_]+?)_target_(?P<targets>[A-Za-z0-9_]+)_element_linear"
        r"(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_template_"
        r"(?P<template>[A-Za-z0-9_]+?)_target_(?P<targets>[A-Za-z0-9_]+?)"
        r"_layer_(?P<layer>final|block)"
        r"_slot_window_(?P<start>\d+)_(?P<count>\d+)"
        r"(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_template_"
        r"(?P<template>[A-Za-z0-9_]+?)_target_(?P<targets>[A-Za-z0-9_]+?)"
        r"_slot_window_(?P<start>\d+)_(?P<count>\d+)"
        r"(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_except_template_"
        r"(?P<template>[A-Za-z0-9_]+?)(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_except_templates_"
        r"(?P<templates>[A-Za-z0-9_+]+)_and_family_lookup_table$"
    ),
    re.compile(
        r"^replace_power_coverage_elements_template_"
        r"(?P<template>[A-Za-z0-9_]+)_with_selected_coord_literals_and_family_lookup_table$"
    ),
    re.compile(
        r"^replace_power_coverage_elements_only_template_"
        r"(?P<template>[A-Za-z0-9_]+)_with_selected_coord_literals_and_family_lookup_table$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_except_template_"
        r"(?P<template>[A-Za-z0-9_]+)_and_template_(?P<targets>[A-Za-z0-9_]+)"
        r"(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_except_template_"
        r"(?P<template>[A-Za-z0-9_]+)_and_template_(?P<targets>[A-Za-z0-9_]+)_element_linear"
        r"(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_except_template_"
        r"(?P<template>[A-Za-z0-9_]+)_and_restrict_template_index_first_(?P<limit>\d+)"
        r"(?P<family_suffix>_and_family_lookup_table)?$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_except_template_"
        r"(?P<template>[A-Za-z0-9_]+)_and_restrict_template_index_last_(?P<limit>\d+)"
        r"(?P<family_suffix>_and_family_lookup_table)?$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_except_template_"
        r"(?P<template>[A-Za-z0-9_]+)_and_restrict_template_index_window_(?P<start>\d+)_(?P<count>\d+)"
        r"(?P<family_suffix>_and_family_lookup_table)?$"
    ),
    re.compile(
        r"^remove_power_coverage_elements_except_template_"
        r"(?P<template>[A-Za-z0-9_]+)_and_add_template_index_active_prefix_guard_and_family_lookup_table$"
    ),
)


def build_phase3b_forced_anchor_proto_reduction(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 1,
    anchor_indices: Optional[Sequence[int]] = None,
    time_limit_seconds: float = 10.0,
    worker_count: int = 4,
    variants: Optional[Sequence[str]] = None,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    before_hash = _file_hash(campaign_path)
    state, state_error = _load_json_mapping(campaign_path)
    candidates = _mapping(state.get("candidates")) if state else {}
    record = _mapping(candidates.get(str(candidate)))
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
    normalized_variants = _normalize_variants(variants or DEFAULT_PROTO_REDUCTION_VARIANTS)
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Forced-anchor proto reduction has not run.",
    }
    entries: list[Dict[str, Any]] = []
    proto_profile: Dict[str, Any] = {}
    model_error: Optional[str] = None
    timing: Dict[str, float] = {}
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before proto reduction.",
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
            ghost_rect = _candidate_ghost_rect(str(candidate), record)
            model, base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=str(master_search_profile),
            )
            base_proto = _clone_model_proto(base_proto)
            proto_profile = _proto_profile(base_proto)
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            solve_started = time.perf_counter()
            for anchor_idx in selected_anchor_indices:
                u_var = model.u_vars.get(int(anchor_idx))
                if u_var is None:
                    for variant in normalized_variants:
                        entries.append(
                            {
                                "anchor_idx": int(anchor_idx),
                                "variant": str(variant),
                                "evaluated": False,
                                "status": "SKIPPED",
                                "skip_reason": "anchor_not_in_model_u_vars",
                            }
                        )
                    continue
                for variant in normalized_variants:
                    entries.append(
                        _solve_proto_reduction_variant(
                            base_proto,
                            model=model,
                            anchor_idx=int(anchor_idx),
                            u_var_index=int(u_var.Index()),
                            variant=str(variant),
                            time_limit_seconds=float(time_limit_seconds),
                            worker_count=int(worker_count),
                            solver_parameter_profile=solver_parameter_profile,
                        )
                    )
            timing["reduction_solve_seconds"] = float(time.perf_counter() - solve_started)
            status.update(_status_from_entries(entries))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Forced-anchor proto reduction failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    return {
        "metadata": {
            "source": FORCED_ANCHOR_PROTO_REDUCTION_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "proto_constraint_reduction_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
        },
        "candidate": {
            "key": str(candidate),
            "campaign_status": record.get("status") if record else None,
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "sample_limit": int(sample_limit),
            "selected_anchor_indices": [int(idx) for idx in selected_anchor_indices],
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "variants": list(normalized_variants),
        },
        "proto_profile": proto_profile,
        "status": status,
        "reduction": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "status_counts_by_variant": _status_counts_by_key(entries, "variant"),
            "best_terminal_entry": _best_terminal_entry(entries),
            "unknown_diagnostics": _unknown_diagnostics(entries),
            "unlocking_variants": _unlocking_variants(entries),
        },
        "timing": timing,
        "model_error": model_error,
        "campaign_state_unchanged": bool(before_hash == after_hash),
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            status=status,
            campaign_state_unchanged=before_hash == after_hash,
            model_error=model_error,
        ),
    }


def render_phase3b_forced_anchor_proto_reduction_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    reduction = _mapping(report.get("reduction"))
    unknowns = _mapping(reduction.get("unknown_diagnostics"))
    lines = [
        "# Phase 3B Forced-Anchor Proto Reduction",
        "",
        f"- Candidate: {_mapping(report.get('candidate')).get('key')}",
        "- Diagnostic semantics: proto_constraint_reduction_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Status counts: {reduction.get('status_counts', {})}",
        f"- Zero-branch UNKNOWN entries: {unknowns.get('zero_branch_unknown_count', 0)}",
        f"- Unlocking variants: {reduction.get('unlocking_variants', [])}",
        "",
        "## Reduction Matrix",
        "",
        "| Variant | Status | Removed | Wall | Branches | Conflicts |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(reduction.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("variant")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("removed_constraint_count")),
                    _markdown_cell(entry.get("wall_time")),
                    _markdown_cell(entry.get("branches")),
                    _markdown_cell(entry.get("conflicts")),
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


def render_phase3b_forced_anchor_proto_reduction_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    reduction = _mapping(report.get("reduction"))
    unknowns = _mapping(reduction.get("unknown_diagnostics"))
    lines = [
        "Phase 3B forced-anchor proto reduction",
        f"candidate={_mapping(report.get('candidate')).get('key')}",
        "diagnostic_semantics=proto_constraint_reduction_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"status_counts={reduction.get('status_counts', {})}",
        f"zero_branch_unknown_count={unknowns.get('zero_branch_unknown_count', 0)}",
        f"unlocking_variants={reduction.get('unlocking_variants', [])}",
    ]
    for entry in list(reduction.get("entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "entry "
                f"variant={entry.get('variant')} "
                f"status={entry.get('status')} "
                f"removed={entry.get('removed_constraint_count')} "
                f"wall={entry.get('wall_time')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')}"
            )
    return "\n".join(lines) + "\n"


def _solve_proto_reduction_variant(
    base_proto: Any,
    *,
    model: Any = None,
    anchor_idx: int,
    u_var_index: int,
    variant: str,
    time_limit_seconds: float,
    worker_count: int,
    solver_parameter_profile: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    local_proto = _clone_model_proto(base_proto)
    removal_payload = _apply_proto_reduction(local_proto, str(variant))
    local_model = cp_model_from_proto(local_proto)
    replacement_payload: Dict[str, Any] = {"added_constraint_count": 0}
    if str(variant) == POWER_COVERAGE_SELECTED_COORD_LITERAL_REPLACEMENT_VARIANT:
        replacement_payload = _add_power_coverage_selected_coord_literal_replacement(
            local_model,
            model,
        )
    elif str(variant) == FAMILY_LOOKUP_LINEAR_SHELL_GUARD_REPLACEMENT_VARIANT:
        replacement_payload = _add_family_lookup_linear_shell_guards(
            local_model,
            model,
            local_proto,
        )
    elif str(variant) == POWER_COVERAGE_AND_FAMILY_LINEAR_GUARD_REPLACEMENT_VARIANT:
        power_payload = _add_power_coverage_selected_coord_literal_replacement(
            local_model,
            model,
        )
        family_payload = _add_family_lookup_linear_shell_guards(
            local_model,
            model,
            local_proto,
        )
        replacement_payload = {
            "mode": "power_coverage_selected_coord_and_family_linear_shell_guards",
            "diagnostic_semantics": "mutated_clone_not_proof_source",
            "power_coverage": power_payload,
            "family_lookup": family_payload,
            "added_constraint_count": int(power_payload.get("added_constraint_count", 0))
            + int(family_payload.get("added_constraint_count", 0)),
        }
    else:
        template_replacement = _selected_coord_template_replacement_from_variant(
            str(variant)
        )
        if template_replacement is not None:
            replacement_payload = _add_power_coverage_selected_coord_literal_replacement(
                local_model,
                model,
                powered_template=str(template_replacement["powered_template"]),
            )
            replacement_payload["replacement_variant_mode"] = str(
                template_replacement["mode"]
            )
        else:
            index_restriction = _template_index_restriction_from_variant(str(variant))
            if index_restriction is not None:
                replacement_payload = _add_power_coverage_template_index_restriction(
                    local_model,
                    model,
                    powered_template=str(index_restriction["powered_template"]),
                    mode=str(index_restriction["mode"]),
                    limit=int(index_restriction.get("limit", 0)),
                    start=int(index_restriction.get("start", 0)),
                    count=int(index_restriction.get("count", 0)),
                )
            else:
                active_prefix_guard = _template_index_active_prefix_guard_from_variant(
                    str(variant)
                )
                if active_prefix_guard is not None:
                    replacement_payload = _add_power_coverage_template_index_active_prefix_guard(
                        local_model,
                        model,
                        powered_template=str(active_prefix_guard["powered_template"]),
                    )
    local_model.Add(local_model.GetBoolVarFromProtoIndex(int(u_var_index)) == 1)
    solver = cp_model.CpSolver()
    applied_profile = _apply_solver_parameter_profile(
        solver,
        time_limit_seconds=float(time_limit_seconds),
        default_worker_count=int(worker_count),
        profile=solver_parameter_profile,
    )
    started = time.perf_counter()
    status = solver.Solve(local_model)
    elapsed = float(time.perf_counter() - started)
    response_stats = solver.ResponseStats()
    return {
        "anchor_idx": int(anchor_idx),
        "u_var_index": int(u_var_index),
        "variant": str(variant),
        "evaluated": True,
        "status": solver.StatusName(status),
        "elapsed_seconds": float(elapsed),
        "wall_time": float(solver.WallTime()),
        "user_time": float(solver.UserTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "removed_constraint_count": int(removal_payload.get("removed_constraint_count", 0)),
        "reduction_payload": removal_payload,
        "replacement_payload": replacement_payload,
        "solver_parameter_profile": applied_profile,
        "response_summary": _first_line(response_stats),
        "response_stats": str(response_stats),
        "response_stats_parsed": _response_stats_payload(response_stats),
        "deterministic_time": _response_stats_payload(response_stats).get(
            "deterministic_time",
            0,
        ),
    }


def _apply_proto_reduction(model_proto: Any, variant: str) -> Dict[str, Any]:
    variant_text = str(variant)
    if variant_text == "base":
        return {"variant": variant_text, "removed_constraint_count": 0}
    if variant_text == "remove_power_coverage_elements":
        payload = _remove_power_coverage_element_constraints_payload(model_proto)
    elif variant_text == "remove_power_coverage_linear":
        payload = _remove_power_coverage_linear_constraints_payload(
            model_proto,
            mode="power_coverage_active_and_geometry_relaxed",
        )
    elif variant_text == "remove_power_pole_no_overlap":
        payload = _remove_power_pole_intervals_from_no_overlap_2d_payload(model_proto)
        payload = {
            **payload,
            "removed_constraint_count": int(payload.get("touched_constraint_count", 0)),
        }
    elif variant_text == "remove_family_lookup_table":
        payload = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_table_constraints_relaxed",
        )
    elif variant_text == "remove_family_lookup_sentinel_linear":
        payload = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_sentinel_constraints_relaxed",
        )
    elif variant_text == "remove_family_lookup_membership_linear":
        payload = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_membership_linear_constraints_relaxed",
        )
    elif variant_text == "remove_family_lookup_ordering_linear":
        payload = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_ordering_linear_constraints_relaxed",
        )
    elif variant_text == "remove_family_lookup_all_linear":
        payload = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_linear_constraints_relaxed",
        )
    elif variant_text == "remove_family_lookup_all":
        payload = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_constraints_relaxed",
        )
    elif variant_text == "remove_power_coverage_dynamic":
        parts = {
            "power_coverage_elements": _remove_power_coverage_element_constraints_payload(
                model_proto
            ),
            "power_coverage_linear": _remove_power_coverage_linear_constraints_payload(
                model_proto,
                mode="power_coverage_active_and_geometry_relaxed",
            ),
            "power_pole_no_overlap": _remove_power_pole_intervals_from_no_overlap_2d_payload(
                model_proto
            ),
        }
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_dynamic_and_family_lookup_all":
        parts = {
            "power_coverage_elements": _remove_power_coverage_element_constraints_payload(
                model_proto
            ),
            "power_coverage_linear": _remove_power_coverage_linear_constraints_payload(
                model_proto,
                mode="power_coverage_active_and_geometry_relaxed",
            ),
            "power_pole_no_overlap": _remove_power_pole_intervals_from_no_overlap_2d_payload(
                model_proto
            ),
            "family_lookup_all": _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_constraints_relaxed",
            ),
        }
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_dynamic_and_family_lookup_table":
        parts = {
            "power_coverage_elements": _remove_power_coverage_element_constraints_payload(
                model_proto
            ),
            "power_coverage_linear": _remove_power_coverage_linear_constraints_payload(
                model_proto,
                mode="power_coverage_active_and_geometry_relaxed",
            ),
            "power_pole_no_overlap": _remove_power_pole_intervals_from_no_overlap_2d_payload(
                model_proto
            ),
            "family_lookup_table": _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            ),
        }
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_dynamic_and_family_lookup_all_linear":
        parts = {
            "power_coverage_elements": _remove_power_coverage_element_constraints_payload(
                model_proto
            ),
            "power_coverage_linear": _remove_power_coverage_linear_constraints_payload(
                model_proto,
                mode="power_coverage_active_and_geometry_relaxed",
            ),
            "power_pole_no_overlap": _remove_power_pole_intervals_from_no_overlap_2d_payload(
                model_proto
            ),
            "family_lookup_all_linear": _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_linear_constraints_relaxed",
            ),
        }
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_elements_and_family_lookup_all":
        parts = {
            "power_coverage_elements": _remove_power_coverage_element_constraints_payload(
                model_proto
            ),
            "family_lookup_all": _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_constraints_relaxed",
            ),
        }
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_linear_and_family_lookup_all":
        parts = {
            "power_coverage_linear": _remove_power_coverage_linear_constraints_payload(
                model_proto,
                mode="power_coverage_active_and_geometry_relaxed",
            ),
            "family_lookup_all": _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_constraints_relaxed",
            ),
        }
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_pole_no_overlap_and_family_lookup_all":
        parts = {
            "power_pole_no_overlap": _remove_power_pole_intervals_from_no_overlap_2d_payload(
                model_proto
            ),
            "family_lookup_all": _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_constraints_relaxed",
            ),
        }
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_elements_and_family_lookup_table":
        parts = _coverage_family_parts(model_proto, coverage_parts=("elements",), family_part="table")
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_elements_and_family_lookup_all_linear":
        parts = _coverage_family_parts(model_proto, coverage_parts=("elements",), family_part="all_linear")
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_linear_and_family_lookup_table":
        parts = _coverage_family_parts(model_proto, coverage_parts=("linear",), family_part="table")
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_linear_and_family_lookup_all_linear":
        parts = _coverage_family_parts(model_proto, coverage_parts=("linear",), family_part="all_linear")
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_pole_no_overlap_and_family_lookup_table":
        parts = _coverage_family_parts(model_proto, coverage_parts=("no_overlap",), family_part="table")
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_pole_no_overlap_and_family_lookup_all_linear":
        parts = _coverage_family_parts(model_proto, coverage_parts=("no_overlap",), family_part="all_linear")
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_element_active_and_family_lookup_table":
        parts = _element_target_family_parts(
            model_proto,
            target_prefixes=("cover_choice_active__",),
            family_part="table",
        )
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_element_x_and_family_lookup_table":
        parts = _element_target_family_parts(
            model_proto,
            target_prefixes=("cover_choice_x__",),
            family_part="table",
        )
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_element_y_and_family_lookup_table":
        parts = _element_target_family_parts(
            model_proto,
            target_prefixes=("cover_choice_y__",),
            family_part="table",
        )
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_element_xy_and_family_lookup_table":
        parts = _element_target_family_parts(
            model_proto,
            target_prefixes=("cover_choice_x__", "cover_choice_y__"),
            family_part="table",
        )
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_element_active_x_and_family_lookup_table":
        parts = _element_target_family_parts(
            model_proto,
            target_prefixes=("cover_choice_active__", "cover_choice_x__"),
            family_part="table",
        )
        payload = _combined_payload(variant_text, parts)
    elif variant_text == "remove_power_coverage_element_active_y_and_family_lookup_table":
        parts = _element_target_family_parts(
            model_proto,
            target_prefixes=("cover_choice_active__", "cover_choice_y__"),
            family_part="table",
        )
        payload = _combined_payload(variant_text, parts)
    elif variant_text == POWER_COVERAGE_SELECTED_COORD_LITERAL_REPLACEMENT_VARIANT:
        parts = {
            "power_coverage_elements": _remove_power_coverage_element_constraints_payload(
                model_proto
            ),
            "power_coverage_linear": _remove_power_coverage_linear_constraints_payload(
                model_proto,
                mode="power_coverage_active_and_geometry_relaxed",
            ),
        }
        payload = _combined_payload(variant_text, parts)
        payload["diagnostic_warning"] = (
            "diagnostic-only selected-coordinate literal replacement; not proof-source semantics"
        )
    elif variant_text == FAMILY_LOOKUP_LINEAR_SHELL_GUARD_REPLACEMENT_VARIANT:
        payload = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_table_constraints_relaxed",
        )
        payload["diagnostic_warning"] = (
            "diagnostic-only family lookup table replacement with linear shell guards; not proof-source semantics"
        )
    elif variant_text == POWER_COVERAGE_AND_FAMILY_LINEAR_GUARD_REPLACEMENT_VARIANT:
        parts = {
            "power_coverage_elements": _remove_power_coverage_element_constraints_payload(
                model_proto
            ),
            "power_coverage_linear": _remove_power_coverage_linear_constraints_payload(
                model_proto,
                mode="power_coverage_active_and_geometry_relaxed",
            ),
            "family_lookup_table": _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            ),
        }
        payload = _combined_payload(variant_text, parts)
        payload["diagnostic_warning"] = (
            "diagnostic-only power coverage selected-coordinate and family linear shell replacement; not proof-source semantics"
        )
    elif variant_text.startswith("remove_power_coverage_elements_and_family_lookup_table_first_"):
        limit = int(variant_text.rsplit("_", 1)[1])
        parts = _element_targets_family_table_subset_parts(
            model_proto,
            selector={"kind": "first", "limit": int(limit)},
        )
        payload = _combined_payload(variant_text, parts)
    elif variant_text.startswith("remove_power_coverage_elements_and_family_lookup_table_last_"):
        limit = int(variant_text.rsplit("_", 1)[1])
        parts = _element_targets_family_table_subset_parts(
            model_proto,
            selector={"kind": "last", "limit": int(limit)},
        )
        payload = _combined_payload(variant_text, parts)
    elif variant_text.startswith("remove_power_coverage_elements_and_family_lookup_table_quarter_"):
        quarter = int(variant_text.rsplit("_", 1)[1])
        parts = _element_targets_family_table_subset_parts(
            model_proto,
            selector={"kind": "quarter", "quarter": int(quarter), "quarter_count": 4},
        )
        payload = _combined_payload(variant_text, parts)
    else:
        dynamic_payload = _apply_dynamic_proto_reduction(model_proto, variant_text)
        if dynamic_payload is None:
            raise ValueError(f"Unsupported proto reduction variant: {variant!r}")
        payload = dynamic_payload
    return {"variant": variant_text, **dict(payload)}


def _add_family_lookup_linear_shell_guards(
    local_model: Any,
    source_model: Any,
    local_proto: Any,
) -> Dict[str, Any]:
    payload = _power_family_shell_pair_table_payload(source_model, local_proto)
    rows_by_family_id = {
        str(family_id): [
            [int(row[0]), int(row[1])]
            for row in list(rows)
            if isinstance(row, (list, tuple)) and len(row) == 2
        ]
        for family_id, rows in _mapping(payload.get("rows_by_family_id")).items()
    }
    shapes_by_family_id = {
        str(family_id): _family_shell_guard_shape(rows)
        for family_id, rows in sorted(rows_by_family_id.items(), key=lambda item: int(item[0]))
    }
    slot_count = 0
    family_lit_count = 0
    linear_constraint_count = 0
    fallback_table_constraint_count = 0
    fallback_table_row_total = 0
    shape_counts: Dict[str, int] = {}
    for slot in list(payload.get("slots", [])):
        if not isinstance(slot, Mapping):
            continue
        d_lo_idx = slot.get("d_lo_var_index")
        d_hi_idx = slot.get("d_hi_var_index")
        if d_lo_idx is None or d_hi_idx is None:
            continue
        d_lo_var = local_model.GetIntVarFromProtoIndex(int(d_lo_idx))
        d_hi_var = local_model.GetIntVarFromProtoIndex(int(d_hi_idx))
        slot_count += 1
        for family_id, lit_idx in sorted(
            _mapping(slot.get("family_lit_indices_by_family_id")).items(),
            key=lambda item: int(item[0]),
        ):
            shape = shapes_by_family_id.get(str(family_id))
            if not shape:
                continue
            lit_var = local_model.GetBoolVarFromProtoIndex(int(lit_idx))
            family_lit_count += 1
            kind = str(shape.get("kind"))
            shape_counts[kind] = int(shape_counts.get(kind, 0)) + 1
            if kind == "single":
                local_model.Add(d_lo_var == int(shape["d_lo"])).OnlyEnforceIf(lit_var)
                local_model.Add(d_hi_var == int(shape["d_hi"])).OnlyEnforceIf(lit_var)
                linear_constraint_count += 2
            elif kind == "rectangle":
                linear_constraint_count += _add_guarded_bounds(
                    local_model,
                    lit_var=lit_var,
                    d_lo_var=d_lo_var,
                    d_hi_var=d_hi_var,
                    d_lo_min=int(shape["d_lo_min"]),
                    d_lo_max=int(shape["d_lo_max"]),
                    d_hi_min=int(shape["d_hi_min"]),
                    d_hi_max=int(shape["d_hi_max"]),
                )
            elif kind == "upper_triangle":
                linear_constraint_count += _add_guarded_bounds(
                    local_model,
                    lit_var=lit_var,
                    d_lo_var=d_lo_var,
                    d_hi_var=d_hi_var,
                    d_lo_min=int(shape["d_lo_min"]),
                    d_lo_max=int(shape["d_lo_max"]),
                    d_hi_min=int(shape["d_hi_min"]),
                    d_hi_max=int(shape["d_hi_max"]),
                )
                local_model.Add(d_lo_var <= d_hi_var).OnlyEnforceIf(lit_var)
                linear_constraint_count += 1
            else:
                rows = [
                    [int(row[0]), int(row[1])]
                    for row in list(shape.get("rows", []))
                    if isinstance(row, (list, tuple)) and len(row) == 2
                ]
                if not rows:
                    continue
                local_model.AddAllowedAssignments([d_lo_var, d_hi_var], rows).OnlyEnforceIf(
                    lit_var
                )
                fallback_table_constraint_count += 1
                fallback_table_row_total += int(len(rows))
    added_constraint_count = int(linear_constraint_count + fallback_table_constraint_count)
    return {
        "mode": "family_lookup_linear_shell_guards",
        "diagnostic_semantics": "mutated_clone_not_proof_source",
        "slot_count": int(slot_count),
        "family_count": int(len(rows_by_family_id)),
        "family_lit_count": int(family_lit_count),
        "shape_counts": dict(sorted(shape_counts.items())),
        "linear_constraint_count": int(linear_constraint_count),
        "fallback_table_constraint_count": int(fallback_table_constraint_count),
        "fallback_table_row_total": int(fallback_table_row_total),
        "added_constraint_count": int(added_constraint_count),
        "rows_by_family_shape": {
            str(family_id): {
                key: value
                for key, value in dict(shape).items()
                if key != "rows"
            }
            for family_id, shape in sorted(shapes_by_family_id.items(), key=lambda item: int(item[0]))
        },
    }


def _family_shell_guard_shape(rows: Sequence[Sequence[int]]) -> Dict[str, Any]:
    row_set = {
        (int(row[0]), int(row[1]))
        for row in list(rows)
        if isinstance(row, (list, tuple)) and len(row) == 2
    }
    if not row_set:
        return {"kind": "empty", "row_count": 0, "rows": []}
    if len(row_set) == 1:
        d_lo, d_hi = next(iter(row_set))
        return {"kind": "single", "row_count": 1, "d_lo": int(d_lo), "d_hi": int(d_hi)}
    d_los = sorted({int(row[0]) for row in row_set})
    d_his = sorted({int(row[1]) for row in row_set})
    rectangle = {
        (int(d_lo), int(d_hi))
        for d_lo in range(min(d_los), max(d_los) + 1)
        for d_hi in range(min(d_his), max(d_his) + 1)
    }
    if row_set == rectangle:
        return {
            "kind": "rectangle",
            "row_count": int(len(row_set)),
            "d_lo_min": int(min(d_los)),
            "d_lo_max": int(max(d_los)),
            "d_hi_min": int(min(d_his)),
            "d_hi_max": int(max(d_his)),
        }
    upper_triangle = {
        (int(d_lo), int(d_hi))
        for d_lo in range(min(d_los), max(d_los) + 1)
        for d_hi in range(min(d_his), max(d_his) + 1)
        if int(d_lo) <= int(d_hi)
    }
    if row_set == upper_triangle:
        return {
            "kind": "upper_triangle",
            "row_count": int(len(row_set)),
            "d_lo_min": int(min(d_los)),
            "d_lo_max": int(max(d_los)),
            "d_hi_min": int(min(d_his)),
            "d_hi_max": int(max(d_his)),
        }
    return {
        "kind": "fallback_table",
        "row_count": int(len(row_set)),
        "rows": [[int(row[0]), int(row[1])] for row in sorted(row_set)],
    }


def _add_guarded_bounds(
    local_model: Any,
    *,
    lit_var: Any,
    d_lo_var: Any,
    d_hi_var: Any,
    d_lo_min: int,
    d_lo_max: int,
    d_hi_min: int,
    d_hi_max: int,
) -> int:
    local_model.Add(d_lo_var >= int(d_lo_min)).OnlyEnforceIf(lit_var)
    local_model.Add(d_lo_var <= int(d_lo_max)).OnlyEnforceIf(lit_var)
    local_model.Add(d_hi_var >= int(d_hi_min)).OnlyEnforceIf(lit_var)
    local_model.Add(d_hi_var <= int(d_hi_max)).OnlyEnforceIf(lit_var)
    return 4


def _add_power_coverage_selected_coord_literal_replacement(
    local_model: Any,
    source_model: Any,
    *,
    powered_template: Optional[str] = None,
) -> Dict[str, Any]:
    delegate = getattr(source_model, "_coordinate_delegate", None)
    if delegate is None:
        raise ValueError("coordinate delegate missing for selected-coordinate replacement")
    pole_slots = list(getattr(delegate, "residual_optional_slots", {}).get("power_pole", []))
    all_powered_slots = list(delegate._all_powered_slots())
    powered_slots = [
        slot
        for slot in all_powered_slots
        if powered_template is None
        or str(getattr(slot, "template", "")) == str(powered_template)
    ]
    radius = int(delegate._power_coverage_radius())
    grid_w = int(getattr(source_model, "grid_w", getattr(delegate, "grid_w", 0)))
    grid_h = int(getattr(source_model, "grid_h", getattr(delegate, "grid_h", 0)))
    cover_literal_count = 0
    active_implication_constraint_count = 0
    selected_coord_channel_constraint_count = 0
    geometry_constraint_count = 0
    witness_sum_constraint_count = 0
    powered_without_candidate_count = 0
    selected_coord_var_count = 0

    pole_payload = [
        {
            "active": _bool_var_from_slot(local_model, slot, "active"),
            "x": _int_var_from_slot(local_model, slot, "x"),
            "y": _int_var_from_slot(local_model, slot, "y"),
        }
        for slot in pole_slots
        if getattr(slot, "active", None) is not None
        and getattr(slot, "x", None) is not None
        and getattr(slot, "y", None) is not None
    ]

    for powered_index, powered_slot in enumerate(powered_slots):
        if not pole_payload:
            powered_active = _optional_bool_var_from_slot(local_model, powered_slot, "active")
            if powered_active is not None:
                local_model.Add(powered_active == 0)
                witness_sum_constraint_count += 1
                powered_without_candidate_count += 1
                continue
            local_model.Add(0 >= 1)
            witness_sum_constraint_count += 1
            powered_without_candidate_count += 1
            continue

        powered_x = _int_var_from_slot(local_model, powered_slot, "x")
        powered_y = _int_var_from_slot(local_model, powered_slot, "y")
        powered_active = _optional_bool_var_from_slot(local_model, powered_slot, "active")
        selected_x = local_model.NewIntVar(
            0,
            max(0, int(grid_w) - 1),
            f"selected_cover_x__{getattr(powered_slot, 'key', powered_index)}",
        )
        selected_y = local_model.NewIntVar(
            0,
            max(0, int(grid_h) - 1),
            f"selected_cover_y__{getattr(powered_slot, 'key', powered_index)}",
        )
        selected_coord_var_count += 2
        cover_lits = []
        for pole_index, pole in enumerate(pole_payload):
            lit = local_model.NewBoolVar(
                f"cover_lit__{getattr(powered_slot, 'key', powered_index)}__pole_{pole_index}"
            )
            cover_lits.append(lit)
            cover_literal_count += 1
            local_model.AddImplication(lit, pole["active"])
            active_implication_constraint_count += 1
            if powered_active is not None:
                local_model.AddImplication(lit, powered_active)
                active_implication_constraint_count += 1
            local_model.Add(selected_x == pole["x"]).OnlyEnforceIf(lit)
            local_model.Add(selected_y == pole["y"]).OnlyEnforceIf(lit)
            selected_coord_channel_constraint_count += 2

        if powered_active is not None:
            local_model.Add(sum(cover_lits) >= powered_active)
        else:
            local_model.Add(sum(cover_lits) >= 1)
        witness_sum_constraint_count += 1
        enforcement = powered_active
        geometry_constraint_count += _add_selected_coord_geometry_constraints(
            local_model,
            powered_x=powered_x,
            powered_y=powered_y,
            selected_x=selected_x,
            selected_y=selected_y,
            dims=getattr(powered_slot, "dims", (1, 1)),
            radius=int(radius),
            enforcement_literal=enforcement,
        )

    added_constraint_count = int(
        active_implication_constraint_count
        + selected_coord_channel_constraint_count
        + geometry_constraint_count
        + witness_sum_constraint_count
    )
    return {
        "mode": "selected_coord_literal_replacement",
        "diagnostic_semantics": "mutated_clone_not_proof_source",
        "selected_powered_template": (
            str(powered_template) if powered_template is not None else None
        ),
        "source_powered_slot_count": int(len(all_powered_slots)),
        "skipped_powered_slot_count": int(len(all_powered_slots) - len(powered_slots)),
        "powered_slot_count": int(len(powered_slots)),
        "pole_slot_count": int(len(pole_payload)),
        "cover_literal_count": int(cover_literal_count),
        "selected_coord_var_count": int(selected_coord_var_count),
        "active_implication_constraint_count": int(active_implication_constraint_count),
        "selected_coord_channel_constraint_count": int(selected_coord_channel_constraint_count),
        "geometry_constraint_count": int(geometry_constraint_count),
        "witness_sum_constraint_count": int(witness_sum_constraint_count),
        "powered_without_candidate_count": int(powered_without_candidate_count),
        "added_constraint_count": int(added_constraint_count),
    }


def _add_selected_coord_geometry_constraints(
    local_model: Any,
    *,
    powered_x: Any,
    powered_y: Any,
    selected_x: Any,
    selected_y: Any,
    dims: Any,
    radius: int,
    enforcement_literal: Any,
) -> int:
    dims_list = [int(value) for value in list(dims or (1, 1))]
    width = int(dims_list[0]) if dims_list else 1
    height = int(dims_list[1]) if len(dims_list) > 1 else 1
    constraints = [
        local_model.Add(powered_x <= selected_x + 2 + int(radius) - 1),
        local_model.Add(selected_x - int(radius) <= powered_x + int(width) - 1),
        local_model.Add(powered_y <= selected_y + 2 + int(radius) - 1),
        local_model.Add(selected_y - int(radius) <= powered_y + int(height) - 1),
    ]
    if enforcement_literal is not None:
        for constraint in constraints:
            constraint.OnlyEnforceIf(enforcement_literal)
    return int(len(constraints))


def _add_power_coverage_template_index_restriction(
    local_model: Any,
    source_model: Any,
    *,
    powered_template: str,
    mode: str = "first",
    limit: int = 0,
    start: int = 0,
    count: int = 0,
) -> Dict[str, Any]:
    delegate = getattr(source_model, "_coordinate_delegate", None)
    if delegate is None:
        raise ValueError("coordinate delegate missing for index restriction")
    all_powered_slots = list(delegate._all_powered_slots())
    powered_slots = [
        slot
        for slot in all_powered_slots
        if str(getattr(slot, "template", "")) == str(powered_template)
    ]
    pole_slot_count = int(
        len(list(getattr(delegate, "residual_optional_slots", {}).get("power_pole", [])))
    )
    variable_index_by_name = {
        str(getattr(var, "name", "")): int(index)
        for index, var in enumerate(list(getattr(local_model.Proto(), "variables", [])))
    }
    window = _index_restriction_window(
        mode=str(mode),
        limit=int(limit),
        start=int(start),
        count=int(count),
        pole_slot_count=int(pole_slot_count),
    )
    lower_bound = int(window["lower_bound"])
    upper_bound = int(window["upper_bound"])
    added_constraint_count = 0
    missing_index_var_count = 0
    for powered_slot in powered_slots:
        var_name = f"cover_choice_idx__{getattr(powered_slot, 'key', '')}"
        var_index = variable_index_by_name.get(str(var_name))
        if var_index is None:
            missing_index_var_count += 1
            continue
        idx_var = local_model.GetIntVarFromProtoIndex(int(var_index))
        if lower_bound > 0:
            local_model.Add(idx_var >= int(lower_bound))
            added_constraint_count += 1
        if pole_slot_count <= 0 or upper_bound < int(pole_slot_count) - 1:
            local_model.Add(idx_var <= int(upper_bound))
            added_constraint_count += 1
    return {
        "mode": "template_cover_choice_index_restriction",
        "diagnostic_semantics": "mutated_clone_not_proof_source",
        "powered_template": str(powered_template),
        "source_powered_slot_count": int(len(all_powered_slots)),
        "powered_slot_count": int(len(powered_slots)),
        "restriction_mode": str(mode),
        "limit": int(limit),
        "start": int(start),
        "count": int(count),
        "pole_slot_count": int(pole_slot_count),
        "lower_bound": int(lower_bound),
        "upper_bound": int(upper_bound),
        "window_width": int(max(0, upper_bound - lower_bound + 1)),
        "added_constraint_count": int(added_constraint_count),
        "missing_index_var_count": int(missing_index_var_count),
    }


def _index_restriction_window(
    *,
    mode: str,
    limit: int,
    start: int,
    count: int,
    pole_slot_count: int,
) -> Dict[str, int]:
    mode_text = str(mode)
    max_index = max(0, int(pole_slot_count) - 1) if int(pole_slot_count) > 0 else None
    if mode_text == "first":
        width = max(1, int(limit))
        lower = 0
        upper = width - 1
    elif mode_text == "last":
        width = max(1, int(limit))
        if max_index is None:
            lower = 0
            upper = width - 1
        else:
            upper = int(max_index)
            lower = max(0, int(max_index) - width + 1)
    elif mode_text == "window":
        width = max(1, int(count))
        lower = max(0, int(start))
        upper = lower + width - 1
    else:
        raise ValueError(f"Unsupported index restriction mode: {mode!r}")
    if max_index is not None:
        lower = min(int(lower), int(max_index))
        upper = min(max(int(upper), int(lower)), int(max_index))
    return {"lower_bound": int(lower), "upper_bound": int(upper)}


def _add_power_coverage_template_index_active_prefix_guard(
    local_model: Any,
    source_model: Any,
    *,
    powered_template: str,
) -> Dict[str, Any]:
    delegate = getattr(source_model, "_coordinate_delegate", None)
    if delegate is None:
        raise ValueError("coordinate delegate missing for active-prefix guard")
    pole_slots = list(getattr(delegate, "residual_optional_slots", {}).get("power_pole", []))
    pole_active_vars = [
        _bool_var_from_slot(local_model, slot, "active")
        for slot in pole_slots
        if getattr(slot, "active", None) is not None
    ]
    all_powered_slots = list(delegate._all_powered_slots())
    powered_slots = [
        slot
        for slot in all_powered_slots
        if str(getattr(slot, "template", "")) == str(powered_template)
    ]
    variable_index_by_name = {
        str(getattr(var, "name", "")): int(index)
        for index, var in enumerate(list(getattr(local_model.Proto(), "variables", [])))
    }
    added_constraint_count = 0
    missing_index_var_count = 0
    powered_active_guard_count = 0
    if not pole_active_vars:
        return {
            "mode": "template_cover_choice_index_active_prefix_guard",
            "diagnostic_semantics": "mutated_clone_not_proof_source",
            "powered_template": str(powered_template),
            "source_powered_slot_count": int(len(all_powered_slots)),
            "powered_slot_count": int(len(powered_slots)),
            "pole_slot_count": int(len(pole_slots)),
            "pole_active_var_count": 0,
            "added_constraint_count": 0,
            "missing_index_var_count": int(len(powered_slots)),
            "powered_active_guard_count": 0,
        }
    active_count_expr = sum(pole_active_vars)
    for powered_slot in powered_slots:
        var_name = f"cover_choice_idx__{getattr(powered_slot, 'key', '')}"
        var_index = variable_index_by_name.get(str(var_name))
        if var_index is None:
            missing_index_var_count += 1
            continue
        idx_var = local_model.GetIntVarFromProtoIndex(int(var_index))
        constraint = local_model.Add(idx_var <= active_count_expr - 1)
        powered_active = _optional_bool_var_from_slot(local_model, powered_slot, "active")
        if powered_active is not None:
            constraint.OnlyEnforceIf(powered_active)
            powered_active_guard_count += 1
        added_constraint_count += 1
    return {
        "mode": "template_cover_choice_index_active_prefix_guard",
        "diagnostic_semantics": "mutated_clone_not_proof_source",
        "powered_template": str(powered_template),
        "source_powered_slot_count": int(len(all_powered_slots)),
        "powered_slot_count": int(len(powered_slots)),
        "pole_slot_count": int(len(pole_slots)),
        "pole_active_var_count": int(len(pole_active_vars)),
        "added_constraint_count": int(added_constraint_count),
        "missing_index_var_count": int(missing_index_var_count),
        "powered_active_guard_count": int(powered_active_guard_count),
    }


def _int_var_from_slot(local_model: Any, slot: Any, attr_name: str) -> Any:
    var = getattr(slot, str(attr_name), None)
    if var is None:
        raise ValueError(f"slot {getattr(slot, 'key', '')} missing {attr_name} var")
    return local_model.GetIntVarFromProtoIndex(int(var.Index()))


def _bool_var_from_slot(local_model: Any, slot: Any, attr_name: str) -> Any:
    var = getattr(slot, str(attr_name), None)
    if var is None:
        raise ValueError(f"slot {getattr(slot, 'key', '')} missing {attr_name} bool var")
    return local_model.GetBoolVarFromProtoIndex(int(var.Index()))


def _optional_bool_var_from_slot(local_model: Any, slot: Any, attr_name: str) -> Any:
    var = getattr(slot, str(attr_name), None)
    if var is None:
        return None
    return local_model.GetBoolVarFromProtoIndex(int(var.Index()))



def _apply_dynamic_proto_reduction(
    model_proto: Any,
    variant_text: str,
) -> Optional[Dict[str, Any]]:
    every_match = re.match(
        r"^remove_power_coverage_elements_and_family_lookup_table_every_(\d+)"
        r"(?:_offset_(\d+))?$",
        str(variant_text),
    )
    if every_match is not None:
        step = max(1, int(every_match.group(1)))
        offset = max(0, int(every_match.group(2) or 0))
        parts = _element_targets_family_table_subset_parts(
            model_proto,
            selector={"kind": "every", "step": int(step), "offset": int(offset)},
        )
        return _combined_payload(str(variant_text), parts)

    mod_match = re.match(
        r"^remove_power_coverage_elements_and_family_lookup_table_mod_(\d+)_(\d+)$",
        str(variant_text),
    )
    if mod_match is not None:
        modulus = max(1, int(mod_match.group(1)))
        remainder = int(mod_match.group(2)) % modulus
        parts = _element_targets_family_table_subset_parts(
            model_proto,
            selector={
                "kind": "slot_mod",
                "modulus": int(modulus),
                "remainder": int(remainder),
            },
        )
        return _combined_payload(str(variant_text), parts)

    hash_match = re.match(
        r"^remove_power_coverage_elements_and_family_lookup_table_hash_bucket_(\d+)_(\d+)$",
        str(variant_text),
    )
    if hash_match is not None:
        bucket_count = max(1, int(hash_match.group(1)))
        bucket = int(hash_match.group(2)) % bucket_count
        parts = _element_targets_family_table_subset_parts(
            model_proto,
            selector={
                "kind": "slot_hash_bucket",
                "bucket_count": int(bucket_count),
                "bucket": int(bucket),
            },
        )
        return _combined_payload(str(variant_text), parts)

    row_family_mod_match = re.match(
        r"^remove_power_coverage_elements_and_family_lookup_table_rows_family_mod_"
        r"(\d+)_(\d+)$",
        str(variant_text),
    )
    if row_family_mod_match is not None:
        modulus = max(1, int(row_family_mod_match.group(1)))
        remainder = int(row_family_mod_match.group(2)) % modulus
        parts = {
            "power_coverage_elements": _remove_power_coverage_element_constraints_payload(
                model_proto
            ),
            "family_lookup_table_rows": _remove_family_lookup_table_rows_payload(
                model_proto,
                selector={
                    "kind": "family_mod",
                    "modulus": int(modulus),
                    "remainder": int(remainder),
                },
            ),
        }
        return _combined_payload(str(variant_text), parts)

    template_target_element_linear_match = re.match(
        r"^remove_power_coverage_elements_template_"
        r"([A-Za-z0-9_]+?)_target_([A-Za-z0-9_]+)_element_linear"
        r"(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$",
        str(variant_text),
    )
    if template_target_element_linear_match is not None:
        template = str(template_target_element_linear_match.group(1))
        target_token = str(template_target_element_linear_match.group(2))
        target_prefixes = _cover_choice_target_prefixes_from_token(target_token)
        parts = {
            "power_coverage_template_element_targets": _remove_power_coverage_element_template_constraints_payload(
                model_proto,
                powered_template=template,
                target_prefixes=target_prefixes,
            ),
            "power_coverage_template_linear_targets": _remove_power_coverage_linear_template_target_constraints_payload(
                model_proto,
                powered_template=template,
                target_prefixes=target_prefixes,
            ),
        }
        if str(template_target_element_linear_match.group("family_suffix")) == "_and_family_lookup_table":
            parts["family_lookup_table"] = _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            )
        payload = _combined_payload(str(variant_text), parts)
        payload["diagnostic_warning"] = (
            "diagnostic-only template target element+linear reduction; not proof-source semantics"
        )
        payload["family_lookup_table_removed"] = bool(
            str(template_target_element_linear_match.group("family_suffix"))
            == "_and_family_lookup_table"
        )
        return payload

    template_target_layer_slot_window_match = re.match(
        r"^remove_power_coverage_elements_template_"
        r"([A-Za-z0-9_]+?)_target_([A-Za-z0-9_]+?)"
        r"_layer_(final|block)"
        r"_slot_window_(\d+)_(\d+)"
        r"(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$",
        str(variant_text),
    )
    if template_target_layer_slot_window_match is not None:
        template = str(template_target_layer_slot_window_match.group(1))
        target_token = str(template_target_layer_slot_window_match.group(2))
        channel_layer = str(template_target_layer_slot_window_match.group(3))
        parts = {
            "power_coverage_template_element_target_slot_window": _remove_power_coverage_element_template_slot_window_constraints_payload(
                model_proto,
                powered_template=template,
                target_prefixes=_cover_choice_target_prefixes_from_token(target_token),
                channel_layer=channel_layer,
                start=int(template_target_layer_slot_window_match.group(4)),
                count=int(template_target_layer_slot_window_match.group(5)),
            ),
        }
        if str(template_target_layer_slot_window_match.group("family_suffix")) == "_and_family_lookup_table":
            parts["family_lookup_table"] = _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            )
        payload = _combined_payload(str(variant_text), parts)
        payload["diagnostic_warning"] = (
            "diagnostic-only template target layer slot-window Element deletion; not proof-source semantics"
        )
        payload["family_lookup_table_removed"] = bool(
            str(template_target_layer_slot_window_match.group("family_suffix"))
            == "_and_family_lookup_table"
        )
        return payload

    template_target_slot_window_match = re.match(
        r"^remove_power_coverage_elements_template_"
        r"([A-Za-z0-9_]+?)_target_([A-Za-z0-9_]+?)"
        r"_slot_window_(\d+)_(\d+)"
        r"(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$",
        str(variant_text),
    )
    if template_target_slot_window_match is not None:
        template = str(template_target_slot_window_match.group(1))
        target_token = str(template_target_slot_window_match.group(2))
        parts = {
            "power_coverage_template_element_target_slot_window": _remove_power_coverage_element_template_slot_window_constraints_payload(
                model_proto,
                powered_template=template,
                target_prefixes=_cover_choice_target_prefixes_from_token(target_token),
                start=int(template_target_slot_window_match.group(3)),
                count=int(template_target_slot_window_match.group(4)),
            ),
        }
        if str(template_target_slot_window_match.group("family_suffix")) == "_and_family_lookup_table":
            parts["family_lookup_table"] = _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            )
        payload = _combined_payload(str(variant_text), parts)
        payload["diagnostic_warning"] = (
            "diagnostic-only template target slot-window Element deletion; not proof-source semantics"
        )
        payload["family_lookup_table_removed"] = bool(
            str(template_target_slot_window_match.group("family_suffix"))
            == "_and_family_lookup_table"
        )
        return payload

    template_target_match = re.match(
        r"^remove_power_coverage_elements_template_"
        r"([A-Za-z0-9_]+?)_target_([A-Za-z0-9_]+)"
        r"(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$",
        str(variant_text),
    )
    if template_target_match is not None:
        template = str(template_target_match.group(1))
        target_token = str(template_target_match.group(2))
        parts = {
            "power_coverage_template_element_targets": _remove_power_coverage_element_template_constraints_payload(
                model_proto,
                powered_template=template,
                target_prefixes=_cover_choice_target_prefixes_from_token(target_token),
            ),
        }
        if str(template_target_match.group("family_suffix")) == "_and_family_lookup_table":
            parts["family_lookup_table"] = _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            )
        payload = _combined_payload(str(variant_text), parts)
        payload["family_lookup_table_removed"] = bool(
            str(template_target_match.group("family_suffix")) == "_and_family_lookup_table"
        )
        return payload

    template_match = re.match(
        r"^remove_power_coverage_elements_template_"
        r"([A-Za-z0-9_]+)_and_family_lookup_table$",
        str(variant_text),
    )
    if template_match is not None:
        template = str(template_match.group(1))
        parts = {
            "power_coverage_template_elements": _remove_power_coverage_element_template_constraints_payload(
                model_proto,
                powered_template=template,
            ),
            "family_lookup_table": _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            ),
        }
        return _combined_payload(str(variant_text), parts)

    except_template_target_element_linear_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"([A-Za-z0-9_]+)_and_template_([A-Za-z0-9_]+)_element_linear"
        r"(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$",
        str(variant_text),
    )
    if except_template_target_element_linear_match is not None:
        template = str(except_template_target_element_linear_match.group(1))
        target_token = str(except_template_target_element_linear_match.group(2))
        target_prefixes = _cover_choice_target_prefixes_from_token(target_token)
        parts = {
            "power_coverage_except_template_elements": _remove_power_coverage_element_except_template_constraints_payload(
                model_proto,
                excluded_powered_template=template,
            ),
            "power_coverage_template_element_targets": _remove_power_coverage_element_template_constraints_payload(
                model_proto,
                powered_template=template,
                target_prefixes=target_prefixes,
            ),
            "power_coverage_template_linear_targets": _remove_power_coverage_linear_template_target_constraints_payload(
                model_proto,
                powered_template=template,
                target_prefixes=target_prefixes,
            ),
        }
        if str(except_template_target_element_linear_match.group("family_suffix")) == "_and_family_lookup_table":
            parts["family_lookup_table"] = _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            )
        payload = _combined_payload(str(variant_text), parts)
        payload["family_lookup_table_removed"] = bool(
            str(except_template_target_element_linear_match.group("family_suffix"))
            == "_and_family_lookup_table"
        )
        return payload

    except_template_index_restrict_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"([A-Za-z0-9_]+)_and_restrict_template_index_first_(\d+)"
        r"(?P<family_suffix>_and_family_lookup_table)?$",
        str(variant_text),
    )
    if except_template_index_restrict_match is not None:
        template = str(except_template_index_restrict_match.group(1))
        parts = {
            "power_coverage_except_template_elements": _remove_power_coverage_element_except_template_constraints_payload(
                model_proto,
                excluded_powered_template=template,
            ),
        }
        if except_template_index_restrict_match.group("family_suffix") is not None:
            parts["family_lookup_table"] = _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            )
        payload = _combined_payload(str(variant_text), parts)
        payload["diagnostic_warning"] = (
            "diagnostic-only protocol cover-choice index-domain restriction; not proof-source semantics"
        )
        payload["family_lookup_table_removed"] = bool(
            except_template_index_restrict_match.group("family_suffix") is not None
        )
        return payload

    except_template_index_restrict_last_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"([A-Za-z0-9_]+)_and_restrict_template_index_last_(\d+)"
        r"(?P<family_suffix>_and_family_lookup_table)?$",
        str(variant_text),
    )
    if except_template_index_restrict_last_match is not None:
        template = str(except_template_index_restrict_last_match.group(1))
        parts = {
            "power_coverage_except_template_elements": _remove_power_coverage_element_except_template_constraints_payload(
                model_proto,
                excluded_powered_template=template,
            ),
        }
        if except_template_index_restrict_last_match.group("family_suffix") is not None:
            parts["family_lookup_table"] = _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            )
        payload = _combined_payload(str(variant_text), parts)
        payload["diagnostic_warning"] = (
            "diagnostic-only protocol cover-choice index-domain restriction; not proof-source semantics"
        )
        payload["family_lookup_table_removed"] = bool(
            except_template_index_restrict_last_match.group("family_suffix") is not None
        )
        return payload

    except_template_index_restrict_window_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"([A-Za-z0-9_]+)_and_restrict_template_index_window_(\d+)_(\d+)"
        r"(?P<family_suffix>_and_family_lookup_table)?$",
        str(variant_text),
    )
    if except_template_index_restrict_window_match is not None:
        template = str(except_template_index_restrict_window_match.group(1))
        parts = {
            "power_coverage_except_template_elements": _remove_power_coverage_element_except_template_constraints_payload(
                model_proto,
                excluded_powered_template=template,
            ),
        }
        if except_template_index_restrict_window_match.group("family_suffix") is not None:
            parts["family_lookup_table"] = _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            )
        payload = _combined_payload(str(variant_text), parts)
        payload["diagnostic_warning"] = (
            "diagnostic-only protocol cover-choice index-domain restriction; not proof-source semantics"
        )
        payload["family_lookup_table_removed"] = bool(
            except_template_index_restrict_window_match.group("family_suffix") is not None
        )
        return payload

    except_template_active_prefix_guard_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"([A-Za-z0-9_]+)_and_add_template_index_active_prefix_guard_and_family_lookup_table$",
        str(variant_text),
    )
    if except_template_active_prefix_guard_match is not None:
        template = str(except_template_active_prefix_guard_match.group(1))
        parts = {
            "power_coverage_except_template_elements": _remove_power_coverage_element_except_template_constraints_payload(
                model_proto,
                excluded_powered_template=template,
            ),
            "family_lookup_table": _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            ),
        }
        payload = _combined_payload(str(variant_text), parts)
        payload["diagnostic_warning"] = (
            "diagnostic-only active-prefix index guard; not proof-source semantics"
        )
        return payload

    except_template_target_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"([A-Za-z0-9_]+)_and_template_([A-Za-z0-9_]+)"
        r"(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$",
        str(variant_text),
    )
    if except_template_target_match is not None:
        template = str(except_template_target_match.group(1))
        target_token = str(except_template_target_match.group(2))
        parts = {
            "power_coverage_except_template_elements": _remove_power_coverage_element_except_template_constraints_payload(
                model_proto,
                excluded_powered_template=template,
            ),
            "power_coverage_template_element_targets": _remove_power_coverage_element_template_constraints_payload(
                model_proto,
                powered_template=template,
                target_prefixes=_cover_choice_target_prefixes_from_token(target_token),
            ),
        }
        if str(except_template_target_match.group("family_suffix")) == "_and_family_lookup_table":
            parts["family_lookup_table"] = _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            )
        payload = _combined_payload(str(variant_text), parts)
        payload["family_lookup_table_removed"] = bool(
            str(except_template_target_match.group("family_suffix"))
            == "_and_family_lookup_table"
        )
        return payload

    except_template_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"([A-Za-z0-9_]+?)(?P<family_suffix>_and_family_lookup_table|_keep_family_lookup_table)$",
        str(variant_text),
    )
    if except_template_match is not None:
        template = str(except_template_match.group(1))
        parts = {
            "power_coverage_except_template_elements": _remove_power_coverage_element_except_template_constraints_payload(
                model_proto,
                excluded_powered_template=template,
            ),
        }
        if str(except_template_match.group("family_suffix")) == "_and_family_lookup_table":
            parts["family_lookup_table"] = _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            )
        payload = _combined_payload(str(variant_text), parts)
        payload["family_lookup_table_removed"] = bool(
            str(except_template_match.group("family_suffix")) == "_and_family_lookup_table"
        )
        return payload

    except_templates_match = re.match(
        r"^remove_power_coverage_elements_except_templates_"
        r"([A-Za-z0-9_+]+)_and_family_lookup_table$",
        str(variant_text),
    )
    if except_templates_match is not None:
        templates = _template_group_from_token(str(except_templates_match.group(1)))
        parts = {
            "power_coverage_except_templates_elements": _remove_power_coverage_element_except_templates_constraints_payload(
                model_proto,
                excluded_powered_templates=templates,
            ),
            "family_lookup_table": _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            ),
        }
        return _combined_payload(str(variant_text), parts)

    replace_template_match = re.match(
        r"^replace_power_coverage_elements_template_"
        r"([A-Za-z0-9_]+)_with_selected_coord_literals_and_family_lookup_table$",
        str(variant_text),
    )
    if replace_template_match is not None:
        template = str(replace_template_match.group(1))
        parts = {
            "power_coverage_template_elements": _remove_power_coverage_element_template_constraints_payload(
                model_proto,
                powered_template=template,
            ),
            "power_coverage_template_linear": _remove_power_coverage_linear_template_constraints_payload(
                model_proto,
                powered_template=template,
                mode="power_coverage_active_and_geometry_relaxed",
            ),
            "family_lookup_table": _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            ),
        }
        payload = _combined_payload(str(variant_text), parts)
        payload["diagnostic_warning"] = (
            "diagnostic-only template selected-coordinate replacement; not proof-source semantics"
        )
        return payload

    replace_only_template_match = re.match(
        r"^replace_power_coverage_elements_only_template_"
        r"([A-Za-z0-9_]+)_with_selected_coord_literals_and_family_lookup_table$",
        str(variant_text),
    )
    if replace_only_template_match is not None:
        parts = {
            "power_coverage_elements": _remove_power_coverage_element_constraints_payload(
                model_proto
            ),
            "power_coverage_linear": _remove_power_coverage_linear_constraints_payload(
                model_proto,
                mode="power_coverage_active_and_geometry_relaxed",
            ),
            "family_lookup_table": _remove_power_family_layer_constraints_payload(
                model_proto,
                mode="power_family_lookup_table_constraints_relaxed",
            ),
        }
        payload = _combined_payload(str(variant_text), parts)
        payload["diagnostic_warning"] = (
            "diagnostic-only isolated template selected-coordinate replacement; not proof-source semantics"
        )
        return payload

    return None

def _element_targets_family_table_subset_parts(
    model_proto: Any,
    *,
    selector: Mapping[str, Any],
) -> Dict[str, Mapping[str, Any]]:
    return {
        "power_coverage_elements": _remove_power_coverage_element_constraints_payload(
            model_proto
        ),
        "family_lookup_table_subset": _remove_family_lookup_table_constraints_by_slot_selector_payload(
            model_proto,
            selector=selector,
        ),
    }


def _element_target_family_parts(
    model_proto: Any,
    *,
    target_prefixes: Sequence[str],
    family_part: str,
) -> Dict[str, Mapping[str, Any]]:
    parts = {
        "power_coverage_element_targets": _remove_power_coverage_element_target_constraints_payload(
            model_proto,
            target_prefixes=target_prefixes,
        )
    }
    if family_part == "table":
        parts["family_lookup_table"] = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_table_constraints_relaxed",
        )
    elif family_part == "all_linear":
        parts["family_lookup_all_linear"] = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_linear_constraints_relaxed",
        )
    elif family_part == "all":
        parts["family_lookup_all"] = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_constraints_relaxed",
        )
    else:
        raise ValueError(f"Unsupported family part: {family_part!r}")
    return parts


def _expanded_cover_choice_target_prefixes(
    target_prefixes: Sequence[str],
) -> tuple[str, ...]:
    expansion = {
        "cover_choice_active__": ("cover_choice_active__", "cover_choice_block_active__"),
        "cover_choice_x__": ("cover_choice_x__", "cover_choice_block_x__"),
        "cover_choice_y__": ("cover_choice_y__", "cover_choice_block_y__"),
    }
    expanded: list[str] = []
    for raw_prefix in target_prefixes:
        for prefix in expansion.get(str(raw_prefix), (str(raw_prefix),)):
            if prefix not in expanded:
                expanded.append(prefix)
    return tuple(expanded)


def _remove_power_coverage_element_target_constraints_payload(
    model_proto: Any,
    *,
    target_prefixes: Sequence[str],
) -> Dict[str, Any]:
    requested_prefixes = tuple(str(prefix) for prefix in target_prefixes)
    prefixes = _expanded_cover_choice_target_prefixes(target_prefixes)
    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
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
        target_names = [
            var_names.get(int(var_idx), "")
            for var_idx in _element_target_var_indices(element)
        ]
        matched = {
            str(prefix)
            for name in target_names
            for prefix in prefixes
            if str(name).startswith(str(prefix))
        }
        if not matched:
            continue
        remove_indices.append(int(constraint_idx))
        for prefix in matched:
            removed_by_prefix[str(prefix)] = int(removed_by_prefix.get(str(prefix), 0)) + 1
    if remove_indices:
        _delete_constraint_indices(model_proto, remove_indices)
    return {
        "removed_constraint_count": int(len(remove_indices)),
        "removed_constraint_indices": [int(index) for index in remove_indices],
        "target_prefixes": [str(prefix) for prefix in prefixes],
        "removed_by_prefix": dict(
            sorted(
                (str(prefix), int(count))
                for prefix, count in removed_by_prefix.items()
                if int(count) > 0 or str(prefix) in set(requested_prefixes)
            )
        ),
    }


def _remove_power_coverage_element_template_constraints_payload(
    model_proto: Any,
    *,
    powered_template: str,
    target_prefixes: Sequence[str] = (
        "cover_choice_active__",
        "cover_choice_x__",
        "cover_choice_y__",
    ),
) -> Dict[str, Any]:
    template_marker = f"::{str(powered_template)}::"
    requested_prefixes = tuple(str(prefix) for prefix in target_prefixes)
    prefixes = _expanded_cover_choice_target_prefixes(target_prefixes)
    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
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
        target_names = [
            var_names.get(int(var_idx), "")
            for var_idx in _element_target_var_indices(element)
        ]
        matched_prefixes = {
            str(prefix)
            for name in target_names
            for prefix in prefixes
            if str(name).startswith(str(prefix)) and template_marker in str(name)
        }
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
        "powered_template": str(powered_template),
        "target_prefixes": [str(prefix) for prefix in prefixes],
        "removed_by_prefix": dict(
            sorted(
                (str(prefix), int(count))
                for prefix, count in removed_by_prefix.items()
                if int(count) > 0 or str(prefix) in set(requested_prefixes)
            )
        ),
    }


def _remove_power_coverage_element_template_slot_window_constraints_payload(
    model_proto: Any,
    *,
    powered_template: str,
    target_prefixes: Sequence[str],
    start: int,
    count: int,
    channel_layer: str = "all",
) -> Dict[str, Any]:
    template_marker = f"::{str(powered_template)}::"
    prefixes = _cover_choice_target_prefixes_for_layer(
        _expanded_cover_choice_target_prefixes(target_prefixes),
        channel_layer=channel_layer,
    )
    start_idx = max(0, int(start))
    count_int = max(1, int(count))
    end_idx = start_idx + count_int
    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
    remove_indices: list[int] = []
    removed_by_prefix: Dict[str, int] = {str(prefix): 0 for prefix in prefixes}
    removed_slot_indices: set[int] = set()
    constraints = getattr(model_proto, "constraints", [])
    for constraint_idx, constraint in enumerate(list(constraints)):
        element = (
            getattr(constraint, "element", None)
            if _constraint_has_field(constraint, "element")
            else None
        )
        if element is None:
            continue
        target_names = [
            var_names.get(int(var_idx), "")
            for var_idx in _element_target_var_indices(element)
        ]
        matched_prefixes: set[str] = set()
        matched_slots: set[int] = set()
        for name in target_names:
            if template_marker not in str(name):
                continue
            slot_idx = _powered_template_slot_index_from_var_name(
                str(name),
                powered_template=str(powered_template),
            )
            if slot_idx is None or not (start_idx <= int(slot_idx) < end_idx):
                continue
            for prefix in prefixes:
                if str(name).startswith(str(prefix)):
                    matched_prefixes.add(str(prefix))
                    matched_slots.add(int(slot_idx))
        if not matched_prefixes:
            continue
        remove_indices.append(int(constraint_idx))
        for prefix in matched_prefixes:
            removed_by_prefix[str(prefix)] = int(removed_by_prefix.get(str(prefix), 0)) + 1
        removed_slot_indices.update(matched_slots)
    if remove_indices:
        _delete_constraint_indices(model_proto, remove_indices)
    return {
        "removed_constraint_count": int(len(remove_indices)),
        "removed_constraint_indices": [int(index) for index in remove_indices],
        "powered_template": str(powered_template),
        "target_prefixes": [str(prefix) for prefix in prefixes],
        "channel_layer": str(channel_layer),
        "slot_window": {"start": int(start_idx), "count": int(count_int), "end": int(end_idx)},
        "removed_slot_indices": [int(index) for index in sorted(removed_slot_indices)],
        "removed_by_prefix": dict(
            sorted(
                (str(prefix), int(count))
                for prefix, count in removed_by_prefix.items()
                if int(count) > 0
            )
        ),
    }


def _cover_choice_target_prefixes_for_layer(
    prefixes: Sequence[str],
    *,
    channel_layer: str,
) -> tuple[str, ...]:
    layer = str(channel_layer).strip().lower()
    normalized = tuple(str(prefix) for prefix in prefixes)
    if layer in {"", "all"}:
        return normalized
    if layer == "final":
        return tuple(
            prefix for prefix in normalized if not str(prefix).startswith("cover_choice_block_")
        )
    if layer == "block":
        return tuple(
            prefix for prefix in normalized if str(prefix).startswith("cover_choice_block_")
        )
    raise ValueError(f"Unsupported cover-choice target channel layer: {channel_layer!r}")


def _remove_power_coverage_element_except_template_constraints_payload(
    model_proto: Any,
    *,
    excluded_powered_template: str,
    target_prefixes: Sequence[str] = (
        "cover_choice_active__",
        "cover_choice_x__",
        "cover_choice_y__",
    ),
) -> Dict[str, Any]:
    payload = _remove_power_coverage_element_except_templates_constraints_payload(
        model_proto,
        excluded_powered_templates=(str(excluded_powered_template),),
        target_prefixes=target_prefixes,
    )
    payload["excluded_powered_template"] = str(excluded_powered_template)
    return payload


def _remove_power_coverage_element_except_templates_constraints_payload(
    model_proto: Any,
    *,
    excluded_powered_templates: Sequence[str],
    target_prefixes: Sequence[str] = (
        "cover_choice_active__",
        "cover_choice_x__",
        "cover_choice_y__",
    ),
) -> Dict[str, Any]:
    excluded_templates = tuple(str(template) for template in excluded_powered_templates)
    excluded_markers = tuple(f"::{template}::" for template in excluded_templates)
    prefixes = tuple(str(prefix) for prefix in target_prefixes)
    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
    remove_indices: list[int] = []
    removed_by_prefix: Dict[str, int] = {str(prefix): 0 for prefix in prefixes}
    kept_by_prefix: Dict[str, int] = {str(prefix): 0 for prefix in prefixes}
    constraints = getattr(model_proto, "constraints", [])
    for constraint_idx, constraint in enumerate(list(constraints)):
        element = (
            getattr(constraint, "element", None)
            if _constraint_has_field(constraint, "element")
            else None
        )
        if element is None:
            continue
        target_names = [
            var_names.get(int(var_idx), "")
            for var_idx in _element_target_var_indices(element)
        ]
        matched_prefixes = {
            str(prefix)
            for name in target_names
            for prefix in prefixes
            if str(name).startswith(str(prefix))
        }
        if not matched_prefixes:
            continue
        if any(
            marker in str(name)
            for marker in excluded_markers
            for name in target_names
        ):
            for prefix in matched_prefixes:
                kept_by_prefix[str(prefix)] = int(kept_by_prefix.get(str(prefix), 0)) + 1
            continue
        remove_indices.append(int(constraint_idx))
        for prefix in matched_prefixes:
            removed_by_prefix[str(prefix)] = int(removed_by_prefix.get(str(prefix), 0)) + 1
    if remove_indices:
        _delete_constraint_indices(model_proto, remove_indices)
    return {
        "removed_constraint_count": int(len(remove_indices)),
        "removed_constraint_indices": [int(index) for index in remove_indices],
        "excluded_powered_templates": [str(template) for template in excluded_templates],
        "target_prefixes": [str(prefix) for prefix in prefixes],
        "removed_by_prefix": dict(sorted(removed_by_prefix.items())),
        "kept_by_prefix": dict(sorted(kept_by_prefix.items())),
    }


def _remove_power_coverage_linear_template_constraints_payload(
    model_proto: Any,
    *,
    powered_template: str,
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
    template_marker = f"::{str(powered_template)}::"
    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
    remove_indices: list[int] = []
    removed_by_prefix: Dict[str, int] = {str(prefix): 0 for prefix in prefixes}
    constraints = getattr(model_proto, "constraints", [])
    for constraint_idx, constraint in enumerate(list(constraints)):
        linear = (
            getattr(constraint, "linear", None)
            if _constraint_has_field(constraint, "linear")
            else None
        )
        if linear is None:
            continue
        matched_prefixes: set[str] = set()
        for var_idx in list(getattr(linear, "vars", [])):
            name = var_names.get(int(var_idx), "")
            if template_marker not in str(name):
                continue
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
        "powered_template": str(powered_template),
        "var_name_prefixes": [str(prefix) for prefix in prefixes],
        "removed_by_prefix": dict(sorted(removed_by_prefix.items())),
    }


def _remove_power_coverage_linear_template_target_constraints_payload(
    model_proto: Any,
    *,
    powered_template: str,
    target_prefixes: Sequence[str],
) -> Dict[str, Any]:
    prefixes = tuple(str(prefix) for prefix in target_prefixes)
    template_marker = f"::{str(powered_template)}::"
    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
    remove_indices: list[int] = []
    removed_by_prefix: Dict[str, int] = {str(prefix): 0 for prefix in prefixes}
    constraints = getattr(model_proto, "constraints", [])
    for constraint_idx, constraint in enumerate(list(constraints)):
        linear = (
            getattr(constraint, "linear", None)
            if _constraint_has_field(constraint, "linear")
            else None
        )
        if linear is None:
            continue
        matched_prefixes: set[str] = set()
        for var_idx in list(getattr(linear, "vars", [])):
            name = var_names.get(int(var_idx), "")
            if template_marker not in str(name):
                continue
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
        "powered_template": str(powered_template),
        "target_prefixes": [str(prefix) for prefix in prefixes],
        "removed_by_prefix": dict(sorted(removed_by_prefix.items())),
    }


def _template_group_from_token(raw_token: str) -> tuple[str, ...]:
    return tuple(
        str(token).strip()
        for token in str(raw_token).split("+")
        if str(token).strip()
    )


def _cover_choice_target_prefixes_from_token(raw_token: str) -> tuple[str, ...]:
    token = str(raw_token).strip().lower()
    prefix_by_token = {
        "active": ("cover_choice_active__",),
        "x": ("cover_choice_x__",),
        "y": ("cover_choice_y__",),
        "xy": ("cover_choice_x__", "cover_choice_y__"),
        "active_x": ("cover_choice_active__", "cover_choice_x__"),
        "active_y": ("cover_choice_active__", "cover_choice_y__"),
        "active_xy": (
            "cover_choice_active__",
            "cover_choice_x__",
            "cover_choice_y__",
        ),
    }
    prefixes = prefix_by_token.get(token)
    if prefixes is None:
        raise ValueError(f"Unsupported cover-choice target token: {raw_token!r}")
    return tuple(prefixes)


def _selected_coord_template_replacement_from_variant(
    variant_text: str,
) -> Optional[Dict[str, str]]:
    replace_template_match = re.match(
        r"^replace_power_coverage_elements_template_"
        r"([A-Za-z0-9_]+)_with_selected_coord_literals_and_family_lookup_table$",
        str(variant_text),
    )
    if replace_template_match is not None:
        return {
            "mode": "template_in_place",
            "powered_template": str(replace_template_match.group(1)),
        }
    replace_only_template_match = re.match(
        r"^replace_power_coverage_elements_only_template_"
        r"([A-Za-z0-9_]+)_with_selected_coord_literals_and_family_lookup_table$",
        str(variant_text),
    )
    if replace_only_template_match is not None:
        return {
            "mode": "isolated_template",
            "powered_template": str(replace_only_template_match.group(1)),
        }
    return None


def _template_index_restriction_from_variant(
    variant_text: str,
) -> Optional[Dict[str, Any]]:
    first_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"([A-Za-z0-9_]+)_and_restrict_template_index_first_(\d+)"
        r"(?:_and_family_lookup_table)?$",
        str(variant_text),
    )
    if first_match is not None:
        return {
            "powered_template": str(first_match.group(1)),
            "mode": "first",
            "limit": max(1, int(first_match.group(2))),
        }
    last_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"([A-Za-z0-9_]+)_and_restrict_template_index_last_(\d+)"
        r"(?:_and_family_lookup_table)?$",
        str(variant_text),
    )
    if last_match is not None:
        return {
            "powered_template": str(last_match.group(1)),
            "mode": "last",
            "limit": max(1, int(last_match.group(2))),
        }
    window_match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"([A-Za-z0-9_]+)_and_restrict_template_index_window_(\d+)_(\d+)"
        r"(?:_and_family_lookup_table)?$",
        str(variant_text),
    )
    if window_match is not None:
        return {
            "powered_template": str(window_match.group(1)),
            "mode": "window",
            "start": max(0, int(window_match.group(2))),
            "count": max(1, int(window_match.group(3))),
        }
    return None


def _template_index_active_prefix_guard_from_variant(
    variant_text: str,
) -> Optional[Dict[str, str]]:
    match = re.match(
        r"^remove_power_coverage_elements_except_template_"
        r"([A-Za-z0-9_]+)_and_add_template_index_active_prefix_guard_and_family_lookup_table$",
        str(variant_text),
    )
    if match is None:
        return None
    return {"powered_template": str(match.group(1))}



def _element_target_var_indices(element: Any) -> list[int]:
    indices: set[int] = set()
    for expr_attr in ("linear_target", "target"):
        expr = getattr(element, expr_attr, None)
        if expr is None:
            continue
        vars_ = getattr(expr, "vars", None)
        if vars_ is not None:
            indices.update(int(var_idx) for var_idx in list(vars_))
            continue
        try:
            value = int(expr)
        except Exception:
            continue
        if value >= 0:
            indices.add(int(value))
    return sorted(indices)


def _remove_family_lookup_table_constraints_by_slot_selector_payload(
    model_proto: Any,
    *,
    selector: Mapping[str, Any],
) -> Dict[str, Any]:
    candidates = _family_lookup_table_candidates(model_proto)
    selected: list[Dict[str, Any]] = []
    kind = str(selector.get("kind", ""))
    if kind == "first":
        limit = max(0, int(selector.get("limit", 0)))
        selected = candidates[:limit]
    elif kind == "last":
        limit = max(0, int(selector.get("limit", 0)))
        selected = candidates[-limit:] if limit > 0 else []
    elif kind == "quarter":
        quarter_count = max(1, int(selector.get("quarter_count", 4)))
        quarter = max(0, min(int(selector.get("quarter", 0)), quarter_count - 1))
        total = len(candidates)
        start = (total * quarter) // quarter_count
        end = (total * (quarter + 1)) // quarter_count
        selected = candidates[start:end]
    elif kind == "every":
        step = max(1, int(selector.get("step", 1)))
        offset = int(selector.get("offset", 0)) % step
        selected = [
            item
            for ordinal, item in enumerate(candidates)
            if int(ordinal) % int(step) == int(offset)
        ]
    elif kind == "slot_mod":
        modulus = max(1, int(selector.get("modulus", 1)))
        remainder = int(selector.get("remainder", 0)) % modulus
        selected = [
            item
            for item in candidates
            if int(item["slot_idx"]) % int(modulus) == int(remainder)
        ]
    elif kind == "slot_hash_bucket":
        bucket_count = max(1, int(selector.get("bucket_count", 1)))
        bucket = int(selector.get("bucket", 0)) % bucket_count
        selected = [
            item
            for item in candidates
            if _stable_slot_bucket(int(item["slot_idx"]), int(bucket_count)) == int(bucket)
        ]
    else:
        raise ValueError(f"Unsupported family lookup table slot selector: {dict(selector)!r}")
    remove_indices = [int(item["constraint_idx"]) for item in selected]
    if remove_indices:
        _delete_constraint_indices(model_proto, remove_indices)
    return {
        "selector": dict(selector),
        "candidate_table_constraint_count": int(len(candidates)),
        "removed_constraint_count": int(len(remove_indices)),
        "removed_constraint_indices": remove_indices,
        "removed_slot_indices": [int(item["slot_idx"]) for item in selected],
        "removed_slot_sample": [
            int(item["slot_idx"]) for item in selected[:25]
        ],
        "slot_selection_profile": _slot_selection_profile(candidates, selected),
        "table_shape_profile": _family_lookup_table_shape_profile(candidates),
    }


def _family_lookup_table_candidates(model_proto: Any) -> list[Dict[str, Any]]:
    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
    candidates: list[Dict[str, Any]] = []
    constraints = getattr(model_proto, "constraints", [])
    for constraint_idx, constraint in enumerate(list(constraints)):
        if not _constraint_has_field(constraint, "table"):
            continue
        table = getattr(constraint, "table", None)
        if table is None:
            continue
        var_indices = _constraint_var_indices(constraint)
        family_var_indices = [
            int(var_idx)
            for var_idx in var_indices
            if str(var_names.get(int(var_idx), "")).startswith("family__")
        ]
        if not family_var_indices:
            continue
        slot_indices: list[int] = []
        for var_idx in family_var_indices:
            slot_idx = _slot_index_from_var_name(var_names.get(int(var_idx), ""))
            if slot_idx is not None:
                slot_indices.append(int(slot_idx))
        if not slot_indices:
            continue
        expr_var_indices = _table_expr_var_indices(table)
        arity = _table_arity(table)
        value_count = len(list(getattr(table, "values", [])))
        row_count = (value_count // arity) if arity > 0 else 0
        family_column = _table_column_for_var(table, int(family_var_indices[0]))
        candidates.append(
            {
                "slot_idx": int(slot_indices[0]),
                "constraint_idx": int(constraint_idx),
                "arity": int(arity),
                "row_count": int(row_count),
                "value_count": int(value_count),
                "family_column": None if family_column is None else int(family_column),
                "negated": bool(getattr(table, "negated", False)),
                "uses_exprs": bool(len(expr_var_indices) > 0),
                "expr_var_indices": [int(var_idx) for var_idx in expr_var_indices],
                "var_names": [var_names.get(int(var_idx), "") for var_idx in var_indices],
            }
        )
    return sorted(candidates, key=lambda item: (int(item["slot_idx"]), int(item["constraint_idx"])))


def _remove_family_lookup_table_rows_payload(
    model_proto: Any,
    *,
    selector: Mapping[str, Any],
) -> Dict[str, Any]:
    if str(selector.get("kind")) != "family_mod":
        raise ValueError(f"Unsupported family lookup table row selector: {dict(selector)!r}")
    modulus = max(1, int(selector.get("modulus", 1)))
    remainder = int(selector.get("remainder", 0)) % modulus
    candidates = _family_lookup_table_candidates(model_proto)
    constraints = getattr(model_proto, "constraints", [])
    touched_indices: list[int] = []
    rows_before_total = 0
    rows_after_total = 0
    removed_rows_total = 0
    skipped: list[Dict[str, Any]] = []
    touched_slot_indices: list[int] = []
    for item in candidates:
        constraint_idx = int(item["constraint_idx"])
        if constraint_idx < 0 or constraint_idx >= len(constraints):
            continue
        constraint = constraints[constraint_idx]
        if not _constraint_has_field(constraint, "table"):
            continue
        table = getattr(constraint, "table", None)
        if table is None:
            continue
        arity = _table_arity(table)
        family_column = item.get("family_column")
        values = [int(value) for value in list(getattr(table, "values", []))]
        if arity <= 0 or family_column is None or len(values) % arity != 0:
            skipped.append(
                {
                    "slot_idx": int(item["slot_idx"]),
                    "constraint_idx": int(constraint_idx),
                    "reason": "table_arity_or_family_column_unavailable",
                }
            )
            continue
        kept: list[int] = []
        row_count = len(values) // int(arity)
        removed_rows = 0
        for row_start in range(0, len(values), int(arity)):
            row = values[row_start : row_start + int(arity)]
            family_value = int(row[int(family_column)])
            if family_value % int(modulus) == int(remainder):
                removed_rows += 1
                continue
            kept.extend(row)
        if removed_rows <= 0:
            rows_before_total += int(row_count)
            rows_after_total += int(row_count)
            continue
        table.values.clear()
        table.values.extend(int(value) for value in kept)
        touched_indices.append(int(constraint_idx))
        touched_slot_indices.append(int(item["slot_idx"]))
        rows_before_total += int(row_count)
        rows_after_total += int(len(kept) // int(arity))
        removed_rows_total += int(removed_rows)
    return {
        "selector": dict(selector),
        "candidate_table_constraint_count": int(len(candidates)),
        "touched_constraint_count": int(len(touched_indices)),
        "removed_constraint_count": 0,
        "touched_constraint_indices": [int(index) for index in touched_indices],
        "touched_slot_indices": [int(index) for index in touched_slot_indices],
        "touched_slot_sample": [int(index) for index in touched_slot_indices[:25]],
        "rows_before_total": int(rows_before_total),
        "rows_after_total": int(rows_after_total),
        "removed_row_count": int(removed_rows_total),
        "skipped_table_count": int(len(skipped)),
        "skipped_table_sample": skipped[:10],
        "table_shape_profile": _family_lookup_table_shape_profile(candidates),
        "diagnostic_warning": "row removal strengthens allowed-assignment tables and is not proof-source semantics",
    }


def _table_expr_var_indices(table: Any) -> list[int]:
    result: list[int] = []
    for expr in list(getattr(table, "exprs", [])):
        vars_ = [int(var_idx) for var_idx in list(getattr(expr, "vars", []))]
        if len(vars_) == 1 and len(list(getattr(expr, "coeffs", []))) <= 1:
            result.append(int(vars_[0]))
        else:
            result.extend(vars_)
    return result


def _table_arity(table: Any) -> int:
    exprs = list(getattr(table, "exprs", []))
    if exprs:
        return int(len(exprs))
    vars_ = list(getattr(table, "vars", []))
    return int(len(vars_))


def _table_column_for_var(table: Any, var_index: int) -> Optional[int]:
    exprs = list(getattr(table, "exprs", []))
    if exprs:
        for column, expr in enumerate(exprs):
            vars_ = [int(var_idx) for var_idx in list(getattr(expr, "vars", []))]
            coeffs = [int(coeff) for coeff in list(getattr(expr, "coeffs", []))]
            if vars_ == [int(var_index)] and (not coeffs or coeffs == [1]):
                return int(column)
        return None
    vars_ = [int(var_idx) for var_idx in list(getattr(table, "vars", []))]
    for column, var_idx in enumerate(vars_):
        if int(var_idx) == int(var_index):
            return int(column)
    return None


def _stable_slot_bucket(slot_idx: int, bucket_count: int) -> int:
    # Small, deterministic integer mixer.  This avoids Python's randomized hash()
    # while still producing non-contiguous buckets over slot ids.
    bucket_count = max(1, int(bucket_count))
    value = (int(slot_idx) ^ 0x9E3779B9) * 0x85EBCA6B
    value ^= value >> 13
    value *= 0xC2B2AE35
    value ^= value >> 16
    return int(value % bucket_count)


def _slot_selection_profile(
    candidates: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    all_slots = [int(item["slot_idx"]) for item in candidates]
    selected_slots = [int(item["slot_idx"]) for item in selected]
    selected_set = set(selected_slots)
    return {
        "candidate_slot_count": int(len(all_slots)),
        "selected_slot_count": int(len(selected_slots)),
        "unselected_slot_count": int(len(all_slots) - len(selected_slots)),
        "selected_fraction": float(len(selected_slots) / len(all_slots)) if all_slots else 0.0,
        "selected_min_slot": min(selected_slots) if selected_slots else None,
        "selected_max_slot": max(selected_slots) if selected_slots else None,
        "unselected_slot_sample": [
            int(slot_idx) for slot_idx in all_slots if int(slot_idx) not in selected_set
        ][:25],
    }


def _family_lookup_table_shape_profile(
    candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    arity_counts: Dict[str, int] = {}
    row_count_counts: Dict[str, int] = {}
    family_column_counts: Dict[str, int] = {}
    expr_style_counts: Dict[str, int] = {"exprs": 0, "vars": 0}
    negated_count = 0
    for item in candidates:
        arity = str(int(item.get("arity", 0)))
        rows = str(int(item.get("row_count", 0)))
        family_column = item.get("family_column")
        arity_counts[arity] = int(arity_counts.get(arity, 0)) + 1
        row_count_counts[rows] = int(row_count_counts.get(rows, 0)) + 1
        family_column_key = "none" if family_column is None else str(int(family_column))
        family_column_counts[family_column_key] = int(family_column_counts.get(family_column_key, 0)) + 1
        if bool(item.get("uses_exprs", False)):
            expr_style_counts["exprs"] = int(expr_style_counts.get("exprs", 0)) + 1
        else:
            expr_style_counts["vars"] = int(expr_style_counts.get("vars", 0)) + 1
        if bool(item.get("negated", False)):
            negated_count += 1
    return {
        "table_count": int(len(candidates)),
        "arity_counts": dict(sorted(arity_counts.items())),
        "row_count_counts": dict(sorted(row_count_counts.items())),
        "family_column_counts": dict(sorted(family_column_counts.items())),
        "expr_style_counts": dict(sorted(expr_style_counts.items())),
        "negated_table_count": int(negated_count),
        "slot_index_sample": [int(item["slot_idx"]) for item in list(candidates)[:25]],
    }

def _slot_index_from_var_name(name: str) -> Optional[int]:
    marker = "::slot::"
    if marker not in str(name):
        return None
    tail = str(name).rsplit(marker, 1)[1]
    token = tail.split("::", 1)[0]
    try:
        return int(token)
    except Exception:
        return None


def _powered_template_slot_index_from_var_name(
    name: str,
    *,
    powered_template: str,
) -> Optional[int]:
    marker = f"::{str(powered_template)}::slot::"
    text = str(name)
    marker_index = text.find(marker)
    if marker_index < 0:
        return None
    tail = text[marker_index + len(marker) :]
    match = re.match(r"(\d+)", tail)
    if match is None:
        return None
    token = match.group(1)
    try:
        return int(token)
    except Exception:
        return None


def _coverage_family_parts(
    model_proto: Any,
    *,
    coverage_parts: Sequence[str],
    family_part: str,
) -> Dict[str, Mapping[str, Any]]:
    parts: Dict[str, Mapping[str, Any]] = {}
    for coverage_part in coverage_parts:
        if coverage_part == "elements":
            parts["power_coverage_elements"] = _remove_power_coverage_element_constraints_payload(
                model_proto
            )
        elif coverage_part == "linear":
            parts["power_coverage_linear"] = _remove_power_coverage_linear_constraints_payload(
                model_proto,
                mode="power_coverage_active_and_geometry_relaxed",
            )
        elif coverage_part == "no_overlap":
            parts["power_pole_no_overlap"] = _remove_power_pole_intervals_from_no_overlap_2d_payload(
                model_proto
            )
        else:
            raise ValueError(f"Unsupported coverage part: {coverage_part!r}")
    if family_part == "table":
        parts["family_lookup_table"] = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_table_constraints_relaxed",
        )
    elif family_part == "all_linear":
        parts["family_lookup_all_linear"] = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_linear_constraints_relaxed",
        )
    elif family_part == "all":
        parts["family_lookup_all"] = _remove_power_family_layer_constraints_payload(
            model_proto,
            mode="power_family_lookup_constraints_relaxed",
        )
    else:
        raise ValueError(f"Unsupported family part: {family_part!r}")
    return parts


def _combined_payload(variant: str, parts: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    total = 0
    for payload in parts.values():
        total += int(payload.get("removed_constraint_count", 0))
        total += int(payload.get("touched_constraint_count", 0))
    return {
        "variant": str(variant),
        "removed_constraint_count": int(total),
        "parts": {str(key): dict(value) for key, value in parts.items()},
    }


def _proto_profile(model_proto: Any) -> Dict[str, Any]:
    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
    var_domains = {
        int(index): [int(value) for value in list(getattr(var, "domain", []))]
        for index, var in enumerate(variables)
    }
    kind_counts: Dict[str, int] = {}
    family_linear_categories: Dict[str, int] = {}
    constraints = list(getattr(model_proto, "constraints", []))
    for constraint in constraints:
        kind = _constraint_kind(constraint)
        kind_counts[kind] = int(kind_counts.get(kind, 0)) + 1
        category = _family_lookup_linear_constraint_category(
            constraint,
            var_names=var_names,
            var_domains=var_domains,
        )
        if category is not None:
            family_linear_categories[str(category)] = int(
                family_linear_categories.get(str(category), 0)
            ) + 1
    prefix_counts = {
        "family__": 0,
        "is_family__": 0,
        "cover_choice_": 0,
        "active__": 0,
        "d_lo__": 0,
        "d_hi__": 0,
    }
    for name in var_names.values():
        for prefix in list(prefix_counts):
            if str(name).startswith(prefix):
                prefix_counts[prefix] = int(prefix_counts[prefix]) + 1
    family_lookup_table_candidates = _family_lookup_table_candidates(model_proto)
    return {
        "variable_count": int(len(variables)),
        "constraint_count": int(len(constraints)),
        "constraint_kind_counts": dict(sorted(kind_counts.items())),
        "variable_prefix_counts": dict(sorted(prefix_counts.items())),
        "cover_choice_profile": _cover_choice_variable_profile(var_names.values()),
        "family_lookup_linear_category_counts": dict(
            sorted(family_linear_categories.items())
        ),
        "family_lookup_table_profile": _family_lookup_table_shape_profile(
            family_lookup_table_candidates
        ),
    }


def _cover_choice_variable_profile(var_names: Sequence[str]) -> Dict[str, Any]:
    prefix_counts: Dict[str, int] = {}
    mode_counts: Dict[str, int] = {
        "wide_idx": 0,
        "wide_target": 0,
        "block_idx": 0,
        "block_local_idx": 0,
        "block_local_selected": 0,
        "block_target": 0,
        "block_selected": 0,
        "other_cover_choice": 0,
    }
    role_counts: Dict[str, int] = {
        "wide_selector": 0,
        "final_target_channel": 0,
        "block_selector": 0,
        "local_selector": 0,
        "local_selected_literal": 0,
        "block_intermediate_target_channel": 0,
        "block_selected_literal": 0,
        "other_cover_choice": 0,
    }
    template_counts: Dict[str, Dict[str, int]] = {}
    template_slot_samples: Dict[str, list[int]] = {}
    for raw_name in var_names:
        name = str(raw_name)
        if not name.startswith("cover_choice_"):
            continue
        prefix = name.split("__", 1)[0]
        prefix_counts[prefix] = int(prefix_counts.get(prefix, 0)) + 1
        mode = _cover_choice_mode_from_var_name(name)
        mode_counts[mode] = int(mode_counts.get(mode, 0)) + 1
        role = _cover_choice_role_from_var_name(name)
        role_counts[role] = int(role_counts.get(role, 0)) + 1
        template = _template_from_var_name(name)
        if template is None:
            continue
        by_mode = template_counts.setdefault(str(template), {})
        by_mode[mode] = int(by_mode.get(mode, 0)) + 1
        slot_idx = _slot_index_from_var_name(name)
        if slot_idx is not None:
            samples = template_slot_samples.setdefault(str(template), [])
            if len(samples) < 10 and int(slot_idx) not in samples:
                samples.append(int(slot_idx))
    return {
        "total_cover_choice_variables": int(sum(prefix_counts.values())),
        "prefix_counts": dict(sorted(prefix_counts.items())),
        "mode_counts": dict(sorted(mode_counts.items())),
        "role_counts": dict(sorted(role_counts.items())),
        "target_channel_profile": {
            "final_target_channel_variables": int(
                role_counts.get("final_target_channel", 0)
            ),
            "block_intermediate_target_channel_variables": int(
                role_counts.get("block_intermediate_target_channel", 0)
            ),
            "wide_selector_variables": int(role_counts.get("wide_selector", 0)),
            "block_selector_variables": int(role_counts.get("block_selector", 0)),
            "local_selector_variables": int(role_counts.get("local_selector", 0)),
            "local_selected_literal_variables": int(
                role_counts.get("local_selected_literal", 0)
            ),
            "block_selected_literal_variables": int(
                role_counts.get("block_selected_literal", 0)
            ),
            "note": (
                "cover_choice_active/x/y are final selected-pole target channels; "
                "they remain in block_element encoding even when wide selectors "
                "are eliminated."
            ),
        },
        "template_counts": {
            str(template): dict(sorted(counts.items()))
            for template, counts in sorted(template_counts.items())
        },
        "template_slot_samples": {
            str(template): [int(value) for value in values]
            for template, values in sorted(template_slot_samples.items())
        },
    }


def _cover_choice_mode_from_var_name(name: str) -> str:
    text = str(name)
    if text.startswith("cover_choice_idx__"):
        return "wide_idx"
    if text.startswith(("cover_choice_active__", "cover_choice_x__", "cover_choice_y__")):
        return "wide_target"
    if text.startswith("cover_choice_block_idx__"):
        return "block_idx"
    if text.startswith("cover_choice_local_idx__"):
        return "block_local_idx"
    if text.startswith("cover_choice_local_selected__"):
        return "block_local_selected"
    if text.startswith("cover_choice_block_selected__"):
        return "block_selected"
    if text.startswith(
        (
            "cover_choice_block_active__",
            "cover_choice_block_x__",
            "cover_choice_block_y__",
        )
    ):
        return "block_target"
    return "other_cover_choice"


def _cover_choice_role_from_var_name(name: str) -> str:
    text = str(name)
    if text.startswith("cover_choice_idx__"):
        return "wide_selector"
    if text.startswith(("cover_choice_active__", "cover_choice_x__", "cover_choice_y__")):
        return "final_target_channel"
    if text.startswith("cover_choice_block_idx__"):
        return "block_selector"
    if text.startswith("cover_choice_local_idx__"):
        return "local_selector"
    if text.startswith("cover_choice_local_selected__"):
        return "local_selected_literal"
    if text.startswith("cover_choice_block_selected__"):
        return "block_selected_literal"
    if text.startswith(
        (
            "cover_choice_block_active__",
            "cover_choice_block_x__",
            "cover_choice_block_y__",
        )
    ):
        return "block_intermediate_target_channel"
    return "other_cover_choice"


def _template_from_var_name(name: str) -> Optional[str]:
    parts = str(name).split("__", 1)
    if len(parts) != 2:
        return None
    key = parts[1]
    tokens = key.split("::")
    try:
        slot_index = tokens.index("slot")
    except ValueError:
        return None
    if slot_index >= 2:
        return str(tokens[1])
    if slot_index <= 0:
        return None
    return str(tokens[slot_index - 1])


def _constraint_kind(constraint: Any) -> str:
    kinds = [
        field_name
        for field_name in (
            "bool_or",
            "bool_and",
            "linear",
            "element",
            "table",
            "interval",
            "no_overlap_2d",
            "lin_max",
        )
        if _constraint_has_field(constraint, field_name)
    ]
    return "+".join(kinds) if kinds else "empty"


def _normalize_variants(variants: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in variants:
        token = str(raw).strip()
        if not token or token in seen:
            continue
        if not _is_supported_variant(token):
            raise ValueError(f"Unsupported proto reduction variant: {raw!r}")
        seen.add(token)
        result.append(token)
    return tuple(result or DEFAULT_PROTO_REDUCTION_VARIANTS)


def _is_supported_variant(token: str) -> bool:
    if str(token) in set(DEFAULT_PROTO_REDUCTION_VARIANTS):
        return True
    if str(token) == POWER_COVERAGE_SELECTED_COORD_LITERAL_REPLACEMENT_VARIANT:
        return True
    if str(token) == FAMILY_LOOKUP_LINEAR_SHELL_GUARD_REPLACEMENT_VARIANT:
        return True
    if str(token) == POWER_COVERAGE_AND_FAMILY_LINEAR_GUARD_REPLACEMENT_VARIANT:
        return True
    return any(pattern.match(str(token)) for pattern in _DYNAMIC_PROTO_REDUCTION_VARIANT_PATTERNS)


def _status_from_entries(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    evaluated = [entry for entry in entries if bool(entry.get("evaluated", False))]
    counts = _status_counts(evaluated)
    unknowns = _unknown_diagnostics(evaluated)
    if not entries:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_proto_reduction_entries",
            "status_counts": counts,
            "recommendation": "No proto-reduction entries were evaluated.",
        }
    if any(
        str(entry.get("status")) in TERMINAL_PROTO_REDUCTION_STATUSES
        for entry in evaluated
    ):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "proto_reduction_terminal_found",
            "status_counts": counts,
            "recommendation": (
                "At least one proto-reduction variant reached terminal status; "
                "inspect status_counts and best_terminal_entry before interpreting "
                "UNKNOWN diagnostics."
            ),
        }
    if int(unknowns.get("search_progress_unknown_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "proto_reduction_search_progress_without_terminal",
            "status_counts": counts,
            "recommendation": "At least one proto-reduction variant produced branches/conflicts without terminal status; compare it against zero-branch variants.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "proto_reduction_zero_branch_unknown_remaining",
        "status_counts": counts,
        "recommendation": "All proto-reduction variants remain zero-branch UNKNOWN; broaden reduction families or inspect model build stats.",
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


def _best_terminal_entry(entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    terminal = [
        entry
        for entry in entries
        if str(entry.get("status")) in TERMINAL_PROTO_REDUCTION_STATUSES
    ]
    if not terminal:
        return None
    return dict(
        sorted(
            terminal,
            key=lambda entry: (
                int(entry.get("removed_constraint_count", 10**9)),
                float(entry.get("wall_time", 10**9)),
                str(entry.get("variant")),
            ),
        )[0]
    )


def _unknown_diagnostics(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    unknowns = [entry for entry in entries if str(entry.get("status")) == "UNKNOWN"]
    zero_branch = [
        entry
        for entry in unknowns
        if _number_or_zero(entry.get("branches")) == 0
        and _number_or_zero(entry.get("conflicts")) == 0
    ]
    progress = [entry for entry in unknowns if entry not in zero_branch]
    return {
        "unknown_count": int(len(unknowns)),
        "zero_branch_unknown_count": int(len(zero_branch)),
        "search_progress_unknown_count": int(len(progress)),
        "zero_branch_unknown_by_variant": _count_entries_by_key(zero_branch, "variant"),
        "search_progress_unknown_samples": [
            {
                "variant": entry.get("variant"),
                "branches": entry.get("branches"),
                "conflicts": entry.get("conflicts"),
                "wall_time": entry.get("wall_time"),
            }
            for entry in progress[:8]
        ],
    }


def _unlocking_variants(entries: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for entry in entries:
        status = str(entry.get("status"))
        if status not in UNLOCKING_PROTO_REDUCTION_STATUSES:
            continue
        result.append(
            {
                "variant": str(entry.get("variant")),
                "status": status,
                "removed_constraint_count": int(entry.get("removed_constraint_count", 0)),
                "wall_time": entry.get("wall_time"),
                "branches": entry.get("branches"),
                "conflicts": entry.get("conflicts"),
            }
        )
    return sorted(
        result,
        key=lambda item: (
            int(item.get("removed_constraint_count", 10**9)),
            str(item.get("variant")),
        ),
    )


def _count_entries_by_key(
    entries: Sequence[Mapping[str, Any]],
    key_name: str,
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        key = str(entry.get(key_name))
        counts[key] = int(counts.get(key, 0)) + 1
    return counts


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
            "anchor_samples_present",
            "pass" if selected_anchor_count > 0 else "fail",
            f"selected_anchor_count={int(selected_anchor_count)}",
        ),
        _check(
            "proto_reduction_evaluated",
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


def _number_or_zero(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
