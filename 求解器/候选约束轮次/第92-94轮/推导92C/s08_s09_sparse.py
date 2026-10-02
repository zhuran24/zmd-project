import s08_s09_probe as p,json,random
rng=random.Random(9209); found=[]; tested=0
for run in range(1000):
 counts=[(rng.randrange(3),rng.randrange(5)),(rng.randrange(3),rng.randrange(3)),(0,0),(0,0)]
 ages=[[rng.choice([None,*range(9)])],[rng.choice([None,*range(9)])],[None],[None]]
 phase=[rng.choice([None,*range(1,9)]),rng.choice([None,*range(1,9)]),None,None]
 first=rng.choice(['A','B']);w,ms,rs=p.build((1,1,1,1),counts,ages,phase,first)
 w.step();start=p.snapshot(w,ms,rs)
 if start['phi']<4.5:continue
 tested+=1
 for i in range(2500):w.step()
 bad=[]
 for i in range(128):
  w.step()
  if any(not(x.running or x.cache) for x in ms):bad.append(p.snapshot(w,ms,rs))
 if bad:
  found.append({'counts':counts,'ages':ages,'phase':phase,'first':first,'start':start,'bad':bad});break
print(json.dumps({'runs':run+1,'tested':tested,'found':found},ensure_ascii=False,indent=2))
