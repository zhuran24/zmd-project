"""P2 #14 evaluator v1 — baseline + hint round reader/runner.

阶段:
  v1.0: 验证 jsonl dump 能 reconstruct PortBindingModel + solve (baseline only)
  v1.1: 加 hint round — 同一 dump 跑两遍, 第二遍把第一遍的 var→value 当 hint
        注入, 算 T_base / T_hint score

不改 src/models/binding_subproblem.py — hint 通过 model.model.AddHint() 外部
注入. evaluator 是 scaffolding, master chain 上的核心文件不动.

下一步 (v2): 加大规模 production data (D 落地之后), 训一个真预测模型.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ortools.sat.python import cp_model
from src.models.binding_subproblem import PortBindingModel


def load_facility_pools(project_root: Path) -> dict:
    data = json.loads(
        (project_root / "data" / "preprocessed" / "candidate_placements.json").read_text(
            encoding="utf-8"
        )
    )
    return data["facility_pools"]


def load_dumps(jsonl_path: Path, limit: int | None = None):
    with jsonl_path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            yield json.loads(line)


def build_binding_model(dump: dict, facility_pools: dict, project_root: Path) -> PortBindingModel:
    model = PortBindingModel(
        placement_solution=dump["placement_solution"],
        facility_pools=facility_pools,
        instances=dump["instances"],
        required_generic_outputs=dump["required_generic_outputs"],
        required_generic_inputs=dump["required_generic_inputs"],
        project_root=project_root,
    )
    model.build()
    return model


def extract_var_values(model: PortBindingModel, solver: cp_model.CpSolver) -> Dict[Tuple[str, ...], int]:
    """提取 binding/generic_input/generic_output 三类变量的 var→value 映射.

    key 是 (var_namespace, slot_id, commodity_or_idx) 三元组, value 是 int (BoolVar 0/1).
    """
    values: Dict[Tuple[str, ...], int] = {}
    for slot_id, commodity_dict in model.generic_output_vars.items():
        for commodity, var in commodity_dict.items():
            values[("generic_output", str(slot_id), str(commodity))] = int(solver.Value(var))
    for slot_id, commodity_dict in model.generic_input_vars.items():
        for commodity, var in commodity_dict.items():
            values[("generic_input", str(slot_id), str(commodity))] = int(solver.Value(var))
    for instance_id, idx_dict in model.binding_vars.items():
        for idx, var in idx_dict.items():
            values[("binding", str(instance_id), str(idx))] = int(solver.Value(var))
    return values


def inject_hint(model: PortBindingModel, hint_values: Dict[Tuple[str, ...], int]) -> int:
    """把 var→value 映射作为 hint 注入新 model. 返回成功注入的 var 数."""
    n_injected = 0
    for slot_id, commodity_dict in model.generic_output_vars.items():
        for commodity, var in commodity_dict.items():
            key = ("generic_output", str(slot_id), str(commodity))
            if key in hint_values:
                model.model.AddHint(var, hint_values[key])
                n_injected += 1
    for slot_id, commodity_dict in model.generic_input_vars.items():
        for commodity, var in commodity_dict.items():
            key = ("generic_input", str(slot_id), str(commodity))
            if key in hint_values:
                model.model.AddHint(var, hint_values[key])
                n_injected += 1
    for instance_id, idx_dict in model.binding_vars.items():
        for idx, var in idx_dict.items():
            key = ("binding", str(instance_id), str(idx))
            if key in hint_values:
                model.model.AddHint(var, hint_values[key])
                n_injected += 1
    return n_injected


def run_round(model: PortBindingModel, time_limit_seconds: float) -> Tuple[float, str, cp_model.CpSolver]:
    """跑一次 solve, 返回 (wall_time, status_name, solver)."""
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    # 跟 PortBindingModel.solve() 内部一致的 num_workers / search_branching
    # 不在这里 force 用 default 是因为 evaluator 测的是 hint vs no-hint 的 *相对*
    # 时间, 用统一 default 设置足够对照.
    t0 = time.perf_counter()
    status = solver.Solve(model.model)
    elapsed = time.perf_counter() - t0
    return elapsed, solver.StatusName(status), solver


def main(limit: int = 10, with_hint: bool = False):
    project_root = PROJECT_ROOT
    facility_pools = load_facility_pools(project_root)
    dumps_path = project_root / "data" / "telemetry" / "binding_dumps.jsonl"

    results = []
    print(f"Reading {dumps_path}, limit={limit}, with_hint={with_hint}")

    for i, dump in enumerate(load_dumps(dumps_path, limit=limit)):
        n_placements = len(dump.get("placement_solution", {}))
        n_instances = len(dump.get("instances", []))
        tl = dump.get("time_limit_seconds", 0)
        print(
            f"\n=== dump {i+1} | placements={n_placements} instances={n_instances} time_limit={tl}s ==="
        )

        try:
            # baseline round
            model_a = build_binding_model(dump, facility_pools, project_root)
            t_base, status_a, solver_a = run_round(model_a, tl)
            print(f"  baseline:  {t_base*1000:7.3f}ms  status={status_a}")

            if i == 0:
                print(f"  --- model API inspect (first dump) ---")
                print(f"  generic_output_vars: {len(model_a.generic_output_vars)} slots")
                print(f"  generic_input_vars: {len(model_a.generic_input_vars)} slots")
                print(f"  binding_vars: {len(model_a.binding_vars)} instances")

            row = {"i": i, "t_base_ms": t_base * 1000, "status_base": status_a}

            if with_hint and status_a in {"OPTIMAL", "FEASIBLE"}:
                # 提取 baseline 解作为 hint
                hint_values = extract_var_values(model_a, solver_a)
                # 重建 model + 注入 hint
                model_b = build_binding_model(dump, facility_pools, project_root)
                n_inj = inject_hint(model_b, hint_values)
                t_hint, status_b, _ = run_round(model_b, tl)
                ratio = t_base / t_hint if t_hint > 0 else float("inf")
                print(
                    f"  +hint:     {t_hint*1000:7.3f}ms  status={status_b}  "
                    f"hint_vars={n_inj}  ratio={ratio:.2f}x"
                )
                row.update({"t_hint_ms": t_hint * 1000, "status_hint": status_b,
                            "hint_vars": n_inj, "ratio": ratio})

            results.append(row)

        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            continue

    # summary
    print(f"\n=== summary ===")
    print(f"实例数: {len(results)}")
    if results:
        from collections import Counter
        base_times = [r["t_base_ms"] for r in results]
        print(f"baseline ms: avg={sum(base_times)/len(base_times):.3f} "
              f"min={min(base_times):.3f} max={max(base_times):.3f}")
        print(f"status: {dict(Counter(r['status_base'] for r in results))}")

        if with_hint and any("t_hint_ms" in r for r in results):
            hint_rows = [r for r in results if "t_hint_ms" in r]
            hint_times = [r["t_hint_ms"] for r in hint_rows]
            ratios = [r["ratio"] for r in hint_rows]
            print(f"\n+hint ms: avg={sum(hint_times)/len(hint_times):.3f} "
                  f"min={min(hint_times):.3f} max={max(hint_times):.3f}")
            print(f"ratio (T_base/T_hint): avg={sum(ratios)/len(ratios):.2f}x "
                  f"min={min(ratios):.2f}x max={max(ratios):.2f}x")
            # 注: fixture 数据 baseline 已 0.001-0.005s, hint 加速比可能为噪声
            # production-scale 数据 (D 落地之后) 才能得到有意义的加速比


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--with-hint", action="store_true",
                        help="跑 hint round (跑两遍同一 dump 对比)")
    args = parser.parse_args()
    main(args.limit, with_hint=args.with_hint)
