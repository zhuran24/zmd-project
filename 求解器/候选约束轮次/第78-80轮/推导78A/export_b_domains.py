"""Archive encoding B's independently generated domains for standard-library audit."""
from single_pole_b import enumerate_objects,OUT
import json,hashlib
out={}
for wall in (False,True):
    objects=enumerate_objects(wall)
    out[str(wall)]=[{**z,'body':sorted(z['body'])} for z in objects]
out['source_sha256']=hashlib.sha256((OUT/'single_pole_b.py').read_bytes()).hexdigest()
(OUT/'domains_b.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
