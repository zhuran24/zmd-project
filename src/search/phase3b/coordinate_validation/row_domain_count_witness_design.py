from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from src.search.exact_campaign import now_iso

ROW_DOMAIN_COUNT_WITNESS_DESIGN_SOURCE = (
    "phase3b_coordinate_validation_row_domain_count_witness_design_v1"
)
ROW_DOMAIN_EXTRACTION_CANDIDATE_SOURCE = (
    "phase3b_coordinate_validation_row_domain_extraction_candidate_v1"
)
PAIR_X_ORDER_DOMAIN_EXTRACTION_SOURCE = (
    "phase3b_anchor119_pair_x_order_domain_extraction_v1"
)
PAIR_X_GLOBAL_CONTEXT_SYNTHESIS_SOURCE = (
    "phase3b_anchor119_pair_x_global_context_synthesis_v1"
)

DEFAULT_ROW_DOMAIN_EXTRACTION_CANDIDATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_row_domain_extraction_candidate_20260423/"
    "row_domain_extraction_candidate.json"
)
DEFAULT_ORDER_DOMAIN_EXTRACTION_PATH = Path(
    ".artifacts/phase3b_anchor119_pair_x_order_domain_extraction_20260423/"
    "order_domain_extraction.json"
)
DEFAULT_GLOBAL_CONTEXT_SYNTHESIS_PATH = Path(
    ".artifacts/phase3b_anchor119_pair_x_global_context_synthesis_20260423/"
    "global_context_synthesis.json"
)


def build_phase3b_coordinate_validation_row_domain_count_witness_design(
    project_root: Path,
    *,
    row_domain_extraction_candidate_path: Optional[Path] = None,
    order_domain_extraction_path: Optional[Path] = None,
    global_context_synthesis_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    candidate_resolved = _resolve_path(
        project_root,
        row_domain_extraction_candidate_path
        if row_domain_extraction_candidate_path is not None
        else DEFAULT_ROW_DOMAIN_EXTRACTION_CANDIDATE_PATH,
    )
    order_resolved = _resolve_path(
        project_root,
        order_domain_extraction_path
        if order_domain_extraction_path is not None
        else DEFAULT_ORDER_DOMAIN_EXTRACTION_PATH,
    )
    synthesis_resolved = _resolve_path(
        project_root,
        global_context_synthesis_path
        if global_context_synthesis_path is not None
        else DEFAULT_GLOBAL_CONTEXT_SYNTHESIS_PATH,
    )

    candidate_report, candidate_error = _load_json_mapping(candidate_resolved)
    order_report, order_error = _load_json_mapping(order_resolved)
    synthesis_report, synthesis_error = _load_json_mapping(synthesis_resolved)

    candidate_meta = _mapping(candidate_report.get("metadata")) if candidate_report else {}
    order_meta = _mapping(order_report.get("metadata")) if order_report else {}
    synthesis_meta = _mapping(synthesis_report.get("metadata")) if synthesis_report else {}

    candidate_status = _mapping(candidate_report.get("status")) if candidate_report else {}
    candidate_evidence = _mapping(candidate_report.get("evidence")) if candidate_report else {}
    candidate = _mapping(candidate_report.get("candidate")) if candidate_report else {}

    forced_labels = [
        dict(entry)
        for entry in list(order_report.get("forced_labels", []) if order_report else [])
        if isinstance(entry, Mapping)
    ]
    row_entries = _extract_row_entries(order_report, forced_labels)
    synthesis_status = _mapping(synthesis_report.get("status")) if synthesis_report else {}
    synthesis_evidence = _mapping(synthesis_report.get("evidence")) if synthesis_report else {}
    order_overlap_summary = _mapping(synthesis_evidence.get("order_domain_extraction"))

    candidate_present = bool(
        candidate_report is not None
        and candidate_error is None
        and candidate_meta.get("source") == ROW_DOMAIN_EXTRACTION_CANDIDATE_SOURCE
    )
    order_present = bool(
        order_report is not None
        and order_error is None
        and order_meta.get("source") == PAIR_X_ORDER_DOMAIN_EXTRACTION_SOURCE
    )
    synthesis_present = bool(
        synthesis_report is not None
        and synthesis_error is None
        and synthesis_meta.get("source") == PAIR_X_GLOBAL_CONTEXT_SYNTHESIS_SOURCE
    )

    candidate_gate_passed = bool(candidate_status.get("design_gate_passed", False))
    candidate_points_to_witness = (
        candidate_status.get("recommended_next_step") == "implement_row_domain_extraction_witness"
    )
    exact_three_label_core = len(forced_labels) == 3 and len(row_entries) == 3
    all_single_x_domain = bool(
        row_entries and all(int(entry.get("x_domain_count", 0) or 0) == 1 for entry in row_entries)
    )
    all_no_below_ghost_room = bool(
        row_entries and all(int(entry.get("below_y_count", 0) or 0) == 0 for entry in row_entries)
    )
    all_above_counts_match_avoiding = bool(
        row_entries
        and all(
            int(entry.get("above_y_count", -1) or -1)
            == int(entry.get("avoiding_y_count", -2) or -2)
            for entry in row_entries
        )
    )
    shared_safe_strip_lower_bound = _shared_int(
        entry.get("avoiding_y_min") for entry in row_entries if entry.get("avoiding_y_min") is not None
    )
    all_labels_overlap_all_anchors = bool(
        order_overlap_summary.get("all_forced_labels_x_overlap_all_anchors", False)
    )
    synthesis_keeps_default_off = "default-off" in str(
        synthesis_status.get("recommendation") or ""
    ).lower()

    free_ghost_threshold = _optional_int(candidate_evidence.get("free_ghost_threshold"))
    fixed_anchor_threshold = _optional_int(candidate_evidence.get("fixed_anchor_threshold"))
    threshold_delta = (
        int(free_ghost_threshold - fixed_anchor_threshold)
        if free_ghost_threshold is not None and fixed_anchor_threshold is not None
        else None
    )

    design_ready = bool(
        candidate_present
        and order_present
        and synthesis_present
        and candidate_gate_passed
        and candidate_points_to_witness
        and exact_three_label_core
        and all_single_x_domain
        and all_no_below_ghost_room
        and all_above_counts_match_avoiding
        and shared_safe_strip_lower_bound is not None
        and all_labels_overlap_all_anchors
    )

    checks = [
        _check(
            "row_domain_extraction_candidate_present",
            "pass" if candidate_present else "fail",
            "row-domain extraction candidate loaded"
            if candidate_present
            else candidate_error
            or f"missing:{_display_path(project_root, candidate_resolved)}",
        ),
        _check(
            "row_domain_candidate_gate_passed",
            "pass" if candidate_gate_passed else "fail",
            str(candidate_status.get("recommendation") or "design gate not passed"),
        ),
        _check(
            "candidate_points_to_witness_step",
            "pass" if candidate_points_to_witness else "fail",
            f"recommended_next_step={candidate_status.get('recommended_next_step')}",
        ),
        _check(
            "order_domain_extraction_present",
            "pass" if order_present else "fail",
            "order-domain extraction loaded"
            if order_present
            else order_error or f"missing:{_display_path(project_root, order_resolved)}",
        ),
        _check(
            "exact_three_label_core_available",
            "pass" if exact_three_label_core else "fail",
            f"forced_label_count={len(forced_labels)} row_entry_count={len(row_entries)}",
        ),
        _check(
            "all_core_labels_have_single_x_domain",
            "pass" if all_single_x_domain else "fail",
            f"x_domain_counts={[entry.get('x_domain_count') for entry in row_entries]}",
        ),
        _check(
            "all_core_labels_have_no_below_ghost_room",
            "pass" if all_no_below_ghost_room else "fail",
            f"below_y_counts={[entry.get('below_y_count') for entry in row_entries]}",
        ),
        _check(
            "shared_safe_strip_lower_bound_present",
            "pass" if shared_safe_strip_lower_bound is not None else "fail",
            f"shared_safe_strip_lower_bound={shared_safe_strip_lower_bound}",
        ),
        _check(
            "all_labels_overlap_all_anchors",
            "pass" if all_labels_overlap_all_anchors else "fail",
            f"all_forced_labels_x_overlap_all_anchors={all_labels_overlap_all_anchors}",
        ),
        _check(
            "global_context_synthesis_present",
            "pass" if synthesis_present else "fail",
            "global-context synthesis loaded"
            if synthesis_present
            else synthesis_error
            or f"missing:{_display_path(project_root, synthesis_resolved)}",
        ),
        _check(
            "default_off_context_retained",
            "pass" if synthesis_keeps_default_off else "fail",
            str(synthesis_status.get("recommendation") or synthesis_status.get("outcome")),
        ),
        _check(
            "runtime_promotion_guard",
            "fail",
            (
                "row-domain/count witness design is still pre-implementation; keep runtime default-off "
                "until the anchored bridge and non-trigger controls are extracted and verified"
            ),
        ),
    ]

    return {
        "metadata": {
            "source": ROW_DOMAIN_COUNT_WITNESS_DESIGN_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "coordinate_validation_row_domain_count_witness_design_not_proof_source"
            ),
            "solver_invoked": False,
            "proof_source": False,
        },
        "paths": {
            "project_root": str(project_root),
            "row_domain_extraction_candidate": _display_path(project_root, candidate_resolved),
            "order_domain_extraction": _display_path(project_root, order_resolved),
            "global_context_synthesis": _display_path(project_root, synthesis_resolved),
        },
        "candidate": dict(candidate),
        "status": {
            "design_ready": bool(design_ready),
            "runtime_promotion_ready": False,
            "witness_shape": "three_label_overlap_above_strip_count_guard",
            "recommended_next_step": "implement_row_domain_count_witness",
            "recommendation": _recommendation(design_ready),
        },
        "witness_design": {
            "core_label_count": len(forced_labels),
            "forced_labels": forced_labels,
            "row_summaries": row_entries,
            "shared_safe_strip_lower_bound": shared_safe_strip_lower_bound,
            "all_single_x_domain": all_single_x_domain,
            "all_no_below_ghost_room": all_no_below_ghost_room,
            "all_above_counts_match_avoiding": all_above_counts_match_avoiding,
            "all_labels_overlap_all_anchors": all_labels_overlap_all_anchors,
            "implied_fixed_slots": list(candidate_evidence.get("implied_fixed_slots", [])),
        },
        "count_witness": {
            "free_ghost_threshold": free_ghost_threshold,
            "fixed_anchor_threshold": fixed_anchor_threshold,
            "threshold_delta": threshold_delta,
            "highest_non_exceeded_unknown_slot_index": candidate_evidence.get(
                "highest_non_exceeded_unknown_slot_index"
            ),
            "exceeded_infeasible_slot_indices": list(
                candidate_evidence.get("exceeded_infeasible_slot_indices", [])
            ),
            "ghost_avoiding_y_counts": list(candidate_evidence.get("ghost_avoiding_y_counts", [])),
            "planter_order_implication_count": candidate_evidence.get(
                "planter_order_implication_count"
            ),
        },
        "required_outputs": [
            "Extract the three forced-label row domains with exact row counts and safe-strip bounds.",
            "Encode the shared above-ghost strip lower bound and prove all three labels have no below-ghost room.",
            "Bridge the count transition from free_ghost_threshold=15 to fixed_anchor_threshold=14 for the anchored case.",
            "Define non-trigger controls for anchors missing the same three-label overlap or staying at slot count <= 13.",
            "Keep the runtime slice default-off until the anchored bridge is verified end-to-end.",
        ],
        "checks": checks,
    }


def render_phase3b_coordinate_validation_row_domain_count_witness_design_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    witness = _mapping(report.get("witness_design"))
    count_witness = _mapping(report.get("count_witness"))
    lines = [
        "# Phase 3B Coordinate-Validation Row-Domain Count Witness Design",
        "",
        f"- Design ready: {bool(status.get('design_ready', False))}",
        f"- Runtime promotion ready: {bool(status.get('runtime_promotion_ready', False))}",
        f"- Witness shape: {status.get('witness_shape')}",
        f"- Recommended next step: {status.get('recommended_next_step')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Witness Design",
        "",
        f"- Core label count: {witness.get('core_label_count')}",
        f"- Shared safe-strip lower bound: {witness.get('shared_safe_strip_lower_bound')}",
        f"- All single x-domain: {witness.get('all_single_x_domain')}",
        f"- All no below-ghost room: {witness.get('all_no_below_ghost_room')}",
        f"- All labels overlap all anchors: {witness.get('all_labels_overlap_all_anchors')}",
        f"- Implied fixed slots: {witness.get('implied_fixed_slots')}",
        "",
        "## Count Witness",
        "",
        f"- Free-ghost threshold: {count_witness.get('free_ghost_threshold')}",
        f"- Fixed-anchor threshold: {count_witness.get('fixed_anchor_threshold')}",
        f"- Threshold delta: {count_witness.get('threshold_delta')}",
        f"- Highest non-exceeded unknown slot index: {count_witness.get('highest_non_exceeded_unknown_slot_index')}",
        f"- Exceeded infeasible slot indices: {count_witness.get('exceeded_infeasible_slot_indices')}",
        "",
        "## Row Summaries",
        "",
        "| Group | Slot | Forced X | Row Count | Avoiding Y Count | Below Y Count | Above Y Count |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in list(witness.get("row_summaries", [])):
        if isinstance(row, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(row.get("group_id")),
                        _markdown_cell(row.get("slot_index")),
                        _markdown_cell(row.get("forced_x")),
                        _markdown_cell(row.get("row_count")),
                        _markdown_cell(row.get("avoiding_y_count")),
                        _markdown_cell(row.get("below_y_count")),
                        _markdown_cell(row.get("above_y_count")),
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


def render_phase3b_coordinate_validation_row_domain_count_witness_design_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    witness = _mapping(report.get("witness_design"))
    count_witness = _mapping(report.get("count_witness"))
    lines = [
        "Phase 3B coordinate-validation row-domain count witness design",
        f"design_ready={bool(status.get('design_ready', False))}",
        f"runtime_promotion_ready={bool(status.get('runtime_promotion_ready', False))}",
        f"witness_shape={status.get('witness_shape')}",
        f"recommended_next_step={status.get('recommended_next_step')}",
        f"shared_safe_strip_lower_bound={witness.get('shared_safe_strip_lower_bound')}",
        f"row_counts={[row.get('row_count') for row in list(witness.get('row_summaries', [])) if isinstance(row, Mapping)]}",
        f"avoiding_y_counts={[row.get('avoiding_y_count') for row in list(witness.get('row_summaries', [])) if isinstance(row, Mapping)]}",
        f"threshold_delta={count_witness.get('threshold_delta')}",
        f"recommendation={status.get('recommendation')}",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                f"check id={check.get('check_id')} status={check.get('status')} detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _extract_row_entries(
    order_report: Optional[Mapping[str, Any]],
    forced_labels: Iterable[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    if not order_report:
        return []
    entry_by_key: Dict[tuple[str, int], Mapping[str, Any]] = {}
    for group in list(order_report.get("groups", [])):
        if not isinstance(group, Mapping):
            continue
        group_id = str(group.get("group_id", ""))
        for entry in list(group.get("entries", [])):
            if not isinstance(entry, Mapping):
                continue
            slot_index = _optional_int(entry.get("slot_index"))
            key = (group_id, slot_index if slot_index is not None else -1)
            entry_by_key[key] = entry

    rows: list[Dict[str, Any]] = []
    for label in forced_labels:
        group_id = str(label.get("group_id", ""))
        slot_index_value = _optional_int(label.get("slot_index"))
        slot_index = slot_index_value if slot_index_value is not None else -1
        entry = _mapping(entry_by_key.get((group_id, slot_index)))
        avoiding = _mapping(entry.get("anchor119_avoiding_y"))
        below = _mapping(entry.get("anchor119_below_y"))
        above = _mapping(entry.get("anchor119_above_y"))
        x_domain = _mapping(entry.get("x_domain"))
        y_domain = _mapping(entry.get("y_domain"))
        rows.append(
            {
                "group_id": group_id,
                "solution_id": label.get("solution_id"),
                "slot_index": slot_index,
                "template": label.get("template"),
                "forced_x": label.get("forced_value"),
                "row_count": _optional_int(entry.get("order_filtered_row_count")),
                "x_domain_count": _optional_int(x_domain.get("count")),
                "y_domain_count": _optional_int(y_domain.get("count")),
                "avoiding_y_count": _optional_int(avoiding.get("count")),
                "avoiding_y_min": _optional_int(avoiding.get("min")),
                "avoiding_y_max": _optional_int(avoiding.get("max")),
                "below_y_count": _optional_int(below.get("count")),
                "above_y_count": _optional_int(above.get("count")),
            }
        )
    return rows


def _shared_int(values: Iterable[Any]) -> Optional[int]:
    normalized = [int(value) for value in values if value is not None]
    if not normalized:
        return None
    first = normalized[0]
    if all(value == first for value in normalized):
        return first
    return None


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _recommendation(design_ready: bool) -> str:
    if design_ready:
        return (
            "Row-domain/count witness design is ready: implement the deterministic three-label "
            "row/count witness, then bridge it back into the anchored B5A guard without changing "
            "runtime semantics by default."
        )
    return "Row-domain/count witness design is incomplete; repair prerequisite evidence first."


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


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
