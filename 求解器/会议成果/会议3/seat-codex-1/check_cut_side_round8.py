"""Exact two-case check of source-side versus complement lower-bound cuts.
The general identity is derived in the round-8 vote document.
"""
from itertools import chain,combinations
from pathlib import Path
import json


def subsets(vs):
    return chain.from_iterable(combinations(vs,n) for n in range(len(vs)+1))


def check_case(name, nodes, arcs, d):
    assert sum(d.values())==0
    r=dict(d)
    for a,b,l,u in arcs:
        assert 0<=l<=u
        r[a]+=l
        r[b]-=l
    need=sum(max(v,0) for v in r.values())
    records=[]
    for rr in subsets(nodes):
        R=set(rr);X=set(nodes)-R
        cap=sum(-r[v] for v in X if r[v]<0)+sum(r[v] for v in R if r[v]>0)
        cap+=sum(u-l for a,b,l,u in arcs if a in R and b in X)
        hX=sum(d[v] for v in X)+sum(l for a,b,l,u in arcs if a in X and b in R)-sum(u for a,b,l,u in arcs if a in R and b in X)
        hR=-sum(d[v] for v in R)+sum(l for a,b,l,u in arcs if a in X and b in R)-sum(u for a,b,l,u in arcs if a in R and b in X)
        wrong=sum(d[v] for v in R)+sum(l for a,b,l,u in arcs if a in R and b in X)-sum(u for a,b,l,u in arcs if a in X and b in R)
        assert need-cap==hX==hR
        records.append({'R':sorted(R),'X':sorted(X),'aux_cut_capacity':cap,'gap':need-cap,'correct_X_residual':hX,'correct_R_residual':hR,'incoming_form_wrongly_on_R':wrong})
    value=min(x['aux_cut_capacity'] for x in records)
    cuts=[x for x in records if x['aux_cut_capacity']==value]
    assert value<need
    assert all(x['gap']>0 for x in cuts)
    return {'name':name,'d':d,'shifted_r':r,'need':need,'min_cut_capacity':value,'minimum_cuts':cuts,'all_subset_identity_checks':len(records)}

cases=[
 check_case('forced a->b without return',('a','b'),[('a','b',1,1),('b','a',0,0)],{'a':0,'b':0}),
 check_case('nonzero demand sign check',('a','b'),[('a','b',0,0)],{'a':-1,'b':1}),
]
assert cases[0]['minimum_cuts'][0]['R']==['b']
assert cases[0]['minimum_cuts'][0]['X']==['a']
assert cases[0]['minimum_cuts'][0]['incoming_form_wrongly_on_R']==-1
out={'scope':'exact algebra on abstract networks; not a factory/performance test','identity':'need-capacity = d(X)+l(out X)-u(in X) = -d(R)+l(in R)-u(out R)','cases':cases}
Path(__file__).with_name('cut-side-round8-result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
