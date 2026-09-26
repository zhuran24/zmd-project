"""三审：把 out/ 下各次求解回执汇总成 out/summary.json（只读回执，不重算）。"""
import glob
import json
import os

rows = []
for path in sorted(glob.glob('out/proj_*.json') + glob.glob('out/milp_*.json')):
    d = json.load(open(path))
    rows.append({k: d.get(k) for k in ['b', 'P', 'J', 'cap', 'status', 'message', 'engine', 'seconds', 'S', 'X', 'Y', 'Jval',
                                       'n_mach', 'n_core', 'n_poles']} | {'file': os.path.basename(path)})
local = {}
for name in ['wall_weight', 'wall_count', 'general_ge55', 'general_ge54']:
    p = f'out/{name}.json'
    if os.path.exists(p):
        d = json.load(open(p))
        local[name] = {k: d.get(k) for k in ['status', 'value', 'n_options', 'seconds']}
for name in ['highs_wall_count', 'highs_wall_weight', 'highs_general_ge55']:
    p = f'out/{name}.json'
    if os.path.exists(p):
        local[name] = json.loads(open(p).read().strip().splitlines()[-1])
strip = json.load(open('out/strip_b7.json'))['summary']
ore = {}
for name in ['ore_distance_cpsat_b7', 'ore_distance_highs_b7']:
    d = json.load(open(f'out/{name}.json'))
    ore[name] = {'arrangements': len(d), 'statuses': sorted({str(r['status']) for r in d})}
ore['min_sample'] = json.load(open('out/ore_distance_min_sample.json'))
grid = json.load(open('out/check_grid66.json'))
site = {}
for b in (6, 7, 9, 17):
    d = json.load(open(f'out/site_power_b{b}.json'))
    site[b] = {'positions': len(d), 'all_optimal': all(v['status'] == 'OPTIMAL' for v in d.values())}
json.dump(dict(projection_runs=rows, local_pole=local, strip_b7=strip, ore_distance=ore, grid66=grid, site_power=site),
          open('out/summary.json', 'w'), ensure_ascii=False, indent=1)
print(len(rows), 'runs')
for r in rows:
    print(r['file'], r['status'], r['seconds'])
