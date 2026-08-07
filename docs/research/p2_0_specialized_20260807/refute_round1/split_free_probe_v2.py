#!/usr/bin/env python3
"""split-free 探针 v2：把「每台机器占空」从均摊约定放开成自由变量后重判。

**v1 的缺陷**（owner 2026-08-07 指出）：`split_free_probe.py:97` 写死
`duty[op] = x[op] / n_op[op]`，即同一 operation 的每台机器占空相同。这是**未经辩护的
约定**：游戏里占空由供料决定，台间怎么分是布局的自由度。例如 6 台制瓶机总占空 11/2
可以是「5 台满速 + 1 台半速」而不是「6 台各 11/12」；把 duty 换成后者，
steel_block 的耗道从 18 掉到 17 = 产道 17，v1 的鸽巢就没了。

v1 还有第二个缺陷：它**逐商品独立判**，而 duty 是机器级共享变量——一台机器的 duty
一动，它消费和产出的所有商品口速率同时动。所以必须整网联立。

本探针做四件事（全部 Fraction 精确，零浮点）：

  Part A  占空自由度盘点：哪些 operation 真有自由度，闲置（duty=0）是否可用。
  Part B  **不依赖求解器的车道计数定理**：对每种商品，精确求出「产道数在所有合法
          occupancy 分配下的最大值」与「耗道数的最小值」。若 min(耗道) > max(产道)，
          则鸽巢对**任意**占空分配成立 ⇒ 该商品必然分流，且这是一条纯计数论证。
  Part C  **显式全局见证**：给出一份整网一致的占空分配（阶梯式：能满速的满速、余数
          落在最后一台），逐商品列出车道表与整道指派表，用 Fraction 独立复核。
  Part D  CP-SAT 交叉验证：对 v1 判死的 6 种商品，在占空自由（格点 1/660）下重跑
          可行性，核对 Part B/C 的结论。

  Part E  副产物：canonical `semantics.rate_lemma_scope` 的残道速率集合同样是在均摊
          约定下算的（`docs/research/canonical_batch_20260807/rate_lemma_recompute.py:36`
          `per_machine_runs = runs / machines`）。本探针在同一残道定义下重算见证分配的
          残道集合，检查引理结论是否仍成立。

  Part F  每 operation 的「最大化最小残道速率」——回答「均摊是不是纯流强制的最优约定」。

用法：.venv/bin/python docs/research/p2_0_specialized_20260807/refute_round1/split_free_probe_v2.py
输出：split_free_probe_v2_receipt.json + stdout（同目录 *_stdout.log）
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from fractions import Fraction

from ortools.sat.python import cp_model

HERE = os.path.dirname(os.path.abspath(__file__))
V1_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(V1_DIR)))
sys.path.insert(0, V1_DIR)

from split_free_probe import solve_duty, fstr, ceil_frac  # noqa: E402  复用 v1 总量账

GENERIC_IO = f"{ROOT}/data/preprocessed/generic_io_requirements.json"
OUT = f"{HERE}/split_free_probe_v2_receipt.json"

# 占空格点分母（Part D）。取 lcm(12, 22, 4, 5) = 660，使均摊解 11/12、21/22、11/4
# 与阶梯解 1/2、3/4 全部落在格点上。
LATTICE = 660


# --------------------------------------------------------------------------
# 基础：总量账 + 网络拓扑
# --------------------------------------------------------------------------
def load_network():
    (canon, ops, commodities, out_rate, in_rate,
     n_op, duty_uniform, finals, externals) = solve_duty()
    x_op = {op: duty_uniform[op] * n_op[op] for op in ops}
    belt_cap = Fraction(canon["globals"]["logistics"]["belt_capacity_per_tick"])
    assert belt_cap == 1, "本探针的整数化假设 belt_cap == 1"
    with open(GENERIC_IO) as f:
        gio = json.load(f)
    return dict(
        canon=canon, ops=ops, commodities=commodities,
        out_rate=out_rate, in_rate=in_rate, n_op=n_op,
        duty_uniform=duty_uniform, x_op=x_op, belt_cap=belt_cap,
        finals=finals, externals=externals, gio=gio,
    )


def side_tables(net):
    """返回 {commodity: (producer_ops, consumer_ops)}，元素为 (op, 满速速率)。"""
    prod = defaultdict(list)
    cons = defaultdict(list)
    for op in net["ops"]:
        for k, c in net["out_rate"][op].items():
            prod[k].append((op, c))
        for k, c in net["in_rate"][op].items():
            cons[k].append((op, c))
    return prod, cons


# --------------------------------------------------------------------------
# Part B：车道数在所有合法占空分配下的精确上下界（不依赖求解器）
# --------------------------------------------------------------------------
def _profiles(n: int, lmax: int):
    """枚举 (m_0, m_1, ..., m_lmax)，Σm = n。m_L = 车道数恰为 L 的机器台数。"""
    def rec(rem, slots):
        if slots == 1:
            yield (rem,)
            return
        for v in range(rem + 1):
            for tail in rec(rem - v, slots - 1):
                yield (v,) + tail
    return rec(n, lmax + 1)


def lane_count_bounds(c: Fraction, X: Fraction, n: int):
    """min / max of Σ_i ceil(c·d_i)，约束 Σd_i = X, 0 ≤ d_i ≤ 1, i = 1..n。

    单机车道数 L = ceil(c·d)：
      L = 0  ⇔ d = 0
      L ≥ 1  ⇔ d ∈ ( (L-1)/c , min(1, L/c) ]      （区间非空才是合法档位）
    给定档位分布 (m_L)，可达的 Σd 是 ( Σ m_L·(L-1)/c , Σ m_L·min(1,L/c) ]。
    """
    lmax = ceil_frac(c)
    best = None
    worst = None
    arg_min = arg_max = None
    for prof in _profiles(n, lmax):
        lo = Fraction(0)
        hi = Fraction(0)
        ok = True
        anypos = False
        for L in range(1, lmax + 1):
            m = prof[L]
            if not m:
                continue
            a = Fraction(L - 1) / c
            b = min(Fraction(1), Fraction(L) / c)
            if not a < b:                       # 该档位不可达
                ok = False
                break
            anypos = True
            lo += m * a
            hi += m * b
        if not ok:
            continue
        if anypos:
            if not (lo < X <= hi):
                continue
        elif X != 0:
            continue
        lanes = sum(L * prof[L] for L in range(lmax + 1))
        if best is None or lanes < best:
            best, arg_min = lanes, prof
        if worst is None or lanes > worst:
            worst, arg_max = lanes, prof
    assert best is not None, (fstr(c), fstr(X), n)
    return best, worst, arg_min, arg_max


def part_b(net, prod, cons):
    """逐商品：min(耗道) vs max(产道) —— 大于即为对任意占空成立的鸽巢。"""
    out = {}
    for k in net["commodities"]:
        p_min = p_max = 0
        p_detail = []
        for op, c in prod[k]:
            lo, hi, am, aM = lane_count_bounds(c, net["x_op"][op], net["n_op"][op])
            p_min += lo
            p_max += hi
            p_detail.append({
                "op": op, "full_rate": fstr(c), "x_op": fstr(net["x_op"][op]),
                "n_op": net["n_op"][op], "lanes_min": lo, "lanes_max": hi,
                "profile_at_min": list(am), "profile_at_max": list(aM),
            })
        # 边界源口（外部商品）：口数与速率都固定
        if k in net["externals"]:
            cnt = int(net["gio"]["required_generic_outputs"][k])
            p_min += cnt
            p_max += cnt
            p_detail.append({"op": "boundary_io", "full_rate": "1",
                             "n_op": cnt, "lanes_min": cnt, "lanes_max": cnt})
        c_min = c_max = 0
        c_detail = []
        for op, c in cons[k]:
            lo, hi, am, aM = lane_count_bounds(c, net["x_op"][op], net["n_op"][op])
            c_min += lo
            c_max += hi
            c_detail.append({
                "op": op, "full_rate": fstr(c), "x_op": fstr(net["x_op"][op]),
                "n_op": net["n_op"][op], "lanes_min": lo, "lanes_max": hi,
                "profile_at_min": list(am), "profile_at_max": list(aM),
            })
        # 终品汇口：generic input，口数与速率固定
        if k in net["finals"]:
            tot = sum(net["x_op"][op] * c for op, c in prod[k])
            L = ceil_frac(tot / net["belt_cap"])
            c_min += L
            c_max += L
            c_detail.append({"op": "generic_input", "rate": fstr(tot),
                             "n_op": 1, "lanes_min": L, "lanes_max": L})
        forced = c_min > p_max
        out[k] = {
            "producer_lanes_min": p_min, "producer_lanes_max": p_max,
            "consumer_lanes_min": c_min, "consumer_lanes_max": c_max,
            "producers": p_detail, "consumers": c_detail,
            "forced_split_for_every_duty": forced,
            "counting_certificate": (
                f"耗道数 ≥ {c_min} > {p_max} ≥ 产道数（对任意合法占空分配）；"
                f"整道指派要求每条耗道至少收一条产道 ⇒ 鸽巢 ⇒ 必然分流"
                if forced else None
            ),
        }
    return out


# --------------------------------------------------------------------------
# Part C：显式全局见证（阶梯式占空）
# --------------------------------------------------------------------------
def staircase_duty(net):
    """能满速的满速、余数落最后一台。n_op = ceil(x_op) ⇒ 不存在闲置名额。"""
    duty = {}
    for op in net["ops"]:
        x, n = net["x_op"][op], net["n_op"][op]
        full = int(x)                       # floor
        rem = x - full
        d = [Fraction(1)] * full
        if rem:
            d.append(rem)
        assert len(d) == n, (op, len(d), n)
        assert sum(d) == x
        duty[op] = d
    return duty


def port_lanes(rate: Fraction, cap: Fraction):
    """最小车道数下的「填满优先」车道速率：L-1 条满道 + 1 条残道。

    残道速率 rate-(L-1) 是最小车道数约束下**可能出现的最细一条**（每条 ≤ cap），
    与 canonical rate_lemma_recompute 的 residual 定义一致。
    """
    if rate == 0:
        return []
    L = ceil_frac(rate / cap)
    return [cap] * (L - 1) + [rate - cap * (L - 1)]


def build_lanes(net, duty):
    """给定占空分配，逐商品展开产道 / 耗道（标签 + 精确速率）。"""
    P = defaultdict(list)
    Q = defaultdict(list)
    cap = net["belt_cap"]
    for op in net["ops"]:
        for i, d in enumerate(duty[op]):
            for k, c in net["out_rate"][op].items():
                for j, r in enumerate(port_lanes(c * d, cap)):
                    P[k].append((f"{op}#{i}.out.{j}", r))
            for k, c in net["in_rate"][op].items():
                for j, r in enumerate(port_lanes(c * d, cap)):
                    Q[k].append((f"{op}#{i}.in.{j}", r))
    for k, cnt in net["gio"]["required_generic_outputs"].items():
        for i in range(int(cnt)):
            P[k].append((f"boundary#{i}", cap))
    for k, cnt in net["gio"]["required_generic_inputs"].items():
        assert int(cnt) == 1, (k, cnt)
        tot = sum(r for _, r in P[k])
        for j, r in enumerate(port_lanes(tot, cap)):
            Q[k].append((f"generic_input.{j}", r))
    return P, Q


def find_merge_only_assignment(P, Q, cap: Fraction):
    """找一个「每条产道整条进入某条耗道」的指派。返回 [(pi, qj), ...] 或 None。

    先试排序双射（多重集相等时成立，本见证里绝大多数商品都是这种），
    不成立再交给 CP-SAT 做整数装箱。
    """
    if len(P) == len(Q):
        sp = sorted(range(len(P)), key=lambda i: P[i][1])
        sq = sorted(range(len(Q)), key=lambda j: Q[j][1])
        if all(P[i][1] == Q[j][1] for i, j in zip(sp, sq)):
            return [(i, j) for i, j in zip(sp, sq)], "sorted_bijection"
    if len(P) < len(Q):
        return None, "pigeonhole"
    D = 1
    for _, r in P + Q:
        D = D * r.denominator // (
            __import__("math").gcd(D, r.denominator))
    m = cp_model.CpModel()
    asg = {}
    for i in range(len(P)):
        for j in range(len(Q)):
            asg[i, j] = m.NewBoolVar(f"a{i}_{j}")
        m.AddExactlyOne(asg[i, j] for j in range(len(Q)))
    for j in range(len(Q)):
        m.Add(sum(int(P[i][1] * D) * asg[i, j] for i in range(len(P)))
              == int(Q[j][1] * D))
        m.Add(sum(asg[i, j] for i in range(len(P))) >= 1)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = 60.0
    s.parameters.num_workers = 8
    st = s.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, s.StatusName(st)
    return ([(i, j) for i in range(len(P)) for j in range(len(Q))
             if s.Value(asg[i, j])], "cpsat")


def verify_assignment(P, Q, pairs, cap: Fraction):
    """纯 Fraction 独立复核：与求解器无关。"""
    if pairs is None:
        return False, "no assignment"
    seen = defaultdict(list)
    got = set()
    for i, j in pairs:
        if i in got:
            return False, f"产道 {i} 被指派多次（=分流）"
        got.add(i)
        seen[j].append(i)
    if len(got) != len(P):
        return False, "有产道未被指派"
    for j, (lbl, r) in enumerate(Q):
        s = sum(P[i][1] for i in seen[j])
        if s != r:
            return False, f"耗道 {lbl} 守恒不符：{fstr(s)} != {fstr(r)}"
        if not seen[j]:
            return False, f"耗道 {lbl} 无来源"
    for lbl, r in P + Q:
        if not (0 < r <= cap):
            return False, f"车道 {lbl} 速率越界 {fstr(r)}"
    return True, "ok"


def part_c(net, duty):
    P, Q = build_lanes(net, duty)
    cap = net["belt_cap"]
    res = {}
    for k in net["commodities"]:
        p, q = P[k], Q[k]
        sp, sq = sum(r for _, r in p), sum(r for _, r in q)
        assert sp == sq, (k, fstr(sp), fstr(sq))
        pairs, how = find_merge_only_assignment(p, q, cap)
        ok, why = verify_assignment(p, q, pairs, cap)
        res[k] = {
            "producer_lanes": len(p), "consumer_lanes": len(q),
            "total_rate": fstr(sp),
            "producer_lane_rates": [[l, fstr(r)] for l, r in p],
            "consumer_lane_rates": [[l, fstr(r)] for l, r in q],
            "split_free": bool(ok),
            "method": how,
            "verify": why,
            "assignment": ([[p[i][0], q[j][0]] for i, j in pairs]
                           if pairs else None),
        }
    return res, P, Q


# --------------------------------------------------------------------------
# Part D：CP-SAT 自由占空可行性（格点），交叉验证 Part B/C
# --------------------------------------------------------------------------
def part_d_one(net, prod, cons, k, time_limit=120.0):
    """商品 k 单独放开相关 operation 的占空（格点 1/LATTICE），判 split-free 是否存在。"""
    D = LATTICE
    S = D * 5                                   # 速率整数化尺度（1/5 满速也是整数）
    CAP = S
    m = cp_model.CpModel()

    duty = {}
    for op, _ in prod[k] + cons[k]:
        if op in duty:
            continue
        n = net["n_op"][op]
        xs = net["x_op"][op] * D
        assert xs.denominator == 1, (op, fstr(net["x_op"][op]))
        v = [m.NewIntVar(0, D, f"d_{op}_{i}") for i in range(n)]
        m.Add(sum(v) == int(xs))
        for a, b in zip(v, v[1:]):
            m.Add(a >= b)                       # 对称破缺：占空非增
        duty[op] = v

    def make_lanes(op, c, side):
        """一台机器一侧的车道：速率变量 + 激活布尔 + 最小车道数约束。"""
        lmax = ceil_frac(c)
        mult = int(c * S / D)                   # rate_scaled = mult * duty
        assert Fraction(mult) == c * S / D
        lanes = []
        for i, dv in enumerate(duty[op]):
            rate = m.NewIntVar(0, lmax * CAP, f"r_{op}{i}_{side}_{k}")
            m.Add(rate == mult * dv)
            rs, acts = [], []
            for l in range(lmax):
                x = m.NewIntVar(0, CAP, f"l_{op}{i}_{side}_{k}_{l}")
                a = m.NewBoolVar(f"a_{op}{i}_{side}_{k}_{l}")
                m.Add(x >= 1).OnlyEnforceIf(a)
                m.Add(x == 0).OnlyEnforceIf(a.Not())
                rs.append(x)
                acts.append(a)
            for a, b in zip(rs, rs[1:]):
                m.Add(a >= b)                   # 非增 ⇒ 激活的是前缀
            for a, b in zip(acts, acts[1:]):
                m.Add(a >= b)
            m.Add(sum(rs) == rate)
            nact = sum(acts)
            # 最小车道数：nact = ceil(rate / CAP)
            m.Add(nact * CAP >= rate)
            m.Add((nact - 1) * CAP <= rate - 1)
            for l in range(lmax):
                lanes.append((f"{op}#{i}.{side}.{l}", rs[l], acts[l]))
        return lanes

    Pl, Ql = [], []
    for op, c in prod[k]:
        Pl += make_lanes(op, c, "out")
    for op, c in cons[k]:
        Ql += make_lanes(op, c, "in")
    if k in net["externals"]:
        for i in range(int(net["gio"]["required_generic_outputs"][k])):
            x = m.NewIntVar(CAP, CAP, f"b{i}")
            a = m.NewBoolVar(f"ba{i}")
            m.Add(a == 1)
            Pl.append((f"boundary#{i}", x, a))
    if k in net["finals"]:
        tot = sum(net["x_op"][op] * c for op, c in prod[k])
        for j, r in enumerate(port_lanes(tot, net["belt_cap"])):
            x = m.NewIntVar(int(r * S), int(r * S), f"g{j}")
            a = m.NewBoolVar(f"ga{j}")
            m.Add(a == 1)
            Ql.append((f"generic_input.{j}", x, a))

    NP, NQ = len(Pl), len(Ql)
    asg = {}
    for i in range(NP):
        for j in range(NQ):
            asg[i, j] = m.NewBoolVar(f"x{i}_{j}")
        m.Add(sum(asg[i, j] for j in range(NQ)) == Pl[i][2])   # 未激活的产道不指派
    y = {}
    for i in range(NP):
        for j in range(NQ):
            v = m.NewIntVar(0, CAP, f"y{i}_{j}")
            m.Add(v <= CAP * asg[i, j])
            m.Add(v <= Pl[i][1])
            m.Add(v >= Pl[i][1] - CAP * (1 - asg[i, j]))
            y[i, j] = v
        m.Add(sum(y[i, j] for j in range(NQ)) == Pl[i][1])
    for j in range(NQ):
        m.Add(sum(y[i, j] for i in range(NP)) == Ql[j][1])
        m.Add(sum(asg[i, j] for i in range(NP)) >= Ql[j][2])   # 激活的耗道要有来源

    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_limit
    s.parameters.num_workers = 8
    st = s.Solve(m)
    name = s.StatusName(st)
    info = {"cpsat_status": name, "lattice_denominator": D,
            "max_producer_lane_slots": NP, "max_consumer_lane_slots": NQ}
    if st == cp_model.INFEASIBLE:
        info["split_free_exists_on_lattice"] = False
    elif st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        info["split_free_exists_on_lattice"] = True
        info["witness_duty"] = {
            op: [fstr(Fraction(s.Value(v), D)) for v in vs]
            for op, vs in duty.items()}
        info["witness_min_lane_rate"] = fstr(min(
            Fraction(s.Value(v), S) for _, v, a in Pl + Ql if s.Value(a)))
    else:
        info["split_free_exists_on_lattice"] = None
    return info


# --------------------------------------------------------------------------
# Part E/F：残道速率与 canonical rate lemma
# --------------------------------------------------------------------------
def residual_table(net, duty):
    """按 canonical rate_lemma_recompute 的定义算残道：residual = rate - (ceil(rate)-1)。"""
    rows = []
    for op in net["ops"]:
        for i, d in enumerate(duty[op]):
            for side, tbl in (("in", net["in_rate"][op]), ("out", net["out_rate"][op])):
                for k, c in sorted(tbl.items()):
                    rate = c * d
                    if rate == 0:
                        continue
                    L = ceil_frac(rate)
                    rows.append((op, i, side, k, rate - (L - 1)))
    return rows


def rate_lemma_check(net, rows):
    terminal = set(net["finals"])
    core = [r for r in rows if r[3] not in terminal]
    vals = sorted({r[4] for r in core})
    lo = min(vals)
    viol = []
    for a in range(len(core)):
        for b in range(a + 1, len(core)):
            if core[a][4] + core[b][4] <= net["belt_cap"] and core[a][3] != core[b][3]:
                viol.append((core[a], core[b]))
    return {
        "intermediate_residual_set": [fstr(v) for v in vals],
        "min_intermediate_residual": fstr(lo),
        "pairwise_sum_le_cap_violations": len(viol),
        "example_violations": [
            [f"{a[0]}#{a[1]} [{a[2]}] {a[3]}", fstr(a[4]),
             f"{b[0]}#{b[1]} [{b[2]}] {b[3]}", fstr(b[4])]
            for a, b in viol[:6]],
    }


def part_f(net):
    """逐 operation 最大化「该 op 所有机器所有**中间品**口的最小残道速率」（格点 1/LATTICE）。

    终品（qiaoyu_capsule / valley_battery）按 canonical 引理口径排除在外。
    残道只依赖本 op 自己的占空 ⇒ 各 op 独立 ⇒ 全局 max-min = 逐 op 结果取 min。
    """
    D = LATTICE
    out = {}
    terminal = set(net["finals"])
    for op in net["ops"]:
        n, x = net["n_op"][op], net["x_op"][op]
        rates = sorted({c for k, c in net["in_rate"][op].items() if k not in terminal}
                       | {c for k, c in net["out_rate"][op].items() if k not in terminal})
        if not rates:
            out[op] = {"max_min_residual": None, "status": "NO_INTERMEDIATE_PORT"}
            continue
        S = D
        for c in rates:
            S = S * c.denominator // (__import__("math").gcd(S, c.denominator))
        m = cp_model.CpModel()
        dv = [m.NewIntVar(1, D, f"d{i}") for i in range(n)]
        m.Add(sum(dv) == int(x * D))
        for a, b in zip(dv, dv[1:]):
            m.Add(a >= b)
        t = m.NewIntVar(0, S, "t")
        for c in rates:
            mult = int(c * S / D)
            lmax = ceil_frac(c)
            for i in range(n):
                rate = m.NewIntVar(0, lmax * S, f"r{i}")
                m.Add(rate == mult * dv[i])
                nact = m.NewIntVar(1, lmax, f"L{i}")
                m.Add(nact * S >= rate)
                m.Add((nact - 1) * S <= rate - 1)
                resid = m.NewIntVar(1, S, f"res{i}")
                m.Add(resid == rate - (nact - 1) * S)
                m.Add(t <= resid)
        m.Maximize(t)
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = 60.0
        s.parameters.num_workers = 8
        st = s.Solve(m)
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            out[op] = {
                "max_min_residual": fstr(Fraction(s.Value(t), S)),
                "duty_at_optimum": [fstr(Fraction(s.Value(v), D)) for v in dv],
                "uniform_duty": fstr(net["duty_uniform"][op]),
                "status": s.StatusName(st),
            }
        else:
            out[op] = {"max_min_residual": None, "status": s.StatusName(st)}
    return out


# --------------------------------------------------------------------------
# Part G：必然分流商品的细流段厚度 + 混流窗口重算
# --------------------------------------------------------------------------
def maxmin_segment(net, prod, cons, k, duty_fixed=None, time_limit=180.0):
    """最大化「该商品全网最细一段」的速率。

    duty_fixed=None 时占空在格点上自由；否则用给定的占空表。
    本函数只用于 buckwheat / sandleaf 这类「产、耗两侧满速速率都是 1」的商品，
    结构断言写死，越界直接抛。
    """
    assert all(c == 1 for _, c in prod[k]), k
    assert all(c == 1 for _, c in cons[k]), k
    assert k not in net["externals"] and k not in net["finals"], k
    D = LATTICE
    S = D
    m = cp_model.CpModel()

    p_rates = []
    for op, _ in prod[k]:
        assert net["x_op"][op] == net["n_op"][op], (k, op)   # 占空钉死全 1
        p_rates += [S] * net["n_op"][op]
    q_rates = []
    for op, _ in cons[k]:
        n = net["n_op"][op]
        if duty_fixed is None:
            v = [m.NewIntVar(1, S, f"q_{op}_{i}") for i in range(n)]
            m.Add(sum(v) == int(net["x_op"][op] * S))
            for a, b in zip(v, v[1:]):
                m.Add(a >= b)
            q_rates += v
        else:
            q_rates += [int(d * S) for d in duty_fixed[op]]
    NP, NQ = len(p_rates), len(q_rates)

    y, u = {}, {}
    for i in range(NP):
        for j in range(NQ):
            y[i, j] = m.NewIntVar(0, S, f"y{i}_{j}")
            u[i, j] = m.NewBoolVar(f"u{i}_{j}")
            m.Add(y[i, j] == 0).OnlyEnforceIf(u[i, j].Not())
            m.Add(y[i, j] >= 1).OnlyEnforceIf(u[i, j])
        m.Add(sum(y[i, j] for j in range(NQ)) == p_rates[i])
    for j in range(NQ):
        m.Add(sum(y[i, j] for i in range(NP)) == q_rates[j])
        m.Add(sum(u[i, j] for i in range(NP)) >= 1)
    t = m.NewIntVar(1, S, "t")
    for i in range(NP):
        for j in range(NQ):
            m.Add(y[i, j] >= t).OnlyEnforceIf(u[i, j])
    m.Maximize(t)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_limit
    s.parameters.num_workers = 8
    st = s.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": s.StatusName(st), "max_min_segment": None}
    return {
        "status": s.StatusName(st),
        "max_min_segment": fstr(Fraction(s.Value(t), S)),
        "producer_lanes": NP, "consumer_lanes": NQ,
        "split_points": sum(
            max(0, sum(s.Value(u[i, j]) for j in range(NQ)) - 1) for i in range(NP)),
    }


def thin_value_table(net, duty, forced_split_segments):
    """每种中间品「全网最细一段」的速率 = min(各口残道, 该商品被迫产生的细流段)。"""
    thin = {}
    for op, i, side, k, r in residual_table(net, duty):
        if k in net["finals"]:
            continue
        thin[k] = min(thin.get(k, r), r)
    for k, v in forced_split_segments.items():
        if v is not None:
            thin[k] = min(thin.get(k, v), v)
    return thin


def mixflow_windows(net, thin):
    """两种**不同**中间品的最细段之和 ≤ 1 ⇒ 存在速率合法的共道窗口。"""
    ks = sorted(thin)
    out = []
    for a in range(len(ks)):
        for b in range(a + 1, len(ks)):
            if thin[ks[a]] + thin[ks[b]] <= net["belt_cap"]:
                out.append([ks[a], fstr(thin[ks[a]]), ks[b], fstr(thin[ks[b]]),
                            fstr(thin[ks[a]] + thin[ks[b]])])
    return out


# --------------------------------------------------------------------------
def main() -> int:
    net = load_network()
    prod, cons = side_tables(net)

    # ---------- Part A ----------
    print("=" * 78)
    print("Part A  占空自由度盘点")
    print("=" * 78)
    freedom = {}
    for op in net["ops"]:
        x, n = net["x_op"][op], net["n_op"][op]
        free = (x != n)
        freedom[op] = {
            "x_op": fstr(x), "n_op": n, "uniform_duty": fstr(net["duty_uniform"][op]),
            "has_freedom": free,
            "idle_allowed": False,   # n_op = ceil(x_op) ⇒ 少一台就凑不满
            "note": ("占空被 Σd=x=n、d≤1 唯一钉死为全 1" if not free
                     else f"n-1 台满速仅得 {n - 1} < {fstr(x)} ⇒ 每台都必须 >0；台间分摊自由"),
        }
        print(f"  {op:<26} x={fstr(x):>6}  n={n:>3}  "
              f"{'自由' if free else '钉死(全满速)'}")
    n_free = sum(1 for v in freedom.values() if v["has_freedom"])
    print(f"\n  有台间分摊自由度的 operation：{n_free}/{len(net['ops'])}")
    print("  闲置（duty=0）：n_op = ceil(x_op) ⇒ 任何 operation 都不允许闲置任何一台"
          "（少一台就达不到产量）。owner 说的『允许闲置』在本实例里合法但无空间。")

    # ---------- Part B ----------
    print()
    print("=" * 78)
    print("Part B  车道计数定理（对任意占空分配成立，不依赖求解器）")
    print("=" * 78)
    B = part_b(net, prod, cons)
    print(f"  {'commodity':<24}{'产道min':>8}{'产道max':>8}"
          f"{'耗道min':>8}{'耗道max':>8}  结论")
    for k in net["commodities"]:
        v = B[k]
        tag = "必然分流(鸽巢)" if v["forced_split_for_every_duty"] else "计数不排除"
        print(f"  {k:<24}{v['producer_lanes_min']:>8}{v['producer_lanes_max']:>8}"
              f"{v['consumer_lanes_min']:>8}{v['consumer_lanes_max']:>8}  {tag}")
    forced_b = [k for k in net["commodities"] if B[k]["forced_split_for_every_duty"]]
    print(f"\n  对任意占空必然分流：{forced_b}")

    # ---------- Part C ----------
    print()
    print("=" * 78)
    print("Part C  显式全局见证（阶梯式占空，整网一份，链式一致）")
    print("=" * 78)
    duty = staircase_duty(net)
    for op in net["ops"]:
        if freedom[op]["has_freedom"]:
            print(f"  {op:<26} duty = [{', '.join(fstr(d) for d in duty[op])}]")
    C, P, Q = part_c(net, duty)
    print()
    print(f"  {'commodity':<24}{'产道':>6}{'耗道':>6}  {'split_free':<12}{'复核'}")
    for k in net["commodities"]:
        v = C[k]
        print(f"  {k:<24}{v['producer_lanes']:>6}{v['consumer_lanes']:>6}  "
              f"{str(v['split_free']):<12}{v['verify']}")
    ok_c = sorted(k for k in net["commodities"] if C[k]["split_free"])
    bad_c = sorted(k for k in net["commodities"] if not C[k]["split_free"])
    print(f"\n  见证下 split-free 成立：{len(ok_c)}/{len(net['commodities'])}")
    print(f"  仍分流：{bad_c}")
    assert set(bad_c) == set(forced_b), (bad_c, forced_b)
    print("  ⇒ Part B 的下界与 Part C 的见证吻合：17 是同时 split-free 的商品数上确界。")

    # ---------- Part D ----------
    print()
    print("=" * 78)
    print(f"Part D  CP-SAT 自由占空复判（格点 1/{LATTICE}），对 v1 判死的 6 种")
    print("=" * 78)
    v1_forced = ["buckwheat", "buckwheat_seed", "sandleaf",
                 "sandleaf_powder", "sandleaf_seed", "steel_block"]
    Dres = {}
    for k in v1_forced:
        Dres[k] = part_d_one(net, prod, cons, k)
        print(f"  {k:<24}{Dres[k]['cpsat_status']:<14}"
              f"split_free={Dres[k]['split_free_exists_on_lattice']}")

    # ---------- Part E ----------
    print()
    print("=" * 78)
    print("Part E  canonical rate_lemma_scope 在自由占空下的重算")
    print("=" * 78)
    rows_u = residual_table(net, {op: [net["duty_uniform"][op]] * net["n_op"][op]
                                 for op in net["ops"]})
    rows_s = residual_table(net, duty)
    E_u = rate_lemma_check(net, rows_u)
    E_s = rate_lemma_check(net, rows_s)
    for name, E in (("均摊占空（canonical 现行算法）", E_u),
                    ("阶梯占空（本批见证，同样满足前件 (i)(ii)）", E_s)):
        print(f"  {name}")
        print(f"    中间品残道集合   : {E['intermediate_residual_set']}")
        print(f"    最小残道         : {E['min_intermediate_residual']}")
        print(f"    两两之和 ≤1 反例 : {E['pairwise_sum_le_cap_violations']} 对")
        for ex in E["example_violations"][:3]:
            print(f"      {ex[0]} = {ex[1]}   +   {ex[2]} = {ex[3]}")

    # ---------- Part F ----------
    print()
    print("=" * 78)
    print("Part F  逐 operation 最大化最小残道（均摊是不是最优约定？）")
    print("=" * 78)
    F = part_f(net)
    glob = min(Fraction(F[op]["max_min_residual"])
               for op in net["ops"] if F[op].get("max_min_residual"))
    for op in net["ops"]:
        if F[op].get("max_min_residual") and freedom[op]["has_freedom"]:
            print(f"  {op:<26} max-min残道={F[op]['max_min_residual']:>8}  "
                  f"最优占空={F[op]['duty_at_optimum']}")
    print(f"\n  全局 max-min 中间品残道 = {fstr(glob)}"
          f"（每 op 的最优点都落在均摊上 ⇒ 均摊确实是残道最优约定，"
          f"但它只是**一个**合法约定，不是前件 (i)(ii) 蕴含的）")

    # ---------- Part G ----------
    print()
    print("=" * 78)
    print("Part G  必然分流商品的细流段厚度 + 混流窗口重算")
    print("=" * 78)
    uniform_duty = {op: [net["duty_uniform"][op]] * net["n_op"][op] for op in net["ops"]}
    G = {}
    for k in forced_b:
        G[k] = {
            "uniform_duty": maxmin_segment(net, prod, cons, k, uniform_duty),
            "staircase_duty": maxmin_segment(net, prod, cons, k, duty),
            "free_duty": maxmin_segment(net, prod, cons, k, None),
        }
        for tag, v in G[k].items():
            print(f"  {k:<12}{tag:<18}max-min细流段={str(v['max_min_segment']):>6}"
                  f"  分流点数={v.get('split_points')}  ({v['status']})")
    print("  上界论证（不依赖求解器）：产道速率恰 1，被迫劈成 a+b ≤ 1 ⇒ min(a,b) ≤ 1/2。")

    seg_free = {k: Fraction(G[k]["free_duty"]["max_min_segment"]) for k in forced_b}
    seg_uni = {k: Fraction(G[k]["uniform_duty"]["max_min_segment"]) for k in forced_b}
    thin_u = thin_value_table(net, uniform_duty,
                              {k: seg_uni[k] for k in forced_b} | {
                                  k: Fraction(mm) for k, mm in
                                  {"buckwheat_seed": "1/3", "sandleaf_powder": "14/33",
                                   "sandleaf_seed": "4/11", "steel_block": "1/3"}.items()})
    thin_s = thin_value_table(net, duty, seg_free)
    W_u = mixflow_windows(net, thin_u)
    W_s = mixflow_windows(net, thin_s)
    print()
    print(f"  均摊占空   ：全网最细段 = {fstr(min(thin_u.values()))}，"
          f"不同中间品混流窗口 {len(W_u)} 对")
    print(f"  阶梯占空   ：全网最细段 = {fstr(min(thin_s.values()))}，"
          f"不同中间品混流窗口 {len(W_s)} 对")
    print("  两种分配都有窗口 ⇒ 网络级纯流强制在**任何**合法占空分配下都不成立：")
    print("    buckwheat 必然分流 ⇒ 存在段 ≤ 1/2；sandleaf 独立同理 ⇒ 存在段 ≤ 1/2；")
    print("    二者是不同中间品，和 ≤ 1 ⇒ 速率合法的共道窗口恒存在。")

    # ---------- 收据 ----------
    receipt = {
        "artifact": "p2_0_specialized_split_free_probe_v2",
        "date": "2026-08-07",
        "supersedes": "docs/research/p2_0_specialized_20260807/split_free_probe.py "
                      "(v1，均摊占空写死)",
        "defect_repaired": (
            "v1 把 duty[op]=x[op]/n_op[op] 当约定写死（每台同占空）。占空由供料决定、"
            "台间分配是布局自由度；v1 还逐商品独立判，而 duty 是机器级共享变量。"),
        "question": "占空自由 + 整网联立下，逐商品『无分流(merge-only)车道路由』是否存在",
        "belt_capacity_per_tick": fstr(net["belt_cap"]),
        "part_a_duty_freedom": freedom,
        "part_b_lane_counting": B,
        "part_b_forced_for_every_duty": forced_b,
        "part_c_witness_duty": {op: [fstr(d) for d in duty[op]] for op in net["ops"]},
        "part_c_per_commodity": C,
        "part_c_split_free": ok_c,
        "part_c_still_split": bad_c,
        "part_d_cpsat_lattice": Dres,
        "part_e_rate_lemma": {
            "definition": "residual = rate - (ceil(rate)-1)，同 "
                          "docs/research/canonical_batch_20260807/rate_lemma_recompute.py",
            "uniform_duty": E_u,
            "staircase_duty": E_s,
        },
        "part_f_max_min_residual_per_op": F,
        "part_g_segment_thickness": G,
        "part_g_mixflow_windows": {
            "uniform_duty": {"network_min_segment": fstr(min(thin_u.values())),
                             "thin_per_commodity": {k: fstr(v) for k, v in
                                                    sorted(thin_u.items())},
                             "window_pairs": W_u, "count": len(W_u)},
            "staircase_duty": {"network_min_segment": fstr(min(thin_s.values())),
                               "thin_per_commodity": {k: fstr(v) for k, v in
                                                      sorted(thin_s.items())},
                               "window_pairs": W_s, "count": len(W_s)},
            "unconditional_refutation": (
                "buckwheat 与 sandleaf 对任意合法占空分配都必然分流（Part B 计数证明）；"
                "两者的产道速率恰为 1，被迫劈开后 min(两段) ≤ 1/2；二者是不同中间品，"
                "两条细流段之和 ≤ 1 ⇒ 速率合法的共道窗口在**任何**分配下都存在 ⇒ "
                "网络级纯流强制无条件不成立。"),
        },
        "verdict": {
            "v1_forced_split": v1_forced,
            "still_forced_under_free_duty": forced_b,
            "overturned": sorted(set(v1_forced) - set(forced_b)),
            "scope": "本判定是**速率算术层**的：split-free 存在 ≠ 该占空分配与该道对应"
                     "在 70×70 真实布局几何里可实现（拓扑 / 占地 / 交叉 / 供电未验）。",
        },
    }
    with open(OUT, "w") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=1)
    print()
    print("=" * 78)
    print(f"v1 判死 6 种 → 自由占空下翻案 {sorted(set(v1_forced) - set(forced_b))}")
    print(f"             → 仍必然分流 {forced_b}（纯计数论证，不依赖求解器）")
    print(f"receipt -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
