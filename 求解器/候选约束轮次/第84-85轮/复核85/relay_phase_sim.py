#!/usr/bin/env python3
"""复核85：「专线制造单位不空手的传递」的细分时刻检验（各单位相位任意）。

X 只做一个配方：d tick、原料 i 每批 a_i 件，经 c_i 条专线进货（d·c_i ≥ a_i）。
每条专线的源头是一台 1 tick 配方、原料无限（故始终不空手）的制造单位 Y，Y 每批 k_Y 件、
取货通道 ≤ k_Y 条，其中一条接 X，其余去对手控制的下游。X 的取货通道去对手控制的下游。
1 tick = q 子刻；运输格滞留 q 子刻；每子刻闭包；对手阶段随机次序、随机下游，之后固定规则、
周期下游，跑到状态重复，检查循环里 X 每个子刻结束缓存非空（不空手），以及
d=1 且 X 取货通道 ≤ 每批件数时，X 的每条就绪取货通道都取得到（首格独占）。
配置：研磨机（2 主料经 2 条 + 1 砂叶粉末经 1 条，d=1）、封装机（10 零件经 2 条、15 粉末经 3 条，d=5）、
精炼炉（1 矿经 1 条，源头为仓库取货口：永远有货）。
"""
import random, sys, json, time

class Sim:
    def __init__(self, q, m, cfg, rng):
        self.q, self.m, self.rng = q, m, rng
        self.now = 0
        # X
        self.recipe = cfg["recipe"]          # {item: a}
        self.d = cfg["d"]
        self.xk = cfg["x_out_batch"]
        self.xinp = {i: 0 for i in self.recipe}
        self.xcache = None
        self.xout = 0
        self.xdown = [None] * cfg["x_outlets"]    # X 取货通道首格（独占）
        # 专线：每条 (item, source_index, cells)
        self.lines = []
        self.src = []                          # 源头：{"kind": "machine"/"port", "k": k, "cache", "out", "others": [cells]}
        for item, c in cfg["channels"].items():
            for _ in range(c):
                L = rng.randint(1, 3)
                if cfg["source"] == "port":
                    s = {"kind": "port"}
                else:
                    kY = cfg["src_batch"][item]
                    s = {"kind": "machine", "k": kY, "cache": None, "out": 0,
                         "others": [None] * rng.randint(0, kY - 1)}
                self.src.append(s)
                self.lines.append({"item": item, "src": len(self.src) - 1, "cells": [None] * L})

    def mature(self, t):
        return t is not None and self.now - t >= self.q

    def enabled(self, down_x, down_o):
        A = []
        q, m = self.q, self.m
        # X 开工、进格
        if self.xcache is None and all(self.xinp[i] >= a for i, a in self.recipe.items()):
            A.append(("xstart",))
        if self.xcache is not None and self.now >= self.xcache and self.xout + self.xk <= m:
            A.append(("xemit",))
        # 源头
        for si, s in enumerate(self.src):
            if s["kind"] == "machine":
                if s["cache"] is None:
                    A.append(("sstart", si))
                elif self.now >= s["cache"] and s["out"] + s["k"] <= m:
                    A.append(("semit", si))
                if s["out"] > 0:
                    for j, cell in enumerate(s["others"]):
                        if cell is None: A.append(("stakeo", si, j))
                for j, cell in enumerate(s["others"]):
                    if self.mature(cell) and down_o[si][j]: A.append(("sleaveo", si, j))
        # 专线
        for li, ln in enumerate(self.lines):
            cells = ln["cells"]; s = self.src[ln["src"]]
            if cells[0] is None and (s["kind"] == "port" or s["out"] > 0):
                A.append(("ltake", li))
            for i in range(len(cells) - 1):
                if self.mature(cells[i]) and cells[i + 1] is None:
                    A.append(("lmv", li, i))
            if self.mature(cells[-1]) and self.xinp[ln["item"]] < m:
                A.append(("lin", li))
        # X 出货
        if self.xout > 0:
            for j, cell in enumerate(self.xdown):
                if cell is None: A.append(("xtake", j))
        for j, cell in enumerate(self.xdown):
            if self.mature(cell) and down_x[j]: A.append(("xleave", j))
        return A

    def apply(self, a):
        now, q = self.now, self.q
        t = a[0]
        if t == "xstart":
            for i, n in self.recipe.items(): self.xinp[i] -= n
            self.xcache = now + self.d * q
        elif t == "xemit":
            self.xout += self.xk; self.xcache = None
        elif t == "sstart":
            self.src[a[1]]["cache"] = now + q
        elif t == "semit":
            s = self.src[a[1]]; s["out"] += s["k"]; s["cache"] = None
        elif t == "stakeo":
            s = self.src[a[1]]; s["out"] -= 1; s["others"][a[2]] = now
        elif t == "sleaveo":
            self.src[a[1]]["others"][a[2]] = None
        elif t == "ltake":
            ln = self.lines[a[1]]; s = self.src[ln["src"]]
            if s["kind"] == "machine": s["out"] -= 1
            ln["cells"][0] = now
            self._got.add(("line", a[1]))
        elif t == "lmv":
            c = self.lines[a[1]]["cells"]; c[a[2] + 1] = now; c[a[2]] = None
        elif t == "lin":
            ln = self.lines[a[1]]; ln["cells"][-1] = None; self.xinp[ln["item"]] += 1
        elif t == "xtake":
            self.xout -= 1; self.xdown[a[1]] = now; self._got.add(("x", a[1]))
        elif t == "xleave":
            self.xdown[a[1]] = None

    def closure(self, dx, do, fixed=None):
        self._got = set()
        ready_x = [c is None for c in self.xdown]
        g = 0
        while True:
            A = self.enabled(dx, do)
            # 就绪：X 取货首格本刻某时点为空
            for j, c in enumerate(self.xdown):
                if c is None: ready_x[j] = True
            if not A: break
            if fixed is None:
                a = self.rng.choice(A)
            else:
                a = min(A, key=lambda z: fixed.get(z, (99, z)))
            self.apply(a); g += 1
            assert g < 200000
        return ready_x, self._got

    def key(self, ph):
        cap = lambda t: None if t is None else min(self.now - t, self.q)
        ks = (tuple(sorted(self.xinp.items())), None if self.xcache is None else max(self.xcache - self.now, 0), self.xout,
              tuple(cap(c) for c in self.xdown),
              tuple((s.get("out"), None if s.get("cache") is None else max(s["cache"] - self.now, 0),
                     tuple(cap(c) for c in s.get("others", []))) for s in self.src),
              tuple(tuple(cap(c) for c in ln["cells"]) for ln in self.lines), ph)
        return ks


CFGS = {
    "研磨机": {"recipe": {"P": 2, "S": 1}, "d": 1, "x_out_batch": 1, "x_outlets": 1,
             "channels": {"P": 2, "S": 1}, "source": "machine", "src_batch": {"P": 1, "S": 3}},
    "研磨机_荞花源": {"recipe": {"P": 2, "S": 1}, "d": 1, "x_out_batch": 1, "x_outlets": 1,
             "channels": {"P": 2, "S": 1}, "source": "machine", "src_batch": {"P": 2, "S": 3}},
    "封装机": {"recipe": {"Z": 10, "F": 15}, "d": 5, "x_out_batch": 1, "x_outlets": 1,
             "channels": {"Z": 2, "F": 3}, "source": "machine", "src_batch": {"Z": 1, "F": 1}},
    "精炼炉": {"recipe": {"O": 1}, "d": 1, "x_out_batch": 1, "x_outlets": 1,
             "channels": {"O": 1}, "source": "port", "src_batch": {}},
    "粉碎机砂叶出3": {"recipe": {"O": 1}, "d": 1, "x_out_batch": 3, "x_outlets": 3,
             "channels": {"O": 1}, "source": "machine", "src_batch": {"O": 1}},
}

def run(seed, cfgname):
    rng = random.Random(seed)
    q = rng.choice([1, 2, 3, 4])
    m = 50 if cfgname == "封装机" else rng.choice([3, 5, 8, 50])
    cfg = CFGS[cfgname]
    s = Sim(q, m, cfg, rng)
    # 随机合法起态：只放本线物品，相位任意
    for i in s.xinp: s.xinp[i] = rng.randint(0, min(m, 20))
    r = rng.random()
    s.xcache = None if r < 0.5 else rng.randint(1, cfg["d"] * q)
    s.xout = rng.randint(0, m - cfg["x_out_batch"])
    for j in range(len(s.xdown)):
        s.xdown[j] = -rng.randint(0, 2 * q) if rng.random() < 0.5 else None
    for src in s.src:
        if src["kind"] == "machine":
            src["out"] = rng.randint(0, m - src["k"])
            src["cache"] = rng.randint(1, q) if rng.random() < 0.7 else None
            for j in range(len(src["others"])):
                src["others"][j] = -rng.randint(0, 2 * q) if rng.random() < 0.5 else None
    for ln in s.lines:
        prev = -rng.randint(0, 2 * q)
        for i in range(len(ln["cells"]) - 1, -1, -1):   # 下游的货不比上游的新
            if rng.random() < 0.6:
                prev = prev + rng.randint(0, q)
                ln["cells"][i] = min(prev, 0)
            else:
                ln["cells"][i] = None
    nx = len(s.xdown)
    do_all = [[True] * len(src.get("others", [])) for src in s.src]
    s.closure([True] * nx, do_all)
    # 对手阶段
    for step in range(rng.choice([40, 120]) * q):
        s.now += 1
        dx = [rng.random() < 0.6 for _ in range(nx)]
        do = [[rng.random() < 0.5 for _ in src.get("others", [])] for src in s.src]
        s.closure(dx, do)
    # 固定阶段
    labels = {}
    per = rng.choice([1, 2, 3])
    phx = [rng.randrange(per * q) for _ in range(nx)]
    pho = [[rng.randrange(per * q) for _ in src.get("others", [])] for src in s.src]
    perm_seed = rng.random()
    class Order(dict):
        def get(self, a, default=None):
            return (hash((perm_seed, a)) % 100003, a)
    fixed = Order()
    seen = {}; hist = []
    for step in range(6000 * q):
        s.now += 1
        ph = s.now % (per * q)
        dx = [per == 1 or ph == phx[j] for j in range(nx)]
        do = [[per == 1 or ph == pho[si][j] for j in range(len(src.get("others", [])))] for si, src in enumerate(s.src)]
        ready, got = s.closure(dx, do, fixed)
        idle = s.xcache is None
        miss = any(ready[j] and ("x", j) not in got for j in range(nx)) if (cfg["d"] == 1 and nx <= cfg["x_out_batch"]) else False
        hist.append((idle, miss))
        k = s.key(ph)
        if k in seen:
            cyc = hist[seen[k] + 1:]
            return {"seed": seed, "cfg": cfgname, "q": q, "m": m, "cycle": True, "period": len(cyc),
                    "idle": sum(1 for h in cyc if h[0]), "miss": sum(1 for h in cyc if h[1])}
        seen[k] = len(hist) - 1
    return {"seed": seed, "cfg": cfgname, "q": q, "m": m, "cycle": False}

def main():
    w, n = int(sys.argv[1]), int(sys.argv[2])
    agg = {}; bad = []
    t0 = time.time()
    for c in range(n):
        name = list(CFGS)[c % len(CFGS)]
        r = run(w * 7919 + c, name)
        a = agg.setdefault(name, {"runs": 0, "cycles": 0, "cycles_q_gt1": 0, "idle_cycles": 0, "miss_cycles": 0})
        a["runs"] += 1
        if r["cycle"]:
            a["cycles"] += 1
            if r["q"] > 1: a["cycles_q_gt1"] += 1
            if r["idle"]: a["idle_cycles"] += 1; bad.append(r)
            if r["miss"]: a["miss_cycles"] += 1; bad.append(r)
    print(json.dumps({"worker": w, "agg": agg, "bad": bad[:10], "sec": round(time.time() - t0, 1)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
