#!/usr/bin/env python3
from pathlib import Path
from fractions import Fraction
from collections import defaultdict
import json,copy
E=Path(__file__).resolve().parent
flows=['core_inbound','wireless_inbound','port_outbound','external_supply','player_withdrawal','representative_adjustment']
def n(x):
 while isinstance(x,dict):x=x['value']
 return Fraction(x)
def ware(s):return {r['item'] or r['empty_identity']['value']:n(r['quantity']) for r in s['warehouse']['slots'] if r['item'] or r['empty_identity']['value']}
def states(trace):
 old=copy.deepcopy(trace['start_state'])
 for r in trace['ticks']:
  new=copy.deepcopy(r.get('state',old))
  for op in r.get('delta',[]):
   assert op['op']=='replace';target=new
   for k in op['path'][:-1]:target=target[k]
   target[op['path'][-1]]=copy.deepcopy(op['value'])
  yield r,old,new
  old=new
rows=[]
for p in sorted((E/'runs').glob('*.json')):
 r=json.loads(p.read_text())
 if r.get('schema')!='kernel-output-v4':continue
 ticks=0;totals=defaultdict(Fraction);attempts=[]
 for tick,old,new in states(r['trace']):
  ticks+=1;W0,W1=ware(old),ware(new);ledger=tick['warehouse_ledger'];sums=defaultdict(lambda:defaultdict(Fraction))
  for f in flows:
   for v in ledger[f]:sums[v['item']][f]+=n(v['quantity'])
  for item in set(W0)|set(W1)|set(sums):
   s=sums[item];delta=s['core_inbound']+s['wireless_inbound']+s['external_supply']-s['port_outbound']-s['player_withdrawal']-s['representative_adjustment'];assert W1.get(item,0)-W0.get(item,0)==delta,(p,item,tick['time'])
   totals[item]+=s['core_inbound']+s['wireless_inbound']
  for row in ledger['totals']:
   for f in flows:assert n(row[f])==sums[row['item']][f]
   assert n(row['actual_inbound'])==sums[row['item']]['core_inbound']+sums[row['item']]['wireless_inbound']
  if p.stem.startswith('无线') or p.stem=='同刻双箱争余量':
   stock={slot['slot']:copy.deepcopy(slot['contents']) for slot in old['inventory']};current=defaultdict(Fraction,W0)
   for ev in tick['events']:
    if ev['operation']!='transfer' or ev['outcome'] not in ['success','failure']:continue
    uid=ev['target'];byitem=defaultdict(Fraction)
    for slot,cs in stock.items():
     if slot.startswith(uid+':'):
      for c in cs:byitem[c['item']]+=n(c['quantity'])
    expected={item:min(count,80000-current[item]) for item,count in byitem.items() if min(count,80000-current[item])>0}
    detail=json.loads(ev['detail']);assert {k:Fraction(v) for k,v in detail['sent'].items()}==expected
    for item,count in expected.items():
     current[item]+=count;rest=count
     for slot,cs in stock.items():
      if not slot.startswith(uid+':'):continue
      for c in cs:
       if c['item']==item:
        take=min(rest,n(c['quantity']));c['quantity']={'value':str(n(c['quantity'])-take)};rest-=take
     assert rest==0
    attempts.append({'unit':uid,'time':str(n(tick['time'])),'sent':{k:str(v) for k,v in expected.items()}})
    assert detail['cooldown_restarted'] is True
    assert n(next(pr for pr in new['progress'] if pr['unit']==uid)['cooldowns'][0]['remaining'])==5
   for slot,cs in stock.items():
    newslot=next(row for row in new['inventory'] if row['slot']==slot);a=defaultdict(Fraction);b=defaultdict(Fraction)
    for c in cs:a[c['item']]+=n(c['quantity'])
    for c in newslot['contents']:b[c['item']]+=n(c['quantity'])
    assert {k:v for k,v in a.items() if v}==dict(b)
  if p.stem in ['无线空箱','无线全拒收'] and ticks==len(r['trace']['ticks']):assert [x['time'] for x in attempts]==['0','5']
 rows.append({'file':str(p),'ticks':ticks,'actual_inbound':{k:str(v) for k,v in totals.items() if v},'wireless_attempts':attempts,'warehouse_balance':True})
(E/'runs-independent.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print('PASS',len(rows),'records;',sum(x['ticks'] for x in rows),'tick ledgers')
