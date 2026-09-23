#!/usr/bin/env python3
"""顺序复核本轮快照：保留原CLI的版本拒绝，再做明示范围的组件与独立LP诊断。"""
import os,sys,json,subprocess,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE.parents[2]
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
candidate=HERE/'候选只读快照.json'
raw=(HERE/'候选-待交付.json').read_bytes();candidate.write_bytes(raw)
hashes={k:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for k,n in {'rules':'《明日方舟：终末地》游戏规则.txt','task':'求解任务.txt','constraints':'求解约束.txt'}.items()}
assert json.loads(raw)['source_fingerprints']==hashes
jobs=[
 ('A当前入口',[BASE/'检查器A/check_full.py',candidate,'--out',HERE/'A当前入口.json']),
 ('B当前入口',[BASE/'检查器B/check.py',candidate,'--output',HERE/'B当前入口.json']),
 ('A组件复核',[HERE/'组件复核.py','A',candidate]),
 ('B组件复核',[HERE/'组件复核.py','B',candidate]),
 ('独立LP',[HERE/'独立LP.py']),
 ('独立证书回放',[HERE/'独立证书回放.py'])]
results=[]
for name,args in jobs:
 command=[sys.executable,'-B',*map(str,args)]
 with (HERE/(name+'.log')).open('wb') as log:
  proc=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,cwd=ROOT)
 results.append({'name':name,'command':command,'returncode':proc.returncode})
 print(name,proc.returncode,flush=True)
 (HERE/'执行状态.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
 assert name in ['A当前入口','B当前入口'] or proc.returncode==0,(name,proc.returncode)
assert [x['returncode'] for x in results[:2]]==[1,2]
a=json.loads((HERE/'A组件复核.json').read_text());b=json.loads((HERE/'B组件复核.json').read_text());ind=json.loads((HERE/'独立LP.json').read_text())
norm=lambda ee:{(tuple(x),tuple(y)) for x,y in ee}
edges=norm(a['edges']);assert edges==norm(b['edges'])
from_dict=lambda p:(p['unit'],p['side'],p['offset'])
assert edges=={(from_dict(e['from']),from_dict(e['to'])) for e in ind['geometry']['physical_channels_rebuilt']}
assert ind['geometry']['connected_sources']==52
assert len(ind['geometry']['power'])==219 and all(ind['geometry']['power'].values())
assert not any(x['status']=='violation' for x in a['checks']),[x for x in a['checks'] if x['status']=='violation']
assert not any(x['status']=='FAIL' for x in b['checks']),[x for x in b['checks'] if x['status']=='FAIL']
out={'candidate_sha256':hashlib.sha256(raw).hexdigest(),'pass':False,'original_cli_statuses':{k:json.loads((HERE/(k+'当前入口.json')).read_text())['status'] for k in ['A','B']},'structure_three_way_equal':True,'channels':len(edges),'connected_mineral_sources':52,'powered_manufacturers':219,'independent_lp_status':ind['strict']['status'],'certification_note':'原A/B入口不支持当前正式指纹；组件诊断不得替代原入口或全部72条认证。独立LP仍按实际固定图判定。'}
(HERE/'复验汇总.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False))
