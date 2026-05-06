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
from src.search.phase3b_start_compatibility import _build_portfolio_probe

START_REPAIR_PROFILER_SOURCE = "phase3b_start_repair_profiler_v1"
DEFAULT_CAMPAIGN_STATE_PATH = Path("data/checkpoints/exact_campaign_state.json")
DEFAULT_CANDIDATE = "69x19"


def build_phase3b_start_repair_profile(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 8,
    max_window_size: int = 3,
    max_attempts_per_sample: int = 64,
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
        "recommendation": "Start-repair profiler has not run.",
    }
    portfolio_probe: Dict[str, Any] = _disabled_portfolio_probe(
        sample_limit=sample_limit,
        max_window_size=max_window_size,
        max_attempts_per_sample=max_attempts_per_sample,
    )
    timing: Dict[str, float] = {}
    model_error: Optional[str] = None
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before start-repair profiling.",
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
    elif not failed_anchor_samples:
        status.update(
            {
                "completed": True,
                "outcome": "start_failure_samples_missing",
                "recommendation": "Candidate has no failed-anchor samples; rerun B5A with failed-anchor sampling enabled.",
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
            portfolio_probe = _build_portfolio_probe(
                model,
                failure_attribution=failure_attribution,
                sample_limit=int(sample_limit),
                max_window_size=int(max_window_size),
                max_attempts_per_sample=int(max_attempts_per_sample),
            )
            timing["portfolio_probe_seconds"] = float(time.perf_counter() - probe_started)
            status.update(_status_from_probe(portfolio_probe))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Start-repair profiler failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    campaign_state_unchanged = before_hash == after_hash
    return {
        "metadata": {
            "source": START_REPAIR_PROFILER_SOURCE,
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
            "max_window_size": int(max_window_size),
            "max_attempts_per_sample": int(max_attempts_per_sample),
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
            "failure_reason_counts": dict(
                failure_attribution.get("failure_reason_counts", {})
            )
            if isinstance(failure_attribution.get("failure_reason_counts"), Mapping)
            else {},
        },
        "status": status,
        "portfolio_probe": portfolio_probe,
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


def render_phase3b_start_repair_profile_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("portfolio_probe"))
    lines = [
        "# Phase 3B Start-Repair Profile",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Campaign state unchanged: {bool(report.get('campaign_state_unchanged', False))}",
        "",
        "## Portfolio Probe",
        "",
        f"- Samples: {probe.get('sample_count', 0)}",
        f"- Success: {probe.get('success_count', 0)}",
        f"- Max window size: {probe.get('max_window_size', 0)}",
        f"- Max attempts per sample: {probe.get('max_attempts_per_sample', 0)}",
    ]
    samples = [
        sample for sample in list(probe.get("samples", [])) if isinstance(sample, Mapping)
    ]
    if samples:
        lines.extend(
            [
                "",
                "## Samples",
                "",
                "| Anchor | Success | Attempts | Window | Group Order | Pose Orderings | Top Failure |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for sample in samples:
            top_failure = ""
            failures = [
                entry
                for entry in list(sample.get("top_failed_attempt_reasons", []))
                if isinstance(entry, Mapping)
            ]
            if failures:
                first = failures[0]
                top_failure = (
                    f"{first.get('group_id')}:{first.get('failure_reason')} "
                    f"x{first.get('count')}"
                )
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(sample.get("anchor_idx")),
                        _markdown_cell(sample.get("success")),
                        _markdown_cell(sample.get("attempt_count")),
                        _markdown_cell(sample.get("window_size")),
                        _markdown_cell(sample.get("group_order")),
                        _markdown_cell(",".join(str(item) for item in list(sample.get("pose_orderings", [])))),
                        _markdown_cell(top_failure),
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


def render_phase3b_start_repair_profile_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("portfolio_probe"))
    lines = [
        "Phase 3B start-repair profile",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"campaign_state_unchanged={bool(report.get('campaign_state_unchanged', False))}",
        (
            "portfolio_probe "
            f"samples={probe.get('sample_count', 0)} "
            f"success={probe.get('success_count', 0)} "
            f"max_window_size={probe.get('max_window_size', 0)} "
            f"max_attempts_per_sample={probe.get('max_attempts_per_sample', 0)}"
        ),
    ]
    for sample in list(probe.get("samples", [])):
        if not isinstance(sample, Mapping):
            continue
        lines.append(
            "sample "
            f"anchor={sample.get('anchor_idx')} "
            f"success={bool(sample.get('success', False))} "
            f"attempts={sample.get('attempt_count')} "
            f"window={sample.get('window_size')} "
            f"group_order={sample.get('group_order')} "
            f"pose_orderings={','.join(str(item) for item in list(sample.get('pose_orderings', [])))}"
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


def _status_from_probe(probe: Mapping[str, Any]) -> Dict[str, Any]:
    sample_count = int(probe.get("sample_count", 0))
    success_count = int(probe.get("success_count", 0))
    if sample_count <= 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_samples_evaluated",
            "recommendation": "No failed-anchor samples were evaluated; increase sample_limit only in a workspace.",
        }
    if success_count > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "start_repair_candidate_found",
            "recommendation": "Portfolio probe found at least one start-repair candidate; inspect the successful sample before changing runtime behavior.",
        }
    max_attempts_reached = sum(
        1
        for sample in list(probe.get("samples", []))
        if isinstance(sample, Mapping) and bool(sample.get("max_attempts_reached", False))
    )
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "start_repair_not_found_in_budget",
        "recommendation": (
            "No repair found within the diagnostic budget; broaden window/attempts "
            "only in workspace diagnostics."
        ),
        "max_attempts_reached_sample_count": int(max_attempts_reached),
    }


def _disabled_portfolio_probe(
    *,
    sample_limit: int,
    max_window_size: int,
    max_attempts_per_sample: int,
) -> Dict[str, Any]:
    return {
        "enabled": False,
        "sample_limit": int(sample_limit),
        "max_window_size": int(max_window_size),
        "max_attempts_per_sample": int(max_attempts_per_sample),
        "sample_count": 0,
        "success_count": 0,
        "success_found": False,
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
            "portfolio_probe_evaluated",
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
