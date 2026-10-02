#!/usr/bin/env python3
"""Independent integer checks for 92E throughput lemmas; no full-layout simulator."""
from fractions import Fraction as F
from math import ceil
from itertools import product
from pathlib import Path
import json

out = Path(__file__).resolve().parent
# Encoding A: closed bound from c-channel recurrence.
packing_a = {(c,q):8*((q-1)//c)+(q-1)%c+1 for c in range(1,7) for q in range(1,41)}
# Encoding B: exact dynamic program on the previous seven send/no-send bits.
# Each 8-step window has <=c events. This is equivalent to assigning the events
# to c channels with separation >=8: intervals [t,t+8) form an interval graph.
packing_b = {}
for c in range(1,7):
    states = {0:0}
    t = 0
    while len([key for key in packing_b if key[0] == c]) < 40:
        t += 1
        new = {}
        for mask,number in states.items():
            for bit in (0,1):
                if bit and mask.bit_count() >= c:
                    continue
                next_mask = ((mask << 1) | bit) & 127
                new[next_mask] = max(new.get(next_mask,-1),number+bit)
        states = new
        reached = max(states.values())
        for q in range(1,min(40,reached)+1):
            packing_b.setdefault((c,q),t)
assert packing_a == packing_b
# Encoding A: rational recipe balance from rates.
battery, capsule = F(3,5), F(11,20)
steel = 10*battery+20*capsule
mill_batches = steel+15*battery+10*capsule
seed_batches = mill_batches/3+10*capsule
assert (steel,mill_batches,seed_batches) == (F(17),F(63,2),F(16))
# Encoding B: integer recipe expansion over 20 ticks.
battery_count,capsule_count = 12,11
steel_count = battery_count*10 + capsule_count*10*2
mill_count = steel_count + battery_count*15 + capsule_count*10
seed_count = mill_count//3 + (capsule_count*10*2)//2
assert (steel_count,mill_count,seed_count) == (340,630,320)
assert (F(steel_count,20),F(mill_count,20),F(seed_count,20)) == (steel,mill_batches,seed_batches)
# Restricted seeders: capacity 8/9; count bound >=18.
seeder_n_a = min(n for n in range(1,40) if n*F(8,9) >= seed_batches)
seeder_n_b = next(n for n in range(1,40) if 8*n*20 >= 9*seed_count)
assert seeder_n_a == seeder_n_b == 18
# Restricted alternating grinders among 32: at most4.
grinder_a = max(a for a in range(33) if 32-a+a*F(8,9) >= mill_batches)
grinder_b = max(a for a in range(33) if 18*32-2*a >= 567)
assert grinder_a == grinder_b == 4
switch_bound_a = 8*(32-mill_batches)
switch_bound_b = F(32*160-8*mill_count,20)
assert switch_bound_a == switch_bound_b == 4
# A separate event schedule realizes the 18-step output word locally, with
# one channel per kind. This is a scheduler witness, NOT a plant/layout claim.
word = 'AABB'*20
last = {'A':-8,'B':-8}
events=[]
t=0
for kind in word:
    while t-last[kind] < 8:
        t+=1
    events.append((t,kind))
    last[kind]=t
    t+=1
assert [events[4*j][0] for j in range(20)] == [18*j for j in range(20)]
# Independent finite check of the full-speed two-channel species balancing:
# arbitrary binary recipe cycles of length1..10; k=2 per batch; both choices
# of first channel. Each cyclic species run has an even number of events.
equal_cases=0
for batches in range(1,11):
    for recipes in product((0,1),repeat=batches):
        items=[kind for kind in recipes for _ in range(2)]
        for offset in (0,1):
            count=[[0,0],[0,0]]
            for j,kind in enumerate(items):
                count[kind][(j+offset)%2]+=1
            assert all(a==b for a,b in count)
            equal_cases+=1
result={
 'status':'PASS',
 'scope':'arithmetic and local discrete output schedules; not a layout simulator',
 'packing_independent_cases':len(packing_a),
 'packing_max_q':40,
 'recipe_rates':{'steel':str(steel),'grinder':str(mill_batches),'seeder':str(seed_batches)},
 'integer_20_tick_counts':{'steel':steel_count,'grinder':mill_count,'seeder':seed_count},
 'restricted_all_seeders_minimum':seeder_n_a,
 'restricted_alternating_grinders_among_32_maximum':grinder_a,
 'one_channel_grinder_switches_per_tick_at_32_maximum':str(switch_bound_a),
 'local_AABB_first_events':events[:16],
 'two_channel_species_balance_cases':equal_cases,
 'packing_table':[{'channels':c,'items':q,'minimum_steps':packing_a[(c,q)]} for c in range(1,7) for q in range(1,41)],
}
(out/'check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='packing_table'},ensure_ascii=False,indent=2))
