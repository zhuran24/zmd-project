#!/usr/bin/env python3
"""编码二：小容量穷举（与编码一独立写法）。

把出口侧（路 CB 之后的种植机 B、粉碎机 K 和 K 的下游）整个换成对手：每刻由对手决定
B 通道首格本刻空不空（就绪与否）。这比真实出口侧更宽，所以对它成立的「种群下界」对真实单元也成立；
「不自成瓶颈」用 B 通道每刻都就绪来代表「K 从不因取货格放不下而停」的情形（第 3.4 节说明这一推论）。

同刻闭包用「规则反复套用到不动」求：机器（完成的一批整批进取货格、空闲且有料就开工）、
运输格逐格前移（本刻刚进格的货不能再动）、路尾进机器存货格（未满）、单通道出货；
C 取货格的两条通道不用指针，而是枚举「本刻准许谁取」fa、fb∈{0,1}，
再检查闭包是否自洽：准许的必须取到，不准许的若首格在闭包时空着则 C 取货格必须为 0。
这样得到的后继集合包含任何判定次序、任何指针（含离线改指针）下的真实后继。

检查：
  E1 ΔΦ=(α-β)/2（逐状态、逐后继）；
  E2 A 通道被堵 ⇒ 闭包后 Φ ≥ L1+L2+3m+2+(m-1)/2；
  E3 下界：从任一状态出发，对手任意，能到达的最小 Φ ≥ min(Φ0-1/2, 堵塞界-1/2)；
  E4 B 通道每刻就绪、分配按三种确定规则（偏 A、偏 B、交替）时，所有循环里若 Φ 最小值 ≥ S=L1+L2+2，
     则每刻 B 都取到种子（出口满速），C 每刻开一批。
"""
import itertools, json, sys, time
from collections import defaultdict

IDLE, WORK, DONE = 0, 1, 2


def make(m, L1, L2):
    S = L1 + L2 + 2
    stall = L1 + L2 + 3 * m + 2 + (m - 1) / 2.0

    def phi(st):
        (ci, cs, co), (ai, as_, ao), ca, ac = st
        return (sum(ca) + ai + (as_ != IDLE) + ao + sum(ac) + ci + (cs != IDLE)) + co / 2.0

    def closure(st, b_ready, fa, fb):
        (ci, cs, co), (ai, as_, ao), ca, ac = st
        # 计时：上一刻开工的在本刻完成
        if cs == WORK: cs = DONE
        if as_ == WORK: as_ = DONE
        ca = [1 if x else 0 for x in ca]   # 0 空, 1 旧货, 2 本刻新进
        ac = [1 if x else 0 for x in ac]
        cb_free = b_ready                   # B 通道首格本刻是否空出
        tookA = tookB = 0
        ca0_old = ca[0] == 1
        while True:
            ch = False
            # 机器 C
            if cs == DONE and co + 2 <= m:
                co += 2; cs = IDLE; ch = True
            if cs == IDLE and ci >= 1:
                ci -= 1; cs = WORK; ch = True
            # 机器 A
            if as_ == DONE and ao + 1 <= m:
                ao += 1; as_ = IDLE; ch = True
            if as_ == IDLE and ai >= 1:
                ai -= 1; as_ = WORK; ch = True
            # 路 CA：路尾进 A
            if ca[-1] == 1 and ai < m:
                ca[-1] = 0; ai += 1; ch = True
            for i in range(len(ca) - 2, -1, -1):
                if ca[i] == 1 and ca[i + 1] == 0:
                    ca[i + 1] = 2; ca[i] = 0; ch = True
            # 路 AC：路尾进 C
            if ac[-1] == 1 and ci < m:
                ac[-1] = 0; ci += 1; ch = True
            for i in range(len(ac) - 2, -1, -1):
                if ac[i] == 1 and ac[i + 1] == 0:
                    ac[i + 1] = 2; ac[i] = 0; ch = True
            # A 出货到路 AC
            if ao >= 1 and ac[0] == 0:
                ao -= 1; ac[0] = 2; ch = True
            # C 出货：只许准许的通道取
            if fa and not tookA and co >= 1 and ca[0] == 0:
                co -= 1; ca[0] = 2; tookA = 1; ch = True
            if fb and not tookB and co >= 1 and cb_free:
                co -= 1; cb_free = False; tookB = 1; ch = True
            if not ch:
                break
        # 自洽检查
        if fa and not tookA: return None
        if fb and not tookB: return None
        if not fa and ca[0] == 0 and co > 0: return None
        if not fb and cb_free and co > 0: return None
        a_blocked = ca0_old and ca[0] == 1
        nst = ((ci, cs, co), (ai, as_, ao), tuple(1 if x else 0 for x in ca), tuple(1 if x else 0 for x in ac))
        c_started = (cs == WORK)
        return nst, tookA, tookB, a_blocked, c_started

    states = []
    for ci in range(m + 1):
        for cs in (IDLE, WORK, DONE):
            for co in range(m + 1):
                for ai in range(m + 1):
                    for as_ in (IDLE, WORK, DONE):
                        for ao in range(m + 1):
                            for ca in itertools.product((0, 1), repeat=L1):
                                for ac in itertools.product((0, 1), repeat=L2):
                                    states.append(((ci, cs, co), (ai, as_, ao), ca, ac))
    return S, stall, phi, closure, states


def run(m, L1, L2):
    t0 = time.time()
    S, stall, phi, closure, states = make(m, L1, L2)
    idx = {s: i for i, s in enumerate(states)}
    n = len(states)
    ph = [phi(s) for s in states]
    viol = defaultdict(int)
    viol['E1'] = 0; viol['E2'] = 0; viol['no_successor'] = 0
    examples = {}
    succ = [[] for _ in range(n)]
    for i, s in enumerate(states):
        outs = set()
        for b_ready in (True, False):
            for fa in (0, 1):
                for fb in (0, 1):
                    r = closure(s, b_ready, fa, fb)
                    if r is None:
                        continue
                    nst, a, b, ablk, _ = r
                    j = idx[nst]
                    if abs((ph[j] - ph[i]) - (a - b) / 2.0) > 1e-9:
                        viol['E1'] += 1; examples.setdefault('E1', (s, nst, a, b))
                    if ablk and ph[j] < stall - 1e-9:
                        viol['E2'] += 1; examples.setdefault('E2', (s, nst))
                    outs.add(j)
        if not outs:
            viol['no_successor'] += 1; examples.setdefault('no_successor', s)
        succ[i] = list(outs)
    # E3：能到达的最小 Φ（对手任意）。反向传播求 minreach。
    pred = [[] for _ in range(n)]
    for i in range(n):
        for j in succ[i]:
            pred[j].append(i)
    minr = ph[:]
    # 按 Φ 从小到大把值往前驱传
    order = sorted(range(n), key=lambda i: ph[i])
    import heapq
    heap = [(ph[i], i) for i in range(n)]
    heapq.heapify(heap)
    done = [False] * n
    while heap:
        v, j = heapq.heappop(heap)
        if done[j] or v > minr[j]:
            continue
        done[j] = True
        for i in pred[j]:
            if v < minr[i]:
                minr[i] = v
                heapq.heappush(heap, (v, i))
    e3_bad = 0
    e3_tight = 0
    for i in range(n):
        bound = min(ph[i] - 0.5, stall - 0.5)
        if minr[i] < bound - 1e-9:
            e3_bad += 1; examples.setdefault('E3', (states[i], ph[i], minr[i], bound))
        if abs(minr[i] - bound) < 1e-9:
            e3_tight += 1
    viol['E3'] = e3_bad
    # E4：B 每刻就绪、三种确定分配规则下的循环
    cyc_stats = {}
    for pol in ('preferA', 'preferB', 'alt'):
        nxt = {}
        def step(key):
            s, p = key
            if pol == 'preferA': cands = [(1, 1), (1, 0), (0, 1), (0, 0)]
            elif pol == 'preferB': cands = [(1, 1), (0, 1), (1, 0), (0, 0)]
            else: cands = [(1, 1), (1, 0), (0, 1), (0, 0)] if p == 0 else [(1, 1), (0, 1), (1, 0), (0, 0)]
            for fa, fb in cands:
                r = closure(s, True, fa, fb)
                if r is not None:
                    nst, a, b, _, cst = r
                    np_ = p
                    if pol == 'alt' and a + b == 1:
                        np_ = 1 if a else 0   # 取过的一方下次让给另一方
                    return (nst, np_), a, b, cst
            raise RuntimeError('no det successor')
        visited = {}
        ncyc = 0; bad = 0; lowrate = 0; lowrate_ge_S = 0; rates = defaultdict(int)
        keys = [(s, 0) for s in states] + ([(s, 1) for s in states] if pol == 'alt' else [])
        for k0 in keys:
            if k0 in visited:
                continue
            path = []
            pos = {}
            k = k0
            while k not in visited and k not in pos:
                pos[k] = len(path)
                nk, a, b, cst = step(k)
                path.append((k, a, b, cst))
                k = nk
            if k in pos:
                cyc = path[pos[k]:]
                ncyc += 1
                L = len(cyc)
                brate = sum(x[2] for x in cyc) / L
                crate = sum(1 for x in cyc if x[3]) / L
                pmin = min(ph[idx[x[0][0]]] for x in cyc)
                rates[(round(brate, 4), pmin >= S)] += 1
                if brate < 1:
                    lowrate += 1
                    if pmin >= S:
                        lowrate_ge_S += 1
                        examples.setdefault('E4_' + pol, [x[0] for x in cyc][:5])
                if pmin >= S and (brate != 1 or crate != 1):
                    bad += 1
            for x in path:
                visited[x[0]] = True
        cyc_stats[pol] = dict(cycles=ncyc, low_rate_cycles=lowrate, low_rate_cycles_phi_ge_S=lowrate_ge_S,
                              violations=bad,
                              rate_hist={'%s|phi>=S:%s' % kk: v for kk, v in sorted(rates.items())})
        viol['E4_' + pol] = bad
    return dict(m=m, L1=L1, L2=L2, S=S, stall=stall, states=n, edges=sum(len(x) for x in succ),
                violations=dict(viol), e3_tight_states=e3_tight, cycles=cyc_stats,
                examples={k: str(v) for k, v in examples.items()}, seconds=round(time.time() - t0, 1))


if __name__ == '__main__':
    m, L1, L2 = map(int, sys.argv[1:4])
    json.dump(run(m, L1, L2), sys.stdout, ensure_ascii=False, indent=1)
