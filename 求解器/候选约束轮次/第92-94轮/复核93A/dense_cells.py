#!/usr/bin/env python3
"""Dense splitter/merger witness, independently rebuilt from the report geometry.
Representation A: absolute entry time in each individual transport cell.
No imported simulator or derivation-seat code.
"""
from pathlib import Path
from collections import Counter
from fractions import Fraction
import json,hashlib
D=Path(__file__).resolve().parent

def run(q_first):
    belts={'甲长带':[None]*16,'乙长带':[None]*16,'甲回带':[None],'乙回带':[None]*2}
    singles={n:None for n in ['甲限流','乙限流','分流器','另一准入口','甲汇流','乙汇流']}
    slots={**belts,**{n:[None] for n in singles}}
    gates={'甲限流':0,'乙限流':0}
    pointer=None # The special initial second-channel rule is distinct from a successful cursor.
    stock=80000; minimum=stock; seen={}; totals=Counter(); events=[]; trace=[]
    order=['甲回带','乙回带','甲汇流','乙汇流']+(['另一准入口','分流器'] if q_first else ['分流器','另一准入口'])+['甲限流','乙限流','甲长带','乙长带']
    dest={'甲回带':'仓库','乙回带':'仓库','甲汇流':'甲回带','乙汇流':'乙回带','另一准入口':'甲汇流','甲限流':'分流器','乙限流':'另一准入口','甲长带':'甲限流','乙长带':'乙限流'}
    def slide(t):
        for arr in belts.values():
            for i in range(len(arr)-2,-1,-1):
                if arr[i] is not None and t-arr[i]>=8 and arr[i+1] is None:
                    arr[i+1]=t;arr[i]=None
    def transfer(src,dst,t):
        nonlocal stock,minimum
        if src=='取货口甲' or src=='取货口乙':
            if not stock:return False
        elif slots[src][-1] is None or t-slots[src][-1]<8:return False
        if dst=='仓库':
            if stock>=80000:return False
        elif slots[dst][0] is not None or (dst in gates and t<gates[dst]):return False
        if src.startswith('取货口'):stock-=1
        else:slots[src][-1]=None
        if dst=='仓库':stock+=1
        else:
            slots[dst][0]=t
            if dst in gates:gates[dst]=t+40
        minimum=min(minimum,stock)
        totals[src+'→'+dst]+=1;events.append((t,src,dst));slide(t)
        return True
    for t in range(1000):
        slide(t)
        for src in order:
            if src=='分流器':
                candidates=['乙汇流','甲汇流'] if pointer is None or pointer==1 else ['甲汇流','乙汇流']
                for dst in candidates:
                    if transfer(src,dst,t):
                        pointer=1 if dst=='甲汇流' else 0
                        break
            else:transfer(src,dest[src],t)
        transfer('取货口甲','甲长带',t);transfer('取货口乙','乙长带',t)
        # Warehouse amount plus outside amounts is an exact invariant, not an unlimited sink.
        assert stock+sum(x is not None for arr in slots.values() for x in arr)==80000
        state=(tuple(tuple(-1 if x is None else min(8,t+1-x) for x in slots[n]) for n in slots),
               tuple(max(0,gates[n]-t-1) for n in gates),1 if pointer is None else pointer,stock)
        trace.append({'step':t,'stock':stock,'split_next':pointer,'state':state,'counts':dict(totals)})
        if state in seen:
            start,old=seen[state];end=t+1;period=end-start
            delta=totals-old
            sc={name:delta['分流器→'+name] for name in ['甲汇流','乙汇流']}
            result={'first':'另一准入口' if q_first else '分流器','cycle_steps':[start,end],'period_steps':period,
              'split_counts':sc,'split_rates':{n:str(Fraction(8*v,period)) for n,v in sc.items()},
              'other_input_count':delta['另一准入口→甲汇流'],'merger_output_count':delta['甲汇流→甲回带'],
              'core_stock_min':minimum,'cycle_events':[{'step':a-start,'from':b,'to':c} for a,b,c in events if start<=a<end]}
            return result,trace
        seen[state]=(t+1,totals.copy())
    raise AssertionError('No cycle')
results=[]
for first in [True,False]:
    result,trace=run(first);results.append(result)
    (D/('dense_cells_trace_q_first.json' if first else 'dense_cells_trace_split_first.json')).write_text(json.dumps(trace,ensure_ascii=False,indent=2)+'\n')
(D/'dense_cells.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([{k:r[k] for k in ['first','cycle_steps','split_rates','core_stock_min']} for r in results],ensure_ascii=False))
