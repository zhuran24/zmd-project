"""批C 零头:门6「触发>0」prod 层注入式演习点(owner 07-13 拍板②第二条腿)。

背景:cap 口径矩阵(§2,已收官)双臂 cut 均 0——机制上 binding 在 cap 口径下是
ALT_CAP_REACHED→UNKNOWN(fail-closed),从不产生 "binding_infeasible" 触发信号,
attach 链根本不被调用(双零=空对照,门6 rev3 预警场景)。演习口径(拍板②):
手动触发信号 + 流水线逐环验真。

本 driver = attach_host_runner.py 的演习变体(clean-room 构建纪律逐字同款):
1. 真 session + 真 prod-scale master + 真 LBBD run_with_status()(master solve 到
   OPTIMAL 选定 ghost anchor;binding 走 cap 口径快速 fail-closed);
2. run 结束后在同一 controller 上手动调 _maybe_attach_framework_cuts(
   trigger="binding_infeasible")——这是唯一注入点(触发信号);state 构建
   (_build_cut_framework_state → _selected_ghost_context)、4 族 oracle、typed
   registry → resolver → step_8 → typed_apply → master lowering、ledger 全部真实。
3. 逐环采证:attach 返回值、cut_framework_attach_last telemetry(attached_by_family/
   rejected taxonomy/shadow)、ledger 事件、master coordinate_framework_cut_count。

臂设计(D-13 rollback 演练与演习共用本 driver):
  臂1 全族:--enabled-families 缺省(全四族);
  臂2 关族:--enabled-families 去掉臂1 中有产出的族(无产出则按 spec 08 D-13 关
  region_capacity),对照「被关族被编排层拒之、其余不变」。

诚实边界(与 §4 PIC-5 同款纪律):触发信号是注入的(演习口径,owner 已裁可作
门6「触发>0」格证据);oracle 在真 state 上的 generated=0 也是有效结论的一部分
(如实记录,不构造溢出)。运行内存纪律:prod-scale master 一次一个(~60G 峰)。

Usage:
  .venv/bin/python injection_drill_runner.py --ghost-w 6 --ghost-h 6 \
      --out /path/cell.json --run-tag drill_arm1 [--enabled-families a,b,c]
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


def _exact_env_manifest_digest() -> str:
    pairs = sorted(
        (k, v) for k, v in os.environ.items() if k.startswith("EXACT_")
    )
    return hashlib.sha256(
        json.dumps(pairs, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, required=True)
    parser.add_argument("--ghost-h", type=int, required=True)
    parser.add_argument("--master-seconds", type=float, default=900.0)
    parser.add_argument("--binding-seconds", type=float, default=600.0)
    parser.add_argument("--routing-seconds", type=float, default=600.0)
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--master-branching",
        choices=("fixed", "automatic", "portfolio"),
        default="fixed",
    )
    parser.add_argument("--probing-level", type=int, default=3)
    parser.add_argument("--symmetry-level", type=int, default=3)
    parser.add_argument(
        "--binding-alt-cap",
        type=int,
        default=200,
        help="cap 口径快速 fail-closed(演习重点在 attach 链非 binding 穷尽)",
    )
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--ledger-root", type=Path, default=None)
    # D-1 waiver oracle 重生成开销测量:restart 链两段(段B 带血缘;restart
    # 重取资格=重生成、ledger 永不作 cut 来源——比较两段 drill wall 即开销)。
    parser.add_argument("--predecessor-segment", default=None)
    parser.add_argument("--predecessor-tail-hash", default=None)
    parser.add_argument("--recovery-reason", default="fresh_start")
    parser.add_argument(
        "--enabled-families",
        default=None,
        help="comma list(缺省全四族);臂2 rollback 演练关族用",
    )
    parser.add_argument(
        "--drill-iterations",
        type=int,
        default=1,
        help="手动注入 attach 调用次数(>1 观察 dedup pool per-master-build 语义)",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    # Clean-room env for construction(attach env 只能在构建后 export;
    # attach_host_runner.py 同款 sanctioned 形态)。
    os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
    os.environ["EXACT_CP_SAT_WORKERS"] = str(args.workers)
    os.environ["EXACT_MASTER_SEARCH_BRANCHING"] = args.master_branching
    os.environ["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = str(args.probing_level)
    os.environ["EXACT_MASTER_SYMMETRY_LEVEL"] = str(args.symmetry_level)
    os.environ["EXACT_B1_BINDING_ALT_CAP"] = str(args.binding_alt_cap)

    from src.cuts.ledger import CutLedgerWriter, read_segment
    from src.models.cut_manager import CutManager
    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import ExactSearchSession, LBBDController

    try:
        from importlib.metadata import version as _pkg_version

        ortools_version = _pkg_version("ortools")
    except Exception:  # noqa: BLE001 — telemetry only
        ortools_version = "unknown"

    result: dict = {
        "drill": "gate6_injection_prod_point",
        "ghost_rect": [args.ghost_w, args.ghost_h],
        "recipe": {
            "master_branching": args.master_branching,
            "probing_level": args.probing_level,
            "symmetry_level": args.symmetry_level,
            "workers": args.workers,
            "binding_alt_cap": args.binding_alt_cap,
        },
        "enabled_families": args.enabled_families,
        "run_tag": args.run_tag,
    }

    def _dump() -> None:
        # 增量落盘(probe_15 硬崩全损教训):每阶段写一次。
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

    ledger_root = args.ledger_root or Path(tempfile.mkdtemp(prefix="ce_drill_ledger_"))
    ledger = CutLedgerWriter(
        ledger_root,
        scope_id=args.run_tag,
        genesis_context={
            "predecessor_segment": args.predecessor_segment,
            "predecessor_tail_hash": args.predecessor_tail_hash,
            "recovery_reason": args.recovery_reason,
            "ortools_version": ortools_version,
            "workers": args.workers,
            "exact_env_manifest_digest": _exact_env_manifest_digest(),
            "ghost_rect": [args.ghost_w, args.ghost_h],
            "drill": "gate6_injection_prod_point",
        },
    )
    result["ledger_segment"] = str(ledger.path)

    enabled = (
        [name.strip() for name in args.enabled_families.split(",") if name.strip()]
        if args.enabled_families
        else None
    )
    scratch = Path(tempfile.mkdtemp(prefix="ce_drill_cell_"))
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
        enabled_cut_families=enabled,
        cut_ledger=ledger,
    )

    # Only NOW may the attach switch appear(runner 同款 sanctioned 形态)。
    os.environ["EXACT_CUT_FRAMEWORK_ATTACH"] = "1"

    # 阶段 1:真流程(master solve → binding cap 口径 fail-closed)。
    t2 = time.perf_counter()
    try:
        status, solution = controller.run_with_status()
        result["lbbd_status"] = str(status)
        result["lbbd_has_solution"] = solution is not None
    except Exception as exc:  # noqa: BLE001 — record, don't crash the driver
        result["lbbd_status"] = "HARNESS_EXCEPTION"
        result["lbbd_exception"] = f"{type(exc).__name__}: {exc}"
    result["lbbd_wall_seconds"] = round(time.perf_counter() - t2, 3)
    result["organic_attach_last"] = (master.build_stats or {}).get(
        "cut_framework_attach_last"
    )
    _dump()

    # 阶段 2:注入触发信号(演习唯一注入点)——同一 controller、solved master、
    # 真 state builder / oracle / typed 链 / ledger。
    drill_rounds = []
    for drill_i in range(1, args.drill_iterations + 1):
        t3 = time.perf_counter()
        round_rec: dict = {"drill_call": drill_i}
        try:
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible",
                iteration=1000 + drill_i,  # 与真实迭代号明确区隔
            )
            round_rec["attached"] = attached
        except Exception as exc:  # noqa: BLE001
            round_rec["exception"] = f"{type(exc).__name__}: {exc}"
        round_rec["wall_seconds"] = round(time.perf_counter() - t3, 3)
        stats = (master.build_stats or {}).get("cut_framework_attach_last")
        round_rec["attach_telemetry"] = stats
        drill_rounds.append(round_rec)
        result["drill_rounds"] = drill_rounds
        _dump()

    try:
        ledger.seal()
    except Exception as exc:  # noqa: BLE001
        result["ledger_seal_error"] = f"{type(exc).__name__}: {exc}"

    result["coordinate_framework_cut_count"] = (master.build_stats or {}).get(
        "coordinate_framework_cut_count", 0
    )

    seg = read_segment(ledger.path)
    result["ledger_read"] = {
        "status": seg.status,
        "events": len(seg.events),
        "event_kinds": sorted({e["event"] for e in seg.events}),
        "applied": sum(1 for e in seg.events if e["event"] == "APPLIED"),
        "rejected": sum(1 for e in seg.events if e["event"] == "REJECTED"),
        "reject_reasons": sorted(
            {
                str(e.get("reason_code"))
                for e in seg.events
                if e["event"] == "REJECTED"
            }
        ),
        "tail_hash": seg.tail_hash,
    }
    _dump()
    print(json.dumps({"drill_rounds": drill_rounds, "ledger_read": result["ledger_read"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
