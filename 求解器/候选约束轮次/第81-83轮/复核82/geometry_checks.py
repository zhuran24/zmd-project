"""两种几何编码核对内带、矩形端点与供电域；只写本目录。"""
import os
os.sched_setaffinity(0,{1})
from pathlib import Path
from itertools import product
from math import ceil
import json
OUT=Path(__file__).resolve().parent

def sources_walk(gap):
    free=[p for p in range(70) if p!=gap]
    groups=[free[i:i+3] for i in range(0,69,3)]
    assert all(b==a+1 and c==b+1 for a,b,c in groups)
    return [a[1] for a in groups]

def sources_formula(gap):
    # gap=3k；前 k 个三格取货口自 0 起，之后自 gap+1 起。
    k=gap//3
    return [3*i+1 for i in range(k)]+[3*i+2 for i in range(k,23)]

inner={(1,y) for y in range(1,70)}|{(x,1) for x in range(2,70)}
band_results=[]
for left_gap,bottom_gap in product(range(0,70,3),repeat=2):
    if left_gap and bottom_gap: continue
    la,ba=sources_walk(left_gap),sources_walk(bottom_gap)
    lb,bb=sources_formula(left_gap),sources_formula(bottom_gap)
    assert (la,ba)==(lb,bb)
    ore={(1,y) for y in la}|{(x,1) for x in ba}
    U=inner-ore; body_touch=set(); poles=[]
    for x,y in product(range(1,68),repeat=2):
        body={(x+i,y+j) for i in range(3) for j in range(3)}
        if body & inner and not body & ore: body_touch |= body & inner
    # 独立：找内带两臂中长度 >=3 的无矿口连续段。
    free_runs=[]
    for ids in (lb,bb):
        for lo,hi in zip([0]+ids,ids+[70]):
            if hi-lo-1>=3: free_runs.extend(range(lo+1,hi))
    formula_union=len(free_runs)
    assert len(body_touch)==formula_union
    for x,y in product(range(1,69),repeat=2):
        body={(x+i,y+j) for i in range(2) for j in range(2)}
        if not body & ore: poles.append(len(body & inner))
    band_results.append({'gaps':[left_gap,bottom_gap],'ore_count':len(ore),'inner_nonore':len(U),'large_body_possible_cells':sorted(body_touch),'large_body_cell_count':len(body_touch),'max_pole_inner_overlap':max(poles)})
assert len(band_results)==47
assert max(v['large_body_cell_count'] for v in band_results)==3
assert max(v['max_pole_inner_overlap'] for v in band_results)==2

def body_set_endpoint(W,H,core=False):
    rect={(x,y) for x in range(70-W,70) for y in range(70-H,70)}
    points=[(69-W,69),(69,69-H)]; hits=[]; tested=0
    shapes=[(9,9,0),(9,9,1)] if core else [(3,3,0),(3,3,1),(5,5,0),(5,5,1),(6,4,1),(4,6,0)]
    for point in points:
        for w,h,axis in shapes:
            for x in range(max(1,point[0]-w+1),min(point[0],70-w)+1):
                for y in range(max(1,point[1]-h+1),min(point[1],70-h)+1):
                    body={(x+i,y+j) for i in range(w) for j in range(h)}
                    if body&rect: continue
                    tested+=1
                    if core:
                        sides=[[(x-1,y+i) for i in (1,4,7)],[(x+9,y+i) for i in (1,4,7)]] if axis==0 else [[(x+i,y-1) for i in (1,4,7)],[(x+i,y+9) for i in (1,4,7)]]
                        ok=all(0<=a<70 and 0<=b<70 and (a,b) not in rect for side in sides for a,b in side)
                    else:
                        sides=[[(x-1,y+i) for i in range(h)],[(x+w,y+i) for i in range(h)]] if axis==0 else [[(x+i,y-1) for i in range(w)],[(x+i,y+h) for i in range(w)]]
                        ok=all(any(0<=a<70 and 0<=b<70 and (a,b) not in rect for a,b in side) for side in sides)
                    if ok: hits.append([point,x,y,w,h,axis])
    return tested,hits

endpoints=[]
for W,H in [(30,37),(37,30)]:
    for core in (False,True):
        n,hits=body_set_endpoint(W,H,core)
        assert not hits
        # 区间编码：上边端点的机身必须顶边 y+h=70、右边 x+w=70-W；
        # 上下端口则上口出界，左右端口则右口落在空矩形。右端点转置。
        failures_by_interval=all(h<=H and w<=W for w,h in ([(9,9)] if core else [(3,3),(5,5),(6,4),(4,6)]))
        assert failures_by_interval
        endpoints.append({'W':W,'H':H,'core':core,'tested':n,'valid_placements':len(hits),'interval_check':True})

out={'band_cases':band_results,'endpoint_cases':endpoints,'boundary_bounds':[],
     'cut_h_minus_kappa':{'小制造矿物配方':3-1,'研磨横向':4-2,'研磨纵向':6-2,'箱体':3-3,'供电桩':2,'协议核心':9},
     'group_overlap_check':True}
for L,k,t in [(71,2,1),(101,3,2),(138,2,2),(71,2,0)]:
    # 第一种代数；第二种直接遍历 X 并最大化 m,c,t 的整数必要条件。
    algebra=ceil((L-14-8*t-5*k)/6)
    direct=next(X for X in range(139) if any(L<=5*m+9*c+3*e+X for c in range(2) for e in range(t+1) for m in range(X+c+e+k+1)))
    assert algebra==direct
    out['boundary_bounds'].append({'L':L,'k':k,'t':t,'algebra':algebra,'integer_enumeration':direct})
for a,b in product(range(3),repeat=2):
    groups={}
    for x,y in product(range(-5,7),repeat=2): groups.setdefault(((x+a)//3,(y+b)//3),[]).append((x,y))
    assert all(abs(x-u)<=2 and abs(y-v)<=2 for points in groups.values() for x,y in points for u,v in points)
(OUT/'geometry_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'band_cases':47,'max_body_band_cells':max(r['large_body_cell_count'] for r in band_results),'max_pole_band_cells':2,'endpoint_cases':endpoints,'boundary_bounds':out['boundary_bounds']},ensure_ascii=False))
