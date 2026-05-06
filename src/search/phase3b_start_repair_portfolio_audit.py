from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from src.search.exact_campaign import now_iso

START_REPAIR_PORTFOLIO_AUDIT_SOURCE = "phase3b_start_repair_portfolio_audit_v1"


def build_phase3b_start_repair_portfolio_audit(
    project_root: Path,
    *,
    workspace_root: Optional[Path] = None,
    candidate: str = "67x13",
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    workspace_root = Path(workspace_root or project_root).resolve()
    started = time.perf_counter()
    paths = _paths(workspace_root)
    telemetry, telemetry_error = _load_json(paths["telemetry"])
    evidence, evidence_error = _load_json(paths["start_repair_evidence_surface"])
    candidate_result = _first_candidate_result(telemetry)
    proof = _candidate_proof_summary(candidate_result)
    warm_start = _mapping(proof.get("master_warm_start"))
    final_attr = _mapping(proof.get("master_start_failure_attribution"))
    evidence_status = _mapping(evidence.get("status")) if evidence else {}
    final_counts = dict(
        _mapping(evidence_status.get("final_failure_reason_counts"))
        or _mapping(final_attr.get("failure_reason_counts"))
    )
    portfolio_counts = dict(
        _mapping(evidence_status.get("portfolio_failure_reason_counts"))
        or _mapping(warm_start.get("ghost_aware_pose_order_portfolio_failure_reason_counts"))
    )
    samples = _sample_surface(final_attr=final_attr, warm_start=warm_start)
    profiler_surface = _profiler_surface(paths["start_repair_profiler_dir"], candidate)
    unknown_surface = _unknown_surface(portfolio_counts, samples, profiler_surface)
    status = _status(telemetry_error, evidence_error, portfolio_counts, samples, profiler_surface)
    return {
        "metadata": {
            "source": START_REPAIR_PORTFOLIO_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "start_repair_portfolio_audit_report_only_not_proof_source",
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "workspace_root": str(workspace_root),
            **{key: str(value) for key, value in paths.items()},
        },
        "candidate": {
            "key": str(candidate),
            "telemetry_candidate_key": _candidate_key(candidate_result),
        },
        "status": status,
        "final_start_attribution": {
            "failure_reason_counts": final_counts,
            "attempted_anchor_count": int(final_attr.get("attempted_anchor_count", 0) or 0),
            "failed_anchor_count": int(final_attr.get("failed_anchor_count", 0) or 0),
        },
        "pose_order_portfolio": {
            "failure_reason_counts": portfolio_counts,
            "attempt_count": int(
                warm_start.get("ghost_aware_pose_order_portfolio_attempt_count", 0) or 0
            ),
            "failed_anchor_count": int(
                warm_start.get("ghost_aware_pose_order_portfolio_failed_anchor_count", 0) or 0
            ),
            "success": bool(warm_start.get("ghost_aware_pose_order_portfolio_success", False)),
            "selected_ordering": warm_start.get("ghost_aware_pose_order_portfolio_selected_ordering"),
        },
        "sample_surface": samples,
        "portfolio_unknowns": unknown_surface,
        "start_repair_profiler": profiler_surface,
        "checks": _checks(status, telemetry_error, evidence_error),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }


def render_phase3b_start_repair_portfolio_audit_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    final_attr = _mapping(report.get("final_start_attribution"))
    portfolio = _mapping(report.get("pose_order_portfolio"))
    unknowns = _mapping(report.get("portfolio_unknowns"))
    profiler = _mapping(report.get("start_repair_profiler"))
    lines = [
        "# Phase 3B Start-Repair Portfolio Audit",
        "",
        f"- Outcome: {_markdown_cell(status.get('outcome'))}",
        f"- Runtime promotion ready: {_markdown_cell(status.get('runtime_promotion_ready'))}",
        f"- Recommendation: {_markdown_cell(status.get('recommendation'))}",
        "",
        "## Layer Counts",
        "",
        f"- Final start attribution: {_markdown_cell(final_attr.get('failure_reason_counts'))}",
        f"- Pose-order portfolio: {_markdown_cell(portfolio.get('failure_reason_counts'))}",
        "",
        "## Portfolio Unknowns",
        "",
        f"- Count: {_markdown_cell(unknowns.get('count'))}",
        f"- Localized: {_markdown_cell(unknowns.get('localized'))}",
        f"- Diagnosis: {_markdown_cell(unknowns.get('diagnosis'))}",
        "",
        "## Profiler Evidence",
        "",
        f"- Current candidate profiles: {_markdown_cell(profiler.get('current_candidate_profile_count'))}",
        f"- Stale profile candidates: {_markdown_cell(profiler.get('stale_candidate_keys'))}",
    ]
    return "\n".join(lines) + "\n"


def render_phase3b_start_repair_portfolio_audit_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    final_attr = _mapping(report.get("final_start_attribution"))
    portfolio = _mapping(report.get("pose_order_portfolio"))
    unknowns = _mapping(report.get("portfolio_unknowns"))
    profiler = _mapping(report.get("start_repair_profiler"))
    return "\n".join(
        [
            "Phase 3B start-repair portfolio audit",
            f"outcome={status.get('outcome')}",
            f"runtime_promotion_ready={status.get('runtime_promotion_ready')}",
            f"final_failure_reason_counts={final_attr.get('failure_reason_counts')}",
            f"portfolio_failure_reason_counts={portfolio.get('failure_reason_counts')}",
            f"portfolio_unknown_count={unknowns.get('count')}",
            f"portfolio_unknown_diagnosis={unknowns.get('diagnosis')}",
            f"current_candidate_profile_count={profiler.get('current_candidate_profile_count')}",
            f"recommendation={status.get('recommendation')}",
        ]
    ) + "\n"


def _paths(root: Path) -> Dict[str, Path]:
    return {
        "telemetry": root / "data/checkpoints/exact_campaign_telemetry.json",
        "start_repair_evidence_surface": root
        / ".artifacts/phase3b_start_repair_evidence_surface/start_repair_evidence_surface.json",
        "start_repair_profiler_dir": root / ".artifacts/phase3b_start_repair_profiler",
    }


def _sample_surface(*, final_attr: Mapping[str, Any], warm_start: Mapping[str, Any]) -> Dict[str, Any]:
    final_samples = [entry for entry in list(final_attr.get("failed_anchor_samples", [])) if isinstance(entry, Mapping)]
    pose_samples = [
        entry
        for entry in list(warm_start.get("ghost_aware_pose_order_validation_rejection_samples", []))
        if isinstance(entry, Mapping)
    ]
    portfolio_samples = [
        entry
        for entry in list(warm_start.get("ghost_aware_pose_order_portfolio_failure_samples", []))
        if isinstance(entry, Mapping)
    ]
    coordinate_samples = [
        entry
        for entry in list(warm_start.get("ghost_aware_coordinate_validation_rejection_samples", []))
        if isinstance(entry, Mapping)
    ]
    return {
        "final_failed_anchor_sample_count": len(final_samples),
        "final_failed_anchor_sample_reason_counts": dict(
            Counter(str(entry.get("failure_reason") or "unknown") for entry in final_samples)
        ),
        "pose_order_validation_rejection_sample_count": len(pose_samples),
        "pose_order_validation_rejection_status_counts": dict(
            Counter(str(entry.get("status") or "unknown") for entry in pose_samples)
        ),
        "pose_order_portfolio_failure_sample_count": len(portfolio_samples),
        "pose_order_portfolio_failure_reason_counts": dict(
            Counter(str(entry.get("failure_reason") or "unknown") for entry in portfolio_samples)
        ),
        "coordinate_validation_rejection_sample_count": len(coordinate_samples),
        "coordinate_validation_rejection_status_counts": dict(
            Counter(str(entry.get("status") or "unknown") for entry in coordinate_samples)
        ),
    }


def _unknown_surface(
    portfolio_counts: Mapping[str, Any],
    samples: Mapping[str, Any],
    profiler: Mapping[str, Any],
) -> Dict[str, Any]:
    unknown_count = int(portfolio_counts.get("coordinate_validation_unknown", 0) or 0)
    pose_sample_count = int(samples.get("pose_order_validation_rejection_sample_count", 0) or 0)
    portfolio_sample_count = int(samples.get("pose_order_portfolio_failure_sample_count", 0) or 0)
    current_profiles = int(profiler.get("current_candidate_profile_count", 0) or 0)
    if unknown_count <= 0:
        diagnosis = "no_portfolio_unknowns_present"
        localized = True
    elif portfolio_sample_count <= 0 and pose_sample_count <= 0:
        diagnosis = "portfolio_unknowns_unlocalized_no_rejection_samples"
        localized = False
    elif current_profiles <= 0:
        diagnosis = "portfolio_unknowns_have_samples_but_no_current_start_repair_profile"
        localized = False
    else:
        diagnosis = "portfolio_unknowns_have_local_evidence_for_review"
        localized = True
    return {
        "count": unknown_count,
        "localized": bool(localized),
        "diagnosis": diagnosis,
        "pose_order_validation_rejection_sample_count": pose_sample_count,
        "pose_order_portfolio_failure_sample_count": portfolio_sample_count,
        "current_candidate_profile_count": current_profiles,
    }


def _profiler_surface(profiler_dir: Path, candidate: str) -> Dict[str, Any]:
    profiles: List[Dict[str, Any]] = []
    if profiler_dir.exists():
        for path in sorted(profiler_dir.glob("*.json")):
            report, error = _load_json(path)
            entry = {
                "path": str(path),
                "load_error": error,
                "candidate_key": None,
                "outcome": None,
            }
            if report:
                entry["candidate_key"] = _mapping(report.get("candidate")).get("key")
                entry["outcome"] = _mapping(report.get("status")).get("outcome")
            profiles.append(entry)
    current = [entry for entry in profiles if entry.get("candidate_key") == candidate]
    stale_keys = sorted(
        {
            str(entry.get("candidate_key"))
            for entry in profiles
            if entry.get("candidate_key") and entry.get("candidate_key") != candidate
        }
    )
    return {
        "present": profiler_dir.exists(),
        "profile_count": len(profiles),
        "current_candidate_profile_count": len(current),
        "current_candidate_profiles": current,
        "stale_candidate_keys": stale_keys,
        "stale_profile_count": max(0, len(profiles) - len(current)),
    }


def _status(
    telemetry_error: Optional[str],
    evidence_error: Optional[str],
    portfolio_counts: Mapping[str, Any],
    samples: Mapping[str, Any],
    profiler: Mapping[str, Any],
) -> Dict[str, Any]:
    if telemetry_error:
        outcome = "missing_telemetry"
    elif evidence_error:
        outcome = "missing_start_repair_evidence_surface"
    elif int(portfolio_counts.get("coordinate_validation_unknown", 0) or 0) > 0 and int(
        samples.get("pose_order_validation_rejection_sample_count", 0) or 0
    ) == 0 and int(
        samples.get("pose_order_portfolio_failure_sample_count", 0) or 0
    ) == 0:
        outcome = "portfolio_unknowns_unlocalized"
    elif int(profiler.get("current_candidate_profile_count", 0) or 0) == 0:
        outcome = "current_start_repair_profile_missing"
    else:
        outcome = "portfolio_audit_ready_for_manual_review"
    return {
        "completed": True,
        "outcome": outcome,
        "runtime_promotion_ready": False,
        "proof_source": False,
        "recommendation": (
            "Run a bounded current-candidate start-repair profiler only if the next step needs "
            "sample-level localization; do not treat aggregate portfolio UNKNOWN counts as proof."
        ),
    }


def _checks(
    status: Mapping[str, Any],
    telemetry_error: Optional[str],
    evidence_error: Optional[str],
) -> List[Dict[str, str]]:
    return [
        _check("report_only_semantics", "pass", "report reads existing artifacts and invokes no solver"),
        _check("telemetry_present", "pass" if telemetry_error is None else "fail", str(telemetry_error)),
        _check(
            "start_repair_evidence_surface_present",
            "pass" if evidence_error is None else "skipped",
            str(evidence_error),
        ),
        _check(
            "runtime_promotion_guard",
            "pass" if not bool(status.get("runtime_promotion_ready")) else "fail",
            "runtime_promotion_ready remains false",
        ),
    ]


def _first_candidate_result(telemetry: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    if not telemetry:
        return {}
    for wave in list(telemetry.get("waves", [])):
        if not isinstance(wave, Mapping):
            continue
        for result in list(wave.get("candidate_results", [])):
            if isinstance(result, Mapping):
                return result
    return {}


def _candidate_proof_summary(candidate_result: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(
        candidate_result.get("proof_summary") or candidate_result.get("proof_status_summary")
    )


def _candidate_key(result: Mapping[str, Any]) -> Optional[str]:
    return str(result.get("candidate_key")) if result.get("candidate_key") else _mapping(result.get("candidate")).get("key")


def _load_json(path: Path) -> Tuple[Optional[Mapping[str, Any]], Optional[str]]:
    if not path.exists():
        return None, "missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(value, Mapping):
        return None, f"not_object:{type(value).__name__}"
    return value, None


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": check_id, "status": status, "detail": detail}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return "`" + json.dumps(value, ensure_ascii=False, sort_keys=True) + "`"
    return "`" + str(value) + "`"
