from itertools import combinations, combinations_with_replacement
from functools import cache
from math import ceil
from pathlib import Path
from collections import Counter
import json

# 边长、基准台数、单台吞吐上限、需要的整件吞吐容量
specs = [(3,68,3,95),(6,32,3,95),(3,6,2,11),(6,3,4,11),(6,3,5,15)]
area = [9,24,9,24,24,9,9,25,25]

@cache
def gaps(spec, extra):
    width, base, cap, demand = specs[spec]
    options = []
    for k in range(width+1):
        charge = min(2*sum(b-a<=3 for a,b in zip(seq,seq[1:]))
                     for seq in combinations(range(width),k))
        options.append((min(k,cap),charge))
    best = {0:0}
    for _ in range(base+extra):
        later = {}
        for have,total in best.items():
            for throughput,charge in options:
                key = min(demand,have+throughput)
                later[key] = min(later.get(key,10000),total+charge)
        best=later
    return best[demand]

print('各类成本', [[gaps(i,j) for i in range(5)] for j in range(3)])
for cnt in range(3):
    totals = []
    for added in combinations_with_replacement(range(9),cnt):
        cost = sum(gaps(i,added.count(i)) for i in range(5))
        for eta in range(4):
            for extra_gap in [0,3]:
                combined = sum(area[i] for i in added) + ceil((718+eta+cost/2+extra_gap)/4)
                totals.append(combined-ceil((800+eta+extra_gap)/4))
    print('增机数、核对项数、最小富余',cnt,len(totals), min(totals))
    assert min(totals)>=0
out=Path('求解器/候选约束轮次/三审-第63-80轮/out')
expected={(k,0) for k in range(0,70,3)}|{(0,k) for k in range(0,70,3)}
for name in ('highs','cpsat'):
    results=json.loads((out/f'ore_distance_{name}_b7.json').read_text())
    print(name,len(results), Counter(i['status'] for i in results), sorted({i['eL'] for i in results})[:4])
    assert {(i['eL'],i['eB']) for i in results}==expected
