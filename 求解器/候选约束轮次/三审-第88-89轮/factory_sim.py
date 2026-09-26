#!/usr/bin/env python3
"""全厂专用进路接法：随机相位逐事件模拟（三审自写）。

用法：python3 -B factory_sim.py 种子 次数 [control]

按「全厂专用进路接法达标」的接法建 221 台制造单位、52 个矿石来源、两条成品汇（协议核心收电池、收胶囊分开开关），
每条专用进路长 1—3 格，砂叶粉末的 32 条取货通道随机分给 32 台研磨机（10 台砂叶粉碎机各 3 条、1 台 2 条）。
1 tick 取 Q 个时间单位（Q 在 1、2、3、5、7、12 里随机）；起态每格物品都对（件数、已停留时间、缓存格剩余时间随机），
每个采种单元在 0 时刻闭合后 Φ≥L1+L2+5/2。
对手期（200—600 tick）：判定先后随机（含轮询、离线改接通先后），两种成品随机停收再恢复（停收时回压传遍上游，
恢复的时刻任意，把新相位带进全厂）；确定期：判定先后固定、轮询按指针、协议核心一直收，跑到状态重复，再走一整个周期核：
  1. 一个周期里电池、胶囊进仓库的件数恰为 0.6、0.55 乘周期；52 个矿石来源每个恰为周期件数；
  2. 除单路供钢的塑形机与第三台灌装机外，每台制造单位在每个时刻闭合后缓存格都不空；
  3. 起点是 1 tick 配方制造单位（单路供钢的塑形机除外）或矿石来源的进路，每格在每个时刻闭合后都有物品；
  4. 第三台灌装机的钢质瓶存货至多 11 件；单路供钢的塑形机钢块存货至多 3 件。
control：把一个采种单元的回路存量压到阈值以下（只在 CA 上放 1 粒种子），看模拟查得出不达标。
"""
import json
import random
import sys
from fractions import Fraction

from engine import Net

ITEM_OUT = {}  # 机器号 -> 产物（本线）


class Factory(Net):
    def __init__(self, Q, rng):
        super().__init__(Q, rng)
        self.checking = False
        self.xfer_set = set()
        self.vac_set = set()
        self.claim_m = set()
        self.claim_c = set()
        self.viol_m = 0
        self.viol_c = 0
        self.max_bottle = 0
        self.max_steel6 = 0
        self.ore_cnt = None
        self.on_leave = self._leave
        self.on_ore = self._ore
        self.nev = 0
        self.phases = set()

    def _leave(self, c):
        if self.checking and c in self.claim_c:
            self.vac_set.add(c)

    def _ore(self, o):
        if self.ore_cnt is not None:
            self.ore_cnt[o] += 1

    def act_mach(self, i):
        m = self.machs[i]
        before = m['cache']
        r = super().act_mach(i)
        if r and self.checking and before is not None and m['cache'] is None:
            self.xfer_set.add(i)
        return r

    def pre_closure(self):
        self.xfer_set = set()
        self.vac_set = set()

    def post_closure(self):
        if not self.checking:
            return
        self.nev += 1
        self.phases.add(self.t % self.Q)
        for i in self.xfer_set:
            if i in self.claim_m and self.machs[i]['cache'] is None:
                self.viol_m += 1
        for c in self.vac_set:
            if self.cells[c][0] is None:
                self.viol_c += 1
        b = self.machs[self.F[2]]['store'].get('钢质瓶', 0)
        self.max_bottle = max(self.max_bottle, b)
        s6 = self.machs[self.S[5]]['store'].get('钢块', 0)
        self.max_steel6 = max(self.max_steel6, s6)


def build(rng, control):
    Q = rng.choice([1, 2, 3, 5, 7, 12])
    f = Factory(Q, rng)
    L = lambda: rng.randint(1, 3)
    lines = []   # (src, dst, cells, item)

    def ln(src, dst, item):
        cs = f.line(src, dst, L())
        lines.append((src, dst, cs, item))
        return cs

    batt = f.sink('协议核心（电池）')
    caps = f.sink('协议核心（胶囊）')
    f.batt, f.caps = batt, caps
    M = lambda name, typ: f.mach(name, typ)
    # 矿线
    ore_fe = [f.ore('蓝铁矿') for _ in range(34)]
    ore_src = [f.ore('源矿') for _ in range(18)]
    R_ore = [M(f'矿精炼{i}', '精炼炉') for i in range(34)]
    Cr_fe = [M(f'铁块粉碎{i}', '粉碎机') for i in range(34)]
    Cr_src = [M(f'源矿粉碎{i}', '粉碎机') for i in range(18)]
    for i in range(34):
        ln(('o', ore_fe[i]), ('m', R_ore[i]), '蓝铁矿')
        ln(('m', R_ore[i]), ('m', Cr_fe[i]), '蓝铁块')
    for i in range(18):
        ln(('o', ore_src[i]), ('m', Cr_src[i]), '源矿')
    G_fe = [M(f'蓝铁研磨{i}', '研磨机') for i in range(17)]
    G_src = [M(f'源石研磨{i}', '研磨机') for i in range(9)]
    G_q = [M(f'荞花研磨{i}', '研磨机') for i in range(6)]
    for i in range(17):
        ln(('m', Cr_fe[2 * i]), ('m', G_fe[i]), '蓝铁粉末')
        ln(('m', Cr_fe[2 * i + 1]), ('m', G_fe[i]), '蓝铁粉末')
    for i in range(9):
        ln(('m', Cr_src[2 * i]), ('m', G_src[i]), '源石粉末')
        ln(('m', Cr_src[2 * i + 1]), ('m', G_src[i]), '源石粉末')
    # 采种单元
    units = []
    for plant, n, seed, powder in (('砂叶', 11, '砂叶种子', '砂叶粉末'), ('荞花', 6, '荞花种子', '荞花粉末')):
        for i in range(n):
            C = M(f'{plant}采种{i}', '采种机')
            A = M(f'{plant}种植A{i}', '种植机')
            B = M(f'{plant}种植B{i}', '种植机')
            K = M(f'{plant}粉碎{i}', '粉碎机')
            CA = ln(('m', C), ('m', A), seed)
            CB = ln(('m', C), ('m', B), seed)
            AC = ln(('m', A), ('m', C), plant)
            BK = ln(('m', B), ('m', K), plant)
            units.append(dict(plant=plant, seed=seed, powder=powder, C=C, A=A, B=B, K=K, CA=CA, AC=AC))
    sandK = [u['K'] for u in units if u['plant'] == '砂叶']
    qK = [u['K'] for u in units if u['plant'] == '荞花']
    for i in range(6):
        ln(('m', qK[i]), ('m', G_q[i]), '荞花粉末')
        ln(('m', qK[i]), ('m', G_q[i]), '荞花粉末')
    nex = [3] * 11
    nex[rng.randrange(11)] = 2
    exits = [k for k, n in zip(sandK, nex) for _ in range(n)]
    grinders = G_fe + G_src + G_q
    rng.shuffle(exits)
    for k, g in zip(exits, grinders):
        ln(('m', k), ('m', g), '砂叶粉末')
    R_st = [M(f'制钢精炼{i}', '精炼炉') for i in range(17)]
    for i in range(17):
        ln(('m', G_fe[i]), ('m', R_st[i]), '致密蓝铁粉末')
    P = [M(f'配件{i}', '配件机') for i in range(6)]
    S = [M(f'塑形{i}', '塑形机') for i in range(6)]
    for i in range(6):
        ln(('m', R_st[i]), ('m', P[i]), '钢块')
    for i in range(5):
        ln(('m', R_st[6 + 2 * i]), ('m', S[i]), '钢块')
        ln(('m', R_st[7 + 2 * i]), ('m', S[i]), '钢块')
    ln(('m', R_st[16]), ('m', S[5]), '钢块')
    E = [M(f'封装{i}', '封装机') for i in range(3)]
    F = [M(f'灌装{i}', '灌装机') for i in range(3)]
    for i in range(3):
        ln(('m', P[2 * i]), ('m', E[i]), '钢制零件')
        ln(('m', P[2 * i + 1]), ('m', E[i]), '钢制零件')
        for j in range(3):
            ln(('m', G_src[3 * i + j]), ('m', E[i]), '致密源石粉末')
        ln(('m', S[2 * i]), ('m', F[i]), '钢质瓶')
        ln(('m', S[2 * i + 1]), ('m', F[i]), '钢质瓶')
        ln(('m', G_q[2 * i]), ('m', F[i]), '细磨荞花粉末')
        ln(('m', G_q[2 * i + 1]), ('m', F[i]), '细磨荞花粉末')
        ln(('m', E[i]), ('s', batt), '高容谷地电池')
        ln(('m', F[i]), ('s', caps), '精选荞愈胶囊')
    f.E, f.F, f.S, f.units = E, F, S, units
    counts = {}
    for m in f.machs:
        counts[m['typ']] = counts.get(m['typ'], 0) + 1
    f.counts = counts
    # 各机的原料与产物（本线）
    ins = {i: {} for i in range(len(f.machs))}
    outs = {}
    for src, dst, cs, item in lines:
        if dst[0] == 'm':
            ins[dst[1]][item] = ins[dst[1]].get(item, 0) + 1
        if src[0] == 'm':
            outs[src[1]] = item
    f.lines = lines
    # 起态
    fillp = rng.random()
    for src, dst, cs, item in lines:
        for c in cs:
            if rng.random() < fillp:
                f.cells[c][0] = item
                f.cells[c][1] = -rng.randint(0, 2 * Q)
    for i, m in enumerate(f.machs):
        # 找到本机要做的配方
        rec = next(r for r in m['rec'] if set(r[0]) == set(ins[i]))
        for it in rec[0]:
            n = rng.randint(0, 50)
            if n:
                m['store'][it] = n
        n = rng.randint(0, 50)
        if n:
            m['pk_item'] = rec[1]
            m['pk_n'] = n
        if rng.random() < 0.6:
            m['cache'] = (rec[1], rec[2], rng.randint(0, rec[3] * Q))
    if control:
        u = rng.choice(units)
        for key in ('C', 'A'):
            m = f.machs[u[key]]
            m['store'] = {}
            m['pk_item'] = None
            m['pk_n'] = 0
            m['cache'] = None
        for c in u['CA'] + u['AC']:
            f.cells[c][0] = None
        f.cells[u['CA'][0]][0] = u['seed']
        f.cells[u['CA'][0]][1] = 0
    else:
        for u in units:
            # 保证回路存量够：A 存货物品格补满种子
            if rng.random() < 0.5:
                f.machs[u['A']]['store'] = {u['seed']: 50}
    # 声称不空手的机器、声称每格都有物品的进路
    f.claim_m = set(range(len(f.machs))) - {S[5], F[2]}
    one_tick_src = {i for i in range(len(f.machs)) if i not in (S[5],) and i not in E and i not in F}
    for src, dst, cs, item in lines:
        if src[0] == 'o' or (src[0] == 'm' and src[1] in one_tick_src):
            f.claim_c.update(cs)
    return f


def phi(f, u):
    mc, ma = f.machs[u['C']], f.machs[u['A']]
    v = Fraction(sum(1 for c in u['CA'] + u['AC'] if f.cells[c][0] is not None))
    v += sum(ma['store'].values()) + (1 if ma['cache'] else 0) + ma['pk_n']
    v += sum(mc['store'].values()) + (1 if mc['cache'] else 0) + Fraction(mc['pk_n'], 2)
    return v


def run_one(rng, control):
    f = build(rng, control)
    Q = f.Q
    f.set_mode(True)
    f.start(0)
    ok_start = all(phi(f, u) >= len(u['CA']) + len(u['AC']) + Fraction(5, 2) for u in f.units)
    if not control and not ok_start:
        return dict(skipped=True)
    Tadv = rng.randint(200, 600) * Q
    t = 0
    nstop = 0
    while t < Tadv:
        t2 = min(Tadv, t + rng.randint(1, 60 * Q))
        f.advance_to(t2)
        t = t2
        for s in (f.batt, f.caps):
            if rng.random() < 0.5:
                st = rng.random() < 0.55
                nstop += int(not st)
                f.set_sink(s, st)
        f.poke()
    f.set_sink(f.batt, True)
    f.set_sink(f.caps, True)
    f.poke()
    f.set_mode(False)
    T0 = f.t
    seen = {}
    kk = 0
    found = None
    while kk < 30000:
        key = f.snapshot()
        if key in seen:
            found = (seen[key], kk)
            break
        seen[key] = kk
        f.advance_to(T0 + (kk + 1) * Q)
        kk += 1
    if found is None:
        return dict(skipped=False, cycle=False, Q=Q)
    per = found[1] - found[0]
    snap0 = f.snapshot()
    start_t = f.t
    got0 = dict(f.sinks[f.batt]['got']), dict(f.sinks[f.caps]['got'])
    f.ore_cnt = [0] * len(f.ores)
    f.checking = True
    # 起点状态也要核
    viol_m0 = sum(1 for i in f.claim_m if f.machs[i]['cache'] is None)
    viol_c0 = sum(1 for c in f.claim_c if f.cells[c][0] is None)
    f.advance_to(start_t + per * Q)
    f.checking = False
    assert f.snapshot() == snap0, '周期复核失败'
    nb = f.sinks[f.batt]['got'].get('高容谷地电池', 0) - got0[0].get('高容谷地电池', 0)
    nc = f.sinks[f.caps]['got'].get('精选荞愈胶囊', 0) - got0[1].get('精选荞愈胶囊', 0)
    res = dict(skipped=False, cycle=True, Q=Q, per=per, transient=found[1], nstop=nstop,
               batt=nb, caps=nc, batt_ok=(Fraction(nb, per) == Fraction(3, 5)),
               caps_ok=(Fraction(nc, per) == Fraction(11, 20)),
               ore_ok=all(x == per for x in f.ore_cnt), ore_min=min(f.ore_cnt), ore_max=max(f.ore_cnt),
               viol_m=f.viol_m + viol_m0, viol_c=f.viol_c + viol_c0,
               max_bottle=f.max_bottle, max_steel6=f.max_steel6, phases=len(f.phases), events=f.nev,
               counts=f.counts, control=control)
    return res


def main():
    seed = int(sys.argv[1])
    n = int(sys.argv[2])
    control = len(sys.argv) > 3 and sys.argv[3] == 'control'
    rng = random.Random(seed)
    for _ in range(n):
        r = run_one(rng, control)
        r['seed'] = seed
        print(json.dumps(r, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
