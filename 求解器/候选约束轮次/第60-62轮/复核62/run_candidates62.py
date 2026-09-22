#!/usr/bin/env python3
import json,time
from mip62 import mip_solve
from boundary62 import BASE

def run(name,R,**kw):
    path=BASE/(name+'.json')
    if path.exists():
        result=json.loads(path.read_text())
        if result.get('status')==0: return result
    result=mip_solve(R,seconds=600,**kw)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({'name':name,**{k:v for k,v in result.items() if k!='chosen'}},ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':
    entries=[]
    for transpose in (False,True):
        for b in list(range(5,15))+[17]:
            R=(b,49,53,21) if transpose else (49,b,21,53)
            entries.append(run(f'mip_{R[0]}_{R[1]}',R))
    (BASE/'candidate_summary.json').write_text(json.dumps([{k:v for k,v in r.items() if k!='chosen'} for r in entries],ensure_ascii=False,indent=2))
    for p in (None,10,11,12):
        run(f'weak_49_13_P{p}',(49,13,21,53),edge0=True,fixed_p=p)
    for p in (10,11,12):
        run(f'strict_49_13_P{p}',(49,13,21,53),fixed_p=p)
