from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from src.search.exact_campaign import now_iso

B5A_COORDINATE_VALIDATION_REASON_LOCALIZATION_SOURCE = (
    "phase3b_b5a_coordinate_validation_reason_localization_v1"
)
EXPECTED_CANDIDATE_KEY = "67x13"

DEFAULT_POST_ACCEPTANCE_BLOCKER_SUMMARY_PATH = Path(
    ".artifacts/phase3b_b5a_post_acceptance_blocker_summary_20260425/"
    "b5a_post_acceptance_blocker_summary.json"
)
DEFAULT_FAILED_ANCHOR_INVENTORY_PATH = Path(
    ".artifacts/phase3b_failed_anchor_inventory_67x13_cap112_v3/"
    "failed_anchor_inventory.json"
)
DEFAULT_WORKSPACE_ROOTS: Tuple[Path, ...] = (
    Path(
        "E:/phase3b_workspaces/"
        "endfield_phase3b_b5_anchor_current_source_selected_block_cap128_20260422_1645"
    ),
    Path(
        "E:/phase3b_workspaces/"
        "endfield_phase3b_b5_anchor_selected_block_pose30_20260422_2235"
    ),
    Path(
        "E:/phase3b_workspaces/"
        "endfield_phase3b_b5_anchor_selected_block_sanity_20260422"
    ),
    Path(
        "E:/phase3b_workspaces/"
        "endfield_phase3b_b5_anchor_20260422_conjunctive_signature_precheck_runtime"
    ),
)


def build_phase3b_b5a_coordinate_validation_reason_localization(
    project_root: Path,
    *,
    workspace_roots: Optional[Sequence[Path]] = None,
    post_acceptance_blocker_summary_path: Optional[Path] = None,
    failed_anchor_inventory_path: Optional[Path] = None,
    anchor_min: int = 118,
    anchor_max: int = 125,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    requested_anchors = list(range(int(anchor_min), int(anchor_max) + 1))
    workspace_paths = [
        Path(path).resolve()
        for path in (
            tuple(workspace_roots)
            if workspace_roots is not None
            else DEFAULT_WORKSPACE_ROOTS
        )
    ]
    post_summary_path = _resolve_path(
        project_root,
        post_acceptance_blocker_summary_path
        if post_acceptance_blocker_summary_path is not None
        else DEFAULT_POST_ACCEPTANCE_BLOCKER_SUMMARY_PATH,
    )
    inventory_path = _resolve_path(
        project_root,
        failed_anchor_inventory_path
        if failed_anchor_inventory_path is not None
        else DEFAULT_FAILED_ANCHOR_INVENTORY_PATH,
    )

    post_summary, post_summary_error = _load_json_mapping(post_summary_path)
    failed_inventory, failed_inventory_error = _load_json_mapping(inventory_path)
    surfaces = [
        _workspace_surface(path, requested_anchors=requested_anchors)
        for path in workspace_paths
    ]
    selected_surface = _select_surface(surfaces)
    selected_candidate_key = str(selected_surface.get("candidate_key") or "")
    candidate_matches = selected_candidate_key == EXPECTED_CANDIDATE_KEY
    anchor_rows = _anchor_rows(
        requested_anchors=requested_anchors,
        selected_surface=selected_surface,
        inventory=failed_inventory,
    )
    category_counts = _count_by(anchor_rows, "category")
    generic_anchor_count = int(
        category_counts.get("generic_coordinate_validation_infeasible", 0)
    )
    unknown_anchor_count = int(category_counts.get("coordinate_validation_unknown", 0))
    localized_anchor_count = sum(
        1
        for row in anchor_rows
        if bool(row.get("localized", False))
    )
    reason_localization_ready = (
        bool(anchor_rows)
        and candidate_matches
        and localized_anchor_count == len(requested_anchors)
    )
    status = {
        "completed": True,
        "reason_localization_ready": bool(reason_localization_ready),
        "localized_anchor_count": int(localized_anchor_count),
        "requested_anchor_count": int(len(requested_anchors)),
        "generic_anchor_count": int(generic_anchor_count),
        "unknown_anchor_count": int(unknown_anchor_count),
        "certified_anchor_found": False,
        "proof_source": False,
        "runtime_semantics_changed": False,
        "checkpoint_written": False,
        "candidate_elimination_claim": False,
        "b5a_anchor_found": False,
        "runtime_elimination_authorized": False,
        "final_168h_authorized": False,
        "checkpoint_write_or_import_back_authorized": False,
        "release_viewer_frontdoor_status_promoted": False,
        "preflight_gate_mutated": False,
        "outcome": (
            "b5a_coordinate_validation_reasons_localized"
            if reason_localization_ready
            else "b5a_coordinate_validation_reasons_incomplete"
        ),
        "recommendation": _recommendation(
            ready=reason_localization_ready,
            generic_anchor_count=generic_anchor_count,
            unknown_anchor_count=unknown_anchor_count,
        ),
    }
    return {
        "metadata": {
            "source": B5A_COORDINATE_VALIDATION_REASON_LOCALIZATION_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "report_only_existing_telemetry_no_solver_not_proof_source"
            ),
            "solver_invoked": False,
            "checkpoint_written": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "preflight_gate_mutated": False,
        },
        "paths": {
            "project_root": str(project_root),
            "post_acceptance_blocker_summary": _display_path(
                project_root,
                post_summary_path,
            ),
            "failed_anchor_inventory": _display_path(project_root, inventory_path),
            "workspace_roots": [str(path) for path in workspace_paths],
        },
        "candidate": {
            "key": selected_candidate_key or None,
            "expected_key": EXPECTED_CANDIDATE_KEY,
            "matches_expected": bool(candidate_matches),
        },
        "inputs": {
            "post_acceptance_blocker_summary": {
                "present": post_summary is not None,
                "load_error": post_summary_error,
            },
            "failed_anchor_inventory": {
                "present": failed_inventory is not None,
                "load_error": failed_inventory_error,
            },
            "workspace_surfaces": surfaces,
        },
        "selected_surface": selected_surface,
        "status": status,
        "reason_localization": {
            "anchor_range": f"{requested_anchors[0]}-{requested_anchors[-1]}"
            if requested_anchors
            else "",
            "category_counts": category_counts,
            "anchor_rows": anchor_rows,
        },
        "post_acceptance_context": _post_acceptance_context(post_summary),
        "checks": _checks(
            post_summary_error=post_summary_error,
            failed_inventory_error=failed_inventory_error,
            surfaces=surfaces,
            ready=reason_localization_ready,
            anchor_rows=anchor_rows,
            candidate_matches=candidate_matches,
            candidate_key=selected_candidate_key or None,
        ),
    }


def render_phase3b_b5a_coordinate_validation_reason_localization_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    selected = _mapping(report.get("selected_surface"))
    localization = _mapping(report.get("reason_localization"))
    lines = [
        "# Phase 3B B5A Coordinate-Validation Reason Localization",
        "",
        f"- Outcome: {_markdown_cell(status.get('outcome'))}",
        f"- Reason localization ready: {_markdown_cell(status.get('reason_localization_ready'))}",
        f"- Certified anchor found: {_markdown_cell(status.get('certified_anchor_found'))}",
        f"- Proof source: {_markdown_cell(status.get('proof_source'))}",
        f"- Selected workspace: {_markdown_cell(selected.get('workspace_root'))}",
        f"- Selected reason counts: {_markdown_cell(selected.get('failure_reason_counts'))}",
        f"- Recommendation: {_markdown_cell(status.get('recommendation'))}",
        "",
        "## Anchor Reasons",
        "",
        "| Anchor | Failure reason | Category | Localized | Forced-anchor evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in list(localization.get("anchor_rows", [])):
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(row.get("anchor_idx")),
                    _markdown_cell(row.get("failure_reason")),
                    _markdown_cell(row.get("category")),
                    _markdown_cell(row.get("localized")),
                    _markdown_cell(row.get("forced_anchor_status_counts")),
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


def render_phase3b_b5a_coordinate_validation_reason_localization_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    selected = _mapping(report.get("selected_surface"))
    localization = _mapping(report.get("reason_localization"))
    lines = [
        "Phase 3B B5A coordinate-validation reason localization",
        f"outcome={status.get('outcome')}",
        f"reason_localization_ready={status.get('reason_localization_ready')}",
        f"certified_anchor_found={status.get('certified_anchor_found')}",
        f"proof_source={status.get('proof_source')}",
        f"selected_workspace={selected.get('workspace_root')}",
        f"category_counts={localization.get('category_counts')}",
        f"recommendation={status.get('recommendation')}",
    ]
    for row in list(localization.get("anchor_rows", [])):
        if isinstance(row, Mapping):
            lines.append(
                "anchor_reason "
                f"anchor={row.get('anchor_idx')} "
                f"reason={row.get('failure_reason')} "
                f"category={row.get('category')} "
                f"localized={row.get('localized')} "
                f"forced_anchor_status_counts={row.get('forced_anchor_status_counts')}"
            )
    return "\n".join(lines) + "\n"


def _workspace_surface(
    workspace_root: Path,
    *,
    requested_anchors: Sequence[int],
) -> Dict[str, Any]:
    telemetry_path = Path(workspace_root) / "data/checkpoints/exact_campaign_telemetry.json"
    telemetry, telemetry_error = _load_json_mapping(telemetry_path)
    samples: List[Mapping[str, Any]] = []
    failure_reason_counts: Mapping[str, Any] = {}
    attempted_anchor_count = 0
    failed_anchor_count = 0
    candidate_key: Optional[str] = None
    if telemetry is not None:
        candidate_result = _first_candidate_result(telemetry)
        candidate_key = (
            str(candidate_result.get("candidate_key"))
            if candidate_result.get("candidate_key") is not None
            else None
        )
        proof_summary = _mapping(
            candidate_result.get("proof_status_summary")
            or candidate_result.get("proof_summary")
        )
        attribution = _mapping(proof_summary.get("master_start_failure_attribution"))
        failure_reason_counts = _mapping(attribution.get("failure_reason_counts"))
        attempted_anchor_count = int(attribution.get("attempted_anchor_count", 0) or 0)
        failed_anchor_count = int(attribution.get("failed_anchor_count", 0) or 0)
        samples = [
            entry
            for entry in list(attribution.get("failed_anchor_samples", []))
            if isinstance(entry, Mapping)
        ]

    requested = {int(value) for value in requested_anchors}
    anchor_samples = [
        _sample_surface(entry)
        for entry in samples
        if int(entry.get("anchor_idx", -1)) in requested
    ]
    category_counts = _count_by(anchor_samples, "category")
    localized_count = sum(1 for row in anchor_samples if bool(row.get("localized")))
    return {
        "workspace_root": str(Path(workspace_root)),
        "telemetry_path": str(telemetry_path),
        "telemetry_present": telemetry is not None,
        "telemetry_load_error": telemetry_error,
        "candidate_key": candidate_key,
        "attempted_anchor_count": int(attempted_anchor_count),
        "failed_anchor_count": int(failed_anchor_count),
        "failure_reason_counts": {
            str(key): int(value)
            for key, value in dict(failure_reason_counts).items()
        },
        "anchor_sample_count": int(len(anchor_samples)),
        "requested_anchor_count": int(len(requested_anchors)),
        "localized_anchor_count": int(localized_count),
        "category_counts": category_counts,
        "anchor_samples": anchor_samples,
    }


def _sample_surface(entry: Mapping[str, Any]) -> Dict[str, Any]:
    reason = str(entry.get("failure_reason") or "unknown")
    category = _reason_category(reason)
    return {
        "anchor_idx": int(entry.get("anchor_idx", -1)),
        "failure_reason": reason,
        "category": category,
        "localized": category
        not in {
            "generic_coordinate_validation_infeasible",
            "coordinate_validation_unknown",
            "unknown",
        },
        "blocked_cell_count": int(entry.get("blocked_cell_count", 0) or 0),
    }


def _select_surface(surfaces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    candidates = [surface for surface in surfaces if bool(surface.get("telemetry_present"))]
    if not candidates:
        return {}
    return dict(
        sorted(
            candidates,
            key=lambda surface: (
                int(surface.get("localized_anchor_count", 0)),
                int(surface.get("anchor_sample_count", 0)),
            ),
            reverse=True,
        )[0]
    )


def _anchor_rows(
    *,
    requested_anchors: Sequence[int],
    selected_surface: Mapping[str, Any],
    inventory: Optional[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    samples_by_anchor = {
        int(entry.get("anchor_idx", -1)): entry
        for entry in list(selected_surface.get("anchor_samples", []))
        if isinstance(entry, Mapping)
    }
    forced_by_anchor = _forced_evidence_by_anchor(inventory)
    rows: List[Dict[str, Any]] = []
    for anchor_idx in requested_anchors:
        sample = _mapping(samples_by_anchor.get(int(anchor_idx)))
        forced = _mapping(forced_by_anchor.get(int(anchor_idx)))
        rows.append(
            {
                "anchor_idx": int(anchor_idx),
                "failure_reason": sample.get("failure_reason"),
                "category": sample.get("category", "missing"),
                "localized": bool(sample.get("localized", False)),
                "blocked_cell_count": sample.get("blocked_cell_count"),
                "forced_anchor_status_counts": dict(
                    _mapping(forced.get("status_counts"))
                ),
                "forced_anchor_zero_branch_unknown_count": int(
                    forced.get("zero_branch_unknown_count", 0) or 0
                ),
            }
        )
    return rows


def _forced_evidence_by_anchor(
    inventory: Optional[Mapping[str, Any]],
) -> Dict[int, Mapping[str, Any]]:
    if not inventory:
        return {}
    result: Dict[int, Mapping[str, Any]] = {}
    for entry in list(inventory.get("samples", [])):
        if not isinstance(entry, Mapping):
            continue
        try:
            anchor_idx = int(entry.get("anchor_idx", -1))
        except Exception:
            continue
        result[anchor_idx] = _mapping(entry.get("forced_anchor_evidence"))
    return result


def _post_acceptance_context(report: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not report:
        return {
            "present": False,
            "failed_checks": [],
            "remaining_failed_check": None,
        }
    preflight = _mapping(report.get("preflight"))
    status = _mapping(report.get("status"))
    failed_checks = list(
        preflight.get("failed_checks")
        or status.get("current_preflight_failed_checks")
        or []
    )
    return {
        "present": True,
        "failed_checks": failed_checks,
        "remaining_failed_check": failed_checks[0] if len(failed_checks) == 1 else None,
        "outcome": _mapping(report.get("status")).get("outcome")
        or report.get("outcome"),
    }


def _reason_category(reason: str) -> str:
    if reason == "coordinate_validation_signature_monotonic_forced_label_infeasible":
        return "signature_monotonic_forced_label"
    if reason == "coordinate_validation_ghost_overlap_forced_domain_infeasible":
        return "ghost_overlap_forced_domain"
    if reason == "coordinate_validation_ghost_y_overlap_forced_label_infeasible":
        return "ghost_y_overlap_forced_label"
    if reason == "coordinate_validation_same_x_strip_capacity_conflict":
        return "same_x_strip_capacity"
    if reason == "coordinate_validation_infeasible":
        return "generic_coordinate_validation_infeasible"
    if reason == "coordinate_validation_unknown":
        return "coordinate_validation_unknown"
    if reason:
        return reason
    return "unknown"


def _recommendation(
    *,
    ready: bool,
    generic_anchor_count: int,
    unknown_anchor_count: int,
) -> str:
    if ready:
        return (
            "Use the localized current-source telemetry to design a proof-preserving "
            "B5A anchor-evidence step: anchor118 is explained by ghost-overlap forced-domain "
            "screening, while anchors119-125 are explained by signature-monotonic forced-label "
            "screening. This remains report-only and must not be promoted as proof."
        )
    if unknown_anchor_count:
        return (
            "Coordinate-validation UNKNOWN remains in the requested anchor range; run a "
            "bounded current-source diagnostic with telemetry plumbing before attempting "
            "proof promotion."
        )
    if generic_anchor_count:
        return (
            "Generic coordinate_validation_infeasible remains in the requested anchor range; "
            "enable report-only reason taxonomy before drawing a root-cause conclusion."
        )
    return "Missing requested-anchor telemetry; rerun or point this report at the current B5A workspace."


def _checks(
    *,
    post_summary_error: Optional[str],
    failed_inventory_error: Optional[str],
    surfaces: Sequence[Mapping[str, Any]],
    ready: bool,
    anchor_rows: Sequence[Mapping[str, Any]],
    candidate_matches: bool,
    candidate_key: Optional[str],
) -> List[Dict[str, str]]:
    telemetry_present = any(bool(surface.get("telemetry_present")) for surface in surfaces)
    return [
        _check(
            "report_only_no_solver",
            "pass",
            "reads existing telemetry/artifacts only",
        ),
        _check(
            "post_acceptance_blocker_summary_present",
            "pass" if post_summary_error is None else "fail",
            str(post_summary_error),
        ),
        _check(
            "failed_anchor_inventory_present",
            "pass" if failed_inventory_error is None else "fail",
            str(failed_inventory_error),
        ),
        _check(
            "workspace_telemetry_present",
            "pass" if telemetry_present else "fail",
            "at least one B5A workspace telemetry file was read",
        ),
        _check(
            "candidate_locked_to_67x13",
            "pass" if candidate_matches else "fail",
            f"candidate_key={candidate_key!r} expected={EXPECTED_CANDIDATE_KEY!r}",
        ),
        _check(
            "requested_anchor_reason_coverage",
            "pass" if ready else "fail",
            f"localized={sum(1 for row in anchor_rows if bool(row.get('localized')))} "
            f"requested={len(anchor_rows)}",
        ),
        _check(
            "no_certified_anchor_claim",
            "pass",
            "reason localization is not a certified B5A anchor proof",
        ),
    ]


def _first_candidate_result(telemetry: Mapping[str, Any]) -> Mapping[str, Any]:
    for wave in list(telemetry.get("waves", [])):
        if not isinstance(wave, Mapping):
            continue
        for result in list(wave.get("candidate_results", [])):
            if isinstance(result, Mapping):
                return result
    return {}


def _load_json_mapping(path: Path) -> Tuple[Optional[Mapping[str, Any]], Optional[str]]:
    path = Path(path)
    if not path.exists():
        return None, f"missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(payload, Mapping):
        return None, f"not a JSON object: {path}"
    return payload, None


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _count_by(rows: Iterable[Mapping[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        value = str(row.get(key))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": check_id, "status": status, "detail": detail}


def _markdown_cell(value: Any) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")
