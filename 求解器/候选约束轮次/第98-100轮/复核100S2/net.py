#!/usr/bin/env python3
"""复核100S2：按推导98S2第2节文字独立重建230台接法（不读推导席的脚本或图文件）。

只描述物料图：机器、配方、每条纯带进路的起点与终点。两套引擎（engine_a.py 自写，
engine_sim2.py 借用项目独立模拟器 sim2）都从这里取图。
"""

# 物品名用规则里的名字
ORE_S = '源矿'; ORE_B = '蓝铁矿'
BLOCK = '蓝铁块'; BPOW = '蓝铁粉末'; SPOW = '源石粉末'
SL = '砂叶'; SLS = '砂叶种子'; SLP = '砂叶粉末'
QH = '荞花'; QHS = '荞花种子'; QHP = '荞花粉末'
DB = '致密蓝铁粉末'; DS = '致密源石粉末'; FQ = '细磨荞花粉末'
STEEL = '钢块'; PART = '钢制零件'; BOTTLE = '钢质瓶'
BAT = '高容谷地电池'; CAP = '精选荞愈胶囊'

SIZE = {'粉碎机': 'small', '精炼炉': 'small', '配件机': 'small', '塑形机': 'small',
        '种植机': 'medium', '采种机': 'medium',
        '研磨机': 'large', '封装机': 'large', '灌装机': 'large'}


def build():
    """返回 machines, sources, paths。

    machines: name -> dict(type, inputs{kind:amt}, product, qty, dur, role)
    sources: name -> dict(kind, nout)   （协议核心、仓库取货口）
    paths: list of dict(src, dst, kind)
    role: 'contract'（按请求供货）、'slow'（H6、Q6）、'final'、'C'、'A'、'B'、'K'
    """
    M, S, P = {}, {}, []

    def mach(name, typ, inputs, product, qty=1, dur=8, role='contract'):
        assert name not in M
        M[name] = dict(type=typ, inputs=dict(inputs), product=product, qty=qty, dur=dur, role=role)

    def path(src, dst, kind):
        P.append(dict(src=src, dst=dst, kind=kind))

    S['核心'] = dict(kind=ORE_S, nout=6)
    # 34 条蓝铁矿：仓库取货口 -> 精炼炉 -> 蓝铁块粉碎机 -> Bi
    for i in range(1, 35):
        S[f'W蓝{i}'] = dict(kind=ORE_B, nout=1)
        mach(f'炼{i}', '精炼炉', {ORE_B: 1}, BLOCK)
        mach(f'铁碎{i}', '粉碎机', {BLOCK: 1}, BPOW)
        path(f'W蓝{i}', f'炼{i}', ORE_B)
        path(f'炼{i}', f'铁碎{i}', BLOCK)
    # 18 条源矿：前六条来自协议核心，其余仓库取货口
    for i in range(1, 19):
        mach(f'源碎{i}', '粉碎机', {ORE_S: 1}, SPOW)
        if i <= 6:
            path('核心', f'源碎{i}', ORE_S)
        else:
            S[f'W源{i}'] = dict(kind=ORE_S, nout=1)
            path(f'W源{i}', f'源碎{i}', ORE_S)
    for i in range(1, 18):
        mach(f'B{i}', '研磨机', {BPOW: 2, SLP: 1}, DB)
        path(f'铁碎{2*i-1}', f'B{i}', BPOW)
        path(f'铁碎{2*i}', f'B{i}', BPOW)
        mach(f'R{i}', '精炼炉', {DB: 1}, STEEL)
        path(f'B{i}', f'R{i}', DB)
    for i in range(1, 10):
        mach(f'O{i}', '研磨机', {SPOW: 2, SLP: 1}, DS)
        path(f'源碎{2*i-1}', f'O{i}', SPOW)
        path(f'源碎{2*i}', f'O{i}', SPOW)
    for i in range(1, 7):
        mach(f'P{i}', '配件机', {STEEL: 1}, PART)
        path(f'R{i}', f'P{i}', STEEL)
    for i in range(1, 7):
        mach(f'H{i}', '塑形机', {STEEL: 2}, BOTTLE, role='slow' if i == 6 else 'contract')
    for h, rs in {1: (7, 8), 2: (9, 10), 3: (11, 12), 4: (13, 14), 5: (15, 16), 6: (17,)}.items():
        for r in rs:
            path(f'R{r}', f'H{h}', STEEL)
    for i in range(1, 7):
        mach(f'Q{i}', '研磨机', {QHP: 2, SLP: 1}, FQ, role='slow' if i == 6 else 'contract')
    for i in range(1, 4):
        mach(f'E{i}', '封装机', {PART: 10, DS: 15}, BAT, dur=40, role='final')
        path(f'P{2*i-1}', f'E{i}', PART)
        path(f'P{2*i}', f'E{i}', PART)
        for o in (3*i-2, 3*i-1, 3*i):
            path(f'O{o}', f'E{i}', DS)
    for i in range(1, 5):
        mach(f'F{i}', '灌装机', {BOTTLE: 10, FQ: 10}, CAP, dur=40, role='final')
    for f, hs, qs in ((1, (1, 2), (1, 2)), (2, (3, 4), (3, 4)), (3, (5,), (5,)), (4, (6,), (6,))):
        for h in hs:
            path(f'H{h}', f'F{f}', BOTTLE)
        for q in qs:
            path(f'Q{q}', f'F{f}', FQ)
    for i in range(1, 4):
        path(f'E{i}', '核心', BAT)
    for i in range(1, 5):
        path(f'F{i}', '核心', CAP)

    def unit(prefix, plant, seed, powder, k):
        mach(prefix + 'C', '采种机', {plant: 1}, seed, qty=2, role='C')
        mach(prefix + 'A', '种植机', {seed: 1}, plant, role='A')
        mach(prefix + 'B', '种植机', {seed: 1}, plant, role='B')
        mach(prefix + 'K', '粉碎机', {plant: 1}, powder, qty=k, role='K')
        path(prefix + 'C', prefix + 'A', seed)
        path(prefix + 'C', prefix + 'B', seed)
        path(prefix + 'A', prefix + 'C', plant)
        path(prefix + 'B', prefix + 'K', plant)

    sand = {1: ['B1', 'B2', 'O1'], 2: ['O2', 'O3'], 3: ['B3', 'B4', 'O4'], 4: ['O5', 'O6'],
            5: ['B5', 'B6', 'O7'], 6: ['O8', 'O9'], 7: ['B7', 'B8', 'B9'], 8: ['B10', 'Q1', 'Q2'],
            9: ['B11', 'B12', 'B13'], 10: ['B14', 'Q3', 'Q4'], 11: ['B15', 'B16', 'Q5'],
            12: ['B17'], 13: ['Q6']}
    for s, dsts in sand.items():
        unit(f'砂{s}', SL, SLS, SLP, 3)
        for d in dsts:
            path(f'砂{s}K', d, SLP)
    for q in range(1, 7):
        unit(f'荞{q}', QH, QHS, QHP, 2)
        path(f'荞{q}K', f'Q{q}', QHP)
        if q <= 5:
            path(f'荞{q}K', f'Q{q}', QHP)
    return M, S, P


def summary():
    M, S, P = build()
    from collections import Counter
    c = Counter(m['type'] for m in M.values())
    return dict(machines=len(M), by_type=dict(c), paths=len(P), sources=len(S),
                ore_paths=sum(1 for p in P if p['src'] in S))


if __name__ == '__main__':
    import json
    print(json.dumps(summary(), ensure_ascii=False, indent=1))
