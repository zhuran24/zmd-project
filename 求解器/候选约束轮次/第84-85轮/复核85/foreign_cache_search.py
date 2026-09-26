#!/usr/bin/env python3
"""复核85：随机起态＋C 缓存格里一批另一种植物，找 Φ0≥S+1/2 而循环态里 C 空手的例子（整数 tick）。"""
import random, json, sys
from pathlib import Path
import foreign_cache_sim as F
HERE = Path(__file__).resolve().parent

def rand_unit(seed):
    rng = random.Random(seed)
    m = rng.choice([3, 4, 5, 6, 8]); L = rng.randint(1, 3); kk = rng.choice([2, 3])
    u = F.Unit(m, L, L, L, L, kk, rng)
    Qs, Qp = "荞花·种子", "荞花·植株"
    for cells, kind in ((u.P["CA"], Qs), (u.P["AC"], Qp), (u.P["CB"], Qs), (u.P["BK"], Qp)):
        for i in range(L):
            if rng.random() < 0.5: cells[i] = (kind, -1)
    for n, kind in (("C", Qp), ("A", Qs), ("B", Qs), ("K", Qp)):
        for _ in range(rng.randint(0, 2)): u.inp[n].put(kind)
    for n, kind in (("A", Qp), ("B", Qp)):
        for _ in range(rng.randint(0, 2)): u.out[n].put(kind)
    for _ in range(rng.randint(1, 3)): u.out["C"].put(Qs)
    u.cache["C"] = ("砂叶·种子", 2, 0)
    return u, m, L

def main():
    w, n = int(sys.argv[1]), int(sys.argv[2])
    found = []; stats = {"runs": 0, "applicable": 0, "cycles": 0, "idle_cycles": 0}
    for c in range(n):
        seed = w * 100003 + c
        u, m, L = rand_unit(seed)
        u.closure()
        phi0 = u.phi2(); S = 2 * L + 2
        stats["runs"] += 1
        if phi0 < 2 * S + 1: continue
        stats["applicable"] += 1
        seen = {}; hist = []
        for t in range(6000):
            u.now += 1; u.closure()
            hist.append((u.cache["C"] is None, u.phi2()))
            k = u.key()
            if k in seen:
                cyc = hist[seen[k] + 1:]
                stats["cycles"] += 1
                idle = sum(1 for h in cyc if h[0])
                if idle:
                    stats["idle_cycles"] += 1
                    if len(found) < 5:
                        found.append({"seed": seed, "m": m, "L": L, "phi0": phi0 / 2, "S": S, "idle": idle, "period": len(cyc),
                                      "phi_cycle": min(h[1] for h in cyc) / 2})
                break
            seen[k] = len(hist) - 1
    print(json.dumps({"worker": w, "stats": stats, "found": found}, ensure_ascii=False))

if __name__ == "__main__":
    main()
