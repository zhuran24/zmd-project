#!/usr/bin/env python3
"""Re-evaluate the original exact integer boundary DP for the four positions.

This is a same-source replay, not a new independent geometry proof. The
projection argument and prior independent checks are in the frozen reports.
No CP-SAT instance is started here.
"""
from pathlib import Path
import hashlib,json,time
from filter_positions import line_table,combine,overlaps

root=Path(__file__).resolve().parent
source=root/'inputs/positions.json';positions=json.loads(source.read_text())
begin=time.monotonic();records=[]
for position in positions:
    r=tuple(position['rect']);a,b,w,h=r
    inner=[line_table(r,s,False,False) for s in 'WESN'
           if {'W':a>0,'E':a+w<70,'S':b>0,'N':b+h<70}[s]]
    outer0=[line_table(r,s,True,False) for s in 'EN']
    outer1=[line_table(r,s,True,True) for s in 'EN'] if not overlaps((68,68,2,2),r) else None
    branches=[]
    for P in (10,11,12):
        budget=23*P-217;J=budget//9;X=combine(outer0,P,budget)
        if budget>=15 and outer1:X=min(X,combine(outer1,P-1,budget-15))
        Y=combine(inner,P,budget);allowed=187-16*P+2*J
        branches.append(dict(P=P,X_lower=X,Y_lower=Y,allowed=allowed,keep=X+Y<=allowed))
    assert branches==position['branches'],(position,branches)
    allowed_P=[v['P'] for v in branches if v['keep']]
    assert allowed_P==position['allowed_P']
    records.append(dict(rect=r,allowed_P=allowed_P,branches=branches))
out=dict(ok=True,method='same-source exact integer DP replay; no solver called',
         seconds=time.monotonic()-begin,positions_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
         filter_sha256=hashlib.sha256((root/'filter_positions.py').read_bytes()).hexdigest(),positions=records)
(root/'original_domain_recheck.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
