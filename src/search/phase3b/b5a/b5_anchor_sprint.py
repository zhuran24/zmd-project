from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from src.io.delivery_manifest import delivery_manifest_output_path
from src.search.campaign_telemetry import campaign_telemetry_output_path
from src.search.campaign_triage import build_phase3b_unknown_triage_inventory
from src.search.exact_campaign import now_iso
from src.search.exact_campaign_inspector import build_exact_campaign_inspection
from src.search.phase3b.operating_profile.operating_profile import build_phase3b_operating_profile_summary

B5_ANCHOR_SPRINT_SCHEMA_SOURCE = "phase3b_b5_anchor_sprint_summary_v1"
DEFAULT_CAMPAIGN_STATE_PATH = Path("data/checkpoints/exact_campaign_state.json")
RUNTIME_GROUP_PACKING_DIR = Path(".artifacts/phase3b_runtime_group_packing")
COORDINATOR_SOURCE_ROOT = Path(__file__).resolve().parents[4]
B5A_PROVENANCE_FILES = (
    Path("src/models/master_model.py"),
    Path("src/search/campaign_triage.py"),
    Path("scripts/run_phase3b_b5_anchor_sprint.ps1"),
)


def build_phase3b_b5_anchor_sprint_summary(
    project_root: Path,
    campaign_state_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    telemetry_path = campaign_telemetry_output_path(campaign_path)
    manifest_path = delivery_manifest_output_path(project_root)
    inspection = build_exact_campaign_inspection(
        project_root=project_root,
        campaign_state_path=campaign_path,
    )
    triage = build_phase3b_unknown_triage_inventory(
        project_root=project_root,
        campaign_state_path=campaign_path,
    )
    operating_profile = build_phase3b_operating_profile_summary(project_root)

    certified_surface = _mapping(inspection.get("certified_surface"))
    campaign = _mapping(inspection.get("campaign"))
    telemetry = _mapping(inspection.get("telemetry"))
    delivery_manifest = _mapping(inspection.get("delivery_manifest"))
    best_certified = _mapping_or_none(campaign.get("best_certified_result"))
    final_status = campaign.get("final_status")
    delivery_manifest_terminal_certified = bool(
        delivery_manifest.get("terminal_full_frontier_certified", False)
    )
    certified_surface_publishable = bool(certified_surface.get("publishable", False))
    anchor_found = bool(certified_surface_publishable and best_certified)
    last_stop_reason = _mapping_or_none(campaign.get("last_stop_reason"))
    candidate_status_counts = _mapping(campaign.get("candidate_status_counts"))
    triage_summary = _mapping(triage.get("summary"))
    blockers = [
        dict(entry)
        for entry in list(triage.get("blockers", []))
        if isinstance(entry, Mapping)
    ]
    current_candidate_keys = _current_candidate_keys(
        blockers=blockers,
        best_certified=best_certified,
    )
    runtime_group_packing = _load_runtime_group_packing_diagnostics(
        project_root,
        current_candidate_keys=current_candidate_keys,
    )
    telemetry_aggregate = _mapping(telemetry.get("aggregate"))
    pose_order_validation = _pose_order_validation_summary(telemetry_aggregate)
    source_provenance = _source_provenance(project_root)

    return {
        "metadata": {
            "source": B5_ANCHOR_SPRINT_SCHEMA_SOURCE,
            "generated_at": now_iso(),
            "project_root": str(project_root),
        },
        "paths": {
            "campaign_state": _display_path(project_root, campaign_path),
            "campaign_telemetry": _display_path(project_root, telemetry_path),
            "delivery_manifest": _display_path(project_root, manifest_path),
            "operator_summary": ".artifacts/phase3b_b5_anchor_sprint/operator_summary.json",
        },
        "workspace_policy": {
            "workspace_only": True,
            "repo_main_checkpoint_policy": "Do not copy intermediate B5A checkpoints into repo main proof paths.",
            "large_output_drive": _drive_label(project_root),
        },
        "status": {
            "campaign_present": bool(campaign.get("present", False)),
            "telemetry_present": bool(telemetry.get("present", False)),
            "delivery_manifest_present": bool(delivery_manifest.get("present", False)),
            "delivery_manifest_terminal_full_frontier_certified": delivery_manifest_terminal_certified,
            "certified_surface_public": certified_surface_publishable,
            "certified_surface_publishable": certified_surface_publishable,
            "certified_surface_blocked_reason": certified_surface.get("blocked_reason"),
            "source_matches_coordinator": bool(
                source_provenance.get("workspace_source_matches_coordinator", False)
            ),
            "attribution_trustworthy_with_current_source": bool(
                source_provenance.get("workspace_source_matches_coordinator", False)
            ),
            "anchor_found": anchor_found,
            "outcome": _outcome(
                campaign_present=bool(campaign.get("present", False)),
                anchor_found=anchor_found,
                blockers=blockers,
                last_stop_reason=last_stop_reason,
                candidate_status_counts=candidate_status_counts,
            ),
            "recommendation": _recommendation(
                campaign_present=bool(campaign.get("present", False)),
                anchor_found=anchor_found,
                blockers=blockers,
                last_stop_reason=last_stop_reason,
                candidate_status_counts=candidate_status_counts,
            ),
        },
        "anchor": _anchor_summary(best_certified) if anchor_found else None,
        "campaign": {
            "final_status": final_status,
            "last_stop_reason": last_stop_reason,
            "reset_reason": campaign.get("reset_reason"),
            "candidate_count": int(campaign.get("candidate_count", 0)),
            "candidate_status_counts": campaign.get("candidate_status_counts", {}),
            "resume_compatible_with_current_hashes": bool(
                campaign.get("resume_compatible_with_current_hashes", False)
            ),
            "resume_validation_reason": campaign.get("resume_validation_reason"),
            "delivery_manifest_terminal_full_frontier_certified": delivery_manifest_terminal_certified,
            "certified_surface_public": certified_surface_publishable,
            "certified_surface_publishable": certified_surface_publishable,
            "certified_surface_blocked_reason": certified_surface.get("blocked_reason"),
        },
        "telemetry": {
            "wave_count": int(telemetry.get("wave_count", 0)),
            "aggregate": telemetry.get("aggregate"),
        },
        "pose_order_validation": pose_order_validation,
        "triage": {
            "generated": True,
            "blocker_count": int(triage_summary.get("blocker_count", 0)),
            "classification_counts": triage_summary.get("classification_counts", {}),
            "subtype_counts": triage_summary.get("subtype_counts", {}),
            "top_blockers": blockers[:10],
        },
        "runtime_group_packing": runtime_group_packing,
        "source_provenance": source_provenance,
        "operating_profile": {
            "defaults": operating_profile.get("defaults", {}),
            "policy": operating_profile.get("policy", {}),
        },
    }


def render_phase3b_b5_anchor_sprint_markdown(summary: Mapping[str, Any]) -> str:
    status = _mapping(summary.get("status"))
    campaign = _mapping(summary.get("campaign"))
    telemetry = _mapping(summary.get("telemetry"))
    triage = _mapping(summary.get("triage"))
    runtime_group_packing = _mapping(summary.get("runtime_group_packing"))
    pose_order_validation = _mapping(summary.get("pose_order_validation"))
    anchor = _mapping(summary.get("anchor"))
    lines = [
        "# Phase 3B B5A Anchor Sprint Operator Summary",
        "",
        f"- Anchor found: {bool(status.get('anchor_found', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Source matches coordinator: {bool(status.get('source_matches_coordinator', False))}",
        f"- Attribution trustworthy with current source: {bool(status.get('attribution_trustworthy_with_current_source', False))}",
        f"- Campaign final status: {campaign.get('final_status')}",
        f"- Last stop reason: {_reason_text(campaign.get('last_stop_reason'))}",
        f"- Telemetry waves: {telemetry.get('wave_count', 0)}",
        f"- Triage blockers: {triage.get('blocker_count', 0)}",
        f"- Runtime group-packing diagnostics: {runtime_group_packing.get('diagnostic_count', 0)}",
        f"- Runtime group-packing diagnostics for current candidate: {runtime_group_packing.get('relevant_diagnostic_count', 0)}",
        f"- Pose-order validation rejected: {pose_order_validation.get('rejected_count', 0)}",
    ]
    if anchor:
        lines.extend(
            [
                "",
                "## Anchor",
                "",
                f"- Candidate: {anchor.get('candidate_key')}",
                f"- Ghost rect: {anchor.get('ghost_rect')}",
                f"- Objective: {anchor.get('objective')}",
            ]
        )
    blockers = [
        entry
        for entry in list(triage.get("top_blockers", []))
        if isinstance(entry, Mapping)
    ]
    if blockers:
        lines.extend(
            [
                "",
                "## Top Blockers",
                "",
                "| Candidate | Classification | Subtype | Stop reason |",
                "| --- | --- | --- | --- |",
            ]
        )
        for entry in blockers:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("candidate_key")),
                        _markdown_cell(entry.get("classification")),
                        _markdown_cell(entry.get("blocker_subtype")),
                        _markdown_cell(entry.get("stop_reason")),
                    ]
                )
                + " |"
            )
    pose_order_samples = [
        entry
        for entry in list(pose_order_validation.get("portfolio_failure_samples", []))[:10]
        if isinstance(entry, Mapping)
    ]
    if pose_order_samples:
        lines.extend(
            [
                "",
                "## Pose-Order Portfolio Failure Samples",
                "",
                "| Candidate | Anchor | Ordering | Source | Reason | Status |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in pose_order_samples:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("candidate_key")),
                        _markdown_cell(entry.get("anchor_idx")),
                        _markdown_cell(entry.get("ordering")),
                        _markdown_cell(entry.get("source")),
                        _markdown_cell(entry.get("failure_reason")),
                        _markdown_cell(entry.get("status")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_b5_anchor_sprint_text(summary: Mapping[str, Any]) -> str:
    status = _mapping(summary.get("status"))
    campaign = _mapping(summary.get("campaign"))
    telemetry = _mapping(summary.get("telemetry"))
    triage = _mapping(summary.get("triage"))
    runtime_group_packing = _mapping(summary.get("runtime_group_packing"))
    pose_order_validation = _mapping(summary.get("pose_order_validation"))
    lines = [
        "Phase 3B B5A anchor sprint operator summary",
        f"anchor_found={bool(status.get('anchor_found', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"source_matches_coordinator={bool(status.get('source_matches_coordinator', False))}",
        f"attribution_trustworthy_with_current_source={bool(status.get('attribution_trustworthy_with_current_source', False))}",
        f"campaign_final_status={campaign.get('final_status')}",
        f"last_stop_reason={_reason_text(campaign.get('last_stop_reason'))}",
        f"telemetry_wave_count={telemetry.get('wave_count', 0)}",
        f"triage_blocker_count={triage.get('blocker_count', 0)}",
        f"runtime_group_packing_diagnostic_count={runtime_group_packing.get('diagnostic_count', 0)}",
        f"runtime_group_packing_relevant_diagnostic_count={runtime_group_packing.get('relevant_diagnostic_count', 0)}",
        f"pose_order_validation_rejected_count={pose_order_validation.get('rejected_count', 0)}",
        f"pose_order_portfolio_failure_sample_count={pose_order_validation.get('portfolio_failure_sample_count', 0)}",
    ]
    for entry in list(pose_order_validation.get("portfolio_failure_samples", []))[:10]:
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "pose_order_portfolio_failure_sample="
            f"candidate={entry.get('candidate_key')} "
            f"anchor={entry.get('anchor_idx')} "
            f"ordering={entry.get('ordering')} "
            f"source={entry.get('source')} "
            f"reason={entry.get('failure_reason')} "
            f"status={entry.get('status')}"
        )
    for entry in list(triage.get("top_blockers", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "blocker "
            f"candidate={entry.get('candidate_key')} "
            f"classification={entry.get('classification')} "
            f"subtype={entry.get('blocker_subtype')} "
            f"reason={entry.get('stop_reason')}"
        )
    return "\n".join(lines) + "\n"


def _source_provenance(project_root: Path) -> Dict[str, Any]:
    file_reports = []
    all_known_files_match = True
    any_known_file = False
    for relative_path in B5A_PROVENANCE_FILES:
        workspace_path = project_root / relative_path
        coordinator_path = COORDINATOR_SOURCE_ROOT / relative_path
        workspace_hash = _sha256_file(workspace_path)
        coordinator_hash = _sha256_file(coordinator_path)
        if workspace_hash is not None and coordinator_hash is not None:
            any_known_file = True
            if workspace_hash != coordinator_hash:
                all_known_files_match = False
        elif workspace_hash is not None or coordinator_hash is not None:
            all_known_files_match = False
        file_reports.append(
            {
                "path": str(relative_path).replace("\\", "/"),
                "workspace_present": workspace_hash is not None,
                "workspace_sha256": workspace_hash,
                "coordinator_present": coordinator_hash is not None,
                "coordinator_sha256": coordinator_hash,
                "matches_coordinator": bool(
                    workspace_hash is not None
                    and coordinator_hash is not None
                    and workspace_hash == coordinator_hash
                ),
            }
        )

    master_model_path = project_root / "src" / "models" / "master_model.py"
    return {
        "coordinator_source_root": str(COORDINATOR_SOURCE_ROOT),
        "workspace_source_matches_coordinator": bool(
            any_known_file and all_known_files_match
        ),
        "files": file_reports,
        "precheck_support": {
            "ghost_overlap_forced_domain": _source_support(
                master_model_path,
                markers=(
                    "EXACT_GHOST_OVERLAP_FORCED_DOMAIN_PRECHECK",
                    "evaluate_ghost_overlap_forced_domain_conflict",
                ),
            ),
            "signature_monotonic_forced_label": _source_support(
                master_model_path,
                markers=(
                    "EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK",
                    "evaluate_signature_monotonic_forced_label_conflict",
                ),
            ),
        },
    }


def _source_support(path: Path, *, markers: Iterable[str]) -> Dict[str, Any]:
    missing_markers = _missing_markers(path, markers)
    display_root = path.parents[2] if len(path.parents) > 2 else path.parent
    return {
        "path": _display_path(display_root, path) if path.exists() else str(path),
        "present": path.exists(),
        "supported": path.exists() and not missing_markers,
        "missing_markers": missing_markers,
    }


def _missing_markers(path: Path, markers: Iterable[str]) -> list[str]:
    if not path.exists():
        return [str(marker) for marker in markers]
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return [str(marker) for marker in markers]
    return [str(marker) for marker in markers if str(marker) not in text]


def _sha256_file(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_runtime_group_packing_diagnostics(
    project_root: Path,
    *,
    current_candidate_keys: list[str],
) -> Dict[str, Any]:
    diagnostics_dir = project_root / RUNTIME_GROUP_PACKING_DIR
    reports: list[Dict[str, Any]] = []
    if diagnostics_dir.exists():
        for path in sorted(diagnostics_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, Mapping):
                continue
            candidate = _mapping(payload.get("candidate"))
            status = _mapping(payload.get("status"))
            diagnostics = _mapping(payload.get("diagnostics"))
            blockers = _mapping(diagnostics.get("group_packing_blockers"))
            reports.append(
                {
                    "path": _display_path(project_root, path),
                    "candidate_key": candidate.get("key"),
                    "outcome": status.get("outcome"),
                    "evaluated": bool(status.get("evaluated", False)),
                    "blocker_count": int(blockers.get("blocker_count", 0)),
                    "campaign_state_unchanged": bool(
                        payload.get("campaign_state_unchanged", False)
                    ),
                }
            )
    current_key_set = {str(key) for key in current_candidate_keys if str(key)}
    relevant_reports = [
        dict(report)
        for report in reports
        if str(report.get("candidate_key", "")) in current_key_set
    ]
    stale_reports = [
        dict(report)
        for report in reports
        if str(report.get("candidate_key", "")) not in current_key_set
    ]
    return {
        "present": bool(reports),
        "diagnostic_count": int(len(reports)),
        "current_candidate_keys": list(current_candidate_keys),
        "relevant_diagnostic_count": int(len(relevant_reports)),
        "stale_diagnostic_count": int(len(stale_reports)),
        "relevant_reports": relevant_reports,
        "stale_reports": stale_reports,
        "reports": reports,
    }


def _current_candidate_keys(
    *,
    blockers: list[Mapping[str, Any]],
    best_certified: Optional[Mapping[str, Any]],
) -> list[str]:
    keys: list[str] = []
    for entry in blockers:
        key = entry.get("candidate_key")
        if key is not None:
            keys.append(str(key))
    if best_certified:
        anchor = _anchor_summary(best_certified)
        key = anchor.get("candidate_key")
        if key is not None:
            keys.append(str(key))
    return _dedupe_strings(keys)


def _pose_order_validation_summary(telemetry_aggregate: Mapping[str, Any]) -> Dict[str, Any]:
    status_counts = _mapping(
        telemetry_aggregate.get("ghost_aware_pose_order_validation_status_counts")
    )
    reason_counts = _mapping(
        telemetry_aggregate.get("ghost_aware_pose_order_validation_reason_counts")
    )
    selected_ordering_counts = _mapping(
        telemetry_aggregate.get(
            "ghost_aware_pose_order_portfolio_selected_ordering_counts"
        )
    )
    portfolio_failure_samples = [
        dict(entry)
        for entry in list(
            telemetry_aggregate.get(
                "ghost_aware_pose_order_portfolio_failure_samples",
                [],
            )
        )
        if isinstance(entry, Mapping)
    ]
    return {
        "attempt_count": int(
            telemetry_aggregate.get(
                "ghost_aware_pose_order_validation_attempt_count_sum",
                0,
            )
        ),
        "rejected_count": int(
            telemetry_aggregate.get(
                "ghost_aware_pose_order_validation_rejected_count_sum",
                0,
            )
        ),
        "portfolio_attempted_count": int(
            telemetry_aggregate.get(
                "ghost_aware_pose_order_portfolio_attempted_count",
                0,
            )
        ),
        "portfolio_success_count": int(
            telemetry_aggregate.get(
                "ghost_aware_pose_order_portfolio_success_count",
                0,
            )
        ),
        "portfolio_attempt_count_sum": int(
            telemetry_aggregate.get(
                "ghost_aware_pose_order_portfolio_attempt_count_sum",
                0,
            )
        ),
        "portfolio_failure_sample_count": int(
            telemetry_aggregate.get(
                "ghost_aware_pose_order_portfolio_failure_sample_count",
                len(portfolio_failure_samples),
            )
        ),
        "portfolio_failure_samples": portfolio_failure_samples,
        "status_counts": {
            str(key): int(value) for key, value in dict(status_counts).items()
        },
        "reason_counts": {
            str(key): int(value) for key, value in dict(reason_counts).items()
        },
        "selected_ordering_counts": {
            str(key): int(value)
            for key, value in dict(selected_ordering_counts).items()
        },
    }


def _outcome(
    *,
    campaign_present: bool,
    anchor_found: bool,
    blockers: list[Mapping[str, Any]],
    last_stop_reason: Optional[Mapping[str, Any]],
    candidate_status_counts: Mapping[str, Any],
) -> str:
    if not campaign_present:
        return "no_campaign_state"
    if anchor_found:
        return "anchor_found"
    if int(candidate_status_counts.get("RUNNING", 0)) > 0:
        return "interrupted_running_candidate"
    reason = "" if last_stop_reason is None else str(last_stop_reason.get("reason", ""))
    if reason in {"worker_process_failed"}:
        return "orchestration_failure"
    if reason in {
        "candidate_returned_unknown",
        "candidate_returned_unproven",
        "max_attempts_exhausted",
        "campaign_time_budget_exhausted",
    }:
        return "triage_required"
    if blockers:
        return "triage_required"
    return "no_anchor"


def _recommendation(
    *,
    campaign_present: bool,
    anchor_found: bool,
    blockers: list[Mapping[str, Any]],
    last_stop_reason: Optional[Mapping[str, Any]],
    candidate_status_counts: Mapping[str, Any],
) -> str:
    if not campaign_present:
        return "Prepare a B5A workspace and run the short anchor sprint before interpreting results."
    if anchor_found:
        return "Proceed to resume-to-prune planning; do not promote B6/B7 until terminal exhaustion is proven."
    if int(candidate_status_counts.get("RUNNING", 0)) > 0:
        return "B5A did not terminate cleanly; inspect the workspace RUNNING candidate before any longer run."
    reason = "" if last_stop_reason is None else str(last_stop_reason.get("reason", ""))
    if blockers:
        return "Return to B3 triage or B2 targeted shrink using the generated blocker inventory."
    if reason in {"max_attempts_exhausted", "campaign_time_budget_exhausted"}:
        return "Inspect telemetry throughput and either resume B5A or return to B3 if stop reason is unclear."
    return "Inspect campaign state, telemetry, and triage output before any longer run."


def _anchor_summary(best_certified: Mapping[str, Any]) -> Dict[str, Any]:
    ghost_rect = _mapping(best_certified.get("ghost_rect"))
    w = int(ghost_rect.get("w", 0))
    h = int(ghost_rect.get("h", 0))
    area = int(ghost_rect.get("area", w * h))
    return {
        "candidate_key": f"{w}x{h}" if w and h else None,
        "ghost_rect": {"w": w, "h": h, "area": area},
        "objective": {"area": area, "min_side": min(w, h) if w and h else 0},
        "best_certified_result": dict(best_certified),
    }


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


def _drive_label(path: Path) -> str:
    drive = Path(path).drive
    return drive or "unknown"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_or_none(value: Any) -> Optional[Dict[str, Any]]:
    return dict(value) if isinstance(value, Mapping) else None


def _reason_text(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    return value.get("reason", value)


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = str(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
