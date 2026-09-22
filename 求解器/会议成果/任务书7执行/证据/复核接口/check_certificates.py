#!/usr/bin/env python3
"""Independent evidence reader: hashes, state normalization, periods and accounting; no kernel checker import."""
from pathlib import Path
from collections import defaultdict
from fractions import Fraction
import copy,json,hashlib
B=Path('/home/zhuran24/zmd-research-fresh/求解器');E=Path(__file__).resolve().parent
PRODUCTS=['高容谷地电池','精选荞愈胶囊'];ORES=['源矿','蓝铁矿'];references={};checks=[]
def read(p):return json.loads(p.read_text())
def num(x):
 while isinstance(x,dict):x=x['value']
 return Fraction(str(x))
def q(n):return {'value':str(Fraction(n))}
def tm(n):return {'kind':'rational','value':q(n)}
def clean(x):
 if isinstance(x,list):return [clean(a) for a in x]
 if not isinstance(x,dict):return x
 if set(x)=={'category','value'}:return q(x['value'])
 return {k:clean(v) for k,v in x.items() if not (k=='basis' and 'status' in x)}
def bind(node,parent):
 if isinstance(node,list):
  for x in node:bind(x,parent)
 elif isinstance(node,dict):
  if 'path' in node and 'sha256' in node:
   p=(parent/node['path']).resolve();actual=hashlib.sha256(p.read_bytes()).hexdigest();assert actual==node['sha256'],(p,actual,node['sha256']);references[str(p)]=actual
  for x in node.values():bind(x,parent)
def normalize(state,source):
 s=clean(copy.deepcopy(state));t=num(s['environment']['time']);units={u['id']:u['kind'] for u in source['layout']['units']};trans={'传送带','桥接器','汇流器','分流器','物品准入口'}
 rows=s['warehouse']['slots'];rows[:]=[r for r in rows if (r['item'] or r['empty_identity']['value']) not in PRODUCTS]
 for r in rows:
  if r['item'] in ORES:r['quantity']={'value':'sufficient'}
 rows.sort(key=lambda r:r['slot'])
 for r in s['inventory']:
  if units[r['slot'].split(':')[0]] in trans:
   for c in r['contents']:c['entered_at']={'residual':q(max(0,1-(t-num(c['entered_at']))))}
  else:
   sums=defaultdict(Fraction)
   for c in r['contents']:sums[c['item']]+=num(c['quantity'])
   r['contents']=[{'item':item,'quantity':q(n),'entered_at':None} for item,n in sorted(sums.items())]
  r['contents'].sort(key=lambda c:(c['item'],str(c['entered_at'])))
 s['inventory'].sort(key=lambda r:r['slot']);s['progress'].sort(key=lambda r:r['unit'])
 for r in s['progress']:
  r['candidate_recipes'].sort();r['cooldowns'].sort(key=lambda r:r['slot'] or '')
 lg=s['logistics']
 for f in ['active_channels','blocked_channels']:lg[f].sort()
 lg['poll_memory']['value']['sides'].sort(key=lambda r:(r['unit'],r['side']))
 for r in lg['poll_memory']['value']['sides']:r['levels'].sort(key=lambda r:r['id'])
 gates={r['unit']:r for r in source['settings']['gates']}
 for r in lg['gate_counters']:
  r['blocked_reasons'].sort();C=gates[r['unit']]['total_limit'];r['total_received']=None if C is None else q(min(num(r['total_received']),num(C)))
  r['window_started_at']=({'phase':'idle'} if r['window_started_at'] is None else {'phase':'active','received':int(num(r['window_received'])),'remaining':q(num(r['window_started_at'])+5-t)})
 lg['gate_counters'].sort(key=lambda r:r['unit']);s['environment']['time']=tm(0)
 sc=s['semantic_context'];sc['parameter_values'].sort(key=lambda r:r['axis']);sc['judgment_context']['value']={'instant':tm(0),'phase':'after_closure','order_scope':'global'}
 for r in sc['pending_events']['value']:
  assert r['predecessors']==[] and r['status']=='waiting' and r['trigger']['kind']=='at_time'
  if r['operation']=='manufacture_complete':
   remaining=num(next(p for p in s['progress'] if p['unit']==r['target'])['remaining']);r['trigger']['kind']='remaining_work'
  else:remaining=num(r['trigger']['value'])-t
  r['event']=[r['operation'],r['target'],str(remaining)];r['trigger']['value']=tm(remaining)
 sc['pending_events']['value'].sort(key=lambda r:(r['operation'],r['target'],str(num(r['trigger']['value']))))
 tc=sc['tick_context']['value']
 for f in ['window_start','window_end']:tc[f]=tm(num(tc[f])-t)
 tc['port_usage']=[r for r in tc['port_usage'] if num(r['quantity'])!=0];tc['port_usage'].sort(key=lambda r:r['port']);tc.pop('movements');tc.pop('internal_passages')
 return {'schema':'phase-cycle-key-v1','domain':'phase_production_v1','state':s,'product_acceptance':[{'item':i,'state':'receivable_at_all_checks'} for i in PRODUCTS]}

def warehouse(s):
 return {r['item'] or r['empty_identity']['value']:num(r['quantity']) for r in s['warehouse']['slots'] if r['item'] or r['empty_identity']['value']}

def decode_trace(r):
 trace=r['trace'];previous=copy.deepcopy(trace.get('start_state'));ticks=[]
 for row in trace['ticks']:
  if 'state' in row:previous=copy.deepcopy(row['state'])
  elif 'checkpoint' in row:previous=copy.deepcopy(row['checkpoint'])
  elif 'delta' in row:
   for op in row['delta']:
    parent=previous
    for key in op['path'][:-1]:parent=parent[key]
    assert op['op']=='replace';parent[op['path'][-1]]=copy.deepcopy(op['value'])
  else:raise AssertionError(row.keys())
  ticks.append((row,copy.deepcopy(previous)))
 return trace.get('start_state'),ticks

for folder in [B/'会议成果/任务书7执行/证据/内核/runs',E/'runs']:
 for p in sorted(folder.glob('*.json')):
  r=read(p);bind(r,p.parent)
  if r.get('schema')!='kernel-cycle-v3':continue
  assert r['environment_assumption']=='仓库收得下成品。'
  if r['cycle'] is None:
   assert r['status']=='inconclusive';checks.append({'file':str(p),'status':r['status'],'completed_ticks':r['budget']['completed_ticks']});continue
  c=r['cycle'];source=read((p.parent/r['replay_input_ref']['path']).resolve());a=num(c['start_time']);b=num(c['end_time']);P=num(c['period']);assert b-a==P>0
  assert num(c['start_state']['environment']['time'])==a and num(c['end_state']['environment']['time'])==b
  assert normalize(c['start_state'],source)==c['start_key']==normalize(c['end_state'],source)==c['end_key']
  assert [num(x['time']) for x in c['ledger']]==list(range(int(a)+1,int(b)+1))
  sums=defaultdict(lambda:defaultdict(Fraction))
  for x in c['ledger']:
   l=x['warehouse_ledger']
   for flow in ['core_inbound','wireless_inbound','port_outbound','external_supply','player_withdrawal','representative_adjustment']:
    for row in l[flow]:sums[row['item']][flow]+=num(row['quantity'])
  Wa,Wb=warehouse(c['start_state']),warehouse(c['end_state'])
  for item in set(Wa)|set(Wb)|set(sums):
   l=sums[item];assert Wb.get(item,0)-Wa.get(item,0)==l['core_inbound']+l['wireless_inbound']+l['external_supply']-l['port_outbound']-l['player_withdrawal']-l['representative_adjustment'],(p,item)
  for rate,target in zip(c['rates'],[Fraction(3,5),Fraction(11,20)]):
   I=sums[rate['item']]['core_inbound']+sums[rate['item']]['wireless_inbound'];assert num(rate['inbound'])==I and num(rate['average'])==I/P and num(rate['target'])==target
   assert rate['comparison']==('lt' if I/P<target else 'gt' if I/P>target else 'eq')
  assert r['parameter_point']['assignment']==source['parameters']
  for s in [c['start_state'],c['end_state']]:
   vals={x['axis']:x for x in s['semantic_context']['parameter_values']}
   for g,life in [('fixed','F'),('offline_mutable','O'),('fixedness_unproven','U')]:
    for k,v in source['parameters'][g].items():assert vals[k]['lifetime']==life and vals[k]['value']==v
  assert r['status']=='diagnostic_cycle' and c['correspondence']['forward_projection']['status']=='unresolved' and c['correspondence']['reverse_reconstruction']['status']=='not_claimed' and c['correspondence']['all_reachable_cycles']['status']=='not_claimed'
  checks.append({'file':str(p),'status':r['status'],'period':str(P),'rates':[str(num(x['average'])) for x in c['rates']],'normalized_endpoints_independently_reconstructed':True,'parameter_identity':True,'warehouse_balance':True})
(E/'certificate-independent.json').write_text(json.dumps({'checks':checks,'references':references},ensure_ascii=False,indent=2)+'\n')
print('PASS',len(checks),'cycle results;',len(references),'distinct referenced file hashes')
