#!/usr/bin/env python3
"""汇总 out/ 下的模拟输出，写 out/summary.json。"""
import glob
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'out'


def main():
    unit = {}
    for kind, pat in (('normal', 'unit_[0-9].json'), ('edge', 'unit_edge_*.json')):
        acc = {}
        for f in sorted(glob.glob(str(OUT / pat))):
            r = json.loads(Path(f).read_text())
            for k, v in r.items():
                if k in ('seed', 'n', 'edge'):
                    continue
                if isinstance(v, list):
                    acc[k] = [a + b for a, b in zip(acc.get(k, [0] * len(v)), v)]
                else:
                    acc[k] = acc.get(k, 0) + v
        unit[kind] = acc
    rows = [json.loads(l) for f in sorted(glob.glob(str(OUT / 'factory_[0-9b]*.jsonl'))) for l in open(f)]
    cyc = [r for r in rows if r.get('cycle')]
    good = [r for r in cyc if r['batt_ok'] and r['caps_ok'] and r['ore_ok'] and r['viol_m'] == 0
            and r['viol_c'] == 0 and r['max_bottle'] <= 11 and r['max_steel6'] <= 3]
    fac = dict(runs=len(rows), cycles=len(cyc), no_cycle=sum(1 for r in rows if r.get('cycle') is False),
               skipped=sum(1 for r in rows if r.get('skipped')), all_checks_pass=len(good),
               Q=sorted({r['Q'] for r in cyc}), periods=sorted({r['per'] for r in cyc}),
               multi_phase=sum(1 for r in cyc if r['phases'] > 1), max_bottle=max(r['max_bottle'] for r in cyc),
               max_steel6=max(r['max_steel6'] for r in cyc), max_transient=max(r['transient'] for r in cyc),
               stops=sum(r['nstop'] for r in cyc), events=sum(r['events'] for r in cyc),
               counts=cyc[0]['counts'])
    ctl = [json.loads(l) for f in sorted(glob.glob(str(OUT / 'factory_control_*.jsonl'))) for l in open(f)]
    cc = [r for r in ctl if r.get('cycle')]
    control = dict(runs=len(ctl), cycles=len(cc), below_target=sum(1 for r in cc if not (r['batt_ok'] and r['caps_ok'])),
                   empty_hand_detected=sum(1 for r in cc if r['viol_m'] > 0),
                   rates=[[str(r['batt']) + '/' + str(r['per']), str(r['caps']) + '/' + str(r['per'])] for r in cc])
    relay = {}
    for kind, pat in (('normal', 'relay_[0-9].json'), ('few_lines', 'relay_control_few.json'), ('extra_exit', 'relay_control_extra.json')):
        acc = {}
        for f in sorted(glob.glob(str(OUT / pat))):
            r = json.loads(Path(f).read_text())
            for k, v in r.items():
                if k in ('seed', 'control'):
                    continue
                if isinstance(v, dict):
                    d = acc.setdefault(k, {})
                    for kk, vv in v.items():
                        d[kk] = d.get(kk, 0) + vv
                else:
                    acc[k] = acc.get(k, 0) + v
        relay[kind] = acc
    other = {'relay': relay}
    for name in ('shutdown_check', 'transfer_defects'):
        p = OUT / (name + '.json')
        if p.exists():
            other[name] = json.loads(p.read_text())
    s = dict(unit=unit, factory=fac, factory_control=control, **other)
    (OUT / 'summary.json').write_text(json.dumps(s, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps(s, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
