from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

ROW_DOMAIN_COUNT_WITNESS_PAYLOAD_SOURCE = (
    "phase3b_coordinate_validation_row_domain_count_witness_payload_v1"
)
ROW_DOMAIN_COUNT_WITNESS_DESIGN_SOURCE = (
    "phase3b_coordinate_validation_row_domain_count_witness_design_v1"
)

DEFAULT_ROW_DOMAIN_COUNT_WITNESS_DESIGN_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_row_domain_count_witness_design_20260423/"
    "row_domain_count_witness_design.json"
)


def build_phase3b_coordinate_validation_row_domain_count_witness_payload(
    project_root: Path,
    *,
    row_domain_count_witness_design_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    design_resolved = _resolve_path(
        project_root,
        row_domain_count_witness_design_path
        if row_domain_count_witness_design_path is not None
        else DEFAULT_ROW_DOMAIN_COUNT_WITNESS_DESIGN_PATH,
    )

    design_report, design_error = _load_json_mapping(design_resolved)
    design_meta = _mapping(design_report.get("metadata")) if design_report else {}
    design_status = _mapping(design_report.get("status")) if design_report else {}
    witness_design = _mapping(design_report.get("witness_design")) if design_report else {}
    count_witness = _mapping(design_report.get("count_witness")) if design_report else {}
    candidate = _mapping(design_report.get("candidate")) if design_report else {}

    row_summaries = [
        dict(entry)
        for entry in list(witness_design.get("row_summaries", []))
        if isinstance(entry, Mapping)
    ]

    design_present = bool(
        design_report is not None
        and design_error is None
        and design_meta.get("source") == ROW_DOMAIN_COUNT_WITNESS_DESIGN_SOURCE
    )
    design_ready = bool(design_status.get("design_ready", False))
    witness_shape_supported = (
        design_status.get("witness_shape") == "three_label_overlap_above_strip_count_guard"
    )
    exact_three_rows = len(row_summaries) == 3
    shared_safe_strip_lower_bound = _optional_int(
        witness_design.get("shared_safe_strip_lower_bound")
    )
    threshold_delta = _optional_int(count_witness.get("threshold_delta"))
    non_trigger_max_slot_count = _optional_int(
        count_witness.get("highest_non_exceeded_unknown_slot_index")
    )
    anchored_trigger_min_slot_count = _optional_int(
        count_witness.get("fixed_anchor_threshold")
    )
    free_ghost_trigger_min_slot_count = _optional_int(
        count_witness.get("free_ghost_threshold")
    )
    payload_ready = bool(
        design_present
        and design_ready
        and witness_shape_supported
        and exact_three_rows
        and shared_safe_strip_lower_bound is not None
        and threshold_delta == 1
        and non_trigger_max_slot_count is not None
        and anchored_trigger_min_slot_count is not None
        and free_ghost_trigger_min_slot_count is not None
    )

    total_row_count = sum(
        int(entry.get("row_count", 0) or 0) for entry in row_summaries
    )

    payload_rows = [
        {
            "group_id": str(entry.get("group_id", "")),
            "solution_id": entry.get("solution_id"),
            "slot_index": _optional_int(entry.get("slot_index")),
            "template": entry.get("template"),
            "forced_x": _optional_int(entry.get("forced_x")),
            "row_count": _optional_int(entry.get("row_count")),
            "safe_y_min": _optional_int(entry.get("avoiding_y_min")),
            "safe_y_max": _optional_int(entry.get("avoiding_y_max")),
            "safe_y_count": _optional_int(entry.get("avoiding_y_count")),
            "below_y_count": _optional_int(entry.get("below_y_count")),
            "above_y_count": _optional_int(entry.get("above_y_count")),
        }
        for entry in row_summaries
    ]

    checks = [
        _check(
            "row_domain_count_witness_design_present",
            "pass" if design_present else "fail",
            "row-domain/count witness design loaded"
            if design_present
            else design_error or f"missing:{_display_path(project_root, design_resolved)}",
        ),
        _check(
            "row_domain_count_design_ready",
            "pass" if design_ready else "fail",
            str(design_status.get("recommendation") or "design not ready"),
        ),
        _check(
            "supported_witness_shape",
            "pass" if witness_shape_supported else "fail",
            f"witness_shape={design_status.get('witness_shape')}",
        ),
        _check(
            "exact_three_row_summaries",
            "pass" if exact_three_rows else "fail",
            f"row_summary_count={len(row_summaries)}",
        ),
        _check(
            "shared_safe_strip_lower_bound_present",
            "pass" if shared_safe_strip_lower_bound is not None else "fail",
            f"shared_safe_strip_lower_bound={shared_safe_strip_lower_bound}",
        ),
        _check(
            "threshold_delta_is_one",
            "pass" if threshold_delta == 1 else "fail",
            f"threshold_delta={threshold_delta}",
        ),
        _check(
            "anchored_and_nontrigger_boundaries_present",
            "pass"
            if (
                non_trigger_max_slot_count is not None
                and anchored_trigger_min_slot_count is not None
                and free_ghost_trigger_min_slot_count is not None
            )
            else "fail",
            (
                f"non_trigger_max_slot_count={non_trigger_max_slot_count}; "
                f"anchored_trigger_min_slot_count={anchored_trigger_min_slot_count}; "
                f"free_ghost_trigger_min_slot_count={free_ghost_trigger_min_slot_count}"
            ),
        ),
        _check(
            "runtime_promotion_guard",
            "fail",
            (
                "deterministic witness payload is ready for anchored-bridge extraction only; "
                "keep runtime default-off until the anchored bridge and non-trigger controls "
                "are extracted and verified"
            ),
        ),
    ]

    return {
        "metadata": {
            "source": ROW_DOMAIN_COUNT_WITNESS_PAYLOAD_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "coordinate_validation_row_domain_count_witness_payload_not_proof_source"
            ),
            "solver_invoked": False,
            "proof_source": False,
        },
        "paths": {
            "project_root": str(project_root),
            "row_domain_count_witness_design": _display_path(project_root, design_resolved),
        },
        "candidate": dict(candidate),
        "status": {
            "payload_ready": bool(payload_ready),
            "anchored_bridge_ready": False,
            "runtime_promotion_ready": False,
            "recommended_next_step": "extract_anchor119_row_domain_bridge",
            "recommendation": _recommendation(payload_ready),
        },
        "deterministic_payload": {
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "witness_shape": design_status.get("witness_shape"),
            "shared_safe_strip_lower_bound": shared_safe_strip_lower_bound,
            "total_row_count": total_row_count,
            "rows": payload_rows,
            "all_labels_overlap_all_anchors": bool(
                witness_design.get("all_labels_overlap_all_anchors", False)
            ),
            "all_single_x_domain": bool(witness_design.get("all_single_x_domain", False)),
            "all_no_below_ghost_room": bool(
                witness_design.get("all_no_below_ghost_room", False)
            ),
            "implied_fixed_slots": list(witness_design.get("implied_fixed_slots", [])),
        },
        "count_boundaries": {
            "non_trigger_max_slot_count": non_trigger_max_slot_count,
            "anchored_trigger_min_slot_count": anchored_trigger_min_slot_count,
            "free_ghost_trigger_min_slot_count": free_ghost_trigger_min_slot_count,
            "threshold_delta": threshold_delta,
            "exceeded_infeasible_slot_indices": list(
                count_witness.get("exceeded_infeasible_slot_indices", [])
            ),
        },
        "required_outputs": [
            "Map the deterministic three-label payload back to anchor119 fixed-anchor semantics.",
            "Show exactly why slot count 13 is non-trigger while slot count 14 is the anchored trigger boundary.",
            "Encode non-trigger controls for anchors lacking the same three-label overlap-above-strip payload.",
            "Keep any runtime helper default-off until the anchored bridge is validated end-to-end.",
        ],
        "checks": checks,
    }


def render_phase3b_coordinate_validation_row_domain_count_witness_payload_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    payload = _mapping(report.get("deterministic_payload"))
    boundaries = _mapping(report.get("count_boundaries"))
    lines = [
        "# Phase 3B Coordinate-Validation Row-Domain Count Witness Payload",
        "",
        f"- Payload ready: {bool(status.get('payload_ready', False))}",
        f"- Anchored bridge ready: {bool(status.get('anchored_bridge_ready', False))}",
        f"- Runtime promotion ready: {bool(status.get('runtime_promotion_ready', False))}",
        f"- Recommended next step: {status.get('recommended_next_step')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Deterministic Payload",
        "",
        f"- Payload id: {payload.get('payload_id')}",
        f"- Witness shape: {payload.get('witness_shape')}",
        f"- Shared safe-strip lower bound: {payload.get('shared_safe_strip_lower_bound')}",
        f"- Total row count: {payload.get('total_row_count')}",
        f"- Implied fixed slots: {payload.get('implied_fixed_slots')}",
        "",
        "## Count Boundaries",
        "",
        f"- Non-trigger max slot count: {boundaries.get('non_trigger_max_slot_count')}",
        f"- Anchored trigger min slot count: {boundaries.get('anchored_trigger_min_slot_count')}",
        f"- Free-ghost trigger min slot count: {boundaries.get('free_ghost_trigger_min_slot_count')}",
        f"- Threshold delta: {boundaries.get('threshold_delta')}",
        "",
        "## Rows",
        "",
        "| Group | Slot | Forced X | Row Count | Safe Y Min | Safe Y Max | Safe Y Count |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in list(payload.get("rows", [])):
        if isinstance(row, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(row.get("group_id")),
                        _markdown_cell(row.get("slot_index")),
                        _markdown_cell(row.get("forced_x")),
                        _markdown_cell(row.get("row_count")),
                        _markdown_cell(row.get("safe_y_min")),
                        _markdown_cell(row.get("safe_y_max")),
                        _markdown_cell(row.get("safe_y_count")),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
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


def render_phase3b_coordinate_validation_row_domain_count_witness_payload_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    payload = _mapping(report.get("deterministic_payload"))
    boundaries = _mapping(report.get("count_boundaries"))
    lines = [
        "Phase 3B coordinate-validation row-domain count witness payload",
        f"payload_ready={bool(status.get('payload_ready', False))}",
        f"anchored_bridge_ready={bool(status.get('anchored_bridge_ready', False))}",
        f"runtime_promotion_ready={bool(status.get('runtime_promotion_ready', False))}",
        f"recommended_next_step={status.get('recommended_next_step')}",
        f"payload_id={payload.get('payload_id')}",
        f"shared_safe_strip_lower_bound={payload.get('shared_safe_strip_lower_bound')}",
        f"row_counts={[row.get('row_count') for row in list(payload.get('rows', [])) if isinstance(row, Mapping)]}",
        f"non_trigger_max_slot_count={boundaries.get('non_trigger_max_slot_count')}",
        f"anchored_trigger_min_slot_count={boundaries.get('anchored_trigger_min_slot_count')}",
        f"free_ghost_trigger_min_slot_count={boundaries.get('free_ghost_trigger_min_slot_count')}",
        f"recommendation={status.get('recommendation')}",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                f"check id={check.get('check_id')} status={check.get('status')} detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _recommendation(payload_ready: bool) -> str:
    if payload_ready:
        return (
            "Deterministic row-domain/count witness payload is ready: the next bounded move is "
            "to extract the anchor119 fixed-anchor bridge and the matching non-trigger controls "
            "without changing runtime semantics by default."
        )
    return "Deterministic row-domain/count witness payload is incomplete; repair prerequisite evidence first."


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {
        "check_id": str(check_id),
        "status": str(status),
        "detail": str(detail),
    }


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        if not path.exists():
            return None, f"missing:{path}"
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return None, "json root is not an object"
        return payload, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


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


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
