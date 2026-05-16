from __future__ import annotations

import os
import time
from contextlib import contextmanager
from itertools import product
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from ortools.sat.python import cp_model

from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS,
    EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV,
    EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS,
    EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV,
    EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT,
    EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT_ENV,
    MasterPlacementModel,
)
from src.search.benders_loop import create_exact_search_session
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso

START_COMPATIBILITY_SCHEMA_SOURCE = "phase3b_start_compatibility_diagnostics_v1"


def build_phase3b_start_compatibility_diagnostics(
    project_root: Path,
    *,
    candidate: str = "69x19",
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    boundary_port_precheck_max_anchors: Optional[int] = None,
    mandatory_rectangle_precheck_max_anchors: Optional[int] = None,
    portfolio_probe_sample_limit: int = 0,
    portfolio_probe_max_window_size: int = 3,
    portfolio_probe_max_attempts_per_sample: int = 64,
    group_packing_probe_sample_limit: int = 0,
    group_packing_time_limit_seconds: float = 2.0,
    group_packing_max_candidates: int = 2500,
    failed_anchor_sample_limit: Optional[int] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    ghost_w, ghost_h = _parse_candidate(candidate)
    caps = {
        EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV: boundary_port_precheck_max_anchors,
        EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV: mandatory_rectangle_precheck_max_anchors,
        EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT_ENV: failed_anchor_sample_limit,
    }
    resolved_caps = {
        "boundary_port_precheck_max_anchors": _resolved_cap(
            EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV,
            EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS,
            boundary_port_precheck_max_anchors,
        ),
        "mandatory_rectangle_precheck_max_anchors": _resolved_cap(
            EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV,
            EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS,
            mandatory_rectangle_precheck_max_anchors,
        ),
        "failed_anchor_sample_limit": _resolved_cap(
            EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT_ENV,
            EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT,
            failed_anchor_sample_limit,
        ),
    }

    started = time.perf_counter()
    hash_error: Optional[str] = None
    try:
        artifact_hashes = compute_exact_artifact_hashes(project_root)
    except Exception as exc:
        artifact_hashes = {}
        hash_error = f"{type(exc).__name__}: {exc}"

    with _temporary_env_caps(caps):
        session_started = time.perf_counter()
        exact_session = create_exact_search_session(
            project_root,
            solve_mode="certified_exact",
            master_search_profile=master_search_profile,
        )
        session_build_seconds = time.perf_counter() - session_started

        boundary_port_precheck = _evaluate_boundary_port_precheck(
            exact_session=exact_session,
            ghost_rect=(ghost_w, ghost_h),
        )
        overlay_started = time.perf_counter()
        model = MasterPlacementModel.from_exact_core(
            exact_session.core,
            ghost_rect=(ghost_w, ghost_h),
            master_search_profile=master_search_profile,
            precomputed_boundary_port_feasibility=boundary_port_precheck,
        )
        overlay_build_seconds = time.perf_counter() - overlay_started
        warm_start_started = time.perf_counter()
        warm_start = model.build_exact_candidate_warm_start()
        warm_start_seconds = time.perf_counter() - warm_start_started
        failure_attribution = _mapping(
            model.build_stats.get("exact_candidate_warm_start_failure_attribution")
        )
        portfolio_probe_started = time.perf_counter()
        portfolio_probe = _build_portfolio_probe(
            model,
            failure_attribution=failure_attribution,
            sample_limit=int(portfolio_probe_sample_limit),
            max_window_size=int(portfolio_probe_max_window_size),
            max_attempts_per_sample=int(portfolio_probe_max_attempts_per_sample),
        )
        portfolio_probe_seconds = time.perf_counter() - portfolio_probe_started
        group_packing_probe_started = time.perf_counter()
        group_packing_probe = _build_group_packing_probe(
            model,
            failure_attribution=failure_attribution,
            sample_limit=int(group_packing_probe_sample_limit),
            time_limit_seconds=float(group_packing_time_limit_seconds),
            max_candidates=int(group_packing_max_candidates),
        )
        group_packing_blockers = _build_group_packing_blockers(group_packing_probe)
        group_packing_probe_seconds = time.perf_counter() - group_packing_probe_started

    build_stats = dict(model.build_stats)
    start_failure_summary = _start_failure_summary(failure_attribution)
    status = _status_from_warm_start(
        warm_start,
        start_failure_summary,
        portfolio_probe,
        group_packing_probe,
        group_packing_blockers,
    )
    return {
        "metadata": {
            "source": START_COMPATIBILITY_SCHEMA_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "canonical_rules": "rules/canonical_rules.json",
            "candidate_placements": "data/preprocessed/candidate_placements.json",
            "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
            "generic_io_requirements": "data/preprocessed/generic_io_requirements.json",
        },
        "candidate": {
            "key": f"{ghost_w}x{ghost_h}",
            "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": ghost_w * ghost_h},
            "objective": {"area": ghost_w * ghost_h, "min_side": min(ghost_w, ghost_h)},
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "precheck_caps": resolved_caps,
        },
        "artifact_hashes": artifact_hashes,
        "artifact_hash_error": hash_error,
        "status": status,
        "timing": {
            "session_build_seconds": float(session_build_seconds),
            "overlay_build_seconds": float(overlay_build_seconds),
            "warm_start_seconds": float(warm_start_seconds),
            "portfolio_probe_seconds": float(portfolio_probe_seconds),
            "group_packing_probe_seconds": float(group_packing_probe_seconds),
            "total_seconds": float(time.perf_counter() - started),
        },
        "diagnostics": {
            "boundary_port_precheck": _compact_boundary_port_precheck(
                boundary_port_precheck
            ),
            "mandatory_group_prechecks": _compact_mandatory_group_prechecks(
                build_stats.get("exact_candidate_warm_start_mandatory_group_prechecks")
            ),
            "warm_start": _compact_warm_start(warm_start),
            "start_failure_attribution": _compact_failure_attribution(
                failure_attribution
            ),
            "start_failure_summary": start_failure_summary,
            "portfolio_probe": portfolio_probe,
            "group_packing_probe": group_packing_probe,
            "group_packing_blockers": group_packing_blockers,
        },
        "checks": _checks(status, boundary_port_precheck, failure_attribution),
    }


def render_phase3b_start_compatibility_markdown(
    diagnostics: Mapping[str, Any],
) -> str:
    candidate = _mapping(diagnostics.get("candidate"))
    status = _mapping(diagnostics.get("status"))
    diag = _mapping(diagnostics.get("diagnostics"))
    summary = _mapping(diag.get("start_failure_summary"))
    lines = [
        "# Phase 3B Start Compatibility Diagnostics",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Compatible start found: {bool(status.get('compatible_start_found', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Pose-order validation rejected: {status.get('coordinate_pose_order_validation_rejected_count', 0)}",
        f"- Failed anchors: {summary.get('failed_anchor_count', 0)}",
        f"- Failure reasons: {summary.get('failure_reason_counts', {})}",
        "",
    ]
    first_group = _mapping(summary.get("first_failed_group"))
    if first_group:
        lines.extend(
            [
                "## First Failed Group",
                "",
                f"- Group: {first_group.get('group_id')}",
                f"- Facility type: {first_group.get('facility_type')}",
                f"- Position: {first_group.get('position')}",
                f"- Required count: {first_group.get('required_count')}",
                f"- Candidate count: {first_group.get('candidate_count')}",
                f"- Surviving after blocked: {first_group.get('surviving_after_blocked_count')}",
                f"- Surviving at failure: {first_group.get('surviving_at_failure_count')}",
                "",
            ]
        )
    top_failures = [
        entry
        for entry in list(summary.get("top_failed_group_failures", []))
        if isinstance(entry, Mapping)
    ]
    if top_failures:
        lines.extend(
            [
                "## Top Failed Group Failures",
                "",
                "| Group | Facility | Reason | Count |",
                "| --- | --- | --- | --- |",
            ]
        )
        for entry in top_failures:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("group_id")),
                        _markdown_cell(entry.get("facility_type")),
                        _markdown_cell(entry.get("failure_reason")),
                        _markdown_cell(entry.get("count")),
                    ]
                )
                + " |"
            )
        lines.append("")
    warm_start = _mapping(diag.get("warm_start"))
    rejection_samples = [
        entry
        for entry in list(
            warm_start.get(
                "ghost_aware_pose_order_validation_rejection_samples",
                [],
            )
        )
        if isinstance(entry, Mapping)
    ]
    if rejection_samples:
        lines.extend(
            [
                "## Pose-Order Validation Rejections",
                "",
                "| Anchor | Ordering | Status | Reason | Forced slots | Branches | Conflicts |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in rejection_samples:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("anchor_idx")),
                        _markdown_cell(entry.get("ordering")),
                        _markdown_cell(entry.get("status")),
                        _markdown_cell(entry.get("reason")),
                        _markdown_cell(entry.get("forced_slot_field_count")),
                        _markdown_cell(entry.get("branches")),
                        _markdown_cell(entry.get("conflicts")),
                    ]
                )
                + " |"
            )
        lines.append("")
    portfolio_failure_samples = [
        entry
        for entry in list(
            warm_start.get(
                "ghost_aware_pose_order_portfolio_failure_samples",
                [],
            )
        )
        if isinstance(entry, Mapping)
    ]
    if portfolio_failure_samples:
        lines.extend(
            [
                "## Pose-Order Portfolio Failure Samples",
                "",
                "| Anchor | Ordering | Source | Reason | Status |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for entry in portfolio_failure_samples:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("anchor_idx")),
                        _markdown_cell(entry.get("ordering")),
                        _markdown_cell(entry.get("source")),
                        _markdown_cell(entry.get("failure_reason")),
                        _markdown_cell(entry.get("status")),
                    ]
                )
                + " |"
            )
        lines.append("")
    portfolio_probe = _mapping(diag.get("portfolio_probe"))
    if bool(portfolio_probe.get("enabled", False)):
        lines.extend(
            [
                "## Portfolio Probe",
                "",
                f"- Success found: {bool(portfolio_probe.get('success_found', False))}",
                f"- Samples: {portfolio_probe.get('sample_count', 0)}",
                f"- Successes: {portfolio_probe.get('success_count', 0)}",
                "",
                "| Anchor | Success | Attempts | Window | Group order | Pose orderings | Failure summary |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in list(portfolio_probe.get("samples", [])):
            if not isinstance(entry, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("anchor_idx")),
                        _markdown_cell(entry.get("success")),
                        _markdown_cell(entry.get("attempt_count")),
                        _markdown_cell(entry.get("window_size")),
                        _markdown_cell(entry.get("group_order")),
                        _markdown_cell(",".join(str(name) for name in list(entry.get("pose_orderings", [])))),
                        _markdown_cell(_probe_failure_summary(entry)),
                    ]
                )
                + " |"
            )
        lines.append("")
    group_packing_probe = _mapping(diag.get("group_packing_probe"))
    if bool(group_packing_probe.get("enabled", False)):
        lines.extend(
            [
                "## Group Packing Probe",
                "",
                f"- Feasible found: {bool(group_packing_probe.get('feasible_found', False))}",
                f"- Samples: {group_packing_probe.get('sample_count', 0)}",
                f"- Feasible: {group_packing_probe.get('feasible_count', 0)}",
                f"- Infeasible: {group_packing_probe.get('infeasible_count', 0)}",
                f"- Unknown: {group_packing_probe.get('unknown_count', 0)}",
                f"- Skipped: {group_packing_probe.get('skipped_count', 0)}",
                "",
                "| Anchor | Group | Required | Surviving | Greedy | Exact feasible | Status |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in list(group_packing_probe.get("samples", [])):
            if not isinstance(entry, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("anchor_idx")),
                        _markdown_cell(entry.get("group_id")),
                        _markdown_cell(entry.get("required_count")),
                        _markdown_cell(entry.get("surviving_at_failure_count")),
                        _markdown_cell(entry.get("greedy_selected_count")),
                        _markdown_cell(entry.get("exact_feasible")),
                        _markdown_cell(
                            entry.get("solver_status") or entry.get("skip_reason")
                        ),
                    ]
                )
                + " |"
            )
        lines.append("")
    group_packing_blockers = _mapping(diag.get("group_packing_blockers"))
    if bool(group_packing_blockers.get("enabled", False)):
        lines.extend(
            [
                "## Diagnostic Group Packing Blockers",
                "",
                f"- Blockers: {group_packing_blockers.get('blocker_count', 0)}",
                f"- Precheck design candidate: {bool(group_packing_blockers.get('precheck_design_candidate', False))}",
                f"- Recommendation: {group_packing_blockers.get('recommendation')}",
                "",
                "| Group | Facility | Status | Samples | Anchors | Required | Surviving | Greedy |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in list(group_packing_blockers.get("blockers", [])):
            if not isinstance(entry, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("group_id")),
                        _markdown_cell(entry.get("facility_type")),
                        _markdown_cell(entry.get("solver_status")),
                        _markdown_cell(entry.get("sample_count")),
                        _markdown_cell(",".join(str(idx) for idx in list(entry.get("anchor_indices", [])))),
                        _markdown_cell(
                            f"{entry.get('required_count_min')}..{entry.get('required_count_max')}"
                        ),
                        _markdown_cell(
                            f"{entry.get('surviving_at_failure_min')}..{entry.get('surviving_at_failure_max')}"
                        ),
                        _markdown_cell(
                            f"{entry.get('greedy_selected_min')}..{entry.get('greedy_selected_max')}"
                        ),
                    ]
                )
                + " |"
            )
        lines.append("")
    samples = [
        entry
        for entry in list(summary.get("failed_anchor_samples", []))
        if isinstance(entry, Mapping)
    ]
    if samples:
        lines.extend(
            [
                "## Failed Anchor Samples",
                "",
                "| Anchor | Reason | Group | Position | Surviving at failure | Local repair |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in samples:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("anchor_idx")),
                        _markdown_cell(entry.get("failure_reason")),
                        _markdown_cell(entry.get("first_failed_group_id")),
                        _markdown_cell(entry.get("first_failed_group_position")),
                        _markdown_cell(
                            entry.get(
                                "first_failed_group_surviving_at_failure_count"
                            )
                        ),
                        _markdown_cell(
                            "success"
                            if bool(entry.get("local_repair_success", False))
                            else (
                                "attempted"
                                if bool(entry.get("local_repair_attempted", False))
                                else "not_attempted"
                            )
                        ),
                    ]
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def render_phase3b_start_compatibility_text(diagnostics: Mapping[str, Any]) -> str:
    candidate = _mapping(diagnostics.get("candidate"))
    status = _mapping(diagnostics.get("status"))
    diag = _mapping(diagnostics.get("diagnostics"))
    summary = _mapping(diag.get("start_failure_summary"))
    lines = [
        "Phase 3B start compatibility diagnostics",
        f"candidate={candidate.get('key')}",
        f"compatible_start_found={bool(status.get('compatible_start_found', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        "coordinate_pose_order_validation_rejected_count="
        f"{status.get('coordinate_pose_order_validation_rejected_count', 0)}",
        f"failed_anchor_count={summary.get('failed_anchor_count', 0)}",
        f"failure_reason_counts={summary.get('failure_reason_counts', {})}",
    ]
    first_group = _mapping(summary.get("first_failed_group"))
    if first_group:
        lines.append(
            "first_failed_group="
            f"{first_group.get('group_id')}/"
            f"{first_group.get('facility_type')}@{first_group.get('position')} "
            f"required={first_group.get('required_count')} "
            f"candidates={first_group.get('candidate_count')} "
            f"surviving_at_failure={first_group.get('surviving_at_failure_count')}"
        )
    for entry in list(summary.get("top_failed_group_failures", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "top_failed_group_failure="
            f"{entry.get('group_id')}/"
            f"{entry.get('facility_type')}:"
            f"{entry.get('failure_reason')}x{entry.get('count')}"
        )
    warm_start = _mapping(diag.get("warm_start"))
    for entry in list(
        warm_start.get("ghost_aware_pose_order_validation_rejection_samples", [])
    ):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "pose_order_validation_rejection_sample="
            f"anchor={entry.get('anchor_idx')} "
            f"ordering={entry.get('ordering')} "
            f"status={entry.get('status')} "
            f"reason={entry.get('reason')} "
            f"forced_slots={entry.get('forced_slot_field_count')} "
            f"branches={entry.get('branches')} "
            f"conflicts={entry.get('conflicts')}"
        )
    for entry in list(
        warm_start.get("ghost_aware_pose_order_portfolio_failure_samples", [])
    ):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "pose_order_portfolio_failure_sample="
            f"anchor={entry.get('anchor_idx')} "
            f"ordering={entry.get('ordering')} "
            f"source={entry.get('source')} "
            f"reason={entry.get('failure_reason')} "
            f"status={entry.get('status')}"
        )
    for entry in list(summary.get("failed_anchor_samples", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "failed_anchor_sample="
            f"anchor={entry.get('anchor_idx')} "
            f"reason={entry.get('failure_reason')} "
            f"group={entry.get('first_failed_group_id')} "
            f"position={entry.get('first_failed_group_position')} "
            f"surviving_at_failure={entry.get('first_failed_group_surviving_at_failure_count')} "
            f"local_repair_attempted={bool(entry.get('local_repair_attempted', False))} "
            f"local_repair_success={bool(entry.get('local_repair_success', False))}"
        )
    portfolio_probe = _mapping(diag.get("portfolio_probe"))
    if bool(portfolio_probe.get("enabled", False)):
        lines.append(
            "portfolio_probe="
            f"success_found={bool(portfolio_probe.get('success_found', False))} "
            f"samples={portfolio_probe.get('sample_count', 0)} "
            f"successes={portfolio_probe.get('success_count', 0)}"
        )
        for entry in list(portfolio_probe.get("samples", [])):
            if not isinstance(entry, Mapping):
                continue
            lines.append(
                "portfolio_probe_sample="
                f"anchor={entry.get('anchor_idx')} "
                f"success={bool(entry.get('success', False))} "
                f"attempts={entry.get('attempt_count')} "
                f"window={entry.get('window_size')} "
                f"group_order={entry.get('group_order')} "
                f"failure_summary={_probe_failure_summary(entry)}"
            )
    group_packing_probe = _mapping(diag.get("group_packing_probe"))
    if bool(group_packing_probe.get("enabled", False)):
        lines.append(
            "group_packing_probe="
            f"feasible_found={bool(group_packing_probe.get('feasible_found', False))} "
            f"samples={group_packing_probe.get('sample_count', 0)} "
            f"feasible={group_packing_probe.get('feasible_count', 0)} "
            f"infeasible={group_packing_probe.get('infeasible_count', 0)} "
            f"unknown={group_packing_probe.get('unknown_count', 0)} "
            f"skipped={group_packing_probe.get('skipped_count', 0)}"
        )
        for entry in list(group_packing_probe.get("samples", [])):
            if not isinstance(entry, Mapping):
                continue
            lines.append(
                "group_packing_sample="
                f"anchor={entry.get('anchor_idx')} "
                f"group={entry.get('group_id')} "
                f"required={entry.get('required_count')} "
                f"surviving={entry.get('surviving_at_failure_count')} "
                f"greedy={entry.get('greedy_selected_count')} "
                f"exact_feasible={entry.get('exact_feasible')} "
                f"status={entry.get('solver_status') or entry.get('skip_reason')}"
            )
    group_packing_blockers = _mapping(diag.get("group_packing_blockers"))
    if bool(group_packing_blockers.get("enabled", False)):
        lines.append(
            "group_packing_blockers="
            f"count={group_packing_blockers.get('blocker_count', 0)} "
            f"precheck_design_candidate={bool(group_packing_blockers.get('precheck_design_candidate', False))}"
        )
        for entry in list(group_packing_blockers.get("blockers", [])):
            if not isinstance(entry, Mapping):
                continue
            lines.append(
                "group_packing_blocker="
                f"group={entry.get('group_id')} "
                f"status={entry.get('solver_status')} "
                f"samples={entry.get('sample_count')} "
                f"anchors={','.join(str(idx) for idx in list(entry.get('anchor_indices', [])))} "
                f"required={entry.get('required_count_min')}..{entry.get('required_count_max')} "
                f"surviving={entry.get('surviving_at_failure_min')}..{entry.get('surviving_at_failure_max')}"
            )
    return "\n".join(lines) + "\n"


def _evaluate_boundary_port_precheck(
    *,
    exact_session: Any,
    ghost_rect: Tuple[int, int],
) -> Dict[str, Any]:
    candidate_precheck_artifacts = dict(
        getattr(exact_session.core, "candidate_precheck_artifacts", {})
    )
    boundary_port_screen_spec = candidate_precheck_artifacts.get(
        "boundary_port_screen_spec"
    )
    if not isinstance(boundary_port_screen_spec, Mapping):
        return MasterPlacementModel._default_exact_candidate_boundary_port_feasibility_payload()
    return MasterPlacementModel.evaluate_boundary_port_feasibility_from_screen_spec(
        rules=exact_session.core.rules,
        ghost_rect=ghost_rect,
        screen_spec=boundary_port_screen_spec,
    )


def _status_from_warm_start(
    warm_start: Mapping[str, Any],
    start_failure_summary: Optional[Mapping[str, Any]],
    portfolio_probe: Mapping[str, Any],
    group_packing_probe: Mapping[str, Any],
    group_packing_blockers: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    compatible = int(warm_start.get("ghost_anchor_compatible_count", 0)) > 0
    skipped = bool(warm_start.get("ghost_anchor_compatibility_skipped", False))
    probe_success = bool(portfolio_probe.get("success_found", False))
    packing_feasible = bool(group_packing_probe.get("feasible_found", False))
    packing_blockers = _mapping(group_packing_blockers)
    packing_infeasible_found = int(packing_blockers.get("blocker_count", 0)) > 0
    pose_order_validation_rejected_count = int(
        warm_start.get("ghost_aware_pose_order_validation_rejected_count", 0)
    )
    precheck_design_candidate = bool(
        packing_blockers.get("precheck_design_candidate", False)
    )
    if compatible:
        outcome = "compatible_start_found"
        recommendation = "Proceed to a bounded B5A solve probe for this candidate in a workspace copy."
    elif probe_success:
        outcome = "diagnostic_portfolio_start_found"
        recommendation = "Promote the successful diagnostic portfolio pattern into a conservative B2/B3 runtime patch before rerunning B5A."
    elif packing_feasible:
        outcome = "diagnostic_group_packing_feasible"
        recommendation = "A failed group can pack exactly under the sampled prefix; investigate greedy/order repair before shrinking the domain."
    elif precheck_design_candidate:
        outcome = "diagnostic_group_packing_infeasible"
        recommendation = "Sampled failed groups are exact-infeasible; use this as B2 precheck design input, not as terminal proof."
    elif skipped:
        outcome = "compatibility_skipped"
        recommendation = "Raise diagnostic caps only in workspace runs if more start evidence is needed."
    elif isinstance(start_failure_summary, Mapping):
        outcome = "start_incompatible"
        recommendation = "Return to B2/B3 targeted shrink or warm-start/local-repair diagnostics for the listed groups."
    else:
        outcome = "no_start_evidence"
        recommendation = "Inspect mandatory support and boundary precheck diagnostics before running a longer solve."
    return {
        "compatible_start_found": bool(compatible),
        "compatibility_skipped": bool(skipped),
        "diagnostic_portfolio_start_found": bool(probe_success),
        "diagnostic_group_packing_feasible": bool(packing_feasible),
        "diagnostic_group_packing_infeasible_found": bool(packing_infeasible_found),
        "diagnostic_group_packing_precheck_design_candidate": bool(
            precheck_design_candidate
        ),
        "coordinate_pose_order_validation_rejected": bool(
            pose_order_validation_rejected_count > 0
        ),
        "coordinate_pose_order_validation_rejected_count": int(
            pose_order_validation_rejected_count
        ),
        "outcome": outcome,
        "recommendation": recommendation,
    }


def _build_portfolio_probe(
    model: MasterPlacementModel,
    *,
    failure_attribution: Mapping[str, Any],
    sample_limit: int,
    max_window_size: int,
    max_attempts_per_sample: int,
) -> Dict[str, Any]:
    sample_limit = max(0, int(sample_limit))
    max_window_size = max(1, int(max_window_size))
    max_attempts_per_sample = max(1, int(max_attempts_per_sample))
    payload: Dict[str, Any] = {
        "enabled": bool(sample_limit > 0),
        "sample_limit": int(sample_limit),
        "max_window_size": int(max_window_size),
        "max_attempts_per_sample": int(max_attempts_per_sample),
        "sample_count": 0,
        "success_count": 0,
        "success_found": False,
        "samples": [],
    }
    if sample_limit <= 0:
        return payload

    raw_samples = [
        entry
        for entry in list(failure_attribution.get("failed_anchor_samples", []))
        if isinstance(entry, Mapping)
    ][:sample_limit]
    candidates_by_group = {
        str(group["group_id"]): model._candidate_pose_indices_for_group(group)
        for group in model._mandatory_groups
    }
    ordered_groups = model._ordered_mandatory_groups_for_greedy(candidates_by_group)
    for raw_sample in raw_samples:
        sample_result = _probe_failed_anchor_sample(
            model,
            sample=raw_sample,
            ordered_groups=ordered_groups,
            candidates_by_group=candidates_by_group,
            max_window_size=max_window_size,
            max_attempts=max_attempts_per_sample,
        )
        payload["samples"].append(sample_result)
        if bool(sample_result.get("success", False)):
            payload["success_count"] = int(payload["success_count"]) + 1
    payload["sample_count"] = len(payload["samples"])
    payload["success_found"] = int(payload["success_count"]) > 0
    return payload


def _build_group_packing_probe(
    model: MasterPlacementModel,
    *,
    failure_attribution: Mapping[str, Any],
    sample_limit: int,
    time_limit_seconds: float,
    max_candidates: int,
) -> Dict[str, Any]:
    sample_limit = max(0, int(sample_limit))
    time_limit_seconds = max(0.01, float(time_limit_seconds))
    max_candidates = max(1, int(max_candidates))
    payload: Dict[str, Any] = {
        "enabled": bool(sample_limit > 0),
        "sample_limit": int(sample_limit),
        "time_limit_seconds": float(time_limit_seconds),
        "max_candidates": int(max_candidates),
        "sample_count": 0,
        "feasible_count": 0,
        "infeasible_count": 0,
        "unknown_count": 0,
        "skipped_count": 0,
        "feasible_found": False,
        "samples": [],
    }
    if sample_limit <= 0:
        return payload

    raw_samples = [
        entry
        for entry in list(failure_attribution.get("failed_anchor_samples", []))
        if isinstance(entry, Mapping)
    ][:sample_limit]
    candidates_by_group = {
        str(group["group_id"]): model._candidate_pose_indices_for_group(group)
        for group in model._mandatory_groups
    }
    ordered_groups = model._ordered_mandatory_groups_for_greedy(candidates_by_group)
    for raw_sample in raw_samples:
        sample_result = _probe_group_packing_for_failed_anchor(
            model,
            sample=raw_sample,
            ordered_groups=ordered_groups,
            candidates_by_group=candidates_by_group,
            time_limit_seconds=time_limit_seconds,
            max_candidates=max_candidates,
        )
        payload["samples"].append(sample_result)
        if bool(sample_result.get("skipped", False)):
            payload["skipped_count"] = int(payload["skipped_count"]) + 1
        elif sample_result.get("exact_feasible") is True:
            payload["feasible_count"] = int(payload["feasible_count"]) + 1
        elif sample_result.get("exact_feasible") is False:
            payload["infeasible_count"] = int(payload["infeasible_count"]) + 1
        else:
            payload["unknown_count"] = int(payload["unknown_count"]) + 1
    payload["sample_count"] = len(payload["samples"])
    payload["feasible_found"] = int(payload["feasible_count"]) > 0
    return payload


def _build_group_packing_blockers(
    group_packing_probe: Mapping[str, Any],
) -> Dict[str, Any]:
    enabled = bool(group_packing_probe.get("enabled", False))
    samples = [
        sample
        for sample in list(group_packing_probe.get("samples", []))
        if isinstance(sample, Mapping)
    ]
    blocker_samples = [
        sample
        for sample in samples
        if sample.get("exact_feasible") is False
        and not bool(sample.get("skipped", False))
    ]
    grouped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for sample in blocker_samples:
        key = (
            str(sample.get("group_id", "")),
            str(sample.get("facility_type", "")),
            str(sample.get("solver_status", "")),
        )
        entry = grouped.setdefault(
            key,
            {
                "group_id": key[0],
                "facility_type": key[1],
                "solver_status": key[2],
                "sample_count": 0,
                "anchor_indices": [],
                "required_count_min": None,
                "required_count_max": None,
                "surviving_at_failure_min": None,
                "surviving_at_failure_max": None,
                "greedy_selected_min": None,
                "greedy_selected_max": None,
                "evidence_strength": "sampled_exact_infeasible",
            },
        )
        entry["sample_count"] = int(entry["sample_count"]) + 1
        entry["anchor_indices"].append(int(sample.get("anchor_idx", 0)))
        _update_min_max(entry, "required_count", int(sample.get("required_count", 0)))
        _update_min_max(
            entry,
            "surviving_at_failure",
            int(sample.get("surviving_at_failure_count", 0)),
        )
        _update_min_max(
            entry,
            "greedy_selected",
            int(sample.get("greedy_selected_count", 0)),
        )
    blockers = sorted(
        grouped.values(),
        key=lambda entry: (
            -int(entry.get("sample_count", 0)),
            str(entry.get("group_id", "")),
            str(entry.get("solver_status", "")),
        ),
    )
    sample_count = int(group_packing_probe.get("sample_count", len(samples)))
    feasible_count = int(group_packing_probe.get("feasible_count", 0))
    unknown_count = int(group_packing_probe.get("unknown_count", 0))
    skipped_count = int(group_packing_probe.get("skipped_count", 0))
    blocker_count = int(len(blockers))
    precheck_design_candidate = bool(
        enabled
        and sample_count > 0
        and blocker_count > 0
        and feasible_count == 0
        and unknown_count == 0
        and skipped_count == 0
        and len(blocker_samples) == sample_count
    )
    if not enabled:
        recommendation = "Group packing probe disabled."
    elif precheck_design_candidate:
        recommendation = (
            "Use sampled exact-infeasible group packing evidence to design a "
            "B2 diagnostic/pre-master precheck; keep it out of terminal proof until broadened."
        )
    elif blocker_count > 0:
        recommendation = (
            "Some sampled groups are exact-infeasible, but evidence is mixed or incomplete; "
            "broaden sampling before precheck promotion."
        )
    else:
        recommendation = "No sampled exact-infeasible group packing blocker was found."
    return {
        "enabled": enabled,
        "blocker_count": blocker_count,
        "sample_count": sample_count,
        "precheck_design_candidate": precheck_design_candidate,
        "recommendation": recommendation,
        "blockers": blockers,
    }


def _update_min_max(entry: Dict[str, Any], name: str, value: int) -> None:
    min_key = f"{name}_min"
    max_key = f"{name}_max"
    if entry.get(min_key) is None or int(value) < int(entry[min_key]):
        entry[min_key] = int(value)
    if entry.get(max_key) is None or int(value) > int(entry[max_key]):
        entry[max_key] = int(value)


def _probe_group_packing_for_failed_anchor(
    model: MasterPlacementModel,
    *,
    sample: Mapping[str, Any],
    ordered_groups: Sequence[Mapping[str, Any]],
    candidates_by_group: Mapping[str, Sequence[int]],
    time_limit_seconds: float,
    max_candidates: int,
) -> Dict[str, Any]:
    try:
        anchor_idx = int(sample.get("anchor_idx"))
        failed_position = int(sample.get("first_failed_group_position"))
    except Exception:
        return {
            "anchor_idx": sample.get("anchor_idx"),
            "skipped": True,
            "skip_reason": "missing_anchor_or_position",
        }
    if anchor_idx < 0 or anchor_idx >= len(model._ghost_domains):
        return {
            "anchor_idx": int(anchor_idx),
            "skipped": True,
            "skip_reason": "anchor_index_out_of_range",
        }
    if failed_position < 0 or failed_position >= len(ordered_groups):
        return {
            "anchor_idx": int(anchor_idx),
            "skipped": True,
            "skip_reason": "failed_group_position_out_of_range",
        }

    target_group = dict(ordered_groups[int(failed_position)])
    group_id = str(target_group.get("group_id", ""))
    tpl = str(target_group.get("facility_type", ""))
    required_count = int(target_group.get("count", 0))
    domain = model._ghost_domains[int(anchor_idx)]
    blocked_cells = {
        (int(cell[0]), int(cell[1]))
        for cell in list(domain.get("cells", []))
    }
    prefix_result = model._run_mandatory_greedy_pass(
        ordered_groups=list(ordered_groups[:failed_position]),
        candidates_by_group=candidates_by_group,
        blocked_cells=set(blocked_cells),
        stop_on_first_failure=False,
    )
    if not bool(prefix_result.get("complete", False)):
        return {
            "anchor_idx": int(anchor_idx),
            "group_id": group_id,
            "facility_type": tpl,
            "skipped": True,
            "skip_reason": "prefix_failed",
            "prefix_failed_group_id": prefix_result.get("first_failed_group_id"),
        }
    committed_cells = {
        (int(cell[0]), int(cell[1]))
        for cell in set(prefix_result.get("committed_cells", set()))
    }
    candidate_indices = [int(idx) for idx in candidates_by_group.get(group_id, [])]
    surviving_after_blocked = [
        int(idx)
        for idx in candidate_indices
        if blocked_cells.isdisjoint(model._pose_cells(tpl, int(idx)))
    ]
    surviving_at_failure = [
        int(idx)
        for idx in candidate_indices
        if committed_cells.isdisjoint(model._pose_cells(tpl, int(idx)))
    ]
    if len(surviving_at_failure) > int(max_candidates):
        return {
            "anchor_idx": int(anchor_idx),
            "group_id": group_id,
            "facility_type": tpl,
            "required_count": int(required_count),
            "surviving_after_blocked_count": int(len(surviving_after_blocked)),
            "surviving_at_failure_count": int(len(surviving_at_failure)),
            "skipped": True,
            "skip_reason": "candidate_limit_exceeded",
            "max_candidates": int(max_candidates),
        }
    greedy_selected_count = _greedy_select_count(
        model,
        tpl=tpl,
        candidate_indices=surviving_at_failure,
        committed_cells=committed_cells,
    )
    exact_result = _solve_group_packing_feasibility(
        model,
        tpl=tpl,
        candidate_indices=surviving_at_failure,
        required_count=required_count,
        time_limit_seconds=time_limit_seconds,
    )
    return {
        "anchor_idx": int(anchor_idx),
        "group_id": group_id,
        "facility_type": tpl,
        "required_count": int(required_count),
        "candidate_count": int(len(candidate_indices)),
        "surviving_after_blocked_count": int(len(surviving_after_blocked)),
        "surviving_at_failure_count": int(len(surviving_at_failure)),
        "greedy_selected_count": int(greedy_selected_count),
        "skipped": False,
        **exact_result,
    }


def _greedy_select_count(
    model: MasterPlacementModel,
    *,
    tpl: str,
    candidate_indices: Sequence[int],
    committed_cells: set[Tuple[int, int]],
) -> int:
    trial_cells = set(committed_cells)
    selected_count = 0
    for pose_idx in candidate_indices:
        pose_cells = model._pose_cells(str(tpl), int(pose_idx))
        if trial_cells.intersection(pose_cells):
            continue
        trial_cells.update(pose_cells)
        selected_count += 1
    return int(selected_count)


def _solve_group_packing_feasibility(
    model: MasterPlacementModel,
    *,
    tpl: str,
    candidate_indices: Sequence[int],
    required_count: int,
    time_limit_seconds: float,
) -> Dict[str, Any]:
    required_count = int(required_count)
    if required_count <= 0:
        return {
            "exact_feasible": True,
            "solver_status": "TRIVIAL",
            "selected_count": 0,
            "constraint_cell_count": 0,
            "candidate_count_considered": int(len(candidate_indices)),
        }
    if len(candidate_indices) < required_count:
        return {
            "exact_feasible": False,
            "solver_status": "CANDIDATE_COUNT_BELOW_REQUIRED",
            "selected_count": int(len(candidate_indices)),
            "constraint_cell_count": 0,
            "candidate_count_considered": int(len(candidate_indices)),
        }

    local_model = cp_model.CpModel()
    vars_by_pose = {
        int(pose_idx): local_model.NewBoolVar(f"pose_{int(pose_idx)}")
        for pose_idx in candidate_indices
    }
    cell_to_terms: Dict[Tuple[int, int], List[Any]] = {}
    for pose_idx in candidate_indices:
        var = vars_by_pose[int(pose_idx)]
        for cell in model._pose_cells(str(tpl), int(pose_idx)):
            cell_to_terms.setdefault((int(cell[0]), int(cell[1])), []).append(var)
    constraint_cell_count = 0
    for terms in cell_to_terms.values():
        if len(terms) > 1:
            local_model.Add(sum(terms) <= 1)
            constraint_cell_count += 1
    local_model.Add(sum(vars_by_pose.values()) >= int(required_count))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = 1
    status = solver.Solve(local_model)
    status_name = _cp_solver_status_name(status)
    if status in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        selected_count = sum(
            1 for var in vars_by_pose.values() if int(solver.Value(var)) > 0
        )
        return {
            "exact_feasible": True,
            "solver_status": status_name,
            "selected_count": int(selected_count),
            "constraint_cell_count": int(constraint_cell_count),
            "candidate_count_considered": int(len(candidate_indices)),
        }
    if status == cp_model.INFEASIBLE:
        return {
            "exact_feasible": False,
            "solver_status": status_name,
            "selected_count": 0,
            "constraint_cell_count": int(constraint_cell_count),
            "candidate_count_considered": int(len(candidate_indices)),
        }
    return {
        "exact_feasible": None,
        "solver_status": status_name,
        "selected_count": None,
        "constraint_cell_count": int(constraint_cell_count),
        "candidate_count_considered": int(len(candidate_indices)),
    }


def _cp_solver_status_name(status: int) -> str:
    return {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN: "UNKNOWN",
    }.get(int(status), str(status))


def _probe_failed_anchor_sample(
    model: MasterPlacementModel,
    *,
    sample: Mapping[str, Any],
    ordered_groups: Sequence[Mapping[str, Any]],
    candidates_by_group: Mapping[str, Sequence[int]],
    max_window_size: int,
    max_attempts: int,
) -> Dict[str, Any]:
    try:
        anchor_idx = int(sample.get("anchor_idx"))
        failed_position = int(sample.get("first_failed_group_position"))
    except Exception:
        return {
            "anchor_idx": sample.get("anchor_idx"),
            "success": False,
            "skipped": True,
            "skip_reason": "missing_anchor_or_position",
            "attempt_count": 0,
        }
    if anchor_idx < 0 or anchor_idx >= len(model._ghost_domains):
        return {
            "anchor_idx": int(anchor_idx),
            "success": False,
            "skipped": True,
            "skip_reason": "anchor_index_out_of_range",
            "attempt_count": 0,
        }
    if failed_position < 0 or failed_position >= len(ordered_groups):
        return {
            "anchor_idx": int(anchor_idx),
            "success": False,
            "skipped": True,
            "skip_reason": "failed_group_position_out_of_range",
            "attempt_count": 0,
        }

    domain = model._ghost_domains[int(anchor_idx)]
    blocked_cells = {
        (int(cell[0]), int(cell[1]))
        for cell in list(domain.get("cells", []))
    }
    attempt_count = 0
    failed_attempt_reasons: Dict[Tuple[str, str, str], int] = {}
    first_attempt_failures: List[Dict[str, Any]] = []
    order_portfolio = (
        "canonical",
        "reverse_canonical",
        "overlap_degree_asc",
        "overlap_degree_desc",
    )

    for window_size in range(1, max(1, int(max_window_size)) + 1):
        window_start = max(0, int(failed_position) - int(window_size) + 1)
        repair_groups = list(ordered_groups[window_start : failed_position + 1])
        if not repair_groups:
            continue
        prefix_groups = list(ordered_groups[:window_start])
        suffix_groups = list(ordered_groups[failed_position + 1 :])
        prefix_result = model._run_mandatory_greedy_pass(
            ordered_groups=prefix_groups,
            candidates_by_group=candidates_by_group,
            blocked_cells=set(blocked_cells),
            stop_on_first_failure=False,
        )
        if not bool(prefix_result.get("complete", False)):
            return {
                "anchor_idx": int(anchor_idx),
                "success": False,
                "skipped": False,
                "skip_reason": None,
                "attempt_count": int(attempt_count),
                "failure_reason": "prefix_failed",
                "prefix_failed_group_id": prefix_result.get("first_failed_group_id"),
            }

        group_orderings = _repair_group_orderings(
            model,
            repair_groups=repair_groups,
            candidates_by_group=candidates_by_group,
            frozen_committed_cells=set(prefix_result.get("committed_cells", set())),
        )
        group_order_variants = [("canonical_group_order", list(repair_groups))]
        if len(repair_groups) > 1:
            group_order_variants.append(("reverse_group_order", list(reversed(repair_groups))))

        for group_order_name, repair_order_groups in group_order_variants:
            for pose_order_names in product(order_portfolio, repeat=len(repair_order_groups)):
                if attempt_count >= int(max_attempts):
                    return _failed_probe_result(
                        anchor_idx=anchor_idx,
                        attempt_count=attempt_count,
                        max_attempts=max_attempts,
                        failed_attempt_reasons=failed_attempt_reasons,
                        first_attempt_failures=first_attempt_failures,
                    )
                attempt_count += 1
                custom_group_orders = {
                    str(group["group_id"]): list(
                        group_orderings.get(str(group["group_id"]), {}).get(
                            str(order_name),
                            [],
                        )
                    )
                    for group, order_name in zip(repair_order_groups, pose_order_names)
                }
                window_result = model._run_mandatory_greedy_pass(
                    ordered_groups=repair_order_groups,
                    candidates_by_group=candidates_by_group,
                    blocked_cells=set(blocked_cells),
                    initial_solution_hint=prefix_result.get("solution_hint", {}),
                    initial_committed_cells=set(prefix_result.get("committed_cells", set())),
                    initial_hinted_occupied_cells=set(
                        prefix_result.get("hinted_occupied_cells", set())
                    ),
                    custom_group_orders=custom_group_orders,
                    stop_on_first_failure=True,
                )
                if not bool(window_result.get("complete", False)):
                    _record_probe_failure(
                        window_result,
                        failed_attempt_reasons,
                        first_attempt_failures,
                    )
                    continue
                if suffix_groups:
                    suffix_result = model._run_mandatory_greedy_pass(
                        ordered_groups=suffix_groups,
                        candidates_by_group=candidates_by_group,
                        blocked_cells=set(blocked_cells),
                        initial_solution_hint=window_result.get("solution_hint", {}),
                        initial_committed_cells=set(window_result.get("committed_cells", set())),
                        initial_hinted_occupied_cells=set(
                            window_result.get("hinted_occupied_cells", set())
                        ),
                        stop_on_first_failure=True,
                    )
                    if not bool(suffix_result.get("complete", False)):
                        _record_probe_failure(
                            suffix_result,
                            failed_attempt_reasons,
                            first_attempt_failures,
                        )
                        continue
                    result = suffix_result
                else:
                    result = window_result
                return {
                    "anchor_idx": int(anchor_idx),
                    "success": True,
                    "skipped": False,
                    "skip_reason": None,
                    "attempt_count": int(attempt_count),
                    "window_size": int(len(repair_groups)),
                    "window_start_position": int(window_start),
                    "window_end_position": int(failed_position),
                    "group_order": str(group_order_name),
                    "pose_orderings": [str(name) for name in pose_order_names],
                    "hinted_instances": int(result.get("hinted_instances", 0)),
                }

    return _failed_probe_result(
        anchor_idx=anchor_idx,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        failed_attempt_reasons=failed_attempt_reasons,
        first_attempt_failures=first_attempt_failures,
    )


def _repair_group_orderings(
    model: MasterPlacementModel,
    *,
    repair_groups: Sequence[Mapping[str, Any]],
    candidates_by_group: Mapping[str, Sequence[int]],
    frozen_committed_cells: set[Tuple[int, int]],
) -> Dict[str, Dict[str, List[int]]]:
    group_orderings: Dict[str, Dict[str, List[int]]] = {}
    for group in repair_groups:
        group_id = str(group["group_id"])
        tpl = str(group["facility_type"])
        group_orderings[group_id] = model._local_repair_pose_orderings(
            tpl,
            candidates_by_group.get(group_id, []),
            frozen_committed_cells,
        )
    return group_orderings


def _record_probe_failure(
    result: Mapping[str, Any],
    failed_attempt_reasons: Dict[Tuple[str, str, str], int],
    first_attempt_failures: List[Dict[str, Any]],
) -> None:
    reason = str(result.get("first_failure_reason") or "unknown")
    group_id = str(result.get("first_failed_group_id") or "")
    facility_type = str(result.get("first_failed_group_template") or "")
    key = (group_id, facility_type, reason)
    failed_attempt_reasons[key] = int(failed_attempt_reasons.get(key, 0)) + 1
    if len(first_attempt_failures) < 5:
        first_attempt_failures.append(
            {
                "group_id": group_id or None,
                "facility_type": facility_type or None,
                "failure_reason": reason,
                "position": result.get("first_failed_group_position"),
                "surviving_at_failure_count": int(
                    result.get("first_failed_group_surviving_at_failure_count", 0)
                ),
            }
        )


def _failed_probe_result(
    *,
    anchor_idx: int,
    attempt_count: int,
    max_attempts: int,
    failed_attempt_reasons: Mapping[Tuple[str, str, str], int],
    first_attempt_failures: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    return {
        "anchor_idx": int(anchor_idx),
        "success": False,
        "skipped": False,
        "skip_reason": None,
        "attempt_count": int(attempt_count),
        "max_attempts_reached": bool(int(attempt_count) >= int(max_attempts)),
        "top_failed_attempt_reasons": [
            {
                "group_id": str(group_id),
                "facility_type": str(facility_type),
                "failure_reason": str(reason),
                "count": int(count),
            }
            for (group_id, facility_type, reason), count in sorted(
                failed_attempt_reasons.items(),
                key=lambda item: (-int(item[1]), item[0][0], item[0][2]),
            )[:5]
        ],
        "first_attempt_failures": [dict(entry) for entry in first_attempt_failures[:5]],
    }


def _start_failure_summary(
    failure_attribution: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    failed_anchor_count = int(failure_attribution.get("failed_anchor_count", 0))
    failure_reason_counts = {
        str(key): int(value)
        for key, value in dict(
            failure_attribution.get("failure_reason_counts", {})
        ).items()
        if int(value) > 0
    }
    top_failed_group_failures = [
        {
            "group_id": str(entry.get("group_id", "")),
            "facility_type": str(entry.get("facility_type", "")),
            "failure_reason": str(entry.get("failure_reason", "")),
            "count": int(entry.get("count", 0)),
        }
        for entry in list(failure_attribution.get("top_failed_group_failures", []))[:8]
        if isinstance(entry, Mapping) and int(entry.get("count", 0)) > 0
    ]
    failed_anchor_samples = [
        _compact_failed_anchor_sample(entry)
        for entry in list(failure_attribution.get("failed_anchor_samples", []))[:8]
        if isinstance(entry, Mapping)
    ]
    if (
        failed_anchor_count <= 0
        and not failure_reason_counts
        and not top_failed_group_failures
        and not failed_anchor_samples
    ):
        return None
    return {
        "failed_anchor_count": int(failed_anchor_count),
        "failure_reason_counts": failure_reason_counts,
        "first_failed_group": {
            "group_id": failure_attribution.get("first_failed_group_id"),
            "facility_type": failure_attribution.get("first_failed_group_template"),
            "position": failure_attribution.get("first_failed_group_position"),
            "required_count": int(
                failure_attribution.get("first_failed_group_required_count", 0)
            ),
            "candidate_count": int(
                failure_attribution.get("first_failed_group_candidate_count", 0)
            ),
            "surviving_after_blocked_count": int(
                failure_attribution.get(
                    "first_failed_group_surviving_after_blocked_count",
                    0,
                )
            ),
            "surviving_at_failure_count": int(
                failure_attribution.get(
                    "first_failed_group_surviving_at_failure_count",
                    0,
                )
            ),
        },
        "top_failed_group_failures": top_failed_group_failures,
        "failed_anchor_samples": failed_anchor_samples,
    }


def _compact_failed_anchor_sample(entry: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "anchor_idx": int(entry.get("anchor_idx", 0)),
        "failure_reason": str(entry.get("failure_reason", "")),
        "first_failed_group_id": entry.get("first_failed_group_id"),
        "first_failed_group_template": entry.get("first_failed_group_template"),
        "first_failed_group_position": entry.get("first_failed_group_position"),
        "first_failed_group_required_count": int(
            entry.get("first_failed_group_required_count", 0)
        ),
        "first_failed_group_candidate_count": int(
            entry.get("first_failed_group_candidate_count", 0)
        ),
        "first_failed_group_surviving_after_blocked_count": int(
            entry.get("first_failed_group_surviving_after_blocked_count", 0)
        ),
        "first_failed_group_surviving_at_failure_count": int(
            entry.get("first_failed_group_surviving_at_failure_count", 0)
        ),
        "blocked_cell_count": int(entry.get("blocked_cell_count", 0)),
        "blocked_bbox": entry.get("blocked_bbox"),
        "local_repair_attempted": bool(entry.get("local_repair_attempted", False)),
        "local_repair_success": bool(entry.get("local_repair_success", False)),
        "local_repair_attempt_count": int(entry.get("local_repair_attempt_count", 0)),
        **_coordinate_validation_failure_sample_fields(entry),
    }


def _coordinate_validation_failure_sample_fields(entry: Mapping[str, Any]) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    for key in (
        "coordinate_validation_status",
        "coordinate_validation_reason",
        "coordinate_validation_solver_profile_id",
    ):
        if key in entry:
            fields[key] = str(entry.get(key, ""))
    for key in (
        "coordinate_validation_forced_slot_field_count",
        "coordinate_validation_forced_ghost_anchor",
    ):
        if key in entry:
            fields[key] = entry.get(key)
    for key in (
        "capacity_conflict",
        "same_x_strip_capacity_precheck",
        "ghost_overlap_forced_domain_precheck",
        "ghost_y_overlap_precheck",
        "signature_monotonic_precheck",
    ):
        value = entry.get(key)
        if isinstance(value, Mapping):
            fields[key] = dict(value)
    return fields


def _compact_boundary_port_precheck(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "supported": bool(payload.get("supported", False)),
        "skipped_due_to_anchor_limit": bool(
            payload.get("skipped_due_to_anchor_limit", False)
        ),
        "considered_anchor_count": int(payload.get("considered_anchor_count", 0)),
        "screened_infeasible_anchor_count": int(
            payload.get("screened_infeasible_anchor_count", 0)
        ),
        "screen_pass_anchor_count": int(payload.get("screen_pass_anchor_count", 0)),
        "unsupported_anchor_count": int(payload.get("unsupported_anchor_count", 0)),
        "max_packable_min": payload.get("max_packable_min"),
        "max_packable_max": payload.get("max_packable_max"),
        "first_infeasible_anchor_idx": payload.get("first_infeasible_anchor_idx"),
        "screen_pass_anchor_indices": [
            int(idx) for idx in list(payload.get("screen_pass_anchor_indices", []))
        ][:16],
    }


def _compact_mandatory_group_prechecks(raw_payload: Any) -> Dict[str, Any]:
    payload = _mapping(raw_payload)
    return {
        "evaluated": bool(payload.get("evaluated", False)),
        "skipped_due_to_upstream_precheck": bool(
            payload.get("skipped_due_to_upstream_precheck", False)
        ),
        "upstream_anchor_filter_count": int(
            payload.get("upstream_anchor_filter_count", 0)
        ),
        "supported_group_count": int(payload.get("supported_group_count", 0)),
        "groups": [
            {
                "group_id": str(entry.get("group_id", "")),
                "facility_type": str(entry.get("facility_type", "")),
                "operation_type": str(entry.get("operation_type", "")),
                "required_count": int(entry.get("required_count", 0)),
                "supported": bool(entry.get("supported", False)),
                "oracle_mode": str(entry.get("oracle_mode", "unsupported")),
                "screened_infeasible_anchor_count": int(
                    entry.get("screened_infeasible_anchor_count", 0)
                ),
                "screen_pass_anchor_count": int(
                    entry.get("screen_pass_anchor_count", 0)
                ),
                "unsupported_anchor_count": int(
                    entry.get("unsupported_anchor_count", 0)
                ),
            }
            for entry in list(payload.get("groups", []))[:16]
            if isinstance(entry, Mapping)
        ],
    }


def _compact_warm_start(warm_start: Mapping[str, Any]) -> Dict[str, Any]:
    keys = (
        "ghost_anchor_hint_status",
        "ghost_anchor_total_count",
        "ghost_anchor_compatible_count",
        "first_compatible_ghost_anchor_idx",
        "ghost_anchor_compatibility_skipped",
        "warm_start_strategy",
        "ghost_aware_anchor_attempt_count",
        "ghost_aware_anchor_selected_idx",
        "ghost_aware_complete_mandatory_hint",
        "ghost_aware_hint_instances",
        "local_repair_attempted",
        "local_repair_success",
        "local_repair_trigger_reason",
        "local_repair_window_size",
        "local_repair_attempt_count",
        "local_repair_success_count",
        "local_repair_intra_group_attempted_count",
        "local_repair_committed_attempted_count",
        "ghost_aware_pose_order_portfolio_attempted",
        "ghost_aware_pose_order_portfolio_success",
        "ghost_aware_pose_order_portfolio_attempt_count",
        "ghost_aware_pose_order_portfolio_failed_anchor_count",
        "ghost_aware_pose_order_portfolio_failure_reason_counts",
        "ghost_aware_pose_order_portfolio_failure_samples",
        "ghost_aware_pose_order_validation_attempt_count",
        "ghost_aware_pose_order_validation_rejected_count",
        "ghost_aware_pose_order_validation_last_status",
        "ghost_aware_pose_order_validation_last_reason",
        "ghost_aware_pose_order_validation_rejection_samples",
        "ghost_aware_coordinate_validation_attempt_count",
        "ghost_aware_coordinate_validation_rejected_count",
        "ghost_aware_coordinate_validation_last_status",
        "ghost_aware_coordinate_validation_last_reason",
        "ghost_aware_coordinate_validation_rejection_samples",
        "ghost_aware_coordinate_validation_limit_reached",
    )
    return {key: warm_start.get(key) for key in keys}


def _compact_failure_attribution(payload: Mapping[str, Any]) -> Dict[str, Any]:
    keys = (
        "attempted_anchor_count",
        "failed_anchor_count",
        "failure_reason_counts",
        "first_failed_anchor_idx",
        "first_failed_group_id",
        "first_failed_group_template",
        "first_failed_group_position",
        "first_failed_group_required_count",
        "first_failed_group_candidate_count",
        "first_failed_group_surviving_after_blocked_count",
        "first_failed_group_surviving_at_failure_count",
        "top_failed_groups",
        "top_failed_group_failures",
        "failed_anchor_samples",
    )
    return {key: payload.get(key) for key in keys if key in payload}


def _checks(
    status: Mapping[str, Any],
    boundary_port_precheck: Mapping[str, Any],
    failure_attribution: Mapping[str, Any],
) -> list[Dict[str, str]]:
    return [
        _check(
            "boundary_port_precheck_not_skipped",
            "pass"
            if not bool(boundary_port_precheck.get("skipped_due_to_anchor_limit", False))
            else "skipped",
            "boundary port precheck evaluated"
            if not bool(boundary_port_precheck.get("skipped_due_to_anchor_limit", False))
            else "boundary port precheck skipped due to anchor cap",
        ),
        _check(
            "compatible_start_found",
            "pass" if bool(status.get("compatible_start_found", False)) else "fail",
            "at least one ghost anchor can seed a mandatory start"
            if bool(status.get("compatible_start_found", False))
            else "no compatible ghost anchor start found",
        ),
        _check(
            "start_failure_attribution_present",
            "pass" if int(failure_attribution.get("failed_anchor_count", 0)) > 0 else "skipped",
            "start failure attribution was captured"
            if int(failure_attribution.get("failed_anchor_count", 0)) > 0
            else "no failed anchor attribution was captured",
        ),
    ]


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": check_id, "status": status, "detail": detail}


def _parse_candidate(candidate: str) -> Tuple[int, int]:
    try:
        raw_w, raw_h = str(candidate).lower().split("x", 1)
        ghost_w = int(raw_w)
        ghost_h = int(raw_h)
    except Exception:
        raise ValueError(f"Unsupported candidate key: {candidate!r}; expected WxH") from None
    if ghost_w <= 0 or ghost_h <= 0:
        raise ValueError(f"Unsupported candidate key: {candidate!r}; dimensions must be positive")
    return ghost_w, ghost_h


def _resolved_cap(env_name: str, default: int, explicit_value: Optional[int]) -> int:
    if explicit_value is not None:
        return max(0, int(explicit_value))
    raw_value = os.environ.get(env_name)
    if raw_value is None or str(raw_value).strip() == "":
        return max(0, int(default))
    try:
        return max(0, int(str(raw_value).strip()))
    except ValueError:
        return max(0, int(default))


@contextmanager
def _temporary_env_caps(caps: Mapping[str, Optional[int]]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in caps}
    try:
        for key, value in caps.items():
            if value is not None:
                os.environ[str(key)] = str(max(0, int(value)))
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _probe_failure_summary(entry: Mapping[str, Any]) -> str:
    if bool(entry.get("success", False)):
        return "success"
    reasons = [
        item
        for item in list(entry.get("top_failed_attempt_reasons", []))
        if isinstance(item, Mapping)
    ]
    if not reasons:
        if entry.get("skip_reason"):
            return str(entry.get("skip_reason"))
        if entry.get("failure_reason"):
            return str(entry.get("failure_reason"))
        return ""
    first = reasons[0]
    return (
        f"{first.get('group_id')}/"
        f"{first.get('facility_type')}:"
        f"{first.get('failure_reason')}x"
        f"{first.get('count')}"
    )
