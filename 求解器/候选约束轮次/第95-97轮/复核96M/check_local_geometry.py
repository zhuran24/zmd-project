"""Recheck the cited 93F local coordinate DATA without importing its code."""
from pathlib import Path
import json,itertools
OUT=Path(__file__).resolve().parent
source=OUT.parent.parent/'第92-94轮/复核93F/local_geometry.json'
data=json.loads(source.read_text())
rects=data['rectangles'];routes={};lengths={}
for name,vertices in data['route_vertices'].items():
    cells=[tuple(vertices[0])]
    for begin,end in zip(vertices,vertices[1:]):
        x,y=begin;dx=(end[0]>x)-(end[0]<x);dy=(end[1]>y)-(end[1]<y)
        assert (dx==0)!=(dy==0)
        while (x,y)!=tuple(end):x+=dx;y+=dy;cells.append((x,y))
    assert len(cells)==len(set(cells))
    assert cells==[tuple(p) for p in data['route_cells'][name]]
    # Independent length by Manhattan segment sums.
    length=1+sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(vertices,vertices[1:]))
    assert length==len(cells)
    routes[name]=cells;lengths[name]=length
grid={};inputs={};outputs={};unitcells={}
for name,(x,y,w,h) in rects.items():
    body={(i,j) for i in range(x,x+w) for j in range(y,y+h)}
    unitcells[name]=body
    assert not set(grid)&body
    grid.update({p:name for p in body})
    if name in data['machine_types']:
        inputs[name]={((x,j),(-1,0)) for j in range(y,y+h)}
        outputs[name]={((x+w-1,j),(1,0)) for j in range(y,y+h)}
    elif name=='协议核心':
        inputs[name]={((i,j),direction) for i in range(x+1,x+8)
                      for j,direction in ((y,(0,-1)),(y+h-1,(0,1)))}
        outputs[name]={((i,y+offset),direction) for offset in (1,4,7)
                       for i,direction in ((x,(-1,0)),(x+w-1,(1,0)))}
    else:inputs[name]=set();outputs[name]=set()
expected=set()
for route,path in routes.items():
    src,dst=data['route_ends'][route]
    sx,sy,sw,sh=rects[src];tx,ty,tw,th=rects[dst]
    assert path[0][0]==sx+sw and sy<=path[0][1]<sy+sh
    assert path[-1][0]==tx-1 and ty<=path[-1][1]<ty+th
    chain=[src]+[f'{route}:{i}' for i in range(len(path))]+[dst]
    expected.update(zip(chain,chain[1:]))
    for i,p in enumerate(path):
        name=chain[i+1];assert p not in grid;grid[p]=name;unitcells[name]={p}
        prev=path[i-1] if i else (p[0]-1,p[1])
        nxt=path[i+1] if i+1<len(path) else (p[0]+1,p[1])
        inputs[name]={(p,(prev[0]-p[0],prev[1]-p[1]))}
        outputs[name]={(p,(nxt[0]-p[0],nxt[1]-p[1]))}
formed=set()
for name,ports in outputs.items():
    for (x,y),(dx,dy) in ports:
        q=(x+dx,y+dy);other=grid.get(q)
        if other and (q,(-dx,-dy)) in inputs[other]:formed.add((name,other))
assert formed==expected
assert all(0<=x<70 and 0<=y<70 for x,y in grid)
area_by_sum=sum(w*h for x,y,w,h in rects.values())+sum(lengths.values())
assert area_by_sum==len(grid)==267
assert len(formed)==sum(n+1 for n in lengths.values())==72
coverage={}
for m in data['machine_types']:
    got=[];independent=[];x,y,w,h=rects[m]
    for p,(px,py,pw,ph) in rects.items():
        if not p.startswith('供电桩'):continue
        # Pole centre px+1, py+1; its 12x12 square covers integer cells
        # px-5 ... px+6 and py-5 ... py+6.
        square={(i,j) for i in range(px-5,px+7) for j in range(py-5,py+7)}
        if square&unitcells[m]:got.append(p)
        if max(x,px-5)<min(x+w,px+7) and max(y,py-5)<min(y+h,py+7):independent.append(p)
    assert got==independent and got
    coverage[m]=got
ans={'source':str(source),'lengths':lengths,'occupied_cells':len(grid),'channels':len(formed),
     'unintended_channels':len(formed-expected),'coverage':coverage,'scope':'Local geometry only'}
(OUT/'local_geometry_check.json').write_text(json.dumps(ans,ensure_ascii=False,indent=2)+'\n')
print(ans)
