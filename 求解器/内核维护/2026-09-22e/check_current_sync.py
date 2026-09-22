#!/usr/bin/env python3
"""本轮正式源/目录/活动引用同步审计；不代替规格全门禁或全厂运行认证。"""
from pathlib import Path
import ast, hashlib,json,re,subprocess,sys
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'数据/工具'))
from formal_catalog import verify
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cat=json.loads((R/'数据/正式静态目录.json').read_text());verify(cat)
assert cat['version']=='2026-09-22-r23-constraints-72'
assert len(cat['constraints'])==72 and len(cat['static_checks']['constants'])==32
assert 'plant_trigger' not in cat['static_checks']['constants']
for p,h in json.loads((O/'只读文件指纹.json').read_text()).items():assert sha(Path(p))==h,p
sections_changed=['矿系不入库','非成品零入库','回路守恒','回路存量','植株半分','1113 位置']
old=json.loads(subprocess.check_output(['git','show','HEAD:求解器/数据/正式静态目录.json'],cwd=R))
old_rules={r['name']:r for r in old['constraints']}
changed=[r['name'] for r in cat['constraints'] if r['name'] not in old_rules or any(r[k]!=old_rules[r['name']][k] for k in ['text','basis'])]
assert set(changed)==set(sections_changed),changed
for key in ['units','recipes','task']:assert cat[key]==old[key],key
rows=[]
for base in [R/'数据/样例',R/'crates/kernel/tests/fixtures']:
 for p in sorted(base.rglob('*.json')):
  if any(x in p.parts for x in ['复核','证据','快照']):continue
  d=json.loads(p.read_text());schema=d.get('schema');refs=[]
  if schema in ['kernel-input-v2','kernel-input-v3']:refs=[d['catalog'],d['parameters']['axis_registry']]
  elif schema=='profile-assignment-v2':refs=[d[k] for k in ['profile_source','configuration_source','axis_source']]
  else:continue
  for ref in refs:assert sha((p.parent/ref['path']).resolve())==ref['sha256'],(p,ref['path'])
  rows.append({'path':str(p.relative_to(R)),'schema':schema,'refs':len(refs)})
assert len(rows)==56
for source in json.loads((R/'数据/候选B/来源清单.json').read_text()):assert sha(Path(source['path']))==source['sha256']
for file in ['数据/规则覆盖表.md','规格/规则覆盖表.md']:
 sections=(R/file).read_text().split('## ')
 for i,source in enumerate(cat['sources'][:2],1):
  table=[line.split('|')[1:-1] for line in sections[i].splitlines() if re.match(r'^\| \d+ \|',line)]
  assert len(table)==len(source['lines'])
  for n,(row,line) in enumerate(zip(table,source['lines']),1):assert int(row[0])==n and row[1].strip()==(line.strip() or '（空行）')
 if file.startswith('数据'):
  table=[l for l in sections[3].splitlines() if '`constraints[' in l]
  assert len(table)==72
  for i,(line,rule) in enumerate(zip(table,cat['constraints'])):assert f'`constraints[{i}]`' in line and f"据行 {rule['basis_line']} 完整转录" in line
 else:
  table=[l.split('|')[1:-1] for l in sections[3].splitlines() if re.match(r'^\| \d+ \|',l)]
  assert len(table)==72
  for i,(row,rule) in enumerate(zip(table,cat['constraints']),1):assert int(row[0])==i and row[1].strip()==rule['source_line'] and row[2].strip()=='约束·'+rule['name']
report=(R/'数据/候选B/校验报告.md').read_text()
assert '能检且不通过（0 项' in report and '目录/阈值/plant_trigger' not in report
for rule in cat['constraints']:assert '正式条目/'+rule['name'] in report and rule['basis'] in report
assert sha(R/'数据/正式静态目录.json') in (R/'规格/修订记录.md').read_text()
for source in cat['sources']:assert source['sha256'] in (R/'规格/运行语义.md').read_text()
# 独立记录总自查的既有阻断，不修改其旧断言以取得通过。
head=lambda p:subprocess.check_output(['git','show','HEAD:求解器/'+p],cwd=R).decode()
choices=head('规格/选择点清单.md')
t12=re.search(r'^## T12\..*?\n(.*?)(?=^## |\Z)',choices,re.M|re.S).group(1)
old_check="check('操作精度' in choice_sections['T12'] and '周期末' in choice_sections['T12'], 'T12包含成品拿取操作精度及周期末限制')"
assert old_check in head('规格/check_revision.py') and not ('操作精度' in t12 and '周期末' in t12)
assert (R/'数据/样例/runtime_example.py').read_text()==head('数据/样例/runtime_example.py')
blockers=[{'entry':'规格/check_revision.py','status':'FAIL','preexisting':True,'reason':'旧 T12 周期末限制断言与 HEAD 文档不符；本轮不扩到规格总门禁重审'},
 {'entry':'数据/样例/check_examples.py --self-test','status':'FAIL','preexisting':True,'reason':'未改动的 runtime_example.validate_decision_tree 将桥轴 status/input_side/basis 误作 Decision status/value/basis'},
 {'entry':'数据/工具/check_revision.py','status':'FAIL','reason':'依赖上述样例检查成功报告；目录、CSV、来源、覆盖检查已执行到该依赖处'}]
result={'status':'PASS','scope':'本轮正式来源、投影、56份活动引用、候选来源与两张覆盖表同步；不是规格全门禁通过',
'catalog_sha256':sha(R/'数据/正式静态目录.json'),'constraints':72,'constants':32,'changed_rules':changed,'reference_documents':rows,'sources_unchanged':True,'global_gate_blockers':blockers}
(O/'current-sync-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='reference_documents'},ensure_ascii=False,indent=2))
