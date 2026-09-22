#!/usr/bin/env python3
"""校验已知输入哈希后恢复早期CLI测试覆盖的旧输出；不以推测内容冒充原件。"""
from pathlib import Path
import hashlib,json,re
R=Path.cwd();O=R/'内核维护/2026-09-22';m=json.loads((O/'before.json').read_text())['files'];out=[]
def h(b):return hashlib.sha256(b).hexdigest()
for name in ['relocated-seed.json','resource-statistics.json','invalid-cycle-result.json']:
 p=R/'crates/kernel/evidence/round5'/name;key=str(p.relative_to(R));want=m[key]['sha256'];current=p.read_bytes()
 if h(current)==want:continue
 (O/('early-test-'+name)).write_bytes(current);found=None;origin=None
 for q,v in m.items():
  if q!=key and v['sha256']==want and h((R/q).read_bytes())==want:found=(R/q).read_bytes();origin=q;break
 if found is None and name=='resource-statistics.json':
  # 唯一运行计时字段的字节长度由原清单约束，SHA-256确认恢复而非猜值。
  head,tail=re.split(rb'"elapsed_ns": "\d+"',current);base=head+b'"elapsed_ns": "';tail=b'"'+tail
  for newline in [b'',b'\n']:
   digits=m[key]['bytes']-len(base)-len(tail.rstrip(b'\n'))-len(newline)
   if not 1<=digits<=7:continue
   for n in range(10**(digits-1),10**digits):
    candidate=base+str(n).encode()+tail.rstrip(b'\n')+newline
    if h(candidate)==want:found=candidate;origin='exact SHA-256 recovery of elapsed_ns serialization';break
   if found:break
 if found is None and name=='invalid-cycle-result.json':
  # 在已有JSON中寻找相同语义对象的不同序列化，仍要求完整原哈希一致。
  for q,v in m.items():
   if not q.endswith('.json') or not 1000<=v['bytes']<=30000:continue
   try:d=json.loads((R/q).read_text())
   except Exception:continue
   if not isinstance(d,dict) or d.get('status')!='invalid_input' or not str(d.get('schema','')).startswith('kernel-cycle'):continue
   for sort in [False,True]:
    for ind in [2,4,None]:
     for ascii in [False,True]:
      for nl in ['', '\n']:
       b=(json.dumps(d,ensure_ascii=ascii,sort_keys=sort,indent=ind)+nl).encode()
       if h(b)==want:found=b;origin=q;break
   if found:break
 if found is not None:assert h(found)==want;p.write_bytes(found)
 out.append({'path':key,'restored':found is not None,'expected_sha256':want,'source':origin})
(O/'early-test-output-restoration.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(out)
