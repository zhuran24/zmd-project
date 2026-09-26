#!/usr/bin/env python3
"""Exhaustive overapproximation: two-machine plant loop and straight bridges.
No third-party or earlier-seat scripts are imported. Capacity 3, CA=AC=1.
"""
import itertools as it
import json
import os
import sys
from collections import deque
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
sys.setrecursionlimit(100000)
M = 3


def phi2(s):
    ci, co, ai, ao, cc, aa, ca, ac = s
    return 2 * (ci + ai + ao + bool(cc) + bool(aa) + bool(ca) + bool(ac)) + co


def closed(s):
    ci, co, ai, ao, cc, aa, ca, ac = s
    return not ((cc == 0 and ci) or (cc == 2 and co <= M-2)
                or (aa == 0 and ai) or (aa == 2 and ao < M)
                or (co and not ca) or (ao and not ac))


@lru_cache(None)
def close_all(s):
    ci, co, ai, ao, cc, aa, ca, ac, b = s
    nxt = []
    def add(changes):
        x = list(s)
        for i, v in changes.items(): x[i] = v
        nxt.append(tuple(x))
    if cc == 2 and co + 2 <= M: add({1: co+2, 4: 0})
    if cc == 0 and ci: add({0: ci-1, 4: 1})
    if aa == 2 and ao < M: add({3: ao+1, 5: 0})
    if aa == 0 and ai: add({2: ai-1, 5: 1})
    if ca == 1 and ai < M: add({2: ai+1, 6: 0})
    if ac == 1 and ci < M: add({0: ci+1, 7: 0})
    if ca == 0 and co: add({1: co-1, 6: 2})
    if ac == 0 and ao: add({3: ao-1, 7: 2})
    if b and co: add({1: co-1, 8: 0})
    if not nxt:
        return frozenset({(ci, co, ai, ao, cc, aa, int(bool(ca)), int(bool(ac)))})
    return frozenset().union(*(close_all(x) for x in nxt))


def plant_graph():
    states = [s for s in it.product(range(M+1), range(M+1), range(M+1), range(M+1),
                                    range(3), range(3), range(2), range(2)) if closed(s)]
    ids = {s: i for i, s in enumerate(states)}
    edges = []
    for s in states:
        ci, co, ai, ao, cc, aa, ca, ac = s
        start = (ci, co, ai, ao, 2 if cc else 0, 2 if aa else 0, ca, ac)
        ends = close_all(start+(0,)) | close_all(start+(1,))
        assert ends <= ids.keys()
        edges.append({ids[e] for e in ends})
    index = {}; low = {}; stack = []; active = set(); components = []
    def visit(v):
        index[v] = low[v] = len(index)
        stack.append(v); active.add(v)
        for w in edges[v]:
            if w not in index:
                visit(w); low[v] = min(low[v], low[w])
            elif w in active:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            group = []
            while True:
                w = stack.pop(); active.remove(w); group.append(w)
                if w == v: break
            components.append(group)
    for v in range(len(states)):
        if v not in index: visit(v)
    owner = {v: j for j, g in enumerate(components) for v in g}
    dag = [{owner[w] for v in g for w in edges[v] if owner[w] != j} for j, g in enumerate(components)]
    p = [phi2(s) for s in states]
    @lru_cache(None)
    def reachable_min(j):
        return min([min(p[v] for v in components[j])] + [reachable_min(k) for k in dag[j]])
    bad = [states[v] for v in range(len(states)) if reachable_min(owner[v]) < min(p[v]-1, 7*M+6)]
    cyclic = [v for g in components if len(g)>1 or g[0] in edges[g[0]] for v in g]
    idle_bad = [states[v] for v in cyclic if p[v] >= 8 and states[v][4] == 0]
    assert not bad and not idle_bad
    return {'capacity': M, 'CA_AC_lengths': [1, 1], 'states': len(states),
            'edges': sum(map(len, edges)), 'components': len(components), 'cyclic_states': len(cyclic),
            'lower_bound_violations': len(bad), 'C_empty_cycle_states_phi_ge_4': len(idle_bad),
            'microstate_closure_cache': close_all.cache_info()._asdict()}


def bridge_chains():
    # 0=empty, 1=unacceptable blocker, 2=needed acceptable item.
    # We even allow reversing and zero dwell: a strict reachability enlargement.
    # The far terminal either only emits items or only accepts items.
    cases = visited = 0
    for length in range(1, 8):
        for terminal in ('source', 'sink'):
            for tail in it.product(range(3), repeat=length-1):
                initial = (1,) + tail
                q = deque([initial]); seen = {initial}
                while q:
                    s = q.popleft(); visited += 1
                    assert s[0] != 2, (length, terminal, initial, s)
                    nxt = []
                    for j in range(length-1):
                        if bool(s[j]) != bool(s[j+1]):
                            x = list(s); x[j], x[j+1] = x[j+1], x[j]; nxt.append(tuple(x))
                    if terminal == 'source' and s[-1] == 0:
                        nxt.append(s[:-1] + (2,))
                    if terminal == 'sink' and s[-1] != 0:
                        nxt.append(s[:-1] + (0,))
                    for x in nxt:
                        if x not in seen: seen.add(x); q.append(x)
                cases += 1
    return {'max_axis_length': 7, 'initial_axis_cases': cases, 'visited_with_multiplicity': visited,
            'needed_item_reaches_machine': 0,
            'scope': 'supports the order-preservation proof; does not assume the first item itself stays forever'}


def batch_modulus():
    cases = 0
    for k in range(2, 7):
        for initial in range(51):
            reachable = {(initial, 0)}
            for _ in range(80):
                nxt = set()
                for q, partial in reachable:
                    # no completed batch, or one whole k batch available;
                    # in either case every exclusive first cell is ready.
                    for batch in (0, 1):
                        available = q + batch * k
                        sent = min(k, available)
                        pp = partial + int(0 < sent < k)
                        assert pp <= 1
                        if initial % k == 0: assert pp == 0
                        nxt.add((available - sent, pp))
                        cases += 1
                reachable = nxt
    return {'k_range': [2, 6], 'initial_output_range': [0, 50], 'horizon': 80,
            'transitions_checked': cases, 'more_than_one_partial_step': 0}


if __name__ == '__main__':
    out = {'plant_graph': plant_graph(), 'bridge_axes': bridge_chains(), 'batch_modulus': batch_modulus()}
    (HERE / 'state_graph.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(out, ensure_ascii=False))
