#!/usr/bin/env python3
"""Reconstruct four boundary projections and all corner/P branches."""
from recompute import *
from itertools import product

CORNERS=[(47,68,2,2),(68,15,2,2)]
FORBIDDEN={('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}

def geometry():
    result=[]
    for w,h,a in SHAPES+[(9,9,0),(9,9,1),(2,2,-1)]:
        k='C' if w==9 else 'P' if w==2 else 'M'
        for x in range(1,71-w):
            for y in range(1,71-h):
                r=(x,y,w,h)
                if intersects(r,HOLE) or not(cells(r)&TARGET):continue
                ps=[];ns=[]
                if k=='M':
                    ps=[[c for c in s if legal(c)] for s in sides(r,a)];ns=[1,1]
                elif k=='C':
                    take=[s[i] for s in sides(r,a) for i in (1,4,7)]
                    if not all(map(legal,take)):continue
                    ps=[[c] for c in take]+[[c for s in sides(r,1-a) for c in s[1:-1] if legal(c)]]
                    ns=[1]*6+[2]
                if any(len(s)<n for s,n in zip(ps,ns)):continue
                result.append((k,r,a,ps,ns))
    return result

def frontier(d):
    out={}
    for (c,p,l),v in sorted(d.items()):
        if not any(cc==c and pp==p and ll<=l and vv<=v for (cc,pp,ll),vv in out.items()):out[c,p,l]=v
    return out

def line_table(options,gaps):
    states=[{} for _ in range(len(gaps)+1)];states[0][('',0,0,0)]=0
    for x in range(len(gaps)):
        for (prev,c,p,l),value in states[x].items():
            if gaps[x] is not None:
                key=('',c,p,l);states[x+1][key]=min(states[x+1].get(key,10000),value+gaps[x])
            for end,tag,dc,dp,dl,fee in options[x]:
                if (prev,tag) in FORBIDDEN or c+dc>1 or p+dp>12 or l+dl>59:continue
                key=(tag,c+dc,p+dp,l+dl)
                states[end][key]=min(states[end].get(key,10000),value+fee)
    result={}
    for (prev,c,p,l),v in states[-1].items():result[c,p,l]=min(result.get((c,p,l),10000),v)
    return result

def projection(r,e):
    occupied=cells(r)&e
    if not occupied:return None
    horizontal=len({c[1] for c in e})==1
    axis=0 if horizontal else 1
    start=min(c[axis] for c in e)
    lo=min(c[axis] for c in occupied)-start
    hi=max(c[axis] for c in occupied)-start+1
    full=(hi-lo==r[2+axis])
    return lo,hi,full

def run():
    bs=geometry();loss=get_losses()
    multiple=[r for k,r,a,ps,ns in bs if sum(bool(cells(r)&e) for e in EDGES)>1]
    assert set(multiple)==set(CORNERS) and len(multiple)==2
    # Verify every complete forbidden adjacency by its real bodies/ports.
    checks=0
    for e in EDGES:
        parts=[(b,projection(b[1],e)) for b in bs if projection(b[1],e)]
        for left,l in parts:
            for right,r in parts:
                if not(l[2] and r[2] and l[1]==r[0] and (left[0],right[0]) in FORBIDDEN):continue
                both=cells(left[1])|cells(right[1])
                conflict=intersects(left[1],right[1]) or any(len(set(s)-both)<n for b in (left,right) for s,n in zip(b[3],b[4]))
                assert conflict;checks+=1
    submitted=read('第69-71轮/推导69/new_edge_local_certificate.json')
    answers=[];table_checks=0;option_count=0
    for mask in product((0,1),repeat=2):
        chosen=[r for i,r in enumerate(CORNERS) if mask[i]];tabs=[]
        case=next(c for c in submitted['cases'] if tuple(c['mask'])==mask)
        for no,e in enumerate(EDGES):
            n=len(e);options=[set() for _ in range(n)];gaps=[1]*n
            for r in chosen:
                pr=projection(r,e)
                if pr:
                    for pos in range(pr[0],pr[1]):gaps[pos]=None
            for k,r,a,ps,ns in bs:
                pr=projection(r,e)
                if not pr or (r in CORNERS and r not in chosen):continue
                if any(intersects(r,t) and r!=t for t in chosen):continue
                lo,hi,full=pr;tag=k if full else 'Z'
                dc=int(k=='C');dp=int(k=='P');dl=loss[r[:2]] if k=='P' else 0
                j=int(k=='P' and (r[0] in (1,68) or r[1] in (1,68)))
                if r in chosen:dc=dp=dl=j=0
                options[lo].add((hi,tag,dc,dp,dl,-2*j))
            ref=case['lines'][no]
            assert [sorted(o) for o in options]==[[tuple(o) for o in os] for os in ref['options']]
            assert gaps==ref['gaps']
            raw=line_table(options,gaps);tab=frontier(raw)
            assert tab=={tuple(k):v for k,v in ref['frontier']}
            table_checks+=1;option_count+=sum(map(len,options));tabs.append(raw)
        k=len(chosen);cl=sum(loss[r[:2]] for r in chosen)
        for P in (10,11,12):
            budget=23*P-217
            if cl>budget:
                answers.append(dict(mask=mask,P=P,excluded_by_corner_loss=cl,budget=budget));continue
            acc={(0,0,0):0}
            for tab in tabs:
                nxt={}
                for (c,p,l),v in acc.items():
                    for (cc,pp,ll),vv in tab.items():
                        if c+cc<=1 and p+pp<=P-k and l+ll<=budget-cl:
                            key=(c+cc,p+pp,l+ll);nxt[key]=min(nxt.get(key,10000),v+vv)
                acc=nxt
            best=min(v+16*P-2*k-2*min(P-k-p,(budget-cl-l)//10) for (c,p,l),v in acc.items())
            ref=next(t for t in submitted['results'] if t['P']==P and tuple(t['corner_mask'])==mask)
            assert best==ref['min_S']
            answers.append(dict(mask=mask,P=P,min_S=best))
    result=dict(body_options=len(bs),multiple_edge_rectangles=multiple,adjacency_pairs=checks,
                tables=table_checks,option_count=option_count,branches=answers)
    save('edges',result);print(json.dumps(result),flush=True)

if __name__=='__main__':run()
