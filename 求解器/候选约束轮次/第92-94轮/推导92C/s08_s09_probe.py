import importlib.util,sys,json,random,pathlib
p=pathlib.Path('/home/zhuran24/zmd-research-fresh/求解器/规则修订/2026-09-30-迟滞/sim2/simulator.py')
s=importlib.util.spec_from_file_location('sim2_92C',p); m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
def build(lengths=(1,1,1,1), counts=None, ages=None, phase=None, first='A', trace=False):
 C=m.Machine('C',recipes=[m.Recipe('seed',(('plant',1),),'seed',2)])
 A=m.Machine('A',recipes=[m.Recipe('plant',(('seed',1),),'plant',1)])
 B=m.Machine('B',recipes=[m.Recipe('plant',(('seed',1),),'plant',1)])
 K=m.Machine('K',recipes=[m.Recipe('powder',(('plant',1),),'powder',2)])
 machines=[C,A,B,K]; routes=[]
 for name,l,src,dst,kind in zip(['CA','AC','CB','BK'],lengths,[C,A,C,B],[A,C,B,K],['seed','plant','seed','plant']):
  r=m.Belt(name,l);src.connect(r);r.connect(dst);routes.append(r)
 if first=='B':
  C.output_channels[0].connected,C.output_channels[1].connected=C.output_channels[1].connected,C.output_channels[0].connected
 O1=m.Belt('O1');O2=m.Belt('O2');sink=m.Sink('sink')
 K.connect(O1);K.connect(O2);O1.connect(sink);O2.connect(sink)
 nodes=machines+routes+[O1,O2,sink]
 w=m.World(nodes,trace=trace)
 if counts:
  for x,(inp,out) in zip(machines,counts):
   x.slots[0]=[m.Item(x.recipes[0].ingredients[0][0]) for _ in range(inp)]
   x.output=[m.Item(x.recipes[0].product) for _ in range(out)]
 if ages:
  for r,a,kind in zip(routes,ages,['seed','plant','seed','plant']):
   r.cells=[None if age is None else m.Item(kind,entered=-age) for age in a]
 if phase:
  for x,rem in zip(machines,phase):
   if rem is not None:
    if rem==0:x.cache=[m.Item(x.recipes[0].product) for _ in range(x.recipes[0].quantity)]
    else:x.running=x.recipes[0];x.remaining=rem
 return w,machines,routes

def phi(ms,rs):
 C,A,B,K=ms;CA,AC,CB,BK=rs
 return len(A.slots[0])+len(A.output)+len(C.slots[0])+sum(v is not None for r in (CA,AC) for v in r.cells)+bool(A.running or A.cache)+bool(C.running or C.cache)+len(C.output)/2

def snapshot(w,ms,rs):
 return {'step':w.t-1,'phi':phi(ms,rs),'machines':{x.name:{'in':len(x.slots[0]),'out':len(x.output),'remain':x.remaining,'cache':len(x.cache)} for x in ms},'routes':{r.name:[None if i is None else min(8,w.t-1-i.entered) for i in r.cells] for r in rs}}

def main():
 rng=random.Random(92809); found=[]
 for run in range(1200):
  lengths=tuple(rng.randrange(1,6) for _ in range(4));
  counts=[(rng.randrange(51),rng.randrange(51)) for _ in range(4)]
  ages=[[None if rng.random()<.12 else rng.randrange(9) for _ in range(l)] for l in lengths]
  phase=[rng.choice([None,*range(1,9)]) for _ in range(4)]
  first=rng.choice(['A','B'])
  w,ms,rs=build(lengths,counts,ages,phase,first)
  w.step();p0=phi(ms,rs);bound=min(p0-.5,sum(lengths[:2])+176);start=snapshot(w,ms,rs)
  for t in range(2000):
   w.step()
   if phi(ms,rs)<bound:
    found.append({'run':run,'lengths':lengths,'counts':counts,'ages':ages,'phase':phase,'first':first,'start':start,'bad':snapshot(w,ms,rs),'bound':bound})
    break
  if found:break
 print(json.dumps({'found':found,'runs':run+1},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
