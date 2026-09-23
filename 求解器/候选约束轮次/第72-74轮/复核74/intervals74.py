"""Recompute the four corner branches and P=10,11,12 without source tables."""
from geometry74 import *
from collections import defaultdict
from itertools import product

FORBID={('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}

def frontier(table):
    best={};result={}
    for (c,p,l),v in sorted(table.items()):
        if v<best.get((c,p),100000):
            result[c,p,l]=v;best[c,p]=v
    return result

def calculate(units,line,forced,corners):
    ids={c:i for i,c in enumerate(sorted(line))}; n=len(line)
    blocks=[];reserved=set(); options=defaultdict(set)
    for r in forced:
        common=rect(*r)&line
        if common:
            a=min(ids[c] for c in common);b=max(ids[c] for c in common)+1
            blocks.append((a,b));reserved.update(range(a,b))
    for u in units:
        r=u['r']
        if u['kind']=='p' and tuple(r[:2]) in corners:continue
        common=rect(*r)&line
        if not common:continue
        a=min(ids[c] for c in common);b=max(ids[c] for c in common)+1
        if set(range(a,b))&reserved:continue
        full=len(common)==(r[3] if len({c[0] for c in line})==1 else r[2])
        typ=('C' if u['kind']=='c' else 'P' if u['kind']=='p' else 'M') if full else 'T'
        options[a].add((b,typ,int(u['kind']=='c'),int(u['kind']=='p'),u.get('loss',0),-2*u.get('j',0)))
    for a,b in blocks:options[a].add((b,'P',0,0,0,0))
    states=[{} for _ in range(n+1)];states[0]['',0,0,0]=0
    def update(pos,key,cost):states[pos][key]=min(states[pos].get(key,100000),cost)
    for a in range(n):
        for (prev,c,p,l),cost in list(states[a].items()):
            if a not in reserved:update(a+1,('',c,p,l),cost+1)
            for b,t,dc,dp,dl,dv in options[a]:
                if (prev,t) in FORBID or c+dc>1 or p+dp>12 or l+dl>59:continue
                update(b,(t,c+dc,p+dp,l+dl),cost+dv)
    table={}
    for (_,c,p,l),v in states[-1].items():table[c,p,l]=min(table.get((c,p,l),100000),v)
    return frontier(table)

def main():
    # Historical scalar relaxation omits core-distance strengthening.
    units=boundary_domain(core_rules=False);caps={tuple(d['p']):d for d in json.loads((OUT/'capacities.json').read_text())}
    for (x,y),d in caps.items():
        if rect(x,y,2,2).isdisjoint(WEIGHT):continue
        units.append(dict(kind='p',r=[x,y,2,2],**d))
    multiple=[(u['kind'],u['r']) for u in units if sum(not rect(*u['r']).isdisjoint(line) for line in LINES)>1]
    assert multiple==[('p',[47,68,2,2]),('p',[68,15,2,2])]
    corners={(47,68),(68,15)};results=[];cases=[]
    source=json.loads((ROUNDS/'第69-71轮/推导69/new_edge_local_certificate.json').read_text())
    for ci,mask in enumerate(product((0,1),repeat=2)):
        forced=[(*p,2,2) for p,b in zip(sorted(corners),mask) if b]
        tables=[calculate(units,line,forced,corners) for line in LINES]
        # Submitted frontiers are compared only after independent recomputation.
        comparisons=[]
        for no,(own,submitted) in enumerate(zip(tables,source['cases'][ci]['lines'])):
            expected={tuple(k):v for k,v in submitted['frontier']}
            comparisons.append(own==expected)
            assert own==expected,(ci,no,[(k,v,expected.get(k)) for k,v in own.items() if expected.get(k)!=v][:8])
        combined={(0,0,0):0}
        for tab in tables:
            new={}
            for (c,p,l),v in combined.items():
                for (dc,dp,dl),dv in tab.items():
                    if c+dc>1 or p+dp>12 or l+dl>59:continue
                    key=c+dc,p+dp,l+dl;new[key]=min(new.get(key,100000),v+dv)
            combined=frontier(new)
        count=len(forced); loss=sum(caps[r[:2]]['loss'] for r in forced)
        for P in (10,11,12):
            budget=23*P-217
            if loss>budget:results.append(dict(P=P,mask=mask,status='corner loss exceeds budget',loss=loss));continue
            opt=100000;arg=None
            for (c,p,l),value in combined.items():
                if p+count>P or l+loss>budget:continue
                omitted=min(P-p-count,(budget-l-loss)//10)
                score=16*P+value-2*count-2*omitted
                if score<opt:opt=score;arg=[c,p,l,value,omitted]
            results.append(dict(P=P,mask=mask,min_S=opt,resources=arg))
        cases.append(dict(mask=mask,corner_loss=loss,frontiers=[[[*k],v] for t in tables for k,v in t.items()],submitted_tables_match=comparisons))
    dump('interval_results.json',dict(units=len(units),multi_line_units=multiple,cases=cases,results=results))
    print('unit options',len(units))
    for r in results:print(r)

if __name__=='__main__':main()
