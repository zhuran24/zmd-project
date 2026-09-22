#!/usr/bin/env python3
"""重锁正式源、可运行输入和参数赋值的引用；不改历史输出/证书。"""
from pathlib import Path
import hashlib,json,re,sys
R=Path.cwd();O=R/'内核维护/2026-09-22b'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
p=R/'数据/正式静态目录.json';d=json.loads(p.read_text())
for row in d['sources']:
 source=R.parent/row['path'];row['sha256']=sha(source);row['lines']=source.read_text().splitlines()
d['version']='2026-09-22-r21-switch-wording';save(p,d)
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
save(O/'relock.json',{'sources':hashes,'catalog_sha256':sha(R/'数据/正式静态目录.json'),'inputs':rows,'historical_outputs':'unchanged; not relabeled as current evidence'})
print(json.dumps({'sources':hashes,'catalog_sha256':sha(R/'数据/正式静态目录.json'),'updated_inputs':len(rows)},ensure_ascii=False,indent=2))
