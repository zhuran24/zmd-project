#!/usr/bin/env python
"""Phase 3C P2 #18 — MUS via CPMpy QuickXplain PoC.

目标: 验证 CPMpy 现成 MUS 算法 (QuickXplain / Deletion / OCUS) 在
INFEASIBLE 约束集合上能提取最小不可满足子集 (Minimal Unsatisfiable
Subset, MUS), 比项目当前的"whole-layout nogood" (binding INFEASIBLE
fallback 路径) 更小.

PoC 范围:
- 构造微型 INFEASIBLE 约束模型 (BoolVar + 线性约束)
- 调 cpmpy.tools.explain.quickxplain / mus
- 输出 MUS 大小 + 与 trivial cut (全约束) 对比
- *不动* 项目主路径——production 集成要把 binding_subproblem 表达式
  改用 CPMpy DSL 或写桥接器, 那是 1 周量级的工作, 不在 PoC 范围

环境:
- 需要 `pip install --no-deps cpmpy>=0.10.0` (CPMpy 0.10.0 PyPI 包
  pyproject 限 ortools<=9.14, 但 API 兼容 9.15; --no-deps 绕过即可)

参考:
- R5 `a3bef849bbe8777ab` (MUS algorithms)
- R13 audit `ae3860a1dc6cbabb8` (CPMpy 0.10.0 验证 + cvc5 1.3.4)
- 路线图 P2 #18
"""

from __future__ import annotations


def _build_infeasible_demo():
    """构造微型 INFEASIBLE 模型, 模拟 binding subproblem 的 BoolVar
    cardinality 冲突场景 (storage box 不能同时绑两个互斥 commodity).
    """
    import cpmpy as cp

    x = cp.boolvar(shape=4, name="x")

    constraints = [
        # 约束 0: x[0] + x[1] >= 1
        x[0] + x[1] >= 1,
        # 约束 1: x[2] + x[3] >= 1
        x[2] + x[3] >= 1,
        # 约束 2: x[0] + x[1] + x[2] + x[3] <= 1
        # ⚠ 跟约束 0 + 约束 1 不可同时满足
        x[0] + x[1] + x[2] + x[3] <= 1,
        # 无关约束 (red herring, 应该不在 MUS 里)
        x[0] + x[2] >= 0,        # trivially true
        x[1] | ~x[1],            # tautology
        x[3] | ~x[3],            # tautology
    ]
    return x, constraints


def run_poc():
    import cpmpy as cp
    from cpmpy.tools.explain import mus, quickxplain

    x, constraints = _build_infeasible_demo()
    print(f"Total constraints: {len(constraints)}")

    m = cp.Model(constraints)
    is_sat = m.solve()
    print(f"Model satisfiable: {is_sat} (expected False)")
    assert not is_sat, "Demo model 必须 INFEASIBLE"

    deletion_mus = mus(soft=constraints)
    print(f"\n=== deletion-based MUS ===")
    print(f"MUS size: {len(deletion_mus)} / {len(constraints)} 总约束")
    for i, c in enumerate(deletion_mus):
        print(f"  [{i}] {c}")

    qx_mus = quickxplain(soft=constraints)
    print(f"\n=== QuickXplain MUS ===")
    print(f"MUS size: {len(qx_mus)} / {len(constraints)} 总约束")
    for i, c in enumerate(qx_mus):
        print(f"  [{i}] {c}")

    print("\n" + "=" * 60)
    expected_core = 3
    print(f"Expected core size: {expected_core}")
    print(f"deletion-MUS size:  {len(deletion_mus)} {'OK' if len(deletion_mus) == expected_core else 'WARN'}")
    print(f"QuickXplain size:   {len(qx_mus)} {'OK' if len(qx_mus) == expected_core else 'WARN'}")
    print(f"Whole-set baseline: {len(constraints)} (项目当前 fallback cut 等价)")
    reduction_pct = 100 * (1 - len(qx_mus) / len(constraints))
    print(f"MUS reduction:      {len(constraints) - len(qx_mus)} 约束 ({reduction_pct:.0f}%)")
    print("=" * 60)
    print(
        "\nPoC 结论: CPMpy 0.10.0 MUS API 在 OR-Tools 9.15 (--no-deps 装) 上工作正常,\n"
        "API 一行调用 quickxplain(soft=constraints) 即得最小不可满足子集.\n"
        "Production 集成: 需要把项目 binding/routing 子问题模型从 OR-Tools\n"
        "cp_model 重写为 CPMpy DSL 或写桥接器 (~1 周量级工作), 不在 PoC 范围."
    )


if __name__ == "__main__":
    run_poc()
