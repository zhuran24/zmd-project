#!/usr/bin/env python3
"""Serial resource-bounded partition campaigns. No model solving."""
import json,os,subprocess,sys,time
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
which=sys.argv[1];jobs=[]
if which=='hypergraph':
    for model in ('flow_all','flow_ore','geometry','residual75'):
        for mode in ('full','noglobal'):
            for k in (2,4,8):jobs.append((model+'_whole','kahypar',mode,k))
elif which=='graph':
    for model in ('flow_all','flow_ore','geometry','residual75'):
        for mode in ('full','noglobal'):
            scopes=['whole'] if model=='residual75' else (['window'] if mode=='full' else ['whole','window'])
            for scope in scopes:
                for k in (2,4,8):jobs.append((model+'_'+scope,'metis',mode,k))
    for model in ('flow_all','flow_ore','geometry','residual75'):
        for scope in (['whole'] if model=='residual75' else ['whole','window']):
            for mode in ('full','noglobal'):jobs.append((model+'_'+scope,'manual',mode,4))
else:raise ValueError(which)
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(OUT/'tmp'),XDG_CACHE_HOME=str(OUT/'cache'))
records=[]
for dataset,algo,mode,k in jobs:
    if which=='hypergraph' and dataset=='flow_all_whole' and mode=='full' and k==2:
        # Started separately as the full-size installation/runtime probe.
        continue
    result=OUT/'raw'/dataset/'partitions'/f'{algo}_{mode}_k{k}.json'
    if result.exists():continue
    cmd=[sys.executable,'-B',str(OUT/'scripts/partition_run.py'),dataset,algo,mode,'--ks',str(k)]
    log=OUT/'logs'/f'{dataset}_{algo}_{mode}_k{k}.log';start=time.monotonic()
    limit=360 if algo=='kahypar' else 180
    with log.open('w') as f:
        try:
            p=subprocess.run(cmd,env=env,cwd=OUT,stdout=f,stderr=subprocess.STDOUT,timeout=limit)
            status='complete' if p.returncode==0 and result.exists() else 'error'
            code=p.returncode
        except subprocess.TimeoutExpired:status='timeout';code=None
    item=dict(dataset=dataset,algorithm=algo,mode=mode,k=k,status=status,returncode=code,seconds=time.monotonic()-start,limit_seconds=limit,log=str(log.relative_to(OUT)))
    records.append(item);print(json.dumps(item),flush=True)
    (OUT/'logs'/f'campaign_{which}.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
