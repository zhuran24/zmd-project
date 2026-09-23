"""第六轮：真实引用读取、相对基目录、前缀绑定、P刻重跑、KQ-09两阶段。"""
import sys
sys.dont_write_bytecode=True
import copy,hashlib,json,os,subprocess
from pathlib import Path
from evidence_paths import instance_dir
from verify_all import schema_check
ROOT=Path(__file__).resolve().parents[3];E=None
BIN=Path(os.environ.get('KERNEL_BIN',ROOT/'target/release/kernel'));CFG=ROOT/'规格/内核配置-v1.json';BASE=ROOT/'数据/样例'
def read(p):return json.loads(p.read_text())
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');return p
def call(*args,ok=True,cwd=ROOT):
 p=subprocess.run([str(BIN),*map(str,args),'--config',str(CFG)],capture_output=True,text=True,cwd=cwd)
 assert (p.returncode==0)==ok,(args,p.returncode,p.stdout,p.stderr)
 return json.loads(p.stdout) if p.stdout.strip() else None
def main():
 global E
 E=instance_dir('round6_cli')
 cases=[];positives=[]
 for mode in ('referenced','none'):
  cert=E/(mode+'.json');flags=['--no-record'] if mode=='none' else []
  call('cycle',BASE/'生产循环环带.json','--max-ticks',50,'--out',cert,*flags)
  r=read(cert);assert r['record_mode']==mode;assert 'run_record' not in r and 'replay_input' not in r
  verified=call('verify-cycle',cert,cwd=ROOT.parent);assert verified['cycle_replayed'] and verified['prefix_replayed']>verified['period']
  positives.append(cert)
  relative=copy.deepcopy(r)
  for ref in ('replay_input_ref','run_record_ref'):
   if relative[ref]:
    relative[ref]['path']=os.path.relpath(relative[ref]['path'],E)
    relative[ref]['producer']['path']=os.path.relpath(relative[ref]['producer']['path'],E)
  for row in relative['fingerprints']:row['path']=os.path.relpath(row['path'],E)
  relative['cycle']['normalization']['definition']['path']=os.path.relpath(relative['cycle']['normalization']['definition']['path'],E)
  p=save(E/(mode+'-relative.json'),relative);call('verify-cycle',p,cwd=ROOT.parent);positives.append(p)
  cases.append(dict(name=mode+'-relative-cwd',status='pass',verification=verified))
  mutations=[('missing_input',lambda d:d['replay_input_ref'].update(path='missing.json')),
  ('input_hash',lambda d:d['replay_input_ref'].update(sha256='0'*64)),
  ('input_format',lambda d:d['replay_input_ref'].update(format='kernel-output-v3')),
  ('input_producer',lambda d:d['replay_input_ref']['producer'].update(kind='input_generator')),
  ('producer_claim',lambda d:d['replay_input_ref']['producer'].update(claim='冒名')),
  ('seed_reachability',lambda d:d['seed'].update(reachability=None)),
  ('parameter_point',lambda d:d['parameter_point']['input_axes'].clear()),
  ('reading',lambda d:d['reading'].update(port_meeting='closed_segment_touch')),
  ('missing_domain',lambda d:d['domain_report'].pop()),
  ('static_as_cycle',lambda d:d['domain_report'][1].update(scope='static')),
  ('rate',lambda d:d['cycle']['rates'][0].update(comparison='gt')),
  ('ledger',lambda d:d['cycle']['ledger'].pop()),
  ('acceptance',lambda d:d['cycle']['acceptance'][0]['products'][0].update(selected_acceptance=False)),
  ('start_key',lambda d:d['cycle'].update(start_key=None)),
  ('unreachable_start',lambda d:d['cycle']['start_state']['environment']['time']['value'].update(value='-500')),
  ('prefix_erasure',lambda d:d['budget'].update(completed_ticks=0)),
  ('full_base',lambda d:d.update(level='full_base'))]
  if mode=='referenced':mutations += [('missing_record',lambda d:d['run_record_ref'].update(path='missing.json')),('record_format',lambda d:d['run_record_ref'].update(format='kernel-output-v3/checkpoint_delta')),('record_producer',lambda d:d['run_record_ref']['producer'].update(kind='bounded_reference_checker'))]
  for name,change in mutations:
   bad=copy.deepcopy(r);change(bad);call('verify-cycle',save(E/'tamper.json',bad),ok=False);cases.append(dict(name=mode+'-'+name,status='rejected'))
  if mode=='referenced':
   record=read(Path(r['run_record_ref']['path']));record['trace']['ticks'][0]['events'].append(copy.deepcopy(record['trace']['ticks'][0]['events'][0]))
   changed=save(E/'tampered-record.json',record);bad=copy.deepcopy(r);bad['run_record_ref']['path']=str(changed);bad['run_record_ref']['sha256']=hashlib.sha256(changed.read_bytes()).hexdigest()
   call('verify-cycle',save(E/'tamper.json',bad),ok=False);changed.unlink();cases.append(dict(name='resealed-record-duplicate-event',status='rejected'))
  # 引用文件改字节，不改证书摘要。
  original=Path(r['replay_input_ref']['path']);mutated=E/'mutated-input.json';mutated.write_bytes(original.read_bytes()+b' ')
  bad=copy.deepcopy(r);bad['replay_input_ref']['path']=str(mutated);call('verify-cycle',save(E/'tamper.json',bad),ok=False);cases.append(dict(name=mode+'-changed_bytes',status='rejected'))
  # 已装载首刻失败须保留可恢复种子和引用。
  p=E/(mode+'-zero-prefix.json');call('cycle',BASE/'生产循环环带.json','--max-ticks',2,'--max-sweeps',1,'--out',p,*flags)
  zero=read(p);assert zero['budget']['completed_ticks']==0 and zero['seed'] and zero['last_state'] and zero['replay_input_ref'];call('verify-cycle',p);positives.append(p)
  if mode=='referenced':
   record=read(Path(zero['run_record_ref']['path']));assert record['trace']['ticks']==[] and record['trace']['end_time']==record['trace']['start_state']['environment']['time']
  cases.append(dict(name=mode+'-loaded-zero-prefix',status='pass'))
 # 检查点导出后第一个新时刻为t+1；固定参数、既有游标保持。
 checkpoint=E/'checkpoint-input.json';call('checkpoint',E/'none.json','--out',checkpoint)
 cp=read(checkpoint);state=read(E/'none.json')['cycle']['end_state'];assert cp['initial_state']['nonwarehouse']['value']==state
 continued=E/'continued.json';call('cycle',checkpoint,'--no-record','--max-ticks',25,'--out',continued);call('verify-cycle',continued);positives.append(continued)
 assert read(continued)['cycle']['start_state']==state
 # 未装载整数溢出维持resource，结构合法，但不能给独立核验通过。
 raw=read(BASE/'生产循环环带.json')
 for ref in (raw['catalog'],raw['parameters']['axis_registry']):ref['path']=str((BASE/ref['path']).resolve())
 next(r for r in raw['initial_state']['nonwarehouse']['value']['inventory'] if r['contents'])['contents'][0]['entered_at']['value']['value']=str(-(2**63))
 source=save(E/'overflow-input.json',raw);shell=E/'overflow.json';call('cycle',source,'--max-ticks',2,'--out',shell,ok=False)
 d=read(shell);assert d['status']=='inconclusive' and d['stop']['kind']=='resource' and d['replay_input_ref'] is None and d['last_state'] is None
 diagnostic=call('verify-cycle',shell);assert diagnostic['diagnostic_replayed'] and not diagnostic['cycle_replayed'];positives.append(shell);cases.append(dict(name='KQ-09-load-resource',status='diagnostic_replayed_no_cycle'))
 forged=copy.deepcopy(d)
 for row in forged['fingerprints']:
  if row['role']=='input':row.update(path=str(BASE/'生产循环环带.json'),sha256=hashlib.sha256((BASE/'生产循环环带.json').read_bytes()).hexdigest())
 call('verify-cycle',save(E/'tamper.json',forged),ok=False);cases.append(dict(name='loaded-input-forged-as-load-shell',status='rejected'))
 # 无轨迹静态入口。
 static=call('check',BASE/'生产循环环带.json','--cycle-domain');assert static['trajectory_executed'] is False and all(r['scope']=='static' for r in static['domain_report']);save(E/'domain-static.json',static)
 schema_check(positives)
 (E/'tamper.json').unlink();(E/'mutated-input.json').unlink()
 report=dict(status='pass',cases=cases,positive_schema_documents=len(positives),schema_sha256=hashlib.sha256((ROOT/'规格/内核输出.schema.json').read_bytes()).hexdigest())
 save(E/'results.json',report);print(json.dumps(dict(status='pass',cases=len(cases),positive_schema_documents=len(positives)),ensure_ascii=False))

if __name__=='__main__':main()
