"""只读复用逐账验收函数，独立比对所有现行记录、周期键和重跑结果。"""
from pathlib import Path
import sys,json,subprocess,hashlib
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器'); OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'crates/kernel/tests'))
import audit_round5 as audit
report=audit.read(ROOT/'crates/kernel/evidence/round5/audit-results.json')
results={'records':[],'cycles':[],'key_checks':[],'artifact_summaries':[]}
for row in report['records']:
 try:results['records'].append(dict(status='pass',**audit.audit_record(Path(row['path']))))
 except Exception as e:results['records'].append(dict(status='fail',path=row['path'],error=str(e)))
for row in report['cycles']:
 p=Path(row['path']);data=audit.read(p); c=data['cycle']
 try:
  audit.validate_schema(data,audit.SCHEMA,audit.SCHEMA)
  if c:
   for side in ['start','end']:
    expected=audit.reference_key(c[side+'_state']);actual=c[side+'_key'];assert expected==actual,(p,side)
    results['key_checks'].append(dict(path=str(p),side=side,match=True))
   audit.audit_ledger(data['run_record'],data['replay_input'])
  cmd=[str(audit.BIN),'verify-cycle',str(p),'--config',str(audit.CFG)]
  proc=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
  assert proc.returncode==0,(proc.stdout,proc.stderr)
  results['cycles'].append(dict(path=str(p),status='pass',result=data['status'],verification=json.loads(proc.stdout)))
 except Exception as e:results['cycles'].append(dict(path=str(p),status='fail',error=str(e)))
# 原始交付清单及日志只读；保存概要与当前指纹，不拷贝其内容。
paths=[ROOT/'crates/kernel/evidence/benchmark.json']
paths+=list((ROOT/'crates/kernel/evidence/revision-r3').glob('*.json'))
paths+=list((ROOT/'crates/kernel/evidence/revision-r3').glob('*.log'))
paths+=[ROOT/'crates/kernel/evidence/revision-r3/cli/results.json',ROOT/'crates/kernel/evidence/round5/bridge-first-contact-audit.json']
paths+=list((ROOT/'规格/第五轮规格修订-r8').glob('*.json'))+list((ROOT/'规格/第五轮规格修订-r8').glob('*.log'))
for p in paths:
 raw=p.read_bytes();row=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 if p.suffix=='.json':
  data=json.loads(raw);row['shape']={k:(len(v) if isinstance(v,(dict,list)) else v) for k,v in data.items()} if isinstance(data,dict) else {'rows':len(data)}
 else:
  text=raw.decode();row['tail']=text.splitlines()[-4:];row['has_failure_marker']='FAILED' in text
 results['artifact_summaries'].append(row)
(OUT/'current-audit.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:[{x:r[x] for x in ('path','status','error') if x in r} for r in v] for k,v in results.items() if k in ('records','cycles')},ensure_ascii=False))
