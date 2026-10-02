#!/usr/bin/env python3
"""复核100S2：引擎甲整厂批量运行。用法 run_a.py START COUNT [age_reset]"""
import sys, json, time
from engine_a import run_case

def multi_out_paths(f):
    srcs = {}
    for b in f.belts:
        srcs.setdefault(b.src, []).append(b)
    keep = []
    for s, bs in srcs.items():
        if len(bs) > 1 and (s == '核心' or (s.endswith('K'))):
            keep.extend(bs)
    return keep

def main():
    start, count = int(sys.argv[1]), int(sys.argv[2])
    age_reset = len(sys.argv) > 3 and sys.argv[3] == 'age_reset'
    out = []
    for seed in range(start, start + count):
        hist = ['clear', 'keep', 'mix'][seed % 3]
        maxlen = [1, 2, 4, 8, 16][seed % 5]
        t0 = time.time()
        r = run_case(seed, maxlen=maxlen, history=hist, disturb=True, age_reset=age_reset,
                     extra_offline=6 + seed % 5, stops=4 + seed % 4)
        f = r.pop('f', None)
        rec = dict(seed=seed, history=hist, maxlen=maxlen, age_reset=age_reset,
                   period=r.get('period'), cycle_start=r.get('cycle_start'),
                   battery=r.get('battery'), capsule=r.get('capsule'),
                   nviol=r.get('nviol'), viol=[list(map(str, v)) for v in r.get('violations', [])[:5]],
                   events=r.get('events'), secs=round(time.time() - t0, 1))
        if f is not None and r.get('period'):
            p = r['period']
            ore = [r['ore'][b.idx] for b in f.belts if b.src in f.src]
            rec['ore_set'] = sorted(set(ore))
            rec['ore_paths'] = len(ore)
            rec['rate_bat'] = f"{r['battery']}/{p}*8"
            rec['bat_per_tick_x100'] = round(100 * r['battery'] * 8 / p, 4)
            rec['cap_per_tick_x100'] = round(100 * r['capsule'] * 8 / p, 4)
            rec['ore_per_tick'] = sorted(set(round(x * 8 / p, 6) for x in ore))
            mo = multi_out_paths(f)
            rec['multi_out_paths'] = len(mo)
            rec['multi_out_rej'] = sum(r['rej'][b.idx] for b in mo)
        out.append(rec)
        print(json.dumps(rec, ensure_ascii=False), flush=True)
    return out

if __name__ == '__main__':
    main()
