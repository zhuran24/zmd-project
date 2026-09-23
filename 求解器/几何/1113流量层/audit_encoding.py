#!/usr/bin/env python3
"""Independent port-coordinate/pattern arithmetic checks; no solver calls."""
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import flow_model
import check_solution as direct
from filter_positions import PATTERNS,cells,overlaps

def main():
    root=Path(__file__).resolve().parent
    errors=[];patterns=0;port_cases=0;power_cases=0
    for i,p in enumerate(PATTERNS):
        body,ports=direct.pattern(i)
        expected={(tuple(c),2 if j<23 else 3) for j,c in enumerate(p['ports'])}
        if body!=set(map(tuple,p['bodies'])) or set(ports)!=expected or len(body)!=138 or len(ports)!=46:
            errors.append(['pattern',i])
        if len({c for c,d in ports})!=46 or body&{c for c,d in ports}:errors.append(['source_collision',i])
        patterns+=1
    for b in (6,7,9,17):
        R=(49,b,21,53);ts=cells((0,0,70,70))-cells(R)
        for w,h,axes,iscore in [(3,3,(0,1),False),(5,5,(0,1),False),
                               (6,4,(1,),False),(4,6,(0,),False),(9,9,(0,1),True)]:
            for x in range(1,71-w):
                for y in range(1,71-h):
                    rr=(x,y,w,h)
                    if overlaps(rr,R):continue
                    for axis in axes:
                        got=flow_model.ports(rr,axis,ts,iscore)
                        expected=[[e for e in direct.face(rr,axis,side,[1,4,7] if iscore else None)
                                   if e[0] in ts and min(e[0])>=1] for side in (0,1)]
                        if got!=expected:errors.append(['port',rr,axis,iscore])
                        port_cases+=1
    for w,h in [(3,3),(5,5),(6,4),(4,6)]:
        for x,y in [(1,1),(10,10),(70-w,70-h)]:
            body=direct.footprint((x,y,w,h))
            for px in range(1,69):
                for py in range(1,69):
                    # Independent direct intersection, no prefix/image formula.
                    actual=any(px-5<=cx<px+7 and py-5<=cy<py+7 for cx,cy in body)
                    formula=max(1,x-6)<=px<=min(68,x+w+4) and max(1,y-6)<=py<=min(68,y+h+4)
                    if actual!=formula:errors.append(['power',(x,y,w,h),(px,py)])
                    power_cases+=1
    total_in=sum(Fraction(a,20) for a,b in flow_model.TOTAL_LO.values())
    total_out=sum(Fraction(b,20) for a,b in flow_model.TOTAL_LO.values())
    assert total_in==Fraction(6090,20) and total_out==Fraction(5073,20)
    assert total_in+Fraction(23,20)==total_out+52==Fraction(6113,20)
    counts=flow_model.TYPES
    assert sum(sum(v.values()) for v in counts.values())==217
    area=sum(counts['small'].values())*9+sum(counts['medium'].values())*25+sum(counts['large'].values())*24
    assert area==3291
    out=dict(ok=not errors,errors=errors,warehouse_patterns=patterns,port_cases=port_cases,
             power_overlap_cases=power_cases,machine_count=217,machine_area=area,
             all_machine_input=str(total_in),all_machine_output=str(total_out),all_transport_source=str(total_out+52),
             transport_upper_by_P={str(P):4900-1113-3291-81-138-4*P for P in (10,11,12)},
             source_hashes={n:hashlib.sha256((root/n).read_bytes()).hexdigest()
                            for n in ('flow_model.py','check_solution.py','filter_positions.py','geometry.py')})
    (root/'encoding_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps(out,ensure_ascii=False,indent=2));assert not errors

if __name__=='__main__':main()
