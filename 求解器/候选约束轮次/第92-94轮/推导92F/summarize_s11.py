#!/usr/bin/env python3
"""汇总 s11_sim.py 的日志（run_s11_?.jsonl：协议核心 6 个取货端口记作一个单位；run_s11_52src_?.jsonl：52 个各算一个取货口）。"""
import glob, json, sys
from collections import defaultdict
def summ(pattern):
    rows = [json.loads(l) for f in sorted(glob.glob(pattern)) for l in open(f) if l.strip()]
    by = defaultdict(list)
    for r in rows: by[r['exp']].append(r)
    out = {}
    for e, rs in sorted(by.items()):
        d = dict(runs=len(rs), full_rate=sum(r['full_rate'] for r in rs),
                 BAT=sorted({r['window']['BAT'] for r in rs}), CAP=sorted({r['window']['CAP'] for r in rs}),
                 ore=[min(r['window']['ore_min'] for r in rs), max(r['window']['ore_max'] for r in rs)],
                 phi_margin_min=min(r['phi_margin_min_after_seeding'] for r in rs),
                 phi_margin_end_debug_min=min(r['phi_margin_at_end_of_debug'] for r in rs),
                 wrong_items_end=max(r['wrong_items_end'] for r in rs),
                 seeds=[min(r['seed'] for r in rs), max(r['seed'] for r in rs)])
        if e == 'E2':
            d['sweeps'] = [min(r['sweeps'] for r in rs), max(r['sweeps'] for r in rs)]
            d['removed'] = [min(r['removed'] for r in rs), max(r['removed'] for r in rs)]
        if e == 'E3':
            d['stop_ticks'] = [min((r['stop'][1]-r['stop'][0])/8 for r in rs), max((r['stop'][1]-r['stop'][0])/8 for r in rs)]
        if e == 'E4':
            d['offline_events'] = sum(r['offline_events'] for r in rs)
        out[e] = d
    return out
print(json.dumps({'核心6端口为一个单位': summ('run_s11_[0-9].jsonl'), '52个各算一个取货口': summ('run_s11_52src_*.jsonl')}, ensure_ascii=False, indent=1))
