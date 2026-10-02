#!/usr/bin/env python3
import json,hashlib
from pathlib import Path
from collections import Counter,defaultdict
B=Path(__file__).resolve().parents[1];delta=[(1,0),(0,1),(-1,0),(0,-1)]
def verify(path,spec):
 d=json.loads(path.read_text());l=d['layout'];W,H=l['W'],l['H'];rules={r['name']:r for r in spec['roles']};occ={};units={};typ={};ports={};at={};errors=[]
 def addport(uid,xy,di,off,mode):
  p=(uid,di,off);ports[p]=(xy,mode);at[xy,di]=p
 def face(u,s):
  if s==0:return [(u['x1'],y) for y in range(u['y0'],u['y1']+1)]
  if s==2:return [(u['x0'],y) for y in range(u['y0'],u['y1']+1)]
  if s==1:return [(x,u['y1']) for x in range(u['x0'],u['x1']+1)]
  return [(x,u['y0']) for x in range(u['x0'],u['x1']+1)]
 for i,u in enumerate(l['machines']):
  uid='M'+str(i);units[uid]=u;typ[uid]='machine'
  for y in range(u['y0'],u['y1']+1):
   for x in range(u['x0'],u['x1']+1):
    if (x,y) in occ:errors.append('overlap')
    occ[x,y]=uid
  for di,mode in [(u['Din'],'in'),((u['Din']+2)%4,'out')]:
   for off,xy in enumerate(face(u,di)):addport(uid,xy,di,off,mode)
 for i,t in enumerate(l['transport']):
  uid='T'+str(i);units[uid]=t;typ[uid]=t['type'];xy=(t['x'],t['y'])
  if xy in occ:errors.append('overlap')
  occ[xy]=uid
  if t['type']=='belt':
   addport(uid,xy,t['in_side'],0,'in');addport(uid,xy,t['out_side'],0,'out')
  else:
   for di in range(4):addport(uid,xy,di,0,'both')
 for mode,arr in [('out',l['vin']),('in',l['vout'])]:
  for i,v in enumerate(arr):
   di=v['side'];xy=(v['x']+delta[di][0],v['y']+delta[di][1]);uid=('VI' if mode=='out' else 'VO')+str(i)
   if 0<=xy[0]<W and 0<=xy[1]<H:errors.append('virtual_not_boundary')
   units[uid]=v;typ[uid]='virtual';addport(uid,xy,(di+2)%4,0,mode)
 if any(not(0<=x<W and 0<=y<H) for x,y in occ):errors.append('outside')
 edges=set();out=defaultdict(list)
 for p,(xy,mode) in ports.items():
  if mode not in ['out','both']:continue
  di=p[1];nextxy=(xy[0]+delta[di][0],xy[1]+delta[di][1]);q=at.get((nextxy,(di+2)%4))
  if q and ports[q][1] in ['in','both'] and (typ[p[0]] in ['belt','bridge'] or typ[q[0]] in ['belt','bridge']):edges.add((p,q));out[p].append((p,q))
 used=set();paths=[];incoming=defaultdict(Counter);outgoing=Counter()
 for p,q in sorted(edges):
  if typ[p[0]] in ['belt','bridge']:continue
  start=p;cur=q;pe=[(p,q)];physical=[]
  for step in range(2*W*H):
   if typ[cur[0]] not in ['belt','bridge']:break
   if cur[0] in physical:errors.append('repeated_unit');break
   physical.append(cur[0]);t=units[cur[0]];ds=(cur[1]+2)%4 if typ[cur[0]]=='bridge' else t['out_side'];nexts=out.get((cur[0],ds,0),[])
   if len(nexts)!=1:errors.append('broken_or_branched_path');break
   pe.append(nexts[0]);cur=nexts[0][1]
  else:errors.append('cycle')
  if any(e in used for e in pe):errors.append('shared_channel')
  used.update(pe)
  label=units[start[0]]['label'] if typ[start[0]]=='virtual' else rules[units[start[0]]['role']]['out'][0]
  if typ[cur[0]]=='virtual':
   if units[cur[0]]['label']!=label:errors.append('wrong_boundary_label')
  elif typ[cur[0]]=='machine':incoming[cur[0]][label]+=1
  else:errors.append('no_terminal')
  outgoing[start[0]]+=1;paths.append(dict(source=start[0],target=cur[0],label=label,cells=len(physical)))
 if used!=edges:errors.append('unaccounted_channel')
 for uid,u in units.items():
  if typ[uid]!='machine':continue
  r=rules[u['role']]
  if incoming[uid]!=Counter(r['in_count']) or outgoing[uid]!=r['n_out']:errors.append('machine_interface_counts')
 if Counter(u['role'] for u in l['machines'])!=Counter({r['name']:r['count'] for r in spec['roles']}):errors.append('role_counts')
 return dict(file=str(path.relative_to(B)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),W=W,H=H,machines=len(l['machines']),machine_area=sum((u['x1']-u['x0']+1)*(u['y1']-u['y0']+1) for u in l['machines']),transport=len(l['transport']),bridges=sum(t['type']=='bridge' for t in l['transport']),path_count=len(paths),channel_count=len(edges),local_structure_pass=not errors,errors=sorted(set(errors)),virtual_inputs=len(l['vin']),virtual_outputs=len(l['vout']),scope='只核局部端口与路径；虚拟接口必须由全厂实际路径替换，未含供电或动态认证。')
plant=dict(roles=[dict(name='种植',count=2,in_count={'种子':1},out=['植物'],n_out=1),dict(name='采种',count=1,in_count={'植物':1},out=['种子'],n_out=2),dict(name='粉碎',count=1,in_count={'植物':1},out=['粉末'],n_out=3)])
res=[]
for dims in ['12x11','13x11','12x12','16x8']:res.append(verify(B/f'模块/plant-{dims}.json',plant))
res.append(verify(B/'模块/qplant-12x13.json',json.loads((B/'模块/qplant-spec.json').read_text())))
(B/'证据/模块独立检查.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps(res,ensure_ascii=False))
