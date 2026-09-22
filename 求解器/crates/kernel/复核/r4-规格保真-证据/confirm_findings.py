"""独立汇总三个规范反例的前件，所有证据限定为实际公开入口结果。"""
from pathlib import Path
import json,subprocess
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');OUT=Path(__file__).resolve().parent
read=lambda name:json.loads((OUT/(name+'.json')).read_text())
data=read('branch-control-input');record=read('branch-control-result')
kinds={u['id']:u['kind'] for u in data['layout']['units']}
transport={'桥接器','分流器','汇流器','物品准入口','传送带'}
levels={u:set() for u,k in kinds.items() if k not in transport and k!='供电桩'}
for c in data['layout']['physical_channels']:
 u=c['source_port'].split(':')[0];v=c['target_port'].split(':')[0]
 if u in levels:levels[u].add('direct:'+c['id'] if kinds[v]=='汇流器' else 'other')
assert all(len(v)<=1 for v in levels.values())
missing=read('unqueried-branch-result');assert missing['status']=='unresolved' and 'damping.branch' in str(missing['open_items'])
assert record['status']=='completed'
first=dict(maximum_geometric_output_levels={k:sorted(v) for k,v in levels.items()},
 no_possible_damping_request=True,control_ticks=len(record['trace']['ticks']),
 missing_table_status=missing['status'],missing_table_reason=missing['open_items'])
base=read('control-key-result');extended=read('extra-key-result')
assert base['status']==extended['status']=='accepted'
a=base['key'];b=extended['key'];extra=b['state']['semantic_context']['pending_events']['value'][0]['trigger'].pop('extra')
assert a==b
second=dict(seed_cli_accepted=read('pending-trigger-extra-result')['schema']=='kernel-input-v3',
 public_key_accepted=True,key_difference_only='/state/semantic_context/pending_events/value/0/trigger/extra',value=extra,
 input_requirement='trigger恰含kind/value；未知扩展拒收')
p=OUT/'checkpoint-control-input.json';target=OUT/'closed-first-sweep-stop-result.json'
cmd=[str(ROOT/'target/release/kernel'),'run',str(p),'--config',str(ROOT/'规格/内核配置-v1.json'),'--ticks','1','--max-sweeps','1','--out',str(target)]
proc=subprocess.run(cmd,capture_output=True,text=True);result=json.loads(target.read_text());state=read('checkpoint-control-input')['initial_state']['nonwarehouse']['value']
assert read('checkpoint-control-result')['initial_state']['nonwarehouse']['value']==state
assert state['semantic_context']['judgment_context']['value']['phase']=='after_closure'
assert result['status']=='inconclusive' and result['trace'] is None
third=dict(command=cmd,exit_code=proc.returncode,seed_phase='after_closure',seed_time=state['environment']['time'],
 independent_seed_validation='成功且完整StateSeed不变',trace=result['trace'],has_start_state=False,has_end_time=False,
 status=result['status'],reason=result['open_items'])
report=dict(branch_scope=first,unknown_trigger=second,empty_prefix=third)
(OUT/'confirmed-findings.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
