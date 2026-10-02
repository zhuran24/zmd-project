#!/usr/bin/env python3
"""Cross-check flow_network step states against independently written sim2."""
import sys, importlib.util, json
from pathlib import Path
sys.dont_write_bytecode=True
from flow_network import Net
path=Path(__file__).parents[4]/'规则修订'/'2026-09-30-迟滞'/'sim2'/'simulator.py'
if not path.exists():path=Path('/home/zhuran24/zmd-research-fresh/求解器/规则修订/2026-09-30-迟滞/sim2/simulator.py')
spec=importlib.util.spec_from_file_location('independent_sim2',path);s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s)

def verify(mixed):
 n=Net(mixed); mapped={};nodes=[]
 for m in n.ms:
  if m is n.sink:u=s.Warehouse(m.name,limit=80000)
  elif not m.need:u=s.Source(m.name,kinds=(m.kind,))
  else:
   r=s.Recipe(m.name,tuple(m.need.items()),m.kind,m.k,m.d)
   u=s.Machine(m.name,auxiliary=len(m.need)==2,recipes=[r]);u.slots=[[s.Item(k) for _ in range(50)]for k in m.need];u.output=[s.Item(m.kind)for _ in range(50)]
  mapped[m.name]=u;nodes.append(u)
 belts=[]
 for i,r in enumerate(n.routes):
  b=s.Belt('route'+str(i));b.fill(r[2]);mapped[r[0].name].connect(b,2*i);b.connect(mapped[r[1].name],2*i+1);nodes.append(b);belts.append(b)
 schedule={'order':[b.name for b in belts]+[m.name for m in n.ms]}
 w=s.World(nodes,schedule=schedule)
 def checks(t):
  for m in n.ms:
   u=mapped[m.name]
   if m.need:
    assert m.stock=={k:sum(len(sl)for sl in u.slots if sl and sl[0].kind==k)for k in m.need},(t,m.name,'stock')
    assert m.out==len(u.output),(t,m.name,'out')
    assert m.done==bool(u.cache),(t,m.name,'cache')
    assert (m.ready is None)==(u.running is None and not u.cache),(t,m.name,'ready')
    if u.running is not None:assert m.ready-n.t+1==u.remaining,(t,m.name,'remaining',m.ready,n.t,u.remaining)
  for r,b in zip(n.routes,belts):
   assert (r[3] is None)==(b.cells[0] is None),(t,b.name,'filled')
   if r[3] is not None:assert r[3]==b.cells[0].entered,(t,b.name,'entered')
 for t in range(3000):
  n.step();w.step();checks(t)
 return dict(mixed=mixed,steps=n.t,all_machine_inventories_and_transport_timestamps_equal=True,
             warehouse=n.taken,sim2_warehouse={k:sum(x[1]==k for x in mapped[n.sink.name].received)for k in n.taken})

if __name__=='__main__':
 out=[verify(False),verify(True)]
 Path(__file__).with_suffix('.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(out,ensure_ascii=False,indent=2))
