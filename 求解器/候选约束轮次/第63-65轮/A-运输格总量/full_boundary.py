#!/usr/bin/env python3
"""Certify total excess >=8 with all 46 boundary sources, all 47 gaps."""
from pathlib import Path
import runpy,json
HERE=Path(__file__).resolve().parent
solve=runpy.run_path(str(HERE/'corner_bound.py'))['solve']

def main():
    rows=[]
    for gl,gb in [(g,0) for g in range(0,70,3)]+[(0,g) for g in range(3,70,3)]:
        r=solve(gl,gb,n=23,cutoff=9,budget=7)
        rows.append(r)
        print(json.dumps(r,ensure_ascii=False),flush=True)
        (HERE/'full_boundary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    assert all(r['status']=='INFEASIBLE' for r in rows)
    # Cost-8 placement is a witness only for this relaxed distance model.
    witness=solve(3,0,n=23,cutoff=10,budget=8)
    assert witness['status'] in ('OPTIMAL','FEASIBLE') and witness['assignment_excess']==8
    (HERE/'relaxation_witness.json').write_text(json.dumps(witness,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    main()
