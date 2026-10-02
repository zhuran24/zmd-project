"""Drivers import only this audit's independently written models."""
import dynamics_a as A, dynamics_b as B
from fractions import Fraction
from pathlib import Path
import json,itertools,random
OUT=Path(__file__).resolve().parent
capacity=[];capacity_judgment_only=[]
for n in (1,2,3,4,6,16,32,64):
    for mod in (1,3,11):
        a=A.belt(n,mod);b=B.belt(n,mod);assert a==b,(n,mod,a,b)
        K,Q,H=a['K'],a['Q'],a['H']
        assert 8*n*Q<=H<=n*K-Q
        capacity.append({'n':n,'mod':mod,**a,'rate':str(Fraction(8*Q,K))})
        a=A.belt(n,mod,False);b=B.belt(n,mod,False);assert a==b
        K,Q,H=a['K'],a['Q'],a['H'];assert 8*n*Q<=H<=n*K-Q
        capacity_judgment_only.append({'n':n,'mod':mod,**a,'rate':str(Fraction(8*Q,K))})

x,y=A.Plant(),B.Plant();x.stock['A']=50;y.inputs[1]=50
first_nonempty=first_full=None
for s in range(6080):
    x.step();y.step();assert x.state()==y.state(),('unrepaired',s,x.state(),y.state())
    if x.stock['C']>0 and first_nonempty is None:first_nonempty=s+1
    if x.stock['C']==50 and first_full is None:first_full=s+1
    if s==5999:steady=x.state();steady_phi=x.phi2();steady_counts=steady.copy()
assert {k:v for k,v in x.state().items() if k!='routes'}=={k:v for k,v in steady.items() if k!='routes'}
unrepaired={'first_C_nonempty_steps':first_nonempty,'first_C_full_steps':first_full,
            'state6000':steady,'phi2':steady_phi,'checks':6080}

prepared=[]
for total in (38,97,98,100,137):
    for seed in range(4):
        randomizer=random.Random(96000+10*total+seed)
        l1=total//3;l2=total-l1
        x,y=A.Plant((l1,13,l2,5,5,5)),B.Plant((l1,13,l2,5,5,5))
        x.on['C']=x.on['A']=False;y.enabled[0]=y.enabled[1]=False
        waited=0
        def wait():
            global waited
            n=randomizer.randrange(1,181);waited+=n
            for _ in range(n):
                x.step();y.step();assert x.state()==y.state()
        wait();x.stock['A']=50;y.inputs[1]=50;wait()
        x.stock['C']=50;y.inputs[0]=50;wait()
        if total>97:
            for name,index in [('CA',0),('AC',2)]:
                for i in reversed(range(len(x.routes[name]['cells']))):
                    if x.routes[name]['cells'][i] is None:
                        x.fill(name,i);assert y.paths[index][i]<0;y.paths[index][i]=8
                    wait()
        x.on['C']=x.on['A']=True;y.enabled[0]=y.enabled[1]=True
        expected=200+(2*total if total>97 else 0)
        assert x.phi2()==y.phi2()==expected
        x.step();y.step();assert x.state()==y.state() and x.phi2()==y.phi2()==expected
        prepared.append({'L':total,'seed':seed,'wait_steps':waited,'phi2':expected})

# Earliest new-main-input arrivals: schedule enumeration vs countdown BFS.
switch=[]
for channels in (1,2):
    earliest=min(max(8,t2) for t1 in range(1,21) for t2 in range(t1,21)
                 if channels==2 or t2-t1>=8)
    states={(tuple([0]*channels),0)};earliest_b=None
    for s in range(1,21):
        nxt=set()
        for cds,n in states:
            cds=tuple(max(0,x-1) for x in cds)
            for take in itertools.product((0,1),repeat=channels):
                if any(t and cd for t,cd in zip(take,cds)):continue
                nn=min(2,n+sum(take));newcd=tuple(8 if t else cd for t,cd in zip(take,cds))
                if nn==2 and s>=8:earliest_b=s;break
                nxt.add((newcd,nn))
            if earliest_b is not None:break
        if earliest_b is not None:break
        states=nxt
    assert earliest==earliest_b
    switch.append({'channels':channels,'earliest':earliest})

ans={'capacity':capacity,'capacity_judgment_only':capacity_judgment_only,'unrepaired':unrepaired,'prepared':prepared,'switch':switch,
     'note':'Local states only; no full 70x70 layout or output-rate certification.'}
(OUT/'dynamics.json').write_text(json.dumps(ans,ensure_ascii=False,indent=2)+'\n')
print({'capacity_cases':len(capacity),'first_C_nonempty':first_nonempty,'first_C_full':first_full,
       'startup_cases':len(prepared),'switch':switch})
