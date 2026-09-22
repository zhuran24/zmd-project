#!/usr/bin/env python3
"""将活动样例按现有任务7配置重新分组；只更新输入，旧输出通过重新运行处理。"""
from pathlib import Path
import json
R=Path.cwd();O=R/'内核维护/2026-09-22';c=json.loads((R/'规格/内核配置-v1.json').read_text())['axes']
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def group(k):
 life=c[k]['lifetime']
 return 'fixed' if life.startswith('F') or k=='judgment.order' else 'offline_mutable' if life=='O' else 'fixedness_unproven'
reports=[]
for base in [R/'数据/样例',R/'crates/kernel/tests/fixtures']:
 for p in sorted(base.rglob('*.json')):
  d=json.loads(p.read_text()); old=json.dumps(d,ensure_ascii=False);changes=[]
  if d.get('schema') in ['kernel-input-v2','kernel-input-v3']:
   params=d['parameters']; allaxes={k:v for g in ['fixed','offline_mutable','fixedness_unproven'] for k,v in params[g].items()}
   for g in ['fixed','offline_mutable','fixedness_unproven']:params[g]={}
   for k,v in allaxes.items():
    row=c[k]
    if row['disposition'] in {'已定','超出覆盖即停'} and v.get('value')!=row['value']:
     changes.append({'axis':k,'before':v.get('value'),'after':row['value']});v={'status':'specified','value':row['value'],'basis':[row['basis']]}
    params[group(k)][k]=v
   state=d['initial_state']['nonwarehouse'].get('value')
   if isinstance(state,dict):
    for row in state['semantic_context']['parameter_values']:
     k=row['axis']; row['lifetime']={'fixed':'F','offline_mutable':'O','fixedness_unproven':'U'}[group(k)]; row['value']=params[group(k)][k]
  elif d.get('schema')=='profile-assignment-v2':
   for row in d['axes']:
    k=row['axis'];cfg=c[k]
    if cfg['disposition'] in {'已定','超出覆盖即停'}:row['decision']={'status':'specified','value':cfg['value'],'basis':[cfg['basis']]}
    # 镜像字段遵循既有配置，不改变该样例的自由赋值。
    for field in ['disposition','coverage_loss','extension_gate','meaning','lifetime']:
     if field in row:row[field]=cfg[field]
  if json.dumps(d,ensure_ascii=False)!=old:save(p,d);reports.append({'file':str(p.relative_to(R)),'value_changes':changes,'groups':'current registry'})
save(O/'input-migration.json',reports);print('migrated',len(reports))
# 现有检查器已定值和目录投影必须识别已经落地的任务7登记。
p=R/'数据/样例/check_examples.py';s=p.read_text();start=s.index('KNOWN_VALUES = {');end=s.index('\n\n\ndef axis_registry',start)
known={k:v['value'] for k,v in c.items() if v['disposition']=='已定'}
s=s[:start]+'KNOWN_VALUES = '+repr(known)+s[end:];p.write_text(s)
p=R/'数据/工具/formal_units.py';s=p.read_text();a=s.index("        transfer={'cooldown_ticks'");b=s.index("\n    body = clauses['仓库取货口']",a)
u=next(x for x in json.loads((R/'数据/正式静态目录.json').read_text())['units'] if x['id']=='协议储存箱')
# 同步现有目录字段，保持当前内核箱行为；cooldown仍从正式原句抽取。
x=repr(u['transfer']).replace("{'value': '5', 'category': '条文直引'}",'quantity(cooldown)')
s=s[:a]+'        transfer='+x+')'+s[b:];p.write_text(s)
