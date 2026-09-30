"""第六轮：从输入重跑迁移，核验成功才替换旧产物；不修改来源指纹冒充重验。"""
from pathlib import Path
import argparse,json,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'数据/样例';E=ROOT/'crates/kernel/evidence/round6'
BIN=ROOT/'target/release/kernel';CFG=ROOT/'规格/内核配置-v1.json'
def read(p):return json.loads(p.read_text())
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def run(args):
 p=subprocess.run([str(BIN),*map(str,args),'--config',str(CFG)],capture_output=True,text=True)
 assert p.returncode==0,(args,p.stdout,p.stderr)
 return json.loads(p.stdout)
def plan():
 path=E/'migration-plan.json'
 if path.exists():return read(path)
 certificates=[];records=[]
 for p in sorted(BASE.glob('*-周期证书-kernel.json')):
  d=read(p);source=BASE/(p.name.replace('-周期证书-kernel',''))
  certificates.append(dict(path=str(p),input=str(source),budget=d['budget'],old_status=d['status'],old_bytes=p.stat().st_size,old_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
 for p in sorted(BASE.glob('*-运行记录*v3-kernel.json')):
  d=read(p);source=next(r['path'] for r in d['fingerprints'] if r['role']=='input');old_ticks=len(d['trace']['ticks'])
  records.append(dict(path=str(p),input=source,ticks=min(old_ticks,32),old_ticks=old_ticks,format=d['trace']['format'],interval=d['trace'].get('checkpoint_interval',10),old_bytes=p.stat().st_size,old_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
 d=dict(certificates=certificates,records=records);assert len(certificates)==10 and len(records)==26;save(path,d);return d
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--certificates',action='store_true');parser.add_argument('--records',action='store_true');args=parser.parse_args();p=plan();results=[]
 for kind in ['certificates','records']:
  if not getattr(args,kind):continue
  for row in p[kind]:
   dest=Path(row['path']);temp=dest.with_suffix('.round6.json')
   if kind=='certificates':
    run(['cycle',row['input'],'--max-ticks',row['budget']['max_ticks'],'--max-sweeps',row['budget']['max_sweeps'],'--search-checkpoint-interval',32,'--no-record','--out',temp])
    verification=run(['verify-cycle',temp]);new=read(temp);assert new['status']==row['old_status'],(dest,new['status'],row['old_status'])
   else:
    run(['run',row['input'],'--ticks',row['ticks'],'--format',row['format'],'--checkpoint-interval',row['interval'],'--out',temp]);verification=run(['verify-record',temp]);new=read(temp)
   temp.replace(dest)
   results.append(dict(path=str(dest),old_bytes=row['old_bytes'],new_bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),status=new['status'],verification=verification))
   print(kind,dest.name,new['status'],dest.stat().st_size,flush=True)
  save(E/f'migration-{kind}.json',dict(status='pass',results=results));results=[]

 if args.records:
  import sys
  sys.path.insert(0,str(BASE))
  from runtime_record import build_record,validate_record
  from check_golden_trace import run as reference_run
  for name in ('混做粉碎机两下游','分流器三路轮询'):
   raw=read(BASE/(name+'.json'));ticks=reference_run(raw)
   record=build_record(raw,ticks,read(BASE/'混做粉碎机两下游-黄金轨迹.json') if name.startswith('混做') else None)
   validate_record(record,raw,ticks);save(BASE/(name+'-运行记录-v3.json'),record)
