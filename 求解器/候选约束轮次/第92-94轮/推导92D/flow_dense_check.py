#!/usr/bin/env python3
"""Dense planting module, independent integer-count engine vs sim2 per step.
External sinks prescribe availability; this is a transport-service probe,
not a claim that these exact sink schedules are another legal factory.
"""
import sys,random,json,importlib.util
from pathlib import Path
sys.dont_write_bytecode=True
p=Path('/home/zhuran24/zmd-research-fresh/求解器/规则修订/2026-09-30-迟滞/sim2/simulator.py')
spec=importlib.util.spec_from_file_location('dense_sim2',p);s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s)

class Plant:
 def __init__(self,k,n,seed,mode):
  self.rng=random.Random(seed);self.k=k;self.n=n;self.mode=mode;self.t=0
  self.need=['plant','seed','seed','plant'];self.prod=['seed','plant','plant','powder'];self.qty=[2,1,1,k]
  self.stock=[50]*4;self.out=[50]*4;self.remaining=[self.rng.randrange(8)for _ in range(4)];self.done=[x==0 for x in self.remaining]
  self.routes=[];self.ins=[[]for _ in range(4+n)];self.outs=[[]for _ in range(4)];self.cursor=[0]*(4+n);self.last={};self.received=[0]*n
  for source,target in [(0,1),(0,2),(1,0),(2,3)]+[(3,4+i)for i in range(n)]:
   length=self.rng.randrange(1,4) if target<4 else 1
   cells=[self.rng.randrange(9)for _ in range(length)];idx=len(self.routes)
   self.routes.append([source,target,cells]);self.outs[source].append(idx);self.ins[target].append(idx);self.last[idx]=-1
  for arr in self.outs+self.ins:self.rng.shuffle(arr)
  if seed>=100:
   corner=seed-100
   self.remaining=[[7,7,7,0],[0,0,0,7],[7,7,7,7],[0,0,0,0],
                   [7,0,0,0],[0,7,0,0],[0,0,7,0],[1,7,1,7]][corner]
   self.done=[x==0 for x in self.remaining]
   for idx,(_,target,cells)in enumerate(self.routes):
    length=(1 if corner%2==0 else 3)if target<4 else 1
    self.routes[idx][2]=[8 if corner!=7 or j%2==0 else 0 for j in range(length)]
  self.deadline=[None]*n;self.max_wait=0;self.min_stock=[50]*4;self.min_out=[50]*4;self.send_log=[];self.failure=None
 def sink_open(self,i,t):
  if 200<=t<400 or 750<=t<1100:return False
  periods=[9,11,40];period=periods[(i+self.mode)%3]
  if self.mode==3:return True
  return (t+3*i+self.mode)%period==0
 def flush(self,i):
  if self.done[i] and self.out[i]+self.qty[i]<=50:
   self.out[i]+=self.qty[i];self.done[i]=False
 def settle(self,idx):
  cells=self.routes[idx][2]
  for j in range(len(cells)-2,-1,-1):
   if cells[j] is not None and cells[j]>=8 and cells[j+1] is None:cells[j+1]=0;cells[j]=None
 def step(self):
  t=self.t
  for i in range(4):
   if self.remaining[i]:
    self.remaining[i]-=1
    if not self.remaining[i]:self.done[i]=True
   self.flush(i)
  for idx in range(len(self.routes)):self.settle(idx)
  for target,arr in enumerate(self.ins):
   start=self.cursor[target]
   for j in range(len(arr)):
    ix=(start+j)%len(arr);idx=arr[ix];cells=self.routes[idx][2]
    if cells[-1] is not None and cells[-1]>=8 and (self.stock[target]<50 if target<4 else self.sink_open(target-4,t)):
     if target<4:self.stock[target]+=1
     else:self.received[target-4]+=1
     cells[-1]=None;self.cursor[target]=(ix+1)%len(arr);self.settle(idx)
  head_empty=[self.routes[1][2][0] is None,self.routes[3][2][0] is None]
  for j in range(self.n):
   if self.routes[4+j][2][0] is None and self.deadline[j] is None:self.deadline[j]=t
  for i in range(4):
   if self.out[i]:
    for idx in sorted(self.outs[i],key=lambda idx:self.last[idx]):
     if self.routes[idx][2][0] is None:
      self.routes[idx][2][0]=0;self.out[i]-=1;self.last[idx]=t;self.send_log.append((t,idx));self.flush(i);break
  for i in range(4):
   if not self.remaining[i] and not self.done[i] and self.stock[i]:self.stock[i]-=1;self.remaining[i]=8
  if head_empty[0] and self.routes[1][2][0] is None:self.fail('C_to_CB_not_same_step')
  if head_empty[1] and self.routes[3][2][0] is None:self.fail('B_to_BK_not_same_step')
  for i in (2,3):
   if self.stock[i]<49:self.fail('B_or_K_stock_below49')
  if self.out[3]<50-self.k:self.fail('K_output_below_50-k')
  if any(not (self.remaining[i] or self.done[i])for i in range(4)):self.fail('empty_cache_end_of_step')
  for j in range(self.n):
   if self.deadline[j] is not None:
    wait=t-self.deadline[j]
    if wait>self.n-1:self.fail('K_head_deadline')
    if self.routes[4+j][2][0] is not None:self.max_wait=max(self.max_wait,wait);self.deadline[j]=None
  self.min_stock=[min(a,b)for a,b in zip(self.min_stock,self.stock)];self.min_out=[min(a,b)for a,b in zip(self.min_out,self.out)]
  for _,_,cells in self.routes:
   for j in range(len(cells)):
    if cells[j] is not None:cells[j]+=1
  self.t+=1
 def fail(self,reason):
  if self.failure is None:self.failure=dict(t=self.t,reason=reason,stock=self.stock[:],out=self.out[:],remaining=self.remaining[:],done=self.done[:])

def replay(k,n,seed,mode,steps):
 a=Plant(k,n,seed,mode);nodes=[];machines=[];belts=[];sinks=[]
 class Terminal(s.Warehouse):
  def __init__(self,i):super().__init__('terminal'+str(i));self.i=i
  def can_accept(self,item,w):return a.sink_open(self.i,w.t)
 for i,name in enumerate(['C','A','B','K']):
  recipe=s.Recipe(name,((a.need[i],1),),a.prod[i],a.qty[i],8)
  m=s.Machine(name,recipes=[recipe]);m.slots=[[s.Item(a.need[i])for _ in range(50)]];m.output=[s.Item(a.prod[i])for _ in range(50)]
  if a.done[i]:m.cache=[s.Item(a.prod[i])for _ in range(a.qty[i])]
  else:m.running=recipe;m.remaining=a.remaining[i]
  machines.append(m);nodes.append(m)
 for i in range(n):u=Terminal(i);sinks.append(u);nodes.append(u)
 for idx,(src,dst,cells)in enumerate(a.routes):
  b=s.Belt('route'+str(idx),len(cells));b.cells=[s.Item(a.prod[src],-age)for age in cells]
  machines[src].connect(b,a.outs[src].index(idx));b.connect((machines+sinks)[dst],a.ins[dst].index(idx));belts.append(b);nodes.append(b)
 schedule={'order':[b.name for b in belts]+[m.name for m in machines+sinks]};w=s.World(nodes,schedule=schedule)
 initial=dict(lengths=[len(r[2])for r in a.routes],ages=[r[2][:]for r in a.routes],remaining=a.remaining[:],done=a.done[:],send_order=[x[:]for x in a.outs])
 for t in range(steps):
  a.step();w.step()
  for i,m in enumerate(machines):
   assert a.stock[i]==len(m.slots[0]),(k,n,seed,mode,t,'stock',i)
   assert a.out[i]==len(m.output),(k,n,seed,mode,t,'output',i)
   assert a.remaining[i]==(m.remaining if m.running else 0),(k,n,seed,mode,t,'remaining',i)
   assert a.done[i]==bool(m.cache),(k,n,seed,mode,t,'cache',i)
  for idx,b in enumerate(belts):
   assert a.routes[idx][2]==[None if it is None else w.t-it.entered for it in b.cells],(k,n,seed,mode,t,'transport',idx)
  if a.failure:break
 return dict(k=k,n=n,seed=seed,mode=mode,steps=a.t,initial=initial,all_states_equal=True,failure=a.failure,
             min_input=a.min_stock,min_output=a.min_out,max_head_wait_steps=a.max_wait,received=a.received)

if __name__=='__main__':
 results=[]
 for k in (2,3):
  for n in range(1,k+1):
   for seed in range(8):
    for mode in range(4):results.append(replay(k,n,seed,mode,2000))
   for seed in range(100,108):results.append(replay(k,n,seed,3,2000))
 out=dict(cases=len(results),step_pairs=sum(x['steps']for x in results),all_states_equal=all(x['all_states_equal']for x in results),
  all_invariants_observed=all(x['failure']is None for x in results),failures=[x for x in results if x['failure']],cases_detail=results)
 Path(__file__).with_suffix('.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in out.items()if k!='cases_detail'},ensure_ascii=False))
