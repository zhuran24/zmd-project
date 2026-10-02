#!/usr/bin/env python3
"""读法敏感性：数层若按别的读法，同一张接法会掉速。不扰动、一次建造，跑 9000 步，量后 4000 步（500 tick）。
axis：按轴、逆向往返不参与数层（推导与本复核采用的读法）；
cross：送往的桥接器另一轴也可用来数层（字面扩大读法，层数随接通先后可取最小）；
rev_undet：同轴相邻桥串层数“无法确定”，取其中一种（相邻桥串上游先判）。"""
import json
import sys

from engine_x import Factory, FINISHED

res = []
for mode in ('axis', 'cross', 'rev_undet'):
    for seed in (109301, 109302):
        f = Factory(seed, 'bridge', 6, pbridge=0.8, layer_mode=mode)
        for _ in range(5000):
            f.step()
        d0 = dict(f.delivered); o0 = list(f.oresent)
        for _ in range(4000):
            f.step()
        dl = {k: f.delivered[k] - d0[k] for k in FINISHED}
        ore = [f.oresent[p] - o0[p] for p in range(len(f.P)) if f.P[p][0] == 'CORE' or f.P[p][0].startswith('PORT')]
        res.append({'mode': mode, 'seed': seed, 'delivered_500tick': dl, 'need': {'高容谷地电池': 300, '精选荞愈胶囊': 275},
                    'ore_total_500tick': sum(ore), 'ore_need': 52 * 500, 'ore_min_path': min(ore)})
        print(json.dumps(res[-1], ensure_ascii=False), flush=True)
json.dump(res, open('sensitivity.json', 'w'), ensure_ascii=False, indent=1)
