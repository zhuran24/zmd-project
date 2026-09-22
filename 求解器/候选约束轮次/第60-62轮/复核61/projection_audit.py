#!/usr/bin/env python3
"""Adversarial check of DP candidate completeness using independent 2-D bodies.
No CP-SAT solve is performed here. Does not read any other review's files.
"""
from collections import Counter
import importlib.util
import json
from pathlib import Path
import time
from independent_boundary import enumerate_bodies,targets,cells,loss

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
SOURCE=ROOT/'求解器/几何/1113放松'
spec=importlib.util.spec_from_file_location('original_dp',SOURCE/'filter_positions.py')
f=importlib.util.module_from_spec(spec); spec.loader.exec_module(f)

def write(name,data): (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def main():
    counts=Counter(); starttime=time.monotonic()
    for a in range(4,50):
        for b in range(4,18):
            R=(a,b,21,53); bd,X,Y,corner=enumerate_bodies(R)
            sides=[s for s in 'WESN' if s!='E' or a+21<70 if s!='N' or b+53<70]
            tables={}
            for side in sides: tables[side,False,False]=f._options(R,side,False,False)[0]
            for side in 'EN':
                tables[side,True,False]=f._options(R,side,True,False)[0]
                if not f.overlaps((68,68,2,2),R): tables[side,True,True]=f._options(R,side,True,True)[0]
            for d in bd:
                x,y,w,h=d['rect']; kind=d['kind']; cc=d['cells']
                if kind=='core' and x<=3 and y<=3: continue
                tag0='C' if kind=='core' else 'P' if kind=='pole' else 'M'
                ring_sides=0
                for (side,outer,cp),opts in tables.items():
                    horizontal=side in 'SN'
                    low,high=(1,70) if outer else ((a,a+21) if horizontal else (b,b+53))
                    line=69 if outer else {'W':a-1,'E':a+21,'S':b-1,'N':b+53}[side]
                    pts={(u,line) if horizontal else (line,u) for u in range(low,high)}
                    if not cc&pts: continue
                    if not outer: ring_sides+=1
                    if outer and cp and f.overlaps(d['rect'],(68,68,2,2)) and tuple(d['rect'])!=(68,68,2,2): continue
                    if outer and not cp and tuple(d['rect'])==(68,68,2,2): continue
                    u=x if horizontal else y; length=w if horizontal else h
                    lo,hi=max(low,u),min(high,u+length)
                    tag=tag0 if lo==u and hi==u+length else 'Z'
                    nc,np,ll=int(kind=='core'),int(kind=='pole'),d['loss']
                    if outer and cp and tuple(d['rect'])==(68,68,2,2): nc=np=ll=0
                    expected=(hi-low,tag,nc,np,ll)
                    assert expected in opts[lo-low],(R,d['rect'],d['axis'],side,outer,cp,expected)
                    counts['projected_body_occurrences']+=1
                assert ring_sides<=1,(R,d['rect'],ring_sides)
                counts['independent_bodies']+=1
            # The corner can pay X twice and Y once; the three directions differ.
            if corner and (69,69) in Y:
                rc=cells(R)
                inward=[(dx,dy) for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)] if (69+dx,69+dy) in rc]
                assert len(inward)==1 and inward[0] not in [(1,0),(0,1)]
                counts['corner_triple_direction_cases']+=1
            counts['rectangles']+=1
        if a%5==4: print(a,dict(counts),round(time.monotonic()-starttime,2),flush=True)
    # Exact geometric candidate transpose, including costs and port requirements.
    for b in [5,6,7,8,9,10,11,12,13,14,17]:
        one=enumerate_bodies((49,b,21,53))[0]
        two=enumerate_bodies((b,49,53,21))[0]
        def sig(d,transpose=False):
            x,y,w,h=d['rect']; ax=d['axis']
            if transpose: x,y,w,h=y,x,h,w; ax=None if ax is None else 1-ax
            requirements=[]
            for k,cs in d['need']:
                requirements.append((k,tuple(sorted((v,u) if transpose else (u,v) for u,v in cs))))
            return (d['kind'],x,y,w,h,ax,d['loss'],d['edge'],d['xc'],d['yc'],tuple(sorted(requirements)))
        assert {sig(d,True) for d in one}=={sig(d) for d in two}
        counts['transpose_position_pairs']+=1
    write('projection_checks.json',dict(counts=counts,seconds=time.monotonic()-starttime,all_passed=True))
    print('PASS',dict(counts),flush=True)

if __name__=='__main__': main()
