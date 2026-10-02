import time, sys
from engine_a import run_case
t0=time.time()
r=run_case(1, disturb=False, max_steps=40000)
f=r.pop('f',None)
print(time.time()-t0, {k:v for k,v in r.items() if k not in ('ore','rej')})
if r.get('period'):
    ore=[r['ore'][b.idx] for b in f.belts if b.src in f.src]
    print('ore per path', set(ore), len(ore), 'period', r['period'])
