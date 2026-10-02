import s08_s09_probe as p,itertools,json
found=[]; runs=0
for ai,ao,ci,co in itertools.product([49,50],[48,49,50],[49,50],[48,49,50]):
 for ar,cr in itertools.product([None,*range(1,9)],repeat=2):
  for first in ['A','B']:
   runs+=1;w,ms,rs=p.build((1,1,1,1),[(ci,co),(ai,ao),(10,10),(10,10)],[[8],[8],[8],[8]],[cr,ar,1,1],first)
   w.step();p0=p.phi(ms,rs);bound=min(p0-.5,178); start=p.snapshot(w,ms,rs)
   for t in range(40):
    w.step()
    if p.phi(ms,rs)<bound:
     found.append({'counts':[(ci,co),(ai,ao),(10,10),(10,10)],'phase':[cr,ar,1,1],'first':first,'start':start,'bad':p.snapshot(w,ms,rs),'bound':bound});break
   if found:break
  if found:break
 if found:break
print(json.dumps({'runs':runs,'found':found},ensure_ascii=False,indent=2))
