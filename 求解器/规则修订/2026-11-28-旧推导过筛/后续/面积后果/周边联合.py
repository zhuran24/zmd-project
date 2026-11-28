"""联合放置两条外边及矩形周圈上的单位。仅投影到这些格，未列出的单位均可在投影外。"""
import sys
import json
import os
from collections import Counter, defaultdict
import ortools
from pathlib import Path
from ortools.sat.python import cp_model

def capacity(x,y,w,h,px,py):
    points=[]
    for a in range(max(1,px-7),min(68,px+7)):
        for b in range(max(1,py-7),min(68,py+7)):
            if (a<x+w and a+3>x and b<y+h and b+3>y or
                a<px+2 and a+3>px and b<py+2 and b+3>py):
                continue
            points.append((a,b))
    return min(23,*[len({((a-i)//3,(b-j)//3) for a,b in points})
                    for i in range(3) for j in range(3)])

def project(x, y, w, h, p, j, case, seconds, pattern=True):
    end_x, end_y = x+w, y+h
    delta, frees = {'base':(0,()), 'shaper':(34,(3,)), 'box':(36,(3,)),
                    'small':(36,(3,)), 'mix':(72,(3,3)), 'special':(136,(3,5))}[case]
    q = {(i,k) for i in range(x,end_x) for k in range(y,end_y)}
    boundary = Counter([(i,69) for i in range(1,70)]+[(69,i) for i in range(1,70)])
    for pt in q: boundary.pop(pt,None)
    ring = set([(x-1,i) for i in range(y,end_y)] + [(i,y-1) for i in range(x,end_x)])
    if end_x<70: ring.update((end_x,i) for i in range(y,end_y))
    if end_y<70: ring.update((i,end_y) for i in range(x,end_x))
    target = set(boundary) | ring
    model=cp_model.CpModel()
    occ=defaultdict(list)
    transport={}
    def tv(pt):
        if pt not in transport: transport[pt]=model.new_bool_var('')
        return transport[pt]
    def available(pt):
        return 1<=pt[0]<70 and 1<=pt[1]<70 and pt not in q
    def cover(cell,wd,ht):
        i,k=cell
        return ((i-a,k-b) for a in range(wd) for b in range(ht) if
                1<=i-a<=70-wd and 1<=k-b<=70-ht)
    units=defaultdict(list)
    placements=[]; edge_poles=[]; losses=[]; inner=[]; penalties=[]
    shapes=[('M',3,3,[0,1]),('M',5,5,[0,1]),('M',6,4,[1]),('M',4,6,[0]),
            ('C',9,9,[0,1]),('P',2,2,[-1])]
    for n in sorted(set(frees)): shapes.append((str(n),n,n,[-1]))
    for kind,wd,ht,axes in shapes:
        origins=set(origin for cell in target for origin in cover(cell,wd,ht))
        for i,k in sorted(origins):
            body=[(a,b) for a in range(i,i+wd) for b in range(k,k+ht)]
            if q.intersection(body): continue
            edge=(i==1 or k==1 or i+wd==70 or k+ht==70)
            if kind=='P' and edge and j==0: continue
            if kind=='P' and 23-capacity(x,y,w,h,i,k)>23*p-217: continue
            for axis in axes:
                need=[]
                if axis>=0:
                    for s in (-1,1):
                        if axis==0:
                            side=[(i-1 if s<0 else i+wd,k+b) for b in range(ht)]
                        else:
                            side=[(i+b,k-1 if s<0 else k+ht) for b in range(wd)]
                        if kind=='C': side=[side[t] for t in (1,4,7)]
                        good=[pt for pt in side if available(pt)]
                        if kind=='C':
                            if len(good)<3: break
                            need.extend([[pt] for pt in good])
                        elif good: need.append(good)
                        else: break
                    else: pass
                    if len(need)!=(6 if kind=='C' else 2): continue
                v=model.new_bool_var('')
                for pt in body: occ[pt].append(v)
                for side in need: model.add_bool_or([tv(pt) for pt in side]).only_enforce_if(v)
                units[kind].append(v); placements.append((kind,i,k,wd,ht,axis,v))
                if kind=='P':
                    num_edge=int(i in (1,68))+int(k in (1,68))
                    loss=max((0,10,15)[num_edge],23-capacity(x,y,w,h,i,k))
                    if i>=x+5 and i+7<=end_x:
                        g=max(y-(k+2),k-end_y)
                        if 0<=g<=6: loss=max(loss,(10,9,9,6,5,4,1)[g])
                    if k>=y+5 and k+7<=end_y:
                        g=max(x-(i+2),i-end_x)
                        if 0<=g<=6: loss=max(loss,(10,9,9,6,5,4,1)[g])
                    losses.append(loss*v)
                    if edge: edge_poles.append(v)
                    inner.append(sum(a==1 or b==1 for a,b in body)*v)
    patterns=[]
    if pattern and not os.environ.get('RELAX'):
        for gap in range(24):
            for swap in range(1 if gap==0 else 2):
                if os.environ.get('ELBOW') and not os.environ.get('RELAX') and (gap!=2 or swap): continue
                g1,g2=(gap,0) if not swap else (0,gap)
                rows=[3*i+1+int(i>=g1) for i in range(23)]
                cols=[3*i+1+int(i>=g2) for i in range(23)]
                if (x==4 and sum(y<=k<end_y for k in rows)>6 or
                    y==4 and sum(x<=i<end_x for i in cols)>6): continue
                v=model.new_bool_var(''); patterns.append((gap*3,swap,v))
                for pt in [(1,k) for k in rows]+[(i,1) for i in cols]:
                    if pt in occ:model.add_implication(v,tv(pt))
                penalties.append((9 if gap in (0,23) else 2 if gap in (1,22) else 0)*v)
        model.add_exactly_one(v for _,_,v in patterns)
    for pt,vs in occ.items(): model.add(sum(vs)+transport.get(pt,0)<=1)
    model.add(sum(units['C'])<=1)
    for n in set(frees):model.add(sum(units[str(n)])<=frees.count(n))
    model.add(sum(edge_poles)<=j)
    model.add(sum(units['P'])+j-sum(edge_poles)<=p)
    model.add(sum(losses)+10*(j-sum(edge_poles))<=23*p-217)
    K=sum(inner)+2*(j-sum(edge_poles))
    X=sum(c*(1-sum(occ[pt])) for pt,c in boundary.items())
    Y=sum(1-sum(occ[pt]) for pt in ring)
    model.add(X+Y+sum(penalties)-K <=4558-4*w*h-16*p-delta)
    elbow=os.environ.get('ELBOW','')
    if elbow and case in ('box','shaper','small'):
        # Optional restrictions only for finding a local witness.
        left=(x-3,67); bottom=(67,y-3)
        for kind,i,k,wd,ht,axis,v in placements:
            if kind=='3':
                if elbow=='left': model.add(v==int((i,k)==left))
                if elbow=='bottom': model.add(v==int((i,k)==bottom))
                if elbow=='neither' and (i,k) in (left,bottom): model.add(v==0)
                if elbow=='active': model.add(v==0)
    solver=cp_model.CpSolver(); solver.parameters.num_search_workers=4
    solver.parameters.max_time_in_seconds=seconds
    status=solver.solve(model)
    result=dict(rect=[x,y,w,h],P=p,J=j,case=case,status=solver.status_name(status),ortools=ortools.__version__,branches=solver.num_branches)
    if status in (cp_model.FEASIBLE,cp_model.OPTIMAL):
        result.update(X0=solver.value(X),Y0=solver.value(Y),K_upper=solver.value(K),
                      h=solver.value(sum(penalties)),
                      pattern=[r[:2] for r in patterns if solver.value(r[-1])],
                      placements=[r[:-1] for r in placements if solver.value(r[-1])])
    return result
if __name__=='__main__':
    *nums,case,seconds=sys.argv[1:]
    res=project(*map(int,nums),case,float(seconds))
    dest=Path(__file__).parent/('_'.join(sys.argv[1:-1])+os.environ.get('ELBOW','')+os.environ.get('RELAX','')+'.json')
    dest.write_text(json.dumps(res,ensure_ascii=False,indent=1))
    print({k:v for k,v in res.items() if k!='placements'},flush=True)
