#!/usr/bin/env python3
import importlib.util,pathlib,json,sys,collections
OUT=pathlib.Path(__file__).resolve().parent
src=OUT.parents[3]/'规则修订/2026-09-30-迟滞/sim2/simulator.py'
# output dir is 求解器/候选约束轮次/第92-94轮/推导92D
src=OUT.parent.parent.parent/'规则修订/2026-09-30-迟滞/sim2/simulator.py'
spec=importlib.util.spec_from_file_location('plant_sim2',src);s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s)
def build(full=False):
 C=s.Machine('C',recipes=[s.Recipe('采种',(('plant',1),),'seed',2,8)])
 A=s.Machine('A',recipes=[s.Recipe('种植',(('seed',1),),'plant',1,8)])
 B=s.Machine('B',recipes=[s.Recipe('种植',(('seed',1),),'plant',1,8)])
 K=s.Machine('K',recipes=[s.Recipe('粉碎',(('plant',1),),'powder',3,8)])
 CA,CB,AC,BK=[s.Belt(n) for n in ('CA','CB','AC','BK')]
 C.connect(CA,0).connect(A);C.connect(CB,1).connect(B);A.connect(AC).connect(C);B.connect(BK).connect(K)
 exits=[s.Belt('out'+str(i)) for i in range(3)];sinks=[s.Sink('sink'+str(i),every=9) for i in range(3)]
 for belt,sink in zip(exits,sinks):K.connect(belt);belt.connect(sink)
 machines=[C,A,B,K];routes=[CA,CB,AC,BK];nodes=machines+routes+exits+sinks
 if full:
  for m,kind,prod in zip(machines,['plant','seed','seed','plant'],['seed','plant','plant','powder']):
   m.slots[0]=[s.Item(kind) for _ in range(50)];m.output=[s.Item(prod) for _ in range(50)]
  for b,k in zip(routes+exits,['seed','seed','plant','plant','powder','powder','powder']):b.fill(k)
 else:
  C.slots[0]=[s.Item('plant') for _ in range(4)];C.output=[s.Item('seed')]
 w=s.World(nodes)
 return w,machines,routes,exits,sinks

def snap(w,ms,rs,es,ss):
 return dict(t=w.t,i=[len(m.slots[0]) for m in ms],o=[len(m.output) for m in ms],r=[m.remaining if m.running else (-1 if m.cache else 0) for m in ms],routes=[[min(8,w.t-1-i.entered) if i else -1 for i in b.cells] for b in rs+es],last=[[w.t-1-m.last_output[c] for c in m.output_channels] for m in ms],sink=[min(9,w.t-1-u.last) for u in ss],phi2=2*(sum(i is not None for b in (rs[0],rs[2]) for i in b.cells)+len(ms[0].slots[0])+len(ms[1].slots[0])+len(ms[1].output)+bool(ms[0].running or ms[0].cache)+bool(ms[1].running or ms[1].cache))+len(ms[0].output))

def run(full):
 w,ms,rs,es,ss=build(full);start=snap(w,ms,rs,es,ss)
 w.run(30000);hist=[]
 for _ in range(90):w.step();hist.append(snap(w,ms,rs,es,ss))
 a=dict(hist[-1]);b=dict(hist[-10]);a.pop('t');b.pop('t');assert a==b
 empty=[sum(x['r'][i]==0 for x in hist) for i in range(4)]
 result=dict(full=full,initial=start,cycle_period_steps=9,last90_empty=empty,cycle=hist[-9:],production_last90=[sum(t>=30000 for t,_ in m.finishes) for m in ms],phi2_range=[min(x['phi2'] for x in hist),max(x['phi2'] for x in hist)])
 print(json.dumps({k:v for k,v in result.items() if k not in ('cycle','initial')},ensure_ascii=False))
 return result
if __name__=='__main__':
 result=[run(False),run(True)];(OUT/'plant_sim2_nine.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
