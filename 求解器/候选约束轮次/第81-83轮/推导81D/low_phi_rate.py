#!/usr/bin/env python3
"""旁证：K 下游每刻全收、Φ 小于 S 的循环态里，K 的批率是否恰为 Φ/S（说明阈值 S 不能再降）。"""
import json, random, sys
sys.path.insert(0, '.')
from cell_sweep_sim import run_case
rng = random.Random(777)
rows = []
for r in range(1500):
    m = rng.choice([50, 6, 9])
    L = [rng.randint(1, 8) for _ in range(4)]
    k = rng.choice([2, 3])
    res = run_case(900000 + r, m, *L, k, rng.choice([50, 300]), 0.0, rng.choice([0.0, 0.3]), rng.choice([5, 50]))
    cy = res.get('cycle')
    if cy and cy['phi_min'] < res['S']:
        rows.append((cy['phi_min'], cy['phi_max'], res['S'], cy['k_rate'],
                     abs(cy['k_rate'] - cy['phi_min'] / res['S']) < 1e-9))
print(json.dumps(dict(low_cycles=len(rows), rate_equals_phi_over_S=sum(1 for x in rows if x[4]),
                      phi_constant=sum(1 for x in rows if x[0] == x[1]),
                      counter=[x for x in rows if not x[4]][:10]), ensure_ascii=False, indent=1))
