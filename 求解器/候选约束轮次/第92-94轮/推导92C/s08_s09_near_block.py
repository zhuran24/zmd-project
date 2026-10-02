import s08_s09_probe as p,json,random
rng=random.Random(9208);found=[]
for run in range(20000):
 counts=[(rng.choice([49,50]),rng.randrange(7)),(rng.choice([49,50]),rng.choice([49,50])),(0,0),(0,0)]
 ages=[[rng.randrange(9)],[rng.randrange(9)],[rng.choice([None,*range(9)])],[None]]
 phase=[rng.choice([None,*range(1,9)]),rng.choice([None,*range(1,9)]),None,None]
 first=rng.choice(['A','B']);w,ms,rs=p.build((1,1,1,1),counts,ages,phase,first)
 w.step();start=p.snapshot(w,ms,rs);bound=min(start['phi']-.5,178)
 for i in range(80):
  w.step()
  if p.phi(ms,rs)<bound:
   found.append({'counts':counts,'ages':ages,'phase':phase,'first':first,'start':start,'bad':p.snapshot(w,ms,rs),'bound':bound});break
 if found:break
print(json.dumps({'runs':run+1,'found':found},ensure_ascii=False,indent=2))
