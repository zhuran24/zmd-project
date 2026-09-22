"""覆盖抽查直接读取事件、库存和历史，不将生产者的exercised标签当证明。"""
import json,collections
from pathlib import Path
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');OUT=Path(__file__).resolve().parent;BASE=ROOT/'数据/样例'
def read(p):return json.loads(p.read_text())
def n(v):return int(v['value'])
def at(v):return n(v['value'])
reports={}
for name in ['桥接器双通路','传输拒收与暂停核验','研磨混做核验','阻尼连续带核验','阻尼切支恢复核验']:
 data=read(BASE/(name+'.json'));record=read(BASE/(name+'-运行记录-v3-kernel.json'));ticks=record['trace']['ticks'];all_events={e['event']:(at(t['time']),e)for t in ticks for e in t['events']}
 info={'record':str(BASE/(name+'-运行记录-v3-kernel.json')),'ticks':len(ticks),'axis_samples':{}}
 for row in record['uncovered_axes']:
  axis=row['axis']
  if row['coverage_status']=='exercised' and (axis.startswith(('transfer.','bridge.','manufacturing.','damping.'))or axis in ['connection.bridge_first_contact','warehouse.delivery_count','warehouse.empty_slot_identity','warehouse.external_supply']):
   witnesses=[{'time':all_events[e][0],'event':all_events[e][1]}for e in row['evidence']if e in all_events]
   assert len(witnesses)==len(row['evidence']),(name,axis)
   info['axis_samples'][axis]={'claimed':'exercised','event_references_exist':True,'count':len(witnesses),'first_event':witnesses[0]}
 if name=='桥接器双通路':
  moves=[m for t in ticks for m in t['state']['semantic_context']['tick_context']['value']['movements']]
  flux=collections.Counter(m['channel']for m in moves);assert len(flux)==4 and set(flux.values())=={8}
  info['bridge_flux']=dict(flux)
  info['wireless_inbound']=dict(sum((collections.Counter({r['item']:n(r['quantity'])for r in t['warehouse_ledger']['wireless_inbound']})for t in ticks),collections.Counter()))
  assert info['wireless_inbound']=={'精选荞愈胶囊':8,'高容谷地电池':8}
  times={e['id']:at(e['time'])for e in data['timeline']['events']}
  info['bridge_connection_history']=[dict(c,time=times[c['event']])for c in data['timeline']['connection_events']if 'bridge:'in c['channel']]
  info['bridge_axes_at_input']=next(u['bridge_axes']for u in data['layout']['units']if u['kind']=='桥接器')
  assert all(c['time']<0 for c in info['bridge_connection_history'])
  assert min(at(t['time'])for t in ticks)==0
  assert not any(e['operation']in ['build','connection_open','bridge_direction']for _,e in all_events.values())
  info['first_contact_executed_in_trace']=False
 if name=='传输拒收与暂停核验':
  initial=data['initial_state']['nonwarehouse']['value'];paused=next(p for p in initial['progress']if p['unit']=='east_box')['cooldowns'];assert paused[0]['remaining']['value']['value']=='3'
  assert all(next(p for p in t['state']['progress']if p['unit']=='east_box')['cooldowns']==paused for t in ticks)
  rejected=[(time,e)for time,e in all_events.values()if e['operation']=='transfer'and e['outcome']=='failure'];assert len(rejected)==1
  time,e=rejected[0];assert e['detail']=='warehouse_capacity'
  assert not any(r['event']==e['event']for t in ticks for r in t['warehouse_ledger']['wireless_inbound'])
  info['rejected_transaction']=e;info['paused_cooldown']=3;info['pause_preserved_at_all_ticks']=True
 if name=='研磨混做核验':
  completions=[{'time':at(t['time']),'event':e,'recipe':next(p['recipe']for p in t['state']['progress']if p['unit']==e['target'])}for t in ticks for e in t['events']if e['operation']=='manufacture_complete']
  # 完成事件可能同刻清空旧配方；依据上一刻working批次核完整配方。
  previous=record['trace']['start_state'];completions=[]
  for t in ticks:
   for e in t['events']:
    if e['operation']=='manufacture_complete':completions.append({'time':at(t['time']),'event':e['event'],'unit':e['target'],'recipe':next(p['recipe']for p in previous['progress']if p['unit']==e['target'])})
   previous=t['state']
  assert len(completions)==2 and len({r['recipe']for r in completions})==2;info['completions']=completions
 if name.startswith('阻尼'):
  used=sorted({b for _,e in all_events.values()for b in e['basis']if b.startswith('damping.evaluated:')});assert used
  info['damping_basis']=used
  initial=data['initial_state']['nonwarehouse']['value'];info['nontransport_output_level_count']={s['unit']:len(s['levels'])for s in initial['logistics']['poll_memory']['value']['sides']if s['side']=='output'and s['graded']and len(s['levels'])>=2};assert info['nontransport_output_level_count']
  info['active_graphs']=[{'time':at(t['time']),'blocked':t['state']['logistics']['blocked_channels']}for t in ticks]
 reports[name]=info
(OUT/'coverage-raw-samples.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n')
print('桥两通路各8件，两种成品各实际无线入库8件；拒收、暂停、研磨双配方和多级阻尼记录原文已核。先接事件全部早于运行段。')
