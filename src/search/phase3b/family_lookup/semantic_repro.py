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
    _candidate_ghost_rect,
    _clone_model_proto,
    _first_line,
    _power_family_shell_pair_table_payload,
    _response_stats_payload,
)

FAMILY_LOOKUP_SEMANTIC_REPRO_SOURCE = "phase3b_family_lookup_semantic_repro_v1"

DEFAULT_SEMANTIC_REPRO_VARIANTS = (
    "coverage_only",
    "membership_only",
    "shell_pair_only",
    "ordering_only",
    "membership_shell_pair",
    "membership_ordering",
    "shell_pair_ordering",
    "full_rebuilt_semantics",
)

_VARIANT_COMPONENTS = {
    "coverage_only": set(),
    "membership_only": {"active_domain", "membership_reification", "membership_sum"},
    "shell_pair_only": {"shell_pair_table"},
    "ordering_only": {"ordering"},
    "membership_shell_pair": {
        "active_domain",
        "membership_reification",
        "membership_sum",
        "shell_pair_table",
    },
    "membership_ordering": {
        "active_domain",
        "membership_reification",
        "membership_sum",
        "ordering",
    },
    "shell_pair_ordering": {"shell_pair_table", "ordering"},
    "full_rebuilt_semantics": {
        "active_domain",
        "membership_reification",
        "membership_sum",
        "shell_pair_table",
        "ordering",
    },
}


def build_phase3b_family_lookup_semantic_repro(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 1,
    anchor_indices: Optional[Sequence[int]] = None,
    time_limit_seconds: float = 5.0,
    worker_count: int = 4,
    variants: Optional[Sequence[str]] = None,
    slot_limit: int = 3,
    family_limit_per_slot: int = 3,
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
    normalized_variants = _normalize_variants(variants or DEFAULT_SEMANTIC_REPRO_VARIANTS)
    entries: list[Dict[str, Any]] = []
    extraction: Dict[str, Any] = {}
    model_error: Optional[str] = None
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Family lookup semantic repro has not run.",
    }
    timing: Dict[str, float] = {}
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before semantic repro extraction.",
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
            payload = _power_family_shell_pair_table_payload(
                model,
                _clone_model_proto(base_proto),
            )
            extraction = _semantic_repro_extraction(
                payload,
                slot_limit=max(1, int(slot_limit)),
                family_limit_per_slot=max(1, int(family_limit_per_slot)),
            )
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            solve_started = time.perf_counter()
            for anchor_idx in selected_anchor_indices:
                for variant in normalized_variants:
                    entries.append(
                        _solve_semantic_repro_variant(
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
                    "recommendation": "Family lookup semantic repro failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    return {
        "metadata": {
            "source": FAMILY_LOOKUP_SEMANTIC_REPRO_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "micro_semantic_repro_not_proof_source",
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


def render_phase3b_family_lookup_semantic_repro_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    repro = _mapping(report.get("repro"))
    unknowns = _mapping(repro.get("unknown_diagnostics"))
    extraction = _mapping(report.get("extraction"))
    lines = [
        "# Phase 3B Family Lookup Semantic Repro",
        "",
        f"- Candidate: {_mapping(report.get('candidate')).get('key')}",
        "- Diagnostic semantics: micro_semantic_repro_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Selected slots: {extraction.get('selected_slot_count', 0)}",
        f"- Selected family ids: {extraction.get('selected_family_ids', [])}",
        f"- Status counts: {repro.get('status_counts', {})}",
        f"- Zero-branch UNKNOWN entries: {unknowns.get('zero_branch_unknown_count', 0)}",
        "",
        "## Micro Matrix",
        "",
        "| Variant | Status | Variables | Constraints | Wall | Branches | Conflicts |",
        "| --- | --- | --- | --- | --- | --- | --- |",
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
                    _markdown_cell(entry.get("micro_variable_count")),
                    _markdown_cell(entry.get("micro_constraint_count")),
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


def render_phase3b_family_lookup_semantic_repro_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    repro = _mapping(report.get("repro"))
    unknowns = _mapping(repro.get("unknown_diagnostics"))
    extraction = _mapping(report.get("extraction"))
    lines = [
        "Phase 3B family lookup semantic repro",
        f"candidate={_mapping(report.get('candidate')).get('key')}",
        "diagnostic_semantics=micro_semantic_repro_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"selected_slot_count={extraction.get('selected_slot_count', 0)}",
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
                f"vars={entry.get('micro_variable_count')} "
                f"constraints={entry.get('micro_constraint_count')} "
                f"wall={entry.get('wall_time')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')}"
            )
    return "\n".join(lines) + "\n"


def _semantic_repro_extraction(
    payload: Mapping[str, Any],
    *,
    slot_limit: int,
    family_limit_per_slot: int,
) -> Dict[str, Any]:
    rows_by_family_id = {
        str(family_id): [
            [int(row[0]), int(row[1])]
            for row in list(rows)
            if isinstance(row, (list, tuple)) and len(row) == 2
        ]
        for family_id, rows in _mapping(payload.get("rows_by_family_id")).items()
    }
    selected_slots: list[Dict[str, Any]] = []
    selected_family_ids: set[int] = set()
    for raw_slot in list(payload.get("slots", []))[: max(0, int(slot_limit))]:
        if not isinstance(raw_slot, Mapping):
            continue
        family_ids = [
            int(family_id)
            for family_id in sorted(_mapping(raw_slot.get("family_lit_indices_by_family_id")))
            if str(family_id) in rows_by_family_id
        ][: max(0, int(family_limit_per_slot))]
        if not family_ids:
            continue
        selected_family_ids.update(family_ids)
        selected_slots.append(
            {
                "slot_key": str(raw_slot.get("slot_key")),
                "family_ids": family_ids,
            }
        )
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
        "selected_family_ids": [int(family_id) for family_id in sorted(selected_family_ids)],
        "selected_family_count": int(len(selected_family_ids)),
        "selected_rows_by_family_id": selected_rows_by_family_id,
        "selected_row_count": int(sum(len(rows) for rows in selected_rows_by_family_id.values())),
        "shell_value_min": int(min(shell_values)) if shell_values else 0,
        "shell_value_max": int(max(shell_values)) if shell_values else 0,
    }


def _solve_semantic_repro_variant(
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
    selected_family_ids = [int(value) for value in list(extraction.get("selected_family_ids", []))]
    selected_slots = [
        dict(slot)
        for slot in list(extraction.get("selected_slots", []))
        if isinstance(slot, Mapping)
    ]
    rows_by_family_id = {
        str(family_id): [
            [int(row[0]), int(row[1])]
            for row in list(rows)
            if isinstance(row, (list, tuple)) and len(row) == 2
        ]
        for family_id, rows in _mapping(extraction.get("selected_rows_by_family_id")).items()
    }
    shell_min = int(extraction.get("shell_value_min", 0))
    shell_max = int(extraction.get("shell_value_max", 0))
    max_family_id = max(selected_family_ids) if selected_family_ids else 0
    sentinel_family_id = max_family_id + 1
    active_vars = []
    d_lo_vars = []
    d_hi_vars = []
    family_vars = []
    previous_family_var = None
    for slot_index, slot in enumerate(selected_slots):
        active = model.NewBoolVar(f"active__slot_{slot_index}")
        family = model.NewIntVar(0, sentinel_family_id, f"family__slot_{slot_index}")
        d_lo = model.NewIntVar(shell_min, shell_max, f"d_lo__slot_{slot_index}")
        d_hi = model.NewIntVar(shell_min, shell_max, f"d_hi__slot_{slot_index}")
        model.Add(d_lo <= d_hi)
        active_vars.append(active)
        family_vars.append(family)
        d_lo_vars.append(d_lo)
        d_hi_vars.append(d_hi)
        if "active_domain" in components:
            model.Add(family <= sentinel_family_id - 1).OnlyEnforceIf(active)
            model.Add(family == sentinel_family_id).OnlyEnforceIf(active.Not())
        lit_vars = []
        for family_id in [int(value) for value in list(slot.get("family_ids", []))]:
            lit = model.NewBoolVar(f"is_family__slot_{slot_index}__family_{family_id:03d}")
            lit_vars.append(lit)
            rows = rows_by_family_id.get(str(family_id), [])
            if "membership_reification" in components:
                model.Add(family == family_id).OnlyEnforceIf(lit)
                model.Add(family != family_id).OnlyEnforceIf(lit.Not())
            if "shell_pair_table" in components and rows:
                model.AddAllowedAssignments([d_lo, d_hi], rows).OnlyEnforceIf(lit)
        if "membership_sum" in components and lit_vars:
            model.Add(sum(lit_vars) == active)
        if previous_family_var is not None and "ordering" in components:
            model.Add(previous_family_var <= family)
        previous_family_var = family
    if active_vars:
        cover_idx = model.NewIntVar(0, len(active_vars) - 1, "cover_choice_idx")
        cover_active = model.NewBoolVar("cover_choice_active")
        cover_d_lo = model.NewIntVar(shell_min, shell_max, "cover_choice_d_lo")
        cover_d_hi = model.NewIntVar(shell_min, shell_max, "cover_choice_d_hi")
        model.AddElement(cover_idx, active_vars, cover_active)
        model.AddElement(cover_idx, d_lo_vars, cover_d_lo)
        model.AddElement(cover_idx, d_hi_vars, cover_d_hi)
        model.Add(cover_active == 1)
        model.Add(cover_d_lo <= cover_d_hi)
    else:
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
        "micro_variable_count": int(len(getattr(proto, "variables", []))),
        "micro_constraint_count": int(len(getattr(proto, "constraints", []))),
        "solver_parameter_profile": applied_profile,
        "response_summary": _first_line(response_stats),
        "response_stats": str(response_stats),
        "response_stats_parsed": _response_stats_payload(response_stats),
    }


def _normalize_variants(variants: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in variants:
        token = str(raw).strip()
        if not token or token in seen:
            continue
        if token not in _VARIANT_COMPONENTS:
            raise ValueError(f"Unsupported semantic repro variant: {raw!r}")
        seen.add(token)
        result.append(token)
    return tuple(result or DEFAULT_SEMANTIC_REPRO_VARIANTS)


def _status_from_entries(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    evaluated = [entry for entry in entries if bool(entry.get("evaluated", False))]
    counts = _status_counts(evaluated)
    unknowns = _unknown_diagnostics(evaluated)
    if not entries:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_semantic_repro_entries",
            "status_counts": counts,
            "recommendation": "No semantic repro entries were evaluated.",
        }
    if int(unknowns.get("zero_branch_unknown_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "semantic_repro_zero_branch_reproduced",
            "status_counts": counts,
            "recommendation": "The micro semantic repro still has zero-branch UNKNOWN entries; inspect the smallest variant before proto reduction.",
        }
    if any(str(entry.get("status")) == "UNKNOWN" for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "semantic_repro_unknown_with_search_progress",
            "status_counts": counts,
            "recommendation": "The micro semantic repro is UNKNOWN but not zero-branch; compare search stats against the full slice.",
        }
    if all(str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"} for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "semantic_repro_terminal_without_zero_branch",
            "status_counts": counts,
            "recommendation": "The micro semantic repro solves terminally; the blocker needs actual proto reduction rather than basic semantic rewrites.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "semantic_repro_mixed_terminal",
        "status_counts": counts,
        "recommendation": "The micro semantic repro has mixed terminal statuses; inspect infeasible variants before proto reduction.",
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
    return {
        "unknown_count": int(len(unknowns)),
        "zero_branch_unknown_count": int(len(zero_branch)),
        "zero_branch_unknown_by_variant": _count_entries_by_key(
            zero_branch,
            "variant",
        ),
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
            "semantic_repro_extraction_present",
            "pass" if int(extraction.get("selected_slot_count", 0)) > 0 else "fail",
            f"selected_slot_count={int(extraction.get('selected_slot_count', 0))}",
        ),
        _check(
            "semantic_repro_evaluated",
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
