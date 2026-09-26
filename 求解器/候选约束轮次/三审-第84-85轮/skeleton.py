#!/usr/bin/env python3
"""三审自写：全厂专用进路接法（221 台）在共同相位（全部事件在整数 tick）下的逐 tick 模拟核对。

这不是证明，只核对证明里用到的几件事与关键数字：
- 台数 69、51、32、6、6、34、17、3、3，共 221；逻辑进路 317 条（矿 52、机器之间 259、成品 6）。
- 调试期结束时各格只有本线物品、每个采种单元 Φ ≥ L1+L2+5/2；此后一段「对手期」：
  每 tick 随机打乱全部判定的先后（含同一台机器几条取货通道谁先取），随机让仓库停收电池、胶囊或两种。
  这段里逐 tick 核对种群下界 Φ ≥ min(Φ0−1/2, L1+L2+176)。
- 然后仓库一直收两种成品、判定先后固定，跑到状态重复，得到一个可到达循环态，核对：
  52 条矿石进路每 tick 各 1 件、电池 0.6/tick、胶囊 0.55/tick；
  不空手传递与不断料所覆盖的机器（除单路塑形机、第三台灌装机与各单元的种植机 A 外）每 tick 结束缓存格都非空；
  第三台灌装机的钢质瓶格不超过 11 件。

规则取法：整数 tick；运输物品格上限 1、进格后下一 tick 才能再走；制造单位存货格按「同种一格、
空格收任何种类」；缓存格上一批全部进取货格才开下一批，完成后整批进取货格（放得下才进）；
同一 tick 的判定做到没有可动为止。配方从正式游戏规则解析。
"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CAP = 50


def parse_recipes():
    text = (REPO / '《明日方舟：终末地》游戏规则.txt').read_text()
    body = text.split('\n配方\n', 1)[1]
    machine, out = None, {}
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if '→' not in line:
            machine = line
            continue
        left, right = line.split('→')
        prod, dur = right.split('，')
        d = int(dur.strip().split()[0])

        def terms(s):
            r = {}
            for t in s.strip().split('＋'):
                n, item = t.strip().split(' ', 1)
                r[item.strip()] = int(n)
            return r
        ins, outs = terms(left), terms(prod)
        (oi, on), = outs.items()
        out[(machine, tuple(sorted(ins)))] = (ins, oi, on, d)
    return out


RECIPES = parse_recipes()


def recipe(machine, *inputs):
    return RECIPES[(machine, tuple(sorted(inputs)))]


class Net:
    def __init__(self):
        self.m_type, self.m_rec, self.m_ngrid = [], [], []
        self.m_in, self.m_out = [], []
        self.p_src, self.p_dst, self.p_len, self.p_item = [], [], [], []

    def machine(self, mtype, rec):
        self.m_type.append(mtype)
        self.m_rec.append(rec)
        self.m_ngrid.append(2 if mtype in ('研磨机', '封装机', '灌装机') else 1)
        self.m_in.append([])
        self.m_out.append([])
        return len(self.m_type) - 1

    def path(self, src, dst, item, L):
        """src: ('ore', 物品) 或 ('m', 机器)；dst: ('m', 机器) 或 ('core', 物品)。"""
        self.p_src.append(src)
        self.p_dst.append(dst)
        self.p_len.append(L)
        self.p_item.append(item)
        pid = len(self.p_src) - 1
        if src[0] == 'm':
            self.m_out[src[1]].append(pid)
        if dst[0] == 'm':
            self.m_in[dst[1]].append(pid)
        return pid


def build(rng, lmax):
    N = Net()
    Lr = lambda: rng.randint(1, lmax)
    units = []  # (物种, C, A, B, K, pCA, pAC)
    # 植物单元
    for species, cnt in (('砂叶', 11), ('荞花', 6)):
        seed = species + '种子'
        for _ in range(cnt):
            C = N.machine('采种机', recipe('采种机', species))
            A = N.machine('种植机', recipe('种植机', seed))
            B = N.machine('种植机', recipe('种植机', seed))
            K = N.machine('粉碎机', recipe('粉碎机', species))
            L1, L2 = Lr(), Lr()
            pCA = N.path(('m', C), ('m', A), seed, L1)
            N.path(('m', C), ('m', B), seed, Lr())
            pAC = N.path(('m', A), ('m', C), species, L2)
            N.path(('m', B), ('m', K), species, Lr())
            units.append((species, C, A, B, K, pCA, pAC, L1, L2))
    sand_K = [u[4] for u in units if u[0] == '砂叶']
    qiao_K = [u[4] for u in units if u[0] == '荞花']
    # 矿石初级
    R_ore = [N.machine('精炼炉', recipe('精炼炉', '蓝铁矿')) for _ in range(34)]
    F_iron = [N.machine('粉碎机', recipe('粉碎机', '蓝铁块')) for _ in range(34)]
    F_src = [N.machine('粉碎机', recipe('粉碎机', '源矿')) for _ in range(18)]
    ore_paths = []
    for r, f in zip(R_ore, F_iron):
        ore_paths.append(N.path(('ore', '蓝铁矿'), ('m', r), '蓝铁矿', Lr()))
        N.path(('m', r), ('m', f), '蓝铁块', Lr())
    for f in F_src:
        ore_paths.append(N.path(('ore', '源矿'), ('m', f), '源矿', Lr()))
    G_iron = [N.machine('研磨机', recipe('研磨机', '蓝铁粉末', '砂叶粉末')) for _ in range(17)]
    G_src = [N.machine('研磨机', recipe('研磨机', '源石粉末', '砂叶粉末')) for _ in range(9)]
    G_q = [N.machine('研磨机', recipe('研磨机', '荞花粉末', '砂叶粉末')) for _ in range(6)]
    for i, g in enumerate(G_iron):
        for f in F_iron[2 * i:2 * i + 2]:
            N.path(('m', f), ('m', g), '蓝铁粉末', Lr())
    for i, g in enumerate(G_src):
        for f in F_src[2 * i:2 * i + 2]:
            N.path(('m', f), ('m', g), '源石粉末', Lr())
    for k, g in zip(qiao_K, G_q):
        for _ in range(2):
            N.path(('m', k), ('m', g), '荞花粉末', Lr())
    grinders = G_iron + G_src + G_q
    order = grinders[:]
    rng.shuffle(order)
    slots = [k for k in sand_K[:10] for _ in range(3)] + [sand_K[10]] * 2
    rng.shuffle(slots)
    for g, k in zip(order, slots):
        N.path(('m', k), ('m', g), '砂叶粉末', Lr())
    R_steel = [N.machine('精炼炉', recipe('精炼炉', '致密蓝铁粉末')) for _ in range(17)]
    for g, r in zip(G_iron, R_steel):
        N.path(('m', g), ('m', r), '致密蓝铁粉末', Lr())
    parts = [N.machine('配件机', recipe('配件机', '钢块')) for _ in range(6)]
    shapers = [N.machine('塑形机', recipe('塑形机', '钢块')) for _ in range(6)]
    for r, p in zip(R_steel[:6], parts):
        N.path(('m', r), ('m', p), '钢块', Lr())
    for i in range(5):
        for r in R_steel[6 + 2 * i:8 + 2 * i]:
            N.path(('m', r), ('m', shapers[i]), '钢块', Lr())
    N.path(('m', R_steel[16]), ('m', shapers[5]), '钢块', Lr())
    packs = [N.machine('封装机', recipe('封装机', '钢制零件', '致密源石粉末')) for _ in range(3)]
    fills = [N.machine('灌装机', recipe('灌装机', '钢质瓶', '细磨荞花粉末')) for _ in range(3)]
    for i, pk in enumerate(packs):
        for p in parts[2 * i:2 * i + 2]:
            N.path(('m', p), ('m', pk), '钢制零件', Lr())
        for g in G_src[3 * i:3 * i + 3]:
            N.path(('m', g), ('m', pk), '致密源石粉末', Lr())
        N.path(('m', pk), ('core', '高容谷地电池'), '高容谷地电池', Lr())
    for i, fl in enumerate(fills):
        for s in shapers[2 * i:2 * i + 2]:
            N.path(('m', s), ('m', fl), '钢质瓶', Lr())
        for g in G_q[2 * i:2 * i + 2]:
            N.path(('m', g), ('m', fl), '细磨荞花粉末', Lr())
        N.path(('m', fl), ('core', '精选荞愈胶囊'), '精选荞愈胶囊', Lr())
    info = {'units': units, 'ore_paths': ore_paths, 'shaper6': shapers[5], 'fill3': fills[2],
            'relay_excluded': {shapers[5], fills[2]} | {u[2] for u in units}}
    return N, info


class Sim:
    def __init__(self, N, info, rng, extra_fill, low_seed=False):
        self.N, self.info, self.rng = N, info, rng
        nm = len(N.m_type)
        self.grids = [[[None, 0] for _ in range(N.m_ngrid[m])] for m in range(nm)]
        self.cache = [None] * nm  # [完成 tick, 已完成?]
        self.outg = [[None, 0] for _ in range(nm)]
        self.cells = [[None] * N.p_len[p] for p in range(len(N.p_src))]
        self.arr = [[0] * N.p_len[p] for p in range(len(N.p_src))]
        self.t = 0
        self.reject = set()
        self.delivered = {'高容谷地电池': 0, '精选荞愈胶囊': 0}
        self.ore_taken = [0] * len(N.p_src)
        # 调试期结束时的合法起态：路上、格里随机放本线物品；再给每个单元 A 的存货格补种子
        if extra_fill:
            for p in range(len(N.p_src)):
                for i in range(N.p_len[p]):
                    if rng.random() < 0.5:
                        self.cells[p][i] = N.p_item[p]
                        self.arr[p][i] = -1
            for m in range(nm):
                for pid in N.m_in[m]:
                    it = N.p_item[pid]
                    if rng.random() < 0.5:
                        self.put_in(m, it, rng.randint(1, 20))
                ins, oi, on, d = N.m_rec[m]
                if rng.random() < 0.5:
                    self.outg[m] = [oi, rng.randint(0, CAP)]
                    if self.outg[m][1] == 0:
                        self.outg[m][0] = None
        for (species, C, A, B, K, pCA, pAC, L1, L2) in info['units']:
            if low_seed:  # 对照：每个单元只放 1 粒种子，Φ 低于阈值
                self.grids[A][0] = [species + '种子', 1]
                continue
            need = 2 * (L1 + L2) + 6  # 2Φ ≥ 2(L1+L2)+6，即 Φ ≥ L1+L2+3
            while self.phi2(C, A, pCA, pAC) < need:
                g = self.grids[A][0]
                if g[1] >= CAP:
                    break
                g[0] = species + '种子'
                g[1] += 1
            assert self.phi2(C, A, pCA, pAC) >= need

    def put_in(self, m, item, n=1):
        gs = self.grids[m]
        for g in gs:
            if g[0] == item:
                if g[1] + n > CAP:
                    return False
                g[1] += n
                return True
        for g in gs:
            if g[0] is None:
                g[0], g[1] = item, n
                return True
        return False

    def accepts(self, m, item):
        gs = self.grids[m]
        for g in gs:
            if g[0] == item:
                return g[1] < CAP
        for g in gs:
            if g[0] is None:
                return True
        return False

    def phi2(self, C, A, pCA, pAC):
        """2Φ（整数）。"""
        N = self.N
        s = 0
        s += 2 * sum(1 for x in self.cells[pCA] if x is not None)
        s += 2 * sum(g[1] for g in self.grids[A])
        s += 2 * (self.cache[A] is not None)
        s += 2 * self.outg[A][1]
        s += 2 * sum(1 for x in self.cells[pAC] if x is not None)
        s += 2 * sum(g[1] for g in self.grids[C])
        s += 2 * (self.cache[C] is not None)
        s += self.outg[C][1]
        return s

    def step(self, order):
        N, t = self.N, self.t
        cells, arr = self.cells, self.arr
        for m in range(len(N.m_type)):
            c = self.cache[m]
            if c is not None and not c[1] and c[0] == t:
                c[1] = True
        changed = True
        while changed:
            changed = False
            for kind, x in order:
                if kind == 0:  # 路径 x：从尾到头逐格前移、尾格交出、首格取货
                    p = x
                    cl, ar = cells[p], arr[p]
                    L = N.p_len[p]
                    it = cl[L - 1]
                    if it is not None and ar[L - 1] <= t - 1:
                        dst = N.p_dst[p]
                        if dst[0] == 'core':
                            if it not in self.reject:
                                self.delivered[it] += 1
                                cl[L - 1] = None
                                changed = True
                        elif self.accepts(dst[1], it):
                            self.put_in(dst[1], it)
                            cl[L - 1] = None
                            changed = True
                    for i in range(L - 2, -1, -1):
                        if cl[i] is not None and cl[i + 1] is None and ar[i] <= t - 1:
                            cl[i + 1], ar[i + 1] = cl[i], t
                            cl[i] = None
                            changed = True
                    if cl[0] is None:
                        src = N.p_src[p]
                        if src[0] == 'ore':
                            cl[0], ar[0] = src[1], t
                            self.ore_taken[p] += 1
                            changed = True
                        else:
                            og = self.outg[src[1]]
                            if og[1] > 0:
                                cl[0], ar[0] = og[0], t
                                og[1] -= 1
                                if og[1] == 0:
                                    og[0] = None
                                changed = True
                else:  # 机器 x：整批进取货格、开新批
                    m = x
                    ins, oi, on, d = N.m_rec[m]
                    c = self.cache[m]
                    if c is not None and c[1]:
                        og = self.outg[m]
                        if (og[0] is None or og[0] == oi) and og[1] + on <= CAP:
                            og[0] = oi
                            og[1] += on
                            self.cache[m] = None
                            c = None
                            changed = True
                    if c is None:
                        gs = self.grids[m]
                        ok = True
                        for item, n in ins.items():
                            have = 0
                            for g in gs:
                                if g[0] == item:
                                    have = g[1]
                            if have < n:
                                ok = False
                                break
                        if ok:
                            for item, n in ins.items():
                                for g in gs:
                                    if g[0] == item:
                                        g[1] -= n
                                        if g[1] == 0:
                                            g[0] = None
                            self.cache[m] = [t + d, False]
                            changed = True
        self.t += 1

    def key(self):
        t = self.t
        mk = tuple((tuple(tuple(g) for g in self.grids[m]),
                    None if self.cache[m] is None else (self.cache[m][0] - t, self.cache[m][1]),
                    tuple(self.outg[m])) for m in range(len(self.N.m_type)))
        return (mk, tuple(tuple(c) for c in self.cells))


def run(seed, lmax, adv_ticks, max_ticks, low_seed=False):
    rng = random.Random(seed)
    N, info = build(rng, lmax)
    counts = {}
    for mt in N.m_type:
        counts[mt] = counts.get(mt, 0) + 1
    fill = rng.random() < 0.7
    sim = Sim(N, info, rng, extra_fill=fill and not low_seed, low_seed=low_seed)
    actions = [(0, p) for p in range(len(N.p_src))] + [(1, m) for m in range(len(N.m_type))]
    units = info['units']
    # 起态闭合：先走一个 tick，取它结束时的 Φ 作 Φ0
    order = actions[:]
    rng.shuffle(order)
    sim.step(order)
    phi0 = [sim.phi2(u[1], u[2], u[5], u[6]) for u in units]
    viol = 0
    min_margin = None
    for _ in range(adv_ticks):
        if rng.random() < 0.01:
            sim.reject = rng.choice([set(), {'高容谷地电池'}, {'精选荞愈胶囊'}, {'高容谷地电池', '精选荞愈胶囊'}])
        rng.shuffle(order)
        sim.step(order)
        for u, p0 in zip(units, phi0):
            L1, L2 = u[7], u[8]
            bound2 = min(p0 - 1, 2 * (L1 + L2 + 176))
            v = sim.phi2(u[1], u[2], u[5], u[6])
            if v < bound2:
                viol += 1
            mg = v - 2 * (L1 + L2 + 2)
            min_margin = mg if min_margin is None else min(min_margin, mg)
    sim.reject = set()
    rng.shuffle(order)
    fixed = order[:]
    seen = {}
    hist = []
    for i in range(max_ticks):
        sim.step(fixed)
        k = sim.key()
        empties = [m for m in range(len(N.m_type)) if sim.cache[m] is None]
        rec = (dict(sim.delivered), sum(sim.ore_taken[p] for p in info['ore_paths']),
               [sim.ore_taken[p] for p in info['ore_paths']], set(empties),
               max(g[1] for g in sim.grids[info['fill3']] if g[0] == '钢质瓶') if any(g[0] == '钢质瓶' for g in sim.grids[info['fill3']]) else 0)
        hist.append(rec)
        if k in seen:
            j = seen[k]
            P = i - j
            d0, d1 = hist[j], hist[i]
            bat = d1[0]['高容谷地电池'] - d0[0]['高容谷地电池']
            cap = d1[0]['精选荞愈胶囊'] - d0[0]['精选荞愈胶囊']
            ore_each = [b - a for a, b in zip(d0[2], d1[2])]
            idle = set()
            bottle = 0
            for r in hist[j + 1:i + 1]:
                idle |= r[3]
                bottle = max(bottle, r[4])
            relay_idle = sorted(idle - info['relay_excluded'])
            return {'seed': seed, '路长上限': lmax, '台数': counts, '总台数': len(N.m_type), '进路数': len(N.p_src),
                    '对手期种群下界违例': viol, '对手期 Φ−S 最小值（半件）': min_margin,
                    '循环起点': j, '周期': P, '电池/周期': bat, '胶囊/周期': cap,
                    '矿石进路每条每周期': sorted(set(ore_each)),
                    '达标': bat * 20 == 12 * P and cap * 20 == 11 * P and set(ore_each) == {P},
                    '不空手覆盖的机器在循环里空手': relay_idle, '第三台灌装机瓶格最大': bottle}
        seen[k] = i
    return {'seed': seed, '路长上限': lmax, '截断': max_ticks, '对手期种群下界违例': viol}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'control':
        # 对照：每个采种单元只放 1 粒种子（Φ 低于阈值），仓库一直收货、判定先后固定，
        # 跑 6000 tick 后再数 2000 tick 的交付，应明显低于 0.6、0.55
        res = []
        for s in range(1, 7):
            rng = random.Random(1000 + s)
            N, info = build(rng, 2)
            sim = Sim(N, info, rng, extra_fill=False, low_seed=True)
            order = [(0, p) for p in range(len(N.p_src))] + [(1, m) for m in range(len(N.m_type))]
            rng.shuffle(order)
            for _ in range(6000):
                sim.step(order)
            b0, c0 = sim.delivered['高容谷地电池'], sim.delivered['精选荞愈胶囊']
            for _ in range(2000):
                sim.step(order)
            r = {'seed': 1000 + s, '电池/tick': (sim.delivered['高容谷地电池'] - b0) / 2000,
                 '胶囊/tick': (sim.delivered['精选荞愈胶囊'] - c0) / 2000}
            res.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
        (HERE / 'out' / 'skeleton_control.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
        return
    seed0 = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    res = []
    for s in range(seed0, seed0 + n):
        rng = random.Random(s * 7919)
        r = run(s, rng.choice([1, 2, 3]), rng.choice([300, 800]), 12000)
        res.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)
    (HERE / 'out' / f'skeleton_{seed0}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
