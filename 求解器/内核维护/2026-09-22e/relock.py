#!/usr/bin/env python3
"""重锁正式源、可运行输入和参数赋值的引用；不改历史输出/证书。"""
from pathlib import Path
import hashlib,json,re,sys
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
p=R/'数据/正式静态目录.json';d=json.loads(p.read_text())
from importlib import import_module
sys.path.insert(0,str(R/'数据/工具'))
import_module('formal_catalog').verify(d)
assert d['version']=='2026-09-22-r23-constraints-72'
hashes={r['path']:r['sha256'] for r in d['sources']}
c=R/'数据/样例/check_examples.py';s=c.read_text();s=re.sub(r'SOURCE_HASHES = \{.*?\n\}', 'SOURCE_HASHES = '+json.dumps(hashes,ensure_ascii=False,indent=4),s,flags=re.S);c.write_text(s)
rows=[]
for base in [R/'数据/样例',R/'crates/kernel/tests/fixtures']:
 for p in sorted(base.rglob('*.json')):
  if any(x in p.parts for x in ['复核','证据','快照']):continue
  d=json.loads(p.read_text());schema=d.get('schema',''); refs=[]
  if schema in ['kernel-input-v2','kernel-input-v3']:
   refs=[d['catalog'],d['parameters']['axis_registry']]
  elif schema=='profile-assignment-v2':
   refs=[d[k] for k in ['profile_source','configuration_source','axis_source']]
  changes=[]
  for ref in refs:
   source=(p.parent/ref['path']).resolve();new=sha(source)
   if ref['sha256']!=new:changes.append({'path':ref['path'],'before':ref['sha256'],'after':new});ref['sha256']=new
  if changes:save(p,d);rows.append({'file':str(p.relative_to(R)),'refs':changes})
# 候选 B 正式源/候选约束/目录引用更新；历史外部来源不能静默重指。
p=R/'数据/候选B/来源清单.json'; records=json.loads(p.read_text()); source_changes=[]
current_paths={str(R.parent/name) for name in [*hashes,'候选约束.txt']}|{str(R/'数据/正式静态目录.json')}
for ref in records:
 if ref['path'] in current_paths:
  new=sha(Path(ref['path']))
  if ref['sha256']!=new:source_changes.append({'path':ref['path'],'before':ref['sha256'],'after':new});ref['sha256']=new
save(p,records)
previous=json.loads((O/'relock-initial.json').read_text()) if (O/'relock-initial.json').exists() else {}
merged={row['file']:{ref['path']:dict(ref) for ref in row['refs']} for row in previous.get('inputs',[])}
for row in rows:
 refs=merged.setdefault(row['file'],{})
 for ref in row['refs']:
  if ref['path'] in refs:refs[ref['path']]['after']=ref['after']
  else:refs[ref['path']]=ref
all_rows=[{'file':file,'refs':list(refs.values())} for file,refs in sorted(merged.items())]
save(O/'relock.json',{'sources':hashes,'catalog_sha256':sha(R/'数据/正式静态目录.json'),'inputs':all_rows,'candidate_b_sources':previous.get('candidate_b_sources',[])+source_changes,'relocated_byte_identical_sources':previous.get('relocated_byte_identical_sources',[]),'historical_outputs':'retained at their original bytes; test restoration separately recorded'})

print(json.dumps({'sources':hashes,'catalog_sha256':sha(R/'数据/正式静态目录.json'),'updated_inputs':len(rows)},ensure_ascii=False,indent=2))
