"""三审自写：(49,7) 七格条带（列 49..69、行 1..6）的全物料切线下界。

前提（逐条在三审报告里核过）：条带内至多一台完整大制造单位，必须是研磨机（总批次率 1/2..1，
两种矿物研磨批次率 G>=1/2）；没有跨线非运输单位，入口切线 6 条物理边，每条双向合计 <=1；
其余机身都经过第 4 行：6+3(粉碎+精炼+配件+塑形)+5(种植+采种)<=21，共 215 种台数组合。
满载机型（粉碎、精炼、配件、种植、采种）条带批次率之和等于台数；塑形机在 [n-1/2, n]；
各配方不超过全厂恰产率。7 个原矿入口中 z 个蓝铁矿、7-z 个源矿，z 放宽为 [0,7] 连续。
对 19 种物品，v_i=条带来源+配方净产出，周期守恒要求跨线双向总量 >= Σ|v_i|，须 <= 6。
本程序对 215 支各解一个线性规划 min Σ|v_i|，用两个执行器（scipy/HiGHS 与 OR-Tools GLOP）。
"""
import itertools
import json
from fractions import Fraction as Fr

import numpy as np
from scipy.optimize import linprog

ITEMS = ['蓝铁矿', '源矿', '蓝铁块', '蓝铁粉末', '源石粉末', '砂叶粉末', '砂叶', '砂叶种子', '荞花', '荞花种子',
         '荞花粉末', '致密蓝铁粉末', '钢块', '致密源石粉末', '细磨荞花粉末', '钢制零件', '钢质瓶', '电池', '胶囊']
# 配方：(机型, 名, {物品: 净产出}, 全厂恰产率上限)
RECIPES = [
    ('粉碎', 'c1', {'源矿': -1, '源石粉末': 1}, Fr(18)),
    ('粉碎', 'c2', {'蓝铁块': -1, '蓝铁粉末': 1}, Fr(34)),
    ('粉碎', 'c3', {'荞花': -1, '荞花粉末': 2}, Fr(11, 2)),
    ('粉碎', 'c4', {'砂叶': -1, '砂叶粉末': 3}, Fr(21, 2)),
    ('精炼', 'r1', {'蓝铁矿': -1, '蓝铁块': 1}, Fr(34)),
    ('精炼', 'r2', {'致密蓝铁粉末': -1, '钢块': 1}, Fr(17)),
    ('精炼', 'r3', {'蓝铁粉末': -1, '蓝铁块': 1}, Fr(0)),
    ('研磨', 'g1', {'蓝铁粉末': -2, '砂叶粉末': -1, '致密蓝铁粉末': 1}, Fr(17)),
    ('研磨', 'g2', {'源石粉末': -2, '砂叶粉末': -1, '致密源石粉末': 1}, Fr(9)),
    ('研磨', 'g3', {'荞花粉末': -2, '砂叶粉末': -1, '细磨荞花粉末': 1}, Fr(11, 2)),
    ('塑形', 's1', {'钢块': -2, '钢质瓶': 1}, Fr(11, 2)),
    ('配件', 'p1', {'钢块': -1, '钢制零件': 1}, Fr(6)),
    ('种植', 'z1', {'荞花种子': -1, '荞花': 1}, Fr(11)),
    ('种植', 'z2', {'砂叶种子': -1, '砂叶': 1}, Fr(21)),
    ('采种', 'a1', {'荞花': -1, '荞花种子': 2}, Fr(11, 2)),
    ('采种', 'a2', {'砂叶': -1, '砂叶种子': 2}, Fr(21, 2)),
]
TYPES = ['粉碎', '精炼', '配件', '塑形', '种植', '采种']


def combos():
    out = []
    for n in itertools.product(range(6), repeat=6):
        small = n[0] + n[1] + n[2] + n[3]
        med = n[4] + n[5]
        if 6 + 3 * small + 5 * med <= 21:
            out.append(dict(zip(TYPES, n)))
    return out


def lp_data(n):
    """变量：16 个配方率 + z + 19 个 t_i（|v_i| 的上界）。返回 (c, A_ub, b_ub, A_eq, b_eq, bounds)。"""
    nr = len(RECIPES)
    iz = nr
    it0 = nr + 1
    nv = nr + 1 + len(ITEMS)
    c = np.zeros(nv); c[it0:] = 1
    A_ub, b_ub, A_eq, b_eq = [], [], [], []
    # v_i 表达式系数
    def vrow(item):
        row = np.zeros(nv); const = 0.0
        for k, (_, _, net, _) in enumerate(RECIPES):
            row[k] += net.get(item, 0)
        if item == '蓝铁矿':
            row[iz] += 1
        if item == '源矿':
            row[iz] -= 1; const += 7
        return row, const
    for i, item in enumerate(ITEMS):
        row, const = vrow(item)
        # t_i >= v_i  ->  row - t_i <= -const ;  t_i >= -v_i -> -row - t_i <= const
        r1 = row.copy(); r1[it0 + i] -= 1; A_ub.append(r1); b_ub.append(-const)
        r2 = -row.copy(); r2[it0 + i] -= 1; A_ub.append(r2); b_ub.append(const)
    # 满载机型：条带批次率之和 = 台数
    for ty in ('粉碎', '精炼', '配件', '种植', '采种'):
        row = np.zeros(nv)
        for k, (t, *_rest) in enumerate(RECIPES):
            if t == ty:
                row[k] = 1
        A_eq.append(row); b_eq.append(n[ty])
    # 塑形 [n-1/2, n]
    row = np.zeros(nv); row[[k for k, r in enumerate(RECIPES) if r[0] == '塑形']] = 1
    A_ub.append(row.copy()); b_ub.append(n['塑形'])
    A_ub.append(-row); b_ub.append(-max(0.0, n['塑形'] - 0.5))
    # 研磨机一台：总批次率 [1/2,1]，矿物研磨 G>=1/2
    gidx = [k for k, r in enumerate(RECIPES) if r[0] == '研磨']
    row = np.zeros(nv); row[gidx] = 1
    A_ub.append(row.copy()); b_ub.append(1.0)
    A_ub.append(-row); b_ub.append(-0.5)
    row = np.zeros(nv); row[[k for k, r in enumerate(RECIPES) if r[1] in ('g1', 'g2')]] = 1
    A_ub.append(-row); b_ub.append(-0.5)
    bounds = [(0, float(r[3])) for r in RECIPES] + [(0, 7)] + [(0, None)] * len(ITEMS)
    return c, np.array(A_ub), np.array(b_ub), np.array(A_eq), np.array(b_eq), bounds


def solve_scipy(n):
    c, A_ub, b_ub, A_eq, b_eq, bounds = lp_data(n)
    r = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
    return r.status, (r.fun if r.status == 0 else None)


def solve_glop(n):
    from ortools.linear_solver import pywraplp
    c, A_ub, b_ub, A_eq, b_eq, bounds = lp_data(n)
    s = pywraplp.Solver.CreateSolver('GLOP')
    x = [s.NumVar(lo, hi if hi is not None else s.infinity(), f'x{k}') for k, (lo, hi) in enumerate(bounds)]
    for row, rhs in zip(A_ub, b_ub):
        s.Add(sum(float(row[k]) * x[k] for k in np.nonzero(row)[0]) <= float(rhs))
    for row, rhs in zip(A_eq, b_eq):
        s.Add(sum(float(row[k]) * x[k] for k in np.nonzero(row)[0]) == float(rhs))
    s.Minimize(sum(float(c[k]) * x[k] for k in range(len(x))))
    st = s.Solve()
    return st, (s.Objective().Value() if st == 0 else None)


def main():
    cs = combos()
    res = []
    for n in cs:
        st1, v1 = solve_scipy(n)
        st2, v2 = solve_glop(n)
        res.append(dict(n=n, scipy_status=st1, scipy=v1, glop_status=st2, glop=v2))
    feas = [r for r in res if r['scipy'] is not None]
    mins1 = min(r['scipy'] for r in feas)
    mins2 = min(r['glop'] for r in res if r['glop'] is not None)
    infeas = [r for r in res if r['scipy'] is None]
    summary = dict(combos=len(cs), lp_infeasible=len(infeas), min_scipy=mins1, min_glop=mins2,
                   n_attaining=sum(1 for r in feas if abs(r['scipy'] - mins1) < 1e-7),
                   disagree=sum(1 for r in res if (r['scipy'] is None) != (r['glop'] is None) or
                                (r['scipy'] is not None and abs(r['scipy'] - r['glop']) > 1e-6)))
    print(json.dumps(summary, ensure_ascii=False))
    json.dump(dict(summary=summary, branches=res), open('out/strip_b7.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
