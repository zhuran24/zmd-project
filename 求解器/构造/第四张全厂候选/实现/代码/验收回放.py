#!/usr/bin/env python3
"""复跑当前布局的静态核验，不启动布局搜索。缺路候选的检查失败不会被改写成通过。"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,{6})
import sys,json,subprocess,hashlib
from pathlib import Path
B=Path(__file__).resolve().parents[1];layout=B/'布局.json';evidence=B/'证据';evidence.mkdir(exist_ok=True)
jobs=[('自写静态检查',[sys.executable,'-B',str(B/'代码/static_check.py'),str(layout),'--out',str(evidence/'静态检查结果.json')],{}),
      ('逐路与端口',[sys.executable,'-B',str(B/'代码/逐路与端口核查.py'),str(layout)],{}),
      ('独立主',[sys.executable,'-B',str(B/'独立复核/check_main.py')],dict(CAND_PATH=str(layout),OUT_PATH=str(B/'独立复核/结果-主.json'))),
      ('独立副',[sys.executable,'-B',str(B/'独立复核/check_alt.py')],dict(CAND_PATH=str(layout),OUT_PATH=str(B/'独立复核/结果-副.json'))),
      ('旧A几何',[sys.executable,'-B',str(B/'代码/旧检查器复查.py'),'A',str(layout)],{}),
      ('旧B几何',[sys.executable,'-B',str(B/'代码/旧检查器复查.py'),'B',str(layout)],{}),
      ('拒绝性核验',[sys.executable,'-B',str(B/'代码/核查拒绝性.py'),str(layout)],{})]
rows=[]
for name,args,extra in jobs:
    with (evidence/(name+'.log')).open('w') as log:
        p=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,**extra})
    rows.append(dict(name=name,exit_code=p.returncode));print(name,p.returncode,flush=True)
own=json.loads((evidence/'静态检查结果.json').read_text());a=json.loads((B/'独立复核/结果-主.json').read_text());z=json.loads((B/'独立复核/结果-副.json').read_text());la=json.loads((evidence/'旧A复查.json').read_text());lb=json.loads((evidence/'旧B复查.json').read_text())
counts=dict(occupied=[own['statistics']['occupied_cells'],a['counts']['occupied_cells'],z['occupied'],la['occupied_cells'],lb['occupied_cells']],channels=[own['statistics']['physical_channels'],a['channels_rebuilt'],z['channels'],la['channels'],lb['channels']],routes=[own['statistics']['routes'],a['routes_complete'],z['routes']],powered=[230-len(own['checks']['power']['failures']),230-len(a['unpowered_machines']),230-len(z['unpowered']),la['powered_machines'],lb['powered_machines']])
agree=all(len(set(v))==1 for v in counts.values())
result=dict(candidate_sha256=hashlib.sha256(layout.read_bytes()).hexdigest(),static_pass=own['static_pass'],numeric_agreement=agree,counts=counts,jobs=rows,scope='旧A/B仅复查几何模块；动态运行不在本回放范围。')
(evidence/'复核汇总.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
raise SystemExit(0 if agree and all(q['exit_code']==0 for q in rows if q['name']!='自写静态检查') else 2)
