#!/usr/bin/env python3
"""小容量穷举：专用进路下缓存格不空的传递（任意相位版）的三审核对。

时间取 1/Q tick 的格点。每个格点先推进计时（运输物品格停留时间、缓存格剩余进度、
物品准入口的 5 tick 窗口），再把同一时刻的判定按一切可能的先后做到没有可动为止（闭合）。
- 判定先后、轮询、取货优先级：同一时刻里任一可动的判定都可以先做（覆盖离线改接通先后）。
- 下游收货端（SINK）每个时刻收不收任意（覆盖仓库停收与恢复、下游任意运行）。
- 各单位事件可落在 1/Q 的不同余数上（物品进格、开批时刻由闭合决定）。
这是对真实规则的放宽：真实运行（判定先后固定、轮询按接通先后）是这张图里的一条路。

在「前提成立」（起点制造单位缓存格非空；主组起点一直开着）的状态导出的子图里求强连通分量，
凡落在环上的状态（真实循环态都在这些环上）都核：
  X 缓存格非空；起点满足前提的进路每格非空；起点的首格非空；末句适用时 X 的首格非空。
对照组故意去掉一个前提，应当查出违反。

用法：python3 exhaust.py <组名> [随机起态数] [种子]
只用标准库，单线程。
"""
import json
import random
import sys
import time

SINK = 'SINK'


class Model:
    def __init__(self, cfg):
        self.cfg = cfg
        Q = self.Q = cfg['Q']
        M = self.M = cfg['M']
        radices, names = [], []

        def field(name, r):
            names.append(name)
            radices.append(r)
            return len(radices) - 1

        self.cell = {c: field(c, Q + 2) for c in cfg['cells']}   # 0 空；1..Q+1 有货、停留 v-1 个 1/Q（Q+1 为停满）
        self.gate = {}
        for g, lim in cfg.get('gates', {}).items():
            assert g in self.cell
            self.gate[g] = (field(g + '.窗口剩余', 5 * Q + 1), field(g + '.窗口件数', lim + 1), lim)
        self.mach = {}
        for m, sp in cfg['machines'].items():
            st = {mat: field(f'{m}.存货.{mat}', M + 1) for mat in sorted(sp['inputs'])}
            dur = sp['d'] * Q
            self.mach[m] = dict(
                inputs=sp['inputs'], k=sp['k'], dur=dur, FIN=dur + 1, st=st,
                cache=field(m + '.缓存', dur + 2),   # 0 空；1..dur 剩余；dur+1 做好等进取货格
                pick=field(m + '.取货', M + 1),
                on=field(m + '.开着', 2),
                switchable=sp.get('switchable', False))
        self.radices, self.names = radices, names
        self.nf = len(radices)
        # 通道
        self.chans = []
        for src, dst in cfg['channels']:
            self.chans.append((self._src(src), self._dst(dst), dst != SINK))

    def _src(self, s):
        if s == 'W':
            return ('W',)
        if s in self.cell:
            return ('cell', self.cell[s])
        m = self.mach[s]
        return ('mach', m['pick'])

    def _dst(self, d):
        if d == SINK:
            return ('sink',)
        if d in self.cell:
            g = self.gate.get(d)
            return ('cell', self.cell[d], g)
        m, mat = d.split(':')
        return ('store', self.mach[m]['st'][mat])

    # ---- 编码 ----
    def enc(self, L):
        v = 0
        for x, r in zip(L, self.radices):
            v = v * r + x
        return v

    def dec(self, v):
        L = [0] * self.nf
        for i in range(self.nf - 1, -1, -1):
            v, L[i] = divmod(v, self.radices[i])
        return L

    # ---- 推进 1/Q tick ----
    def advance(self, L):
        Q = self.Q
        for i in self.cell.values():
            if 1 <= L[i] <= Q:
                L[i] += 1
        for wi, ni, lim in self.gate.values():
            if L[wi] > 0:
                L[wi] -= 1
                if L[wi] == 0:
                    L[ni] = 0
        for m in self.mach.values():
            c = L[m['cache']]
            if 1 <= c <= m['dur'] and L[m['on']]:
                c -= 1
                L[m['cache']] = m['FIN'] if c == 0 else c

    # ---- 同一时刻的判定 ----
    def moves(self, L):
        """返回 [(新状态列表, 是否必做)]。必做：能动就一定会在这一时刻动；可选：收货端收不收任意、开关。"""
        Q, M = self.Q, self.M
        out = []
        for src, dst, mand in self.chans:
            # 来源有货吗
            if src[0] == 'cell':
                if L[src[1]] != Q + 1:
                    continue
            elif src[0] == 'mach':
                if L[src[1]] == 0:
                    continue
            # 去处收得下吗
            if dst[0] == 'cell':
                if L[dst[1]] != 0:
                    continue
                g = dst[2]
                if g is not None and L[g[0]] > 0 and L[g[1]] >= g[2]:
                    continue   # 收下上限用尽，存货端口通道断开
            elif dst[0] == 'store':
                if L[dst[1]] >= M:
                    continue
            N = L[:]
            if src[0] == 'cell':
                N[src[1]] = 0
            elif src[0] == 'mach':
                N[src[1]] -= 1
            if dst[0] == 'cell':
                N[dst[1]] = 1
                g = dst[2]
                if g is not None:
                    if N[g[0]] == 0:
                        N[g[0]] = 5 * Q
                        N[g[1]] = 1
                    else:
                        N[g[1]] += 1
            elif dst[0] == 'store':
                N[dst[1]] += 1
            out.append((N, mand))
        for m in self.mach.values():
            c = L[m['cache']]
            if c == 0 and all(L[m['st'][mat]] >= a for mat, a in m['inputs'].items()):
                N = L[:]
                for mat, a in m['inputs'].items():
                    N[m['st'][mat]] -= a
                N[m['cache']] = m['dur']
                out.append((N, True))
            if c == m['FIN'] and L[m['pick']] + m['k'] <= M:
                N = L[:]
                N[m['pick']] += m['k']
                N[m['cache']] = 0
                out.append((N, True))
            if m['switchable']:
                N = L[:]
                N[m['on']] ^= 1
                out.append((N, False))
        return out

    def closure(self, L):
        """一切判定先后下，做到没有必做判定可动为止的全部结果（编码）。"""
        start = self.enc(L)
        seen = {start: L}
        stack = [L]
        finals = set()
        while stack:
            cur = stack.pop()
            mand = False
            for N, mnd in self.moves(cur):
                if mnd:
                    mand = True
                e = self.enc(N)
                if e not in seen:
                    seen[e] = N
                    stack.append(N)
            if not mand:
                finals.add(self.enc(cur))
        return finals

    def step(self, v):
        L = self.dec(v)
        self.advance(L)
        return self.closure(L)

    def random_state(self, rng):
        L = [rng.randrange(r) for r in self.radices]
        for wi, ni, lim in self.gate.values():
            if L[wi] == 0:
                L[ni] = 0
            elif L[ni] == 0:
                L[ni] = 1
        for m in self.mach.values():
            L[m['on']] = 1 if not m['switchable'] else L[m['on']]
        return L

    def all_states(self):
        import itertools
        ranges = [range(r) for r in self.radices]
        for m in self.mach.values():
            if not m['switchable']:
                ranges[m['on']] = range(1, 2)
        for L in itertools.product(*ranges):
            ok = True
            for wi, ni, lim in self.gate.values():
                if (L[wi] == 0) != (L[ni] == 0):
                    ok = False
            if ok:
                yield list(L)

    def size_all(self):
        n = 1
        for i, r in enumerate(self.radices):
            n *= r
        for m in self.mach.values():
            if not m['switchable']:
                n //= 2
        return n

    def empty_state(self):
        L = [0] * self.nf
        for m in self.mach.values():
            L[m['on']] = 1
        return L


def tarjan(nodes, succ):
    """迭代 Tarjan；返回在环上的节点集合（分量大于 1 或有自环）。"""
    index, low, onst = {}, {}, set()
    st, res = [], set()
    counter = 0
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(succ[root]))]
        index[root] = low[root] = counter
        counter += 1
        st.append(root)
        onst.add(root)
        while work:
            v, it = work[-1]
            adv = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    st.append(w)
                    onst.add(w)
                    work.append((w, iter(succ[w])))
                    adv = True
                    break
                elif w in onst:
                    low[v] = min(low[v], index[w])
            if adv:
                continue
            work.pop()
            if work:
                u = work[-1][0]
                low[u] = min(low[u], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = st.pop()
                    onst.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1 or v in succ[v]:
                    res.update(comp)
    return res


# ---------------- 各组接法 ----------------
def configs():
    C = {}
    # 主组：起点满足条文（一直开着、产物就是本线物品、1 tick、全部取货通道不多于每批件数）
    C['C1'] = dict(desc='仓库→精炼炉式 Y(1→1)→两格→X(1→1)→一格→下游任意；Q=2', Q=2, M=3,
                   machines={'Y': dict(inputs={'r': 1}, k=1, d=1), 'X': dict(inputs={'p': 1}, k=1, d=1)},
                   cells=['w1', 'a1', 'a2', 'o1'],
                   channels=[('W', 'w1'), ('w1', 'Y:r'), ('Y', 'a1'), ('a1', 'a2'), ('a2', 'X:p'), ('X', 'o1'), ('o1', SINK)],
                   premise=['Y'], target='X', lines=['a1', 'a2'], yfirst=['a1'], xfirst=['o1'])
    C['C1q3'] = dict(C['C1'], Q=3, desc='同 C1，Q=3')
    C['C2'] = dict(desc='Y(1→2) 一条进路进 X、一条经每 5 tick 限 1 件的物品准入口到下游任意；Q=2', Q=2, M=3,
                   machines={'Y': dict(inputs={'r': 1}, k=2, d=1), 'X': dict(inputs={'p': 1}, k=1, d=1)},
                   cells=['w1', 'a1', 'o1', 'g1'], gates={'g1': 1},
                   channels=[('W', 'w1'), ('w1', 'Y:r'), ('Y', 'a1'), ('a1', 'X:p'), ('X', 'o1'), ('o1', SINK),
                             ('Y', 'g1'), ('g1', SINK)],
                   premise=['Y'], target='X', lines=['a1'], yfirst=['a1'], xfirst=['o1'])
    C['C2b'] = dict(C['C2'], gates={'g1': 2}, desc='同 C2，准入口每 5 tick 限 2 件')
    C['C3'] = dict(desc='Y(1→2) 两条进路（长 1、2）同进塑形机式 X(2→1)；Q=2', Q=2, M=3,
                   machines={'Y': dict(inputs={'r': 1}, k=2, d=1), 'X': dict(inputs={'p': 2}, k=1, d=1)},
                   cells=['w1', 'a1', 'b1', 'b2', 'o1'],
                   channels=[('W', 'w1'), ('w1', 'Y:r'), ('Y', 'a1'), ('a1', 'X:p'), ('Y', 'b1'), ('b1', 'b2'),
                             ('b2', 'X:p'), ('X', 'o1'), ('o1', SINK)],
                   premise=['Y'], target='X', lines=['a1', 'b1', 'b2'], yfirst=['a1', 'b1'], xfirst=['o1'])
    C['C4'] = dict(desc='X 时长 2 tick、每批 3 件、两条仓库进路（2·2≥3），存货上限 3；Q=2', Q=2, M=3,
                   machines={'X': dict(inputs={'p': 3}, k=1, d=2)},
                   cells=['a1', 'b1', 'b2', 'o1'],
                   channels=[('W', 'a1'), ('a1', 'X:p'), ('W', 'b1'), ('b1', 'b2'), ('b2', 'X:p'), ('X', 'o1'), ('o1', SINK)],
                   premise=[], target='X', lines=['a1', 'b1', 'b2'], yfirst=['a1', 'b1'], xfirst=[])
    C['C4b'] = dict(C['C4'], M=4, machines={'X': dict(inputs={'p': 4}, k=1, d=2)},
                    desc='X 时长 2 tick、每批 4 件、两条进路（2·2=4 取等），存货上限 4；Q=2')
    C['C5'] = dict(desc='研磨机式 X(2A+1B)：A 来自 Y(1→2) 两条进路，B 来自仓库一条；Q=2', Q=2, M=3,
                   machines={'Y': dict(inputs={'r': 1}, k=2, d=1), 'X': dict(inputs={'A': 2, 'B': 1}, k=1, d=1)},
                   cells=['w1', 'a1', 'b1', 'c1', 'o1'],
                   channels=[('W', 'w1'), ('w1', 'Y:r'), ('Y', 'a1'), ('a1', 'X:A'), ('Y', 'b1'), ('b1', 'X:A'),
                             ('W', 'c1'), ('c1', 'X:B'), ('X', 'o1'), ('o1', SINK)],
                   premise=['Y'], target='X', lines=['a1', 'b1', 'c1'], yfirst=['a1', 'b1', 'c1'], xfirst=['o1'])
    C['C6'] = dict(desc='X 时长 5 tick、每批 5 件、一条两格仓库进路（5·1=5 取等），存货上限 5；Q=2', Q=2, M=5,
                   machines={'X': dict(inputs={'p': 5}, k=1, d=5)},
                   cells=['a1', 'a2', 'o1'],
                   channels=[('W', 'a1'), ('a1', 'a2'), ('a2', 'X:p'), ('X', 'o1'), ('o1', SINK)],
                   premise=[], target='X', lines=['a1', 'a2'], yfirst=['a1'], xfirst=[])
    C['C6b'] = dict(desc='封装机式 X 时长 5 tick、每批 10A+15B，A 两条、B 三条仓库进路（取等），存货上限 15；Q=1', Q=1, M=15,
                    machines={'X': dict(inputs={'A': 10, 'B': 15}, k=1, d=5)},
                    cells=['a1', 'a2', 'b1', 'b2', 'b3', 'o1'],
                    channels=[('W', 'a1'), ('a1', 'X:A'), ('W', 'a2'), ('a2', 'X:A'),
                              ('W', 'b1'), ('b1', 'X:B'), ('W', 'b2'), ('b2', 'X:B'), ('W', 'b3'), ('b3', 'X:B'),
                              ('X', 'o1'), ('o1', SINK)],
                    premise=[], target='X', lines=['a1', 'a2', 'b1', 'b2', 'b3'], yfirst=['a1', 'a2', 'b1', 'b2', 'b3'], xfirst=[])
    C['C7'] = dict(desc='两级：仓库→Z(1→1)→Y(1→2)，Y 一条进 X、一条到下游任意；前提只加在 Z；Q=2', Q=2, M=3,
                   machines={'Z': dict(inputs={'r': 1}, k=1, d=1), 'Y': dict(inputs={'z': 1}, k=2, d=1),
                             'X': dict(inputs={'p': 1}, k=1, d=1)},
                   cells=['w1', 'z1', 'a1', 's1', 'o1'],
                   channels=[('W', 'w1'), ('w1', 'Z:r'), ('Z', 'z1'), ('z1', 'Y:z'), ('Y', 'a1'), ('a1', 'X:p'),
                             ('Y', 's1'), ('s1', SINK), ('X', 'o1'), ('o1', SINK)],
                   premise=['Z'], target='Y', lines=['z1'], yfirst=['z1'], xfirst=['a1', 's1'], also_target=['X'])
    C['C8'] = dict(desc='砂叶粉碎机式 Y(1→3)：一条进 X、一条经每 5 tick 限 1 件的物品准入口、一条直接到下游任意；Q=2', Q=2, M=4,
                   machines={'Y': dict(inputs={'r': 1}, k=3, d=1), 'X': dict(inputs={'p': 1}, k=1, d=1)},
                   cells=['w1', 'a1', 'o1', 'g1', 's1'], gates={'g1': 1},
                   channels=[('W', 'w1'), ('w1', 'Y:r'), ('Y', 'a1'), ('a1', 'X:p'), ('X', 'o1'), ('o1', SINK),
                             ('Y', 'g1'), ('g1', SINK), ('Y', 's1'), ('s1', SINK)],
                   premise=['Y'], target='X', lines=['a1'], yfirst=['a1', 's1'], xfirst=['o1'])
    C['C9'] = dict(desc='荞花粉碎机式 X(1→2) 两条取货通道到下游任意，核末句的首格；Q=2', Q=2, M=3,
                   machines={'X': dict(inputs={'p': 1}, k=2, d=1)},
                   cells=['a1', 'a2', 'o1', 'o2'],
                   channels=[('W', 'a1'), ('a1', 'a2'), ('a2', 'X:p'), ('X', 'o1'), ('o1', SINK), ('X', 'o2'), ('o2', SINK)],
                   premise=[], target='X', lines=['a1', 'a2'], yfirst=['a1'], xfirst=['o1', 'o2'])
    # 对照组：各去掉一个前提
    C['K1'] = dict(desc='对照：Y(1→1) 另有一条到下游任意的取货通道（通道数 2 > 每批 1 件）', Q=2, M=3,
                   machines={'Y': dict(inputs={'r': 1}, k=1, d=1), 'X': dict(inputs={'p': 1}, k=1, d=1)},
                   cells=['w1', 'a1', 's1', 'o1'],
                   channels=[('W', 'w1'), ('w1', 'Y:r'), ('Y', 'a1'), ('a1', 'X:p'), ('Y', 's1'), ('s1', SINK),
                             ('X', 'o1'), ('o1', SINK)],
                   premise=['Y'], target='X', lines=['a1'], yfirst=['a1'], xfirst=['o1'])
    C['K2'] = dict(C['C1'], machines={'Y': dict(inputs={'r': 1}, k=1, d=1, switchable=True),
                                      'X': dict(inputs={'p': 1}, k=1, d=1)},
                   desc='对照：起点 Y 的开关可随时开关（前提只剩缓存格非空）')
    C['K3'] = dict(desc='对照：X(2→1) 只有一条进路（1·1<2）', Q=2, M=3,
                   machines={'X': dict(inputs={'p': 2}, k=1, d=1)},
                   cells=['a1', 'o1'],
                   channels=[('W', 'a1'), ('a1', 'X:p'), ('X', 'o1'), ('o1', SINK)],
                   premise=[], target='X', lines=['a1'], yfirst=['a1'], xfirst=[])
    C['K4'] = dict(desc='对照：X 的进路上有每 5 tick 限 1 件的物品准入口', Q=2, M=3,
                   machines={'X': dict(inputs={'p': 1}, k=1, d=1)},
                   cells=['g1', 'a1', 'o1'], gates={'g1': 1},
                   channels=[('W', 'g1'), ('g1', 'a1'), ('a1', 'X:p'), ('X', 'o1'), ('o1', SINK)],
                   premise=[], target='X', lines=['g1', 'a1'], yfirst=['g1'], xfirst=[])
    C['K5'] = dict(desc='对照：X(1→2) 两条取货通道外加一条到下游任意（3 > 2），核 X 的首格', Q=2, M=3,
                   machines={'X': dict(inputs={'p': 1}, k=2, d=1)},
                   cells=['a1', 'o1', 'o2', 'o3'],
                   channels=[('W', 'a1'), ('a1', 'X:p'), ('X', 'o1'), ('o1', SINK), ('X', 'o2'), ('o2', SINK),
                             ('X', 'o3'), ('o3', SINK)],
                   premise=[], target='X', lines=['a1'], yfirst=['a1'], xfirst=['o1', 'o2', 'o3'])
    return C


def run(name, n_random, seed):
    cfg = configs()[name]
    mdl = Model(cfg)
    rng = random.Random(seed)
    t0 = time.time()
    starts = set(mdl.closure(mdl.empty_state()))
    if n_random < 0:
        # 全部合法起态：每个字段取遍，开关固定开着（可开关的除外），准入口窗口与件数相容
        for L in mdl.all_states():
            starts |= mdl.closure(L)
    for _ in range(max(n_random, 0)):
        starts |= mdl.closure(mdl.random_state(rng))
    succ = {}
    stack = list(starts)
    while stack:
        v = stack.pop()
        if v in succ:
            continue
        s = mdl.step(v)
        succ[v] = s
        for w in s:
            if w not in succ:
                stack.append(w)
    t1 = time.time()

    def prem(L):
        for m in cfg['premise']:
            mm = mdl.mach[m]
            if L[mm['cache']] == 0:
                return False
            if not mm['switchable'] and not L[mm['on']]:
                return False
        return True

    P = {v for v in succ if prem(mdl.dec(v))}
    psucc = {v: [w for w in succ[v] if w in P] for v in P}
    cyc = tarjan(sorted(P), psucc)
    t2 = time.time()

    targets = [cfg['target']] + cfg.get('also_target', [])
    viol = {'X缓存格空': 0, '进路格空': 0, '起点首格空': 0, 'X首格空': 0}
    example = {}
    for v in cyc:
        L = mdl.dec(v)
        bad = []
        if any(L[mdl.mach[t]['cache']] == 0 for t in targets):
            bad.append('X缓存格空')
        if any(L[mdl.cell[c]] == 0 for c in cfg['lines']):
            bad.append('进路格空')
        if any(L[mdl.cell[c]] == 0 for c in cfg['yfirst']):
            bad.append('起点首格空')
        if any(L[mdl.cell[c]] == 0 for c in cfg['xfirst']):
            bad.append('X首格空')
        for b in bad:
            viol[b] += 1
            if b not in example:
                example[b] = v
    # 给一个违反的环作见证：从该状态出发，在前提子图的同一分量里走回自己
    witness = None
    if example:
        v0 = next(iter(example.values()))
        prev = {v0: None}
        q = [v0]
        found = None
        while q and found is None:
            nq = []
            for u in q:
                for w in psucc[u]:
                    if w not in cyc:
                        continue
                    if w == v0:
                        found = u
                        break
                    if w not in prev:
                        prev[w] = u
                        nq.append(w)
                if found is not None:
                    break
            q = nq
        path = []
        u = found
        while u is not None:
            path.append(u)
            u = prev[u]
        path.reverse()
        witness = [dict(zip(mdl.names, mdl.dec(u))) for u in path]
    res = dict(组=name, 说明=cfg['desc'], Q=cfg['Q'], 存货上限=cfg['M'], 随机起态=(n_random if n_random >= 0 else '全部合法起态'), 种子=seed,
               状态数=len(succ), 前提成立的状态=len(P), 前提子图中在环上的状态=len(cyc),
               违反=viol, 用时秒=round(t2 - t0, 1),
               见证环长=(len(witness) if witness else 0), 见证环=witness[:40] if witness else None)
    return res


if __name__ == '__main__':
    name = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 9001
    print(json.dumps(run(name, n, seed), ensure_ascii=False, indent=1))
