"""full-factory-static-v1 严格解析，语法失败不进入几何/LP。"""
import json, re, hashlib
from pathlib import PurePosixPath
from catalog import *
class Invalid(ValueError): pass
def need(ok,p,msg):
 if not ok: raise Invalid(p+': '+msg)
def obj(v,required,p,optional=()):
 need(type(v)==dict,p,'须为对象');need(set(required)<=v.keys() and v.keys()<=set(required)|set(optional),p,'字段集合错误: '+str(sorted(v.keys())))
def seq(v,p,limit=4900): need(type(v)==list and len(v)<=limit,p,'须为有界数组')
def integer(v,p,lo=0,hi=69): need(type(v)==int and lo<=v<=hi,p,'整数越界或类型错误')
def enum(v,values,p): need(type(v)==str and v in values,p,'未知枚举')
def text(v,p): need(type(v)==str and bool(v.strip()),p,'非空文本')
def ident(v,p): need(type(v)==str and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}',v)!=None,p,'非法 ID')
def sha(v,p): need(type(v)==str and re.fullmatch('[0-9a-f]{64}',v)!=None,p,'非法 SHA256')
def rate(v,p):
 need(type(v)==str and re.fullmatch(r'(0|[1-9][0-9]*)(/[1-9][0-9]*)?',v)!=None,p,'非法 Rate')
 f=F(v);need(str(f)==v and f>=0,p,'Rate 须约分且无前导零');return f
def unique(xs,p): need(len(xs)==len(set(xs)),p,'重复值或 ID')
def itemset(v,p,nonempty=True):
 seq(v,p,19);need(bool(v) or not nonempty,p,'物品集合为空')
 for x in v: enum(x,ITEMS,p)
 unique(v,p)
def bounds(v,p):
 for k in ['x0','y0','x1','y1']: integer(v[k],p+'.'+k)
 need(v['x0']<=v['x1'] and v['y0']<=v['y1'],p,'倒置 Bounds')
def port(v,p):
 obj(v,['unit','side','offset'],p);ident(v['unit'],p);integer(v['side'],p,0,3);integer(v['offset'],p,0,69)
def rates(v,p):
 need(type(v)==dict,p,'Rates 须为对象')
 for k,x in v.items(): enum(k,ITEMS,p);need(rate(x,p)>0,p,'显式 Rates 须正')
def pairs(ps):
 d={}
 for k,v in ps:
  if k in d: raise Invalid('JSON 重复键: '+k)
  d[k]=v
 return d
def loads(raw):
 try: return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x: (_ for _ in ()).throw(Invalid('JSON 非有限值 '+x)))
 except (ValueError,UnicodeError) as e: raise Invalid(str(e)) from e

def validate(d,verify_sources=True):
 obj(d,['schema','candidate_id','source_fingerprints','targets','layout','empty_rectangle','design','flow_witness'],'root',['provenance'])
 need(d['schema']=='full-factory-static-v1','schema','版本不符');ident(d['candidate_id'],'candidate_id')
 obj(d['source_fingerprints'],HASHES,'source_fingerprints')
 for k in HASHES:
  sha(d['source_fingerprints'][k],k)
  need(d['source_fingerprints'][k] in CONSTRAINT_PROFILES if k=='constraints' else d['source_fingerprints'][k]==HASHES[k],k,'不支持的正式文件版本')
  if verify_sources: need(hashlib.sha256((ROOT/FILES[k]).read_bytes()).hexdigest()==d['source_fingerprints'][k],k,'候选指纹与当前正式文件不符；不得跳过版本检查')
 obj(d['targets'],TARGETS,'targets');need(d['targets']==TARGETS,'targets','不得改变目标')
 if 'provenance' in d:
  seq(d['provenance'],'provenance')
  for v in d['provenance']:
   obj(v,['path','sha256'],'provenance');text(v['path'],'provenance.path');sha(v['sha256'],'provenance.sha256')
   need(not PurePosixPath(v['path']).is_absolute() and '..' not in PurePosixPath(v['path']).parts,'provenance','须仓库相对路径')
 l=d['layout'];obj(l,['W','H','machines','warehouse_outlets','core','power_poles','storage_boxes','transport','vin','vout'],'layout')
 for k in ['W','H']: integer(l[k],k,70,70)
 need(l['vin']==[] and l['vout']==[],'layout','禁止虚拟接口')
 ids=[];b=['x0','y0','x1','y1']
 for k in ['machines','warehouse_outlets','power_poles','storage_boxes','transport']: seq(l[k],k)
 for u in l['machines']:
  obj(u,['id','model','kind',*b,'Din','recipe_ids','settings'],'machine',['role']);bounds(u,'machine');integer(u['Din'],'Din',0,3)
  enum(u['model'],MODELS,'model');need(u['kind']==MODELS[u['model']],'kind','机型不符')
  seq(u['recipe_ids'],'recipe_ids',18);need(bool(u['recipe_ids']),'recipe_ids','空配方')
  for r in u['recipe_ids']: enum(r,RECIPES,'recipe_ids');need(RECIPES[r][0]==u['model'],'recipe_ids','错误机型配方')
  unique(u['recipe_ids'],'recipe_ids');obj(u['settings'],['manufacture_on'],'settings');need(type(u['settings']['manufacture_on'])==bool,'manufacture_on','须布尔')
  if 'role' in u: text(u['role'],'role')
 for u in l['warehouse_outlets']:
  obj(u,['id',*b,'Dout','item'],'outlet');bounds(u,'outlet');integer(u['Dout'],'Dout',0,1);enum(u['item'],ITEMS,'item')
 u=l['core'];obj(u,['id',*b,'Din','output_items'],'core');need(u['id']=='CORE','core.id','须 CORE');bounds(u,'core');integer(u['Din'],'core.Din',0,3)
 seq(u['output_items'],'output_items',6);need(len(u['output_items'])==6,'output_items','须六口')
 for v in u['output_items']:
  obj(v,['side','offset','item'],'output_item');integer(v['side'],'side',0,3);integer(v['offset'],'offset',0,8);enum(v['item'],ITEMS,'item')
 unique([(v['side'],v['offset']) for v in u['output_items']],'core output port')
 need({(v['side'],v['offset']) for v in u['output_items']}=={(s,o) for s in [(u['Din']+1)%4,(u['Din']+3)%4] for o in [1,4,7]},'core ports','须正确两边偏移 1/4/7')
 for u in l['power_poles']: obj(u,['id',*b,'orientation'],'pole');bounds(u,'pole');integer(u['orientation'],'orientation',0,0)
 for u in l['storage_boxes']:
  obj(u,['id',*b,'Din','settings'],'box');bounds(u,'box');integer(u['Din'],'Din',0,3);obj(u['settings'],['transfer_on'],'box.settings');need(type(u['settings']['transfer_on'])==bool,'transfer_on','须布尔')
 extra={'belt':['in_side','out_side'],'splitter':['in_side'],'merger':['out_side'],'gate':['in_side','filter','k5','cum'],'bridge':['H_in','V_in']}
 for u in l['transport']:
  need(type(u)==dict and type(u.get('type'))==str and u['type'] in extra,'transport','未知 type')
  obj(u,['id','x','y','type',*extra[u['type']]],'transport');integer(u['x'],'x');integer(u['y'],'y')
  for k in ['in_side','out_side']:
   if k in u: integer(u[k],k,0,3)
  if u['type']=='belt': need(u['in_side']!=u['out_side'],'belt','存取同边')
  if u['type']=='bridge':
   for k,vs in [('H_in',[0,2]),('V_in',[1,3])]: need(u[k] is None or type(u[k])==int and u[k] in vs,k,'桥声明错误')
  if u['type']=='gate':
   if u['filter'] is not None: enum(u['filter'],ITEMS,'filter')
   else: need(u['k5'] is None and u['cum'] is None,'gate','不限物品不可限量')
   for k,hi in [('k5',5),('cum',5000)]:
    if u[k] is not None: integer(u[k],k,1,hi)
 for k in ['machines','warehouse_outlets','power_poles','storage_boxes','transport','core']:
  for u in [l[k]] if k=='core' else l[k]: ident(u['id'],'id');ids.append(u['id'])
 unique(ids,'layout IDs')
 obj(d['empty_rectangle'],b,'empty_rectangle');bounds(d['empty_rectangle'],'empty_rectangle')
 z=d['design'];obj(z,['class','physical_channels','restrictions'],'design',['source_bindings','logical_feeds']);enum(z['class'],['p2p','n_restricted'],'class')
 seq(z['physical_channels'],'physical_channels',9800)
 for e in z['physical_channels']:
  obj(e,['id','from','to','allowed_items'],'channel');ident(e['id'],'channel.id');port(e['from'],'from');port(e['to'],'to');itemset(e['allowed_items'],'allowed_items')
 unique([e['id'] for e in z['physical_channels']],'channel IDs');unique([(ref(e['from']),ref(e['to'])) for e in z['physical_channels']],'channel endpoints')
 seq(z['restrictions'],'restrictions')
 for r in z['restrictions']:
  obj(r,['id','source','statement','coverage_loss','release_obligations','failure_scope'],'restriction');ident(r['id'],'restriction.id');seq(r['source'],'source',3);need(bool(r['source']),'source','empty')
  for s in r['source']: enum(s,['dynamic','shape','numeric'],'source')
  unique(r['source'],'source')
  for k in ['statement','coverage_loss','release_obligations','failure_scope']: text(r[k],k)
 unique([r['id'] for r in z['restrictions']],'restriction IDs')
 if 'source_bindings' in z:
  seq(z['source_bindings'],'source_bindings',52)
  for r in z['source_bindings']: obj(r,['logical_source_id','port'],'binding');ident(r['logical_source_id'],'logical_source_id');port(r['port'],'binding.port')
  unique([r['logical_source_id'] for r in z['source_bindings']],'source ids');unique([ref(r['port']) for r in z['source_bindings']],'source ports')
 if 'logical_feeds' in z:
  need(z['class']=='p2p','logical_feeds','只支持 p2p');seq(z['logical_feeds'],'logical_feeds',9800)
  for f in z['logical_feeds']:
   obj(f,['id','from','to','item','rate','path'],'feed');ident(f['id'],'feed.id');port(f['from'],'feed.from');port(f['to'],'feed.to');enum(f['item'],ITEMS,'feed.item');need(0<rate(f['rate'],'feed.rate')<=1,'feed.rate','须 (0,1]')
   seq(f['path'],'feed.path',9800);need(bool(f['path']),'path','empty')
   for e in f['path']: ident(e,'path id')
   unique(f['path'],'path')
  unique([f['id'] for f in z['logical_feeds']],'feed IDs')
 w=d['flow_witness']
 if w is not None:
  obj(w,['channel_flows','batch_rates','box_transfers','delta'],'flow_witness');need(0<rate(w['delta'],'delta')<=1,'delta','须 (0,1]')
  for arr,ks in [('channel_flows',['channel_id','rates']),('batch_rates',['machine_id','recipe_id','rate']),('box_transfers',['box_id','rates'])]:
   seq(w[arr],arr,88200)
   for v in w[arr]:
    obj(v,ks,arr);ident(v[ks[0]],ks[0])
    if arr=='batch_rates': enum(v['recipe_id'],RECIPES,'recipe_id');rate(v['rate'],'batch rate')
    else: rates(v['rates'],'rates')
   unique([(v['machine_id'],v['recipe_id']) if arr=='batch_rates' else v[ks[0]] for v in w[arr]],arr)
 return d
