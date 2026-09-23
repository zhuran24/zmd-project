"""从 seat-opus-3/check.py 的占格/端口/桥邻端推导扩展；不读取其他检查器。"""
from collections import defaultdict, Counter, deque
from catalog import *

class Checks:
 def __init__(self): self.records=[]
 def add(self,code,ok,basis,evidence=None,remaining=''):
  self.records.append(dict(check=code,status='PASS' if ok else 'FAIL',basis=basis,evidence=evidence,remaining=remaining))
 def note(self,code,status,basis,evidence=None,remaining=''):
  self.records.append(dict(check=code,status=status,basis=basis,evidence=evidence,remaining=remaining))
 def good(self,*codes): return not any(r['status']=='FAIL' and (not codes or r['check'] in codes) for r in self.records)

def maximum_empty(occupied,W=70,H=70,min_side=6):
 """穷举上下界，扫描各条全空横区间；每个高度只保留最大宽区间已足够。"""
 best=(0,0);rects=[]
 for y0 in range(H-min_side+1):
  blocked=[False]*W
  for y1 in range(y0,H):
   for x in range(W): blocked[x] |= (x,y1) in occupied
   h=y1-y0+1
   if h<min_side: continue
   start=0
   for x in range(W+1):
    if x==W or blocked[x]:
     w=x-start
     if w>=min_side:
      score=(w*h,min(w,h))
      r={'x0':start,'y0':y0,'x1':x-1,'y1':y1}
      if score>best: best=score;rects=[r]
      elif score==best: rects.append(r)
     start=x+1
 return dict(area=best[0],short_side=best[1],rectangles=rects)

class Geometry:
 def __init__(self,layout,checks):
  self.l=layout;self.c=checks;self.units={};self.kind={};self.occ={};self.ports={};self.spatial={};self.axes={};self.powered={};self.source_items={};self.edges=[];self.ambiguities=[]
  # ports: PortRef tuple -> (cell, 'in'/'out'); spatial independently rebuilt.
  for group in ['machines','warehouse_outlets','core','power_poles','storage_boxes','transport']:
   for u in [layout[group]] if group=='core' else layout[group]:
    uid=u['id'];self.units[uid]=u;self.kind[uid]=u.get('type',group)
    w=u.get('x1',0)-u.get('x0',0)+1;h=u.get('y1',0)-u.get('y0',0)+1
    expected=None
    if group=='machines': expected={'小':(3,3),'中':(5,5),'大':(6,4) if u['Din']%2 else (4,6)}[u['kind']]
    elif group=='core': expected=(9,9)
    elif group=='power_poles': expected=(2,2)
    elif group=='storage_boxes': expected=(3,3)
    elif group=='warehouse_outlets':
     expected=(1,3) if u['Dout']==0 else (3,1)
     checks.add('outlet-position',u['x0']==0 if u['Dout']==0 else u['y0']==0,'规则·仓库取货口；任务·仓库取货口位置',uid)
    if expected: checks.add('shape',(w,h)==expected,'规则·单位尺寸、制造单位端口边',{'unit':uid,'actual':[w,h],'expected':expected})
    for xy in cells(u):
     checks.add('overlap',xy not in self.occ,'规则·基地/单位；格式 §2.2',{'unit':uid,'cell':xy,'previous':self.occ.get(xy)}) if xy in self.occ else None
     checks.add('boundary',0<=xy[0]<70 and 0<=xy[1]<70,'规则·基地',{'unit':uid,'cell':xy}) if not(0<=xy[0]<70 and 0<=xy[1]<70) else None
     self.occ[xy]=uid
  checks.add('occupancy',checks.good('shape','outlet-position','overlap','boundary'),'规则·基地/各单位；格式 §2.2',{'occupied':len(self.occ),'units':len(self.units)})
  self.valid=checks.good('occupancy')
  if not self.valid: return
  for uid,u in self.units.items():
   k=self.kind[uid]
   if k in ['machines','storage_boxes']:
    for d,io in [(u['Din'],'in'),(opp(u['Din']),'out')]:
     for o,xy in enumerate(edge(u,d)): self.port(uid,d,o,xy,io)
   elif k=='warehouse_outlets':
    d=u['Dout'];self.port(uid,d,1,edge(u,d)[1],'out');self.source_items[(uid,d,1)]=u['item']
   elif k=='core':
    for d in [u['Din'],opp(u['Din'])]:
     for o in range(1,8): self.port(uid,d,o,edge(u,d)[o],'in')
    for q in u['output_items']:
     d,o=q['side'],q['offset'];self.port(uid,d,o,edge(u,d)[o],'out');self.source_items[(uid,d,o)]=q['item']
   elif k in ['belt','splitter','merger','gate']:
    for d in range(4):
     io=None
     if k in ['belt','gate']:
      if d==u['in_side']: io='in'
      if d==(u['out_side'] if k=='belt' else opp(u['in_side'])): io='out'
     elif k=='splitter': io='in' if d==u['in_side'] else 'out'
     else: io='out' if d==u['out_side'] else 'in'
     if io: self.port(uid,d,0,(u['x'],u['y']),io)
  # Simultaneous derivation against non-bridge ports; adjacent bridges rejected first.
  for u in layout['transport']:
   if u['type']!='bridge': continue
   uid=u['id'];xy=(u['x'],u['y'])
   adjacent=[self.occ[nb(xy,d)] for d in range(4) if nb(xy,d) in self.occ and self.kind[self.occ[nb(xy,d)]]=='bridge']
   checks.add('N4b',not adjacent,'规则·桥接器；共识 §三.3 N4b；格式 §8.2',{'unit':uid,'adjacent':adjacent})
   for ax,ends,key in [(0,[0,2],'H_in'),(1,[1,3],'V_in')]:
    facing={}
    for d in ends:
     p=self.spatial.get((nb(xy,d),opp(d)))
     if p and self.kind[p[0]]!='bridge': facing[d]=self.ports[p][1]
    got=next((d for d in ends if facing.get(d)=='out'),None) if len(facing)==2 and set(facing.values())=={'in','out'} else None
    if len(facing)==1:
     # One attached end already determines the bridge direction and forms a real
     # channel. Keep it in the graph even though the restricted class rejects
     # its dead end; otherwise an undeclared automatic channel would disappear.
     side=next(iter(facing));got=side if facing[side]=='out' else opp(side)
    if adjacent or len(facing)==2 and len(set(facing.values()))==1:
     self.ambiguities.append({'bridge':uid,'axis':ax,'adjacent_bridges':adjacent,'facing':facing})
    valid=(len(facing)==0 or len(facing)==2 and set(facing.values())=={'in','out'}) and not adjacent and u[key]==got
    checks.add('N4a',valid,'规则·桥接器；共识 §1.1.3/三.3 N4a；格式 §6',{'unit':uid,'axis':ax,'facing':facing,'derived':got,'claimed':u[key]})
    if got is not None: self.axes[(uid,ax)]=got
  for (uid,ax),d in self.axes.items():
   u=self.units[uid];self.port(uid,d,0,(u['x'],u['y']),'in');self.port(uid,opp(d),0,(u['x'],u['y']),'out')
  for p,(xy,io) in self.ports.items():
   if io!='out': continue
   q=self.spatial.get((nb(xy,p[1]),opp(p[1])))
   if q and self.ports[q][1]=='in' and (self.transport(p[0]) or self.transport(q[0])): self.edges.append((p,q))
  self.edges.sort();self.ins=defaultdict(list);self.outs=defaultdict(list);self.sin=defaultdict(list);self.sout=defaultdict(list)
  for i,(p,q) in enumerate(self.edges):
   self.outs[p[0]].append(i);self.ins[q[0]].append(i);self.sout[self.slot(p)].append(i);self.sin[self.slot(q)].append(i)
  self.slots={(u['id'],0) for u in layout['transport'] if u['type']!='bridge'} | set(self.axes)
  for u in layout['machines']+layout['storage_boxes']:
   cover=[p['id'] for p in layout['power_poles'] if self.covers(p,u)]
   self.powered[u['id']]=cover
  checks.add('power-rebuild',True,'规则·供电桩/供电状态/需电功能；格式 §5.4',self.powered)
 def port(self,uid,d,o,xy,io):
  p=(uid,d,o);self.ports[p]=(xy,io);self.spatial[(xy,d)]=p
 def transport(self,uid): return self.kind[uid] in ['belt','bridge','gate','splitter','merger']
 def slot(self,p):
  uid,d,o=p;k=self.kind[uid]
  if k=='bridge': return uid,d%2
  if self.transport(uid): return uid,0
  if k in ['warehouse_outlets','core'] and self.ports[p][1]=='out': return p
  return uid,self.ports[p][1]
 @staticmethod
 def covers(p,u): return u['x0']<=p['x0']+6 and u['x1']>=p['x0']-5 and u['y0']<=p['y0']+6 and u['y1']>=p['y0']-5

def structural(d,g,c):
 z=d['design'];claims={(ref(e['from']),ref(e['to'])):e for e in z['physical_channels']};actual=set(g.edges)
 difference={'missing':[list(x) for x in sorted(actual-claims.keys())],'extra':[list(x) for x in sorted(claims.keys()-actual)]}
 if g.ambiguities:
  c.note('N5a','BLOCKED','规则·桥接器/接通；格式 §6/8.2 N4/N5a',{'ambiguous_bridge_directions':g.ambiguities,'known_subset_difference':difference},'桥方向不唯一；已由 N4 拒绝，未把部分已知图冒充完整图。')
 else:
  c.add('N5a',actual==claims.keys(),'规则·通道；约束·端口对接；格式 §8.2 N5a',difference)
 c.add('port-references',all(ref(e[s]) in g.ports for e in z['physical_channels'] for s in ['from','to']),'规则·端口/各单位；格式 §2.3')
 c.add('N1',not any(len(g.outs[u])>=2 and any(g.kind[g.edges[i][1][0]]=='merger' for i in g.outs[u]) for u in g.units if not g.transport(u)),'规则·取货优先级；约束·取货分级；格式 §8.2 N1')
 c.add('N2',not any(len(g.ins[u])>=2 and any(g.kind[g.edges[i][0][0]]=='splitter' for i in g.ins[u]) for u in g.units),'规则·存货优先级；约束·密集结点；格式 §8.2 N2')
 c.add('N3a',all(u['cum'] is None for u in g.l['transport'] if u['type']=='gate' and (g.ins[u['id']] or g.outs[u['id']])),'规则·物品准入口；约束·准入累计；格式 §8.2 N3a')
 if not any(u['type']=='bridge' for u in g.l['transport']):
  c.note('N4a','NOT_APPLICABLE','格式 §8.2 N4a','无桥');c.note('N4b','NOT_APPLICABLE','格式 §8.2 N4b','无桥')
 # Every transport slot must have an external origin and an external destination.
 fwd=defaultdict(set);rev=defaultdict(set);starts=set();ends=set()
 for p,q in g.edges:
  a,b=g.slot(p),g.slot(q)
  if g.transport(p[0]) and g.transport(q[0]): fwd[a].add(b);rev[b].add(a)
  elif not g.transport(p[0]): starts.add(b)
  else: ends.add(a)
 def reach(s,adj):
  seen=set(s);todo=list(s)
  while todo:
   for b in adj[todo.pop()]:
    if b not in seen: seen.add(b);todo.append(b)
  return seen
 from_src=reach(starts,fwd);to_sink=reach(ends,rev)
 c.add('transport-terminal-reachability',g.slots<=from_src & to_sink,'格式 §8.2 禁止无源无汇纯运输循环；约束·植物再生来路',{'without_source':sorted(g.slots-from_src),'without_sink':sorted(g.slots-to_sink)})
 # Real reachability intentionally ignores candidate allowed_items.
 possible=defaultdict(set)
 for p,it in g.source_items.items(): possible[g.slot(p)].add(it)
 for u in g.l['machines']:
  for r in u['recipe_ids']: possible[(u['id'],'out')].update(RECIPES[r][2])
 changed=True
 while changed:
  changed=False
  for p,q in g.edges:
   a,b=g.slot(p),g.slot(q);v=set(possible[a]);u=g.units[q[0]]
   if g.kind[q[0]]=='gate' and u['filter'] is not None: v &= {u['filter']}
   n=len(possible[b]);possible[b]|=v;changed|=len(possible[b])!=n
  for u in g.l['machines']:
   for r,(model,inp,out,t) in RECIPES.items():
    if model==u['model'] and set(inp)<=possible[(u['id'],'in')]:
     k=(u['id'],'out');n=len(possible[k]);possible[k].update(out);changed|=len(possible[k])!=n
  for u in g.l['storage_boxes']:
   k=(u['id'],'out');n=len(possible[k]);possible[k]|=possible[(u['id'],'in')];changed|=len(possible[k])!=n
 g.possible=possible;g.edge_items=[]
 for p,q in g.edges:
  it=set(possible[g.slot(p)]);u=g.units[q[0]]
  if g.kind[q[0]]=='gate' and u['filter'] is not None: it &= {u['filter']}
  g.edge_items.append(it)
 bad_material=[];outside_recipe=[]
 for u in g.l['machines']:
  full=set().union(*(set(r[1]) for r in RECIPES.values() if r[0]==u['model']))
  design=set().union(*(set(RECIPES[r][1]) for r in u['recipe_ids']))
  got=possible[(u['id'],'in')]
  if got-full: bad_material.append([u['id'],sorted(got-full)])
  if (got & full)-design: outside_recipe.append([u['id'],sorted((got & full)-design)])
  for r,(model,ins,outs,t) in RECIPES.items():
   if model==u['model'] and r not in u['recipe_ids'] and set(ins)<=got: outside_recipe.append([u['id'],'reachable recipe '+r])
 c.add('wrong-material',not bad_material,'约束·存货误料停机与可用台数；规则·存货物品格；格式 §5.1/8.1',bad_material)
 c.add('outside-recipe',not outside_recipe,'规则·配方/制造；格式 §5.1/8.1（设计声明不是配方开关）',outside_recipe)
 if actual==claims.keys():
  c.add('outside-allowed-items',all(g.edge_items[i]<=set(claims[e]['allowed_items']) for i,e in enumerate(g.edges)),'规则·通道/准入口；格式 §8.1',[[claims[e]['id'],sorted(g.edge_items[i]-set(claims[e]['allowed_items']))] for i,e in enumerate(g.edges) if g.edge_items[i]-set(claims[e]['allowed_items'])])
 blocked=[]
 for i,(p,q) in enumerate(g.edges):
  u=g.units[q[0]]
  if g.kind[q[0]]!='gate' or u['filter'] is None: continue
  for it in possible[g.slot(p)]-{u['filter']}:
   alternatives=[]
   for j in g.sout[g.slot(p)]:
    if j==i: continue
    v=g.units[g.edges[j][1][0]]
    if g.kind[v['id']]!='gate' or v['filter'] in [None,it]: alternatives.append(j)
   if not alternatives: blocked.append({'gate':q[0],'upstream':p,'item':it})
 c.add('N3b',not blocked,'规则·物品准入口/物品格；格式 §8.2 N3b',blocked,'仅排除身份拒绝且无替代出口图样；及时通过与活性另证。')
 g.paths=[]
 if z['class']=='p2p':
  c.add('P1',not g.l['storage_boxes'] and all(u['type'] in ['belt','bridge'] for u in g.l['transport']),'共识 §1.3 P1；格式 §8.2')
  c.add('P6',all(len(u['recipe_ids'])==1 for u in g.l['machines'] if u['model'] in ['粉碎机','采种机']),'共识 §1.3 P6；约束·满载配置；格式 §8.2')
  ok=True;seen=[]
  for i,(p,q) in enumerate(g.edges):
   if g.transport(p[0]): continue
   path=[];j=i
   while j not in path:
    path.append(j);a,b=g.edges[j]
    if not g.transport(b[0]): break
    s=g.slot(b)
    if len(g.sin[s])!=1 or len(g.sout[s])!=1: ok=False;break
    j=g.sout[s][0]
   else: ok=False
   if g.transport(g.edges[path[-1]][1][0]): ok=False
   g.paths.append(path);seen.extend(path)
  ok &= len(seen)==len(g.edges) and len(set(seen))==len(seen)
  if actual==claims.keys():
   for path in g.paths:
    labels=[claims[g.edges[i]]['allowed_items'] for i in path]
    ok &= all(len(x)==1 and x==labels[0] for x in labels)
  c.add('P2-paths',ok,'共识 §1.3 P2；格式 §8.2/8.4',{'paths':len(g.paths),'covered':len(set(seen)),'edges':len(g.edges)})
  c.add('P4',c.good('N4a') and all(len(g.sin[s])==len(g.sout[s])==1 for s in g.axes),'共识 §1.3 P4；规则·桥接器；格式 §8.2')
  c.add('P5',c.good('N4b'),'共识 §1.3 P5；规则·桥接器；格式 §8.2')
 else:
  for k in P_IDS: c.note(k,'NOT_APPLICABLE','格式 §8.2','候选类 n_restricted')
 return claims

def check_rectangle(d,g,c):
 r=d['empty_rectangle'];w=r['x1']-r['x0']+1;h=r['y1']-r['y0']+1
 got=maximum_empty(g.occ);c.add('empty-rectangle',min(w,h)>=6 and not(set(cells(r)) & g.occ.keys()) and (w*h,min(w,h))==(got['area'],got['short_side']),'任务·目标（最大面积，同面积最长短边≥6）；格式 §7',{'declared':r,'recomputed':got})
 g.rectangle=got;return got
