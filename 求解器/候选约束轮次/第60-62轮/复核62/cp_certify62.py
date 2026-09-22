#!/usr/bin/env python3
"""Try exact-integer CP-SAT lower bounds independently of HiGHS LP arithmetic."""
import json
from boundary62 import BASE,solve

if __name__=='__main__':
    entries=json.loads((BASE/'candidate_summary.json').read_text())
    result=[]
    for r in entries:
        a,b,W,H=r['R'];name=f'cp_below_min_{a}_{b}'
        path=BASE/(name+'.json')
        if path.exists():
            c=json.loads(path.read_text())
        else:
            c=solve(tuple(r['R']),seconds=90,workers=1,cap=r['objective']-1,log_path=BASE/(name+'.log'))
            path.write_text(json.dumps(c,ensure_ascii=False,indent=2))
        result.append({k:v for k,v in c.items() if k not in ('chosen','model_stats','response_stats')})
        print(json.dumps(result[-1],ensure_ascii=False),flush=True)
    (BASE/'cp_certification_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
