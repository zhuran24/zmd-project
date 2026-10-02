import importlib.util,pathlib,random,json,collections
p=pathlib.Path(__file__).parent/'plant_probe.py';s=importlib.util.spec_from_file_location('plant_probe',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
rng=random.Random(217);found=[];counts=collections.Counter();best=0
for case in range(3000):
 lens=tuple(rng.randrange(1,8) for _ in range(4));q=m.Plant(lens)
 q.i=[50,50,rng.randrange(51),rng.randrange(51)];q.o=[50,50,rng.randrange(51),rng.randrange(51)];q.r=[rng.choice((-1,*range(1,9))) for _ in range(4)]
 for z in q.routes:
  for j in range(len(z)):z[j]=rng.randrange(9)
 start=q.short();phi=q.phi2();bound=min(phi-1,2*(lens[0]+lens[2]+176));history=[]
 for t in range(1600):
  q.step();history.append(q.short() if len(found)<2 else None)
  best=min(best,q.phi2()-bound)
  if q.phi2()<bound:
   found.append(dict(case=case,start=start,bound=bound,end=q.short(),history=history));counts['fail']+=1;break
 else:counts['pass']+=1
 if len(found)>=2:break
result=dict(counts=dict(counts),minimum_margin=best,counterexamples=found);(p.parent/'plant_dense.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='counterexamples'}));print([(x['case'],x['end']) for x in found])
