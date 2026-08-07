#!/usr/bin/env python3
"""前件 (ii) 的可实现性探针：逐商品判定「无分流（merge-only）车道路由」是否存在。

**为什么要问这个**：canonical `semantics.rate_lemma_scope` 的纯流强制断言
「中间品的逐道残余速率两两之和 > 1 车道容量 ⇒ 任两种中间品不得共用一条带道」。
该断言比较的是**端口侧**车道速率。但一条车道从产口走到耗口的途中允许经 splitter
拆细：若某商品被迫拆出低于其最小车道速率的细流段，那段上的混流就重新变得速率合法，
纯流强制在网络中段失效。

因此前件 (ii)「最小车道分配」要真正兑现纯流强制，需要的不只是**车道条数**最小，
而是**整条网络上不出现次最小速率段**——等价于：存在一个只合流、不分流的车道路由。

本探针逐商品判定该路由是否存在（CP-SAT，整数化后精确，无浮点）：
  产口车道集合 P_k（每口 L=ceil(rate) 条，条速率自由、和 = 口速率、每条 ≤ cap）
  耗口车道集合 Q_k（同上）
  问：能否把每条产道**整条**指派给某条耗道（允许多条产道并入一条耗道），使两侧守恒？
若答 INFEASIBLE，则该商品在任何最小车道分配下都必然出现分流 ⇒ 纯流强制在其上不成立。

用法：.venv/bin/python docs/research/p2_0_specialized_20260807/split_free_probe.py
输出：split_free_probe_receipt.json + stdout（同目录 *_stdout.log）
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from fractions import Fraction

from ortools.sat.python import cp_model

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
CANON = f"{ROOT}/rules/canonical_rules.json"
INSTANCES = f"{ROOT}/data/preprocessed/mandatory_exact_instances.json"
GENERIC_IO = f"{ROOT}/data/preprocessed/generic_io_requirements.json"
OUT = f"{os.path.dirname(os.path.abspath(__file__))}/split_free_probe_receipt.json"


def fstr(x: Fraction) -> str:
    x = Fraction(x)
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def ceil_frac(x: Fraction) -> int:
    return -((-x.numerator) // x.denominator)


def solve_duty():
    """复算钉死目标下的 x_op / n_op / duty（与 rate_table.py、OB1 同算法）。"""
    with open(CANON) as f:
        canon = json.load(f, parse_float=Fraction, parse_int=Fraction)
    recipes = canon["recipes"]
    meta = canon["commodity_metadata"]
    ops = sorted(recipes)
    commodities = sorted(meta)

    def pm(op, table):
        r = recipes[op]
        return {k: Fraction(q) / Fraction(r["ticks_per_cycle"])
                for k, q in r[table].items()}

    out_rate = {op: pm(op, "outputs") for op in ops}
    in_rate = {op: pm(op, "inputs") for op in ops}
    targets = canon["production_targets"]
    target_rate = {c: Fraction(t["value"]) * out_rate[t["final_recipe_id"]][c]
                   for c, t in targets.items()}
    finals = [c for c in commodities if meta[c]["sink_kind"] == "generic_input"]
    externals = [c for c in commodities
                 if meta[c]["source_kind"] == "external_boundary"]
    internal = [c for c in commodities
                if c not in finals and c not in externals]
    eq_comms = internal + finals
    n = len(ops)
    M = []
    for c in eq_comms:
        M.append([out_rate[op].get(c, Fraction(0))
                  - (Fraction(0) if c in finals else in_rate[op].get(c, Fraction(0)))
                  for op in ops] + [target_rate.get(c, Fraction(0))])
    for col in range(n):
        piv = next(r for r in range(col, n) if M[r][col] != 0)
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        M[col] = [v / pv for v in M[col]]
        for r in range(n):
            if r != col and M[r][col] != 0:
                f = M[r][col]
                M[r] = [v - f * w for v, w in zip(M[r], M[col])]
    x = {op: M[j][n] for j, op in enumerate(ops)}
    n_op = {op: ceil_frac(x[op]) for op in ops}
    with open(INSTANCES) as f:
        census = defaultdict(int)
        for inst in json.load(f):
            if inst["operation_type"] in recipes:
                census[inst["operation_type"]] += 1
    assert all(n_op[op] == census[op] for op in ops), "普查不符"
    duty = {op: x[op] / n_op[op] for op in ops}
    return canon, ops, commodities, out_rate, in_rate, n_op, duty, finals, externals


def main() -> int:
    (canon, ops, commodities, out_rate, in_rate,
     n_op, duty, finals, externals) = solve_duty()
    belt_cap = Fraction(canon["globals"]["logistics"]["belt_capacity_per_tick"])
    with open(GENERIC_IO) as f:
        gio = json.load(f)

    # ---- 逐商品收集产口 / 耗口（口 = 一台机器的一个方向的一种商品）----
    # 每个「口」记 (标签, 口总速率, 车道数 ceil)
    producers: dict[str, list] = defaultdict(list)
    consumers: dict[str, list] = defaultdict(list)
    for op in ops:
        for k, full in out_rate[op].items():
            r = full * duty[op]
            for i in range(n_op[op]):
                producers[k].append((f"{op}#{i}", r, ceil_frac(r / belt_cap)))
        for k, full in in_rate[op].items():
            r = full * duty[op]
            for i in range(n_op[op]):
                consumers[k].append((f"{op}#{i}", r, ceil_frac(r / belt_cap)))
    # 外部商品：boundary 源口（每口 1 件/tick，口数 = generic_io 声明）
    for k, cnt in gio["required_generic_outputs"].items():
        for i in range(int(cnt)):
            producers[k].append((f"boundary#{i}", belt_cap, 1))
    # 终品：generic input 汇口（每商品声明 1 个口，口速率 = 总产量）
    for k, cnt in gio["required_generic_inputs"].items():
        total = sum(r * n for _, r, _ in [] ) if False else None
        tot = sum(r for lbl, r, _ in producers[k])
        assert int(cnt) == 1, (k, cnt)
        consumers[k].append((f"generic_input#{0}", tot, ceil_frac(tot / belt_cap)))

    results = {}
    for k in commodities:
        P, Q = producers[k], consumers[k]
        sp = sum(r for _, r, _ in P)
        sq = sum(r for _, r, _ in Q)
        assert sp == sq, (k, fstr(sp), fstr(sq))
        # 整数化：乘以全部速率分母的 lcm
        D = 1
        for _, r, _ in P + Q:
            D = D * r.denominator // math.gcd(D, r.denominator)
        D = D * belt_cap.denominator // math.gcd(D, belt_cap.denominator)
        CAP = int(belt_cap * D)

        # 展开成逐条车道
        p_lanes = []   # (port_idx, 口总速率scaled, 该口车道数)
        for pi, (_, r, L) in enumerate(P):
            for _ in range(L):
                p_lanes.append(pi)
        q_lanes = []
        for qi, (_, r, L) in enumerate(Q):
            for _ in range(L):
                q_lanes.append(qi)
        NP, NQ = len(p_lanes), len(q_lanes)

        info = {
            "producer_ports": len(P), "consumer_ports": len(Q),
            "producer_lanes": NP, "consumer_lanes": NQ,
            "total_rate_per_tick": fstr(sp),
            "scale_D": D,
        }
        if NP < NQ:
            # 产道少于耗道 ⇒ 必须分流（一条产道要喂多条耗道）
            info["split_free_exists"] = False
            info["reason"] = ("产道数 < 耗道数 ⇒ 鸽巢：至少一条产道要喂多条耗道 = 必然分流")
            results[k] = info
            continue

        m = cp_model.CpModel()
        # 每条产道的速率
        pf = [m.NewIntVar(1, CAP, f"pf{i}") for i in range(NP)]
        # 每条耗道的速率
        qf = [m.NewIntVar(1, CAP, f"qf{j}") for j in range(NQ)]
        # 口内守恒
        for pi, (_, r, L) in enumerate(P):
            idx = [i for i in range(NP) if p_lanes[i] == pi]
            m.Add(sum(pf[i] for i in idx) == int(r * D))
            for a, b in zip(idx, idx[1:]):      # 对称破缺：口内非降
                m.Add(pf[a] <= pf[b])
        for qi, (_, r, L) in enumerate(Q):
            idx = [j for j in range(NQ) if q_lanes[j] == qi]
            m.Add(sum(qf[j] for j in idx) == int(r * D))
            for a, b in zip(idx, idx[1:]):
                m.Add(qf[a] <= qf[b])
        # 指派：每条产道整条进入某条耗道
        asg = {}
        for i in range(NP):
            for j in range(NQ):
                asg[i, j] = m.NewBoolVar(f"a{i}_{j}")
            m.AddExactlyOne(asg[i, j] for j in range(NQ))
        # y[i][j] = pf[i] if asg else 0
        y = {}
        for i in range(NP):
            for j in range(NQ):
                v = m.NewIntVar(0, CAP, f"y{i}_{j}")
                m.Add(v <= CAP * asg[i, j])
                m.Add(v <= pf[i])
                m.Add(v >= pf[i] - CAP * (1 - asg[i, j]))
                y[i, j] = v
        for i in range(NP):
            m.Add(sum(y[i, j] for j in range(NQ)) == pf[i])
        for j in range(NQ):
            m.Add(sum(y[i, j] for i in range(NP)) == qf[j])
            m.Add(sum(asg[i, j] for i in range(NP)) >= 1)  # 每条耗道要被喂

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        solver.parameters.num_workers = 8
        st = solver.Solve(m)
        name = solver.StatusName(st)
        info["cpsat_status"] = name
        if st == cp_model.INFEASIBLE:
            info["split_free_exists"] = False
            info["reason"] = "CP-SAT 证明无解：任何最小车道分配下都必然出现分流"
        elif st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            info["split_free_exists"] = True
            info["witness_min_lane_rate"] = fstr(
                Fraction(min(solver.Value(v) for v in pf + qf), D))
        else:
            info["split_free_exists"] = None
            info["reason"] = f"未判定（{name}）"
        results[k] = info
        print(f"{k:<24} 产道{NP:>3} 耗道{NQ:>3}  {name:<12} "
              f"split_free={info['split_free_exists']}")

    forced_split = sorted(c for c, v in results.items()
                          if v.get("split_free_exists") is False)
    undetermined = sorted(c for c, v in results.items()
                          if v.get("split_free_exists") is None)

    receipt = {
        "artifact": "p2_0_specialized_split_free_probe",
        "date": "2026-08-07",
        "question": "前件 (ii)『最小车道分配』能否在整条网络上兑现（无次最小速率段）",
        "method": "逐商品 CP-SAT：产道整条指派给耗道（允许合流、禁止分流），"
                  "车道速率自由但口内守恒、每道 ≤ cap；INFEASIBLE = 必然分流",
        "belt_capacity_per_tick": fstr(belt_cap),
        "per_commodity": results,
        "commodities_forcing_split": forced_split,
        "undetermined": undetermined,
        "interpretation": (
            "凡列入 commodities_forcing_split 的商品，在任何最小车道分配下都必然出现"
            "低于最小车道速率的细流段；canonical rate_lemma_scope 的纯流强制在这些细流段上"
            "不成立（细流 + 另一中间品的残道之和可以 ≤ 1）。"
            "⇒ 前件 (ii) 若只声明『车道条数最小』，不足以推出网络级纯流；"
            "要么把前件加强为『无次最小速率段』（但本探针显示该加强前件对这些商品不可满足，"
            "即前件族为空 = 该读法不可用），要么承认纯流强制只是**逐口局部**结论。"
        ),
    }
    with open(OUT, "w") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=1)
    print()
    print(f"必然分流的商品（{len(forced_split)}）: {forced_split}")
    print(f"未判定: {undetermined}")
    print(f"receipt -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
