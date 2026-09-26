"""Exact accounting A: parse recipes, symbolic balance, support-set DP, scalar enumeration."""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations, product
from functools import lru_cache
import json, math, re

OUT=Path(__file__).resolve().parent
src=json.loads((OUT/'inputs.json').read_text())['sources']
rules=next(s['text'] for s in src if s['role']=='formal premise' and '游戏规则' in s['path'])

def recipes():
    ans=[]; machine=None
    for line in rules.split('\n配方\n',1)[1].splitlines():
        line=line.strip()
        if not line: continue
        if '→' not in line: machine=line; continue
        left,right=line.split('→'); right,duration=right.split('，')
        def side(s):
            return {name:int(n) for n,name in re.findall(r'(\d+)\s+([^\s＋]+)',s)}
        ans.append(dict(machine=machine,inputs=side(left),outputs=side(right),ticks=int(duration.strip().split()[0]),recipe=line))
    return ans

def flow():
    rec=recipes(); goods=sorted(set().union(*(set(r['inputs'])|set(r['outputs']) for r in rec)))
    mat=[[F(r['outputs'].get(g,0)-r['inputs'].get(g,0)) for r in rec] for g in goods]
    external={'蓝铁矿':-34,'源矿':-18,'高容谷地电池':F(3,5),'精选荞愈胶囊':F(11,20)}
    rows=[a+[F(external.get(g,0)),F(0)] for a,g in zip(mat,goods)]
    loop=next(i for i,r in enumerate(rec) if r['machine']=='精炼炉' and '蓝铁粉末' in r['inputs'])
    rows.append([F(i==loop) for i in range(len(rec))]+[F(0),F(1)])
    pivot=0; sol={}
    for j in range(len(rec)):
        k=next((k for k in range(pivot,len(rows)) if rows[k][j]),None)
        if k is None:continue
        rows[pivot],rows[k]=rows[k],rows[pivot]
        a=rows[pivot][j];rows[pivot]=[x/a for x in rows[pivot]]
        for k in range(len(rows)):
            if k!=pivot and rows[k][j]:
                a=rows[k][j];rows[k]=[x-a*y for x,y in zip(rows[k],rows[pivot])]
        sol[j]=pivot;pivot+=1
    assert len(sol)==len(rec)
    assert all(all(x==0 for x in row) for row in rows[pivot:])
    batches=[tuple(rows[sol[j]][-2:]) for j in range(len(rec))]
    def fmt(v):return str(v[0])+(('+' if v[1]>0 else '')+str(v[1])+'*r' if v[1] else '')
    all_batches={}; duty={}
    for r,v in zip(rec,batches):
        old=all_batches.get(r['machine'],(0,0));all_batches[r['machine']]=tuple(a+b for a,b in zip(old,v))
        old=duty.get(r['machine'],(0,0));duty[r['machine']]=tuple(a+r['ticks']*b for a,b in zip(old,v))
    outputs=tuple((52 if i==0 else 0)+sum(v[i]*sum(r['outputs'].values()) for r,v in zip(rec,batches)) for i in (0,1))
    return dict(goods=goods,recipes=[dict(**r,batches=fmt(v),affine=[str(x) for x in v]) for r,v in zip(rec,batches)],rank=pivot-1,
        variables=len(rec),nullity=1,batches={k:fmt(v) for k,v in all_batches.items()},
        duty={k:fmt(v) for k,v in duty.items()},nontransport_output=fmt(outputs))

def one_machine(length,cap):
    # Given the support, a linear optimum fills the least-weight ports first.
    # All vertices of the total-flow polytope lie on the half-integer grid.
    best=[None]*(2*cap+1)
    for mask in range(1<<length):
        places=[i for i in range(length) if mask>>i&1]
        alpha={i:0 for i in places}
        for a,b in zip(places,places[1:]):
            if b-a<=3: alpha[a]+=1;alpha[b]+=1
        weights=sorted(alpha.values())
        for q in range(2*cap+1):
            d=F(q,2)
            if d>len(places): continue
            v=sum(weights[:q//2],0)+(F(weights[q//2],2) if q%2 else 0)
            if best[q] is None or v<best[q]: best[q]=v
    return best

def cost_tables():
    settings={'研磨机':(6,3,189,32,48,24),'塑形机':(3,2,22,6,11,9),
        '封装机':(6,5,30,3,8,24),'灌装机':(6,4,22,3,6,24)}
    result={}
    for typ,(length,cap,demand,nmin,nmax,area) in settings.items():
        one=one_machine(length,cap); dp={0:F(0)}; vals={}
        for n in range(1,nmax+1):
            nxt={}
            for q,old in dp.items():
                for z,w in enumerate(one):
                    if w is None or q+z>demand: continue
                    v=old+w
                    if q+z not in nxt or v<nxt[q+z]:nxt[q+z]=v
            dp=nxt
            if n>=nmin: vals[n]=dp[demand]
        base=vals[nmin]
        net={n:4*area*(n-nmin)+v-base for n,v in vals.items()}
        assert all(net[n+1]>net[n] for n in range(nmin,nmax))
        assert all(net[n+1]-net[n]>=34 for n in range(nmin,nmax))
        assert vals[nmax]==0
        result[typ]=dict(single=[str(x) for x in one],weight={str(n):str(v) for n,v in vals.items()},
            net_cost={str(n):str(v) for n,v in net.items()},first_cost=str(net[nmin+1]))
    return result

def budget(tables):
    weights={m:{int(n):F(v) for n,v in row['weight'].items()} for m,row in tables.items()}
    base=sum(v[min(v)] for v in weights.values())
    assert base==F(219,2)
    scalar=[]
    types=['粉碎机','精炼炉','配件机','塑形机','种植机','采种机','研磨机','封装机','灌装机','协议储存箱']
    # Enumerate at most two additions: any later marginal addition has nonnegative
    # weight and strictly increasing net area cost in the preceding exhaustive tables.
    areas=[9,9,9,9,25,25,24,24,24,9]
    for ex in product(range(3),repeat=len(types)):
        if sum(ex)>2:continue
        e=sum(a*v for a,v in zip(areas,ex)); w=base
        for typ,v in zip(types,ex):
            if typ in weights:
                n0=min(weights[typ]);w+=weights[typ][n0+v]-weights[typ][n0]
        for p in range(10,19):
            for j in range(p+1):
                if 10*j>23*p-217 or 25*j>54*p-520:continue
                if 4440+16*p-2*j+4*e+w>4751:continue
                scalar.append(dict(extras={t:v for t,v in zip(types,ex) if v},P=p,J=j,
                    extra_area=e,weight=str(w),XY_allowance=math.floor(F(4751)-4440-16*p+2*j-4*e-w)))
    only_single=[z for z in scalar if z['extras']]
    assert {tuple(z['extras'].items()) for z in only_single}=={((t,1),) for t in ['粉碎机','精炼炉','配件机','塑形机','协议储存箱']}
    assert all(z['P']==10 and z['J']==0 for z in only_single)
    shapes=sorted({tuple(sorted((w,h))) for w in range(6,69) for h in range(6,69) if 1110<=w*h<=1113})
    assert shapes==[(21,53),(30,37)]
    boundaries=[]
    # X0 counts the right and top edge, with their common corner counted twice.
    # c <= 1 core contact, t <= 2 exceptional 3x3 contacts, r = number of edge runs.
    for w,h in shapes:
        for right,top in product((False,True),repeat=2):
            length=138-int(right)*h-int(top)*w
            runs=3 if right!=top else 2
            for exception in (0,1):
                tmax=exception*(1 if right and top else 2)
                upper_constant=14+8*tmax+5*runs
                lower=math.ceil(F(length-upper_constant,6))
                boundaries.append(dict(shape=[w,h],area=w*h,right=right,top=top,exception=exception,
                    counted_length=length,runs=runs,exception_contacts=tmax,X_lower=lower))
    assert min(z['X_lower'] for z in boundaries if z['area']==1110 and z['exception']==1)==7
    assert min(z['X_lower'] for z in boundaries if not z['exception'])==7
    nextarea=max(w*h for w in range(6,69) for h in range(6,69) if w*h<1110)
    assert nextarea==1107
    return dict(base_weight=str(base),scalar_survivors=scalar,shapes=shapes,boundary_bounds=boundaries,next_below_1110=nextarea,
        note='The single-addition scalar survivors are all excluded by the edge and rectangle-neighbor argument in the report.')

def main():
    tables=cost_tables(); data=dict(flow=flow(),cost_tables=tables,budget=budget(tables))
    (OUT/'accounts_a.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'flow':data['flow']['batches'],'weights':{k:v['weight'] for k,v in tables.items()},
        'scalar_survivors':data['budget']['scalar_survivors'],'boundary_bounds':data['budget']['boundary_bounds']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
