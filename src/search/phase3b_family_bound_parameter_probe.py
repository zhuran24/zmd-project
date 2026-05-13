from __future__ import annotations

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
    _build_exact_overlay,
    _candidate_ghost_rect,
    _check,
    _clone_model_proto,
    _display_path,
    _file_hash,
    _load_json_mapping,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
)

FAMILY_BOUND_PARAMETER_PROBE_SOURCE = "phase3b_family_bound_parameter_probe_v1"
DEFAULT_PROFILES = (
    {
        "profile_id": "portfolio_p3_s3_w4",
        "search_branching": "portfolio",
        "cp_model_probing_level": 3,
        "symmetry_level": 3,
        "worker_count": 4,
    },
    {
        "profile_id": "fixed_p3_s3_w1",
        "search_branching": "fixed",
        "cp_model_probing_level": 3,
        "symmetry_level": 3,
        "worker_count": 1,
    },
    {
        "profile_id": "automatic_p3_s3_w4",
        "search_branching": "automatic",
        "cp_model_probing_level": 3,
        "symmetry_level": 3,
        "worker_count": 4,
    },
    {
        "profile_id": "portfolio_p0_s0_w4",
        "search_branching": "portfolio",
        "cp_model_probing_level": 0,
        "symmetry_level": 0,
        "worker_count": 4,
    },
    {
        "profile_id": "portfolio_p1_s1_w4",
        "search_branching": "portfolio",
        "cp_model_probing_level": 1,
        "symmetry_level": 1,
        "worker_count": 4,
    },
)


def build_phase3b_family_bound_parameter_probe(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 1,
    anchor_indices: Optional[Sequence[int]] = None,
    time_limit_seconds: float = 20.0,
    profiles: Optional[Sequence[Mapping[str, Any]]] = None,
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
    normalized_profiles = _normalize_profiles(profiles or DEFAULT_PROFILES)
    ghost_rect = _candidate_ghost_rect(candidate_key, record)
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Family-bound parameter probe has not run.",
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
                "recommendation": "Campaign state is missing or invalid; run B5A before parameter probing.",
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
                "outcome": "anchor_samples_missing",
                "recommendation": "No anchor sample selected for parameter probing.",
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
            for anchor_idx in selected_anchor_indices:
                u_var = model.u_vars.get(int(anchor_idx))
                if u_var is None:
                    for profile in normalized_profiles:
                        entries.append(
                            {
                                "anchor_idx": int(anchor_idx),
                                "profile_id": profile["profile_id"],
                                "evaluated": False,
                                "status": "SKIPPED",
                                "skip_reason": "anchor_not_in_model_u_vars",
                            }
                        )
                    continue
                for profile in normalized_profiles:
                    entries.append(
                        _solve_parameter_profile(
                            base_proto,
                            u_var_index=int(u_var.Index()),
                            anchor_idx=int(anchor_idx),
                            profile=profile,
                            time_limit_seconds=float(time_limit_seconds),
                        )
                    )
            timing["probe_solve_seconds"] = float(time.perf_counter() - solve_started)
            status.update(_status_from_entries(entries))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Family-bound parameter probe failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    return {
        "metadata": {
            "source": FAMILY_BOUND_PARAMETER_PROBE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "bound_present_parameter_probe_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
        },
        "candidate": {
            "key": candidate_key,
            "ghost_rect": ghost_rect,
            "campaign_status": record.get("status") if record else None,
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "sample_limit": int(sample_limit),
            "selected_anchor_indices": [int(idx) for idx in selected_anchor_indices],
            "time_limit_seconds": float(time_limit_seconds),
            "profiles": normalized_profiles,
        },
        "status": status,
        "probe": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "status_counts_by_profile": _status_counts_by_key(entries, "profile_id"),
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
            status=status,
            campaign_state_unchanged=before_hash == after_hash,
            model_error=model_error,
        ),
    }


def render_phase3b_family_bound_parameter_probe_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("probe"))
    lines = [
        "# Phase 3B Family Bound Parameter Probe",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        "- Diagnostic semantics: bound_present_parameter_probe_not_proof_source",
        f"- Status counts: {probe.get('status_counts', {})}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "| Anchor | Profile | Status | Branching | Probing | Symmetry | Workers | Wall | Deterministic | Branches | Conflicts |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(probe.get("entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("anchor_idx")),
                        _markdown_cell(entry.get("profile_id")),
                        _markdown_cell(entry.get("status")),
                        _markdown_cell(entry.get("search_branching")),
                        _markdown_cell(entry.get("cp_model_probing_level")),
                        _markdown_cell(entry.get("symmetry_level")),
                        _markdown_cell(entry.get("worker_count")),
                        _markdown_cell(entry.get("wall_time")),
                        _markdown_cell(entry.get("deterministic_time")),
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


def render_phase3b_family_bound_parameter_probe_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("probe"))
    lines = [
        "Phase 3B family bound parameter probe",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        "diagnostic_semantics=bound_present_parameter_probe_not_proof_source",
        f"status_counts={probe.get('status_counts', {})}",
        f"recommendation={status.get('recommendation')}",
    ]
    for entry in list(probe.get("entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "entry "
                f"anchor={entry.get('anchor_idx')} "
                f"profile={entry.get('profile_id')} "
                f"status={entry.get('status')} "
                f"branching={entry.get('search_branching')} "
                f"probing={entry.get('cp_model_probing_level')} "
                f"symmetry={entry.get('symmetry_level')} "
                f"workers={entry.get('worker_count')} "
                f"wall={entry.get('wall_time')} "
                f"deterministic={entry.get('deterministic_time')} "
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


def _solve_parameter_profile(
    base_proto: Any,
    *,
    u_var_index: int,
    anchor_idx: int,
    profile: Mapping[str, Any],
    time_limit_seconds: float,
) -> Dict[str, Any]:
    local_model = cp_model_from_proto(_clone_model_proto(base_proto))
    local_model.Add(local_model.GetBoolVarFromProtoIndex(int(u_var_index)) == 1)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = max(1, int(profile["worker_count"]))
    _apply_branching(solver, str(profile["search_branching"]))
    solver.parameters.cp_model_probing_level = int(profile["cp_model_probing_level"])
    solver.parameters.symmetry_level = int(profile["symmetry_level"])
    solver.parameters.hint_conflict_limit = max(
        int(solver.parameters.hint_conflict_limit),
        1000,
    )
    started = time.perf_counter()
    status = solver.Solve(local_model)
    elapsed_seconds = float(time.perf_counter() - started)
    response_stats = solver.ResponseStats()
    parsed = _response_stats_payload(response_stats)
    return {
        "anchor_idx": int(anchor_idx),
        "profile_id": str(profile["profile_id"]),
        "evaluated": True,
        "status": solver.StatusName(status),
        "elapsed_seconds": float(elapsed_seconds),
        "wall_time": float(solver.WallTime()),
        "user_time": float(solver.UserTime()),
        "deterministic_time": _float_or_none(parsed.get("deterministic_time")),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "search_branching": str(profile["search_branching"]),
        "cp_model_probing_level": int(profile["cp_model_probing_level"]),
        "symmetry_level": int(profile["symmetry_level"]),
        "worker_count": int(profile["worker_count"]),
        "time_limit_seconds": float(time_limit_seconds),
        "response_summary": _first_line(response_stats),
        "response_stats": response_stats,
        "response_stats_parsed": parsed,
    }


def _apply_branching(solver: Any, search_branching: str) -> None:
    branching = str(search_branching).strip().lower()
    if branching == "fixed":
        solver.parameters.search_branching = cp_model.FIXED_SEARCH
    elif branching == "automatic":
        solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    elif branching == "portfolio":
        solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
    else:
        raise ValueError(f"Unsupported search_branching: {search_branching}")


def _normalize_profiles(profiles: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(profiles):
        profile_id = str(raw.get("profile_id") or f"profile_{index}").strip()
        if not profile_id or profile_id in seen:
            continue
        seen.add(profile_id)
        branching = str(raw.get("search_branching", "portfolio")).strip().lower()
        if branching not in {"fixed", "automatic", "portfolio"}:
            raise ValueError(f"Unsupported search_branching in profile {profile_id}: {branching}")
        result.append(
            {
                "profile_id": profile_id,
                "search_branching": branching,
                "cp_model_probing_level": max(0, int(raw.get("cp_model_probing_level", 3))),
                "symmetry_level": max(0, int(raw.get("symmetry_level", 3))),
                "worker_count": max(1, int(raw.get("worker_count", 4))),
            }
        )
    return result or _normalize_profiles(DEFAULT_PROFILES)


def _status_from_entries(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    evaluated = [entry for entry in entries if bool(entry.get("evaluated", False))]
    counts = _status_counts(evaluated)
    if not entries:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_parameter_probe_entries",
            "status_counts": counts,
            "recommendation": "No parameter-probe entries were evaluated.",
        }
    if any(str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"} for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "parameter_probe_terminal_found",
            "status_counts": counts,
            "recommendation": "At least one bound-present parameter profile reached a terminal feasible status; inspect before runtime changes.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "parameter_probe_unknown_remaining",
        "status_counts": counts,
        "recommendation": "No bound-present parameter profile reached terminal status; consider formulation-level diagnostics.",
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
                str(entry.get("profile_id")),
            ),
        )[0]
    )


def _unknown_diagnostics(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    unknowns = [entry for entry in entries if str(entry.get("status")) == "UNKNOWN"]
    zero_progress = [
        entry
        for entry in unknowns
        if int(entry.get("branches", 0)) == 0 and int(entry.get("conflicts", 0)) == 0
    ]
    return {
        "unknown_count": int(len(unknowns)),
        "zero_branch_unknown_count": int(len(zero_progress)),
        "zero_branch_unknown_profiles": [
            str(entry.get("profile_id")) for entry in zero_progress
        ],
    }


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
            "parameter_probe_evaluated",
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


def _response_stats_payload(text: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for raw_line in str(text).splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().replace(" ", "_").lower()
        if key:
            payload[key] = _parse_value(value.strip())
    return payload


def _parse_value(value: str) -> Any:
    if not value:
        return ""
    try:
        if any(token in value for token in (".", "e", "E")):
            return float(value)
        return int(value)
    except Exception:
        return value


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _first_line(text: str) -> str:
    for line in str(text).splitlines():
        if line.strip():
            return line.strip()
    return ""


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
