#!/usr/bin/env python3
"""三审自写：仓库停收成品时哪些配方与矿石取货必在有限次后停止。

记账：仓库外每种物品件数有上限（运输格、制造单位物品格、缓存格一次一批、协议储存箱都有容量）；
非矿物品在仓库里也至多 80000，所以对非矿物品记「仓库外＋仓库」合计，入库与取出都不改合计；
矿石在仓库里持续可得（外部过程），只记仓库外件数：取货 +1，入库 −1（前提允许时）。
仍被接收的成品有一个无限的去处（玩家拿取），被停收的成品没有。
一个活动（配方或矿石取货）只能发生有限次 ⇔ 不存在非负平稳活动率使各记账量净变化为 0 而它为正。

写法甲：权重取某个物品集合上全 +1 或全 −1（2×2^19 组），反复用「减小加权量的活动都已有限 ⇒
增大它的活动也有限」传播，直到不动。
写法乙：对每个活动解线性规划求平稳活动率；为正的给出精确有理数平稳解，为零的给出精确的
Farkas 权重证书（每个活动不减小加权量、它严格增大），都用分数逐项核验。
配方从正式游戏规则解析。
"""
import itertools
import json
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ORES = ['蓝铁矿', '源矿']
PRODUCTS = ['高容谷地电池', '精选荞愈胶囊']


def parse():
    text = (REPO / '《明日方舟：终末地》游戏规则.txt').read_text()
    body = text.split('\n配方\n', 1)[1]
    machine, rec = None, []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if '→' not in line:
            machine = line
            continue
        left, right = line.split('→')
        right = right.split('，')[0]

        def terms(s):
            d = {}
            for t in s.strip().split('＋'):
                n, item = t.strip().split(' ', 1)
                d[item.strip()] = int(n)
            return d
        ins, outs = terms(left), terms(right)
        name = machine[:-1] + '·' + '+'.join(ins) + '→' + '+'.join(outs)
        rec.append((name, ins, outs))
    return rec


RECIPES = parse()
ITEMS = sorted({i for _, a, b in RECIPES for i in list(a) + list(b)})
assert len(RECIPES) == 18 and len(ITEMS) == 19


def activities(case, ore_return_allowed):
    """case: 集合，停收的成品。ore_return_allowed: 允许入库的矿石集合。"""
    acts = []
    for name, ins, outs in RECIPES:
        d = {i: 0 for i in ITEMS}
        for i, n in ins.items():
            d[i] -= n
        for i, n in outs.items():
            d[i] += n
        acts.append((name, d))
    for o in ORES:
        acts.append(('取货·' + o, {i: (1 if i == o else 0) for i in ITEMS}))
    for o in ore_return_allowed:
        acts.append(('入库·' + o, {i: (-1 if i == o else 0) for i in ITEMS}))
    for p in PRODUCTS:
        if p not in case:
            acts.append(('拿取·' + p, {i: (-1 if i == p else 0) for i in ITEMS}))
    return acts


def method_a(acts):
    n_items = len(ITEMS)
    D = np.array([[a[1][i] for i in ITEMS] for a in acts], dtype=np.int64)  # acts × items
    subsets = ((np.arange(1 << n_items)[:, None] >> np.arange(n_items)) & 1).astype(np.int64)
    P = subsets @ D.T  # subsets × acts
    bits = (1 << np.arange(len(acts))).astype(np.int64)
    pos = ((P > 0) * bits).sum(axis=1)
    neg = ((P < 0) * bits).sum(axis=1)
    fin = 0
    while True:
        new = fin
        for dec, inc in ((neg, pos), (pos, neg)):
            ok = (dec & ~new) == 0
            if ok.any():
                new |= int(np.bitwise_or.reduce(inc[ok]))
        if new == fin:
            break
        fin = new
    return {acts[k][0] for k in range(len(acts)) if fin >> k & 1}


def exact(v, den=100000):
    return Fraction(float(v)).limit_denominator(den)


def method_b(acts):
    m = len(acts)
    A = np.array([[a[1][i] for a in acts] for i in ITEMS], dtype=float)  # items × acts
    finite, certs = set(), {}
    for k in range(m):
        c = np.zeros(m)
        c[k] = -1
        r = linprog(c, A_eq=A, b_eq=np.zeros(len(ITEMS)), bounds=[(0, 1)] * m, method='highs')
        assert r.status == 0
        if -r.fun > 1e-9:
            x = [exact(v) for v in r.x]
            for i, item in enumerate(ITEMS):
                assert sum(Fraction(int(A[i][j])) * x[j] for j in range(m)) == 0, ('平稳解不精确', acts[k][0])
            assert x[k] > 0 and all(v >= 0 for v in x)
            certs[acts[k][0]] = {'平稳解': {acts[j][0]: str(x[j]) for j in range(m) if x[j] != 0}}
        else:
            # Farkas：找 π 使 π·Δ_b ≥ 0（全部 b），π·Δ_k ≥ 1
            n = len(ITEMS)
            A_ub = -A.T  # −π·Δ_b ≤ 0
            b_ub = np.zeros(m)
            b_ub[k] = -1
            r2 = linprog(np.zeros(n), A_ub=A_ub, b_ub=b_ub, bounds=[(-1000, 1000)] * n, method='highs')
            assert r2.status == 0, acts[k][0]
            pi = [exact(v, 1000) for v in r2.x]
            vals = [sum(pi[i] * Fraction(int(A[i][j])) for i in range(n)) for j in range(m)]
            assert all(v >= 0 for v in vals) and vals[k] > 0, ('证书不精确', acts[k][0])
            finite.add(acts[k][0])
            certs[acts[k][0]] = {'权重': {ITEMS[i]: str(pi[i]) for i in range(n) if pi[i] != 0}}
    return finite, certs


CASES = {
    '（一）电池停收；源矿不入库': ({'高容谷地电池'}, ['蓝铁矿']),
    '（二）胶囊停收': ({'精选荞愈胶囊'}, ['蓝铁矿', '源矿']),
    '（三）两种都停收；非成品都不入库': ({'高容谷地电池', '精选荞愈胶囊'}, []),
    '对照：电池停收但源矿可入库': ({'高容谷地电池'}, ['蓝铁矿', '源矿']),
    '对照：两种都停收但矿石可入库': ({'高容谷地电池', '精选荞愈胶囊'}, ['蓝铁矿', '源矿']),
}


def main():
    res = {}
    for label, (case, ret) in CASES.items():
        acts = activities(case, ret)
        fa = method_a(acts)
        fb, certs = method_b(acts)
        assert fa == fb, (label, fa ^ fb)
        stop = sorted(x for x in fa if not x.startswith(('入库', '拿取')))
        res[label] = {'必停（两法一致）': stop, '必停配方数': len([x for x in stop if not x.startswith('取货')]),
                      '可持续': sorted(a[0] for a in acts if a[0] not in fa), '证书': certs}
        print(label, len(stop), stop)
        print('   可持续:', res[label]['可持续'])
    (HERE / 'out' / 'freeze.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
