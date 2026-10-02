#!/usr/bin/env python3
"""Two independent integer/fraction encodings of the fixed S2 accounting."""
import json,math,hashlib
from collections import Counter,defaultdict
from fractions import Fraction as Q
from static_check import BASE,read,expected_edges

c=read(BASE/'逻辑接法.json');sp={u['id']:u for u in c['machines']};size={'小':9,'中':25,'大':24}
counts=Counter(u['model'] for u in sp.values());area=sum(size[u['kind']] for u in sp.values());ins=defaultdict(lambda:defaultdict(Q));outs=defaultdict(lambda:defaultdict(Q))
for e in c['logical_feeds']:ins[e['target']][e['item']]+=Q(e['rate']);outs[e['source']][e['item']]+=Q(e['rate'])
bad=[]
for uid,u in sp.items():
    r=Q(u['batch_rate'])
    if dict(ins[uid])!={k:r*v for k,v in u['inputs'].items()} or dict(outs[uid])!={k:r*v for k,v in u['outputs'].items()}:bad.append(uid)
A=dict(counts=dict(counts),machines=len(sp),routes=len(c['logical_feeds']),body_area=area,nontransport_area_without_poles=area+81+3*len(c['warehouse_outlets']),interface_count=2*len(c['logical_feeds']),kinds=dict(Counter(u['kind'] for u in sp.values())),balance_bad=bad,finished_inflow={k:str(v) for k,v in ins['CORE'].items()})
# Independent hand-transcription: nine machine counts and their dimensions.
table=[('粉碎机',34+18+13+6,3,3),('精炼炉',34+17,3,3),('研磨机',17+9+6,6,4),('塑形机',6,3,3),('配件机',6,3,3),('种植机',2*(13+6),5,5),('采种机',13+6,5,5),('封装机',3,6,4),('灌装机',4,6,4)]
ee=expected_edges();B=dict(counts={n:k for n,k,w,h in table},machines=sum(k for n,k,w,h in table),body_area=sum(k*w*h for n,k,w,h in table),routes=sum(ee.values()),interface_count=2*sum(ee.values()))
match=all(A[k]==v for k,v in B.items()) and ee==Counter((e['source'],e['target'],e['item']) for e in c['logical_feeds']) and not bad
# The following bounds use the stated formal direction-count argument with the
# actual 650 nontransport/transport interfaces. They are not a layout certificate.
omega=Q(379-8*32,2)+(22-2*6)+24+6
weighted=2*A['kinds']['小']+3*(A['kinds']['中']+A['kinds']['大']);budget=4900-A['nontransport_area_without_poles']
rows=[]
for p in range(1,budget//4+1):
    for j in range(p+1):
        if 23*p-10*j<len(sp) or 54*p-25*j<weighted:continue
        t=math.ceil((A['interface_count']+90+8+omega)/4)
        tf=max(t,math.ceil((A['interface_count']+90+8+omega+88+4-2*j)/4))
        aa=budget-4*p-tf
        rows.append((aa,p,j,t,tf))
best=max(rows);mul=max((w*h,min(w,h),w,h) for w in range(6,69) for h in range(6,69) if w*h<=best[0])
# Independent scaled-integer encoding: no fractions, no use of omega or first loop.
integer_best=(-1,None)
for w in range(6,69):
    for h in range(6,69):
        area2=w*h
        for p in range(1,279):
            maxj=min(p,(23*p-230)//10,(54*p-556)//25)
            if maxj<0:continue
            k=1114-4*p-area2
            if 8*k+4*maxj>=1883 and 8*k>=1699:
                if (area2,min(w,h))>integer_best[:2] if integer_best[1] is not None else area2>=0:integer_best=(area2,min(w,h),w,h,p,maxj)
                break
result={'all_agree':match and integer_best[:2]==mul[:2],'encoding_A':A,'encoding_B':B,'fixed_S2_budget':dict(omega=str(omega),weighted_machine_count=weighted,free_before_power_transport=budget,best_area_integer=best[0],at_poles=best[1],boundary_poles=best[2],transport_minimum=best[3],transport_plus_other_empty_minimum=best[4],largest_allowed_product=list(mul),independent_integer_result=list(integer_best)),'not_a_layout':True,'global_U_unchanged':1110,'global_L_unchanged':0}
(BASE/'证据/双重算术核验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
