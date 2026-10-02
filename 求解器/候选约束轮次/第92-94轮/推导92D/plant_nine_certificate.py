#!/usr/bin/env python3
"""Independent countdown model for the 9-step downstream service obstruction."""
import importlib.util,pathlib,json
OUT=pathlib.Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('plant',OUT/'plant_nine.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
q=m.Plant();q.i=[4,0,0,0];q.o=[1,0,0,0];initial=q.short()
for _ in range(30000):q.step()
a=q.state();prod=q.prod[:];history=[]
for _ in range(9):q.step();history.append(q.short())
assert q.state()==a
r=dict(initial=initial,period_steps=9,empty_counts=[sum(x['r'][i]==0 for x in history) for i in range(4)],batches=[x-y for x,y in zip(q.prod,prod)],phi2_range=[min(x['phi2'] for x in history),max(x['phi2'] for x in history)],cycle=history)
assert r['empty_counts']==[1,1,0,0] and r['batches']==[1,1,1,1] and r['phi2_range']==[9,10]
(OUT/'plant_nine_certificate.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in r.items() if k!='cycle'},ensure_ascii=False))
