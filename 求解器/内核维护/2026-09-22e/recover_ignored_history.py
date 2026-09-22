#!/usr/bin/env python3
"""对旧忽略文件仅在重建字节与测试前 SHA 完全一致时恢复。"""
from pathlib import Path
import hashlib,json,subprocess
O=Path(__file__).resolve().parent;R=O.parents[2]
a=json.loads((O/'before-tests-history.json').read_text());b=json.loads((O/'after-tests-history.json').read_text())
tracked=set(subprocess.check_output(['git','ls-files','-z'],cwd=R).decode().split('\0'))
changed=[p for p,h in a['files'].items() if h!=b['files'].get(p) and p not in tracked]
mapping={'bfbee742587e8e9a08c8231483bef578ee4494450447d0d783466cc28b29dd7a':'6e609fbab15104489f7e00a03c64b3f89cd77668de26789622d78be27a0ee3ff'}
sha=lambda raw:hashlib.sha256(raw).hexdigest()
for p in subprocess.check_output(['git','diff','--name-only','-z'],cwd=R).decode().split('\0'):
 if not p:continue
 try: mapping[sha((R/p).read_bytes())]=sha(subprocess.check_output(['git','show','HEAD:'+p],cwd=R))
 except (OSError,subprocess.CalledProcessError):pass

def visit(d):
 if isinstance(d,dict):
  if isinstance(d.get('path'),str) and isinstance(d.get('sha256'),str):
   p=Path(d['path'])
   if not p.is_absolute():return
   try: rel=str(p.relative_to(R))
   except ValueError:return
   old=a['files'].get(rel)
   if old and old!=d['sha256']:mapping[d['sha256']]=old
  for v in d.values():visit(v)
 elif isinstance(d,list):
  for v in d:visit(v)
for p in changed:visit(json.loads((R/p).read_text()))
# 同轮未被写动的完整记录保存了此前正式约束（早于当前 HEAD）的指纹。
historical=json.loads((R/'求解器/crates/kernel/evidence/round6/cli/referenced.record.json').read_text())
for ref in historical['fingerprints']:
 p=Path(ref['path'])
 if p.exists():
  current=sha(p.read_bytes())
  if current!=ref['sha256']:mapping[current]=ref['sha256']
rows=[]
for p in changed:
 raw=(R/p).read_bytes();new=raw
 for src,dst in mapping.items():new=new.replace(src.encode(),dst.encode())
 match=sha(new)==a['files'][p]
 row={'path':p,'expected_sha256':a['files'][p],'test_sha256':sha(raw),'reconstructed_sha256':sha(new),'exact_match':match}
 if match:
  backup=O/'ignored-test-outputs'/Path(p).name;backup.parent.mkdir(exist_ok=True);backup.write_bytes(raw)
  (R/p).write_bytes(new)
 rows.append(row)
(O/'ignored-history-recovery.json').write_text(json.dumps({'mapping':mapping,'files':rows},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(rows,ensure_ascii=False,indent=2))
assert all(r['exact_match'] for r in rows)
