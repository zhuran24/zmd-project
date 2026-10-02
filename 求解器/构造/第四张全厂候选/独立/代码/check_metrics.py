#!/usr/bin/env python3
import json,hashlib,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];p=BASE/'布局.json';d=json.loads(p.read_text());l=d['layout'];grid=[[0]*70 for _ in range(70)];dups=[];areas={}
for name in ['machines','warehouse_outlets','power_poles','storage_boxes','transport','core']:
 area=0
 for u in ([l['core']] if name=='core' else l[name]):
  x0=u.get('x0',u.get('x'));x1=u.get('x1',u.get('x'));y0=u.get('y0',u.get('y'));y1=u.get('y1',u.get('y'))
  area+=(x1-x0+1)*(y1-y0+1)
  for y in range(y0,y1+1):
   for x in range(x0,x1+1):
    if grid[y][x]:dups.append([x,y])
    grid[y][x]+=1
 areas[name]=area
power=set()
for u in l['power_poles']:
 for x in range(u['x0']-5,u['x0']+7):
  for y in range(u['y0']-5,u['y0']+7):power.add((x,y))
covered=[u['id'] for u in l['machines'] if any((x,y) in power for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1))]
ps=[[0]*71 for _ in range(71)]
for y in range(70):
 for x in range(70):ps[y+1][x+1]=int(grid[y][x]>0)+ps[y][x+1]+ps[y+1][x]-ps[y][x]
best=(0,0);rects=[];checked=0
for x0 in range(65):
 for x1 in range(x0+6,71):
  w=x1-x0
  for y0 in range(65):
   for y1 in range(y0+6,71):
    checked+=1
    if ps[y1][x1]-ps[y0][x1]-ps[y1][x0]+ps[y0][x0]:continue
    h=y1-y0;score=(w*h,min(w,h))
    if score>best:best=score;rects=[]
    if score==best:rects.append(dict(x0=x0,y0=y0,x1=x1-1,y1=y1-1))
r={'layout_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'method':'整数网格涂色、逐格供电覆盖、二维前缀和枚举所有两边至少6的矩形','areas':areas,'overlaps':dups,'powered_machines':len(covered),'occupied':sum(v>0 for row in grid for v in row),'empty_rectangles_enumerated':checked,'maximum_area':best[0],'maximum_short_side':best[1],'maximizers':rects}
a=json.loads((BASE/'静态检查结果.json').read_text())['stats'];r['agrees_with_static_check']=not dups and r['powered_machines']==a['powered'] and r['occupied']==a['occupied'] and areas['machines']==a['machine_area'] and (best[0],best[1])==(a['empty_rectangle']['area'],a['empty_rectangle']['short_side'])
(BASE/'结果/独立几何数字复算.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False))
