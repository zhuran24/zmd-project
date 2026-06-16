from __future__ import annotations

import json
import time
import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.search.exact_campaign import now_iso
from src.search.phase3b.pose_order.residual_pose_order_taxonomy import (
    DEFAULT_RESIDUAL_ANCHORS,
    build_phase3b_residual_pose_order_taxonomy,
)

POSE_ORDER_GEOMETRY_SIGNATURE_SOURCE = "phase3b_pose_order_geometry_signature_v1"


def build_phase3b_pose_order_geometry_signature(
    project_root: Path,
    *,
    anchors: Optional[Sequence[int]] = None,
    artifact_root: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    artifact_root = (
        Path(artifact_root).resolve()
        if artifact_root is not None
        else (project_root / ".artifacts").resolve()
    )
    normalized_anchors = [int(anchor) for anchor in (anchors or DEFAULT_RESIDUAL_ANCHORS)]
    started = time.perf_counter()
    taxonomy = build_phase3b_residual_pose_order_taxonomy(
        project_root,
        anchors=normalized_anchors,
        artifact_root=artifact_root,
    )
    entries = [
        _anchor_signature(anchor_entry)
        for anchor_entry in list(taxonomy.get("anchors", []))
        if isinstance(anchor_entry, Mapping)
    ]
    status = _status(entries, taxonomy)
    return {
        "metadata": {
            "source": POSE_ORDER_GEOMETRY_SIGNATURE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "geometry_signature_report_only_not_proof_source",
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "artifact_root": str(artifact_root),
        },
        "profile": {"anchors": normalized_anchors},
        "taxonomy_status": _mapping(taxonomy.get("status")),
        "status": status,
        "anchors": entries,
        "class_summary": _class_summary(entries),
        "checks": _checks(entries, status),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }


def render_phase3b_pose_order_geometry_signature_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "# Phase 3B Pose-Order Geometry Signature",
        "",
        f"- Outcome: {_markdown_cell(status.get('outcome'))}",
        f"- Anchors summarized: {_markdown_cell(status.get('summarized_anchor_count'))}",
        f"- Runtime promotion ready: {_markdown_cell(status.get('runtime_promotion_ready'))}",
        f"- Recommendation: {_markdown_cell(status.get('recommendation'))}",
        "",
        "## Class Summary",
        "",
        "| Class | Anchors | Stable Status Pattern | Dominant Axes |",
        "| --- | --- | --- | --- |",
    ]
    for class_name, summary in sorted(_mapping(report.get("class_summary")).items()):
        if not isinstance(summary, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(class_name),
                    _markdown_cell(",".join(str(v) for v in summary.get("anchors", []))),
                    _markdown_cell(summary.get("stable_status_pattern")),
                    _markdown_cell(summary.get("dominant_axis_counts_by_strategy")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Anchor Strategy Matrix",
            "",
            "| Anchor | Class | Strategy | Status | Axis | Points | X span | Y span | X counts | Y counts |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for anchor_entry in list(report.get("anchors", [])):
        if not isinstance(anchor_entry, Mapping):
            continue
        for strategy in list(anchor_entry.get("strategies", [])):
            if not isinstance(strategy, Mapping):
                continue
            geometry = _mapping(strategy.get("geometry"))
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(anchor_entry.get("anchor_idx")),
                        _markdown_cell(anchor_entry.get("taxonomy_class")),
                        _markdown_cell(strategy.get("strategy")),
                        _markdown_cell(strategy.get("status")),
                        _markdown_cell(geometry.get("dominant_axis")),
                        _markdown_cell(geometry.get("point_count")),
                        _markdown_cell(geometry.get("x_span")),
                        _markdown_cell(geometry.get("y_span")),
                        _markdown_cell(geometry.get("x_value_counts")),
                        _markdown_cell(geometry.get("y_value_counts")),
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


def render_phase3b_pose_order_geometry_signature_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "Phase 3B pose-order geometry signature",
        f"outcome={status.get('outcome')}",
        f"summarized_anchor_count={status.get('summarized_anchor_count')}",
        f"runtime_promotion_ready={status.get('runtime_promotion_ready')}",
        f"recommendation={status.get('recommendation')}",
        "",
        "class_summary:",
    ]
    for class_name, summary in sorted(_mapping(report.get("class_summary")).items()):
        if isinstance(summary, Mapping):
            lines.append(
                "  "
                + ", ".join(
                    [
                        f"class={class_name}",
                        f"anchors={','.join(str(v) for v in summary.get('anchors', []))}",
                        f"stable_status_pattern={summary.get('stable_status_pattern')}",
                    ]
                )
            )
    return "\n".join(lines) + "\n"


def _anchor_signature(anchor_entry: Mapping[str, Any]) -> Dict[str, Any]:
    taxonomy_class = str(anchor_entry.get("taxonomy_class", ""))
    artifact_paths = _mapping(anchor_entry.get("artifact_paths"))
    if taxonomy_class == "planter_buckwheat_xy_ordering_sensitive_diagnostic":
        greedy_path = str(artifact_paths.get("greedy_pose_order", ""))
    elif taxonomy_class == "non_target_first_group_ordering_sensitive_diagnostic":
        greedy_path = str(artifact_paths.get("first_group_greedy_pose_order", ""))
    else:
        greedy_path = ""
    greedy_report, greedy_error = _load_json(Path(greedy_path)) if greedy_path else (None, "missing")
    strategies = _strategy_signatures(greedy_report) if greedy_report else []
    comparison = _mapping(greedy_report.get("comparison")) if greedy_report else {}
    return {
        "anchor_idx": int(anchor_entry.get("anchor_idx", -1)),
        "taxonomy_class": taxonomy_class,
        "group_ids": list(anchor_entry.get("group_first_infeasible_group_ids", [])),
        "greedy_artifact_path": greedy_path,
        "greedy_artifact_status": "present" if greedy_report else "missing_or_error",
        "greedy_artifact_error": greedy_error,
        "status_pattern": _status_pattern(strategies),
        "pairwise_overlap": list(comparison.get("pairwise_overlap", [])),
        "single_group_blocked_vs_full_blocked": _mapping(
            comparison.get("single_group_blocked_vs_full_blocked")
        ),
        "strategies": strategies,
        "runtime_promotion_ready": False,
        "proof_source": False,
    }


def _strategy_signatures(report: Mapping[str, Any]) -> list[Dict[str, Any]]:
    entries = list(_mapping(report.get("comparison")).get("entries", []))
    signatures: list[Dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        validation = _mapping(entry.get("target_validation"))
        labels = list(validation.get("force_equality_labels", []))
        points = _points_from_labels(labels)
        signatures.append(
            {
                "strategy": str(entry.get("strategy", "")),
                "status": str(validation.get("status", "")),
                "target_pose_indices": list(entry.get("target_pose_indices", [])),
                "forced_slot_field_count": int(validation.get("forced_slot_field_count", 0) or 0),
                "geometry": _geometry_from_points(points),
                "points": points,
            }
        )
    return signatures


def _points_from_labels(labels: Sequence[Any]) -> list[Dict[str, Any]]:
    by_slot: dict[int, dict[str, Any]] = {}
    for raw_label in labels:
        if not isinstance(raw_label, Mapping):
            continue
        field = str(raw_label.get("field", ""))
        if field not in {"x", "y", "mode"}:
            continue
        slot_index = int(raw_label.get("slot_index", -1))
        point = by_slot.setdefault(
            slot_index,
            {
                "slot_index": slot_index,
                "slot_key": raw_label.get("slot_key"),
                "solution_id": raw_label.get("solution_id"),
                "pose_index": raw_label.get("pose_index"),
            },
        )
        point[field] = raw_label.get("forced_value")
    return [by_slot[key] for key in sorted(by_slot)]


def _geometry_from_points(points: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    x_values = [int(point["x"]) for point in points if "x" in point]
    y_values = [int(point["y"]) for point in points if "y" in point]
    x_counts = Counter(x_values)
    y_counts = Counter(y_values)
    x_steps = _steps(x_values)
    y_steps = _steps(y_values)
    x_span = _span(x_values)
    y_span = _span(y_values)
    return {
        "point_count": len(points),
        "complete_xy_point_count": min(len(x_values), len(y_values)),
        "x_unique_count": len(x_counts),
        "y_unique_count": len(y_counts),
        "x_span": x_span,
        "y_span": y_span,
        "x_value_counts": dict(sorted(x_counts.items())),
        "y_value_counts": dict(sorted(y_counts.items())),
        "x_step_counts": dict(sorted(Counter(x_steps).items())),
        "y_step_counts": dict(sorted(Counter(y_steps).items())),
        "x_run_lengths": _run_lengths(x_values),
        "y_run_lengths": _run_lengths(y_values),
        "mode_counts": dict(sorted(Counter(_mode_values(points)).items())),
        "normalized_dx_dy_mode": _normalized_sequence(points),
        "sequence_fingerprint": _sequence_fingerprint(points),
        "dominant_axis": _dominant_axis(
            x_unique_count=len(x_counts),
            y_unique_count=len(y_counts),
            x_span=x_span,
            y_span=y_span,
        ),
    }


def _dominant_axis(
    *,
    x_unique_count: int,
    y_unique_count: int,
    x_span: int,
    y_span: int,
) -> str:
    if x_unique_count <= 2 and y_span > x_span:
        return "vertical_or_few_x_strip"
    if y_unique_count <= 2 and x_span > y_span:
        return "horizontal_or_few_y_strip"
    if x_span == 0 and y_span == 0:
        return "point_or_empty"
    return "mixed_or_diagonal"


def _status(entries: Sequence[Mapping[str, Any]], taxonomy: Mapping[str, Any]) -> Dict[str, Any]:
    missing_count = sum(1 for entry in entries if entry.get("greedy_artifact_status") != "present")
    summarized_count = len(entries) - missing_count
    return {
        "completed": True,
        "summarized_anchor_count": summarized_count,
        "missing_greedy_artifact_count": missing_count,
        "taxonomy_outcome": _mapping(taxonomy.get("status")).get("outcome"),
        "outcome": "geometry_signature_complete" if missing_count == 0 else "geometry_signature_incomplete",
        "runtime_promotion_ready": False,
        "proof_source": False,
        "recommendation": (
            "Use this as a geometry/order diagnostic map only; promotion still requires "
            "a separate order-independent predicate or proof-safe order contract."
        ),
    }


def _class_summary(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_class: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for entry in entries:
        by_class[str(entry.get("taxonomy_class", "unknown"))].append(entry)
    summary: Dict[str, Any] = {}
    for class_name, class_entries in by_class.items():
        axis_by_strategy: dict[str, Counter[str]] = defaultdict(Counter)
        axis_by_status: dict[str, Counter[str]] = defaultdict(Counter)
        fingerprint_by_strategy: dict[str, Counter[str]] = defaultdict(Counter)
        status_patterns = Counter(str(entry.get("status_pattern", "")) for entry in class_entries)
        for entry in class_entries:
            for strategy in list(entry.get("strategies", [])):
                if not isinstance(strategy, Mapping):
                    continue
                geometry = _mapping(strategy.get("geometry"))
                axis = str(geometry.get("dominant_axis", ""))
                strategy_name = str(strategy.get("strategy", ""))
                status = str(strategy.get("status", ""))
                axis_by_strategy[strategy_name][axis] += 1
                axis_by_status[status][axis] += 1
                fingerprint = str(geometry.get("sequence_fingerprint", ""))
                if fingerprint:
                    fingerprint_by_strategy[strategy_name][fingerprint] += 1
        summary[class_name] = {
            "anchors": [int(entry.get("anchor_idx", -1)) for entry in class_entries],
            "stable_status_pattern": len(status_patterns) == 1,
            "status_pattern_counts": dict(status_patterns),
            "dominant_axis_counts_by_strategy": {
                strategy: dict(counts)
                for strategy, counts in sorted(axis_by_strategy.items())
            },
            "dominant_axis_counts_by_status": {
                status: dict(counts)
                for status, counts in sorted(axis_by_status.items())
            },
            "sequence_fingerprint_counts_by_strategy": {
                strategy: dict(counts)
                for strategy, counts in sorted(fingerprint_by_strategy.items())
            },
        }
    return summary


def _checks(entries: Sequence[Mapping[str, Any]], status: Mapping[str, Any]) -> list[Dict[str, str]]:
    return [
        {
            "check_id": "report_only_semantics",
            "status": "pass",
            "detail": "report reads existing artifacts and does not invoke solver",
        },
        {
            "check_id": "runtime_promotion_guard",
            "status": "pass",
            "detail": "runtime_promotion_ready is fixed false for this diagnostic report",
        },
        {
            "check_id": "greedy_artifact_coverage",
            "status": "pass" if int(status.get("missing_greedy_artifact_count", 0)) == 0 else "fail",
            "detail": f"{status.get('missing_greedy_artifact_count')} anchors are missing greedy artifacts",
        },
        {
            "check_id": "anchor_entry_count",
            "status": "pass" if entries else "fail",
            "detail": f"{len(entries)} taxonomy anchor entries summarized",
        },
    ]


def _status_pattern(strategies: Sequence[Mapping[str, Any]]) -> str:
    return ";".join(
        f"{strategy.get('strategy')}={strategy.get('status')}"
        for strategy in strategies
    )


def _steps(values: Sequence[int]) -> list[int]:
    return [int(values[index + 1]) - int(values[index]) for index in range(len(values) - 1)]


def _run_lengths(values: Sequence[int]) -> list[int]:
    if not values:
        return []
    runs: list[int] = []
    current = values[0]
    length = 1
    for value in values[1:]:
        if value == current:
            length += 1
        else:
            runs.append(length)
            current = value
            length = 1
    runs.append(length)
    return runs


def _mode_values(points: Sequence[Mapping[str, Any]]) -> list[int]:
    values: list[int] = []
    for point in points:
        if "mode" in point:
            values.append(int(point["mode"]))
    return values


def _normalized_sequence(points: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    if not points:
        return []
    base_x = int(points[0].get("x", 0) or 0)
    base_y = int(points[0].get("y", 0) or 0)
    normalized: list[Dict[str, Any]] = []
    for point in points:
        item: Dict[str, Any] = {"slot_index": int(point.get("slot_index", -1))}
        if "x" in point:
            item["dx"] = int(point["x"]) - base_x
        if "y" in point:
            item["dy"] = int(point["y"]) - base_y
        if "mode" in point:
            item["mode"] = int(point["mode"])
        normalized.append(item)
    return normalized


def _sequence_fingerprint(points: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(
        _normalized_sequence(points),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _span(values: Sequence[int]) -> int:
    return max(values) - min(values) if values else 0


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
