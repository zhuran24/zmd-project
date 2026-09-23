#!/usr/bin/env python3
"""Serial, resource-bounded experiments; never runs two CP-SAT jobs together."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
MODEL_SCRIPT='flow_model.py'


def invoke(y,layer,stage,seconds,cut='formal',seed=20260922):
    tag=f'y{y}_{layer}_{stage}'; result=ROOT/'results'/f'{tag}.json'
    if result.exists(): return json.loads(result.read_text())
    cmd=['nice','-n','10',sys.executable,'-B',str(ROOT/MODEL_SCRIPT),
         '--y',str(y),'--layer',layer,'--stage',stage,'--seconds',str(seconds),
         '--workers','8','--cut-mode',cut,'--seed',str(seed)]
    state=dict(state='running',tag=tag,utc=datetime.now(timezone.utc).isoformat(),command=cmd)
    (ROOT/'campaign_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))
    print(json.dumps(state,ensure_ascii=False),flush=True)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    with (ROOT/'logs'/f'{tag}.console.log').open('w') as log:
        r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=env)
    if r.returncode: raise RuntimeError(f'{tag} failed {r.returncode}; see console log')
    d=json.loads(result.read_text())
    print(json.dumps({k:d[k] for k in ('tag','status','solve_seconds','build_seconds')},ensure_ascii=False),flush=True)
    if 'solution' in d:
        subprocess.run([sys.executable,'-B',str(ROOT/'check_solution.py'),str(result)],check=True,env=env)
    return d


def main():
    global MODEL_SCRIPT
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['ore_long','all_long','all_retry','compact_short','compact_long'],required=True)
    ap.add_argument('--seconds',type=float);ap.add_argument('--ys',default='6,9,7,17')
    ap.add_argument('--script',choices=['flow_model.py','flow_model_global.py','flow_model_compact.py','flow_model_min_edges.py','flow_model_min_edges_domain.py'],default='flow_model.py')
    ap.add_argument('--deadline-utc',help='ISO UTC deadline; reserve time for a possible weakened-model recheck')
    args=ap.parse_args()
    MODEL_SCRIPT=args.script
    deadline=datetime.fromisoformat(args.deadline_utc.replace('Z','+00:00')).timestamp() if args.deadline_utc else None
    layer,seconds,seed={'ore_long':('ore',600,20260922),'all_long':('all',1800,20260922),
                        'all_retry':('all',600,20260923),'compact_short':('ore',60,20260922),
                        'compact_long':('ore',300,20260923)}[args.phase]
    seconds=args.seconds or seconds
    ys=list(map(int,args.ys.split(',')))
    for index,y in enumerate(ys):
        earlier=[json.loads(p.read_text()) for p in (ROOT/'results').glob(f'y{y}_*.json')
                 if not p.name.endswith(('.assignment.json','.check.json'))]
        if any(d.get('status')=='INFEASIBLE' for d in earlier):
            continue
        if any(d.get('status') in ('FEASIBLE','OPTIMAL') and d.get('layer')==layer for d in earlier):
            continue
        limit=seconds
        if deadline:
            left=deadline-time.time()
            if left<60:break
            reserve=min(900,left*0.4)
            limit=min(seconds,max(30,(left-reserve-30)/(len(ys)-index)))
        d=invoke(y,layer,args.phase,limit,seed=seed)
        if d['status']=='INFEASIBLE':
            proof_limit=min(seconds,900)
            if deadline:proof_limit=min(proof_limit,max(30,deadline-time.time()-30))
            invoke(y,layer,args.phase+'_nocuts',proof_limit,cut='none',seed=20260923)
    (ROOT/'campaign_state.json').write_text(json.dumps(dict(state='phase_finished',phase=args.phase,
        utc=datetime.now(timezone.utc).isoformat()),ensure_ascii=False,indent=2))


if __name__=='__main__': main()
