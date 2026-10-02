#!/usr/bin/env python3
"""Run the switch/fill/wait debugging procedure, never writing a cache."""
import json
import random
from collections import Counter
from pathlib import Path
from types import MethodType
from factory_check import Layout, rebuild
from debug_engine_a import Factory as SwitchFactory
from debug_engine_b import EngineB

HERE=Path(__file__).resolve().parent
quota=json.loads((HERE/'startup_budget.json').read_text())['feedstock_quota_by_item']

def run(seed,maxlen):
    rng=random.Random(seed)
    f=Layout(seed,maxlen,layer=False,separate=True)
    # A newly cleaned, empty installation. This initialization represents the
    # empty start, not an operation used later to prepare a cache.
    for u in f.ms:
        u.stock=Counter(); u.out=0; u.done=False; u.remaining=0; u.enabled=False
    for r in f.rs: r.cells=[None]*len(r.cells)
    f.step=MethodType(SwitchFactory.step,f)
    b=EngineB(f)
    b.enabled=[getattr(u,'enabled',False) for u in b.units]
    nonfinal=[u for u in f.ms if u.typ not in ('封装机','灌装机')]
    roads=[r for r in f.rs if r.target is not f.sink]
    used=Counter(); operations=[]; offline=[]

    def step(count):
        for _ in range(count):
            if rng.random()<.004:
                rebuild(f,rng); b.copy_order(f,reset=True); offline.append(f.t)
            f.step(); b.step(); b.compare(f)
            assert f.received==b.received

    def enable(which):
        target=set(which)
        for u in f.ms:
            u.enabled=u in target; b.enabled[b.index[u]]=u.enabled
        operations.append({'t':f.t,'action':'switch','enabled_machines':len(target)})

    def insert_input(u,k):
        q=50-u.stock[k]
        if q:
            u.stock[k]+=q; b.stock[b.index[u]][k]=u.stock[k]; used[k]+=q

    rounds=0
    for rounds in range(1,101):
        enable([])
        # Off machines cannot consume the just-filled input stacks.
        for u in f.ms:
            for k in u.recipe[0]: insert_input(u,k)
            step(rng.randrange(4))
        for u in nonfinal:
            q=50-u.out
            if q:
                u.out+=q; b.out[b.index[u]]=u.out; used[u.recipe[1]]+=q
            step(rng.randrange(4))
        # Correct warehouse-sourced goods, placed only on non-product roads.
        for r in roads:
            for j in reversed(range(len(r.cells))):
                if r.cells[j] is None:
                    r.cells[j]=f.t; b.cargo[r.index][j]=0; used[r.kind]+=1
                step(rng.randrange(3))
        for u in nonfinal:
            q=50-u.out
            if q:
                u.out+=q; b.out[b.index[u]]=u.out; used[u.recipe[1]]+=q
            step(rng.randrange(3))
        assert all(u.stock[k]==50 for u in f.ms for k in u.recipe[0])
        assert all(u.out==50 for u in nonfinal)
        assert all(all(c is not None for c in r.cells) for r in roads)
        if all(u.done for u in nonfinal): break
        # All nonfinal recipes last eight steps. Any wait >=16 suffices here;
        # the varied, longer waits verify that no exact timing is required.
        enable(nonfinal); step(rng.randrange(16,65)); enable([])
    else: raise AssertionError('preparation did not terminate in the test budget')
    step(rng.randrange(16,65))
    assert all(u.done and u.remaining==0 and u.out==50 for u in nonfinal)
    assert all(u.stock[k]==50 for u in f.ms for k in u.recipe[0])
    assert all(all(c is not None and f.t-c>=8 for c in r.cells) for r in roads)
    assert all(not u.done and not u.remaining and not u.out for u in f.ms if u not in nonfinal)
    assert all(used[k]<=quota[k] for k in used),(used,quota)
    ready=f.t
    enable(f.ms)
    fast=[u for u in nonfinal if u not in f.plant_machines and u.name not in ('塑形5','荞研磨5')]
    for _ in range(2400):
        step(1)
        assert all(u.out==50 and (u.done or u.remaining) and all(u.stock[k]>=50-v for k,v in u.recipe[0].items()) for u in fast)
    return {'seed':seed,'maxlen':maxlen,'rounds':rounds,'ready_step':ready,'cross_checked_steps':f.t,
            'manual_items':dict(used),'cache_write_operations':0,'within_proved_feedstock_budget':True,
            'offline_count':len(offline),'operation_log':operations,
            'prepared_state_pass':True,'fast_service_after_start_pass':True}

cases=[run(98400+i,L) for i,L in enumerate((1,4,12))]
out={'cases':cases,'all_pass':True,'independent_step_engines_equal':True,
     'total_steps':sum(x['cross_checked_steps'] for x in cases)}
(HERE/'startup_check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='cases'}|{'rounds':[x['rounds'] for x in cases]},ensure_ascii=False))
