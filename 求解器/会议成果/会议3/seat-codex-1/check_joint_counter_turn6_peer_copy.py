"""Independent exact verification of the subset-layer bottleneck witness.

Abstract network only; not a factory layout or a solver performance test.
"""
from itertools import product
from pathlib import Path
from time import perf_counter
import json


def main():
    started = perf_counter()
    nodes = ('sA', 'sB', 'p', 'q', 'tA', 'tB')
    edges = (('sA','p'), ('sB','p'), ('p','q'), ('q','tA'),
             ('q','tB'), ('sA','tB'), ('sB','tA'))
    demands = {
        'all': {'sA':-1, 'sB':-1, 'tA':1, 'tB':1},
        'A': {'sA':-1, 'tA':1},
        'B': {'sB':-1, 'tB':1},
    }
    feasible = {k: [] for k in demands}
    for values in product((0,1), repeat=len(edges)):
        balance = dict.fromkeys(nodes, 0)
        for (a,b), value in zip(edges, values):
            balance[a] -= value
            balance[b] += value
        for name, demand in demands.items():
            if all(balance[n] == demand.get(n,0) for n in nodes):
                feasible[name].append(values)
    assert all(feasible.values())
    assert len(feasible['A']) == len(feasible['B']) == 1
    joint_integer = [(a,b) for a in feasible['A'] for b in feasible['B']
                     if all(x+y <= 1 for x,y in zip(a,b))]
    assert not joint_integer
    central = edges.index(('p','q'))
    assert feasible['A'][0][central] == feasible['B'][0][central] == 1
    # For real flows the same unique-route argument applies: the wrong sink
    # has demand zero and no outgoing edge; the other source has demand zero
    # and no incoming edge. Conservation therefore forces each correct unit
    # demand through p->q, contradicting its shared capacity 1.
    result = {
        'scope': 'abstract directed network; no factory or CP-SAT claim',
        'nodes': list(nodes), 'edges': [list(e) for e in edges],
        'integer_assignments_checked': 2**len(edges),
        'feasible_integer_layers': {k: len(v) for k,v in feasible.items()},
        'joint_integer_solutions': len(joint_integer),
        'joint_real_infeasibility': 'A and B each force 1 through p->q, so 2<=1',
        'elapsed_seconds_excluding_imports_and_write': perf_counter()-started,
    }
    Path(__file__).with_name('joint_counter_turn5_result.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
