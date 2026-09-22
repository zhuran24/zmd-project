#!/usr/bin/env python3
from pathlib import Path
import sys,json,copy,hashlib
sys.dont_write_bytecode=True
from run_review import ROOT,E,run
sys.path.insert(0,str(ROOT/'crates/kernel/tests'));sys.path.insert(0,str(ROOT/'数据/样例'))
import build_fixtures as b
from generate_examples import unit
from runtime_example import quantity as q,time_value as t
b.OUT=E
cfg=json.loads((ROOT/'规格/内核配置-v1.json').read_text());BIN=ROOT/'target/release/kernel';CFG=ROOT/'规格/内核配置-v1.json'
def migrate(d):
 p=d['parameters'];old={k:v for g in ['fixed','offline_mutable','fixedness_unproven'] for k,v in p[g].items()}
 for g in ['fixed','offline_mutable','fixedness_unproven']:p[g]={}
 for k,r in cfg['axes'].items():
  v=copy.deepcopy(old[k]);g='fixed' if r['lifetime'].startswith('F') else 'offline_mutable' if r['lifetime']=='O' else 'fixedness_unproven'
  if r['disposition']!='由输入全称量化':v['value']=copy.deepcopy(r['value'])
  p[g][k]=v
 for ref,path in [(d['catalog'],ROOT/'数据/正式静态目录.json'),(p['axis_registry'],ROOT/'规格/选择点参数轴.md')]:ref.update(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 d['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']=[dict(axis=k,value=copy.deepcopy(v),lifetime=life) for g,life in [('fixed','F'),('offline_mutable','O'),('fixedness_unproven','U')] for k,v in p[g].items()]
 return d
units=[unit('cross','桥接器',15,41),unit('west','传送带',14,41,'r270'),unit('south','传送带',15,40),unit('east','传送带',16,41,'r270'),unit('north','传送带',15,42)]
base=migrate(b.generate('bridge-template',units));summary=[]
for name,item in [('bridge-same','高容谷地电池'),('bridge-different','精选荞愈胶囊')]:
 d=copy.deepcopy(base);s=d['initial_state']['nonwarehouse']['value']
 for slot,what in [('west:transport:0','高容谷地电池'),('south:transport:0',item)]:
  next(r for r in s['inventory'] if r['slot']==slot)['contents']=[dict(item=what,quantity=q(1),entered_at=t(-1))]
 p=E/(name+'-unseeded.json');p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');seed=E/(name+'-input.json')
 run(name+'-seed',[BIN,'seed',p,'--config',CFG,'--out',seed]);run(name+'-check',[BIN,'check',seed,'--config',CFG])
 record=E/(name+'-record.json');run(name+'-run',[BIN,'run',seed,'--config',CFG,'--ticks','2','--format','full_state_each_instant','--out',record]);run(name+'-verify',[BIN,'verify-record',record,'--config',CFG])
 r=json.loads(record.read_text());s=r['trace']['ticks'][0]['state'];v={x['slot']:x['contents'] for x in s['inventory']};total=sum(int(c['quantity']['value']) for k,cs in v.items() if k.startswith('cross:') for c in cs)
 assert total==(1 if name=='bridge-same' else 2)
 summary.append({'case':name,'t0_bridge_count':total,'t0_inventory':v,'trace_scope':'fixed integer engineering point; rule-level exclusion independently follows R13/R23/R63'})
(E/'bridge-probe-results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print('bridge same-kind:',summary[0]['t0_bridge_count'],'different-kind:',summary[1]['t0_bridge_count'])
