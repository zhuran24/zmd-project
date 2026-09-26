#!/usr/bin/env python3
"""复核85：D 组单元起态缓存格里放着另一种植物的一批时会怎样（整数 tick，逐刻闭包）。

第 83 轮修正版「种群下界」「不断料」只限定了各路和各存货/取货物品格里的物品，没有限定缓存格。
采种机、种植机、粉碎机都有荞花、砂叶两个配方，缓存格可以在调试期留下另一种植物的一批。
本程序带物品种类逐件模拟：物品格一格一种、上限 m；运输格上限 1、滞留 1 tick；
每刻闭包；争用随机；K 下游每刻全收。

起态（荞花单元）：路 CA、AC 满，A、C 存货格与取货格按条文只放荞花的种子/植株，
C 的缓存格里是做好的一批砂叶种子（2 粒），因取货格里是荞花种子而放不进，等着。
这个起态的来路：调试时 C 取货格有荞花种子、C 存货格空，往 C 存货格放 1 株砂叶，
C 开工做完后整批放不进，一直等；再把 C 存货格补满荞花植株，结束调试。
Φ 按条文计（缓存格有东西记 1，种子、植株都计）。
"""
import random, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

class Grid:
    def __init__(self, cap):
        self.kind, self.n, self.cap = None, 0, cap
    def can(self, k):
        return (self.kind == k and self.n < self.cap) or self.n == 0
    def put(self, k):
        assert self.can(k); self.kind = k; self.n += 1
    def take(self):
        self.n -= 1; k = self.kind
        if self.n == 0: self.kind = None
        return k

class Unit:
    def __init__(self, m, L1, L2, L3, L4, kk, rng):
        self.m, self.rng, self.kk = m, rng, kk
        self.inp = {n: Grid(m) for n in "CABK"}
        self.out = {n: Grid(m) for n in "CABK"}
        self.cache = {n: None for n in "CABK"}   # (kind_out, count, done_tick) 或 None
        self.P = {"CA": [None] * L1, "AC": [None] * L2, "CB": [None] * L3, "BK": [None] * L4}  # (kind, entry)
        self.D = [None] * kk
        self.now = 0
    def recipe(self, n, k):
        base = k.split("·")[0]
        if n == "C": return (base + "·种子", 2)
        if n in "AB": return (base + "·植株", 1)
        return (base + "·粉末", self.kk)
    def mature(self, c):
        return c is not None and self.now - c[1] >= 1
    def acts(self):
        A = []
        for n in "CABK":
            g = self.inp[n]
            if self.cache[n] is None and g.n >= 1:
                A.append(("start", n))
            c = self.cache[n]
            if c is not None and self.now >= c[2]:
                o = self.out[n]
                if (o.n == 0) or (o.kind == c[0] and o.n + c[1] <= self.m):
                    A.append(("emit", n))
        dest = {"CA": "A", "AC": "C", "CB": "B", "BK": "K"}
        src = {"CA": "C", "AC": "A", "CB": "C", "BK": "B"}
        for p, cells in self.P.items():
            for i in range(len(cells) - 1):
                if self.mature(cells[i]) and cells[i + 1] is None: A.append(("mv", p, i))
            if self.mature(cells[-1]) and self.inp[dest[p]].can(cells[-1][0]): A.append(("in", p))
            if cells[0] is None and self.out[src[p]].n > 0: A.append(("take", p))
        for j in range(self.kk):
            if self.D[j] is None and self.out["K"].n > 0: A.append(("tk", j))
            if self.mature(self.D[j]): A.append(("lv", j))
        return A
    def apply(self, a):
        t = a[0]
        dest = {"CA": "A", "AC": "C", "CB": "B", "BK": "K"}
        src = {"CA": "C", "AC": "A", "CB": "C", "BK": "B"}
        if t == "start":
            k = self.inp[a[1]].take(); ko, c = self.recipe(a[1], k)
            self.cache[a[1]] = (ko, c, self.now + 1)
        elif t == "emit":
            ko, c, _ = self.cache[a[1]]
            for _ in range(c): self.out[a[1]].put(ko)
            self.cache[a[1]] = None
        elif t == "mv":
            cells = self.P[a[1]]; cells[a[2] + 1] = (cells[a[2]][0], self.now); cells[a[2]] = None
        elif t == "in":
            cells = self.P[a[1]]; self.inp[dest[a[1]]].put(cells[-1][0]); cells[-1] = None
        elif t == "take":
            k = self.out[src[a[1]]].take(); self.P[a[1]][0] = (k, self.now)
            self._tk.add(a[1])
        elif t == "tk":
            k = self.out["K"].take(); self.D[a[1]] = (k, self.now)
        elif t == "lv":
            self.D[a[1]] = None
    def closure(self):
        self._tk = set()
        while True:
            A = self.acts()
            if not A: return self._tk
            self.apply(self.rng.choice(A))
    def phi2(self):
        s = sum(c is not None for c in self.P["CA"]) + self.inp["A"].n + (self.cache["A"] is not None) + self.out["A"].n
        s += sum(c is not None for c in self.P["AC"]) + self.inp["C"].n + (self.cache["C"] is not None)
        return 2 * s + self.out["C"].n
    def key(self):
        return (tuple((self.inp[n].kind, self.inp[n].n, self.out[n].kind, self.out[n].n,
                       None if self.cache[n] is None else (self.cache[n][0], max(self.cache[n][2] - self.now, 0))) for n in "CABK"),
                tuple(tuple(None if c is None else (c[0], min(self.now - c[1], 1)) for c in cells) for cells in self.P.values()),
                tuple(None if c is None else min(self.now - c[1], 1) for c in self.D))

def build(m, L, kk, seed, foreign):
    rng = random.Random(seed)
    u = Unit(m, L, L, L, L, kk, rng)
    Qs, Qp = "荞花·种子", "荞花·植株"
    for i in range(L):
        u.P["CA"][i] = (Qs, -1); u.P["AC"][i] = (Qp, -1)
    for _ in range(m): u.inp["A"].put(Qs); u.inp["C"].put(Qp)
    for _ in range(m): u.out["A"].put(Qp)
    for _ in range(m - 1): u.out["C"].put(Qs)
    if foreign:
        u.cache["C"] = ("砂叶·种子", 2, 0)       # 做好的一批砂叶种子，放不进
    else:
        u.cache["C"] = (Qs, 2, 0)
    return u

def run(m, L, kk, seed, foreign, T=20000):
    u = build(m, L, kk, seed, foreign)
    u.closure()
    phi0 = u.phi2(); minphi = phi0
    seen = {}; hist = []
    for t in range(T):
        u.now += 1
        u.closure()
        ph = u.phi2(); minphi = min(minphi, ph)
        hist.append((u.cache["C"] is None, ph))
        k = u.key()
        if k in seen:
            cyc = hist[seen[k] + 1:]
            return {"m": m, "L": L, "k": kk, "seed": seed, "foreign": foreign, "phi0": phi0 / 2, "S": 2 * L + 2,
                    "bound_D02": min(phi0 / 2 - 0.5, 2 * L + 3 * m + 2 + (m - 1) / 2 - 0.5), "min_phi": minphi / 2,
                    "cycle_at": seen[k], "period": len(cyc), "C_idle_ticks_in_cycle": sum(1 for h in cyc if h[0]),
                    "phi_in_cycle": [min(h[1] for h in cyc) / 2, max(h[1] for h in cyc) / 2]}
        seen[k] = len(hist) - 1
    return {"m": m, "L": L, "seed": seed, "foreign": foreign, "no_cycle": True, "min_phi": minphi / 2, "phi0": phi0 / 2}

def main():
    out = []
    for m in (50, 8, 5):
        for L in (1, 2, 4):
            for seed in range(3):
                for foreign in (False, True):
                    r = run(m, L, 3, seed, foreign)
                    out.append(r)
                    print(r, flush=True)
    (HERE / "foreign_cache_sim.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
