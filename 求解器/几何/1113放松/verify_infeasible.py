#!/usr/bin/env python3
"""Replay boundary UNSAT with original parameters; also remove all DP cuts."""
import copy,json,time,hashlib
from ortools.sat.python import cp_model
from filter_positions import ROOT
from boundary_joint import build
def solve(model,tag,seconds):
    dest=ROOT/'models';dest.mkdir(exist_ok=True)
    path=dest/(tag+'.pb');model.export_to_file(str(path))
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=2
    solver.parameters.max_time_in_seconds=seconds;solver.parameters.random_seed=20260922
    solver.parameters.log_search_progress=True;solver.parameters.log_to_stdout=False
    with (ROOT/'logs'/(tag+'.log')).open('w') as f:
        solver.log_callback=lambda msg:f.write(msg+'\n')
        status=solver.solve(model)
    return dict(status=solver.status_name(status),seconds=solver.wall_time,workers=2,
                model_path=str(path),model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),response_stats=solver.response_stats())
def main():
    pos={x['id']:x for x in json.loads((ROOT/'positions.json').read_text())['candidates']}
    for path in sorted((ROOT/'results').glob('*_boundary.json')):
        data=json.loads(path.read_text())
        if data['status']!='INFEASIBLE':continue
        tag=data['id'];dest=ROOT/'results'/(tag+'_proofcheck.json')
        if dest.exists():continue
        strong,_=build(pos[tag]);again=solve(strong,tag+'_replay_parallel',60)
        assert again['status']=='INFEASIBLE',again
        weakpos=copy.deepcopy(pos[tag]);weakpos['allowed_P']=[10,11,12];weakpos['branches']=[]
        weak,_=build(weakpos);independent=solve(weak,tag+'_no_DP_cuts',60)
        out=dict(id=tag,status='PASS',replay=again,all_P_without_DP_cuts=independent)
        dest.write_text(json.dumps(out,ensure_ascii=False,indent=2))
        print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
