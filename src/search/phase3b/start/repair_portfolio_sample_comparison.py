from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src.search.exact_campaign import now_iso

START_REPAIR_PORTFOLIO_SAMPLE_COMPARISON_SOURCE = (
    "phase3b_start_repair_portfolio_sample_comparison_v1"
)


def build_phase3b_start_repair_portfolio_sample_comparison(
    workspace_root: Path,
    *,
    start_compatibility_path: Optional[Path] = None,
) -> Dict[str, Any]:
    workspace_root = Path(workspace_root).resolve()
    started = time.perf_counter()
    paths = _paths(workspace_root, start_compatibility_path)
    operator_summary, operator_error = _load_json(paths["operator_summary"])
    start_compat, start_compat_error = _load_json(paths["start_compatibility_samples"])
    baseline_counts = _baseline_counts(operator_summary)
    sample_surface = _sample_surface(start_compat)
    status = _status(operator_error, start_compat_error, baseline_counts, sample_surface)
    return {
        "metadata": {
            "source": START_REPAIR_PORTFOLIO_SAMPLE_COMPARISON_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "portfolio_sample_comparison_report_only_not_proof_source",
            "solver_invoked": False,
        },
        "paths": {key: str(value) for key, value in paths.items()},
        "status": status,
        "baseline_b5a_portfolio": {
            "failure_reason_counts": baseline_counts,
            "unknown_count": int(baseline_counts.get("coordinate_validation_unknown", 0) or 0),
        },
        "rerun_start_compatibility_portfolio": sample_surface,
        "checks": _checks(status, operator_error, start_compat_error),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }


def render_phase3b_start_repair_portfolio_sample_comparison_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    baseline = _mapping(report.get("baseline_b5a_portfolio"))
    rerun = _mapping(report.get("rerun_start_compatibility_portfolio"))
    lines = [
        "# Phase 3B Start-Repair Portfolio Sample Comparison",
        "",
        f"- Outcome: {_markdown_cell(status.get('outcome'))}",
        f"- Runtime promotion ready: {_markdown_cell(status.get('runtime_promotion_ready'))}",
        f"- Recommendation: {_markdown_cell(status.get('recommendation'))}",
        "",
        "## Counts",
        "",
        f"- Baseline B5A portfolio: {_markdown_cell(baseline.get('failure_reason_counts'))}",
        f"- Rerun portfolio: {_markdown_cell(rerun.get('failure_reason_counts'))}",
        f"- Rerun sample count: {_markdown_cell(rerun.get('sample_count'))}",
        "",
        "## Rerun Unknown Samples",
        "",
        "| Anchor | Ordering | Status | Wall time | Deterministic time |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in list(rerun.get("unknown_samples", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("anchor_idx")),
                    _markdown_cell(entry.get("ordering")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("wall_time")),
                    _markdown_cell(entry.get("deterministic_time")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def render_phase3b_start_repair_portfolio_sample_comparison_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    baseline = _mapping(report.get("baseline_b5a_portfolio"))
    rerun = _mapping(report.get("rerun_start_compatibility_portfolio"))
    return "\n".join(
        [
            "Phase 3B start-repair portfolio sample comparison",
            f"outcome={status.get('outcome')}",
            f"runtime_promotion_ready={status.get('runtime_promotion_ready')}",
            f"baseline_counts={baseline.get('failure_reason_counts')}",
            f"rerun_counts={rerun.get('failure_reason_counts')}",
            f"rerun_unknown_samples={rerun.get('unknown_samples')}",
            f"recommendation={status.get('recommendation')}",
        ]
    ) + "\n"


def _paths(root: Path, start_compatibility_path: Optional[Path]) -> Dict[str, Path]:
    return {
        "operator_summary": root
        / ".artifacts/phase3b_b5_anchor_sprint/operator_summary.json",
        "start_compatibility_samples": Path(start_compatibility_path).resolve()
        if start_compatibility_path
        else root
        / ".artifacts/phase3b_start_compatibility_selected_block_samples_20260422/start_compatibility_67x13.json",
    }


def _baseline_counts(operator_summary: Optional[Mapping[str, Any]]) -> Dict[str, int]:
    aggregate = _mapping(_mapping(operator_summary.get("telemetry")).get("aggregate")) if operator_summary else {}
    return {
        str(key): int(value)
        for key, value in dict(
            _mapping(aggregate.get("ghost_aware_pose_order_portfolio_failure_reason_counts"))
        ).items()
    }


def _sample_surface(start_compat: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    warm = _mapping(_mapping(start_compat.get("diagnostics")).get("warm_start")) if start_compat else {}
    samples = [
        entry
        for entry in list(warm.get("ghost_aware_pose_order_portfolio_failure_samples", []))
        if isinstance(entry, Mapping)
    ]
    counts = dict(Counter(str(entry.get("failure_reason") or "unknown") for entry in samples))
    unknown_samples = [
        _compact_sample(entry)
        for entry in samples
        if str(entry.get("failure_reason")) == "coordinate_validation_unknown"
    ]
    return {
        "failure_reason_counts": counts,
        "sample_count": len(samples),
        "unknown_count": int(counts.get("coordinate_validation_unknown", 0)),
        "unknown_samples": unknown_samples,
    }


def _compact_sample(entry: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "anchor_idx": entry.get("anchor_idx"),
        "ordering": entry.get("ordering"),
        "source": entry.get("source"),
        "status": entry.get("status"),
        "reason": entry.get("reason"),
        "forced_slot_field_count": entry.get("forced_slot_field_count"),
        "wall_time": entry.get("wall_time"),
        "deterministic_time": entry.get("deterministic_time"),
        "branches": entry.get("branches"),
        "conflicts": entry.get("conflicts"),
    }


def _status(
    operator_error: Optional[str],
    start_compat_error: Optional[str],
    baseline_counts: Mapping[str, int],
    sample_surface: Mapping[str, Any],
) -> Dict[str, Any]:
    if operator_error:
        outcome = "missing_b5a_operator_summary"
    elif start_compat_error:
        outcome = "missing_start_compatibility_sample_rerun"
    else:
        baseline_unknown = int(baseline_counts.get("coordinate_validation_unknown", 0) or 0)
        rerun_unknown = int(sample_surface.get("unknown_count", 0) or 0)
        if baseline_unknown > 0 and rerun_unknown < baseline_unknown:
            outcome = "portfolio_unknowns_reduced_by_bounded_rerun"
        elif rerun_unknown > 0:
            outcome = "portfolio_unknowns_reproduced_with_samples"
        else:
            outcome = "portfolio_unknowns_not_reproduced"
    return {
        "completed": True,
        "outcome": outcome,
        "runtime_promotion_ready": False,
        "proof_source": False,
        "recommendation": (
            "Use the rerun samples to target anchor/order-specific diagnostics; do not promote "
            "portfolio rerun results as proof or final B5A readiness."
        ),
    }


def _checks(
    status: Mapping[str, Any],
    operator_error: Optional[str],
    start_compat_error: Optional[str],
) -> List[Dict[str, str]]:
    return [
        _check("report_only_semantics", "pass", "report compares existing artifacts and invokes no solver"),
        _check("operator_summary_present", "pass" if operator_error is None else "fail", str(operator_error)),
        _check(
            "start_compatibility_sample_rerun_present",
            "pass" if start_compat_error is None else "fail",
            str(start_compat_error),
        ),
        _check(
            "runtime_promotion_guard",
            "pass" if not bool(status.get("runtime_promotion_ready")) else "fail",
            "runtime_promotion_ready remains false",
        ),
    ]


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
