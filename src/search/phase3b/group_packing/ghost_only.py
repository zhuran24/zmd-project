from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    MasterPlacementModel,
)
from src.search.benders_loop import create_exact_search_session
from src.search.exact_campaign import now_iso
from src.search.phase3b.start.compatibility import (
    _greedy_select_count,
    _solve_group_packing_feasibility,
)

GROUP_PACKING_GHOST_ONLY_SOURCE = "phase3b_group_packing_ghost_only_verifier_v1"
DEFAULT_CAMPAIGN_STATE_PATH = Path("data/checkpoints/exact_campaign_state.json")
DEFAULT_CANDIDATE = "69x19"


def build_phase3b_group_packing_ghost_only_verifier(
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
        "recommendation": "Ghost-only group-packing verifier has not run.",
    }
    verifier: Dict[str, Any] = _disabled_verifier(
        sample_limit=sample_limit,
        time_limit_seconds=time_limit_seconds,
        max_candidates=max_candidates,
    )
    timing: Dict[str, float] = {}
    model_error: Optional[str] = None
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before ghost-only verification.",
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
            verifier_started = time.perf_counter()
            verifier = _build_ghost_only_verifier(
                model,
                failure_attribution=failure_attribution,
                sample_limit=int(sample_limit),
                time_limit_seconds=float(time_limit_seconds),
                max_candidates=int(max_candidates),
            )
            timing["ghost_only_verifier_seconds"] = float(
                time.perf_counter() - verifier_started
            )
            status.update(_status_from_verifier(verifier))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Ghost-only verifier failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    campaign_state_unchanged = before_hash == after_hash
    return {
        "metadata": {
            "source": GROUP_PACKING_GHOST_ONLY_SOURCE,
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
            "failed_anchor_count": int(
                failure_attribution.get("failed_anchor_count", 0)
            )
            if failure_attribution
            else 0,
            "failed_anchor_sample_count": len(failed_anchor_samples),
        },
        "status": status,
        "ghost_only_verifier": verifier,
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


def render_phase3b_group_packing_ghost_only_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    verifier = _mapping(report.get("ghost_only_verifier"))
    lines = [
        "# Phase 3B Ghost-Only Group-Packing Verifier",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Campaign state unchanged: {bool(report.get('campaign_state_unchanged', False))}",
        "",
        "## Summary",
        "",
        f"- Samples: {verifier.get('sample_count', 0)}",
        f"- Ghost-only feasible: {verifier.get('feasible_count', 0)}",
        f"- Ghost-only infeasible: {verifier.get('infeasible_count', 0)}",
        f"- Unknown: {verifier.get('unknown_count', 0)}",
        f"- Skipped: {verifier.get('skipped_count', 0)}",
    ]
    samples = [
        sample
        for sample in list(verifier.get("samples", []))
        if isinstance(sample, Mapping)
    ]
    if samples:
        lines.extend(
            [
                "",
                "## Samples",
                "",
                "| Anchor | Group | Required | After Ghost | Greedy | Feasible | Status |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for sample in samples:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(sample.get("anchor_idx")),
                        _markdown_cell(sample.get("group_id")),
                        _markdown_cell(sample.get("required_count")),
                        _markdown_cell(sample.get("surviving_after_blocked_count")),
                        _markdown_cell(sample.get("ghost_only_greedy_selected_count")),
                        _markdown_cell(sample.get("ghost_only_feasible")),
                        _markdown_cell(sample.get("solver_status")),
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


def render_phase3b_group_packing_ghost_only_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    verifier = _mapping(report.get("ghost_only_verifier"))
    lines = [
        "Phase 3B ghost-only group-packing verifier",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"campaign_state_unchanged={bool(report.get('campaign_state_unchanged', False))}",
        (
            "verifier "
            f"samples={verifier.get('sample_count', 0)} "
            f"feasible={verifier.get('feasible_count', 0)} "
            f"infeasible={verifier.get('infeasible_count', 0)} "
            f"unknown={verifier.get('unknown_count', 0)} "
            f"skipped={verifier.get('skipped_count', 0)}"
        ),
    ]
    for sample in list(verifier.get("samples", [])):
        if not isinstance(sample, Mapping):
            continue
        lines.append(
            "sample "
            f"anchor={sample.get('anchor_idx')} "
            f"group={sample.get('group_id')} "
            f"required={sample.get('required_count')} "
            f"after_ghost={sample.get('surviving_after_blocked_count')} "
            f"greedy={sample.get('ghost_only_greedy_selected_count')} "
            f"feasible={sample.get('ghost_only_feasible')} "
            f"status={sample.get('solver_status')}"
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


def _build_ghost_only_verifier(
    model: MasterPlacementModel,
    *,
    failure_attribution: Mapping[str, Any],
    sample_limit: int,
    time_limit_seconds: float,
    max_candidates: int,
) -> Dict[str, Any]:
    sample_limit = max(0, int(sample_limit))
    time_limit_seconds = max(0.01, float(time_limit_seconds))
    max_candidates = max(1, int(max_candidates))
    payload: Dict[str, Any] = _disabled_verifier(
        sample_limit=sample_limit,
        time_limit_seconds=time_limit_seconds,
        max_candidates=max_candidates,
    )
    payload["enabled"] = bool(sample_limit > 0)
    if sample_limit <= 0:
        return payload
    raw_samples = [
        entry
        for entry in list(failure_attribution.get("failed_anchor_samples", []))
        if isinstance(entry, Mapping)
    ][:sample_limit]
    candidates_by_group = {
        str(group["group_id"]): model._candidate_pose_indices_for_group(group)
        for group in model._mandatory_groups
    }
    ordered_groups = model._ordered_mandatory_groups_for_greedy(candidates_by_group)
    for raw_sample in raw_samples:
        sample_result = _verify_ghost_only_sample(
            model,
            sample=raw_sample,
            ordered_groups=ordered_groups,
            candidates_by_group=candidates_by_group,
            time_limit_seconds=time_limit_seconds,
            max_candidates=max_candidates,
        )
        payload["samples"].append(sample_result)
        if bool(sample_result.get("skipped", False)):
            payload["skipped_count"] = int(payload["skipped_count"]) + 1
        elif sample_result.get("ghost_only_feasible") is True:
            payload["feasible_count"] = int(payload["feasible_count"]) + 1
        elif sample_result.get("ghost_only_feasible") is False:
            payload["infeasible_count"] = int(payload["infeasible_count"]) + 1
        else:
            payload["unknown_count"] = int(payload["unknown_count"]) + 1
    payload["sample_count"] = len(payload["samples"])
    payload["feasible_found"] = int(payload["feasible_count"]) > 0
    return payload


def _verify_ghost_only_sample(
    model: MasterPlacementModel,
    *,
    sample: Mapping[str, Any],
    ordered_groups: Sequence[Mapping[str, Any]],
    candidates_by_group: Mapping[str, Sequence[int]],
    time_limit_seconds: float,
    max_candidates: int,
) -> Dict[str, Any]:
    try:
        anchor_idx = int(sample.get("anchor_idx"))
        failed_position = int(sample.get("first_failed_group_position"))
    except Exception:
        return {
            "anchor_idx": sample.get("anchor_idx"),
            "skipped": True,
            "skip_reason": "missing_anchor_or_position",
        }
    if anchor_idx < 0 or anchor_idx >= len(model._ghost_domains):
        return {
            "anchor_idx": int(anchor_idx),
            "skipped": True,
            "skip_reason": "anchor_index_out_of_range",
        }
    if failed_position < 0 or failed_position >= len(ordered_groups):
        return {
            "anchor_idx": int(anchor_idx),
            "skipped": True,
            "skip_reason": "failed_group_position_out_of_range",
        }

    target_group = dict(ordered_groups[int(failed_position)])
    group_id = str(target_group.get("group_id", ""))
    tpl = str(target_group.get("facility_type", ""))
    required_count = int(target_group.get("count", 0))
    domain = model._ghost_domains[int(anchor_idx)]
    blocked_cells = {
        (int(cell[0]), int(cell[1]))
        for cell in list(domain.get("cells", []))
    }
    candidate_indices = [int(idx) for idx in candidates_by_group.get(group_id, [])]
    surviving_after_blocked = [
        int(idx)
        for idx in candidate_indices
        if blocked_cells.isdisjoint(model._pose_cells(tpl, int(idx)))
    ]
    greedy_selected_count = _greedy_select_count(
        model,
        tpl=tpl,
        candidate_indices=surviving_after_blocked,
        committed_cells=set(blocked_cells),
    )
    base = {
        "anchor_idx": int(anchor_idx),
        "group_id": group_id,
        "facility_type": tpl,
        "required_count": int(required_count),
        "candidate_count": int(len(candidate_indices)),
        "surviving_after_blocked_count": int(len(surviving_after_blocked)),
        "ghost_only_greedy_selected_count": int(greedy_selected_count),
        "skipped": False,
    }
    if greedy_selected_count >= required_count:
        return {
            **base,
            "ghost_only_feasible": True,
            "solver_status": "GREEDY_FEASIBLE_WITNESS",
            "selected_count": int(greedy_selected_count),
            "candidate_count_considered": int(len(surviving_after_blocked)),
        }
    if len(surviving_after_blocked) > int(max_candidates):
        return {
            **base,
            "ghost_only_feasible": None,
            "solver_status": "SKIPPED_CANDIDATE_LIMIT_EXCEEDED",
            "skipped": True,
            "skip_reason": "candidate_limit_exceeded",
            "max_candidates": int(max_candidates),
        }
    exact_result = _solve_group_packing_feasibility(
        model,
        tpl=tpl,
        candidate_indices=surviving_after_blocked,
        required_count=required_count,
        time_limit_seconds=time_limit_seconds,
    )
    return {
        **base,
        "ghost_only_feasible": exact_result.get("exact_feasible"),
        **exact_result,
    }


def _status_from_verifier(verifier: Mapping[str, Any]) -> Dict[str, Any]:
    sample_count = int(verifier.get("sample_count", 0))
    feasible_count = int(verifier.get("feasible_count", 0))
    infeasible_count = int(verifier.get("infeasible_count", 0))
    unknown_count = int(verifier.get("unknown_count", 0))
    skipped_count = int(verifier.get("skipped_count", 0))
    if sample_count <= 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_samples_evaluated",
            "recommendation": "No failed-anchor samples were evaluated; increase sample_limit only in a workspace.",
        }
    if feasible_count > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "ghost_only_feasible_counterexample_found",
            "recommendation": "At least one failed group is feasible with only the ghost cells blocked; do not promote prefix-conditioned evidence to terminal proof.",
        }
    if infeasible_count == sample_count and unknown_count == 0 and skipped_count == 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "ghost_only_uniformly_infeasible",
            "recommendation": "Sampled groups are infeasible even without prefix cells; this may support a future terminal-safe proof path.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "ghost_only_mixed_or_incomplete",
        "recommendation": "Ghost-only evidence is mixed or incomplete; inspect unknown/skipped samples before proof work.",
    }


def _disabled_verifier(
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
            "ghost_only_verifier_evaluated",
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
