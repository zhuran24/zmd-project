#!/usr/bin/env python3
"""Independent audit A: parse snapshot recipes, solve exact balances, enumerate clocks.
Does not load any derivation-seat program. Writes only beside this script.
"""
from pathlib import Path
from fractions import Fraction as Q
from math import ceil, gcd
import re, json, hashlib
D = Path(__file__).resolve().parent
S = D.parent / '前提快照'
rules = (S/'《明日方舟：终末地》游戏规则.txt').read_text()
factory_names=['粉碎机','精炼炉','研磨机','塑形机','配件机','种植机','采种机','封装机','灌装机']
recipes=[]; current=None
for line in rules.splitlines()[79:]:
    line=line.strip()
    if line in factory_names: current=line
    if '→' not in line: continue
    left, right=line.split('→')
    prod, duration=right.split('，')
    def parts(s):
        return {m.group(2):int(m.group(1)) for p in s.split('＋') if (m:=re.fullmatch(r'\s*(\d+)\s+(.+?)\s*',p))}
    recipes.append({'factory':current,'inputs':parts(left),'outputs':parts(prod),'duration':int(duration.split()[0]),'line':line})
species=sorted(set().union(*(set(r['inputs'])|set(r['outputs']) for r in recipes)))
# Variables: all recipe rates, blue-ore import, source-ore import.
n=len(recipes)+2
A=[]
for item in species:
    row=[Q(r['outputs'].get(item,0)-r['inputs'].get(item,0)) for r in recipes]
    row += [Q(item=='蓝铁矿'),Q(item=='源矿')]
    A.append(row+[{'高容谷地电池':Q(3,5),'精选荞愈胶囊':Q(11,20)}.get(item,Q(0))])
recycle=next(i for i,r in enumerate(recipes) if r['factory']=='精炼炉' and '蓝铁粉末' in r['inputs'])

def solve(extra):
    mat=[row[:] for row in A]
    mat.append([Q(i==recycle) for i in range(n)]+[Q(extra)])
    pivot=0; cols=[]
    for col in range(n):
        j=next((j for j in range(pivot,len(mat)) if mat[j][col]),None)
        if j is None: continue
        mat[pivot],mat[j]=mat[j],mat[pivot]
        v=mat[pivot][col]; mat[pivot]=[x/v for x in mat[pivot]]
        for j in range(len(mat)):
            if j!=pivot and mat[j][col]:
                v=mat[j][col]; mat[j]=[x-v*y for x,y in zip(mat[j],mat[pivot])]
        cols.append(col); pivot+=1
    assert all(any(row[:-1]) or row[-1]==0 for row in mat)
    assert len(cols)==n,(len(cols),n)
    x=[Q(0)]*n
    for row,col in zip(mat,cols): x[col]=row[-1]
    assert all(sum(row[i]*x[i] for i in range(n))==row[-1] for row in A)
    return x
base,one=solve(0),solve(1)
rates={f:sum(base[i] for i,r in enumerate(recipes) if r['factory']==f) for f in factory_names}
slopes={f:sum(one[i]-base[i] for i,r in enumerate(recipes) if r['factory']==f) for f in factory_names}
mins={f:ceil(rates[f]*next(r['duration'] for r in recipes if r['factory']==f)) for f in factory_names}
production={s:sum(base[i]*r['outputs'].get(s,0) for i,r in enumerate(recipes)) for s in species}
production['蓝铁矿']=base[-2]; production['源矿']=base[-1]
areas={f: (25 if f in ('种植机','采种机') else 24 if f in ('研磨机','封装机','灌装机') else 9) for f in factory_names}

# Longest independent set of event times on an integer clock with a minimum gap.
def max_events(points,gap):
    dp={}
    for t in points:
        dp[t]=max([0]+[dp[u] for u in points if u<t])+0
        dp[t]=max(dp[t],1+max([0]+[dp[u] for u in points if u<=t-gap]))
    return max(dp.values(),default=0)
closed=max_events(list(range(41)),8)
next8=max_events(list(range(1,9)),8)
wireless_steps=int(Q(5)/Q(1,8))
phase_events={str(p):[t for t in range(3*wireless_steps+1) if (t-p)%wireless_steps==0] for p in range(wireless_steps)}
assert all(all(b-a==40 for a,b in zip(ts,ts[1:])) for ts in phase_events.values())
# All one-machine phases and all observation steps for the half-open 2-tick windows.
window_counts=[]
for phase in range(8):
    for t in range(16):
        past=sum((u-phase)%8==0 for u in range(t-15,t+1))
        future=sum((u-phase)%8==0 for u in range(t+1,t+17))
        window_counts.append((past,future))
assert set(window_counts)=={(2,2)}
# Recompute the reported finite family size from combinatorics, without running their scripts.
word_counts=[]
for k in range(1,7):
    count=sum(1 for a in range(k+1) for b in range(k+1) for c in range(k+1) for d in range(k+1) if a+b<=k and b+c<=k and c+d<=k)
    word_counts.append(count)
family_count=sum(w*2**k*16*2 for k,w in enumerate(word_counts,1))

out={'status':'PASS','encoding':'parsed stoichiometric matrix and rational Gaussian elimination',
     'recipe_count':len(recipes),'species_count':len(species),
     'recipes':[dict(r,rate=str(base[i]),recycle_slope=str(one[i]-base[i])) for i,r in enumerate(recipes)],
     'recipe_rates':{k:str(v) for k,v in rates.items()},'recycle_slopes':{k:str(v) for k,v in slopes.items()},
     'machine_minimum':mins,'machine_count':sum(mins.values()),'machine_area':sum(mins[f]*areas[f] for f in factory_names),
     'material_flow':{k:str(v) for k,v in production.items()},'total_flow':str(sum(production.values())),
     'ore_total':str(base[-2]+base[-1]),'mixed_channel_bounds':[ceil(Q(a+b,2)) for a,b in [(3,2),(3,1),(2,1),(2,2)]],
     'two_tick_window_per_machine':2,'plant_stock_total_bound':32*2,
     'mean_stock_bounds':{item:int(2*production[item]) for item in ['荞花种子','荞花','砂叶种子','砂叶']},
     'wireless_period_steps':wireless_steps,'wireless_phase_count':len(phase_events),'closed_5_tick_one_port_events':closed,
     'box_conservative_bound':3*closed,'next_8_steps_one_port_events':next8,
     'four_group_word_counts':word_counts,'reported_polling_family_count':family_count,
     'snapshots':{p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'lines':len(p.read_text().splitlines())} for p in sorted(S.glob('*.txt'))}}
(D/'arithmetic_matrix.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['status','recipe_count','species_count','machine_minimum','machine_count','machine_area','total_flow','reported_polling_family_count']},ensure_ascii=False))
