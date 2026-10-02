"""Independent integer batch-capacity and modular-window calculation."""
import json
from pathlib import Path

root=Path(__file__).resolve().parent
# Actual required minimum batches in 20 ticks; 1-tick or 5-tick batch capacities.
names=['粉碎机','精炼炉','研磨机','塑形机','配件机','种植机','采种机','封装机','灌装机']
required=[1360,1020,630,110,120,640,320,12,11]
capacity=[20,20,20,20,20,20,20,4,4]
counts={name:next(n for n in range(100) if n*cap>=need) for name,need,cap in zip(names,required,capacity)}
ports={f'{a}+{b}':next(n for n in range(5) if 2*n>=a+b) for a,b in [(3,2),(3,1),(2,1),(2,2)]}
per_inlet=max(sum(0<=t<=40 for t in range(phase-80,81,8)) for phase in range(8))
# Arbitrary eight possible machine phase classes: each contributes two events to
# each half-open interval of length sixteen steps. All 32-machine phase choices
# then have sixty-four completions, without enumerating 8**32 assignments.
window_counts={phase:sum(0<t<=16 for t in range(phase-80,81,8)) for phase in range(8)}
assert set(window_counts.values())=={2}
out={'machine_minima':counts,'alternation_min_ports':ports,
     'plant_total_pointwise_each':32*min(window_counts.values()),
     'plant_species_mean_each':{'荞花':220*16//160,'砂叶':420*16//160},
     'inclusive_5_tick_per_inlet':per_inlet,'box_bound':sum([per_inlet]*3)}
reference=json.loads((root/'clearing_check_fraction.json').read_text())
assert out==reference,(out,reference)
(root/'clearing_check_integer.json').write_text(json.dumps({'result':out,'window_counts_by_phase':window_counts,'matches_fraction':True},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'matches_fraction':True,'result':out},ensure_ascii=False,sort_keys=True))
