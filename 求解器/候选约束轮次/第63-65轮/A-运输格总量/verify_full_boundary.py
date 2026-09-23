#!/usr/bin/env python3
"""Independent assignment-only HiGHS formulation; no CP-SAT model imported."""
from pathlib import Path
from time import perf_counter
import json
import numpy as np
from scipy.sparse import coo_array
from scipy.optimize import milp,Bounds,LinearConstraint

HERE=Path(__file__).resolve().parent

def sources_for(gl,gb):
    def ports(g):
        cells=[j for j in range(70) if j!=g]
        groups=[cells[k:k+3] for k in range(0,len(cells),3)]
        assert len(groups)==23 and all(c-a==2 for a,b,c in groups)
        return [b for a,b,c in groups]
    return [(1,v) for v in ports(gl)]+[(v,1) for v in ports(gb)]

def solve(gl,gb):
    sources=sources_for(gl,gb)
    forced=set(sources)
    assignments=[]
    cells_rows={}
    for x in range(1,68):
        for y in range(1,68):
            cells=[(a,b) for a in range(x,x+3) for b in range(y,y+3)]
            if forced.intersection(cells):
                continue
            for i,(sx,sy) in enumerate(sources):
                d=min(abs(sx-a)+abs(sy-b) for a,b in cells)
                if d<=8:
                    assignments.append((i,x,y,d-1,cells))
                    for cell in cells:
                        if cell not in cells_rows:
                            cells_rows[cell]=len(sources)+len(cells_rows)
    extra_row=len(sources)+len(cells_rows)
    rr=[];cc=[];vv=[]
    for j,(i,x,y,cost,cells) in enumerate(assignments):
        rr.append(i);cc.append(j);vv.append(1)
        for cell in cells:
            rr.append(cells_rows[cell]);cc.append(j);vv.append(1)
        rr.append(extra_row);cc.append(j);vv.append(cost)
    mat=coo_array((np.array(vv,dtype=float),(np.array(rr,dtype=np.int32),np.array(cc,dtype=np.int32))),
                  shape=(extra_row+1,len(assignments))).tocsc()
    lo=np.zeros(extra_row+1);hi=np.ones(extra_row+1)
    lo[:len(sources)]=1
    hi[-1]=7
    start=perf_counter()
    result=milp(np.zeros(len(assignments)),integrality=np.ones(len(assignments)),
                bounds=Bounds(0,1),constraints=LinearConstraint(mat,lo,hi),
                options={'time_limit':20,'mip_rel_gap':0})
    return dict(gap_left=gl,gap_bottom=gb,status=int(result.status),message=result.message,
                variable_count=len(assignments),constraint_count=extra_row+1,
                seconds=perf_counter()-start)

def check_witness():
    w=json.loads((HERE/'relaxation_witness.json').read_text())
    remaining=set(sources_for(w['gap_left'],w['gap_bottom']))
    forced=set(remaining);occupied=set();excess=0
    assert not w['dummy_sources']
    for a in w['assignment']:
        src=tuple(a['source']);x,y=a['machine']
        assert src in remaining
        remaining.remove(src)
        cells={(xx,yy) for xx in range(x,x+3) for yy in range(y,y+3)}
        assert all(1<=xx<70 and 1<=yy<70 for xx,yy in cells)
        assert not(cells&forced) and not(cells&occupied)
        occupied |= cells
        distance=min(abs(src[0]-xx)+abs(src[1]-yy) for xx,yy in cells)
        assert distance==a['distance']
        excess+=distance-1
    assert not remaining and excess==8
    return dict(assignment_count=len(w['assignment']),occupied_cells=len(occupied),excess=excess,
                scope='distance relaxation only; not a running-layout witness')

def main():
    rows=[]
    # All 47 arrangements checked, including explicit transpositions.
    for gl,gb in [(g,0) for g in range(0,70,3)]+[(0,g) for g in range(3,70,3)]:
        r=solve(gl,gb);rows.append(r)
        print(json.dumps(r,ensure_ascii=False),flush=True)
        (HERE/'verify_full_boundary.json').write_text(json.dumps(dict(cases=rows),ensure_ascii=False,indent=2)+'\n')
    assert len(rows)==47 and all(r['status']==2 for r in rows)
    (HERE/'verify_full_boundary.json').write_text(json.dumps(dict(cases=rows,all_infeasible=True,
                    witness_check=check_witness()),ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    main()
