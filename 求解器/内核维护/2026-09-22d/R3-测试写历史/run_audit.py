#!/usr/bin/env python3
"""Run only this audit's read-only scripts and save exact command outputs."""
import json,os,subprocess,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
commands=[];log=[]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CARGO_TARGET_DIR=str(ROOT/'target'),CARGO_BUILD_JOBS='6',RUST_TEST_THREADS='6')
for name in ('audit_git.py','inventory.py','writer_catalog.py','default_path_probe.py','compare_baseline.py','assemble_report.py'):
    argv=[sys.executable,'-B',str(OUT/name)]
    p=subprocess.run(argv,cwd=ROOT,env=env,capture_output=True,text=True)
    commands.append(dict(argv=argv,cwd=str(ROOT),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
    log.append('$ '+' '.join(argv)+'\n'+p.stdout+p.stderr+'\nexit_code='+str(p.returncode)+'\n')
    if p.returncode:break
(OUT/'commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n')
(OUT/'commands.log').write_text('\n'.join(log))
for c in commands:print(Path(c['argv'][-1]).name,c['exit_code'])
assert all(c['exit_code']==0 for c in commands)
