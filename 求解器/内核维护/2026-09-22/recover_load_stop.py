#!/usr/bin/env python3
"""以已记录SHA256确认旧诊断封套的无损恢复；不接受近似匹配。"""
from pathlib import Path
import hashlib,json,copy,itertools
R=Path.cwd();O=R/'内核维护/2026-09-22';m=json.loads((O/'before.json').read_text())['files'];dest=R/'crates/kernel/evidence/round5/invalid-cycle-result.json';want=m[str(dest.relative_to(R))]['sha256'];current=json.loads(dest.read_text())
for p,meta in m.items():
 if not p.endswith('.json') or not 8000<meta['bytes']<15000:continue
 try:base=json.loads((R/p).read_text())
 except:continue
 if not isinstance(base,dict) or base.get('schema')!='kernel-cycle-v2' or base.get('status')!='invalid_input':continue
 for use_current in [True,False]:
  d=copy.deepcopy(current if use_current else base)
  d.pop('evidence_scope',None);d.pop('environment_assumption',None);d['schema']='kernel-cycle-v2'
  d['fingerprints']=copy.deepcopy(base['fingerprints'])
  for row in d['fingerprints']:
   if row['role']=='input':row.update(path=str(dest.with_name('invalid-cycle-input.json')),sha256=m[str(dest.with_name('invalid-cycle-input.json').relative_to(R))]['sha256'])
  for key in ['budget','domain_report','stop','open_items','reading','port_meeting']:
   d[key]=copy.deepcopy(current[key])
  for sort,nl,ascii in itertools.product([False,True],['','\n'],[False,True]):
   b=(json.dumps(d,ensure_ascii=ascii,sort_keys=sort,indent=2)+nl).encode()
   if hashlib.sha256(b).hexdigest()==want:
    dest.write_bytes(b);print('RESTORED',p,len(b));q=O/'early-test-output-restoration.json';a=json.loads(q.read_text());a[-1].update(restored=True,source='hash-verified original v2 envelope recovered from '+p);q.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n');raise SystemExit
print('no exact match; original bytes not claimed restored')
# v2装载失败的依赖闭包不含后加的周期键审计，且域名为production_v1。
for p,meta in m.items():
 if not p.endswith('.json') or not 8000<meta['bytes']<15000:continue
 try:base=json.loads((R/p).read_text())
 except:continue
 if not isinstance(base,dict) or base.get('schema')!='kernel-cycle-v2':continue
 d=copy.deepcopy(current);d.pop('evidence_scope',None);d.pop('environment_assumption',None);d['schema']='kernel-cycle-v2';d['support_domain']['name']='production_v1'
 oldrefs={(x['role'],x['path']):x['sha256'] for x in base.get('fingerprints',[])}
 d['fingerprints']=[x for x in d['fingerprints'] if not x['path'].endswith('周期键读取审计.md')]
 for x in d['fingerprints']:
  key=(x['role'],x['path'])
  if x['role']=='input':x['sha256']=m[str(Path(x['path']).relative_to(R))]['sha256']
  elif key in oldrefs:x['sha256']=oldrefs[key]
 for sort,nl,ascii in itertools.product([False,True],['','\n'],[False,True]):
  b=(json.dumps(d,ensure_ascii=ascii,sort_keys=sort,indent=2)+nl).encode()
  if hashlib.sha256(b).hexdigest()==want:
   dest.write_bytes(b);print('RESTORED',p,len(b));q=O/'early-test-output-restoration.json';a=json.loads(q.read_text());a[-1].update(restored=True,source='hash-verified v2 load-stop reconstructed from historical dependency manifest '+p);q.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n');raise SystemExit
print('v2 manifest candidates exhausted')
