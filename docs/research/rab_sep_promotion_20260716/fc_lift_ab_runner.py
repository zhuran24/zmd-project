"""front-clear lift 阶梯4/5：同 revision 独立进程 OFF/ON A/B runner（单发 6×6）。

镜像 ③段 rab_drill_runner 配方（fixed/probing3/symmetry3/workers1/alt_cap200/
RAB=1），**唯一变量 = EXACT_MASTER_FRONT_CLEAR_LIFT**（--lift on|off）。
两臂必须在同一 post-change revision、各自独立进程跑（审查 F-06）。

验收判据（doc 04 v2 §4.3，raw 口径）：
- lift ON 臂：master 产 FEASIBLE incumbent 并进入 binding build 时，
  `[front-clear] raw ... lift_scope=` 必须逐迭代严格 = 0（正值=lift 失败）；
  master 未到 binding（INFEASIBLE/UNKNOWN）= NOT_EVALUATED，不判绿。
- accepted-cut counter 只作诊断。

corpus（阶梯3 输入）：逐迭代 master 布局快照（wrap extract_solution）+
layout sha + controller cert/cut 遥测——离线结构 checker 可从布局重建
binding raw 事件，含 RAB-nonempty 负控。

内存纪律：调用方用 systemd-run --user MemoryMax/MemorySwapMax 包裹本进程
（1s 采样只是观测不是保护，R16）；一次只跑一个 prod-scale solve。
"""

from __future__ import annotations

import argparse
import hashlib
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
    parser.add_argument("--lift", choices=["on", "off"], required=True)
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
    # 探针杠杆（默认 = 镜像批C drill_arm1 配方；判别配方绑定 vs 结构性时用）
    # 注意 "default" = 不设 env——exact 模式缺省仍 fixed（master_model.py:11553），
    # 不是有效杠杆（探针2 教训）；真换搜索策略用 automatic/portfolio（env 合法值域）。
    parser.add_argument(
        "--branching",
        choices=["fixed", "default", "automatic", "portfolio"],
        default="fixed",
    )
    parser.add_argument("--master-workers", type=int, default=0,
                        help=">0 时设 EXACT_MASTER_CP_SAT_WORKERS（stage 专属，全局 workers 不动）")
    parser.add_argument("--master-presolve", choices=["unset", "off"], default="unset",
                        help="off = 设 EXACT_MASTER_CP_MODEL_PRESOLVE=0（element 走原生传播器，"
                             "诊断 presolve 展开病灶）")
    parser.add_argument("--solution-hint-file", type=Path, default=None,
                        help="两段式 master 段2（牌B）：witness 构造器结果 JSON，"
                             "其 solution {iid:{facility_type,pose_idx}} 经 "
                             "apply_solution_hint 注入 master（AddHint 仅引导搜索，"
                             "不影响可行域/正确性；pole 槽不打 0 hint）")
    args = parser.parse_args()

    os.environ["EXACT_CP_SAT_WORKERS"] = str(args.workers)
    if args.branching == "default":
        os.environ.pop("EXACT_MASTER_SEARCH_BRANCHING", None)
    else:
        os.environ["EXACT_MASTER_SEARCH_BRANCHING"] = args.branching
    if args.master_workers > 0:
        os.environ["EXACT_MASTER_CP_SAT_WORKERS"] = str(args.master_workers)
    if args.master_presolve == "off":
        os.environ["EXACT_MASTER_CP_MODEL_PRESOLVE"] = "0"
    os.environ["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = "3"
    os.environ["EXACT_MASTER_SYMMETRY_LEVEL"] = "3"
    os.environ["EXACT_B1_BINDING_ALT_CAP"] = str(args.binding_alt_cap)
    os.environ["EXACT_B1_ROUTING_AWARE_BINDING"] = "1"
    if args.lift == "on":
        os.environ["EXACT_MASTER_FRONT_CLEAR_LIFT"] = "1"
    else:
        os.environ.pop("EXACT_MASTER_FRONT_CLEAR_LIFT", None)

    from src.models.cut_manager import CutManager
    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import ExactSearchSession, LBBDController

    result: dict = {
        "drill": "front_clear_lift_ab_single_anchor",
        "arm": f"lift_{args.lift}",
        "ghost_rect": [args.ghost_w, args.ghost_h],
        "recipe": {
            "master_branching": args.branching,
            "master_workers": args.master_workers or args.workers,
            "probing_level": 3,
            "symmetry_level": 3,
            "workers": args.workers,
            "binding_alt_cap": args.binding_alt_cap,
            "max_iterations": args.max_iterations,
            "rab": 1,
            "master_presolve": args.master_presolve,
        },
        "run_tag": args.run_tag,
        "layout_snapshots": [],
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
    result["front_clear_lift_stats"] = {
        k: v
        for k, v in dict(master.build_stats.get("front_clear_lift", {})).items()
        if k != "demands_by_operation"
    }
    result["master_interval_count"] = master.build_stats.get("master_interval_count")
    _dump()

    # 牌B 段2：段1 装箱解注入为 solution hint（研究级诊断包装，零 sealed 行为
    # 改动——apply_solution_hint 是 delegate 既有公开方法，AddHint 语义只引导
    # 搜索不改可行域）
    if args.solution_hint_file is not None:
        hint_payload = json.loads(
            args.solution_hint_file.read_text(encoding="utf-8")
        )
        hint_map = {
            str(iid): int(entry["pose_idx"])
            for iid, entry in dict(hint_payload.get("solution", {})).items()
        }
        delegate = getattr(master, "_coordinate_delegate", None)
        if delegate is None or not hasattr(delegate, "apply_solution_hint"):
            result["solution_hint_stats"] = {
                "error": "coordinate delegate 无 apply_solution_hint"
            }
        else:
            hint_stats = delegate.apply_solution_hint(
                hint_map, hint_inactive_residual_optionals=False
            )
            result["solution_hint_stats"] = {
                "hint_entries": len(hint_map),
                **{k: v for k, v in dict(hint_stats).items()
                   if isinstance(v, (int, str, bool))},
            }
        _dump()

    # corpus：逐迭代布局快照（阶梯3 离线结构 checker 的输入；诊断包装，
    # 不改任何 sealed 行为——原方法原样调用、返回值原样透传）
    corpus_dir = args.out.parent / f"{args.run_tag}_layouts"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    original_extract = master.extract_solution

    def _capturing_extract(*e_args, **e_kwargs):
        solution = original_extract(*e_args, **e_kwargs)
        try:
            payload = json.dumps(
                solution, ensure_ascii=False, sort_keys=True, default=str
            )
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            seq = len(result["layout_snapshots"])
            (corpus_dir / f"layout_{seq:03d}_{digest[:12]}.json").write_text(
                payload, encoding="utf-8"
            )
            result["layout_snapshots"].append({"seq": seq, "sha256": digest})
            _dump()
        except Exception as exc:  # noqa: BLE001 — corpus 失败不影响 drill 本体
            result.setdefault("corpus_errors", []).append(
                f"{type(exc).__name__}: {exc}"
            )
        return solution

    master.extract_solution = _capturing_extract  # type: ignore[method-assign]

    scratch = Path(tempfile.mkdtemp(prefix="fc_lift_ab_"))
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

    # master 侧最后一次 solve 的遥测（wall/status/参数——定位 cap 与实耗差额）
    last_solve = dict(master.build_stats.get("last_solve", {}) or {})
    result["master_last_solve_scalars"] = {
        k: v
        for k, v in last_solve.items()
        if isinstance(v, (str, int, float, bool)) or v is None
    }
    for attr in (
        "_fine_grained_exact_safe_cut_count",
        "_binding_domain_empty_cut_count",
        "_front_clear_raw_empty_by_iteration",
    ):
        value = getattr(controller, attr, None)
        result[attr.lstrip("_")] = value if not callable(value) else None

    raw_iters = result.get("front_clear_raw_empty_by_iteration") or []
    if args.lift == "on":
        if not raw_iters:
            result["acceptance_raw_scope_zero"] = "NOT_EVALUATED"
        else:
            result["acceptance_raw_scope_zero"] = (
                "PASS"
                if all(int(item.get("raw_lift_scope", -1)) == 0 for item in raw_iters)
                else "FAIL"
            )
    _dump()
    print(
        json.dumps(
            {
                "arm": result["arm"],
                "lbbd_status": result.get("lbbd_status"),
                "wall": result.get("lbbd_wall_seconds"),
                "empty_domain_cuts": result.get("binding_domain_empty_cut_count"),
                "raw_by_iteration": raw_iters,
                "acceptance": result.get("acceptance_raw_scope_zero"),
                "layouts": len(result.get("layout_snapshots", [])),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
