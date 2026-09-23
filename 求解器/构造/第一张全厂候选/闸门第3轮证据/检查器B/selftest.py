#!/usr/bin/env python3
"""局部正反例、旧路由回归、候选B纯速率层LP；不提供绕过全厂闸门的模式。"""
import sys
sys.dont_write_bytecode=True
import copy, hashlib, json, random, time
from types import SimpleNamespace
from collections import defaultdict
from catalog import *
from schema import loads,validate,Invalid
from geometry import Checks,Geometry,structural,check_rectangle,maximum_empty
from check import check_document,safe_write,code_fingerprint
from interfaces import EXTRA
from flow import LP,build,vector_from_witness,witness
import legacy_check
RESULTS=[]
def test(name,fn):
 start=time.monotonic()
 try:
  ev=fn();RESULTS.append({'name':name,'status':'PASS','seconds':round(time.monotonic()-start,5),'evidence':ev})
 except Exception as e:
  import traceback
  RESULTS.append({'name':name,'status':'FAIL','error':repr(e),'traceback':traceback.format_exc()})
  print(name,'FAIL',repr(e),flush=True)
def req(ok,msg='assertion'): assert ok,msg

def restrictions(cls='p2p'):
 return [dict(id=k,source=['shape'],statement=EXTRA.get(k,'落实格式 §8.2 '+k),coverage_loss='不覆盖撤去本限制后的原问题合法布局。',release_obligations='撤去后补相应结构、物料和运行证明。',failure_scope='固定本候选；未覆盖初态、调试及全部合法先后；不排除其他布局。') for k in N_IDS+(P_IDS if cls=='p2p' else [])+['recipe-subsets']]
def base(cls='p2p'):
 return {'schema':'full-factory-static-v1','candidate_id':'test-local','source_fingerprints':dict(HASHES),'targets':dict(TARGETS),'layout':{'W':70,'H':70,'machines':[],'warehouse_outlets':[],'core':{'id':'CORE','x0':50,'y0':50,'x1':58,'y1':58,'Din':0,'output_items':[{'side':s,'offset':o,'item':'源矿' if o==1 else '蓝铁矿'} for s in [1,3] for o in [1,4,7]]},'power_poles':[],'storage_boxes':[],'transport':[],'vin':[],'vout':[]},'empty_rectangle':{'x0':0,'y0':0,'x1':49,'y1':69},'design':{'class':cls,'physical_channels':[],'restrictions':restrictions(cls)},'flow_witness':None}
def machine(uid,x,y,model='精炼炉',r='精炼-蓝铁矿',side=2):
 kind=MODELS[model];w,h={'小':(3,3),'中':(5,5),'大':(6,4) if side%2 else (4,6)}[kind]
 return dict(id=uid,model=model,kind=kind,x0=x,y0=y,x1=x+w-1,y1=y+h-1,Din=side,recipe_ids=[r],settings={'manufacture_on':True})
def belt(uid,x,y,ins=2,outs=0): return dict(id=uid,x=x,y=y,type='belt',in_side=ins,out_side=outs)
def box(uid,x,y,side=2,on=False): return dict(id=uid,x0=x,y0=y,x1=x+2,y1=y+2,Din=side,settings={'transfer_on':on})
def pole(uid,x,y): return dict(id=uid,x0=x,y0=y,x1=x+1,y1=y+1,orientation=0)
def outlet(uid,y=1,it='蓝铁矿'): return dict(id=uid,x0=0,y0=y,x1=0,y1=y+2,Dout=0,item=it)
def local(d,items=None):
 validate(d);c=Checks();g=Geometry(d['layout'],c);req(g.valid)
 d['design']['physical_channels']=[{'id':'PC'+str(i),'from':unref(p),'to':unref(q),'allowed_items':[items or '蓝铁矿']} for i,(p,q) in enumerate(g.edges)]
 structural(d,g,c);return g,c

def basic_line():
 d=base();d['layout']['machines']=[machine('M',2,1)];d['layout']['warehouse_outlets']=[outlet('O')];d['layout']['transport']=[belt('T',1,2)];d['layout']['power_poles']=[pole('P',6,6)];return d

def check_basic():
 d=basic_line();g,c=local(d)
 req(g.edges==[(('O',0,1),('T',2,0)),(('T',0,0),('M',2,1))]);req(c.good('N1','N2','N3a','N3b','N5a','P1','P2-paths','P6','wrong-material','outside-recipe'));req(g.powered['M']==['P'])
 safe_write(BASE/'tests'/'real-outlet-line.json',d)
 r=check_document(d);req(r['status']=='REJECTED');req(len(r['constraints'])==72);safe_write(BASE/'test-results'/'real-outlet-line.report.json',r)
 return {'channels':2,'local_structure':'pass','full_factory':'REJECTED'}

def schema_bad(mut):
 d=basic_line();mut(d)
 try: validate(d)
 except Invalid: return True
 raise AssertionError('invalid schema accepted')

def channel_tamper(extra=False):
 d=basic_line();g,c=local(d)
 if extra:
  d['design']['physical_channels'].append({'id':'PHANTOM','from':{'unit':'M','side':0,'offset':0},'to':{'unit':'CORE','side':0,'offset':1},'allowed_items':['蓝铁矿']})
 else: d['design']['physical_channels'].pop()
 c=Checks();structural(d,g,c);req(not c.good('N5a'))

def bridge_cross():
 d=base();l=d['layout'];l['transport']=[dict(id='B',x=10,y=10,type='bridge',H_in=2,V_in=3)]
 l['machines']=[machine('W',7,8,'精炼炉','精炼-蓝铁矿',2),machine('E',11,10,'粉碎机','粉碎-蓝铁块',2),machine('S',10,7,'精炼炉','精炼-蓝铁矿',3),machine('N',8,11,'粉碎机','粉碎-蓝铁块',3)]
 return d

def bridge_good():
 d=bridge_cross();g,c=local(d,'蓝铁块');req(c.good('N4a','N4b','P2-paths'));req(len(g.edges)==4);req(g.possible[('B',0)]==g.possible[('B',1)]=={'蓝铁块'});req(('B',0) in g.slots and ('B',1) in g.slots)
 safe_write(BASE/'tests'/'same-item-bridge.json',d);return {'same_item_on_two_axes':'PASS','channels':4}

def bridge_bad(kind):
 d=bridge_cross()
 if kind=='same-direction': d['layout']['machines'][1]['Din']=0
 if kind=='single-end': d['layout']['machines']=d['layout']['machines'][:1]
 if kind=='claim': d['layout']['transport'][0]['H_in']=0
 if kind=='adjacent':
  d['layout']['machines']=[];d['layout']['transport'].append(dict(id='B2',x=11,y=10,type='bridge',H_in=None,V_in=None))
 g,c=local(d);req(not c.good('N4a','N4b'));return [r for r in c.records if r['check'].startswith('N4') and r['status']=='FAIL']

def no_nontransport_channel():
 d=base();d['layout']['machines']=[machine('A',2,2),machine('B',5,2)];g,c=local(d);req(g.edges==[])

def dimensions_overlap():
 d=base();d['layout']['machines']=[machine('M',2,2)];d['layout']['power_poles']=[pole('P',3,3)];g=Geometry(d['layout'],Checks());req(not g.valid)
 d=base();u=machine('M',2,2,'研磨机','研磨-致密蓝铁',2);u['x1']=7;u['y1']=5;d['layout']['machines']=[u];g=Geometry(d['layout'],Checks());req(not g.valid)

def power_test():
 p=pole('P',10,10)
 req(Geometry.covers(p,machine('A',16,12)))
 req(not Geometry.covers(p,machine('B',17,12)))
 req(Geometry.covers(p,machine('C',3,12)))
 req(not Geometry.covers(p,machine('D',2,12)))
 req(Geometry.covers(p,box('E',16,12)))
 return {'covered_columns':'5..16','edge_contact_x17':'not covered','one_cell_overlap':'covered'}

def priority(n):
 d=base('n_restricted')
 if n==1:
  d['layout']['machines']=[machine('M',10,10)];d['layout']['transport']=[dict(id='G',x=13,y=10,type='merger',out_side=0),belt('T',13,11)]
 else:
  d['layout']['machines']=[machine('M',10,10)];d['layout']['transport']=[dict(id='S',x=9,y=10,type='splitter',in_side=2),belt('T',9,11)]
 g,c=local(d);req(not c.good('N'+str(n)))

def n2_bridge():
 d=bridge_cross();d['design']['class']='n_restricted';d['design']['restrictions']=restrictions('n_restricted')
 d['layout']['machines']=[u for u in d['layout']['machines'] if u['id']!='W'];d['layout']['transport'].append(dict(id='SPL',x=9,y=10,type='splitter',in_side=2))
 g,c=local(d);req(not c.good('N2'))

def wrong_material():
 d=basic_line();d['layout']['warehouse_outlets'][0]['item']='荞花';g,c=local(d);req(not c.good('wrong-material'));req(not c.good('outside-allowed-items'))

def outside_recipe():
 d=basic_line();d['layout']['warehouse_outlets'][0]['item']='蓝铁粉末';g,c=local(d,'蓝铁粉末');req(c.good('wrong-material'));req(not c.good('outside-recipe'))

def core_items():
 d=base();core=d['layout']['core'];d['layout']['transport']=[belt('A',51,59,3,1),belt('B',54,59,3,1)]
 g,c=local(d);req(g.possible[('A',0)]=={'源矿'});req(g.possible[('B',0)]=={'蓝铁矿'})


def gate_fixture(alternative=False):
 d=base('n_restricted');l=d['layout'];l['machines']=[machine('M',10,10)]
 l['transport']=[dict(id='G',x=13,y=10,type='gate',in_side=2,filter='源矿',k5=5,cum=None)]
 if alternative:l['transport'].append(belt('T',13,11))
 return d

def gate_test(alt,cum=False):
 d=gate_fixture(alt)
 if cum:d['layout']['transport'][0]['cum']=1
 g,c=local(d);req(c.good('N3b')==alt)
 req(c.good('N3a')!=cum);req(any(q[0]=='G' for p,q in g.edges),'filter must not delete structural edge')
 req(g.possible[('G',0)]==set());return {'alternative':alt,'N3b':c.good('N3b'),'structural_gate_input':'retained'}

def gate_bridge_alternative():
 d=bridge_cross();d['design']['class']='n_restricted';d['design']['restrictions']=restrictions('n_restricted');d['layout']['machines']=[u for u in d['layout']['machines'] if u['id']!='E']
 d['layout']['transport'].append(dict(id='G',x=11,y=10,type='gate',in_side=2,filter='源矿',k5=None,cum=None))
 g,c=local(d);req(not c.good('N3b'))

def pure_cycle():
 d=base();d['layout']['transport']=[belt('A',10,10,1,0),belt('B',11,10,2,1),belt('C',11,11,3,2),belt('D',10,11,0,3)]
 g,c=local(d);req(not c.good('transport-terminal-reachability'));req(not c.good('P2-paths'));req(len(g.edges)==4)

def storage_test():
 d=base('n_restricted');d['layout']['storage_boxes']=[box('BOX',10,10)];d['layout']['transport']=[belt('I',9,11),belt('O',13,11)];g,c=local(d)
 req(len(g.edges)==2);req(g.powered['BOX']==[])
 d['design']['class']='p2p';c=Checks();structural(d,g,c);req(not c.good('P1'));return {'recognized':True,'physical_ports_when_unpowered':2,'p2p':'rejected'}

def brute_rect(occ,W,H,s):
 best=(0,0)
 for x0 in range(W):
  for y0 in range(H):
   for x1 in range(x0+s-1,W):
    for y1 in range(y0+s-1,H):
     if not any((x,y) in occ for x in range(x0,x1+1) for y in range(y0,y1+1)):best=max(best,((x1-x0+1)*(y1-y0+1),min(x1-x0+1,y1-y0+1)))
 return best

def rectangle_test():
 rng=random.Random(391)
 for k in range(80):
  occ={(x,y) for x in range(8) for y in range(8) if rng.random()<.27};r=maximum_empty(occ,8,8,2);req((r['area'],r['short_side'])==brute_rect(occ,8,8,2))
 # Equal area 6x12 and 8x9: choose short side 8.
 occ={(x,y) for x in range(70) for y in range(70)}
 for x in range(6):
  for y in range(12):occ.remove((x,y))
 for x in range(20,28):
  for y in range(20,29):occ.remove((x,y))
 r=maximum_empty(occ);req((r['area'],r['short_side'])==(72,8));return {'random_bruteforce_grids':80,'tie':r}

def rectangle_claim():
 d=base();g,c=local(d);best=maximum_empty(g.occ);d['empty_rectangle']=best['rectangles'][0];check_rectangle(d,g,c);req(c.good('empty-rectangle'))
 d['empty_rectangle']={'x0':0,'y0':0,'x1':5,'y1':5};c=Checks();check_rectangle(d,g,c);req(not c.good('empty-rectangle'))
 d['empty_rectangle']={'x0':49,'y0':49,'x1':60,'y1':60};c=Checks();check_rectangle(d,g,c);req(not c.good('empty-rectangle'))

def matrix_test(kind):
 lp=LP();v=lp.var(('x',));de=lp.var(('delta',));lp.row('delta bound',{de:1},'le',1,'test');lp.row('positive',{de:1,v:-1},'le',0,'test')
 if kind=='positive': lp.row('x-fixed',{v:1},'eq',F(1,7),'test')
 if kind=='zero': lp.row('x-fixed',{v:1},'eq',0,'test')
 if kind=='infeasible': lp.row('x-fixed',{v:1},'eq',2,'test');lp.row('x-cap',{v:1},'le',1,'test')
 info,x=lp.solve(20);expected={'positive':'FEASIBLE_EXACT','zero':'ZERO_SUPPORT_EXACT','infeasible':'INFEASIBLE_EXACT'}[kind];req(info['status']==expected,info)
 if x is not None:req(not lp.exact(x,True));x[v]+=F(1,10**10);req(bool(lp.exact(x,True)))
 return info

def algebra_B():
 """Mock physical graph ONLY for LP algebra. No coordinates, ports or static certificate."""
 B=json.loads((ROOT/'求解器/数据/候选B/contract.json').read_text());l={'machines':[],'warehouse_outlets':[],'storage_boxes':[],'transport':[]}
 g=SimpleNamespace(l=l,units={},kind={},powered={},edges=[],ins=defaultdict(list),outs=defaultdict(list),sin=defaultdict(list),sout=defaultdict(list),slots=set(),source_items={})
 for u in B['machines']:
  m={'id':u['id'],'model':u['kind'],'recipe_ids':[r['recipe'] for r in u['recipes']],'settings':{'manufacture_on':True}};l['machines'].append(m);g.units[m['id']]=m;g.kind[m['id']]='machines';g.powered[m['id']]=['TEST_POWER_ASSUMPTION']
 for src in B['sources']:g.source_items[(src['id'],0,0)]=src['item'];g.units[src['id']]={'id':src['id']};g.kind[src['id']]='warehouse_outlets'
 g.units['CORE']={'id':'CORE'};g.kind['CORE']='core'
 g.transport=lambda uid:g.kind[uid]=='belt'
 def slot(p):
  if g.transport(p[0]):return p[0],0
  if p in g.source_items:return p
  return p[0],'in' if p[1]==2 else 'out'
 g.slot=slot;channels=[];expected={};feeds=[];inport=defaultdict(int);outport=defaultdict(int)
 for feed in B['logical_feeds']:
  src,tgt=feed['source'],feed['target'];uid='T'+feed['id'];g.units[uid]={'id':uid,'type':'belt'};g.kind[uid]='belt';l['transport'].append(g.units[uid]);g.slots.add((uid,0))
  p=(src,0,outport[src]);outport[src]+=1;q=(tgt,2,inport[tgt]);inport[tgt]+=1
  if (src,0,0) in g.source_items:p=(src,0,0)
  for aa,bb in [(p,(uid,2,0)),((uid,0,0),q)]:
   i=len(g.edges);g.edges.append((aa,bb));g.outs[aa[0]].append(i);g.ins[bb[0]].append(i);g.sout[slot(aa)].append(i);g.sin[slot(bb)].append(i)
   eid='C'+str(i);channels.append(dict(id=eid,**{'from':unref(aa),'to':unref(bb)},allowed_items=[feed['item']]));expected[eid]=F(feed['planned_rate']['value'])
 d={'layout':l,'design':{'physical_channels':channels},'flow_witness':None};lp=build(d,g);info,x=lp.solve(30);req(info['status']=='FEASIBLE_EXACT',info)
 # The free LP can choose another rational distribution; check original B fixed values separately.
 w=witness(lp,x,d);req(not lp.exact(vector_from_witness(w,lp,d),True))
 for row in w['channel_flows']:row['rates']={channels[int(row['channel_id'][1:])]['allowed_items'][0]:str(expected[row['channel_id']])}
 for row in w['batch_rates']:
  old=next(u for u in B['machines'] if u['id']==row['machine_id']);rr=next(r for r in old['recipes'] if r['recipe']==row['recipe_id']);row['rate']=rr['planned_batch_rate']['value']
 w['delta']=str(min(expected.values()));req(not lp.exact(vector_from_witness(w,lp,d),True),'candidate B fixed rate vector rejected')
 safe_write(BASE/'test-results'/'candidate-b-rate-layer.json',{'scope':'LP algebra on abstract split channels; no geometry, power or real-port certificate','solver':info,'fixed_B_vector_exact':True,'witness':w})
 # Machine power, manufacture switch, wrong material and per-slot total capacity mutations.
 original=x[:];idx=next(iter(lp.batch.values()));x[idx]+=F(1,10**12);req(bool(lp.exact(x,True)));x=original
 u=l['machines'][0];g.powered[u['id']]=[];lp2=build(d,g);req(bool(lp2.exact(vector_from_witness(w,lp2,d),True)));g.powered[u['id']]=['P'];u['settings']['manufacture_on']=False;lp3=build(d,g);req(bool(lp3.exact(vector_from_witness(w,lp3,d),True)))
 return {'machines':219,'logical_feeds':315,'abstract_channels':630,'continuous_LP':info,'fixed_B_exact':True,'scope':'rate algebra only'}

def old_spec(k):
 rs=[('精炼-蓝铁矿',2*k,{'蓝铁矿':1},'蓝铁块'),('粉碎-蓝铁块',2*k,{'蓝铁块':1},'蓝铁粉末'),('研磨-致密蓝铁',k,{'蓝铁粉末':2,'砂叶粉末':1},'致密蓝铁粉末'),('精炼-致密蓝铁',k,{'致密蓝铁粉末':1},'钢块')]
 return {'roles':[{'name':name,'count':count,'in_count':ins,'out':[out],'n_out':1} for name,count,ins,out in rs]}

def meeting(k,expect):
 p=ROOT/f'求解器/会议成果/会议3/seat-opus-3/rt_k{k}.json';old=loads(p.read_bytes());res=legacy_check.check(old['layout'],old_spec(k));req(res['channels']==expect and not res['errors'] and not res['warnings'],res)
 # Honest partial migration: remove external interfaces, add isolated core. It MUST NOT certify.
 d=base();l=d['layout'];ol=old['layout'];l['machines']=[]
 for i,u in enumerate(ol['machines']):
  v=copy.deepcopy(u);v.update(id='M'+str(i),model=RECIPES[u['role']][0],recipe_ids=[u['role']],settings={'manufacture_on':True});l['machines'].append(v)
 l['transport']=[dict(t,id='T'+str(i)) for i,t in enumerate(ol['transport'])]
 cx,cy=(60,56) if k==16 else (2,57);l['core'].update(x0=cx,y0=cy,x1=cx+8,y1=cy+8)
 c=Checks();g=Geometry(l,c);req(g.valid)
 req(len(g.edges)==expect-len(ol['vin'])-len(ol['vout']),{'actual':len(g.edges)})
 req(c.good('N4b'));req(c.good('N4a')==(k==16))
 d['design']['physical_channels']=[{'id':'PC'+str(i),'from':unref(aa),'to':unref(bb),'allowed_items':ITEMS[:]} for i,(aa,bb) in enumerate(g.edges)]
 d['empty_rectangle']=maximum_empty(g.occ)['rectangles'][0]
 d['candidate_id']='partial-migration-k'+str(k)
 r=check_document(d);req(r['status']=='REJECTED');safe_write(BASE/'tests'/f'rt_k{k}.partial-v1.json',d);safe_write(BASE/'test-results'/f'rt_k{k}.report.json',r)
 # Original file itself cannot pass v1 schema.
 try:validate(old)
 except Invalid:pass
 else:raise AssertionError('legacy schema silently accepted')
 evidence={'original_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'legacy':res,'new_geometry_internal_channels':len(g.edges),'removed_virtual_interfaces':len(ol['vin'])+len(ol['vout']),'lossless_full_factory_conversion':False,'reason':'virtual ore/plant powder/output interfaces; absent real outlets/power/full factory; W/H are local','partial_v1_status':r['status']}
 safe_write(BASE/'test-results'/f'rt_k{k}.regression.json',evidence);return evidence

def main():
 test('real-outlet-offset-and-two-channels',check_basic)
 mutations={
 'unknown-field':lambda d:d.update(extra=1),
 'bool-coordinate':lambda d:d['layout']['machines'][0].update(x0=True),
 'float-coordinate':lambda d:d['layout']['transport'][0].update(x=1.0),
 'float-rate':lambda d:d['targets'].update(高容谷地电池=0.6),
 'wrong-fingerprint':lambda d:d['source_fingerprints'].update(rules='0'*64),
 'out-of-bound-transport':lambda d:d['layout']['transport'][0].update(x=70),
 'out-of-bound-core':lambda d:d['layout']['core'].update(x1=70),
 'virtual-interface':lambda d:d['layout']['vin'].append({'x':0}),
 'duplicate-unit-id':lambda d:d['layout']['machines'][0].update(id='CORE'),
 'foreign-recipe':lambda d:d['layout']['machines'][0].update(recipe_ids=['粉碎-源矿']),
 'missing-bridge-fields':lambda d:d['layout']['transport'][0].update(type='bridge'),
 'core-output-side':lambda d:d['layout']['core']['output_items'][0].update(side=0),
 'unknown-model':lambda d:d['layout']['machines'][0].update(model='未知机'),
 'gate-limit-without-filter':lambda d:d['layout']['transport'].__setitem__(0,dict(id='G',x=1,y=2,type='gate',in_side=2,filter=None,k5=1,cum=None)),
 }
 for name,mut in mutations.items():test('schema-'+name,lambda mut=mut:schema_bad(mut))
 def duplicate():
  try:loads('{"schema":1,"schema":2}')
  except Invalid:return True
  raise AssertionError('duplicate JSON accepted')
 test('duplicate-json-key',duplicate)
 test('missing-automatic-channel',lambda:channel_tamper(False));test('phantom-channel',lambda:channel_tamper(True));test('nontransport-touch-no-channel',no_nontransport_channel)
 test('overlap-and-large-machine-orientation',dimensions_overlap);test('power-exact-partial-intersection',power_test)
 test('bridge-two-axes-same-item',bridge_good)
 for k in ['same-direction','single-end','claim','adjacent']:test('bridge-'+k,lambda k=k:bridge_bad(k))
 test('N1-priority',lambda:priority(1));test('N2-priority',lambda:priority(2));test('N2-bridge-physical-aggregation',n2_bridge)
 test('wrong-material-not-hidden-by-allowed',wrong_material);test('outside-recipe-material',outside_recipe);test('core-source-items-per-port',core_items)
 test('N3b-blocked',lambda:gate_test(False));test('N3b-real-alternative',lambda:gate_test(True));test('N3a-cumulative',lambda:gate_test(True,True));test('N3b-other-bridge-axis-no-alternative',gate_bridge_alternative)
 test('pure-transport-cycle',pure_cycle);test('box-recognition-unpowered-ports-p2p-rejection',storage_test)
 test('maximum-rectangle-exhaustive-oracle',rectangle_test);test('rectangle-declaration',rectangle_claim)
 for kind in ['positive','zero','infeasible']:test('exact-LP-'+kind,lambda kind=kind:matrix_test(kind))
 test('candidate-B-rate-LP-and-tampered-witness',algebra_B)
 test('meeting-rt-k16',lambda:meeting(16,999));test('meeting-rt-k17',lambda:meeting(17,1186))
 from component_tests import extra_cases
 for name,fn in extra_cases():test(name,fn)
 report={'status':'PASS' if all(r['status']=='PASS' for r in RESULTS) else 'FAIL','tests':RESULTS,'total':len(RESULTS),'passed':sum(r['status']=='PASS' for r in RESULTS),'checker_files_sha256':code_fingerprint(),'scope':'component/unit/regression tests; no certified complete factory candidate'}
 safe_write(BASE/'test-results'/'selftest.json',report);print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total']},ensure_ascii=False));return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
