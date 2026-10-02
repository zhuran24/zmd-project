#!/usr/bin/env python3
"""复核109S2B 自写整厂步进引擎（不导入推导席或 sim2 的任何代码）。

按快照规则第23—33行 + 临时规则第1、2、4条（含主会话按轴收货读法）实现：
- 每步：结束到时制造 -> 缓存整批进取货格 -> 连续带内部前移 -> 按(层数, 最早送货通道接通)判定元件
  -> 按最早送货通道接通判定非运输单位 -> 开始能开始的制造。
- 元件：一段连续传送带，或桥接器的一轴。桥接器同轴相邻时两向都有通道（真实逆向通道保留）。
- 层数：在元件图(含逆向边)上枚举不重复经过元件、终止于直接送非运输单位的元件的走法；断言唯一。
- 收货（临时规则第1条）：某元件有能送往接收方 R 的物品时，R 的全部未判定元件上游一起判定，
  R 按轮询逐条尝试；被带动的成员若有别处可送，记为异常。
- 不移回刚离开的单位：按物理单位记（桥两轴共用一个物理单位）。
- 离线：全部单位按任意次序重建，通道接通时刻=两端较晚的建造时刻（同刻随机），层数重算；
  物品位置、货龄、来源记录、制造进度保留；轮询成功记录 keep/clear 两种读法。
mode='bridge'：进路含桥轴、相邻桥串、与别路交叉；mode='belt'：同长纯带对照。
"""
import random

DWELL = 8
CAP = 50

RECIPES = {
    'OS': ({'蓝铁矿': 1}, ('蓝铁块', 1), 1),
    'IC': ({'蓝铁块': 1}, ('蓝铁粉末', 1), 1),
    'SC': ({'源矿': 1}, ('源石粉末', 1), 1),
    'B': ({'蓝铁粉末': 2, '砂叶粉末': 1}, ('致密蓝铁粉末', 1), 1),
    'O': ({'源石粉末': 2, '砂叶粉末': 1}, ('致密源石粉末', 1), 1),
    'Q': ({'荞花粉末': 2, '砂叶粉末': 1}, ('细磨荞花粉末', 1), 1),
    'R': ({'致密蓝铁粉末': 1}, ('钢块', 1), 1),
    'P': ({'钢块': 1}, ('钢制零件', 1), 1),
    'H': ({'钢块': 2}, ('钢质瓶', 1), 1),
    'E': ({'钢制零件': 10, '致密源石粉末': 15}, ('高容谷地电池', 1), 5),
    'F': ({'钢质瓶': 10, '细磨荞花粉末': 10}, ('精选荞愈胶囊', 1), 5),
    'Cs': ({'砂叶': 1}, ('砂叶种子', 2), 1),
    'As': ({'砂叶种子': 1}, ('砂叶', 1), 1),
    'Ks': ({'砂叶': 1}, ('砂叶粉末', 3), 1),
    'Cq': ({'荞花': 1}, ('荞花种子', 2), 1),
    'Aq': ({'荞花种子': 1}, ('荞花', 1), 1),
    'Kq': ({'荞花': 1}, ('荞花粉末', 2), 1),
}
FINISHED = ('高容谷地电池', '精选荞愈胶囊')
AREA = {'OS': 9, 'IC': 9, 'SC': 9, 'B': 24, 'O': 24, 'Q': 24, 'R': 9, 'P': 9, 'H': 9,
        'E': 24, 'F': 24, 'Cs': 25, 'As': 25, 'Ks': 9, 'Cq': 25, 'Aq': 25, 'Kq': 9}

SAND_GROUPS = [['B1', 'B2', 'O1'], ['O2', 'O3'], ['B3', 'B4', 'O4'], ['O5', 'O6'],
               ['B5', 'B6', 'O7'], ['O8', 'O9'], ['B7', 'B8', 'B9'], ['B10', 'Q1', 'Q2'],
               ['B11', 'B12', 'B13'], ['B14', 'Q3', 'Q4'], ['B15', 'B16', 'Q5'], ['B17'], ['Q6']]


def wiring():
    """返回 machines {id: kind}, paths [(src, dst, item)]。src/dst 可为 'CORE'、'PORTk'。"""
    M = {}
    paths = []
    for i in range(1, 35):
        M[f'OS{i}'] = 'OS'; M[f'IC{i}'] = 'IC'
        paths.append((f'PORT{i}', f'OS{i}', '蓝铁矿'))
        paths.append((f'OS{i}', f'IC{i}', '蓝铁块'))
    for i in range(1, 19):
        M[f'SC{i}'] = 'SC'
        src = 'CORE' if i <= 6 else f'PORT{34 + i - 6}'
        paths.append((src, f'SC{i}', '源矿'))
    for i in range(1, 18):
        M[f'B{i}'] = 'B'; M[f'R{i}'] = 'R'
        paths.append((f'IC{2*i-1}', f'B{i}', '蓝铁粉末'))
        paths.append((f'IC{2*i}', f'B{i}', '蓝铁粉末'))
        paths.append((f'B{i}', f'R{i}', '致密蓝铁粉末'))
    for i in range(1, 10):
        M[f'O{i}'] = 'O'
        paths.append((f'SC{2*i-1}', f'O{i}', '源石粉末'))
        paths.append((f'SC{2*i}', f'O{i}', '源石粉末'))
    for i in range(1, 7):
        M[f'P{i}'] = 'P'; M[f'H{i}'] = 'H'; M[f'Q{i}'] = 'Q'
        paths.append((f'R{i}', f'P{i}', '钢块'))
    hmap = {7: 1, 8: 1, 9: 2, 10: 2, 11: 3, 12: 3, 13: 4, 14: 4, 15: 5, 16: 5, 17: 6}
    for r, h in hmap.items():
        paths.append((f'R{r}', f'H{h}', '钢块'))
    for i in range(1, 4):
        M[f'E{i}'] = 'E'
        for p in (2 * i - 1, 2 * i):
            paths.append((f'P{p}', f'E{i}', '钢制零件'))
        for o in (3 * i - 2, 3 * i - 1, 3 * i):
            paths.append((f'O{o}', f'E{i}', '致密源石粉末'))
    finl = {1: ([1, 2], [1, 2]), 2: ([3, 4], [3, 4]), 3: ([5], [5]), 4: ([6], [6])}
    for f, (hs, qs) in finl.items():
        M[f'F{f}'] = 'F'
        for h in hs:
            paths.append((f'H{h}', f'F{f}', '钢质瓶'))
        for q in qs:
            paths.append((f'Q{q}', f'F{f}', '细磨荞花粉末'))
    for i in range(1, 4):
        paths.append((f'E{i}', 'CORE', '高容谷地电池'))
    for f in range(1, 5):
        paths.append((f'F{f}', 'CORE', '精选荞愈胶囊'))
    for s in range(1, 14):
        C, A, G, K = f'Cs{s}', f'As{s}', f'Gs{s}', f'S{s}'
        M[C] = 'Cs'; M[A] = 'As'; M[G] = 'As'; M[K] = 'Ks'
        paths += [(C, A, '砂叶种子'), (C, G, '砂叶种子'), (A, C, '砂叶'), (G, K, '砂叶')]
        for d in SAND_GROUPS[s - 1]:
            paths.append((K, d, '砂叶粉末'))
    for s in range(1, 7):
        C, A, G, K = f'Cq{s}', f'Aq{s}', f'Gq{s}', f'K{s}'
        M[C] = 'Cq'; M[A] = 'Aq'; M[G] = 'Aq'; M[K] = 'Kq'
        paths += [(C, A, '荞花种子'), (C, G, '荞花种子'), (A, C, '荞花'), (G, K, '荞花')]
        for _ in range(2 if s <= 5 else 1):
            paths.append((K, f'Q{s}', '荞花粉末'))
    return M, paths


class Item:
    __slots__ = ('name', 'entered', 'last')

    def __init__(self, name, entered, last):
        self.name = name; self.entered = entered; self.last = last


class Factory:
    def __init__(self, seed, mode, maxlen, pbridge=0.6, pcross=0.8, keep=True,
                 core_per_side=False, layout=None, layer_mode='axis'):
        self.layer_mode = layer_mode
        self.rng = random.Random(seed)
        self.mode = mode
        self.keep = keep
        self.core_per_side = core_per_side
        self.M, self.P = wiring()
        rng = self.rng
        n = len(self.P)
        # ---- 进路格的形状（bridge/belt）与长度；layout 可由外部给定以便两个模式共用 ----
        if layout is None:
            lengths = [rng.randint(1, maxlen) for _ in range(n)]
            h6 = [k for k, p in enumerate(self.P) if p[0] == 'H6' and p[1] == 'F4'][0]
            q6 = [k for k, p in enumerate(self.P) if p[0] == 'Q6' and p[1] == 'F4'][0]
            lengths[q6] = lengths[h6]
            kinds = [[('bridge' if rng.random() < pbridge else 'belt') for _ in range(L)] for L in lengths]
            # 交叉：把不同进路的桥格两两配成同一个物理桥接器（另一轴）
            bcells = [(p, i) for p in range(n) for i in range(lengths[p]) if kinds[p][i] == 'bridge']
            rng.shuffle(bcells)
            phys = {}
            nb = 0
            pool = []
            for c in bcells:
                partner = None
                if rng.random() < pcross:
                    for j, d in enumerate(pool):
                        if d[0] != c[0]:
                            partner = pool.pop(j); break
                if partner is not None:
                    phys[c] = ('br', phys[partner][1]);
                else:
                    phys[c] = ('br', nb); nb += 1
                    pool.append(c)
            layout = {'lengths': lengths, 'kinds': kinds, 'phys': phys}
        self.layout = layout
        self.lengths = layout['lengths']
        if mode == 'bridge':
            self.kinds = layout['kinds']
            self.phys = {}
            for p in range(n):
                for i in range(self.lengths[p]):
                    self.phys[(p, i)] = layout['phys'][(p, i)] if self.kinds[p][i] == 'bridge' else ('belt', p, i)
        else:
            self.kinds = [['belt'] * L for L in self.lengths]
            self.phys = {(p, i): ('belt', p, i) for p in range(n) for i in range(self.lengths[p])}
        self.cells = {(p, i): None for p in range(n) for i in range(self.lengths[p])}
        # ---- 元件 ----
        self.elems = []   # (p, a, b, kind)
        self.elem_of = {}
        for p in range(n):
            i = 0
            L = self.lengths[p]
            while i < L:
                if self.kinds[p][i] == 'bridge':
                    self.elem_of[(p, i)] = len(self.elems)
                    self.elems.append((p, i, i, 'bridge')); i += 1
                else:
                    j = i
                    while j + 1 < L and self.kinds[p][j + 1] == 'belt':
                        j += 1
                    for k in range(i, j + 1):
                        self.elem_of[(p, k)] = len(self.elems)
                    self.elems.append((p, i, j, 'belt')); i = j + 1
        self.compute_layers()
        # ---- 机器状态 ----
        self.mach = {}
        for m, k in self.M.items():
            ins, (oi, oq), dur = RECIPES[k]
            fin = oi in FINISHED
            self.mach[m] = {
                'kind': k, 'in': {it: CAP for it in ins},
                'out_item': oi, 'out': 0 if fin else CAP,
                'cache': None if fin else 'done', 'due': None, 'fin': fin,
            }
        self.inpaths = {}
        self.outpaths = {}
        for p, (s, d, it) in enumerate(self.P):
            self.inpaths.setdefault(d, []).append(p)
            self.outpaths.setdefault(s, []).append(p)
        # 进路初态：非成品路满载成熟、来源为本路前一物理单位；成品路空
        for p, (s, d, it) in enumerate(self.P):
            if it in FINISHED:
                continue
            for i in range(self.lengths[p]):
                last = s if i == 0 else self.phys[(p, i - 1)]
                self.cells[(p, i)] = Item(it, -DWELL, last)
        self.accept = {f: True for f in FINISHED}
        self.budget = {f: None for f in FINISHED}   # 仓库只余少量库位时每步可收件数
        self.rejects = {}
        self.t = 0
        self.recv_last = {}     # 接收方 -> 上次成功的通道
        self.send_last = {}     # 非运输单位 -> {通道: 上次成功时刻}
        self.delivered = {f: 0 for f in FINISHED}
        self.oresent = [0] * n
        self.anom = {'reverse_success': 0, 'reverse_trigger': 0, 'cross_member': 0,
                     'reverse_checks': 0, 'layer_nonunique': 0}
        self.rebuild()

    # ---------------- 层数 ----------------
    def compute_layers(self):
        E = self.elems
        targets = []   # 元件目标：('E', idx) 或 ('U', unit)
        for idx, (p, a, b, k) in enumerate(E):
            t = []
            if b + 1 < self.lengths[p]:
                t.append(('E', self.elem_of[(p, b + 1)]))
            else:
                t.append(('U', self.P[p][1]))
            if k == 'bridge' and a > 0 and self.kinds[p][a - 1] == 'bridge':
                t.append(('E', self.elem_of[(p, a - 1)]))   # 同轴相邻桥的逆向通道
            targets.append(t)
        self.etargets = targets
        layers = []
        for idx in range(len(E)):
            vals = set()
            stack = [(idx, frozenset([idx]), 1)]
            while stack:
                x, seen, d = stack.pop()
                ts = targets[x]
                if any(tt[0] == 'U' for tt in ts):
                    vals.add(d)
                for tt in ts:
                    if tt[0] == 'E' and tt[1] not in seen:
                        stack.append((tt[1], seen | {tt[1]}, d + 1))
            if len(vals) != 1:
                self.anom['layer_nonunique'] += 1
            layers.append(min(vals))
            # 交叉检验：等于到路尾的前向元件数
            p, a, b, k = E[idx]
            fwd = len({self.elem_of[(p, i)] for i in range(a, self.lengths[p])})
            assert min(vals) == fwd, (idx, vals, fwd)
        self.layer = layers
        if self.layer_mode == 'cross':
            # 字面扩大读法：送往的桥接器“单位里”另一轴的元件也可用来数层；对抗地取最短（Bellman-Ford）
            other = {}
            for (p, i), ph in self.phys.items():
                if ph[0] == 'br':
                    other.setdefault(ph, []).append(self.elem_of[(p, i)])
            succ = []
            for idx, (p, a, b, k) in enumerate(E):
                if b + 1 < self.lengths[p]:
                    nx = self.elem_of[(p, b + 1)]
                    ss = [nx]
                    if self.kinds[p][b + 1] == 'bridge':
                        ss += [o for o in other[self.phys[(p, b + 1)]] if o != nx]
                    succ.append(ss)
                else:
                    succ.append(None)
            lay = [1 if succ[i] is None else 10 ** 9 for i in range(len(E))]
            ch = True
            while ch:
                ch = False
                for i in range(len(E)):
                    if succ[i] is not None:
                        v = 1 + min(lay[j] for j in succ[i])
                        if v < lay[i]:
                            lay[i] = v; ch = True
            self.layer = lay
        elif self.layer_mode == 'rev_undet':
            lay = list(layers)
            for idx, (p, a, b, k) in enumerate(E):
                if k == 'bridge' and ((a > 0 and self.kinds[p][a - 1] == 'bridge') or
                                      (b + 1 < self.lengths[p] and self.kinds[p][b + 1] == 'bridge')):
                    lay[idx] = 1000 - lay[idx]   # 层数不定时的一种取法：上游先判
            self.layer = lay

    # ---------------- 离线重建 ----------------
    def rebuild(self, shared=None):
        """shared=(bt, conn)：对照模式下沿用另一模式在机器侧的建造时刻与通道接通时刻。"""
        rng = self.rng
        units = set(self.phys.values()) | set(self.M) | {'CORE'} | {f'PORT{i}' for i in range(1, 47)}
        order = sorted(units, key=repr)   # 先排定再洗牌，使结果与 PYTHONHASHSEED 无关
        rng.shuffle(order)
        self.bt = {u: k for k, u in enumerate(order)}
        # 通道接通时刻
        self.conn = {}
        for p, (s, d, it) in enumerate(self.P):
            L = self.lengths[p]
            def ct(u, v):
                return (max(self.bt[u], self.bt[v]), rng.random())
            self.conn[('h', p)] = ct(s, self.phys[(p, 0)])
            self.conn[('t', p)] = ct(self.phys[(p, L - 1)], d)
            for i in range(L - 1):
                self.conn[('f', p, i)] = ct(self.phys[(p, i)], self.phys[(p, i + 1)])
                if self.kinds[p][i] == 'bridge' and self.kinds[p][i + 1] == 'bridge':
                    self.conn[('r', p, i + 1)] = ct(self.phys[(p, i + 1)], self.phys[(p, i)])
        if shared is not None:
            for key, v in shared.items():
                if key in self.conn:
                    self.conn[key] = v
        # 元件判定次序
        def esend(idx):
            p, a, b, k = self.elems[idx]
            cs = [self.conn[('t', p)] if b + 1 == self.lengths[p] else self.conn[('f', p, b)]]
            if ('r', p, a) in self.conn and k == 'bridge':
                cs.append(self.conn[('r', p, a)])
            return min(cs)
        self.eorder = sorted(range(len(self.elems)), key=lambda e: (self.layer[e], esend(e)))
        nt = [u for u in self.outpaths]
        self.uorder = sorted(nt, key=lambda u: min(self.conn[('h', p)] for p in self.outpaths[u]))
        if not self.keep:
            self.recv_last = {}
            self.send_last = {}

    # ---------------- 基本动作 ----------------
    def mature(self, it):
        return it is not None and self.t - it.entered >= DWELL

    def settle(self, e):
        p, a, b, k = self.elems[e]
        if k != 'belt':
            return
        for i in range(b - 1, a - 1, -1):
            it = self.cells[(p, i)]
            if self.mature(it) and self.cells[(p, i + 1)] is None:
                self.cells[(p, i + 1)] = it
                it.entered = self.t
                it.last = self.phys[(p, i)]
                self.cells[(p, i)] = None

    def flush(self, m):
        st = self.mach[m]
        if st['cache'] == 'done':
            q = RECIPES[st['kind']][1][1]
            if st['out'] + q <= CAP:
                st['out'] += q
                st['cache'] = None

    def try_start(self, m):
        st = self.mach[m]
        if st['cache'] is not None:
            return
        ins, _, dur = RECIPES[st['kind']]
        if all(st['in'][i] >= q for i, q in ins.items()):
            for i, q in ins.items():
                st['in'][i] -= q
            st['cache'] = 'wip'
            st['due'] = self.t + DWELL * dur

    # 一个元件的“送货侧”：返回 (发送格, [(接收方, 通道)])
    def elem_targets(self, e):
        p, a, b, k = self.elems[e]
        out = []
        if b + 1 < self.lengths[p]:
            out.append((('C', p, b + 1), ('f', p, b)))
        else:
            out.append((('U', self.P[p][1]), ('t', p)))
        if k == 'bridge' and a > 0 and self.kinds[p][a - 1] == 'bridge':
            out.append((('C', p, a - 1), ('r', p, a)))
        return (p, b), out

    def recv_phys(self, R):
        return self.phys[(R[1], R[2])] if R[0] == 'C' else R[1]

    def upstream_channels(self, R):
        """接收方 R 的全部元件上游通道：[(通道, 发送元件, 发送格)]。"""
        if R[0] == 'C':
            p, i = R[1], R[2]
            res = []
            if i > 0:
                res.append((('f', p, i - 1), self.elem_of[(p, i - 1)], (p, i - 1)))
            if (('r', p, i + 1) in self.conn):
                res.append((('r', p, i + 1), self.elem_of[(p, i + 1)], (p, i + 1)))
            return res
        u = R[1]
        res = []
        for p in self.inpaths.get(u, []):
            L = self.lengths[p]
            res.append((('t', p), self.elem_of[(p, L - 1)], (p, L - 1)))
        return res

    def can_take(self, R, it):
        if R[0] == 'C':
            return self.cells[(R[1], R[2])] is None
        u = R[1]
        if u == 'CORE':
            b = self.budget.get(it.name)
            return self.accept.get(it.name, False) and (b is None or b > 0)
        st = self.mach[u]
        return it.name in st['in'] and st['in'][it.name] < CAP

    def put(self, R, it, from_phys):
        it.entered = self.t
        it.last = from_phys
        if R[0] == 'C':
            self.cells[(R[1], R[2])] = it
        else:
            u = R[1]
            if u == 'CORE':
                self.delivered[it.name] += 1
                if self.budget.get(it.name) is not None:
                    self.budget[it.name] -= 1
            else:
                self.mach[u]['in'][it.name] += 1

    def judge_element(self, e, judged):
        judged.add(e)
        cell, tgts = self.elem_targets(e)
        it = self.cells[cell]
        if not self.mature(it):
            return
        for R, ch in tgts:
            if ch[0] == 'r':
                self.anom['reverse_checks'] += 1
            if self.recv_phys(R) == it.last:
                continue   # 不能移回刚离开的单位：不算“往它送货”
            if ch[0] == 'r':
                self.anom['reverse_trigger'] += 1
            self.fire_group(R, e, judged)
            if self.cells[cell] is not it:
                return

    def fire_group(self, R, e, judged):
        ups = self.upstream_channels(R)
        members = []
        for ch, el, cell in ups:
            if el == e or el not in judged:
                members.append((ch, el, cell))
                judged.add(el)
        # 被带动的成员若有别处能送的成熟货，记异常（本接法不应出现）
        for ch, el, cell in members:
            if el == e:
                continue
            it = self.cells[cell]
            if self.mature(it):
                _, tg = self.elem_targets(el)
                for R2, ch2 in tg:
                    if R2 != R and self.recv_phys(R2) != it.last:
                        self.anom['cross_member'] += 1
        # 按轮询：接通先后循环，从上次成功的下一条开始
        allch = sorted([c for c, _, _ in ups], key=lambda c: self.conn[c])
        last = self.recv_last.get(R)
        if last in allch:
            k = allch.index(last) + 1
            allch = allch[k:] + allch[:k]
        mem = {c: (el, cell) for c, el, cell in members}
        for c in allch:
            if c not in mem:
                continue
            el, cell = mem[c]
            it = self.cells[cell]
            if not self.mature(it) or self.recv_phys(R) == it.last:
                continue
            if not self.can_take(R, it):
                if c[0] == 't':
                    self.rejects[c[1]] = self.rejects.get(c[1], 0) + 1
                continue
            if True:
                if c[0] == 'r':
                    self.anom['reverse_success'] += 1
                self.cells[cell] = None
                self.put(R, it, self.phys[cell])
                self.recv_last[R] = c
                self.settle(el)

    def judge_unit(self, u):
        chans = self.outpaths[u]
        last = self.send_last.setdefault(u, {})
        # 非运输单位取货侧：从未成功的按接通先后在前，其余按上次成功最早的先试
        never = sorted([p for p in chans if p not in last], key=lambda p: self.conn[('h', p)])
        had = sorted([p for p in chans if p in last], key=lambda p: (last[p], self.conn[('h', p)]))
        order = never + had
        if u == 'CORE' or u.startswith('PORT'):
            sends_left = 2 if (u == 'CORE' and self.core_per_side) else 1
            for p in order:
                if sends_left == 0:
                    break
                if self.cells[(p, 0)] is None:
                    self.cells[(p, 0)] = Item(self.P[p][2], self.t, u)
                    last[p] = self.t
                    self.oresent[p] += 1
                    sends_left -= 1
            return
        st = self.mach[u]
        if st['out'] <= 0:
            return
        for p in order:
            if self.cells[(p, 0)] is None:
                self.cells[(p, 0)] = Item(st['out_item'], self.t, u)
                st['out'] -= 1
                last[p] = self.t
                self.flush(u)
                return

    def step(self):
        for m, st in self.mach.items():
            if st['cache'] == 'wip' and st['due'] == self.t:
                st['cache'] = 'done'
        for m in self.mach:
            self.flush(m)
        for e, el in enumerate(self.elems):
            if el[3] == 'belt':
                self.settle(e)
        judged = set()
        for e in self.eorder:
            if e not in judged:
                self.judge_element(e, judged)
        for u in self.uorder:
            self.judge_unit(u)
        for m in self.mach:
            self.try_start(m)
        self.t += 1

    # ---------------- 比较与哈希 ----------------
    def snapshot(self, rel_last=True):
        """与模式无关的逐格快照：来源记录换成“本路前一格/起点/其他”。"""
        cells = []
        for p in range(len(self.P)):
            for i in range(self.lengths[p]):
                it = self.cells[(p, i)]
                if it is None:
                    cells.append(None); continue
                src = self.P[p][0]
                if i == 0:
                    lr = 'src' if it.last == src else repr(it.last)
                else:
                    lr = 'prev' if it.last == self.phys[(p, i - 1)] else repr(it.last)
                cells.append((it.name, it.entered, lr))
        mach = tuple((m, tuple(sorted(st['in'].items())), st['out'], st['cache'], st['due'])
                     for m, st in sorted(self.mach.items()))
        return (tuple(cells), mach, tuple(sorted(self.delivered.items())))

    def state_key(self):
        t = self.t
        cells = []
        for p in range(len(self.P)):
            for i in range(self.lengths[p]):
                it = self.cells[(p, i)]
                cells.append(None if it is None else (min(t - it.entered, DWELL), repr(it.last)))
        mach = tuple((tuple(st['in'].values()), st['out'], st['cache'],
                      None if st['due'] is None else st['due'] - t) for st in self.mach.values())
        rl = tuple(sorted((repr(k), repr(v)) for k, v in self.recv_last.items()))
        sl = tuple(sorted((u, tuple(sorted(d, key=lambda p: (d[p], self.conn[('h', p)]))))
                          for u, d in self.send_last.items()))
        return hash((tuple(cells), mach, rl, sl, tuple(self.accept.values())))
