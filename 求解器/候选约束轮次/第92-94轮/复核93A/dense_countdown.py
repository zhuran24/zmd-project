#!/usr/bin/env python3
"""Independent dense-witness encoding B: a graph of occupancy countdowns.
Schedule derived from connection times and layers; no sim2 or audit-A imports.
"""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import json
D=Path(__file__).resolve().parent

def calculate(early):
    lengths={'甲长带':16,'乙长带':16,'甲回带':1,'乙回带':2,
             '甲限流':1,'乙限流':1,'分流器':1,'另一准入口':1,'甲汇流':1,'乙汇流':1}
    index={};n=0
    for name,length in lengths.items():index[name]=list(range(n,n+length));n+=length
    cells=[-1]*n # -1 empty, otherwise steps still to wait
    inner=[(idx[i],idx[i+1]) for name,idx in index.items() if name.endswith('带') for i in range(len(idx)-1)]
    graph={'甲长带':['甲限流'],'乙长带':['乙限流'],'甲限流':['分流器'],'乙限流':['另一准入口'],
           '分流器':['甲汇流','乙汇流'],'另一准入口':['甲汇流'],
           '甲汇流':['甲回带'],'乙汇流':['乙回带'],'甲回带':['仓库'],'乙回带':['仓库']}
    # Connection ranks follow the two concrete construction orders.
    ranks={('甲长带','甲限流'):125,('乙长带','乙限流'):145,('甲限流','分流器'):5,
       ('乙限流','另一准入口'):6,('甲汇流','甲回带'):100,('乙汇流','乙回带'):101,
       ('甲回带','仓库'):100,('乙回带','仓库'):102}
    if early=='另一准入口':ranks.update({('另一准入口','甲汇流'):2,('分流器','甲汇流'):3,('分流器','乙汇流'):4})
    else:ranks.update({('另一准入口','甲汇流'):4,('分流器','甲汇流'):2,('分流器','乙汇流'):3})
    layers={}
    def layer(name):
        if name not in layers:
            choices=[v for v in graph[name] if v in graph and graph[v]]
            values=[layer(v)+1 for v in choices]
            # This witness intentionally gives both splitter branches the same layer.
            assert len(set(values))<=1
            layers[name]=values[0] if values else 1
        return layers[name]
    for name in graph:layer(name)
    schedule=sorted(graph,key=lambda u:(layers[u],min(ranks[u,v] for v in graph[u])))
    quota={'甲限流':0,'乙限流':0}; turn=1;warehouse=80000;minimum=warehouse
    events=[];counts=Counter();seen={};traces=[]
    def settle():
        changed=True
        while changed:
            changed=False
            for a,b in inner:
                if cells[a]==0 and cells[b]<0:
                    cells[a]=-1;cells[b]=8;changed=True
    def attempt(source,target,t):
        nonlocal warehouse,minimum
        if source in index:
            a=index[source][-1]
            if cells[a]!=0:return False
        elif warehouse<=0:return False
        if target in index:
            b=index[target][0]
            if cells[b]>=0 or quota.get(target,0)>0:return False
        elif warehouse==80000:return False
        if source in index:cells[a]=-1
        else:warehouse-=1
        if target in index:
            cells[b]=8
            if target in quota:quota[target]=40
        else:warehouse+=1
        counts[source+'→'+target]+=1;events.append((t,source,target));minimum=min(minimum,warehouse)
        settle();return True
    for step in range(1000):
        # Full state at a step boundary. Absolute elapsed time is not part of the machine state.
        state=(tuple(cells),tuple(quota.items()),turn,warehouse)
        if state in seen:
            start,old=seen[state];period=step-start;delta=counts-old
            return {'first':early,'cycle_steps':[start,step],'period_steps':period,
                'split_counts':{u:delta['分流器→'+u] for u in ['甲汇流','乙汇流']},
                'split_rates':{u:str(Fraction(8*delta['分流器→'+u],period)) for u in ['甲汇流','乙汇流']},
                'other_input_count':delta['另一准入口→甲汇流'],'merger_output_count':delta['甲汇流→甲回带'],
                'core_stock_min':minimum,'layers':layers,'schedule':schedule,
                'cycle_events':[{'step':t-start,'from':u,'to':v} for t,u,v in events if start<=t<step]},traces
        seen[state]=(step,counts.copy())
        settle();judged=set()
        for source in schedule:
            if source in judged:continue
            if source=='分流器':
                judged.add(source)
                for j in [turn,1-turn]:
                    if attempt(source,graph[source][j],step):turn=1-j;break
            else:
                target=graph[source][0]
                # Rule 31: mark every non-splitter component sharing this receiver judged.
                group=[u for u in schedule if u!='分流器' and graph[u]==[target]]
                assert not (set(group)&judged)
                judged.update(group)
                for u in sorted(group,key=lambda u:ranks[u,target]):attempt(u,target,step)
        attempt('取货口甲','甲长带',step);attempt('取货口乙','乙长带',step)
        assert warehouse+sum(v>=0 for v in cells)==80000
        traces.append({'step':step,'warehouse':warehouse,'countdowns':cells[:],'quota':quota.copy(),'turn':turn})
        cells[:]=[max(0,v-1) if v>=0 else -1 for v in cells]
        for name in quota:quota[name]=max(0,quota[name]-1)
    raise AssertionError('No cycle')

results=[]
for early in ['另一准入口','分流器']:
    r,trace=calculate(early);results.append(r)
    (D/('dense_countdown_trace_q_first.json' if early=='另一准入口' else 'dense_countdown_trace_split_first.json')).write_text(json.dumps(trace,ensure_ascii=False,indent=2)+'\n')
(D/'dense_countdown.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
# Independent results are compared only here, after both simulations have terminated.
A=json.loads((D/'dense_cells.json').read_text())
for a,b in zip(A,results):
    for key in ['cycle_steps','period_steps','split_counts','split_rates','other_input_count','merger_output_count','core_stock_min','cycle_events']:
        assert a[key]==b[key],(key,a[key],b[key])
print(json.dumps({'status':'PASS','independent_agreement':True,'cycles':[r['cycle_steps'] for r in results],'minimum_warehouse':[r['core_stock_min'] for r in results]},ensure_ascii=False))
