"""第 87 轮复核：「专线制造单位不空手的传递」任意有理相位探测（本席自写）。

X 只做一个配方：原料 i 每批 a_i 件、配方 d tick、每批产 1 件；原料 i 经 c_i 条独占纯料专线进 X。
每条专线的源头：仓库取货口（首格一空就补）或一台 1 tick 配方的源机（存货无限，故每刻不空手），
源机每批 k 件、取货通道 <= k 条：一条是这条专线，其余接对手下游。X 的取货通道接对手下游（造出回压）。
各源机、X 的初始相位随机（有理数）。对手期随机判定次序与下游开关，之后固定次序、周期下游，跑到状态重复。
检查循环态中 X 是否在某个事件时刻闭合后空手（缓存为空）；d=1 且 X 取货通道 <= 1 时查就绪取不到。
用法：python3 -B relay_sim.py <seed> <runs>
"""
import json
import random
import sys
from fractions import Fraction as F

RECIPES = [  # (名称, [(a_i, c_i)], d)
    ('单料1', [(1, 1)], 1),
    ('塑形紧', [(2, 2)], 1),
    ('塑形松', [(2, 3)], 1),
    ('研磨', [(2, 2), (1, 1)], 1),
    ('封装', [(10, 2), (15, 3)], 5),
    ('灌装', [(10, 2), (10, 2)], 5),
]


def one(rng, st):
    q = rng.choice([1, 2, 3, 4, 6, 12])
    name, mats, d = rng.choice(RECIPES)
    lines = []  # 每条：{'mat','cells','src'}；src: None=仓库口，否则源机下标
    srcs = []
    for mi, (a, c) in enumerate(mats):
        for _ in range(c):
            L = rng.randint(1, 4)
            if rng.random() < 0.3:
                src = None
            else:
                k = rng.randint(1, 3)
                extra = rng.randint(0, k - 1)
                cache = ('run', -F(rng.randint(0, q - 1), q)) if rng.random() < 0.8 else ('done',)
                srcs.append({'k': k, 'pk': rng.randint(0, 50 - k), 'cache': cache,
                             'extra': [None] * extra, 'line': len(lines)})
                src = len(srcs) - 1
            cells = [(-F(rng.randint(0, 2 * q), q) if rng.random() < 0.5 else None) for _ in range(L)]
            lines.append({'mat': mi, 'cells': cells, 'src': src})
    X = {'st': [rng.randint(0, 50) for _ in mats], 'cache': rng.choice([None, ('done',), ('run', -F(rng.randint(0, d * q - 1), q))]),
         'pk': rng.randint(0, 50), 'out': [None] * rng.randint(1, 2)}
    sinks = [('x', j) for j in range(len(X['out']))] + [('s', si, j) for si, s in enumerate(srcs) for j in range(len(s['extra']))]
    T_adv = rng.randint(10, 80)
    tog = {sk: sorted(F(rng.randint(0, T_adv * q), q) for _ in range(rng.randint(0, T_adv))) for sk in sinks}
    init = {sk: rng.random() < 0.6 for sk in sinks}

    def open_adv(sk, t):
        return init[sk] ^ (sum(1 for x in tog[sk] if x <= t) % 2 == 1)

    def cellref(sk):
        return X['out'] if sk[0] == 'x' else srcs[sk[1]]['extra']

    def moves(t, opn):
        mv = []
        for si, s in enumerate(srcs):
            c = s['cache']
            if c[0] == 'run' and c[1] + 1 <= t:
                mv.append(('sdone', si))
            if c[0] == 'done' and s['pk'] + s['k'] <= 50:
                mv.append(('senter', si))
            if s['pk'] > 0:
                if lines[s['line']]['cells'][0] is None:
                    mv.append(('stake', si))
                for j, e in enumerate(s['extra']):
                    if e is None:
                        mv.append(('sext', si, j))
        for li, ln in enumerate(lines):
            cells = ln['cells']
            if cells[0] is None and ln['src'] is None:
                mv.append(('wtake', li))
            for j in range(len(cells) - 1):
                if cells[j] is not None and cells[j] + 1 <= t and cells[j + 1] is None:
                    mv.append(('shift', li, j))
            if cells[-1] is not None and cells[-1] + 1 <= t and X['st'][ln['mat']] < 50:
                mv.append(('deliver', li))
        c = X['cache']
        if c is not None and c[0] == 'run' and c[1] + d <= t:
            mv.append(('xdone',))
        if c == ('done',) and X['pk'] + 1 <= 50:
            mv.append(('xenter',))
        if c is None and all(X['st'][i] >= mats[i][0] for i in range(len(mats))):
            mv.append(('xstart',))
        for j, e in enumerate(X['out']):
            if e is None and X['pk'] > 0:
                mv.append(('xtake', j))
        for sk in sinks:
            arr = cellref(sk)
            j = sk[-1]
            if arr[j] is not None and arr[j] + 1 <= t and opn(sk, t):
                mv.append(('drain', sk))
        return mv

    def apply(x, t, log):
        k0 = x[0]
        if k0 == 'sdone':
            srcs[x[1]]['cache'] = ('done',)
        elif k0 == 'senter':
            s = srcs[x[1]]
            s['pk'] += s['k']
            s['cache'] = ('run', t)  # 存货无限：进格即开下一批
        elif k0 == 'stake':
            s = srcs[x[1]]
            s['pk'] -= 1
            lines[s['line']]['cells'][0] = t
        elif k0 == 'sext':
            s = srcs[x[1]]
            s['pk'] -= 1
            s['extra'][x[2]] = t
        elif k0 == 'wtake':
            lines[x[1]]['cells'][0] = t
        elif k0 == 'shift':
            cells = lines[x[1]]['cells']
            cells[x[2] + 1] = t
            cells[x[2]] = None
        elif k0 == 'deliver':
            ln = lines[x[1]]
            ln['cells'][-1] = None
            X['st'][ln['mat']] += 1
        elif k0 == 'xdone':
            X['cache'] = ('done',)
        elif k0 == 'xenter':
            X['pk'] += 1
            X['cache'] = None
        elif k0 == 'xstart':
            for i in range(len(mats)):
                X['st'][i] -= mats[i][0]
            X['cache'] = ('run', t)
        elif k0 == 'xtake':
            X['pk'] -= 1
            X['out'][x[1]] = t
            log.append(('xtake', x[1]))
        elif k0 == 'drain':
            arr = cellref(x[1])
            arr[x[1][-1]] = None

    def closure(t, opn, order):
        log = []
        emp = set(j for j, e in enumerate(X['out']) if e is None)
        g = 0
        while True:
            mv = moves(t, opn)
            if not mv:
                break
            x = rng.choice(mv) if order is None else min(mv, key=order)
            apply(x, t, log)
            for j, e in enumerate(X['out']):
                if e is None:
                    emp.add(j)
            g += 1
            if g > 200000:
                raise RuntimeError
        return log, emp

    def next_t(t, ext):
        cand = []
        for ln in lines:
            cand += [c + 1 for c in ln['cells'] if c is not None and c + 1 > t]
        for s in srcs:
            if s['cache'][0] == 'run' and s['cache'][1] + 1 > t:
                cand.append(s['cache'][1] + 1)
            cand += [e + 1 for e in s['extra'] if e is not None and e + 1 > t]
        if X['cache'] is not None and X['cache'][0] == 'run' and X['cache'][1] + d > t:
            cand.append(X['cache'][1] + d)
        cand += [e + 1 for e in X['out'] if e is not None and e + 1 > t]
        n = ext(t)
        if n is not None:
            cand.append(n)
        cand = [c for c in cand if c > t]
        return min(cand) if cand else None

    def ext_adv(t):
        c = [x for v in tog.values() for x in v if x > t] + ([F(T_adv)] if F(T_adv) > t else [])
        return min(c) if c else None

    t = F(0)
    closure(t, open_adv, None)
    while True:
        nt = next_t(t, ext_adv)
        if nt is None or nt > T_adv:
            break
        t = nt
        closure(t, open_adv, None)
    t = max(t, F(T_adv))
    closure(t, open_adv, None)
    P = F(rng.randint(1, 8 * q), q)
    patt = {}
    for sk in sinks:
        if rng.random() < 0.5:
            patt[sk] = None
        else:
            a, b = sorted([F(rng.randint(0, int(P * q)), q) for _ in range(2)])
            patt[sk] = (a, b)
    base = t

    def open_det(sk, tt):
        if patt[sk] is None:
            return True
        ph = (tt - base) % P
        return patt[sk][0] <= ph < patt[sk][1]

    def ext_det(tt):
        ph = (tt - base) % P
        c = []
        for v in patt.values():
            if v is None:
                continue
            for x in (v[0], v[1], P):
                if x - ph > 0:
                    c.append(tt + x - ph)
        return min(c) if c else None

    kinds = ['sdone', 'senter', 'stake', 'sext', 'wtake', 'shift', 'deliver', 'xdone', 'xenter', 'xstart', 'xtake', 'drain']
    perm = list(range(len(kinds)))
    rng.shuffle(perm)
    rank = dict(zip(kinds, perm))

    def order(x):
        return (rank[x[0]], str(x[1:]))

    def key(tt):
        def r(c):
            return None if c is None else min(tt - c, F(1))
        return (tuple((s['pk'], 'd' if s['cache'][0] == 'done' else tt - s['cache'][1], tuple(r(e) for e in s['extra'])) for s in srcs),
                tuple(tuple(r(c) for c in ln['cells']) for ln in lines),
                tuple(X['st']), None if X['cache'] is None else ('d' if X['cache'][0] == 'done' else tt - X['cache'][1]),
                X['pk'], tuple(r(e) for e in X['out']), (tt - base) % P)

    closure(t, open_det, order)
    seen = {}
    steps = 0
    while steps < 20000:
        kk = key(t)
        if kk in seen:
            break
        seen[kk] = t
        nt = next_t(t, ext_det)
        if nt is None:
            break
        t = nt
        closure(t, open_det, order)
        steps += 1
    else:
        st['no_cycle'] += 1
        return
    st['cycles'] += 1
    t0 = t
    W = F(40)
    idle = False
    backp = False
    rec = []
    while t < t0 + W:
        if X['cache'] is None:
            idle = True
        if any(X['st'][i] == 50 for i in range(len(mats))):
            backp = True
        nt = next_t(t, ext_det)
        if nt is None:
            break
        t = nt
        log, emp = closure(t, open_det, order)
        rec.append((t, log, emp))
    phases = set(tt % 1 for tt, _, _ in rec)
    if len(phases) > 1:
        st['mixed_phase_cycles'] += 1
    if backp:
        st['cycles_with_full_input_slot'] += 1
    if idle:
        st['X_idle_viol'] += 1
        if len(st['examples']) < 5:
            st['examples'].append({'recipe': name, 'q': q})


def main():
    seed, runs = int(sys.argv[1]), int(sys.argv[2])
    rng = random.Random(seed)
    st = {'runs': runs, 'cycles': 0, 'no_cycle': 0, 'mixed_phase_cycles': 0, 'cycles_with_full_input_slot': 0,
          'X_idle_viol': 0, 'examples': []}
    for _ in range(runs):
        one(rng, st)
    print(json.dumps(st, ensure_ascii=False))


if __name__ == '__main__':
    main()
