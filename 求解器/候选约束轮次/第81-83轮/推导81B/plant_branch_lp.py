#!/usr/bin/env python3
"""第81轮B：植物回路“无分叉则不能粉碎”的独立核对（不依赖正式「植物再生来路」的证明路径）。

模型：一种植物，种植机结点 P1..Pm、采种机结点 S1..Sn、一个粉碎汇点 C。
无分叉＝每个结点的产物只送往一个下家：succ(P) ∈ {S..., C}，succ(S) ∈ {P...}；允许汇合。
循环态平均批率 r ≥ 0，每台 ≤ 1；种植机收种 = 2×上家采种批率之和 = 自身批率；
采种机收株 = 上家种植批率之和 = 自身批率。最大化 F = 送往 C 的种植批率之和。
两套求解器：scipy HiGHS 与 OR-Tools GLOP。另做对照：允许一个种植机把植株分两路（一路采种、一路 C），F 应可为正。
"""
import itertools, json, os
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from ortools.linear_solver import pywraplp

os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
HERE = Path(__file__).resolve().parent


def build(m, n, succP, succS, split=None):
    # 变量：rP[0..m), rS[0..n)，若 split=(i,j) 则 P_i 另有两路流量 xS, xC
    nv = m + n + (2 if split else 0)
    Aeq, beq = [], []
    for p in range(m):  # 种植机收种 = 自身批率
        row = [0.0] * nv
        row[p] = 1.0
        for s in range(n):
            if succS[s] == p:
                row[m + s] -= 2.0
        Aeq.append(row); beq.append(0.0)
    for s in range(n):  # 采种机收株 = 自身批率
        row = [0.0] * nv
        row[m + s] = 1.0
        for p in range(m):
            if split and p == split[0]:
                continue
            if succP[p] == ('S', s):
                row[p] -= 1.0
        if split and split[1] == s:
            row[m + n] -= 1.0
        Aeq.append(row); beq.append(0.0)
    if split:
        row = [0.0] * nv
        row[split[0]] = 1.0; row[m + n] = -1.0; row[m + n + 1] = -1.0
        Aeq.append(row); beq.append(0.0)
    c = [0.0] * nv  # 最大化 F
    for p in range(m):
        if split and p == split[0]:
            continue
        if succP[p] == ('C',):
            c[p] = -1.0
    if split:
        c[m + n + 1] = -1.0
    bounds = [(0, 1)] * (m + n) + ([(0, 1), (0, 1)] if split else [])
    return c, Aeq, beq, bounds


def solve_highs(c, Aeq, beq, bounds):
    r = linprog(c, A_eq=Aeq, b_eq=beq, bounds=bounds, method='highs')
    assert r.status == 0
    return -r.fun


def solve_glop(c, Aeq, beq, bounds):
    s = pywraplp.Solver.CreateSolver('GLOP')
    x = [s.NumVar(lo, hi, f'x{i}') for i, (lo, hi) in enumerate(bounds)]
    for row, b in zip(Aeq, beq):
        s.Add(sum(a * xi for a, xi in zip(row, x) if a) == b)
    s.Minimize(sum(ci * xi for ci, xi in zip(c, x) if ci))
    assert s.Solve() == pywraplp.Solver.OPTIMAL
    return -s.Objective().Value()


summary = []
worst = 0.0
for m in range(1, 4):
    for n in range(1, 4):
        cnt = 0
        mx_h = mx_g = 0.0
        optsP = [('S', s) for s in range(n)] + [('C',)]
        for succP in itertools.product(optsP, repeat=m):
            for succS in itertools.product(range(m), repeat=n):
                c, A, b, bd = build(m, n, succP, succS)
                fh = solve_highs(c, A, b, bd)
                fg = solve_glop(c, A, b, bd)
                mx_h = max(mx_h, fh); mx_g = max(mx_g, fg)
                cnt += 1
        # 对照：P0 分两路（到 S0 和 C），其余任意
        ctrl = []
        for succP in itertools.product(optsP, repeat=m):
            for succS in itertools.product(range(m), repeat=n):
                c, A, b, bd = build(m, n, succP, succS, split=(0, 0))
                ctrl.append(solve_highs(c, A, b, bd))
        summary.append(dict(m=m, n=n, graphs=cnt, maxF_highs=mx_h, maxF_glop=mx_g, split_control_maxF=max(ctrl)))
        worst = max(worst, mx_h, mx_g)
        print(summary[-1])
res = dict(summary=summary, max_crush_without_branch=worst,
           conclusion='无分叉时粉碎流量恒为 0' if worst < 1e-9 else '存在反例')
(HERE / 'plant_branch_lp.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(res['conclusion'])
