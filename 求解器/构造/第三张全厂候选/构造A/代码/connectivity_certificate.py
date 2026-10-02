#!/usr/bin/env python3
"""Two independent encodings certify unreachable routes for fixed bodies.

All transport units and the reserved empty rectangle are REMOVED as obstacles.
Thus the certificate excludes any possible belt/bridge rerouting for exactly
these nontransport positions/rotations, without assuming the attempted paths.
"""
import json,sys
from collections import deque,Counter
from pathlib import Path
from static_check import BASE,read,digest
p=Path(sys.argv[1]);d=read(p);l=d['layout'];c=read(BASE/'逻辑接法.json');units={u['id']:u for k in ('machines','warehouse_outlets','power_poles') for u in l[k]};units['CORE']=l['core'];blocked=set()
for u in units.values():blocked.update((x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1))
free={(x,y) for x in range(70) for y in range(70)}-blocked
def ports_A(uid,inbound):
    u=units[uid];ans=[]
    if uid.startswith('W'):sides=[u['Dout']];offsets=[1]
    elif uid=='CORE':sides=[u['Din'],(u['Din']+2)%4] if inbound else [(u['Din']+1)%4,(u['Din']+3)%4];offsets=range(1,8) if inbound else [1,4,7]
    else:sides=[u['Din'] if inbound else (u['Din']+2)%4];offsets=None
    for s in sides:
        for z in offsets if offsets is not None else range(u['y1']-u['y0']+1 if s%2==0 else u['x1']-u['x0']+1):
            v=[(u['x1']+1,u['y0']+z),(u['x0']+z,u['y1']+1),(u['x0']-1,u['y0']+z),(u['x0']+z,u['y0']-1)][s]
            if v in free:ans.append(v)
    return ans
component={};components=[]
for start in sorted(free):
    if start in component:continue
    no=len(components);component[start]=no;q=deque([start]);cells=[]
    while q:
        x,y=q.popleft();cells.append((x,y))
        for v in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if v in free and v not in component:component[v]=no;q.append(v)
    components.append(cells)
rows=[];bad=[]
for e in c['logical_feeds']:
    starts=ports_A(e['source'],False);ends=ports_A(e['target'],True);a={component[v] for v in starts};b={component[v] for v in ends};ok=bool(a&b);rows.append(dict(e,source_free_neighbors=starts,target_free_neighbors=ends,source_components=sorted(a),target_components=sorted(b),reachable_in_relaxation=ok))
    if not ok:bad.append(e['id'])
# Independent flat-array encoding and union/find, with independent edge walks.
mask=[False]*4900
for u in units.values():
    for yy in range(u['y0'],u['y1']+1):
        first=70*yy+u['x0']
        for q in range(first,first+u['x1']-u['x0']+1):mask[q]=True
parent=list(range(4900))
def root(q):
    while parent[q]!=q:parent[q]=parent[parent[q]];q=parent[q]
    return q
for q in range(4900):
    if mask[q]:continue
    for z in ([q+1] if q%70<69 else [])+([q+70] if q<4830 else []):
        if not mask[z]:parent[root(q)]=root(z)
def ports_B(uid,inside):
    u=units[uid];x0,y0,x1,y1=[u[k] for k in ('x0','y0','x1','y1')];di=u.get('Din');dirs=([di,(di+2)%4] if inside else [(di+1)%4,(di+3)%4]) if uid=='CORE' else [u['Dout']] if uid.startswith('W') else [di if inside else (di+2)%4];ans=[]
    for side in dirs:
        boundary=([(x1+1,y) for y in range(y0,y1+1)] if side==0 else [(x,y1+1) for x in range(x0,x1+1)] if side==1 else [(x0-1,y) for y in range(y0,y1+1)] if side==2 else [(x,y0-1) for x in range(x0,x1+1)])
        select=range(1,8) if uid=='CORE' and inside else (1,4,7) if uid=='CORE' else (1,) if uid.startswith('W') else range(len(boundary))
        for i in select:
            x,y=boundary[i]
            if 0<=x<70 and 0<=y<70 and not mask[x+70*y]:ans.append(root(x+70*y))
    return set(ans)
bad_B=[e['id'] for e in c['logical_feeds'] if not ports_B(e['source'],False)&ports_B(e['target'],True)]
assert bad==bad_B
result=dict(scope='exact fixed nontransport coordinates and rotations; all attempted transport removed; no empty rectangle forbidden',candidate_sha256=digest(p),all_agree=True,body_cells=len(blocked),free_cells=len(free),component_count=len(components),component_sizes=sorted(map(len,components),reverse=True),unreachable_count=len(bad),unreachable_route_ids=bad,second_encoding_unreachable_route_ids=bad_B,necessary_route_reachability=rows,components=components,not_general_infeasibility=True)
(BASE/'证据/固定摆放不可连通证书.json').write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n');print(json.dumps({k:result[k] for k in ('all_agree','body_cells','free_cells','component_count','unreachable_count')},ensure_ascii=False))
