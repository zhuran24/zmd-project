"""M1 attach spike — 测量 #2 v2: cut 注入挡位 (修正合成负载有效性).

v1 教训 (2026-07-07):
- whole 型 99.99% 被拒 = 同 group 对称 instance 撞同 pose_idx -> alias
  fail-closed (exact_coordinate_master._conflict_pose_entries 的刻意纪律).
  v2 改为组内不放回采样 (贴生产: 真实解里同 group pose 互不相同).
- RSS 熔断在 batch 间才检查 -> v2 batch 内每 500 条检查.
- 50K 挡位砍掉 (v1 已证 10K 时 add 累计 ~20min, 超线性可由 4 点拟合).
- solve 全 censored (UNKNOWN) 没关系: 核心指标是 python 侧 wall 与
  solver 内部 wall 的劈叉 (proto 传输成本).
"""
import json
import random
import sys
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path(r"C:\claude pj\zmd-pj")
sys.path.insert(0, str(PROJECT_ROOT))

RSS_ABORT_MB = 14000.0
SOLVE_SECONDS = 60.0
GHOST = (12, 10)
SEED = 42


def rss_mb() -> float:
    try:
        import psutil

        return psutil.Process().memory_info().rss / 1e6
    except Exception:
        return -1.0


def emit(rec: dict) -> None:
    rec["rss_mb"] = round(rss_mb(), 1)
    print(json.dumps(rec, ensure_ascii=False), flush=True)


def solve_probe(model, scenario: str, cuts_total: int) -> None:
    t = time.perf_counter()
    status = model.solve(time_limit_seconds=SOLVE_SECONDS)
    wall = time.perf_counter() - t
    rec = {
        "event": "solve",
        "scenario": scenario,
        "cuts_total": cuts_total,
        "status_int": int(status),
        "python_wall_seconds": round(wall, 3),
    }
    solver = getattr(model, "_solver", None)
    if solver is not None:
        try:
            rec["solver_wall"] = round(float(solver.WallTime()), 3)
            rec["overhead_seconds"] = round(wall - float(solver.WallTime()), 3)
            rec["branches"] = int(solver.NumBranches())
        except Exception:
            pass
    emit(rec)


def main() -> None:
    rng = random.Random(SEED)
    from src.models.master_model import (
        MasterPlacementModel,
        load_generic_io_requirements_artifact,
        load_project_data,
    )

    instances, facility_pools, rules = load_project_data(
        PROJECT_ROOT, "certified_exact"
    )
    gio = load_generic_io_requirements_artifact(PROJECT_ROOT)
    pool_size = {ft: len(pool) for ft, pool in facility_pools.items()}

    t = time.perf_counter()
    core = MasterPlacementModel.build_exact_core(
        instances, facility_pools, rules, generic_io_requirements=gio
    )
    emit({"event": "core_built", "seconds": round(time.perf_counter() - t, 3)})

    probe = MasterPlacementModel.from_exact_core(core, GHOST)
    group_of = {
        str(iid): str(gid) for iid, gid in probe._group_id_by_instance.items()
    }
    del probe
    ft_of = {str(i["instance_id"]): str(i["facility_type"]) for i in instances}
    groups: dict = {}
    for iid in ft_of:
        groups.setdefault(group_of.get(iid, f"solo::{iid}"), []).append(iid)
    emit(
        {
            "event": "groups",
            "group_count": len(groups),
            "largest_group": max(len(v) for v in groups.values()),
        }
    )

    def synth_layout() -> dict:
        # 一个"伪解": 每 group 内 instance pose 互不相同 (贴生产真实解形态).
        cs: dict = {}
        for _gid, members in groups.items():
            ft = ft_of[members[0]]
            n = pool_size[ft]
            if n < len(members):
                continue
            picks = rng.sample(range(n), len(members))
            for iid, p in zip(members, picks):
                cs[iid] = p
        return cs

    def synth_whole(count: int) -> list:
        return [synth_layout() for _ in range(count)]

    def synth_pattern(count: int, k: int = 8) -> list:
        cuts = []
        for _ in range(count):
            layout = synth_layout()
            keys = rng.sample(sorted(layout), k)
            cuts.append({kk: layout[kk] for kk in keys})
        return cuts

    scenarios = [
        ("pattern_v2", [100, 900, 4000, 5000], synth_pattern),
        ("whole_v2", [100, 900, 4000], synth_whole),
    ]

    for scenario, batches, synth in scenarios:
        t = time.perf_counter()
        model = MasterPlacementModel.from_exact_core(core, GHOST)
        emit(
            {
                "event": "clone",
                "scenario": scenario,
                "seconds": round(time.perf_counter() - t, 3),
            }
        )
        solve_probe(model, scenario, 0)

        total = 0
        aborted = False
        for batch_n in batches:
            cuts = synth(batch_n)
            t = time.perf_counter()
            ok = 0
            fail = 0
            for i, cs in enumerate(cuts):
                if model.add_benders_cut(cs):
                    ok += 1
                else:
                    fail += 1
                if (i + 1) % 500 == 0 and rss_mb() > RSS_ABORT_MB:
                    emit(
                        {
                            "event": "abort_rss_inbatch",
                            "scenario": scenario,
                            "done_in_batch": i + 1,
                        }
                    )
                    aborted = True
                    break
            add_wall = time.perf_counter() - t
            total += ok
            emit(
                {
                    "event": "add_batch",
                    "scenario": scenario,
                    "batch": batch_n,
                    "added_ok": ok,
                    "added_fail": fail,
                    "cuts_total": total,
                    "add_wall_seconds": round(add_wall, 3),
                    "ms_per_cut": round(add_wall * 1000.0 / max(1, ok + fail), 3),
                }
            )
            if aborted:
                break
            solve_probe(model, scenario, total)
        del model
        emit({"event": "scenario_done", "scenario": scenario})

    emit({"event": "all_done"})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
