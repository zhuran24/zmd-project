#!/usr/bin/env python3
"""Independent 1800-location filter: projected interval 0-1 programs, not DP.

Geometry is generated locally. The two measurements get separate resources.
No source audit scripts, result files, or projection caches are loaded.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='1'
import json,hashlib,time,warnings
from collections import defaultdict
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_array
from boundary62 import BASE,generate,measures,cells

def ports(k):
    free=3*k
    starts=list(range(0,free,3))+list(range(free+1,68,3))
    assert len(starts)==23
    return tuple(s+1 for s in starts)

PATTERNS=[(i,j) for i in range(24) for j in range(24) if i==0 or j==0]

def allowed_patterns(R):
    a,b,W,H=R
    return [(i,j) for i,j in PATTERNS
            if (a!=4 or sum(b<=p<b+H for p in ports(i))<=6)
            and (b!=4 or sum(a<=p<a+W for p in ports(j))<=6)]

def core_possible(body,patterns):
    x,y=body.x,body.y
    if x<2 or y<2 or (x<=3 and y<=3): return False
    for i,j in patterns:
        ml=sum(y<=p<y+9 for p in ports(i))
        md=sum(x<=p<x+9 for p in ports(j))
        if ml+3*(body.axis=='h')>(1 if y+9==70 else 2)*(x-1): continue
        if md+3*(body.axis=='v')>(1 if x+9==70 else 2)*(y-1): continue
        return True
    return False

def line_segments(R,mode):
    a,b,W,H=R; X,Y=measures(R)
    if mode=='Y':
        ans=[]
        if a>0: ans.append([(a-1,j) for j in range(b,b+H)])
        if a+W<70: ans.append([(a+W,j) for j in range(b,b+H)])
        if b>0: ans.append([(i,b-1) for i in range(a,a+W)])
        if b+H<70: ans.append([(i,b+H) for i in range(a,a+W)])
        return ans
    ans=[]
    for line in ([ (69,j) for j in range(1,69) ],[ (i,69) for i in range(1,69) ]):
        segment=[]
        for c in line:
            if c in X: segment.append(c)
            elif segment: ans.append(segment);segment=[]
        if segment: ans.append(segment)
    return ans

def interval_data(R,mode,corner):
    bodies,X,Y=generate(R,mode)
    patterns=allowed_patterns(R)
    lines=line_segments(R,mode)
    lookup={c:(s,i) for s,line in enumerate(lines) for i,c in enumerate(line)}
    corner_cells=set(cells(68,68,2,2)) if corner else set()
    # A fixed corner pole covers at most one cell of each 68-cell line.
    fixed={lookup[c] for c in corner_cells if c in lookup}
    tokens=set()
    for body in bodies:
        if body.kind=='c' and not core_possible(body,patterns): continue
        footprint=set(body.footprint())
        if mode=='X' and (69,69) in footprint: continue
        if footprint & corner_cells: continue
        if any(len(set(g)-corner_cells)<n for g,n in zip(body.ports,body.needs)): continue
        projection=defaultdict(list)
        for c in footprint:
            if c in lookup:
                s,i=lookup[c];projection[s].append(i)
        # Multi-line corner poles were removed. Y bodies cannot meet two sides.
        assert len(projection)<=1, (R,mode,body,projection)
        for s,indices in projection.items():
            l,r=min(indices),max(indices)+1
            assert len(indices)==r-l
            vertical=lines[s][0][0]==lines[s][-1][0]
            full=(r-l==(body.h if vertical else body.w))
            kind='M' if body.kind in ('s','m','l') else body.kind.upper()
            tokens.add((s,l,r,kind,int(full),body.loss if kind=='P' else 0))
    return [len(line) for line in lines],sorted(fixed),sorted(tokens)

CACHE={}
CANONICAL_CACHE={}
CACHE_PATH=BASE/'interval_cache.jsonl'
def canonical_key(lengths,fixed,tokens,P,loss,corner_cost):
    # Independent lines have no positional identity; retain their full token
    # sets, fixed cells and lengths, then sort whole lines (no reflection).
    signature=[]
    for s,length in enumerate(lengths):
        signature.append((length,tuple(sorted(j for ss,j in fixed if ss==s)),
                          tuple(sorted(tuple(t[1:]) for t in tokens if t[0]==s))))
    return hashlib.sha256(json.dumps([sorted(signature),P,loss,corner_cost]).encode()).hexdigest()

if CACHE_PATH.exists():
    for line in CACHE_PATH.read_text().splitlines():
        r=json.loads(line)
        if r['status']==0:
            CACHE[r['key']]=r
            ckey=canonical_key(r['lengths'],r['fixed'],r['tokens'],r['P'],r['loss_budget'],r['corner_cost'])
            if ckey in CANONICAL_CACHE: assert r['minimum']==CANONICAL_CACHE[ckey]['minimum']
            CANONICAL_CACHE[ckey]=r

def minimum(lengths,fixed,tokens,P,loss,corner_cost):
    key=hashlib.sha256(json.dumps([lengths,fixed,tokens,P,loss,corner_cost],sort_keys=True).encode()).hexdigest()
    if key in CACHE: return CACHE[key]['minimum'],key
    ckey=canonical_key(lengths,fixed,tokens,P,loss,corner_cost)
    if ckey in CANONICAL_CACHE:
        saved=CANONICAL_CACHE[ckey]
        return saved['minimum'],saved['key']
    n=len(tokens);rows=[];cols=[];vals=[];lower=[];upper=[]
    def row(data,hi):
        r=len(upper)
        for c,v in data:
            if v: rows.append(r);cols.append(c);vals.append(v)
        lower.append(-np.inf);upper.append(hi)
    hit=defaultdict(list);start=defaultdict(list);end=defaultdict(list)
    for i,(s,l,r,k,f,d) in enumerate(tokens):
        for j in range(l,r): hit[s,j].append(i)
        if f: start[s,l,k].append(i);end[s,r,k].append(i)
    for ids in hit.values(): row([(i,1) for i in ids],1)
    for s,j in fixed: row([(i,1) for i in hit[s,j]],0)
    forbidden={('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}
    for (s,pos,k),left in end.items():
        for k2 in ('M','C','P'):
            if (k,k2) in forbidden:
                right=start.get((s,pos,k2),[])
                # All members of each list already overlap internally. This
                # clique is equivalent to all cross-pair incompatibilities.
                if right: row([(i,1) for i in left+right],1)
    row([(i,1) for i,t in enumerate(tokens) if t[3]=='P'],P)
    row([(i,1) for i,t in enumerate(tokens) if t[3]=='C'],1)
    row([(i,t[5]) for i,t in enumerate(tokens)],loss)
    objective=np.array([-(t[2]-t[1]) for t in tokens],dtype=float)
    matrix=coo_array((np.array(vals,dtype=float),(np.array(rows,dtype=np.int32),np.array(cols,dtype=np.int32))),shape=(len(upper),n)).tocsc()
    before=time.monotonic()
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',message='Unrecognized options detected')
        res=milp(objective,integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.ones(n)),
            constraints=LinearConstraint(matrix,np.array(lower),np.array(upper)),
            options={'time_limit':120,'mip_rel_gap':0.0,'threads':1})
    if res.status!=0: raise RuntimeError(f'Interval solve incomplete: {key} {res}')
    rounded=np.rint(res.x)
    assert np.max(np.abs(rounded-res.x))<1e-5
    assert np.all(matrix@rounded <= np.array(upper)+1e-6)
    result=int(objective@rounded)+sum(lengths)-len(fixed)+corner_cost
    record={'key':key,'status':int(res.status),'minimum':result,'dual':float(res.mip_dual_bound+sum(lengths)-len(fixed)+corner_cost),
            'seconds':time.monotonic()-before,'lengths':lengths,'fixed':fixed,'tokens':tokens,'P':P,'loss_budget':loss,
            'corner_cost':corner_cost,'chosen_indices':[i for i,v in enumerate(rounded) if v]}
    assert abs(record['dual']-result)<1e-6
    with CACHE_PATH.open('a') as fp: fp.write(json.dumps(record,ensure_ascii=False)+'\n')
    CACHE[key]=record
    CANONICAL_CACHE[ckey]=record
    return result,key

def projected_bounds(R):
    X,Y=measures(R)
    dataY=interval_data(R,'Y',False)
    xcases=[(0,interval_data(R,'X',False))]
    if (69,69) in X and not (set(cells(68,68,2,2)) & set(cells(*R))):
        xcases.append((1,interval_data(R,'X',True)))
    result=[]
    for P in (10,11,12):
        budget=23*P-217
        yr,ykey=minimum(*dataY,P,budget,0)
        xv=[]
        for corner,data in xcases:
            if 15*corner>budget: continue
            cr=0 if corner or (69,69) not in X else 2
            xr,xkey=minimum(*data,P-corner,budget-15*corner,cr)
            xv.append((xr,xkey,corner))
        xr=min(x[0] for x in xv)
        allowance=187-16*P+2*((23*P-217)//9)
        result.append({'P':P,'X':xr,'Y':yr,'allowance':allowance,'pass':xr+yr<=allowance,
                       'X_models':xv,'Y_model':ykey})
    return result

def main():
    records=[];counts=defaultdict(int)
    # Each orientation is enumerated, while expensive optimization is reused
    # only after explicit coordinate-transpose equivalence of token data.
    for W,H in ((21,53),(53,21)):
        for a in range(71-W):
            for b in range(71-H):
                R=(a,b,W,H);rec={'R':R};counts['initial']+=1
                if a<4 or b<4: rec['reason']='distance'
                else:
                    counts['after_distance']+=1
                    if (a==4 and H>21) or (b==4 and W>21): rec['reason']='corridor_length'
                    else:
                        counts['after_corridor_length']+=1
                        pat=allowed_patterns(R)
                        rec['pattern_count']=len(pat)
                        if not pat: rec['reason']='exact_ports'
                        else:
                            counts['after_exact_ports']+=1
                            rec['bounds']=projected_bounds(R)
                            rec['reason']='survives' if any(r['pass'] for r in rec['bounds']) else 'interval_bound'
                            counts[rec['reason']]+=1
                            print(json.dumps({'R':R,'reason':rec['reason'],'bounds':[(v['P'],v['X'],v['Y'],v['pass']) for v in rec['bounds']], 'cache':len(CACHE)},ensure_ascii=False),flush=True)
                records.append(rec)
                with (BASE/'filter_progress.jsonl').open('a') as fp: fp.write(json.dumps(rec,ensure_ascii=False)+'\n')
    result={'counts':dict(counts),'records':records,'survivors':[r for r in records if r['reason']=='survives']}
    (BASE/'filter_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({'FINAL':dict(counts),'survivors':[r['R'] for r in result['survivors']]},ensure_ascii=False),flush=True)

if __name__=='__main__': main()
