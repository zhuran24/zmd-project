# 第三轮工程席：全量读取交付清单，逐字节指纹与JSON结构核验。
from pathlib import Path
import hashlib, json, os, time
ROOT=Path('/home/zhuran24/zmd-research-fresh')
OUT=ROOT/'求解器/crates/kernel/复核/r3-工程证据'
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
k=ROOT/'求解器/crates/kernel/evidence/round5/交付清单.json'
s=ROOT/'求解器/规格/第五轮规格修订-r8/交付清单.json'
km=json.loads(k.read_text());sm=json.loads(s.read_text())
paths={Path(x['path']) for x in km['files']}|{Path(x) for x in sm['files']}|{k,s}
paths.update((ROOT/'求解器/crates/kernel/src').glob('*.rs'))
paths.update((ROOT/'求解器/crates/kernel/tests').glob('*.rs'))
paths.update((ROOT/'求解器/crates/kernel/tests').glob('*.py'))
paths.update((ROOT/'求解器/数据/样例').glob('*.py'))
paths.update([ROOT/x for x in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt','求解器/Cargo.toml','求解器/Cargo.lock','求解器/crates/kernel/Cargo.toml','求解器/数据/正式静态目录.json','求解器/规格/内核输出.schema.json','求解器/规格/普遍审查场景.md','求解器/规格/第四轮前置-疑问记录.md']])
expected={x['path']:x['sha256'] for x in km['files']}
rows=[];bad=[]
for p in sorted(paths):
 r={'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p)}
 if str(p) in expected and expected[str(p)]!=r['sha256']:bad.append(str(p))
 if p.suffix=='.json':
  with p.open() as f: v=json.load(f)
  r['json_type']=type(v).__name__
  if isinstance(v,dict):
   r['keys']=list(v);r['array_lengths']={k:len(x) for k,x in v.items() if isinstance(x,list)}
   r['status']={k:v[k] for k in ['status','schema','schema_version','result','level','max_ticks','period','production_period'] if k in v and not isinstance(v[k],(dict,list))}
   if 'ticks' in v and isinstance(v['ticks'],list):
    r['tick_count']=len(v['ticks']);r['first_tick']=v['ticks'][0].get('time') if v['ticks'] else None;r['last_tick']=v['ticks'][-1].get('time') if v['ticks'] else None
  del v
 else:
  with p.open() as f: content=f.read()
  r['lines']=len(content.splitlines())
 rows.append(r)
 print(p.name,flush=True)
(OUT/'全量读取与指纹.json').write_text(json.dumps({'files':rows,'kernel_manifest_entries':len(km['files']),'manifest_mismatches':bad},ensure_ascii=False,indent=2)+'\n')
scan=[]
for base in [ROOT/'求解器/crates/kernel/evidence',ROOT/'求解器/crates/kernel/复核']:
 for parent,dirs,files in os.walk(base):
  for n in dirs:
   if n in ['target','.cargo-home','registry','.git']:scan.append({'kind':'forbidden_directory','path':str(Path(parent)/n)})
  for n in files:
   f=Path(parent)/n
   if f.suffix not in ['.py','.rs','.sh','.js','.log','.json','.md']:
    scan.append({'kind':'other_extension','path':str(f),'bytes':f.stat().st_size})
(OUT/'证据目录扫描.json').write_text(json.dumps(scan,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'files':len(rows),'bytes':sum(x['bytes'] for x in rows),'mismatches':bad,'scan_flags':len(scan)},ensure_ascii=False))
