from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Mapping, Optional, Sequence, Tuple

from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS,
    EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV,
    EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS,
    EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV,
    MasterPlacementModel,
)
from src.search.benders_loop import (
    _PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS,
    _PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS_ENV,
    _PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS,
    _PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS_ENV,
    _PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS,
    _PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV,
    _compact_coordinate_validation_precheck,
    _compact_exact_candidate_boundary_port_feasibility,
    _compact_exact_candidate_mandatory_group_prechecks,
    _compact_exact_candidate_mandatory_support_diagnostics,
    _evaluate_coordinate_validation_forced_anchor_precheck,
    _pre_master_coordinate_validation_precheck_max_anchors,
    _pre_master_coordinate_validation_precheck_seconds,
    _pre_master_mandatory_rectangle_precheck_max_anchors,
    _triggered_mandatory_rectangle_precheck_group,
    create_exact_search_session,
    evaluate_exact_candidate_pre_master_precheck,
)
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso

PRE_MASTER_PROFILE_SOURCE = "phase3b_pre_master_precheck_profiler_v1"
PRE_MASTER_EMPTY_HINT_ANCHOR_SCAN_SOURCE = (
    "phase3b_pre_master_empty_hint_anchor_scan_v1"
)
DEFAULT_CANDIDATE = "69x19"

ProgressCallback = Callable[[Mapping[str, Any]], None]


def build_phase3b_pre_master_precheck_profile(
    project_root: Path,
    *,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    boundary_port_precheck_max_anchors: Optional[int] = None,
    mandatory_rectangle_precheck_max_anchors: Optional[int] = None,
    pre_master_mandatory_rectangle_precheck_max_anchors: Optional[int] = None,
    coordinate_validation_precheck_max_anchors: Optional[int] = None,
    coordinate_validation_precheck_seconds: Optional[float] = None,
    include_mandatory_rectangle_precheck: bool = True,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    ghost_w, ghost_h = _parse_candidate(candidate)
    caps = {
        EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV: boundary_port_precheck_max_anchors,
        EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV: mandatory_rectangle_precheck_max_anchors,
        _PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV: (
            pre_master_mandatory_rectangle_precheck_max_anchors
        ),
        _PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS_ENV: (
            coordinate_validation_precheck_max_anchors
        ),
        _PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS_ENV: (
            coordinate_validation_precheck_seconds
        ),
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
        "pre_master_mandatory_rectangle_precheck_max_anchors": _resolved_cap(
            _PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV,
            _PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS,
            pre_master_mandatory_rectangle_precheck_max_anchors,
        ),
        "coordinate_validation_precheck_max_anchors": _resolved_cap(
            _PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS_ENV,
            _PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS,
            coordinate_validation_precheck_max_anchors,
        ),
        "coordinate_validation_precheck_seconds": _resolved_float(
            _PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS_ENV,
            _PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS,
            coordinate_validation_precheck_seconds,
        ),
    }
    started = time.perf_counter()
    profile: Dict[str, Any] = {
        "metadata": {
            "source": PRE_MASTER_PROFILE_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
        },
        "candidate": {
            "key": f"{ghost_w}x{ghost_h}",
            "ghost_rect": {
                "w": int(ghost_w),
                "h": int(ghost_h),
                "area": int(ghost_w * ghost_h),
            },
            "objective": {
                "area": int(ghost_w * ghost_h),
                "min_side": int(min(ghost_w, ghost_h)),
            },
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "include_mandatory_rectangle_precheck": bool(
                include_mandatory_rectangle_precheck
            ),
            "precheck_caps": dict(resolved_caps),
        },
        "artifact_hashes": {},
        "artifact_hash_error": None,
        "status": {
            "completed": False,
            "running_stage": None,
            "outcome": "running",
            "triggered": False,
            "precheck_reason": None,
            "recommendation": "Profiler is running.",
        },
        "stages": {},
        "checks": [],
    }

    def publish() -> None:
        if progress_callback is not None:
            progress_callback(profile)

    def start_stage(stage_id: str, detail: Optional[Mapping[str, Any]] = None) -> float:
        profile["status"]["running_stage"] = str(stage_id)
        profile["stages"][stage_id] = {
            "status": "running",
            "started_at": now_iso(),
            **dict(detail or {}),
        }
        publish()
        return time.perf_counter()

    def finish_stage(
        stage_id: str,
        stage_started: float,
        *,
        status: str = "complete",
        payload: Optional[Mapping[str, Any]] = None,
    ) -> None:
        entry = dict(profile["stages"].get(stage_id, {}))
        entry.update(dict(payload or {}))
        entry["status"] = str(status)
        entry["elapsed_seconds"] = float(time.perf_counter() - stage_started)
        entry["finished_at"] = now_iso()
        profile["stages"][stage_id] = entry
        profile["status"]["running_stage"] = None
        publish()

    with _temporary_env_caps(caps):
        hash_stage_started = start_stage("artifact_hashes")
        try:
            profile["artifact_hashes"] = compute_exact_artifact_hashes(project_root)
            finish_stage(
                "artifact_hashes",
                hash_stage_started,
                payload={"hash_count": len(profile["artifact_hashes"])},
            )
        except Exception as exc:
            profile["artifact_hash_error"] = f"{type(exc).__name__}: {exc}"
            finish_stage(
                "artifact_hashes",
                hash_stage_started,
                status="error",
                payload={"error": profile["artifact_hash_error"]},
            )

        session_started = start_stage("session_build")
        exact_session = create_exact_search_session(
            project_root,
            solve_mode="certified_exact",
            master_search_profile=master_search_profile,
        )
        finish_stage(
            "session_build",
            session_started,
            payload={
                "core_build_seconds": float(exact_session.core_build_seconds),
                "master_search_profile": str(exact_session.master_search_profile),
            },
        )

        support_started = start_stage("mandatory_support_diagnostics")
        candidate_precheck_artifacts = dict(
            getattr(exact_session.core, "candidate_precheck_artifacts", {})
        )
        mandatory_support_diagnostics = dict(
            candidate_precheck_artifacts.get(
                "mandatory_support_diagnostics",
                exact_session.core.build_stats.get(
                    "exact_candidate_mandatory_support_diagnostics",
                    {},
                ),
            )
        )
        support_summary = _compact_exact_candidate_mandatory_support_diagnostics(
            mandatory_support_diagnostics
        )
        finish_stage(
            "mandatory_support_diagnostics",
            support_started,
            payload={
                "summary": support_summary,
                "group_count": len(list(support_summary.get("groups", []))),
                "empty_candidate_pool_group_count": int(
                    support_summary.get("empty_candidate_pool_group_count", 0)
                ),
                "unsupported_group_count": int(
                    support_summary.get("unsupported_group_count", 0)
                ),
            },
        )

        boundary_started = start_stage("boundary_port_precheck")
        precheck_outcome = evaluate_exact_candidate_pre_master_precheck(
            ghost_w=int(ghost_w),
            ghost_h=int(ghost_h),
            exact_session=exact_session,
            master_search_profile=master_search_profile,
            include_mandatory_rectangle_precheck=False,
        )
        boundary_payload = dict(precheck_outcome.get("boundary_port_precheck", {}))
        boundary_summary = _compact_exact_candidate_boundary_port_feasibility(
            boundary_payload
        )
        boundary_triggered = bool(precheck_outcome.get("triggered", False))
        precheck_reason = _precheck_reason(precheck_outcome)
        finish_stage(
            "boundary_port_precheck",
            boundary_started,
            payload={
                "summary": boundary_summary,
                "triggered": bool(boundary_triggered),
                "precheck_reason": precheck_reason,
                "screen_pass_anchor_indices_count": len(
                    list(boundary_payload.get("screen_pass_anchor_indices", ()))
                ),
                "rebuild_anchor_indices_count": len(
                    list(boundary_payload.get("rebuild_anchor_indices", ()))
                ),
                "skipped_due_to_anchor_limit": bool(
                    boundary_payload.get("skipped_due_to_anchor_limit", False)
                ),
            },
        )
        if boundary_triggered:
            _finalize_profile(
                profile,
                started=started,
                outcome="pre_master_boundary_eliminated",
                triggered=True,
                precheck_reason=precheck_reason,
                recommendation="Boundary-port precheck already eliminates this candidate.",
            )
            publish()
            return profile

        mandatory_stage_detail = {
            "enabled": bool(include_mandatory_rectangle_precheck),
            "pre_master_anchor_cap": int(
                _pre_master_mandatory_rectangle_precheck_max_anchors()
            ),
        }
        mandatory_started = start_stage(
            "mandatory_rectangle_precheck",
            mandatory_stage_detail,
        )
        boundary_pass_anchor_indices = tuple(
            int(idx) for idx in boundary_payload.get("screen_pass_anchor_indices", ())
        )
        model: Optional[MasterPlacementModel] = None
        overlay_elapsed = 0.0
        mandatory_payload: Optional[Dict[str, Any]] = None
        if not bool(include_mandatory_rectangle_precheck):
            finish_stage(
                "mandatory_rectangle_precheck",
                mandatory_started,
                status="skipped",
                payload={
                    **mandatory_stage_detail,
                    "skip_reason": "disabled",
                    "anchor_count": len(boundary_pass_anchor_indices),
                },
            )
        elif not bool(boundary_payload.get("supported", False)):
            finish_stage(
                "mandatory_rectangle_precheck",
                mandatory_started,
                status="skipped",
                payload={
                    **mandatory_stage_detail,
                    "skip_reason": "boundary_precheck_not_supported",
                    "anchor_count": len(boundary_pass_anchor_indices),
                },
            )
        elif not boundary_pass_anchor_indices:
            finish_stage(
                "mandatory_rectangle_precheck",
                mandatory_started,
                status="skipped",
                payload={
                    **mandatory_stage_detail,
                    "skip_reason": "no_boundary_pass_anchors",
                    "anchor_count": 0,
                },
            )
        elif len(boundary_pass_anchor_indices) > int(
            mandatory_stage_detail["pre_master_anchor_cap"]
        ):
            finish_stage(
                "mandatory_rectangle_precheck",
                mandatory_started,
                status="skipped",
                payload={
                    **mandatory_stage_detail,
                    "skip_reason": "pre_master_anchor_cap_exceeded",
                    "anchor_count": len(boundary_pass_anchor_indices),
                },
            )
        else:
            overlay_started = time.perf_counter()
            model = MasterPlacementModel.from_exact_core(
                exact_session.core,
                ghost_rect=(int(ghost_w), int(ghost_h)),
                master_search_profile=master_search_profile,
                precomputed_boundary_port_feasibility=boundary_payload,
            )
            overlay_elapsed = time.perf_counter() - overlay_started
            mandatory_payload = model.evaluate_exact_candidate_mandatory_rectangle_prechecks(
                anchor_indices=boundary_pass_anchor_indices
            )
            mandatory_summary = _compact_exact_candidate_mandatory_group_prechecks(
                mandatory_payload
            )
            triggered_group = _triggered_mandatory_rectangle_precheck_group(
                mandatory_payload
            )
            finish_stage(
                "mandatory_rectangle_precheck",
                mandatory_started,
                payload={
                    **mandatory_stage_detail,
                    "anchor_count": len(boundary_pass_anchor_indices),
                    "overlay_build_seconds": float(overlay_elapsed),
                    "summary": mandatory_summary,
                    "triggered": triggered_group is not None,
                    "triggered_group": triggered_group,
                },
            )
            if triggered_group is not None:
                _finalize_profile(
                    profile,
                    started=started,
                    outcome="pre_master_mandatory_rectangle_eliminated",
                    triggered=True,
                    precheck_reason="mandatory_rect_group_all_anchors_infeasible",
                    recommendation=(
                        "Mandatory-rectangle precheck eliminates this candidate "
                        "within the bounded pre-master cap."
                    ),
                )
                publish()
                return profile

        coordinate_stage_detail = {
            "enabled": bool(include_mandatory_rectangle_precheck),
            "max_anchor_count": int(
                _pre_master_coordinate_validation_precheck_max_anchors()
            ),
            "time_limit_seconds": float(
                _pre_master_coordinate_validation_precheck_seconds()
            ),
        }
        coordinate_started = start_stage(
            "coordinate_validation_precheck",
            coordinate_stage_detail,
        )
        coordinate_anchor_indices: Tuple[int, ...] = tuple()
        if isinstance(mandatory_payload, Mapping) and bool(
            mandatory_payload.get("evaluated", False)
        ):
            coordinate_anchor_indices = tuple(
                int(idx)
                for idx in mandatory_payload.get("rebuild_anchor_indices", ())
            )
        if not coordinate_anchor_indices and boundary_pass_anchor_indices:
            coordinate_anchor_indices = tuple(int(idx) for idx in boundary_pass_anchor_indices)
        coordinate_cap = int(coordinate_stage_detail["max_anchor_count"])
        coordinate_seconds = float(coordinate_stage_detail["time_limit_seconds"])
        coordinate_anchor_source = (
            "mandatory_rectangle_rebuild"
            if coordinate_anchor_indices
            and isinstance(mandatory_payload, Mapping)
            and bool(mandatory_payload.get("evaluated", False))
            else "boundary_pass"
            if coordinate_anchor_indices
            else "none"
        )
        if (
            not coordinate_anchor_indices
            and not bool(boundary_payload.get("supported", False))
            and coordinate_cap > 0
            and coordinate_seconds > 0.0
        ):
            if model is None:
                overlay_started = time.perf_counter()
                model = MasterPlacementModel.from_exact_core(
                    exact_session.core,
                    ghost_rect=(int(ghost_w), int(ghost_h)),
                    master_search_profile=master_search_profile,
                    precomputed_boundary_port_feasibility=boundary_payload,
                )
                overlay_elapsed = time.perf_counter() - overlay_started
            coordinate_anchor_indices = tuple(
                range(len(list(getattr(model, "_ghost_domains", []))))
            )
            coordinate_anchor_source = "ghost_domains_boundary_unsupported"
        if not bool(include_mandatory_rectangle_precheck):
            finish_stage(
                "coordinate_validation_precheck",
                coordinate_started,
                status="skipped",
                payload={
                    **coordinate_stage_detail,
                    "skip_reason": "mandatory_rectangle_precheck_disabled",
                    "anchor_count": len(coordinate_anchor_indices),
                    "anchor_source": coordinate_anchor_source,
                },
            )
        elif coordinate_cap <= 0 or coordinate_seconds <= 0.0:
            finish_stage(
                "coordinate_validation_precheck",
                coordinate_started,
                status="skipped",
                payload={
                    **coordinate_stage_detail,
                    "skip_reason": "disabled",
                    "anchor_count": len(coordinate_anchor_indices),
                    "anchor_source": coordinate_anchor_source,
                },
            )
        elif not coordinate_anchor_indices:
            finish_stage(
                "coordinate_validation_precheck",
                coordinate_started,
                status="skipped",
                payload={
                    **coordinate_stage_detail,
                    "skip_reason": "empty_anchor_set",
                    "anchor_count": 0,
                    "anchor_source": coordinate_anchor_source,
                },
            )
        elif len(coordinate_anchor_indices) > coordinate_cap:
            finish_stage(
                "coordinate_validation_precheck",
                coordinate_started,
                status="skipped",
                payload={
                    **coordinate_stage_detail,
                    "skip_reason": "anchor_limit_exceeded",
                    "anchor_count": len(coordinate_anchor_indices),
                    "anchor_source": coordinate_anchor_source,
                },
            )
        else:
            if model is None:
                overlay_started = time.perf_counter()
                model = MasterPlacementModel.from_exact_core(
                    exact_session.core,
                    ghost_rect=(int(ghost_w), int(ghost_h)),
                    master_search_profile=master_search_profile,
                    precomputed_boundary_port_feasibility=boundary_payload,
                )
                overlay_elapsed = time.perf_counter() - overlay_started
            coordinate_payload = _evaluate_coordinate_validation_forced_anchor_precheck(
                model,
                anchor_indices=coordinate_anchor_indices,
                time_limit_seconds=coordinate_seconds,
                max_anchor_count=coordinate_cap,
            )
            coordinate_summary = _compact_coordinate_validation_precheck(
                coordinate_payload
            )
            finish_stage(
                "coordinate_validation_precheck",
                coordinate_started,
                payload={
                    **coordinate_stage_detail,
                    "anchor_count": len(coordinate_anchor_indices),
                    "anchor_source": coordinate_anchor_source,
                    "overlay_build_seconds": float(overlay_elapsed),
                    "summary": coordinate_summary,
                    "triggered": bool(coordinate_payload.get("triggered", False)),
                    "short_circuited_after_non_triggering_anchor": bool(
                        coordinate_payload.get(
                            "short_circuited_after_non_triggering_anchor",
                            False,
                        )
                    ),
                },
            )
            if bool(coordinate_payload.get("triggered", False)):
                _finalize_profile(
                    profile,
                    started=started,
                    outcome="pre_master_coordinate_validation_eliminated",
                    triggered=True,
                    precheck_reason="coordinate_validation_infeasible",
                    recommendation=(
                        "Coordinate-validation precheck eliminates this candidate "
                        "within the bounded pre-master cap."
                    ),
                )
                publish()
                return profile

    _finalize_profile(
        profile,
        started=started,
        outcome="not_eliminated_by_bounded_pre_master",
        triggered=False,
        precheck_reason=None,
        recommendation=(
            "Bounded pre-master profiling did not eliminate this candidate; inspect "
            "stage timings and caps before increasing B5A budgets."
        ),
    )
    publish()
    return profile


def build_phase3b_pre_master_empty_hint_anchor_scan(
    project_root: Path,
    *,
    candidate: str = DEFAULT_CANDIDATE,
    anchor_indices: Sequence[int],
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 2.0,
    exhaustive: bool = False,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """Run a bounded empty-hint coordinate validation scan without proof promotion."""

    project_root = Path(project_root).resolve()
    ghost_w, ghost_h = _parse_candidate(candidate)
    normalized_anchor_indices = _normalize_anchor_indices(anchor_indices)
    started = time.perf_counter()
    scan: Dict[str, Any] = {
        "metadata": {
            "source": PRE_MASTER_EMPTY_HINT_ANCHOR_SCAN_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "Bounded empty-hint coordinate-validation scan. Non-exhaustive scans "
                "are diagnostic only and cannot eliminate a candidate."
            ),
        },
        "paths": {
            "project_root": str(project_root),
        },
        "candidate": {
            "key": f"{ghost_w}x{ghost_h}",
            "ghost_rect": {
                "w": int(ghost_w),
                "h": int(ghost_h),
                "area": int(ghost_w * ghost_h),
            },
            "objective": {
                "area": int(ghost_w * ghost_h),
                "min_side": int(min(ghost_w, ghost_h)),
            },
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "solution_hint_mode": "empty",
            "time_limit_seconds": float(max(0.0, time_limit_seconds)),
            "requested_anchor_indices": list(normalized_anchor_indices),
            "requested_anchor_count": int(len(normalized_anchor_indices)),
            "exhaustive_requested": bool(exhaustive),
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "artifact_hashes": {},
        "artifact_hash_error": None,
        "session": {},
        "scan": {
            "anchor_source": "explicit_anchor_indices",
            "total_ghost_anchor_count": None,
            "anchor_indices": list(normalized_anchor_indices),
            "anchor_count": int(len(normalized_anchor_indices)),
            "evaluated_anchor_count": 0,
            "status_counts": {},
            "anchors": [],
            "invalid_anchor_indices": [],
            "candidate_elimination_claim": False,
            "candidate_elimination_claim_reason": "not_evaluated",
        },
        "status": {
            "completed": False,
            "outcome": "running",
            "running_stage": "artifact_hashes",
            "recommendation": "Empty-hint anchor scan is running.",
        },
        "checks": [],
    }

    def publish() -> None:
        if progress_callback is not None:
            progress_callback(scan)

    publish()
    try:
        scan["artifact_hashes"] = compute_exact_artifact_hashes(project_root)
    except Exception as exc:
        scan["artifact_hash_error"] = f"{type(exc).__name__}: {exc}"

    scan["status"]["running_stage"] = "session_build"
    publish()
    exact_session = create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
        master_search_profile=master_search_profile,
    )
    scan["session"] = {
        "core_build_seconds": float(exact_session.core_build_seconds),
        "master_search_profile": str(exact_session.master_search_profile),
    }

    scan["status"]["running_stage"] = "overlay_build"
    publish()
    overlay_started = time.perf_counter()
    model = MasterPlacementModel.from_exact_core(
        exact_session.core,
        ghost_rect=(int(ghost_w), int(ghost_h)),
        master_search_profile=master_search_profile,
    )
    overlay_elapsed = time.perf_counter() - overlay_started
    total_ghost_anchor_count = len(list(getattr(model, "_ghost_domains", [])))
    scan["scan"]["total_ghost_anchor_count"] = int(total_ghost_anchor_count)
    scan["scan"]["overlay_build_seconds"] = float(overlay_elapsed)

    invalid_anchor_indices = [
        int(anchor_idx)
        for anchor_idx in normalized_anchor_indices
        if int(anchor_idx) < 0 or int(anchor_idx) >= int(total_ghost_anchor_count)
    ]
    scan["scan"]["invalid_anchor_indices"] = invalid_anchor_indices
    if invalid_anchor_indices:
        scan["status"] = {
            "completed": True,
            "outcome": "invalid_anchor_indices",
            "running_stage": None,
            "recommendation": (
                "Fix the requested anchor list before interpreting this scan."
            ),
        }
        scan["timing"] = {"total_seconds": float(time.perf_counter() - started)}
        scan["checks"] = _empty_hint_scan_checks(scan)
        publish()
        return scan

    if not normalized_anchor_indices:
        scan["scan"]["candidate_elimination_claim_reason"] = "empty_anchor_set"
        scan["status"] = {
            "completed": True,
            "outcome": "empty_anchor_set",
            "running_stage": None,
            "recommendation": "No anchors were requested for the empty-hint scan.",
        }
        scan["timing"] = {"total_seconds": float(time.perf_counter() - started)}
        scan["checks"] = _empty_hint_scan_checks(scan)
        publish()
        return scan

    if float(time_limit_seconds) <= 0.0:
        scan["scan"]["candidate_elimination_claim_reason"] = "disabled_time_limit"
        scan["status"] = {
            "completed": True,
            "outcome": "disabled_time_limit",
            "running_stage": None,
            "recommendation": (
                "Use a positive coordinate-validation scan time budget before "
                "interpreting anchor statuses."
            ),
        }
        scan["timing"] = {"total_seconds": float(time.perf_counter() - started)}
        scan["checks"] = _empty_hint_scan_checks(scan)
        publish()
        return scan

    status_counts: Dict[str, int] = {}
    scan["status"]["running_stage"] = "anchor_scan"
    publish()
    for anchor_idx in normalized_anchor_indices:
        validation = model._validate_coordinate_forced_hint(
            solution_hint={},
            ghost_anchor_hint_idx=int(anchor_idx),
            time_limit_seconds=float(time_limit_seconds),
            require_complete=False,
        )
        entry = _empty_hint_anchor_scan_entry(
            int(anchor_idx),
            validation if isinstance(validation, Mapping) else {},
        )
        status = str(entry.get("status", ""))
        status_counts[status] = int(status_counts.get(status, 0)) + 1
        scan["scan"]["anchors"].append(entry)
        scan["scan"]["evaluated_anchor_count"] = int(
            scan["scan"].get("evaluated_anchor_count", 0)
        ) + 1
        scan["scan"]["status_counts"] = dict(sorted(status_counts.items()))
        publish()

    all_requested_anchors = set(normalized_anchor_indices) == set(
        range(int(total_ghost_anchor_count))
    )
    all_infeasible = bool(normalized_anchor_indices) and all(
        str(entry.get("status")) == "INFEASIBLE"
        for entry in list(scan["scan"].get("anchors", []))
    )
    if bool(exhaustive) and all_requested_anchors and all_infeasible:
        claim_reason = "all_anchors_infeasible_but_scan_keeps_proof_source_false"
    elif not bool(exhaustive):
        claim_reason = "non_exhaustive_scan"
    elif not all_requested_anchors:
        claim_reason = "requested_anchors_do_not_cover_all_ghost_domains"
    else:
        claim_reason = "non_infeasible_anchor_present"
    scan["scan"]["candidate_elimination_claim"] = False
    scan["scan"]["candidate_elimination_claim_reason"] = claim_reason
    scan["profile"]["candidate_elimination_claim"] = False
    scan["status"] = {
        "completed": True,
        "outcome": "empty_hint_anchor_scan_completed",
        "running_stage": None,
        "recommendation": (
            "Use this as bounded diagnostic evidence only. Do not promote it to "
            "campaign proof or final long-run readiness."
        ),
    }
    scan["timing"] = {"total_seconds": float(time.perf_counter() - started)}
    scan["checks"] = _empty_hint_scan_checks(scan)
    publish()
    return scan


def render_phase3b_pre_master_empty_hint_anchor_scan_markdown(
    scan: Mapping[str, Any],
) -> str:
    candidate = _mapping(scan.get("candidate"))
    status = _mapping(scan.get("status"))
    profile = _mapping(scan.get("profile"))
    scan_payload = _mapping(scan.get("scan"))
    lines = [
        "# Phase 3B Empty-Hint Anchor Scan",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Completed: {bool(status.get('completed', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Solution hint mode: {profile.get('solution_hint_mode')}",
        f"- Proof source: {profile.get('proof_source')}",
        f"- Candidate elimination claim: {scan_payload.get('candidate_elimination_claim')}",
        f"- Claim reason: {scan_payload.get('candidate_elimination_claim_reason')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Anchor source | {_markdown_cell(scan_payload.get('anchor_source'))} |",
        f"| Total ghost anchors | {_markdown_cell(scan_payload.get('total_ghost_anchor_count'))} |",
        f"| Requested anchors | {_markdown_cell(scan_payload.get('anchor_indices'))} |",
        f"| Evaluated anchors | {_markdown_cell(scan_payload.get('evaluated_anchor_count'))} |",
        f"| Status counts | {_markdown_cell(scan_payload.get('status_counts'))} |",
        "",
        "## Anchors",
        "",
        "| Anchor | Status | Reason | Fields | Solver | Branches | Conflicts | DTime | Wall |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for entry in list(scan_payload.get("anchors", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("anchor_idx")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("reason")),
                    _markdown_cell(entry.get("forced_slot_field_count")),
                    _markdown_cell(entry.get("attempted_solver")),
                    _markdown_cell(entry.get("branches")),
                    _markdown_cell(entry.get("conflicts")),
                    _markdown_cell(_seconds_text(entry.get("deterministic_time"))),
                    _markdown_cell(_seconds_text(entry.get("wall_time"))),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(scan.get("checks", [])):
        if not isinstance(check, Mapping):
            continue
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


def render_phase3b_pre_master_empty_hint_anchor_scan_text(
    scan: Mapping[str, Any],
) -> str:
    candidate = _mapping(scan.get("candidate"))
    status = _mapping(scan.get("status"))
    profile = _mapping(scan.get("profile"))
    scan_payload = _mapping(scan.get("scan"))
    lines = [
        "Phase 3B empty-hint anchor scan",
        f"candidate={candidate.get('key')}",
        f"completed={bool(status.get('completed', False))}",
        f"outcome={status.get('outcome')}",
        f"solution_hint_mode={profile.get('solution_hint_mode')}",
        f"proof_source={profile.get('proof_source')}",
        f"candidate_elimination_claim={scan_payload.get('candidate_elimination_claim')}",
        f"candidate_elimination_claim_reason={scan_payload.get('candidate_elimination_claim_reason')}",
        f"status_counts={scan_payload.get('status_counts')}",
    ]
    for entry in list(scan_payload.get("anchors", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "anchor "
                f"idx={entry.get('anchor_idx')} "
                f"status={entry.get('status')} "
                f"reason={entry.get('reason')} "
                f"fields={entry.get('forced_slot_field_count')} "
                f"solver={entry.get('attempted_solver')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')} "
                f"deterministic_time={_seconds_text(entry.get('deterministic_time'))} "
                f"wall_time={_seconds_text(entry.get('wall_time'))}"
            )
    for check in list(scan.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_pre_master_profile_markdown(profile: Mapping[str, Any]) -> str:
    candidate = _mapping(profile.get("candidate"))
    status = _mapping(profile.get("status"))
    lines = [
        "# Phase 3B Pre-Master Precheck Profile",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Completed: {bool(status.get('completed', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Precheck reason: {status.get('precheck_reason')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Stages",
        "",
        "| Stage | Status | Seconds | Key detail |",
        "| --- | --- | --- | --- |",
    ]
    for stage_id, stage in _ordered_stages(profile).items():
        if not isinstance(stage, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(stage_id),
                    _markdown_cell(stage.get("status")),
                    _markdown_cell(_seconds_text(stage.get("elapsed_seconds"))),
                    _markdown_cell(_stage_detail(stage_id, stage)),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(profile.get("checks", [])):
        if not isinstance(check, Mapping):
            continue
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


def render_phase3b_pre_master_profile_text(profile: Mapping[str, Any]) -> str:
    candidate = _mapping(profile.get("candidate"))
    status = _mapping(profile.get("status"))
    lines = [
        "Phase 3B pre-master precheck profile",
        f"candidate={candidate.get('key')}",
        f"completed={bool(status.get('completed', False))}",
        f"outcome={status.get('outcome')}",
        f"precheck_reason={status.get('precheck_reason')}",
        f"recommendation={status.get('recommendation')}",
    ]
    for stage_id, stage in _ordered_stages(profile).items():
        if isinstance(stage, Mapping):
            lines.append(
                "stage "
                f"id={stage_id} "
                f"status={stage.get('status')} "
                f"seconds={_seconds_text(stage.get('elapsed_seconds'))} "
                f"detail={_stage_detail(stage_id, stage)}"
            )
    for check in list(profile.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _normalize_anchor_indices(anchor_indices: Sequence[int]) -> Tuple[int, ...]:
    normalized: list[int] = []
    seen: set[int] = set()
    for raw_anchor_idx in anchor_indices:
        anchor_idx = int(raw_anchor_idx)
        if anchor_idx in seen:
            continue
        seen.add(anchor_idx)
        normalized.append(anchor_idx)
    return tuple(normalized)


def _empty_hint_anchor_scan_entry(
    anchor_idx: int,
    validation: Mapping[str, Any],
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "anchor_idx": int(anchor_idx),
        "status": str(validation.get("status", "")),
        "accepted": bool(validation.get("accepted", False)),
        "reason": validation.get("reason"),
        "forced_slot_field_count": int(validation.get("forced_slot_field_count", 0)),
        "forced_ghost_anchor": bool(validation.get("forced_ghost_anchor", False)),
        "attempted": bool(validation.get("attempted", False)),
        "attempted_solver": bool(validation.get("attempted_solver", False)),
        "wall_time": float(validation.get("wall_time", 0.0)),
        "user_time": float(validation.get("user_time", 0.0)),
        "deterministic_time": float(validation.get("deterministic_time", 0.0)),
        "branches": int(validation.get("branches", 0)),
        "conflicts": int(validation.get("conflicts", 0)),
        "binary_propagations": int(validation.get("binary_propagations", 0)),
        "integer_propagations": int(validation.get("integer_propagations", 0)),
    }
    if "solver_parameters" in validation:
        entry["solver_parameters"] = dict(_mapping(validation.get("solver_parameters")))
    if validation.get("capacity_conflict") is not None:
        entry["capacity_conflict"] = dict(_mapping(validation.get("capacity_conflict")))
    if validation.get("signature_monotonic_conflict") is not None:
        entry["signature_monotonic_conflict"] = dict(
            _mapping(validation.get("signature_monotonic_conflict"))
        )
    return entry


def _empty_hint_scan_checks(scan: Mapping[str, Any]) -> list[Dict[str, str]]:
    status = _mapping(scan.get("status"))
    profile = _mapping(scan.get("profile"))
    scan_payload = _mapping(scan.get("scan"))
    invalid_anchor_indices = list(scan_payload.get("invalid_anchor_indices", []))
    checks = [
        _check(
            "scan_completed",
            "pass" if bool(status.get("completed", False)) else "fail",
            str(status.get("outcome")),
        ),
        _check(
            "empty_solution_hint_mode",
            "pass" if profile.get("solution_hint_mode") == "empty" else "fail",
            str(profile.get("solution_hint_mode")),
        ),
        _check(
            "proof_source_false",
            "pass" if profile.get("proof_source") is False else "fail",
            str(profile.get("proof_source")),
        ),
        _check(
            "candidate_elimination_claim_false",
            "pass"
            if scan_payload.get("candidate_elimination_claim") is False
            else "fail",
            str(scan_payload.get("candidate_elimination_claim_reason")),
        ),
        _check(
            "anchor_indices_valid",
            "pass" if not invalid_anchor_indices else "fail",
            (
                "all requested anchors are within ghost domain range"
                if not invalid_anchor_indices
                else f"invalid anchors: {invalid_anchor_indices}"
            ),
        ),
    ]
    return checks


def _finalize_profile(
    profile: Dict[str, Any],
    *,
    started: float,
    outcome: str,
    triggered: bool,
    precheck_reason: Optional[str],
    recommendation: str,
) -> None:
    profile["status"] = {
        "completed": True,
        "running_stage": None,
        "outcome": str(outcome),
        "triggered": bool(triggered),
        "precheck_reason": precheck_reason,
        "recommendation": str(recommendation),
    }
    profile["timing"] = {"total_seconds": float(time.perf_counter() - started)}
    profile["checks"] = _checks(profile)


def _checks(profile: Mapping[str, Any]) -> list[Dict[str, str]]:
    stages = _mapping(profile.get("stages"))
    status = _mapping(profile.get("status"))
    boundary = _mapping(stages.get("boundary_port_precheck"))
    mandatory = _mapping(stages.get("mandatory_rectangle_precheck"))
    coordinate = _mapping(stages.get("coordinate_validation_precheck"))
    checks = [
        _check(
            "profile_completed",
            "pass" if bool(status.get("completed", False)) else "fail",
            str(status.get("outcome")),
        ),
        _check(
            "boundary_profile_present",
            "pass" if boundary else "fail",
            "boundary stage recorded" if boundary else "boundary stage missing",
        ),
    ]
    if mandatory:
        checks.append(
            _check(
                "mandatory_rectangle_profile_present",
                "pass",
                str(mandatory.get("status")),
            )
        )
    if coordinate:
        checks.append(
            _check(
                "coordinate_validation_profile_present",
                "pass",
                str(coordinate.get("status")),
            )
        )
    return checks


def _precheck_reason(outcome: Mapping[str, Any]) -> Optional[str]:
    proof_summary = _mapping(outcome.get("proof_summary"))
    master_candidate_precheck = _mapping(proof_summary.get("master_candidate_precheck"))
    reason = master_candidate_precheck.get("precheck_reason")
    return None if reason is None else str(reason)


def _parse_candidate(candidate: str) -> Tuple[int, int]:
    raw = str(candidate).lower().strip()
    if "x" not in raw:
        raise ValueError(f"Unsupported candidate {candidate!r}; expected <w>x<h>.")
    w_text, h_text = raw.split("x", 1)
    ghost_w = int(w_text)
    ghost_h = int(h_text)
    if ghost_w <= 0 or ghost_h <= 0:
        raise ValueError(f"Unsupported candidate {candidate!r}; dimensions must be positive.")
    return ghost_w, ghost_h


@contextmanager
def _temporary_env_caps(caps: Mapping[str, Optional[int | float]]) -> Iterator[None]:
    previous: Dict[str, Optional[str]] = {}
    try:
        for key, value in caps.items():
            previous[str(key)] = os.environ.get(str(key))
            if value is None:
                continue
            os.environ[str(key)] = str(value)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(str(key), None)
            else:
                os.environ[str(key)] = value


def _resolved_cap(env_name: str, default: int, override: Optional[int]) -> int:
    if override is not None:
        return max(0, int(override))
    raw_value = os.environ.get(env_name)
    if raw_value is None or str(raw_value).strip() == "":
        return max(0, int(default))
    return max(0, int(str(raw_value).strip()))


def _resolved_float(env_name: str, default: float, override: Optional[float]) -> float:
    if override is not None:
        return max(0.0, float(override))
    raw_value = os.environ.get(env_name)
    if raw_value is None or str(raw_value).strip() == "":
        return max(0.0, float(default))
    return max(0.0, float(str(raw_value).strip()))


def _ordered_stages(profile: Mapping[str, Any]) -> Dict[str, Any]:
    stages = _mapping(profile.get("stages"))
    ordered: Dict[str, Any] = {}
    for key in [
        "artifact_hashes",
        "session_build",
        "mandatory_support_diagnostics",
        "boundary_port_precheck",
        "mandatory_rectangle_precheck",
        "coordinate_validation_precheck",
    ]:
        if key in stages:
            ordered[key] = stages[key]
    for key, value in stages.items():
        if key not in ordered:
            ordered[str(key)] = value
    return ordered


def _stage_detail(stage_id: str, stage: Mapping[str, Any]) -> str:
    if stage_id == "boundary_port_precheck":
        summary = _mapping(stage.get("summary"))
        return (
            f"supported={summary.get('supported')} "
            f"considered={summary.get('considered_anchor_count')} "
            f"pass={summary.get('screen_pass_anchor_count')} "
            f"infeasible={summary.get('screened_infeasible_anchor_count')} "
            f"triggered={stage.get('triggered')}"
        )
    if stage_id == "mandatory_rectangle_precheck":
        return (
            f"anchor_count={stage.get('anchor_count')} "
            f"cap={stage.get('pre_master_anchor_cap')} "
            f"skip={stage.get('skip_reason')} "
            f"triggered={stage.get('triggered')}"
        )
    if stage_id == "coordinate_validation_precheck":
        summary = _mapping(stage.get("summary"))
        return (
            f"anchor_count={stage.get('anchor_count')} "
            f"cap={stage.get('max_anchor_count')} "
            f"seconds={stage.get('time_limit_seconds')} "
            f"skip={stage.get('skip_reason')} "
            f"triggered={stage.get('triggered')} "
            f"evaluated={summary.get('evaluated_anchor_count')} "
            f"unknown={summary.get('unknown_anchor_count')} "
            f"infeasible={summary.get('infeasible_anchor_count')}"
        )
    if stage_id == "mandatory_support_diagnostics":
        return (
            f"groups={stage.get('group_count')} "
            f"empty={stage.get('empty_candidate_pool_group_count')} "
            f"unsupported={stage.get('unsupported_group_count')}"
        )
    if stage_id == "session_build":
        return f"core_build_seconds={stage.get('core_build_seconds')}"
    if stage_id == "artifact_hashes":
        return f"hash_count={stage.get('hash_count')}"
    return ""


def _seconds_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.3f}"
    except Exception:
        return str(value)


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
