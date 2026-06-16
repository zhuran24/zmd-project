from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.search.exact_campaign import now_iso

ORDER_INDEPENDENT_PREDICATE_SCAN_SOURCE = "phase3b_order_independent_predicate_scan_v1"


def build_phase3b_order_independent_predicate_scan(
    project_root: Path,
    *,
    geometry_signature_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    geometry_path = (
        Path(geometry_signature_path).resolve()
        if geometry_signature_path is not None
        else (
            project_root
            / ".artifacts"
            / "phase3b_pose_order_geometry_signature"
            / "pose_order_geometry_signature.json"
        ).resolve()
    )
    started = time.perf_counter()
    signature, load_error = _load_json(geometry_path)
    class_scans = _scan_classes(signature) if signature else {}
    global_scan = _combine_class_scans(class_scans)
    status = _status(signature, load_error, class_scans, global_scan)
    return {
        "metadata": {
            "source": ORDER_INDEPENDENT_PREDICATE_SCAN_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "predicate_scan_report_only_not_proof_source",
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "geometry_signature": str(geometry_path),
        },
        "status": status,
        "class_scans": class_scans,
        "global_scan": global_scan,
        "checks": _checks(status),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "load_error": load_error,
    }


def render_phase3b_order_independent_predicate_scan_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "# Phase 3B Order-Independent Predicate Scan",
        "",
        f"- Outcome: {_markdown_cell(status.get('outcome'))}",
        f"- Candidate count: {_markdown_cell(status.get('candidate_count'))}",
        f"- Runtime promotion ready: {_markdown_cell(status.get('runtime_promotion_ready'))}",
        f"- Recommendation: {_markdown_cell(status.get('recommendation'))}",
        "",
        "## Class Scans",
        "",
        "| Class | INFEASIBLE | UNKNOWN | Common INFEASIBLE | UNKNOWN Features | Candidate Features |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]
    for class_name, scan in sorted(_mapping(report.get("class_scans")).items()):
        if not isinstance(scan, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(class_name),
                    _markdown_cell(scan.get("infeasible_strategy_count")),
                    _markdown_cell(scan.get("unknown_strategy_count")),
                    _markdown_cell(scan.get("common_infeasible_features")),
                    _markdown_cell(scan.get("unknown_feature_union")),
                    _markdown_cell(scan.get("candidate_features")),
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


def render_phase3b_order_independent_predicate_scan_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "Phase 3B order-independent predicate scan",
        f"outcome={status.get('outcome')}",
        f"candidate_count={status.get('candidate_count')}",
        f"runtime_promotion_ready={status.get('runtime_promotion_ready')}",
        f"recommendation={status.get('recommendation')}",
        "",
        "class_scans:",
    ]
    for class_name, scan in sorted(_mapping(report.get("class_scans")).items()):
        if isinstance(scan, Mapping):
            lines.append(
                "  "
                + ", ".join(
                    [
                        f"class={class_name}",
                        f"infeasible={scan.get('infeasible_strategy_count')}",
                        f"unknown={scan.get('unknown_strategy_count')}",
                        f"candidate_features={scan.get('candidate_features')}",
                    ]
                )
            )
    return "\n".join(lines) + "\n"


def _scan_classes(signature: Mapping[str, Any]) -> Dict[str, Any]:
    class_entries: dict[str, list[Mapping[str, Any]]] = {}
    for anchor in list(signature.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        class_entries.setdefault(str(anchor.get("taxonomy_class", "unknown")), []).append(anchor)
    return {
        class_name: _scan_class(entries)
        for class_name, entries in sorted(class_entries.items())
    }


def _scan_class(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    infeasible_sets: list[set[str]] = []
    unknown_sets: list[set[str]] = []
    strategy_status_counts: Counter[str] = Counter()
    feature_status_counts: dict[str, Counter[str]] = {}
    for anchor in entries:
        for strategy in list(anchor.get("strategies", [])):
            if not isinstance(strategy, Mapping):
                continue
            status = str(strategy.get("status", ""))
            strategy_status_counts[f"{strategy.get('strategy')}={status}"] += 1
            features = _features_for_strategy(strategy)
            for feature in features:
                feature_status_counts.setdefault(feature, Counter())[status] += 1
            if status == "INFEASIBLE":
                infeasible_sets.append(features)
            elif status == "UNKNOWN":
                unknown_sets.append(features)
    common_infeasible = set.intersection(*infeasible_sets) if infeasible_sets else set()
    unknown_union = set.union(*unknown_sets) if unknown_sets else set()
    candidate_features = sorted(common_infeasible - unknown_union)
    return {
        "anchor_count": len(entries),
        "anchors": [int(entry.get("anchor_idx", -1)) for entry in entries],
        "infeasible_strategy_count": len(infeasible_sets),
        "unknown_strategy_count": len(unknown_sets),
        "strategy_status_counts": dict(sorted(strategy_status_counts.items())),
        "common_infeasible_features": sorted(common_infeasible),
        "unknown_feature_union": sorted(unknown_union),
        "candidate_features": candidate_features,
        "feature_status_counts": {
            feature: dict(counts)
            for feature, counts in sorted(feature_status_counts.items())
        },
    }


def _features_for_strategy(strategy: Mapping[str, Any]) -> set[str]:
    geometry = _mapping(strategy.get("geometry"))
    features = {
        f"axis:{geometry.get('dominant_axis')}",
        f"point_count:{geometry.get('point_count')}",
        f"x_unique:{geometry.get('x_unique_count')}",
        f"y_unique:{geometry.get('y_unique_count')}",
        f"x_span:{geometry.get('x_span')}",
        f"y_span:{geometry.get('y_span')}",
        f"fingerprint:{geometry.get('sequence_fingerprint')}",
        f"strategy:{strategy.get('strategy')}",
    }
    for key, value in sorted(_mapping(geometry.get("x_step_counts")).items()):
        features.add(f"x_step:{key}={value}")
    for key, value in sorted(_mapping(geometry.get("y_step_counts")).items()):
        features.add(f"y_step:{key}={value}")
    return {feature for feature in features if not feature.endswith(":None")}


def _combine_class_scans(class_scans: Mapping[str, Any]) -> Dict[str, Any]:
    candidate_sets: list[set[str]] = []
    class_local_candidates: set[str] = set()
    for scan in class_scans.values():
        if isinstance(scan, Mapping):
            candidates = {str(value) for value in scan.get("candidate_features", [])}
            candidate_sets.append(candidates)
            class_local_candidates.update(candidates)
    global_candidates = set.intersection(*candidate_sets) if candidate_sets else set()
    return {
        "candidate_features": sorted(global_candidates),
        "candidate_feature_count": len(global_candidates),
        "class_local_candidate_features": sorted(class_local_candidates),
        "class_local_candidate_feature_count": len(class_local_candidates),
    }


def _status(
    signature: Optional[Mapping[str, Any]],
    load_error: Optional[str],
    class_scans: Mapping[str, Any],
    global_scan: Mapping[str, Any],
) -> Dict[str, Any]:
    candidate_count = int(global_scan.get("candidate_feature_count", 0) or 0)
    if load_error:
        outcome = "geometry_signature_missing_or_invalid"
    elif candidate_count == 0:
        outcome = "no_order_independent_predicate_found"
    else:
        outcome = "candidate_features_need_solver_validation"
    return {
        "completed": True,
        "geometry_signature_present": signature is not None,
        "class_count": len(class_scans),
        "candidate_count": candidate_count,
        "outcome": outcome,
        "runtime_promotion_ready": False,
        "proof_source": False,
        "recommendation": _recommendation(outcome, candidate_count),
    }


def _recommendation(outcome: str, candidate_count: int) -> str:
    if outcome == "no_order_independent_predicate_found":
        return (
            "Keep ordering-sensitive evidence diagnostic-only; no feature survived the "
            "all-INFEASIBLE and no-UNKNOWN filter."
        )
    if candidate_count:
        return (
            "Treat candidate features as a hypothesis only; validate with no-overlap, "
            "capacity, signature, or domain diagnostics before runtime discussion."
        )
    return "Generate the geometry signature report first, then rerun this scan."


def _checks(status: Mapping[str, Any]) -> list[Dict[str, str]]:
    return [
        {
            "check_id": "report_only_semantics",
            "status": "pass",
            "detail": "scan reads geometry-signature JSON and does not invoke solver",
        },
        {
            "check_id": "runtime_promotion_guard",
            "status": "pass",
            "detail": "runtime_promotion_ready remains false",
        },
        {
            "check_id": "geometry_signature_present",
            "status": "pass" if status.get("geometry_signature_present") else "fail",
            "detail": str(status.get("geometry_signature_present")),
        },
    ]


def _load_json(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, "missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(value, dict):
        return None, "json_root_not_object"
    return value, None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
