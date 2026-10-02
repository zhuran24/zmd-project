#!/usr/bin/env python3
import json,random,pathlib,collections,itertools
OUT=pathlib.Path(__file__).resolve().parent
class Plant:
 def __init__(self,lengths=(1,1,1,1), k=3):
  self.k=k;self.lens=lengths;self.routes=[[-1]*n for n in lengths];self.i=[0]*4;self.o=[0]*4;self.r=[0]*4;self.last=[-100,-100];self.t=0;self.prod=[0]*4;self.sends=[0]*4;self.trace=[];self.blocked=False
 def phi2(self):return 2*(sum(x>=0 for z in (0,2) for x in self.routes[z])+self.i[0]+self.i[1]+self.o[1]+bool(self.r[0])+bool(self.r[1]))+self.o[0]
 def state(self):return (self.t%9,tuple(self.i),tuple(self.o),tuple(self.r),tuple(tuple(r) for r in self.routes),tuple(self.t-x for x in self.last))
 def short(self):return dict(t=self.t,i=self.i[:],o=self.o[:],r=self.r[:],routes=[z[:] for z in self.routes],last=self.last[:],phi2=self.phi2())
 def step(self):
  self.t+=1
  for route in self.routes:
   for j,x in enumerate(route):
    if x>=0:route[j]=min(8,x+1)
  for m,k in enumerate((2,1,1,self.k)):
   if self.r[m]>0:self.r[m]-=1;self.r[m]=-1 if self.r[m]==0 else self.r[m]
   if self.r[m]==-1 and self.o[m]+k<=50:self.o[m]+=k;self.r[m]=0;self.prod[m]+=1
  for z,dst in enumerate((1,2,0,3)):
   rr=self.routes[z]
   if rr[-1]>=8 and self.i[dst]<50:self.i[dst]+=1;rr[-1]=-1
   for p in range(len(rr)-2,-1,-1):
    if rr[p]>=8 and rr[p+1]<0:rr[p+1]=0;rr[p]=-1
  # order of distinct machine outputs commutes since new route item cannot move.
  for m,k in enumerate((2,1,1,self.k)):
   if m==0:
    for z in sorted((0,1),key=lambda z:self.last[z]):
     if self.routes[z][0]<0 and self.o[0]>0:
      self.o[0]-=1;self.routes[z][0]=0;self.last[z]=self.t;self.sends[0]+=1;break
   elif m<3:
    z=m+1
    if self.routes[z][0]<0 and self.o[m]>0:self.o[m]-=1;self.routes[z][0]=0;self.sends[m]+=1
   elif not self.blocked and self.o[m]>0:
    # exactly k independent mature-first-cell exits in 8-step cycle
    if self.t%9<self.k:self.o[m]-=1;self.sends[m]+=1
   if self.r[m]==-1 and self.o[m]+k<=50:self.o[m]+=k;self.r[m]=0;self.prod[m]+=1
  for m in range(4):
   if self.r[m]==0 and self.i[m]:self.i[m]-=1;self.r[m]=8
  # timestamps only matter relative for priority
  mn=min(self.last)
  if mn < self.t-100:self.last=[max(x,self.t-100) for x in self.last]


def run(seed=1,n=300):
 rng=random.Random(seed);found=[];stats=collections.Counter();minloss=0
 for case in range(n):
  lens=tuple(rng.randrange(1,7) for _ in range(4));p=Plant(lens,rng.choice((2,3)))
  mode=case%3
  if mode==0:
   # Sparse threshold stock placed directly by debugging; route inventory ages free.
   p.i=[rng.randrange(3) for _ in range(4)];p.o=[rng.randrange(3) for _ in range(4)];p.r=[rng.choice((0,*range(1,9))) for _ in range(4)]
   for z in p.routes:
    for j in range(len(z)):z[j]=rng.randrange(-1,9)
   while p.phi2()<2*(lens[0]+lens[2])+5:p.i[rng.choice((0,1))]+=1
  elif mode==1:
   p.i=[rng.randrange(51) for _ in range(4)];p.o=[rng.randrange(51) for _ in range(4)];p.r=[rng.choice((-1,0,*range(1,9))) for _ in range(4)]
   for z in p.routes:
    for j in range(len(z)):z[j]=rng.randrange(-1,9)
  else:
   p.i=[50]*4;p.o=[48,49,49,50-p.k];p.r=[rng.randrange(1,9) for _ in range(4)];p.routes=[[8]*n for n in lens]
  initial=p.short();phi0=p.phi2();bound=min(phi0-1,2*(lens[0]+lens[2]+176));lo=phi0;starves=0;periodseen={};past=[];status=None
  for t in range(3000):
   p.blocked=(600<=t<900)
   p.step();lo=min(lo,p.phi2());past.append(p.short() if len(found)<3 else None)
   if p.phi2()<bound and len(found)<3:
    found.append(dict(kind='phi_lower_bound',case=case,initial=initial,bound=bound,end=p.short(),trace=past[-40:]));status='phi';break
   if t>1200:
    state=p.state()
    if state in periodseen:
     a=periodseen[state];span=t-a
     empties=[q for q in p.trace if q[0]>a and any(x==0 for x in q[1])]
     if empties and phi0>=2*(lens[0]+lens[2])+5 and len(found)<3:
      found.append(dict(kind='cycle_starvation',case=case,initial=initial,period=span,end=p.short(),empty=empties[:5],trace=past[-(span+10):]));status='starve'
     stats['cycle']+=1;break
    periodseen[state]=t;p.trace.append((t,p.r[:]))
  stats[mode]+=1;stats[status or 'pass']+=1;minloss=min(minloss,lo-phi0)
 return dict(seed=seed,cases=n,stats=dict(stats),minimum_phi2_loss=minloss,counterexamples=found)
if __name__=='__main__':
 result=run();(OUT/'plant_nine.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='counterexamples'},ensure_ascii=False));print('counterexamples',[(r['kind'],r['case']) for r in result['counterexamples']])
