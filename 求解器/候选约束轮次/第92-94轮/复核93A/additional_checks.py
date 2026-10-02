#!/usr/bin/env python3
"""Independent supporting-premise and subset-channel adversarial checks."""
from pathlib import Path
from collections import Counter
from random import Random
import json,re,hashlib
D=Path(__file__).resolve().parent
R=json.loads((D/'arithmetic_matrix.json').read_text())['recipes']
# Two conserved mineral weights. Production never creates or destroys either weight.
blue={'蓝铁矿':1,'蓝铁块':1,'蓝铁粉末':1,'致密蓝铁粉末':2,'钢块':2,'钢制零件':2,'钢质瓶':4,'高容谷地电池':20,'精选荞愈胶囊':40}
source={'源矿':1,'源石粉末':1,'致密源石粉末':2,'高容谷地电池':30}
weight_checks=[]
for r in R:
    for weights in [blue,source]:
        before=sum(n*weights.get(a,0) for a,n in r['inputs'].items())
        after=sum(n*weights.get(a,0) for a,n in r['outputs'].items())
        assert before==after
        weight_checks.append([r['line'],before,after])
# For every machine, one input slot occupied by a material absent from all recipes
# leaves fewer usable species slots than every recipe requires.
input_slots={'粉碎机':1,'精炼炉':1,'研磨机':2,'塑形机':1,'配件机':1,'种植机':1,'采种机':1,'封装机':2,'灌装机':2}
for f,slots in input_slots.items():
    assert all(len(r['inputs'])>slots-1 for r in R if r['factory']==f)
assert all('砂叶粉末' in r['inputs'] for r in R if r['factory']=='研磨机')

# Adversarial extension of the four-group exhaustive test:
# selected channels can be only part of a level; other outlets are allowed to be blocked.
# Total group size, including goods sent through other channels, obeys the candidate.
rng=Random(93092);subset_cases=0;subset_successes=0;digest=hashlib.sha256()
for mode in ['transport','nontransport']:
    for case in range(20000):
        m=rng.randint(2,3 if mode=='transport' else 6)
        k=rng.randint(1,m-1)
        selected=sorted(rng.sample(range(m),k)); selected_set=set(selected)
        order=list(range(m))
        if mode=='nontransport':rng.shuffle(order)
        initial=[x for x in order if x in selected_set]
        groups=[rng.randrange(k+1)]
        for _ in range(11):groups.append(rng.randrange(k-groups[-1]+1))
        delays=[rng.randrange(2) for _ in groups]
        late=[rng.randrange(2) for _ in range(m)]
        free_at=[-1]*m;busy=[False]*m;pending=0;actual=[];full_trace=[]
        for t in range(112):
            for j in range(m):
                if busy[j] and free_at[j]==t and not late[j]:busy[j]=False
            g=t//8
            if t%8==0 and g<len(groups) and not delays[g]:pending+=groups[g]
            extra_ok={j:bool(rng.randrange(2)) for j in range(m) if j not in selected_set}
            if pending:
                eligible=[j for j in order if not busy[j] and (j in selected_set or extra_ok[j])]
                if eligible:
                    j=eligible[0];pos=order.index(j)
                    pending-=1;busy[j]=True;free_at[j]=t+8
                    full_trace.append((t,j))
                    if mode=='transport':order=order[pos+1:]+order[:pos+1]
                    else:order.remove(j);order.append(j)
                    if j in selected_set:actual.append(j)
            for j in range(m):
                if busy[j] and free_at[j]==t and late[j]:busy[j]=False
            if t%8==0 and g<len(groups) and delays[g]:pending+=groups[g]
        assert not pending
        assert len(full_trace)==sum(groups)
        assert all(j==initial[i%k] for i,j in enumerate(actual)),(mode,m,k,initial,groups,actual)
        digest.update(json.dumps([mode,m,k,selected,initial,groups,delays,late,full_trace],separators=(',',':')).encode())
        subset_cases+=1;subset_successes+=len(actual)

# The old nontransport connection-order assertion: two different encodings of recency.
connections=['A','B','C'];times={'A':-30,'B':-10,'C':-20};trace_a=[]
for t in range(0,120,8):
    j=min(connections,key=lambda j:(times[j],connections.index(j)))
    trace_a.append(j);times[j]=t
queue=['A','C','B'];trace_b=[]
for _ in range(15):j=queue.pop(0);trace_b.append(j);queue.append(j)
assert trace_a==trace_b==['A','C','B']*5

text=(D.parent/'前提快照'/'求解约束.txt').read_text()
needles=re.compile('阻尼|存货优先级|判定次序|判定先后|同一时刻')
matched=[i for i,line in enumerate(text.splitlines(),1) if needles.search(line)]
assert len(matched)==19
candidates=json.loads((D.parent/'推导92A'/'candidates.json').read_text())
assert len(candidates)==15 and len({c['name'] for c in candidates})==15
out={'status':'PASS','mineral_conservation_equalities':len(weight_checks),'mineral_weights':{'蓝铁矿':blue,'源矿':source},
     'all_nine_mistaken_input_slot_checks':True,'grinder_two_main_materials_deadlock':True,
     'subset_channel_cases':subset_cases,'selected_successes_checked':subset_successes,'subset_trace_sha256':digest.hexdigest(),
     'subset_violations':0,'old_LRU_order_counterexample':{'connection_order':connections,'initial_success_order':['A','C','B'],'next_15_channels':trace_a,'two_encodings_agree':True},
     'old_term_matched_lines':matched,'old_term_line_count':len(matched),'actual_candidate_count':len(candidates),'actual_candidate_names':[c['name'] for c in candidates]}
(D/'additional_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['status','mineral_conservation_equalities','subset_channel_cases','selected_successes_checked','subset_violations','actual_candidate_count']},ensure_ascii=False))
