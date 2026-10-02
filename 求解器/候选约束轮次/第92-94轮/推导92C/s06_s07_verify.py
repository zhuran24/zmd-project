#!/usr/bin/env python3
"""Two independent encodings: unchanged sim2 versus a small direct step table.
Only directed one-cell belts and fixed recipes with distinct input/output kinds.
No sim2 same-kind-flush or physical-bridge identity corner is exercised.
"""
from pathlib import Path
from itertools import permutations
import importlib.util, json, sys
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[3]
p=ROOT/'求解器/规则修订/2026-09-30-迟滞/sim2/simulator.py'
spec=importlib.util.spec_from_file_location('s06_s07_sim2',p)
sim=importlib.util.module_from_spec(spec);sys.modules[spec.name]=sim;spec.loader.exec_module(sim)

def definitions(case):
    if case=='s06':
        machines={
            'K':dict(ingredients={'flower':1},product='flower_powder',qty=2,inputs={'flower':49},output=0,remaining=8,ready=False),
            'G':dict(ingredients={'flower_powder':2,'sand_powder':1},product='fine_flower',qty=1,inputs={'flower_powder':0,'sand_powder':50},output=0,remaining=None,ready=False)}
        paths=[('KA','K','G','flower_powder',False),('KB','K','G','flower_powder',False)]
    else:
        machines={
            'C':dict(ingredients={'plant':1},product='seed',qty=2,inputs={'plant':50},output=50,remaining=None,ready=True),
            'A':dict(ingredients={'seed':1},product='plant',qty=1,inputs={'seed':50},output=50,remaining=None,ready=True),
            'B':dict(ingredients={'seed':1},product='plant',qty=1,inputs={'seed':50},output=50,remaining=None,ready=True),
            'K':dict(ingredients={'plant':1},product='sand_powder',qty=3,inputs={'plant':50},output=48,remaining=None,ready=True),
            'G':dict(ingredients={'blue_powder':2,'sand_powder':1},product='dense_blue',qty=1,inputs={'blue_powder':50,'sand_powder':49},output=0,remaining=8,ready=False)}
        paths=[('CA','C','A','seed',True),('CB','C','B','seed',True),('AC','A','C','plant',True),('BK','B','K','plant',True)]
        paths += [(f'KG{i}','K','G','sand_powder',True) for i in range(3)]
    return machines,paths

def sim2_run(case,steps,port_order=None,nt_order=None):
    specs,ps=definitions(case);ms={};belts={}
    for name,z in specs.items():
        r=sim.Recipe(name,tuple(z['ingredients'].items()),z['product'],z['qty'],8)
        m=sim.Machine(name,auxiliary=len(z['ingredients'])==2,recipes=[r]);m.slots=[]
        for kind,count in z['inputs'].items():m.slots.append([sim.Item(kind) for _ in range(count)])
        m.output=[sim.Item(z['product']) for _ in range(z['output'])]
        m.cache=[sim.Item(z['product']) for _ in range(z['qty'])] if z['ready'] else []
        m.running=r if z['remaining'] is not None else None;m.remaining=z['remaining'];ms[name]=m
    rank=0
    if port_order is None:port_order=[p[0] for p in ps]
    byname={z[0]:z for z in ps}
    for name in port_order:
        _,src,dst,kind,full=byname[name];b=sim.Belt(name)
        if full:b.fill(kind,entered=-8)
        ms[src].connect(b,rank);rank+=1;b.connect(ms[dst],rank);rank+=1;belts[name]=b
    names=[p[0] for p in ps];nts=list(ms) if nt_order is None else list(nt_order)
    nodes=list(ms.values())+[belts[n] for n in names]
    sch={'order':names+nts,'choices':{}}
    w=sim.World(nodes,schedule=sch,trace=True)
    rows=[]
    for t in range(steps):
        w.step()
        rows.append(dict(t=t,machines={n:dict(inputs={kind:sum(i.kind==kind for slot in m.slots for i in slot) for kind in specs[n]['ingredients']},output=len(m.output),remaining=m.remaining,ready=bool(m.cache),active=m.running is not None,starts=sum(tt==t for tt,_ in m.starts),sent=[dst for tt,_,dst in m.sent if tt==t]) for n,m in ms.items()},belts={n:None if b.cells[0] is None else b.cells[0].entered for n,b in belts.items()}))
    return rows,w.events

def table_run(case,steps,port_order=None,nt_order=None):
    # Independent dictionaries; no imported sim2 class/method is used here.
    specs,ps=definitions(case);ms=json.loads(json.dumps(specs));bs={name:(-8 if full else None) for name,_,_,_,full in ps}
    byname={z[0]:z for z in ps};port_order=port_order or list(byname);rank={n:i for i,n in enumerate(port_order)}
    outs={n:sorted([p[0] for p in ps if p[1]==n],key=rank.get) for n in ms}
    ins={n:sorted([p[0] for p in ps if p[2]==n],key=rank.get) for n in ms}
    last={p[0]:-1 for p in ps};cursor={n:0 for n in ms}
    nts=list(ms) if nt_order is None else list(nt_order);rows=[]
    def flush(m):
        if m['ready'] and m['output']+m['qty']<=50:m['output']+=m['qty'];m['ready']=False
    for t in range(steps):
        sent={n:[] for n in ms};started={n:0 for n in ms}
        for m in ms.values():
            if m['remaining'] is not None:
                m['remaining']-=1
                if m['remaining']==0:m['remaining']=None;m['ready']=True
            flush(m)
        judged=set()
        for pname,_,dst,_,_ in ps:
            if pname in judged:continue
            group=ins[dst];start=cursor[dst];ordered=group[start:]+group[:start];judged.update(group)
            for bn in ordered:
                _,_,dn,kind,_=byname[bn]
                if bs[bn] is not None and t-bs[bn]>=8 and ms[dn]['inputs'][kind]<50:
                    bs[bn]=None;ms[dn]['inputs'][kind]+=1;cursor[dn]=(group.index(bn)+1)%len(group)
        for n in nts:
            m=ms[n]
            for bn in sorted(outs[n],key=lambda z:(last[z],rank[z])):
                if m['output'] and bs[bn] is None:
                    m['output']-=1;flush(m);bs[bn]=t;last[bn]=t;sent[n].append(bn);break
        for n,m in ms.items():
            if m['remaining'] is None and not m['ready'] and all(m['inputs'][kind]>=count for kind,count in m['ingredients'].items()):
                for kind,count in m['ingredients'].items():m['inputs'][kind]-=count
                m['remaining']=8;started[n]=1
        rows.append(dict(t=t,machines={n:dict(inputs=m['inputs'].copy(),output=m['output'],remaining=m['remaining'],ready=m['ready'],active=m['remaining'] is not None,starts=started[n],sent=sent[n]) for n,m in ms.items()},belts=bs.copy()))
    return rows

def finite50_counter():
    # A one-input, one-output 1-tick machine with exactly 50 initial inputs,
    # zero further inflow, and an always-draining dedicated one-cell belt.
    inp=50;out=49;remaining=None;entered=None;first_empty=None;rows=[]
    for t in range(410):
        if remaining is not None:
            remaining-=1
            if remaining==0:remaining=None;out+=1
        if entered is not None and t-entered>=8:entered=None
        if out and entered is None:out-=1;entered=t
        if remaining is None and inp:inp-=1;remaining=8
        if remaining is None and first_empty is None:first_empty=t
        if t in [0,391,392,399,400]:rows.append(dict(t=t,input=inp,output=out,cache_nonempty=remaining is not None))
    # Separately: starts are 8*j, j=0..49; final finish is 8*50.
    arithmetic=8*50
    assert first_empty==arithmetic==400
    return dict(first_empty_step=first_empty,independent_final_finish=arithmetic,selected_rows=rows)

def corrected_s06_check():
    total=0
    for k in (2,3):
        for initial in permutations(range(k)):
            for batches in ([0,8,16,24,32],[7,15,31,39],[0,17,25,49]):
                # Timestamp ordering implementation.
                last=[-1]*k;rank=list(initial);empty_at=[0]*k;q=0;seq=[]
                # Independent service queue implementation.
                queue=list(initial);never=set(range(k));free=[0]*k;q2=0;seq2=[]
                for t in range(64):
                    if t%5==0:
                        rank=rank[1:]+rank[:1]
                        queue=sorted(never,key=rank.index)+[j for j in queue if j not in never]
                    if t in batches:q+=k;q2+=k
                    for j in sorted(range(k),key=lambda j:(last[j],rank.index(j))):
                        if q and t>=empty_at[j]:q-=1;last[j]=t;empty_at[j]=t+8;seq.append(j);break
                    j=queue[0]
                    if q2 and t>=free[j]:
                        q2-=1;free[j]=t+8;seq2.append(j);queue=queue[1:]+[j];never.discard(j)
                assert seq==seq2
                for a in range(len(seq)):
                    for b in range(a+1,len(seq)+1):
                        counts=[seq[a:b].count(j) for j in range(k)]
                        assert max(counts)-min(counts)<=1
                assert all(seq[j]==seq[j%k] for j in range(len(seq)))
                total+=1
    assert total==(2+6)*3
    return dict(scenarios=total,independent_count=(2+6)*3,timestamp_vs_queue_identical=True,all_contiguous_success_substrings_balanced=True)

result={'cases':{},'finite50':finite50_counter(),'corrected_s06':corrected_s06_check()}
for case,steps in [('s06',18),('s07',32)]:
    a,events=sim2_run(case,steps);b=table_run(case,steps);assert a==b,(case,a,b)
    (BASE/f's06_s07_{case}_trace.json').write_text(json.dumps(dict(rows=a,events=events),ensure_ascii=False,indent=2))
    result['cases'][case]={'steps_compared':steps,'identical':True}
    if case=='s06':
        counts=[sum(n in r['machines']['K']['sent'] for r in a[:8]) for n in ['KA','KB']]
        assert sorted(counts)==[0,1]
        result['cases'][case]['first_tick_counts']=counts
    else:
        assert a[0]['machines']['K']['inputs']['plant']==49
        assert a[1]['machines']['K']['inputs']['plant']==50
        result['cases'][case]['K_input_steps0_1']=[49,50]
        result['cases'][case]['K_cache_ready_flush_step0']=True
# Sweep both connection orders and both NT orders for the S06 one-tick failure.
n06=0
for po in permutations(['KA','KB']):
    for no in permutations(['K','G']):
        a,_=sim2_run('s06',9,list(po),no);b=table_run('s06',9,list(po),no);assert a==b
        assert sum(len(r['machines']['K']['sent']) for r in a[:8])==1;n06+=1
# For S07 all NT orders and all permutations within the three KG outlets.
n07=0
for po in permutations(['KG0','KG1','KG2']):
    for no in permutations(['C','A','B','K','G']):
        order=['CA','CB','AC','BK']+list(po)
        a,_=sim2_run('s07',3,order,no);b=table_run('s07',3,order,no);assert a==b
        assert a[0]['machines']['K']['inputs']['plant']==49;n07+=1
a,_=sim2_run('s07',400);b=table_run('s07',400);assert a==b
kv={'C':2,'A':1,'B':1,'K':3}
formula={n:50-3*k for n,k in kv.items()}
independent={n:50-sum(k for _ in range(3)) for n,k in kv.items()}
assert formula==independent
for row in a:
    for n in kv:
        assert row['machines'][n]['ready'] or row['machines'][n]['active']
        assert row['machines'][n]['output']>=formula[n]
result['finite400_plant_unit']={'steps_compared':400,'identical':True,'all_four_caches_nonempty':True,'output_lower_bounds':formula,'minimum_observed_output':{n:min(row['machines'][n]['output'] for row in a) for n in kv}}
result['order_sweep']={'s06':n06,'s07':n07,'independent_counts':[2*2,6*120]}
assert n06==2*2 and n07==6*120
(BASE/'s06_s07_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
