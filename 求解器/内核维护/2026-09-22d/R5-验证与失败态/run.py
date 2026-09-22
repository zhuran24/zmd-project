#!/usr/bin/env python3
"""Build in shared target, run a standalone read-only probe and the audited reference target."""
import json, os, subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
TARGET=ROOT/'target'
env=dict(os.environ,CARGO_TARGET_DIR=str(TARGET),CARGO_BUILD_JOBS='2',CARGO_PROFILE_DEV_CODEGEN_UNITS='1',RUST_TEST_THREADS='1',RAYON_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
commands=[]
LOG=OUT/('attempt-'+str(1+len(list(OUT.glob('attempt-*')))))
LOG.mkdir()
def run(name,args):
    p=subprocess.run(args,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    (LOG/(name+'.stdout.log')).write_text(p.stdout)
    (LOG/(name+'.stderr.log')).write_text(p.stderr)
    commands.append({'name':name,'argv':args,'cwd':str(ROOT),'exit_code':p.returncode})
    (LOG/'commands.json').write_text(json.dumps({'environment':{k:env[k] for k in ['CARGO_TARGET_DIR','CARGO_BUILD_JOBS','CARGO_PROFILE_DEV_CODEGEN_UNITS','RUST_TEST_THREADS','RAYON_NUM_THREADS','OMP_NUM_THREADS','PYTHONDONTWRITEBYTECODE']},'commands':commands},ensure_ascii=False,indent=2)+'\n')
    print(name, 'exit_code=',p.returncode,flush=True)
    if p.returncode: print(p.stderr,p.stdout); raise SystemExit(p.returncode)
    return p.stdout
run('rustc-version',['rustc','-Vv'])
raw=run('build',['cargo','build','--locked','--offline','-p','kernel','--lib','-j','2','--message-format=json'])
artifacts={}
for line in raw.splitlines():
    row=json.loads(line)
    if row.get('reason')=='compiler-artifact':
        for file in row['filenames']:
            if file.endswith('.rlib'): artifacts[row['target']['name']]=file
binary=TARGET/'r5-validation-failure-probe'
run('rustc-probe',['rustc','--edition=2021','-C','codegen-units=1',str(OUT/'probe.rs'),'-L','dependency='+str(TARGET/'debug/deps'),'--extern','kernel='+artifacts['kernel'],'--extern','serde_json='+artifacts['serde_json'],'-o',str(binary)])
run('probe',[str(binary),str(ROOT),str(OUT)])
run('reference',['cargo','test','--locked','--offline','-p','kernel','--test','reference','-j','2','--','--test-threads=1'])
run('kernel-lib-list',['cargo','test','--locked','--offline','-p','kernel','--lib','-j','2','--','--list'])
run('topology-lib-list',['cargo','test','--locked','--offline','-p','topology','--lib','-j','2','--','--list'])
