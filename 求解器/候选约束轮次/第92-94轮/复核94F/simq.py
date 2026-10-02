#!/usr/bin/env python3
"""复核 94F 编码丁：与编码丙（simp.py）分开写的第二套步进模拟器，用于关键数字互核。

不共享代码。数据结构不同：全部单位编成整数下标，运输格是「格对象」的平铺数组，一段传送带是一串格下标；
轮询状态按收货方存「上次成功通道的接通名次」，非运输送货侧存每条通道「上次成功的步」（从未成功 = -1，同值按名次）。
读法开关同编码丙：settle ∈ {'eager','judge'}，bridge_group ∈ {'axis','unit'}。
"""

T = 8


class Q:
    def __init__(self, desc, settle='eager', bridge_group='axis'):
        U = desc['units']
        self.names = sorted(U)
        idx = {u: i for i, u in enumerate(self.names)}
        self.idx = idx
        self.ty = [U[u]['type'] for u in self.names]
        self.d = [U[u] for u in self.names]
        self.settle_mode, self.bg = settle, bridge_group
        chans = sorted(desc['chans'], key=lambda c: c[2])
        self.cs = [(idx[a], idx[b], r) for a, b, r in chans]
        n = len(self.names)
        self.out = [[] for _ in range(n)]
        self.inn = [[] for _ in range(n)]
        for ci, (a, b, r) in enumerate(self.cs):
            self.out[a].append(ci)
            self.inn[b].append(ci)
        self.is_el = [t in ('seg', 'gate', 'bax', 'mer') for t in self.ty]
        # 运输格：每个元件若干格，cells[u] = 格下标表（入口在前）
        self.cells = [[] for _ in range(n)]
        self.cv = []      # 格内容：None 或 [kind, entered, prev_phys]
        for u in range(n):
            if self.is_el[u]:
                L = self.d[u].get('len', 1) if self.ty[u] == 'seg' else 1
                for _ in range(L):
                    self.cells[u].append(len(self.cv))
                    self.cv.append(None)
        # 层数
        self.lay = [0] * n

        def lay(u, depth=0):
            if self.lay[u]:
                return self.lay[u]
            assert depth < 10000
            nx = [self.cs[c][1] for c in self.out[u] if self.is_el[self.cs[c][1]] and self.out[self.cs[c][1]]]
            self.lay[u] = lay(nx[0], depth + 1) + 1 if nx else 1
            return self.lay[u]
        for u in range(n):
            if self.is_el[u]:
                lay(u)
        # 收货方
        self.rk = []
        for u in range(n):
            if self.ty[u] == 'bax' and self.bg == 'unit':
                self.rk.append(('b', self.d[u]['bridge']))
            else:
                self.rk.append(('u', u))
        self.rin = {}
        for ci, (a, b, r) in enumerate(self.cs):
            self.rin.setdefault(self.rk[b], []).append(ci)
        for k in self.rin:
            self.rin[k].sort(key=lambda c: self.cs[c][2])
        self.lastrank = {}
        # 制造单位、准入口、源、汇
        self.slots = {}
        self.tk = {}
        self.cache = {}
        self.left = {}
        self.on = {}
        self.gw = {}
        self.lastok = {}  # 非运输送货侧：通道 -> 上次成功的步
        self.kind_of = {}
        self.stock = {}
        self.recv = {}
        for u in range(n):
            t = self.ty[u]
            if t == 'mach':
                self.slots[u] = []        # 有物品的格：[kind, count]，空格不存
                self.tk[u] = None
                self.cache[u] = None
                self.left[u] = 0
                self.on[u] = self.d[u].get('on', True)
            if t == 'gate':
                self.gw[u] = None
            if t == 'src':
                ks = self.d[u]['kinds']
                for j, ci in enumerate(self.out[u]):
                    self.kind_of[ci] = ks[j]
                self.stock[u] = dict(self.d[u].get('stock', {}))
            if t == 'sink':
                self.recv[u] = 0
        for ci in range(len(self.cs)):
            if self.ty[self.cs[ci][0]] in ('src', 'mach'):
                self.lastok[ci] = -1
        init = desc.get('init', {})
        for u, lst in init.get('cell', {}).items():
            for j, x in enumerate(lst):
                self.cv[self.cells[idx[u]][j]] = None if x is None else [x[0], x[1], None]
        for u, lst in init.get('slot', {}).items():
            self.slots[idx[u]] = [[k, c] for k, c in lst if k is not None and c > 0]
        for u, x in init.get('take', {}).items():
            self.tk[idx[u]] = [x[0], x[1]] if x[1] > 0 else None
        for u, x in init.get('cache', {}).items():
            self.cache[idx[u]] = tuple(x) if x else None
        for u, x in init.get('run', {}).items():
            if x:
                self.left[idx[u]] = x[1]
        for u, x in init.get('gwin', {}).items():
            self.gw[idx[u]] = list(x) if x else None
        self.now = 0

    def physid(self, u):
        return ('B', self.d[u]['bridge']) if self.ty[u] == 'bax' else ('N', u)

    # ---- 移动 ----
    def creep(self, u):
        cl = self.cells[u]
        for j in range(len(cl) - 2, -1, -1):
            a, b = cl[j], cl[j + 1]
            x = self.cv[a]
            if x is not None and self.cv[b] is None and self.now - x[1] >= T:
                self.cv[b] = [x[0], self.now, ('C', a)]
                self.cv[a] = None

    def ready(self, u):
        x = self.cv[self.cells[u][-1]]
        return x if (x is not None and self.now - x[1] >= T) else None

    def can_take(self, v, kind, prev):
        t = self.ty[v]
        if prev is not None:
            entry = ('C', self.cells[v][0]) if t == 'seg' else self.physid(v)
            if prev == entry:
                return False
        if t in ('seg', 'bax', 'mer'):
            return self.cv[self.cells[v][0]] is None
        if t == 'gate':
            if self.cv[self.cells[v][0]] is not None:
                return False
            al = self.d[v].get('allow')
            if al is not None and al != kind:
                return False
            q = self.d[v].get('q5')
            if q is not None and self.gw[v] is not None:
                ws, c = self.gw[v]
                if self.now < ws + 5 * T and c >= q:
                    return False
            return True
        if t == 'mach':
            same = [s for s in self.slots[v] if s[0] == kind]
            if same:
                return same[0][1] < 50
            return len(self.slots[v]) < self.d[v]['nslots']
        if t == 'sink':
            sp = self.d[v].get('open')
            if sp is None or sp[0] == 'always':
                return True
            if sp[0] == 'period':
                return self.now % sp[1] < sp[2]
            if sp[0] == 'window':
                return not (sp[1] <= self.now < sp[1] + sp[2])
            return False
        return False

    def give(self, v, kind, prev):
        t = self.ty[v]
        if t in ('seg', 'bax', 'mer', 'gate'):
            self.cv[self.cells[v][0]] = [kind, self.now, prev]
            if t == 'gate' and self.d[v].get('q5') is not None:
                g = self.gw[v]
                if g is None or self.now >= g[0] + 5 * T:
                    self.gw[v] = [self.now, 1]
                else:
                    g[1] += 1
        elif t == 'mach':
            for s in self.slots[v]:
                if s[0] == kind:
                    s[1] += 1
                    return
            self.slots[v].append([kind, 1])
        elif t == 'sink':
            self.recv[v] += 1

    def try_flush(self, m):
        c = self.cache[m]
        if c is None or self.left[m] > 0:
            return
        t = self.tk[m]
        if t is None:
            self.tk[m] = [c[0], c[1]]
            self.cache[m] = None
        elif t[0] == c[0] and t[1] + c[1] <= 50:
            t[1] += c[1]
            self.cache[m] = None

    def nt_order(self, v):
        lst = self.out[v]
        if len(lst) <= 1:
            return lst
        grades = {}
        for ci in lst:
            tgt = self.cs[ci][1]
            key = ('m', ci) if self.ty[tgt] == 'mer' else ('r',)
            grades.setdefault(key, []).append(ci)
        gl = []
        for g in grades.values():
            lay = max(self.lay[self.cs[ci][1]] if self.is_el[self.cs[ci][1]] else 1 for ci in g)
            gl.append((lay, min(self.cs[ci][2] for ci in g), g))
        gl.sort(key=lambda x: (x[0], x[1]))
        res = []
        for _, _, g in gl:
            res += sorted(g, key=lambda ci: (self.lastok[ci], self.cs[ci][2]))
        return res

    def step(self, eorder, norder):
        n = len(self.names)
        for m in self.slots:
            if self.left[m] > 0 and self.on[m]:
                self.left[m] -= 1
            self.try_flush(m)
        if self.settle_mode == 'eager':
            for u in range(n):
                if self.ty[u] == 'seg':
                    self.creep(u)
        done = [False] * n
        for name in eorder:
            u = self.idx[name]
            if done[u]:
                continue
            if not self.out[u]:
                done[u] = True
                if self.settle_mode == 'judge' and self.ty[u] == 'seg':
                    self.creep(u)
                continue
            tgt0 = self.cs[self.out[u][0]][1]
            key = self.rk[tgt0]
            arr = self.rin[key]
            grp = sorted({self.cs[ci][0] for ci in arr if self.is_el[self.cs[ci][0]]})
            for g in grp:
                done[g] = True
            lr = self.lastrank.get(key)
            if lr is None:
                st = 1 if (self.ty[tgt0] == 'mer' and len(arr) > 1) else 0
            else:
                pos = [self.cs[ci][2] for ci in arr].index(lr)
                st = (pos + 1) % len(arr)
            for ci in arr[st:] + arr[:st]:
                a, b, r = self.cs[ci]
                if not self.is_el[a]:
                    continue
                x = self.ready(a)
                if x is None or not self.can_take(b, x[0], x[2]):
                    continue
                self.cv[self.cells[a][-1]] = None
                if self.settle_mode == 'eager' and self.ty[a] == 'seg':
                    self.creep(a)
                prev = ('C', self.cells[a][-1]) if self.ty[a] == 'seg' else self.physid(a)
                self.give(b, x[0], prev)
                self.lastrank[key] = r
            if self.settle_mode == 'judge':
                for g in grp:
                    if self.ty[g] == 'seg':
                        self.creep(g)
        for name in norder:
            v = self.idx[name]
            t = self.ty[v]
            if t not in ('src', 'mach'):
                continue
            for ci in self.nt_order(v):
                b = self.cs[ci][1]
                if t == 'mach':
                    if self.tk[v] is None:
                        break
                    kind = self.tk[v][0]
                else:
                    kind = self.kind_of[ci]
                    if kind is None:
                        continue
                    if kind in self.stock[v] and self.stock[v][kind] <= 0:
                        continue
                if not self.can_take(b, kind, self.physid(v)):
                    continue
                if t == 'mach':
                    self.tk[v][1] -= 1
                    if self.tk[v][1] == 0:
                        self.tk[v] = None
                    self.try_flush(v)
                elif kind in self.stock[v]:
                    self.stock[v][kind] -= 1
                self.give(b, kind, self.physid(v))
                self.lastok[ci] = self.now
                self.lastrank[self.rk[b]] = self.cs[ci][2]
                break
        for m in self.slots:
            if not self.on[m] or self.left[m] > 0 or self.cache[m] is not None:
                continue
            have = {s[0]: s for s in self.slots[m]}
            for rec in self.d[m]['recipes']:
                if all(k in have and have[k][1] >= c for k, c in rec['in']):
                    for k, c in rec['in']:
                        have[k][1] -= c
                    self.slots[m] = [s for s in self.slots[m] if s[1] > 0]
                    self.left[m] = rec['dur']
                    self.cache[m] = (rec['out'], rec['qty'])
                    break
        self.now += 1

    def canon(self):
        """与编码丙可比的状态摘要：各元件格（物品、进格步），制造单位，汇收件数。"""
        el = {}
        for u in range(len(self.names)):
            if self.is_el[u]:
                el[self.names[u]] = tuple(None if self.cv[c] is None else (self.cv[c][0], self.cv[c][1])
                                          for c in self.cells[u])
        mc = {}
        for m in self.slots:
            mc[self.names[m]] = (tuple(sorted(tuple(s) for s in self.slots[m])),
                                 None if self.tk[m] is None else tuple(self.tk[m]),
                                 self.cache[m], self.left[m])
        sk = {self.names[s]: c for s, c in self.recv.items()}
        return (self.now, tuple(sorted(el.items())), tuple(sorted(mc.items())), tuple(sorted(sk.items())))


def canon_p(w):
    """编码丙 World 的同一摘要。"""
    el = {}
    for e, cs in w.cell.items():
        el[e] = tuple(None if x is None else (x[0], x[1]) for x in cs)
    mc = {}
    for m in w.slot:
        tk = w.take[m]
        left = 0 if w.run[m] is None else w.run[m][1]
        mc[m] = (tuple(sorted(tuple(s) for s in w.slot[m] if s[0] is not None)),
                 None if tk[1] == 0 else tuple(tk), w.cache[m], left)
    sk = {s: len(v) for s, v in w.got.items()}
    return (w.t, tuple(sorted(el.items())), tuple(sorted(mc.items())), tuple(sorted(sk.items())))
