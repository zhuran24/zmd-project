#!/usr/bin/env python3
"""Independent exact-Fraction reconstruction from supplied logs only.

Inputs are transcribed from:
- probes/rate_table_stdout.log lines 31-69 (full-rate port coefficients inferred as rate/duty)
- refute_round1/split_free_probe_v2_stdout.log lines 4-20 and 54-60 (counts and staircase duties)
No project source data or OR-Tools is used.
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction as F
from math import ceil

OPS = {
    "crusher_blue_iron": (34, [F(1)]*34, {"blue_iron_block":F(1)}, {"blue_iron_powder":F(1)}),
    "crusher_buckwheat": (6, [F(1)]*5+[F(1,2)], {"buckwheat":F(1)}, {"buckwheat_powder":F(2)}),
    "crusher_sandleaf": (11, [F(1)]*10+[F(1,2)], {"sandleaf":F(1)}, {"sandleaf_powder":F(3)}),
    "crusher_source": (18, [F(1)]*18, {"source_ore":F(1)}, {"source_powder":F(1)}),
    "filling_capsule": (3, [F(1),F(1),F(3,4)], {"fine_buckwheat_powder":F(2),"steel_bottle":F(2)}, {"qiaoyu_capsule":F(1,5)}),
    "grinder_dense_blue_iron": (17, [F(1)]*17, {"blue_iron_powder":F(2),"sandleaf_powder":F(1)}, {"dense_blue_iron_powder":F(1)}),
    "grinder_dense_source": (9, [F(1)]*9, {"sandleaf_powder":F(1),"source_powder":F(2)}, {"dense_source_powder":F(1)}),
    "grinder_fine_buckwheat": (6, [F(1)]*5+[F(1,2)], {"buckwheat_powder":F(2),"sandleaf_powder":F(1)}, {"fine_buckwheat_powder":F(1)}),
    "molding_bottle": (6, [F(1)]*5+[F(1,2)], {"steel_block":F(2)}, {"steel_bottle":F(1)}),
    "packaging_battery": (3, [F(1)]*3, {"dense_source_powder":F(3),"steel_part":F(2)}, {"valley_battery":F(1,5)}),
    "parts_maker": (6, [F(1)]*6, {"steel_block":F(1)}, {"steel_part":F(1)}),
    "planter_buckwheat": (11, [F(1)]*11, {"buckwheat_seed":F(1)}, {"buckwheat":F(1)}),
    "planter_sandleaf": (21, [F(1)]*21, {"sandleaf_seed":F(1)}, {"sandleaf":F(1)}),
    "refinery_blue_iron": (34, [F(1)]*34, {"blue_iron_ore":F(1)}, {"blue_iron_block":F(1)}),
    "refinery_steel": (17, [F(1)]*17, {"dense_blue_iron_powder":F(1)}, {"steel_block":F(1)}),
    "seed_collector_buckwheat": (6, [F(1)]*5+[F(1,2)], {"buckwheat":F(1)}, {"buckwheat_seed":F(2)}),
    "seed_collector_sandleaf": (11, [F(1)]*10+[F(1,2)], {"sandleaf":F(1)}, {"sandleaf_seed":F(2)}),
}
EXTERNAL = {"blue_iron_ore":34, "source_ore":18}
FINAL = {"qiaoyu_capsule", "valley_battery"}


def lanes(rate: F) -> list[F]:
    if rate == 0: return []
    n = ceil(rate)
    return [F(1)]*(n-1)+[rate-(n-1)]


def exact_partition(producers: list[F], consumers: list[F]) -> bool:
    """Can each producer lane be assigned whole to exactly one consumer bin?"""
    ps = sorted(producers, reverse=True)
    caps = sorted(consumers, reverse=True)
    if sum(ps) != sum(caps) or len(ps) < len(caps): return False
    def rec(i: int) -> bool:
        if i == len(ps): return all(c == 0 for c in caps)
        x = ps[i]
        tried = set()
        for j,c in enumerate(caps):
            if c >= x and c not in tried:
                tried.add(c); caps[j] -= x
                if rec(i+1): return True
                caps[j] += x
        return False
    return rec(0)

P=defaultdict(list); Q=defaultdict(list)
manufacturing_slots=0
for op,(n,ds,ins,outs) in OPS.items():
    assert n == len(ds)
    for i,d in enumerate(ds):
        for k,c in ins.items():
            ls=lanes(c*d); Q[k] += ls; manufacturing_slots += len(ls)
        for k,c in outs.items():
            ls=lanes(c*d); P[k] += ls; manufacturing_slots += len(ls)
for k,n in EXTERNAL.items(): P[k] += [F(1)]*n
for k in FINAL: Q[k] = lanes(sum(P[k]))

commodities=sorted(set(P)|set(Q))
ok=[]; bad=[]
print(f"manufacturing_port_slots={manufacturing_slots}")
print(f"all_endpoint_slots_including_52_sources_and_2_final_sinks={manufacturing_slots+52+2}")
for k in commodities:
    assert sum(P[k]) == sum(Q[k]), (k,sum(P[k]),sum(Q[k]))
    sf=exact_partition(P[k],Q[k])
    (ok if sf else bad).append(k)
    rates=sorted(set(P[k]+Q[k]))
    print(f"{k:24s} P={len(P[k]):2d} Q={len(Q[k]):2d} split_free={str(sf):5s} rates={','.join(map(str,rates))}")
print(f"split_free_count={len(ok)}/{len(commodities)}")
print("not_split_free="+",".join(bad))
print("qiaoyu_producer_rates="+",".join(map(str,P['qiaoyu_capsule']))+f" merged={Q['qiaoyu_capsule'][0]}")
print("valley_producer_rates="+",".join(map(str,P['valley_battery']))+f" merged={Q['valley_battery'][0]}")
