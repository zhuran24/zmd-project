#!/usr/bin/env python3
"""Independent pipe simulation vs first-cell event recurrence for common rounds."""
import json
import random
from pathlib import Path

HERE=Path(__file__).resolve().parent

def check(seed,n,shared):
    rng=random.Random(seed)
    lengths=[rng.randint(1,48) for _ in range(n)]
    consume=[]; x=0
    for _ in range(100):
        consume.append(x); x+=rng.choice([8,8,8,9,12,25,100])
    stops=consume[-1]+n+1
    resets={t:rng.sample(range(n),n) for t in range(stops) if rng.random()<.035}
    order=list(range(n)); rng.shuffle(order)
    pipes=[[-8]*m for m in lengths]
    stock=[50]*(1 if shared else n)
    last=[-1]*n; rank=[order.index(i) for i in range(n)]
    sends=[[] for _ in range(n)]
    minimum=stock[:]; at={t:j for j,t in enumerate(consume)}
    deadlines={t+n:j for j,t in enumerate(consume)}
    for t in range(stops):
        if t in resets:
            rank=[resets[t].index(i) for i in range(n)]; last=[-1]*n
        for i,p in enumerate(pipes):
            k=0 if shared else i
            if p[-1] is not None and t-p[-1]>=8 and stock[k]<50:
                p[-1]=None; stock[k]+=1
            for a in range(len(p)-2,-1,-1):
                if p[a] is not None and t-p[a]>=8 and p[a+1] is None:
                    p[a+1]=t; p[a]=None
        choices=[i for i,p in enumerate(pipes) if p[0] is None]
        if choices:
            i=min(choices,key=lambda k:(last[k],rank[k]))
            pipes[i][0]=t; last[i]=t; sends[i].append(t)
        if t in at:
            for k in range(len(stock)): stock[k]-=n if shared else 1
        minimum=[min(a,b) for a,b in zip(minimum,stock)]
        if t in deadlines:
            j=deadlines[t]
            assert all(len(v)==j+1 for v in sends), (seed,t,'missing source fill')
            assert all(v==50 for v in stock), (seed,t,'receiver not refilled',stock)
            assert all(all(v is not None for v in p) for p in pipes), (seed,t,'road not full')
    # B: no transport arrays, queues or receiver counts; release recurrence.
    next_round=[0]*n
    previous=[None]*n
    hist=[-1]*n; rank=[order.index(i) for i in range(n)]
    event_sends=[[] for _ in range(n)]
    for t in range(stops):
        if t in resets:
            rank=[resets[t].index(i) for i in range(n)]; hist=[-1]*n
        ready=[]
        for i in range(n):
            j=next_round[i]
            if j>=len(consume): continue
            release=consume[j]+1
            if previous[i] is not None: release=max(release,previous[i]+8)
            if release<=t: ready.append(i)
        if ready:
            i=min(ready,key=lambda k:(hist[k],rank[k]))
            event_sends[i].append(t); hist[i]=previous[i]=t; next_round[i]+=1
    assert sends==event_sends,(seed,n,shared,'event recurrence differs')
    assert minimum==[50-(n if shared else 1)]*len(stock)
    return {'seed':seed,'outlets':n,'shared_receiver':shared,'lengths':lengths,
            'rounds':len(consume),'steps':stops,'history_resets':len(resets),'minimum_stock':minimum,
            'latest_fill_delay':max(sends[i][j]-consume[j] for i in range(n) for j in range(len(consume)))}

cases=[check(981000+100*n+i,n,shared) for n in range(1,7) for shared in (False,True) for i in range(10)]
out={'cases':cases,'case_count':len(cases),'steps':sum(x['steps'] for x in cases),'all_cross_equal':True,
     'all_rounds_refilled_within_n':True,'scope':'local_common_consumption_calendar_not_factory_proof'}
(HERE/'common_rounds.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='cases'},ensure_ascii=False))
