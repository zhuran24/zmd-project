"""批C 零头:PIC-5 多 rect 序列(§4 flip 前可做臂;owner 拍板④矩阵零头)。

harness 自建外循环复刻多 rect 序列:同一进程、同一 ExactSearchSession,串行多个
ghost rect(6×6→6×7→7×6),每 rect 完整 LBBD(master solve→binding cap 口径
fail-closed)+ per-rect CutLedgerWriter 连续段(rect N+1 的 genesis_context 携带
rect N 的 segment 路径+tail_hash=predecessor 血缘)。每 rect 结束后手动注入一次
attach 调用(与 injection_drill_runner.py 同款演习口径——cap 口径下 organic
触发不发生,注入让 step5→6→7→8 编排+预算+rejection taxonomy 在每个 rect 的
真 state 上真实跑一遍;注入点只有触发信号本身)。

诚实边界(§4 原文,写死防「harness 绿=生产层已验」):这是复刻,不是真生产
编排——真编排入口在 sealed 守卫层,certified 下 attach fail-closed;真 production
campaign 烧机验证属 flip 后 promotion 包⑤。

内存纪律:prod-scale master 一次一个(~60G 峰);rect 间顺序执行,前一 master
释放后再建下一个。

Usage:
  .venv/bin/python multi_rect_sequence_runner.py \
      --rects 6x6,6x7,7x6 --run-tag pic5_seq --out-dir /path/out/
"""
from __future__ import annotations

import argparse
import gc
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
    parser.add_argument(
        "--rects",
        default="6x6,6x7,7x6",
        help="comma list of WxH ghost rects, run in order",
    )
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
    parser.add_argument("--binding-alt-cap", type=int, default=200)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--ledger-root", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    rects = []
    for token in args.rects.split(","):
        w_str, _, h_str = token.strip().partition("x")
        rects.append((int(w_str), int(h_str)))

    # Clean-room env for construction(attach_host_runner.py 同款 sanctioned 形态)。
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

    args.out_dir.mkdir(parents=True, exist_ok=True)
    seq_path = args.out_dir / "sequence.json"
    sequence: dict = {
        "drill": "pic5_multi_rect_sequence",
        "rects": [list(r) for r in rects],
        "recipe": {
            "master_branching": args.master_branching,
            "probing_level": args.probing_level,
            "symmetry_level": args.symmetry_level,
            "workers": args.workers,
            "binding_alt_cap": args.binding_alt_cap,
        },
        "run_tag": args.run_tag,
        "cells": [],
    }

    def _dump() -> None:
        # 增量落盘(probe_15 硬崩全损教训)。
        seq_path.write_text(
            json.dumps(sequence, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    t0 = time.perf_counter()
    session = ExactSearchSession.create(PROJECT_ROOT, solve_mode="certified_exact")
    sequence["session_build_seconds"] = round(time.perf_counter() - t0, 3)
    _dump()

    ledger_root = args.ledger_root or Path(
        tempfile.mkdtemp(prefix="ce_pic5_ledger_")
    )
    predecessor_segment: str | None = None
    predecessor_tail_hash: str | None = None

    for rect_i, (ghost_w, ghost_h) in enumerate(rects, start=1):
        cell: dict = {
            "rect_index": rect_i,
            "ghost_rect": [ghost_w, ghost_h],
        }
        sequence["cells"].append(cell)
        _dump()

        t1 = time.perf_counter()
        master = MasterPlacementModel.from_exact_core(
            session.core, ghost_rect=(ghost_w, ghost_h)
        )
        cell["master_build_seconds"] = round(time.perf_counter() - t1, 3)

        ledger = CutLedgerWriter(
            ledger_root,
            scope_id=f"{args.run_tag}_rect{rect_i}_{ghost_w}x{ghost_h}",
            genesis_context={
                # PIC-5 连续段血缘:rect N+1 指向 rect N 的 segment。
                "predecessor_segment": predecessor_segment,
                "predecessor_tail_hash": predecessor_tail_hash,
                "recovery_reason": (
                    "fresh_start" if rect_i == 1 else "sequence_continuation"
                ),
                "ortools_version": ortools_version,
                "workers": args.workers,
                "exact_env_manifest_digest": _exact_env_manifest_digest(),
                "ghost_rect": [ghost_w, ghost_h],
                "drill": "pic5_multi_rect_sequence",
            },
        )
        cell["ledger_segment"] = str(ledger.path)

        scratch = Path(tempfile.mkdtemp(prefix="ce_pic5_cell_"))
        controller = LBBDController(
            master=master,
            cut_manager=CutManager(
                checkpoint_dir=scratch, solve_mode="certified_exact"
            ),
            project_root=PROJECT_ROOT,
            solve_mode="certified_exact",
            master_seconds=args.master_seconds,
            binding_seconds=args.binding_seconds,
            routing_seconds=args.routing_seconds,
            max_iterations=args.max_iterations,
            artifact_hashes=session.artifact_hashes,
            session=session,
            cut_ledger=ledger,
        )

        # rect 1 构建后才首次 export(sanctioned 形态);后续 rect 保持 on——
        # 真生产序列里开关是 campaign 级恒定的,这里复刻同款语义。
        os.environ["EXACT_CUT_FRAMEWORK_ATTACH"] = "1"

        t2 = time.perf_counter()
        try:
            status, solution = controller.run_with_status()
            cell["lbbd_status"] = str(status)
            cell["lbbd_has_solution"] = solution is not None
        except Exception as exc:  # noqa: BLE001
            cell["lbbd_status"] = "HARNESS_EXCEPTION"
            cell["lbbd_exception"] = f"{type(exc).__name__}: {exc}"
        cell["lbbd_wall_seconds"] = round(time.perf_counter() - t2, 3)
        _dump()

        # 演习注入(每 rect 一次;与 injection_drill_runner 同口径)。
        t3 = time.perf_counter()
        try:
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=1000 + rect_i
            )
            cell["drill_attached"] = attached
        except Exception as exc:  # noqa: BLE001
            cell["drill_exception"] = f"{type(exc).__name__}: {exc}"
        cell["drill_wall_seconds"] = round(time.perf_counter() - t3, 3)
        cell["attach_telemetry"] = (master.build_stats or {}).get(
            "cut_framework_attach_last"
        )
        cell["coordinate_framework_cut_count"] = (master.build_stats or {}).get(
            "coordinate_framework_cut_count", 0
        )

        try:
            ledger.seal()
        except Exception as exc:  # noqa: BLE001
            cell["ledger_seal_error"] = f"{type(exc).__name__}: {exc}"

        seg = read_segment(ledger.path)
        cell["ledger_read"] = {
            "status": seg.status,
            "events": len(seg.events),
            "event_kinds": sorted({e["event"] for e in seg.events}),
            "applied": sum(1 for e in seg.events if e["event"] == "APPLIED"),
            "tail_hash": seg.tail_hash,
        }
        predecessor_segment = str(ledger.path)
        predecessor_tail_hash = seg.tail_hash
        _dump()

        # 释放本 rect 的 master/controller 再建下一个(单跑内存纪律)。
        del controller, master, ledger
        gc.collect()

    print(json.dumps(sequence["cells"], ensure_ascii=False)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
