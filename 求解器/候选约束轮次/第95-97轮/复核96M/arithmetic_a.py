"""Independent audit A: rational stoichiometry, support costs, exact budgets."""
from fractions import Fraction as F
from itertools import combinations, permutations
from pathlib import Path
import json, math

OUT=Path(__file__).resolve().parent
# All 18 recipes, written directly from the rule snapshot.
recipes=[
 ('crush',{'ore':1},{'op':1},1),('crush',{'ingot':1},{'ip':1},1),
 ('crush',{'flower':1},{'fp':2},1),('crush',{'leaf':1},{'lp':3},1),
 ('refine',{'iron':1},{'ingot':1},1),('refine',{'di':1},{'steel':1},1),
 ('refine',{'ip':1},{'ingot':1},1),
 ('grind',{'ip':2,'lp':1},{'di':1},1),('grind',{'op':2,'lp':1},{'do':1},1),
 ('grind',{'fp':2,'lp':1},{'fine':1},1),('shape',{'steel':2},{'bottle':1},1),
 ('part',{'steel':1},{'part':1},1),('plant',{'fs':1},{'flower':1},1),
 ('plant',{'ls':1},{'leaf':1},1),('seed',{'flower':1},{'fs':2},1),
 ('seed',{'leaf':1},{'ls':2},1),
 ('pack',{'part':10,'do':15},{'battery':1},5),
 ('fill',{'bottle':10,'fine':10},{'capsule':1},5)]
species=sorted(set().union(*(set(a)|set(b) for _,a,b,_ in recipes)))
assert len(species)==19

def solve(recycle):
    mat=[]
    for s in species:
        mat.append([F(b.get(s,0)-a.get(s,0)) for _,a,b,_ in recipes]+
                   [F(s=='ore'),F(s=='iron'),{'battery':F(3,5),'capsule':F(11,20)}.get(s,F(0))])
    mat.append([F(i==6) for i in range(20)]+[F(recycle)])
    for c in range(20):
        p=next(i for i in range(c,20) if mat[i][c])
        mat[c],mat[p]=mat[p],mat[c]
        div=mat[c][c]; mat[c]=[v/div for v in mat[c]]
        for i in range(20):
            if i!=c and mat[i][c]:
                a=mat[i][c]; mat[i]=[x-a*y for x,y in zip(mat[i],mat[c])]
    return [r[-1] for r in mat]

rates=solve(0); r1=solve(1)
types=['crush','refine','grind','shape','part','plant','seed','pack','fill']
areas=[9,9,24,9,9,25,25,24,24]
work={t:sum((rates[i]*d for i,(k,_,_,d) in enumerate(recipes) if k==t),F(0)) for t in types}
counts={t:math.ceil(work[t]) for t in types}
inputs={t:sum((rates[i]*sum(a.values()) for i,(k,a,b,d) in enumerate(recipes) if k==t),F(0)) for t in types}
outputs={t:sum((rates[i]*sum(b.values()) for i,(k,a,b,d) in enumerate(recipes) if k==t),F(0)) for t in types}
inports=sum(math.ceil(v) for v in inputs.values())
outports=sum(max(math.ceil(outputs[t]),counts[t]) for t in types)

def one_machine(length,limit):
    best=[10**8]*(2*limit+1)
    for mask in range(1<<length):
        support=[i for i in range(length) if mask>>i&1]
        costs=[]
        for j,x in enumerate(support):
            c=int(j>0 and x-support[j-1]<=3)+int(j+1<len(support) and support[j+1]-x<=3)
            costs.extend([c,c])
        costs.sort()
        for flow in range(min(2*limit,len(costs))+1):
            best[flow]=min(best[flow],sum(costs[:flow]))
    return best

weights={}; singles={}
for t,length,limit,demand,n0,nmax in [('grind',6,3,189,32,49),('shape',3,2,22,6,13),('pack',6,5,30,3,10),('fill',6,4,22,3,9)]:
    c=one_machine(length,limit); singles[t]=c
    dp={0:0}; tab={}
    for n in range(1,nmax+1):
        nxt={}
        for x,v in dp.items():
            for k,cost in enumerate(c):
                if x+k<=demand:
                    nxt[x+k]=min(nxt.get(x+k,10**8),v+cost)
        dp=nxt
        if n>=n0:tab[n]=F(dp[demand],2)
    weights[t]=tab

omega=sum(v[min(v)] for v in weights.values())
min_increment={t:min(4*areas[types.index(t)]+tab[n+1]-tab[n] for n in tab if n+1 in tab) for t,tab in weights.items()}
for t,a in zip(types,areas):min_increment.setdefault(t,F(4*a))
min_increment['box']=F(36)
pj=[(p,j) for p in range(10,348) for j in range(p+1) if 23*p-10*j>=217 and 54*p-25*j>=520]
increment_bound=max((F(4751)-16*p+2*j-omega-34)/4 for p,j in pj)
fixed1110=[(p,j) for p,j in pj if 16*p-2*j<=199]
factors={a:[(w,a//w) for w in range(6,69) if a%w==0 and 6<=a//w<=68] for a in range(1107,1112)}
outer=[]
for length,k,t in [(71,2,1),(101,3,2),(138,2,2)]:
    outer.append([math.ceil((length-14-8*t-5*k)/6), math.ceil((length-14-5*k)/6)])
grade=[]
for h,l in [(1,1),(2,1),(1,3),(3,2)]:
    numbers=[0,0,0]
    for perm in permutations(range(1+h+l)):
        times={v:i for i,v in enumerate(perm)}
        a=min(max(times[0],times[k]) for k in range(1,h+1))
        b=min(max(times[0],times[k]) for k in range(h+1,h+l+1))
        numbers[(a>b)-(a<b)+1]+=1
    grade.append({'sizes':[h,l],'high_first_equal_low_first':numbers})

ans={'rates':rates,'recycle_derivative':[b-a for a,b in zip(rates,r1)],'work':work,'counts':counts,
     'machine_area':sum(counts[t]*a for t,a in zip(types,areas)), 'total_machines':sum(counts.values()),
     'input_ports':inports,'output_ports':outports,'interfaces':inports+outports+52+2,
     'single_cost_twice':singles,'weights':weights,'omega':omega,'min_increment':min_increment,
     'free_budget':4900-3291-81-46*3,'area_constant':4*1390-921,
     'uniform_budget':1390-math.ceil(F(829,4)),'increment_area_bound':increment_bound,
     'fixed1110_pj':fixed1110,'factors':factors,'outer':outer,'grade':grade,
     'startup_loss':52*50+18*(50+3)+9*(100+50+3)+3*100+2*70*70,
     'startup_need':550+2*70*70,'switch':{'batches20':630,'N32_W':4,'N32_a':4,'N33_a':13}}
def clean(x):
    if isinstance(x,F):return str(x)
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    return x
(OUT/'arithmetic_a.json').write_text(json.dumps(clean(ans),ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:clean(ans[k]) for k in ['machine_area','total_machines','interfaces','omega','increment_area_bound','outer','startup_loss']}))
