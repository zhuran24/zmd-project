"""补充组件测试：不修改检查器的全厂入口与认证条件。"""
import copy
from collections import defaultdict
from selftest import *
from audit import Audit,static_audit,rectangle_audit,flow_audit

def strict_rates():
 from schema import rate
 for v in ['0','1','3/5','11/20','123/1000']: req(rate(v,'test')==F(v))
 for v in ['00','01','0/2','2/2','1/1','1/0','-1','0.6','1e-3','01/2','1/02',True,1,.6,None,[],{}]:
  try:rate(v,'test')
  except Invalid:continue
  raise AssertionError('accepted '+repr(v))

def strict_nested_mutations():
 d=basic_line();paths=[]
 def walk(v,p):
  paths.append(p)
  if type(v)==dict:
   for k,x in v.items():walk(x,p+[k])
  elif type(v)==list:
   for i,x in enumerate(v):walk(x,p+[i])
 walk(d,[]);trials=accepted=0
 for path in paths:
  for replacement in [None,False,0,0.0,'',[],{}]:
   v=copy.deepcopy(d)
   if not path:v=copy.deepcopy(replacement)
   else:
    parent=v
    for k in path[:-1]:parent=parent[k]
    parent[path[-1]]=copy.deepcopy(replacement)
   trials+=1
   try:validate(v)
   except Invalid:continue
   accepted+=1
   # Semantic failures are valid reports rather than tracebacks.
   r=check_document(v);req(r['status'] in ['REJECTED','INVALID_INPUT','UNRESOLVED'])
 return {'mutations':trials,'syntax_valid_semantically_rejected':accepted}

def selected_bad_rows(lp,x,prefix):
 return [r for r in lp.exact(x) if type(r)==dict and r['row'].startswith(prefix)]

def bridge_flow_axis():
 d=bridge_cross();g,c=local(d)
 for e in d['design']['physical_channels']:e['allowed_items']=['蓝铁块','源石粉末']
 lp=build(d,g);x=[F(0)]*len(lp.keys)
 for i,(p,q) in enumerate(g.edges):
  bp=p if p[0]=='B' else q;it='蓝铁块' if bp[1]%2==0 else '源石粉末';x[lp.f[i,it]]=1
 req(not selected_bad_rows(lp,x,'slot:'))
 for i,(p,q) in enumerate(g.edges):
  if p[0]=='B':
   for it in ['蓝铁块','源石粉末']:x[lp.f[i,it]]=1-x[lp.f[i,it]]
 req(bool(selected_bad_rows(lp,x,'slot:')))
 return '汇总总量相等但桥跨轴换物仍被逐轴逐物品守恒拒绝'

def transport_capacity():
 d=base('n_restricted');l=d['layout'];l['transport']=[dict(id='S',x=10,y=10,type='splitter',in_side=2),belt('W',9,10),belt('N',10,11,3,1),belt('E',11,10)]
 g,c=local(d);lp=build(d,g);x=[F(0)]*len(lp.keys)
 for i,(p,q) in enumerate(g.edges):
  x[lp.f[i,'蓝铁矿']]=F(6,5) if q[0]=='S' else F(3,5)
 req(not selected_bad_rows(lp,x,"slot:('S', 0)"));req(bool(selected_bad_rows(lp,x,"slot-cap:('S', 0)")))
 # Merger is the same one-slot capacity with inputs/outputs reversed.
 l['transport']=[dict(id='M',x=10,y=10,type='merger',out_side=0),belt('W',9,10),belt('N',10,11,1,3),belt('E',11,10)]
 g,c=local(d);lp=build(d,g);x=[F(0)]*len(lp.keys)
 for i,(p,q) in enumerate(g.edges):x[lp.f[i,'蓝铁矿']]=F(6,5) if p[0]=='M' else F(3,5)
 req(not selected_bad_rows(lp,x,"slot:('M', 0)"));req(bool(selected_bad_rows(lp,x,"slot-cap:('M', 0)")))

def gate_capacity():
 for cum,k,good in [(None,1,F(1,5)),(1,None,F(0)),(None,None,F(1))]:
  d=base('n_restricted');d['layout']['transport']=[belt('W',9,10),dict(id='G',x=10,y=10,type='gate',in_side=2,filter='蓝铁矿',k5=k,cum=cum),belt('E',11,10)]
  g,c=local(d);lp=build(d,g);x=[F(0)]*len(lp.keys)
  for i in range(len(g.edges)):x[lp.f[i,'蓝铁矿']]=good
  req(not selected_bad_rows(lp,x,'gate-cap:'))
  for i in range(len(g.edges)):x[lp.f[i,'蓝铁矿']]=good+F(1,100)
  req(bool(selected_bad_rows(lp,x,'gate-cap:')))

def wireless_box():
 d=base('n_restricted');l=d['layout'];l['storage_boxes']=[box('BOX',10,10,on=True)];l['transport']=[belt('I',9,11)];l['power_poles']=[pole('P',15,15)]
 g,c=local(d,'高容谷地电池');lp=build(d,g);x=[F(0)]*len(lp.keys);x[lp.f[0,'高容谷地电池']]=F(3,5);x[lp.wireless['BOX','高容谷地电池']]=F(3,5)
 req(not selected_bad_rows(lp,x,'box:'));req(not selected_bad_rows(lp,x,'target:高容谷地电池'))
 # Wireless cannot run without power, cannot run with transfer off, and cannot import nonproducts.
 g.powered['BOX']=[];lp2=build(d,g);req(bool(selected_bad_rows(lp2,x,'box-wireless-off:BOX:高容谷地电池')))
 g.powered['BOX']=['P'];l['storage_boxes'][0]['settings']['transfer_on']=False;lp3=build(d,g);req(bool(selected_bad_rows(lp3,x,'box-wireless-off:BOX:高容谷地电池')))
 x[lp.wireless['BOX','蓝铁矿']]=F(1,10);req(bool(selected_bad_rows(lp,x,'box-wireless-off:BOX:蓝铁矿')))
 return '真实箱体平均无线弧、供电开关与非成品零入库逐行核验；槽位/相位未模拟'

def recipe_p6():
 d=base();u=machine('M',10,10,'粉碎机','粉碎-源矿');u['recipe_ids'].append('粉碎-蓝铁块');d['layout']['machines']=[u];g,c=local(d);req(not c.good('P6'))
 d['design']['class']='n_restricted';g,c=local(d);req(all(r['status']=='NOT_APPLICABLE' for r in c.records if r['check']=='P6'))

def full_catalog_execution():
 # Feed an exact B algebra witness through the audit API on an intentionally
 # impossible overlapping geometry fixture. This exercises ledger calculations
 # only; it must contain violations and cannot be a public STATIC_PASS result.
 B=json.loads((ROOT/'求解器/数据/候选B/contract.json').read_text())
 l={'machines':[],'warehouse_outlets':[],'storage_boxes':[],'transport':[],'power_poles':[pole('P'+str(i),5+i*2,65) for i in range(10)],'core':base()['layout']['core']}
 g=SimpleNamespace(l=l,units={},kind={},powered={},edges=[],ins=defaultdict(list),outs=defaultdict(list),sin=defaultdict(list),sout=defaultdict(list),slots=set(),source_items={},ports={},occ={},rectangle={'area':72,'short_side':8},ore_fronts=set())
 for u in B['machines']:
  r=u['recipes'][0]['recipe'];m=machine(u['id'],20,20,u['kind'],r);l['machines'].append(m);g.units[m['id']]=m;g.kind[m['id']]='machines';g.powered[m['id']]=['TEST_POWER_ASSUMPTION']
 for src in B['sources']:
  g.source_items[(src['id'],0,0)]=src['item'];u=outlet(src['id']);l['warehouse_outlets'].append(u);g.units[src['id']]=u;g.kind[src['id']]='warehouse_outlets'
 g.units['CORE']=l['core'];g.kind['CORE']='core'
 for u in l['power_poles']:g.units[u['id']]=u;g.kind[u['id']]='power_poles'
 g.transport=lambda uid:g.kind[uid]=='belt';g.covers=Geometry.covers
 def slot(p):
  if g.transport(p[0]):return p[0],0
  if p in g.source_items:return p
  return p[0],'in' if p[1]==2 else 'out'
 g.slot=slot;channels=[];vals={};ic=defaultdict(int);oc=defaultdict(int)
 for feed in B['logical_feeds']:
  src,tgt=feed['source'],feed['target'];uid='T'+feed['id'];u=belt(uid,10,10);g.units[uid]=u;g.kind[uid]='belt';l['transport'].append(u);g.slots.add((uid,0));p=(src,0,oc[src]);oc[src]+=1;q=(tgt,2,ic[tgt]);ic[tgt]+=1
  if (src,0,0) in g.source_items:p=(src,0,0)
  for aa,bb in [(p,(uid,2,0)),((uid,0,0),q)]:
   i=len(g.edges);g.edges.append((aa,bb));g.outs[aa[0]].append(i);g.ins[bb[0]].append(i);g.sout[slot(aa)].append(i);g.sin[slot(bb)].append(i);g.ports[aa]=((10,10),'out');g.ports[bb]=((11,10),'in')
   eid='C'+str(i);channels.append({'id':eid,'from':unref(aa),'to':unref(bb),'allowed_items':[feed['item']]});vals[eid]=F(feed['planned_rate']['value'])
 d=base();d['layout']=l;d['design']['physical_channels']=channels;lp=build(d,g);x=[F(0)]*len(lp.keys)
 for (i,it),j in lp.f.items():x[j]=vals['C'+str(i)]
 for (uid,r),j in lp.batch.items():x[j]=F(next(rr['planned_batch_rate']['value'] for u in B['machines'] if u['id']==uid for rr in u['recipes'] if rr['recipe']==r))
 x[lp.index['delta',]]=min(vals.values());req(not lp.exact(x,True))
 c=Checks();a=static_audit(d,g,c);rectangle_audit(d,g,a);flow_audit(d,g,lp,x,a);table=a.finish()
 req(len(table)==72);req(not any(p['status']=='BLOCKED' for row in table for p in row['checks']));req(any(p['status']=='VIOLATION' for row in table for p in row['checks']))
 safe_write(BASE/'test-results'/'all-72-ledger-execution.json',{'scope':'intentionally invalid overlapping abstract fixture; execution coverage only, NOT a layout certificate','constraints':table})
 return {'rows':72,'blocked':0,'invalid_fixture_rejected':True}

def source_version_profiles():
 old=next(k for k in CONSTRAINT_PROFILES if k!=HASHES['constraints']);d=basic_line();d['source_fingerprints']['constraints']=old
 validate(d,verify_sources=False)
 r=check_document(d,verify_sources=False);req(len(r['constraints'])==71)
 try:validate(d)
 except Invalid:pass
 else:raise AssertionError('old candidate accepted against new live source')
 d['source_fingerprints']['constraints']=HASHES['constraints'];validate(d);r=check_document(d);req(len(r['constraints'])==72)
 return {'historical_profile':71,'current_profile':72,'old_candidate_against_current_files':'rejected'}

def position_1113():
 cases=[(21,53,49,y,True) for y in [6,7,9,17]]+[(53,21,x,49,True) for x in [6,7,9,17]]+[(21,53,49,8,False),(21,53,48,6,False),(53,21,8,49,False)]
 for w,h,x,y,expected in cases:
  d=base();d['empty_rectangle']=dict(x0=x,y0=y,x1=x+w-1,y1=y+h-1);g,c=local(d);a=static_audit(d,g,c);g.rectangle={'area':1113,'short_side':21};rectangle_audit(d,g,a)
  req((a.results['1113 位置'][0]['status']=='PASS_STATIC_PROJECTION')==expected)
 return {'allowed_positions':8,'disallowed_positions':3,'scope':'condition unit test, not an empty-layout certificate'}

def extra_cases():
 return [('rate-canonical-encoding',strict_rates),('strict-nested-mutation-matrix',strict_nested_mutations),('LP-bridge-axis-material-conservation',bridge_flow_axis),('LP-splitter-merger-shared-capacity',transport_capacity),('LP-gate-k5-and-cumulative',gate_capacity),('LP-box-wireless-power-switch-and-nonproduct',wireless_box),('P6-explicit-recipe-restriction',recipe_p6),('all-72-ledger-execution',full_catalog_execution),('source-version-profiles',source_version_profiles),('new-1113-position-condition',position_1113)]
