#!/usr/bin/env python3
"""Finite-activity certificates: bounded inventories and monotone sums."""
from pathlib import Path
import re,json
P=Path(__file__).resolve().parent
RULE=P.parent/'前提快照/《明日方舟：终末地》游戏规则.txt'
recipes=[]
for line in RULE.read_text().splitlines():
 if ' → ' not in line:continue
 left,right=line.split(' → ');right=right.split('，')[0]
 def parts(s):return {m[1]:int(m[0]) for m in re.findall(r'(\d+)\s+(\S+)',s)}
 inp,out=parts(left),parts(right); vec={}
 for x,n in inp.items():vec[x]=vec.get(x,0)-n
 for x,n in out.items():vec[x]=vec.get(x,0)+n
 recipes.append({'name':left+' → '+right,'v':vec})
raw=['蓝铁矿','源矿']; finals=['高容谷地电池','精选荞愈胶囊']
species=sorted(set(x for rec in recipes for x in rec['v']))
potentials=[{x:1} for x in species]+[{p:1,p+'种子':1} for p in ['荞花','砂叶']]+[{'蓝铁块':1,'蓝铁粉末':1}]
results=[]
for label,blocked,forbid_raw in [('battery',['高容谷地电池'],['源矿']),('capsule',['精选荞愈胶囊'],[]),('both',finals,raw)]:
 acts=recipes+[{'name':x+'取货','v':{x:1}} for x in raw]
 acts += [{'name':x+'入库','v':{x:-1}} for x in raw if x not in forbid_raw]
 acts += [{'name':x+'玩家拿取','v':{x:-1}} for x in finals if x not in blocked]
 known=set();certs=[]
 while True:
  old=len(known)
  for pot in potentials:
   coeff=[sum(pot.get(x,0)*n for x,n in a['v'].items()) for a in acts]
   pending=[i for i,n in enumerate(coeff) if i not in known and n]
   if not pending:continue
   for sign in [1,-1]:
    if all(sign*coeff[i]>0 for i in pending):
     certs.append({'weights':{x:sign*n for x,n in pot.items()},'already_finite':[acts[i]['name'] for i,n in enumerate(coeff) if n and i in known],'newly_finite':[acts[i]['name'] for i in pending]})
     known.update(pending);break
  if len(known)==old:break
 finite=[acts[i]['name'] for i in sorted(known)]
 results.append({'scenario':label,'finite':finite,'recipe_count':sum(i<len(recipes) for i in known),'certificates':certs})
assert [x['recipe_count'] for x in results]==[4,6,16]
# Independent manual dependency chain checker: material inventories or plant sum.
manual={
'battery':['高容谷地电池','钢制零件','致密源石粉末','源石粉末','源矿'],
'capsule':['精选荞愈胶囊','钢质瓶','细磨荞花粉末','荞花粉末','荞花+荞花种子','荞花种子'],
'both':['高容谷地电池','精选荞愈胶囊','钢制零件','钢质瓶','致密源石粉末','细磨荞花粉末','源石粉末','源矿','荞花粉末','荞花+荞花种子','荞花种子','钢块','致密蓝铁粉末','砂叶粉末','砂叶+砂叶种子','砂叶种子','蓝铁矿+蓝铁块+蓝铁粉末','蓝铁矿']}
# Input/output pairs independently transcribed; no sign-table or parse reuse.
r2=[({'源矿':1},{'源石粉末':1}),({'蓝铁块':1},{'蓝铁粉末':1}),({'荞花':1},{'荞花粉末':2}),({'砂叶':1},{'砂叶粉末':3}),({'蓝铁矿':1},{'蓝铁块':1}),({'致密蓝铁粉末':1},{'钢块':1}),({'蓝铁粉末':1},{'蓝铁块':1}),({'蓝铁粉末':2,'砂叶粉末':1},{'致密蓝铁粉末':1}),({'源石粉末':2,'砂叶粉末':1},{'致密源石粉末':1}),({'荞花粉末':2,'砂叶粉末':1},{'细磨荞花粉末':1}),({'钢块':2},{'钢质瓶':1}),({'钢块':1},{'钢制零件':1}),({'荞花种子':1},{'荞花':1}),({'砂叶种子':1},{'砂叶':1}),({'荞花':1},{'荞花种子':2}),({'砂叶':1},{'砂叶种子':2}),({'钢制零件':10,'致密源石粉末':15},{'高容谷地电池':1}),({'钢质瓶':10,'细磨荞花粉末':10},{'精选荞愈胶囊':1})]
for result in results:
 label=result['scenario']; rules=r2+[({}, {x:1}) for x in raw]
 forbidden={'battery':['源矿'],'capsule':[],'both':raw}[label]
 stopped={'battery':[finals[0]],'capsule':[finals[1]],'both':finals}[label]
 rules += [({x:1},{}) for x in raw if x not in forbidden]
 rules += [({x:1},{}) for x in finals if x not in stopped]
 done=set()
 for expr in manual[label]:
  subset=expr.split('+')
  delta=[sum(out.get(x,0)-inp.get(x,0) for x in subset) for inp,out in rules]
  active=[i for i,q in enumerate(delta) if q and i not in done]
  assert not active or all(delta[i]>0 for i in active) or all(delta[i]<0 for i in active),(label,expr,active)
  done.update(active)
 assert sum(i<18 for i in done)==result['recipe_count']
 assert sorted(i for i in done if i<18)==[i for i,r in enumerate(recipes) if r['name'] in result['finite']]
result={'recipe_count':len(recipes),'species_count':len(species),'scenarios':results,'independent_manual_check':'PASS'}
(P/'counts_freeze.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({r['scenario']:{'recipe_count':r['recipe_count'],'finite':r['finite']} for r in results},ensure_ascii=False,indent=2))
