"""第 87 轮复核：采种双出口专线单元的逐事件模拟（任意有理相位）。

本席自写，只按快照规则：运输物品格上限 1、至少滞留 1 tick；移动零时；同一时刻做到没有可动为止；
制造 1 tick、上一批整批进取货格后才开下一批；缓存格只放一批。
单元：采种机 C、种植机 A、B、粉碎机 K；路 CA、AC、CB、BK；K 有 n_out 条独占出口（首格只从 K 收货），
出口首格的物品由下游按开放时段取走（对手）。所有物品都是这种植物的正确物品，所以只记件数。

检查：
  E1 种群下界：每个事件时刻闭合后 Phi >= min(Phi0-1/2, L1+L2+3m+2+(m-1)/2-1/2)（m=50 时即 L1+L2+176）。
  E2 不断料：Phi0 >= S+1/2 时，循环态中 C、B、K 在每个事件时刻闭合后缓存都非空。
  E3 K 出口：循环态中取任意起点的单位时段，K 送出 >= min(就绪出口数, k)；出口数 <= k 时每条就绪出口都取到 1 件。
  对照：Phi0 < S 的循环里统计 C 空手次数（检验查得出）。
用法：python3 -B unit_sim.py <seed> <runs> [edge]  → 输出 JSON 汇总到 stdout。
"""
import json
import random
import sys
from fractions import Fraction as F

OUT = {'C': 2, 'A': 1, 'B': 1}  # K 的每批件数另给
FORCE_TARGET = sys.argv[3] if len(sys.argv) > 3 else None  # 可选：只跑 edge（Phi0=S+1/2）


class Unit:
    def __init__(self, rng, L, m, k, n_out, q):
        self.rng = rng
        self.L = L  # dict path->length
        self.m = m
        self.k = k
        self.n_out = n_out
        self.q = q
        self.out = dict(OUT)
        self.out['K'] = k
        # 路：(源机器, 目标机器)
        self.pdef = {'CA': ('C', 'A'), 'AC': ('A', 'C'), 'CB': ('C', 'B'), 'BK': ('B', 'K')}

    def rand_age_entry(self):
        q = self.q
        # 进格时刻在 [-2, 0]，有一半概率未满 1 tick
        return -F(self.rng.randint(0, 2 * q), q)

    def init_state(self, fill):
        rng, m = self.rng, self.m
        s = {'mach': {}, 'paths': {}, 'sinks': []}
        for name in 'CABK':
            c = rng.choice([None, 'run', 'done'])
            if c == 'run':
                c = ('run', -F(rng.randint(0, self.q - 1), self.q))
            elif c == 'done':
                c = ('done',)
            cap_pk = m
            s['mach'][name] = {'st': rng.randint(0, int(m * fill)), 'cache': c,
                               'pk': rng.randint(0, int(cap_pk * fill))}
        for p, Lp in self.L.items():
            s['paths'][p] = [self.rand_age_entry() if rng.random() < fill else None for _ in range(Lp)]
        s['sinks'] = [self.rand_age_entry() if rng.random() < 0.5 else None for _ in range(self.n_out)]
        return s

    # ---------- 规则 ----------
    def moves(self, s, t, open_fn):
        mv = []
        m = self.m
        for name, M in s['mach'].items():
            c = M['cache']
            if c is not None and c[0] == 'run' and c[1] + 1 <= t:
                mv.append(('done', name))
            if c is not None and c[0] == 'done' and M['pk'] + self.out[name] <= m:
                mv.append(('enter', name))
            if c is None and M['st'] >= 1:
                mv.append(('start', name))
        for p, (src, dst) in self.pdef.items():
            cells = s['paths'][p]
            Lp = len(cells)
            if cells[Lp - 1] is not None and cells[Lp - 1] + 1 <= t and s['mach'][dst]['st'] < m:
                mv.append(('deliver', p))
            for j in range(Lp - 1):
                if cells[j] is not None and cells[j] + 1 <= t and cells[j + 1] is None:
                    mv.append(('shift', p, j))
            if cells[0] is None and s['mach'][src]['pk'] > 0:
                mv.append(('take', p))
        K = s['mach']['K']
        for j, cell in enumerate(s['sinks']):
            if cell is None and K['pk'] > 0:
                mv.append(('ktake', j))
            if cell is not None and cell + 1 <= t and open_fn(j, t):
                mv.append(('drain', j))
        return mv

    def apply(self, s, mvv, t, log):
        kind = mvv[0]
        if kind == 'done':
            s['mach'][mvv[1]]['cache'] = ('done',)
        elif kind == 'enter':
            M = s['mach'][mvv[1]]
            M['pk'] += self.out[mvv[1]]
            M['cache'] = None
        elif kind == 'start':
            M = s['mach'][mvv[1]]
            M['st'] -= 1
            M['cache'] = ('run', t)
        elif kind == 'deliver':
            p = mvv[1]
            s['paths'][p][-1] = None
            s['mach'][self.pdef[p][1]]['st'] += 1
        elif kind == 'shift':
            p, j = mvv[1], mvv[2]
            s['paths'][p][j + 1] = t
            s['paths'][p][j] = None
        elif kind == 'take':
            p = mvv[1]
            s['paths'][p][0] = t
            s['mach'][self.pdef[p][0]]['pk'] -= 1
            log.append(('take', p))
        elif kind == 'ktake':
            j = mvv[1]
            s['sinks'][j] = t
            s['mach']['K']['pk'] -= 1
            log.append(('ktake', j))
        elif kind == 'drain':
            s['sinks'][mvv[1]] = None
            log.append(('drain', mvv[1]))

    def closure(self, s, t, open_fn, order):
        """order=None：每步随机挑（对手，含一切判定次序与轮询/接通变化）；否则按固定排名。
        返回本时刻日志与闭合中曾空过的出口首格集合。"""
        log = []
        empty_seen = set(j for j, c in enumerate(s['sinks']) if c is None)
        guard = 0
        while True:
            mv = self.moves(s, t, open_fn)
            if not mv:
                break
            if order is None:
                x = self.rng.choice(mv)
            else:
                x = min(mv, key=order)
            self.apply(s, x, t, log)
            for j, c in enumerate(s['sinks']):
                if c is None:
                    empty_seen.add(j)
            guard += 1
            if guard > 100000:
                raise RuntimeError('closure too long')
        return log, empty_seen

    def phi(self, s):
        M = s['mach']
        v = F(0)
        v += sum(1 for c in s['paths']['CA'] if c is not None)
        v += M['A']['st'] + (1 if M['A']['cache'] is not None else 0) + M['A']['pk']
        v += sum(1 for c in s['paths']['AC'] if c is not None)
        v += M['C']['st'] + (1 if M['C']['cache'] is not None else 0) + F(M['C']['pk'], 2)
        return v

    def next_time(self, s, t, ext_times):
        cand = []
        for p, cells in s['paths'].items():
            for c in cells:
                if c is not None and c + 1 > t:
                    cand.append(c + 1)
        for c in s['sinks']:
            if c is not None and c + 1 > t:
                cand.append(c + 1)
        for M in s['mach'].values():
            c = M['cache']
            if c is not None and c[0] == 'run' and c[1] + 1 > t:
                cand.append(c[1] + 1)
        nxt = ext_times(t)
        if nxt is not None:
            cand.append(nxt)
        return min(cand) if cand else None

    def key(self, s, t, period_phase):
        mk = []
        for name in 'CABK':
            M = s['mach'][name]
            c = M['cache']
            if c is None:
                cc = None
            elif c[0] == 'done':
                cc = 'd'
            else:
                cc = t - c[1]
            mk.append((M['st'], cc, M['pk']))
        pk = []
        for p in ('CA', 'AC', 'CB', 'BK'):
            pk.append(tuple(None if c is None else min(t - c, F(1)) for c in s['paths'][p]))
        sk = tuple(None if c is None else min(t - c, F(1)) for c in s['sinks'])
        return (tuple(mk), tuple(pk), sk, period_phase)


def run_one(rng, stats):
    q = rng.choice([1, 2, 3, 4, 5, 6, 8, 12])
    L = {p: rng.randint(1, 4) for p in ('CA', 'AC', 'CB', 'BK')}
    m = rng.choice([3, 4, 5, 8, 50])
    k = rng.choice([2, 3])
    n_out = rng.randint(1, 4)
    u = Unit(rng, L, m, k, n_out, q)
    S = L['CA'] + L['AC'] + 2
    jam = L['CA'] + L['AC'] + 3 * m + 2 + F(m - 1, 2)
    s = u.init_state(rng.random())

    # 对手期的下游：每条出口一串随机开关时刻
    T_adv = rng.randint(5, 60)
    toggles = []
    for j in range(n_out):
        ts = sorted(F(rng.randint(0, T_adv * q), q) for _ in range(rng.randint(0, 3 * T_adv // 2 + 1)))
        toggles.append(ts)
    init_open = [rng.random() < 0.6 for _ in range(n_out)]

    def open_adv(j, t):
        n = sum(1 for x in toggles[j] if x <= t)
        return init_open[j] ^ (n % 2 == 1)

    def ext_adv(t):
        c = [x for ts in toggles for x in ts if x > t]
        c.append(F(T_adv))
        c = [x for x in c if x > t]
        return min(c) if c else None

    t = F(0)
    u.closure(s, t, open_adv, None)
    phi0 = u.phi(s)
    target = rng.choice(['low', 'edge', 'edge', 'mid', 'free'])
    if FORCE_TARGET:
        target = FORCE_TARGET
    want = {'low': None, 'edge': S + F(1, 2), 'mid': S + F(rng.randint(1, 6), 2), 'free': None}[target]
    if want is not None:
        # 往 A 存货格补种子到目标（不会引起取种，不改 Phi 以外的事件）
        while phi0 < want and s['mach']['A']['st'] < m:
            s['mach']['A']['st'] += 1
            u.closure(s, t, open_adv, None)
            phi0 = u.phi(s)
        while phi0 < want and s['mach']['C']['st'] < m:
            s['mach']['C']['st'] += 1
            u.closure(s, t, open_adv, None)
            phi0 = u.phi(s)
    if target == 'low':
        # 刻意压低存量，作检验对照
        s['mach']['A']['st'] = 0
        s['mach']['C']['st'] = 0
        u.closure(s, t, open_adv, None)
        phi0 = u.phi(s)
    bound = min(phi0 - F(1, 2), jam - F(1, 2))
    stats['runs'] += 1

    def check_phi(tt):
        v = u.phi(s)
        if v < bound:
            stats['E1_viol'] += 1
            if len(stats['E1_examples']) < 5:
                stats['E1_examples'].append({'L': L, 'm': m, 'q': q, 't': str(tt), 'phi0': str(phi0), 'phi': str(v)})

    # 对手期
    while True:
        nt = u.next_time(s, t, ext_adv)
        if nt is None or nt > T_adv:
            break
        t = nt
        u.closure(s, t, open_adv, None)
        check_phi(t)
    t = F(T_adv) if t < T_adv else t
    u.closure(s, t, open_adv, None)
    check_phi(t)

    # 固定期：固定判定次序、周期下游
    perm = list(range(10))
    rng.shuffle(perm)
    kinds = ['done', 'enter', 'start', 'deliver', 'shift', 'take', 'ktake', 'drain']
    rank = {kd: perm[i] for i, kd in enumerate(kinds)}
    tie = rng.random() < 0.5

    def order(x):
        return (rank[x[0]], tuple(str(y) for y in x[1:]) if tie else tuple(reversed([str(y) for y in x[1:]])))

    P = F(rng.randint(1, 6 * q), q)
    patt = []
    for j in range(n_out):
        mode = rng.choice(['open', 'open', 'win'])
        if mode == 'open':
            patt.append(None)
        else:
            a = F(rng.randint(0, int(P * q)), q)
            b = F(rng.randint(0, int(P * q)), q)
            patt.append((min(a, b), max(a, b)))
    base = t

    def open_det(j, tt):
        if patt[j] is None:
            return True
        ph = (tt - base) % P
        a, b = patt[j]
        return a <= ph < b

    def ext_det(tt):
        c = []
        for j in range(n_out):
            if patt[j] is None:
                continue
            ph = (tt - base) % P
            for x in (patt[j][0], patt[j][1], P):
                d = x - ph
                if d > 0:
                    c.append(tt + d)
        return min(c) if c else None

    seen = {}
    trace = []
    steps = 0
    cyc = None
    u.closure(s, t, open_det, order)
    while steps < 6000:
        ph = (t - base) % P
        kk = u.key(s, t, ph)
        if kk in seen:
            cyc = (seen[kk], t)
            break
        seen[kk] = t
        nt = u.next_time(s, t, ext_det)
        if nt is None:
            cyc = (t, t)  # 静止不动点
            break
        t = nt
        u.closure(s, t, open_det, order)
        check_phi(t)
        steps += 1
    if cyc is None:
        stats['no_cycle'] += 1
        return
    stats['cycles'] += 1
    t1, t2 = cyc
    per = t2 - t1
    # 在循环里再走若干周期，记录每个事件时刻的状态
    W = max(F(12), 3 * per) if per > 0 else F(0)
    rec = []
    tt = t2
    # 事件时刻闭合后的状态已在 s 中（t==t2）
    def snap(tt, log, emp):
        M = s['mach']
        return {'t': tt,
                'idle': {n: M[n]['cache'] is None for n in 'CBK'},
                'kt': [sum(1 for e in log if e == ('ktake', j)) for j in range(n_out)],
                'emp': emp,
                'end_empty': [c is None for c in s['sinks']],
                }
    rec.append(snap(tt, [], set(j for j, c in enumerate(s['sinks']) if c is None)))
    if per > 0:
        while True:
            nt = u.next_time(s, tt, ext_det)
            if nt is None or nt >= t2 + W:
                break
            tt = nt
            log, emp = u.closure(s, tt, open_det, order)
            check_phi(tt)
            rec.append(snap(tt, log, emp))
    ok_phi = phi0 >= S + F(1, 2)
    idle_any = {n: any(r['idle'][n] for r in rec) for n in 'CBK'}
    if ok_phi:
        stats['E2_cycles'] += 1
        for n in 'CBK':
            if idle_any[n]:
                stats['E2_viol_' + n] += 1
                if len(stats['E2_examples']) < 5:
                    stats['E2_examples'].append({'L': L, 'm': m, 'q': q, 'k': k, 'n_out': n_out, 'who': n,
                                                 'phi0': str(phi0), 'per': str(per)})
        if len(set(F(r['t']) % 1 for r in rec)) > 1:
            stats['E2_cycles_mixed_phase'] += 1
    else:
        stats['ctrl_cycles'] += 1
        if idle_any['C']:
            stats['ctrl_C_idle'] += 1
    # E3：单位时段（起点取 t2 及 t2+1/2 等若干）
    if ok_phi and per > 0:
        for off in (F(0), F(1, 3), F(1, 2), F(5, 7)):
            th = t2 + off
            n = 0
            while th + n + 1 <= t2 + W:
                a, b = th + n, th + n + 1
                inside = [r for r in rec if a <= r['t'] < b]
                before = [r for r in rec if r['t'] < a]
                # 时段起点的状态 = 起点前最后一个事件后的状态
                start_empty = before[-1]['end_empty'] if before else None
                ready = []
                took = [0] * n_out
                for j in range(n_out):
                    rj = (start_empty is not None and start_empty[j]) or any(j in r['emp'] for r in inside)
                    ready.append(rj)
                    took[j] = sum(r['kt'][j] for r in inside)
                if start_empty is None:
                    n += 1
                    continue
                nr = sum(ready)
                sent = sum(took)
                stats['E3_intervals'] += 1
                if sent < min(nr, k):
                    stats['E3_min_viol'] += 1
                if n_out <= k:
                    for j in range(n_out):
                        if ready[j] and took[j] < 1:
                            stats['E3_each_viol'] += 1
                if max(took) > 1:
                    stats['E3_rate_viol'] += 1
                n += 1


def main():
    seed = int(sys.argv[1])
    runs = int(sys.argv[2])
    rng = random.Random(seed)
    stats = {k: 0 for k in ['runs', 'E1_viol', 'no_cycle', 'cycles', 'E2_cycles', 'E2_viol_C', 'E2_viol_B',
                            'E2_viol_K', 'E2_cycles_mixed_phase', 'ctrl_cycles', 'ctrl_C_idle',
                            'E3_intervals', 'E3_min_viol', 'E3_each_viol', 'E3_rate_viol']}
    stats['E1_examples'] = []
    stats['E2_examples'] = []
    for _ in range(runs):
        run_one(rng, stats)
    stats['seed'] = seed
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
