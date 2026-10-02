#!/usr/bin/env python3
"""复核103H：H06 采种单元的回路存量下界、H07 采种单元不断料。自写，不导入推导席脚本、不用 sim2。

模型（纯传送带进路；每条进路是一个元件，层数 1，往机器送货）：
  一步 = 一个时点：先结束到时的制造（到时的一批若取货格放得下就整批进入），再判定元件（带末成熟件
  送进下游机器或出口；带内成熟件在后格空时前移，进格重新计 8 步），再判定机器（非运输单位，向取货
  通道首格送 1 件，之后若缓存里做好的一批放得下就立即进入），最后开始能开始的制造（用 1 件原料，
  8 步后到时）。
  C 两条出口 CA、CB 按第32行轮询：从未成功的按接通先后在前，已成功的按上次成功由早到晚。
  K 的 n 条出口同理。离线在两步之间：keep 保留成功记录、只换接通先后；clear 全部记录清空、按新接通先后。
  B、K 真实运行，K 出口带末端由对手随时决定收或不收；或 B 换成对手随时收货的出口（更宽）。
编码甲：入格步号；编码乙：倒计时＋显式队列＋不动点式前移。两者逐步比较全状态。
"""
import json, random, sys
from fractions import Fraction as Fr

YIELD = {'C': 2, 'A': 1, 'B': 1}

class EngA:
    def __init__(self, cfg, st):
        self.k = cfg['k']; self.n = cfg['n']; self.Bmode = cfg['Bmode']
        self.belts = {b: list(st['belts'][b]) for b in st['belts']}
        self.m = {x: dict(st['m'][x]) for x in st['m']}
        self.connC = list(st['connC']); self.lastC = list(st['lastC'])
        self.connK = list(st['connK']); self.lastK = list(st['lastK'])
        self.dest = {'CA': 'A', 'AC': 'C', 'CB': 'B' if self.Bmode == 'real' else 'sinkB', 'BK': 'K'}
        for j in range(self.n): self.dest['K%d' % j] = 'sink%d' % j
        self.yield_ = dict(YIELD); self.yield_['K'] = self.k

    def flush(self, x):
        mm = self.m[x]
        if mm['cache'] == 'done' and mm['out'] + self.yield_[x] <= 50:
            mm['out'] += self.yield_[x]; mm['cache'] = None

    def accepts(self, d, acc):
        if d.startswith('sink'): return acc.get(d, False)
        return self.m[d]['inp'] < 50

    def offline(self, mode, cC, cK):
        self.connC = list(cC); self.connK = list(cK)
        if mode == 'clear':
            self.lastC = [None, None]; self.lastK = [None] * self.n

    def order(self, conn, last):
        return sorted(range(len(last)), key=lambda i: (0, conn.index(i)) if last[i] is None else (1, last[i]))

    def step(self, t, acc):
        ms = [x for x in self.m]
        for x in ms:
            mm = self.m[x]
            if isinstance(mm['cache'], int) and mm['cache'] <= t:
                mm['cache'] = 'done'
            self.flush(x)
        for b, cells in self.belts.items():
            L = len(cells); d = self.dest[b]
            if cells[L - 1] is not None and t - cells[L - 1] >= 8 and self.accepts(d, acc):
                cells[L - 1] = None
                if not d.startswith('sink'): self.m[d]['inp'] += 1
            for i in range(L - 2, -1, -1):
                if cells[i] is not None and t - cells[i] >= 8 and cells[i + 1] is None:
                    cells[i + 1] = t; cells[i] = None
        sent = {}
        # C
        if self.m['C']['out'] > 0:
            for i in self.order(self.connC, self.lastC):
                b = 'CA' if i == 0 else 'CB'
                if self.belts[b][0] is None:
                    self.belts[b][0] = t; self.m['C']['out'] -= 1; self.lastC[i] = t; sent['C'] = i; break
            self.flush('C')
        if self.m['A']['out'] > 0 and self.belts['AC'][0] is None:
            self.belts['AC'][0] = t; self.m['A']['out'] -= 1; self.flush('A')
        if 'B' in self.m and self.m['B']['out'] > 0 and self.belts['BK'][0] is None:
            self.belts['BK'][0] = t; self.m['B']['out'] -= 1; self.flush('B')
        if 'K' in self.m and self.m['K']['out'] > 0 and self.n > 0:
            for i in self.order(self.connK, self.lastK):
                b = 'K%d' % i
                if self.belts[b][0] is None:
                    self.belts[b][0] = t; self.m['K']['out'] -= 1; self.lastK[i] = t; sent['K'] = i; break
            self.flush('K')
        for x in ms:
            mm = self.m[x]
            if mm['cache'] is None and mm['inp'] >= 1:
                mm['inp'] -= 1; mm['cache'] = t + 8
        return sent

    def snapshot(self, t):
        bel = {b: tuple(None if c is None else max(0, 8 - (t - c)) for c in cells) for b, cells in self.belts.items()}
        mm = {x: (v['inp'], v['out'], 'none' if v['cache'] is None else ('done' if v['cache'] == 'done' else max(0, v['cache'] - t)))
              for x, v in self.m.items()}
        return bel, mm

    def phi(self):
        m = self.m; b = self.belts
        v = Fr(sum(1 for c in b['CA'] if c is not None) + sum(1 for c in b['AC'] if c is not None))
        v += m['A']['inp'] + m['A']['out'] + m['C']['inp']
        v += (1 if m['A']['cache'] is not None else 0) + (1 if m['C']['cache'] is not None else 0)
        v += Fr(m['C']['out'], 2)
        return v

class EngB:
    """倒计时编码：格内存剩余滞留步数（0=成熟），机器缓存存剩余步数；C/K 轮询用显式队列。"""
    def __init__(self, cfg, st, t0):
        self.k = cfg['k']; self.n = cfg['n']; self.Bmode = cfg['Bmode']
        # 把入格步号换成「到 t0 步开头时」的剩余滞留
        self.b = {b: [None if c is None else max(0, 8 - (t0 - c)) for c in cells] for b, cells in st['belts'].items()}
        self.mc = {}
        for x, v in st['m'].items():
            c = v['cache']
            cc = None if c is None else ('D' if c == 'done' else max(0, c - t0))
            self.mc[x] = [v['inp'], v['out'], cc]
        self.yl = {'C': 2, 'A': 1, 'B': 1, 'K': self.k}
        def mkq(conn, last):
            nv = [i for i in conn if last[i] is None]
            sc = sorted([i for i in range(len(last)) if last[i] is not None], key=lambda i: last[i])
            return nv + sc, set(nv)
        self.qC, self.nvC = mkq(st['connC'], st['lastC'])
        self.qK, self.nvK = mkq(st['connK'], st['lastK'])
        self.dst = {'CA': 'A', 'AC': 'C', 'CB': 'B' if self.Bmode == 'real' else None, 'BK': 'K'}
        for j in range(self.n): self.dst['K%d' % j] = None

    def offline(self, mode, cC, cK):
        if mode == 'clear':
            self.qC, self.nvC = list(cC), set(cC); self.qK, self.nvK = list(cK), set(cK)
        else:
            def re(q, nv, conn):
                a = [i for i in conn if i in nv]; return a + [i for i in q if i not in nv]
            self.qC = re(self.qC, self.nvC, cC); self.qK = re(self.qK, self.nvK, cK)

    def tick_clock(self):
        for cells in self.b.values():
            for i, c in enumerate(cells):
                if c is not None and c > 0: cells[i] = c - 1
        for v in self.mc.values():
            if isinstance(v[2], int) and v[2] > 0: v[2] -= 1

    def fl(self, x):
        v = self.mc[x]
        if v[2] == 'D' and v[1] + self.yl[x] <= 50:
            v[1] += self.yl[x]; v[2] = None

    def step(self, acc):
        for x, v in self.mc.items():
            if v[2] == 0: v[2] = 'D'
            self.fl(x)
        for bname, cells in self.b.items():
            d = self.dst[bname]
            sinkname = 'sinkB' if bname == 'CB' else ('sink' + bname[1:] if bname.startswith('K') else None)
            last = len(cells) - 1
            if cells[last] == 0:
                ok = acc.get(sinkname, False) if d is None else self.mc[d][0] < 50
                if ok:
                    cells[last] = None
                    if d is not None: self.mc[d][0] += 1
            changed = True
            while changed:  # 不动点：成熟件只要后格空就前移（前移后不再成熟，不会一步走两格）
                changed = False
                for i in range(last):
                    if cells[i] == 0 and cells[i + 1] is None:
                        cells[i + 1] = 8; cells[i] = None; changed = True
        sent = {}
        v = self.mc['C']
        if v[1] > 0:
            for i in self.qC:
                cells = self.b['CA' if i == 0 else 'CB']
                if cells[0] is None:
                    cells[0] = 8; v[1] -= 1; self.qC.remove(i); self.qC.append(i); self.nvC.discard(i); sent['C'] = i; break
            self.fl('C')
        v = self.mc['A']
        if v[1] > 0 and self.b['AC'][0] is None:
            self.b['AC'][0] = 8; v[1] -= 1; self.fl('A')
        if 'B' in self.mc:
            v = self.mc['B']
            if v[1] > 0 and self.b['BK'][0] is None:
                self.b['BK'][0] = 8; v[1] -= 1; self.fl('B')
        if 'K' in self.mc and self.n > 0:
            v = self.mc['K']
            if v[1] > 0:
                for i in self.qK:
                    cells = self.b['K%d' % i]
                    if cells[0] is None:
                        cells[0] = 8; v[1] -= 1; self.qK.remove(i); self.qK.append(i); self.nvK.discard(i); sent['K'] = i; break
                self.fl('K')
        for x, v in self.mc.items():
            if v[2] is None and v[0] >= 1:
                v[0] -= 1; v[2] = 8
        return sent

    def snapshot(self):
        # 与甲的 snapshot 同格式：格内剩余滞留在下一步开头会减 1，这里给「本步末」口径：剩余 = c
        bel = {b: tuple(c for c in cells) for b, cells in self.b.items()}
        mm = {x: (v[0], v[1], 'none' if v[2] is None else ('done' if v[2] == 'D' else v[2])) for x, v in self.mc.items()}
        return bel, mm

# ---------------- 起态生成 ----------------
def gen_state(rng, cfg, kind):
    L1, L2, L3, L4 = cfg['L']
    k, n = cfg['k'], cfg['n']
    def belt(L, p):
        return [(-rng.randrange(0, 12) if rng.random() < p else None) for _ in range(L)]
    st = {'belts': {}, 'm': {}}
    if kind == 'full177':
        st['belts']['CA'] = [-rng.randrange(0, 12) for _ in range(L1)]
        st['belts']['AC'] = [-rng.randrange(0, 12) for _ in range(L2)]
        st['belts']['CB'] = [-rng.randrange(0, 12) for _ in range(L3)]
        st['belts']['BK'] = [-rng.randrange(0, 12) for _ in range(L4)]
        def cache(): return rng.choice(['done', rng.randrange(1, 9)])
        st['m']['C'] = {'inp': 50, 'out': 50, 'cache': cache()}
        st['m']['A'] = {'inp': 50, 'out': 50, 'cache': cache()}
        st['m']['B'] = {'inp': 50, 'out': 50, 'cache': cache()}
        st['m']['K'] = {'inp': 50, 'out': 50, 'cache': cache()}
    else:
        hi = kind == 'high'
        p = rng.choice([1.0, 1.0, 0.9, 0.5]) if hi else rng.random()
        st['belts']['CA'] = belt(L1, p); st['belts']['AC'] = belt(L2, p)
        st['belts']['CB'] = belt(L3, rng.random()); st['belts']['BK'] = belt(L4, rng.random())
        def cnt(lo):
            return rng.randrange(lo, 51) if hi else rng.choice([0, 1, 2, rng.randrange(0, 51)])
        def cache(): return rng.choice([None, 'done', rng.randrange(1, 9)])
        st['m']['C'] = {'inp': cnt(44), 'out': cnt(40), 'cache': cache()}
        st['m']['A'] = {'inp': cnt(44), 'out': cnt(44), 'cache': cache()}
        st['m']['B'] = {'inp': rng.randrange(0, 51), 'out': rng.randrange(0, 51), 'cache': cache()}
        st['m']['K'] = {'inp': rng.randrange(0, 51), 'out': rng.randrange(0, 51), 'cache': cache()}
    if cfg['Bmode'] != 'real':
        del st['m']['B']; del st['m']['K']; del st['belts']['BK']
    else:
        for j in range(n):
            st['belts']['K%d' % j] = belt(rng.randrange(1, 4), rng.random() if kind != 'full177' else rng.random())
    if kind == 'full177' and cfg['Bmode'] == 'real':
        for j in range(n):
            st['belts']['K%d' % j] = [None if rng.random() < 0.5 else -rng.randrange(0, 12) for _ in range(rng.randrange(1, 4))]
    st['connC'] = rng.sample([0, 1], 2)
    st['lastC'] = [None if rng.random() < 0.4 else -rng.randrange(1, 30) - 0.1 * i for i in range(2)]
    st['connK'] = rng.sample(range(n), n)
    st['lastK'] = [None if rng.random() < 0.4 else -rng.randrange(1, 30) - 0.1 * i for i in range(n)]
    return st

def gen_sched(rng, cfg, horizon, offmode):
    n = cfg['n']
    rate = rng.choice([0.0, 0.01, 0.05, 0.2, 0.5])
    greedy = rng.random() < 0.5
    sinks = ['sinkB'] + ['sink%d' % j for j in range(n)]
    acc = []
    state = {s: True for s in sinks}
    for t in range(horizon + 2):
        for s in sinks:
            if rng.random() < 0.05: state[s] = not state[s]
        acc.append({s: (state[s] and rng.random() < 0.9) for s in sinks})
    offl = {}
    for x in range(1, horizon + 1):
        if rng.random() < rate:
            md = offmode if offmode in ('keep', 'clear') else rng.choice(['keep', 'clear'])
            cC = [1, 0] if greedy else rng.sample([0, 1], 2)   # greedy：让 CB 先接通，利于送 B
            offl[x] = (md, cC, rng.sample(range(n), n))
    return acc, offl

# ---------------- 运行与检查 ----------------
def run_case(rng, cfg, kind, horizon, offmode, dual, normal):
    st = gen_state(rng, cfg, kind)
    acc, offl = gen_sched(rng, cfg, horizon, offmode)
    A = EngA(cfg, st)
    t0 = 1
    if normal:
        # 先实际运行一步（第 1 步），s 取其步末；该步前不离线
        A.step(1, acc[1]); t0 = 2
    B = EngB(cfg, {'belts': A.belts, 'm': A.m, 'connC': A.connC, 'lastC': A.lastC, 'connK': A.connK, 'lastK': A.lastK}, t0 - 1) if dual else None
    L = cfg['L'][0] + cfg['L'][1]
    H0 = 176 if normal else 150
    phis = A.phi(); phiseg = phis; seg_normal = normal
    m_clear = 0; m_all = 0
    out = dict(viol_seg=0, viol_keep_cross=0, viol_cum=0, viol_half=0, old_bound_break=0, enc_mismatch=0,
               min_slack_seg=None, phis=float(phis))
    all_keep = True
    for t in range(t0, horizon):
        if t in offl:
            md, cC, cK = offl[t]
            A.offline(md, cC, cK)
            if B: B.offline(md, cC, cK)
            m_all += 1
            if md == 'clear':
                m_clear += 1; all_keep = False
            phiseg = A.phi()
            if t > 1: seg_normal = True  # 段首是实际运行过的完整步末；第 1 步前的离线仍是准备截面
        if B: B.tick_clock()
        A.step(t, acc[t])
        if B:
            B.step(acc[t])
            if A.snapshot(t) != B.snapshot():
                out['enc_mismatch'] += 1; B = None
        ph = A.phi()
        Hs = 176 if seg_normal else H0
        # 段内界（任何离线都切段）
        bnd = min(phiseg - Fr(1, 2), L + Hs)
        if ph < bnd: out['viol_seg'] += 1
        sl = ph - bnd
        out['min_slack_seg'] = sl if out['min_slack_seg'] is None else min(out['min_slack_seg'], sl)
        # 只保留记录时，从 s 起跨离线
        if all_keep and ph < min(phis - Fr(1, 2), L + H0): out['viol_keep_cross'] += 1
        # 累计界：m 只数清空离线
        if ph < min(phis - Fr(m_clear + 1, 2), L + H0 - Fr(m_clear, 2)): out['viol_cum'] += 1
        if phis >= 1 and ph < Fr(1, 2): out['viol_half'] += 1
        # 旧版（第92C/D、95T）跨离线起值支是否被打破
        if ph < min(phis - Fr(1, 2), L + 150): out['old_bound_break'] += 1
    return out

def run_full(rng, cfg, horizon, offmode):
    """H07（二）：Φ(s)=L+177 满起态。检查四缓存不空、B/K 存货>=49、B 取货>=49、K 取货>=50-k、
    CB/BK 首格步末非空、K 首格等待 <= n-1 步。"""
    st = gen_state(rng, cfg, 'full177')
    acc, offl = gen_sched(rng, cfg, horizon, offmode)
    A = EngA(cfg, st)
    k, n = cfg['k'], cfg['n']
    out = dict(viol_cache=0, viol_inv=0, viol_head=0, viol_wait=0, max_wait=0, min_Kout=50, min_inp=50)
    assert A.phi() == cfg['L'][0] + cfg['L'][1] + 177
    empty_since = {}
    for t in range(1, horizon):
        if t in offl:
            md, cC, cK = offl[t]; A.offline(md, cC, cK)
        sent = A.step(t, acc[t])
        mm = A.m
        if any(mm[x]['cache'] is None for x in 'CABK'): out['viol_cache'] += 1
        if mm['B']['inp'] < 49 or mm['K']['inp'] < 49 or mm['B']['out'] < 49 or mm['K']['out'] < 50 - k: out['viol_inv'] += 1
        out['min_Kout'] = min(out['min_Kout'], mm['K']['out']); out['min_inp'] = min(out['min_inp'], mm['B']['inp'], mm['K']['inp'])
        if A.belts['CB'][0] is None or A.belts['BK'][0] is None: out['viol_head'] += 1
        # K 首格等待：判定前空（元件阶段后仍空）到获补的步数
        for j in range(n):
            b = A.belts['K%d' % j]
            if b[0] is not None and b[0] == t:
                if j in empty_since:
                    w = t - empty_since.pop(j)
                    out['max_wait'] = max(out['max_wait'], w)
                    if w > n - 1: out['viol_wait'] += 1
            elif b[0] is None:
                empty_since.setdefault(j, t)
    return out

def liveness(rng, cfg, horizon):
    """H07（一）：Φ(s)>=1 的低存量起态，K 出口最终总会收；清空读法、贪心让 CB 先接通。
    看四机在最后 400 步内是否都开过批，及 Φ>=1/2。"""
    st = gen_state(rng, cfg, 'low')
    A = EngA(cfg, st)
    if A.phi() < 1: return None
    n = cfg['n']
    sinks = ['sink%d' % j for j in range(n)]
    lastb = {x: -1 for x in 'CABK'}
    minphi = A.phi()
    starts = {x: 0 for x in 'CABK'}
    for t in range(1, horizon):
        if rng.random() < 0.1:
            A.offline('clear', [1, 0], rng.sample(range(n), n))
        acc = {s: rng.random() < 0.5 for s in sinks}
        before = {x: A.m[x]['cache'] for x in 'CABK'}
        A.step(t, acc)
        for x in 'CABK':
            if A.m[x]['cache'] == t + 8:
                lastb[x] = t; starts[x] += 1
        minphi = min(minphi, A.phi())
    return dict(all_recent=all(lastb[x] >= horizon - 400 for x in 'CABK'), minphi=float(minphi), starts=starts)

def main():
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    rng = random.Random(seed)
    res = {'seed': seed}
    agg = {}
    def add(key, o):
        a = agg.setdefault(key, dict(cases=0, viol_seg=0, viol_keep_cross=0, viol_cum=0, viol_half=0,
                                      old_bound_break_cases=0, enc_mismatch=0, min_slack_seg=None, dual=0))
        a['cases'] += 1
        for f in ('viol_seg', 'viol_keep_cross', 'viol_cum', 'viol_half', 'enc_mismatch'):
            a[f] += o[f]
        if o['old_bound_break']: a['old_bound_break_cases'] += 1
        if o['min_slack_seg'] is not None:
            a['min_slack_seg'] = o['min_slack_seg'] if a['min_slack_seg'] is None else min(a['min_slack_seg'], o['min_slack_seg'])
    NR = int(sys.argv[3]) if len(sys.argv) > 3 else 600
    for it in range(NR):
        k = rng.choice([2, 3]); n = rng.randrange(0, k + 1)
        cfg = dict(k=k, n=n, L=[rng.randrange(1, 7), rng.randrange(1, 7), rng.randrange(1, 6), rng.randrange(1, 6)],
                   Bmode=rng.choice(['real', 'real', 'adv']))
        kind = rng.choice(['high', 'high', 'high', 'low'])
        offmode = rng.choice(['keep', 'clear', 'mixed'])
        normal = rng.random() < 0.5
        dual = it % 4 == 0
        o = run_case(rng, cfg, kind, 500, offmode, dual, normal)
        add(f'{offmode}_{"normal" if normal else "prep"}', o)
        if dual: agg[f'{offmode}_{"normal" if normal else "prep"}']['dual'] += 1
    for key in agg:
        if agg[key]['min_slack_seg'] is not None: agg[key]['min_slack_seg'] = str(agg[key]['min_slack_seg'])
    res['H06'] = agg
    fa = dict(cases=0, viol_cache=0, viol_inv=0, viol_head=0, viol_wait=0, max_wait_by_n={}, min_Kout_by_k={}, min_inp=50)
    for it in range(NR // 2):
        k = rng.choice([2, 3]); n = rng.randrange(0, k + 1)
        cfg = dict(k=k, n=n, L=[rng.randrange(1, 7), rng.randrange(1, 7), rng.randrange(1, 6), rng.randrange(1, 6)], Bmode='real')
        o = run_full(rng, cfg, 600, rng.choice(['keep', 'clear', 'mixed']))
        fa['cases'] += 1
        for f in ('viol_cache', 'viol_inv', 'viol_head', 'viol_wait'): fa[f] += o[f]
        fa['max_wait_by_n'][n] = max(fa['max_wait_by_n'].get(n, 0), o['max_wait'])
        fa['min_Kout_by_k'][k] = min(fa['min_Kout_by_k'].get(k, 50), o['min_Kout'])
        fa['min_inp'] = min(fa['min_inp'], o['min_inp'])
    res['H07_full'] = fa
    lv = dict(cases=0, not_live=0, minphi=99)
    for it in range(NR // 4):
        k = rng.choice([2, 3]); n = rng.randrange(1, k + 1)
        cfg = dict(k=k, n=n, L=[rng.randrange(1, 7), rng.randrange(1, 7), rng.randrange(1, 6), rng.randrange(1, 6)], Bmode='real')
        o = liveness(rng, cfg, 2500)
        if o is None: continue
        lv['cases'] += 1
        if not o['all_recent']: lv['not_live'] += 1
        lv['minphi'] = min(lv['minphi'], o['minphi'])
    res['H07_live'] = lv
    json.dump(res, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))

if __name__ == '__main__':
    main()
