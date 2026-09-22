"""Exact small-network check of lower-bound cuts and integer max-flow reduction.
No factory model or solver-performance claim. Uses only Python integers.
"""
from itertools import product
from collections import deque
from pathlib import Path
import json, random


def enumerated_feasible(n, arcs, demand):
    # demand = incoming - outgoing
    for flows in product(*(range(lo, hi+1) for u,v,lo,hi in arcs)):
        balance = [0]*n
        for (u,v,lo,hi), f in zip(arcs, flows):
            balance[u] -= f
            balance[v] += f
        if balance == demand:
            return True
    return False


def cut_check(n, arcs, demand):
    if sum(demand):
        return False, None
    for mask in range(1 << n):
        inside = {v for v in range(n) if mask >> v & 1}
        d = sum(demand[v] for v in inside)
        lower_out = sum(lo for u,v,lo,hi in arcs if u in inside and v not in inside)
        upper_in = sum(hi for u,v,lo,hi in arcs if u not in inside and v in inside)
        if d + lower_out > upper_in:
            return False, {'S':sorted(inside), 'demand':d, 'lower_out':lower_out, 'upper_in':upper_in}
    return True, None


def maxflow_feasible(n, arcs, demand):
    if sum(demand):
        return False
    shifted = demand[:]
    cap = [[0]*(n+2) for _ in range(n+2)]
    for u,v,lo,hi in arcs:
        assert 0 <= lo <= hi
        cap[u][v] += hi-lo
        shifted[u] += lo
        shifted[v] -= lo
    source, sink = n, n+1
    target = sum(max(d,0) for d in shifted)
    for v,d in enumerate(shifted):
        if d < 0:
            cap[source][v] += -d
        elif d > 0:
            cap[v][sink] += d
    value = 0
    while True:
        prev = [-1]*(n+2)
        prev[source] = source
        q = deque([source])
        while q and prev[sink] < 0:
            u = q.popleft()
            for v, c in enumerate(cap[u]):
                if c > 0 and prev[v] < 0:
                    prev[v] = u
                    q.append(v)
        if prev[sink] < 0:
            break
        delta = target + 1
        v = sink
        while v != source:
            u = prev[v]
            delta = min(delta, cap[u][v])
            v = u
        v = sink
        while v != source:
            u = prev[v]
            cap[u][v] -= delta
            cap[v][u] += delta
            v = u
        value += delta
    return value == target


count = 0
bound_pairs = [(lo,hi) for hi in range(3) for lo in range(hi+1)]
for (lo1,hi1),(lo2,hi2),d in product(bound_pairs,bound_pairs,range(-2,3)):
    arcs = [(0,1,lo1,hi1),(1,0,lo2,hi2)]
    demand = [d,-d]
    a = enumerated_feasible(2,arcs,demand)
    b,_ = cut_check(2,arcs,demand)
    c = maxflow_feasible(2,arcs,demand)
    assert a == b == c, (arcs,demand,a,b,c)
    count += 1
rng=random.Random(20260922)
for _ in range(100):
    arcs=[]
    for u,v in [(0,1),(1,2),(2,0),(0,2)]:
        lo,hi=rng.choice(bound_pairs)
        arcs.append((u,v,lo,hi))
    d0,d1=[rng.randrange(-2,3) for _ in range(2)]
    demand=[d0,d1,-d0-d1]
    a=enumerated_feasible(3,arcs,demand)
    b,_=cut_check(3,arcs,demand)
    c=maxflow_feasible(3,arcs,demand)
    assert a == b == c, (arcs,demand,a,b,c)
    count += 1

# A naive zero-demand <= incoming-upper-capacity test passes all subsets,
# but a forced outward arc without return capacity prevents circulation.
missing_lower=[]
for x in [0,1]:
    arcs=[(0,1,1,1),(1,0,0,x)]
    ok,witness=cut_check(2,arcs,[0,0])
    naive=all(0 <= sum(hi for u,v,lo,hi in arcs if not(mask>>u&1) and mask>>v&1)
              for mask in range(4))
    assert naive and ok == bool(x)
    missing_lower.append({'x':x,'naive_all_subsets_pass':naive,'feasible':ok,'violated_cut':witness})

out={
    'scope':'exact small-network algebra checks, not factory or performance validation',
    'instances_checked':count,
    'methods_compared':['exhaustive_integer_flows','all_lower_bound_cut_inequalities','integer_maxflow_after_lower_shift'],
    'cut_convention':'d=in-out; d(S)+l(delta_out(S))<=u(delta_in(S))',
    'missing_lower_bound_example':missing_lower,
    'parametric_global_cut':'1<=x',
}
Path(__file__).with_name('lower-bound-cut-check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
