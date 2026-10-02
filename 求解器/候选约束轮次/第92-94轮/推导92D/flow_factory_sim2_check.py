#!/usr/bin/env python3
"""Independent sim2 replay of factory_check seed 920, including disturbances."""
import sys,importlib.util,json
from pathlib import Path
sys.dont_write_bytecode=True
from factory_check import Factory
p=Path('/home/zhuran24/zmd-research-fresh/求解器/规则修订/2026-09-30-迟滞/sim2/simulator.py')
spec=importlib.util.spec_from_file_location('replay_sim2',p);s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s)
f=Factory(920,1,'thin');mapped={};nodes=[];belts=[]
class Sink(s.Warehouse):
 def can_accept(self,item,w):return f.open
for m in f.ms+f.sources+[f.sink]:
 if m is f.sink:u=Sink(m.name)
 elif not m.recipe:u=s.Source(m.name,kinds=(m.routes[0].kind,))
 else:
  need,kind,k,d=m.recipe;r=s.Recipe(m.name,tuple(need.items()),kind,k,d)
  u=s.Machine(m.name,auxiliary=len(need)==2,recipes=[r]);u.slots=[[s.Item(k) for _ in range(m.stock[k])]for k in need];u.output=[s.Item(kind)for _ in range(m.out)]
 mapped[m]=u;nodes.append(u)
for r in f.rs:
 b=s.Belt('route'+str(r.index),len(r.cells));b.cells=[None if t is None else s.Item(r.kind,t)for t in r.cells]
 mapped[r.source].connect(b,r.source.order[r.index]);b.connect(mapped[r.target],r.target.accept_order[r.index]);belts.append(b);nodes.append(b)
schedule={'order':[b.name for b in belts]+[mapped[m].name for m in f.sources+f.ms+[f.sink]]}
w=s.World(nodes,schedule=schedule)
def reorder():
 for r,b in zip(f.rs,belts):b.input_channels[0].connected=r.source.order[r.index];b.output_channels[0].connected=r.target.accept_order[r.index]
 for m,vs in f.incoming.items():
  u=mapped[m];u.input_cursor=0 if m.cursor is None else (next(i for i,r in enumerate(vs)if r.index==m.cursor)+1)%len(vs)
def check(t):
 for m in f.ms:
  u=mapped[m]
  assert {k:m.stock[k]for k in m.recipe[0]}=={k:sum(len(sl)for sl in u.slots if sl and sl[0].kind==k)for k in m.recipe[0]},(t,m.name,'stock')
  assert m.out==len(u.output),(t,m.name,'out')
  assert m.done==bool(u.cache),(t,m.name,'cache')
  assert m.remaining==(u.remaining if u.running else 0),(t,m.name,'remaining')
 for r,b in zip(f.rs,belts):assert r.cells==[None if it is None else it.entered for it in b.cells],(t,b.name,'cells')
for t in range(18000):
 f.open=not(1000<=t<6000 or 7500<=t<14000)
 if t in (899,1200,5900,7501,13500,15999):f.reorder();reorder()
 f.step();w.step();check(t)
result=dict(seed=920,maxlen=1,initial='thin',steps=18000,all_step_states_equal=True,
 warehouse_interruptions=[[1000,6000],[7500,14000]],reorders=[899,1200,5900,7501,13500,15999],
 warehouse=dict(f.delivered),sim2_warehouse=dict(mapped[f.sink].stock))
Path(__file__).with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
