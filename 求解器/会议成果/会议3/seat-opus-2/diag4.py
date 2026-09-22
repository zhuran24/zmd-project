import json, sys
import flowcheck as F
res = json.load(open(sys.argv[1]))
arcs, bad = F.build(res)
def relax(arcs, drop):
    out=[]
    for (u,v,lo,hi) in arcs:
        if drop(u,v): lo=0
        out.append((u,v,lo,hi))
    return out
isK=lambda x: isinstance(x,tuple) and x[0] in ('Kin','Kout')
ism=lambda x: isinstance(x,tuple) and x[0] in ('mi','mo')
for name, drop in [
  ('all', lambda u,v: False),
  ('drop type totals', lambda u,v: isK(u) and v=='T' or u=='S' and isK(v)),
  ('drop per-machine lower', lambda u,v: (ism(u) and isK(v)) or (isK(u) and ism(v))),
  ('drop both (only ore/core sources + core sink)', lambda u,v: isK(u) or isK(v)),
  ('drop core sink too', lambda u,v: isK(u) or isK(v) or u=='CORE'),
]:
    ok,S,d = F.feasible(relax(arcs,drop)); print(name, ok, d/20)
