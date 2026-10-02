#!/usr/bin/env python3
"""S11 one-cell dedicated belt network; standalone step implementation.
Only intended to test timed flow, not to certify geometric embeddability.
Each machine receives all eligible incoming belts in cyclic order, sends <=1.
No bridges, splitters, mergers, boxes or wrong-kind slots.
"""
import json, argparse, hashlib
from pathlib import Path

class M:
 def __init__(self,name,need=None,kind=None,k=1,d=8):
  self.name=name; self.need=need or {}; self.kind=kind; self.k=k; self.d=d
  self.stock={x:50 for x in self.need}; self.out=50 if self.need else 0
  self.ready=None; self.done=False; self.ins=[]; self.outs=[]; self.cursor=0; self.batches=0
 def flush(self):
  if self.done and self.out+self.k<=50:self.out+=self.k;self.done=False;self.ready=None
 def signature(self,t):
  return (tuple(self.stock.values()),self.out,None if self.ready is None else max(0,self.ready-t),self.done,self.cursor,
          tuple(sorted(range(len(self.outs)),key=lambda j:self.outs[j][4])))

class Net:
 def __init__(self,mixed=False):
  self.ms=[];self.routes=[];self.t=0;self.taken={'battery':0,'capsule':0};self.mixed=mixed
  self.sink=self.m('warehouse')
  def chain(src,dst):self.connect(src,dst)
  self.mines=[]; self.blue=[]; self.ore=[]; self.grinds=[]; self.sands=[]; self.flowers=[]
  for i in range(34):
   s=self.m('blue_source'+str(i),kind='blue_ore');f=self.m('blue_furnace'+str(i),{'blue_ore':1},'blue_block');p=self.m('blue_crush'+str(i),{'blue_block':1},'blue_powder')
   chain(s,f);chain(f,p);self.mines.append(s);self.blue.append(p)
  for i in range(18):
   s=self.m('ore_source'+str(i),kind='ore');p=self.m('ore_crush'+str(i),{'ore':1},'ore_powder');chain(s,p);self.mines.append(s);self.ore.append(p)
  for i in range(17):
   g=self.m('blue_grind'+str(i),{'blue_powder':2,'sand_powder':1},'dense_blue');chain(self.blue[2*i],g);chain(self.blue[2*i+1],g);self.grinds.append(g)
  for i in range(9):
   g=self.m('ore_grind'+str(i),{'ore_powder':2,'sand_powder':1},'dense_ore');chain(self.ore[2*i],g);chain(self.ore[2*i+1],g);self.grinds.append(g)
  for typ,number,k in [('sand',11,3),('flower',6,2)]:
   for i in range(number):
    c=self.m(typ+'_seed'+str(i),{typ:1},typ+'_seed',2);a=self.m(typ+'_growA'+str(i),{typ+'_seed':1},typ);b=self.m(typ+'_growB'+str(i),{typ+'_seed':1},typ);p=self.m(typ+'_crush'+str(i),{typ:1},typ+'_powder',k)
    chain(c,a);chain(c,b);chain(a,c);chain(b,p)
    if typ=='sand':self.sands.append(p)
    else:
     g=self.m('flower_grind'+str(i),{'flower_powder':2,'sand_powder':1},'fine_flower');chain(p,g);chain(p,g);self.grinds.append(g);self.flowers.append(g)
  order=list(range(32))
  if mixed:order[0],order[30]=order[30],order[0];order[3],order[31]=order[31],order[3]
  for i,j in enumerate(order):chain(self.sands[i//3],self.grinds[j])
  self.steels=[]
  for i,g in enumerate(self.grinds[:17]):
   f=self.m('steel'+str(i),{'dense_blue':1},'steel');chain(g,f);self.steels.append(f)
  parts=[]
  for i in range(6):
   p=self.m('part'+str(i),{'steel':1},'part');chain(self.steels[i],p);parts.append(p)
  bottles=[]
  for i in range(6):
   p=self.m('bottle'+str(i),{'steel':2},'bottle');bottles.append(p)
   for j in ([6+2*i,7+2*i] if i<5 else [16]):chain(self.steels[j],p)
  self.finals=[]
  for i in range(3):
   p=self.m('battery'+str(i),{'part':10,'dense_ore':15},'battery',d=40)
   for j in range(2):chain(parts[2*i+j],p)
   for j in range(3):chain(self.grinds[17+3*i+j],p)
   chain(p,self.sink);self.finals.append(p)
  for i in range(3):
   p=self.m('capsule'+str(i),{'bottle':10,'fine_flower':10},'capsule',d=40)
   for j in range(2):chain(bottles[2*i+j],p);chain(self.flowers[2*i+j],p)
   chain(p,self.sink);self.finals.append(p)
 def m(self,*a,**k):
  x=M(*a,**k);self.ms.append(x);return x
 def connect(self,s,d):
  # [source,destination,kind,entered_or_None,last_success,total_success]
  r=[s,d,s.kind,-8,-100,0];self.routes.append(r);s.outs.append(r);d.ins.append(r)
 def step(self):
  t=self.t
  for m in self.ms:
   if m.ready is not None and not m.done and m.ready<=t:m.done=True;m.batches+=1
   m.flush()
  for m in self.ms:
   if not m.ins:continue
   n=len(m.ins);start=m.cursor
   for j in range(n):
    idx=(start+j)%n;r=m.ins[idx]
    if r[3] is not None and t-r[3]>=8 and (m is self.sink or m.stock[r[2]]<50):
     if m is self.sink:self.taken[r[2]]+=1
     else:m.stock[r[2]]+=1
     r[3]=None;m.cursor=(idx+1)%n
  for m in self.ms:
   if m.need and m.out==0:continue
   for r in sorted(m.outs,key=lambda r:r[4]):
    if r[3] is None:
     r[3]=t;r[4]=t;r[5]+=1
     if m.need:m.out-=1;m.flush()
     break
  for m in self.ms:
   if m.need and m.ready is None and all(m.stock[k]>=q for k,q in m.need.items()):
    for k,q in m.need.items():m.stock[k]-=q
    m.ready=t+m.d
  self.t+=1
 def signature(self):
  return tuple(m.signature(self.t) for m in self.ms),tuple(None if r[3] is None else min(8,self.t-r[3]) for r in self.routes)
 def counts(self):return dict(taken=self.taken.copy(),sources=[s.outs[0][5] for s in self.mines],finals=[m.batches for m in self.finals],sands=[[r[5] for r in m.outs] for m in self.sands])

def run(mixed,steps):
 n=Net(mixed);seen={};cycle=None
 for t in range(steps):
  if t%8==0:
   sig=hashlib.sha256(repr(n.signature()).encode()).hexdigest()
   if sig in seen:
    prev,counts=seen[sig];now=n.counts();period=t-prev
    cycle=dict(start=prev,end=t,period_steps=period,counts_before=counts,counts_after=now,
      warehouse_rates={k:(now['taken'][k]-counts['taken'][k])*8/period for k in now['taken']},
      mineral_rates=[(a-b)*8/period for a,b in zip(now['sources'],counts['sources'])],
      final_rates=[(a-b)*8/period for a,b in zip(now['finals'],counts['finals'])]);break
   seen[sig]=(t,n.counts())
  n.step()
 return dict(mixed=mixed,machines=sum(bool(m.need) for m in n.ms),routes=len(n.routes),steps=n.t,cycle=cycle,final_counts=n.counts())

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--steps',type=int,default=100000);p.add_argument('--output');a=p.parse_args()
 result=[run(x,a.steps) for x in [False,True]]
 s=json.dumps(result,ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(s+'\n')
 print(s)
