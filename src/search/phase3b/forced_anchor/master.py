from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ortools.sat.python import cp_model

from src.models._cpsat_compat import cp_model_from_proto
from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    MasterPlacementModel,
    _clone_model_proto,
)
from src.search.benders_loop import create_exact_search_session
from src.search.exact_campaign import now_iso

FORCED_ANCHOR_MASTER_SOURCE = "phase3b_forced_anchor_master_profiler_v1"
DEFAULT_CAMPAIGN_STATE_PATH = Path("data/checkpoints/exact_campaign_state.json")
DEFAULT_CANDIDATE = "69x19"


def build_phase3b_forced_anchor_master_profile(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 3,
    anchor_indices: Optional[Sequence[int]] = None,
    time_limit_seconds: float = 20.0,
    worker_count: int = 4,
    search_branching: str = "portfolio",
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
    ghost_rect = _candidate_ghost_rect(candidate_key, record)

    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Forced-anchor master profiler has not run.",
    }
    forced_anchors: list[Dict[str, Any]] = []
    timing: Dict[str, float] = {}
    model_error: Optional[str] = None
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before forced-anchor master profiling.",
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
                "recommendation": "Candidate has no failed-anchor samples; rerun B5A with failed-anchor sampling enabled.",
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
                    forced_anchors.append(
                        {
                            "anchor_idx": int(anchor_idx),
                            "evaluated": False,
                            "status": "SKIPPED",
                            "skip_reason": "anchor_not_in_model_u_vars",
                        }
                    )
                    continue
                forced_anchors.append(
                    _solve_forced_anchor_clone(
                        base_proto,
                        u_var_index=int(u_var.Index()),
                        anchor_idx=int(anchor_idx),
                        time_limit_seconds=float(time_limit_seconds),
                        worker_count=int(worker_count),
                        search_branching=str(search_branching),
                    )
                )
            timing["forced_anchor_solve_seconds"] = float(
                time.perf_counter() - solve_started
            )
            status.update(_status_from_forced_anchors(forced_anchors))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Forced-anchor master profiler failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    campaign_state_unchanged = before_hash == after_hash
    return {
        "metadata": {
            "source": FORCED_ANCHOR_MASTER_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
        },
        "candidate": {
            "key": candidate_key,
            "ghost_rect": ghost_rect,
            "campaign_status": record.get("status") if record else None,
            "attempts": int(record.get("attempts", 0)) if record else 0,
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "sample_limit": int(sample_limit),
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "search_branching": str(search_branching),
        },
        "input_evidence": {
            "campaign_present": state is not None and state_error is None,
            "campaign_load_error": state_error,
            "candidate_present": bool(record),
            "failed_anchor_count": int(
                failure_attribution.get("failed_anchor_count", 0)
            )
            if failure_attribution
            else 0,
            "failed_anchor_sample_count": len(failed_anchor_samples),
            "selected_anchor_indices": [int(idx) for idx in selected_anchor_indices],
        },
        "status": status,
        "forced_anchors": forced_anchors,
        "timing": timing,
        "model_error": model_error,
        "campaign_state_unchanged": bool(campaign_state_unchanged),
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            status=status,
            campaign_state_unchanged=campaign_state_unchanged,
            model_error=model_error,
        ),
    }


def render_phase3b_forced_anchor_master_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    profile = _mapping(report.get("profile"))
    lines = [
        "# Phase 3B Forced-Anchor Master Profile",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Time limit: {profile.get('time_limit_seconds')}s",
        f"- Campaign state unchanged: {bool(report.get('campaign_state_unchanged', False))}",
        "",
        "## Anchors",
        "",
        "| Anchor | Status | Wall | Branches | Conflicts | Detail |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(report.get("forced_anchors", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("anchor_idx")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("wall_time")),
                    _markdown_cell(entry.get("branches")),
                    _markdown_cell(entry.get("conflicts")),
                    _markdown_cell(entry.get("skip_reason") or entry.get("response_summary", "")),
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


def render_phase3b_forced_anchor_master_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    profile = _mapping(report.get("profile"))
    lines = [
        "Phase 3B forced-anchor master profile",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"time_limit_seconds={profile.get('time_limit_seconds')}",
        f"campaign_state_unchanged={bool(report.get('campaign_state_unchanged', False))}",
    ]
    for entry in list(report.get("forced_anchors", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "anchor "
                f"idx={entry.get('anchor_idx')} "
                f"status={entry.get('status')} "
                f"wall={entry.get('wall_time')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')} "
                f"skip={entry.get('skip_reason')}"
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


def _build_exact_overlay(
    project_root: Path,
    *,
    ghost_rect: Tuple[int, int],
    master_search_profile: str,
) -> tuple[MasterPlacementModel, Any]:
    exact_session = create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
        master_search_profile=master_search_profile,
    )
    model = MasterPlacementModel.from_exact_core(
        exact_session.core,
        ghost_rect=(int(ghost_rect[0]), int(ghost_rect[1])),
        master_search_profile=master_search_profile,
    )
    model.build()
    return model, _clone_model_proto(model.model.Proto())


def _solve_forced_anchor_clone(
    base_proto: Any,
    *,
    u_var_index: int,
    anchor_idx: int,
    time_limit_seconds: float,
    worker_count: int,
    search_branching: str,
) -> Dict[str, Any]:
    local_model = cp_model_from_proto(_clone_model_proto(base_proto))
    u_var = local_model.GetBoolVarFromProtoIndex(int(u_var_index))
    local_model.Add(u_var == 1)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = max(1, int(worker_count))
    branching = str(search_branching).strip().lower()
    if branching in {"", "fixed"}:
        solver.parameters.search_branching = cp_model.FIXED_SEARCH
        branching = "fixed"
    elif branching == "automatic":
        solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    elif branching == "portfolio":
        solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
    else:
        raise ValueError(f"Unsupported search_branching: {search_branching}")
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
    response_stats = solver.ResponseStats()
    return {
        "anchor_idx": int(anchor_idx),
        "evaluated": True,
        "status": solver.StatusName(status),
        "elapsed_seconds": float(elapsed_seconds),
        "wall_time": float(solver.WallTime()),
        "user_time": float(solver.UserTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "search_branching": branching,
        "worker_count": int(worker_count),
        "time_limit_seconds": float(time_limit_seconds),
        "response_summary": _first_line(response_stats),
        "response_stats": response_stats,
    }


def _status_from_forced_anchors(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    evaluated = [entry for entry in entries if bool(entry.get("evaluated", False))]
    status_counts: Dict[str, int] = {}
    for entry in evaluated:
        status = str(entry.get("status", "UNKNOWN"))
        status_counts[status] = int(status_counts.get(status, 0)) + 1
    if not entries:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_anchors_evaluated",
            "status_counts": status_counts,
            "recommendation": "No anchors were evaluated; increase sample_limit only in a workspace.",
        }
    if any(str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"} for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "forced_anchor_feasible_found",
            "status_counts": status_counts,
            "recommendation": "At least one forced anchor is master-feasible; use it as B5A repair input before shrink work.",
        }
    if evaluated and all(str(entry.get("status")) == "INFEASIBLE" for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "forced_anchor_all_infeasible",
            "status_counts": status_counts,
            "recommendation": "All sampled forced anchors are master-infeasible; broaden anchor coverage before drawing candidate-level conclusions.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "forced_anchor_unknown_remaining",
        "status_counts": status_counts,
        "recommendation": "Some sampled forced anchors remain UNKNOWN or skipped; increase per-anchor time or triage the unknown anchors.",
    }


def _selected_anchor_indices(
    samples: Sequence[Mapping[str, Any]],
    sample_limit: int,
    *,
    explicit_anchor_indices: Optional[Sequence[int]] = None,
) -> list[int]:
    if explicit_anchor_indices is not None:
        result: list[int] = []
        seen: set[int] = set()
        for raw_idx in explicit_anchor_indices:
            anchor_idx = int(raw_idx)
            if anchor_idx in seen:
                continue
            seen.add(anchor_idx)
            result.append(anchor_idx)
        return result
    limit = max(0, int(sample_limit))
    result: list[int] = []
    seen: set[int] = set()
    for sample in samples:
        if len(result) >= limit:
            break
        try:
            anchor_idx = int(sample.get("anchor_idx"))
        except Exception:
            continue
        if anchor_idx in seen:
            continue
        seen.add(anchor_idx)
        result.append(anchor_idx)
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
            "forced_anchor_profile_evaluated",
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


def _candidate_ghost_rect(candidate_key: str, record: Mapping[str, Any]) -> Dict[str, int]:
    ghost_rect = _mapping(record.get("ghost_rect"))
    try:
        w = int(ghost_rect.get("w", 0))
        h = int(ghost_rect.get("h", 0))
        area = int(ghost_rect.get("area", w * h))
    except Exception:
        w, h = _parse_candidate(candidate_key)
        area = w * h
    if w <= 0 or h <= 0:
        w, h = _parse_candidate(candidate_key)
        area = w * h
    return {"w": int(w), "h": int(h), "area": int(area)}


def _parse_candidate(candidate: str) -> Tuple[int, int]:
    raw = str(candidate).lower().strip()
    if "x" not in raw:
        raise ValueError(f"Unsupported candidate {candidate!r}; expected <w>x<h>.")
    w_text, h_text = raw.split("x", 1)
    w = int(w_text)
    h = int(h_text)
    if w <= 0 or h <= 0:
        raise ValueError(f"Unsupported candidate {candidate!r}; dimensions must be positive.")
    return w, h


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"json_load_error:{type(exc).__name__}:{exc}"
    if not isinstance(payload, Mapping):
        return None, "json_payload_not_object"
    return dict(payload), None


def _file_hash(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _first_line(text: str) -> str:
    for line in str(text).splitlines():
        if line.strip():
            return line.strip()
    return ""


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
