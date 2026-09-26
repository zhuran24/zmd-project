"""Finite corroboration of the arbitrary-phase plant and the full skeleton."""
import json
import hashlib
import os
import random
from collections import Counter
from fractions import Fraction
from pathlib import Path
from dynamics import Net, plant, phi2, randomize

HERE = Path(__file__).resolve().parent
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))+1})


def plants(trials=600):
    totals = Counter()
    examples = []
    for seed in range(trials):
        rng = random.Random(860000+seed)
        q = [1,2,3,5][seed%4]
        lengths = tuple(rng.randrange(1,7) for _ in range(4))
        k = rng.choice([2,3])
        net = plant(q,lengths,k)
        randomize(net,rng,'dense' if seed%3 == 0 else 'sparse')
        start = phi2(net)
        bound = min(start-1,2*(lengths[0]+lengths[1]+176))
        threshold = 2*(lengths[0]+lengths[1]+2)
        eligible = start >= threshold+1
        low = start
        seen = {}
        idle_prefix = 0
        period = (7+seed%4)*q
        # Refusal, recovery, then periodic partial or complete reception.
        final_mode = seed%4
        def receive(name,t):
            if t < 30*q:
                return (t//(3*q)+int(name[-1]))%3 == 0
            if final_mode == 0:
                return False
            if final_mode == 1:
                return True
            return (t%period) < (2+int(name[-1]))*q
        net.sink_open = receive
        for t in range(1,2200*q):
            net.t = t
            net.close(rng if t < 30*q else None)
            value = phi2(net)
            low = min(low,value)
            assert value >= bound, (seed,t,start,value,bound)
            idle_prefix += any(net.m[x]['cache'] is None for x in ['C','B','K'])
            if t >= 30*q:
                key = net.key(period)
                if key in seen:
                    old_t,old_idle = seen[key]
                    cycle_idle = idle_prefix-old_idle
                    totals['cycles'] += 1
                    totals['eligible_cycles'] += eligible
                    totals['eligible_cycle_idle'] += eligible and cycle_idle > 0
                    totals['low_population_cycles_with_idle'] += not eligible and cycle_idle > 0
                    assert not (eligible and cycle_idle), (seed,old_t,t,cycle_idle)
                    if len(examples) < 8:
                        examples.append(dict(seed=seed,q=q,lengths=lengths,k=k,phi0_2=start,
                                             min_phi_2=low,period_subticks=t-old_t,cycle_idle=cycle_idle,
                                             eligible=eligible))
                    break
                seen[key] = t,idle_prefix
        else:
            totals['truncated'] += 1
        totals['trials'] += 1
        totals['fractional_trials'] += q > 1
        totals['population_bound_violations'] += 0
    result = dict(counts=dict(totals),examples=examples,
                  note='Capacity 50; finite probes only. Period keys include timers, pointers and sink schedule phase.')
    (HERE/'plant_probes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


def skeleton(seed, q=1, quota=None):
    rng = random.Random(seed)
    n = Net(q)
    plants_list = []
    def route(a,b,item):
        return n.link(a,b,item,rng.randrange(1,4),quota if a.startswith(('oreIron','oreRock')) else None)
    for i in range(34):
        n.machine(f'ore_ref{i}',{'iron_ore':1},'iron')
        n.machine(f'iron_crush{i}',{'iron':1},'iron_powder')
        route(f'oreIron{i}',f'ore_ref{i}','iron_ore')
        route(f'ore_ref{i}',f'iron_crush{i}','iron')
    for i in range(18):
        n.machine(f'ore_crush{i}',{'rock_ore':1},'rock_powder')
        route(f'oreRock{i}',f'ore_crush{i}','rock_ore')
    for family,count,raw in [('iron',17,'iron_powder'),('rock',9,'rock_powder'),('flower',6,'flower_powder')]:
        for i in range(count):
            n.machine(f'{family}_grind{i}',{raw:2,'sand_powder':1},family+'_fine')
            if family != 'flower':
                for j in range(2):
                    route(f'{"iron_crush" if family=="iron" else "ore_crush"}{2*i+j}',f'{family}_grind{i}',raw)
    sand_targets = [f'{f}_grind{i}' for f,c in [('iron',17),('rock',9),('flower',6)] for i in range(c)]
    for family,count,k in [('sand',11,3),('flower',6,2)]:
        for i in range(count):
            stem = f'{family}{i}'
            C,A,B,K = [stem+x for x in 'CABK']
            n.machine(C,{family+'_plant':1},family+'_seed',2)
            n.machine(A,{family+'_seed':1},family+'_plant')
            n.machine(B,{family+'_seed':1},family+'_plant')
            n.machine(K,{family+'_plant':1},family+'_powder',k)
            ca=route(C,A,family+'_seed'); ac=route(A,C,family+'_plant')
            route(C,B,family+'_seed'); route(B,K,family+'_plant')
            if family == 'sand':
                for _ in range(3 if i<10 else 2):
                    route(K,sand_targets.pop(0),'sand_powder')
            else:
                for _ in range(2):
                    route(K,f'flower_grind{i}','flower_powder')
            plants_list.append((C,A,ca,ac))
    for i in range(17):
        n.machine(f'steel{i}',{'iron_fine':1},'steel')
        route(f'iron_grind{i}',f'steel{i}','iron_fine')
    for i in range(6):
        n.machine(f'parts{i}',{'steel':1},'parts')
        route(f'steel{i}',f'parts{i}','steel')
        n.machine(f'bottle{i}',{'steel':2},'bottle')
        for j in range(2 if i<5 else 1):
            route(f'steel{6+2*i+j}',f'bottle{i}','steel')
    for i in range(3):
        n.machine(f'battery{i}',{'parts':10,'rock_fine':15},'battery',duration=5)
        n.machine(f'capsule{i}',{'bottle':10,'flower_fine':10},'capsule',duration=5)
        for j in range(2):
            route(f'parts{2*i+j}',f'battery{i}','parts')
            route(f'bottle{2*i+j}',f'capsule{i}','bottle')
            route(f'flower_grind{2*i+j}',f'capsule{i}','flower_fine')
        for j in range(3):
            route(f'rock_grind{3*i+j}',f'battery{i}','rock_fine')
        route(f'battery{i}','sink_battery','battery')
        route(f'capsule{i}','sink_capsule','capsule')
    assert len(n.m)==221 and len(n.lines)==317
    if q > 1:
        randomize(n,rng,'sparse')
    for C,A,ca,ac in plants_list:
        amount = len(n.lines[ca]['cells'])+len(n.lines[ac]['cells'])+5
        n.m[A]['stock'][n.m[A]['product'].replace('_plant','_seed')] = amount
    n.close()
    n.sink_open=lambda name,t: t>=120*q or (t//(20*q)+int(name.endswith('battery')))%3 == 0
    seen={}
    for t in range(1,12000*q):
        n.t=t; n.close()
        if t < 120*q:
            continue
        key=n.key(q)
        if key in seen:
            old_t,old_del,old_ship=seen[key]
            ticks=Fraction(t-old_t,q)
            rates={x:str(Fraction(n.delivered[x]-old_del[x])/ticks) for x in ('battery','capsule')}
            ore_rates=[Fraction(n.shipped[j]-old_ship[j])/ticks for j,l in enumerate(n.lines) if l['source'].startswith(('oreIron','oreRock'))]
            if quota is None:
                assert rates=={'battery':'3/5','capsule':'11/20'} and set(ore_rates)=={Fraction(1)}
            return dict(seed=seed,q=q,quota=quota,start=old_t,end=t,period_ticks=str(ticks),rates=rates,
                        ore_rates=sorted(set(map(str,ore_rates))),machines=len(n.m),paths=len(n.lines),
                        repeated_state_sha256=hashlib.sha256(repr(key).encode()).hexdigest(),
                        cycle_delivery={x:n.delivered[x]-old_del[x] for x in ('battery','capsule')})
        seen[key]=(t,n.delivered.copy(),n.shipped.copy())
    return dict(seed=seed,q=q,quota=quota,truncated=True)


if __name__ == '__main__':
    import sys
    if len(sys.argv)>1 and sys.argv[1]=='skeleton':
        rows=[skeleton(seed,q) for seed,q in [(8601,1),(8602,1),(8603,2),(8604,3)]]
        rows.append(skeleton(8605,1,1))
        (HERE/'skeleton_probes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(rows,ensure_ascii=False))
    else:
        plants()
