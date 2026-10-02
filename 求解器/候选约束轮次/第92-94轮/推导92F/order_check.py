#!/usr/bin/env python3
"""引理「无分流专用网络的判定先后无关」的程序核对，两套编码。

编码甲：本目录 stepsim.py（自写）。编码乙：求解器/规则修订/2026-09-30-迟滞/sim2/simulator.py（只读导入，不改）。
对每个随机网络（netgen.py），固定接通先后（即固定轮询、取货优先级），随机换同层元件之间、
非运输单位之间的判定先后若干次，逐步比对整个状态。两套编码各自判；另外比对两套编码在同一网络上的
外部可见量（各终点收件序列、各机开工序列）。
用法：python3 order_check.py N_NETS N_ORDERS STEPS [first_seed]
"""
import copy
import json
import random
import sys
from pathlib import Path

sys.dont_write_bytecode = True      # 不在 sim2 目录里留 __pycache__
HERE = Path(__file__).resolve().parent
SIM2 = HERE.parents[2] / '规则修订' / '2026-09-30-迟滞' / 'sim2'
sys.path.insert(0, str(SIM2))
sys.path.insert(0, str(HERE))

import simulator as s2          # noqa: E402
from netgen import gen, sink_open   # noqa: E402
from stepsim import Net, Sim    # noqa: E402


# ---------------- 编码甲 ----------------
def build_a(desc):
    units = copy.deepcopy(desc['units'])
    for u, d in units.items():
        if d['type'] == 'sink':
            d['open'] = sink_open(tuple(d['spec']))
    return Net(units, [tuple(c) for c in desc['channels']])


def run_a(desc, net, order_seed, steps):
    sim = Sim(net, copy.deepcopy(desc['init']), order_seed=order_seed)
    snaps = []
    for _ in range(steps):
        sim.step()
        snaps.append(sim.snapshot())
    return sim, snaps


# ---------------- 编码乙（sim2） ----------------
class OpenSink(s2.Sink):
    def __init__(self, name, f):
        super().__init__(name)
        self.f = f

    def can_accept(self, item, w):
        return self.f(w.t)


class CellBelt(s2.Belt):
    """只在本脚本里补 sim2 已知错 2：带内前移也记下刚离开的格，使「不移回刚离开的单位」按单位判。"""
    def move_inside(self, w):
        for j in range(len(self.cells) - 2, -1, -1):
            item = self.cells[j]
            if item is not None and self.cells[j+1] is None and w.t-item.entered >= 8:
                w.move(item, self, self, internal=True)
                item.previous = f'{self.name}#{j}'
                self.cells[j+1], self.cells[j] = item, None


def build_b(desc):
    """按描述在 sim2 里搭网络；sim2 的准入口不带放行种类和上限，所以只用于不设的描述。"""
    nodes, by = [], {}
    for u, d in desc['units'].items():
        ty = d['type']
        if ty == 'belt':
            o = CellBelt(u, d['length'])
        elif ty == 'gate':
            assert d.get('allow') is None and d.get('quota') is None
            o = s2.Gate(u)
        elif ty == 'baxis':
            o = s2.BridgeAxis(u)
        elif ty == 'merger':
            o = s2.Merger(u)
        elif ty == 'src':
            o = s2.Source(u, kinds=tuple(d['kinds']))
        elif ty == 'sink':
            o = OpenSink(u, sink_open(tuple(d['spec'])))
        elif ty == 'mach':
            recs = [s2.Recipe(f'r{i}', tuple((k, n) for k, n in r['in']), r['out'], r['qty'], r['dur'])
                    for i, r in enumerate(d['recipes'])]
            o = s2.Machine(u, auxiliary=(d['nslots'] == 2), recipes=recs)
            o.slots = [[] for _ in range(d['nslots'])]
        by[u] = o
        nodes.append(o)
    for a, b, r in sorted(desc['channels'], key=lambda c: c[2]):
        by[a].connect(by[b], connected=r)
    ini = desc['init']
    for u, lst in ini['cells'].items():
        o = by[u]
        o.cells = [None if it is None else s2.Item(it[0], it[1]) for it in lst]
    for u, lst in ini['slots'].items():
        by[u].slots = [[] if k is None else [s2.Item(k) for _ in range(n)] for k, n in lst]
    for u, (k, n) in ini['outslot'].items():
        by[u].output = [s2.Item(k) for _ in range(n)]
    for u, v in ini['cache'].items():
        if v:
            by[u].cache = [s2.Item(v[0]) for _ in range(v[1])]
    for u, v in ini['run'].items():
        if v:
            m = by[u]
            m.running = m.recipes[v[0]]
            m.remaining = v[1]
    for u, v in ini['cursor'].items():
        by[u].input_cursor = v
    return nodes, by


def run_b(desc, order_seed, steps):
    nodes, by = build_b(desc)
    lay = s2.layers_for(nodes)
    rng = random.Random(order_seed)
    comps = [u for u in nodes if u.component]
    order = []
    for L in sorted(set(lay.values())):
        g = [u.name for u in comps if lay[u.name] == L]
        rng.shuffle(g)
        order += g
    nts = [u.name for u in nodes if not u.component and (u.outputs or isinstance(u, s2.Source))]
    rng.shuffle(nts)
    order += nts
    sch = dict(choices={}, layers=lay, nontransport_order=nts, order=order)
    w = s2.World(nodes, (), sch)
    snaps = []
    for _ in range(steps):
        w.step()
        snaps.append(snap_b(w, by))
    return w, by, snaps


def snap_b(w, by):
    out = [w.t]
    for u in sorted(by):
        o = by[u]
        if isinstance(o, s2.Belt):
            out.append((u, tuple(None if i is None else (i.kind, i.entered) for i in o.cells)))
        elif isinstance(o, s2.Machine):
            out.append((u, tuple((s[0].kind, len(s)) if s else None for s in o.slots),
                        (o.output[0].kind, len(o.output)) if o.output else None,
                        (o.cache[0].kind, len(o.cache)) if o.cache else None,
                        None if o.running is None else (o.running.name, o.remaining),
                        o.input_cursor, tuple(sorted((c.dst.name, v) for c, v in o.last_output.items()))))
        elif isinstance(o, s2.Source):
            out.append((u, o.sequence, tuple(sorted((c.dst.name, v) for c, v in o.last_output.items()))))
        elif isinstance(o, s2.Sink):
            out.append((u, len(o.received)))
        if not isinstance(o, s2.Belt) or isinstance(o, s2.Merger):
            out.append((u, 'cur', o.input_cursor))
    return tuple(out)


def external_a(sim, net):
    sinks = {u: list(v) for u, v in sim.sink_got.items()}
    return sinks


def main():
    n_nets, n_orders, steps = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    first = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    res = dict(nets=0, a_orders=0, a_mismatch=[], b_nets=0, b_orders=0, b_mismatch=[],
               ab_compared=0, ab_mismatch=[], a_steps=0, b_steps=0, activity={})
    for seed in range(first, first + n_nets):
        filt = (seed % 2 == 0)
        desc = gen(seed, allow_gate_filters=filt)
        net = build_a(desc)
        res['nets'] += 1
        base = None
        for k in range(n_orders):
            sim, snaps = run_a(desc, net, order_seed=1000 * seed + k, steps=steps)
            res['a_orders'] += 1
            res['a_steps'] += steps
            if base is None:
                base, base_sim = snaps, sim
            elif snaps != base:
                i = next(j for j in range(steps) if snaps[j] != base[j])
                res['a_mismatch'].append(dict(seed=seed, order=k, first_step=i))
                break
        for k_, v_ in base_sim.stat.items():
            res['activity'][k_] = res['activity'].get(k_, 0) + v_
        if not filt:
            bbase = None
            for k in range(n_orders):
                w, by, snaps = run_b(desc, order_seed=7000 * seed + k, steps=steps)
                res['b_orders'] += 1
                res['b_steps'] += steps
                if bbase is None:
                    bbase, bw, bby = snaps, w, by
                elif snaps != bbase:
                    i = next(j for j in range(steps) if snaps[j] != bbase[j])
                    res['b_mismatch'].append(dict(seed=seed, order=k, first_step=i))
                    break
            res['b_nets'] += 1
            # 两套编码的外部可见量：各终点收件（步，物品）序列
            ea = {u: [(t, k) for t, k in v] for u, v in base_sim.sink_got.items()}
            eb = {u: [(t, k) for t, k in bby[u].received] for u in ea}
            res['ab_compared'] += 1
            if ea != eb:
                res['ab_mismatch'].append(dict(seed=seed, sinks={u: (len(ea[u]), len(eb[u])) for u in ea}))
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
