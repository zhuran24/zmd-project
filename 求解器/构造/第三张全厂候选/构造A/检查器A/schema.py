"""格式.md §§2-9 的严格语法核验。语法失败不进入几何或 LP。"""
import json,re
from pathlib import PurePosixPath
from fractions import Fraction
from catalog import *
class Invalid(ValueError):pass
def need(ok,msg):
 if not ok:raise Invalid(msg)
def obj(v,required,optional=()):
 need(type(v) is dict,'期望对象');need(set(required)<=set(v)<=set(required)|set(optional),f'字段集合错误: missing={set(required)-set(v)}, unknown={set(v)-set(required)-set(optional)}')
def arr(v,limit=4900):need(type(v)is list and len(v)<=limit,'数组类型或长度不合法')
def integer(v,lo,hi):need(type(v)is int and lo<=v<=hi,f'整数范围 {lo}…{hi}: {v!r}')
def ident(v):need(type(v)is str and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}',v),'Id 错误')
def text(v):need(type(v)is str and bool(v.strip()),'Text 须非空')
def sha(v):need(type(v)is str and re.fullmatch('[0-9a-f]{64}',v),'Sha256 错误')
def enum(v,choices):need(type(v)is str and v in choices,f'未知枚举 {v!r}')
def rate(v,positive=False):
 need(type(v)is str and re.fullmatch(r'(0|[1-9][0-9]*)(/[1-9][0-9]*)?',v),'Rate 编码错误')
 q=Fraction(v);need(str(q)==v and (q>0 if positive else q>=0),'Rate 须约分且非负');return q
def unique(v):need(len(v)==len(set(v)),'数组有重复值')
def items(v):
 arr(v,19);unique(v)
 for a in v:enum(a,ITEMS)
def rates(v):
 need(type(v)is dict,'Rates 须对象')
 for k,a in v.items():enum(k,ITEMS);rate(a,True)
def bounds(v):
 for k in ('x0','y0','x1','y1'):integer(v[k],0,69)
 need(v['x0']<=v['x1'] and v['y0']<=v['y1'],'Bounds 上下界倒置')
def port(v):
 obj(v,['unit','side','offset']);ident(v['unit']);integer(v['side'],0,3);integer(v['offset'],0,69)
def read_bytes(raw):
 def pairs(xs):
  d={}
  for k,v in xs:need(k not in d,'JSON 重复键: '+k);d[k]=v
  return d
 def bad(v):raise Invalid('非法 JSON 常量: '+v)
 try:return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=bad)
 except (UnicodeError,json.JSONDecodeError) as e:raise Invalid(str(e)) from e

def validate(d):
 obj(d,['schema','candidate_id','source_fingerprints','targets','layout','empty_rectangle','design','flow_witness'],['provenance'])
 need(d['schema']=='full-factory-static-v1','不支持的 schema');ident(d['candidate_id'])
 obj(d['source_fingerprints'],HASHES)
 for v in d['source_fingerprints'].values():sha(v)
 obj(d['targets'],TARGETS)
 for k,v in d['targets'].items():rate(v);need(v==TARGETS[k],'目标不可修改')
 if 'provenance' in d:
  arr(d['provenance'])
  for p in d['provenance']:
   obj(p,['path','sha256']);text(p['path']);sha(p['sha256']);pp=PurePosixPath(p['path']);need(not pp.is_absolute() and '..' not in pp.parts,'provenance 非仓库相对路径')
 lay=d['layout'];obj(lay,['W','H','machines','warehouse_outlets','core','power_poles','storage_boxes','transport','vin','vout'])
 integer(lay['W'],70,70);integer(lay['H'],70,70)
 need(lay['vin']==[] and type(lay['vin'])is list and lay['vout']==[] and type(lay['vout'])is list,'禁止虚拟 vin/vout')
 bkeys=['id','x0','y0','x1','y1'];uids=[]
 for group in ['machines','warehouse_outlets','power_poles','storage_boxes','transport']:
  arr(lay[group])
  for v in lay[group]:
   need(type(v)is dict,'单位须对象');ident(v.get('id'));uids.append(v['id'])
   if group=='machines':
    obj(v,bkeys+['model','kind','Din','recipe_ids','settings'],['role']);enum(v['model'],MODELS);enum(v['kind'],['小','中','大']);integer(v['Din'],0,3)
    arr(v['recipe_ids'],18);need(bool(v['recipe_ids']),'空配方集');unique(v['recipe_ids'])
    for a in v['recipe_ids']:enum(a,RECIPES);need(RECIPES[a][0]==v['model'],'配方与机型不符')
    obj(v['settings'],['manufacture_on']);need(type(v['settings']['manufacture_on'])is bool,'开关须布尔值')
    if 'role'in v:text(v['role'])
   elif group=='warehouse_outlets':obj(v,bkeys+['Dout','item']);integer(v['Dout'],0,1);enum(v['item'],ITEMS)
   elif group=='power_poles':obj(v,bkeys+['orientation']);integer(v['orientation'],0,0)
   elif group=='storage_boxes':
    obj(v,bkeys+['Din','settings']);integer(v['Din'],0,3);obj(v['settings'],['transfer_on']);need(type(v['settings']['transfer_on'])is bool,'开关须布尔值')
   else:
    enum(v['type'],['belt','splitter','merger','gate','bridge'])
    extras={'belt':['in_side','out_side'],'splitter':['in_side'],'merger':['out_side'],'gate':['in_side','filter','k5','cum'],'bridge':['H_in','V_in']}[v['type']]
    obj(v,['id','x','y','type']+extras);integer(v['x'],0,69);integer(v['y'],0,69)
    for k in ['in_side','out_side']:
     if k in v:integer(v[k],0,3)
    if v['type']=='belt':need(v['in_side']!=v['out_side'],'带子存取同边')
    if v['type']=='bridge':
     for k,sides in [('H_in',(0,2)),('V_in',(1,3))]:need(v[k]is None or type(v[k])is int and v[k]in sides,'桥轴声明类型错误')
    if v['type']=='gate':
     if v['filter']is not None:enum(v['filter'],ITEMS)
     else:need(v['k5']is None and v['cum']is None,'未限种不能限量')
     for k,hi in [('k5',5),('cum',5000)]:
      if v[k]is not None:integer(v[k],1,hi)
   if group!='transport':bounds(v)
 c=lay['core'];obj(c,bkeys+['Din','output_items']);need(c['id']=='CORE','核心 id 须 CORE');uids.append(c['id']);bounds(c);integer(c['Din'],0,3)
 arr(c['output_items'],6);need(len(c['output_items'])==6,'核心须六个取货设定');ps=[]
 for p in c['output_items']:
  obj(p,['side','offset','item']);integer(p['side'],0,3);integer(p['offset'],0,8);enum(p['item'],ITEMS);ps.append((p['side'],p['offset']))
 need(set(ps)=={(s,o) for s in [(c['Din']+1)%4,(c['Din']+3)%4] for o in [1,4,7]},'核心六口位置错误');unique(uids)
 obj(d['empty_rectangle'],['x0','y0','x1','y1']);bounds(d['empty_rectangle'])
 de=d['design'];obj(de,['class','physical_channels','restrictions'],['source_bindings','logical_feeds']);enum(de['class'],['p2p','n_restricted'])
 arr(de['physical_channels'],9800);ids=[];pairs=[]
 for v in de['physical_channels']:
  obj(v,['id','from','to','allowed_items']);ident(v['id']);ids.append(v['id']);port(v['from']);port(v['to']);items(v['allowed_items']);need(bool(v['allowed_items']),'通道物品集为空');pairs.append((tuple(v['from'][k] for k in ['unit','side','offset']),tuple(v['to'][k] for k in ['unit','side','offset'])))
 unique(ids);unique(pairs)
 arr(de['restrictions']);ids=[]
 for v in de['restrictions']:
  obj(v,['id','source','statement','coverage_loss','release_obligations','failure_scope']);ident(v['id']);ids.append(v['id']);arr(v['source'],3);unique(v['source']);need(bool(v['source']),'空限制来源')
  for x in v['source']:enum(x,['dynamic','shape','numeric'])
  for k in ['statement','coverage_loss','release_obligations','failure_scope']:text(v[k])
 unique(ids)
 if 'source_bindings'in de:
  arr(de['source_bindings'],52);ids=[];ports=[]
  for v in de['source_bindings']:
   obj(v,['logical_source_id','port']);ident(v['logical_source_id']);port(v['port']);ids.append(v['logical_source_id']);ports.append(tuple(v['port'][k] for k in ['unit','side','offset']))
  unique(ids);unique(ports)
 if 'logical_feeds'in de:
  need(de['class']=='p2p','logical_feeds 仅 p2p');arr(de['logical_feeds'],9800);ids=[]
  for v in de['logical_feeds']:
   obj(v,['id','from','to','item','rate','path']);ident(v['id']);ids.append(v['id']);port(v['from']);port(v['to']);enum(v['item'],ITEMS);need(rate(v['rate'],True)<=1,'逻辑速率超 1');arr(v['path'],9800);need(bool(v['path']),'空路径');unique(v['path'])
   for a in v['path']:ident(a)
  unique(ids)
 w=d['flow_witness']
 if w is not None:
  obj(w,['channel_flows','batch_rates','box_transfers','delta']);need(rate(w['delta'],True)<=1,'delta 超1')
  for group,keys in [('channel_flows',['channel_id','rates']),('batch_rates',['machine_id','recipe_id','rate']),('box_transfers',['box_id','rates'])]:
   arr(w[group],88200)
   for v in w[group]:
    obj(v,keys)
    for k in keys:
     if k=='rates':rates(v[k])
     elif k=='rate':rate(v[k])
     elif k=='recipe_id':enum(v[k],RECIPES)
     else:ident(v[k])
 return d
