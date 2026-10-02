#!/usr/bin/env python3
"""Second implementation: bit rows, exact route arithmetic and geometry without importing construction/check code."""
import json,sys,hashlib
from pathlib import Path
from fractions import Fraction
from collections import Counter,defaultdict
p=Path(sys.argv[1]);d=json.loads(p.read_text());l=d['layout'];bits=[0]*70;area=Counter();seen=set();overlap=[]
for group in ['machines','warehouse_outlets','core','power_poles','transport']:
 units=[l[group]] if group=='core' else l[group]
 for u in units:
  if group=='transport':xs=[u['x']];ys=[u['y']]
  else:xs=range(u['x0'],u['x1']+1);ys=range(u['y0'],u['y1']+1)
  for yy in ys:
   for xx in xs:
    if (xx,yy) in seen:overlap.append([xx,yy])
    seen.add((xx,yy));bits[yy]|=1<<xx;area[group]+=1
best=(0,0);bounds=None
for left in range(65):
 for right in range(left+5,70):
  mask=((1<<(right-left+1))-1)<<left;begin=0
  for y in range(71):
   if y==70 or bits[y]&mask:
    height=y-begin;width=right-left+1
    if height>=6 and (width*height,min(width,height))>best:best=(width*height,min(width,height));bounds=dict(x0=left,y0=begin,x1=right,y1=y-1)
    begin=y+1
cov={u['id']:[] for u in l['machines']}
for pp in l['power_poles']:
 # Enumerated covered cells, independent of the interval-overlap formula.
 covered={(x,y) for x in range(max(0,pp['x0']-5),min(70,pp['x0']+7)) for y in range(max(0,pp['y0']-5),min(70,pp['y0']+7))}
 for u in l['machines']:
  if any((x,y) in covered for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)):cov[u['id']].append(pp['id'])
bridges={(t['x'],t['y']):t['id'] for t in l['transport'] if t['type']=='bridge'};adj=[]
for x,y in bridges:
 for xx,yy in [(x+1,y),(x,y+1)]:
  if (xx,yy) in bridges:adj.append([bridges[x,y],bridges[xx,yy]])
lens={f['id']:len(f['path'])-1 for f in d['design'].get('logical_feeds',[])}
rev=len(d['design'].get('bridge_reverse_channels',[]));forward=sum(v+1 for v in lens.values());slots=sum(lens.values())
# Each physical occupied bridge contributes exactly one extra path slot in this generated candidate.
out=dict(candidate_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),machine_counts=dict(Counter(u['model'] for u in l['machines'])),machine_area=area['machines'],occupied_area=sum(area.values()),area_by_kind=dict(area),overlap=overlap,powered=sum(bool(v) for v in cov.values()),unpowered=[k for k,v in cov.items() if not v],power_poles=len(l['power_poles']),maximum_empty_rectangle=dict(area=best[0],short_side=best[1],bounds=bounds),transport=len(l['transport']),bridges=len(bridges),adjacent_bridge_pairs=len(adj),route_count=len(lens),route_slots=slots,physical_channels=len(d['design']['physical_channels']),reverse_channels=rev,identities=dict(slots_equals_transport_plus_bridges=(slots==len(l['transport'])+len(bridges)),channels_equals_slots_plus_routes_plus_reverse=(len(d['design']['physical_channels'])==slots+len(lens)+rev)))
if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False))
