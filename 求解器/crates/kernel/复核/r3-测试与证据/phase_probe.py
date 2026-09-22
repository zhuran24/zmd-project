"""检查点transfer.phase须保留初始参数，但仍须验证该参数的表示和值域。"""
import json,copy,subprocess
from pathlib import Path
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');OUT=Path(__file__).resolve().parent;CFG=ROOT/'规格/内核配置-v1.json';BIN=ROOT/'target/release/kernel'
raw=json.loads((OUT/'seed-control-input.json').read_text());reports=[]
for name,value in [('valid_0',{'kind':'rational','value':{'category':'候选','value':'0'}}),('negative',{'kind':'rational','value':{'category':'候选','value':'-1'}}),('too_large',{'kind':'rational','value':{'category':'候选','value':'6'}}),('fractional',{'kind':'rational','value':{'category':'候选','value':'1/2'}}),('malformed','not-a-Time')]:
 d=copy.deepcopy(raw)
 d['parameters']['fixedness_unproven']['transfer.phase']['value']['values'][0]['remaining']=value
 for r in d['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']:
  if r['axis']=='transfer.phase':r['value']=copy.deepcopy(d['parameters']['fixedness_unproven']['transfer.phase'])
 src=OUT/f'phase-{name}-input.json';dest=OUT/f'phase-{name}-record.json';src.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 command=[str(BIN),'run',str(src),'--config',str(CFG),'--ticks','2','--out',str(dest)];p=subprocess.run(command,text=True,capture_output=True)
 result=json.loads(dest.read_text());reports.append({'case':name,'value':value,'command':command,'exit_code':p.returncode,'status':result['status'],'record':str(dest),'diagnostics':result['open_items']})
 print(name,p.returncode,result['status'])
(OUT/'phase-probe-results.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n')
# 原样完整周期起点作为有效检查点，仅将历史相位参数改成非法字符串。
source=ROOT/'数据/样例/生产循环环带.json';d=json.loads(source.read_text());certificate=json.loads((ROOT/'数据/样例/生产循环环带-周期证书-kernel.json').read_text());d['initial_state']['nonwarehouse']['value']=certificate['cycle']['start_state']
for ref in [d['catalog'],d['parameters']['axis_registry']]:ref['path']=str((source.parent/ref['path']).resolve())
d['parameters']['fixedness_unproven']['transfer.phase']['value']['values'][0]['remaining']='not-a-Time'
for r in d['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']:
 if r['axis']=='transfer.phase':r['value']=copy.deepcopy(d['parameters']['fixedness_unproven']['transfer.phase'])
src=OUT/'phase-malformed-cycle-input.json';dest=OUT/'phase-malformed-cycle-result.json';src.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
command=[str(BIN),'cycle',str(src),'--config',str(CFG),'--max-ticks','25','--out',str(dest)];p=subprocess.run(command,text=True,capture_output=True);result=json.loads(dest.read_text())
verification=subprocess.run([str(BIN),'verify-cycle',str(dest),'--config',str(CFG)],text=True,capture_output=True)
(OUT/'phase-malformed-cycle-check.json').write_text(json.dumps({'command':command,'exit_code':p.returncode,'status':result['status'],'period':result['cycle']['period']if result['cycle']else None,'input_axis':result['parameter_point']['input_axes']['transfer.phase']if result['parameter_point']else None,'verify_exit_code':verification.returncode,'verify_stdout':verification.stdout,'verify_stderr':verification.stderr},ensure_ascii=False,indent=2)+'\n')
print('malformed phase cycle',p.returncode,result['status'],'verify',verification.returncode)
