import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,hashlib
from pack_factory import BASE
from route_factory import Router,choose_power,export
p=BASE/'证据/powered-anneal-11-layout-plants.json';d=json.loads(p.read_text());l=d['layout'];rect=d['reserved_rectangle']
assert not choose_power(l,rect)
r=Router(l,rect,11);r.search(60);out=BASE/'证据/重放候选.json';export(r,out)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
res=dict(source=str(p.relative_to(BASE)),seed=11,iterations=60,candidate_sha256=sha(BASE/'候选布局.json'),replay_sha256=sha(out),byte_identical=out.read_bytes()==(BASE/'候选布局.json').read_bytes())
(BASE/'证据/构造重放结果.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps(res,ensure_ascii=False));assert res['byte_identical']
