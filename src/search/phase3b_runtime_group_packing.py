from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    MasterPlacementModel,
)
from src.search.benders_loop import create_exact_search_session
from src.search.exact_campaign import now_iso
from src.search.phase3b_start_compatibility import (
    _build_group_packing_blockers,
    _build_group_packing_probe,
)

RUNTIME_GROUP_PACKING_SOURCE = "phase3b_runtime_group_packing_diagnostic_v1"
DEFAULT_CAMPAIGN_STATE_PATH = Path("data/checkpoints/exact_campaign_state.json")
DEFAULT_CANDIDATE = "69x19"


def build_phase3b_runtime_group_packing_diagnostic(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 8,
    time_limit_seconds: float = 0.5,
    max_candidates: int = 2500,
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
    ghost_rect = _candidate_ghost_rect(candidate_key, record)

    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Runtime group-packing diagnostic has not run.",
    }
    diagnostics: Dict[str, Any] = {
        "group_packing_probe": _disabled_probe(
            sample_limit=sample_limit,
            time_limit_seconds=time_limit_seconds,
            max_candidates=max_candidates,
        ),
        "group_packing_blockers": _build_group_packing_blockers(
            _disabled_probe(
                sample_limit=sample_limit,
                time_limit_seconds=time_limit_seconds,
                max_candidates=max_candidates,
            )
        ),
    }
    timing: Dict[str, float] = {}
    model_error: Optional[str] = None
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before runtime group-packing diagnostics.",
            }
        )
    elif not record:
        status.update(
            {
                "completed": True,
                "outcome": "candidate_missing",
                "recommendation": "Candidate is not present in campaign state; rerun B5A or choose a recorded blocker candidate.",
            }
        )
    elif not failed_anchor_samples:
        status.update(
            {
                "completed": True,
                "outcome": "start_failure_samples_missing",
                "recommendation": "Candidate has no failed-anchor samples; run start-compatibility diagnostics with a sample cap before probing group packing.",
            }
        )
    else:
        try:
            session_started = time.perf_counter()
            exact_session = create_exact_search_session(
                project_root,
                solve_mode="certified_exact",
                master_search_profile=master_search_profile,
            )
            timing["session_build_seconds"] = float(time.perf_counter() - session_started)
            model_started = time.perf_counter()
            model = MasterPlacementModel.from_exact_core(
                exact_session.core,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=master_search_profile,
            )
            timing["overlay_build_seconds"] = float(time.perf_counter() - model_started)
            probe_started = time.perf_counter()
            probe = _build_group_packing_probe(
                model,
                failure_attribution=failure_attribution,
                sample_limit=int(sample_limit),
                time_limit_seconds=float(time_limit_seconds),
                max_candidates=int(max_candidates),
            )
            blockers = _build_group_packing_blockers(probe)
            timing["group_packing_probe_seconds"] = float(
                time.perf_counter() - probe_started
            )
            diagnostics = {
                "group_packing_probe": probe,
                "group_packing_blockers": blockers,
            }
            status.update(
                _status_from_probe(
                    probe=probe,
                    blockers=blockers,
                )
            )
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Runtime group-packing diagnostic failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    campaign_state_unchanged = before_hash == after_hash
    report = {
        "metadata": {
            "source": RUNTIME_GROUP_PACKING_SOURCE,
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
            "max_candidates": int(max_candidates),
        },
        "input_evidence": {
            "campaign_present": state is not None and state_error is None,
            "campaign_load_error": state_error,
            "candidate_present": bool(record),
            "master_status": proof_summary.get("master_status"),
            "master_start_feasibility": proof_summary.get("master_start_feasibility")
            if isinstance(proof_summary.get("master_start_feasibility"), Mapping)
            else None,
            "failed_anchor_count": int(
                failure_attribution.get("failed_anchor_count", 0)
            )
            if failure_attribution
            else 0,
            "failed_anchor_sample_count": len(failed_anchor_samples),
            "first_failed_group_id": failure_attribution.get("first_failed_group_id")
            if failure_attribution
            else None,
            "first_failed_group_template": failure_attribution.get(
                "first_failed_group_template"
            )
            if failure_attribution
            else None,
            "failure_reason_counts": dict(
                failure_attribution.get("failure_reason_counts", {})
            )
            if isinstance(failure_attribution.get("failure_reason_counts"), Mapping)
            else {},
        },
        "status": status,
        "diagnostics": diagnostics,
        "timing": timing,
        "model_error": model_error,
        "campaign_state_unchanged": bool(campaign_state_unchanged),
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            failed_anchor_sample_count=len(failed_anchor_samples),
            status=status,
            campaign_state_unchanged=campaign_state_unchanged,
            model_error=model_error,
        ),
    }
    return report


def render_phase3b_runtime_group_packing_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    diagnostics = _mapping(report.get("diagnostics"))
    probe = _mapping(diagnostics.get("group_packing_probe"))
    blockers = _mapping(diagnostics.get("group_packing_blockers"))
    lines = [
        "# Phase 3B Runtime Group-Packing Diagnostic",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Campaign state unchanged: {bool(report.get('campaign_state_unchanged', False))}",
        "",
        "## Probe",
        "",
        f"- Samples: {probe.get('sample_count', 0)}",
        f"- Feasible: {probe.get('feasible_count', 0)}",
        f"- Infeasible: {probe.get('infeasible_count', 0)}",
        f"- Unknown: {probe.get('unknown_count', 0)}",
        f"- Skipped: {probe.get('skipped_count', 0)}",
        f"- Blockers: {blockers.get('blocker_count', 0)}",
    ]
    blocker_entries = [
        entry
        for entry in list(blockers.get("blockers", []))
        if isinstance(entry, Mapping)
    ]
    if blocker_entries:
        lines.extend(
            [
                "",
                "## Blockers",
                "",
                "| Group | Status | Samples | Required | Surviving | Greedy |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in blocker_entries:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("group_id")),
                        _markdown_cell(entry.get("solver_status")),
                        _markdown_cell(entry.get("sample_count")),
                        _markdown_cell(
                            f"{entry.get('required_count_min')}..{entry.get('required_count_max')}"
                        ),
                        _markdown_cell(
                            f"{entry.get('surviving_at_failure_min')}..{entry.get('surviving_at_failure_max')}"
                        ),
                        _markdown_cell(
                            f"{entry.get('greedy_selected_min')}..{entry.get('greedy_selected_max')}"
                        ),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
        if not isinstance(check, Mapping):
            continue
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


def render_phase3b_runtime_group_packing_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    diagnostics = _mapping(report.get("diagnostics"))
    probe = _mapping(diagnostics.get("group_packing_probe"))
    blockers = _mapping(diagnostics.get("group_packing_blockers"))
    lines = [
        "Phase 3B runtime group-packing diagnostic",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"campaign_state_unchanged={bool(report.get('campaign_state_unchanged', False))}",
        (
            "probe "
            f"samples={probe.get('sample_count', 0)} "
            f"feasible={probe.get('feasible_count', 0)} "
            f"infeasible={probe.get('infeasible_count', 0)} "
            f"unknown={probe.get('unknown_count', 0)} "
            f"skipped={probe.get('skipped_count', 0)} "
            f"blockers={blockers.get('blocker_count', 0)}"
        ),
    ]
    for entry in list(blockers.get("blockers", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "blocker "
            f"group={entry.get('group_id')} "
            f"status={entry.get('solver_status')} "
            f"samples={entry.get('sample_count')} "
            f"required={entry.get('required_count_min')}..{entry.get('required_count_max')} "
            f"surviving={entry.get('surviving_at_failure_min')}..{entry.get('surviving_at_failure_max')}"
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


def _status_from_probe(
    *,
    probe: Mapping[str, Any],
    blockers: Mapping[str, Any],
) -> Dict[str, Any]:
    blocker_count = int(blockers.get("blocker_count", 0))
    feasible_count = int(probe.get("feasible_count", 0))
    unknown_count = int(probe.get("unknown_count", 0))
    skipped_count = int(probe.get("skipped_count", 0))
    sample_count = int(probe.get("sample_count", 0))
    if sample_count <= 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_samples_evaluated",
            "recommendation": "No failed-anchor samples were evaluated; increase sample_limit only in a workspace.",
        }
    if blocker_count > 0 and feasible_count == 0 and unknown_count == 0 and skipped_count == 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "diagnostic_group_packing_infeasible",
            "recommendation": "Runtime blocker samples are exact-infeasible; keep as diagnostic evidence until proof semantics are promoted.",
        }
    if feasible_count > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "diagnostic_group_packing_feasible",
            "recommendation": "At least one failed-anchor group packs exactly; focus on greedy/order repair rather than elimination.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "diagnostic_group_packing_mixed_or_incomplete",
        "recommendation": "Runtime group-packing evidence is mixed or incomplete; inspect skipped/unknown samples before promotion.",
    }


def _disabled_probe(
    *,
    sample_limit: int,
    time_limit_seconds: float,
    max_candidates: int,
) -> Dict[str, Any]:
    return {
        "enabled": False,
        "sample_limit": int(sample_limit),
        "time_limit_seconds": float(time_limit_seconds),
        "max_candidates": int(max_candidates),
        "sample_count": 0,
        "feasible_count": 0,
        "infeasible_count": 0,
        "unknown_count": 0,
        "skipped_count": 0,
        "feasible_found": False,
        "samples": [],
    }


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    failed_anchor_sample_count: int,
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
            "failed_anchor_samples_present",
            "pass" if failed_anchor_sample_count > 0 else "fail",
            f"failed_anchor_sample_count={int(failed_anchor_sample_count)}",
        ),
        _check(
            "diagnostic_evaluated",
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


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
