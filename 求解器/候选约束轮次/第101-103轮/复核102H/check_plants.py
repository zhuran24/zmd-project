from copy import deepcopy
from pathlib import Path
from random import Random
import json
from plant_models import Absolute, Countdown

OUT=Path(__file__).resolve().parent

def settings(rng,t,n,mode,frequency=17,allow_pause=False):
    co=[0,1]; ko=list(range(n)); mo=list(range(4))
    rng.shuffle(co); rng.shuffle(ko); rng.shuffle(mo)
    return dict(offline=(t%frequency==0 if frequency<5 else rng.randrange(frequency)==0),
                clear=mode=='clear',c_order=co,k_order=ko,machine_order=mo,
                drain=[rng.randrange(4)!=0 for _ in range(n)],
                enabled=[True,True,not allow_pause or rng.randrange(5)!=0,not allow_pause or rng.randrange(5)!=0])

def paired(initial,k,n):
    return Absolute(initial,k,n),Countdown(initial,k,n)

def step_pair(a,b,t,config):
    old=a.phi2()
    ea=a.step(t,config); eb=b.step(t,config)
    assert ea==eb
    assert a.canonical(t)==b.canonical(t), (t,a.canonical(t),b.canonical(t))
    assert a.phi2()==b.phi2()==old+sum(1 if e=='A' else -1 for e in ea)
    return a.phi2()

def general_cases():
    rng=Random(10102026)
    count=states=0
    tight_preparation=None
    for trial in range(180):
        lengths=[rng.randint(1,10) for _ in range(4)]
        bias=[0,1,2,47,48,49,50]
        initial=dict(machines=[[rng.choice(bias),rng.choice(bias),rng.choice([None,0,1,2,7,8])]
                               for _ in range(4)],
                     roads=[[None if rng.randrange(5)==0 else rng.randrange(9) for _ in range(l)] for l in lengths])
        k=rng.choice([2,3]); n=rng.randrange(k+1)
        for mode in ['retain','clear']:
            a,b=paired(initial,k,n)
            start=a.phi2(); normal=None; m=mn=0
            h=2*(lengths[0]+lengths[1]+150)
            hn=h+52
            for t in range(1,1201):
                config=settings(rng,t,n,mode,frequency=1 if trial%11==0 else 19,allow_pause=True)
                if config['offline'] and config['clear']:
                    m+=1
                    if t>1: mn+=1
                phi=step_pair(a,b,t,config)
                assert phi>=min(start-m-1,h-m),(trial,mode,t,start,phi,m)
                if start>=2: assert phi>=1
                if t==1: normal=phi
                else: assert phi>=min(normal-mn-1,hn-mn),(trial,mode,t,normal,phi,mn)
                if mode=='retain' and len(a.events)>=2 and a.events[-1][0]==t and a.events[-2][1]==a.events[-1][1]=='B':
                    offset=phi-2*(lengths[0]+lengths[1])
                    if tight_preparation is None or offset<tight_preparation['offset2']:
                        tight_preparation=dict(offset2=offset,trial=trial,step=t)
                states+=1
            count+=1
    return dict(cases=count,compared_steps=states,violations=0,lowest_sampled_BB_offset2=tight_preparation)

def full_cases():
    rng=Random(177150176)
    count=states=0
    maxwait=0
    minima=[50,50,50,50]
    for trial in range(100):
        k=2+trial%2; n=trial%(k+1)
        lengths=[rng.randint(1,18) for _ in range(4)]
        initial=dict(machines=[[50,50,rng.randrange(9)] for _ in range(4)],
                     roads=[[rng.randrange(9) for _ in range(l)] for l in lengths])
        for mode in ['retain','clear']:
            a,b=paired(initial,k,n)
            assert a.phi2()==2*(lengths[0]+lengths[1]+177)
            wait=[None]*n
            for t in range(1,1601):
                config=settings(rng,t,n,mode,1 if trial%3==0 else 13)
                # Realistic on/off blocks as well as an adversarial per-step priority.
                config['drain']=[v and (t%127)<90 for v in config['drain']]
                for j,entered in enumerate(a.outlets):
                    empty=entered is None or t-entered>=8 and config['drain'][j]
                    if empty and wait[j] is None: wait[j]=t
                step_pair(a,b,t,config)
                assert all(row[2] is not None for row in a.m)
                assert a.m[2][0]>=49 and a.m[3][0]>=49
                assert a.m[2][1]>=49 and a.m[3][1]>=50-k
                assert a.roads[2][0] is not None and a.roads[3][0] is not None
                minima=[min(x,y) for x,y in zip(minima,[a.m[2][0],a.m[3][0],a.m[2][1],a.m[3][1]])]
                for j,start in enumerate(wait):
                    if start is not None:
                        if a.outlets[j] is not None:
                            maxwait=max(maxwait,t-start)
                            assert t-start<=n-1
                            wait[j]=None
                        else: assert t-start<n-1
                states+=1
            count+=1
    return dict(cases=count,compared_steps=states,violations=0,
                min_Braw_Kraw_Bout_Kout=minima,max_K_wait_steps=maxwait)

def old_bound_witness():
    # Five CA cells and a 35-cell AC detour can be laid out; geometry is separate.
    initial=dict(machines=[[0,2,None],[50,49,8],[0,0,None],[0,0,None]],
                 roads=[[8]*5,[None]*35,[None]*11,[None]*5])
    runs={}
    for mode in ['retain','clear']:
        a,b=paired(initial,2,2)
        start=a.phi2()
        trace=[]
        for t in range(1,25):
            config=dict(offline=t==5,clear=mode=='clear',c_order=[1,0],k_order=[0,1],
                        machine_order=[0,1,2,3],drain=[True,True])
            phi=step_pair(a,b,t,config)
            trace.append(dict(step=t,phi2=phi,machines=deepcopy(a.canonical(t)[0]),
                              C_success=[e for s,e in a.events if s==t]))
        runs[mode]=dict(initial_phi2=start,events=a.events,trace=trace)
    clear9=runs['clear']['trace'][8]['phi2']
    retain9=runs['retain']['trace'][8]['phi2']
    assert clear9==runs['clear']['initial_phi2']-2
    assert retain9==runs['retain']['initial_phi2']
    return dict(initial=initial,runs=runs,violation_at_step=9,
                old_bound2=runs['clear']['initial_phi2']-1,new_bound2=clear9)

def low_inventory_cycles():
    result=[]
    for lengths in [(1,1,1,1),(5,35,11,5),(2,3,4,5)]:
        for k in [2,3]:
            for clear in [False,True]:
                initial=dict(machines=[[0,2,None],[0,0,None],[0,0,None],[0,0,None]],
                             roads=[[None]*l for l in lengths])
                a,b=paired(initial,k,k)
                seen={}
                for t in range(1,20001):
                    setting=dict(offline=True,clear=clear,c_order=[1,0],k_order=list(reversed(range(k))),
                                 machine_order=[3,2,1,0],drain=[True]*k)
                    step_pair(a,b,t,setting)
                    assert a.phi2()>=1
                    key=json.dumps(a.canonical(t)[:4])
                    if key in seen:
                        old,counts,deliv=seen[key]
                        delta=[x-y for x,y in zip(a.starts,counts)]
                        assert len(set(delta))==1 and delta[0]>0
                        assert a.delivered-deliv==k*delta[0]
                        result.append(dict(lengths=lengths,k=k,clear=clear,period=t-old,
                                           starts=delta,powder=a.delivered-deliv))
                        break
                    seen[key]=(t,list(a.starts),a.delivered)
                else: raise AssertionError('cycle not found within independent test limit')
    return result

def main():
    out=dict(general=general_cases(),full=full_cases(),old_bound_witness=old_bound_witness(),
             low_inventory_cycles=low_inventory_cycles())
    (OUT/'plants.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k not in ['old_bound_witness']},ensure_ascii=False))

if __name__=='__main__': main()
