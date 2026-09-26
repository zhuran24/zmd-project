#!/usr/bin/env python3
"""编码一：按「判定逐个进行、同刻反复扫到没有可动为止」直接模拟「采种双出口专线植物单元」。

单元：采种机 C、种植机 A（回路侧）、种植机 B（出口侧）、粉碎机 K。
专线：C 取货格 -> 路 CA(L1 格) -> A 存货格；C 取货格 -> 路 CB(L3) -> B 存货格；
      A 取货格 -> 路 AC(L2) -> C 存货格；B 取货格 -> 路 BK(L4) -> K 存货格；
      K 取货格 -> k 条下游通道（下游是否收货由对手每刻决定）。
机器格上限 m（游戏里 50），运输格上限 1、至少滞留 1 tick。
对手：每刻任意判定次序（每刻重新打乱，比「固定次序」更宽）、C 取货侧轮询指针随时被改
（离线）、K 下游每条通道每刻收不收。
检查：
  F1 每刻 ΔΦ = (α-β)/2（α、β 为本刻 A、B 通道是否从 C 取到种子）；
  F2 A 通道就绪却没取 ⇒ 本刻结束 C 取货格为 0；B 同理；
  F3 A 通道被堵（首格旧货整刻没动）⇒ 本刻结束 Φ ≥ L1+L2+3m+2+(m-1)/2；
  F4 下界：Φ(t) ≥ min(Φ0-1/2, L1+L2+3m+2+(m-1)/2-1/2)；
  T  对手停手后（K 下游每刻全收、次序与指针规则固定、不再离线）跑到状态重复，
     若循环里 Φ ≥ S=L1+L2+2，则循环里 K 每 tick 开一批且从不因取货格放不下而停。
"""
import json, random, sys, time

IDLE, WORK, DONE = 0, 1, 2


class Cell:
    def __init__(self, m, L1, L2, L3, L4, k, rng):
        self.m, self.k = m, k
        self.L = {'CA': L1, 'AC': L2, 'CB': L3, 'BK': L4}
        self.rng = rng
        # machines: [inp, state, out]
        self.M = {x: [0, IDLE, 0] for x in 'CABK'}
        self.batch = {'C': 2, 'A': 1, 'B': 1, 'K': k}
        # path slots: list of entered-tick or None
        self.P = {p: [None] * n for p, n in self.L.items()}
        self.ptr = 'A'
        self.t = 0
        self.tmpl = (['mach:' + x for x in 'CABK']
                     + ['move:%s:%d' % (p, i) for p, n in self.L.items() for i in range(n - 1)]
                     + ['exit:' + p for p in self.L]
                     + ['entry:CA', 'entry:CB', 'entry:AC', 'entry:BK']
                     + ['kout:%d' % j for j in range(k)])

    def randomize(self, fill):
        m = self.m
        for x in 'CABK':
            self.M[x][0] = self.rng.randint(0, m) if self.rng.random() < fill else self.rng.randint(0, 2)
            self.M[x][1] = self.rng.choice([IDLE, WORK, DONE])
            cap = m
            b = self.batch[x]
            self.M[x][2] = self.rng.randint(0, cap) if self.rng.random() < fill else self.rng.randint(0, min(cap, 2))
            if self.M[x][1] == WORK:
                pass
        for p in self.P:
            self.P[p] = [(-1 if self.rng.random() < fill else None) for _ in self.P[p]]
        self.ptr = self.rng.choice('AB')

    def phi(self):
        C, A = self.M['C'], self.M['A']
        v = sum(1 for s in self.P['CA'] if s is not None) + A[0] + (1 if A[1] != IDLE else 0) + A[2]
        v += sum(1 for s in self.P['AC'] if s is not None) + C[0] + (1 if C[1] != IDLE else 0)
        return v + C[2] / 2.0

    def key(self):
        return (tuple(tuple(self.M[x]) for x in 'CABK'),
                tuple(tuple(s is not None for s in self.P[p]) for p in ('CA', 'AC', 'CB', 'BK')),
                self.ptr)

    def step(self, order, accept, flip):
        """一刻。order: 模板次序；accept[j]: K 第 j 条下游通道本刻收不收；flip: 本刻开始时改指针。"""
        t = self.t
        m = self.m
        if flip is not None:
            self.ptr = flip
        for x in 'CABK':  # 计时事件：上一刻开工的批次在本刻完成
            if self.M[x][1] == WORK:
                self.M[x][1] = DONE
        took = {'CA': 0, 'CB': 0}
        kout_taken = [False] * self.k
        first_old = {p: (self.P[p][0] is not None and self.P[p][0] < t) for p in ('CA', 'CB')}
        k_started = False
        k_blocked_any = False
        tgt = {'CA': 'A', 'AC': 'C', 'CB': 'B', 'BK': 'K'}
        src = {'CA': 'C', 'CB': 'C', 'AC': 'A', 'BK': 'B'}
        changed = True
        while changed:
            changed = False
            for tp in order:
                kind, _, rest = tp.partition(':')
                if kind == 'mach':
                    x = rest
                    mm = self.M[x]
                    if mm[1] == DONE and mm[2] + self.batch[x] <= m:
                        mm[2] += self.batch[x]
                        mm[1] = IDLE
                        changed = True
                    if mm[1] == IDLE and mm[0] >= 1:
                        mm[0] -= 1
                        mm[1] = WORK
                        if x == 'K':
                            k_started = True
                        changed = True
                elif kind == 'move':
                    p, i = rest.split(':')
                    i = int(i)
                    sl = self.P[p]
                    if sl[i] is not None and sl[i] < t and sl[i + 1] is None:
                        sl[i + 1] = t
                        sl[i] = None
                        changed = True
                elif kind == 'exit':
                    p = rest
                    sl = self.P[p]
                    mm = self.M[tgt[p]]
                    if sl[-1] is not None and sl[-1] < t and mm[0] < m:
                        sl[-1] = None
                        mm[0] += 1
                        changed = True
                elif kind == 'entry':
                    p = rest
                    sl = self.P[p]
                    mm = self.M[src[p]]
                    if mm[2] < 1 or sl[0] is not None:
                        continue
                    if p in ('CA', 'CB'):
                        me = 'A' if p == 'CA' else 'B'
                        other = 'CB' if p == 'CA' else 'CA'
                        other_movable = self.P[other][0] is None and mm[2] >= 1
                        # 分级侧：从指针起找第一条能动的通道授权
                        if self.ptr != me and other_movable:
                            continue
                        mm[2] -= 1
                        sl[0] = t
                        took[p] += 1
                        self.ptr = 'B' if me == 'A' else 'A'
                        changed = True
                    else:
                        mm[2] -= 1
                        sl[0] = t
                        changed = True
                elif kind == 'kout':
                    j = int(rest)
                    if accept[j] and not kout_taken[j] and self.M['K'][2] >= 1:
                        kout_taken[j] = True
                        self.M['K'][2] -= 1
                        changed = True
        # 就绪：首格在本刻某时空着（本刻收了货，或结束时空着）
        ready = {}
        blocked = {}
        for p in ('CA', 'CB'):
            s0 = self.P[p][0]
            ready[p] = (took[p] > 0) or (s0 is None)
            blocked[p] = first_old[p] and s0 is not None and s0 < t
        k_outblocked = (self.M['K'][1] == DONE)
        self.last_kout = sum(1 for x in kout_taken if x)
        self.t += 1
        return took, ready, blocked, k_started, k_outblocked


def run_case(seed, m, L1, L2, L3, L4, k, prefix, fill, flip_p, phase_len):
    rng = random.Random(seed)
    c = Cell(m, L1, L2, L3, L4, k, rng)
    c.randomize(fill)
    phi0 = c.phi()
    S = L1 + L2 + 2
    stall = L1 + L2 + 3 * m + 2 + (m - 1) / 2.0
    floor = min(phi0 - 0.5, stall - 0.5)
    viol = []
    minphi = phi0
    nstall = 0
    acc_mode = 'all'
    for step in range(prefix):
        if step % phase_len == 0:
            acc_mode = rng.choice(['all', 'none', 'rand', 'one'])
        if acc_mode == 'all':
            accept = [True] * k
        elif acc_mode == 'none':
            accept = [False] * k
        elif acc_mode == 'one':
            accept = [j == 0 for j in range(k)]
        else:
            accept = [rng.random() < 0.5 for _ in range(k)]
        order = c.tmpl[:]
        rng.shuffle(order)
        flip = rng.choice('AB') if rng.random() < flip_p else None
        before = c.phi()
        took, ready, blocked, _, _ = c.step(order, accept, flip)
        after = c.phi()
        a, b = took['CA'], took['CB']
        if a > 1 or b > 1:
            viol.append(('F0', step, a, b))
        if abs((after - before) - (a - b) / 2.0) > 1e-9:
            viol.append(('F1', step, before, after, a, b))
        s_end = c.M['C'][2]
        if ready['CA'] and a == 0 and s_end != 0:
            viol.append(('F2A', step, s_end))
        if ready['CB'] and b == 0 and s_end != 0:
            viol.append(('F2B', step, s_end))
        if blocked['CA']:
            nstall += 1
            if after < stall - 1e-9:
                viol.append(('F3', step, after, stall))
        if after < floor - 1e-9:
            viol.append(('F4', step, after, floor))
        minphi = min(minphi, after)
        if len(viol) > 5:
            break
    # 对手停手
    order = c.tmpl[:]
    rng.shuffle(order)
    ptr_rule_fixed = True
    seen = {}
    hist = []
    res = None
    for step in range(20000):
        kk = c.key()
        if kk in seen:
            start = seen[kk]
            cyc = hist[start:]
            kst = [h[0] for h in cyc]
            kob = [h[1] for h in cyc]
            phis = [h[2] for h in cyc]
            res = dict(cycle_len=len(cyc), k_rate=sum(kst) / len(cyc), k_outblocked=any(kob),
                       phi_min=min(phis), phi_max=max(phis))
            break
        seen[kk] = len(hist)
        took, ready, blocked, ks, kob = c.step(order, [True] * k, None)
        hist.append((1 if ks else 0, kob, c.phi()))
        if blocked['CA'] and c.phi() < stall - 1e-9:
            viol.append(('F3b', step))
        if c.phi() < floor - 1e-9:
            viol.append(('F4b', step, c.phi(), floor))
    if res is None:
        viol.append(('nocycle',))
        return dict(seed=seed, phi0=phi0, viol=viol)
    thm_ok = True
    if res['phi_min'] >= S and not res['k_outblocked'] and res['k_rate'] != 1.0:
        thm_ok = False
        viol.append(('T', res))
    return dict(seed=seed, m=m, L=(L1, L2, L3, L4), k=k, phi0=phi0, S=S, floor=floor, minphi=minphi,
                nstall=nstall, cycle=res, viol=viol)


def main():
    t0 = time.time()
    nruns = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    base = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    rng = random.Random(12345 + base)
    out = []
    stats = dict(runs=0, viol_runs=0, stall_runs=0, full_cycles=0, low_cycles=0, low_cycles_phi_ge_S=0,
                 low_cycles_phi_lt_S=0, outblocked_cycles=0)
    for r in range(nruns):
        m = rng.choice([50, 50, 50, 5, 8, 12])
        L1 = rng.randint(1, 8); L2 = rng.randint(1, 8); L3 = rng.randint(1, 8); L4 = rng.randint(1, 6)
        k = rng.choice([2, 3])
        prefix = rng.choice([200, 600, 1500])
        fill = rng.choice([0.0, 0.2, 0.6, 1.0])
        flip_p = rng.choice([0.0, 0.1, 0.5])
        phase_len = rng.choice([5, 30, 200])
        res = run_case(base * 100000 + r, m, L1, L2, L3, L4, k, prefix, fill, flip_p, phase_len)
        stats['runs'] += 1
        if res['viol']:
            stats['viol_runs'] += 1
        if res.get('nstall', 0):
            stats['stall_runs'] += 1
        cy = res.get('cycle')
        if cy:
            if cy['k_outblocked']:
                stats['outblocked_cycles'] += 1
            if cy['k_rate'] == 1.0:
                stats['full_cycles'] += 1
            else:
                stats['low_cycles'] += 1
                if cy['phi_min'] >= res['S']:
                    stats['low_cycles_phi_ge_S'] += 1
                else:
                    stats['low_cycles_phi_lt_S'] += 1
        out.append(res)
    stats['seconds'] = round(time.time() - t0, 1)
    bad = [o for o in out if o['viol']]
    lows = [o for o in out if o.get('cycle') and o['cycle']['k_rate'] != 1.0][:10]
    json.dump(dict(stats=stats, violations=bad[:20], low_rate_examples=lows), sys.stdout, ensure_ascii=False,
              indent=1, default=str)


if __name__ == '__main__':
    main()
