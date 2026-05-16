from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

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
    _build_exact_overlay,
    _clone_model_proto,
    _solve_slice_clone,
)

FORCED_ANCHOR_PRESOLVE_PROFILE_PROBE_SOURCE = (
    "phase3b_forced_anchor_presolve_profile_probe_v1"
)

DEFAULT_PRESOLVE_PROFILE_PROFILES = (
    {
        "profile_id": "fixed_presolve_on_p0_s0_w1",
        "search_branching": "fixed",
        "cp_model_probing_level": 0,
        "symmetry_level": 0,
        "worker_count": 1,
        "random_seed": 1,
        "randomize_search": False,
        "cp_model_presolve": True,
    },
    {
        "profile_id": "fixed_presolve_off_p0_s0_w1",
        "search_branching": "fixed",
        "cp_model_probing_level": 0,
        "symmetry_level": 0,
        "worker_count": 1,
        "random_seed": 1,
        "randomize_search": False,
        "cp_model_presolve": False,
    },
    {
        "profile_id": "portfolio_presolve_off_p0_s0_w4",
        "search_branching": "portfolio",
        "cp_model_probing_level": 0,
        "symmetry_level": 0,
        "worker_count": 4,
        "random_seed": 1,
        "randomize_search": False,
        "cp_model_presolve": False,
    },
)


def build_phase3b_forced_anchor_presolve_profile_probe(
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
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    before_hash = _file_hash(campaign_path)
    state, state_error = _load_json_mapping(campaign_path)
    candidate_key = str(candidate)
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
    normalized_profiles = _normalize_profiles(profiles or DEFAULT_PRESOLVE_PROFILE_PROFILES)
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Forced-anchor presolve profile probe has not run.",
    }
    entries: list[Dict[str, Any]] = []
    model_error: Optional[str] = None
    timing: Dict[str, float] = {}
    overlay_built = False
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before presolve profile probing.",
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
            overlay_built = True
            base_proto = _clone_model_proto(base_proto)
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            solve_started = time.perf_counter()
            for anchor_idx in selected_anchor_indices:
                u_var = dict(getattr(model, "u_vars", {}) or {}).get(int(anchor_idx))
                if u_var is None:
                    for profile in normalized_profiles:
                        entries.append(
                            {
                                "anchor_idx": int(anchor_idx),
                                "variant": "base",
                                "solver_profile_id": str(profile["profile_id"]),
                                "evaluated": False,
                                "status": "SKIPPED",
                                "skip_reason": "anchor_not_in_model_u_vars",
                            }
                        )
                    continue
                for profile in normalized_profiles:
                    entry = _solve_slice_clone(
                        base_proto,
                        anchor_idx=int(anchor_idx),
                        u_var_index=int(u_var.Index()),
                        disabled_active_var_indices=[],
                        variant="base",
                        time_limit_seconds=float(time_limit_seconds),
                        worker_count=int(profile.get("worker_count", 1)),
                        solver_parameter_profile=profile,
                        assumption_label="presolve_profile_probe",
                    )
                    entry["solver_profile_id"] = str(profile["profile_id"])
                    entry["probe_variant"] = "base"
                    entries.append(entry)
            timing["probe_solve_seconds"] = float(time.perf_counter() - solve_started)
            status.update(_status_from_entries(entries))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Forced-anchor presolve profile probe failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    return {
        "metadata": {
            "source": FORCED_ANCHOR_PRESOLVE_PROFILE_PROBE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "presolve_profile_probe_not_proof_source",
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
            "profiles": normalized_profiles,
        },
        "status": status,
        "probe": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "status_counts_by_profile": _status_counts_by_key(entries, "solver_profile_id"),
            "best_terminal_entry": _best_terminal_entry(entries),
            "unknown_diagnostics": _unknown_diagnostics(entries),
            "profile_comparison": _profile_comparison(entries),
        },
        "timing": timing,
        "model_error": model_error,
        "overlay_built_once": bool(overlay_built),
        "campaign_state_unchanged": bool(before_hash == after_hash),
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            overlay_built=overlay_built,
            status=status,
            campaign_state_unchanged=before_hash == after_hash,
            model_error=model_error,
        ),
    }


def render_phase3b_forced_anchor_presolve_profile_probe_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("probe"))
    unknowns = _mapping(probe.get("unknown_diagnostics"))
    lines = [
        "# Phase 3B Forced-Anchor Presolve Profile Probe",
        "",
        f"- Candidate: {_mapping(report.get('candidate')).get('key')}",
        "- Diagnostic semantics: presolve_profile_probe_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Status counts: {probe.get('status_counts', {})}",
        f"- Zero-branch UNKNOWN entries: {unknowns.get('zero_branch_unknown_count', 0)}",
        f"- Search-progress UNKNOWN entries: {unknowns.get('search_progress_unknown_count', 0)}",
        "",
        "## Profile Matrix",
        "",
        "| Profile | Status | Presolve | Branching | Workers | Wall | Branches | Conflicts | Deterministic |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(probe.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        solver_profile = _mapping(entry.get("solver_parameter_profile"))
        parsed = _mapping(entry.get("response_stats_parsed"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("solver_profile_id")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(solver_profile.get("cp_model_presolve")),
                    _markdown_cell(entry.get("search_branching")),
                    _markdown_cell(entry.get("solver_worker_count")),
                    _markdown_cell(entry.get("wall_time")),
                    _markdown_cell(entry.get("branches")),
                    _markdown_cell(entry.get("conflicts")),
                    _markdown_cell(parsed.get("deterministic_time")),
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


def render_phase3b_forced_anchor_presolve_profile_probe_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("probe"))
    unknowns = _mapping(probe.get("unknown_diagnostics"))
    lines = [
        "Phase 3B forced-anchor presolve profile probe",
        f"candidate={_mapping(report.get('candidate')).get('key')}",
        "diagnostic_semantics=presolve_profile_probe_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"status_counts={probe.get('status_counts', {})}",
        f"zero_branch_unknown_count={unknowns.get('zero_branch_unknown_count', 0)}",
        f"search_progress_unknown_count={unknowns.get('search_progress_unknown_count', 0)}",
    ]
    for entry in list(probe.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        solver_profile = _mapping(entry.get("solver_parameter_profile"))
        parsed = _mapping(entry.get("response_stats_parsed"))
        lines.append(
            "entry "
            f"profile={entry.get('solver_profile_id')} "
            f"status={entry.get('status')} "
            f"presolve={solver_profile.get('cp_model_presolve')} "
            f"branching={entry.get('search_branching')} "
            f"workers={entry.get('solver_worker_count')} "
            f"wall={entry.get('wall_time')} "
            f"branches={entry.get('branches')} "
            f"conflicts={entry.get('conflicts')} "
            f"deterministic={parsed.get('deterministic_time')}"
        )
    return "\n".join(lines) + "\n"


def _normalize_profiles(profiles: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(profiles):
        profile_id = str(raw.get("profile_id") or f"profile_{index}").strip()
        if not profile_id or profile_id in seen:
            continue
        seen.add(profile_id)
        branching = str(raw.get("search_branching", "fixed")).strip().lower()
        if branching not in {"fixed", "automatic", "portfolio"}:
            raise ValueError(f"Unsupported search_branching in profile {profile_id}: {branching}")
        normalized: Dict[str, Any] = {
            "profile_id": profile_id,
            "search_branching": branching,
            "cp_model_probing_level": max(0, int(raw.get("cp_model_probing_level", 0))),
            "symmetry_level": max(0, int(raw.get("symmetry_level", 0))),
            "worker_count": max(1, int(raw.get("worker_count", 1))),
        }
        for key in ("hint_conflict_limit", "linearization_level", "random_seed"):
            if key in raw and raw[key] is not None:
                normalized[key] = int(raw[key])
        for key in ("cp_model_presolve", "randomize_search"):
            if key in raw and raw[key] is not None:
                normalized[key] = _bool_value(raw[key])
        result.append(normalized)
    return result or _normalize_profiles(DEFAULT_PRESOLVE_PROFILE_PROFILES)


def _status_from_entries(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    evaluated = [entry for entry in entries if bool(entry.get("evaluated", False))]
    counts = _status_counts(evaluated)
    unknowns = _unknown_diagnostics(evaluated)
    if not entries:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "no_presolve_profile_entries",
            "status_counts": counts,
            "recommendation": "No presolve-profile entries were evaluated.",
        }
    if any(str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"} for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "presolve_profile_terminal_found",
            "status_counts": counts,
            "recommendation": "At least one presolve profile reached terminal feasibility; inspect before any runtime promotion.",
        }
    if int(unknowns.get("search_progress_unknown_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "presolve_profile_progress_without_terminal",
            "status_counts": counts,
            "recommendation": "At least one presolve profile produced search progress before timeout; compare with zero-branch profiles.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "presolve_profile_zero_branch_unknown_remaining",
        "status_counts": counts,
        "recommendation": "All presolve profiles remain zero-branch UNKNOWN; continue formulation diagnostics.",
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
                str(entry.get("solver_profile_id")),
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
        "zero_branch_unknown_by_profile": _count_entries_by_key(zero_branch, "solver_profile_id"),
        "search_progress_unknown_by_profile": _count_entries_by_key(progress, "solver_profile_id"),
    }


def _profile_comparison(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    comparison: Dict[str, Any] = {}
    for entry in entries:
        profile_id = str(entry.get("solver_profile_id"))
        solver_profile = _mapping(entry.get("solver_parameter_profile"))
        parsed = _mapping(entry.get("response_stats_parsed"))
        comparison[profile_id] = {
            "status": entry.get("status"),
            "presolve": solver_profile.get("cp_model_presolve"),
            "branches": entry.get("branches"),
            "conflicts": entry.get("conflicts"),
            "wall_time": entry.get("wall_time"),
            "deterministic_time": parsed.get("deterministic_time"),
        }
    return comparison


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
    overlay_built: bool,
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
            "overlay_built_once",
            "pass" if overlay_built else "skipped",
            "overlay built once" if overlay_built else "overlay not built",
        ),
        _check(
            "presolve_profile_probe_evaluated",
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


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value!r}")


def _number_or_zero(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
