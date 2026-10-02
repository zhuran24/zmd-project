#!/usr/bin/env python3
"""Finite probes only, not an exhaustive state-space proof."""
import random,json
from pathlib import Path
from flow_network import Net
out=[]
for seed in range(20):
 r=random.Random(seed);n=Net(True)
 for m in n.ms:
  r.shuffle(m.ins);r.shuffle(m.outs)
  if m.need:m.ready=r.randrange(1,m.d+1)
 for route in n.routes:route[3]=-r.randrange(9)
 for _ in range(8000):n.step()
 old=n.taken.copy();ore=[s.outs[0][5] for s in n.mines]
 for _ in range(1600):n.step()
 d={k:n.taken[k]-old[k]for k in old};od=[s.outs[0][5]-v for s,v in zip(n.mines,ore)]
 out.append(dict(seed=seed,warmup_steps=8000,window_steps=1600,delivery=d,mineral_min=min(od),mineral_max=max(od),pass_observed=d=={'battery':120,'capsule':110} and all(x==200 for x in od)))
Path(__file__).with_suffix('.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(cases=len(out),pass_observed=all(x['pass_observed']for x in out)),ensure_ascii=False))
