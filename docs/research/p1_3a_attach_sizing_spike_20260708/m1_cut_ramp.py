"""M1 attach spike — 测量 #2: cut 注入挡位 (add wall / solve wall / RSS).

只读消费生产入口, 不写仓库文件. 合成负载贴生产形态:
- whole_narrow: whole-layout 型 nogood (~266 literal/条, 每 instance 从固定
  3-pose 窄池采样, 模拟相邻迭代 master 解 pose 高复用) — 生产唯一真实 cut 形态.
- pattern_narrow: 8-literal 短 cut (F5 pattern nogood 型, F1-F9 literal family
  接入后的主形态).
- wide_literal_probe: 266-literal x 全池随机采样, 量 presence literal 惰性
  创建的最坏成本 (只 500 条).

每挡位 emit 一行 JSON (增量, 中途死也有数据). RSS > 16GB 熔断.
solve 预算 60s = 生产 master 每轮默认预算, 退化直接同轴可比.
"""
import json
import random
import sys
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path(r"C:\claude pj\zmd-pj")
sys.path.insert(0, str(PROJECT_ROOT))

RSS_ABORT_MB = 16000.0
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


def solve_probe(model, label: str, scenario: str, cuts_total: int) -> None:
    t = time.perf_counter()
    status = model.solve(time_limit_seconds=SOLVE_SECONDS)
    wall = time.perf_counter() - t
    rec = {
        "event": "solve",
        "scenario": scenario,
        "label": label,
        "cuts_total": cuts_total,
        "status_int": int(status),
        "solve_wall_seconds": round(wall, 3),
    }
    try:
        from ortools.sat.python import cp_model

        names = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "MODEL_INVALID",
            cp_model.UNKNOWN: "UNKNOWN",
        }
        rec["status"] = names.get(int(status), str(status))
    except Exception:
        pass
    solver = getattr(model, "_solver", None)
    if solver is not None:
        try:
            rec["branches"] = int(solver.NumBranches())
            rec["conflicts"] = int(solver.NumConflicts())
            rec["solver_wall"] = round(float(solver.WallTime()), 3)
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
    inst_list = [
        (str(inst["instance_id"]), str(inst["facility_type"])) for inst in instances
    ]
    emit({"event": "loaded", "instances": len(inst_list)})

    t = time.perf_counter()
    core = MasterPlacementModel.build_exact_core(
        instances, facility_pools, rules, generic_io_requirements=gio
    )
    emit({"event": "core_built", "seconds": round(time.perf_counter() - t, 3)})

    narrow = {
        iid: rng.sample(range(pool_size[ft]), min(3, pool_size[ft]))
        for iid, ft in inst_list
    }

    def synth_whole(n: int, wide: bool = False) -> list:
        cuts = []
        for _ in range(n):
            if wide:
                cs = {
                    iid: rng.randrange(pool_size[ft]) for iid, ft in inst_list
                }
            else:
                cs = {iid: rng.choice(narrow[iid]) for iid, _ft in inst_list}
            cuts.append(cs)
        return cuts

    def synth_pattern(n: int, k: int = 8) -> list:
        cuts = []
        for _ in range(n):
            chosen = rng.sample(inst_list, k)
            cs = {iid: rng.choice(narrow[iid]) for iid, _ft in chosen}
            cuts.append(cs)
        return cuts

    scenarios = [
        ("whole_narrow", [100, 900, 9000], synth_whole),
        ("pattern_narrow", [1000, 9000, 40000], lambda n: synth_pattern(n)),
        ("wide_literal_probe", [500], lambda n: synth_whole(n, wide=True)),
    ]

    baseline_done = False
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
        if not baseline_done:
            solve_probe(model, "baseline_0cut", scenario, 0)
            baseline_done = True

        total = 0
        for batch_n in batches:
            cuts = synth(batch_n)
            t = time.perf_counter()
            ok = 0
            fail = 0
            for cs in cuts:
                if model.add_benders_cut(cs):
                    ok += 1
                else:
                    fail += 1
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
                    "ms_per_cut": round(add_wall * 1000.0 / max(1, batch_n), 3),
                }
            )
            if rss_mb() > RSS_ABORT_MB:
                emit({"event": "abort_rss", "scenario": scenario})
                return
            solve_probe(model, f"after_{total}", scenario, total)
        del model
        emit({"event": "scenario_done", "scenario": scenario})

    emit({"event": "all_done"})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
