"""KQ-07检查点负例：正确参数/缺失参数/冲突参数经run与seed分别验证。"""
import json,copy,subprocess
from pathlib import Path
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');OUT=Path(__file__).resolve().parent;BIN=ROOT/'target/release/kernel';CFG=ROOT/'规格/内核配置-v1.json'
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
source=ROOT/'数据/样例/桥接器双通路.json';raw=json.loads(source.read_text());record=json.loads((ROOT/'数据/样例/桥接器双通路-运行记录-v3-kernel.json').read_text())
raw['initial_state']['nonwarehouse']['value']=copy.deepcopy(record['trace']['ticks'][5]['state'])
for ref in [raw['catalog'],raw['parameters']['axis_registry']]:ref['path']=str((source.parent/ref['path']).resolve())
reports=[]
for case in ['control','missing','conflicting','changed_input_phase']:
 d=copy.deepcopy(raw);state=d['initial_state']['nonwarehouse']['value'];values=state['semantic_context']['parameter_values']
 if case=='missing':state['semantic_context']['parameter_values']=[]
 if case=='conflicting':next(x for x in values if x['axis']=='transfer.phase')['value']['value']['values'][0]['remaining']['value']['value']='4'
 if case=='changed_input_phase':d['parameters']['fixedness_unproven']['transfer.phase']['value']['values'][0]['remaining']['value']['value']='4'
 path=OUT/f'seed-{case}-input.json';save(path,d)
 case_report={'case':case,'input':str(path),'original_phase':'after_closure','time':state['environment']['time']}
 for op in ['run','seed']:
  dest=OUT/f'seed-{case}-{op}.json';command=[str(BIN),op,str(path),'--config',str(CFG),'--out',str(dest)]+(['--ticks','2']if op=='run' else [])
  process=subprocess.run(command,capture_output=True,text=True)
  case_report[op]={'command':command,'code':process.returncode,'stdout':process.stdout,'stderr':process.stderr,'output':str(dest)if dest.exists()else None}
  if op=='seed' and process.returncode==0:
   got=json.loads(dest.read_text())['initial_state']['nonwarehouse']['value'];case_report['seed']['state_equal']=got==state
   case_report['seed']['changed_top_fields']=[k for k in state if got[k]!=state[k]]
   case_report['seed']['parameter_values_equal']=got['semantic_context']['parameter_values']==state['semantic_context']['parameter_values']
 reports.append(case_report)
save(OUT/'seed-probe-results.json',reports)
for r in reports:print(r['case'],'run',r['run']['code'],'seed',r['seed']['code'],'same',r['seed'].get('state_equal'),r['run']['stderr'].strip())
