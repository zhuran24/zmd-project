#!/usr/bin/env python3
"""复核85：采种双出口专线单元的细分时刻模拟（每 tick 分成 q 个子刻，各单位相位任意）。

独立编写，不导入推导席或前两轮复核的脚本。

语义（与规则逐条对应）：
- 时间以子刻计，1 tick = q 子刻；移动耗时 0；运输格物品进格后至少停 q 子刻才能出（滞留）。
- 制造：缓存空且存货格有一批原料即开工（立刻），q 子刻后完成；完成的一批在取货格放得下时整批进入。
- 每个子刻做闭包：反复执行任一可执行动作，直到没有可动（「一直在尝试移动」＋同刻逐个判定）。
- 争用（C 取货格被两条通道同时要、K 取货格被多条通道同时要）的先后由对手（随机）或固定规则决定。
- 各单位的初始相位（缓存完成时刻、各格物品进格时刻）在 q 细分上任意取，所以不同单位可以不同相位。

检查：
- D02：每个子刻结束 Φ ≥ min(Φ0 − 1/2, L1+L2+3m+2+(m−1)/2 − 1/2)。
- STUCK：A 的首格在某子刻结束时放着进格已满 1 tick 的旧货（本报告的「卡住」）时，
  Φ ≥ L1+L2+3m+2+(m−1)/2（F3 的连续时间版）。
- BAL：两次「卡住」之间（及从起点到第一次卡住），B 取件数 − A 取件数 ≤ 1。
- D03：Φ0 ≥ S+1/2 时，对手停手后（固定判定规则、下游按固定周期收货）跑到状态重复，
  循环里 C、B、K 每个子刻结束时缓存都非空。
"""
import random, sys, json, os, time
from fractions import Fraction as Fr

class Unit:
    def __init__(self, q, m, L1, L2, L3, L4, k, rng):
        self.q, self.m, self.k = q, m, k
        self.L = {"CA": L1, "AC": L2, "CB": L3, "BK": L4}
        self.rng = rng
        self.now = 0
        # 机器：inp, cache(None 或 完成时刻), out
        self.M = {n: {"inp": 0, "cache": None, "out": 0} for n in "CABK"}
        self.P = {p: [None] * n for p, n in self.L.items()}   # 格里放进格时刻
        self.D = [None] * k                                     # K 的下游首格
        self.batch = {"C": 2, "A": 1, "B": 1, "K": k}
        self.ptr_C = 0      # C 取货侧轮询指针（确定性阶段用）
        self.ptr_K = 0
        self.takes = {"A": 0, "B": 0}

    # ---------- 状态 ----------
    def mature(self, t):
        return t is not None and self.now - t >= self.q

    def phi2(self):  # 2Φ，整数
        C, A = self.M["C"], self.M["A"]
        s = sum(1 for x in self.P["CA"] if x is not None) + A["inp"] + (A["cache"] is not None) + A["out"]
        s += sum(1 for x in self.P["AC"] if x is not None) + C["inp"] + (C["cache"] is not None)
        return 2 * s + C["out"]

    def key(self, down_phase):
        cap = lambda t: None if t is None else min(self.now - t, self.q)
        mk = tuple((v["inp"], None if v["cache"] is None else max(v["cache"] - self.now, 0), v["out"]) for v in (self.M[n] for n in "CABK"))
        pk = tuple(tuple(cap(t) for t in self.P[p]) for p in ("CA", "AC", "CB", "BK"))
        return (mk, pk, tuple(cap(t) for t in self.D), self.ptr_C, self.ptr_K, down_phase)

    def stuckA(self):
        t = self.P["CA"][0]
        return t is not None and self.now - t >= self.q

    # ---------- 动作 ----------
    def enabled(self, down_ok):
        acts = []
        m, M, P = self.m, self.M, self.P
        # 机器开工、完成进格
        for n in "CABK":
            v = M[n]
            if v["cache"] is None and v["inp"] >= 1:
                acts.append(("start", n))
            elif v["cache"] is not None and self.now >= v["cache"] and v["out"] + self.batch[n] <= m:
                acts.append(("emit", n))
        # 路上前移与进机
        dest = {"CA": "A", "AC": "C", "CB": "B", "BK": "K"}
        for p, cells in P.items():
            for i in range(len(cells) - 1):
                if self.mature(cells[i]) and cells[i + 1] is None:
                    acts.append(("mv", p, i))
            if self.mature(cells[-1]) and M[dest[p]]["inp"] < m:
                acts.append(("in", p))
        # 取件
        if M["C"]["out"] > 0:
            if P["CA"][0] is None: acts.append(("take", "CA"))
            if P["CB"][0] is None: acts.append(("take", "CB"))
        if M["A"]["out"] > 0 and P["AC"][0] is None: acts.append(("take", "AC"))
        if M["B"]["out"] > 0 and P["BK"][0] is None: acts.append(("take", "BK"))
        if M["K"]["out"] > 0:
            for j in range(self.k):
                if self.D[j] is None: acts.append(("takeK", j))
        for j in range(self.k):
            if self.mature(self.D[j]) and down_ok[j]:
                acts.append(("leave", j))
        return acts

    def apply(self, a):
        M, P, now = self.M, self.P, self.now
        dest = {"CA": "A", "AC": "C", "CB": "B", "BK": "K"}
        src = {"CA": "C", "AC": "A", "CB": "C", "BK": "B"}
        if a[0] == "start":
            M[a[1]]["inp"] -= 1; M[a[1]]["cache"] = now + self.q
        elif a[0] == "emit":
            M[a[1]]["out"] += self.batch[a[1]]; M[a[1]]["cache"] = None
        elif a[0] == "mv":
            p, i = a[1], a[2]
            P[p][i + 1] = now; P[p][i] = None
        elif a[0] == "in":
            p = a[1]; P[p][-1] = None; M[dest[p]]["inp"] += 1
        elif a[0] == "take":
            p = a[1]; M[src[p]]["out"] -= 1; P[p][0] = now
            if p == "CA": self.takes["A"] += 1; self._tk.add("A")
            if p == "CB": self.takes["B"] += 1; self._tk.add("B")
        elif a[0] == "takeK":
            M["K"]["out"] -= 1; self.D[a[1]] = now
        elif a[0] == "leave":
            self.D[a[1]] = None

    def closure(self, down_ok, mode):
        self._tk = set()
        guard = 0
        while True:
            acts = self.enabled(down_ok)
            if not acts:
                break
            if mode == "random":
                a = self.rng.choice(acts)
            else:
                a = self.pick_fixed(acts)
            self.apply(a)
            guard += 1
            assert guard < 100000
        return self._tk

    def pick_fixed(self, acts):
        # 固定判定规则：非争用动作按固定序；C 取货侧两条、K 取货侧 k 条按轮询指针，成功后前移
        order = self.fixed_order
        takesC = [a for a in acts if a[0] == "take" and a[1] in ("CA", "CB")]
        takesK = [a for a in acts if a[0] == "takeK"]
        others = [a for a in acts if a not in takesC and a not in takesK]
        if others:
            others.sort(key=lambda a: order.get(a, 0))
            return others[0]
        if takesC:
            want = ("CA", "CB")[self.ptr_C]
            for a in takesC:
                if a[1] == want:
                    self.ptr_C ^= 1; return a
            self.ptr_C ^= 1
            return takesC[0]
        if takesK:
            for d in range(self.k):
                j = (self.ptr_K + d) % self.k
                for a in takesK:
                    if a[1] == j:
                        self.ptr_K = (j + 1) % self.k; return a
        return acts[0]


def random_state(u, rng, sparse):
    q, m = u.q, u.m
    def cnt():
        if sparse:
            return rng.choice([0, 0, 0, 1, 2])
        return rng.randint(0, m)
    for n in "CABK":
        v = u.M[n]
        v["inp"] = cnt()
        r = rng.random()
        if r < 0.4:
            v["cache"] = None
        elif r < 0.85:
            v["cache"] = rng.randint(1, q)          # 进行中，在下一 tick 内任一子刻完成
        else:
            v["cache"] = 0                          # 已做好等进格
        v["out"] = cnt()
        if v["out"] + u.batch[n] > m and v["cache"] is None:
            pass
        if v["out"] > m - (u.batch[n] if n == "C" else 0):
            v["out"] = min(v["out"], m)
    p_occ = 0.25 if sparse else 0.7
    for p, cells in u.P.items():
        for i in range(len(cells)):
            cells[i] = (-rng.randint(0, 2 * q)) if rng.random() < p_occ else None
    for j in range(u.k):
        u.D[j] = (-rng.randint(0, 2 * q)) if rng.random() < 0.5 else None
    # C 取货格种子数不超过上限
    u.M["C"]["out"] = min(u.M["C"]["out"], m)


def run_case(seed, q, m, Ls, k, T_adv_ticks, sparse, max_cycle_ticks=4000):
    rng = random.Random(seed)
    u = Unit(q, m, *Ls, k, rng)
    random_state(u, rng, sparse)
    L1, L2 = Ls[0], Ls[1]
    F3b2 = 2 * (L1 + L2 + 3 * m + 2) + (m - 1)          # 2×F3 界
    S = L1 + L2 + 2
    # 起点闭包（下游全收）
    u.closure([True] * k, "random")
    phi0 = u.phi2()
    lo2 = min(phi0 - 1, F3b2 - 1)
    viol = {"D02": 0, "STUCK": 0, "STUCK_late": 0, "BAL": 0}
    minphi2 = phi0
    bal = 0; balmax = 0
    stuck_seen = 0
    # 对手阶段
    mode_dn = rng.choice(["rand", "block", "one", "all"])
    for step in range(T_adv_ticks * q):
        u.now += 1
        if mode_dn == "rand": down = [rng.random() < 0.5 for _ in range(k)]
        elif mode_dn == "block": down = [((u.now // (7 * q)) % 2 == 0)] * k
        elif mode_dn == "one": down = [j == 0 for j in range(k)]
        else: down = [True] * k
        if rng.random() < 0.02:
            mode_dn = rng.choice(["rand", "block", "one", "all"])
        tk = u.closure(down, "random")
        ph = u.phi2()
        minphi2 = min(minphi2, ph)
        if ph < lo2: viol["D02"] += 1
        bal += ("B" in tk) - ("A" in tk)
        balmax = max(balmax, bal)
        if bal > 1: viol["BAL"] += 1
        if u.stuckA():
            stuck_seen += 1
            if ph < F3b2:
                viol["STUCK"] += 1
                if u.now >= q: viol["STUCK_late"] += 1
            bal = 0
    # 确定性阶段：固定判定规则、下游周期收货
    acts_all = []
    u.fixed_order = {}
    labels = [("start", n) for n in "CABK"] + [("emit", n) for n in "CABK"] + [("in", p) for p in u.P] + \
             [("mv", p, i) for p in u.P for i in range(len(u.P[p]) - 1)] + [("take", "AC"), ("take", "BK")] + \
             [("leave", j) for j in range(k)]
    rng.shuffle(labels)
    u.fixed_order = {a: i for i, a in enumerate(labels)}
    per = rng.choice([1, 1, 2, 3])
    phs = [rng.randrange(per * q) for _ in range(k)]
    seen = {}
    hist = []
    res = {"cycle": False}
    for step in range(max_cycle_ticks * q):
        u.now += 1
        dph = u.now % (per * q)
        down = [dph == phs[j] or per == 1 for j in range(k)]
        tk = u.closure(down, "fixed")
        ph = u.phi2()
        minphi2 = min(minphi2, ph)
        if ph < lo2: viol["D02"] += 1
        bal += ("B" in tk) - ("A" in tk); balmax = max(balmax, bal)
        if bal > 1: viol["BAL"] += 1
        if u.stuckA():
            stuck_seen += 1
            if ph < F3b2:
                viol["STUCK"] += 1
                if u.now >= q: viol["STUCK_late"] += 1
            bal = 0
        idle = tuple(u.M[n]["cache"] is None for n in "CBK")
        hist.append((idle, ph, tuple(sorted(tk))))
        key = u.key(dph)
        if key in seen:
            st = seen[key]
            cyc = hist[st + 1:]
            res = {"cycle": True, "period_sub": len(cyc),
                   "idle_C": sum(1 for h in cyc if h[0][0]), "idle_B": sum(1 for h in cyc if h[0][1]),
                   "idle_K": sum(1 for h in cyc if h[0][2]),
                   "phi2_min_cycle": min(h[1] for h in cyc),
                   "A_takes": sum(1 for h in cyc if "A" in h[2]), "B_takes": sum(1 for h in cyc if "B" in h[2])}
            break
        seen[key] = len(hist) - 1
    d03_applicable = phi0 >= 2 * S + 1
    d03_viol = bool(res.get("cycle") and d03_applicable and (res["idle_C"] or res["idle_B"] or res["idle_K"]))
    return {"seed": seed, "q": q, "m": m, "L": Ls, "k": k, "phi0_x2": phi0, "S": S, "minphi_x2": minphi2,
            "viol": viol, "balmax": balmax, "stuck_seen": stuck_seen, "cyc": res,
            "d03_applicable": d03_applicable, "d03_viol": d03_viol}


def main():
    worker = int(sys.argv[1]); nworkers = int(sys.argv[2]); ncases = int(sys.argv[3])
    out = []
    agg = {"cases": 0, "D02": 0, "STUCK": 0, "STUCK_late": 0, "BAL": 0, "cycles": 0, "d03_applicable_cycles": 0,
           "d03_viol": 0, "idle_cycles_below_S": 0, "stuck_seen_cases": 0, "maxbal": 0,
           "cycles_q_gt1": 0}
    t0 = time.time()
    for c in range(ncases):
        seed = worker * 1000003 + c
        rng = random.Random(seed)
        q = rng.choice([1, 2, 3, 4])
        m = rng.choice([3, 4, 5, 6, 8])
        Ls = [rng.randint(1, 3) for _ in range(4)]
        k = rng.choice([2, 3])
        sparse = rng.random() < 0.6
        r = run_case(seed, q, m, Ls, k, rng.choice([30, 80]), sparse)
        agg["cases"] += 1
        for v in ("D02", "STUCK", "STUCK_late", "BAL"):
            agg[v] += 1 if r["viol"][v] else 0
        agg["maxbal"] = max(agg["maxbal"], r["balmax"])
        if r["stuck_seen"]: agg["stuck_seen_cases"] += 1
        if r["cyc"]["cycle"]:
            agg["cycles"] += 1
            if q > 1: agg["cycles_q_gt1"] += 1
            if r["d03_applicable"]: agg["d03_applicable_cycles"] += 1
            if not r["d03_applicable"] and r["cyc"]["idle_C"]: agg["idle_cycles_below_S"] += 1
        if r["d03_viol"]: agg["d03_viol"] += 1
        if r["viol"]["D02"] or r["viol"]["STUCK_late"] or r["viol"]["BAL"] or r["d03_viol"]:
            out.append(r)
    agg["seconds"] = round(time.time() - t0, 1)
    print(json.dumps({"worker": worker, "agg": agg, "violations": out[:20]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
