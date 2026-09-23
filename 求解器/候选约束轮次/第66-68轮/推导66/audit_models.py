import json,copy,hashlib
from fractions import Fraction as Q
from collections import Counter
from boundary_power import generate,OUT,ROOT,cells,measures
from verify66 import all_bodies,verify_power,verify_dp
from strip_flow import recipes,RATES,COUNTS,KINDS
rr=recipes();items=sorted(set().union(*(set(r['inputs'])|set(r['outputs']) for r in rr)))
assert len(items)==19
rate=list(map(lambda x:Q(str(x)),RATES));net={i:sum(rate[j]*(r['outputs'].get(i,0)-r['inputs'].get(i,0)) for j,r in enumerate(rr)) for i in items}
assert {i:str(v) for i,v in net.items() if v}=={'源矿':'-18','精选荞愈胶囊':'11/20','蓝铁矿':'-34','高容谷地电池':'3/5'}
counts=[]
for b in (9,17):
 bodies,X,Y=generate(b,True);hole=cells(49,b,21,53)
 target=set(X)|set(Y)|cells(49,1,21,b-1)|cells(49,b+53,21,17-b)
 expected=set()
 for k,rect,axis,_,_ in all_bodies(b):
  if k!='P' and not cells(*rect)&target:continue
  x,y,w,h=rect;kind='p' if k=='P' else 'c' if k=='C' else 's' if w==h==3 else 'm' if w==h==5 else 'l'
  expected.add((kind,x,y,w,h,'-' if axis is None else 'h' if axis==0 else 'v'))
 got={(d['kind'],d['x'],d['y'],d['w'],d['h'],d['axis']) for d in bodies}
 assert got==expected
 counts.append(dict(b=b,all_anchors=len(got),strip_machine_anchors=sum(d['kind'] in ('s','m','l') and d['x']+d['w']>49 for d in bodies)))
power=json.loads((OUT/'power_certificates.json').read_text());caps,_,_=verify_power(power)
negative=[]
a=copy.deepcopy(power);a['9'][0]['cap']+=1
try:verify_power(a)
except AssertionError:negative.append('wrong pole cap rejected')
else:raise AssertionError('missed wrong cap')
cases=json.loads((OUT/'edge_integer_certificate.json').read_text())
a=copy.deepcopy(cases)
for line in a[0]['lines']:
 target=next((v for v in line['options'] if v),None)
 if target is not None:target.pop();break
try:verify_dp(a,caps)
except AssertionError:negative.append('omitted body option rejected')
else:raise AssertionError('missed option')
a=copy.deepcopy(cases);a[0]['lines'][0]['frontier'][0][1]+=1
try:verify_dp(a,caps)
except AssertionError:negative.append('wrong DP bound rejected')
else:raise AssertionError('missed DP value')
ports=[]
for g in range(0,70,3):
 starts=list(range(0,g,3))+list(range(g+1,70,3));ps=[x+1 for x in starts]
 assert len(ps)==23 and sum(x>=49 for x in ps)==7
 ports.append(dict(gap=g,ports=ps,suffix_counts={str(a):sum(x>=a for x in ps) for a in (49,56,63)}))
result=dict(status='PASS',recipe_count=len(rr),items=items,global_rates=[str(x) for x in rate],recipes=rr,anchor_audits=counts,negative_controls=negative,bottom_patterns=ports,joint_edge_patterns=47)
(OUT/'model_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('recipes','bottom_patterns','items','global_rates')},ensure_ascii=False))
