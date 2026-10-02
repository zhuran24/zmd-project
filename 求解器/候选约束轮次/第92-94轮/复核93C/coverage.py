"""Small additional adversarial checks; independent of the main interpreters."""
from fractions import Fraction
from itertools import permutations,product
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def initial_history_rotation():
    checked=0
    # Prior success history is not required to be empty when all heads are
    # empty at the theorem's starting step. Distinct finite times are required.
    for k in (2,3):
        for history in product((None,-10,-4,-1),repeat=k):
            used=[x for x in history if x is not None]
            if len(set(used)) != len(used):
                continue
            for connection in permutations(range(k)):
                for supply in (range(24),(0,7,8,16,23),(7,15,23)):
                    last=list(history)
                    heads=[None]*k
                    ranks=list(connection)
                    queue=sorted(range(k),key=lambda j:(-1000 if last[j] is None else last[j],ranks.index(j)))
                    ever=[x is not None for x in history]
                    ready=[0]*k
                    a=b=0
                    first=[]
                    second=[]
                    for t in range(64):
                        if t%3==0:
                            ranks=ranks[1:]+ranks[:1]
                            queue=[j for j in ranks if not ever[j]]+[j for j in queue if ever[j]]
                        if t in supply:
                            a+=k;b+=k
                        for j in range(k):
                            if heads[j] is not None and heads[j]<=t:
                                heads[j]=None
                        for j in sorted(range(k),key=lambda x:(-1000 if last[x] is None else last[x],ranks.index(x))):
                            if a and heads[j] is None:
                                a-=1;heads[j]=t+8;last[j]=t;first.append(j)
                                break
                        if b and ready[queue[0]]<=t:
                            j=queue.pop(0);queue.append(j)
                            b-=1;ready[j]=t+8;ever[j]=True;second.append(j)
                        assert a==b and first==second
                    assert all(v==first[i%k] for i,v in enumerate(first))
                    checked+=1
    return dict(cases=checked,violations=0)


def backpressure_exhaustion():
    cases=0
    # A closed route gets no new supply for eight steps. Compare pure-belt
    # eager internal movement and separately judged gate countdown movement.
    # Receiver is either already full or has one free correct-material slot.
    # All ages 0..8 and empty cells, lengths 1..3, are enumerated.
    for length in range(1,4):
        for start in product(range(-1,9),repeat=length):
            for stock in (49,50):
                a=[None if z<0 else z for z in start]
                b=list(start)
                ia=ib=stock
                moved_a=moved_b=0
                for tick in range(1,9):
                    # Encoding A: absolute eligibility times.
                    for j in range(length-2,-1,-1):
                        if a[j] is not None and a[j]<=tick and a[j+1] is None:
                            a[j],a[j+1]=None,tick+8;moved_a+=1
                    if a[-1] is not None and a[-1]<=tick and ia<50:
                        a[-1]=None;ia+=1;moved_a+=1
                        for j in range(length-2,-1,-1):
                            if a[j] is not None and a[j]<=tick and a[j+1] is None:
                                a[j],a[j+1]=None,tick+8;moved_a+=1
                    # Encoding B: terminal gate before every preceding gate.
                    b=[max(0,z-1) if z>=0 else -1 for z in b]
                    if b[-1]==0 and ib<50:
                        b[-1]=-1;ib+=1;moved_b+=1
                    for j in range(length-2,-1,-1):
                        if b[j]==0 and b[j+1]==-1:
                            b[j]=-1;b[j+1]=8;moved_b+=1
                    norm=[-1 if z is None else max(0,z-tick) for z in a]
                    assert norm==b and ia==ib and moved_a==moved_b
                if a[0] is not None:
                    assert all(z is not None for z in a) and ia==50 and moved_a==0
                cases+=1
    return dict(cases=cases,route_lengths=[1,2,3],no_supply_steps=8,violations=0)


def recipe_species():
    # Transcribed from the snapshot recipe table, then checked set-theoretically.
    recipes={
        '粉碎机': [(['源矿'],['源石粉末']),(['蓝铁块'],['蓝铁粉末']),(['荞花'],['荞花粉末']),(['砂叶'],['砂叶粉末'])],
        '精炼炉': [(['蓝铁矿'],['蓝铁块']),(['致密蓝铁粉末'],['钢块']),(['蓝铁粉末'],['蓝铁块'])],
        '研磨机': [(['蓝铁粉末','砂叶粉末'],['致密蓝铁粉末']),(['源石粉末','砂叶粉末'],['致密源石粉末']),(['荞花粉末','砂叶粉末'],['细磨荞花粉末'])],
        '塑形机': [(['钢块'],['钢质瓶'])],
        '配件机': [(['钢块'],['钢制零件'])],
        '种植机': [(['荞花种子'],['荞花']),(['砂叶种子'],['砂叶'])],
        '采种机': [(['荞花'],['荞花种子']),(['砂叶'],['砂叶种子'])],
        '封装机': [(['钢制零件','致密源石粉末'],['高容谷地电池'])],
        '灌装机': [(['钢质瓶','细磨荞花粉末'],['精选荞愈胶囊'])],
    }
    rows={}
    for name,rs in recipes.items():
        ins={x for a,b in rs for x in a}
        outs={x for a,b in rs for x in b}
        assert not ins&outs
        rows[name]=dict(inputs=sorted(ins),outputs=sorted(outs),intersection=[])
    return rows


if __name__=='__main__':
    result=dict(initial_history_rotation=initial_history_rotation(),
                backpressure=backpressure_exhaustion(),recipe_species=recipe_species(),
                S04_rates=[str(Fraction(12,20)),str(Fraction(11,20))],
                sparse_cycle_rate=str(Fraction(1,Fraction(32,8))))
    (HERE/'coverage_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='recipe_species'},ensure_ascii=False))
