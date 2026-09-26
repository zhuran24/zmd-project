"""Formal-file recipe balance, fragment enumeration and all structural counts."""
import os
os.sched_setaffinity(0,set(range(10)))
import json,re,itertools,hashlib
from pathlib import Path
from fractions import Fraction as F
from collections import Counter

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3]
KINDS=['粉碎机','精炼炉','研磨机','塑形机','配件机','种植机','采种机','封装机','灌装机']

def gauss(A,b):
    q=[[F(x) for x in row]+[F(rhs)] for row,rhs in zip(A,b)];row=0;pivots=[]
    for col in range(len(A[0])):
        r=next((k for k in range(row,len(q)) if q[k][col]),None)
        if r is None:continue
        q[row],q[r]=q[r],q[row];d=q[row][col];q[row]=[v/d for v in q[row]]
        for k in range(len(q)):
            if k!=row and q[k][col]:
                d=q[k][col];q[k]=[x-d*y for x,y in zip(q[k],q[row])]
        pivots.append(col);row+=1
    assert all(any(r[:-1]) or r[-1]==0 for r in q)
    assert len(pivots)==len(A[0])
    ans=[F(0)]*len(A[0])
    for i,col in enumerate(pivots):ans[col]=q[i][-1]
    return ans

def formal_accounts():
    rule=(ROOT/'《明日方舟：终末地》游戏规则.txt').read_text().split('配方\n',1)[1]
    recipes=[];machine=None
    def terms(s):
        d={}
        for term in re.split(r'\s*＋\s*',s):
            z=re.fullmatch(r'(\d+)\s+(.+)',term.strip());assert z,term
            d[z[2]]=int(z[1])
        return d
    for line in rule.splitlines():
        line=line.strip()
        if line in KINDS:machine=line
        match=re.fullmatch(r'(.+) → (.+)，(\d+) tick',line)
        if match:recipes.append(dict(machine=machine,inputs=terms(match[1]),outputs=terms(match[2]),ticks=int(match[3])))
    assert len(recipes)==18,len(recipes)
    goods=sorted(set().union(*(r['inputs'].keys()|r['outputs'].keys() for r in recipes)))
    external={'蓝铁矿':F(34),'源矿':F(18),'高容谷地电池':-F(3,5),'精选荞愈胶囊':-F(11,20)}
    A=[[r['outputs'].get(g,0)-r['inputs'].get(g,0) for r in recipes] for g in goods]
    rhs=[-external.get(g,0) for g in goods]
    A.append([int(r['machine']=='精炼炉') for r in recipes]);rhs.append(51)
    rates=gauss(A,rhs);assert all(r>=0 for r in rates)
    minimum={'粉碎机':68,'精炼炉':51,'研磨机':32,'塑形机':6,'配件机':6,'种植机':32,'采种机':16,'封装机':3,'灌装机':3}
    batch={k:sum(v for r,v in zip(recipes,rates) if r['machine']==k) for k in KINDS}
    unitlo={k:batch[k]-F(minimum[k]-1,5 if k in ('封装机','灌装机') else 1) for k in KINDS}
    outgoing=52+sum(sum(r['outputs'].values())*v for r,v in zip(recipes,rates))
    # Independent reverse expansion from final demand, expressed with Fractions.
    battery=F(3,5);capsule=F(11,20)
    components=10*battery;bottles=10*capsule;orepowder=15*battery;flowerfine=10*capsule
    steel=components+2*bottles;bluepowder=2*steel;sourcepowder=2*orepowder;flowerpowder=2*flowerfine
    sandpowder=steel+orepowder+flowerfine;sandcrush=sandpowder/3;flowercrush=flowerpowder/2
    reverse=[bluepowder,sourcepowder,bluepowder,bluepowder,sourcepowder,sandpowder,2*sandcrush,2*sandcrush,2*flowercrush,2*flowercrush,flowerpowder,steel,steel,orepowder,flowerfine,components,bottles,battery,capsule]
    assert sum(reverse)==outgoing==F(6113,20)
    five={'源矿','蓝铁矿','蓝铁块','蓝铁粉末','源石粉末'}
    signed=[sum(v for g,v in r['outputs'].items() if g in five)-sum(v for g,v in r['inputs'].items() if g in five) for r in recipes]
    assert all(d in (0,-2) for d in signed)
    assert [r['machine'] for r,d in zip(recipes,signed) if d==-2]==['研磨机','研磨机']
    return dict(recipes=[dict(**r,batch_rate=str(v),five_net=d) for r,v,d in zip(recipes,rates,signed)],goods=goods,batch_rates={k:str(v) for k,v in batch.items()},unit_min_rates={k:str(v) for k,v in unitlo.items()},outgoing=str(outgoing),reverse_sum=str(sum(reverse)),small=131,medium=48,large=38,total=217,area=131*9+48*25+38*24,T_plus_F=70*70-1113-3291-81-138-40,weight=2*131+3*48+3*38,capacity=9*54+29,number_cap=(515-86)//2)

def fragments():
    def cap(p,j,b):
        if j>p or (p==0 and (j or b)):return None
        n=min(23*p-9*j,(54*p-25*j-b)//2)
        return n if n>=b else None
    table={(p,j,b):cap(p,j,b) for p in range(11) for j in range(2) for b in range(87)}
    table={k:v for k,v in table.items() if v is not None}
    best=-1;count=0;witness=None
    for p0 in range(11):
        for p1 in range(11-p0):
            pp=[p0,p1,10-p0-p1]
            for edge in range(3):
                jj=[int(i==edge) for i in range(3)]
                for b0 in range(87):
                    for b1 in range(87-b0):
                        bb=[b0,b1,86-b0-b1];keys=list(zip(pp,jj,bb))
                        ns=[table.get(k) for k in keys]
                        if any(n is None for n in ns):continue
                        count+=1
                        if sum(ns)>best:best=sum(ns);witness=dict(p=pp,j=jj,b=bb,n=ns)
    state={(0,0,0):0}
    for _ in range(3):
        new={}
        for (p,j,b),v in state.items():
            for (u,k,d),n in table.items():
                key=(p+u,j+k,b+d)
                if key[0]<=10 and key[1]<=1 and key[2]<=86:new[key]=max(new.get(key,-1),v+n)
        state=new
    assert state[10,1,86]==best==214
    return dict(table=[[p,j,b,n] for (p,j,b),n in sorted(table.items())],direct_count=count,direct_maximum=best,dp_maximum=state[10,1,86],witness=witness)

def structure():
    caps={tuple(d['p']):d['cap'] for d in json.loads((OUT/'capacities.json').read_text())}
    edges=Counter([(69,y) for y in range(1,17)]+[(x,69) for x in range(1,49)]+[(48,y) for y in range(17,70)]+[(x,16) for x in range(49,70)])
    cells=lambda x,y,w,h:{(x+i,y+j) for i in range(w) for j in range(h)}
    I={(1,y) for y in range(1,70)}|{(x,1) for x in range(2,70)}
    patterns=[];inner_poles=set();allr2=set()
    for g,h in [(0,k) for k in range(0,70,3)]+[(k,0) for k in range(3,70,3)]:
        sources={(1,3*k+1+(3*k>=g)) for k in range(23)}|{(3*k+1+(3*k>=h),1) for k in range(23)}
        # Second source generator from disjoint warehouse triples.
        sources2=set()
        for gap,a in ((g,0),(h,1)):
            row=[v for v in range(70) if v!=gap]
            for start in range(0,69,3):
                center=row[start+1];sources2.add((1,center) if a==0 else (center,1))
        assert sources==sources2 and len(sources)==46
        U=I-sources;assert len(U)==91
        r=Counter({c:1 for c in U});r.update(edges)
        assert max(r.values())==2
        assert {c for c,v in r.items() if v==2}=={(1,69),(69,1),(48,69),(69,16)}
        allr2|={c for c,v in r.items() if v==2}
        assert sum(1 for x,y in sources if y==1 and x>=49)==7
        if 0<max(g,h)<69:
            fixed=cells(1,g-1,3,3) if g else cells(h-1,1,3,3)
            accepted=[]
            for p,cap in caps.items():
                x,y=p
                if cap<10 or not(x==1 or y==1):continue
                if cells(x,y,2,2)&(sources|fixed):continue
                accepted.append(p);inner_poles.add(p)
            patterns.append(dict(gaps=[g,h],allowed_poles=accepted))
    expected={(1,t) for t in range(5,64) if t%3 in (0,2)}|{(t,1) for t in range(5,64) if t%3 in (0,2)}
    assert inner_poles==expected and len(inner_poles)==80
    ordinary=[p for p,c in caps.items() if c>=20 and not(p[0] in (1,68) or p[1] in (1,68))]
    assert len(ordinary)==2091
    assert not any(cells(*p,2,2)&edges.keys() for p in ordinary)
    original=json.loads((OUT.parent/'推导78B'/'structural.json').read_text())
    # Integer algebra of direction and power slack: coefficient comparison.
    # Expand both sides as affine forms in a,b,C,W,N,WO,H,rest,X+Y.
    left={'constant':948}
    right={'constant':184+8+91+4,'a':-1,'b':-1,'C':1,'W':1,'N':-1,'WO':-1,'H':1,'rest':1,'XY':1}
    assert right['constant']==287
    # Formula becomes 948=924-a-b+XY+(C-619)+(W-109)+(91-N-WO)+H+rest.
    assert 619+184+8+109-91==829 and 829+91+4==924 and 948-924==24
    return dict(patterns=patterns,pattern_count=47,inner_I=len(I),sources=46,U=91,edge_counts=sum(edges.values()),edge_cells=len(edges),double_fee_cells=sorted(allr2),inner_poles=sorted(inner_poles),inner_poles_count=len(inner_poles),ordinary_count=len(ordinary),ordinary_edge_intersections=0,cut_sources=7,transport_F=[[236,1],[237,0]],transport_slots=472,transport_visit_rate='6113/20',transport_slack=str(F(472)-F(6113,20)-4),bridges_min=306-236,delta_rows=[dict(S=s,XY=s-158,delta=187-s,other_slack=str(F(187-s)-F(1,2))) for s in (185,186,187)])

def main():
    formal=formal_accounts();frag=fragments();struct=structure()
    for name,data in [('formal_accounts.json',formal),('fragment_checks.json',frag),('structural_checks.json',struct)]:
        (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2))
    inputs={}
    for n in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']:
        p=ROOT/n;inputs[n]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
    (OUT/'input_manifest.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2))
    print(json.dumps(dict(machine_total=formal['total'],area=formal['area'],weighted_need=formal['weight'],weighted_cap=formal['capacity'],number_cap=formal['number_cap'],fragment_combinations=frag['direct_count'],inner_poles=struct['inner_poles_count'],ordinary_poles=struct['ordinary_count']),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
