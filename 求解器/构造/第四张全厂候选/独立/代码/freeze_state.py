#!/usr/bin/env python3
import json,sys
from pathlib import Path
p=Path(sys.argv[1]);out=Path(sys.argv[2]);d=json.loads(p.read_text());out.with_suffix('.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');out.with_suffix('.pos').write_text(''.join(f'{u["x"]} {u["y"]} {u["d"]}\n' for u in d['units']))
a={p['r']:p for p in d['paths']}
with out.with_suffix('.routes').open('w') as f:
 print(325,file=f)
 for i in range(325):
  p=a.get(i,{'cells':[],'source':[0]*4,'target':[0]*4});print(len(p['cells']),*p['source'],*p['target'],file=f)
  for c in p['cells']:print(*c,file=f)
print(len([p for p in d['paths'] if p['cells']]))
