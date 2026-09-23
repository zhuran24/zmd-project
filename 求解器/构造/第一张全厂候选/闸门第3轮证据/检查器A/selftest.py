#!/usr/bin/env python3
"""检查器A自测。局部正例只断言指定部件，不伪装全厂正例。所有产物留在本目录。"""
import sys
sys.dont_write_bytecode=True
import json,copy,re,hashlib,time,random,importlib.util,traceback
from pathlib import Path
from fractions import Fraction as Q
from collections import Counter
from catalog import *
from schema import validate,read_bytes,Invalid
from geometry import Geometry,rectangle,covers,pref
from check_full import Report,make_output
from flow import Flow,Linear
BASE=Path(__file__).resolve().parent
RESULTS=[]
def test(name,fn):
 start=time.monotonic()
 try:detail=fn();RESULTS.append({'name':name,'status':'pass','seconds':round(time.monotonic()-start,4),'detail':detail})
 except Exception as e:RESULTS.append({'name':name,'status':'FAIL','error':repr(e),'traceback':traceback.format_exc()})
def assertion(ok,msg='assertion failed'):
 if not ok:raise AssertionError(msg)
def empty():
 return {'schema':'full-factory-static-v1','candidate_id':'unit-fixture','source_fingerprints':dict(HASHES),'targets':dict(TARGETS),'layout':{'W':70,'H':70,'machines':[],'warehouse_outlets':[],'core':{'id':'CORE','x0':50,'y0':50,'x1':58,'y1':58,'Din':0,'output_items':[{'side':s,'offset':o,'item':'源矿'}for s in(1,3)for o in(1,4,7)]},'power_poles':[],'storage_boxes':[],'transport':[],'vin':[],'vout':[]},'empty_rectangle':{'x0':0,'y0':0,'x1':49,'y1':69},'design':{'class':'n_restricted','physical_channels':[],'restrictions':[]},'flow_witness':None}
def machine(uid,x,y,rid='精炼-蓝铁矿',din=2):
 model=RECIPES[rid][0];kind=MODELS[model];w,h={'小':(3,3),'中':(5,5),'大':(4,6)if din%2==0 else(6,4)}[kind]
 return {'id':uid,'x0':x,'y0':y,'x1':x+w-1,'y1':y+h-1,'model':model,'kind':kind,'Din':din,'recipe_ids':[rid],'settings':{'manufacture_on':True}}
def belt(uid,x,y,ins=2,out=0):return {'id':uid,'x':x,'y':y,'type':'belt','in_side':ins,'out_side':out}
def box(uid,x,y,din=2,on=True):return {'id':uid,'x0':x,'y0':y,'x1':x+2,'y1':y+2,'Din':din,'settings':{'transfer_on':on}}
def pole(uid,x,y):return {'id':uid,'x0':x,'y0':y,'x1':x+1,'y1':y+1,'orientation':0}
def geo(d):r=Report();return Geometry(d,r).build(),r
def status(r,key):return r.checks.get(key,{}).get('status','checked')
def normalize(d):
 g,r=geo(d);d['design']['physical_channels']=[{'id':'PC%05d'%i,'from':dict(zip(['unit','side','offset'],p)),'to':dict(zip(['unit','side','offset'],q)),'allowed_items':sorted(g.emit[g.slot(p)])or['源矿']}for i,(p,q)in enumerate(g.channels)];d['empty_rectangle']=g.maximum['bounds'];return d

def format_example():
 fmt=(BASE.parent/'格式.md').read_text();d=json.loads(re.findall(r'```json\n(.*?)\n```',fmt,re.S)[-1]);d['source_fingerprints']=dict(HASHES);raw=json.dumps(d,ensure_ascii=False,indent=2).encode();(BASE/'format_example.json').write_bytes(raw);rep=make_output(raw,10);(BASE/'format_example.report.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n')
 assertion(rep['status']=='rejected');assertion(rep['recomputed']['structural_channels']==2);assertion(rep['recomputed']['maximum_empty_rectangle']['area']==2870);assertion(rep['flow']['status']=='violation');assertion(Q(rep['flow']['certificate']['bound'])>0);assertion(len(rep['formal_constraints'])==72);return {'channels':2,'area':2870,'Farkas_bound':rep['flow']['certificate']['bound'],'full_factory':'rejected as expected'}
def reject_schema(mut):
 d=empty();mut(d)
 try:validate(d)
 except (Invalid,TypeError,KeyError,ValueError):return
 raise AssertionError('应拒绝但未拒绝')
def source_line():
 d=empty();d['layout']['warehouse_outlets']=[{'id':'O','x0':0,'y0':1,'x1':0,'y1':3,'Dout':0,'item':'蓝铁矿'}];d['layout']['machines']=[machine('M',2,1)];d['layout']['transport']=[belt('T',1,2)];d['layout']['power_poles']=[pole('P',6,6)];return normalize(d)
def manual_channel_expected():
 d=source_line();g,r=geo(d);assertion(set(g.channels)=={(('O',0,1),('T',2,0)),(('T',0,0),('M',2,1))});assertion(status(r,'N5a')=='checked');assertion(g.power['M']==['P']);return {'exact_endpoint_pairs':2}
def channel_mutation(mode):
 d=source_line()
 if mode=='omit':d['design']['physical_channels'].pop()
 elif mode=='extra':d['design']['physical_channels'].append({'id':'FAKE','from':{'unit':'O','side':0,'offset':1},'to':{'unit':'M','side':2,'offset':1},'allowed_items':['蓝铁矿']})
 elif mode=='offset':d['design']['physical_channels'][0]['from']['offset']=0
 g,r=geo(d);assertion(status(r,'N5a')=='violation')
def nontransport_adjacent():
 d=empty();d['layout']['machines']=[machine('A',2,2),machine('B',5,2,'粉碎-蓝铁块')];g,r=geo(d);assertion(not g.channels)
def dimensions():
 for rid in ['精炼-蓝铁矿','种植-荞花','研磨-致密蓝铁']:
  for din in range(4):
   d=empty();d['layout']['machines']=[machine('M',5,5,rid,din)];g,r=geo(d);assertion(status(r,'machine_shape')=='checked');u=g.units['M'];count=6 if u['kind']=='大'else 5 if u['kind']=='中'else 3;assertion(sum(p[0]=='M'for p in g.ports)==2*count)
 return {'orientations':12}
def core_ports():
 for din in range(4):
  d=empty();c=d['layout']['core'];c['Din']=din;c['output_items']=[{'side':s,'offset':o,'item':'源矿'if o==1 else'蓝铁矿'}for s in [(din+1)%4,(din+3)%4]for o in [1,4,7]];g,r=geo(d);assertion(len(g.ports)==20);assertion(len(g.sources)==6)
  for p,it in g.sources.items():assertion(g.emit[g.slot(p)]=={it})
 return {'orientations':4,'input_ports':14,'output_ports':6}
def power_edges():
 p=pole('P',6,6);assertion(covers(p,dict(x0=12,x1=14,y0=12,y1=14)));assertion(not covers(p,dict(x0=13,x1=15,y0=12,y1=14)));assertion(covers(p,dict(x0=0,x1=1,y0=0,y1=1)));assertion(not covers(p,dict(x0=0,x1=0,y0=0,y1=0)))
def bridge_fixture(h=2,v=3):
 d=empty();ts=[{'id':'B','x':10,'y':10,'type':'bridge','H_in':h,'V_in':v}]
 for side,name in [(0,'E'),(1,'N'),(2,'W'),(3,'S')]:
  x,y=nb((10,10),side);incoming=side in(h,v);ts.append(belt(name,x,y,side if incoming else opp(side),opp(side)if incoming else side))
 d['layout']['transport']=ts;return d
def bridges():
 for h in[0,2]:
  for v in[1,3]:
   g,r=geo(bridge_fixture(h,v));assertion(status(r,'N4a')=='checked');assertion(len(g.channels)==4);assertion(g.slot(('B',0,0))!=g.slot(('B',1,0)))
 return {'orientations':4,'channels_each':4}
def bridge_bad(which):
 d=bridge_fixture()
 if which=='one_end':d['layout']['transport']=[t for t in d['layout']['transport']if t['id']!='E']
 if which=='same_type':
  t=next(t for t in d['layout']['transport']if t['id']=='E');t['in_side'],t['out_side']=t['out_side'],t['in_side']
 if which=='claim':d['layout']['transport'][0]['H_in']=0
 if which=='idle_neighbor':d['layout']['transport']=[{'id':'A','x':10,'y':10,'type':'bridge','H_in':None,'V_in':None},{'id':'B','x':11,'y':10,'type':'bridge','H_in':None,'V_in':None}]
 g,r=geo(d);assertion(status(r,'N4b'if which=='idle_neighbor'else'N4a')=='violation')
def bridge_idle():
 d=empty();d['layout']['transport']=[{'id':'B','x':5,'y':5,'type':'bridge','H_in':None,'V_in':None}];g,r=geo(d);assertion(status(r,'N4a')=='checked');assertion(g.occ[5,5]=='B')
def n1_core():
 d=empty();d['layout']['transport']=[{'id':'MER','x':51,'y':59,'type':'merger','out_side':0},belt('T',54,59,3,1)];g,r=geo(d);assertion(status(r,'N1')=='violation')
def n2_bridge():
 d=bridge_fixture();t=next(t for t in d['layout']['transport']if t['id']=='W');t.clear();t.update({'id':'W','x':9,'y':10,'type':'splitter','in_side':2});g,r=geo(d);assertion(status(r,'N2')=='violation')
def gate_fixture(alternative=False):
 d=empty();d['layout']['machines']=[machine('M',3,3,'粉碎-源矿')];d['layout']['transport']=[{'id':'G','x':6,'y':3,'type':'gate','in_side':2,'filter':'蓝铁矿','k5':None,'cum':None}]
 if alternative:d['layout']['transport'].append(belt('T',6,4,2,0))
 return d
def n3b_cases(alt):g,r=geo(gate_fixture(alt));assertion(status(r,'N3b')==('checked'if alt else'violation'))
def n3a():
 d=gate_fixture(True);d['layout']['transport'][0]['cum']=10;g,r=geo(d);assertion(status(r,'N3a')=='violation')
def wrong_item():
 d=source_line();d['layout']['warehouse_outlets'][0]['item']='荞花';g,r=geo(d);assertion(status(r,'wrong_material')=='violation')
def off_recipe():
 d=source_line();d['layout']['warehouse_outlets'][0]['item']='致密蓝铁粉末';g,r=geo(d);assertion(status(r,'wrong_material')=='checked');assertion(status(r,'off_recipe')=='violation')
def declared_filter_not_real():
 d=source_line();d['design']['physical_channels'][0]['allowed_items']=['源矿'];g,r=geo(d);assertion(status(r,'channel_possible_items')=='violation');assertion(g.arrive['M',]=={'蓝铁矿'})
def p2_fixture():
 d=empty();d['design']['class']='p2p';d['layout']['machines']=[machine('A',2,2),machine('Z',6,2,'粉碎-蓝铁块')];d['layout']['transport']=[belt('T',5,3)];return normalize(d)
def p2_good():g,r=geo(p2_fixture());assertion(status(r,'P2_structure')=='checked' and status(r,'P2')=='blocked');assertion(len(g.path_decomposition)==1)
def p2_bad():
 d=p2_fixture();d['design']['physical_channels'][1]['allowed_items']=['源矿'];g,r=geo(d);assertion(status(r,'P2_structure')=='violation')
def p1_box():
 d=p2_fixture();d['layout']['storage_boxes']=[box('BOX',20,20)];g,r=geo(d);assertion(status(r,'P1')=='violation');assertion(sum(v=='BOX'for v in g.occ.values())==9)
def p6():
 d=p2_fixture();d['layout']['machines'][1]['recipe_ids'].append('粉碎-源矿');g,r=geo(d);assertion(status(r,'P6')=='violation')
def transport_loop():
 d=empty();d['layout']['transport']=[belt('A',10,10,1,0),belt('B',11,10,2,1),belt('C',11,11,3,2),belt('D',10,11,0,3)];d=normalize(d);g,r=geo(d);assertion(status(r,'transport_endpoints')=='violation')
def strict_duplicate():
 for raw in [b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}']:
  try:read_bytes(raw)
  except Invalid:continue
  raise AssertionError('非法JSON未拒绝')
def rectangle_oracle():
 rng=random.Random(827)
 for W,H,minside in[(7,8,2),(10,10,6),(13,12,6)]:
  for case in range(50):
   occ={(x,y)for x in range(W)for y in range(H)if rng.random()<0.08};got=rectangle(occ,W,H,minside);best=(0,0)
   for x0 in range(W):
    for x1 in range(x0+minside-1,W):
     for y0 in range(H):
      for y1 in range(y0+minside-1,H):
       if all((x,y)not in occ for x in range(x0,x1+1)for y in range(y0,y1+1)):best=max(best,((x1-x0+1)*(y1-y0+1),min(x1-x0+1,y1-y0+1)))
   assertion((got['area'],got['short_side'])==best)
 assertion(rectangle(set(),70,70)['area']==4900);assertion(rectangle({(x,y)for x in range(70)for y in range(70)})['bounds']is None)
 return {'random_cases':150,'oracle':'穷举全部x0,x1,y0,y1，与行区间算法独立'}
def rectangle_tie():
 free={(x,y)for x in range(6)for y in range(12)}|{(x,y)for x in range(10,18)for y in range(9)};occ={(x,y)for x in range(20)for y in range(14)}-free;v=rectangle(occ,20,14);assertion((v['area'],v['short_side'])==(72,8));return v

def linear_positive():
 m=Linear();a=m.var(('a',));b=m.var(('b',));m.eq([(a,3)],1,'3a=1');m.eq([(b,1),(a,-2)],0,'b=2a');m.le([(a,1),(b,1)],1,'共享容量');x,cert,meta=m.solve([0,0],10);assertion(x==[Q(1,3),Q(2,3)]and not m.exact(x));return {'exact_values':list(map(str,x))}
def linear_negative():
 m=Linear();a=m.var(('a',));b=m.var(('b',));m.eq([(a,1)],Q(3,5),'a=.6');m.eq([(b,1)],Q(3,5),'b=.6');m.le([(a,1),(b,1)],1,'共享容量');x,cert,meta=m.solve([0,0],10,True);assertion(x is None and cert is not None and Q(cert['bound'])>0);return cert

def zero_delta():
 m=Linear();f=m.var(('flow',));d=m.var(('delta',));m.eq([(f,1)],0,'零流固定');m.le([(d,1),(f,-1)],0,'共同δ');x,cert,meta=m.solve([0,-1],10);assertion(x==[0,0]and cert and Q(cert['bound'])==0);return cert

def local_flow_fixture(box_on=True,powered=True):
 # Unit test of row assembly only: remove disconnected CORE source equations and global targets;
 # local source is one true outlet, output retained by an unpowered/disabled physical box.
 # This subproblem cannot produce a full-factory status, and never enters make_output.
 d=source_line();d['layout']['storage_boxes']=[box('BOX',6,1,on=box_on)];d['layout']['transport'].append(belt('U',5,2));
 if not powered:d['layout']['power_poles']=[]
 d=normalize(d);g,r=geo(d);f=Flow(g).build();f.add_delta()
 # Keep port source eq only if it has terms; disconnected source positive RHS deliberately excluded in this unit test.
 f.m.rows=[row for row in f.m.rows if row[2]!='目标成品入库'and not(row[2]=='52个真实矿口逐口满速'and not row[0])]
 # Unit fixture permits blue iron to leave BOX via a synthetic accounting sink; production model forbids it.
 f.m.rows=[row for row in f.m.rows if row[2]!='非成品零入库/无线开关及供电']
 return f

def local_flow_positive():
 f=local_flow_fixture();c=[0]*len(f.m.keys);c[f.delta]=-1;x,cert,meta=f.m.solve(c,10);assertion(x is not None and x[f.delta]==1 and not f.m.exact(x));w=f.witness(x);assertion(f.from_witness(w)==x)
 bad=copy.deepcopy(w);bad['channel_flows'][0]['rates']={next(iter(bad['channel_flows'][0]['rates'])):'1/2'};assertion(bool(f.m.exact(f.from_witness(bad))));return {'scope':'局部 LP 组装测试，去掉全厂目标及断开核心来源，并显式开放测试汇；绝非全厂通过','delta':str(x[f.delta])}
def local_flow_unpowered():
 f=local_flow_fixture(powered=False);x,cert,meta=f.m.solve([0]*len(f.m.keys),10,True);assertion(x is None and cert and Q(cert['bound'])>0)
def witness_duplicates():
 f=local_flow_fixture();c=[0]*len(f.m.keys);c[f.delta]=-1;x,_,_=f.m.solve(c,10);w=f.witness(x);w['batch_rates'].append(copy.deepcopy(w['batch_rates'][0]))
 try:f.from_witness(w)
 except ValueError:return
 raise AssertionError('重复配方见证未拒绝')
def box_rows():
 d=source_line();d['layout']['storage_boxes']=[box('BOX',6,1,on=False)];d=normalize(d);g,r=geo(d);f=Flow(g).build();tags=Counter(t for a,b,t in f.m.rows);assertion(tags['箱体逐物品入=物理出+无线']==38);assertion(tags['非成品零入库/无线开关及供电']==38)
 for row in f.m.rows:
  a,b,t=row
  if t=='非成品零入库/无线开关及供电':assertion(b==0)
 return {'box_balance_rows':38,'wireless_zero_rows':38}
def legacy():
 spec=importlib.util.spec_from_file_location('meeting_checker',BASE/'meeting_check_full.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);out=[]
 for name,expected in [('rt_k16.json',999),('rt_k17.json',1186)]:
  p=ROOT/'求解器/会议成果/会议3/seat-opus-3'/name;raw=p.read_bytes();d=json.loads(raw);got=mod.check(d['layout']);assertion(got['structural_channels']==expected and not got['errors']and not got['warnings']);new=make_output(raw,10);assertion(new['status']=='rejected');out.append({'input':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'legacy_result':got,'new_format_result':new['status'],'conversion':'不可无损转成完整v1：虚拟矿/砂叶粉来源、钢块虚拟去处，缺核心、46口、供电、植物/成品链；不伪造接口'})
 (BASE/'legacy_regression.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');return [{'file':Path(v['input']).name,'channels':v['legacy_result']['structural_channels'],'new_format':v['new_format_result']}for v in out]

def overlap_and_shape():
 d=source_line();d['layout']['power_poles']=[pole('P',2,1)];g,r=geo(d);assertion(status(r,'overlap')=='violation')
 d=empty();d['layout']['machines']=[dict(machine('M',10,10,'研磨-致密蓝铁',2),x1=15,y1=13)];g,r=geo(d);assertion(status(r,'machine_shape')=='violation')
 d=empty();d['layout']['storage_boxes']=[dict(box('BOX',10,10),x1=13)];g,r=geo(d);assertion(status(r,'unit_shape')=='violation')

def certificate_replay():
 from verify_certificate import verify
 raw=(BASE/'format_example.json').read_bytes();rep=json.loads((BASE/'format_example.report.json').read_text());got=verify(raw,rep);assertion(got['verified'])
 bad=copy.deepcopy(rep);bad['flow']['certificate']['bound']='999'
 try:verify(raw,bad)
 except ValueError:pass
 else:raise AssertionError('篡改对偶界未拒绝')
 (BASE/'certificate_replay.json').write_text(json.dumps(got,ensure_ascii=False,indent=2)+'\n');return got

def source_fingerprint_bad():
 d=empty();d['source_fingerprints']['rules']='0'*64;v=make_output(json.dumps(d).encode(),10);assertion(not v['static_pass']and v['status']=='rejected')

def projection_forged_zero():
 from projections import geometry_checks,flow_checks
 d=source_line();g,r=geo(d);geometry_checks(g,r);f=Flow(g).build();f.add_delta();flow_checks(g,f,[Q()for _ in f.m.keys],r)
 for n in[18,21,43,44,49,50,51,69,71]:assertion(status(r,'C%02d'%n)=='violation','zero flow escaped '+str(n))
 return {'scope':'直接给投影层伪造零流，核对其真实支撑条件；不经认证入口','rejected_constraints':[18,21,43,44,49,50,51,69,71]}

def candidate_b_rate_layer():
 from types import SimpleNamespace
 from collections import defaultdict
 old=json.loads((ROOT/'求解器/数据/候选B/contract.json').read_text())
 g=SimpleNamespace();g.d={'design':{},'flow_witness':None};g.units={};g.types={};g.lay={'machines':[],'storage_boxes':[]};g.power={};g.channels=[];g.cd=[];g.inc=defaultdict(list);g.out=defaultdict(list);g.si=defaultdict(list);g.so=defaultdict(list);g.sources={};expected={}
 for m in old['machines']:
  u={'id':m['id'],'model':m['kind'],'recipe_ids':[v['recipe']for v in m['recipes']],'settings':{'manufacture_on':True}};g.units[u['id']]=u;g.types[u['id']]='machine';g.lay['machines'].append(u);g.power[u['id']]=['TEST_POWER']
 g.units['CORE']={'id':'CORE'};g.types['CORE']='core'
 sources={}
 for i,src in enumerate(old['sources']):
  if i<46:
   uid='OUT%02d'%i;g.units[uid]={'id':uid};g.types[uid]='outlet';p=(uid,0,1)
  else:p=('CORE',1 if i<49 else 3,[1,4,7][(i-46)%3])
  sources[src['id']]=p;g.sources[p]=src['item']
 g.is_t=lambda u:g.types[u]=='belt'
 g.slot=lambda p:p if p in g.sources and p[0]=='CORE'else(p[0],)
 def channel(p,q,it,rate):
  i=len(g.channels);g.channels.append((p,q));g.cd.append({'id':'PC%04d'%i,'allowed_items':[it]});g.inc[q[0]].append(i);g.out[p[0]].append(i);g.si[g.slot(q)].append(i);g.so[g.slot(p)].append(i);expected[i,it]=Q(rate)
 for j,v in enumerate(old['logical_feeds']):
  uid='T%03d'%j;g.units[uid]={'id':uid};g.types[uid]='belt'
  src=sources[v['source']]if v['source']in sources else(v['source'],0,int(v['source_port'].rsplit(':',1)[1])-1)
  dst=(v['target'],2,int(v['target_port'].rsplit(':',1)[1])-1)
  channel(src,(uid,2,0),v['item'],v['planned_rate']['value']);channel((uid,0,0),dst,v['item'],v['planned_rate']['value'])
 f=Flow(g).build();fr,x=f.run(30);assertion(fr['status']=='checked',str(fr));assertion(x is not None and not f.m.exact(x));planned=[Q()for _ in f.m.keys]
 for k,j in f.f.items():planned[j]=expected[k]
 for m in old['machines']:
  for v in m['recipes']:planned[f.batch[m['id'],v['recipe']]]=Q(v['planned_batch_rate']['value'])
 planned[f.delta]=min(expected.values());assertion(not f.m.exact(planned),'候选B计划流未满足所建平均流行')
 out={'scope':'候选B纯速率层，315条逻辑送料各拆为两条测试弧；位置、真实端口offset、供电均未验证，不可作静态全厂输入','machines':len(g.lay['machines']),'logical_feeds':len(old['logical_feeds']),'test_channels':len(g.channels),'sources':len(g.sources),'LP_status':fr['status'],'delta':fr['delta'],'exact_rows':len(f.m.rows),'variables':len(f.m.keys),'planned_delta':str(planned[f.delta]),'witness':fr['witness']}
 (BASE/'candidate_b_rate_test.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 return {k:v for k,v in out.items()if k!='witness'}

if __name__=='__main__':
 test('格式示例整体拒绝、通道2、矩形2870、精确Farkas',format_example)
 test('严格JSON重复键和非有限常量',strict_duplicate)
 for name,mut in [
 ('未知根字段',lambda d:d.update({'ok':True})),('布尔坐标',lambda d:d['empty_rectangle'].update(x0=True)),('浮点坐标',lambda d:d['empty_rectangle'].update(x0=0.0)),('尺寸非70',lambda d:d['layout'].update(W=69)),('虚拟输入',lambda d:d['layout'].update(vin=[{}])),('虚拟输出',lambda d:d['layout'].update(vout=[{}])),('缺core',lambda d:d['layout'].pop('core')),('错误核心口',lambda d:d['layout']['core']['output_items'][0].update(offset=0)),('降低目标',lambda d:d['targets'].update({'高容谷地电池':'1/2'})),('非约分速率',lambda d:d['targets'].update({'高容谷地电池':'6/10'})),('未知单位字段',lambda d:d['layout']['core'].update(powered=True)),('越界矩形',lambda d:d['empty_rectangle'].update(x1=70)),('整数开关',lambda d:d['layout'].update(machines=[dict(machine('M',1,1),settings={'manufacture_on':1})])),('配方机型错误',lambda d:d['layout'].update(machines=[dict(machine('M',1,1),recipe_ids=['粉碎-源矿'])])),('未知物品',lambda d:d['layout']['core']['output_items'][0].update(item='砂叶粉')),('重复单位ID',lambda d:d['layout'].update(machines=[machine('M',1,1),machine('M',6,6)])),('gate无限种却限量',lambda d:d['layout'].update(transport=[{'id':'G','x':1,'y':1,'type':'gate','in_side':0,'filter':None,'k5':1,'cum':None}]))]:test('语法-'+name,lambda mut=mut:reject_schema(mut))
 test('真实取货口手算端点及部分供电',manual_channel_expected);test('占格冲突及大型旋转尺寸',overlap_and_shape);test('正式文件指纹拒绝',source_fingerprint_bad)
 for name in ['omit','extra','offset']:test('N5a-'+name,lambda name=name:channel_mutation(name))
 test('非运输贴靠不成通道',nontransport_adjacent);test('三类制造尺寸与四方向',dimensions);test('核心四方向20口与逐口种类',core_ports);test('供电范围一格重叠和相碰',power_edges)
 test('桥四朝向双轴',bridges)
 for name in ['one_end','same_type','claim','idle_neighbor']:test('桥反例-'+name,lambda name=name:bridge_bad(name))
 test('未用桥轴仍占格',bridge_idle);test('N1核心同样参加分级',n1_core);test('N2桥两轴按物理单位汇总',n2_bridge);test('N3a累计上限',n3a);test('N3b无替代出口',lambda:n3b_cases(False));test('N3b共用侧有替代出口',lambda:n3b_cases(True));test('误料',wrong_item);test('设计外配方',off_recipe);test('allowed_items不能挡货',declared_filter_not_real)
 test('P2纯料路径',p2_good);test('P2中途换料拒绝',p2_bad);test('P1箱体拒绝且占9格',p1_box);test('P6多配方粉碎拒绝',p6);test('纯运输循环拒绝',transport_loop)
 test('最大空矩形独立穷举150图',rectangle_oracle);test('同面积短边择优',rectangle_tie);test('连续三分之一精确核验',linear_positive);test('共享容量超载精确否证',linear_negative);test('delta零的精确对偶',zero_delta);test('局部流正例和篡改见证',local_flow_positive);test('无电制造局部流否证',local_flow_unpowered);test('重复见证条目',witness_duplicates);test('箱体平均守恒及关传输',box_rows);test('会议rt_k16/k17历史回归与v1拒绝',legacy)
 test('候选B219台315送料联合流正例',candidate_b_rate_layer);test('不用求解器复算并篡改Farkas证书',certificate_replay);test('静态投影拒绝伪造零流',projection_forged_zero)
 out={'scope':'部件正反例及不完整全厂拒绝；没有全厂可行正例','total':len(RESULTS),'passed':sum(x['status']=='pass'for x in RESULTS),'failed':sum(x['status']!='pass'for x in RESULTS),'results':RESULTS};(BASE/'selftest_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2));sys.exit(bool(out['failed']))
