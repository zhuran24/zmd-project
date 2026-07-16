"""RAB-SEP ①′ 第三段: prod 注入演习 runner（单发 6×6 锚点，owner 预批）。

镜像批C 门6 drill_arm1 配方（fixed branching / probing 3 / symmetry 3 /
workers 1 / EXACT_B1_BINDING_ALT_CAP 200，见 .artifacts/batch_c_leftovers_
20260714/drill_arm1），**唯一变量 = EXACT_B1_ROUTING_AWARE_BINDING=1**
（certified-allowlisted，815a73e）。arm1 基线：566s 撞 F-6 踏车 →
UNKNOWN 无解、0 条 rab-sep 输出。

要量的三件事（01 文书 §8 唯一未验面）：
1. EMPTY_DOMAIN 触发率（[rab-sep] stdout 行 + controller 计数）；
2. cert core 分布（"[rab-sep] N certs, core size: ..." 行）；
3. master 吃细粒度 cut 后的收敛行为（逐迭代 wall/状态）。

哨兵语义顺带被 prod 数据检验：thin fallback forbidden 行出现 = 结构守卫
在 prod 形态真实触发（不是坏事，是 fail-closed 面被数据踩到的观测）。

调用形态与 CE runner 同款 sanctioned：session/master 构建后才跑 LBBD；
增量落盘（probe_15 硬崩全损教训）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, default=6)
    parser.add_argument("--ghost-h", type=int, default=6)
    parser.add_argument("--master-seconds", type=float, default=900.0)
    parser.add_argument("--binding-seconds", type=float, default=600.0)
    parser.add_argument("--routing-seconds", type=float, default=600.0)
    parser.add_argument("--max-iterations", type=int, default=6)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--binding-alt-cap", type=int, default=200)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    os.environ["EXACT_CP_SAT_WORKERS"] = str(args.workers)
    os.environ["EXACT_MASTER_SEARCH_BRANCHING"] = "fixed"
    os.environ["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = "3"
    os.environ["EXACT_MASTER_SYMMETRY_LEVEL"] = "3"
    os.environ["EXACT_B1_BINDING_ALT_CAP"] = str(args.binding_alt_cap)
    # 本臂唯一变量：RAB on（certified 启动守卫必须放行 = 收编的 prod 级证明）
    os.environ["EXACT_B1_ROUTING_AWARE_BINDING"] = "1"

    from src.models.cut_manager import CutManager
    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import ExactSearchSession, LBBDController

    result: dict = {
        "drill": "rab_sep_stage3_prod_point",
        "ghost_rect": [args.ghost_w, args.ghost_h],
        "recipe": {
            "master_branching": "fixed",
            "probing_level": 3,
            "symmetry_level": 3,
            "workers": args.workers,
            "binding_alt_cap": args.binding_alt_cap,
            "max_iterations": args.max_iterations,
        },
        "rab_env": os.environ["EXACT_B1_ROUTING_AWARE_BINDING"],
        "baseline_arm": ".artifacts/batch_c_leftovers_20260714/drill_arm1 (RAB off, 566s treadmill UNKNOWN)",
        "run_tag": args.run_tag,
    }

    def _dump() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    t0 = time.perf_counter()
    session = ExactSearchSession.create(PROJECT_ROOT, solve_mode="certified_exact")
    result["session_build_seconds"] = round(time.perf_counter() - t0, 3)
    _dump()

    t1 = time.perf_counter()
    master = MasterPlacementModel.from_exact_core(
        session.core, ghost_rect=(args.ghost_w, args.ghost_h)
    )
    result["master_build_seconds"] = round(time.perf_counter() - t1, 3)
    _dump()

    scratch = Path(tempfile.mkdtemp(prefix="rab_drill_cell_"))
    controller = LBBDController(
        master=master,
        cut_manager=CutManager(checkpoint_dir=scratch, solve_mode="certified_exact"),
        project_root=PROJECT_ROOT,
        solve_mode="certified_exact",
        master_seconds=args.master_seconds,
        binding_seconds=args.binding_seconds,
        routing_seconds=args.routing_seconds,
        max_iterations=args.max_iterations,
        artifact_hashes=session.artifact_hashes,
        session=session,
    )

    t2 = time.perf_counter()
    try:
        status, solution = controller.run_with_status()
        result["lbbd_status"] = str(status)
        result["lbbd_has_solution"] = solution is not None
    except Exception as exc:  # noqa: BLE001 — record, don't crash the driver
        result["lbbd_status"] = "HARNESS_EXCEPTION"
        result["lbbd_exception"] = f"{type(exc).__name__}: {exc}"
    result["lbbd_wall_seconds"] = round(time.perf_counter() - t2, 3)

    # RAB / cut 计数遥测（防御性 getattr——属性名以 815a73e 实态为准）
    for attr in (
        "_fine_grained_exact_safe_cut_count",
        "_binding_domain_empty_cut_count",
    ):
        result[attr.lstrip("_")] = getattr(controller, attr, None)
    last_summary = getattr(controller, "last_proof_summary", None)
    if isinstance(last_summary, dict):
        result["last_proof_summary_scalars"] = {
            k: v
            for k, v in last_summary.items()
            if isinstance(v, (str, int, float, bool)) or v is None
        }
    _dump()
    print(
        json.dumps(
            {
                "lbbd_status": result.get("lbbd_status"),
                "wall": result.get("lbbd_wall_seconds"),
                "fine_grained": result.get("fine_grained_exact_safe_cut_count"),
                "empty_domain_cuts": result.get("binding_domain_empty_cut_count"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
