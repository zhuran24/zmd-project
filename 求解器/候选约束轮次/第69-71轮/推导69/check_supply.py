#!/usr/bin/env python3
"""Independent exact check of every local dual and its actual pole mapping."""
from pathlib import Path
import json,time
from check69 import verify_dual,intersects
OUT=Path(__file__).resolve().parent
start=time.monotonic();certs=json.loads((OUT/'supply_strip_certificates.json').read_text());seen=set();results=[]
for c in certs:
 wall,hole=c['geom'];r=verify_dual(c,wall,hole);assert r['columns']==c['n']
 for p,q in c['positions']:
  assert (p,q) not in seen and 43<=p<=68 and 1<=q<=16 and not intersects((p,q,2,2),(49,17,21,53))
  assert wall==[max(-6,6-p),min(18,75-p),max(-6,6-q),min(18,75-q)]
  assert hole==[max(-6,54-p),max(-6,22-q),18,18]
  seen.add((p,q))
 results.append(dict(positions=c['positions'],upper=r['upper'],integer_upper=r['integer_upper']))
expected={(p,q) for p in range(43,69) for q in range(1,17) if not intersects((p,q,2,2),(49,17,21,53))};assert seen==expected
out=dict(classes=len(certs),positions=len(seen),results=results,elapsed=time.monotonic()-start)
(OUT/'supply_verification.json').write_text(json.dumps(out,separators=(',',':')))
print({k:v for k,v in out.items() if k!='results'})
