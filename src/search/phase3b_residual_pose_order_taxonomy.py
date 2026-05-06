from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.search.exact_campaign import now_iso
from src.search.phase3b_greedy_pose_order_comparison import (
    DEFAULT_FIELD_VARIANT,
    DEFAULT_TARGET_GROUP_ID,
)

RESIDUAL_POSE_ORDER_TAXONOMY_SOURCE = "phase3b_residual_pose_order_taxonomy_v1"
DEFAULT_RESIDUAL_ANCHORS = (159, 171, 172, 173, 217, 229, 230, 231)


def build_phase3b_residual_pose_order_taxonomy(
    project_root: Path,
    *,
    anchors: Optional[Sequence[int]] = None,
    group_id: str = DEFAULT_TARGET_GROUP_ID,
    field_variant: str = DEFAULT_FIELD_VARIANT,
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
    entries = [
        _build_anchor_entry(
            artifact_root=artifact_root,
            anchor_idx=anchor_idx,
            group_id=str(group_id),
            field_variant=str(field_variant),
        )
        for anchor_idx in normalized_anchors
    ]
    taxonomy_counts = Counter(str(entry.get("taxonomy_class", "unknown")) for entry in entries)
    artifact_missing_count = sum(
        1 for entry in entries if not bool(entry.get("artifact_coverage_complete"))
    )
    observed_entries = [
        entry
        for entry in entries
        if str(entry.get("taxonomy_class", "")).endswith(
            "_ordering_sensitive_diagnostic"
        )
    ]
    runtime_promotion_ready = False
    status = {
        "completed": True,
        "evaluated_anchor_count": len(entries),
        "observed_ordering_sensitive_count": len(observed_entries),
        "artifact_missing_count": artifact_missing_count,
        "taxonomy_counts": dict(sorted(taxonomy_counts.items())),
        "outcome": _outcome(
            entries,
            artifact_missing_count=artifact_missing_count,
            observed_count=len(observed_entries),
        ),
        "runtime_promotion_ready": runtime_promotion_ready,
        "proof_source": False,
        "recommendation": _recommendation(
            artifact_missing_count=artifact_missing_count,
            observed_count=len(observed_entries),
            total_count=len(entries),
        ),
    }
    return {
        "metadata": {
            "source": RESIDUAL_POSE_ORDER_TAXONOMY_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "taxonomy_report_only_not_proof_source",
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "artifact_root": str(artifact_root),
        },
        "profile": {
            "anchors": normalized_anchors,
            "group_id": str(group_id),
            "field_variant": str(field_variant),
        },
        "status": status,
        "anchors": entries,
        "checks": _checks(entries, status),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }


def render_phase3b_residual_pose_order_taxonomy_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    profile = _mapping(report.get("profile"))
    lines = [
        "# Phase 3B Residual Pose-Order Taxonomy",
        "",
        f"- Group: {_markdown_cell(profile.get('group_id'))}",
        f"- Field variant: {_markdown_cell(profile.get('field_variant'))}",
        f"- Outcome: {_markdown_cell(status.get('outcome'))}",
        f"- Observed ordering-sensitive anchors: {_markdown_cell(status.get('observed_ordering_sensitive_count'))}",
        f"- Runtime promotion ready: {_markdown_cell(status.get('runtime_promotion_ready'))}",
        f"- Recommendation: {_markdown_cell(status.get('recommendation'))}",
        "",
        "## Anchor Taxonomy",
        "",
        "| Anchor | Class | Group target | Field status | Greedy outcome | Artifacts |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(report.get("anchors", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("anchor_idx")),
                    _markdown_cell(entry.get("taxonomy_class")),
                    _markdown_cell(entry.get("group_target_first_infeasible")),
                    _markdown_cell(entry.get("target_field_status")),
                    _markdown_cell(entry.get("greedy_outcome")),
                    _markdown_cell(_artifact_summary(_mapping(entry.get("artifact_status")))),
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


def render_phase3b_residual_pose_order_taxonomy_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    profile = _mapping(report.get("profile"))
    lines = [
        "Phase 3B residual pose-order taxonomy",
        f"group={profile.get('group_id')}",
        f"field_variant={profile.get('field_variant')}",
        f"outcome={status.get('outcome')}",
        f"observed_ordering_sensitive={status.get('observed_ordering_sensitive_count')}",
        f"runtime_promotion_ready={status.get('runtime_promotion_ready')}",
        f"recommendation={status.get('recommendation')}",
        "",
        "anchors:",
    ]
    for entry in list(report.get("anchors", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "  "
                + ", ".join(
                    [
                        f"anchor={entry.get('anchor_idx')}",
                        f"class={entry.get('taxonomy_class')}",
                        f"group_target={entry.get('group_target_first_infeasible')}",
                        f"field={entry.get('target_field_status')}",
                        f"greedy={entry.get('greedy_outcome')}",
                        f"artifacts={_artifact_summary(_mapping(entry.get('artifact_status')))}",
                    ]
                )
            )
    return "\n".join(lines) + "\n"


def _build_anchor_entry(
    *,
    artifact_root: Path,
    anchor_idx: int,
    group_id: str,
    field_variant: str,
) -> Dict[str, Any]:
    paths = _artifact_paths(artifact_root, anchor_idx)
    group_report, group_error = _load_json(paths["group_delta"])
    field_report, field_error = _load_json(paths["field_channel"])
    greedy_report, greedy_error = _load_json(paths["greedy_pose_order"])
    group_info = _group_info(group_report, group_id=group_id)
    first_group_id = _first_item(group_info.get("first_infeasible_group_ids", []))
    first_group_paths = (
        _followup_artifact_paths(artifact_root, anchor_idx, first_group_id)
        if first_group_id and first_group_id != group_id
        else {}
    )
    first_field_report, first_field_error = _load_json(first_group_paths["field_channel"]) if first_group_paths else (None, None)
    first_greedy_report, first_greedy_error = _load_json(first_group_paths["greedy_pose_order"]) if first_group_paths else (None, None)
    field_info = _field_info(field_report, field_variant=field_variant)
    greedy_info = _greedy_info(greedy_report)
    first_field_info = _field_info(first_field_report, field_variant=field_variant)
    first_greedy_info = _greedy_info(first_greedy_report)
    taxonomy_class = _taxonomy_class(group_info, field_info, greedy_info, first_field_info, first_greedy_info)
    artifact_status = {
        "group_delta": _artifact_status(group_report, group_error),
        "field_channel": _artifact_status(field_report, field_error),
        "greedy_pose_order": _artifact_status(greedy_report, greedy_error),
        **(
            {
                "first_group_field_channel": _artifact_status(
                    first_field_report,
                    first_field_error,
                ),
                "first_group_greedy_pose_order": _artifact_status(
                    first_greedy_report,
                    first_greedy_error,
                ),
            }
            if first_group_paths
            else {}
        ),
    }
    return {
        "anchor_idx": int(anchor_idx),
        "taxonomy_class": taxonomy_class,
        "artifact_paths": {
            **{key: str(value) for key, value in paths.items()},
            **{
                f"first_group_{key}": str(value)
                for key, value in first_group_paths.items()
            },
        },
        "artifact_status": artifact_status,
        "artifact_coverage_complete": _artifact_coverage_complete(
            taxonomy_class,
            artifact_status,
        ),
        "artifact_errors": {
            key: error
            for key, error in {
                "group_delta": group_error,
                "field_channel": field_error,
                "greedy_pose_order": greedy_error,
                "first_group_field_channel": first_field_error,
                "first_group_greedy_pose_order": first_greedy_error,
            }.items()
            if error
        },
        "group_outcome": group_info.get("outcome"),
        "group_target_first_infeasible": group_info.get("target_first_infeasible"),
        "group_first_infeasible_case_id": group_info.get("first_infeasible_case_id"),
        "group_first_infeasible_group_ids": group_info.get("first_infeasible_group_ids", []),
        "target_field_status": field_info.get("target_field_status"),
        "field_statuses": field_info.get("field_statuses", {}),
        "greedy_outcome": greedy_info.get("outcome"),
        "greedy_statuses": greedy_info.get("strategy_statuses", {}),
        "first_group_field_status": first_field_info.get("target_field_status"),
        "first_group_field_statuses": first_field_info.get("field_statuses", {}),
        "first_group_greedy_outcome": first_greedy_info.get("outcome"),
        "first_group_greedy_statuses": first_greedy_info.get("strategy_statuses", {}),
        "single_group_blocked_vs_full_blocked": greedy_info.get(
            "single_group_blocked_vs_full_blocked", {}
        ),
        "diagnostic_only": True,
        "runtime_promotion_ready": False,
    }


def _artifact_paths(artifact_root: Path, anchor_idx: int) -> Dict[str, Path]:
    return {
        "group_delta": artifact_root
        / f"phase3b_coordinate_validation_group_delta_anchor{anchor_idx}"
        / f"coordinate_validation_group_delta_anchor{anchor_idx}.json",
        "field_channel": artifact_root
        / f"phase3b_coordinate_validation_field_channel_delta_anchor{anchor_idx}_planter_buckwheat_ghost_labels"
        / f"field_channel_delta_anchor{anchor_idx}_planter_buckwheat_ghost_labels.json",
        "greedy_pose_order": artifact_root
        / f"phase3b_greedy_pose_order_comparison_anchor{anchor_idx}_planter_buckwheat_xy"
        / f"greedy_pose_order_comparison_anchor{anchor_idx}_planter_buckwheat_xy.json",
    }


def _followup_artifact_paths(
    artifact_root: Path,
    anchor_idx: int,
    group_id: str,
) -> Dict[str, Path]:
    operation_slug = _operation_slug_from_group_id(group_id)
    if not operation_slug:
        return {}
    return {
        "field_channel": artifact_root
        / f"phase3b_coordinate_validation_field_channel_delta_anchor{anchor_idx}_{operation_slug}_ghost_labels"
        / f"field_channel_delta_anchor{anchor_idx}_{operation_slug}_ghost_labels.json",
        "greedy_pose_order": artifact_root
        / f"phase3b_greedy_pose_order_comparison_anchor{anchor_idx}_{operation_slug}_xy"
        / f"greedy_pose_order_comparison_anchor{anchor_idx}_{operation_slug}_xy.json",
    }


def _operation_slug_from_group_id(group_id: str) -> str:
    parts = str(group_id).split("::")
    if len(parts) >= 4 and parts[0] == "group":
        return parts[2]
    return ""


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


def _group_info(report: Optional[Mapping[str, Any]], *, group_id: str) -> Dict[str, Any]:
    if not report:
        return {}
    status = _mapping(report.get("status"))
    delta = _mapping(report.get("delta"))
    first = _mapping(
        delta.get("first_narrower_infeasible_entry")
        or delta.get("first_infeasible_entry")
    )
    included_ids = [str(value) for value in first.get("included_group_ids", [])]
    return {
        "outcome": status.get("outcome"),
        "target_first_infeasible": group_id in included_ids,
        "first_infeasible_case_id": first.get("case_id"),
        "first_infeasible_group_ids": included_ids,
    }


def _field_info(report: Optional[Mapping[str, Any]], *, field_variant: str) -> Dict[str, Any]:
    if not report:
        return {}
    entries = list(_mapping(report.get("field_channel_delta")).get("entries", []))
    field_statuses: Dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        variant = str(entry.get("field_variant", ""))
        status = str(_mapping(entry.get("validation")).get("status", ""))
        if variant:
            field_statuses[variant] = status
    return {
        "target_field_status": field_statuses.get(str(field_variant), ""),
        "field_statuses": field_statuses,
    }


def _greedy_info(report: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not report:
        return {}
    entries = list(_mapping(report.get("comparison")).get("entries", []))
    strategy_statuses: Dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        strategy = str(entry.get("strategy", ""))
        status = str(_mapping(entry.get("target_validation")).get("status", ""))
        if strategy:
            strategy_statuses[strategy] = status
    return {
        "outcome": _mapping(report.get("status")).get("outcome"),
        "strategy_statuses": strategy_statuses,
        "single_group_blocked_vs_full_blocked": _mapping(
            _mapping(report.get("comparison")).get("single_group_blocked_vs_full_blocked")
        ),
    }


def _taxonomy_class(
    group_info: Mapping[str, Any],
    field_info: Mapping[str, Any],
    greedy_info: Mapping[str, Any],
    first_field_info: Mapping[str, Any],
    first_greedy_info: Mapping[str, Any],
) -> str:
    if (
        group_info.get("target_first_infeasible") is True
        and field_info.get("target_field_status") == "INFEASIBLE"
        and greedy_info.get("outcome") == "ordering_sensitive_infeasible"
    ):
        return "planter_buckwheat_xy_ordering_sensitive_diagnostic"
    if not group_info and not field_info and not greedy_info:
        return "missing_artifacts"
    if (
        group_info.get("outcome") == "coordinate_validation_delta_infeasible_found"
        and group_info.get("target_first_infeasible") is False
    ):
        if (
            first_field_info.get("target_field_status") == "INFEASIBLE"
            and first_greedy_info.get("outcome") == "ordering_sensitive_infeasible"
        ):
            return "non_target_first_group_ordering_sensitive_diagnostic"
        return "non_target_first_group_delta_diagnostic"
    if group_info.get("target_first_infeasible") is True:
        return "target_group_infeasible_incomplete_taxonomy"
    return "mixed_or_unclassified"


def _outcome(
    entries: Sequence[Mapping[str, Any]],
    *,
    artifact_missing_count: int,
    observed_count: int,
) -> str:
    if not entries:
        return "no_anchors_requested"
    if observed_count == len(entries):
        return "stable_ordering_sensitive_class_observed"
    if observed_count > 0 and artifact_missing_count > 0:
        return "partial_ordering_sensitive_class_observed"
    if artifact_missing_count == len(entries):
        return "all_artifacts_missing"
    return "mixed_or_incomplete_taxonomy"


def _recommendation(
    *,
    artifact_missing_count: int,
    observed_count: int,
    total_count: int,
) -> str:
    if observed_count >= 3:
        return (
            "Build the next diagnostic around this taxonomy, but keep it report-only; "
            "runtime promotion still needs an order-independent predicate or proof-safe order contract."
        )
    if artifact_missing_count:
        return (
            "Complete missing group/field/greedy artifacts for selected residual anchors "
            "before changing runtime behavior."
        )
    return (
        "Use this as a diagnostic inventory only; do not promote without exact-safe evidence."
    )


def _checks(entries: Sequence[Mapping[str, Any]], status: Mapping[str, Any]) -> list[Dict[str, str]]:
    observed_count = int(status.get("observed_ordering_sensitive_count", 0) or 0)
    missing_count = int(status.get("artifact_missing_count", 0) or 0)
    return [
        {
            "check_id": "report_only_semantics",
            "status": "pass",
            "detail": "taxonomy does not invoke solver and is not proof-source evidence",
        },
        {
            "check_id": "runtime_promotion_guard",
            "status": "pass",
            "detail": "runtime_promotion_ready is fixed false for this diagnostic taxonomy",
        },
        {
            "check_id": "ordering_sensitive_observed",
            "status": "pass" if observed_count > 0 else "fail",
            "detail": f"{observed_count}/{len(entries)} anchors match the ordering-sensitive diagnostic class",
        },
        {
            "check_id": "artifact_coverage",
            "status": "pass" if missing_count == 0 else "skipped",
            "detail": f"{missing_count} requested anchors have at least one missing artifact",
        },
    ]


def _artifact_status(report: Optional[Mapping[str, Any]], error: Optional[str]) -> str:
    if error == "missing":
        return "missing"
    if error:
        return "error"
    if report:
        return "present"
    return "unknown"


def _artifact_summary(statuses: Mapping[str, Any]) -> str:
    return ",".join(f"{key}:{value}" for key, value in sorted(statuses.items()))


def _artifact_coverage_complete(
    taxonomy_class: str,
    statuses: Mapping[str, Any],
) -> bool:
    if taxonomy_class == "planter_buckwheat_xy_ordering_sensitive_diagnostic":
        required = ("group_delta", "field_channel", "greedy_pose_order")
    elif taxonomy_class == "non_target_first_group_ordering_sensitive_diagnostic":
        required = (
            "group_delta",
            "first_group_field_channel",
            "first_group_greedy_pose_order",
        )
    elif taxonomy_class == "non_target_first_group_delta_diagnostic":
        required = ("group_delta",)
    else:
        return False
    return all(statuses.get(key) == "present" for key in required)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_item(value: Any) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return str(value[0]) if value else ""
    return ""


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
