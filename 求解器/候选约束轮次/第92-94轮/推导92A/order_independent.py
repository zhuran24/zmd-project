#!/usr/bin/env python3
"""Independent integer recurrence; no simulator import, no object movement API."""
import json,pathlib
from fractions import Fraction
def calculate(first):
    names=('甲带','乙带','甲准入','乙准入','分流','旁入','汇流','汇后带','另一支','支后带')
    arr={n:[None]*({'甲带':16,'乙带':16,'支后带':2}.get(n,1)) for n in names}
    stock=80000;next_open={'甲准入':0,'乙准入':0};cursor=1;t=0;seen={};events=[];moves=[]
    # Cursor 1 means E first: D-to-M forms before D-to-E in both blueprints.
    def shift(n):
        v=arr[n]
        for i in range(len(v)-2,-1,-1):
            if v[i] is not None and t-v[i]>=8 and v[i+1] is None:v[i+1],v[i]=t,None
    def move(n,d):
        nonlocal stock
        if arr[n][-1] is None or t-arr[n][-1]<8:return False
        if d=='核心':
            if stock>=80000:return False
            arr[n][-1]=None;stock+=1;moves.append((t,n,d));shift(n);return True
        if arr[d][0] is not None:return False
        if d in next_open and t<next_open[d]:return False
        arr[n][-1]=None;arr[d][0]=t;moves.append((t,n,d))
        if d in next_open:next_open[d]=t+40
        shift(n);shift(d);return True
    while t<5000:
        key=(tuple(tuple(None if x is None else min(8,t-x) for x in arr[n]) for n in names),tuple(max(0,next_open[n]-t) for n in ['甲准入','乙准入']),cursor,stock)
        if key in seen:
            lo,hi=seen[key],t;break
        seen[key]=t
        for n in names:shift(n)
        # C and E are simultaneous non-splitter upstreams of the core.
        move('汇后带','核心');move('支后带','核心');move('汇流','汇后带');move('另一支','支后带')
        for n in (['旁入','分流'] if first=='旁入' else ['分流','旁入']):
            if n=='旁入':move(n,'汇流')
            else:
                choices=['汇流','另一支']
                for j in [cursor,1-cursor]:
                    if move(n,choices[j]):events.append((t,choices[j]));cursor=1-j;break
        move('甲准入','分流');move('乙准入','旁入')
        move('甲带','甲准入');move('乙带','乙准入')
        for n in ['甲带','乙带']:
            if arr[n][0] is None and stock>0:arr[n][0]=t;stock-=1;shift(n)
        t+=1
    else:raise AssertionError('no cycle')
    counts={d:sum(lo<=s<hi and z==d for s,z in events) for d in ['汇流','另一支']}
    return {'first':first,'cycle_steps':[lo,hi],'period_steps':hi-lo,'split_counts':counts,'other_input_count':sum(lo<=s<hi and n=='旁入' for s,n,d in moves),'merger_output_count':sum(lo<=s<hi and n=='汇流' for s,n,d in moves),'split_rates':{d:str(Fraction(8*v,hi-lo)) for d,v in counts.items()},'core_stock_min':min(k[-1] for k in seen),'cycle_events':[{'step':s-lo,'to':d} for s,d in events if lo<=s<hi]}
if __name__=='__main__':
    result=[calculate('旁入'),calculate('分流')]
    path=pathlib.Path(__file__).with_name('order_independent.json');path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    reference=json.loads(path.with_name('order_reference.json').read_text())
    for a,b in zip(result,reference):
        assert a['cycle_steps']==b['cycle_steps']
        assert list(a['split_counts'].values())==list(b['split_counts'].values())
        assert a['core_stock_min']==b['core_stock_min']
        assert a['other_input_count']==b['other_input_count']
        assert a['merger_output_count']==b['merger_output_count']
        assert a['split_counts']['汇流']+a['other_input_count']==a['merger_output_count']
    print(json.dumps({'independent_agreement':True,'results':result},ensure_ascii=False,indent=2))
