#!/usr/bin/env python3
"""只调用原A/B的结构和流组件，不替代其带指纹的正式CLI认证。
原检查器不支持新正式指纹时，CLI结果另存；本输出始终static_certified=false。
"""
import os,sys,json,hashlib
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
name=sys.argv[1];p=Path(sys.argv[2]);raw=p.read_bytes();d=json.loads(raw)
sys.path.insert(0,str(BASE/('检查器'+name)))
out={'scope':'原检查器的结构/受限类/流组件诊断；没有绕过或改写正式CLI结果，不认证完整72条，不认证当前正式版本。','static_certified':False,'candidate_sha256':hashlib.sha256(raw).hexdigest(),'source_fingerprints':d['source_fingerprints']}
if name=='A':
 from check_full import Report,implementation_hash
 from schema import validate
 from geometry import Geometry
 from design import check_design
 from projections import geometry_checks
 from flow import Flow
 validate(d);r=Report();g=Geometry(d,r).build();geometry_checks(g,r);check_design(g,r)
 out['implementation_sha256']=implementation_hash()
 out['checks']=list(r.checks.values())
 out['edges']=[[p,q] for p,q in g.channels]
 out['occupied']=len(g.occ);out['rectangle']=g.maximum;out['power']=g.power
 fatal=['bounds','overlap','machine_shape','unit_shape','N4a','N4b','N5a','source_binding','logical_path']
 if not any(r.checks.get(k,{}).get('status')=='violation' for k in fatal):
  f=Flow(g).build();out['flow'],_=f.run(60)
else:
 from check import code_fingerprint
 from geometry import Geometry,Checks,structural,check_rectangle
 from interfaces import check_interfaces
 from flow import build
 c=Checks();g=Geometry(d['layout'],c)
 if g.valid:structural(d,g,c);check_rectangle(d,g,c);check_interfaces(d,g,c)
 out['implementation_sha256']=code_fingerprint();out['checks']=c.records
 out['edges']=[[p,q] for p,q in g.edges]
 out['occupied']=len(g.occ);out['rectangle']=g.rectangle;out['power']=g.powered
 if g.valid and c.good('N5a','port-references','N4a','N4b','logical-feeds'):
  lp=build(d,g);out['flow'],_=lp.solve(60)
dest=HERE/(sys.argv[3] if len(sys.argv)>3 else name+'组件复核.json')
dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'checker':name,'candidate_sha256':out['candidate_sha256'],'static_certified':False,'edges':len(out['edges']),'flow_status':out.get('flow',{}).get('status'),'violations':[r for r in out['checks'] if r['status'] in ['FAIL','violation']]},ensure_ascii=False)[:7000])
