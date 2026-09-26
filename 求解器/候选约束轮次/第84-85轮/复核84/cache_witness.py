#!/usr/bin/env python3
"""A legal completed old planting batch defeats candidate 12's initial list."""
import json
import os
from pathlib import Path
from events import Net, plant, phi

HERE = Path(__file__).resolve().parent
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})


def main():
    n=Net()
    nodes,paths=plant(n,'buck',2,(5,29,13,58))
    for m in n.ms.values():
        m.stock={x:50 for x in m.inp}; m.out=50; m.finish=0
    a=n.ms[nodes[1]]
    a.cache_product='砂叶'  # completed during debugging; no wrong recipe starts after release
    n.stores['finite_box']=[44,50]
    export=n.route(nodes[3],'finite_box','buckpowder',1)
    for r in paths: r.cells=[-1]*len(r.cells)
    export.cells=[0]
    n.ms[nodes[3]].out=49  # its first powder has just entered this route
    n.prepare(21)
    trace=[]; seen={}; cycle=None
    n.settle(0)
    initial=phi(n,nodes,paths)
    bound=min(initial-.5,5+29+176)
    for t in range(30):
        n.settle(t)
        trace.append({'t':t,'phi':phi(n,nodes,paths),'bound':bound,'A_out':a.out,
                      'A_starts_after_release':a.starts,'C_out':n.ms[nodes[0]].out,
                      'B_seed_taken':paths[2].supplied,'box_powder':n.stores['finite_box'][0]})
        key=n.key()
        if key in seen:
            cycle=[seen[key],t]; break
        seen[key]=t
    assert any(r['phi']<bound for r in trace)
    assert a.starts==0 and a.out>0
    result={'phi0':initial,'bound':bound,'minimum_phi':min(x['phi'] for x in trace),
            'trace':trace,'final_cycle':cycle,'cached_old_product':'砂叶',
            'current_species':'荞花','box_implementation':'44 powder in slot 1, other five slots full of five different non-powder items, no output, wireless off',
            'scope':'All newly started plant recipes are buckwheat. Only A has an old completed sandleaf batch retained from debugging.'}
    (HERE/'cache_witness.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__': main()
