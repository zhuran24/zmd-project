#!/usr/bin/env python3
"""逐条列出325路，并以BFS及并查集独立判定固定机身下的单路可达性。"""
import os
os.sched_setaffinity(0,{6})
import json,sys,hashlib
from pathlib import Path
from collections import Counter,defaultdict
B=Path(__file__).resolve().parents[1];src=Path(sys.argv[1]);d=json.loads(src.read_text());l=d['layout'];c=json.loads((B/'逻辑接法.json').read_text());D=[(1,0),(0,1),(-1,0),(0,-1)]
units={};kinds={};occ={}
for group in ['machines','warehouse_outlets','power_poles','core']:
    for u in ([l[group]] if group=='core' else l[group]):
        units[u['id']]=u;kinds[u['id']]=group
        for x in range(u['x0'],u['x1']+1):
            for y in range(u['y0'],u['y1']+1):occ[x,y]=u['id']
free={(x,y) for x in range(70) for y in range(70)}-occ.keys();comp={};cid=0
for first in sorted(free):
    if first in comp:continue
    todo=[first];comp[first]=cid
    for x,y in todo:
        for dx,dy in D:
            q=x+dx,y+dy
            if q in free and q not in comp:comp[q]=cid;todo.append(q)
    cid+=1
# 第二套连通判定，整数格编号和并查集，不读取BFS标签。
parent=list(range(4900))
def root(a):
    while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
    return a
for x,y in free:
    for dx,dy in [(1,0),(0,1)]:
        if (x+dx,y+dy) in free:parent[root(y*70+x)]=root((y+dy)*70+x+dx)
def ports(uid,inbound):
    u=units[uid];kind=kinds[uid]
    if kind=='power_poles':return []
    if kind=='warehouse_outlets':sides=[] if inbound else [u['Dout']]
    elif kind=='core':sides=[u['Din'],(u['Din']+2)%4] if inbound else [(u['Din']+1)%4,(u['Din']+3)%4]
    else:sides=[u['Din'] if inbound else (u['Din']+2)%4]
    rows=[]
    for s in sides:
        offsets=([1] if kind=='warehouse_outlets' else list(range(1,8)) if inbound else [1,4,7]) if kind in ['warehouse_outlets','core'] else range(u['y1']-u['y0']+1 if s%2==0 else u['x1']-u['x0']+1)
        for off in offsets:
            x,y=[(u['x1'],u['y0']+off),(u['x0']+off,u['y1']),(u['x0'],u['y0']+off),(u['x0']+off,u['y0'])][s];q=x+D[s][0],y+D[s][1]
            rows.append(dict(side=s,offset=off,outer=list(q),available=q in free,blocked_by=occ.get(q,'基地外' if not(0<=q[0]<70 and 0<=q[1]<70) else None),component=comp.get(q)))
    return rows
def name(uid):return ('协议核心' if uid=='CORE' else units[uid].get('model','仓库取货口'))+' '+uid
decl={f['id']:f for f in d['design']['logical_feeds']};pc={p['id']:p for p in d['design']['physical_channels']};ts={u['id']:u for u in l['transport']};rows=[];counts=Counter();consistent=True
for e in c['logical_feeds']:
    ps=ports(e['source'],False);pt=ports(e['target'],True)
    aa={q['component'] for q in ps if q['available']};bb={q['component'] for q in pt if q['available']}
    ra={root(q['outer'][1]*70+q['outer'][0]) for q in ps if q['available']};rb={root(q['outer'][1]*70+q['outer'][0]) for q in pt if q['available']}
    reachable=bool(aa&bb);consistent &= reachable==bool(ra&rb)
    f=decl.get(e['id']);r=dict(id=e['id'],source=e['source'],source_name=name(e['source']),target=e['target'],target_name=name(e['target']),item=e['item'],rate=e['rate'],built=bool(f),single_route_reachable_ignoring_transport=reachable)
    if f:
        assert (f['from']['unit'],f['to']['unit'],f['item'],f['rate'])==(e['source'],e['target'],e['item'],e['rate']), '进路ID与约定源汇或物品不一致：'+e['id']
        cells=[]
        for k in f['path']:
            ch=pc[k];uid=ch['to']['unit']
            if uid not in ts:continue
            t=ts[uid];cells.append(dict(x=t['x'],y=t['y'],unit=uid,axis=('水平' if ch['to']['side']%2==0 else '竖直') if t['type']=='bridge' else '传送带'))
        r.update(source_port=f['from'],target_port=f['to'],transport_slots=len(cells),cells=cells)
        if not reachable:raise ValueError('已通进路未通过机身连通放宽：'+e['id'])
    else:
        why='源取货端口没有可用邻格' if not aa else '汇存货端口没有可用邻格' if not bb else '两端位于不同空格连通块' if not reachable else '单路可达，尚未联合布通'
        r.update(reason=why,source_ports=ps,target_ports=pt);counts[why]+=1
    rows.append(r)
nin=Counter(e['target'] for e in c['logical_feeds']);nout=Counter(e['source'] for e in c['logical_feeds']);short=[]
for uid,u in units.items():
    if kinds[uid]=='power_poles':continue
    ip=sum(q['available'] for q in ports(uid,True));op=sum(q['available'] for q in ports(uid,False))
    if ip<nin[uid] or op<nout[uid]:short.append(dict(id=uid,name=name(uid),free_input_neighbors=ip,required_inputs=nin[uid],free_output_neighbors=op,required_outputs=nout[uid]))
result=dict(candidate_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),expected_routes=325,built_routes=len(decl),missing_routes=325-len(decl),missing_classes=dict(counts),nontransport_cells=len(occ),free_cells=len(free),free_components=cid,bfs_unionfind_agree=consistent,port_shortage_units=short,routes=rows,scope='固定全部非运输单位，撤去所有运输单位，不保留空矩形。只判单路必要可达性，不限制多路竞争；可达不代表能同时布出。')
(B/'证据/逐路与端口核查.json').write_text(json.dumps(result,ensure_ascii=False,indent=1));print(json.dumps({k:v for k,v in result.items() if k not in ['routes','port_shortage_units']},ensure_ascii=False))
power_rows=[]
for u in l['machines']:
    covers=[]
    for p in l['power_poles']:
        x0=max(u['x0'],p['x0']-5);x1=min(u['x1'],p['x0']+6)
        y0=max(u['y0'],p['y0']-5);y1=min(u['y1'],p['y0']+6)
        if x0<=x1 and y0<=y1:
            covers.append(dict(pole=p['id'],intersection=[x0,y0,x1,y1],overlap_cells=(x1-x0+1)*(y1-y0+1)))
    power_rows.append(dict(id=u['id'],model=u['model'],covered=bool(covers),covers=covers))
power=dict(candidate_sha256=result['candidate_sha256'],machines=len(power_rows),powered=sum(r['covered'] for r in power_rows),rows=power_rows)
(B/'证据/逐台供电覆盖.json').write_text(json.dumps(power,ensure_ascii=False,indent=1))
raise SystemExit(0 if consistent else 1)
