from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from ortools.sat.python import cp_model

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b.forced_anchor.master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
    _candidate_ghost_rect,
    _check,
    _display_path,
    _file_hash,
    _load_json_mapping,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
)
from src.search.phase3b.forced_anchor.model_slice import (
    _apply_solver_parameter_profile,
    _build_exact_overlay,
    _clone_model_proto,
    _first_line,
    _power_family_shell_pair_table_payload,
    _response_stats_payload,
)

FAMILY_LOOKUP_MEDIUM_REPRO_SOURCE = "phase3b_family_lookup_medium_repro_v1"

DEFAULT_MEDIUM_REPRO_VARIANTS = (
    "coverage_elements_only",
    "family_table_only",
    "coverage_elements_family_table",
    "coverage_elements_family_table_active_domain",
    "coverage_elements_family_table_membership",
    "coverage_elements_family_full",
)

_GEOMETRY_ATOMS = (
    "coverage_geometry_x_min",
    "coverage_geometry_x_max",
    "coverage_geometry_y_min",
    "coverage_geometry_y_max",
)

_GEOMETRY_DELTA_ATOMS = (
    "coverage_geometry_x_delta",
    "coverage_geometry_y_delta",
)

_VARIANT_COMPONENTS = {
    "coverage_elements_only": {
        "coverage_elements",
        "coverage_active_requirement",
    },
    "family_table_only": {
        "family_table",
    },
    "family_table_active_domain": {
        "family_table",
        "active_domain",
    },
    "family_table_membership": {
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_elements_active_domain": {
        "coverage_elements",
        "coverage_active_requirement",
        "active_domain",
    },
    "coverage_literals_family_table": {
        "coverage_literal_replacement",
        "family_table",
    },
    "coverage_literals_family_table_active_domain": {
        "coverage_literal_replacement",
        "family_table",
        "active_domain",
    },
    "coverage_literals_family_table_geometry": {
        "coverage_literal_replacement",
        "coverage_geometry",
        "family_table",
    },
    "coverage_literals_family_table_geometry_x": {
        "coverage_literal_replacement",
        "coverage_geometry_x",
        "family_table",
    },
    "coverage_literals_family_table_geometry_y": {
        "coverage_literal_replacement",
        "coverage_geometry_y",
        "family_table",
    },
    "coverage_literals_family_table_geometry_x_min": {
        "coverage_literal_replacement",
        "coverage_geometry_x_min",
        "family_table",
    },
    "coverage_literals_family_table_geometry_x_max": {
        "coverage_literal_replacement",
        "coverage_geometry_x_max",
        "family_table",
    },
    "coverage_literals_family_table_geometry_y_min": {
        "coverage_literal_replacement",
        "coverage_geometry_y_min",
        "family_table",
    },
    "coverage_literals_family_table_geometry_y_max": {
        "coverage_literal_replacement",
        "coverage_geometry_y_max",
        "family_table",
    },
    "coverage_literals_family_table_geometry_x_delta": {
        "coverage_literal_replacement",
        "coverage_geometry_x_delta",
        "family_table",
    },
    "coverage_literals_family_table_geometry_y_delta": {
        "coverage_literal_replacement",
        "coverage_geometry_y_delta",
        "family_table",
    },
    "coverage_literals_family_table_geometry_delta": {
        "coverage_literal_replacement",
        "coverage_geometry_x_delta",
        "coverage_geometry_y_delta",
        "family_table",
    },
    "coverage_literals_family_table_membership": {
        "coverage_literal_replacement",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_literals_family_full": {
        "coverage_literal_replacement",
        "coverage_geometry",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
        "ordering",
        "distance_order",
    },
    "coverage_literals_family_table_membership_geometry_x": {
        "coverage_literal_replacement",
        "coverage_geometry_x",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_literals_family_table_membership_geometry_y": {
        "coverage_literal_replacement",
        "coverage_geometry_y",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_literals_family_table_membership_geometry_x_min": {
        "coverage_literal_replacement",
        "coverage_geometry_x_min",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_literals_family_table_membership_geometry_x_max": {
        "coverage_literal_replacement",
        "coverage_geometry_x_max",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_literals_family_table_membership_geometry_y_min": {
        "coverage_literal_replacement",
        "coverage_geometry_y_min",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_literals_family_table_membership_geometry_y_max": {
        "coverage_literal_replacement",
        "coverage_geometry_y_max",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_literals_family_table_membership_geometry": {
        "coverage_literal_replacement",
        "coverage_geometry",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_pruned_literals_family_table_geometry": {
        "coverage_literal_pruned_replacement",
        "coverage_geometry",
        "family_table",
    },
    "coverage_pruned_literals_family_table_membership_geometry": {
        "coverage_literal_pruned_replacement",
        "coverage_geometry",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_pruned_literals_family_full": {
        "coverage_literal_pruned_replacement",
        "coverage_geometry",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
        "ordering",
        "distance_order",
    },
    "coverage_selected_coord_literals_family_table_geometry": {
        "coverage_literal_selected_coord_replacement",
        "coverage_geometry",
        "family_table",
    },
    "coverage_selected_coord_literals_family_table_membership_geometry": {
        "coverage_literal_selected_coord_replacement",
        "coverage_geometry",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_selected_coord_literals_family_full": {
        "coverage_literal_selected_coord_replacement",
        "coverage_geometry",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
        "ordering",
        "distance_order",
    },
    "coverage_elements_family_table": {
        "coverage_elements",
        "coverage_active_requirement",
        "family_table",
    },
    "coverage_elements_family_table_active_domain": {
        "coverage_elements",
        "coverage_active_requirement",
        "family_table",
        "active_domain",
    },
    "coverage_elements_family_table_membership": {
        "coverage_elements",
        "coverage_active_requirement",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_elements_family_table_membership_geometry_delta": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_x_delta",
        "coverage_geometry_y_delta",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_elements_family_full": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
        "ordering",
        "distance_order",
    },
    "coverage_elements_family_full_delta": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_x_delta",
        "coverage_geometry_y_delta",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
        "ordering",
        "distance_order",
    },
    "coverage_elements_family_table_distance_order": {
        "coverage_elements",
        "coverage_active_requirement",
        "family_table",
        "distance_order",
    },
    "coverage_elements_family_table_ordering": {
        "coverage_elements",
        "coverage_active_requirement",
        "family_table",
        "ordering",
    },
    "coverage_elements_family_table_geometry": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry",
        "family_table",
    },
    "coverage_elements_family_table_geometry_x": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_x",
        "family_table",
    },
    "coverage_elements_family_table_geometry_y": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_y",
        "family_table",
    },
    "coverage_elements_family_table_geometry_x_min": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_x_min",
        "family_table",
    },
    "coverage_elements_family_table_geometry_x_max": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_x_max",
        "family_table",
    },
    "coverage_elements_family_table_geometry_y_min": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_y_min",
        "family_table",
    },
    "coverage_elements_family_table_geometry_y_max": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_y_max",
        "family_table",
    },
    "coverage_elements_family_table_geometry_x_delta": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_x_delta",
        "family_table",
    },
    "coverage_elements_family_table_geometry_y_delta": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_y_delta",
        "family_table",
    },
    "coverage_elements_family_table_geometry_delta": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_x_delta",
        "coverage_geometry_y_delta",
        "family_table",
    },
    "coverage_elements_family_table_geometry_x_min_y_min": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_x_min",
        "coverage_geometry_y_min",
        "family_table",
    },
    "coverage_elements_family_table_geometry_x_min_y_max": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_x_min",
        "coverage_geometry_y_max",
        "family_table",
    },
    "coverage_elements_family_table_geometry_x_max_y_min": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_x_max",
        "coverage_geometry_y_min",
        "family_table",
    },
    "coverage_elements_family_table_geometry_x_max_y_max": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry_x_max",
        "coverage_geometry_y_max",
        "family_table",
    },
    "coverage_elements_family_table_active_domain_distance_order": {
        "coverage_elements",
        "coverage_active_requirement",
        "family_table",
        "active_domain",
        "distance_order",
    },
    "coverage_elements_family_table_active_domain_ordering": {
        "coverage_elements",
        "coverage_active_requirement",
        "family_table",
        "active_domain",
        "ordering",
    },
    "coverage_elements_family_table_active_domain_geometry": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry",
        "family_table",
        "active_domain",
    },
    "coverage_elements_family_table_membership_distance_order": {
        "coverage_elements",
        "coverage_active_requirement",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
        "distance_order",
    },
    "coverage_elements_family_table_membership_ordering": {
        "coverage_elements",
        "coverage_active_requirement",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
        "ordering",
    },
    "coverage_elements_family_table_membership_geometry": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
    },
    "coverage_elements_family_table_membership_geometry_ordering": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
        "ordering",
    },
    "coverage_elements_family_table_membership_geometry_distance_order": {
        "coverage_elements",
        "coverage_active_requirement",
        "coverage_geometry",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
        "distance_order",
    },
    "coverage_elements_family_table_membership_ordering_distance_order": {
        "coverage_elements",
        "coverage_active_requirement",
        "family_table",
        "active_domain",
        "membership_reification",
        "membership_sum",
        "ordering",
        "distance_order",
    },
}


def build_phase3b_family_lookup_medium_repro(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 1,
    anchor_indices: Optional[Sequence[int]] = None,
    time_limit_seconds: float = 20.0,
    worker_count: int = 1,
    variants: Optional[Sequence[str]] = None,
    slot_limit: int = 763,
    powered_slot_limit: int = 763,
    powered_template_filter: Optional[str] = None,
    family_limit_per_slot: int = 9999,
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
    normalized_variants = _normalize_variants(variants or DEFAULT_MEDIUM_REPRO_VARIANTS)
    entries: list[Dict[str, Any]] = []
    extraction: Dict[str, Any] = {}
    model_error: Optional[str] = None
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Family lookup medium repro has not run.",
    }
    timing: Dict[str, float] = {}
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before medium repro extraction.",
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
            ghost_rect = _candidate_ghost_rect(candidate_key, record)
            model, base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=str(master_search_profile),
            )
            base_proto = _clone_model_proto(base_proto)
            extraction = _medium_repro_extraction(
                model,
                base_proto,
                slot_limit=max(1, int(slot_limit)),
                powered_slot_limit=max(1, int(powered_slot_limit)),
                powered_template_filter=powered_template_filter,
                family_limit_per_slot=max(1, int(family_limit_per_slot)),
            )
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            solve_started = time.perf_counter()
            for anchor_idx in selected_anchor_indices:
                for variant in normalized_variants:
                    entries.append(
                        _solve_medium_repro_variant(
                            extraction,
                            anchor_idx=int(anchor_idx),
                            variant=str(variant),
                            time_limit_seconds=float(time_limit_seconds),
                            worker_count=int(worker_count),
                            solver_parameter_profile=solver_parameter_profile,
                        )
                    )
            timing["repro_solve_seconds"] = float(time.perf_counter() - solve_started)
            status.update(_status_from_entries(entries))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Family lookup medium repro failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    return {
        "metadata": {
            "source": FAMILY_LOOKUP_MEDIUM_REPRO_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "medium_standalone_repro_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
        },
        "candidate": {
            "key": candidate_key,
            "campaign_status": record.get("status") if record else None,
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "sample_limit": int(sample_limit),
            "selected_anchor_indices": [int(idx) for idx in selected_anchor_indices],
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "variants": list(normalized_variants),
            "slot_limit": int(slot_limit),
            "powered_slot_limit": int(powered_slot_limit),
            "powered_template_filter": (
                str(powered_template_filter) if powered_template_filter else None
            ),
            "family_limit_per_slot": int(family_limit_per_slot),
        },
        "extraction": extraction,
        "status": status,
        "repro": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "status_counts_by_variant": _status_counts_by_key(entries, "variant"),
            "best_terminal_entry": _best_terminal_entry(entries),
            "unknown_diagnostics": _unknown_diagnostics(entries),
        },
        "timing": timing,
        "model_error": model_error,
        "campaign_state_unchanged": bool(before_hash == after_hash),
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            extraction=extraction,
            status=status,
            campaign_state_unchanged=before_hash == after_hash,
            model_error=model_error,
        ),
    }


def render_phase3b_family_lookup_medium_repro_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    repro = _mapping(report.get("repro"))
    unknowns = _mapping(repro.get("unknown_diagnostics"))
    extraction = _mapping(report.get("extraction"))
    lines = [
        "# Phase 3B Family Lookup Medium Repro",
        "",
        f"- Candidate: {_mapping(report.get('candidate')).get('key')}",
        "- Diagnostic semantics: medium_standalone_repro_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Selected pole slots: {extraction.get('selected_slot_count', 0)}",
        f"- Selected powered slots: {extraction.get('selected_powered_slot_count', 0)}",
        f"- Powered template filter: {extraction.get('powered_template_filter')}",
        f"- Selected powered template counts: {extraction.get('selected_powered_template_counts', {})}",
        f"- Selected family ids: {extraction.get('selected_family_ids', [])}",
        f"- Status counts: {repro.get('status_counts', {})}",
        f"- Zero-branch UNKNOWN entries: {unknowns.get('zero_branch_unknown_count', 0)}",
        "",
        "## Medium Matrix",
        "",
        "| Variant | Status | Variables | Constraints | Elements | Cover Literals | Kept Pairs | Tables | Wall | Branches | Conflicts | Deterministic |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(repro.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("variant")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("medium_variable_count")),
                    _markdown_cell(entry.get("medium_constraint_count")),
                    _markdown_cell(entry.get("element_constraint_count")),
                    _markdown_cell(entry.get("cover_literal_count")),
                    _markdown_cell(entry.get("pruned_cover_candidate_pair_count")),
                    _markdown_cell(entry.get("family_table_constraint_count")),
                    _markdown_cell(entry.get("wall_time")),
                    _markdown_cell(entry.get("branches")),
                    _markdown_cell(entry.get("conflicts")),
                    _markdown_cell(entry.get("deterministic_time")),
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


def render_phase3b_family_lookup_medium_repro_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    repro = _mapping(report.get("repro"))
    unknowns = _mapping(repro.get("unknown_diagnostics"))
    extraction = _mapping(report.get("extraction"))
    lines = [
        "Phase 3B family lookup medium repro",
        f"candidate={_mapping(report.get('candidate')).get('key')}",
        "diagnostic_semantics=medium_standalone_repro_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"selected_slot_count={extraction.get('selected_slot_count', 0)}",
        f"selected_powered_slot_count={extraction.get('selected_powered_slot_count', 0)}",
        f"powered_template_filter={extraction.get('powered_template_filter')}",
        f"selected_powered_template_counts={extraction.get('selected_powered_template_counts', {})}",
        f"selected_family_ids={extraction.get('selected_family_ids', [])}",
        f"status_counts={repro.get('status_counts', {})}",
        f"zero_branch_unknown_count={unknowns.get('zero_branch_unknown_count', 0)}",
    ]
    for entry in list(repro.get("entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "entry "
                f"variant={entry.get('variant')} "
                f"status={entry.get('status')} "
                f"vars={entry.get('medium_variable_count')} "
                f"constraints={entry.get('medium_constraint_count')} "
                f"elements={entry.get('element_constraint_count')} "
                f"cover_literals={entry.get('cover_literal_count')} "
                f"candidate_pairs={entry.get('cover_candidate_pair_count')} "
                f"kept_pairs={entry.get('pruned_cover_candidate_pair_count')} "
                f"selected_coord_channels={entry.get('selected_coord_channel_constraint_count')} "
                f"tables={entry.get('family_table_constraint_count')} "
                f"wall={entry.get('wall_time')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')} "
                f"deterministic={entry.get('deterministic_time')}"
            )
    return "\n".join(lines) + "\n"


def _medium_repro_extraction(
    model: Any,
    base_proto: Any,
    *,
    slot_limit: int,
    powered_slot_limit: int,
    powered_template_filter: Optional[str],
    family_limit_per_slot: int,
) -> Dict[str, Any]:
    delegate = getattr(model, "_coordinate_delegate", None)
    if delegate is None:
        raise ValueError("coordinate delegate missing from exact overlay")
    shell_payload = _power_family_shell_pair_table_payload(model, base_proto)
    rows_by_family_id = {
        str(family_id): [
            [int(row[0]), int(row[1])]
            for row in list(rows)
            if isinstance(row, (list, tuple)) and len(row) == 2
        ]
        for family_id, rows in _mapping(shell_payload.get("rows_by_family_id")).items()
    }
    var_domains = _proto_var_domains(base_proto)
    pole_slots_by_key = {
        str(getattr(slot, "key", "")): slot
        for slot in list(getattr(delegate, "residual_optional_slots", {}).get("power_pole", []))
    }
    selected_slots: list[Dict[str, Any]] = []
    selected_family_ids: set[int] = set()
    for raw_slot in list(shell_payload.get("slots", []))[: max(0, int(slot_limit))]:
        if not isinstance(raw_slot, Mapping):
            continue
        slot_key = str(raw_slot.get("slot_key"))
        family_ids = [
            int(family_id)
            for family_id in sorted(_mapping(raw_slot.get("family_lit_indices_by_family_id")))
            if str(family_id) in rows_by_family_id
        ][: max(0, int(family_limit_per_slot))]
        if not family_ids:
            continue
        slot_obj = pole_slots_by_key.get(slot_key)
        selected_family_ids.update(family_ids)
        selected_slots.append(
            {
                "slot_key": slot_key,
                "family_ids": family_ids,
                "active_domain": _domain_for_index(var_domains, raw_slot.get("active_var_index"), [0, 1]),
                "family_domain": _domain_for_index(var_domains, raw_slot.get("family_var_index"), [0, max(family_ids) + 1]),
                "d_lo_domain": _domain_for_index(var_domains, raw_slot.get("d_lo_var_index"), [0, 0]),
                "d_hi_domain": _domain_for_index(var_domains, raw_slot.get("d_hi_var_index"), [0, 0]),
                "x_domain": _domain_for_slot_var(var_domains, slot_obj, "x", [0, max(0, int(getattr(delegate, "grid_w", 1)) - 1)]),
                "y_domain": _domain_for_slot_var(var_domains, slot_obj, "y", [0, max(0, int(getattr(delegate, "grid_h", 1)) - 1)]),
            }
        )
    all_powered_slots = _all_powered_slots(delegate)
    available_powered_template_counts = _slot_template_counts(all_powered_slots)
    powered_slots = _extract_powered_slots(
        delegate,
        var_domains=var_domains,
        limit=max(0, int(powered_slot_limit)),
        template_filter=powered_template_filter,
    )
    selected_powered_template_counts = _powered_slot_template_counts(powered_slots)
    selected_rows_by_family_id = {
        str(family_id): rows_by_family_id.get(str(family_id), [])
        for family_id in sorted(selected_family_ids)
    }
    shell_values = [
        int(value)
        for rows in selected_rows_by_family_id.values()
        for row in rows
        for value in row
    ]
    return {
        "selected_slot_count": int(len(selected_slots)),
        "selected_slots": selected_slots,
        "available_powered_slot_count": int(len(all_powered_slots)),
        "available_powered_template_counts": available_powered_template_counts,
        "powered_template_filter": (
            str(powered_template_filter) if powered_template_filter else None
        ),
        "selected_powered_slot_count": int(len(powered_slots)),
        "selected_powered_slots": powered_slots,
        "selected_powered_template_counts": selected_powered_template_counts,
        "scale_checks": {
            "requested_power_pole_slot_limit": int(slot_limit),
            "requested_powered_slot_limit": int(powered_slot_limit),
            "selected_power_pole_slots_match_763": bool(len(selected_slots) == 763),
            "protocol_storage_box_powered_slots_match_544": bool(
                int(selected_powered_template_counts.get("protocol_storage_box", 0)) == 544
            ),
        },
        "selected_family_ids": [int(family_id) for family_id in sorted(selected_family_ids)],
        "selected_family_count": int(len(selected_family_ids)),
        "selected_rows_by_family_id": selected_rows_by_family_id,
        "selected_row_count": int(sum(len(rows) for rows in selected_rows_by_family_id.values())),
        "shell_value_min": int(min(shell_values)) if shell_values else 0,
        "shell_value_max": int(max(shell_values)) if shell_values else 0,
        "grid_width": int(getattr(delegate, "grid_w", 0)),
        "grid_height": int(getattr(delegate, "grid_h", 0)),
        "power_coverage_radius": int(_call_or_default(delegate, "_power_coverage_radius", 0)),
    }


def _solve_medium_repro_variant(
    extraction: Mapping[str, Any],
    *,
    anchor_idx: int,
    variant: str,
    time_limit_seconds: float,
    worker_count: int,
    solver_parameter_profile: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    components = set(_VARIANT_COMPONENTS[str(variant)])
    model = cp_model.CpModel()
    selected_slots = [
        dict(slot)
        for slot in list(extraction.get("selected_slots", []))
        if isinstance(slot, Mapping)
    ]
    powered_slots = [
        dict(slot)
        for slot in list(extraction.get("selected_powered_slots", []))
        if isinstance(slot, Mapping)
    ]
    selected_family_ids = [int(value) for value in list(extraction.get("selected_family_ids", []))]
    rows_by_family_id = {
        str(family_id): [
            [int(row[0]), int(row[1])]
            for row in list(rows)
            if isinstance(row, (list, tuple)) and len(row) == 2
        ]
        for family_id, rows in _mapping(extraction.get("selected_rows_by_family_id")).items()
    }
    table_rows = _family_table_rows(selected_family_ids, rows_by_family_id)
    max_family_id = max(selected_family_ids) if selected_family_ids else 0
    sentinel_family_id = max_family_id + 1
    pole_active_vars = []
    pole_x_vars = []
    pole_y_vars = []
    pole_family_vars = []
    pole_d_lo_vars = []
    pole_d_hi_vars = []
    previous_family_var = None
    family_table_constraint_count = 0
    membership_literal_count = 0
    for slot_index, slot in enumerate(selected_slots):
        active = model.NewBoolVar(f"active__power_pole__slot_{slot_index}")
        x = _new_int_var_from_domain(model, slot.get("x_domain"), f"x__power_pole__slot_{slot_index}")
        y = _new_int_var_from_domain(model, slot.get("y_domain"), f"y__power_pole__slot_{slot_index}")
        family = _new_int_var_from_domain(
            model,
            _domain_with_sentinel(slot.get("family_domain"), sentinel_family_id),
            f"family__power_pole__slot_{slot_index}",
        )
        d_lo = _new_int_var_from_domain(model, slot.get("d_lo_domain"), f"d_lo__power_pole__slot_{slot_index}")
        d_hi = _new_int_var_from_domain(model, slot.get("d_hi_domain"), f"d_hi__power_pole__slot_{slot_index}")
        pole_active_vars.append(active)
        pole_x_vars.append(x)
        pole_y_vars.append(y)
        pole_family_vars.append(family)
        pole_d_lo_vars.append(d_lo)
        pole_d_hi_vars.append(d_hi)
        if "distance_order" in components:
            model.Add(d_lo <= d_hi)
        if "family_table" in components and table_rows:
            model.AddAllowedAssignments([d_lo, d_hi, family], table_rows)
            family_table_constraint_count += 1
        if "active_domain" in components:
            model.Add(family <= sentinel_family_id - 1).OnlyEnforceIf(active)
            model.Add(family == sentinel_family_id).OnlyEnforceIf(active.Not())
        lit_vars = []
        if "membership_reification" in components or "membership_sum" in components:
            for family_id in selected_family_ids:
                lit = model.NewBoolVar(
                    f"is_family__power_pole__slot_{slot_index}__family_{family_id:03d}"
                )
                lit_vars.append(lit)
                membership_literal_count += 1
                if "membership_reification" in components:
                    model.Add(family == int(family_id)).OnlyEnforceIf(lit)
                    model.Add(family != int(family_id)).OnlyEnforceIf(lit.Not())
        if "membership_sum" in components and lit_vars:
            model.Add(sum(lit_vars) == active)
        if previous_family_var is not None and "ordering" in components:
            model.Add(previous_family_var <= family)
        previous_family_var = family
    element_constraint_count = 0
    cover_literal_count = 0
    cover_candidate_pair_count = 0
    pruned_cover_candidate_pair_count = 0
    powered_without_cover_candidate_count = 0
    selected_coord_channel_constraint_count = 0
    coverage_linear_constraint_count = 0
    if "coverage_elements" in components and pole_active_vars:
        for powered_index, powered in enumerate(powered_slots):
            cover_idx = model.NewIntVar(
                0,
                len(pole_active_vars) - 1,
                f"cover_choice_idx__powered_{powered_index}",
            )
            cover_active = model.NewBoolVar(f"cover_choice_active__powered_{powered_index}")
            cover_x = _new_int_var_from_domain(
                model,
                [0, max(0, int(extraction.get("grid_width", 1)) - 1)],
                f"cover_choice_x__powered_{powered_index}",
            )
            cover_y = _new_int_var_from_domain(
                model,
                [0, max(0, int(extraction.get("grid_height", 1)) - 1)],
                f"cover_choice_y__powered_{powered_index}",
            )
            model.AddElement(cover_idx, pole_active_vars, cover_active)
            model.AddElement(cover_idx, pole_x_vars, cover_x)
            model.AddElement(cover_idx, pole_y_vars, cover_y)
            element_constraint_count += 3
            if "coverage_active_requirement" in components:
                model.Add(cover_active == 1)
                coverage_linear_constraint_count += 1
            if _has_coverage_geometry(components):
                powered_x = _new_int_var_from_domain(
                    model,
                    powered.get("x_domain"),
                    f"powered_x__{powered_index}",
                )
                powered_y = _new_int_var_from_domain(
                    model,
                    powered.get("y_domain"),
                    f"powered_y__{powered_index}",
                )
                coverage_linear_constraint_count += _add_coverage_geometry_constraints(
                    model,
                    powered_x=powered_x,
                    powered_y=powered_y,
                    cover_x=cover_x,
                    cover_y=cover_y,
                    dims=powered.get("dims", [1, 1]),
                    radius=int(extraction.get("power_coverage_radius", 0)),
                    components=components,
                    name_prefix=f"element__powered_{powered_index}",
                )
    if (
        (
            "coverage_literal_replacement" in components
            or "coverage_literal_pruned_replacement" in components
            or "coverage_literal_selected_coord_replacement" in components
        )
        and pole_active_vars
    ):
        for powered_index, powered in enumerate(powered_slots):
            pole_indices = list(range(len(pole_active_vars)))
            cover_candidate_pair_count += int(len(pole_indices))
            if "coverage_literal_pruned_replacement" in components and _has_coverage_geometry(components):
                radius = int(extraction.get("power_coverage_radius", 0))
                pole_indices = [
                    int(pole_index)
                    for pole_index in pole_indices
                    if _cover_pair_domain_feasible(
                        powered,
                        selected_slots[int(pole_index)],
                        radius=radius,
                    )
                ]
            pruned_cover_candidate_pair_count += int(len(pole_indices))
            if not pole_indices:
                powered_without_cover_candidate_count += 1
                model.Add(0 >= 1)
                continue
            use_selected_coord = (
                "coverage_literal_selected_coord_replacement" in components
                and _has_coverage_geometry(components)
            )
            cover_lits = [
                model.NewBoolVar(f"cover_lit__powered_{powered_index}__pole_{pole_index}")
                for pole_index in pole_indices
            ]
            cover_literal_count += int(len(cover_lits))
            model.Add(sum(cover_lits) == 1)
            coverage_linear_constraint_count += 1
            powered_x = None
            powered_y = None
            cover_x = None
            cover_y = None
            if _has_coverage_geometry(components):
                powered_x = _new_int_var_from_domain(
                    model,
                    powered.get("x_domain"),
                    f"powered_x__{powered_index}",
                )
                powered_y = _new_int_var_from_domain(
                    model,
                    powered.get("y_domain"),
                    f"powered_y__{powered_index}",
                )
                if use_selected_coord:
                    cover_x = _new_int_var_from_domain(
                        model,
                        [0, max(0, int(extraction.get("grid_width", 1)) - 1)],
                        f"selected_cover_x__powered_{powered_index}",
                    )
                    cover_y = _new_int_var_from_domain(
                        model,
                        [0, max(0, int(extraction.get("grid_height", 1)) - 1)],
                        f"selected_cover_y__powered_{powered_index}",
                    )
            for pole_index, lit in zip(pole_indices, cover_lits):
                model.Add(pole_active_vars[pole_index] == 1).OnlyEnforceIf(lit)
                coverage_linear_constraint_count += 1
                if (
                    use_selected_coord
                    and cover_x is not None
                    and cover_y is not None
                ):
                    model.Add(cover_x == pole_x_vars[pole_index]).OnlyEnforceIf(lit)
                    model.Add(cover_y == pole_y_vars[pole_index]).OnlyEnforceIf(lit)
                    selected_coord_channel_constraint_count += 2
                    coverage_linear_constraint_count += 2
                elif _has_coverage_geometry(components) and powered_x is not None and powered_y is not None:
                    pole_x = pole_x_vars[pole_index]
                    pole_y = pole_y_vars[pole_index]
                    coverage_linear_constraint_count += _add_coverage_geometry_constraints(
                        model,
                        powered_x=powered_x,
                        powered_y=powered_y,
                        cover_x=pole_x,
                        cover_y=pole_y,
                        dims=powered.get("dims", [1, 1]),
                        radius=int(extraction.get("power_coverage_radius", 0)),
                        components=components,
                        enforcement_literal=lit,
                        name_prefix=f"literal__powered_{powered_index}__pole_{pole_index}",
                    )
            if (
                use_selected_coord
                and powered_x is not None
                and powered_y is not None
                and cover_x is not None
                and cover_y is not None
            ):
                coverage_linear_constraint_count += _add_coverage_geometry_constraints(
                    model,
                    powered_x=powered_x,
                    powered_y=powered_y,
                    cover_x=cover_x,
                    cover_y=cover_y,
                    dims=powered.get("dims", [1, 1]),
                    radius=int(extraction.get("power_coverage_radius", 0)),
                    components=components,
                    name_prefix=f"selected_coord__powered_{powered_index}",
                )
    if not selected_slots:
        model.Add(0 >= 1)
    solver = cp_model.CpSolver()
    applied_profile = _apply_solver_parameter_profile(
        solver,
        time_limit_seconds=float(time_limit_seconds),
        default_worker_count=int(worker_count),
        profile=solver_parameter_profile,
    )
    started = time.perf_counter()
    status = solver.Solve(model)
    elapsed = float(time.perf_counter() - started)
    response_stats = solver.ResponseStats()
    proto = model.Proto()
    parsed_stats = _response_stats_payload(response_stats)
    return {
        "anchor_idx": int(anchor_idx),
        "variant": str(variant),
        "components": sorted(components),
        "evaluated": True,
        "status": solver.StatusName(status),
        "elapsed_seconds": float(elapsed),
        "wall_time": float(solver.WallTime()),
        "user_time": float(solver.UserTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "medium_variable_count": int(len(getattr(proto, "variables", []))),
        "medium_constraint_count": int(len(getattr(proto, "constraints", []))),
        "element_constraint_count": int(element_constraint_count),
        "cover_literal_count": int(cover_literal_count),
        "cover_candidate_pair_count": int(cover_candidate_pair_count),
        "pruned_cover_candidate_pair_count": int(pruned_cover_candidate_pair_count),
        "powered_without_cover_candidate_count": int(powered_without_cover_candidate_count),
        "selected_coord_channel_constraint_count": int(selected_coord_channel_constraint_count),
        "family_table_constraint_count": int(family_table_constraint_count),
        "membership_literal_count": int(membership_literal_count),
        "coverage_linear_constraint_count": int(coverage_linear_constraint_count),
        "solver_parameter_profile": applied_profile,
        "response_summary": _first_line(response_stats),
        "response_stats": str(response_stats),
        "response_stats_parsed": parsed_stats,
        "deterministic_time": parsed_stats.get("deterministic_time", 0),
    }


def _extract_powered_slots(
    delegate: Any,
    *,
    var_domains: Mapping[int, Sequence[int]],
    limit: int,
    template_filter: Optional[str] = None,
) -> list[Dict[str, Any]]:
    powered = _all_powered_slots(delegate)
    if template_filter:
        powered = [
            slot
            for slot in powered
            if str(getattr(slot, "template", "")) == str(template_filter)
        ]
    result: list[Dict[str, Any]] = []
    for slot in powered[: max(0, int(limit))]:
        result.append(
            {
                "slot_key": str(getattr(slot, "key", "")),
                "template": str(getattr(slot, "template", "")),
                "dims": [int(value) for value in list(getattr(slot, "dims", (1, 1)))],
                "x_domain": _domain_for_slot_var(var_domains, slot, "x", [0, max(0, int(getattr(delegate, "grid_w", 1)) - 1)]),
                "y_domain": _domain_for_slot_var(var_domains, slot, "y", [0, max(0, int(getattr(delegate, "grid_h", 1)) - 1)]),
            }
        )
    return result


def _all_powered_slots(delegate: Any) -> list[Any]:
    getter = getattr(delegate, "_all_powered_slots", None)
    return list(getter()) if callable(getter) else []


def _slot_template_counts(slots: Sequence[Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for slot in list(slots):
        template = str(getattr(slot, "template", ""))
        counts[template] = int(counts.get(template, 0)) + 1
    return dict(sorted(counts.items()))


def _powered_slot_template_counts(slots: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for slot in list(slots):
        if not isinstance(slot, Mapping):
            continue
        template = str(slot.get("template", ""))
        counts[template] = int(counts.get(template, 0)) + 1
    return dict(sorted(counts.items()))


def _has_coverage_geometry(components: set[str]) -> bool:
    return bool(_coverage_geometry_atoms(components))


def _coverage_geometry_atoms(components: set[str]) -> set[str]:
    atoms: set[str] = set()
    if "coverage_geometry" in components:
        atoms.update(_GEOMETRY_ATOMS)
    if "coverage_geometry_x" in components:
        atoms.update({"coverage_geometry_x_min", "coverage_geometry_x_max"})
    if "coverage_geometry_y" in components:
        atoms.update({"coverage_geometry_y_min", "coverage_geometry_y_max"})
    for atom in _GEOMETRY_ATOMS:
        if atom in components:
            atoms.add(atom)
    for atom in _GEOMETRY_DELTA_ATOMS:
        if atom in components:
            atoms.add(atom)
    return atoms


def _add_coverage_geometry_constraints(
    model: cp_model.CpModel,
    *,
    powered_x: Any,
    powered_y: Any,
    cover_x: Any,
    cover_y: Any,
    dims: Any,
    radius: int,
    components: set[str],
    enforcement_literal: Any = None,
    name_prefix: str = "coverage",
) -> int:
    atoms = _coverage_geometry_atoms(components)
    dims_list = [int(value) for value in list(dims or [1, 1])]
    width = int(dims_list[0]) if dims_list else 1
    height = int(dims_list[1]) if len(dims_list) > 1 else 1
    added = 0

    def add_constraint(constraint: Any) -> None:
        nonlocal added
        if enforcement_literal is not None:
            constraint.OnlyEnforceIf(enforcement_literal)
        added += 1

    if "coverage_geometry_x_max" in atoms:
        add_constraint(model.Add(powered_x <= cover_x + 2 + int(radius) - 1))
    if "coverage_geometry_x_min" in atoms:
        add_constraint(model.Add(cover_x - int(radius) <= powered_x + width - 1))
    if "coverage_geometry_x_delta" in atoms:
        add_constraint(
            _add_axis_delta_constraint(
                model,
                powered_coord=powered_x,
                cover_coord=cover_x,
                span=width,
                radius=int(radius),
                name=f"{name_prefix}__delta_x",
            )
        )
    if "coverage_geometry_y_max" in atoms:
        add_constraint(model.Add(powered_y <= cover_y + 2 + int(radius) - 1))
    if "coverage_geometry_y_min" in atoms:
        add_constraint(model.Add(cover_y - int(radius) <= powered_y + height - 1))
    if "coverage_geometry_y_delta" in atoms:
        add_constraint(
            _add_axis_delta_constraint(
                model,
                powered_coord=powered_y,
                cover_coord=cover_y,
                span=height,
                radius=int(radius),
                name=f"{name_prefix}__delta_y",
            )
        )
    return int(added)


def _add_axis_delta_constraint(
    model: cp_model.CpModel,
    *,
    powered_coord: Any,
    cover_coord: Any,
    span: int,
    radius: int,
    name: str,
) -> Any:
    lower = 1 - int(span) - int(radius)
    upper = int(radius) + 1
    delta = model.NewIntVar(int(lower), int(upper), str(name))
    return model.Add(delta == powered_coord - cover_coord)


def _cover_pair_domain_feasible(
    powered_slot: Mapping[str, Any],
    pole_slot: Mapping[str, Any],
    *,
    radius: int,
) -> bool:
    dims = [int(value) for value in list(powered_slot.get("dims", [1, 1]))]
    width = int(dims[0]) if dims else 1
    height = int(dims[1]) if len(dims) > 1 else 1
    return _axis_cover_domain_feasible(
        powered_slot.get("x_domain", [0, 0]),
        pole_slot.get("x_domain", [0, 0]),
        radius=int(radius),
        span=int(width),
    ) and _axis_cover_domain_feasible(
        powered_slot.get("y_domain", [0, 0]),
        pole_slot.get("y_domain", [0, 0]),
        radius=int(radius),
        span=int(height),
    )


def _axis_cover_domain_feasible(
    powered_domain: Any,
    pole_domain: Any,
    *,
    radius: int,
    span: int,
) -> bool:
    pole_intervals = _domain_intervals(pole_domain)
    left_slack = int(radius) + 1
    right_slack = int(radius) + max(1, int(span)) - 1
    for powered_low, powered_high in _domain_intervals(powered_domain):
        feasible_pole_low = int(powered_low) - int(left_slack)
        feasible_pole_high = int(powered_high) + int(right_slack)
        for pole_low, pole_high in pole_intervals:
            if feasible_pole_low <= int(pole_high) and int(pole_low) <= feasible_pole_high:
                return True
    return False


def _domain_intervals(domain: Any) -> list[tuple[int, int]]:
    flat = _flat_domain(domain if isinstance(domain, Sequence) and not isinstance(domain, str) else [])
    return [
        (int(flat[index]), int(flat[index + 1]))
        for index in range(0, len(flat), 2)
    ]


def _proto_var_domains(model_proto: Any) -> Dict[int, list[int]]:
    return {
        int(index): [int(value) for value in list(getattr(var, "domain", []))]
        for index, var in enumerate(list(getattr(model_proto, "variables", [])))
    }


def _domain_for_slot_var(
    var_domains: Mapping[int, Sequence[int]],
    slot: Any,
    attr_name: str,
    default_domain: Sequence[int],
) -> list[int]:
    var = getattr(slot, str(attr_name), None) if slot is not None else None
    var_index = None
    if var is not None:
        try:
            var_index = int(var.Index())
        except Exception:
            var_index = None
    return _domain_for_index(var_domains, var_index, default_domain)


def _domain_for_index(
    var_domains: Mapping[int, Sequence[int]],
    var_index: Any,
    default_domain: Sequence[int],
) -> list[int]:
    try:
        idx = int(var_index)
    except Exception:
        return _flat_domain(default_domain)
    domain = list(var_domains.get(idx, []))
    return _flat_domain(domain or default_domain)


def _flat_domain(domain: Sequence[int]) -> list[int]:
    values = [int(value) for value in list(domain)]
    if not values:
        return [0, 0]
    if len(values) % 2 == 1:
        values.append(values[-1])
    return values


def _domain_with_sentinel(domain: Any, sentinel_family_id: int) -> list[int]:
    values = _flat_domain(domain if isinstance(domain, Sequence) and not isinstance(domain, str) else [])
    if not values:
        return [0, int(sentinel_family_id)]
    values[-1] = max(int(values[-1]), int(sentinel_family_id))
    return values


def _new_int_var_from_domain(model: cp_model.CpModel, domain: Any, name: str) -> Any:
    flat = _flat_domain(domain if isinstance(domain, Sequence) and not isinstance(domain, str) else [])
    return model.NewIntVarFromDomain(cp_model.Domain.FromFlatIntervals(flat), str(name))


def _family_table_rows(
    selected_family_ids: Sequence[int],
    rows_by_family_id: Mapping[str, Sequence[Sequence[int]]],
) -> list[tuple[int, int, int]]:
    rows: list[tuple[int, int, int]] = []
    for family_id in [int(value) for value in list(selected_family_ids)]:
        for row in list(rows_by_family_id.get(str(family_id), [])):
            if not isinstance(row, (list, tuple)) or len(row) != 2:
                continue
            rows.append((int(row[0]), int(row[1]), int(family_id)))
    return rows


def _call_or_default(obj: Any, method_name: str, default: int) -> int:
    method = getattr(obj, method_name, None)
    if not callable(method):
        return int(default)
    try:
        return int(method())
    except Exception:
        return int(default)


def _normalize_variants(variants: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in variants:
        token = str(raw).strip()
        if not token or token in seen:
            continue
        if token not in _VARIANT_COMPONENTS:
            raise ValueError(f"Unsupported medium repro variant: {raw!r}")
        seen.add(token)
        result.append(token)
    return tuple(result or DEFAULT_MEDIUM_REPRO_VARIANTS)


def _status_from_entries(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    evaluated = [entry for entry in entries if bool(entry.get("evaluated", False))]
    counts = _status_counts(evaluated)
    unknowns = _unknown_diagnostics(evaluated)
    if not entries:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_medium_repro_entries",
            "status_counts": counts,
            "recommendation": "No medium repro entries were evaluated.",
        }
    if int(unknowns.get("zero_branch_unknown_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "medium_repro_zero_branch_reproduced",
            "status_counts": counts,
            "recommendation": "The medium standalone repro reproduced zero-branch UNKNOWN; inspect the smallest layer set.",
        }
    if any(str(entry.get("status")) == "UNKNOWN" for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "medium_repro_unknown_with_search_progress",
            "status_counts": counts,
            "recommendation": "The medium standalone repro is UNKNOWN but has search progress; compare deterministic time against full proto.",
        }
    if all(str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"} for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "medium_repro_terminal_without_zero_branch",
            "status_counts": counts,
            "recommendation": "The medium standalone repro solves terminally; the blocker likely needs full-proto scale or unrelated layer interactions.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "medium_repro_mixed_terminal",
        "status_counts": counts,
        "recommendation": "The medium standalone repro has mixed statuses; inspect infeasible variants.",
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
        if str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"}
    ]
    if not terminal:
        return None
    return dict(
        sorted(
            terminal,
            key=lambda entry: (
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
                "deterministic_time": entry.get("deterministic_time"),
            }
            for entry in progress[:8]
        ],
    }


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
    extraction: Mapping[str, Any],
    status: Mapping[str, Any],
    campaign_state_unchanged: bool,
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    selected_slot_count = int(extraction.get("selected_slot_count", 0))
    selected_powered_slot_count = int(extraction.get("selected_powered_slot_count", 0))
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
            "medium_repro_extraction_present",
            "pass" if selected_slot_count > 0 and selected_powered_slot_count > 0 else "fail",
            f"selected_slot_count={selected_slot_count}; selected_powered_slot_count={selected_powered_slot_count}",
        ),
        _check(
            "medium_repro_evaluated",
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
