"""从复制的 check_full.py 的占格→端口→桥→通道流程扩展。
桥声明及 physical_channels 从不用于建端口。规则：基地、单位、通道、供电桩。
"""
from collections import defaultdict,Counter
from catalog import *
def pref(p):return (p['unit'],p['side'],p['offset'])
def pjson(p):return dict(zip(['unit','side','offset'],p))
def edge(u,d):
 if d==0:return [(u['x1'],y) for y in range(u['y0'],u['y1']+1)]
 if d==2:return [(u['x0'],y) for y in range(u['y0'],u['y1']+1)]
 if d==1:return [(x,u['y1']) for x in range(u['x0'],u['x1']+1)]
 return [(x,u['y0']) for x in range(u['x0'],u['x1']+1)]
def covers(p,u):return max(p['x0']-5,u['x0'])<=min(p['x0']+6,u['x1']) and max(p['y0']-5,u['y0'])<=min(p['y0']+6,u['y1'])
def rectangle(occ,W=70,H=70,minimum=6):
 """枚举行区间，对每个区间扫描最大连续空列，O(H²W)。同面积取最长短边。"""
 best=(0,0);br=None
 for y0 in range(H):
  free=[True]*W
  for y1 in range(y0,H):
   for x in range(W):free[x]&=(x,y1)not in occ
   h=y1-y0+1
   if h<minimum:continue
   start=0
   for x in range(W+1):
    if x==W or not free[x]:
     w=x-start
     if w>=minimum and (w*h,min(w,h))>best:
      best=(w*h,min(w,h));br=dict(x0=start,y0=y0,x1=x-1,y1=y1)
     start=x+1
 return {'area':best[0],'short_side':best[1],'bounds':br}

class Geometry:
 def __init__(self,d,report):
  self.d=d;self.lay=d['layout'];self.r=report;self.units={};self.types={};self.occ={};self.ports={};self.at={};self.sources={};self.power={};self.axis={};self.channels=[];self.inc=defaultdict(list);self.out=defaultdict(list);self.si=defaultdict(list);self.so=defaultdict(list)
 def check(self,code,ok,basis,detail):self.r.check(code,ok,basis,detail)
 def occupy(self,u,kind):
  uid=u['id'];self.units[uid]=u;self.types[uid]=kind
  cells=[(u['x'],u['y'])] if kind in ['belt','splitter','merger','bridge','gate'] else [(x,y)for x in range(u['x0'],u['x1']+1)for y in range(u['y0'],u['y1']+1)]
  for c in cells:
   self.check('bounds',0<=c[0]<70 and 0<=c[1]<70,'规则·基地；格式§2.2',{'unit':uid,'cell':c})
   self.check('overlap',c not in self.occ,'规则·单位大小；格式§2.2',{'unit':uid,'cell':c,'other':self.occ.get(c)})
   self.occ[c]=uid
 def port(self,u,d,off,typ):
  uid=u['id'];c=(u['x'],u['y']) if self.is_t(uid) else edge(u,d)[off];p=(uid,d,off)
  self.ports[p]=(typ,c);self.at[(c,d)]=(typ,p)
 def is_t(self,uid):return self.types[uid] in ['belt','splitter','merger','bridge','gate']
 def slot(self,p):
  u,s,o=p
  if self.types[u]=='bridge':return (u,'H' if s%2==0 else 'V')
  if u=='CORE' and self.ports.get(p,('',None))[0]=='out':return (u,s,o)
  return (u,)
 def build(self):
  l=self.lay
  for group,kind in [('machines','machine'),('warehouse_outlets','outlet'),('power_poles','pole'),('storage_boxes','box')]:
   for u in l[group]:self.occupy(u,kind)
  self.occupy(l['core'],'core')
  for t in l['transport']:self.occupy(t,t['type'])
  for uid,u in self.units.items():
   typ=self.types[uid]
   if typ=='machine':
    want={'小':(3,3),'中':(5,5),'大':((4,6)if u['Din']%2==0 else(6,4))}[MODELS[u['model']]]
    self.check('machine_shape',(u['x1']-u['x0']+1,u['y1']-u['y0']+1)==want and u['kind']==MODELS[u['model']],'规则·小/中/大制造单位；格式§5.1',{'unit':uid,'expected':want})
   if typ in ['core','box','pole','outlet']:
    want={'core':(9,9),'box':(3,3),'pole':(2,2)}.get(typ)
    if typ=='outlet':want=(1,3)if u['Dout']==0 else(3,1)
    self.check('unit_shape',(u['x1']-u['x0']+1,u['y1']-u['y0']+1)==want,'规则·'+{'core':'协议核心','box':'协议储存箱','pole':'供电桩','outlet':'仓库取货口'}[typ],{'unit':uid,'expected':want})
   if typ in ['machine','box']:
    for s,pt in [(u['Din'],'in'),(opp(u['Din']),'out')]:
     for off in range(len(edge(u,s))):self.port(u,s,off,pt)
    self.power[uid]=[p['id']for p in l['power_poles']if covers(p,u)]
   elif typ=='core':
    for s in [u['Din'],opp(u['Din'])]:
     for off in range(1,min(8,len(edge(u,s)))):self.port(u,s,off,'in')
    for v in u['output_items']:
     if v['offset']<len(edge(u,v['side'])):
      self.port(u,v['side'],v['offset'],'out');self.sources[(uid,v['side'],v['offset'])]=v['item']
   elif typ=='outlet':
    self.check('outlet_boundary',u['x0']==u['x1']==0 if u['Dout']==0 else u['y0']==u['y1']==0,'任务·仓库取货口位置；规则·仓库取货口',{'unit':uid})
    if len(edge(u,u['Dout']))>=2:self.port(u,u['Dout'],1,'out');self.sources[(uid,u['Dout'],1)]=u['item']
   elif typ in ['belt','splitter','merger','gate']:
    ds=([u['in_side'],u['out_side']]if typ=='belt'else [u['in_side'],opp(u['in_side'])]if typ=='gate'else list(range(4)))
    for s in ds:
     pt=('out'if s==u['out_side']else'in')if typ=='merger'else('in'if s==u['in_side']else'out')
     self.port(u,s,0,pt)
  bridges=[u for u in self.units if self.types[u]=='bridge']
  # All facing ports queried before adding any bridge port: adjacent bridges are invalid, not inferred iteratively.
  pending=[]
  for uid in bridges:
   u=self.units[uid];c=(u['x'],u['y'])
   for s in range(4):
    n=self.occ.get(nb(c,s));self.check('N4b',n not in bridges,'共识§三.3 N4b；格式§6/8.2',{'bridge':uid,'neighbor':n})
   for axis,ends,key in [('H',(0,2),'H_in'),('V',(1,3),'V_in')]:
    f={s:self.at[(nb(c,s),opp(s))][0]for s in ends if (nb(c,s),opp(s))in self.at}
    valid=not f or len(f)==2 and set(f.values())=={'in','out'}
    # 单端也由已接邻端唯一推导；受限类仍拒绝，真实已接边不可消失。
    ins=(next((s for s in ends if f.get(s)=='out'),None) if valid else
         next((s if typ=='out' else opp(s) for s,typ in f.items()),None) if len(f)==1 else None)
    self.axis[(uid,axis)]=ins
    self.check('N4a',valid and u[key]==ins,'规则·桥接器；共识§1.1.3、三.3；格式§6',{'bridge':uid,'axis':axis,'facing':f,'derived':ins,'declared':u[key]})
    if ins is not None:pending.extend([(u,ins,'in'),(u,opp(ins),'out')])
  for u,s,pt in pending:self.port(u,s,0,pt)
  for p,(pt,c)in sorted(self.ports.items()):
   if pt!='out':continue
   v=self.at.get((nb(c,p[1]),opp(p[1])))
   if v and v[0]=='in' and (self.is_t(p[0])or self.is_t(v[1][0])):
    q=v[1];k=len(self.channels);self.channels.append((p,q));self.out[p[0]].append(k);self.inc[q[0]].append(k);self.so[self.slot(p)].append(k);self.si[self.slot(q)].append(k)
  decl={(pref(c['from']),pref(c['to'])):c for c in self.d['design']['physical_channels']};actual=set(self.channels)
  self.check('N5a',set(decl)==actual,'规则·通道；约束#11 端口对接；共识 N5a；格式§8.1',{'missing':[{'from':pjson(a),'to':pjson(b)}for a,b in sorted(actual-set(decl))],'extra':[{'from':pjson(a),'to':pjson(b)}for a,b in sorted(set(decl)-actual)]})
  self.decl=decl;self.cd=[decl.get(e)for e in self.channels]
  for u in self.units:
   self.check('N1',self.is_t(u)or len(self.out[u])<2 or all(self.types[self.channels[i][1][0]]!='merger'for i in self.out[u]),'约束#5 取货分级；共识 N1；格式§8.2',{'unit':u,'outputs':self.out[u]})
   self.check('N2',len(self.inc[u])<2 or all(self.types[self.channels[i][0][0]]!='splitter'for i in self.inc[u]),'规则·存货优先级；约束#6 密集结点；共识 N2',{'unit':u,'inputs':self.inc[u]})
   if self.types[u]=='gate':self.check('N3a',self.units[u]['cum']is None or not(self.inc[u]or self.out[u]),'约束#29 准入累计；N3a+N5b',{'unit':u,'cum':self.units[u]['cum']})
  self.possibilities();self.reachability();self.paths()
  self.maximum=rectangle(self.occ)
  r=self.d['empty_rectangle'];w=r['x1']-r['x0']+1;h=r['y1']-r['y0']+1
  clean=all((x,y)not in self.occ for x in range(r['x0'],r['x1']+1)for y in range(r['y0'],r['y1']+1))
  self.check('maximum_empty_rectangle',clean and min(w,h)>=6 and(w*h,min(w,h))==(self.maximum['area'],self.maximum['short_side']),'任务·目标；格式§7',{'claimed':r,'computed':self.maximum})
  return self
 def possibilities(self):
  emit=defaultdict(set);arrive=defaultdict(set)
  for p,item in self.sources.items():emit[self.slot(p)].add(item)
  changed=True
  while changed:
   changed=False
   for uid,u in self.units.items():
    typ=self.types[uid];slots=[(uid,'H'),(uid,'V')]if typ=='bridge'else[(uid,)]
    for s in slots:
     if typ=='machine':
      new=set().union(*(set(b)for rid,(m,a,b,t)in RECIPES.items()if m==u['model']and(rid in u['recipe_ids']or set(a)<=arrive[s])))
     elif self.is_t(uid)or typ=='box':
      new=set(arrive[s])
      if typ=='gate'and u['filter']is not None:new&={u['filter']}
     else:continue
     if not new<=emit[s]:emit[s]|=new;changed=True
   for p,q in self.channels:
    # Filter拒收影响到达 gate 的种类；通道风险仍按上游可出物品报告。
    new=emit[self.slot(p)];v=self.units[q[0]]
    if self.types[q[0]]=='gate'and v['filter']is not None:new=new&{v['filter']}
    if not new<=arrive[self.slot(q)]:arrive[self.slot(q)]|=new;changed=True
  self.emit=emit;self.arrive=arrive
  for uid,u in self.units.items():
   if self.types[uid]=='machine':
    allin=set().union(*(set(a)for m,a,b,t in RECIPES.values()if m==u['model']));design=set().union(*(set(RECIPES[r][1])for r in u['recipe_ids']))
    self.check('wrong_material',not(arrive[(uid,)]-allin),'约束#20 存货误料停机与可用台数；格式§8.1',{'unit':uid,'possible_wrong':sorted(arrive[(uid,)]-allin)})
    self.check('off_recipe',not(arrive[(uid,)]-design),'规则·配方/缓存格；格式§5.1/8.1',{'unit':uid,'possible_off_design':sorted(arrive[(uid,)]-design)})
   if self.types[uid]=='gate'and u['filter']is not None:
    for i in self.inc[uid]:
     p,q=self.channels[i];s=self.slot(p)
     for item in emit[s]-{u['filter']}:
      alt=[j for j in self.so[s]if j!=i and (self.types[self.channels[j][1][0]]!='gate'or self.units[self.channels[j][1][0]]['filter']in(None,item))]
      self.check('N3b',bool(alt),'共识 N3b；格式§8.2；规则·物品准入口',{'gate':uid,'upstream':pjson(p),'blocked_item':item,'alternatives':alt})
  for i,(p,q)in enumerate(self.channels):
   if self.cd[i]is not None:self.check('channel_possible_items',emit[self.slot(p)]<=set(self.cd[i]['allowed_items']),'格式§8.1；设计物品集不是游戏过滤器',{'channel':self.cd[i]['id'],'outside_allowed':sorted(emit[self.slot(p)]-set(self.cd[i]['allowed_items']))})
 def reachability(self):
  adj=defaultdict(set);rev=defaultdict(set);starts=set();ends=set();ts=set()
  for p,q in self.channels:
   a,b=self.slot(p),self.slot(q)
   if self.is_t(p[0]):ts.add(a)
   if self.is_t(q[0]):ts.add(b)
   if self.is_t(p[0])and self.is_t(q[0]):adj[a].add(b);rev[b].add(a)
   elif not self.is_t(p[0]):starts.add(b)
   else:ends.add(a)
  def reach(seed,graph):
   seen=set(seed);todo=list(seed)
   while todo:
    for v in graph[todo.pop()]:
     if v not in seen:seen.add(v);todo.append(v)
   return seen
  f=reach(starts,adj);b=reach(ends,rev)
  self.check('transport_endpoints',ts<=f&b,'格式§8.2；共识 N5；纯运输环不能伪装送料',{'no_source':sorted(ts-f),'no_sink':sorted(ts-b)})
 def paths(self):
  self.path_decomposition=[]
  if self.d['design']['class']!='p2p':
   for c in PIDS:self.r.na(c,'格式§8.2','class=n_restricted，不声称 P 类')
   return
  self.check('P1',all(t['type']in['belt','bridge']for t in self.lay['transport'])and not self.lay['storage_boxes'],'共识§1.3 P1；格式§8.2',{})
  self.check('P6',all(len(u['recipe_ids'])==1 for u in self.lay['machines']if u['model']in['粉碎机','采种机']),'共识 P6；格式§8.2',{})
  covered=[]
  for i,(p,q)in enumerate(self.channels):
   if self.is_t(p[0]):continue
   path=[];j=i
   while j not in path:
    path.append(j);a,b=self.channels[j]
    if not self.is_t(b[0]):break
    s=self.slot(b);nxt=self.so[s]
    if len(nxt)!=1 or len(self.si[s])!=1:break
    j=nxt[0]
   dest=self.channels[path[-1]][1];valid=not self.is_t(dest[0]);kinds=[self.cd[k]['allowed_items']if self.cd[k]else[]for k in path]
   self.check('P2_structure',valid and all(len(k)==1 for k in kinds)and all(k==kinds[0]for k in kinds),'共识 P2；格式§8.2',{'path_indices':path,'terminal':pjson(dest),'items':kinds})
   covered+=path;self.path_decomposition.append(path)
  self.check('P2_structure',Counter(covered)==Counter(range(len(self.channels))),'格式§8.2 路径须完整分解且覆盖全部结构通道',{'uncovered':sorted(set(range(len(self.channels)))-set(covered))})
  self.r.blocked('P2','共识 P2；格式§8.2','路径及物品标签见P2_structure；等速尚待精确流核验')
  self.r.alias('P4','N4a','共识 P4；正流另见 N5b/P3')
  self.r.alias('P5','N4b','共识 P5')
