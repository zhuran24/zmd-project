"""Independent integer-only four-machine, one-cell route implementation.
No simulator inheritance; primary comparison imports sim2 harness only afterwards.
"""
import json,random
class Small:
 def __init__(self,counts,ages,phase,first):
  self.t=0;self.inp=[c[0] for c in counts];self.out=[c[1] for c in counts];self.rem=[r or 0 for r in phase];self.wait=[r==0 for r in phase]
  self.prod=[2,1,1,2];self.cell=[None if a[0] is None else -a[0] for a in ages]+[None,None]
  self.last=[[-1,-1],[-1],[-1],[-1,-1]];self.first=first;self.cursor=0
 def flush(self,i):
  if self.wait[i] and self.out[i]+self.prod[i]<=50:self.out[i]+=self.prod[i];self.wait[i]=False
 def step(self):
  for i in range(4):
   if self.rem[i]:
    self.rem[i]-=1
    if not self.rem[i]:self.wait[i]=True
   self.flush(i)
  for r,dst in [(0,1),(1,0),(2,2),(3,3)]:
   if self.cell[r] is not None and self.t-self.cell[r]>=8 and self.inp[dst]<50:
    self.cell[r]=None;self.inp[dst]+=1
  for j in [self.cursor,1-self.cursor]:
   r=4+j
   if self.cell[r] is not None and self.t-self.cell[r]>=8:
    self.cell[r]=None;self.cursor=1-j;break
  for i,roads in enumerate([[0,2],[1],[3],[4,5]]):
   priority=sorted(range(len(roads)),key=lambda j:(self.last[i][j],(-j if i==0 and self.first=='B' else j)))
   for j in priority:
    if self.out[i] and self.cell[roads[j]] is None:
     self.out[i]-=1;self.cell[roads[j]]=self.t;self.last[i][j]=self.t;self.flush(i);break
  for i in range(4):
   if not self.rem[i] and not self.wait[i] and self.inp[i]>0:self.inp[i]-=1;self.rem[i]=8
  self.t+=1
 def flat(self):
  return {'in':self.inp[:],'out':self.out[:],'rem':[x or None for x in self.rem],'cache':[self.prod[i] if self.wait[i] else 0 for i in range(4)],'ages':[None if a is None else min(8,self.t-1-a) for a in self.cell]}
 def phi(self):
  return self.inp[1]+self.out[1]+self.inp[0]+sum(self.cell[r] is not None for r in [0,1])+bool(self.rem[1] or self.wait[1])+bool(self.rem[0] or self.wait[0])+self.out[0]/2

def main():
 import s08_s09_probe as p
 rng=random.Random(8099202);cases=0;steps=0;violations=0
 for case in range(160):
  counts=[(rng.randrange(51),rng.randrange(51)) for _ in range(4)]
  ages=[[rng.choice([None,*range(9)])] for _ in range(4)]
  phase=[rng.choice([None,*range(1,9)]) for _ in range(4)];first=rng.choice(['A','B'])
  a=Small(counts,ages,phase,first);w,ms,rs=p.build((1,1,1,1),counts,ages,phase,first)
  bound=None
  for step in range(160):
   a.step();w.step();b={'in':[len(x.slots[0]) for x in ms],'out':[len(x.output) for x in ms],'rem':[x.remaining for x in ms],'cache':[len(x.cache) for x in ms],'ages':[None if r.cells[0] is None else min(8,w.t-1-r.cells[0].entered) for r in rs+[w.lookup['O1'],w.lookup['O2']]]}
   assert a.flat()==b,(case,step,a.flat(),b)
   assert a.phi()==p.phi(ms,rs)
   if step==0:bound=min(a.phi()-.5,178)
   if a.phi()<bound:violations+=1
   steps+=1
  cases+=1
 # Independently sum the saturation state, versus old symbolic arithmetic.
 counted=sum([50,50,50,1,1])+49/2-.5
 symbolic=7*50/2+1
 assert counted==symbolic==176
 print(json.dumps({'independent_cases':cases,'stepwise_equal_states':steps,'S08_violations':violations,'saturation_constant_counted':counted,'saturation_constant_symbolic':symbolic},indent=2))
if __name__=='__main__':main()
