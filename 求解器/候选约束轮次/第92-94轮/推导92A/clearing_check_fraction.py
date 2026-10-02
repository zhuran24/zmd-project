"""Exact arithmetic and spacing certificate for N20/N41/N43/N48; one process."""
from fractions import Fraction as F
import json
from pathlib import Path

root = Path(__file__).resolve().parent
names = ['粉碎机','精炼炉','研磨机','塑形机','配件机','种植机','采种机','封装机','灌装机']
rates = [F(68),F(51),F(63,2),F(11,2),F(6),F(32),F(16),F(3,5),F(11,20)]
durations = [1,1,1,1,1,1,1,5,5]
ceil = lambda f: -(-f.numerator // f.denominator)
counts = {name:ceil(rate*duration) for name,rate,duration in zip(names,rates,durations)}

# Max count of events on integer steps 0..40, successive events >=8 apart.
best = [0] * 49
for end in range(41):
    best[end+8] = max(best[end+7], 1+best[end])
spacing = best[48]

out = {
    'machine_minima': counts,
    'alternation_min_ports': {f'{a}+{b}':ceil(F(a+b,2)) for a,b in [(3,2),(3,1),(2,1),(2,2)]},
    'plant_total_pointwise_each':32*2,
    'plant_species_mean_each':{'荞花':F(11)*2,'砂叶':F(21)*2},
    'inclusive_5_tick_per_inlet':spacing,
    'box_bound':3*spacing,
}
out['plant_species_mean_each'] = {k:int(v) for k,v in out['plant_species_mean_each'].items()}
assert list(counts.values()) == [68,51,32,6,6,32,16,3,3]
assert spacing == 6
(root/'clearing_check_fraction.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,sort_keys=True))
