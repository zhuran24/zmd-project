#!/usr/bin/env python3
"""Collect every 98S3 run file into summary.json (counts used in the report)."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent

def load(p):
    d = json.loads(p.read_text())
    if isinstance(d, dict) and 'cases' in d:
        return d['cases']
    if isinstance(d, dict) and 'per_round' in d:
        c = dict(d['final_cycle'])
        c['release'] = sum(r['stop'] + r['gap'] for r in d['per_round'])
        return [c]
    return d

groups = {}
for p in sorted(HERE.glob('*.json')):
    if p.name in ('summary.json', 'offsets.json', 'crosscheck.json', 'drain_cross.json', 'stall_times.json') or p.name.startswith('cross_'):
        continue
    cases = load(p)
    ok = 0; bad = 0; nocyc = 0; periods = set(); starts = []
    for c in cases:
        flag = c.get('ok', c.get('pass_rates'))
        if flag is None:
            nocyc += 1
        elif flag:
            ok += 1
        else:
            bad += 1
        per = c.get('period')
        if per:
            periods.add(per)
        s = c.get('start', c.get('cycle_start'))
        if isinstance(s, int):
            if 'trace' in c:
                s -= sum(x[1] + x[2] for x in c['trace'])
            elif 'release' in c:
                s -= c['release']
            starts.append(s)
    groups[p.name] = dict(cases=len(cases), full_rate_cycles=ok, deficit_cycles=bad, no_cycle=nocyc,
                          periods=sorted(periods), latest_cycle_start=max(starts) if starts else None,
                          note='disturb files: cycle start counted from the end of the last round')
tot = dict(cases=sum(g['cases'] for g in groups.values()),
           full_rate_cycles=sum(g['full_rate_cycles'] for g in groups.values()),
           deficit_cycles=sum(g['deficit_cycles'] for g in groups.values()),
           no_cycle=sum(g['no_cycle'] for g in groups.values()))
cross = {}
for p in sorted(HERE.glob('cross_*.json')):
    cs = json.loads(p.read_text())
    cross[p.name] = dict(cases=len(cs), agree_full_rate=sum(1 for c in cs if c.get('ok')),
                         compared_steps=sum(c.get('compared_steps', 0) for c in cs))
dc = HERE / 'drain_cross.json'
if dc.exists():
    d = json.loads(dc.read_text())
    cross['drain_cross.json'] = dict(rounds=d['rounds'], compared_steps=d['compared_steps'],
                                     low_gf16_engineB_first_last=[d['low_gf16_engineB'][0], d['low_gf16_engineB'][-1]])
out = dict(groups=groups, total=tot, crosscheck=cross)
(HERE / 'summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
print(json.dumps(out, ensure_ascii=False, indent=1))
