"""
Outer search（外层搜索） for the maximum empty rectangle objective（最大连续矩形空地目标）.

核心原则：
1. certified_exact（严格认证精确）默认开启。
2. exact 路径只使用 safe static occupied-area lower bound（安全静态占地下界）。
3. 支持 exact campaign（精确战役）恢复与 168 小时级断点续跑。
4. exploratory（探索）结果不得冒充 certified exact（严格认证精确）结果。
"""

from __future__ import annotations

from fractions import Fraction
import json
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from src.io.delivery_manifest import (
    delivery_manifest_output_path,
    export_certified_delivery_manifest,
)
from src.io.output_schema import blueprint_output_path
from src.io.serializer import export_certified_blueprint
from src.models.cut_manager import (
    RUN_STATUS_CERTIFIED,
    RUN_STATUS_INFEASIBLE,
    RUN_STATUS_UNKNOWN,
    RUN_STATUS_UNPROVEN,
)
from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    load_generic_io_requirements_artifact,
    load_project_data,
)
from src.runtime.process_priority import apply_process_priority_if_configured
from src.search.benders_loop import (
    ExactSearchSession,
    _collect_forbidden_certified_master_domain_env_overrides,
    compute_exact_static_area_lower_bound,
    create_exact_search_session,
    evaluate_exact_candidate_pre_master_precheck,
    run_benders_for_ghost_rect,
)
from src.search.campaign_telemetry import (
    append_campaign_wave_summary,
    build_wave_summary,
    load_campaign_telemetry_payload,
)
from src.search.exact_campaign import (
    ExactCampaign,
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    atomic_write_json,
    has_terminal_full_frontier_certified_evidence,
    has_valid_terminal_full_frontier_certified_evidence,
)
from src.search.exact_parallel_scheduler import (
    ExactParallelWorkerPool,
    WorkerResult,
    build_parallel_worker_tasks,
    run_parallel_exact_campaign_wave,
)
from src.search.smt_mt_outer_pruning import (
    OuterPruningEngine,
    maybe_build_engine,
    maybe_notify_infeasible,
    maybe_write_telemetry,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTIER_SELECTION_POLICY = "certification_prune_per_anchor_v1"
_PARALLEL_WAVE_SELECTION_DEPTH_MULTIPLIER = 2
_PRE_MASTER_PRECHECK_LOOKAHEAD_LIMIT = 8
FRONTIER_PROBE_MODE_OFF = "off"
FRONTIER_PROBE_MODE_AUTO = "auto"
FRONTIER_PROBE_SELECTION_REASON = "probe_head"
FRONTIER_PROBE_SELECTION_POLICY = "mid_domain_near_square_v1"
_FRONTIER_PROBE_MIN_POTENTIAL_DOMAIN = 32
_FRONTIER_PROBE_FRONTIER_RATIO = 4
_FRONTIER_PROBE_MAX_ANCHORS = 64
_FRONTIER_PROBE_MAX_ANCHORS_ENV = "EXACT_FRONTIER_PROBE_MAX_ANCHORS"
EXACT_OUTER_SKIP_UNKNOWN_ENV = "EXACT_OUTER_SKIP_UNKNOWN"
_EXACT_OUTER_SKIP_UNKNOWN_TRUE_VALUES = {"1", "true", "yes", "on"}


def _outer_skip_unknown_enabled() -> bool:
    return (
        os.environ.get(EXACT_OUTER_SKIP_UNKNOWN_ENV, "").strip().lower()
        in _EXACT_OUTER_SKIP_UNKNOWN_TRUE_VALUES
    )


def _certified_outer_skip_unknown_blocker() -> Dict[str, Any]:
    return {
        "code": "outer_skip_unknown_not_certified",
        "env": EXACT_OUTER_SKIP_UNKNOWN_ENV,
        "detail": (
            "skipping UNKNOWN frontier candidates makes the campaign declare_mode "
            "best_effort, not a strict full candidate-domain certificate"
        ),
    }


def _mark_certified_campaign_blocked(
    exact_campaign: ExactCampaign,
    *,
    reason: str,
    blockers: Sequence[Mapping[str, Any]],
) -> None:
    # Fail closed on resumed terminal states: an unsafe/manual-gate blocker must
    # not leave stale CERTIFIED-looking final_result payloads in the checkpoint
    # or stale delivery artifacts on disk.
    exact_campaign.state["final_result"] = None
    exact_campaign.state["final_status"] = None
    exact_campaign.mark_campaign_stopped(reason, status=RUN_STATUS_UNPROVEN)
    stop_record = exact_campaign.state.get("last_stop_reason")
    if isinstance(stop_record, dict):
        stop_record["blockers"] = [dict(blocker) for blocker in blockers]
    exact_campaign.save()
    _clear_certified_delivery_solution_artifacts(exact_campaign.project_root)
    _refresh_certified_delivery_manifest_if_any(
        project_root=exact_campaign.project_root,
        exact_campaign=exact_campaign,
    )


def _clear_certified_delivery_solution_artifacts(project_root: Path) -> None:
    """Remove export artifacts that must not survive a fail-closed blocker."""

    stale_artifact_paths = [
        project_root / "data" / "solutions" / "final_solution.json",
        blueprint_output_path(project_root),
        delivery_manifest_output_path(project_root),
    ]
    for artifact_path in stale_artifact_paths:
        try:
            if artifact_path.is_dir() and not artifact_path.is_symlink():
                shutil.rmtree(artifact_path)
            else:
                artifact_path.unlink()
        except FileNotFoundError:
            continue


def _declare_mode_is_strict(exact_campaign: Optional[ExactCampaign]) -> bool:
    if exact_campaign is None:
        return True
    return str(exact_campaign.state.get("declare_mode", "strict")) == "strict"


def _non_strict_terminal_certified_blocker(exact_campaign: ExactCampaign) -> Dict[str, Any]:
    return {
        "code": "final_result_requires_strict_declare_mode",
        "declare_mode": str(exact_campaign.state.get("declare_mode", "strict")),
        "detail": (
            "terminal certified_exact results require strict declare_mode; "
            "best_effort or candidate-subset campaigns must not export certified evidence"
        ),
    }


def _resolve_nonnegative_int_env(env_name: str, default: int) -> int:
    raw_value = os.environ.get(env_name)
    if raw_value is None or str(raw_value).strip() == "":
        return max(0, int(default))
    try:
        return max(0, int(str(raw_value).strip()))
    except ValueError:
        raise ValueError(
            f"Unsupported {env_name}: {raw_value!r}; expected a non-negative integer."
        ) from None


def _frontier_probe_max_anchors() -> int:
    return _resolve_nonnegative_int_env(
        _FRONTIER_PROBE_MAX_ANCHORS_ENV,
        _FRONTIER_PROBE_MAX_ANCHORS,
    )


def _normalize_frontier_probe_mode(frontier_probe_mode: Optional[str]) -> str:
    if frontier_probe_mode is None:
        return FRONTIER_PROBE_MODE_OFF
    normalized = str(frontier_probe_mode).strip().lower()
    if normalized not in {FRONTIER_PROBE_MODE_OFF, FRONTIER_PROBE_MODE_AUTO}:
        raise ValueError(
            "Unsupported frontier probe mode（不支持的 probe 模式）: "
            f"{frontier_probe_mode}"
        )
    return normalized


def _default_frontier_probe_state() -> Dict[str, Any]:
    return {
        "mode": FRONTIER_PROBE_MODE_OFF,
        "executed_candidate_keys": [],
        "execution_count": 0,
        "last_candidate_key": None,
        "last_probe_prune_gain": 0,
        "last_probe_resume_pending": False,
    }


def _load_frontier_probe_state(campaign: Optional[ExactCampaign]) -> Dict[str, Any]:
    state = _default_frontier_probe_state()
    if campaign is None:
        return state
    raw_probe_state = campaign.state.get("frontier_probe")
    if not isinstance(raw_probe_state, Mapping):
        return state
    executed_candidate_keys: List[str] = []
    for raw_key in list(raw_probe_state.get("executed_candidate_keys", [])):
        key = str(raw_key)
        if key and key not in executed_candidate_keys:
            executed_candidate_keys.append(key)
    state.update(
        {
            "mode": str(raw_probe_state.get("mode", FRONTIER_PROBE_MODE_OFF)),
            "executed_candidate_keys": executed_candidate_keys,
            "execution_count": int(raw_probe_state.get("execution_count", len(executed_candidate_keys))),
            "last_candidate_key": raw_probe_state.get("last_candidate_key"),
            "last_probe_prune_gain": int(raw_probe_state.get("last_probe_prune_gain", 0)),
            "last_probe_resume_pending": bool(raw_probe_state.get("last_probe_resume_pending", False)),
        }
    )
    return state


def _persist_frontier_probe_state(
    exact_campaign: Optional[ExactCampaign],
    probe_state: Mapping[str, Any],
) -> None:
    if exact_campaign is None:
        return
    exact_campaign.state["frontier_probe"] = {
        "mode": str(probe_state.get("mode", FRONTIER_PROBE_MODE_OFF)),
        "executed_candidate_keys": [
            str(raw_key)
            for raw_key in list(probe_state.get("executed_candidate_keys", []))
            if str(raw_key)
        ],
        "execution_count": int(probe_state.get("execution_count", 0)),
        "last_candidate_key": probe_state.get("last_candidate_key"),
        "last_probe_prune_gain": int(probe_state.get("last_probe_prune_gain", 0)),
        "last_probe_resume_pending": bool(probe_state.get("last_probe_resume_pending", False)),
    }


def _record_probe_candidate_dispatch(
    *,
    exact_campaign: Optional[ExactCampaign],
    frontier_probe_mode: str,
    candidate: Tuple[int, int, int],
    frontier_candidate_metrics: Mapping[str, Any],
    probe_resume_pending: bool,
) -> None:
    if exact_campaign is None:
        return
    probe_state = _load_frontier_probe_state(exact_campaign)
    candidate_key = _candidate_key(candidate)
    executed_candidate_keys = list(probe_state.get("executed_candidate_keys", []))
    if candidate_key not in executed_candidate_keys:
        executed_candidate_keys.append(candidate_key)
    probe_state.update(
        {
            "mode": str(frontier_probe_mode),
            "executed_candidate_keys": executed_candidate_keys,
            "execution_count": len(executed_candidate_keys),
            "last_candidate_key": candidate_key,
            "last_probe_prune_gain": int(
                frontier_candidate_metrics.get(
                    "probe_prune_gain",
                    frontier_candidate_metrics.get("certification_prune_gain", 0),
                )
            ),
            "last_probe_resume_pending": bool(probe_resume_pending),
        }
    )
    _persist_frontier_probe_state(exact_campaign, probe_state)


def _determine_epsilon_stage(
    elapsed_seconds: float,
    *,
    stage_1_end_hours: float = 25.0,
    stage_2_end_hours: float = 75.0,
) -> float:
    """P1 #7 main: ε-Certified 三阶段 168h split 调度.

    R10 `acb9bd4fdd02868c2` + R11 `a823b529b0879c4bb` 三阶段切分:
    - elapsed < 25h  → ε=0.05 (probe / exploration stage)
    - 25-75h         → ε=0.01 (refinement stage)
    - >= 75h         → ε=0.0  (final certification stage)

    总 168h 预算切 25h prep + 50h refine + 93h cert (duration; 跟 audit C #2 对齐
    后的准确算法; 端点 25h / 75h / 168h). 短跑 (campaign_hours < 25h) 全部走
    stage 1 (ε=0.05); 不影响 cut_manager.cuts_for_stage 的"松到紧 reuse"
    规则 (松 ε 推出的 cut 在紧 ε 仍合法).

    阈值由 EXACT_EPSILON_STAGE1_END_HOURS / EXACT_EPSILON_STAGE2_END_HOURS
    env override; 不设则用 25.0 / 75.0 默认.
    """
    import os
    s1 = stage_1_end_hours
    s2 = stage_2_end_hours
    try:
        s1 = float(os.environ.get("EXACT_EPSILON_STAGE1_END_HOURS", s1))
    except (TypeError, ValueError):
        pass
    try:
        s2 = float(os.environ.get("EXACT_EPSILON_STAGE2_END_HOURS", s2))
    except (TypeError, ValueError):
        pass
    elapsed_hours = float(elapsed_seconds) / 3600.0
    if elapsed_hours < s1:
        return 0.05
    if elapsed_hours < s2:
        return 0.01
    return 0.0


def _normalize_solve_mode(
    solve_mode: Optional[str] = None,
    certification_mode: Optional[bool] = None,
) -> str:
    if certification_mode is not None:
        return "certified_exact" if certification_mode else "exploratory"
    if solve_mode is None:
        return "certified_exact"
    if solve_mode not in {"certified_exact", "exploratory"}:
        raise ValueError(f"Unsupported solve mode（不支持的求解模式）: {solve_mode}")
    return solve_mode


def generate_candidate_sizes(
    *,
    max_w: int = 70,
    max_h: int = 70,
    min_side: int = 6,
    max_aspect_ratio: Optional[float] = None,
    area_upper_bound: Optional[int] = None,
) -> List[Tuple[int, int, int]]:
    candidates: List[Tuple[int, int, int]] = []
    for w in range(min_side, max_w + 1):
        for h in range(min_side, min(max_h, w) + 1):
            area = w * h
            if area_upper_bound is not None and area > area_upper_bound:
                continue
            if max_aspect_ratio is not None and max_aspect_ratio > 0:
                longer = max(w, h)
                shorter = max(1, min(w, h))
                if longer / shorter > max_aspect_ratio:
                    continue
            candidates.append((area, w, h))
    candidates.sort(key=_candidate_sort_key)
    return candidates


def _candidate_objective(candidate: Tuple[int, int, int]) -> Tuple[int, int]:
    area, ghost_w, ghost_h = candidate
    return (int(area), int(min(int(ghost_w), int(ghost_h))))


def _candidate_sort_key(candidate: Tuple[int, int, int]) -> Tuple[int, int, int, int]:
    area, ghost_w, ghost_h = candidate
    min_side = min(int(ghost_w), int(ghost_h))
    max_side = max(int(ghost_w), int(ghost_h))
    # Exact objective source-of-truth is max_lex(area, min_side).
    # Longer-side ordering below is stability-only for deterministic runs.
    return (-int(area), -int(min_side), -int(max_side), -int(int(ghost_w)))


def _candidate_key(candidate: Tuple[int, int, int]) -> str:
    return f"{int(candidate[1])}x{int(candidate[2])}"


def _candidate_dict(candidate: Tuple[int, int, int]) -> Dict[str, int]:
    area, ghost_w, ghost_h = candidate
    return {
        "area": int(area),
        "w": int(ghost_w),
        "h": int(ghost_h),
        "key": _candidate_key(candidate),
    }


def _is_objectively_worse_or_equal(
    candidate: Tuple[int, int, int],
    best_candidate: Tuple[int, int, int],
) -> bool:
    return _candidate_objective(candidate) <= _candidate_objective(best_candidate)


def _find_candidate_by_key(
    candidates: Sequence[Tuple[int, int, int]],
    candidate_key: str,
) -> Optional[Tuple[int, int, int]]:
    normalized_key = str(candidate_key)
    for candidate in candidates:
        if _candidate_key(candidate) == normalized_key:
            return candidate
    return None


def _frontier_probe_domain_large_enough(
    potential_domain: Sequence[Tuple[int, int, int]],
    frontier: Sequence[Tuple[int, int, int]],
) -> bool:
    return len(potential_domain) >= max(
        _FRONTIER_PROBE_MIN_POTENTIAL_DOMAIN,
        len(frontier) * _FRONTIER_PROBE_FRONTIER_RATIO,
    )


def _choose_frontier_probe_candidate(
    potential_domain: Sequence[Tuple[int, int, int]],
    frontier: Sequence[Tuple[int, int, int]],
    *,
    grid_w: int,
    grid_h: int,
) -> Optional[Tuple[int, int, int]]:
    frontier_keys = {_candidate_key(candidate) for candidate in frontier}
    max_anchors = _frontier_probe_max_anchors()
    non_frontier = [
        candidate
        for candidate in potential_domain
        if _candidate_key(candidate) not in frontier_keys
        and _candidate_anchor_count(candidate, grid_w=grid_w, grid_h=grid_h)
        <= max_anchors
    ]
    if not non_frontier:
        return None
    ranked = sorted(non_frontier, key=_candidate_sort_key)
    target_candidate = ranked[len(ranked) // 2]
    target_area, target_w, target_h = target_candidate
    target_min_side = min(int(target_w), int(target_h))
    return min(
        non_frontier,
        key=lambda candidate: (
            abs(int(candidate[0]) - int(target_area)),
            abs(int(candidate[1]) - int(candidate[2])),
            abs(min(int(candidate[1]), int(candidate[2])) - int(target_min_side)),
            _candidate_sort_key(candidate),
        ),
    )


def _candidate_anchor_count(
    candidate: Tuple[int, int, int],
    *,
    grid_w: int,
    grid_h: int,
) -> int:
    _area, ghost_w, ghost_h = candidate
    return max(
        0,
        (int(grid_w) - int(ghost_w) + 1)
        * (int(grid_h) - int(ghost_h) + 1),
    )


def _compute_frontier_candidate_metrics(
    candidate: Tuple[int, int, int],
    potential_domain: List[Tuple[int, int, int]],
    *,
    grid_w: int,
    grid_h: int,
) -> Dict[str, int]:
    area, ghost_w, ghost_h = candidate
    anchor_count = _candidate_anchor_count(candidate, grid_w=grid_w, grid_h=grid_h)
    certification_prune_gain = 0
    infeasible_prune_gain = 0
    for other in potential_domain:
        other_area, other_w, other_h = other
        if _candidate_objective(other) <= _candidate_objective(candidate) or (
            int(other_w) <= int(ghost_w) and int(other_h) <= int(ghost_h)
        ):
            certification_prune_gain += 1
        if int(other_w) >= int(ghost_w) and int(other_h) >= int(ghost_h):
            infeasible_prune_gain += 1

    score = Fraction(certification_prune_gain, max(1, anchor_count))
    return {
        "selection_score_num": int(score.numerator),
        "selection_score_den": int(score.denominator),
        "certification_prune_gain": int(certification_prune_gain),
        "infeasible_prune_gain": int(infeasible_prune_gain),
        "anchor_count": int(anchor_count),
    }


def _frontier_selection_sort_key(
    candidate: Tuple[int, int, int],
    metrics: Dict[str, int],
) -> Tuple[Fraction, int, int, int, int, int, int]:
    min_side = min(int(candidate[1]), int(candidate[2]))
    max_side = max(int(candidate[1]), int(candidate[2]))
    return (
        Fraction(int(metrics["selection_score_num"]), max(1, int(metrics["selection_score_den"]))),
        int(metrics["certification_prune_gain"]),
        -int(metrics["anchor_count"]),
        int(metrics["infeasible_prune_gain"]),
        int(candidate[0]),
        int(min_side),
        int(max_side),
        int(candidate[1]),
    )


def _select_frontier_candidate(
    frontier: List[Tuple[int, int, int]],
    potential_domain: List[Tuple[int, int, int]],
    *,
    grid_w: int,
    grid_h: int,
) -> Tuple[Tuple[int, int, int], Dict[str, int], Dict[str, Dict[str, int]]]:
    metrics_by_key: Dict[str, Dict[str, int]] = {}
    selected_candidate: Optional[Tuple[int, int, int]] = None
    selected_metrics: Optional[Dict[str, int]] = None

    for candidate in frontier:
        metrics = _compute_frontier_candidate_metrics(
            candidate,
            potential_domain,
            grid_w=grid_w,
            grid_h=grid_h,
        )
        metrics["frontier_size"] = len(frontier)
        metrics_by_key[_candidate_key(candidate)] = dict(metrics)
        if selected_candidate is None or _frontier_selection_sort_key(candidate, metrics) > _frontier_selection_sort_key(
            selected_candidate,
            selected_metrics or {},
        ):
            selected_candidate = candidate
            selected_metrics = metrics

    if selected_candidate is None or selected_metrics is None:
        raise ValueError("frontier must be non-empty when selecting a candidate")
    return selected_candidate, selected_metrics, metrics_by_key


def _compute_exact_frontier_state(
    candidates: List[Tuple[int, int, int]],
    campaign: Optional[ExactCampaign],
    *,
    grid_w: int,
    grid_h: int,
    frontier_probe_mode: str = FRONTIER_PROBE_MODE_OFF,
) -> Dict[str, Any]:
    frontier_probe_mode = _normalize_frontier_probe_mode(frontier_probe_mode)
    candidate_records = {}
    if campaign is not None:
        raw_candidates = campaign.state.get("candidates", {})
        if isinstance(raw_candidates, dict):
            candidate_records = raw_candidates
    probe_state = _load_frontier_probe_state(campaign)
    probe_state["mode"] = frontier_probe_mode

    explicit_certified: List[Tuple[int, int, int]] = []
    explicit_infeasible: List[Tuple[int, int, int]] = []
    best_certified_candidate: Optional[Tuple[int, int, int]] = None
    best_certified_record: Optional[Dict[str, Any]] = None

    for candidate in candidates:
        _area, ghost_w, ghost_h = candidate
        record = candidate_records.get(f"{ghost_w}x{ghost_h}")
        if not isinstance(record, dict):
            continue
        status = str(record.get("status", ""))
        if status == RUN_STATUS_CERTIFIED:
            explicit_certified.append(candidate)
            if (
                best_certified_candidate is None
                or _candidate_objective(candidate) > _candidate_objective(best_certified_candidate)
            ):
                best_certified_candidate = candidate
                best_certified_record = dict(record)
        elif status == RUN_STATUS_INFEASIBLE:
            explicit_infeasible.append(candidate)

    potential_domain: List[Tuple[int, int, int]] = []
    derived_pruned_candidates = 0
    # P2 #14 数据收集 A 方案 env-gate: 让 UNKNOWN candidate 也跳过 frontier,
    # 配合 _terminal_stop_reason_for_status (line ~1373) 同 env-gate. 让 outer
    # 真探下一个 candidate 而不是反复 try 同一 UNKNOWN. default off 不影响.
    _frontier_skip_statuses = {RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE}
    if _outer_skip_unknown_enabled():
        _frontier_skip_statuses.add(RUN_STATUS_UNKNOWN)
    for candidate in candidates:
        _area, ghost_w, ghost_h = candidate
        record = candidate_records.get(f"{ghost_w}x{ghost_h}")
        status = None if not isinstance(record, dict) else str(record.get("status", ""))
        if status in _frontier_skip_statuses:
            continue

        if any(ghost_w <= cert_w and ghost_h <= cert_h for _a, cert_w, cert_h in explicit_certified):
            derived_pruned_candidates += 1
            continue
        if any(ghost_w >= inf_w and ghost_h >= inf_h for _a, inf_w, inf_h in explicit_infeasible):
            derived_pruned_candidates += 1
            continue
        if best_certified_candidate is not None and _is_objectively_worse_or_equal(
            candidate,
            best_certified_candidate,
        ):
            derived_pruned_candidates += 1
            continue

        potential_domain.append(candidate)

    frontier: List[Tuple[int, int, int]] = []
    for candidate in potential_domain:
        _area, ghost_w, ghost_h = candidate
        dominated = False
        for other in potential_domain:
            if other == candidate:
                continue
            _other_area, other_w, other_h = other
            if (other_w >= ghost_w and other_h >= ghost_h) and (
                other_w > ghost_w or other_h > ghost_h
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    frontier.sort(key=_candidate_objective, reverse=True)

    frontier_selected_candidate: Optional[Tuple[int, int, int]] = None
    frontier_selected_metrics: Optional[Dict[str, int]] = None
    frontier_metrics_by_key: Dict[str, Dict[str, int]] = {}
    if frontier:
        frontier_selected_candidate, frontier_selected_metrics, frontier_metrics_by_key = _select_frontier_candidate(
            frontier,
            potential_domain,
            grid_w=grid_w,
            grid_h=grid_h,
        )

    selected_candidate = frontier_selected_candidate
    selected_metrics = None if frontier_selected_metrics is None else dict(frontier_selected_metrics)
    selected_candidate_reason = "prune_head"
    probe_candidate: Optional[Tuple[int, int, int]] = None
    probe_candidate_metrics: Optional[Dict[str, int]] = None
    probe_resume_pending = False
    probe_already_executed = bool(list(probe_state.get("executed_candidate_keys", [])))
    probe_candidate_source = None

    if frontier_probe_mode == FRONTIER_PROBE_MODE_AUTO and best_certified_candidate is None:
        pending_key = probe_state.get("last_candidate_key")
        if pending_key is not None:
            pending_candidate = _find_candidate_by_key(potential_domain, str(pending_key))
            pending_record = candidate_records.get(str(pending_key))
            pending_status = (
                None
                if not isinstance(pending_record, Mapping)
                else str(pending_record.get("status", ""))
            )
            if pending_candidate is not None and pending_status in {
                RUN_STATUS_UNKNOWN,
                RUN_STATUS_UNPROVEN,
                "RUNNING",
            }:
                probe_candidate = pending_candidate
                probe_resume_pending = True
                probe_candidate_source = "resume_pending"

        if (
            probe_candidate is None
            and not probe_already_executed
            and frontier
            and _frontier_probe_domain_large_enough(potential_domain, frontier)
        ):
            probe_candidate = _choose_frontier_probe_candidate(
                potential_domain,
                frontier,
                grid_w=grid_w,
                grid_h=grid_h,
            )
            if probe_candidate is not None:
                probe_candidate_source = FRONTIER_PROBE_SELECTION_POLICY

    if probe_candidate is not None:
        probe_candidate_metrics = _compute_frontier_candidate_metrics(
            probe_candidate,
            potential_domain,
            grid_w=grid_w,
            grid_h=grid_h,
        )
        probe_candidate_metrics.update(
            {
                "frontier_size": len(frontier),
                "potential_domain_size": len(potential_domain),
                "probe_candidate": 1,
                "probe_prune_gain": int(probe_candidate_metrics.get("certification_prune_gain", 0)),
                "probe_resume_pending": 1 if probe_resume_pending else 0,
            }
        )
        frontier_metrics_by_key[_candidate_key(probe_candidate)] = dict(probe_candidate_metrics)
        selected_candidate = probe_candidate
        selected_metrics = dict(probe_candidate_metrics)
        selected_candidate_reason = FRONTIER_PROBE_SELECTION_REASON

    return {
        "potential_domain": potential_domain,
        "frontier": frontier,
        "frontier_size": len(frontier),
        "derived_pruned_candidates": derived_pruned_candidates,
        "best_certified_candidate": best_certified_candidate,
        "best_certified_record": best_certified_record,
        "frontier_selected_candidate": frontier_selected_candidate,
        "frontier_selected_candidate_metrics": frontier_selected_metrics,
        "selected_candidate": selected_candidate,
        "selected_candidate_metrics": selected_metrics,
        "selected_candidate_reason": selected_candidate_reason,
        "frontier_metrics_by_key": frontier_metrics_by_key,
        "frontier_probe_mode": frontier_probe_mode,
        "probe_round_active": probe_candidate is not None,
        "probe_candidate": probe_candidate,
        "probe_candidate_source": probe_candidate_source,
        "probe_candidate_metrics": probe_candidate_metrics,
        "probe_resume_pending": probe_resume_pending,
        "probe_already_executed": probe_already_executed,
        "probe_state": probe_state,
    }


def _build_certified_result(
    *,
    candidate: Tuple[int, int, int],
    solution: Dict[str, Any],
    attempts: int,
    solve_mode: str,
    campaign_resumed: bool,
    frontier_peak_size: int,
    derived_pruned_candidates: int,
    frontier_selection_policy: str,
    frontier_candidate_metrics: Mapping[str, Any],
) -> Dict[str, Any]:
    area, ghost_w, ghost_h = candidate
    return {
        "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": area},
        "placement_solution": dict(solution),
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {
            "attempts": attempts,
            "explicit_candidate_solves": attempts,
            "solve_mode": solve_mode,
            "campaign_resumed": campaign_resumed,
            "frontier_peak_size": frontier_peak_size,
            "derived_pruned_candidates": derived_pruned_candidates,
            "frontier_selection_policy": str(frontier_selection_policy),
            "frontier_candidate_metrics": dict(frontier_candidate_metrics),
        },
    }


def _commit_terminal_full_frontier_certified_result(
    exact_campaign: ExactCampaign,
    result: Mapping[str, Any],
) -> None:
    exact_campaign.state["final_result"] = dict(result)
    exact_campaign.state["final_status"] = RUN_STATUS_CERTIFIED
    exact_campaign.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        status=RUN_STATUS_CERTIFIED,
    )
    if not has_valid_terminal_full_frontier_certified_evidence(exact_campaign.state):
        raise RuntimeError(
            "terminal certified_exact export attempted before full-frontier evidence was committed"
        )
    exact_campaign.save()


def _save_final_result(
    project_root: Path,
    result: Dict[str, Any],
    *,
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Path:
    output_dir = project_root / "data" / "solutions"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "final_solution.json"
    atomic_write_json(output_path, result)
    export_certified_blueprint(
        project_root=project_root,
        result=result,
        facility_pools=facility_pools,
    )
    return output_path


def _persist_best_certified_result_if_any(
    *,
    project_root: Path,
    exact_campaign: Optional[ExactCampaign],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Optional[Dict[str, Any]]:
    if exact_campaign is None:
        return None
    best_result = exact_campaign.best_certified_result()
    if best_result is None:
        _clear_certified_delivery_solution_artifacts(project_root)
        return None
    _save_final_result(
        project_root,
        best_result,
        facility_pools=facility_pools,
    )
    return best_result


def _refresh_certified_delivery_manifest_if_any(
    *,
    project_root: Path,
    exact_campaign: Optional[ExactCampaign],
) -> Optional[Dict[str, Any]]:
    if exact_campaign is None:
        return None
    _path, payload = export_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=exact_campaign.state,
        campaign_path=exact_campaign.path,
    )
    return payload


def _refresh_certified_delivery_outputs(
    *,
    project_root: Path,
    exact_campaign: Optional[ExactCampaign],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> None:
    _persist_best_certified_result_if_any(
        project_root=project_root,
        exact_campaign=exact_campaign,
        facility_pools=facility_pools,
    )
    _refresh_certified_delivery_manifest_if_any(
        project_root=project_root,
        exact_campaign=exact_campaign,
    )


def _build_campaign_result_payload(
    *,
    attempts: int,
    proof_summary: Mapping[str, Any],
    exact_safe_cuts: Sequence[Mapping[str, Any]],
    loaded_exact_safe_cut_count: int,
    generated_exact_safe_cut_count: int,
    frontier_selection_policy: str,
    frontier_candidate_metrics: Mapping[str, Any],
) -> Dict[str, Any]:
    proof_summary = dict(proof_summary)
    return {
        "proof_summary": {
            "search_attempts": attempts,
            "frontier_selection_policy": str(frontier_selection_policy),
            "frontier_candidate_metrics": dict(frontier_candidate_metrics),
            **proof_summary,
        },
        "exact_safe_cuts": [dict(raw_cut) for raw_cut in exact_safe_cuts],
        "loaded_exact_safe_cut_count": int(loaded_exact_safe_cut_count),
        "generated_exact_safe_cut_count": int(generated_exact_safe_cut_count),
    }


def _sorted_frontier_candidates(
    frontier_state: Mapping[str, Any],
) -> List[Tuple[int, int, int]]:
    frontier = [tuple(candidate) for candidate in list(frontier_state.get("frontier", []))]
    metrics_by_key = {
        str(key): dict(value)
        for key, value in dict(frontier_state.get("frontier_metrics_by_key", {})).items()
        if isinstance(value, Mapping)
    }
    frontier.sort(
        key=lambda candidate: _frontier_selection_sort_key(
            candidate,
            metrics_by_key.get(_candidate_key(candidate), {}),
        ),
        reverse=True,
    )
    return frontier


def _objective_sorted_frontier_candidates(
    frontier_state: Mapping[str, Any],
) -> List[Tuple[int, int, int]]:
    frontier = [tuple(candidate) for candidate in list(frontier_state.get("frontier", []))]
    frontier.sort(key=_candidate_sort_key)
    return frontier


def _anchor_sorted_frontier_candidates(
    frontier_state: Mapping[str, Any],
) -> List[Tuple[int, int, int]]:
    frontier = [tuple(candidate) for candidate in list(frontier_state.get("frontier", []))]
    metrics_by_key = {
        str(key): dict(value)
        for key, value in dict(frontier_state.get("frontier_metrics_by_key", {})).items()
        if isinstance(value, Mapping)
    }
    frontier.sort(
        key=lambda candidate: (
            int(metrics_by_key.get(_candidate_key(candidate), {}).get("anchor_count", 10**9)),
            *_candidate_sort_key(candidate),
        )
    )
    return frontier


def _append_parallel_wave_head(
    *,
    entries: List[Dict[str, Any]],
    selected_keys: set[str],
    ranked_candidates: Sequence[Tuple[int, int, int]],
    selection_reason: str,
) -> None:
    for candidate in ranked_candidates:
        candidate_key = _candidate_key(candidate)
        if candidate_key in selected_keys:
            continue
        entries.append(
            {
                "candidate": tuple(candidate),
                "selection_reason": str(selection_reason),
                "wave_slot_index": int(len(entries)),
            }
        )
        selected_keys.add(candidate_key)
        return


def _append_precheck_lookahead_entry(
    *,
    entries: List[Dict[str, Any]],
    selected_keys: set[str],
    candidate: Optional[Tuple[int, int, int]],
    selection_reason: str,
    frontier_state: Mapping[str, Any],
) -> None:
    if candidate is None:
        return
    candidate_tuple = tuple(candidate)
    candidate_key = _candidate_key(candidate_tuple)
    if candidate_key in selected_keys:
        return
    entry: Dict[str, Any] = {
        "candidate": candidate_tuple,
        "selection_reason": str(selection_reason),
        "wave_slot_index": int(len(entries)),
    }
    frontier_metrics_by_key = {
        str(key): dict(value)
        for key, value in dict(frontier_state.get("frontier_metrics_by_key", {})).items()
        if isinstance(value, Mapping)
    }
    selected_candidate = frontier_state.get("selected_candidate")
    selected_candidate_tuple = (
        None if selected_candidate is None else tuple(selected_candidate)
    )
    if (
        selected_candidate_tuple is not None
        and _candidate_key(selected_candidate_tuple) == candidate_key
        and isinstance(frontier_state.get("selected_candidate_metrics"), Mapping)
    ):
        entry["frontier_candidate_metrics"] = dict(
            frontier_state.get("selected_candidate_metrics") or {}
        )
    else:
        entry["frontier_candidate_metrics"] = dict(
            frontier_metrics_by_key.get(candidate_key, {})
        )
    probe_candidate = frontier_state.get("probe_candidate")
    probe_candidate_tuple = None if probe_candidate is None else tuple(probe_candidate)
    if (
        str(selection_reason) == FRONTIER_PROBE_SELECTION_REASON
        or (
            probe_candidate_tuple is not None
            and _candidate_key(probe_candidate_tuple) == candidate_key
        )
    ):
        probe_metrics = dict(frontier_state.get("probe_candidate_metrics") or {})
        entry["selection_reason"] = FRONTIER_PROBE_SELECTION_REASON
        entry["probe_candidate"] = True
        entry["probe_prune_gain"] = int(
            probe_metrics.get(
                "probe_prune_gain",
                probe_metrics.get("certification_prune_gain", 0),
            )
        )
        entry["probe_resume_pending"] = bool(
            frontier_state.get("probe_resume_pending", False)
        )
        entry["frontier_probe_mode"] = str(
            frontier_state.get("frontier_probe_mode", FRONTIER_PROBE_MODE_OFF)
        )
        entry["frontier_candidate_metrics"] = dict(probe_metrics)
    entries.append(entry)
    selected_keys.add(candidate_key)


def _select_precheck_lookahead_candidate_entries(
    frontier_state: Mapping[str, Any],
    *,
    limit: int,
) -> List[Dict[str, Any]]:
    limit = max(0, int(limit))
    if limit <= 0:
        return []
    potential_domain = [
        tuple(candidate)
        for candidate in list(frontier_state.get("potential_domain", []))
    ]
    if not potential_domain:
        return []

    potential_keys = {_candidate_key(candidate) for candidate in potential_domain}
    entries: List[Dict[str, Any]] = []
    selected_keys: set[str] = set()
    selected_candidate = frontier_state.get("selected_candidate")
    selected_candidate_tuple = (
        None if selected_candidate is None else tuple(selected_candidate)
    )
    if (
        selected_candidate_tuple is not None
        and _candidate_key(selected_candidate_tuple) in potential_keys
    ):
        _append_precheck_lookahead_entry(
            entries=entries,
            selected_keys=selected_keys,
            candidate=selected_candidate_tuple,
            selection_reason=str(
                frontier_state.get("selected_candidate_reason", "prune_head")
            ),
            frontier_state=frontier_state,
        )

    prune_sorted_frontier = _sorted_frontier_candidates(frontier_state)
    selection_steps = [
        ("objective_head", _objective_sorted_frontier_candidates(frontier_state)),
        ("prune_head", prune_sorted_frontier),
        ("anchor_head", _anchor_sorted_frontier_candidates(frontier_state)),
    ]
    for selection_reason, ranking in selection_steps:
        for candidate in ranking:
            if len(entries) >= limit:
                return entries
            if _candidate_key(candidate) not in potential_keys:
                continue
            _append_precheck_lookahead_entry(
                entries=entries,
                selected_keys=selected_keys,
                candidate=tuple(candidate),
                selection_reason=selection_reason,
                frontier_state=frontier_state,
            )

    while len(entries) < limit:
        size_before = len(entries)
        for candidate in prune_sorted_frontier:
            if _candidate_key(candidate) not in potential_keys:
                continue
            _append_precheck_lookahead_entry(
                entries=entries,
                selected_keys=selected_keys,
                candidate=tuple(candidate),
                selection_reason="prune_fill",
                frontier_state=frontier_state,
            )
            if len(entries) >= limit:
                return entries
            if len(entries) > size_before:
                break
        if len(entries) == size_before:
            break
    return entries


def _select_parallel_wave_candidate_entries(
    frontier_state: Mapping[str, Any],
    *,
    parallel_processes: int,
    remaining_attempt_budget: Optional[int],
) -> List[Dict[str, Any]]:
    parallel_processes = int(parallel_processes)
    if parallel_processes <= 1:
        if remaining_attempt_budget is None:
            limit = parallel_processes
        else:
            limit = min(parallel_processes, max(0, int(remaining_attempt_budget)))
    else:
        limit = parallel_processes * _PARALLEL_WAVE_SELECTION_DEPTH_MULTIPLIER
        if remaining_attempt_budget is not None:
            limit = min(limit, max(0, int(remaining_attempt_budget)))

    prune_sorted_frontier = _sorted_frontier_candidates(frontier_state)
    if not prune_sorted_frontier:
        return []
    potential_domain = [tuple(candidate) for candidate in list(frontier_state.get("potential_domain", []))]
    if not potential_domain:
        potential_domain = list(prune_sorted_frontier)
    available_candidate_count = len({_candidate_key(candidate) for candidate in potential_domain})

    probe_candidate = frontier_state.get("probe_candidate")
    probe_candidate_tuple = None if probe_candidate is None else tuple(probe_candidate)
    inject_probe_candidate = probe_candidate_tuple is not None and _candidate_key(probe_candidate_tuple) in {
        _candidate_key(candidate) for candidate in potential_domain
    }
    extra_probe_slot = 0
    if inject_probe_candidate and (
        remaining_attempt_budget is None or int(remaining_attempt_budget) > int(limit)
    ):
        extra_probe_slot = 1

    limit = min(int(limit) + int(extra_probe_slot), int(max(available_candidate_count, 0)))
    if limit <= 0:
        return []

    entries: List[Dict[str, Any]] = []
    selected_keys: set[str] = set()

    if inject_probe_candidate and probe_candidate_tuple is not None:
        probe_metrics = dict(frontier_state.get("probe_candidate_metrics") or {})
        entries.append(
            {
                "candidate": tuple(probe_candidate_tuple),
                "selection_reason": FRONTIER_PROBE_SELECTION_REASON,
                "wave_slot_index": int(len(entries)),
                "probe_candidate": True,
                "probe_prune_gain": int(
                    probe_metrics.get(
                        "probe_prune_gain",
                        probe_metrics.get("certification_prune_gain", 0),
                    )
                ),
                "probe_resume_pending": bool(frontier_state.get("probe_resume_pending", False)),
                "frontier_probe_mode": str(
                    frontier_state.get("frontier_probe_mode", FRONTIER_PROBE_MODE_OFF)
                ),
            }
        )
        selected_keys.add(_candidate_key(probe_candidate_tuple))

    objective_sorted_frontier = _objective_sorted_frontier_candidates(frontier_state)
    anchor_sorted_frontier = _anchor_sorted_frontier_candidates(frontier_state)

    selection_steps = [
        ("objective_head", objective_sorted_frontier),
        ("prune_head", prune_sorted_frontier),
        ("anchor_head", anchor_sorted_frontier),
    ]
    for selection_reason, ranking in selection_steps:
        if len(entries) >= limit:
            break
        _append_parallel_wave_head(
            entries=entries,
            selected_keys=selected_keys,
            ranked_candidates=ranking,
            selection_reason=selection_reason,
        )

    while len(entries) < limit:
        size_before = len(entries)
        _append_parallel_wave_head(
            entries=entries,
            selected_keys=selected_keys,
            ranked_candidates=prune_sorted_frontier,
            selection_reason="prune_fill",
        )
        if len(entries) == size_before:
            break
    return entries


def _select_parallel_wave_candidates(
    frontier_state: Mapping[str, Any],
    *,
    parallel_processes: int,
    remaining_attempt_budget: Optional[int],
) -> List[Tuple[int, int, int]]:
    return [
        tuple(entry["candidate"])
        for entry in _select_parallel_wave_candidate_entries(
            frontier_state,
            parallel_processes=parallel_processes,
            remaining_attempt_budget=remaining_attempt_budget,
        )
    ]


def _campaign_payload_from_run_metadata(
    *,
    attempts: int,
    run_metadata: Mapping[str, Any],
    frontier_candidate_metrics: Mapping[str, Any],
) -> Dict[str, Any]:
    return _build_campaign_result_payload(
        attempts=attempts,
        proof_summary=dict(run_metadata.get("proof_summary", {})),
        exact_safe_cuts=list(run_metadata.get("exact_safe_cuts", [])),
        loaded_exact_safe_cut_count=int(run_metadata.get("loaded_exact_safe_cut_count", 0)),
        generated_exact_safe_cut_count=int(run_metadata.get("generated_exact_safe_cut_count", 0)),
        frontier_selection_policy=FRONTIER_SELECTION_POLICY,
        frontier_candidate_metrics=frontier_candidate_metrics,
    )


def _campaign_payload_from_precheck_proof(
    *,
    attempts: int,
    proof_summary: Mapping[str, Any],
    frontier_candidate_metrics: Mapping[str, Any],
) -> Dict[str, Any]:
    return _build_campaign_result_payload(
        attempts=attempts,
        proof_summary=dict(proof_summary),
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
        frontier_selection_policy=FRONTIER_SELECTION_POLICY,
        frontier_candidate_metrics=frontier_candidate_metrics,
    )


def _augment_campaign_payload_with_selection(
    campaign_payload: Mapping[str, Any],
    *,
    selection_reason: str,
    frontier_candidate_metrics: Mapping[str, Any],
    frontier_probe_mode: str,
) -> Dict[str, Any]:
    payload = dict(campaign_payload)
    proof_summary = dict(payload.get("proof_summary", {}))
    proof_summary["selection_reason"] = str(selection_reason)
    if (
        str(selection_reason) == FRONTIER_PROBE_SELECTION_REASON
        or str(frontier_probe_mode) != FRONTIER_PROBE_MODE_OFF
    ):
        proof_summary["frontier_probe"] = {
            "mode": str(frontier_probe_mode),
            "probe_candidate": bool(
                str(selection_reason) == FRONTIER_PROBE_SELECTION_REASON
            ),
            "probe_resume_pending": bool(
                frontier_candidate_metrics.get("probe_resume_pending", 0)
            )
            if str(selection_reason) == FRONTIER_PROBE_SELECTION_REASON
            else False,
            "probe_prune_gain": int(
                frontier_candidate_metrics.get(
                    "probe_prune_gain",
                    frontier_candidate_metrics.get("certification_prune_gain", 0),
                )
            )
            if str(selection_reason) == FRONTIER_PROBE_SELECTION_REASON
            else 0,
        }
    payload["proof_summary"] = proof_summary
    return payload


def _selection_metadata(
    *,
    selection_reason: str,
    frontier_candidate_metrics: Mapping[str, Any],
    frontier_probe_mode: str,
) -> Dict[str, Any]:
    is_probe_candidate = str(selection_reason) == FRONTIER_PROBE_SELECTION_REASON
    return {
        "probe_candidate": bool(is_probe_candidate),
        "probe_prune_gain": int(
            frontier_candidate_metrics.get(
                "probe_prune_gain",
                frontier_candidate_metrics.get("certification_prune_gain", 0),
            )
        )
        if is_probe_candidate
        else 0,
        "probe_resume_pending": bool(frontier_candidate_metrics.get("probe_resume_pending", 0))
        if is_probe_candidate
        else False,
        "frontier_probe_mode": str(frontier_probe_mode),
    }


def _ensure_exact_session(
    exact_session: Optional[ExactSearchSession],
    *,
    project_root: Path,
    solve_mode: str,
    master_search_profile: str,
) -> ExactSearchSession:
    if exact_session is not None:
        return exact_session
    return create_exact_search_session(
        project_root,
        solve_mode=solve_mode,
        master_search_profile=master_search_profile,
    )


def _evaluate_pre_master_precheck_best_effort(
    *,
    candidate: Tuple[int, int, int],
    exact_session: Any,
    master_search_profile: str,
    include_mandatory_rectangle_precheck: bool = False,
) -> Dict[str, Any]:
    if exact_session is None or not hasattr(exact_session, "core"):
        return {"triggered": False, "status": None, "proof_summary": {}}
    try:
        kwargs: Dict[str, Any] = {
            "ghost_w": int(candidate[1]),
            "ghost_h": int(candidate[2]),
            "exact_session": exact_session,
            "master_search_profile": master_search_profile,
        }
        if bool(include_mandatory_rectangle_precheck):
            kwargs["include_mandatory_rectangle_precheck"] = True
        return evaluate_exact_candidate_pre_master_precheck(**kwargs)
    except (AttributeError, TypeError):
        if bool(include_mandatory_rectangle_precheck):
            try:
                return evaluate_exact_candidate_pre_master_precheck(
                    ghost_w=int(candidate[1]),
                    ghost_h=int(candidate[2]),
                    exact_session=exact_session,
                    master_search_profile=master_search_profile,
                )
            except (AttributeError, TypeError):
                pass
        return {"triggered": False, "status": None, "proof_summary": {}}


def _record_precheck_elimination(
    *,
    selected_candidate: Tuple[int, int, int],
    attempt_index: int,
    selection_reason: str,
    wave_slot_index: int,
    dispatch_seq: int,
    proof_summary: Mapping[str, Any],
    frontier_candidate_metrics: Mapping[str, Any],
    frontier_probe_mode: str,
    exact_campaign: Optional[ExactCampaign],
    precheck_lookahead: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    _area, ghost_w, ghost_h = selected_candidate
    normalized_proof_summary = dict(proof_summary)
    if precheck_lookahead is not None:
        normalized_proof_summary["precheck_lookahead"] = {
            "enabled": bool(precheck_lookahead.get("enabled", False)),
            "slot_index": int(precheck_lookahead.get("slot_index", 0)),
            "limit": int(precheck_lookahead.get("limit", 0)),
            "is_selected_head": bool(
                precheck_lookahead.get("is_selected_head", False)
            ),
        }
    campaign_payload = _augment_campaign_payload_with_selection(
        _campaign_payload_from_precheck_proof(
            attempts=attempt_index,
            proof_summary=normalized_proof_summary,
            frontier_candidate_metrics=frontier_candidate_metrics,
        ),
        selection_reason=selection_reason,
        frontier_candidate_metrics=frontier_candidate_metrics,
        frontier_probe_mode=frontier_probe_mode,
    )
    if exact_campaign is not None:
        exact_campaign.mark_candidate_result(
            int(ghost_w),
            int(ghost_h),
            RUN_STATUS_INFEASIBLE,
            exact_safe_cuts=campaign_payload["exact_safe_cuts"],
            proof_summary=campaign_payload["proof_summary"],
            loaded_exact_safe_cut_count=campaign_payload["loaded_exact_safe_cut_count"],
            generated_exact_safe_cut_count=campaign_payload[
                "generated_exact_safe_cut_count"
            ],
        )
    return _candidate_result_entry(
        candidate=selected_candidate,
        dispatch_seq=int(dispatch_seq),
        attempt_index=attempt_index,
        wave_slot_index=wave_slot_index,
        selection_reason=selection_reason,
        status=RUN_STATUS_INFEASIBLE,
        proof_summary=campaign_payload["proof_summary"],
        loaded_exact_safe_cut_count=int(campaign_payload["loaded_exact_safe_cut_count"]),
        generated_exact_safe_cut_count=int(
            campaign_payload["generated_exact_safe_cut_count"]
        ),
        **_selection_metadata(
            selection_reason=selection_reason,
            frontier_candidate_metrics=frontier_candidate_metrics,
            frontier_probe_mode=frontier_probe_mode,
        ),
    )


def _campaign_payload_from_worker_result(
    *,
    worker_result: WorkerResult,
    frontier_candidate_metrics: Mapping[str, Any],
) -> Dict[str, Any]:
    return _build_campaign_result_payload(
        attempts=int(worker_result.attempt_index),
        proof_summary=worker_result.proof_summary,
        exact_safe_cuts=worker_result.exact_safe_cuts,
        loaded_exact_safe_cut_count=int(worker_result.loaded_exact_safe_cut_count),
        generated_exact_safe_cut_count=int(worker_result.generated_exact_safe_cut_count),
        frontier_selection_policy=FRONTIER_SELECTION_POLICY,
        frontier_candidate_metrics=frontier_candidate_metrics,
    )


def _candidate_result_entry(
    *,
    candidate: Tuple[int, int, int],
    dispatch_seq: int,
    attempt_index: int,
    wave_slot_index: int,
    selection_reason: str,
    status: str,
    proof_summary: Mapping[str, Any],
    loaded_exact_safe_cut_count: int,
    generated_exact_safe_cut_count: int,
    probe_candidate: bool = False,
    probe_prune_gain: int = 0,
    probe_resume_pending: bool = False,
    frontier_probe_mode: str = FRONTIER_PROBE_MODE_OFF,
) -> Dict[str, Any]:
    return {
        "candidate_key": _candidate_key(candidate),
        "dispatch_seq": int(dispatch_seq),
        "attempt_index": int(attempt_index),
        "wave_slot_index": int(wave_slot_index),
        "selection_reason": str(selection_reason),
        "status": str(status),
        "proof_summary": dict(proof_summary),
        "loaded_exact_safe_cut_count": int(loaded_exact_safe_cut_count),
        "generated_exact_safe_cut_count": int(generated_exact_safe_cut_count),
        "probe_candidate": bool(probe_candidate),
        "probe_prune_gain": int(probe_prune_gain),
        "probe_resume_pending": bool(probe_resume_pending),
        "frontier_probe_mode": str(frontier_probe_mode),
    }


def _append_wave_telemetry_best_effort(
    *,
    project_root: Path,
    exact_campaign: Optional[ExactCampaign],
    wave_index: int,
    candidate_results: Sequence[Mapping[str, Any]],
    completed: bool,
    failure_reason: Optional[str],
    dispatched_candidate_keys: Sequence[str],
    elapsed_seconds: Optional[float] = None,
    peak_rss_bytes_external_total: Optional[int] = None,
    peak_rss_bytes_internal_max_single_process: Optional[int] = None,
    reset: bool = False,
) -> None:
    if exact_campaign is None:
        return
    try:
        payload = append_campaign_wave_summary(
            project_root=project_root,
            campaign_path=exact_campaign.path,
            reset=reset,
            wave_summary=build_wave_summary(
                wave_index=wave_index,
                candidate_results=candidate_results,
                completed=completed,
                failure_reason=failure_reason,
                dispatched_candidate_keys=dispatched_candidate_keys,
                elapsed_seconds=elapsed_seconds,
                peak_rss_bytes_external_total=peak_rss_bytes_external_total,
                peak_rss_bytes_internal_max_single_process=peak_rss_bytes_internal_max_single_process,
            ),
        )
        run_outer_search.last_run_telemetry = payload
        run_outer_search.last_run_telemetry_error = None
    except Exception as exc:
        run_outer_search.last_run_telemetry_error = f"{type(exc).__name__}: {exc}"


def _terminal_stop_reason_for_status(status: str) -> Optional[str]:
    normalized_status = str(status)
    if normalized_status == RUN_STATUS_UNKNOWN:
        # P2 #14 数据收集 A 方案 env-gate: EXACT_OUTER_SKIP_UNKNOWN=1 时
        # UNKNOWN 不标记 campaign terminal stop, 让 main 退出后 watchdog
        # 重启 resume 继续探下一个 frontier candidate (UNKNOWN 已被
        # mark_candidate_result 标记, frontier 跳过). 收 LBBD inner loop
        # binding subproblem 实例做 evaluator fixture.
        #
        # 副作用 (违反 max_lex 严格性): declare 出的"最优"可能漏了 UNKNOWN
        # candidate (求解器超时未确定是否 FEASIBLE). audit_log 应标记
        # campaign 含 UNKNOWN gap → declare 为 best_effort 而非 strict.
        # default off 保留严格证明语义.
        if _outer_skip_unknown_enabled():
            return None
        return "candidate_returned_unknown"
    if normalized_status == RUN_STATUS_UNPROVEN:
        return "candidate_returned_unproven"
    return None


def run_outer_search(
    *,
    start_area: Optional[int] = None,
    max_attempts: Optional[int] = None,
    project_root: Optional[Path] = None,
    solve_mode: Optional[str] = None,
    certification_mode: Optional[bool] = None,
    master_seconds: float = 600.0,
    binding_seconds: float = 600.0,
    routing_seconds: float = 600.0,
    flow_seconds: float = 60.0,
    master_time_limit: Optional[float] = None,
    benders_max_iter: int = 30,
    campaign_hours: float = 168.0,
    resume_campaign: bool = False,
    max_aspect_ratio: Optional[float] = None,
    area_upper_bound: Optional[int] = None,
    min_side: int = 6,
    parallel_processes: int = 1,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    frontier_probe_mode: str = FRONTIER_PROBE_MODE_OFF,
    disable_master_warm_start: bool = False,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    apply_process_priority_if_configured()
    solve_mode = _normalize_solve_mode(solve_mode, certification_mode)
    frontier_probe_mode = _normalize_frontier_probe_mode(frontier_probe_mode)
    if project_root is None:
        project_root = PROJECT_ROOT
    if master_time_limit is not None:
        master_seconds = float(master_time_limit)
    parallel_processes = max(1, int(parallel_processes))

    exact_campaign: Optional[ExactCampaign] = None
    if solve_mode == "certified_exact":
        unsafe_domain_env_blockers = _collect_forbidden_certified_master_domain_env_overrides()
        if unsafe_domain_env_blockers:
            exact_campaign = ExactCampaign.load_or_create(
                project_root,
                campaign_hours=campaign_hours,
                resume=False,
            )
            _mark_certified_campaign_blocked(
                exact_campaign,
                reason="unsafe_certified_exact_master_domain_env",
                blockers=unsafe_domain_env_blockers,
            )
            return RUN_STATUS_UNPROVEN, None
        if _outer_skip_unknown_enabled():
            blocker = _certified_outer_skip_unknown_blocker()
            exact_campaign = ExactCampaign.load_or_create(
                project_root,
                campaign_hours=campaign_hours,
                resume=False,
            )
            _mark_certified_campaign_blocked(
                exact_campaign,
                reason=str(blocker["code"]),
                blockers=[blocker],
            )
            return RUN_STATUS_UNPROVEN, None
        exact_campaign = ExactCampaign.load_or_create(
            project_root,
            campaign_hours=campaign_hours,
            resume=resume_campaign,
        )
        probe_state = _load_frontier_probe_state(exact_campaign)
        probe_state["mode"] = frontier_probe_mode
        _persist_frontier_probe_state(exact_campaign, probe_state)
    telemetry_wave_index = 0
    reset_campaign_telemetry = bool(exact_campaign is not None and not exact_campaign.resumed)
    run_outer_search.last_run_telemetry = None
    run_outer_search.last_run_telemetry_error = None
    if exact_campaign is not None and not reset_campaign_telemetry:
        try:
            existing_telemetry = load_campaign_telemetry_payload(
                project_root=project_root,
                campaign_path=exact_campaign.path,
            )
        except Exception as exc:
            run_outer_search.last_run_telemetry_error = f"{type(exc).__name__}: {exc}"
            reset_campaign_telemetry = True
        else:
            run_outer_search.last_run_telemetry = existing_telemetry
            if isinstance(existing_telemetry, Mapping):
                telemetry_wave_index = int(len(list(existing_telemetry.get("waves", []))))

    exact_instances, _pools, rules = load_project_data(project_root, solve_mode="certified_exact")
    generic_io_requirements = load_generic_io_requirements_artifact(project_root)
    grid = dict(rules["globals"]["grid"])
    grid_w = int(grid["width"])
    grid_h = int(grid["height"])
    safe_area_upper_bound = grid_w * grid_h - compute_exact_static_area_lower_bound(
        exact_instances,
        rules,
        generic_io_requirements,
    )
    if area_upper_bound is None:
        area_upper_bound = safe_area_upper_bound
    else:
        area_upper_bound = min(int(area_upper_bound), safe_area_upper_bound)

    candidates = generate_candidate_sizes(
        max_w=grid_w,
        max_h=grid_h,
        min_side=min_side,
        max_aspect_ratio=max_aspect_ratio,
        area_upper_bound=area_upper_bound,
    )
    if start_area is not None:
        candidates = [item for item in candidates if item[0] <= start_area]

    evaluation_attempts = 0
    solve_attempts = 0
    frontier_peak_size = 0
    exact_session: Optional[ExactSearchSession] = None
    parallel_worker_pool: Optional[ExactParallelWorkerPool] = None

    # SMT-MT outer pruning Phase 1 (env-gated, default off):
    # build R-tree-backed monotone containment engine over (w, h) candidates.
    # The engine is shadow-friendly — it records every INFEASIBLE verdict
    # via O(log N) R-tree query and surfaces telemetry alongside the
    # existing frontier-state size-level superset check. env off => None.
    smt_mt_engine: Optional[OuterPruningEngine] = maybe_build_engine(candidates)
    smt_mt_telemetry_wave_counter: List[int] = [0]

    def _smt_mt_record_infeasible(w: int, h: int) -> None:
        if smt_mt_engine is None:
            return
        try:
            maybe_notify_infeasible(smt_mt_engine, int(w), int(h))
            smt_mt_telemetry_wave_counter[0] += 1
            maybe_write_telemetry(
                smt_mt_engine,
                project_root,
                wave_index=smt_mt_telemetry_wave_counter[0],
            )
        except Exception as exc:
            # Telemetry-only path: never raise into the main loop.
            run_outer_search.last_smt_mt_telemetry_error = (
                f"{type(exc).__name__}: {exc}"
            )

    try:
        if solve_mode == "certified_exact":
            while True:
                frontier_state = _compute_exact_frontier_state(
                    candidates,
                    exact_campaign,
                    grid_w=grid_w,
                    grid_h=grid_h,
                    frontier_probe_mode=frontier_probe_mode,
                )
                frontier_peak_size = max(frontier_peak_size, int(frontier_state["frontier_size"]))

                if not frontier_state["potential_domain"]:
                    if exact_campaign is not None and not _declare_mode_is_strict(exact_campaign):
                        blocker = _non_strict_terminal_certified_blocker(exact_campaign)
                        _mark_certified_campaign_blocked(
                            exact_campaign,
                            reason=str(blocker["code"]),
                            blockers=[blocker],
                        )
                        return RUN_STATUS_UNPROVEN, None

                    best_candidate = frontier_state["best_certified_candidate"]
                    best_record = frontier_state["best_certified_record"]
                    if best_candidate is not None and isinstance(best_record, dict):
                        best_proof_summary = dict(best_record.get("proof_summary", {}))
                        result = _build_certified_result(
                            candidate=best_candidate,
                            solution=dict(best_record.get("solution", {})),
                            attempts=solve_attempts,
                            solve_mode=solve_mode,
                            campaign_resumed=exact_campaign.resumed if exact_campaign is not None else False,
                            frontier_peak_size=frontier_peak_size,
                            derived_pruned_candidates=int(
                                frontier_state["derived_pruned_candidates"]
                            ),
                            frontier_selection_policy=str(
                                best_proof_summary.get(
                                    "frontier_selection_policy",
                                    FRONTIER_SELECTION_POLICY,
                                )
                            ),
                            frontier_candidate_metrics=dict(
                                best_proof_summary.get("frontier_candidate_metrics", {})
                            ),
                        )
                        if exact_campaign is not None:
                            _commit_terminal_full_frontier_certified_result(
                                exact_campaign,
                                result,
                            )
                        try:
                            _save_final_result(
                                project_root,
                                result,
                                facility_pools=_pools,
                            )
                            if exact_campaign is not None:
                                _refresh_certified_delivery_manifest_if_any(
                                    project_root=project_root,
                                    exact_campaign=exact_campaign,
                                )
                        except Exception as exc:  # noqa: BLE001
                            if exact_campaign is None:
                                raise
                            _mark_certified_campaign_blocked(
                                exact_campaign,
                                reason="terminal_certified_export_failed",
                                blockers=[
                                    {
                                        "code": "terminal_certified_export_failed",
                                        "exception_type": type(exc).__name__,
                                        "detail": str(exc),
                                    }
                                ],
                            )
                            return RUN_STATUS_UNPROVEN, None
                        return RUN_STATUS_CERTIFIED, result

                    if exact_campaign is not None:
                        exact_campaign.mark_campaign_stopped(
                            "search_exhausted_all_candidates",
                            status=RUN_STATUS_INFEASIBLE,
                        )
                        exact_campaign.save()
                        _refresh_certified_delivery_outputs(
                            project_root=project_root,
                            exact_campaign=exact_campaign,
                            facility_pools=_pools,
                        )
                    return RUN_STATUS_INFEASIBLE, None

                if exact_campaign is not None and exact_campaign.remaining_seconds() <= 0:
                    exact_campaign.mark_campaign_stopped(
                        "campaign_time_budget_exhausted",
                        status=RUN_STATUS_UNKNOWN,
                    )
                    exact_campaign.save()
                    _refresh_certified_delivery_outputs(
                        project_root=project_root,
                        exact_campaign=exact_campaign,
                        facility_pools=_pools,
                    )
                    return RUN_STATUS_UNKNOWN, None

                if parallel_processes <= 1:
                    while frontier_state["potential_domain"]:
                        exact_session = _ensure_exact_session(
                            exact_session,
                            project_root=project_root,
                            solve_mode=solve_mode,
                            master_search_profile=master_search_profile,
                        )
                        lookahead_entries = _select_precheck_lookahead_candidate_entries(
                            frontier_state,
                            limit=_PRE_MASTER_PRECHECK_LOOKAHEAD_LIMIT,
                        )
                        if not lookahead_entries:
                            break
                        precheck_round_results: List[Dict[str, Any]] = []
                        for entry in lookahead_entries:
                            candidate = tuple(entry["candidate"])
                            precheck_outcome = _evaluate_pre_master_precheck_best_effort(
                                candidate=candidate,
                                exact_session=exact_session,
                                master_search_profile=master_search_profile,
                                include_mandatory_rectangle_precheck=True,
                            )
                            if not bool(precheck_outcome.get("triggered", False)):
                                continue
                            if str(entry["selection_reason"]) == FRONTIER_PROBE_SELECTION_REASON:
                                _record_probe_candidate_dispatch(
                                    exact_campaign=exact_campaign,
                                    frontier_probe_mode=str(
                                        entry.get(
                                            "frontier_probe_mode",
                                            frontier_state.get(
                                                "frontier_probe_mode",
                                                FRONTIER_PROBE_MODE_OFF,
                                            ),
                                        )
                                    ),
                                    candidate=candidate,
                                    frontier_candidate_metrics=dict(
                                        entry.get("frontier_candidate_metrics", {})
                                    ),
                                    probe_resume_pending=bool(
                                        entry.get("probe_resume_pending", False)
                                    ),
                                )
                            evaluation_attempts += 1
                            precheck_round_results.append(
                                _record_precheck_elimination(
                                    selected_candidate=candidate,
                                    attempt_index=evaluation_attempts,
                                    selection_reason=str(entry["selection_reason"]),
                                    wave_slot_index=int(entry["wave_slot_index"]),
                                    dispatch_seq=len(precheck_round_results),
                                    proof_summary=dict(
                                        precheck_outcome.get("proof_summary", {})
                                    ),
                                    frontier_candidate_metrics=dict(
                                        entry.get("frontier_candidate_metrics", {})
                                    ),
                                    frontier_probe_mode=str(
                                        entry.get(
                                            "frontier_probe_mode",
                                            frontier_state.get(
                                                "frontier_probe_mode",
                                                FRONTIER_PROBE_MODE_OFF,
                                            ),
                                        )
                                    ),
                                    precheck_lookahead={
                                        "enabled": True,
                                        "slot_index": int(entry["wave_slot_index"]),
                                        "limit": _PRE_MASTER_PRECHECK_LOOKAHEAD_LIMIT,
                                        "is_selected_head": int(entry["wave_slot_index"])
                                        == 0,
                                    },
                                    exact_campaign=exact_campaign,
                                )
                            )
                            # SMT-MT shadow telemetry: precheck-eliminated
                            # candidate is INFEASIBLE per proof, propagate.
                            _smt_mt_record_infeasible(int(candidate[1]), int(candidate[2]))
                        if not precheck_round_results:
                            break
                        if exact_campaign is not None:
                            exact_campaign.save()
                            telemetry_wave_index += 1
                            _append_wave_telemetry_best_effort(
                                project_root=project_root,
                                exact_campaign=exact_campaign,
                                wave_index=telemetry_wave_index,
                                candidate_results=precheck_round_results,
                                completed=True,
                                failure_reason=None,
                                dispatched_candidate_keys=[],
                                reset=reset_campaign_telemetry,
                            )
                            reset_campaign_telemetry = False
                        frontier_state = _compute_exact_frontier_state(
                            candidates,
                            exact_campaign,
                            grid_w=grid_w,
                            grid_h=grid_h,
                            frontier_probe_mode=frontier_probe_mode,
                        )
                        frontier_peak_size = max(
                            frontier_peak_size,
                            int(frontier_state["frontier_size"]),
                        )

                    if not frontier_state["potential_domain"]:
                        continue

                if max_attempts is not None and solve_attempts >= max_attempts:
                    if exact_campaign is not None:
                        exact_campaign.mark_campaign_stopped(
                            "max_attempts_exhausted",
                            status=RUN_STATUS_UNKNOWN,
                        )
                        exact_campaign.save()
                        _refresh_certified_delivery_outputs(
                            project_root=project_root,
                            exact_campaign=exact_campaign,
                            facility_pools=_pools,
                        )
                    return RUN_STATUS_UNKNOWN, None

                if parallel_processes > 1:
                    remaining_attempt_budget = None
                    if max_attempts is not None:
                        remaining_attempt_budget = max(
                            0,
                            int(max_attempts) - int(solve_attempts),
                        )
                    wave_candidate_entries = _select_parallel_wave_candidate_entries(
                        frontier_state,
                        parallel_processes=parallel_processes,
                        remaining_attempt_budget=remaining_attempt_budget,
                    )
                    if not wave_candidate_entries:
                        if exact_campaign is not None:
                            exact_campaign.mark_campaign_stopped(
                                "max_attempts_exhausted",
                                status=RUN_STATUS_UNKNOWN,
                            )
                            exact_campaign.save()
                            _refresh_certified_delivery_outputs(
                                project_root=project_root,
                                exact_campaign=exact_campaign,
                                facility_pools=_pools,
                            )
                        return RUN_STATUS_UNKNOWN, None

                    wave_metrics_by_key = {
                        _candidate_key(tuple(entry["candidate"])): dict(
                            dict(frontier_state.get("frontier_metrics_by_key", {})).get(
                                _candidate_key(tuple(entry["candidate"])),
                                {},
                            )
                        )
                        for entry in wave_candidate_entries
                    }
                    exact_session = _ensure_exact_session(
                        exact_session,
                        project_root=project_root,
                        solve_mode=solve_mode,
                        master_search_profile=master_search_profile,
                    )
                    coordinator_precheck_results: List[Dict[str, Any]] = []
                    solve_wave_entries: List[Dict[str, Any]] = []
                    for entry in wave_candidate_entries:
                        candidate = tuple(entry["candidate"])
                        candidate_key = _candidate_key(candidate)
                        if str(entry["selection_reason"]) == FRONTIER_PROBE_SELECTION_REASON:
                            _record_probe_candidate_dispatch(
                                exact_campaign=exact_campaign,
                                frontier_probe_mode=str(
                                    entry.get(
                                        "frontier_probe_mode",
                                        frontier_state.get(
                                            "frontier_probe_mode",
                                            FRONTIER_PROBE_MODE_OFF,
                                        ),
                                    )
                                ),
                                candidate=candidate,
                                frontier_candidate_metrics=wave_metrics_by_key.get(
                                    candidate_key,
                                    {},
                                ),
                                probe_resume_pending=bool(
                                    entry.get("probe_resume_pending", False)
                                ),
                            )
                        evaluation_attempts += 1
                        precheck_outcome = _evaluate_pre_master_precheck_best_effort(
                            candidate=candidate,
                            exact_session=exact_session,
                            master_search_profile=master_search_profile,
                        )
                        if bool(precheck_outcome.get("triggered", False)):
                            coordinator_precheck_results.append(
                                _record_precheck_elimination(
                                    selected_candidate=candidate,
                                    attempt_index=evaluation_attempts,
                                    selection_reason=str(entry["selection_reason"]),
                                    wave_slot_index=int(entry["wave_slot_index"]),
                                    dispatch_seq=int(entry["wave_slot_index"]),
                                    proof_summary=dict(
                                        precheck_outcome.get("proof_summary", {})
                                    ),
                                    frontier_candidate_metrics=wave_metrics_by_key.get(
                                        candidate_key,
                                        {},
                                    ),
                                    frontier_probe_mode=str(
                                        entry.get(
                                            "frontier_probe_mode",
                                            frontier_state.get(
                                                "frontier_probe_mode",
                                                FRONTIER_PROBE_MODE_OFF,
                                            ),
                                        )
                                    ),
                                    precheck_lookahead={
                                        "enabled": False,
                                        "slot_index": int(entry["wave_slot_index"]),
                                        "limit": 0,
                                        "is_selected_head": int(entry["wave_slot_index"])
                                        == 0,
                                    },
                                    exact_campaign=exact_campaign,
                                )
                            )
                            # SMT-MT shadow telemetry: precheck-eliminated INFEASIBLE.
                            _smt_mt_record_infeasible(int(candidate[1]), int(candidate[2]))
                            continue
                        solve_wave_entries.append(
                            {
                                "candidate": candidate,
                                "candidate_key": candidate_key,
                                "selection_reason": str(entry["selection_reason"]),
                                "wave_slot_index": int(entry["wave_slot_index"]),
                                "attempt_index": int(evaluation_attempts),
                                "probe_candidate": bool(entry.get("probe_candidate", False)),
                                "probe_prune_gain": int(entry.get("probe_prune_gain", 0)),
                                "probe_resume_pending": bool(entry.get("probe_resume_pending", False)),
                                "frontier_probe_mode": str(
                                    entry.get(
                                        "frontier_probe_mode",
                                        frontier_state.get(
                                            "frontier_probe_mode",
                                            FRONTIER_PROBE_MODE_OFF,
                                        ),
                                    )
                                ),
                            }
                        )

                    if not solve_wave_entries:
                        if exact_campaign is not None:
                            exact_campaign.save()
                            telemetry_wave_index += 1
                            _append_wave_telemetry_best_effort(
                                project_root=project_root,
                                exact_campaign=exact_campaign,
                                wave_index=telemetry_wave_index,
                                candidate_results=coordinator_precheck_results,
                                completed=True,
                                failure_reason=None,
                                dispatched_candidate_keys=[],
                                reset=reset_campaign_telemetry,
                            )
                            reset_campaign_telemetry = False
                        continue

                    if parallel_worker_pool is None:
                        parallel_worker_pool = ExactParallelWorkerPool(
                            process_count=parallel_processes,
                            project_root=project_root,
                            solve_mode=solve_mode,
                            master_search_profile=master_search_profile,
                        )

                    preloaded_cut_map: Dict[str, Sequence[Mapping[str, Any]]] = {}
                    if exact_campaign is not None:
                        for solve_entry in solve_wave_entries:
                            candidate = tuple(solve_entry["candidate"])
                            _area, ghost_w, ghost_h = candidate
                            preloaded_cut_map[str(solve_entry["candidate_key"])] = (
                                exact_campaign.get_candidate_cuts(int(ghost_w), int(ghost_h))
                            )
                            exact_campaign.mark_candidate_started(int(ghost_w), int(ghost_h))
                        exact_campaign.save()

                    # P1 #7 main: parallel 路径 wave-level ε 阶段计算,
                    # 跟单进程路径 (line ~2080) 对齐. WorkerTask 全部带同一 ε,
                    # worker 把 ε tag 传给 run_benders_for_ghost_rect → BendersCut.
                    _parallel_wave_epsilon: Optional[float] = None
                    if exact_campaign is not None and solve_mode == "certified_exact":
                        _parallel_wave_epsilon = _determine_epsilon_stage(
                            exact_campaign.elapsed_seconds()
                        )

                    tasks = build_parallel_worker_tasks(
                        candidates=[
                            tuple(entry["candidate"]) for entry in solve_wave_entries
                        ],
                        attempt_start=0,
                        attempt_indices=[
                            int(entry["attempt_index"]) for entry in solve_wave_entries
                        ],
                        master_seconds=master_seconds,
                        binding_seconds=binding_seconds,
                        routing_seconds=routing_seconds,
                        flow_seconds=flow_seconds,
                        benders_max_iter=benders_max_iter,
                        disable_master_warm_start=bool(disable_master_warm_start),
                        preloaded_cut_map=preloaded_cut_map,
                        epsilon_stage=_parallel_wave_epsilon,
                    )
                    solve_attempts += len(tasks)
                    wave_execution = run_parallel_exact_campaign_wave(
                        pool=parallel_worker_pool,
                        tasks=tasks,
                    )
                    sorted_wave_results = sorted(
                        wave_execution.results,
                        key=lambda result: int(result.dispatch_seq),
                    )

                    if exact_campaign is not None:
                        terminal_status: Optional[str] = None
                        terminal_reason: Optional[str] = None
                        wave_candidate_results_by_key: Dict[str, Dict[str, Any]] = {
                            str(result["candidate_key"]): dict(result)
                            for result in coordinator_precheck_results
                        }
                        for worker_result in sorted_wave_results:
                            matching_solve_entry = next(
                                (
                                    entry
                                    for entry in solve_wave_entries
                                    if str(entry["candidate_key"])
                                    == str(worker_result.candidate_key)
                                ),
                                None,
                            )
                            selection_reason = str(
                                str(matching_solve_entry["selection_reason"])
                                if matching_solve_entry is not None
                                else "prune_fill"
                            )
                            frontier_probe_mode_for_entry = str(
                                str(matching_solve_entry.get("frontier_probe_mode", FRONTIER_PROBE_MODE_OFF))
                                if matching_solve_entry is not None
                                else FRONTIER_PROBE_MODE_OFF
                            )
                            ghost_w = int(worker_result.candidate[1])
                            ghost_h = int(worker_result.candidate[2])
                            candidate_metrics = wave_metrics_by_key.get(
                                worker_result.candidate_key,
                                {},
                            )
                            payload = _augment_campaign_payload_with_selection(
                                _campaign_payload_from_worker_result(
                                    worker_result=worker_result,
                                    frontier_candidate_metrics=candidate_metrics,
                                ),
                                selection_reason=selection_reason,
                                frontier_candidate_metrics=candidate_metrics,
                                frontier_probe_mode=frontier_probe_mode_for_entry,
                            )
                            if (
                                worker_result.status == RUN_STATUS_CERTIFIED
                                and worker_result.solution is not None
                            ):
                                exact_campaign.mark_candidate_result(
                                    ghost_w,
                                    ghost_h,
                                    RUN_STATUS_CERTIFIED,
                                    exact_safe_cuts=payload["exact_safe_cuts"],
                                    solution=worker_result.solution,
                                    proof_summary=payload["proof_summary"],
                                    loaded_exact_safe_cut_count=payload[
                                        "loaded_exact_safe_cut_count"
                                    ],
                                    generated_exact_safe_cut_count=payload[
                                        "generated_exact_safe_cut_count"
                                    ],
                                )
                            elif worker_result.status in {
                                RUN_STATUS_INFEASIBLE,
                                RUN_STATUS_UNKNOWN,
                                RUN_STATUS_UNPROVEN,
                            }:
                                exact_campaign.mark_candidate_result(
                                    ghost_w,
                                    ghost_h,
                                    worker_result.status,
                                    exact_safe_cuts=payload["exact_safe_cuts"],
                                    proof_summary=payload["proof_summary"],
                                    loaded_exact_safe_cut_count=payload[
                                        "loaded_exact_safe_cut_count"
                                    ],
                                    generated_exact_safe_cut_count=payload[
                                        "generated_exact_safe_cut_count"
                                    ],
                                )
                                if worker_result.status == RUN_STATUS_INFEASIBLE:
                                    _smt_mt_record_infeasible(ghost_w, ghost_h)
                                if terminal_status is None:
                                    stop_reason = _terminal_stop_reason_for_status(
                                        worker_result.status
                                    )
                                    if stop_reason is not None:
                                        terminal_status = str(worker_result.status)
                                        terminal_reason = str(stop_reason)
                            wave_candidate_results_by_key[
                                str(worker_result.candidate_key)
                            ] = _candidate_result_entry(
                                candidate=worker_result.candidate,
                                dispatch_seq=int(worker_result.dispatch_seq),
                                attempt_index=int(worker_result.attempt_index),
                                status=str(worker_result.status),
                                proof_summary=payload["proof_summary"],
                                loaded_exact_safe_cut_count=int(
                                    payload["loaded_exact_safe_cut_count"]
                                ),
                                generated_exact_safe_cut_count=int(
                                    payload["generated_exact_safe_cut_count"]
                                ),
                                wave_slot_index=int(
                                    int(matching_solve_entry["wave_slot_index"])
                                    if matching_solve_entry is not None
                                    else int(worker_result.dispatch_seq)
                                ),
                                selection_reason=selection_reason,
                                probe_candidate=bool(
                                    matching_solve_entry.get("probe_candidate", False)
                                )
                                if matching_solve_entry is not None
                                else False,
                                probe_prune_gain=int(
                                    matching_solve_entry.get("probe_prune_gain", 0)
                                )
                                if matching_solve_entry is not None
                                else 0,
                                probe_resume_pending=bool(
                                    matching_solve_entry.get("probe_resume_pending", False)
                                )
                                if matching_solve_entry is not None
                                else False,
                                frontier_probe_mode=frontier_probe_mode_for_entry,
                            )
                        ordered_wave_candidate_results = [
                            dict(wave_candidate_results_by_key[candidate_key])
                            for candidate_key in [
                                _candidate_key(tuple(entry["candidate"]))
                                for entry in wave_candidate_entries
                            ]
                            if candidate_key in wave_candidate_results_by_key
                        ]
                        exact_campaign.save()
                        telemetry_wave_index += 1
                        _append_wave_telemetry_best_effort(
                            project_root=project_root,
                            exact_campaign=exact_campaign,
                            wave_index=telemetry_wave_index,
                            candidate_results=ordered_wave_candidate_results,
                            completed=bool(wave_execution.completed),
                            failure_reason=wave_execution.failure_reason,
                            dispatched_candidate_keys=wave_execution.dispatched_candidate_keys,
                            elapsed_seconds=float(wave_execution.elapsed_seconds),
                            peak_rss_bytes_external_total=int(
                                wave_execution.peak_rss_bytes_external_total
                            ),
                            peak_rss_bytes_internal_max_single_process=int(
                                wave_execution.peak_rss_bytes_internal_max_single_process
                            ),
                            reset=reset_campaign_telemetry,
                        )
                        reset_campaign_telemetry = False

                        if not wave_execution.completed:
                            exact_campaign.mark_campaign_stopped(
                                "worker_process_failed",
                                status=RUN_STATUS_UNKNOWN,
                            )
                            exact_campaign.save()
                            _refresh_certified_delivery_outputs(
                                project_root=project_root,
                                exact_campaign=exact_campaign,
                                facility_pools=_pools,
                            )
                            return RUN_STATUS_UNKNOWN, None

                        if terminal_status is not None and terminal_reason is not None:
                            exact_campaign.mark_campaign_stopped(
                                terminal_reason,
                                status=terminal_status,
                            )
                            exact_campaign.save()
                            _refresh_certified_delivery_outputs(
                                project_root=project_root,
                                exact_campaign=exact_campaign,
                                facility_pools=_pools,
                            )
                            return terminal_status, None
                    continue

                selected_candidate = frontier_state["selected_candidate"]
                if selected_candidate is None:
                    raise ValueError("frontier must provide a selected candidate when potential_domain is non-empty")
                _area, ghost_w, ghost_h = selected_candidate
                frontier_candidate_metrics = dict(frontier_state["selected_candidate_metrics"] or {})
                selected_candidate_reason = str(
                    frontier_state.get("selected_candidate_reason", "prune_head")
                )
                frontier_probe_mode_for_selected = str(
                    frontier_state.get("frontier_probe_mode", FRONTIER_PROBE_MODE_OFF)
                )
                if selected_candidate_reason == FRONTIER_PROBE_SELECTION_REASON:
                    _record_probe_candidate_dispatch(
                        exact_campaign=exact_campaign,
                        frontier_probe_mode=frontier_probe_mode_for_selected,
                        candidate=tuple(selected_candidate),
                        frontier_candidate_metrics=frontier_candidate_metrics,
                        probe_resume_pending=bool(
                            frontier_state.get("probe_resume_pending", False)
                        ),
                    )
                if exact_campaign is not None:
                    exact_campaign.mark_candidate_started(ghost_w, ghost_h)
                    exact_campaign.save()

                evaluation_attempts += 1
                solve_attempts += 1
                exact_session = _ensure_exact_session(
                    exact_session,
                    project_root=project_root,
                    solve_mode=solve_mode,
                    master_search_profile=master_search_profile,
                )
                # P1 #7 main: 算当前 wave 的 ε 阶段 (25h prep / 50h refine / 93h cert),
                # 让 controller 给新生成的 BendersCut tag epsilon_stage.
                _wave_epsilon: Optional[float] = None
                if exact_campaign is not None and solve_mode == "certified_exact":
                    _wave_epsilon = _determine_epsilon_stage(
                        exact_campaign.elapsed_seconds()
                    )
                status, solution = run_benders_for_ghost_rect(
                    ghost_w=ghost_w,
                    ghost_h=ghost_h,
                    max_iterations=benders_max_iter,
                    project_root=project_root,
                    solve_mode=solve_mode,
                    master_seconds=master_seconds,
                    binding_seconds=binding_seconds,
                    routing_seconds=routing_seconds,
                    flow_seconds=flow_seconds,
                    campaign=exact_campaign,
                    session=exact_session,
                    master_search_profile=master_search_profile,
                    disable_master_warm_start=bool(disable_master_warm_start),
                    epsilon_stage=_wave_epsilon,
                )
                run_metadata = dict(getattr(run_benders_for_ghost_rect, "last_run_metadata", {}) or {})
                campaign_payload = _campaign_payload_from_run_metadata(
                    attempts=evaluation_attempts,
                    run_metadata=run_metadata,
                    frontier_candidate_metrics=frontier_candidate_metrics,
                )
                campaign_payload = _augment_campaign_payload_with_selection(
                    campaign_payload,
                    selection_reason=selected_candidate_reason,
                    frontier_candidate_metrics=frontier_candidate_metrics,
                    frontier_probe_mode=frontier_probe_mode_for_selected,
                )
                serial_candidate_result = _candidate_result_entry(
                    candidate=selected_candidate,
                    dispatch_seq=0,
                    attempt_index=evaluation_attempts,
                    wave_slot_index=0,
                    selection_reason=selected_candidate_reason,
                    status=str(status),
                    proof_summary=campaign_payload["proof_summary"],
                    loaded_exact_safe_cut_count=int(campaign_payload["loaded_exact_safe_cut_count"]),
                    generated_exact_safe_cut_count=int(
                        campaign_payload["generated_exact_safe_cut_count"]
                    ),
                    **_selection_metadata(
                        selection_reason=selected_candidate_reason,
                        frontier_candidate_metrics=frontier_candidate_metrics,
                        frontier_probe_mode=frontier_probe_mode_for_selected,
                    ),
                )

                if status == RUN_STATUS_CERTIFIED and solution is not None:
                    if exact_campaign is not None:
                        exact_campaign.mark_candidate_result(
                            ghost_w,
                            ghost_h,
                            RUN_STATUS_CERTIFIED,
                            exact_safe_cuts=campaign_payload["exact_safe_cuts"],
                            solution=solution,
                            proof_summary=campaign_payload["proof_summary"],
                            loaded_exact_safe_cut_count=campaign_payload["loaded_exact_safe_cut_count"],
                            generated_exact_safe_cut_count=campaign_payload[
                                "generated_exact_safe_cut_count"
                            ],
                        )
                        exact_campaign.save()
                        telemetry_wave_index += 1
                        _append_wave_telemetry_best_effort(
                            project_root=project_root,
                            exact_campaign=exact_campaign,
                            wave_index=telemetry_wave_index,
                            candidate_results=[serial_candidate_result],
                            completed=True,
                            failure_reason=None,
                            dispatched_candidate_keys=[_candidate_key(selected_candidate)],
                            reset=reset_campaign_telemetry,
                        )
                        reset_campaign_telemetry = False
                    continue

                if status == RUN_STATUS_INFEASIBLE:
                    if exact_campaign is not None:
                        exact_campaign.mark_candidate_result(
                            ghost_w,
                            ghost_h,
                            RUN_STATUS_INFEASIBLE,
                            exact_safe_cuts=campaign_payload["exact_safe_cuts"],
                            proof_summary=campaign_payload["proof_summary"],
                            loaded_exact_safe_cut_count=campaign_payload["loaded_exact_safe_cut_count"],
                            generated_exact_safe_cut_count=campaign_payload[
                                "generated_exact_safe_cut_count"
                            ],
                        )
                        exact_campaign.save()
                        telemetry_wave_index += 1
                        _append_wave_telemetry_best_effort(
                            project_root=project_root,
                            exact_campaign=exact_campaign,
                            wave_index=telemetry_wave_index,
                            candidate_results=[serial_candidate_result],
                            completed=True,
                            failure_reason=None,
                            dispatched_candidate_keys=[_candidate_key(selected_candidate)],
                            reset=reset_campaign_telemetry,
                        )
                        reset_campaign_telemetry = False
                    _smt_mt_record_infeasible(ghost_w, ghost_h)
                    continue

                if status == RUN_STATUS_UNKNOWN:
                    # P2 #14 audit follow-up (2026-05-15): env on 时这条 return
                    # path 之前漏 env check (helper line 1390 已 fix, 这条 hardcoded
                    # return 没 fix), 导致 168h best-effort 跑撞第一个 UNKNOWN 就
                    # stop 退出. 这里补齐 — env on 时 skip mark_stopped + continue
                    # wave loop 探下个 candidate.
                    _skip_unknown_env = _outer_skip_unknown_enabled()
                    if exact_campaign is not None:
                        exact_campaign.mark_candidate_result(
                            ghost_w,
                            ghost_h,
                            RUN_STATUS_UNKNOWN,
                            exact_safe_cuts=campaign_payload["exact_safe_cuts"],
                            proof_summary=campaign_payload["proof_summary"],
                            loaded_exact_safe_cut_count=campaign_payload["loaded_exact_safe_cut_count"],
                            generated_exact_safe_cut_count=campaign_payload[
                                "generated_exact_safe_cut_count"
                            ],
                        )
                        if not _skip_unknown_env:
                            exact_campaign.mark_campaign_stopped(
                                "candidate_returned_unknown",
                                status=RUN_STATUS_UNKNOWN,
                            )
                        exact_campaign.save()
                        telemetry_wave_index += 1
                        _append_wave_telemetry_best_effort(
                            project_root=project_root,
                            exact_campaign=exact_campaign,
                            wave_index=telemetry_wave_index,
                            candidate_results=[serial_candidate_result],
                            completed=True,
                            failure_reason=None,
                            dispatched_candidate_keys=[_candidate_key(selected_candidate)],
                            reset=reset_campaign_telemetry,
                        )
                        reset_campaign_telemetry = False
                        if not _skip_unknown_env:
                            _refresh_certified_delivery_outputs(
                                project_root=project_root,
                                exact_campaign=exact_campaign,
                                facility_pools=_pools,
                            )
                    if _skip_unknown_env:
                        continue
                    return RUN_STATUS_UNKNOWN, None
                if status == RUN_STATUS_UNPROVEN:
                    if exact_campaign is not None:
                        exact_campaign.mark_candidate_result(
                            ghost_w,
                            ghost_h,
                            RUN_STATUS_UNPROVEN,
                            exact_safe_cuts=campaign_payload["exact_safe_cuts"],
                            proof_summary=campaign_payload["proof_summary"],
                            loaded_exact_safe_cut_count=campaign_payload["loaded_exact_safe_cut_count"],
                            generated_exact_safe_cut_count=campaign_payload[
                                "generated_exact_safe_cut_count"
                            ],
                        )
                        exact_campaign.mark_campaign_stopped(
                            "candidate_returned_unproven",
                            status=RUN_STATUS_UNPROVEN,
                        )
                        exact_campaign.save()
                        telemetry_wave_index += 1
                        _append_wave_telemetry_best_effort(
                            project_root=project_root,
                            exact_campaign=exact_campaign,
                            wave_index=telemetry_wave_index,
                            candidate_results=[serial_candidate_result],
                            completed=True,
                            failure_reason=None,
                            dispatched_candidate_keys=[_candidate_key(selected_candidate)],
                            reset=reset_campaign_telemetry,
                        )
                        reset_campaign_telemetry = False
                        _refresh_certified_delivery_outputs(
                            project_root=project_root,
                            exact_campaign=exact_campaign,
                            facility_pools=_pools,
                        )
                    return RUN_STATUS_UNPROVEN, None
        exploratory_attempts = 0
        for area, ghost_w, ghost_h in candidates:
            if max_attempts is not None and exploratory_attempts >= max_attempts:
                return RUN_STATUS_UNKNOWN, None

            exploratory_attempts += 1
            status, solution = run_benders_for_ghost_rect(
                ghost_w=ghost_w,
                ghost_h=ghost_h,
                max_iterations=benders_max_iter,
                project_root=project_root,
                solve_mode=solve_mode,
                master_seconds=master_seconds,
                binding_seconds=binding_seconds,
                routing_seconds=routing_seconds,
                flow_seconds=flow_seconds,
                campaign=exact_campaign,
                disable_master_warm_start=bool(disable_master_warm_start),
            )
            if status == RUN_STATUS_CERTIFIED and solution is not None:
                return (
                    RUN_STATUS_CERTIFIED,
                    _build_certified_result(
                        candidate=(area, ghost_w, ghost_h),
                        solution=solution,
                        attempts=exploratory_attempts,
                        solve_mode=solve_mode,
                        campaign_resumed=False,
                        frontier_peak_size=0,
                        derived_pruned_candidates=0,
                        frontier_selection_policy=FRONTIER_SELECTION_POLICY,
                        frontier_candidate_metrics={},
                    ),
                )
            if status == RUN_STATUS_INFEASIBLE:
                continue
            if status == RUN_STATUS_UNKNOWN:
                return RUN_STATUS_UNKNOWN, None
            if status == RUN_STATUS_UNPROVEN:
                return RUN_STATUS_UNPROVEN, None
        return RUN_STATUS_INFEASIBLE, None
    finally:
        if parallel_worker_pool is not None:
            parallel_worker_pool.close()


run_outer_search.last_run_telemetry = None
run_outer_search.last_run_telemetry_error = None
run_outer_search.last_smt_mt_telemetry_error = None


if __name__ == "__main__":
    status, result = run_outer_search(max_attempts=3, solve_mode="exploratory", area_upper_bound=64)
    print("status=", status)
    if result:
        print(json.dumps(result["ghost_rect"], ensure_ascii=False))
