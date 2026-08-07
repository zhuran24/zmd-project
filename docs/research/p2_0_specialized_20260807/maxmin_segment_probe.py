#!/usr/bin/env python3
"""细流段厚度探针：逐商品求「最集中路由下最薄的段有多厚」。

`split_free_probe.py` 已证 6 种商品在任何最小车道分配下都**必然**出现分流。
本探针问下一个问题：这些被迫的细流段最厚能做到多厚？

记 m_k = max over 路由 min over 段 (该段速率)。若对任意两种中间品 j,k 都有
m_j + m_k > 1（带容量），则即使存在分流，两种中间品仍然装不进同一格
——纯流强制以**修复后的形式**幸存。反之则真有混流窗口。

建模（逐商品，端口级运输问题 + 车道数变量，整数化后精确）：
  w[p][q] ≥ 0  产口 p 送往耗口 q 的流量
  L[p][q] ∈ Z≥0 该链路的车道数；w ≤ cap·L（每道 ≤ 容量）、w ≥ t·L（每道 ≥ t）
  Σ_q w[p][q] = R_p, Σ_p w[p][q] = R_q
对固定 t 是线性可行性问题；对 t 二分求最大可行 t = m_k。

用法：.venv/bin/python docs/research/p2_0_specialized_20260807/maxmin_segment_probe.py
输出：maxmin_segment_receipt.json + stdout
"""
from __future__ import annotations

import json
import math
import os
from fractions import Fraction

from ortools.sat.python import cp_model

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)
from split_free_probe import solve_duty, fstr, ceil_frac  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
GENERIC_IO = f"{ROOT}/data/preprocessed/generic_io_requirements.json"
OUT = f"{HERE}/maxmin_segment_receipt.json"


def feasible_at(P, Q, cap: Fraction, t: Fraction, D: int) -> bool:
    """固定下界 t，问运输方案是否存在（每条车道速率 ∈ [t, cap]）。"""
    CAP = int(cap * D)
    T = int(t * D)
    if T <= 0:
        return True
    m = cp_model.CpModel()
    NP, NQ = len(P), len(Q)
    Rp = [int(r * D) for _, r, _ in P]
    Rq = [int(r * D) for _, r, _ in Q]
    maxflow = max(max(Rp), max(Rq))
    w = [[m.NewIntVar(0, min(Rp[i], Rq[j]), f"w{i}_{j}")
          for j in range(NQ)] for i in range(NP)]
    L = [[m.NewIntVar(0, maxflow // max(T, 1) + 1, f"L{i}_{j}")
          for j in range(NQ)] for i in range(NP)]
    for i in range(NP):
        m.Add(sum(w[i]) == Rp[i])
    for j in range(NQ):
        m.Add(sum(w[i][j] for i in range(NP)) == Rq[j])
    for i in range(NP):
        for j in range(NQ):
            m.Add(w[i][j] <= CAP * L[i][j])
            m.Add(w[i][j] >= T * L[i][j])
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = 30.0
    s.parameters.num_workers = 8
    st = s.Solve(m)
    return st in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def main() -> int:
    (canon, ops, commodities, out_rate, in_rate,
     n_op, duty, finals, externals) = solve_duty()
    cap = Fraction(canon["globals"]["logistics"]["belt_capacity_per_tick"])
    with open(GENERIC_IO) as f:
        gio = json.load(f)

    from collections import defaultdict
    producers = defaultdict(list)
    consumers = defaultdict(list)
    for op in ops:
        for k, full in out_rate[op].items():
            r = full * duty[op]
            for i in range(n_op[op]):
                producers[k].append((f"{op}#{i}", r, ceil_frac(r / cap)))
        for k, full in in_rate[op].items():
            r = full * duty[op]
            for i in range(n_op[op]):
                consumers[k].append((f"{op}#{i}", r, ceil_frac(r / cap)))
    for k, cnt in gio["required_generic_outputs"].items():
        for i in range(int(cnt)):
            producers[k].append((f"boundary#{i}", cap, 1))
    for k in gio["required_generic_inputs"]:
        tot = sum(r for _, r, _ in producers[k])
        consumers[k].append(("generic_input#0", tot, ceil_frac(tot / cap)))

    results = {}
    m_exact: dict[str, Fraction] = {}
    for k in commodities:
        P, Q = producers[k], consumers[k]
        D = 1
        for _, r, _ in P + Q:
            D = D * r.denominator // math.gcd(D, r.denominator)
        D = D * cap.denominator // math.gcd(D, cap.denominator)
        # 在 1..CAP 上二分最大可行 t（scaled 整数）
        lo, hi = 1, int(cap * D)          # lo 恒可行, hi 可能不可行
        assert feasible_at(P, Q, cap, Fraction(lo, D), D)
        if feasible_at(P, Q, cap, Fraction(hi, D), D):
            best = hi
        else:
            while lo + 1 < hi:
                mid = (lo + hi) // 2
                if feasible_at(P, Q, cap, Fraction(mid, D), D):
                    lo = mid
                else:
                    hi = mid
            best = lo
        m_k = Fraction(best, D)
        m_exact[k] = m_k
        results[k] = {
            "max_min_segment_rate_per_tick": fstr(m_k),
            "scale_D": D,
            "producer_ports": len(P), "consumer_ports": len(Q),
        }
        print(f"{k:<24} m_k = {fstr(m_k):>8}  (= {float(m_k):.4f} 件/tick)")

    # 中间品两两：m_j + m_k ≤ cap 即存在混流窗口
    inter = [c for c in commodities if c not in finals]
    windows = []
    for i, a in enumerate(inter):
        for b in inter[i:]:
            ma, mb = m_exact[a], m_exact[b]
            if ma + mb <= cap:
                windows.append({"a": a, "b": b, "m_a": fstr(ma), "m_b": fstr(mb),
                                "sum": fstr(ma + mb)})

    receipt = {
        "artifact": "p2_0_specialized_maxmin_segment_probe",
        "date": "2026-08-07",
        "question": "最集中路由下每种商品最薄段的厚度 m_k；两两 m_j+m_k ≤ cap 即存在混流窗口",
        "method": "端口级运输问题 + 车道数变量，w ≤ cap·L 且 w ≥ t·L，对 t 二分（CP-SAT，整数精确）",
        "belt_capacity_per_tick": fstr(cap),
        "per_commodity": results,
        "intermediate_mixing_windows": windows,
        "mixing_window_count": len(windows),
        "note": "m_k 是**上界方向友好**的量：它说的是路由方最好情况；对抗方可以把段切得更薄。"
                "所以 windows 为空只说明『最集中路由下装不下』，不等于『任何路由都装不下』——"
                "后者需要前件把路由限死在最集中方案上。",
    }
    with open(OUT, "w") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=1)
    print()
    print(f"中间品混流窗口（m_j+m_k ≤ {fstr(cap)}）：{len(windows)} 对")
    for wdw in windows[:20]:
        print(f"  {wdw['a']} ({wdw['m_a']}) + {wdw['b']} ({wdw['m_b']}) = {wdw['sum']}")
    print(f"receipt -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
