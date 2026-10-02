#!/usr/bin/env python3
"""独立坐标生成 + 等长区间最优选择，重算 135 支及全部近边分支。"""
from pathlib import Path
from collections import Counter
import json

OUT=Path(__file__).resolve().parent

def overlap(a,b):
    return max(a[0],b[0])<=min(a[2],b[2]) and max(a[1],b[1])<=min(a[3],b[3])

def ports(g):
    starts=list(range(0,g,3))+list(range(g+1,70,3))
    assert len(starts)==23
    return [s+1 for s in starts]

def generate(gl,gb):
    left,bottom=ports(gl),ports(gb)
    ore={(1,y) for y in left}|{(x,1) for x in bottom}
    assert len(ore)==46
    options=[[],[]]
    for axis,ps in enumerate((left,bottom)):
        for p in ps:
            for offset in range(3):
                s=p-offset
                r=(2,s,4,s+2) if axis==0 else (s,2,s+2,4)
                if min(r[:2])<1 or max(r[2:])>69:continue
                if any(r[0]<=x<=r[2] and r[1]<=y<=r[3] for x,y in ore):continue
                options[axis].append(r)
    gap=None
    if gl not in (0,69):gap=(0,gl,(1,gl-1,3,gl+1))
    if gb not in (0,69):
        assert gap is None
        gap=(1,gb,(gb-1,1,gb+1,3))
    return ore,options,gap

def solve(options,forbidden,caps):
    rows=[[r for r in rs if not any(overlap(r,b) for b in forbidden)] for rs in options]
    # 若左右两组都选到 [2,4]^2，则必有交叠。反之两组完全独立。
    # 分别禁止一组碰该方块，两种情形覆盖所有可行集。
    best=-1
    for forbidden_axis in (0,1):
        count=[]
        for axis,rs in enumerate(rows):
            ints=sorted({(r[1],r[3]) if axis==0 else (r[0],r[2]) for r in rs},key=lambda t:t[1])
            end=-1;n=0
            for a,b in ints:
                if axis==forbidden_axis and a<=4:continue
                if a>end:n+=1;end=b
            count.append(min(n,caps[axis]))
        best=max(best,sum(count))
    return best

def evaluate(gl,gb,R=None):
    ore,options,gap=generate(gl,gb)
    d=0 if R is None else sum(x==1 and R[1]<=y<=R[3] for x,y in ore)
    caps=[22 if gb==3 else 23,22 if gl==3 else 23]
    base=[] if R is None else [R]
    rows=[dict(mode='none',value=46+solve(options,base,caps),d=d)]
    if gap is None:return rows
    axis,g,G=gap
    if R is not None and overlap(G,R):
        rows += [dict(mode=m,value=None,d=d,reason='gap_body_overlaps_rectangle') for m in ('plain','weighted')]
        return rows
    fixed=base+[G]
    rows.append(dict(mode='plain',value=48+solve(options,fixed,caps),d=d))
    extras=[]
    for edge in (g-2,g+2):
        if g==3 and edge==1:continue
        for across in (2,3):
            point=(across,edge) if axis==0 else (edge,across)
            Q=point+point
            if point not in ore and not any(overlap(Q,b) for b in base):extras.append(Q)
    if extras:
        normal=max(solve(options,fixed+[q],caps) for q in extras)
        tangent=1 if g==3 else 2
        rows.append(dict(mode='weighted',value=46+normal+tangent+1,d=d))
    else:
        rows.append(dict(mode='weighted',value=None,d=d,reason='no_second_input_neighbor'))
    return rows

def main():
    layouts=[(a,b) for a in range(0,70,3) for b in range(0,70,3) if a==0 or b==0]
    assert len(layouts)==47
    base=[];near=[];bad=[]
    for gl,gb in layouts:
        for row in evaluate(gl,gb):base.append(dict(gl=gl,gb=gb,**row))
        for H in range(6,10):
            for y in range(3,70-H):
                R=(2,y,7,y+H-1)
                d=sum(y<=p<=y+H-1 for p in ports(gl))
                if d>2:continue
                for row in evaluate(gl,gb,R):
                    rec=dict(gl=gl,gb=gb,H=H,y=y,**row)
                    near.append(rec)
                    if row['value'] is not None and row['value']+d>91:bad.append(rec)
    summary=dict(layouts=len(layouts),base_branches=len(base),
                 base_histogram=dict(Counter(r['value'] for r in base)),
                 near_total=len(near),near_reason=dict(Counter(r.get('reason','solved') for r in near)),
                 near_d_solved=dict(Counter(r['d'] for r in near if r['value'] is not None)),
                 base_max=max(r['value'] for r in base if r['value'] is not None),
                 near_max=max(r['value']+r['d'] for r in near if r['value'] is not None),
                 violations=bad)
    (OUT/'geometry.json').write_text(json.dumps(dict(summary=summary,base=base,near=near),ensure_ascii=False,indent=2)+'\n')
    assert len(base)==135 and len(near)==16739
    assert summary['base_max']==91 and summary['near_max']==91 and not bad
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
