"""
Project main entry（项目主入口）.

默认模式：certified_exact（严格认证精确）
可选模式：exploratory（探索）
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.campaign_freeze_monitor import start_freeze_monitor
from src.runtime.process_priority import (
    apply_process_priority_if_configured,
    configure_process_priority_env,
)
from src.models.cp_sat_worker_config import format_exact_cp_sat_worker_profile
from src.models.exact_coordinate_master import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    EXACT_COORDINATE_MASTER_SEARCH_PROFILES,
)

# Threshold above which we treat a run as "production-class" and gate it
# behind the readiness check + start the freeze monitor. 24h = 1 day; the
# CachyOS rolling-release / pacman-freeze concern is real for any multi-hour
# run, but day+ runs are the case we genuinely don't want to auto-trash by
# accidentally skipping the gate.
CAMPAIGN_GATE_THRESHOLD_HOURS = 24.0



def run_solve(
    *,
    mode: str,
    max_attempts: Optional[int],
    start_area: Optional[int],
    master_seconds: float,
    binding_seconds: float,
    routing_seconds: float,
    flow_seconds: float,
    benders_max_iter: int,
    campaign_hours: float,
    resume_campaign: bool,
    min_side: int,
    max_aspect_ratio: Optional[float],
    area_upper_bound: Optional[int],
    parallel_processes: int,
    frontier_probe_mode: str,
    master_search_profile: str,
    disable_master_warm_start: bool,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    from src.search.outer_search import run_outer_search

    return run_outer_search(
        project_root=PROJECT_ROOT,
        solve_mode=mode,
        max_attempts=max_attempts,
        start_area=start_area,
        master_seconds=master_seconds,
        binding_seconds=binding_seconds,
        routing_seconds=routing_seconds,
        flow_seconds=flow_seconds,
        benders_max_iter=benders_max_iter,
        campaign_hours=campaign_hours,
        resume_campaign=resume_campaign,
        min_side=min_side,
        max_aspect_ratio=max_aspect_ratio,
        area_upper_bound=area_upper_bound,
        parallel_processes=parallel_processes,
        frontier_probe_mode=frontier_probe_mode,
        master_search_profile=master_search_profile,
        disable_master_warm_start=disable_master_warm_start,
    )



def run_visualization(result: Optional[Dict[str, Any]] = None) -> None:
    out_dir = PROJECT_ROOT / "data" / "solutions"
    out_dir.mkdir(parents=True, exist_ok=True)
    pools = _load_visualization_pools(PROJECT_ROOT)
    payload = _resolve_visualization_payload(PROJECT_ROOT, pools, result=result)
    if payload is None:
        print("⚠️ No optimal_blueprint.json or final_solution.json（没有可用输出），跳过可视化。")
        return

    solution = dict(payload.get("placement_solution", {}))
    ghost = payload.get("ghost_rect")

    try:
        from src.render.grid_visualizer import render_placement_heatmap

        render_placement_heatmap(
            solution,
            pools,
            ghost_rect=ghost,
            output_path=out_dir / "heatmap.png",
        )
    except Exception as exc:  # pragma: no cover - visualization is best-effort.
        print(f"⚠️ VIS heatmap（热力图） failed（失败）: {exc}")

    try:
        from src.render.lbbd_animator import render_flow_topology

        occupied = set()
        for sol in solution.values():
            tpl = str(sol.get("facility_type", ""))
            pose_idx = int(sol.get("pose_idx", 0))
            pool = pools.get(tpl, [])
            if 0 <= pose_idx < len(pool):
                for cell in pool[pose_idx].get("occupied_cells", []):
                    occupied.add((int(cell[0]), int(cell[1])))
        render_flow_topology(occupied, output_path=out_dir / "flow_topology.png")
    except Exception as exc:  # pragma: no cover - visualization is best-effort.
        print(f"⚠️ VIS topology（拓扑图） failed（失败）: {exc}")


def _load_visualization_pools(project_root: Path) -> Dict[str, Any]:
    from src.io.serializer import coerce_facility_pools_payload

    pools_path = project_root / "data" / "preprocessed" / "candidate_placements.json"
    if not pools_path.exists():
        return {}
    pools_payload = json.loads(pools_path.read_text(encoding="utf-8"))
    return dict(coerce_facility_pools_payload(pools_payload))


def _resolve_visualization_payload(
    project_root: Path,
    pools: Dict[str, Any],
    *,
    result: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    from src.io.serializer import recover_legacy_render_payload_from_blueprint
    from src.search.certified_surface import evaluate_certified_delivery_surface

    surface = evaluate_certified_delivery_surface(
        project_root=project_root,
        campaign_state=None,
        campaign_path=project_root / "data" / "checkpoints" / "exact_campaign_state.json",
    )
    if not surface.publishable:
        print(
            "⚠️ VIS certified surface（认证输出面） not publishable（不可发布），"
            f"跳过可视化: {surface.blocked_reason or 'unknown'}"
        )
        return None

    blueprint_payload = surface.optimal_blueprint_payload
    if pools and blueprint_payload is not None:
        try:
            return recover_legacy_render_payload_from_blueprint(
                blueprint_payload=blueprint_payload,
                facility_pools=pools,
            )
        except Exception as exc:  # pragma: no cover - fallback path is covered separately.
            print(
                "⚠️ VIS blueprint recover（蓝图恢复） failed（失败），"
                f"fallback to final_solution.json: {exc}"
            )

    final_solution_payload = surface.final_solution_payload
    return dict(final_solution_payload) if final_solution_payload is not None else None



def main() -> None:
    parser = argparse.ArgumentParser(description="终末地求解器")
    parser.add_argument("--vis", action="store_true", help="Only run visualization（只运行可视化）")
    parser.add_argument(
        "--mode",
        choices=["certified_exact", "exploratory"],
        default="certified_exact",
        help="Solve mode（求解模式），默认 certified_exact（严格认证精确）。",
    )
    parser.add_argument(
        "--exploratory",
        action="store_true",
        help="Backward-compatible flag（兼容旧参数）；等价于 --mode exploratory。",
    )
    parser.add_argument("--campaign-hours", type=float, default=168.0)
    parser.add_argument("--resume-campaign", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=None)
    parser.add_argument("--start-area", type=int, default=None)
    # 168h 长跑 default: master/binding/routing 1800s (30 min) — 之前 600s
    # 在 70x70 复杂 candidate 上频繁撞 UNKNOWN, candidate UNKNOWN 是 outer_search
    # terminal stop reason → campaign 短命退出. 1800s 给 master 更多 search 空间
    # 减少 UNKNOWN 概率, 配合 watchdog 自动重启机制让 168h budget 真用满.
    parser.add_argument("--master-seconds", type=float, default=1800.0)
    parser.add_argument("--binding-seconds", type=float, default=1800.0)
    parser.add_argument("--routing-seconds", type=float, default=1800.0)
    parser.add_argument("--flow-seconds", type=float, default=60.0)
    parser.add_argument("--benders-max-iter", type=int, default=30)
    parser.add_argument("--min-side", type=int, default=6)
    parser.add_argument("--max-aspect-ratio", type=float, default=None)
    parser.add_argument("--area-upper-bound", type=int, default=None)
    parser.add_argument("--parallel-processes", type=int, default=1)
    parser.add_argument(
        "--frontier-probe-mode",
        choices=["off", "auto"],
        default="off",
        help="Optional exact-safe probe insertion before the frontier sweep. Default: off.",
    )
    parser.add_argument(
        "--master-search-profile",
        choices=sorted(EXACT_COORDINATE_MASTER_SEARCH_PROFILES),
        default=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
        help="Exact coordinate master search profile. Default: exact_coordinate_guided_branching_v4.",
    )
    parser.add_argument(
        "--disable-master-warm-start",
        action="store_true",
        help="Diagnostic only: do not inject greedy/ghost master warm-start hints.",
    )
    parser.add_argument(
        "--process-priority",
        choices=["normal", "high"],
        default=None,
        help="Optional Windows process priority override for this repository process tree.",
    )
    parser.add_argument(
        "--skip-readiness-gate",
        action="store_true",
        help=(
            f"Bypass production readiness gate (pacman freeze + venv + preflight + ...) "
            f"that would otherwise BLOCK runs with --campaign-hours >= "
            f"{CAMPAIGN_GATE_THRESHOLD_HOURS}. For dry-runs / debug only."
        ),
    )
    args = parser.parse_args()

    if args.process_priority is not None:
        configure_process_priority_env(str(args.process_priority))
    apply_process_priority_if_configured(cli_value=args.process_priority)

    mode = "exploratory" if args.exploratory else args.mode

    if args.vis:
        run_visualization()
        return

    # Production-class run: gate-check before starting + start freeze monitor
    # daemon for the duration. The gate itself is implemented in
    # scripts/production_readiness_gate.py; we import its in-process API here.
    is_production_class = (
        mode == "certified_exact"
        and float(args.campaign_hours) >= CAMPAIGN_GATE_THRESHOLD_HOURS
    )
    if is_production_class and not args.skip_readiness_gate:
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from production_readiness_gate import gate_check  # noqa: E402
        gate = gate_check()
        print(gate.render())
        if gate.has_block:
            print(
                f"\nBLOCKED: campaign-hours={args.campaign_hours} >= "
                f"{CAMPAIGN_GATE_THRESHOLD_HOURS} 触发 production readiness gate. "
                f"修完阻塞项后重跑，或加 --skip-readiness-gate 强制（不推荐）。",
                file=sys.stderr,
            )
            sys.exit(1)

    if is_production_class:
        # Even with --skip-readiness-gate we still start the monitor — the
        # whole point is to alert if freeze is removed mid-run, regardless
        # of whether the user bypassed the startup gate.
        freeze_log = PROJECT_ROOT / "data" / "telemetry" / "campaign_freeze_monitor.log"
        start_freeze_monitor(log_path=freeze_log)

    print(format_exact_cp_sat_worker_profile())

    status, result = run_solve(
        mode=mode,
        max_attempts=args.max_attempts,
        start_area=args.start_area,
        master_seconds=args.master_seconds,
        binding_seconds=args.binding_seconds,
        routing_seconds=args.routing_seconds,
        flow_seconds=args.flow_seconds,
        benders_max_iter=args.benders_max_iter,
        campaign_hours=args.campaign_hours,
        resume_campaign=args.resume_campaign,
        min_side=args.min_side,
        max_aspect_ratio=args.max_aspect_ratio,
        area_upper_bound=args.area_upper_bound,
        parallel_processes=args.parallel_processes,
        frontier_probe_mode=args.frontier_probe_mode,
        master_search_profile=args.master_search_profile,
        disable_master_warm_start=bool(args.disable_master_warm_start),
    )

    print(f"status={status}")
    if result is not None:
        print(json.dumps(result.get("ghost_rect", result), ensure_ascii=False, indent=2))

    if status == "CERTIFIED" and result is not None:
        run_visualization(result)


if __name__ == "__main__":
    main()
