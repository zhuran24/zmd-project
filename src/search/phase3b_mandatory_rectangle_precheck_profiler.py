from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence, Tuple

from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS,
    EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV,
    EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS,
    EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV,
    MasterPlacementModel,
    _RectangleFrontierDPFallback,
)
from src.search.benders_loop import (
    _compact_exact_candidate_boundary_port_feasibility,
    create_exact_search_session,
    evaluate_exact_candidate_pre_master_precheck,
)
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso

MANDATORY_RECTANGLE_PRECHECK_PROFILE_SOURCE = (
    "phase3b_mandatory_rectangle_precheck_profiler_v1"
)
DEFAULT_CANDIDATE = "69x19"
DEFAULT_ANCHOR_LIMIT = 16
DEFAULT_GROUP_LIMIT = 8


def build_phase3b_mandatory_rectangle_precheck_profile(
    project_root: Path,
    *,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    boundary_port_precheck_max_anchors: Optional[int] = None,
    mandatory_rectangle_precheck_max_anchors: Optional[int] = None,
    anchor_offset: int = 0,
    anchor_limit: int = DEFAULT_ANCHOR_LIMIT,
    group_limit: int = DEFAULT_GROUP_LIMIT,
    group_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    ghost_w, ghost_h = _parse_candidate(candidate)
    caps = {
        EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV: boundary_port_precheck_max_anchors,
        EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV: mandatory_rectangle_precheck_max_anchors,
    }
    started = time.perf_counter()
    report: Dict[str, Any] = {
        "metadata": {
            "source": MANDATORY_RECTANGLE_PRECHECK_PROFILE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "precheck_profiler_not_proof_source",
        },
        "paths": {"project_root": str(project_root)},
        "candidate": {
            "key": f"{int(ghost_w)}x{int(ghost_h)}",
            "ghost_rect": {"w": int(ghost_w), "h": int(ghost_h), "area": int(ghost_w * ghost_h)},
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "anchor_offset": int(anchor_offset),
            "anchor_limit": int(anchor_limit),
            "group_limit": int(group_limit),
            "group_ids": [str(value) for value in group_ids] if group_ids else [],
            "precheck_caps": {
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
            },
        },
        "artifact_hashes": {},
        "artifact_hash_error": None,
        "status": {
            "completed": False,
            "outcome": "running",
            "recommendation": "Mandatory-rectangle precheck profiler is running.",
        },
        "boundary_port_precheck": {},
        "overlay": {},
        "sample": {},
        "groups": [],
        "timing": {},
        "model_error": None,
        "checks": [],
    }

    try:
        with _temporary_env_caps(caps):
            try:
                report["artifact_hashes"] = compute_exact_artifact_hashes(project_root)
            except Exception as exc:
                report["artifact_hash_error"] = f"{type(exc).__name__}: {exc}"

            session_started = time.perf_counter()
            exact_session = create_exact_search_session(
                project_root,
                solve_mode="certified_exact",
                master_search_profile=master_search_profile,
            )
            report["timing"]["session_build_seconds"] = float(
                time.perf_counter() - session_started
            )
            report["overlay"]["core_build_seconds"] = float(
                getattr(exact_session, "core_build_seconds", 0.0)
            )

            boundary_started = time.perf_counter()
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
            report["timing"]["boundary_port_seconds"] = float(
                time.perf_counter() - boundary_started
            )
            report["boundary_port_precheck"] = {
                "triggered": bool(precheck_outcome.get("triggered", False)),
                "summary": boundary_summary,
                "screen_pass_anchor_indices_count": len(
                    list(boundary_payload.get("screen_pass_anchor_indices", ()))
                ),
                "rebuild_anchor_indices_count": len(
                    list(boundary_payload.get("rebuild_anchor_indices", ()))
                ),
            }
            if bool(precheck_outcome.get("triggered", False)):
                _finalize(
                    report,
                    started=started,
                    outcome="boundary_port_eliminated",
                    recommendation="Boundary-port precheck already eliminates this candidate.",
                )
                return report

            boundary_pass_anchor_indices = tuple(
                int(idx) for idx in boundary_payload.get("screen_pass_anchor_indices", ())
            )
            sampled_anchor_indices = _slice_indices(
                boundary_pass_anchor_indices,
                offset=int(anchor_offset),
                limit=int(anchor_limit),
            )
            report["sample"] = {
                "available_anchor_count": len(boundary_pass_anchor_indices),
                "anchor_offset": int(anchor_offset),
                "anchor_limit": int(anchor_limit),
                "sampled_anchor_count": len(sampled_anchor_indices),
                "sampled_anchor_indices": [int(idx) for idx in sampled_anchor_indices],
            }
            if not boundary_pass_anchor_indices:
                _finalize(
                    report,
                    started=started,
                    outcome="no_boundary_pass_anchors",
                    recommendation="No boundary-pass anchors remain for mandatory-rectangle profiling.",
                )
                return report

            overlay_started = time.perf_counter()
            model = MasterPlacementModel.from_exact_core(
                exact_session.core,
                ghost_rect=(int(ghost_w), int(ghost_h)),
                master_search_profile=master_search_profile,
                precomputed_boundary_port_feasibility=boundary_payload,
            )
            report["overlay"].update(
                {
                    "build_seconds": float(time.perf_counter() - overlay_started),
                    "ghost_anchor_count": int(len(getattr(model, "u_vars", {}))),
                    "search_guidance": dict(model.build_stats.get("search_guidance", {})),
                    "exact_core_reuse": dict(model.build_stats.get("exact_core_reuse", {})),
                }
            )
            target_groups = _select_target_groups(model, group_ids, group_limit)
            report["sample"]["available_group_count"] = len(
                [
                    group
                    for group in list(getattr(model, "_mandatory_groups", []))
                    if str(group.get("facility_type", "")) != "boundary_storage_port"
                ]
            )
            report["sample"]["sampled_group_count"] = len(target_groups)
            report["groups"] = [
                _profile_group(model, group, sampled_anchor_indices)
                for group in target_groups
            ]
            _finalize(
                report,
                started=started,
                outcome="profile_built",
                recommendation=(
                    "Use group elapsed seconds and per-anchor timings to choose the next "
                    "mandatory-rectangle precheck optimization or a staged B5A wall budget."
                ),
            )
    except Exception as exc:
        report["model_error"] = f"{type(exc).__name__}: {exc}"
        _finalize(
            report,
            started=started,
            outcome="diagnostic_error",
            recommendation="Profiler failed; inspect model_error before using this evidence.",
        )
    return report


def render_phase3b_mandatory_rectangle_precheck_profile_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    sample = _mapping(report.get("sample"))
    lines = [
        "# Phase 3B Mandatory-Rectangle Precheck Profile",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "- Diagnostic semantics: precheck_profiler_not_proof_source",
        f"- Sampled anchors: {sample.get('sampled_anchor_count')} / {sample.get('available_anchor_count')}",
        f"- Sampled groups: {sample.get('sampled_group_count')} / {sample.get('available_group_count')}",
        "",
        "| Group | Facility | Oracle | Required | Candidate Poses | Anchors | Seconds | Avg/Anchor | Pass | Infeasible | Unsupported |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for group in list(report.get("groups", [])):
        if not isinstance(group, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(group.get("group_id")),
                    _markdown_cell(group.get("facility_type")),
                    _markdown_cell(group.get("oracle_mode")),
                    _markdown_cell(group.get("required_count")),
                    _markdown_cell(group.get("candidate_pose_count")),
                    _markdown_cell(group.get("considered_anchor_count")),
                    _markdown_cell(_seconds_text(group.get("elapsed_seconds"))),
                    _markdown_cell(_seconds_text(group.get("avg_seconds_per_anchor"))),
                    _markdown_cell(group.get("screen_pass_anchor_count")),
                    _markdown_cell(group.get("screened_infeasible_anchor_count")),
                    _markdown_cell(group.get("unsupported_anchor_count")),
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


def render_phase3b_mandatory_rectangle_precheck_profile_text(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    sample = _mapping(report.get("sample"))
    lines = [
        "Phase 3B mandatory-rectangle precheck profile",
        f"candidate={candidate.get('key')}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        "diagnostic_semantics=precheck_profiler_not_proof_source",
        f"sampled_anchors={sample.get('sampled_anchor_count')}/{sample.get('available_anchor_count')}",
        f"sampled_groups={sample.get('sampled_group_count')}/{sample.get('available_group_count')}",
    ]
    for group in list(report.get("groups", [])):
        if isinstance(group, Mapping):
            lines.append(
                "group "
                f"id={group.get('group_id')} "
                f"facility={group.get('facility_type')} "
                f"oracle={group.get('oracle_mode')} "
                f"required={group.get('required_count')} "
                f"candidate_poses={group.get('candidate_pose_count')} "
                f"anchors={group.get('considered_anchor_count')} "
                f"seconds={_seconds_text(group.get('elapsed_seconds'))} "
                f"avg_anchor={_seconds_text(group.get('avg_seconds_per_anchor'))} "
                f"pass={group.get('screen_pass_anchor_count')} "
                f"infeasible={group.get('screened_infeasible_anchor_count')} "
                f"unsupported={group.get('unsupported_anchor_count')}"
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


def _profile_group(
    model: Any,
    group: Mapping[str, Any],
    anchor_indices: Sequence[int],
) -> Dict[str, Any]:
    started = time.perf_counter()
    group_id = str(group.get("group_id", ""))
    tpl = str(group.get("facility_type", ""))
    required_count = int(group.get("count", 0))
    candidate_indices = [
        int(pose_idx) for pose_idx in model._candidate_pose_indices_for_group(group)
    ]
    support_info = model._exact_candidate_mandatory_pool_support_info(
        tpl,
        candidate_indices,
    )
    entry: Dict[str, Any] = {
        "group_id": group_id,
        "facility_type": tpl,
        "operation_type": str(group.get("operation_type", "")),
        "required_count": int(required_count),
        "candidate_pose_count": len(candidate_indices),
        "supported": bool(support_info.get("supported", False)),
        "oracle_class": support_info.get("oracle_class"),
        "oracle_mode": str(support_info.get("oracle_mode", "unsupported")),
        "unsupported_reason": support_info.get("unsupported_reason"),
        "considered_anchor_count": 0,
        "screened_infeasible_anchor_count": 0,
        "screen_pass_anchor_count": 0,
        "unsupported_anchor_count": 0,
        "max_packable_min": None,
        "max_packable_max": None,
        "first_infeasible_anchor_idx": None,
        "first_infeasible_anchor_max_packable": None,
        "anchor_timings": [],
    }
    if not bool(support_info.get("supported", False)):
        entry["unsupported_anchor_count"] = len(anchor_indices)
        entry["elapsed_seconds"] = float(time.perf_counter() - started)
        entry["avg_seconds_per_anchor"] = 0.0
        return entry

    max_packable_values: list[int] = []
    witness_lower_bound_values: list[int] = []
    witness_pass_anchor_count = 0
    exact_capacity_eval_count = 0
    for rect_idx in anchor_indices:
        anchor_started = time.perf_counter()
        domain = model._ghost_domains[int(rect_idx)]
        blocked_cells = {
            (int(cell[0]), int(cell[1]))
            for cell in list(domain.get("cells", []))
        }
        surviving_pose_indices = [
            int(pose_idx)
            for pose_idx in candidate_indices
            if model._pose_cells(tpl, int(pose_idx)).isdisjoint(blocked_cells)
        ]
        witness = model._find_mandatory_rectangle_precheck_witness(
            tpl,
            surviving_pose_indices,
            required_count,
        )
        if witness is not None:
            witness_pass_anchor_count += 1
            witness_lower_bound_values.append(int(len(witness)))
            entry["screen_pass_anchor_count"] += 1
            anchor_status = "witness_pass"
            max_packable = None
            anchor_elapsed = float(time.perf_counter() - anchor_started)
            entry["anchor_timings"].append(
                {
                    "anchor_idx": int(rect_idx),
                    "elapsed_seconds": anchor_elapsed,
                    "status": anchor_status,
                    "surviving_pose_count": len(surviving_pose_indices),
                    "max_packable": max_packable,
                    "witness_size": int(len(witness)),
                }
            )
            entry["considered_anchor_count"] += 1
            continue
        surviving_support = _surviving_signature_support_status(
            model,
            tpl,
            surviving_pose_indices,
        )
        if not bool(surviving_support.get("supported", False)):
            entry["unsupported_anchor_count"] += 1
            entry["screen_pass_anchor_count"] += 1
            anchor_status = "unsupported_pass"
            max_packable = None
        else:
            exact_capacity_eval_count += 1
            max_packable = int(
                model._solve_exact_local_power_capacity_from_compact(
                    tpl,
                    surviving_support.get("compact_signature"),
                )
            )
            max_packable_values.append(int(max_packable))
            if int(max_packable) < int(required_count):
                entry["screened_infeasible_anchor_count"] += 1
                anchor_status = "infeasible"
                if entry["first_infeasible_anchor_idx"] is None:
                    entry["first_infeasible_anchor_idx"] = int(rect_idx)
                    entry["first_infeasible_anchor_max_packable"] = int(max_packable)
            else:
                entry["screen_pass_anchor_count"] += 1
                anchor_status = "pass"
        anchor_elapsed = float(time.perf_counter() - anchor_started)
        entry["anchor_timings"].append(
            {
                "anchor_idx": int(rect_idx),
                "elapsed_seconds": anchor_elapsed,
                "status": anchor_status,
                "surviving_pose_count": len(surviving_pose_indices),
                "max_packable": max_packable,
            }
        )
        entry["considered_anchor_count"] += 1

    entry["max_packable_min"] = min(max_packable_values) if max_packable_values else None
    entry["max_packable_max"] = max(max_packable_values) if max_packable_values else None
    if witness_pass_anchor_count > 0:
        entry["witness_pass_anchor_count"] = int(witness_pass_anchor_count)
        entry["exact_capacity_eval_count"] = int(exact_capacity_eval_count)
        entry["max_packable_lower_bound_min"] = (
            min(witness_lower_bound_values) if witness_lower_bound_values else None
        )
        entry["max_packable_lower_bound_max"] = (
            max(witness_lower_bound_values) if witness_lower_bound_values else None
        )
    entry["elapsed_seconds"] = float(time.perf_counter() - started)
    considered = max(1, int(entry["considered_anchor_count"]))
    entry["avg_seconds_per_anchor"] = float(entry["elapsed_seconds"] / considered)
    return entry


def _surviving_signature_support_status(
    model: Any,
    tpl: str,
    pose_indices: Sequence[int],
) -> Dict[str, Any]:
    compact_signature = model._compact_signature_for_pose_indices(tpl, pose_indices)
    if compact_signature is None:
        return {
            "supported": False,
            "unsupported_reason": "missing_compact_signature",
            "compact_signature": None,
        }
    try:
        normalized = model._normalize_rectangle_frontier_signature(
            tpl,
            compact_signature,
        )
    except _RectangleFrontierDPFallback:
        return {
            "supported": False,
            "unsupported_reason": "non_rectangular_signature",
            "compact_signature": compact_signature,
        }
    if pose_indices and not normalized:
        return {
            "supported": False,
            "unsupported_reason": "normalization_failed",
            "compact_signature": compact_signature,
        }
    return {
        "supported": True,
        "unsupported_reason": None,
        "compact_signature": compact_signature,
    }


def _select_target_groups(
    model: Any,
    group_ids: Optional[Sequence[str]],
    group_limit: int,
) -> list[Mapping[str, Any]]:
    all_groups = [
        dict(group)
        for group in list(getattr(model, "_mandatory_groups", []))
        if str(group.get("facility_type", "")) != "boundary_storage_port"
    ]
    if group_ids:
        wanted = {str(value) for value in group_ids}
        all_groups = [group for group in all_groups if str(group.get("group_id", "")) in wanted]
    limit = max(0, int(group_limit))
    if limit > 0:
        return all_groups[:limit]
    return all_groups


def _slice_indices(indices: Sequence[int], *, offset: int, limit: int) -> tuple[int, ...]:
    start = max(0, int(offset))
    if int(limit) <= 0:
        return tuple(int(idx) for idx in indices[start:])
    return tuple(int(idx) for idx in indices[start : start + int(limit)])


def _finalize(
    report: Dict[str, Any],
    *,
    started: float,
    outcome: str,
    recommendation: str,
) -> None:
    report["status"] = {
        "completed": True,
        "outcome": str(outcome),
        "recommendation": str(recommendation),
    }
    report["timing"]["total_seconds"] = float(time.perf_counter() - started)
    report["checks"] = _checks(report)


def _checks(report: Mapping[str, Any]) -> list[Dict[str, str]]:
    status = _mapping(report.get("status"))
    boundary = _mapping(report.get("boundary_port_precheck"))
    sample = _mapping(report.get("sample"))
    model_error = report.get("model_error")
    return [
        _check(
            "profile_completed",
            "pass" if bool(status.get("completed", False)) else "fail",
            str(status.get("outcome")),
        ),
        _check(
            "boundary_profile_present",
            "pass" if boundary else "fail",
            "boundary summary recorded" if boundary else "boundary summary missing",
        ),
        _check(
            "sample_recorded",
            "pass" if sample else "skipped",
            f"anchors={sample.get('sampled_anchor_count')}" if sample else "no sample",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


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
def _temporary_env_caps(caps: Mapping[str, Optional[int]]) -> Iterator[None]:
    previous: Dict[str, Optional[str]] = {}
    try:
        for key, value in caps.items():
            previous[str(key)] = os.environ.get(str(key))
            if value is not None:
                os.environ[str(key)] = str(int(value))
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


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _seconds_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.3f}"
    except Exception:
        return str(value)


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
