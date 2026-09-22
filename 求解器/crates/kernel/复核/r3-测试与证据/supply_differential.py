"""独立补矿模式差分：完整非矿后态、事件、交付、守恒及确定性。"""
import copy,json,subprocess,hashlib
from pathlib import Path
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');OUT=Path(__file__).resolve().parent;BIN=ROOT/'target/release/kernel';CFG=ROOT/'规格/内核配置-v1.json';ORES=['源矿','蓝铁矿']
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def tv(n):return {'kind':'rational','value':{'category':'候选','value':str(n)}}
def q(n):return {'category':'算术推论','value':str(n)}
def normalize(tick):
 t=copy.deepcopy(tick)
 for row in t['state']['warehouse']['slots']:
  if row['item'] in ORES:row['quantity']={'value':'supply-mode-dependent','category':'supply-mode-dependent'}
 for row in t['state']['semantic_context']['parameter_values']:
  if row['axis']=='warehouse.external_supply':row['value']['value']='supply-mode-dependent'
 t['events']=[e for e in t['events']if e['operation']!='ore_supply']
 t['warehouse_ledger']['external_supply']=[]
 for row in t['warehouse_ledger']['totals']:row['external_supply']=q(0)
 # 可读摘要中只有仓库矿量允许随模式不同，其余字段仍逐项比对。
 if 'warehouse_ore' in t['summary']:t['summary']['warehouse_ore']='supply-mode-dependent'
 if 'external_supply' in t['summary']:t['summary']['external_supply']={}
 return t
reports=[]
for sample in ['混做粉碎机两下游','轮询均分核验']:
 source=ROOT/f'数据/样例/{sample}.json';original=json.loads(source.read_text());records={}
 for mode in ['explicit_ore_history','sufficient']:
  d=copy.deepcopy(original)
  for ref in [d['catalog'],d['parameters']['axis_registry']]:ref['path']=str((source.parent/ref['path']).resolve())
  supply={'kind':'sufficient'}if mode=='sufficient'else{'kind':'explicit_ore_history','events':[],'through':tv(100)}
  d['parameters']['fixedness_unproven']['warehouse.external_supply']['value']=supply
  for row in d['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']:
   if row['axis']=='warehouse.external_supply':row['value']['value']=copy.deepcopy(supply)
  path=OUT/f'diff-{sample}-{mode}.json';dest=OUT/f'diff-{sample}-{mode}-record.json';save(path,d)
  cmd=[str(BIN),'run',str(path),'--config',str(CFG),'--ticks','40','--out',str(dest)]
  r=subprocess.run(cmd,text=True,capture_output=True);assert r.returncode==0,(cmd,r.stdout,r.stderr)
  first=dest.read_bytes();r=subprocess.run(cmd,text=True,capture_output=True);assert r.returncode==0 and dest.read_bytes()==first,'相同CLI输入未逐字节确定'
  records[mode]=json.loads(first)
 a,b=[records[m]for m in ['explicit_ore_history','sufficient']]
 for x,y in zip(a['trace']['ticks'],b['trace']['ticks']):assert normalize(x)==normalize(y),('差分',sample,x['time'])
 sys_supply=sum(int(r['quantity']['value'])for t in b['trace']['ticks']for r in t['warehouse_ledger']['external_supply'])
 outbound=sum(int(r['quantity']['value'])for t in b['trace']['ticks']for r in t['warehouse_ledger']['port_outbound']if r['item']in ORES)
 assert sys_supply==outbound>0
 for mode,rec in records.items():
  before={r['item']:int(r['quantity']['value'])for r in rec['trace']['start_state']['warehouse']['slots']if r['item']}
  for tick in rec['trace']['ticks']:
   after={r['item']:int(r['quantity']['value'])for r in tick['state']['warehouse']['slots']if r['item']}
   for row in tick['warehouse_ledger']['totals']:
    amount=lambda f:int(row[f]['value'])
    assert after.get(row['item'],0)-before.get(row['item'],0)==amount('actual_inbound')+amount('external_supply')-amount('port_outbound')-amount('player_withdrawal')-amount('representative_adjustment')
   before=after
 reports.append({'sample':sample,'ticks':40,'full_normalized_ticks_equal':True,'byte_determinism_each_mode':True,'per_species_conservation':True,'sufficient_external_supply_equals_ore_outbound':outbound})
save(OUT/'supply-differential-results.json',reports);print(json.dumps(reports,ensure_ascii=False))
