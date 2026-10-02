import json,sys
from pathlib import Path
from collections import Counter,deque
from pack_factory import BASE,C,cells,machine
from route_factory import ports
base=json.loads((BASE/'证据/anneal-base-layout.json').read_text())
for name in sys.argv[1:]:
 p=Path(name);z=json.loads(p.read_text());by={u['id']:u for u in z['units']};l={**base['layout'],'machines':[machine(u['id'],by[u['id']]['x'],by[u['id']]['y'],by[u['id']]['Din']) for u in base['layout']['machines']]}
 occ={};overlap=[]
 for u in l['machines']+l['warehouse_outlets']+l['transport']+l['power_poles']+[l['core']]:
  for q in cells(u):
   if q in occ:overlap.append((q,u['id'],occ[q]))
   occ[q]=u['id']
 if overlap:raise ValueError(overlap[:5])
 out=dict(layout=l,reserved_rectangle=base['reserved_rectangle'],anneal=z)
 target=p.with_name(p.stem+'-layout.json');target.write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(target.name,'units',len(l['machines']),'score',z['score'])
