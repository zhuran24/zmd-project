import json,hashlib
from pathlib import Path
from collections import defaultdict,Counter
b=Path(__file__).resolve().parents[1];p=b/'候选布局.json';d=json.loads(p.read_text());feeds={f['id']:f for f in d['design']['logical_feeds']};channels={e['id']:e for e in d['design']['physical_channels']};br={t['id']:t for t in d['layout']['transport'] if t['type']=='bridge'};xy={(t['x'],t['y']):t['id'] for t in br.values()};g=json.loads((b/'依据/groups.json').read_text());group={u:k for k,v in g.items() for u in v};axis={};rows=[]
for f in feeds.values():
 for cid in f['path'][:-1]:
  dest=channels[cid]['to']
  if dest['unit'] in br:axis[dest['unit'],dest['side']%2]=f['id']
def record(fid):
 f=feeds[fid];s,t=f['from']['unit'],f['to']['unit'];return dict(id=fid,source=s,target=t,item=f['item'],product_group=group.get(s,group.get(t)))
for uid,u in sorted(br.items()):rows.append(dict(id=uid,x=u['x'],y=u['y'],horizontal=record(axis[uid,0]),vertical=record(axis[uid,1])))
adj=[]
for (x,y),uid in xy.items():
 for dx,dy,ax in [(1,0,0),(0,1,1)]:
  other=xy.get((x+dx,y+dy))
  if other:adj.append(dict(bridges=[uid,other],axis='H' if ax==0 else 'V',forward_route=axis[uid,ax],same_forward_route=axis[uid,ax]==axis[other,ax],other_axes=[record(axis[uid,1-ax]),record(axis[other,1-ax])]))
maxrun=0
for (x,y),uid in xy.items():
 for dx,dy,ax in [(1,0,0),(0,1,1)]:
  n=1;fid=axis.get((uid,ax))
  while (x+n*dx,y+n*dy) in xy and axis.get((xy[x+n*dx,y+n*dy],ax))==fid:n+=1
  maxrun=max(maxrun,n)
z=dict(candidate_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bridge_count=len(br),both_axes_used=len(rows),adjacent_pairs=len(adj),bridges_in_adjacent_pairs=len({u for a in adj for u in a['bridges']}),longest_straight_run=maxrun,rows=rows,adjacency=adj)
(b/'证据/桥接器结构.json').write_text(json.dumps(z,ensure_ascii=False,indent=2));print(json.dumps(z,ensure_ascii=False))
