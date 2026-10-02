#!/usr/bin/env python3
"""Hard-legal sequential A* with rip-up; failed nets remain explicit and are never claimed."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,sys,time,heapq,random,hashlib,copy
from pathlib import Path
from collections import defaultdict,Counter
from fractions import Fraction
from pack_factory import cells,edge,C,BASE,MC,D,machine
from static_check import largest_rect
ROOT=BASE.parents[3]

def ports(l):
 out=defaultdict(list);inc=defaultdict(list)
 for u in l['machines']:
  for io,di in [(inc,u['Din']),(out,(u['Din']+2)%4)]:
   for off,(x,y) in enumerate(edge(u,di)):
    io[u['id']].append(((x+D[di][0],y+D[di][1]),di,dict(unit=u['id'],side=di,offset=off)))
 for u in l['warehouse_outlets']:
  di=u['Dout'];x,y=edge(u,di)[1];out[u['id']].append(((x+D[di][0],y+D[di][1]),di,dict(unit=u['id'],side=di,offset=1)))
 u=l['core']
 for z in u['output_items']:
  di=z['side'];off=z['offset'];x,y=edge(u,di)[off];out['CORE'].append(((x+D[di][0],y+D[di][1]),di,dict(unit='CORE',side=di,offset=off)))
 for di in [u['Din'],(u['Din']+2)%4]:
  for off in range(1,8):
   x,y=edge(u,di)[off];inc['CORE'].append(((x+D[di][0],y+D[di][1]),di,dict(unit='CORE',side=di,offset=off)))
 return out,inc

def choose_power(l,rect):
 if l['power_poles']:
  return [u['id'] for u in l['machines'] if not any(u['x0']<=p['x0']+6 and u['x1']>=p['x0']-5 and u['y0']<=p['y0']+6 and u['y1']>=p['y0']-5 for p in l['power_poles'])]
 occupied=set(q for u in l['machines']+l['warehouse_outlets']+[l['core'],rect]+l['transport'] for q in cells(u))
 optout,optin=ports(l)
 body=set(q for u in l['machines']+l['warehouse_outlets']+[l['core'],rect] for q in cells(u))
 ni=Counter(f['target'] for f in C['feeds']);no=Counter(f['source'] for f in C['feeds'])
 portsets=[]
 for mapping,needs in [(optout,no),(optin,ni)]:
  for uid,arr in mapping.items():
   pts={c for c,di,p in arr if 0<=c[0]<70 and 0<=c[1]<70 and c not in body}
   portsets.append((pts,max(0,len(pts)-needs[uid])))
 opts=[]
 for x in range(1,69):
  for y in range(1,69):
   footprint={(x,y),(x+1,y),(x,y+1),(x+1,y+1)}
   if footprint & occupied:continue
   if any(len(footprint&pts)>spare for pts,spare in portsets):continue
   covers={u['id'] for u in l['machines'] if u['x0']<=x+6 and u['x1']>=x-5 and u['y0']<=y+6 and u['y1']>=y-5}
   if covers:opts.append((x,y,footprint,covers))
 missing={u['id'] for u in l['machines']};poles=[]
 while missing:
  choices=[(len(cc&missing),len(cc),-abs(x-35)-abs(y-35),x,y,fp,cc) for x,y,fp,cc in opts if not fp&occupied and all(len(fp&pts)<=spare for pts,spare in portsets)]
  if not choices or max(q[0] for q in choices)==0:break
  _,_,_,x,y,fp,cc=max(choices,key=lambda a:a[:3]);poles.append(dict(id=f'POWER{len(poles)+1}',x0=x,y0=y,x1=x+1,y1=y+1,orientation=0));occupied|=fp;missing-=cc
  portsets=[(pts-fp,spare-len(pts&fp)) for pts,spare in portsets]
 l['power_poles']=poles
 return sorted(missing)

class Router:
 def __init__(self,l,rect,seed=1):
  self.l=l;self.rect=rect;self.rng=random.Random(seed);self.out,self.inc=ports(l)
  self.blocked=set(q for u in l['machines']+l['warehouse_outlets']+[l['core'],rect]+l['power_poles'] for q in cells(u))
  self.paths={};self.usage=defaultdict(dict);self.locked=set();self.feeds={f['id']:f for f in C['feeds']}
  self.history=defaultdict(float)
 def free(self,c):return 0<=c[0]<70 and 0<=c[1]<70 and c not in self.blocked
 def add(self,fid,p):
  self.paths[fid]=p
  for x,y,ins,outs in p['cells']:self.usage[(x,y)][fid]=(ins,outs)
 def rip(self,fid):
  p=self.paths.pop(fid,None)
  if p:
   for x,y,*_ in p['cells']:
    self.usage[(x,y)].pop(fid,None)
    if not self.usage[(x,y)]:self.usage.pop((x,y))
  return p
 def compatible(self,c,ins,outs):
  old=self.usage.get(c,{})
  if not old:return True
  if len(old)!=1 or outs!=(ins+2)%4:return False
  oi,oo=next(iter(old.values()))
  return oo==(oi+2)%4 and ins%2!=oi%2
 def initial(self):
  tr={(t['x'],t['y']):t for t in self.l['transport']};targets={}
  for uid,arr in self.inc.items():
   for c,di,p in arr:targets[(c,(di+2)%4)]=p
  todo=defaultdict(list)
  for f in C['feeds']:todo[f['source'],f['target']].append(f['id'])
  for uid,arr in self.out.items():
   for c,di,p in arr:
    cc=c;ins=(di+2)%4;path=[];seen=set();target=None
    while cc in tr and cc not in seen:
     seen.add(cc);t=tr[cc]
     if t['type']!='belt' or t['in_side']!=ins:break
     outs=t['out_side'];path.append((*cc,ins,outs))
     if (cc,outs) in targets:target=targets[cc,outs];break
     cc=(cc[0]+D[outs][0],cc[1]+D[outs][1]);ins=(outs+2)%4
    if target and todo[uid,target['unit']]:
     fid=todo[uid,target['unit']].pop(0);self.add(fid,dict(source=p,target=target,cells=path));self.locked.add(fid)
  claimed={c for p in self.paths.values() for c in [(x,y) for x,y,*_ in p['cells']]}
  assert set(tr)==claimed,('untraced fixed transport',set(tr)-claimed)
 def route(self,fid,noise=0):
  f=self.feeds[fid];starts=[(c,(di+2)%4,p) for c,di,p in self.out[f['source']] if self.free(c)]
  goals=defaultdict(list)
  for c,di,p in self.inc[f['target']]:
   if self.free(c):goals[c].append(((di+2)%4,p))
  if not starts or not goals:return None
  gs=list(goals)
  def heur(c):return min(abs(c[0]-a)+abs(c[1]-b) for a,b in gs)
  pq=[];best={};prev={};origin={};serial=0
  for c,i,p in starts:
   state=(c[0],c[1],i);best[state]=0;origin[state]=p;heapq.heappush(pq,(heur(c),0,serial,state));serial+=1
  finish=None;finish_port=None
  while pq:
   _,score,_,st=heapq.heappop(pq)
   if score!=best.get(st):continue
   x,y,ins=st;c=(x,y)
   dirs=[(ins+2)%4] if self.usage.get(c) else [0,1,2,3]
   if c in goals:
    for outs,p in goals[c]:
     if outs!=ins and self.compatible(c,ins,outs):finish=(st,outs);finish_port=p;break
    if finish:break
   for outs in dirs:
    if outs==ins or not self.compatible(c,ins,outs):continue
    nc=(x+D[outs][0],y+D[outs][1])
    if not self.free(nc):continue
    ni=(outs+2)%4
    old=self.usage.get(nc,{})
    if len(old)>1:continue
    if old:
     oi,oo=next(iter(old.values()))
     if oo!=(oi+2)%4 or oi%2==ni%2:continue
    nst=(*nc,ni)
    cost=(0.72 if self.usage.get(c) else 1)+self.history[c]+(self.rng.random()*noise if noise else 0)
    ns=score+cost
    if ns<best.get(nst,float('inf')):
     best[nst]=ns;prev[nst]=(st,outs);origin[nst]=origin[st]
     heapq.heappush(pq,(ns+0.7*heur(nc),ns,serial,nst));serial+=1
  if finish is None:return None
  st,outs=finish;path=[(st[0],st[1],st[2],outs)]
  while st in prev:
   pst,po=prev[st];path.append((pst[0],pst[1],pst[2],po));st=pst
  path.reverse()
  if len({(x,y) for x,y,*_ in path})!=len(path):return None
  return dict(source=origin[st],target=finish_port,cells=path)
 def score(self):
  ore=sum(self.feeds[fid]['item'] in ['源矿','蓝铁矿'] for fid in self.paths)
  return(len(self.paths),ore,-len(self.usage))
 def search(self,iters=25):
  self.initial();bestpaths=copy.deepcopy(self.paths);bestscore=self.score();log=[]
  print('initial',bestscore,flush=True)
  allids=list(self.feeds)
  for it in range(iters):
   # Respect local paths; all other completed routes may be re-routed.
   if it:
    movable=[f for f in self.paths if f not in self.locked]
    self.rng.shuffle(movable)
    n=max(5,len(movable)//3) if it%7 else len(movable)
    for fid in movable[:n]:self.rip(fid)
   ids=[f for f in allids if f not in self.paths]
   self.rng.shuffle(ids)
   def distance(fid):
    f=self.feeds[fid];a=self.out[f['source']];b=self.inc[f['target']]
    return min(abs(x[0][0]-y[0][0])+abs(x[0][1]-y[0][1]) for x in a for y in b)
   if it%3==0:ids.sort(key=lambda fid:(self.feeds[fid]['item'] not in ['源矿','蓝铁矿'],distance(fid)))
   elif it%3==1:ids.sort(key=distance)
   for fid in ids:
    p=self.route(fid,noise=0.15 if it else 0)
    if p:self.add(fid,p)
   score=self.score();log.append(dict(iteration=it,score=score))
   if score>bestscore:
    bestscore=score;bestpaths=copy.deepcopy(self.paths)
    save_raw(self,BASE/'证据/routed-best.json',log)
   print('routing',it,score,'best',bestscore,flush=True)
   if len(self.paths)==325:break
  self.paths={};self.usage=defaultdict(dict)
  for fid,p in bestpaths.items():self.add(fid,p)
  return log

def save_raw(r,path,log):
 path.write_text(json.dumps(dict(layout=r.l,reserved_rectangle=r.rect,paths=r.paths,score=r.score(),log=log),ensure_ascii=False,indent=2))

def export(r,path):
 l=copy.deepcopy(r.l);l['transport']=[];channels=[];feeds=[];byedge={};directions={};transport_ids={c:f'X_{c[0]}_{c[1]}' for c in r.usage}
 for (x,y),uu in sorted(r.usage.items()):
  if len(uu)==1:
   i,o=next(iter(uu.values()));l['transport'].append(dict(id=transport_ids[x,y],x=x,y=y,type='belt',in_side=i,out_side=o))
  else:
   a={i%2:i for i,o in uu.values()};l['transport'].append(dict(id=transport_ids[x,y],x=x,y=y,type='bridge',H_in=a[0],V_in=a[1]))
 for fid,p in sorted(r.paths.items()):
  f=r.feeds[fid];prev=p['source'];cp=[]
  for x,y,i,o in p['cells']:
   dest=dict(unit=transport_ids[x,y],side=i,offset=0);cid=f'PC{len(channels):05d}';channels.append(dict(id=cid,**{'from':prev,'to':dest},allowed_items=[f['item']]))
   byedge[(prev['unit'],prev['side'],dest['unit'],dest['side'])]=cid;cp.append(cid);prev=dict(unit=transport_ids[x,y],side=o,offset=0)
  cid=f'PC{len(channels):05d}';channels.append(dict(id=cid,**{'from':prev,'to':p['target']},allowed_items=[f['item']]));cp.append(cid)
  feeds.append(dict(id=fid,**{'from':p['source'],'to':p['target']},item=f['item'],rate=f['rate'],path=cp))
 # The complete physical graph includes both directions between neighboring bridges.
 brids={u['id'] for u in l['transport'] if u['type']=='bridge'};reverse=[]
 for e in list(channels):
  if e['from']['unit'] in brids and e['to']['unit'] in brids:
   cid=f'PC{len(channels):05d}';channels.append(dict(id=cid,**{'from':e['to'],'to':e['from']},allowed_items=e['allowed_items']));reverse.append(cid)
 paths=ROOT/'求解器/候选约束轮次/第107-109轮/前提快照';fps={k:hashlib.sha256((paths/name).read_bytes()).hexdigest() for k,name in [('rules','《明日方舟：终末地》游戏规则.txt'),('task','求解任务.txt'),('constraints','求解约束.txt')]}
 occ={q for u in l['machines']+l['warehouse_outlets']+l['transport']+l['power_poles']+[l['core']] for q in cells(u)}
 maxr=largest_rect(occ)
 restriction=dict(id='fixed-s2',source=['dynamic','shape'],statement='固定 S2 第2节的230台机器、325条进路、单机配方与精确平均流量。',coverage_loss='不覆盖其他接法、混合配方或台数。',release_obligations='重新证明运行并构造布局。',failure_scope='仅本文件明确的摆放与已布路径；缺路不证明其他布局无解。')
 data=dict(schema='full-factory-static-s2b-v1',candidate_id='construction-b-third-partial',source_fingerprints=fps,provenance=[dict(path='求解器/候选约束轮次/第107-109轮/临时规则.md',sha256=hashlib.sha256((paths.parent/'临时规则.md').read_bytes()).hexdigest())],targets={'高容谷地电池':'3/5','精选荞愈胶囊':'11/20'},layout=l,empty_rectangle=maxr['rectangle'] or r.rect,design={'class':'s2b_p2p','physical_channels':channels,'logical_feeds':feeds,'bridge_reverse_channels':reverse,'restrictions':[restriction]},flow_witness=None)
 if not reverse:
  data['schema']='full-factory-static-v1';data['design']['class']='p2p';data['design'].pop('bridge_reverse_channels')
  statements={'N1':'不使用汇流器。','N2':'不使用分流器。','N3a':'不使用物品准入口。','N3b':'不使用物品准入口。','N4a':'桥接器每条接通轴两端一取一存，未用轴无通道。','N4b':'桥接器不正交相邻。','N5a':'列举全部自动形成的物理通道。','N5b':'要求全部结构通道有正平均流量；此要求须由检查器核验。','P1':'只用传送带和桥接器，不用协议储存箱。','P2':'每条已列进路为端口到端口的单物品独立路径。','P3':'要求每条结构通道都有正流量，不能从声明推为已实现。','P4':'每条桥轴仅有本路前后关系。','P5':'桥接器不正交相邻。','P6':'粉碎机和采种机均为单配方设计。'}
  data['design']['restrictions'] += [dict(id=k,source=['dynamic','shape'],statement=v,coverage_loss='限定于本文件记录的点对点单配方接法。',release_obligations='解除后需重做通道、流量与运行检查。',failure_scope='静态要求不是通过声明；失败仅拒绝这份固定候选。') for k,v in statements.items()]
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');return data

if __name__=='__main__':
 p=Path(sys.argv[1]);d=json.loads(p.read_text());l=d['layout'];rect=d['reserved_rectangle']
 missing_power=choose_power(l,rect);print('power',len(l['power_poles']),missing_power,flush=True)
 r=Router(l,rect,seed=int(sys.argv[3]) if len(sys.argv)>3 else 1)
 log=r.search(int(sys.argv[2]) if len(sys.argv)>2 else 30)
 save_raw(r,BASE/'证据/routed-final.json',log);export(r,BASE/'候选布局.json')
