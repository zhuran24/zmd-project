from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src.search.exact_campaign import now_iso

POSE_ORDER_UNKNOWN_RESOLUTION_SOURCE = "phase3b_pose_order_unknown_resolution_v1"


def build_phase3b_pose_order_unknown_resolution(
    workspace_root: Path,
    *,
    probe_dir: Optional[Path] = None,
    comparison_path: Optional[Path] = None,
) -> Dict[str, Any]:
    workspace_root = Path(workspace_root).resolve()
    started = time.perf_counter()
    paths = _paths(workspace_root, probe_dir, comparison_path)
    comparison, comparison_error = _load_json(paths["portfolio_sample_comparison"])
    unknown_samples: List[Mapping[str, Any]] = []
    if comparison:
        unknown_samples = [
            entry
            for entry in list(
                _mapping(comparison.get("rerun_start_compatibility_portfolio")).get(
                    "unknown_samples",
                    [],
                )
            )
            if isinstance(entry, Mapping)
        ]
    probe_reports = _probe_reports(paths["probe_dir"], unknown_samples)
    status = _status(comparison_error, probe_reports, unknown_samples)
    return {
        "metadata": {
            "source": POSE_ORDER_UNKNOWN_RESOLUTION_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "pose_order_unknown_resolution_report_only_not_proof_source",
            "solver_invoked": False,
        },
        "paths": {key: str(value) for key, value in paths.items()},
        "status": status,
        "unknown_samples_from_comparison": [_compact_unknown(entry) for entry in unknown_samples],
        "probe_reports": probe_reports,
        "checks": _checks(status, comparison_error, probe_reports, unknown_samples),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }


def render_phase3b_pose_order_unknown_resolution_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "# Phase 3B Pose-Order UNKNOWN Resolution",
        "",
        f"- Outcome: {_markdown_cell(status.get('outcome'))}",
        f"- Runtime promotion ready: {_markdown_cell(status.get('runtime_promotion_ready'))}",
        f"- Recommendation: {_markdown_cell(status.get('recommendation'))}",
        "",
        "| Anchor | Ordering | Full status | First infeasible prefix | First infeasible group |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in list(report.get("probe_reports", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("anchor_idx")),
                    _markdown_cell(entry.get("ordering")),
                    _markdown_cell(entry.get("full_validation_status")),
                    _markdown_cell(entry.get("first_infeasible_prefix_group_count")),
                    _markdown_cell(entry.get("first_infeasible_group_id")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def render_phase3b_pose_order_unknown_resolution_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "Phase 3B pose-order UNKNOWN resolution",
        f"outcome={status.get('outcome')}",
        f"runtime_promotion_ready={status.get('runtime_promotion_ready')}",
    ]
    for entry in list(report.get("probe_reports", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "probe="
            f"anchor={entry.get('anchor_idx')} "
            f"ordering={entry.get('ordering')} "
            f"full_status={entry.get('full_validation_status')} "
            f"first_prefix={entry.get('first_infeasible_prefix_group_count')} "
            f"group={entry.get('first_infeasible_group_id')}"
        )
    lines.append(f"recommendation={status.get('recommendation')}")
    return "\n".join(lines) + "\n"


def _paths(
    root: Path,
    probe_dir: Optional[Path],
    comparison_path: Optional[Path],
) -> Dict[str, Path]:
    return {
        "portfolio_sample_comparison": Path(comparison_path).resolve()
        if comparison_path
        else root
        / ".artifacts/phase3b_start_repair_portfolio_sample_comparison/portfolio_sample_comparison.json",
        "probe_dir": Path(probe_dir).resolve()
        if probe_dir
        else root
        / ".artifacts/phase3b_pose_order_validation_probe_anchor130_131_y_then_x_selected_block_20260422",
    }


def _probe_reports(probe_dir: Path, unknown_samples: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    for sample in unknown_samples:
        anchor_idx = sample.get("anchor_idx")
        ordering = str(sample.get("ordering") or "y_then_x")
        path = probe_dir / f"pose_order_validation_probe_67x13_anchor{anchor_idx}_{ordering}.json"
        payload, error = _load_json(path)
        reports.append(_probe_surface(anchor_idx=anchor_idx, ordering=ordering, path=path, payload=payload, error=error))
    return reports


def _probe_surface(
    *,
    anchor_idx: Any,
    ordering: str,
    path: Path,
    payload: Optional[Mapping[str, Any]],
    error: Optional[str],
) -> Dict[str, Any]:
    diagnostics = _mapping(payload.get("diagnostics")) if payload else {}
    prefix = _mapping(diagnostics.get("prefix_probe"))
    full_validation = _mapping(diagnostics.get("full_validation"))
    first_group = _mapping(prefix.get("first_infeasible_group"))
    return {
        "anchor_idx": anchor_idx,
        "ordering": ordering,
        "path": str(path),
        "present": payload is not None,
        "load_error": error,
        "outcome": _mapping(payload.get("status")).get("outcome") if payload else None,
        "full_validation_status": full_validation.get("status"),
        "full_validation_reason": full_validation.get("reason"),
        "full_validation_wall_time": full_validation.get("wall_time"),
        "full_validation_branches": full_validation.get("branches"),
        "full_validation_conflicts": full_validation.get("conflicts"),
        "first_infeasible_prefix_group_count": prefix.get(
            "first_infeasible_prefix_group_count"
        ),
        "first_infeasible_group_id": first_group.get("group_id"),
        "first_infeasible_group_template": first_group.get("facility_type"),
        "first_infeasible_group_required_count": first_group.get("required_count"),
    }


def _status(
    comparison_error: Optional[str],
    probe_reports: List[Mapping[str, Any]],
    unknown_samples: List[Mapping[str, Any]],
) -> Dict[str, Any]:
    if comparison_error:
        outcome = "missing_portfolio_sample_comparison"
    elif not unknown_samples:
        outcome = "no_unknown_samples_to_resolve"
    elif any(not bool(entry.get("present")) for entry in probe_reports):
        outcome = "missing_pose_order_probe"
    elif all(str(entry.get("outcome")) == "prefix_infeasible" for entry in probe_reports):
        outcome = "portfolio_unknowns_resolved_as_prefix_infeasible"
    else:
        outcome = "portfolio_unknowns_partially_unresolved"
    return {
        "completed": True,
        "outcome": outcome,
        "runtime_promotion_ready": False,
        "proof_source": False,
        "recommendation": (
            "Use anchor/order prefix-infeasible probes as B3 repro material. "
            "Do not promote to proof or final-run readiness without an exact-safe contract."
        ),
    }


def _checks(
    status: Mapping[str, Any],
    comparison_error: Optional[str],
    probe_reports: List[Mapping[str, Any]],
    unknown_samples: List[Mapping[str, Any]],
) -> List[Dict[str, str]]:
    return [
        _check("report_only_semantics", "pass", "report compares existing artifacts and invokes no solver"),
        _check(
            "portfolio_sample_comparison_present",
            "pass" if comparison_error is None else "fail",
            str(comparison_error),
        ),
        _check(
            "all_unknown_samples_have_probe",
            "pass"
            if unknown_samples and all(bool(entry.get("present")) for entry in probe_reports)
            else "fail",
            str(len(probe_reports)),
        ),
        _check(
            "runtime_promotion_guard",
            "pass" if not bool(status.get("runtime_promotion_ready")) else "fail",
            "runtime_promotion_ready remains false",
        ),
    ]


def _compact_unknown(entry: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "anchor_idx": entry.get("anchor_idx"),
        "ordering": entry.get("ordering"),
        "source": entry.get("source"),
        "status": entry.get("status"),
        "reason": entry.get("reason"),
        "forced_slot_field_count": entry.get("forced_slot_field_count"),
    }


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
