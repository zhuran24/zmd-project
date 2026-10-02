import s08_s09_probe as p,json
m=p.m
w,ms,rs=p.build((1,1,1,1),[(50,50),(50,50),(50,50),(50,50)],[[8],[8],[8],[8]],[None]*4,trace=True)
O1=w.lookup['O1'];O2=w.lookup['O2']; old=w.lookup['sink']
for o in [O1,O2]:o.outputs=[];o.output_channels=[];o.last_output={};o.fill('powder')
R=m.Machine('R',auxiliary=True,recipes=[m.Recipe('fine',(('powder',2),('sand',1)),'fine',1)])
R.slots=[[m.Item('powder') for _ in range(50)],[m.Item('sand') for _ in range(50)]];R.output=[m.Item('fine') for _ in range(49)]
O1.connect(R);O2.connect(R)
S=m.Source('S',kinds=('sand',));Sbelt=m.Belt('Sbelt').fill('sand');S.connect(Sbelt);Sbelt.connect(R)
Rbelt=m.Belt('Rbelt').fill('fine');sink=m.Sink('sink');R.connect(Rbelt);Rbelt.connect(sink)
w=m.World([n for n in w.nodes if n is not old]+[R,S,Sbelt,Rbelt,sink],trace=True)

def key(w):
 z=[]
 for x in w.nodes:
  if isinstance(x,m.Machine):z.append((x.name,tuple(tuple(i.kind for i in sl) for sl in x.slots),len(x.output),len(x.cache),x.remaining))
  if x.component:z.append((x.name,tuple(None if i is None else (i.kind,min(8,w.t-1-i.entered)) for i in x.cells)))
  z.append((x.name,x.input_cursor,x.output_cursor,tuple(sorted((c.dst.name,min(16,w.t-x.last_output[c])) for c in x.output_channels))))
 return tuple(z)
seen={};hist=[];cycle=None
for t in range(20000):
 w.step();state=key(w);hist.append(p.snapshot(w,ms,rs))
 if state in seen:
  cycle=(seen[state],w.t-1);break
 seen[state]=w.t-1
lo,hi=cycle
examples=[]
for t in range(lo+1,hi+1):
 events=[e for e in w.events if e['t']==t]
 empties=[e['unit'] for e in events if e['event']=='send' and e['unit'] in ['O1','O2']]
 sends=[e['destination'] for e in events if e['event']=='send' and e['unit']=='K']
 if len(empties)==2 and len(sends)==1:
  examples.append({'step':t,'both_heads_emptied':empties,'K_filled':sends,'events':events})
r={'cycle':{'start_state_step':lo,'end_state_step':hi,'period_steps':hi-lo},'phi_at_first_completed_step':hist[0]['phi'],'initial_state':hist[0], 'counterexamples':examples, 'finite_step_1_events':[e for e in w.events if e['t']==1], 'machine_finishes_in_period':{x.name:sum(lo<t<=hi for t,_ in x.finishes) for x in ms+[R]},'states_in_period':hist[lo+1:hi+1]}
print(json.dumps(r,ensure_ascii=False,indent=2))
