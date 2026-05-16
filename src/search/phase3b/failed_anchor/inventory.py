from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

FAILED_ANCHOR_INVENTORY_SOURCE = "phase3b_failed_anchor_inventory_v1"
DEFAULT_CAMPAIGN_STATE_PATH = Path("data/checkpoints/exact_campaign_state.json")
DEFAULT_FORCED_ANCHOR_DIR = Path(".artifacts/phase3b_forced_anchor_master")
DEFAULT_SOLVER_MATRIX_DIR = Path(".artifacts/phase3b_forced_anchor_solver_matrix")
DEFAULT_CANDIDATE = "69x19"


def build_phase3b_failed_anchor_inventory(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    forced_anchor_dir: Optional[Path] = None,
    solver_matrix_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    forced_dir = _resolve_path(
        project_root,
        forced_anchor_dir if forced_anchor_dir is not None else DEFAULT_FORCED_ANCHOR_DIR,
    )
    matrix_dir = _resolve_path(
        project_root,
        solver_matrix_dir if solver_matrix_dir is not None else DEFAULT_SOLVER_MATRIX_DIR,
    )
    state, state_error = _load_json_mapping(campaign_path)
    candidate_key = str(candidate)
    record = _mapping(_mapping(state.get("candidates")) if state else {}).get(candidate_key)
    record = _mapping(record)
    proof_summary = _mapping(record.get("proof_summary"))
    failure_attribution = _mapping(proof_summary.get("master_start_failure_attribution"))
    samples = [
        _sample_entry(entry)
        for entry in list(failure_attribution.get("failed_anchor_samples", []))
        if isinstance(entry, Mapping)
    ]
    forced_evidence = _load_forced_anchor_evidence(forced_dir, matrix_dir)
    for entry in samples:
        anchor_idx = int(entry["anchor_idx"])
        entry["forced_anchor_evidence"] = forced_evidence.get(anchor_idx, {})
    classification_counts = _count_by(samples, "classification")
    group_counts = _count_by(samples, "group_id")
    forced_status_counts = _forced_status_counts(samples)
    forced_zero_branch_unknown_count = _forced_zero_branch_unknown_count(samples)
    return {
        "metadata": {
            "source": FAILED_ANCHOR_INVENTORY_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
            "forced_anchor_dir": _display_path(project_root, forced_dir),
            "solver_matrix_dir": _display_path(project_root, matrix_dir),
        },
        "candidate": {
            "key": candidate_key,
            "campaign_present": state is not None and state_error is None,
            "campaign_load_error": state_error,
            "candidate_present": bool(record),
            "campaign_status": record.get("status") if record else None,
        },
        "summary": {
            "failed_anchor_count": int(failure_attribution.get("failed_anchor_count", 0))
            if failure_attribution
            else 0,
            "sample_count": len(samples),
            "classification_counts": classification_counts,
            "group_counts": group_counts,
            "forced_status_counts": forced_status_counts,
            "forced_zero_branch_unknown_count": int(forced_zero_branch_unknown_count),
            "recommendation": _recommendation(
                sample_count=len(samples),
                classification_counts=classification_counts,
                forced_status_counts=forced_status_counts,
                forced_zero_branch_unknown_count=forced_zero_branch_unknown_count,
            ),
        },
        "samples": samples,
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            sample_count=len(samples),
        ),
    }


def render_phase3b_failed_anchor_inventory_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    summary = _mapping(report.get("summary"))
    lines = [
        "# Phase 3B Failed-Anchor Inventory",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Sample count: {summary.get('sample_count', 0)}",
        f"- Classification counts: {summary.get('classification_counts', {})}",
        f"- Forced status counts: {summary.get('forced_status_counts', {})}",
        f"- Forced zero-branch UNKNOWN count: {summary.get('forced_zero_branch_unknown_count', 0)}",
        f"- Recommendation: {summary.get('recommendation')}",
        "",
        "## Samples",
        "",
        "| Anchor | Class | Reason | Group | Required | Surviving | Forced Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(report.get("samples", [])):
        if not isinstance(entry, Mapping):
            continue
        evidence = _mapping(entry.get("forced_anchor_evidence"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("anchor_idx")),
                    _markdown_cell(entry.get("classification")),
                    _markdown_cell(entry.get("failure_reason")),
                    _markdown_cell(entry.get("group_id")),
                    _markdown_cell(entry.get("required_count")),
                    _markdown_cell(entry.get("surviving_at_failure_count")),
                    _markdown_cell(evidence.get("status_counts", {})),
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


def render_phase3b_failed_anchor_inventory_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    summary = _mapping(report.get("summary"))
    lines = [
        "Phase 3B failed-anchor inventory",
        f"candidate={candidate.get('key')}",
        f"sample_count={summary.get('sample_count', 0)}",
        f"classification_counts={summary.get('classification_counts', {})}",
        f"forced_status_counts={summary.get('forced_status_counts', {})}",
        f"forced_zero_branch_unknown_count={summary.get('forced_zero_branch_unknown_count', 0)}",
        f"recommendation={summary.get('recommendation')}",
    ]
    for entry in list(report.get("samples", [])):
        if not isinstance(entry, Mapping):
            continue
        evidence = _mapping(entry.get("forced_anchor_evidence"))
        lines.append(
            "sample "
            f"anchor={entry.get('anchor_idx')} "
            f"class={entry.get('classification')} "
            f"reason={entry.get('failure_reason')} "
            f"group={entry.get('group_id')} "
            f"required={entry.get('required_count')} "
            f"surviving={entry.get('surviving_at_failure_count')} "
            f"forced_status_counts={evidence.get('status_counts', {})}"
        )
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _sample_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    anchor_idx = int(entry.get("anchor_idx", -1))
    required_count = int(entry.get("first_failed_group_required_count", 0))
    surviving_after_blocked = int(
        entry.get("first_failed_group_surviving_after_blocked_count", 0)
    )
    surviving_at_failure = int(
        entry.get("first_failed_group_surviving_at_failure_count", 0)
    )
    failure_reason = str(entry.get("failure_reason") or "unknown")
    if failure_reason.startswith("coordinate_validation_"):
        classification = "coordinate_validation_rejected"
    elif surviving_at_failure < required_count:
        classification = "prefix_count_below_required"
    elif failure_reason == "intra_group_greedy_exhausted":
        classification = "prefix_packing_or_greedy_hard"
    else:
        classification = "prefix_other"
    return {
        "anchor_idx": int(anchor_idx),
        "classification": classification,
        "failure_reason": failure_reason,
        "group_id": entry.get("first_failed_group_id"),
        "facility_type": entry.get("first_failed_group_template"),
        "group_position": entry.get("first_failed_group_position"),
        "required_count": int(required_count),
        "surviving_after_blocked_count": int(surviving_after_blocked),
        "surviving_at_failure_count": int(surviving_at_failure),
        "local_repair_attempted": bool(entry.get("local_repair_attempted", False)),
        "local_repair_success": bool(entry.get("local_repair_success", False)),
        "local_repair_attempt_count": int(entry.get("local_repair_attempt_count", 0)),
    }


def _load_forced_anchor_evidence(
    forced_dir: Path,
    matrix_dir: Path,
) -> Dict[int, Dict[str, Any]]:
    evidence: Dict[int, Dict[str, Any]] = {}
    for path in _json_files(forced_dir):
        payload, _error = _load_json_mapping(path)
        if not isinstance(payload, Mapping):
            continue
        for entry in list(payload.get("forced_anchors", [])):
            if not isinstance(entry, Mapping):
                continue
            _add_forced_status(evidence, entry, source_path=path)
    for path in _json_files(matrix_dir):
        payload, _error = _load_json_mapping(path)
        if not isinstance(payload, Mapping):
            continue
        matrix = _mapping(payload.get("matrix"))
        for entry in list(matrix.get("entries", [])):
            if not isinstance(entry, Mapping):
                continue
            _add_forced_status(evidence, entry, source_path=path)
    return evidence


def _add_forced_status(
    evidence: Dict[int, Dict[str, Any]],
    entry: Mapping[str, Any],
    *,
    source_path: Path,
) -> None:
    try:
        anchor_idx = int(entry.get("anchor_idx"))
    except Exception:
        return
    status = str(entry.get("status", "UNKNOWN"))
    bucket = evidence.setdefault(
        anchor_idx,
        {
            "status_counts": {},
            "zero_branch_unknown_count": 0,
            "sources": [],
        },
    )
    status_counts = _mapping(bucket.get("status_counts"))
    status_counts[status] = int(status_counts.get(status, 0)) + 1
    bucket["status_counts"] = dict(status_counts)
    if (
        status == "UNKNOWN"
        and _number_or_zero(entry.get("branches")) == 0
        and _number_or_zero(entry.get("conflicts")) == 0
    ):
        bucket["zero_branch_unknown_count"] = int(
            bucket.get("zero_branch_unknown_count", 0)
        ) + 1
    sources = list(bucket.get("sources", []))
    sources.append(
        {
            "path": str(source_path),
            "status": status,
            "search_branching": entry.get("search_branching"),
            "wall_time": entry.get("wall_time"),
            "branches": entry.get("branches"),
            "conflicts": entry.get("conflicts"),
        }
    )
    bucket["sources"] = sources[-8:]


def _json_files(path: Path) -> list[Path]:
    if not path.exists() or not path.is_dir():
        return []
    return sorted(item for item in path.glob("*.json") if item.is_file())


def _count_by(samples: list[Mapping[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in samples:
        token = str(entry.get(key))
        counts[token] = int(counts.get(token, 0)) + 1
    return counts


def _forced_status_counts(samples: list[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in samples:
        evidence = _mapping(entry.get("forced_anchor_evidence"))
        for status, count in _mapping(evidence.get("status_counts")).items():
            counts[str(status)] = int(counts.get(str(status), 0)) + int(count)
    return counts


def _forced_zero_branch_unknown_count(samples: list[Mapping[str, Any]]) -> int:
    count = 0
    for entry in samples:
        evidence = _mapping(entry.get("forced_anchor_evidence"))
        count += int(evidence.get("zero_branch_unknown_count", 0))
    return int(count)


def _recommendation(
    *,
    sample_count: int,
    classification_counts: Mapping[str, int],
    forced_status_counts: Mapping[str, int],
    forced_zero_branch_unknown_count: int = 0,
) -> str:
    if sample_count <= 0:
        return "No failed-anchor samples are available; rerun B5A with failed-anchor sampling enabled."
    if int(classification_counts.get("coordinate_validation_rejected", 0)) > 0:
        if int(forced_status_counts.get("UNKNOWN", 0)) > 0:
            if int(forced_zero_branch_unknown_count) > 0:
                return (
                    "Coordinate-validation rejected sampled warm starts, but forced-anchor "
                    "solver matrix still has zero-branch UNKNOWN entries; triage presolve "
                    "or model-building bottlenecks by anchor."
                )
            return (
                "Coordinate-validation rejected sampled warm starts, but forced-anchor "
                "solver matrix still has UNKNOWN entries; continue solver-matrix triage."
            )
        return (
            "Coordinate-validation rejected sampled warm starts; inspect forced-anchor "
            "solver matrix evidence before considering runtime promotion."
        )
    if int(classification_counts.get("prefix_packing_or_greedy_hard", 0)) > 0:
        return (
            "Focus next diagnostics on prefix_packing_or_greedy_hard anchors; "
            "count-below-required anchors are the easy subset."
        )
    if int(forced_status_counts.get("UNKNOWN", 0)) > 0:
        return "Forced-anchor evidence still has UNKNOWN entries; continue solver-matrix triage."
    if int(classification_counts.get("prefix_count_below_required", 0)) == int(sample_count):
        return "Failed-anchor inventory is dominated by count-style blockers."
    return "Failed-anchor inventory has unclassified prefix samples; add targeted diagnostics."


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    sample_count: int,
) -> list[Dict[str, str]]:
    return [
        _check(
            "campaign_state_present",
            "pass" if state_present else "fail",
            "campaign state loaded" if state_present else "campaign state missing",
        ),
        _check(
            "candidate_present",
            "pass" if candidate_present else "fail",
            "candidate loaded" if candidate_present else "candidate missing",
        ),
        _check(
            "failed_anchor_samples_present",
            "pass" if sample_count > 0 else "fail",
            f"sample_count={int(sample_count)}",
        ),
    ]


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"json_load_error:{type(exc).__name__}:{exc}"
    if not isinstance(payload, Mapping):
        return None, "json_payload_not_object"
    return dict(payload), None


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


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": detail}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number_or_zero(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
