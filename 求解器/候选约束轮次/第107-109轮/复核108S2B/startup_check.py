"""不直接装运输格、不编辑缓存的装路/开关试验。"""
import json
from collections import Counter
from pathlib import Path
from factory_check import Factory,setup
from transport import Transport

def run(seed,maxlen):
    topo,rng=setup(seed,maxlen,'mixed')
    a=Factory(topo);b=Factory(topo,True)
    for f in (a,b):
        f.trans=Transport(topo,f.trans.logical,empty=True)
        for n in f.nodes:
            f.inv[n]={x:0 for x in f.inv[n]};f.output[n]=0;f.due[n]=None;f.enabled[n]=False
    supplied=Counter();offline=0;compared=0
    def advance(steps):
        nonlocal offline,compared
        for _ in range(steps):
            if not a.rank or a.t%11==0:
                rank=topo.order(rng);clear=bool(rng.randrange(2));offline+=1
                a.offline(rank,clear);b.offline(rank,clear)
            a.step(contracts=False);b.step(contracts=False)
            assert a.observable()==b.observable();compared+=1
    def fill():
        for n,rec in a.nodes.items():
            for x in a.inv[n]:
                supplied[x]+=50-a.inv[n][x]
                a.inv[n][x]=b.inv[n][x]=50
            if rec[4]==8:
                supplied[rec[2]]+=50-a.output[n]
                a.output[n]=b.output[n]=50
    nonfinal=[n for n,rec in a.nodes.items() if rec[4]==8]
    rounds=0;fills=0
    while True:
        rounds+=1;assert rounds<500
        for f in (a,b):
            for n in f.enabled:f.enabled[n]=False
        while True:
            fill();fills+=1
            advance(8*(maxlen+8)+rng.randint(20,80))
            if all(a.trans.entered[c] is not None for r,(_,dest,_) in enumerate(a.routes) if dest!='核心' for c in topo.paths[r]):break
        fill()
        if all(a.due[n] is not None and a.due[n]<=a.t for n in nonfinal):break
        for f in (a,b):
            for n in nonfinal:f.enabled[n]=True
        advance(rng.randint(16,200))
    advance(40)
    for n in nonfinal:
        assert a.output[n]==50 and a.due[n] is not None and a.due[n]<=a.t
    assert all(v==50 for inv in a.inv.values() for v in inv.values())
    for c,e in enumerate(a.trans.entered):
        r,_=topo.owner[c]
        if a.routes[r][1]=='核心':assert e is None
        else:assert e is not None and a.t-e>=8 and a.trans.last[c]==topo.expected_last[c]
    prep=compared
    for f in (a,b):
        for n in f.enabled:f.enabled[n]=True
    for _ in range(2400):
        a.step();b.step();assert a.observable()==b.observable();compared+=1
    return {'seed':seed,'maxlen':maxlen,'is_layout':False,'rounds':rounds,'fill_waits':fills,
            'preparation_steps':prep,'steps_compared':compared,'offline_rebuilds':offline,
            'manual_transport_insertions':0,'manual_cache_edits':0,'startup_reached':True,
            'manual_supplied':dict(supplied),'violations':0}

if __name__=='__main__':
    results=[run(108301,4),run(108302,17),run(108303,72)]
    Path(__file__).with_suffix('.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(results,ensure_ascii=False,indent=2))
