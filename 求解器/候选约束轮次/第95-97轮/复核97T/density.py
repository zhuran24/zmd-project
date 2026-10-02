#!/usr/bin/env python3
"""密集结点见证（推导95T §3.3）的独立复算：两套编码。
编码一：通用引擎 engine.py；编码二：本文件里只为这张网写的数组递推（不用引擎）。
网：取货口1→16格带→P(每5tick收1)→分流器S→{汇流器M, 汇流器N}；取货口2→16格带→Q(每5tick收1)→不限额准入口U→M；
M→1格带→核心，N→2格带→核心。物品全为荞花种子，仓库视为不缺货、不满。"""
from __future__ import annotations
import json, random
from engine import Belt, Cell, Gate, Splitter, Merger, Sink, Source, World, link


class RecMerger(Merger):
    def __init__(self, name):
        super().__init__(name)
        self.log = []

    def accept(self, item, w, src_unit):
        self.log.append((w.t, src_unit))
        super().accept(item, w, src_unit)


def engine_run(special_order, steps=4000):
    rng = random.Random(0)
    core_in = Sink('core_in')
    pu1, pu2 = Source('PU1', 'seed'), Source('PU2', 'seed')
    b1, b2 = Belt('belt1', 16), Belt('belt2', 16)
    P, Q, U = Gate('P', per5=1), Gate('Q', per5=1), Gate('U')
    S = Splitter('S')
    M, N = RecMerger('M'), RecMerger('N')
    bm, bn = Belt('bm', 1), Belt('bn', 2)
    link(pu1, b1); link(b1, P); link(P, S); link(S, M); link(S, N)
    link(pu2, b2); link(b2, Q); link(Q, U); link(U, M)
    link(M, bm); link(bm, core_in); link(N, bn); link(bn, core_in)
    nodes = [core_in, pu1, pu2, b1, b2, P, Q, U, S, M, N, bm, bn]
    w = World(nodes, rng)
    units = w.build_units()
    belts = [x for x in units if '#' in x]
    order = ['core_in', 'PU1', 'PU2'] + list(special_order) + belts
    assert sorted(order) == sorted(units)
    w.offline_build(order=order)
    layers = dict(w.layers)
    w.run_order = [n.name for n in w.order_el]
    for _ in range(steps):
        w.step()
    ev = [(t, 'S->M' if s == 'S' else 'U->M') for t, s in M.log] + [(t, 'S->N') for t, s in N.log]
    return layers, w.run_order, sorted(ev)


def array_run(u_first, steps=4000):
    """编码二：直接按步写出这张网的动作，不用引擎。
    物品只记入格步号；带内成熟前移；层序：回库带(1) → M、N(2) → S、U(3，谁先由 u_first 定) → P、Q(4) → 长带(5) → 取货口。"""
    L = 16
    b1 = [None] * L; b2 = [None] * L
    P = Q = U = S = M = N = None
    bm = [None]; bn = [None, None]
    win = {'P': None, 'Q': None}
    s_cursor = None  # 分流器上次成功：'M' 或 'N'；首次从第二条接通的 N 开始
    ev = []

    def mature(e, t):
        return e is not None and t - e >= 8

    def settle(b, t):
        for j in range(len(b) - 2, -1, -1):
            if b[j] is not None and b[j + 1] is None and t - b[j] >= 8:
                b[j + 1], b[j] = t, None

    def gate_ok(g, t):
        return win[g] is None or t - win[g] >= 40

    for t in range(steps):
        for b in (b1, b2, bm, bn):
            settle(b, t)
        # 层1：回库带出到核心
        for b in (bm, bn):
            if mature(b[-1], t):
                b[-1] = None
                settle(b, t)
        # 层2：M、N 各送入回库带首格
        if mature(M, t) and bm[0] is None:
            bm[0], M = t, None
        if mature(N, t) and bn[0] is None:
            bn[0], N = t, None
        # 层3：S 与 U
        def do_S():
            nonlocal S, M, N, s_cursor
            if not mature(S, t):
                return
            order = ['N', 'M'] if s_cursor in (None, 'M') else ['M', 'N']
            for d in order:
                if d == 'M' and M is None:
                    M, S, s_cursor = t, None, 'M'; ev.append((t, 'S->M')); return
                if d == 'N' and N is None:
                    N, S, s_cursor = t, None, 'N'; ev.append((t, 'S->N')); return

        def do_U():
            nonlocal U, M
            if mature(U, t) and M is None:
                M, U = t, None; ev.append((t, 'U->M'))
        if u_first:
            do_U(); do_S()
        else:
            do_S(); do_U()
        # 层4：P→S，Q→U（S、U 已判定，腾位后才能收）
        if mature(P, t) and S is None:
            S, P = t, None
        if mature(Q, t) and U is None:
            U, Q = t, None
        # 层5：长带末格送入 P、Q（准入口每 5 tick 收 1）
        if mature(b1[-1], t) and P is None and gate_ok('P', t):
            P, b1[-1] = t, None; win['P'] = t; settle(b1, t)
        if mature(b2[-1], t) and Q is None and gate_ok('Q', t):
            Q, b2[-1] = t, None; win['Q'] = t; settle(b2, t)
        # 非运输单位：取货口补长带首格
        if b1[0] is None:
            b1[0] = t
        if b2[0] is None:
            b2[0] = t
    return sorted(ev)


def summarize(ev, steps, warm=2000):
    ev = [e for e in ev if e[0] >= warm]
    # 找周期：最小 p 使事件序列平移 p 后重合
    times = {}
    for t, k in ev:
        times.setdefault(t, []).append(k)
    for p in range(1, 400):
        ok = all(sorted(times.get(t, [])) == sorted(times.get(t + p, [])) for t in range(warm, steps - p))
        if ok:
            break
    span = range(warm, warm + p)
    cnt = {k: sum(1 for t, kk in ev if t in span and kk == k) for k in ('S->M', 'S->N', 'U->M')}
    rate = {k: f'{8 * v}/{p}' for k, v in cnt.items()}
    return dict(period_steps=p, per_period=cnt, per_tick=rate)


if __name__ == '__main__':
    out = {}
    for name, order, ufirst in (('U先', ['M', 'U', 'S', 'N', 'P', 'Q'], True),
                                ('S先', ['M', 'S', 'N', 'U', 'P', 'Q'], False)):
        layers, run_order, ev1 = engine_run(order)
        ev2 = array_run(ufirst)
        out[name] = dict(layers={k: v for k, v in layers.items()}, element_order=run_order,
                         engine=summarize(ev1, 4000), array=summarize(ev2, 4000),
                         identical_events=(ev1 == ev2))
    print(json.dumps(out, ensure_ascii=False, indent=1))
