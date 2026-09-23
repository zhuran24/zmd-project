"""Independent one-dimensional boundary enumeration and integer recursion.
Rechecks all four corner branches and P=10,11,12. No producer code imports.
"""
from geometry77 import *
from itertools import product
from collections import defaultdict
import time

CORNERS=[(47,68,2,2),(68,15,2,2)]
BAD={('M','M'),('M','C'),('C','M'),('P','C'),('C','P')}

def bodies():
    answer=[]
    for kind,w,h,axis in [('M',w,h,a) for _,w,h,a in SPECS]+[('C',9,9,0),('C',9,9,1),('P',2,2,-1)]:
        for x in range(1,71-w):
            for y in range(1,71-h):
                r=(x,y,w,h)
                if not rect_allowed(r) or not cells(r)&WEIGHTS.keys():continue
                if kind=='M' and not all(any(map(allowed,e)) for e in edges(r,axis)):continue
                if kind=='C':
                    if max(x,y)<=3:continue
                    if not all(allowed(e[k]) for e in edges(r,axis) for k in (1,4,7)):continue
                    if sum(allowed(e[k]) for e in edges(r,1-axis) for k in range(1,8))<2:continue
                answer.append((kind,r))
    return answer

def project(r,line):
    positions=[i for i,c in enumerate(line) if c in cells(r)]
    if not positions:return None
    lo,hi=min(positions),max(positions)+1
    length=r[3] if line[0][0]==line[-1][0] else r[2]
    return lo,hi,(hi-lo==length)

def table(options,gaps):
    # Each path spells out every counted cell, either by a gap step or a full
    # interval. The previous unit type retains exactly the local port ban.
    levels=[{} for _ in range(len(gaps)+1)];levels[0]['G',0,0,0]=0
    for pos in range(len(gaps)):
        choices=list(options[pos])
        if gaps[pos]:choices.append((pos+1,'G',0,0,0,1))
        for (last,c,p,l),value in list(levels[pos].items()):
            for end,kind,dc,dp,dl,cost in choices:
                if (last,kind) in BAD or c+dc>1 or p+dp>12 or l+dl>59:continue
                state=(kind,c+dc,p+dp,l+dl);new=value+cost
                if new<levels[end].get(state,10**6):levels[end][state]=new
    final={}
    for (_,c,p,l),value in levels[-1].items():
        key=(c,p,l);final[key]=min(value,final.get(key,10**6))
    return final

def prune(states):
    by=defaultdict(list)
    for (c,p,l),v in states.items():by[c,p].append((l,v))
    result={}
    for (c,p),lv in by.items():
        best=10**6
        for l,v in sorted(lv):
            if v<best:result[c,p,l]=v;best=v
    return result

def main():
    t=time.monotonic();bs=bodies();shared=[r for k,r in bs if sum(project(r,line) is not None for line in LINES)>1]
    assert len(shared)==2 and set(shared)==set(CORNERS)
    caps={tuple(d['p']):d['cap'] for d in read(OUT/'capacities.json')}
    oldcaps={}
    for d in read(ROUNDS/'第66-68轮/推导66/power_certificates.json')['17']:
        p=(d['x'],d['y']);e=edge_count(p);c=min(23,len(d['tiles']),8 if e==2 else 13 if e else 23)
        x,y=p
        if 22<=y<=63 and 41<=x<=47:c=min(c,(13,14,14,17,18,19,22)[47-x])
        if 54<=x<=63 and 9<=y<=15:c=min(c,(13,14,14,17,18,19,22)[15-y])
        oldcaps[p]=c
    outputs={}
    for mode,capacities,filename in [('wall',oldcaps,'new_edge_certificate.json'),('local',caps,'new_edge_local_certificate.json')]:
        producer=read(ROUNDS/'第69-71轮/推导69'/filename);cases=[];results=[]
        for mask in product(range(2),repeat=2):
            pinned=[r for r,chosen in zip(CORNERS,mask) if chosen];tabs=[];savedtabs=[]
            provided=next(c for c in producer['cases'] if c['mask']==list(mask))
            for line,provided_line in zip(LINES,provided['lines']):
                options=[set() for _ in line];gaps=[1]*len(line)
                for r in pinned:
                    for i,c in enumerate(line):
                        if c in cells(r):gaps[i]=0
                for k,r in bs:
                    z=project(r,line)
                    if z is None or (r in CORNERS and r not in pinned):continue
                    if any(hit(r,s) and r!=s for s in pinned):continue
                    lo,hi,whole=z;tag=k if whole else 'Z'
                    dc=int(k=='C');dp=int(k=='P');loss=23-capacities[r[:2]] if dp else 0
                    J=int(dp and edge_count(r[:2])>0)
                    if r in pinned:dc=dp=loss=J=0
                    options[lo].add((hi,tag,dc,dp,loss,-2*J))
                assert [[list(v) for v in sorted(o)] for o in options]==provided_line['options']
                assert [1 if g else None for g in gaps]==provided_line['gaps']
                tab=table(options,gaps)
                assert all(tab[tuple(key)]==value for key,value in provided_line['frontier'])
                tabs.append(prune(tab));savedtabs.append(dict(frontier=[[list(k),v] for k,v in sorted(prune(tab).items())]))
            loss=sum(23-capacities[r[:2]] for r in pinned);J=len(pinned)
            assert provided['corner_loss']==loss
            cases.append(dict(mask=mask,corner_loss=loss,lines=savedtabs))
            for P in (10,11,12):
                budget=23*P-217-loss
                if budget<0:
                    results.append(dict(P=P,mask=mask,status='EXCLUDED_BY_CORNER_LOSS',loss=loss,budget=23*P-217));continue
                state={(0,0,0):0}
                for tab in tabs:
                    nxt={}
                    for (c,p,l),v in state.items():
                        for (C,Q,L),V in tab.items():
                            if c+C>1 or p+Q>P-J or l+L>budget:continue
                            key=(c+C,p+Q,l+L);nxt[key]=min(nxt.get(key,10**6),v+V)
                    state=prune(nxt)
                best=min(16*P-2*J+v-2*min(P-J-p,(budget-l)//10) for (c,p,l),v in state.items())
                wanted=next(z['min_S'] for z in producer['results'] if z['P']==P and z['corner_mask']==list(mask))
                assert wanted==best
                results.append(dict(P=P,mask=mask,min_S=best))
        outputs[mode]=dict(cases=cases,results=results)
    outputs['body_options']=len(bs);outputs['seconds']=time.monotonic()-t
    save('edge_checks.json',outputs)
    print(json.dumps({mode:outputs[mode]['results'] for mode in ('wall','local')},ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
