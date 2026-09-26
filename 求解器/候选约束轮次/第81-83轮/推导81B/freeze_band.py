#!/usr/bin/env python3
"""第81轮B 线索三：双料机器开批时 Z=b·x_A−a·x_B 的区间，及按配方比例到件冻结时是否仍够一批。"""
import json, os
from pathlib import Path
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
HERE = Path(__file__).resolve().parent

def band(a, b):
    zs = [b * xa - a * xb for xa in range(a, 51) for xb in range(b, 51)]
    lo, hi = min(zs), max(zs)
    ok = True
    for xa in range(0, 51):
        for xb in range(0, 51):
            z = b * xa - a * xb
            if not (lo <= z <= hi):
                continue
            t = min((50 - xa) / a, (50 - xb) / b)  # 按比例连续到件，先满的一格满 50
            if xa + a * t < a - 1e-9 or xb + b * t < b - 1e-9:
                ok = False
    return lo, hi, ok

r = {'封装机(10,15)': band(10, 15), '灌装机(10,10)': band(10, 10), '研磨机(2,1)': band(2, 1)}
print(r)
json.dump({k: dict(z_min=v[0], z_max=v[1], ratio_freeze_safe=v[2]) for k, v in r.items()},
          open(HERE / 'freeze_band.json', 'w'), ensure_ascii=False, indent=1)
