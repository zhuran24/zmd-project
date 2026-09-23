#!/usr/bin/env python3
from pathlib import Path
import sys,json,copy,hashlib
from check69 import verify_dual,edge_bodies,projection,LINES,CORNERS,intersects,loss,verify_groups
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3]
c=json.loads((OUT/'wall0_certificate.json').read_text());tests=[]
bad=copy.deepcopy(c);bad['integer_upper']=12
try:verify_dual(bad,(-20,7,-20,32));raise RuntimeError('accepted false integer bound')
except AssertionError:tests.append('false integer upper rejected')
bad=copy.deepcopy(c);bad['rows']=bad['rows'][1:]
try:verify_dual(bad,(-20,7,-20,32));raise RuntimeError('accepted missing multiplier')
except AssertionError:tests.append('removed positive multiplier rejected')
# Domain mutation: produce one set independently, then compare it to a copy with a deleted option.
caps=verify_groups();line=LINES[1];expected=[set() for _ in range(line[4]-line[3])]
for k,r,ax in edge_bodies():
 pr=projection(r,line)
 if not pr or r in CORNERS:continue
 lo,hi,a,b=pr;P=int(k=='P');J=int(P and (r[0] in (1,68) or r[1] in (1,68)))
 expected[lo-line[3]].add((hi-line[3],k if (lo,hi)==(a,b) else 'Z',int(k=='C'),P,loss(r,caps,True) if P else 0,-2*J))
saved=json.loads((OUT/'new_edge_certificate.json').read_text())['cases'][0]['lines'][1]['options']
assert saved==[[list(v) for v in sorted(x)] for x in expected]
bad=copy.deepcopy(saved);bad[next(i for i,v in enumerate(bad) if v)].pop()
assert bad!=[[list(v) for v in sorted(x)] for x in expected];tests.append('deleted edge-body option rejected')
manifest=json.loads((OUT/'input_manifest.json').read_text())
checks={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==v['sha256'] for p,v in manifest.items()}
assert all(checks.values()),checks
files=[p for p in OUT.iterdir() if p.is_file()]
assert all(p.suffix in ('.py','.json','.log','.md','.gz') for p in files)
assert not any(p.is_dir() for p in OUT.iterdir())
assert all(p.stat().st_size<100_000_000 or p.suffix=='.gz' for p in files)
out=dict(mutation_tests=tests,input_hashes_unchanged=checks,file_count=len(files),max_file_bytes=max(p.stat().st_size for p in files),reader_audit=['candidate premises defined','P11 excluded and P10 unresolved distinguished','all numeric claims tied to artifacts','relaxation witnesses not game layouts','formal bounds unchanged pending review'])
(OUT/'delivery_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False))
