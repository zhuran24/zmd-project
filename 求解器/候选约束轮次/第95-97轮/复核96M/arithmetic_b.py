"""Independent audit B: integer 20 tick demand and port vectors, no A imports."""
import json, itertools
from fractions import Fraction
from pathlib import Path
OUT=Path(__file__).resolve().parent
# Backwards quantities over 20 ticks, including regeneration of both plants.
battery,capsule=12,11
part=10*battery; dense_ore=15*battery
bottle=10*capsule; fine=10*capsule
steel=part+2*bottle
iron_powder=2*steel; ore_powder=2*dense_ore; flower_powder=2*fine
leaf_powder=steel+dense_ore+fine
flower_crush=flower_powder//2; leaf_crush=leaf_powder//3
flower_seed=flower_crush; leaf_seed=leaf_crush
flower_plant=2*flower_seed; leaf_plant=2*leaf_seed
work20=[iron_powder+ore_powder+flower_crush+leaf_crush,
        iron_powder+steel,steel+dense_ore+fine,bottle,part,
        flower_plant+leaf_plant,flower_seed+leaf_seed,5*battery,5*capsule]
counts=[(v+19)//20 for v in work20]
areas=[9,9,24,9,9,25,25,24,24]
input20=[work20[0],work20[1],3*work20[2],2*bottle,part,work20[5],work20[6],25*battery,20*capsule]
output20=[iron_powder+ore_powder+flower_powder+leaf_powder,work20[1],work20[2],bottle,part,
          work20[5],2*work20[6],battery,capsule]

singles={}; weights={}
for name,length,limit,target,lo,hi in [('grind',6,3,189,32,49),('shape',3,2,22,6,13),('pack',6,5,30,3,10),('fill',6,4,22,3,9)]:
    costs=[999999]*(2*limit+1)
    for v in itertools.product(range(3),repeat=length):
        s=sum(v)
        if s>2*limit:continue
        indices=[i for i,q in enumerate(v) if q]
        price=0
        for left,right in zip(indices,indices[1:]):
            if right-left<=3:price+=v[left]+v[right]
        costs[s]=min(costs[s],price)
    singles[name]=costs
    dp=[0]+[999999]*target
    table={}
    for n in range(1,hi+1):
        dp=[min((dp[t-k]+costs[k] for k in range(min(t,2*limit)+1)),default=999999) for t in range(target+1)]
        if n>=lo:table[str(n)]=str(Fraction(dp[target],2))
    weights[name]=table
grade=[]
for h,l in [(1,1),(2,1),(1,3),(3,2)]:
    amounts=[0,0,0]
    for permutation in itertools.permutations(['M']+['H'+str(i) for i in range(h)]+['L'+str(i) for i in range(l)]):
        built=set(); first={}
        for t,u in enumerate(permutation):
            built.add(u)
            if 'M' in built:
                for v in built-{'M'}:first.setdefault(v,t)
        a=min(t for v,t in first.items() if v.startswith('H'))
        b=min(t for v,t in first.items() if v.startswith('L'))
        amounts[0 if a<b else 1 if a==b else 2]+=1
    grade.append({'sizes':[h,l],'high_first_equal_low_first':amounts})
outer=[]
for length,k,tmax in [(71,2,1),(101,3,2),(138,2,2)]:
    row=[]
    for allowance in (tmax,0):
        row.append(next(x for x in range(140) if any(length<=5*m+9*c+3*t+x
                   for c in range(2) for t in range(allowance+1) for m in range(x+c+t+k+1))))
    outer.append(row)
pj=[]; best=Fraction(0)
for p in range(348):
    for j in range(p+1):
        if 23*p-10*j<sum(counts) or 54*p-25*j<sum(c*(2 if a==9 else 3) for c,a in zip(counts,areas)):continue
        if 16*p-2*j<=199:pj.append([p,j])
        bound=Fraction(2*(4751-16*p+2*j)-287,8)
        best=max(best,bound)
factor={str(a):sorted({(x,y) for x in range(6,69) for y in range(6,69) if x*y==a}) for a in range(1107,1112)}
loss=sum([50]*52+[53]*18+[153]*9+[100]*3+[2]*4900)
result={'counts':counts,'machine_area':sum(a*b for a,b in zip(counts,areas)),
 'total_machines':sum(counts),'input_ports':sum((x+19)//20 for x in input20),
 'output_ports':sum(max((x+19)//20,c) for x,c in zip(output20,counts)),
 'single_cost_twice':singles,'weights':weights,'omega':str(sum(Fraction(v[next(iter(v))]) for v in weights.values())),
 'grade':grade,'outer':outer,'fixed1110_pj':pj,'increment_area_bound':str(best),'factors':factor,
 'startup_loss':loss,'startup_need':sum([50]*11+[1]*9800),
 'switch':{'batches20':sum([steel,dense_ore,fine]),'N32_W':(32*160-8*(steel+dense_ore+fine))//20,
           'N32_a':max(a for a in range(33) if 160*(32-a)+Fraction(1280,9)*a>=8*630),
           'N33_a':max(a for a in range(34) if 160*(33-a)+Fraction(1280,9)*a>=8*630)}}
result['interfaces']=result['input_ports']+result['output_ports']+sum([1]*46+[1]*6+[1]*2)
(OUT/'arithmetic_b.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['machine_area','total_machines','interfaces','omega','increment_area_bound','outer','startup_loss']}))
