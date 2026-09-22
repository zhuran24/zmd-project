"""第三轮测试复核：只读被审来源，所有输出集中在复核目录。"""
from pathlib import Path
import sys,json,subprocess,time,hashlib,platform,statistics
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'crates/kernel/tests'))
sys.path.insert(0,str(ROOT/'数据/样例'))
def save(name,value):
 (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def run(command):
 start=time.perf_counter_ns();p=subprocess.run([str(c) for c in command],capture_output=True,text=True)
 return {'command':[str(c) for c in command],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'wall_ns':time.perf_counter_ns()-start}
mode=sys.argv[1]
if mode=='audit':
 import verify_outputs as v
 reports=[]
 for name in ['混做粉碎机两下游','分流器三路轮询']:
  data=v.checker.load_json(ROOT/f'数据/样例/{name}.json');expected=v.run(data)
  for suffix in ['运行记录-v3-kernel','运行记录-checkpoint_delta-v3-kernel']:
   reports.append(v.verify(ROOT/f'数据/样例/{name}-{suffix}.json',data,expected))
 baseline=v.checker.load_json(ROOT/'crates/kernel/evidence/round5/protected-baseline.json')
 assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in baseline.items())
 save('verify-outputs.json',{'status':'pass','records':reports,'protected_files':len(baseline)})
 import audit_round5 as a, audit_dense_round5 as d
 a.E=OUT;d.E=OUT
 save('invalid-cycle-result.json',json.loads((OUT/'cli-r5/invalid-cycle-result.json').read_text()))
 a.main()
elif mode=='benchmark':
 reports=[];binary=ROOT/'target/release/kernel'
 for name in ['benchmark_brick_60','benchmark_brick','benchmark_candidate_b']:
  source=ROOT/f'crates/kernel/tests/fixtures/{name}.json';data=json.loads(source.read_text());runs=[]
  for repeat in range(5):
   row=run([binary,'run',source,'--config',ROOT/'规格/内核配置-v1.json','--ticks','12','--no-output'])
   assert row['exit_code']==0,row
   parsed=json.loads(row['stdout']);assert parsed['status']=='completed' and parsed['ticks']==12 and parsed['statistics']=={'completed':1,'inconclusive':0,'stopped':0}
   row['engine']=parsed;row['ms_per_tick']=int(parsed['elapsed_ns'])/1e6/12;del row['stdout'];runs.append(row)
  reports.append({'name':name,'units':len(data['layout']['units']),'physical_channels':len(data['layout']['physical_channels']),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'runs':runs,'median_ms_per_tick':statistics.median(r['ms_per_tick'] for r in runs)})
  print(name,reports[-1]['median_ms_per_tick'],flush=True)
 save('benchmark-recheck.json',{'platform':platform.platform(),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'reports':reports,'scope':'沿用原12刻、无输出推进口径，5次独立进程；wall_ns另列，不含于ms/tick。'})
elif mode=='cycle':
 results=[]
 for name,budget in [('生产循环环带',50),('密集制造闭环序3核验',1000)]:
  path=OUT/f'{name}-重跑周期.json'
  r=run([ROOT/'target/release/kernel','cycle',ROOT/f'数据/样例/{name}.json','--config',ROOT/'规格/内核配置-v1.json','--max-ticks',budget,'--out',path]);assert r['exit_code']==0,r
  result=json.loads(path.read_text());r['status']=result['status'];r['period']=result['cycle']['period'];results.append(r)
  v=run([ROOT/'target/release/kernel','verify-cycle',path,'--config',ROOT/'规格/内核配置-v1.json']);assert v['exit_code']==0,v;results.append(v)
  print(name,result['status'],result['cycle']['period'],flush=True)
 save('cycle-recheck.json',results)
