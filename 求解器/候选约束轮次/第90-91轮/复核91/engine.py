# -*- coding: utf-8 -*-
"""第 91 轮复核席自写的逐判定模拟器（只用标准库，不导入任何前席脚本）。

时间取整数，单位 1/Q tick；各单位的事件可以落在任意余数（相位）上。
规则映射（前提快照《游戏规则》行号 R）：
  - 运输物品格上限 1（R59），物品至少停留 1 tick = Q 个单位（R23）；
  - 移动零时（R24）；同一时刻的判定逐个做，直到一整遍没有成功的判定（闭合）；
  - 制造单位：存货物品格上限 50、种类格数 1 或 2（R17、R44-58），
    缓存格只在上一批全部进入取货格后、存货凑齐一批时装入（R18），
    装入即开始，持续供电开机时 d tick 后完成（R35），不运行时进度保留（R20）；
    整批进入取货物品格（上限 50，R17-18）；
  - 取货侧多条通道按指针轮流（R29 的一种实现：从指针起第一条能动的通道动，
    指针移到它后面）；复核只需一种合法实现即可给反例，结论的核对则另跑
    「对手期」每一步随机次序；
  - 物品准入口：放行种类、每 5 tick 收下上限（窗口从收下第一件起算，走完后由
    下一件重新起算），用尽时阻断（R64）。
"""
import random

EMPTY = -1


class Net:
    def __init__(self, Q):
        self.Q = Q
        # cells
        self.c_item = []
        self.c_tin = []
        self.c_dest = []       # ('c', j) / ('m', j) / ('k', j)
        self.c_allow = []      # None or item
        self.c_k5 = []         # None or 1..5
        self.c_wstart = []
        self.c_wcnt = []
        self.c_tag = []
        self.c_li = []         # the item this line carries (for random legal initial states)
        # machines
        self.m_in = []         # dict item -> a
        self.m_prod = []
        self.m_k = []
        self.m_d = []
        self.m_nslots = []
        self.m_inv = []        # dict item -> count
        self.m_cache = []      # 0 none, 1 running, 2 done
        self.m_rem = []
        self.m_out = []        # count in output slot
        self.m_outch = []      # list of cell idx
        self.m_ptr = []
        self.m_pow = []
        self.m_tag = []
        # sources (warehouse ports): (item, cell)
        self.sources = []
        # sinks: schedule function(t)->bool ; delivered counts
        self.k_open = []
        self.k_sched = []      # callable
        self.k_period = []     # for state key (None = always open in steady)
        self.k_count = []
        # events log for phases
        self.t = 0
        self.order = None
        self.power_events = []  # (t, m, on)
        self.rng = None

    # ---- construction ----
    def add_cell(self, allow=None, k5=None, tag=''):
        self.c_item.append(EMPTY); self.c_tin.append(0); self.c_dest.append(None)
        self.c_allow.append(allow); self.c_k5.append(k5)
        self.c_wstart.append(None); self.c_wcnt.append(0); self.c_tag.append(tag)
        self.c_li.append(None)
        return len(self.c_item) - 1

    def add_machine(self, inputs, prod, k, d, nslots, tag=''):
        self.m_in.append(dict(inputs)); self.m_prod.append(prod); self.m_k.append(k)
        self.m_d.append(d); self.m_nslots.append(nslots); self.m_inv.append({})
        self.m_cache.append(0); self.m_rem.append(0); self.m_out.append(0)
        self.m_outch.append([]); self.m_ptr.append(0); self.m_pow.append(True)
        self.m_tag.append(tag)
        return len(self.m_in) - 1

    def add_sink(self, sched, period=None):
        self.k_open.append(True); self.k_sched.append(sched); self.k_period.append(period)
        self.k_count.append(0)
        return len(self.k_open) - 1

    def line(self, n, dest, allow_gate_item=None, tag='', item=None):
        """n cells in series ending at dest; returns first cell index."""
        cells = [self.add_cell(tag=tag) for _ in range(n)]
        for c in cells:
            self.c_li[c] = item
        if allow_gate_item is not None:
            g = cells[len(cells) // 2]
            self.c_allow[g] = allow_gate_item
        for a, b in zip(cells, cells[1:]):
            self.c_dest[a] = ('c', b)
        self.c_dest[cells[-1]] = dest
        return cells

    # ---- acceptance ----
    def cell_accepts(self, c, item, t):
        if self.c_item[c] != EMPTY:
            return False
        al = self.c_allow[c]
        if al is not None and al != item:
            return False
        k5 = self.c_k5[c]
        if k5 is not None:
            ws = self.c_wstart[c]
            if ws is not None and t < ws + 5 * self.Q and self.c_wcnt[c] >= k5:
                return False
        return True

    def cell_put(self, c, item, t):
        self.c_item[c] = item
        self.c_tin[c] = t
        if self.c_k5[c] is not None:
            ws = self.c_wstart[c]
            if ws is None or t >= ws + 5 * self.Q:
                self.c_wstart[c] = t
                self.c_wcnt[c] = 1
            else:
                self.c_wcnt[c] += 1
        self.obs_recv[c] = 1

    def mach_accepts(self, m, item):
        a = self.m_in[m]
        if item not in a:
            return False
        inv = self.m_inv[m]
        cnt = inv.get(item, 0)
        if cnt > 0:
            return cnt < 50
        used = sum(1 for v in inv.values() if v > 0)
        return used < self.m_nslots[m]

    # ---- one step ----
    def build_order(self, rng):
        dets = []
        for s in range(len(self.sources)):
            dets.append((0, s))
        for c in range(len(self.c_item)):
            dets.append((1, c))
        for m in range(len(self.m_in)):
            dets.append((2, m))
            dets.append((3, m))
            dets.append((4, m))
        rng.shuffle(dets)
        return dets

    def step(self, t, order):
        """advance from t-1 to t, then closure at t."""
        Q = self.Q
        self.t = t
        nC = len(self.c_item)
        self.obs_recv = [0] * nC
        # manufacturing progress during (t-1, t]
        for m in range(len(self.m_in)):
            if self.m_cache[m] == 1 and self.m_pow[m]:
                self.m_rem[m] -= 1
                if self.m_rem[m] == 0:
                    self.m_cache[m] = 2
                    self.ev_phase.add(t % Q)
        # power toggles at t
        for (tt, m, on) in self.power_events:
            if tt == t:
                self.m_pow[m] = on
        for k in range(len(self.k_open)):
            self.k_open[k] = self.k_sched[k](t)
        empt = [self.c_item[c] == EMPTY for c in range(nC)]
        changed = True
        while changed:
            changed = False
            for kind, i in order:
                if kind == 1:
                    it = self.c_item[i]
                    if it == EMPTY or t - self.c_tin[i] < Q:
                        continue
                    dk, j = self.c_dest[i]
                    if dk == 'c':
                        if self.cell_accepts(j, it, t):
                            self.c_item[i] = EMPTY
                            empt[i] = True
                            self.cell_put(j, it, t)
                            self.ev_phase.add(t % Q)
                            changed = True
                    elif dk == 'm':
                        if self.mach_accepts(j, it):
                            self.c_item[i] = EMPTY
                            empt[i] = True
                            inv = self.m_inv[j]
                            inv[it] = inv.get(it, 0) + 1
                            self.ev_phase.add(t % Q)
                            changed = True
                    else:
                        if self.k_open[j]:
                            self.c_item[i] = EMPTY
                            empt[i] = True
                            self.k_count[j] += 1
                            self.ev_phase.add(t % Q)
                            changed = True
                elif kind == 0:
                    it, c = self.sources[i]
                    if self.cell_accepts(c, it, t):
                        self.cell_put(c, it, t)
                        self.ev_phase.add(t % Q)
                        changed = True
                elif kind == 2:  # cache -> output slot
                    if self.m_cache[i] == 2 and self.m_out[i] + self.m_k[i] <= 50:
                        self.m_out[i] += self.m_k[i]
                        self.m_cache[i] = 0
                        self.ev_phase.add(t % Q)
                        changed = True
                elif kind == 3:  # start a batch
                    if self.m_cache[i] == 0 and self.m_pow[i]:
                        inv = self.m_inv[i]
                        ok = True
                        for it, a in self.m_in[i].items():
                            if inv.get(it, 0) < a:
                                ok = False
                                break
                        if ok:
                            for it, a in self.m_in[i].items():
                                inv[it] -= a
                            self.m_cache[i] = 1
                            self.m_rem[i] = self.m_d[i] * Q
                            self.ev_phase.add(t % Q)
                            changed = True
                else:  # output channels
                    if self.m_out[i] > 0:
                        chs = self.m_outch[i]
                        n = len(chs)
                        p = self.m_ptr[i]
                        for r in range(n):
                            idx = (p + r) % n
                            c = chs[idx]
                            if self.cell_accepts(c, self.m_prod[i], t):
                                self.m_out[i] -= 1
                                self.cell_put(c, self.m_prod[i], t)
                                self.m_ptr[i] = (idx + 1) % n
                                self.ev_phase.add(t % Q)
                                changed = True
                                break
        for c in range(nC):
            if self.c_item[c] == EMPTY:
                empt[c] = True
        self.obs_empt = empt

    def state_key(self, t):
        Q = self.Q
        cells = []
        for c in range(len(self.c_item)):
            it = self.c_item[c]
            age = min(t - self.c_tin[c], Q) if it != EMPTY else 0
            if self.c_k5[c] is not None and self.c_wstart[c] is not None and t < self.c_wstart[c] + 5 * Q:
                g = (self.c_wstart[c] + 5 * Q - t, self.c_wcnt[c])
            else:
                g = None
            cells.append((it, age, g))
        machs = []
        for m in range(len(self.m_in)):
            machs.append((tuple(sorted((k, v) for k, v in self.m_inv[m].items() if v > 0)),
                          self.m_cache[m], self.m_rem[m] if self.m_cache[m] == 1 else 0,
                          self.m_out[m], self.m_ptr[m], self.m_pow[m]))
        sinks = tuple((t % p) if p else 0 for p in self.k_period)
        return (tuple(cells), tuple(machs), sinks)

    def run(self, rng, t_trans, t_max, adversarial=True, fixed_order=None):
        """transient (random order per step if adversarial), then fixed order until a
        state repeats.  Returns dict with cycle observations or None."""
        self.ev_phase = set()
        order = fixed_order or self.build_order(rng)
        t = 0
        for t in range(1, t_trans + 1):
            o = self.build_order(rng) if adversarial else order
            self.step(t, o)
        seen = {}
        obs = []
        t0 = t_trans
        key = self.state_key(t0)
        seen[key] = t0
        obs.append(None)
        t = t0
        while t < t_max:
            t += 1
            self.ev_phase = set()
            self.step(t, order)
            nonempty_m = [self.m_cache[m] != 0 for m in range(len(self.m_in))]
            nonempty_c = [self.c_item[c] != EMPTY for c in range(len(self.c_item))]
            full_in = [any(v >= 50 for v in self.m_inv[m].values()) for m in range(len(self.m_in))]
            obs.append((nonempty_m, nonempty_c, self.obs_recv, self.obs_empt,
                        frozenset(self.ev_phase), full_in, list(self.m_pow),
                        [self.m_cache[m] == 1 and self.m_rem[m] == self.m_d[m] * self.Q for m in range(len(self.m_in))]))
            key = self.state_key(t)
            if key in seen:
                t1 = seen[key]
                cyc = obs[t1 - t0 + 1: t - t0 + 1]
                return {'t1': t1, 't2': t, 'period': t - t1, 'obs': cyc}
            seen[key] = t
        return None
