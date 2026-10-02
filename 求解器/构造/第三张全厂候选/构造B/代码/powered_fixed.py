import json
from pack_factory import BASE,C,cells,machine
z=json.loads((BASE/'证据/loose-fixed.json').read_text());l=z['layout']
# Shift the nine interlocked seed-pair modules two cells left to leave a power corridor on the right.
for u in l['machines']:
 if u['model'] in ['采种机','种植机'] and u['x0']>=32:u['x0']-=2;u['x1']-=2
for u in l['machines']:
 if u['id'] in ['QA6','QB6','QC6']:u['x0']-=2;u['x1']-=2
for t in l['transport']:
 if (t['x']>=32 and t['y']>=21) or (18<=t['x']<=29 and t['y']>=59):t['x']-=2;t['id']=f'TR_{t["x"]}_{t["y"]}'
positions=[(9,y) for y in [18,30,42,54,66]]+[(x,9) for x in [24,36,48,61]]+[(x,y) for x in [28,41,54,67] for y in [28,44,60]]+[(19,58),(4,3),(4,12),(18,5),(13,15)]+[(21,y) for y in [24,36,48]]
l['power_poles']=[dict(id=f'POWER{k+1}',x0=x,y0=y,x1=x+1,y1=y+1,orientation=0) for k,(x,y) in enumerate(positions)]
occ={};bad=[]
for u in l['machines']+l['warehouse_outlets']+l['transport']+l['power_poles']+[l['core']]:
 for c in cells(u):
  if c in occ:bad.append((c,occ[c],u['id']))
  occ[c]=u['id']
if bad:raise ValueError(bad)
missing=[]
for u in l['machines']:
 if not any(u['x0']<=p['x0']+6 and u['x1']>=p['x0']-5 and u['y0']<=p['y0']+6 and u['y1']>=p['y0']-5 for p in l['power_poles']):missing.append(u['id'])
print('poles',len(positions),'fixed machines',len(l['machines']),'unpowered',missing)
(BASE/'证据/powered-fixed.json').write_text(json.dumps(z,ensure_ascii=False,indent=2))
