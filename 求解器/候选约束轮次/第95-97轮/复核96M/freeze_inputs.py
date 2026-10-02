from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
OUT=Path(__file__).resolve().parent;ROUND=OUT.parent;PREVIOUS=ROUND.parent/'第92-94轮'
sources=list((ROUND/'前提快照').glob('*.txt'))+[ROUND/'临时规则.md',ROUND/'推导95M.md']
sources += [PREVIOUS/(name+'.md') for name in ['推导92A','推导92B','推导92C','推导92E','推导92F',
                                             '复核93A','复核94A','复核93B','复核94B','复核94C','复核93F','复核94F']]
sources += [ROUND/'推导95M'/name for name in ['corner_a.json','scope_a.json','core_checks.json','startup_checks.json']]
sources += [PREVIOUS/'复核93F/local_geometry.json']
result=[]
for p in sources:
    raw=p.read_bytes();result.append({'path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),
                                    'bytes':len(raw),'text':raw.decode()})
(OUT/'inputs.json').write_text(json.dumps({'read_utc':datetime.now(timezone.utc).isoformat(),'files':result},ensure_ascii=False,indent=2)+'\n')
print({'frozen_inputs':len(result)})
