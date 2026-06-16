from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from ortools.sat.python import cp_model

from src.models._cpsat_compat import cp_model_from_proto
from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    MasterPlacementModel,
    _clone_model_proto,
    load_generic_io_requirements_artifact,
    load_project_data,
)
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

MANDATORY_CORE_MATRIX_SOURCE = "phase3b_mandatory_core_profile_matrix_v1"
DEFAULT_MASTER_PROFILES = (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    "exact_coordinate_ghost_first_v1",
    "exact_coordinate_ghost_after_counts_v1",
)
DEFAULT_SYMMETRY_MODES = (True, False)


def build_phase3b_mandatory_core_profile_matrix(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    sample_limit: int = 1,
    anchor_indices: Optional[Sequence[int]] = None,
    time_limit_seconds: float = 15.0,
    worker_count: int = 4,
    master_profiles: Sequence[str] = DEFAULT_MASTER_PROFILES,
    symmetry_modes: Sequence[bool] = DEFAULT_SYMMETRY_MODES,
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
    profiles = _normalize_profiles(master_profiles)
    symmetry_values = _normalize_symmetry_modes(symmetry_modes)
    ghost_rect = _candidate_ghost_rect(candidate_key, record)
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Mandatory-core profile matrix has not run.",
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
                "recommendation": "Campaign state is missing or invalid; run B5A before mandatory-core matrix profiling.",
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
            for profile in profiles:
                for symmetry_enabled in symmetry_values:
                    build_started = time.perf_counter()
                    model, base_proto = _build_mandatory_core_overlay(
                        project_root,
                        ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                        master_search_profile=str(profile),
                        enable_symmetry_breaking=bool(symmetry_enabled),
                    )
                    build_key = f"{profile}__sym_{int(bool(symmetry_enabled))}_build_seconds"
                    timing[build_key] = float(time.perf_counter() - build_started)
                    disabled_residual_indices = _residual_active_indices(model)
                    for anchor_idx in selected_anchor_indices:
                        u_var = model.u_vars.get(int(anchor_idx))
                        if u_var is None:
                            entries.append(
                                {
                                    "anchor_idx": int(anchor_idx),
                                    "master_search_profile": str(profile),
                                    "symmetry_enabled": bool(symmetry_enabled),
                                    "evaluated": False,
                                    "status": "SKIPPED",
                                    "skip_reason": "anchor_not_in_model_u_vars",
                                }
                            )
                            continue
                        entries.append(
                            _solve_mandatory_core_clone(
                                base_proto,
                                anchor_idx=int(anchor_idx),
                                u_var_index=int(u_var.Index()),
                                disabled_residual_indices=disabled_residual_indices,
                                master_search_profile=str(profile),
                                symmetry_enabled=bool(symmetry_enabled),
                                time_limit_seconds=float(time_limit_seconds),
                                worker_count=int(worker_count),
                                search_guidance=_mapping(
                                    model.build_stats.get("search_guidance")
                                ),
                                symmetry_stats=_mapping(
                                    model.build_stats.get("coordinate_symmetry")
                                ),
                            )
                        )
            status.update(_status_from_entries(entries))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Mandatory-core profile matrix failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    return {
        "metadata": {
            "source": MANDATORY_CORE_MATRIX_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "mutated_mandatory_core_not_proof_source",
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
            "sample_limit": int(sample_limit),
            "selected_anchor_indices": [int(idx) for idx in selected_anchor_indices],
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "master_profiles": list(profiles),
            "symmetry_modes": [bool(value) for value in symmetry_values],
            "slice": "skip_power_coverage_no_protocol_lower_bound_residual_all_inactive",
        },
        "status": status,
        "matrix": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "status_counts_by_profile": _status_counts_by_key(entries, "master_search_profile"),
            "status_counts_by_symmetry": _status_counts_by_key(entries, "symmetry_enabled"),
            "status_counts_by_anchor": _status_counts_by_key(entries, "anchor_idx"),
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


def render_phase3b_mandatory_core_profile_matrix_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    matrix = _mapping(report.get("matrix"))
    lines = [
        "# Phase 3B Mandatory-Core Profile Matrix",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "- Diagnostic semantics: mutated_mandatory_core_not_proof_source",
        f"- Status counts: {matrix.get('status_counts', {})}",
        "",
        "| Anchor | Profile | Symmetry | Status | Branches | Conflicts |",
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
                    _markdown_cell(entry.get("master_search_profile")),
                    _markdown_cell(entry.get("symmetry_enabled")),
                    _markdown_cell(entry.get("status")),
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


def render_phase3b_mandatory_core_profile_matrix_text(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    matrix = _mapping(report.get("matrix"))
    lines = [
        "Phase 3B mandatory-core profile matrix",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        "diagnostic_semantics=mutated_mandatory_core_not_proof_source",
        f"status_counts={matrix.get('status_counts', {})}",
    ]
    for entry in list(matrix.get("entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "entry "
                f"anchor={entry.get('anchor_idx')} "
                f"profile={entry.get('master_search_profile')} "
                f"symmetry={entry.get('symmetry_enabled')} "
                f"status={entry.get('status')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')} "
                f"decision_phases={entry.get('decision_strategy_phases')}"
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


def _build_mandatory_core_overlay(
    project_root: Path,
    *,
    ghost_rect: tuple[int, int],
    master_search_profile: str,
    enable_symmetry_breaking: bool,
) -> tuple[MasterPlacementModel, Any]:
    instances, facility_pools, rules = load_project_data(
        project_root,
        solve_mode="certified_exact",
    )
    generic_io_requirements = {
        **dict(load_generic_io_requirements_artifact(project_root)),
        "required_generic_inputs": {},
    }
    core = MasterPlacementModel.build_exact_core(
        instances,
        facility_pools,
        rules,
        skip_power_coverage=True,
        enable_symmetry_breaking=bool(enable_symmetry_breaking),
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


def _residual_active_indices(model: Any) -> list[int]:
    delegate = getattr(model, "_coordinate_delegate", None)
    residual_slots = getattr(delegate, "residual_optional_slots", {}) if delegate else {}
    result: list[int] = []
    for slots in residual_slots.values():
        for slot in list(slots):
            active = getattr(slot, "active", None)
            if active is not None:
                result.append(int(active.Index()))
    return result


def _solve_mandatory_core_clone(
    base_proto: Any,
    *,
    anchor_idx: int,
    u_var_index: int,
    disabled_residual_indices: Sequence[int],
    master_search_profile: str,
    symmetry_enabled: bool,
    time_limit_seconds: float,
    worker_count: int,
    search_guidance: Mapping[str, Any],
    symmetry_stats: Mapping[str, Any],
) -> Dict[str, Any]:
    local_model = cp_model_from_proto(_clone_model_proto(base_proto))
    local_model.Add(local_model.GetBoolVarFromProtoIndex(int(u_var_index)) == 1)
    for var_idx in disabled_residual_indices:
        local_model.Add(local_model.GetBoolVarFromProtoIndex(int(var_idx)) == 0)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = max(1, int(worker_count))
    solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
    solver.parameters.symmetry_level = max(int(solver.parameters.symmetry_level), 3)
    solver.parameters.cp_model_probing_level = max(
        int(solver.parameters.cp_model_probing_level),
        3,
    )
    solver.parameters.hint_conflict_limit = max(
        int(solver.parameters.hint_conflict_limit),
        1000,
    )
    started = time.perf_counter()
    status = solver.Solve(local_model)
    elapsed_seconds = float(time.perf_counter() - started)
    return {
        "anchor_idx": int(anchor_idx),
        "master_search_profile": str(master_search_profile),
        "symmetry_enabled": bool(symmetry_enabled),
        "evaluated": True,
        "status": solver.StatusName(status),
        "elapsed_seconds": float(elapsed_seconds),
        "wall_time": float(solver.WallTime()),
        "user_time": float(solver.UserTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "disabled_residual_active_count": len(disabled_residual_indices),
        "decision_strategy_phases": list(search_guidance.get("decision_strategy_phases", [])),
        "coordinate_symmetry": {
            "enabled": bool(symmetry_stats.get("enabled", False)),
            "mandatory_signature_monotonic_constraints": int(
                symmetry_stats.get("mandatory_signature_monotonic_constraints", 0)
            ),
            "residual_optional_signature_monotonic_constraints": int(
                symmetry_stats.get("residual_optional_signature_monotonic_constraints", 0)
            ),
            "slot_order_key_monotonic_constraints": int(
                symmetry_stats.get("slot_order_key_monotonic_constraints", 0)
            ),
            "power_pole_family_order_constraints": int(
                symmetry_stats.get("power_pole_family_order_constraints", 0)
            ),
        },
        "response_summary": _first_line(solver.ResponseStats()),
    }


def _normalize_profiles(values: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        token = str(raw).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return tuple(result or DEFAULT_MASTER_PROFILES)


def _normalize_symmetry_modes(values: Sequence[bool]) -> tuple[bool, ...]:
    result: list[bool] = []
    seen: set[bool] = set()
    for raw in values:
        value = bool(raw)
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return tuple(result or DEFAULT_SYMMETRY_MODES)


def _status_from_entries(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    counts = _status_counts(entries)
    if not entries:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_matrix_entries",
            "status_counts": counts,
            "recommendation": "No mandatory-core matrix entries were evaluated.",
        }
    if any(str(entry.get("status")) != "UNKNOWN" for entry in entries):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "mandatory_core_profile_sensitive",
            "status_counts": counts,
            "recommendation": "At least one mandatory-core profile matrix entry reached a terminal status; inspect profile and symmetry settings.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "mandatory_core_unknown_across_profiles",
        "status_counts": counts,
        "recommendation": "Mandatory-core slice remains UNKNOWN across tested profiles/symmetry settings; inspect mandatory no-overlap/domain encoding next.",
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
            "mandatory_core_matrix_evaluated",
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


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
