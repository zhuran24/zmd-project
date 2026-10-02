#!/usr/bin/env python3
"""复核 94F 编码丙：按快照规则第 23—33 行自写的步进模拟器（不导入推导席脚本，不导入 sim2）。

网络描述是纯数据：
  units: id -> dict(type=...)
    src : 仓库取货口/协议核心取货端口。每条送货通道各带一个设定物品（chan_kind[通道下标]），None 为不设。
          货源：ore 里的物品不断；别的物品按 stock 计数（缺省无限）。
    mach: 制造单位。nslots（1 或 2），recipes=[{in:[[k,n],..], out:k, qty:q, dur:步}]，on（开关，缺省 True）。
    sink: 协议核心收货侧（只收不送），open=(kind, a, b) 开合表。
    seg : 一段连续传送带（一个元件），len 格。
    gate: 物品准入口，allow（放行种类，None 不设），q5（每 5 tick 收下上限，None 不设）。
    bax : 桥接器一轴，bridge=桥接器单位 id。
    mer : 汇流器。
  chans: [[from, to, rank], ...]，rank 小的先接通。

读法开关（opts）：
  settle: 'eager'  —— 带内前挪：每步判定前各段挪一次，段头送走后立即再挪（内核设计 §1.6/§1.2 的读法）。
          'judge'  —— 带内前挪只在这一段自己被判定时做（先送头件，再挪）。
  bridge_group: 'axis' —— 第 31 行的「一个单位」对桥接器按轴算（候选的读法）。
                'unit' —— 桥接器两轴的上游合成一个收货组。
一步：结束到时的制造（入缓存格，能整批入取货物品格就入）-> 逐个判定（元件按层数从小到大、同层按给定次序，
      再非运输单位按给定次序）-> 开始能开始的制造。1 tick = 8 步，滞留 = 停满 8 步。
"""
from __future__ import annotations

TICK = 8
ELEM = ('seg', 'gate', 'bax', 'mer')
NONT = ('src', 'mach', 'sink')


def sink_open(spec, t):
    if spec is None or spec[0] == 'always':
        return True
    if spec[0] == 'period':
        return (t % spec[1]) < spec[2]
    if spec[0] == 'window':
        return not (spec[1] <= t < spec[1] + spec[2])
    if spec[0] == 'never':
        return False
    raise ValueError(spec)


class Net:
    def __init__(self, units, chans, bridge_group='axis'):
        self.U = units
        self.ch = [tuple(c) for c in sorted(chans, key=lambda c: c[2])]
        self.outs = {u: [] for u in units}
        self.ins = {u: [] for u in units}
        for i, c in enumerate(self.ch):
            self.outs[c[0]].append(i)
            self.ins[c[1]].append(i)
        self.elems = [u for u in units if units[u]['type'] in ELEM]
        self.nonts = [u for u in units if units[u]['type'] in NONT]
        self.bridge_group = bridge_group
        for e in self.elems:
            assert len(self.outs[e]) <= 1, ('元件至多一条送货通道', e)
        self.layer = {}
        for e in self.elems:
            self._lay(e, set())
        # 收货方：元件或非运输单位；bridge_group=='unit' 时桥接器两轴并成一个收货方
        self.rkey = {}
        for u in units:
            d = units[u]
            if d['type'] == 'bax' and bridge_group == 'unit':
                self.rkey[u] = ('B', d['bridge'])
            else:
                self.rkey[u] = ('U', u)
        self.rmembers = {}
        for u in units:
            self.rmembers.setdefault(self.rkey[u], []).append(u)
        # 收货方的存货侧通道（按接通先后）
        self.rins = {k: sorted([i for u in mem for i in self.ins[u]], key=lambda i: self.ch[i][2])
                     for k, mem in self.rmembers.items()}

    def phys(self, u):
        """物品进出时的物理单位：桥接器轴算桥接器本身。"""
        d = self.U[u]
        return ('bridge', d['bridge']) if d['type'] == 'bax' else ('unit', u)

    def _lay(self, e, seen):
        if e in self.layer:
            return self.layer[e]
        assert e not in seen, ('成环', e)
        seen.add(e)
        nxt = [self.ch[i][1] for i in self.outs[e]
               if self.U[self.ch[i][1]]['type'] in ELEM and self.outs[self.ch[i][1]]]
        self.layer[e] = self._lay(nxt[0], seen) + 1 if nxt else 1
        return self.layer[e]


class World:
    def __init__(self, net: Net, init=None, settle='eager', trigger='first'):
        self.net = net
        self.settle_mode = settle
        self.trigger = trigger      # 'first'：快照第 31 行；'sender'：临时规则 1（最先往它送货的那个判定时）
        self.t = 0
        U = net.U
        self.cell = {}
        self.gwin = {}
        self.slot = {}
        self.take = {}
        self.cache = {}
        self.run = {}
        self.on = {}
        self.stock = {}
        self.chan_kind = {}
        self.last_ok = {}      # 循环侧：(收货方 key) -> 上次成功的通道下标
        self.recency = {}      # 非运输送货侧：u -> 按上次成功从早到晚的通道下标表
        self.got = {}
        self.sent = {}
        for u, d in U.items():
            ty = d['type']
            if ty == 'seg':
                self.cell[u] = [None] * d['len']
            elif ty in ('gate', 'bax', 'mer'):
                self.cell[u] = [None]
            if ty == 'gate':
                self.gwin[u] = None
            if ty == 'mach':
                self.slot[u] = [[None, 0] for _ in range(d['nslots'])]
                self.take[u] = [None, 0]
                self.cache[u] = None
                self.run[u] = None
                self.on[u] = d.get('on', True)
            if ty == 'src':
                self.recency[u] = []
                self.stock[u] = dict(d.get('stock', {}))
            if ty == 'mach':
                self.recency[u] = []
            if ty == 'sink':
                self.got[u] = []
        for i, c in enumerate(net.ch):
            if U[c[0]]['type'] == 'src':
                self.chan_kind[i] = U[c[0]]['kinds'][net.outs[c[0]].index(i)]
        init = init or {}
        for u, lst in init.get('cell', {}).items():
            self.cell[u] = [None if x is None else [x[0], x[1], tuple(x[2]) if x[2] is not None else None]
                            for x in lst]
        for u, lst in init.get('slot', {}).items():
            self.slot[u] = [list(x) for x in lst]
        for u, x in init.get('take', {}).items():
            self.take[u] = list(x)
        for u, x in init.get('cache', {}).items():
            self.cache[u] = tuple(x) if x else None
        for u, x in init.get('run', {}).items():
            self.run[u] = list(x) if x else None
        for k, x in init.get('last_ok', {}).items():
            self.last_ok[k] = x
        for u, x in init.get('gwin', {}).items():
            self.gwin[u] = list(x) if x else None

    # ---------------- 物品格 ----------------
    def settle(self, s):
        cs = self.cell[s]
        for j in range(len(cs) - 2, -1, -1):
            it = cs[j]
            if it is not None and cs[j + 1] is None and self.t - it[1] >= TICK:
                cs[j + 1] = [it[0], self.t, ('belt', s, j)]
                cs[j] = None

    def head(self, e):
        it = self.cell[e][-1]
        if it is not None and self.t - it[1] >= TICK:
            return it
        return None

    def entry_phys(self, u):
        d = self.net.U[u]
        if d['type'] == 'seg':
            return ('belt', u, -1)      # 入口带；段内带用 ('belt', s, j)
        return self.net.phys(u)

    def accepts(self, u, kind, prev):
        U = self.net.U
        d = U[u]
        ty = d['type']
        if prev is not None and prev == self.entry_phys(u):
            return False
        if ty in ('seg', 'bax', 'mer'):
            return self.cell[u][0] is None
        if ty == 'gate':
            if self.cell[u][0] is not None:
                return False
            if d.get('allow') is not None and d['allow'] != kind:
                return False
            q = d.get('q5')
            if q is not None:
                w = self.gwin[u]
                if w is not None and self.t < w[0] + 5 * TICK and w[1] >= q:
                    return False
            return True
        if ty == 'mach':
            for s in self.slot[u]:
                if s[0] == kind:
                    return s[1] < 50
            return any(s[0] is None for s in self.slot[u])
        if ty == 'sink':
            return sink_open(d.get('open'), self.t)
        return False

    def put(self, u, kind, prev):
        d = self.net.U[u]
        ty = d['type']
        if ty in ('seg', 'bax', 'mer', 'gate'):
            self.cell[u][0] = [kind, self.t, prev]
            if ty == 'gate' and d.get('q5') is not None:
                w = self.gwin[u]
                if w is None or self.t >= w[0] + 5 * TICK:
                    self.gwin[u] = [self.t, 1]
                else:
                    w[1] += 1
        elif ty == 'mach':
            for s in self.slot[u]:
                if s[0] == kind:
                    s[1] += 1
                    return
            for s in self.slot[u]:
                if s[0] is None:
                    s[0], s[1] = kind, 1
                    return
            raise AssertionError
        elif ty == 'sink':
            self.got[u].append((self.t, kind))

    def flush(self, m):
        c = self.cache[m]
        if c is None or self.run[m] is not None:
            return
        tk = self.take[m]
        if (tk[0] is None or tk[0] == c[0]) and tk[1] + c[1] <= 50:
            tk[0] = c[0]
            tk[1] += c[1]
            self.cache[m] = None

    # ---------------- 一步 ----------------
    def step(self, elem_order, nont_order):
        net, U = self.net, self.net.U
        # 一、结束到时的制造
        for m in self.slot:
            r = self.run[m]
            if r is not None and self.on[m]:
                r[1] -= 1
                if r[1] == 0:
                    self.run[m] = None
            self.flush(m)
        if self.settle_mode == 'eager':
            for e in net.elems:
                if U[e]['type'] == 'seg':
                    self.settle(e)
        # 二、判定
        judged = set()
        for e in elem_order:
            if e in judged:
                continue
            if not net.outs[e]:
                judged.add(e)
                if self.settle_mode == 'judge' and U[e]['type'] == 'seg':
                    self.settle(e)
                continue
            dst = net.ch[net.outs[e][0]][1]
            rk = net.rkey[dst]
            arr = net.rins[rk]
            if self.trigger == 'sender':
                it0 = self.head(e)
                if it0 is None or (it0[2] is not None and it0[2] == self.entry_phys(dst)):
                    judged.add(e)
                    if self.settle_mode == 'judge' and U[e]['type'] == 'seg':
                        self.settle(e)
                    continue
            members = []
            for i in arr:
                src = net.ch[i][0]
                if U[src]['type'] in ELEM and src not in members and not (self.trigger == 'sender' and src in judged):
                    members.append(src)
            for mbr in members:
                assert mbr not in judged
                judged.add(mbr)
            n = len(arr)
            lo = self.last_ok.get(rk)
            if lo is None:
                start = 1 if (U[dst]['type'] == 'mer' and n > 1) else 0
            else:
                start = (arr.index(lo) + 1) % n
            ordered = arr[start:] + arr[:start]
            for i in ordered:
                src, tgt = net.ch[i][0], net.ch[i][1]
                if src not in members:
                    continue
                it = self.head(src)
                if it is None or not self.accepts(tgt, it[0], it[2]):
                    continue
                self.cell[src][-1] = None
                if self.settle_mode == 'eager' and U[src]['type'] == 'seg':
                    self.settle(src)
                prev = ('belt', src, len(self.cell[src]) - 1) if U[src]['type'] == 'seg' else net.phys(src)
                self.put(tgt, it[0], prev)
                self.last_ok[rk] = i
            if self.settle_mode == 'judge':
                for mbr in members:
                    if U[mbr]['type'] == 'seg':
                        self.settle(mbr)
        for v in nont_order:
            ty = U[v]['type']
            if ty == 'sink':
                continue
            for i in self.send_order(v):
                tgt = net.ch[i][1]
                if ty == 'mach':
                    tk = self.take[v]
                    if tk[1] == 0:
                        break
                    kind = tk[0]
                else:
                    kind = self.chan_kind.get(i)
                    if kind is None:
                        continue
                    if kind in self.stock[v] and self.stock[v][kind] <= 0:
                        continue
                if not self.accepts(tgt, kind, ('unit', v)):
                    continue
                if ty == 'mach':
                    tk[1] -= 1
                    if tk[1] == 0:
                        tk[0] = None
                    self.flush(v)
                else:
                    if kind in self.stock[v]:
                        self.stock[v][kind] -= 1
                    self.sent[i] = self.sent.get(i, 0) + 1
                self.put(tgt, kind, ('unit', v))
                rc = self.recency[v]
                if i in rc:
                    rc.remove(i)
                rc.append(i)
                self.last_ok[net.rkey[tgt]] = i
                break
        # 三、开始能开始的制造
        for m in self.slot:
            if not self.on[m] or self.run[m] is not None or self.cache[m] is not None:
                continue
            have = {s[0]: s for s in self.slot[m] if s[0] is not None}
            for rec in U[m]['recipes']:
                if all(k in have and have[k][1] >= n for k, n in rec['in']):
                    for k, n in rec['in']:
                        have[k][1] -= n
                        if have[k][1] == 0:
                            have[k][0] = None
                    self.run[m] = [rec['out'], rec['dur']]
                    self.cache[m] = (rec['out'], rec['qty'])
                    break
        self.t += 1

    def send_order(self, v):
        net, U = self.net, self.net.U
        arr = net.outs[v]
        if len(arr) <= 1:
            return list(arr)
        mer = [i for i in arr if U[net.ch[i][1]]['type'] == 'mer']
        rest = [i for i in arr if U[net.ch[i][1]]['type'] != 'mer']
        grades = [[i] for i in mer] + ([rest] if rest else [])

        def key(g):
            return (max(net.layer.get(net.ch[i][1], 1) for i in g), min(net.ch[i][2] for i in g))

        grades.sort(key=key)
        rc = self.recency[v]
        res = []
        for g in grades:
            never = sorted([i for i in g if i not in rc], key=lambda i: net.ch[i][2])
            used = [i for i in rc if i in g]
            res += never + used
        return res

    def snapshot(self):
        return (self.t,
                tuple((e, tuple(None if x is None else tuple(x) for x in self.cell[e])) for e in sorted(self.cell)),
                tuple((m, tuple(sorted(tuple(s) for s in self.slot[m] if s[0] is not None)),
                       tuple(self.take[m]), self.cache[m], None if self.run[m] is None else tuple(self.run[m]))
                      for m in sorted(self.slot)),
                tuple(sorted((str(k), v) for k, v in self.last_ok.items())),
                tuple((v, tuple(self.recency[v])) for v in sorted(self.recency)),
                tuple((g, None if w is None else tuple(w)) for g, w in sorted(self.gwin.items())),
                tuple((s, len(self.got[s])) for s in sorted(self.got)),
                tuple(sorted(self.sent.items())))


def default_orders(net, rng):
    """按层数排元件，同层随机；非运输单位随机。"""
    by = {}
    for e in net.elems:
        by.setdefault(net.layer[e], []).append(e)
    eo = []
    for L in sorted(by):
        g = list(by[L])
        rng.shuffle(g)
        eo += g
    no = list(net.nonts)
    rng.shuffle(no)
    return eo, no


def rank_orders(net):
    """按规则第 27 行：同层送货通道最早接通的先；没有送货通道的元件排在本层末尾（按 id）。"""
    def ekey(e):
        o = net.outs[e]
        return (net.layer[e], 0 if o else 1, net.ch[o[0]][2] if o else 0, e)
    eo = sorted(net.elems, key=ekey)

    def nkey(v):
        o = net.outs[v]
        return (0 if o else 1, min(net.ch[i][2] for i in o) if o else 0, v)
    no = sorted(net.nonts, key=nkey)
    return eo, no
