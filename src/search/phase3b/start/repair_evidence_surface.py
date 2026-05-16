from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

START_REPAIR_EVIDENCE_SURFACE_SOURCE = "phase3b_start_repair_evidence_surface_v1"


def build_phase3b_start_repair_evidence_surface(
    project_root: Path,
    *,
    workspace_root: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    workspace_root = Path(workspace_root or project_root).resolve()
    started = time.perf_counter()
    paths = _paths(workspace_root)
    telemetry, telemetry_error = _load_json(paths["telemetry"])
    start_compat, start_compat_error = _load_json(paths["start_compatibility_current"])
    failed_inventory, failed_inventory_error = _load_json(paths["failed_anchor_inventory"])
    aggregate = _mapping(telemetry.get("aggregate")) if telemetry else {}
    candidate_result = _first_candidate_result(telemetry)
    proof_summary = _candidate_proof_summary(candidate_result)
    final_attribution = _mapping(proof_summary.get("master_start_failure_attribution"))
    local_repair = _mapping(proof_summary.get("master_start_local_repair"))
    portfolio = _portfolio_surface(aggregate)
    final_surface = _final_start_surface(final_attribution)
    stale_inventory = _stale_inventory_surface(failed_inventory, failed_inventory_error)
    status = _status(
        telemetry_error=telemetry_error,
        final_surface=final_surface,
        portfolio=portfolio,
        local_repair=local_repair,
        start_compat=start_compat,
    )
    return {
        "metadata": {
            "source": START_REPAIR_EVIDENCE_SURFACE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "start_repair_evidence_surface_report_only_not_proof_source",
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "workspace_root": str(workspace_root),
            **{key: str(value) for key, value in paths.items()},
        },
        "status": status,
        "campaign": {
            "telemetry_present": telemetry is not None,
            "telemetry_error": telemetry_error,
            "candidate_key": _candidate_key(candidate_result),
            "candidate_status": candidate_result.get("status"),
        },
        "final_start_attribution": final_surface,
        "pose_order_portfolio": portfolio,
        "local_repair": {
            "attempted": bool(local_repair.get("local_repair_attempted", False)),
            "success": bool(local_repair.get("local_repair_success", False)),
            "attempt_count": int(local_repair.get("local_repair_attempt_count", 0) or 0),
            "portfolio_attempt_count": int(
                local_repair.get("local_repair_portfolio_attempt_count", 0) or 0
            ),
            "trigger_reason": local_repair.get("local_repair_trigger_reason"),
        },
        "start_compatibility": {
            "present": start_compat is not None,
            "load_error": start_compat_error,
            "status": _mapping(start_compat.get("status")) if start_compat else {},
        },
        "failed_anchor_inventory": stale_inventory,
        "next_branch": {
            "name": "current_source_start_repair_pose_order_portfolio",
            "recommendation": (
                "Build a current-source start-repair / pose-order portfolio report that "
                "preserves final attribution counts separately from portfolio aggregate counts."
            ),
            "do_not_do": [
                "Do not use stale 69x19 or old 118..125 inventories as current evidence.",
                "Do not rerun B5A blindly.",
                "Do not promote ordering-sensitive diagnostics as proof.",
            ],
        },
        "checks": _checks(status, telemetry_error, start_compat_error),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }


def render_phase3b_start_repair_evidence_surface_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    final_surface = _mapping(report.get("final_start_attribution"))
    portfolio = _mapping(report.get("pose_order_portfolio"))
    repair = _mapping(report.get("local_repair"))
    lines = [
        "# Phase 3B Start-Repair Evidence Surface",
        "",
        f"- Outcome: {_markdown_cell(status.get('outcome'))}",
        f"- Runtime promotion ready: {_markdown_cell(status.get('runtime_promotion_ready'))}",
        f"- Recommendation: {_markdown_cell(status.get('recommendation'))}",
        "",
        "## Final Start Attribution",
        "",
        f"- Attempted anchors: {_markdown_cell(final_surface.get('attempted_anchor_count'))}",
        f"- Failed anchors: {_markdown_cell(final_surface.get('failed_anchor_count'))}",
        f"- Failure reason counts: {_markdown_cell(final_surface.get('failure_reason_counts'))}",
        "",
        "## Pose-Order Portfolio Aggregate",
        "",
        f"- Attempt count: {_markdown_cell(portfolio.get('attempt_count'))}",
        f"- Failed anchor count: {_markdown_cell(portfolio.get('failed_anchor_count'))}",
        f"- Failure reason counts: {_markdown_cell(portfolio.get('failure_reason_counts'))}",
        "",
        "## Local Repair",
        "",
        f"- Attempted: {_markdown_cell(repair.get('attempted'))}",
        f"- Success: {_markdown_cell(repair.get('success'))}",
        f"- Attempt count: {_markdown_cell(repair.get('attempt_count'))}",
    ]
    return "\n".join(lines) + "\n"


def render_phase3b_start_repair_evidence_surface_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    final_surface = _mapping(report.get("final_start_attribution"))
    portfolio = _mapping(report.get("pose_order_portfolio"))
    return "\n".join(
        [
            "Phase 3B start-repair evidence surface",
            f"outcome={status.get('outcome')}",
            f"runtime_promotion_ready={status.get('runtime_promotion_ready')}",
            f"final_failure_reason_counts={final_surface.get('failure_reason_counts')}",
            f"portfolio_failure_reason_counts={portfolio.get('failure_reason_counts')}",
            f"recommendation={status.get('recommendation')}",
        ]
    ) + "\n"


def _paths(root: Path) -> Dict[str, Path]:
    return {
        "telemetry": root / "data/checkpoints/exact_campaign_telemetry.json",
        "start_compatibility_current": root
        / ".artifacts/phase3b_start_compatibility_current/start_compatibility_67x13.json",
        "failed_anchor_inventory": root
        / ".artifacts/phase3b_failed_anchor_inventory_67x13_cap112_v3/failed_anchor_inventory.json",
    }


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


def _portfolio_surface(aggregate: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "attempted": int(aggregate.get("ghost_aware_pose_order_portfolio_attempted_count", 0) or 0),
        "success_count": int(aggregate.get("ghost_aware_pose_order_portfolio_success_count", 0) or 0),
        "attempt_count": int(aggregate.get("ghost_aware_pose_order_portfolio_attempt_count_sum", 0) or 0),
        "failed_anchor_count": int(
            aggregate.get("ghost_aware_pose_order_portfolio_failed_anchor_count_sum", 0) or 0
        ),
        "failure_reason_counts": dict(
            _mapping(aggregate.get("ghost_aware_pose_order_portfolio_failure_reason_counts"))
        ),
        "selected_ordering_counts": dict(
            _mapping(aggregate.get("ghost_aware_pose_order_portfolio_selected_ordering_counts"))
        ),
    }


def _candidate_proof_summary(candidate_result: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(
        candidate_result.get("proof_summary") or candidate_result.get("proof_status_summary")
    )


def _final_start_surface(final_attribution: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "attempted_anchor_count": int(final_attribution.get("attempted_anchor_count", 0) or 0),
        "failed_anchor_count": int(final_attribution.get("failed_anchor_count", 0) or 0),
        "failure_reason_counts": dict(_mapping(final_attribution.get("failure_reason_counts"))),
        "first_failed_anchor_idx": final_attribution.get("first_failed_anchor_idx"),
        "sample_count": len(list(final_attribution.get("failed_anchor_samples", []))),
    }


def _stale_inventory_surface(
    report: Optional[Mapping[str, Any]],
    error: Optional[str],
) -> Dict[str, Any]:
    if error:
        return {"present": False, "load_error": error, "current_source_safe": False}
    status = _mapping(report.get("status")) if report else {}
    candidate = _mapping(report.get("candidate")) if report else {}
    return {
        "present": report is not None,
        "load_error": None,
        "candidate_key": candidate.get("key"),
        "campaign_status": candidate.get("campaign_status"),
        "sample_count": status.get("sample_count") or status.get("blocker_count"),
        "current_source_safe": False,
        "warning": "Inventory artifact is named cap112_v3 and should not be used as current cap128 residual evidence without cross-checking.",
    }


def _status(
    *,
    telemetry_error: Optional[str],
    final_surface: Mapping[str, Any],
    portfolio: Mapping[str, Any],
    local_repair: Mapping[str, Any],
    start_compat: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    if telemetry_error:
        outcome = "missing_telemetry"
    elif not bool(local_repair.get("local_repair_attempted", False)):
        outcome = "start_repair_not_attempted_current_source"
    else:
        outcome = "start_repair_attempted_needs_review"
    return {
        "completed": True,
        "outcome": outcome,
        "final_failure_reason_counts": dict(_mapping(final_surface.get("failure_reason_counts"))),
        "portfolio_failure_reason_counts": dict(_mapping(portfolio.get("failure_reason_counts"))),
        "start_compatibility_present": start_compat is not None,
        "runtime_promotion_ready": False,
        "proof_source": False,
        "recommendation": (
            "Preserve final start attribution and portfolio aggregate as separate layers; "
            "next branch should inspect start-repair / pose-order portfolio behavior."
        ),
    }


def _checks(
    status: Mapping[str, Any],
    telemetry_error: Optional[str],
    start_compat_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        {
            "check_id": "report_only_semantics",
            "status": "pass",
            "detail": "report reads existing telemetry/artifacts and does not invoke solver",
        },
        {
            "check_id": "telemetry_present",
            "status": "pass" if telemetry_error is None else "fail",
            "detail": str(telemetry_error),
        },
        {
            "check_id": "start_compatibility_present",
            "status": "pass" if start_compat_error is None else "skipped",
            "detail": str(start_compat_error),
        },
        {
            "check_id": "runtime_promotion_guard",
            "status": "pass" if not bool(status.get("runtime_promotion_ready")) else "fail",
            "detail": "runtime_promotion_ready remains false",
        },
    ]


def _candidate_key(result: Mapping[str, Any]) -> Optional[str]:
    candidate = _mapping(result.get("candidate"))
    return candidate.get("key") or result.get("candidate_key")


def _load_json(path: Path) -> tuple[Optional[Mapping[str, Any]], Optional[str]]:
    if not path.exists():
        return None, "missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(value, Mapping):
        return None, "json_root_not_object"
    return value, None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
