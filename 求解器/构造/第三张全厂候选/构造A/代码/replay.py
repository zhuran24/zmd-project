#!/usr/bin/env python3
"""Cheap deterministic replay of the delivered evidence; no long search or kernel."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
import sys,json,subprocess,hashlib,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];start=time.monotonic();checks=[]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for row in json.loads((BASE/'证据/输入指纹.json').read_text()):
    q=BASE/row['copy'];assert sha(q)==row['sha256'],str(q)
checks.append(dict(check='frozen_input_hashes',pass_=True))
jobs=[('arithmetic_check.py',[],0),('check_components.py',[],0),('static_check.py',[str(BASE/'未通过候选.json')],1),('connectivity_certificate.py',[str(BASE/'未通过候选.json')],0),('legacy_components.py',['A',str(BASE/'未通过候选.json')],0),('legacy_components.py',['B',str(BASE/'未通过候选.json')],0)]
for name,args,expected in jobs:
    r=subprocess.run([sys.executable,'-B',str(BASE/'代码'/name),*args],capture_output=True,text=True)
    (BASE/'证据'/('replay-'+name+'.log')).write_text(r.stdout+r.stderr)
    checks.append(dict(program=name,returncode=r.returncode,expected=expected,pass_=r.returncode==expected))
own=json.loads((BASE/'证据/静态检查结果.json').read_text());a=json.loads((BASE/'检查器A/组件复查结果.json').read_text());b=json.loads((BASE/'检查器B/组件复查结果.json').read_text())
for field,key in [('occupied_cells','occupied_cells'),('physical_channels','channels'),('routes','paths')]:
    assert own['statistics'][field]==a['geometry'][key]==b['geometry'][key],field
assert own['maximum_empty_rectangle']['area']==a['geometry']['maximum']['area']==b['geometry']['maximum']['area']
assert not own['static_pass'] and a['flow']['status']=='violation' and b['flow']['status']=='INFEASIBLE_EXACT'
checks.append(dict(check='three_geometry_counts_and_two_flow_rejections',pass_=True))
out=dict(all_expected_results=all(c['pass_'] for c in checks),static_pass=False,runtime_certified=False,checks=checks,seconds=time.monotonic()-start)
(BASE/'证据/复跑结果.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False));raise SystemExit(0 if out['all_expected_results'] else 1)
