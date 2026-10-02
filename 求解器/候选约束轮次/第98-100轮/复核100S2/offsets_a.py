#!/usr/bin/env python3
"""复核100S2：在引擎甲的循环态里直接读出第6.4节的开批偏移（以 P1 的开批步为 t）。"""
import json, random
from engine_a import run_case
r = run_case(11, maxlen=5, history='mix', disturb=True)
f = r['f']
p = r['period']
names = ['P1', 'P2', 'O1', 'O2', 'O3', 'R1', 'R2', 'B1', 'B2', '铁碎1', '铁碎2', '炼1', '源碎1', '源碎2', '源碎6',
         'H1', 'H2', 'Q1', 'Q2', 'R7', 'B7', 'B10', 'H5', 'Q5', 'R15', 'B15', 'H6', 'Q6', 'R17', 'B17']
starts = {n: [] for n in names}
core_sends = []
ksends = {k: [] for k in ('砂1K', '砂8K', '砂11K', '荞1K')}
t0 = f.t
for _ in range(p):
    before = {n: f.mach[n].cache for n in names}
    lastk = {k: dict(f.mach[k].last) for k in ksends}
    lastc = dict(f.src['核心'].last)
    f.step()
    for n in names:
        c = f.mach[n].cache
        if c is not None and c[0] == 'run' and c[1] == f.t - 1 + f.mach[n].dur:
            starts[n].append(f.t - 1 - t0)
    for k in ksends:
        if f.mach[k].last != lastk[k]:
            ksends[k].append(f.t - 1 - t0)
    if f.src['核心'].last != lastc:
        core_sends.append(f.t - 1 - t0)
base = starts['P1']
def rel(xs):
    # 每个开批步相对于不晚于它的最近一个 P1 开批步
    out = []
    for x in xs:
        b = max([y for y in base if y <= x], default=None)
        out.append(None if b is None else x - b)
    return sorted(set(o for o in out if o is not None))
res = dict(period=p, P1_gaps=sorted(set(b - a for a, b in zip(base, base[1:]))),
           offsets_vs_P1={n: rel(starts[n]) for n in names[:15]},
           core_send_offsets_vs_P1=rel(core_sends),
           K_send_offsets_vs_P1={k: rel(v) for k, v in ksends.items() if k == '砂1K'},
           F1_group_note='H1、Q1 应与本组 F1 拉取同列；以 H1 为基准另算',
           )
baseH = starts['H1']
def relH(xs, base):
    out = []
    for x in xs:
        b = max([y for y in base if y <= x], default=None)
        out.append(None if b is None else x - b)
    return sorted(set(o for o in out if o is not None))
res['offsets_vs_H1'] = {n: relH(starts[n], baseH) for n in ['H2', 'Q1', 'Q2', 'R7', 'B7', 'B10']}
res['offsets_vs_H5'] = {n: relH(starts[n], starts['H5']) for n in ['Q5', 'R15', 'B15']}
res['offsets_vs_H6'] = {n: relH(starts[n], starts['H6']) for n in ['Q6', 'R17', 'B17']}
res['H6_start_gaps'] = sorted(set(b - a for a, b in zip(starts['H6'], starts['H6'][1:])))
res['H5_start_gaps'] = sorted(set(b - a for a, b in zip(starts['H5'], starts['H5'][1:])))
json.dump(res, open('offsets_a.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False))
