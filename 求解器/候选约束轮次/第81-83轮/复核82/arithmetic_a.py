"""82 复核编码甲。仅解析正式规则；不导入任何推导席程序。"""
import os
os.sched_setaffinity(0, {0})
from pathlib import Path
from fractions import Fraction as F
from itertools import product, combinations
from math import gcd, ceil
import re, json, hashlib

OUT = Path(__file__).resolve().parent
RULE = OUT.parent / '前提快照/《明日方舟：终末地》游戏规则.txt'
text = RULE.read_text().split('\n配方\n')[1]
recipes=[]
machine=None
for line in text.splitlines():
    line=line.strip()
    if not line: continue
    if '→' not in line:
        machine=line; continue
    left,right=line.split('→')
    right,dt=right.split('，')
    parse=lambda s: {name.strip():int(n) for n,name in re.findall(r'(\d+)\s+([^＋]+)', s)}
    recipes.append((machine,parse(left),parse(right),int(dt.split()[0])))
items=sorted({i for _,a,b,_ in recipes for i in a|b})
matrix=[]
fixed={'蓝铁矿':F(34),'源矿':F(18),'高容谷地电池':-F(3,5),'精选荞愈胶囊':-F(11,20)}
for i in items:
    matrix.append([F(b.get(i,0)-a.get(i,0)) for _,a,b,_ in recipes]+[-fixed.get(i,F(0))])
pivots=[]; row=0
for col in range(len(recipes)):
    p=next((r for r in range(row,len(matrix)) if matrix[r][col]),None)
    if p is None: continue
    matrix[row],matrix[p]=matrix[p],matrix[row]
    z=matrix[row][col]; matrix[row]=[a/z for a in matrix[row]]
    for r in range(len(matrix)):
        if r!=row and matrix[r][col]:
            z=matrix[r][col]; matrix[r]=[a-z*b for a,b in zip(matrix[r],matrix[row])]
    pivots.append(col); row+=1
free=[j for j in range(len(recipes)) if j not in pivots]
assert len(free)==1
coeff={free[0]:(F(0),F(1))}
for r,c in enumerate(pivots): coeff[c]=(matrix[r][-1],-matrix[r][free[0]])
source=[F(52),F(0)]
rates={}
for j,(m,a,b,d) in enumerate(recipes):
    rates.setdefault(m,[F(0),F(0)])
    for t in range(2):
        rates[m][t]+=coeff[j][t]
        source[t]+=sum(b.values())*coeff[j][t]

def edge_cost(v):
    ix=[i for i,x in enumerate(v) if x]
    return sum(v[a]+v[b] for a,b in zip(ix,ix[1:]) if b-a<=3)
tables={}
for name,width,cap,need,n0,n1 in [('研磨',6,3,189,32,48),('塑形',3,2,22,6,11),('封装',6,5,30,3,8),('灌装',6,4,22,3,6)]:
    one=[10**9]*(2*cap+1)
    witness={}
    for v in product(range(3),repeat=width):
        s=sum(v)
        if s<=2*cap and edge_cost(v)<one[s]:
            one[s]=edge_cost(v); witness[s]=v
    dp=[0]+[10**9]*need
    vals={}
    for n in range(1,n1+1):
        dp=[min(dp[q-u]+one[u] for u in range(min(q,2*cap)+1)) for q in range(need+1)]
        if n>=n0: vals[n]=str(F(dp[need],2))
    tables[name]={'single_cost_twice':one,'single_witness':witness,'global':vals}

safety=[]; residue_pairs=0; residue_records=[]
for a,b,m in [(2,1,6),(10,15,5),(10,10,6)]:
    L=b*(a-1)-50*a; U=50*b-a*(b-1); z=50*(b-a)
    safe=min(z-L,U-z); err=2*m*a*b//gcd(a,b)
    for x,y in product(range(51),repeat=2):
        n=min(x//a,y//b)
        qa,qb=x,y
        while qa>=a and qb>=b: qa-=a; qb-=b
        assert (qa,qb)==(x-a*n,y-b*n)
        residue_records.append([a,b,x,y,n,qa,qb])
        residue_pairs+=1
    safety.append({'a':a,'b':b,'m':m,'L':L,'U':U,'Z0':z,'C':safe,'arbitrary_segment_error':err,'pass':err<safe})

dead={}
for name,raw,req in [('研磨',['蓝铁粉末','源石粉末','荞花粉末','砂叶粉末'],[(2,0,0,1),(0,2,0,1),(0,0,2,1)]),('封装',['钢制零件','致密源石粉末'],[(10,15)]),('灌装',['钢质瓶','细磨荞花粉末'],[(10,10)])]:
    states=[{}]
    for i in raw:
        states += [{i:q} for q in range(1,51)]
    for i,j in combinations(raw,2):
        states += [{i:q,j:r} for q,r in product(range(1,51),repeat=2)]
    count=0; with_bad=0
    for s in states:
        if name=='研磨' and len(s)==2 and '砂叶粉末' not in s: continue
        if any(all(s.get(i,0)>=a for i,a in zip(raw,recipe)) for recipe in req): continue
        blocked=[i for i in raw if s.get(i,0)==50 or (i not in s and len(s)==2)]
        count+=2**len(blocked)-1
        if len(s)==2: blocked.append('源矿（误料首件）')
        with_bad+=2**len(blocked)-1
    dead[name]={'only_recipe_inputs_as_heads':count,'including_one_wrong_head_kind':with_bad}

areas={a:[(w,h) for w in range(6,69) for h in range(w,69) if w*h==a] for a in range(1107,1114)}
PJ=[]
for p in range(10,19):
    for j in range(p+1):
        if 54*p-25*j>=520 and 23*p-10*j>=217:
            budget=4751-4*1110-16*p+2*j
            if 4639-4*1110-16*p+2*j>=0:
                PJ.append({'P':p,'J':j,'extra_budget':budget,'X_plus_Y_max':4639-4440-16*p+2*j})
result={'recipe_count':len(recipes),'item_count':len(items),'rank':row,'free_recipe':recipes[free[0]],
        'recipe_rates':[{'machine':r[0],'input':r[1],'output':r[2],'constant':str(coeff[i][0]),'r':str(coeff[i][1])} for i,r in enumerate(recipes)],
        'machine_rates':{k:list(map(str,v)) for k,v in rates.items()},'physical_source_rate':list(map(str,source)),
        'direction_tables':tables,'mixed_safety':safety,'residue_pairs':residue_pairs,
        'residue_sha256':hashlib.sha256(json.dumps(sorted(residue_records)).encode()).hexdigest(),'dead_combinations':dead,
        'areas':areas,'scalar_1110':PJ,'weighted_minimum':2*131+3*(48+38),'machine_count':68+51+32+6+6+32+16+3+3,
        'plant_mean':{'荞花种子':22,'荞花':22,'砂叶种子':42,'砂叶':42},
        'plant_capacity_coefficients':[100+max(max(sum(a.values()),sum(b.values())) for m,a,b,d in recipes if m==kind) for kind in ['采种机','种植机']]+[1,1,300]}
(OUT/'arithmetic_a.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['direction_tables','recipe_rates']},ensure_ascii=False))
