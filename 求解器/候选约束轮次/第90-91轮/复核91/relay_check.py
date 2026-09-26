# -*- coding: utf-8 -*-
"""随机一般接法下核「专线制造单位不空手的传递」（第 88 轮两份 / 第 89 轮加源头开机）的结论。

每次随机建：一台被考察的 X（九种机型配方的形状：1 tick 单料 k=1/2/3、塑形 2→1、
研磨 2+1→1、采种 1→2；5 tick 封装 10+15、灌装 10+10），每种原料 c_i 条专线
（d·c_i≥a_i，多给 0—1 条），专线起点是仓库出口（矿石来源，一空即补）或一台起点
制造单位 Y（只做产物就是这种原料的 1 tick 配方，自己的原料来自仓库出口或更上游
一台 Z）。Y 另带通往随机开关收货端的取货通道与 X 争货，其中一部分首格是每 5 tick
限 k5 件的物品准入口（计入 Y 的全部取货通道）。X 的取货通道通往随机开关的收货端，
造成回压。各机开机时刻、对手期内的关机/开机、收货端停收/恢复都落在 1/Q 格点的
任意余数上。另有「环」模式：2—4 台 1 tick 机器首尾相接成环（回炼一类），
环里件数随机。

对每个检出的循环态逐判定核：
  前提成立（X 与各源头一直开机；各 Y 在循环每个闭合时刻缓存非空；各 Y 全部取货
  通道数≤每批件数；d·c_i≥a_i）⇒ X 每个闭合时刻缓存非空；
  X 也是 1 tick 配方、全部取货通道≤k 且首格独占可收 ⇒ 首格每个闭合时刻都有货，
  任一长 1 tick 的半开时段里首格「某时点为空」⇒ 恰取 1 件。
用法：python3 relay_check.py SEED N [mode]
  mode: normal（默认）| ring | extra_exit（对照：源头取货通道多于每批件数）
        | few_lines（对照：某原料少一条）| limit_line（对照：专线上有每 5 tick 限量准入口）
"""
import json
import math
import random
import sys

from engine import Net

TEMPL_1 = [
    ({'u': 1}, 1), ({'u': 1}, 2), ({'u': 1}, 3), ({'u': 2}, 1), ({'u': 2, 'v': 1}, 1),
]
TEMPL_X = [
    ({'u': 1}, 1, 1), ({'u': 1}, 2, 1), ({'u': 1}, 3, 1), ({'u': 2}, 1, 1),
    ({'u': 2, 'v': 1}, 1, 1), ({'u': 10, 'v': 15}, 1, 5), ({'u': 10, 'v': 10}, 1, 5),
]


class Gen:
    def __init__(self, rng, mode):
        self.rng = rng
        self.mode = mode
        self.item_ctr = 0

    def new_item(self):
        self.item_ctr += 1
        return self.item_ctr

    def rand_sched(self, net, t_trans):
        """random stop/resume in transient, periodic (or always open) afterwards."""
        rng = self.rng
        Q = net.Q
        toggles = sorted(rng.randrange(1, t_trans) for _ in range(rng.randrange(0, 6)))
        steady = rng.random()
        if steady < 0.5:
            period = None
            def f(t, toggles=toggles, t_trans=t_trans):
                if t > t_trans:
                    return True
                return sum(1 for x in toggles if x <= t) % 2 == 0
            return f, None
        P = rng.randrange(2, 9) * Q
        on = rng.randrange(1, P)
        off = rng.randrange(P)

        def g(t, toggles=toggles, t_trans=t_trans, P=P, on=on, off=off):
            if t > t_trans:
                return (t - off) % P < on
            return sum(1 for x in toggles if x <= t) % 2 == 0
        return g, P

    def sink_line(self, net, t_trans, n, item=None):
        f, P = self.rand_sched(net, t_trans)
        k = net.add_sink(f, P)
        return net.line(n, ('k', k), tag='sink', item=item)

    def add_source_machine(self, net, prod, depth, t_trans, info):
        """a 1-tick machine producing prod; returns (m, list of free output slots count)."""
        rng = self.rng
        inputs, k = rng.choice(TEMPL_1)
        inp = {}
        for key, a in inputs.items():
            inp[self.new_item()] = a
        nslots = len(inp)
        m = net.add_machine(inp, prod, k, 1, nslots, tag='Y')
        for it, a in inp.items():
            c = a + (1 if rng.random() < 0.3 else 0)  # d=1
            for _ in range(c):
                if depth > 0 and rng.random() < 0.4:
                    z, zfree = self.add_source_machine(net, it, depth - 1, t_trans, info)
                    cells = net.line(rng.randrange(1, 4), ('m', m), tag='Zline', item=it)
                    net.m_outch[z].append(cells[0])
                    zfree[0] -= 1
                    if zfree[0] > 0 and rng.random() < 0.5:
                        cells2 = self.sink_line(net, t_trans, rng.randrange(1, 3), item=it)
                        net.m_outch[z].append(cells2[0])
                        zfree[0] -= 1
                else:
                    cells = net.line(rng.randrange(1, 4), ('m', m), tag='Wline', item=it)
                    net.sources.append((it, cells[0]))
        return m, [k]

    def build(self):
        rng = self.rng
        Q = rng.choice([1, 2, 3, 4, 5, 6, 7, 12])
        net = Net(Q)
        t_trans = rng.randrange(40, 160) * Q
        info = {'Q': Q, 't_trans': t_trans}
        if self.mode == 'ring':
            return self.build_ring(net, t_trans, info)
        inputs, kX, d = rng.choice(TEMPL_X)
        inp = {}
        for key, a in inputs.items():
            inp[self.new_item()] = a
        prodX = self.new_item()
        X = net.add_machine(inp, prodX, kX, d, len(inp), tag='X')
        lines = {}
        ysrc = []
        for it, a in inp.items():
            cmin = math.ceil(a / d)
            c = cmin + (1 if rng.random() < 0.3 else 0)
            if self.mode == 'few_lines' and it == list(inp)[0]:
                c = cmin - 1 if cmin > 1 else 0
            lines[it] = []
            remaining = c
            while remaining > 0:
                if rng.random() < 0.35:
                    cells = net.line(rng.randrange(1, 5), ('m', X), tag='Xline', item=it)
                    net.sources.append((it, cells[0]))
                    lines[it].append(('W', None, cells))
                    remaining -= 1
                else:
                    y, yfree = self.add_source_machine(net, it, rng.randrange(0, 2), t_trans, info)
                    ky = net.m_k[y]
                    give = min(remaining, rng.randrange(1, ky + 1))
                    for _ in range(give):
                        gate = it if rng.random() < 0.2 else None
                        cells = net.line(rng.randrange(1, 5), ('m', X), allow_gate_item=gate, tag='Xline', item=it)
                        if self.mode == 'limit_line' and rng.random() < 0.7:
                            g = cells[0]
                            net.c_allow[g] = it
                            net.c_k5[g] = rng.randrange(1, 5)
                        net.m_outch[y].append(cells[0])
                        lines[it].append(('Y', y, cells))
                    remaining -= give
                    free = ky - give
                    extra = rng.randrange(0, free + 1)
                    if self.mode == 'extra_exit':
                        extra = free + 1
                    for _ in range(extra):
                        cells = self.sink_line(net, t_trans, rng.randrange(1, 3), item=it)
                        if rng.random() < 0.4:
                            net.c_allow[cells[0]] = it
                            net.c_k5[cells[0]] = rng.randrange(1, 5)
                        net.m_outch[y].append(cells[0])
                    ysrc.append(y)
        # X outputs
        nout = rng.randrange(1, kX + 1) if rng.random() < 0.85 else kX + 1
        xouts = []
        for _ in range(nout):
            cells = self.sink_line(net, t_trans, rng.randrange(1, 4), item=prodX)
            net.m_outch[X].append(cells[0])
            xouts.append(cells[0])
        # power: every machine switched on at a random grid time; random pauses in transient
        for m in range(len(net.m_in)):
            ton = rng.randrange(0, 20 * Q)
            net.m_pow[m] = (ton == 0)
            if ton > 0:
                net.power_events.append((ton, m, True))
            if rng.random() < 0.3:
                a = rng.randrange(ton + 1, t_trans - 2)
                b = rng.randrange(a + 1, t_trans)
                net.power_events.append((a, m, False))
                net.power_events.append((b, m, True))
        if rng.random() < 0.5:
            self.random_initial(net)
        info.update({'X': X, 'lines': lines, 'xouts': xouts, 'kind': 'tree'})
        return net, info

    def random_initial(self, net):
        """legal random start: line cells hold their own item with random age,
        inventories/outputs hold legal items, caches hold a legal batch at a random
        progress (so every unit starts at its own phase)."""
        rng = self.rng
        Q = net.Q
        for c in range(len(net.c_item)):
            if net.c_li[c] is not None and rng.random() < 0.5:
                net.c_item[c] = net.c_li[c]
                net.c_tin[c] = -rng.randrange(0, 2 * Q)
        for m in range(len(net.m_in)):
            for it in net.m_in[m]:
                if rng.random() < 0.6:
                    net.m_inv[m][it] = rng.randrange(0, 51)
            if rng.random() < 0.5:
                net.m_out[m] = rng.randrange(0, 51 - net.m_k[m])
            r = rng.random()
            if r < 0.4:
                net.m_cache[m] = 1
                net.m_rem[m] = rng.randrange(1, net.m_d[m] * Q + 1)
            elif r < 0.6:
                net.m_cache[m] = 2

    def build_ring(self, net, t_trans, info):
        rng = self.rng
        n = rng.randrange(2, 5)
        items = [self.new_item() for _ in range(n)]
        ms = []
        for i in range(n):
            ms.append(net.add_machine({items[i]: 1}, items[(i + 1) % n], 1, 1, 1, tag='R'))
        lines = []
        for i in range(n):
            cells = net.line(rng.randrange(1, 4), ('m', ms[(i + 1) % n]), tag='Rline', item=items[(i + 1) % n])
            net.m_outch[ms[i]].append(cells[0])
            lines.append(cells)
        # initial items: fill random cells / inventories legally
        for i in range(n):
            for c in lines[i]:
                if rng.random() < 0.7:
                    net.c_item[c] = items[(i + 1) % n]
                    net.c_tin[c] = -rng.randrange(0, 2 * net.Q)
            m = ms[(i + 1) % n]
            net.m_inv[m][items[(i + 1) % n]] = rng.randrange(0, 4)
        for m in ms:
            ton = rng.randrange(0, 20 * net.Q)
            net.m_pow[m] = (ton == 0)
            if ton > 0:
                net.power_events.append((ton, m, True))
        info.update({'kind': 'ring', 'ring': ms, 'ring_lines': lines})
        return net, info


def windows_ok(recv, empt, Q, P):
    """half-open windows of length Q steps (wrapping); ready => exactly 1; always <=1."""
    bad_ready = 0
    bad_over = 0
    for a in range(P):
        s = 0
        ready = False
        for j in range(Q):
            idx = (a + j) % P
            s += recv[idx]
            if empt[idx]:
                ready = True
        if s > 1:
            bad_over += 1
        if ready and s != 1:
            bad_ready += 1
    return bad_ready, bad_over


def analyse(net, info, res):
    Q = net.Q
    obs = res['obs']
    P = res['period']
    nm = len(net.m_in)
    out = {'period': P, 'Q': Q}
    always_on = [all(o[6][m] for o in obs) for m in range(nm)]
    nonempty_all = [all(o[0][m] for o in obs) for m in range(nm)]
    phases = set()
    for step, o in enumerate(obs):
        if o[4]:
            phases.add((res['t1'] + 1 + step) % Q)
    out['phases'] = len(phases)
    out['backpressure'] = any(any(o[5]) for o in obs)

    def lemmaB_ok(y):
        # premise of the source lemma (all outputs counted, incl. gates)
        return always_on[y] and nonempty_all[y] and len(net.m_outch[y]) <= net.m_k[y] and net.m_d[y] == 1

    viol = []
    if info['kind'] == 'tree':
        X = info['X']
        prem = always_on[X]
        for it, ls in info['lines'].items():
            a = net.m_in[X][it]
            if net.m_d[X] * len(ls) < a:
                prem = False
            for kind, y, cells in ls:
                if kind == 'Y' and not lemmaB_ok(y):
                    prem = False
                if any(net.c_k5[c] is not None for c in cells):
                    prem = False
        # X-related phases
        xph = set()
        for step, o in enumerate(obs):
            t = res['t1'] + 1 + step
            hit = o[7][X]
            for it, ls in info['lines'].items():
                for kind, y, cells in ls:
                    if any(o[2][c] for c in cells):
                        hit = True
            if hit:
                xph.add(t % Q)
        out['x_phases'] = len(xph)
        out['x_batches'] = sum(1 for o in obs if o[7][X])
        out['x_full'] = any(o[5][X] for o in obs)
        out['premise'] = prem
        out['x_nonempty'] = nonempty_all[X]
        if prem and not nonempty_all[X]:
            viol.append('X_empty')
        # line cells always non-empty when source satisfies lemma B (or warehouse)
        for it, ls in info['lines'].items():
            for kind, y, cells in ls:
                if (kind == 'W' or lemmaB_ok(y)) and not any(net.c_k5[c] is not None for c in cells):
                    for c in cells:
                        if not all(o[1][c] for o in obs):
                            viol.append('line_cell_empty')
                            break
        # final sentence for 1-tick X
        if prem and net.m_d[X] == 1 and len(net.m_outch[X]) <= net.m_k[X]:
            out['final_checked'] = True
            for c in net.m_outch[X]:
                if not all(o[1][c] for o in obs):
                    viol.append('X_first_cell_empty')
                recv = [o[2][c] for o in obs]
                empt = [o[3][c] for o in obs]
                br, bo = windows_ok(recv, empt, Q, P)
                if br or bo:
                    viol.append('window')
        # also: every source Y satisfying lemma B keeps all its own first cells full
        for y in range(nm):
            if net.m_tag[y] in ('Y',) and lemmaB_ok(y):
                for c in net.m_outch[y]:
                    if net.c_allow[c] is None and net.c_k5[c] is None:
                        if not all(o[1][c] for o in obs):
                            viol.append('Y_first_cell_empty')
    else:
        ms = info['ring']
        prem_all = all(always_on[m] and nonempty_all[m] for m in ms)
        out['premise'] = prem_all
        # each ring machine: premise = its source (previous machine) satisfies lemma B
        n = len(ms)
        for i in range(n):
            y = ms[i - 1]
            x = ms[i]
            if lemmaB_ok(y) and always_on[x] and not nonempty_all[x]:
                viol.append('ring_X_empty')
        out['ring_nonempty'] = [nonempty_all[m] for m in ms]
    out['viol'] = viol
    return out


def main():
    seed = int(sys.argv[1])
    N = int(sys.argv[2])
    mode = sys.argv[3] if len(sys.argv) > 3 else 'normal'
    rng = random.Random(seed)
    stats = {'runs': 0, 'cycles': 0, 'premise': 0, 'premise_multiphase': 0,
             'premise_x_multiphase': 0, 'premise_backpressure': 0, 'final_checked': 0,
             'x5tick_premise': 0, 'viol': {}, 'x_empty_when_premise_false': 0,
             'premise_false': 0, 'examples': []}
    for r in range(N):
        g = Gen(rng, 'ring' if mode == 'ring' else mode)
        net, info = g.build()
        net.rng = rng
        stats['runs'] += 1
        res = net.run(rng, info['t_trans'], info['t_trans'] + 4000 * net.Q, adversarial=True)
        if res is None:
            continue
        stats['cycles'] += 1
        a = analyse(net, info, res)
        if a['premise']:
            stats['premise'] += 1
            if a['phases'] > 1:
                stats['premise_multiphase'] += 1
            if a.get('x_phases', 0) > 1:
                stats['premise_x_multiphase'] += 1
            if a['backpressure']:
                stats['premise_backpressure'] += 1
            if a.get('final_checked'):
                stats['final_checked'] += 1
            if info['kind'] == 'tree' and net.m_d[info['X']] == 5:
                stats['x5tick_premise'] += 1
            if info['kind'] == 'tree':
                stats['premise_x_full'] = stats.get('premise_x_full', 0) + (1 if a['x_full'] else 0)
                stats['premise_x_idle'] = stats.get('premise_x_idle', 0) + (1 if a['x_batches'] == 0 else 0)
        else:
            stats['premise_false'] += 1
            if info['kind'] == 'tree' and not a['x_nonempty']:
                stats['x_empty_when_premise_false'] += 1
        for v in a['viol']:
            stats['viol'][v] = stats['viol'].get(v, 0) + 1
        if a['viol'] and len(stats['examples']) < 5:
            stats['examples'].append({'run': r, 'Q': net.Q, 'period': a['period'], 'viol': a['viol']})
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == '__main__':
    main()
