from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

B5A_BLOCKER_PIVOT_SOURCE = "phase3b_b5a_blocker_pivot_v1"


def build_phase3b_b5a_blocker_pivot(
    project_root: Path,
    *,
    workspace_root: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    workspace_root = Path(workspace_root or project_root).resolve()
    started = time.perf_counter()
    paths = _paths(workspace_root)
    reports = {key: _load_json(path) for key, path in paths.items()}
    closed_branches = _closed_branches(reports)
    open_branch = _open_branch(reports)
    status = _status(reports, closed_branches, open_branch)
    return {
        "metadata": {
            "source": B5A_BLOCKER_PIVOT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "b5a_blocker_pivot_report_only_not_proof_source",
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "workspace_root": str(workspace_root),
            **{key: str(path) for key, path in paths.items()},
        },
        "status": status,
        "closed_branches": closed_branches,
        "open_branch": open_branch,
        "report_status": {
            key: {
                "present": value[0] is not None,
                "load_error": value[1],
            }
            for key, value in reports.items()
        },
        "checks": _checks(status, reports),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }


def render_phase3b_b5a_blocker_pivot_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    open_branch = _mapping(report.get("open_branch"))
    lines = [
        "# Phase 3B B5A Blocker Pivot",
        "",
        f"- Outcome: {_markdown_cell(status.get('outcome'))}",
        f"- Runtime promotion ready: {_markdown_cell(status.get('runtime_promotion_ready'))}",
        f"- Recommendation: {_markdown_cell(status.get('recommendation'))}",
        "",
        "## Closed Branches",
        "",
        "| Branch | Outcome | Reason |",
        "| --- | --- | --- |",
    ]
    for branch in list(report.get("closed_branches", [])):
        if isinstance(branch, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(branch.get("branch")),
                        _markdown_cell(branch.get("outcome")),
                        _markdown_cell(branch.get("reason")),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Open Branch",
            "",
            f"- Branch: {_markdown_cell(open_branch.get('branch'))}",
            f"- Evidence: {_markdown_cell(open_branch.get('evidence'))}",
            f"- Next action: {_markdown_cell(open_branch.get('next_action'))}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_phase3b_b5a_blocker_pivot_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    open_branch = _mapping(report.get("open_branch"))
    lines = [
        "Phase 3B B5A blocker pivot",
        f"outcome={status.get('outcome')}",
        f"runtime_promotion_ready={status.get('runtime_promotion_ready')}",
        f"recommendation={status.get('recommendation')}",
        "",
        "closed_branches:",
    ]
    for branch in list(report.get("closed_branches", [])):
        if isinstance(branch, Mapping):
            lines.append(
                f"  {branch.get('branch')}: {branch.get('outcome')} - {branch.get('reason')}"
            )
    lines.extend(
        [
            "",
            f"open_branch={open_branch.get('branch')}",
            f"next_action={open_branch.get('next_action')}",
        ]
    )
    return "\n".join(lines) + "\n"


def _paths(root: Path) -> Dict[str, Path]:
    return {
        "b5a_summary": root / ".artifacts/phase3b_b5_anchor_sprint/operator_summary.json",
        "triage": root / ".artifacts/phase3b_unknown_triage/blocker_inventory.json",
        "residual_taxonomy": root
        / ".artifacts/phase3b_residual_pose_order_taxonomy/residual_pose_order_taxonomy.json",
        "predicate_scan": root
        / ".artifacts/phase3b_order_independent_predicate_scan/order_independent_predicate_scan.json",
        "y_unique": root / ".artifacts/phase3b_y_unique_local_hypothesis/y_unique_local_hypothesis.json",
        "power_protocol": root / ".artifacts/phase3b_power_protocol_interaction/power_protocol_interaction.json",
    }


def _closed_branches(reports: Mapping[str, tuple[Optional[Mapping[str, Any]], Optional[str]]]) -> list[Dict[str, Any]]:
    branches: list[Dict[str, Any]] = []
    predicate = _report(reports, "predicate_scan")
    if _mapping(predicate.get("status")).get("outcome") == "no_order_independent_predicate_found":
        branches.append(
            {
                "branch": "geometry_order_global_predicate",
                "outcome": "closed_for_promotion",
                "reason": "No global order-independent feature survived the all-INFEASIBLE/no-UNKNOWN scan.",
            }
        )
    y_unique = _report(reports, "y_unique")
    if _mapping(y_unique.get("status")).get("outcome") == "class_local_clue_deprioritized_by_existing_negative_validation":
        branches.append(
            {
                "branch": "buckwheat_y_unique_local_clue",
                "outcome": "deprioritized",
                "reason": "Existing anchor159 no-overlap/capacity diagnostics failed to turn y_unique:11 into a proof-like cut.",
            }
        )
    taxonomy = _report(reports, "residual_taxonomy")
    if _mapping(taxonomy.get("status")).get("outcome") == "stable_ordering_sensitive_class_observed":
        branches.append(
            {
                "branch": "residual_anchor_taxonomy",
                "outcome": "complete_diagnostic_inventory",
                "reason": "All eight residual anchors are classified; inventory is diagnostic-only and not promotion evidence.",
            }
        )
    return branches


def _open_branch(reports: Mapping[str, tuple[Optional[Mapping[str, Any]], Optional[str]]]) -> Dict[str, Any]:
    power_protocol = _report(reports, "power_protocol")
    recommendation = power_protocol.get("recommendation")
    if not recommendation:
        recommendation = _mapping(power_protocol.get("status")).get("recommendation")
    if recommendation:
        return {
            "branch": "power_protocol_family_lookup_global_blocker",
            "evidence": recommendation,
            "next_action": (
                "Return to the power/protocol/family lookup blocker with diagnostic-only "
                "encoding or presolve-profile work; do not rerun B5A blindly."
            ),
        }
    return {
        "branch": "broader_b5a_blocker_refresh",
        "evidence": "Power/protocol interaction report missing or unreadable.",
        "next_action": "Refresh B5A triage and power/protocol interaction reports before choosing a runtime branch.",
    }


def _status(
    reports: Mapping[str, tuple[Optional[Mapping[str, Any]], Optional[str]]],
    closed_branches: list[Mapping[str, Any]],
    open_branch: Mapping[str, Any],
) -> Dict[str, Any]:
    b5a = _report(reports, "b5a_summary")
    b5a_status = _mapping(b5a.get("status"))
    anchor_found = bool(b5a_status.get("anchor_found", False))
    outcome = "pivot_to_power_protocol_global_blocker" if not anchor_found else "anchor_found_unexpected"
    return {
        "completed": True,
        "anchor_found": anchor_found,
        "closed_branch_count": len(closed_branches),
        "open_branch": open_branch.get("branch"),
        "outcome": outcome,
        "runtime_promotion_ready": False,
        "proof_source": False,
        "recommendation": (
            "Pivot away from residual geometry/y_unique promotion and return to the "
            "power/protocol/family lookup global blocker."
        ),
    }


def _checks(
    status: Mapping[str, Any],
    reports: Mapping[str, tuple[Optional[Mapping[str, Any]], Optional[str]]],
) -> list[Dict[str, str]]:
    return [
        {
            "check_id": "report_only_semantics",
            "status": "pass",
            "detail": "pivot report only reads existing artifacts and does not invoke solver",
        },
        {
            "check_id": "runtime_promotion_guard",
            "status": "pass",
            "detail": "runtime_promotion_ready remains false",
        },
        {
            "check_id": "b5a_summary_present",
            "status": "pass" if _report(reports, "b5a_summary") else "fail",
            "detail": str(reports.get("b5a_summary", (None, None))[1]),
        },
        {
            "check_id": "power_protocol_report_present",
            "status": "pass" if _report(reports, "power_protocol") else "fail",
            "detail": str(reports.get("power_protocol", (None, None))[1]),
        },
    ]


def _report(
    reports: Mapping[str, tuple[Optional[Mapping[str, Any]], Optional[str]]],
    key: str,
) -> Mapping[str, Any]:
    value = reports.get(key)
    if not value:
        return {}
    report, _error = value
    return report if isinstance(report, Mapping) else {}


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
