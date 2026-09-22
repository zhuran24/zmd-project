#!/usr/bin/env python3
"""Review 61: independent cell-incidence boundary relaxation, no DP imports.

Writes only JSON below this script. Use python -B to avoid bytecode elsewhere.
The omitted bodies, transport, power coverage and flow are existentially relaxed.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import time
from ortools.sat.python import cp_model

HERE = Path(__file__).resolve().parent
SHAPES = [('small',3,3,0),('small',3,3,1),('medium',5,5,0),
          ('medium',5,5,1),('large',6,4,1),('large',4,6,0),
          ('core',9,9,0),('core',9,9,1),('pole',2,2,None)]

def cells(r):
    x,y,w,h = r
    return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}

def overlap(r,s):
    x,y,w,h=r; a,b,W,H=s
    return max(x,a)<min(x+w,a+W) and max(y,b)<min(y+h,b+H)

def edge_cells(r,axis,offsets=None):
    x,y,w,h=r
    ks=range(h if axis==0 else w) if offsets is None else offsets
    if axis==0:
        return [[(x-1,y+k) for k in ks],[(x+w,y+k) for k in ks]]
    return [[(x+k,y-1) for k in ks],[(x+k,y+h) for k in ks]]

def loss(r,R):
    x,y,_,_=r; a,b,w,h=R
    edge=(1 in (x,x+1) or 69 in (x,x+1))+(1 in (y,y+1) or 69 in (y,y+1))
    bounds=[(0,9,15)[edge]]
    for low,high,p,gaps in [(b,b+h,y,[a-x-2,x-a-w]),(a,a+w,x,[b-y-2,y-b-h])]:
        if low<=p-5 and p+7<=high:
            bounds += [(10,9,9,6,5,4,1)[g] for g in gaps if 0<=g<=6]
    return max(bounds),bool(edge)

def targets(R):
    a,b,w,h=R; rc=cells(R)
    X=({(69,k) for k in range(1,69)}|{(k,69) for k in range(1,69)})-rc
    Y=set()
    for c in rc:
        for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            q=c[0]+dx,c[1]+dy
            if q not in rc and 0<=q[0]<70 and 0<=q[1]<70: Y.add(q)
    return X,Y,(69,69) not in rc

def enumerate_bodies(R,edge0=True):
    X,Y,corner=targets(R); rc=cells(R)
    touch=X|Y|({(69,69)} if corner else set())
    low=1 if edge0 else 0
    def usable(c): return low<=c[0]<70 and low<=c[1]<70 and c not in rc
    out=[]
    for kind,w,h,axis in SHAPES:
        for x in range(1,71-w):
            for y in range(1,71-h):
                r=(x,y,w,h)
                if overlap(r,R): continue
                cc=cells(r)
                if not cc&touch: continue
                need=[]
                if kind=='core':
                    oo=[c for e in edge_cells(r,axis,[1,4,7]) for c in e]
                    ii=[c for e in edge_cells(r,1-axis,range(1,8)) for c in e if usable(c)]
                    if not all(map(usable,oo)) or len(ii)<2: continue
                    need=[(1,[c]) for c in oo]+[(2,ii)]
                elif kind!='pole':
                    es=[[c for c in e if usable(c)] for e in edge_cells(r,axis)]
                    if not all(es): continue
                    need=[(1,e) for e in es]
                ll,ee=loss(r,R) if kind=='pole' else (0,False)
                out.append(dict(kind=kind,rect=r,axis=axis,cells=cc,need=need,loss=ll,edge=ee,
                                xc=len(cc&X)+(2 if corner and kind=='pole' and (69,69) in cc else 0),yc=len(cc&Y)))
    return out,X,Y,corner

def build(R,edge0=True,minimize=False):
    bd,X,Y,corner=enumerate_bodies(R,edge0)
    m=cp_model.CpModel()
    vs=[m.new_bool_var(f'body_{i}') for i in range(len(bd))]
    cov=defaultdict(list)
    for i,d in enumerate(bd):
        for c in d['cells']: cov[c].append(vs[i])
    for vv in cov.values(): m.add(sum(vv)<=1)
    for i,d in enumerate(bd):
        for k,cs in d['need']:
            m.add(k*vs[i]+sum(v for c in cs for v in cov[c])<=len(cs))
    for kind,cap in [('small',131),('medium',48),('large',38),('core',1)]:
        m.add(sum(v for v,d in zip(vs,bd) if d['kind']==kind)<=cap)
    P=m.new_int_var(10,12,'P')
    missing=m.new_int_var(0,12,'omitted_poles')
    missing_edge=m.new_int_var(0,12,'omitted_edge_poles')
    m.add(sum(v for v,d in zip(vs,bd) if d['kind']=='pole')+missing==P)
    m.add(missing_edge<=missing)
    J=sum(v for v,d in zip(vs,bd) if d['edge'])+missing_edge
    m.add(sum(v*d['loss'] for v,d in zip(vs,bd))+9*missing_edge<=23*P-217)
    xval=len(X)+2*corner-sum(v*d['xc'] for v,d in zip(vs,bd))
    yval=len(Y)-sum(v*d['yc'] for v,d in zip(vs,bd))
    S=16*P-2*J+xval+yval
    if minimize: m.minimize(S)
    else: m.add(S<=187)
    return m,dict(bodies=bd,vs=vs,P=P,J=J,X=xval,Y=yval,S=S,missing=missing,missing_edge=missing_edge)

def verify(R,chosen,P,J,hidden,hidden_edge,edge0):
    occ=set(); totals=Counter(); deficit=9*hidden_edge; edge_count=hidden_edge
    low=1 if edge0 else 0; rc=cells(R)
    for d in chosen:
        cc=cells(d['rect']); assert not (cc&rc or cc&occ)
        assert all(1<=x<70 and 1<=y<70 for x,y in cc)
        occ|=cc; totals[d['kind']]+=1
        if d['kind']=='pole':
            ll,ee=loss(d['rect'],R); deficit+=ll; edge_count+=ee
    def available(c): return low<=c[0]<70 and low<=c[1]<70 and c not in occ and c not in rc
    for d in chosen:
        k,r,ax=d['kind'],d['rect'],d['axis']
        if k=='core':
            assert all(available(c) for e in edge_cells(r,ax,[1,4,7]) for c in e)
            assert sum(available(c) for e in edge_cells(r,1-ax,range(1,8)) for c in e)>=2
        elif k!='pole': assert all(any(map(available,e)) for e in edge_cells(r,ax))
    for k,cap in [('small',131),('medium',48),('large',38),('core',1)]: assert totals[k]<=cap
    assert totals['pole']+hidden==P and 0<=hidden_edge<=hidden and J==edge_count
    assert deficit<=23*P-217
    X,Y,corner=targets(R)
    corner_pole=any(d['kind']=='pole' and (69,69) in cells(d['rect']) for d in chosen)
    return len(X-occ)+2*(corner and not corner_pole),len(Y-occ)

def solve(R,edge0=True,minimize=False,seconds=60):
    t=time.monotonic(); m,d=build(R,edge0,minimize)
    assert not m.validate(),m.validate()
    solver=cp_model.CpSolver(); solver.parameters.num_search_workers=4
    solver.parameters.max_time_in_seconds=seconds; solver.parameters.random_seed=61
    status=solver.solve(m)
    out=dict(rect=R,edge0=edge0,minimize=minimize,status=solver.status_name(status),
             seconds=time.monotonic()-t,workers=4,body_count=len(d['bodies']),response=solver.response_stats())
    if minimize: out['best_bound']=solver.best_objective_bound
    if status in (cp_model.FEASIBLE,cp_model.OPTIMAL):
        chosen=[{k:z[k] for k in ('kind','rect','axis')} for v,z in zip(d['vs'],d['bodies']) if solver.value(v)]
        for k in ('P','J','X','Y','S','missing','missing_edge'): out[k]=solver.value(d[k])
        xx,yy=verify(R,chosen,out['P'],out['J'],out['missing'],out['missing_edge'],edge0)
        assert (xx,yy)==(out['X'],out['Y'])
        out['witness']=chosen; out['witness_checked']=True
    return out

def patterns():
    out=[]
    for left in range(24):
        for bottom in range(24):
            if left and bottom: continue
            ports=[]; body=set()
            for axis,gap in [(0,3*left),(1,3*bottom)]:
                remaining=[k for k in range(70) if k!=gap]
                for i in range(0,69,3):
                    seg=remaining[i:i+3]; assert seg==list(range(seg[0],seg[0]+3))
                    cc={(0,k) if axis==0 else (k,0) for k in seg}
                    assert not cc&body; body|=cc
                    ports.append((1,seg[1]) if axis==0 else (seg[1],1))
            assert len(body)==138 and len(set(ports))==46
            out.append((body,ports))
    assert len(out)==47
    return out

def write(name,data): (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('mode',choices=['sweep','minima'])
    args=ap.parse_args(); results=[]
    if args.mode=='minima':
        for b in [5,6,7,8,9,10,11,12,13,14,17]:
            for R in [(49,b,21,53),(b,49,53,21)]:
                row=solve(R,minimize=True); results.append(row)
                print({k:v for k,v in row.items() if k not in ('response','witness')},flush=True)
                write('minima.json',results)
        results.append(solve((49,13,21,53),edge0=False,minimize=True))
        write('minima.json',results)
    else:
        pats=patterns(); t=time.monotonic()
        for a in range(50):
            for b in range(18):
                R=(a,b,21,53)
                if a<4 or b<4: row=dict(rect=R,status='矩形离带')
                elif a==4: row=dict(rect=R,status='矿石走廊长度')
                elif not any(b!=4 or sum(a<=x<a+21 for x,y in ports if y==1)<=6 for _,ports in pats):
                    row=dict(rect=R,status='矿石走廊端口数')
                else:
                    row=solve(R)
                    if row['status']=='UNKNOWN': row=solve(R,seconds=180)
                results.append(row)
                if len(results)%20==0:
                    write('sweep.json',results)
                    print(len(results),round(time.monotonic()-t,2),dict(Counter(z['status'] for z in results)),flush=True)
        write('sweep.json',results)
        print('FINAL',dict(Counter(z['status'] for z in results)),flush=True)

if __name__=='__main__': main()
