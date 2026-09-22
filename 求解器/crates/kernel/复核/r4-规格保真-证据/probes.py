"""规格保真第4轮：公开入口的小型定向复核；所有新文件只写本目录。"""
from pathlib import Path
import copy,json,subprocess,sys,hashlib
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT=Path(__file__).resolve().parent
BIN=ROOT/'target/release/kernel'; CFG=ROOT/'规格/内核配置-v1.json'
sys.path.insert(0,str(ROOT/'数据/样例'))
from test_runtime_input import validate_schema
SCHEMA=json.loads((ROOT/'规格/内核输出.schema.json').read_text())
def read(p): return json.loads(p.read_text())
def write(name,v):
 p=OUT/(name+'.json');p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');return p
def source(name):
 p=ROOT/'数据/样例'/(name+'.json');d=read(p)
 for ref in [d['catalog'],d['parameters']['axis_registry']]: ref['path']=str((p.parent/ref['path']).resolve())
 return d
def axis(d,name,val):
 for group in ['fixed','reconnect','fixedness_unproven']:
  if name in d['parameters'].get(group,{}): d['parameters'][group][name]['value']=copy.deepcopy(val)
 for row in d['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']:
  if row['axis']==name: row['value']['value']=copy.deepcopy(val)
RESULTS=[]
def invoke(name,mode,d,ticks=2,extra=()):
 p=write(name+'-input',d) if isinstance(d,dict) else d
 dest=OUT/(name+'-result.json')
 cmd=[str(BIN),mode,str(p),'--config',str(CFG),'--out',str(dest)]
 if mode in ('run','cycle'):cmd+=['--ticks',str(ticks)]
 cmd+=list(extra)
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=90);data=read(dest)
 schema_ok=None;schema_error=None
 if data.get('schema') in ['kernel-output-v3','kernel-cycle-v1']:
  try:validate_schema(data,SCHEMA,SCHEMA);schema_ok=True
  except Exception as e:schema_ok=False;schema_error=str(e)
 RESULTS.append(dict(case=name,command=cmd,exit_code=r.returncode,status=data.get('status',data.get('schema')),schema_ok=schema_ok,schema_error=schema_error,open_items=data.get('open_items'),stop=data.get('stop'),trace_is_null=data.get('trace','absent') is None,stderr=r.stderr))
 return data
# 完整分支表与永无阻尼查询的单级布局。
d=source('分流器三路轮询');control=invoke('branch-control','run',d,ticks=12)
branch=copy.deepcopy(d['parameters']['fixedness_unproven']['damping.branch']['value']);branch['choices']=[];axis(d,'damping.branch',branch)
invoke('unqueried-branch','run',d,ticks=12)
# 合法装载后第一个时刻在闭包预算处停止。
d=source('生产循环环带');invoke('first-sweep-stop','run',d,extra=['--max-sweeps','1']);invoke('first-sweep-cycle-stop','cycle',d,extra=['--max-sweeps','1'])
# before_boundary初态的派生字段与输出轨迹。
d=source('混做粉碎机两下游');run=invoke('crusher-control','run',d,ticks=3)
closed=copy.deepcopy(d);closed['initial_state']['nonwarehouse']['value']=copy.deepcopy(run['trace']['ticks'][1]['state'])
invoke('checkpoint-control','seed',closed)
for name,mutate in [
 ('pending-trigger-extra',lambda s:s['semantic_context']['pending_events']['value'][0]['trigger'].update(extra='未定义扩展')),
 ('withdrawal-unknown',lambda s:s['environment']['withdrawal_memory']['value']['once_fired'].append('unknown_rule')),
 ('anchor-side',lambda s:s['settings_anchor'].update(side='invalid')),
]:
 trial=copy.deepcopy(closed);mutate(trial['initial_state']['nonwarehouse']['value']);invoke(name,'seed',trial)
# 同一内容的数值合法变写必须按数值验收（Quantity/Time支持有理数）。
trial=copy.deepcopy(closed);trial['initial_state']['nonwarehouse']['value']['semantic_context']['pending_events']['value'][0]['trigger']['value']['value']['value']='4/2'
invoke('pending-rational','seed',trial)
write('probe-results',RESULTS)
print(json.dumps(RESULTS,ensure_ascii=False,indent=2))
