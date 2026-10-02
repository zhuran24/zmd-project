"""固定偏移引理：有限状态闭包穷举（抽象事件）与独立逐格试验。"""
from itertools import combinations_with_replacement,product
import random,json
from pathlib import Path
from transport import Topology,Transport

def event_closure():
    total_states=total_transitions=total_schedules=0;cases=0;worst=[]
    for n in range(1,7):
        for D in range(0,min(2,7-n)+1):
            for offsets in combinations_with_replacement(range(D+1),n):
                if min(offsets)!=0 or max(offsets)!=D:continue
                cases+=1
                def canon(s):return tuple(sorted(zip(offsets,s)))
                def outcomes(prev,gap):
                    ready=[max(offsets[i]+1,prev[i]-gap+8) for i in range(n)]
                    done=set();schedules=0
                    def rec(t,s):
                        nonlocal schedules
                        if all(v is not None for v in s):
                            assert max(s)<=D+n,(offsets,prev,gap,s)
                            done.add(canon(s));schedules+=1;return
                        assert t<=D+n,(offsets,prev,gap,s)
                        can=[i for i in range(n) if s[i] is None and ready[i]<=t]
                        if not can:rec(t+1,s);return
                        for i in can:
                            ss=list(s);ss[i]=t;rec(t+1,ss)
                    rec(1,[None]*n)
                    return done,schedules
                initial,num=outcomes([-100]*n,8);total_schedules+=num
                todo=list(initial);seen=set(initial);maxfinish=0
                while todo:
                    state=todo.pop();prev=[s for d,s in state]
                    maxfinish=max(maxfinish,max(prev))
                    for gap in range(8,16): # >=15 已与首次全成熟情形相同。
                        nxt,num=outcomes(prev,gap)
                        total_transitions+=1;total_schedules+=num
                        for x in nxt:
                            if x not in seen:seen.add(x);todo.append(x)
                total_states+=len(seen);worst.append({'n':n,'D':D,'offsets':offsets,'states':len(seen),'latest':maxfinish})
    return {'cases':cases,'closed_states':total_states,'state_gap_transitions':total_transitions,
            'complete_service_schedules':total_schedules,'deadline_violations':0,'cases_detail':worst}

def physical_trials():
    rng=random.Random(108400);totalsteps=rounds=compared=0;cases=[]
    patterns_to_test=[([0]*6,False),([0,0,2],False),([0,2,2],False),([0,0],True),([2,2,2],True),([0],False)]
    for trial in range(48):
        offsets,common=patterns_to_test[trial%len(patterns_to_test)];n=len(offsets);D=max(offsets)
        # 用共同请求列最早时刻规范化，不改变相对偏移。
        baseoffset=min(offsets);offsets=[d-baseoffset for d in offsets];D=max(offsets)
        routes=[('源', '同格' if common else f'终点{i}', '货') for i in range(n)]
        patterns=[''.join(rng.choice('TB') for _ in range(rng.randint(1,35))) for _ in range(n)]
        topo=Topology(routes,patterns,108400+trial)
        a=Transport(topo);b=Transport(topo,True)
        inva={dest:50 for _,dest,_ in routes};invb=dict(inva)
        starts=[4]
        for j in range(70):starts.append(starts[-1]+rng.choice([8,8,8,9,16,40]))
        consume={}
        for j,x in enumerate(starts):
            for r,d in enumerate(offsets):consume.setdefault(x+d,[]).append(r)
        deadline={x+D+n:j for j,x in enumerate(starts)}
        rank=topo.order(rng);lasts=[None]*n;current_s={};current_r={}
        for t in range(starts[-1]+D+n+1):
            if t%3==0:
                rank=topo.order(rng)
                if rng.randrange(2):a.reset_history();b.reset_history()
            for obj,inv in [(a,inva),(b,invb)]:
                def accept(r):
                    dest=routes[r][1]
                    if inv[dest]>=50:return False
                    inv[dest]+=1;return True
                obj.step(t,rank,accept)
            ready=[r for r in range(n) if a.entered[topo.paths[r][0]] is None]
            for r in ready:
                if r not in current_r:current_r[r]=t
            if ready:
                r=rng.choice(ready)
                for obj in [a,b]:obj.put(topo.paths[r][0],t,'源');obj.sent[r]+=1
                assert r not in current_s
                current_s[r]=t
            for r in consume.get(t,[]):
                dest=routes[r][1];inva[dest]-=1;invb[dest]-=1
            assert a.observable(t)==b.observable(t) and inva==invb
            compared+=1
            if t in deadline:
                j=deadline[t];x=starts[j]
                assert len(current_s)==n and all(e is not None for e in a.entered) and all(v==50 for v in inva.values())
                for r in range(n):
                    expected=max(x+offsets[r]+1, -100 if lasts[r] is None else lasts[r]+8)
                    assert current_r[r]==expected,(trial,j,r,current_r[r],expected)
                lasts=[current_s[r] for r in range(n)];current_s={};current_r={};rounds+=1
        totalsteps+=t+1;cases.append({'n':n,'D':D,'common_inventory':common,'maxlen':max(map(len,patterns))})
    return {'trials':len(cases),'rounds':rounds,'steps':totalsteps,'physical_scalar_comparisons':compared,
            'exact_head_recurrence_violations':0,'deadline_violations':0,'trial_types':patterns_to_test}

if __name__=='__main__':
    res={'event_closure':event_closure(),'physical_trials':physical_trials()}
    Path(__file__).with_suffix('.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:{x:y for x,y in v.items() if x!='cases_detail'} for k,v in res.items()},ensure_ascii=False,indent=2))
