import json,sys,hashlib
from pathlib import Path
from collections import Counter
p=Path(sys.argv[1]);b=Path(__file__).resolve().parents[1];d=json.loads(p.read_text());l=d['layout'];c=json.loads((b/'依据/S2接法.json').read_text())
owner={};rect=d['empty_rectangle']
for group in ['machines','warehouse_outlets','power_poles','core']:
 for u in [l[group]] if group=='core' else l[group]:
  for y in range(u['y0'],u['y1']+1):
   for x in range(u['x0'],u['x1']+1):owner[x,y]=u['id']
blocked=set(owner)|{(x,y) for y in range(rect['y0'],rect['y1']+1) for x in range(rect['x0'],rect['x1']+1)}
def face(u,s):
 if s==0:return [(u['x1']+1,y) for y in range(u['y0'],u['y1']+1)]
 if s==2:return [(u['x0']-1,y) for y in range(u['y0'],u['y1']+1)]
 if s==1:return [(x,u['y1']+1) for x in range(u['x0'],u['x1']+1)]
 return [(x,u['y0']-1) for x in range(u['x0'],u['x1']+1)]
raw_in={};raw_out={}
for u in l['machines']:raw_in[u['id']]=face(u,u['Din']);raw_out[u['id']]=face(u,(u['Din']+2)%4)
for u in l['warehouse_outlets']:raw_in[u['id']]=[];raw_out[u['id']]=[face(u,u['Dout'])[1]]
u=l['core'];raw_in['CORE']=[q for s in [u['Din'],(u['Din']+2)%4] for q in face(u,s)[1:8]];raw_out['CORE']=[face(u,z['side'])[z['offset']] for z in u['output_items']]
labels={};label=0
for y in range(70):
 for x in range(70):
  if (x,y) in blocked or (x,y) in labels:continue
  label+=1;stack=[(x,y)];labels[x,y]=label
  while stack:
   xx,yy=stack.pop()
   for q in [(xx+1,yy),(xx-1,yy),(xx,yy+1),(xx,yy-1)]:
    if 0<=q[0]<70 and 0<=q[1]<70 and q not in blocked and q not in labels:labels[q]=label;stack.append(q)
ni=Counter(f['target'] for f in c['feeds']);no=Counter(f['source'] for f in c['feeds']);bad=[]
for u in l['machines']:
 uid=u['id'];a=sum(q in labels for q in raw_in[uid]);z=sum(q in labels for q in raw_out[uid])
 if a<ni[uid] or z<no[uid]:bad.append(uid)
done={f['id'] for f in d['design']['logical_feeds']};ct=Counter()
for f in c['feeds']:
 if f['id'] in done:continue
 a={labels[q] for q in raw_out[f['source']] if q in labels};z={labels[q] for q in raw_in[f['target']] if q in labels}
 ct['无合法起口邻格' if not a else '无合法终口邻格' if not z else '机身和供电桩阻断连通' if not a&z else '放宽为单路可达，联合布线未完成']+=1
E3=next(u for u in l['machines'] if u['id']=='E3');e3cells=raw_out['E3'];core_in=[e['id'] for e in d['design']['physical_channels'] if e['to']['unit']=='CORE']
out=dict(candidate_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),port_deficit_machine_count=len(bad),port_deficit_machine_ids=sorted(bad),missing_route_counts=dict(ct),ore_routes=sum(f['item'] in ['源矿','蓝铁矿'] for f in d['design']['logical_feeds']),finished_routes=sum(f['to']['unit']=='CORE' for f in d['design']['logical_feeds']),core_incoming_channels=core_in,storage_boxes=len(l['storage_boxes']),finished_delivery_rate_bound={'高容谷地电池':'0','精选荞愈胶囊':'0'} if not core_in and not l['storage_boxes'] else None,E3=dict(machine=E3,output_neighbor_cells=[dict(x=q[0],y=q[1],occupied_by=owner.get(q)) for q in e3cells],all_occupied_by_core=all(owner.get(q)=='CORE' for q in e3cells)),scope='所有保持候选中非运输单位位置、朝向、供电桩和指定空矩形的布线；几何不可达判定已经撤掉全部运输障碍。不是对其他布局的不可行证明。')
(b/'证据/卡点独立复核.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in out.items() if k not in ['port_deficit_machine_ids','E3']},ensure_ascii=False))
