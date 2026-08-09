"""速率引理可复现工件（矛盾清单 E 条，2026-08-06）。

从 demand_solver 精确账独立重算：
1. 每 operation 单机运行率（need/ceil(need)）与「恰=1」的台数口径；
2. 每台机每种原料输入道 / 每种产物输出道的残余速率（占用道 = ceil(rate)，
   残余 = rate - floor(rate) 若非整数），逐条标 operation+commodity+侧；
3. 引理核心断言的机器检查：任取两条非满残道，速率之和是否 > 1（带帽=1 件/tick）。

用法：PYTHONPATH=仓库根 .venv/bin/python rate_lemma_recompute.py
"""
from fractions import Fraction
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.preprocess.demand_solver import solve_demands_exact
from src.interchange.preprocess_context import load_default_preprocess_context


def main() -> int:
    ctx = load_default_preprocess_context()
    flows, machine_runs = solve_demands_exact(ctx)
    belt_cap = Fraction(ctx.belt_capacity_per_tick)  # 件/tick
    print(f"belt_cap={belt_cap}/tick, tick={ctx.tick_interval_seconds}s")

    full_rate = 0
    total_ops = 0
    residuals: list[tuple[str, str, str, Fraction]] = []
    for op_name, runs in sorted(machine_runs.items()):
        total_ops += 1
        recipe = ctx.recipes[op_name]
        machines = -(-runs.numerator // runs.denominator)  # ceil
        util = runs / machines
        if util == 1:
            full_rate += 1
        per_machine_runs = runs / machines
        for side, table in (("in", recipe.inputs), ("out", recipe.outputs)):
            for commodity, qty in sorted(table.items()):
                # 单机该商品速率(件/tick) = qty * runs_per_machine / ticks_per_cycle
                rate = Fraction(qty) * per_machine_runs / recipe.ticks_per_cycle
                lanes = -(-rate.numerator // rate.denominator)  # ceil(rate/cap), cap=1
                residual = rate - (lanes - 1)  # 最末道占用
                if residual != 1:
                    residuals.append((op_name, commodity, side, residual))
    print(f"运行率恰=1 的 operation: {full_rate}/{total_ops}")
    print(f"非满残道 {len(residuals)} 条:")
    for op, com, side, r in residuals:
        print(f"  {op} [{side}] {com}: {r}")
    dist = sorted({r for _, _, _, r in residuals})
    print(f"残余速率集合: {[str(r) for r in dist]}")
    # 引理断言: 除终端成品段外任两条之和>1
    terminal = {"qiaoyu_capsule", "valley_battery"}
    core = [(op, com, side, r) for op, com, side, r in residuals if com not in terminal]
    violations = [
        (a, b)
        for i, a in enumerate(core)
        for b in core[i + 1 :]
        if a[3] + b[3] <= 1
    ]
    print(f"中间产物残道两两之和≤1 的反例: {len(violations)} 对")
    for a, b in violations[:5]:
        print(f"  {a} + {b}")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
