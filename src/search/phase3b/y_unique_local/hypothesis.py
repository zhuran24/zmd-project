from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

Y_UNIQUE_LOCAL_HYPOTHESIS_SOURCE = "phase3b_y_unique_local_hypothesis_v1"


def build_phase3b_y_unique_local_hypothesis(
    project_root: Path,
    *,
    predicate_scan_path: Optional[Path] = None,
    geometry_signature_path: Optional[Path] = None,
    no_overlap_anchor159_path: Optional[Path] = None,
    capacity_anchor159_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    predicate_path = _default_path(
        project_root,
        predicate_scan_path,
        ".artifacts/phase3b_order_independent_predicate_scan/order_independent_predicate_scan.json",
    )
    geometry_path = _default_path(
        project_root,
        geometry_signature_path,
        ".artifacts/phase3b_pose_order_geometry_signature/pose_order_geometry_signature.json",
    )
    no_overlap_path = _default_path(
        project_root,
        no_overlap_anchor159_path,
        ".artifacts/phase3b_coordinate_validation_no_overlap_subset_delta_anchor159_planter_buckwheat_xy/no_overlap_subset_delta_anchor159_planter_buckwheat_xy.json",
    )
    capacity_path = _default_path(
        project_root,
        capacity_anchor159_path,
        ".artifacts/phase3b_coordinate_validation_capacity_cut_design_anchor159_planter_buckwheat_xy/capacity_cut_design_anchor159_planter_buckwheat_xy.json",
    )
    started = time.perf_counter()
    predicate_scan, predicate_error = _load_json(predicate_path)
    geometry_signature, geometry_error = _load_json(geometry_path)
    no_overlap, no_overlap_error = _load_json(no_overlap_path)
    capacity, capacity_error = _load_json(capacity_path)
    y_unique_feature = _feature_present(predicate_scan, "y_unique:11")
    buckwheat = _buckwheat_summary(geometry_signature)
    prior_validation = {
        "no_overlap_anchor159": _prior_result(no_overlap, no_overlap_error),
        "capacity_anchor159": _prior_result(capacity, capacity_error),
    }
    status = _status(
        y_unique_feature=y_unique_feature,
        prior_validation=prior_validation,
        predicate_error=predicate_error,
        geometry_error=geometry_error,
    )
    return {
        "metadata": {
            "source": Y_UNIQUE_LOCAL_HYPOTHESIS_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "class_local_hypothesis_report_only_not_proof_source",
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "predicate_scan": str(predicate_path),
            "geometry_signature": str(geometry_path),
            "no_overlap_anchor159": str(no_overlap_path),
            "capacity_anchor159": str(capacity_path),
        },
        "hypothesis": {
            "feature": "y_unique:11",
            "scope": "buckwheat_class_local_only",
            "global_order_independent": False,
            "runtime_promotion_ready": False,
            "proof_source": False,
        },
        "predicate_scan": {
            "present": predicate_scan is not None,
            "load_error": predicate_error,
            "outcome": _mapping(predicate_scan.get("status")).get("outcome")
            if predicate_scan
            else None,
            "global_candidate_features": list(
                _mapping(predicate_scan.get("global_scan")).get("candidate_features", [])
            )
            if predicate_scan
            else [],
            "class_local_candidate_features": list(
                _mapping(predicate_scan.get("global_scan")).get(
                    "class_local_candidate_features",
                    [],
                )
            )
            if predicate_scan
            else [],
        },
        "geometry_signature": {
            "present": geometry_signature is not None,
            "load_error": geometry_error,
            "buckwheat": buckwheat,
        },
        "prior_validation": prior_validation,
        "status": status,
        "validation_plan": _validation_plan(status),
        "checks": _checks(status, predicate_error, geometry_error),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }


def render_phase3b_y_unique_local_hypothesis_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    prior = _mapping(report.get("prior_validation"))
    lines = [
        "# Phase 3B y_unique Local Hypothesis",
        "",
        f"- Outcome: {_markdown_cell(status.get('outcome'))}",
        f"- Recommendation: {_markdown_cell(status.get('recommendation'))}",
        f"- Runtime promotion ready: {_markdown_cell(status.get('runtime_promotion_ready'))}",
        "",
        "## Prior Validation",
        "",
        "| Probe | Present | Outcome | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for key, value in sorted(prior.items()):
        if isinstance(value, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(key),
                        _markdown_cell(value.get("present")),
                        _markdown_cell(value.get("outcome")),
                        _markdown_cell(value.get("detail")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Validation Plan", ""])
    for item in list(report.get("validation_plan", [])):
        lines.append(f"- {_markdown_cell(item)}")
    return "\n".join(lines) + "\n"


def render_phase3b_y_unique_local_hypothesis_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "Phase 3B y_unique local hypothesis",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"runtime_promotion_ready={status.get('runtime_promotion_ready')}",
        "",
        "validation_plan:",
    ]
    lines.extend(f"  {item}" for item in list(report.get("validation_plan", [])))
    return "\n".join(lines) + "\n"


def _status(
    *,
    y_unique_feature: bool,
    prior_validation: Mapping[str, Any],
    predicate_error: Optional[str],
    geometry_error: Optional[str],
) -> Dict[str, Any]:
    no_overlap = _mapping(prior_validation.get("no_overlap_anchor159"))
    capacity = _mapping(prior_validation.get("capacity_anchor159"))
    prior_negative = (
        no_overlap.get("outcome") == "base_not_infeasible"
        and capacity.get("outcome") == "minimal_subset_not_found"
    )
    if predicate_error or geometry_error:
        outcome = "missing_inputs"
    elif not y_unique_feature:
        outcome = "y_unique_not_present_as_class_local_clue"
    elif prior_negative:
        outcome = "class_local_clue_deprioritized_by_existing_negative_validation"
    else:
        outcome = "class_local_clue_needs_bounded_validation"
    return {
        "completed": True,
        "outcome": outcome,
        "runtime_promotion_ready": False,
        "proof_source": False,
        "recommendation": _recommendation(outcome),
    }


def _recommendation(outcome: str) -> str:
    if outcome == "class_local_clue_deprioritized_by_existing_negative_validation":
        return (
            "Do not promote y_unique:11. Existing anchor159 no-overlap/capacity "
            "diagnostics already failed to turn the clue into a proof-like cut."
        )
    if outcome == "class_local_clue_needs_bounded_validation":
        return (
            "Treat y_unique:11 as a buckwheat-only hypothesis and validate on a "
            "small representative matrix before any runtime discussion."
        )
    if outcome == "y_unique_not_present_as_class_local_clue":
        return "No y_unique local clue is present in the predicate scan."
    return "Refresh predicate and geometry reports before interpreting y_unique."


def _validation_plan(status: Mapping[str, Any]) -> list[str]:
    if status.get("outcome") == "class_local_clue_deprioritized_by_existing_negative_validation":
        return [
            "Stop geometry/order-only promotion for y_unique:11.",
            "If revisiting, use a new representative anchor such as 217 only as a bounded hypothesis test.",
            "Prefer returning to broader B5A blocker analysis instead of expanding y_unique matrices.",
        ]
    return [
        "Run no-overlap subset delta on one buckwheat representative.",
        "Run capacity cut design on the same representative.",
        "Keep results diagnostic-only unless a base INFEASIBLE and exact-safe minimal subset are both found.",
    ]


def _buckwheat_summary(report: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not report:
        return {}
    summary = _mapping(report.get("class_summary"))
    return dict(summary.get("planter_buckwheat_xy_ordering_sensitive_diagnostic", {}))


def _prior_result(report: Optional[Mapping[str, Any]], error: Optional[str]) -> Dict[str, Any]:
    if error:
        return {"present": False, "load_error": error, "outcome": None, "detail": error}
    status = _mapping(report.get("status")) if report else {}
    return {
        "present": report is not None,
        "load_error": None,
        "outcome": status.get("outcome"),
        "detail": status.get("recommendation"),
    }


def _feature_present(report: Optional[Mapping[str, Any]], feature: str) -> bool:
    if not report:
        return False
    global_scan = _mapping(report.get("global_scan"))
    return feature in set(global_scan.get("class_local_candidate_features", []))


def _checks(
    status: Mapping[str, Any],
    predicate_error: Optional[str],
    geometry_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        {
            "check_id": "report_only_semantics",
            "status": "pass",
            "detail": "report reads existing artifacts and does not invoke solver",
        },
        {
            "check_id": "runtime_promotion_guard",
            "status": "pass",
            "detail": "runtime_promotion_ready remains false",
        },
        {
            "check_id": "inputs_present",
            "status": "pass" if not (predicate_error or geometry_error) else "fail",
            "detail": f"predicate_error={predicate_error}; geometry_error={geometry_error}",
        },
        {
            "check_id": "not_proof_source",
            "status": "pass" if not bool(status.get("proof_source")) else "fail",
            "detail": "y_unique hypothesis is a diagnostic report only",
        },
    ]


def _default_path(project_root: Path, value: Optional[Path], suffix: str) -> Path:
    if value is not None:
        return Path(value).resolve()
    return (project_root / suffix).resolve()


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
