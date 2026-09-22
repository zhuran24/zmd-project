# 工程席复现：不再生成/改写原fixture，直接运行已交付输入。
import json, subprocess, hashlib, platform, time, os
from pathlib import Path
R=Path('/home/zhuran24/zmd-research-fresh/求解器');O=R/'crates/kernel/复核/r3-工程证据';B=R/'target/release/kernel';C=R/'规格/内核配置-v1.json'
report={'binary_sha256':hashlib.sha256(B.read_bytes()).hexdigest(),'platform':platform.platform(),'loadavg':os.getloadavg(),'samples':[]}
for name in ['benchmark_brick_60','benchmark_brick','benchmark_candidate_b']:
 p=R/'crates/kernel/tests/fixtures'/(name+'.json')
 for cached in [True,False]:
  for repeat in range(3):
   cmd=[str(B),'run',str(p),'--config',str(C),'--ticks','12','--no-output']+([] if cached else ['--no-cache'])
   start=time.perf_counter_ns();r=subprocess.run(cmd,capture_output=True,text=True);wall=time.perf_counter_ns()-start
   try:v=json.loads(r.stdout)
   except Exception:v=None
   row={'name':name,'cached':cached,'repeat':repeat,'command':cmd,'exit_code':r.returncode,'result':v,'stderr':r.stderr,'wall_ns':wall,'input_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
   if v and v.get('elapsed_ns'):row['ms_per_tick']=int(v['elapsed_ns'])/12000000
   report['samples'].append(row);print(name,cached,repeat,row.get('ms_per_tick'),flush=True)
(O/'性能复现.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
