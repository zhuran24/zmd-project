#!/usr/bin/env python3
"""Exhaustiveness and local incompatibility checks using brute-force anchors."""
import json
from collections import defaultdict
from boundary62 import BASE,generate,measures
from filter62 import PATTERNS,ports,line_segments,core_possible,allowed_patterns

def brute(R):
    a,b,W,H=R
    rect={(i,j) for i in range(a,a+W) for j in range(b,b+H)}
    X={};Y={}
    for x in range(70):
        for y in range(70):
            c=(x,y)
            if c in rect: continue
            weight=int(x==69 and 1<=y<=68)+int(y==69 and 1<=x<=68)+2*int(x==69 and y==69)
            if weight: X[c]=weight
            if any((x+dx,y+dy) in rect for dx,dy in [(0,1),(0,-1),(1,0),(-1,0)]): Y[c]=1
    targets=set(X)|set(Y)
    def legal(c): return 1<=c[0]<70 and 1<=c[1]<70 and c not in rect
    shapes=[('s',3,3,'h'),('s',3,3,'v'),('m',5,5,'h'),('m',5,5,'v'),
            ('l',6,4,'v'),('l',4,6,'h'),('c',9,9,'h'),('c',9,9,'v'),('p',2,2,'-')]
    result=set();count=0
    for kind,w,h,axis in shapes:
        for x in range(1,71-w):
            for y in range(1,71-h):
                count+=1
                body={(i,j) for i in range(x,x+w) for j in range(y,y+h)}
                if body&rect or not body&targets: continue
                left=[(x-1,j) for j in range(y,y+h)];right=[(x+w,j) for j in range(y,y+h)]
                down=[(i,y-1) for i in range(x,x+w)];up=[(i,y+h) for i in range(x,x+w)]
                active=(left,right) if axis=='h' else (down,up)
                if kind=='c':
                    if not all(legal(side[q]) for side in active for q in [1,4,7]): continue
                    storage=(down,up) if axis=='h' else (left,right)
                    if sum(legal(side[q]) for side in storage for q in range(1,8))<2: continue
                elif kind!='p' and not all(any(legal(c) for c in side) for side in active): continue
                result.add((kind,x,y,w,h,axis))
    return result,X,Y,count

def pair_check(R,mode):
    bodies,X,Y=generate(R,mode)
    lines=line_segments(R,mode);lookup={c:(s,i) for s,line in enumerate(lines) for i,c in enumerate(line)}
    starts=defaultdict(list);ends=defaultdict(list);seen=0
    footprints=[set(b.footprint()) for b in bodies]
    for i,body in enumerate(bodies):
        if body.kind=='c' and not core_possible(body,allowed_patterns(R)): continue
        if mode=='X' and (69,69) in footprints[i]: continue
        proj=defaultdict(list)
        for c in footprints[i]:
            if c in lookup:
                s,j=lookup[c];proj[s].append(j)
        assert len(proj)<=1
        for s,indices in proj.items():
            l,r=min(indices),max(indices)+1
            vertical=lines[s][0][0]==lines[s][-1][0]
            if r-l!=(body.h if vertical else body.w): continue
            kind='M' if body.kind in 'sml' else body.kind.upper()
            starts[s,l,kind].append(i);ends[s,r,kind].append(i)
    forbidden={('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}
    for (s,j,k),left in ends.items():
        for k2 in ('M','C','P'):
            if (k,k2) not in forbidden: continue
            for i in left:
                for t in starts.get((s,j,k2),[]):
                    seen+=1
                    b1,b2=bodies[i],bodies[t]
                    clash=bool(footprints[i]&footprints[t])
                    clash |= any(len(set(group)-footprints[t])<need for group,need in zip(b1.ports,b1.needs))
                    clash |= any(len(set(group)-footprints[i])<need for group,need in zip(b2.ports,b2.needs))
                    assert clash,(R,mode,b1,b2)
    return seen

def main():
    patterns=[]
    # Independently tile 70 positions by 23 length-three blocks and one hole.
    # The hole must separate two runs, each of length divisible by three.
    for hole in range(70):
        if hole%3==0 and (69-hole)%3==0:
            occupied=set(range(70))-{hole}
            starts=[s for s in range(70) if s in occupied and (s<hole and s%3==0 or s>hole and (s-hole-1)%3==0)]
            assert {i for s in starts for i in range(s,s+3)}==occupied
            assert tuple(s+1 for s in starts)==ports(hole//3)
            patterns.append((hole,starts))
    joint=0
    for lh,ls in patterns:
        for dh,ds in patterns:
            lbody={(0,y) for s in ls for y in range(s,s+3)}
            dbody={(x,0) for s in ds for x in range(s,s+3)}
            if lbody&dbody: continue
            assert len(lbody|dbody)==138
            take={(1,s+1) for s in ls}|{(s+1,1) for s in ds}
            assert len(take)==46 and not take&(lbody|dbody)
            joint+=1
    assert joint==len(PATTERNS)==47
    locations=[tuple(r['R']) for r in json.loads((BASE/'candidate_summary.json').read_text())]
    locations += [(5,4,21,53),(4,5,53,21),(5,5,21,53),(20,8,21,53),
                  (35,9,21,53),(48,16,21,53),(49,16,21,53),(49,15,21,53)]
    results=[]
    for R in locations:
        truth,X,Y,attempts=brute(R)
        bodies,gX,gY=generate(R)
        got={(u.kind,u.x,u.y,u.w,u.h,u.axis) for u in bodies}
        assert truth==got and X==dict(gX) and Y==dict(gY)
        pairs=pair_check(R,'X')+pair_check(R,'Y')
        row={'R':R,'brute_anchors':attempts,'valid_bodies':len(got),'tested_forbidden_pairs':pairs,'passed':True}
        results.append(row);print(json.dumps(row),flush=True)
    summary={'single_edge_patterns':len(patterns),'joint_edge_patterns':joint,'results':results,
             'total_anchor_attempts':sum(r['brute_anchors'] for r in results),
             'total_forbidden_pairs':sum(r['tested_forbidden_pairs'] for r in results),'all_passed':True}
    (BASE/'geometry_checks.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
