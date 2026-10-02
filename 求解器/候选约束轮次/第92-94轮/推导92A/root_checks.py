#!/usr/bin/env python3
"""Two independent finite checks of arithmetic used by the root audit.

These are interval/clock certificates, not layout simulators.
"""
from fractions import Fraction
from itertools import combinations
from pathlib import Path
import json

out = Path(__file__).resolve().parent
steps_a = int(Fraction(5) / Fraction(1, 8))
t, steps_b = Fraction(0), 0
while t < 5:
    t += Fraction(1, 8)
    steps_b += 1
assert t == 5 and steps_a == steps_b == 40
phases_a = {n % steps_a for n in range(steps_a * 3)}
phases_b = set()
clock = 0
for _ in range(steps_b):
    phases_b.add(clock)
    clock = (clock + 1) % steps_b
assert phases_a == phases_b

# At most one success at a port in an eight-step half-open interval.
# Encoding A exhausts all subsets of the eight later observation steps.
allowed_a = []
for mask in range(1 << 8):
    times = [i+1 for i in range(8) if mask & (1 << i)]
    if all(b-a >= 8 for a, b in zip(times, times[1:])):
        allowed_a.append(times)
max_a = max(map(len, allowed_a))
# Encoding B uses extremal first/last positions, separately from subsets.
feasible_sizes_b = [n for n in range(9) if n == 0 or 1 + (n-1)*8 <= 8]
max_b = max(feasible_sizes_b)
assert max_a == max_b == 1
limits = [{'accepting_ports': c, 'max_removable_in_next_8_steps': c*max_a,
           'blocking_head_stock': c*max_b+1} for c in range(3)]
data = {'status': 'PASS', 'scope': 'clock and residence arithmetic only',
        'transfer_period_steps_two_encodings': [steps_a, steps_b],
        'phase_count_two_encodings': [len(phases_a), len(phases_b)],
        'single_port_next_8_steps_max_two_encodings': [max_a, max_b],
        'N56_head_stock_contradiction': limits}
(out/'root_checks.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(data, ensure_ascii=False))
