#!/usr/bin/env python3
"""Independent review checks. Writes only beside this script; one process.

Run: PYTHONDONTWRITEBYTECODE=1 python3 -B .../复核93C/verify.py
Finite searches check rule interpretations; proofs are in ../复核93C.md.
Neither interpreter imports sim2 or any file under 推导92C/.
"""
import argparse
from collections import Counter, deque
from copy import deepcopy
from fractions import Fraction
import hashlib
from itertools import permutations, product
import json
from pathlib import Path
import random
import time

from engines import DeadlineEngine, CountdownEngine, plant_spec, twice_phi, independent_weight

HERE = Path(__file__).resolve().parent


def save(name, obj):
    (HERE/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')


def paired(spec, steps, policy=None, observer=None):
    a, b = DeadlineEngine(spec), CountdownEngine(spec)
    for t in range(steps):
        sbegin,rbegin=len(b.dispatches),len(b.arrivals)
        budget = None if policy is None else policy(t)
        a.step(budget)
        b.step(budget)
        sa, sb = a.state(), b.state()
        if sa != sb or a.recent_sent != b.dispatches[sbegin:] or a.recent_received != b.arrivals[rbegin:]:
            save('engine_disagreement.json', dict(spec=spec,t=t,A=sa,B=sb))
            raise AssertionError(('engine disagreement',t))
        assert a.step_min_output==dict(zip(b.names,b.minimum_during_step))
        if observer:
            observer(t,sa,a,b)
    return a,b


def arithmetic_checks():
    # S02: all totals 0..150 for all three distinct two-input recipe ratios.
    s02 = []
    for a,b in [(2,1),(10,15),(10,10)]:
        checked = 0
        for x,y in product(range(151),repeat=2):
            m = min(x//a,y//b)
            predicted = x-a*m,y-b*m,m
            p,q,n = x,y,0
            while p >= a and q >= b:
                p -= a
                q -= b
                n += 1
            assert predicted == (p,q,n)
            checked += 1
        s02.append(dict(a=a,b=b,states=checked,mismatches=0))
    # S03: formula vs direct enumeration of all dangerous inventory states,
    # and all complete words within one smallest ratio segment.
    s03 = []
    import math
    for a,b,m in [(2,1,6),(10,15,5),(10,10,6)]:
        g = math.gcd(a,b)
        z0 = 50*(b-a)
        lo = b*(a-1)-50*a
        hi = 50*b-a*(b-1)
        margin = min(z0-lo,hi-z0)
        danger_low = [b*x-a*y for x,y in product(range(51),repeat=2) if y==50 and x<a]
        danger_high = [b*x-a*y for x,y in product(range(51),repeat=2) if x==50 and y<b]
        words = set(permutations('A'*(a//g)+'B'*(b//g)))
        vals = {0}
        for w in words:
            z = 0
            for letter in w:
                z += b if letter=='A' else -a
                vals.add(z)
        assert max(danger_low)==lo and min(danger_high)==hi
        assert max(abs(z) for z in vals)==a*b//g
        arbitrary_start = m*(max(vals)-min(vals))
        assert arbitrary_start == 2*m*a*b//g < margin
        s03.append(dict(a=a,b=b,g=g,m=m,Z0=z0,L=lo,U=hi,C=margin,
                        arbitrary_start_bound=arbitrary_start,segment_words=len(words)))
    # S01: phase enumeration, independently a longest legal arrival sequence.
    phases = []
    for offsets in product(range(8),repeat=3):
        phases.append(sum(sum(1 for t in range(40) if (t-o)%8==0) for o in offsets))
    best = [0]*41
    for length in range(1,41):
        best[length] = 1 + best[max(0,length-8)]
    assert set(phases)=={15} and 3*best[40]==15
    # S05: exact capacity test in all correct two-slot configurations.
    rejected = [(x,y) for x,y in product(range(51),repeat=2) if not x<50 and not y<50]
    assert rejected == [(50,50)]
    # S08: direct expression and a separate capacity-constraint enumeration.
    expression = Fraction(50+50+50+1+1)+Fraction(49,2)-Fraction(1,2)
    witnesses = [(aa,cc,sum(map(Fraction,[50,aa,50,1,1]))+Fraction(cc,2)-Fraction(1,2))
                 for aa,cc in product(range(51),repeat=2)
                 if aa+1>50 and cc+2>50]
    # Independent inventory enumeration includes the variable A output aa.
    minimal = min(z for aa,cc,z in witnesses)
    assert expression==minimal==176
    # Original S02 wrong-material trace: a box containing 51 seeds, one belt,
    # a grinder with two empty input slots. Same species cannot use two slots.
    stock,crate,head=0,51,None
    wrong_rows=[]
    for t in range(425):
        if head is not None and t>=head and stock<50:
            stock+=1
            head=None
        if head is None and crate:
            crate-=1
            head=t+8
        predicted_stock=min(50,t//8)
        predicted_crate=max(0,50-t//8)
        assert (stock,crate)==(predicted_stock,predicted_crate)
        if t in (0,8,392,400,407,408,424):
            wrong_rows.append(dict(step=t,grinder_seeds=stock,box_seeds=crate,
                                   belt_due=head,second_input_slot=0))
    save('wrong_material_certificate.json',wrong_rows)
    return dict(S02=s02,S02_old=dict(delivered=50,first_permanent_rejection_step=408,two_encodings_agree=True),S03=s03,S01=dict(phases=len(phases),max_arrivals=15,dp_max=3*best[40]),
                S05=dict(states=51**2,both_refused=rejected),
                S08=dict(saturation_before_second_B='176.5',barrier=int(expression),
                         independent_minimum=int(minimal),constraints_solutions=len(witnesses)),
                counts=dict(old_S06=2*2,old_S07=6*120,rotation_original=(2+6)*3,
                            s10_original=4*4*8*2*2*2))


def rotation_checks(horizon=12):
    checked,dispatch_count = 0,0
    exemplar = None
    # Availability is relaxed to arbitrary batch arrivals. It includes more
    # schedules than the actual recipes and does not prove their realizability.
    for k in (2,3):
        for initial in permutations(range(k)):
            for mask in range(1<<horizon):
                last = [None]*k
                departure = [None]*k
                qa = 0
                queue = list(initial)
                qb = 0
                free_at = [0]*k
                ever = [False]*k
                sa,sb = [],[]
                order = list(initial)
                for t in range(horizon+24):
                    if t%5==0:
                        order = order[1:]+order[:1]
                        # Offline only permutes as-yet-unused channels in the
                        # queue implementation; real success history survives.
                        new = [j for j in order if not ever[j]]
                        queue = new + [j for j in queue if ever[j]]
                    if t<horizon and mask>>t&1:
                        qa += k
                        qb += k
                    for j in range(k):
                        if departure[j] is not None and departure[j]<=t:
                            departure[j] = None
                    ranks = {j:i for i,j in enumerate(order)}
                    attempt = sorted(range(k),key=lambda j:(-1 if last[j] is None else last[j],ranks[j]))
                    if qa:
                        for j in attempt:
                            if departure[j] is None:
                                qa -= 1
                                last[j] = t
                                departure[j] = t+8
                                sa.append(j)
                                break
                    if qb and free_at[queue[0]]<=t:
                        j = queue.pop(0)
                        qb -= 1
                        free_at[j] = t+8
                        ever[j] = True
                        sb.append(j)
                        queue.append(j)
                    assert qa==qb and sa==sb
                if sa:
                    assert len(set(sa[:k])) == min(k,len(sa))
                    assert all(x==sa[i%k] for i,x in enumerate(sa))
                    # Independent explicit check of all contiguous successful
                    # subsequences, rather than only cumulative total counts.
                    for p in range(len(sa)):
                        counts = [0]*k
                        for x in sa[p:]:
                            counts[x] += 1
                            assert max(counts)-min(counts)<=1
                checked += 1
                dispatch_count += len(sa)
                if exemplar is None and len(sa)>k*2:
                    exemplar = dict(k=k,initial=initial,batch_mask=mask,successes=sa)
    # Old S06: one real two-item batch completes on the last step of a tick.
    traces = []
    for p in permutations(range(2)):
        for machine_order in range(2):
            n={'K':dict(q=2,**{'in':0,'out':0,'work':8})}
            routes=[dict(src='K',dst=None,cells=[-1],rank=p.index(j)) for j in range(2)]
            a,b=paired(dict(nodes=n,routes=routes),18)
            first=Counter(i for t,_,i in a.sent if 0<=t<8)
            assert sum(first.values())==1
            assert [t for t,_,_ in a.sent][:2]==[7,8]
            traces.append(dict(order=p,machine_order=machine_order,dispatches=a.sent))
    save('rotation_certificate.json',dict(exemplar=exemplar,old_clause_traces=traces))
    return dict(scenarios=checked,total_dispatches=dispatch_count,horizon=horizon,
                two_encodings_agree=True,interval_violations=0,old_clause_cases=len(traces))


def fifty_tick_checks():
    counts,minimum,first_empty = 0,{1:50,2:50,3:50},{}
    recovery_max = {1:0,2:0,3:0}
    # No new inputs is a deliberate conservative boundary, not a plant layout.
    for k in (1,2,3):
        for q0 in range(50-k,51):
            for work in range(-1,9):
                for strategy in range(4):
                    n={'M':dict(q=k,**{'in':50,'out':q0,'work':work})}
                    routes=[dict(src='M',dst=None,cells=[0]) for _ in range(k)]
                    spec=dict(nodes=n,routes=routes)
                    waits={}
                    earliest=[]
                    def watch(t,s,a,b):
                        inv,out,cache=s['nodes']['M']
                        if t<400:
                            assert cache>=0
                            minimum[k]=min(minimum[k],a.step_min_output['M'])
                            assert a.step_min_output['M']>=50-3*k
                        for tt,i in a.recent_received:
                            if tt==t:
                                waits[i]=t
                        for tt,_,i in a.recent_sent:
                            if tt==t and i in waits:
                                elapsed=t-waits.pop(i)+1
                                if t<400:
                                    assert elapsed<=k
                                    recovery_max[k]=max(recovery_max[k],elapsed)
                        if t<400:
                            assert all(t-u+1<k for u in waits.values())
                        if cache<0 and not earliest:
                            earliest.append(t)
                    policies=[lambda t:None,lambda t:1,lambda t:0 if t%73<31 else None,
                              lambda t:0 if 41<=t<187 else None]
                    paired(spec,416,policies[strategy],watch)
                    if work==-1 and strategy==0:
                        first_empty[str(k)+':'+str(q0)] = earliest[0] if earliest else None
                    counts += 1
    # Explicitly reconstruct all 720 order choices of the old synchronous claim.
    counterexample=[]
    for outlet_order in permutations(range(3)):
        for nt_order in permutations(['C','A','B','K','M']):
            nodes={n:dict(q=q,**{'in':50,'out':48 if n=='K' else 50,'work':0})
                   for n,q in [('C',2),('A',1),('B',1),('K',3)]}
            spec=plant_spec(k=3,nodes=nodes)
            spec['order']=list(nt_order)
            for r in spec['routes']:
                r['cells']=[0]
            for j in range(3):
                spec['routes'][4+j]['rank']=4+outlet_order.index(j)
            rows=[]
            def w(t,s,a,b):
                rows.append(dict(step=t,stock=s['nodes']['K'][0],out=s['nodes']['K'][1],cache=s['nodes']['K'][2]))
            paired(spec,2,lambda t:1 if t==0 else 0,w)
            assert [x['stock'] for x in rows]==[49,50]
            if not counterexample:
                counterexample=rows
    # Arithmetic independent of the engines.
    starts=[8*j for j in range(50)]
    assert starts[-1]==392 and starts[-1]+8==400 and 50*8==400
    assert all(x==400 for x in first_empty.values())
    save('fifty_tick_certificate.json',dict(old_claim_counterexample=counterexample,
                                          no_input_first_empty=first_empty,
                                          formula_bounds={k:50-k-k-k for k in (1,2,3)}))
    return dict(local_scenarios=counts,old_claim_order_cases=720,last_start=392,
                first_possible_empty=400,observed_output_minimum=minimum,
                proved_output_minimum={k:50-3*k for k in (1,2,3)},
                max_refill_judgements=recovery_max)


def loop_checks(random_cases,random_steps,target_cases):
    rng=random.Random(930092)
    total_states=0
    lowest_slack=None
    double_b_events=0
    samples=[]
    # A fully supplied real-recipe local unit, with powder drainage as an
    # explicitly external boundary, reaches the strong 176 barrier.
    nodes={n:dict(q=q,**{'in':50,'out':48 if n=='K' else 50,'work':0})
           for n,q in [('C',2),('A',1),('B',1),('K',3)]}
    saturated=plant_spec(k=3,nodes=nodes)
    for r in saturated['routes']:
        r['cells']=[0]
    saturation_rows=[]
    def saturate_watch(t,s,a,b):
        saturation_rows.append(dict(step=t,phi=twice_phi(s)/2,
                                    C_dispatch=[i for tt,n,i in a.recent_sent if n=='C'],
                                    C=s['nodes']['C'],A=s['nodes']['A']))
    paired(saturated,24,None,saturate_watch)
    assert min(x['phi'] for x in saturation_rows)==178
    assert any(saturation_rows[i]['C_dispatch']==[1] and
               next((x['C_dispatch'] for x in saturation_rows[i+1:] if x['C_dispatch']),None)==[1]
               for i in range(len(saturation_rows)))
    for case in range(random_cases+target_cases):
        near=case>=random_cases
        k=rng.choice((2,3))
        lengths=tuple(rng.randrange(1,5) for _ in range(4))
        nodes={n:dict(q=q,**{'in':rng.randrange(48,51) if near else rng.randrange(51),
                              'out':rng.randrange(48,51) if near and n in ('A','C') else rng.randrange(51),
                              'work':rng.randrange(-1,9)})
               for n,q in [('C',2),('A',1),('B',1),('K',k)]}
        mode='gates' if case%2 else 'belt'
        spec=plant_spec(lengths,k,nodes,mode)
        rng.shuffle(spec.setdefault('order',list(nodes)))
        spec['routes'][0]['rank'],spec['routes'][1]['rank']=((1,0) if case%3 else (0,1))
        for j,r in enumerate(spec['routes']):
            r['cells']=[rng.randrange(9) if near and j in (0,2) else rng.randrange(-1,9) for _ in r['cells']]
        initial=None
        last_c=None
        prior_phi=None
        minimum_phi=None
        tested=60 if near else random_steps
        def watch(t,s,a,b):
            nonlocal initial,total_states,lowest_slack,double_b_events,last_c,prior_phi,minimum_phi
            v=twice_phi(s)
            assert v==2*independent_weight(b.state())
            total_states+=1
            if t==0:
                initial=v
                last_c=None
                prior_phi=v
                minimum_phi=v
                return
            bound=min(initial-1,2*(lengths[0]+lengths[2]+176))
            assert v>=bound,(case,t,v,bound)
            slack=v-bound
            lowest_slack=slack if lowest_slack is None else min(lowest_slack,slack)
            changes=[i for tt,n,i in a.recent_sent if n=='C']
            assert v-prior_phi==sum(1 if j==0 else -1 for j in changes)
            for j in changes:
                if j==1 and last_c==1:
                    assert v>=2*(lengths[0]+lengths[2]+176)
                    double_b_events+=1
                last_c=j
            prior_phi=v
            minimum_phi=min(minimum_phi,v)
        policy=lambda t:0 if 47<=t%137<103 else None
        a,b=paired(spec,tested,policy,watch)
        if len(samples)<3:
            samples.append(dict(case=case,mode=mode,lengths=lengths,phi_s=initial/2,min_phi=minimum_phi/2))
    # Small, sparse closed seed/plant unit with externally drained powder.
    # It is a transport graph test, not an embedded 70x70 layout certificate.
    periods=[]
    for k in (2,3):
        for mode in ('belt','gates'):
            spec=plant_spec(k=k,mode=mode)
            spec['nodes']['A']['in']=1
            seen={}
            period=None
            start_counts=None
            s0=None
            a,b=DeadlineEngine(spec),CountdownEngine(spec)
            for t in range(512):
                a.step(); b.step()
                s=a.state()
                assert s==b.state()
                if s0 is None:
                    s0=twice_phi(s)
                    assert s0==2
                assert twice_phi(s)>=1
                cyc=deepcopy(s)
                cyc.pop('sink')
                key=json.dumps(cyc,sort_keys=True)
                counts={n:len(z) for n,z in a.starts.items()}
                if key in seen:
                    begin,previous,sinkprev=seen[key]
                    delta={n:counts[n]-previous[n] for n in counts}
                    assert set(delta.values())=={1}
                    period=t-begin
                    assert period==32
                    assert a.sink_count-sinkprev==k
                    start_counts=delta
                    break
                seen[key]=(t,counts,a.sink_count)
            assert period is not None
            periods.append(dict(k=k,mode=mode,period_steps=period,starts=start_counts,rate='1/4',
                                powder_per_period=k,entry_step=begin))
    save('loop_certificate.json',dict(samples=samples,sparse_cycles=periods,saturation_trace=saturation_rows,
                                     graph_only=True,scope='pure belts and unrestricted directed gate chains'))
    return dict(random_cases=random_cases,random_steps=random_steps,target_cases=target_cases,
                target_steps=60,compared_step_states=total_states,
                minimum_doubled_bound_slack=lowest_slack,double_B_events=double_b_events,
                violations=0,independent_phi_weights_agree=True,sparse_cycles=periods)


def transfer_checks():
    cases=0
    max_entry=0
    periods=Counter()
    minima=50
    for l1,l2,phase,transport_order,machine_order,mode in product(range(1,5),range(1,5),range(8),range(2),range(2),('belt','gates')):
        nodes={'Y':dict(q=1,**{'in':49,'out':0,'work':8}),
               'X':dict(q=1,**{'in':49,'out':0,'work':phase+1})}
        routes=[dict(src='Y',dst='X',cells=[-1]*l1,mode=mode),
                dict(src='X',dst='Y',cells=[-1]*l2,mode=mode)]
        if transport_order:
            routes.reverse()
        spec=dict(nodes=nodes,routes=routes,order=['Y','X'] if not machine_order else ['X','Y'])
        seen={}
        found=[]
        last_received=[None,None]
        def w(t,s,a,b):
            nonlocal max_entry,minima
            assert all(v[2]>=0 for v in s['nodes'].values())
            minima=min(minima,*(v[0] for v in s['nodes'].values()))
            for tt,j in a.recent_received:
                if tt==t:
                    last_received[j]=t
            # First-cell refill: for a length-one route every terminal send is
            # also first-cell clearing. Longer routes are checked once full.
            for j,r in enumerate(s['routes']):
                if len(r)==1 and last_received[j]==t:
                    assert r[0]==8
            cy=deepcopy(s);cy.pop('sink')
            key=json.dumps(cy,sort_keys=True)
            if not found:
                if key in seen:
                    entry=seen[key]
                    period=t-entry
                    assert period==8
                    assert all(all(z>=0 for z in r) for r in s['routes'])
                    max_entry=max(max_entry,entry)
                    periods[period]+=1
                    found.append((entry,period))
                else:
                    seen[key]=t
        paired(spec,96,None,w)
        assert found
        cases+=1
    # Wrong-input original S10 counterexample checked in two non-simulator
    # encodings, with the rule-13 uniqueness guard expressly included.
    object_rows=[]
    stock='蓝铁块';running=None;held=None;out=None
    for t in range(24):
        if running is not None and t==running:
            running=None;held='蓝铁粉末'
        if held is not None and held != stock and out is None:
            out=held;held=None
        if t==1:
            assert stock is None
            stock='蓝铁粉末'
        if stock=='蓝铁块' and running is None and held is None:
            stock=None;running=t+8
        object_rows.append(dict(step=t,stock=stock,cache='在制' if running is not None else held,out=out,X_cache=None))
    table_rows=[dict(step=t,stock=None if t==0 else '蓝铁粉末',
                     cache='在制' if t<8 else '蓝铁粉末',out=None,X_cache=None) for t in range(24)]
    assert object_rows==table_rows
    save('transfer_certificate.json',dict(two_recipe_loop=dict(cases=cases,periods=dict(periods),
                                                              latest_cycle_entry=max_entry),
                                          old_S10_trace=object_rows))
    return dict(cases=cases,periods=dict(periods),latest_cycle_entry=max_entry,
                empty_cache_steps=0,minimum_input=minima,old_S10_stationary_from=8)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--quick',action='store_true')
    args=p.parse_args()
    begin=time.time()
    results={}
    for name,fn in [('arithmetic',arithmetic_checks),
                    ('rotation',lambda:rotation_checks(8 if args.quick else 12)),
                    ('fifty_ticks',fifty_tick_checks),
                    ('loops',lambda:loop_checks(20 if args.quick else 1200,160 if args.quick else 2000,
                                               40 if args.quick else 2000)),
                    ('transfer',transfer_checks)]:
        started=time.time()
        results[name]=fn()
        results[name]['wall_seconds']=round(time.time()-started,3)
        save('results.json',results)
        print(name,json.dumps(results[name],ensure_ascii=False),flush=True)
    results['run']=dict(mode='quick' if args.quick else 'full',wall_seconds=round(time.time()-begin,3),
                        parallel_processes=1,imports_from_derivation=0)
    save('results.json',results)
    snapshot=HERE.parent/'前提快照'
    files=[p for p in snapshot.iterdir() if p.is_file()]
    files.extend([HERE.parent/'推导92C.md',HERE/'engines.py',HERE/'verify.py'])
    save('input_manifest.json',{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})


if __name__=='__main__':
    main()
