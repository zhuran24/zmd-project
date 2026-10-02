import json,sys,hashlib
from pathlib import Path
from collections import Counter,deque
from pack_factory import BASE,C,cells,D
from route_factory import ports
p=Path(sys.argv[1]);d=json.loads(p.read_text());l=d['layout'];rect=d['empty_rectangle']
blocked={q for u in l['machines']+l['warehouse_outlets']+l['power_poles']+[l['core'],rect] for q in cells(u)};components={};label=0
for x in range(70):
 for y in range(70):
  c=(x,y)
  if c in components or c in blocked:continue
  label+=1;components[c]=label;todo=deque([c])
  while todo:
   q=todo.popleft()
   for dx,dy in D:
    n=(q[0]+dx,q[1]+dy)
    if 0<=n[0]<70 and 0<=n[1]<70 and n not in blocked and n not in components:components[n]=label;todo.append(n)
out,inc=ports(l);ni=Counter(f['target'] for f in C['feeds']);no=Counter(f['source'] for f in C['feeds']);deficits=[]
for u in l['machines']:
 uid=u['id'];ip=[c for c,s,p in inc[uid] if c in components];op=[c for c,s,p in out[uid] if c in components]
 if len(ip)<ni[uid] or len(op)<no[uid]:deficits.append(dict(unit=uid,in_required=ni[uid],in_available=len(ip),out_required=no[uid],out_available=len(op),input_cells=ip,output_cells=op))
done={f['id'] for f in d['design'].get('logical_feeds',[])};rows=[]
for f in C['feeds']:
 if f['id'] in done:continue
 ss={components[c] for c,s,p in out[f['source']] if c in components};tt={components[c] for c,s,p in inc[f['target']] if c in components}
 kind='无合法起口邻格' if not ss else '无合法终口邻格' if not tt else '机身和供电桩阻断连通' if not(ss&tt) else '放宽为单路可达，联合布线未完成'
 rows.append(dict(**f,reason=kind,source_components=sorted(ss),target_components=sorted(tt)))
z=dict(candidate_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),port_deficits=deficits,unrouted=rows,counts=dict(Counter(r['reason'] for r in rows)),scope='仅固定机器、核心、仓库取货口、供电桩和所声明空矩形；运输障碍全部撤掉，允许四邻自由通行。仍不可达或端口数不足才否掉此固定几何；单路可达不证明联合布线可行。')
(BASE/'证据/固定几何卡点.json').write_text(json.dumps(z,ensure_ascii=False,indent=2));print(json.dumps(dict(port_deficit_machines=len(deficits),unrouted_counts=z['counts']),ensure_ascii=False))
