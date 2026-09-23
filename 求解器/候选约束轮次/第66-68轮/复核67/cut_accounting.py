#!/usr/bin/env python3
"""Independent exact recipe, cut-scope, and local capacity audit (stdlib)."""
from pathlib import Path
from fractions import Fraction as F
from itertools import product
from collections import defaultdict
import json
import re
import hashlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

def save(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def overlap(a,b):
    x,y,w,h=a;u,v,s,t=b
    return x<u+s and u<x+w and y<v+t and v<y+h

def parse_side(text):
    result={}
    for part in re.split('[＋+]',text):
        m=re.fullmatch(r'\s*(\d+)\s+(\S+)\s*',part)
        assert m,part
        count,item=m.groups();result[item]=int(count)
    return result

def solve(A,b):
    rows=[[F(v) for v in row]+[F(rhs)] for row,rhs in zip(A,b)]
    n=len(A[0]);i=0;pivots=[]
    for j in range(n):
        k=next((k for k in range(i,len(rows)) if rows[k][j]),None)
        if k is None:continue
        rows[k],rows[i]=rows[i],rows[k]
        pivot=rows[i][j];rows[i]=[v/pivot for v in rows[i]]
        for k in range(len(rows)):
            if k!=i:
                v=rows[k][j];rows[k]=[a-v*z for a,z in zip(rows[k],rows[i])]
        pivots.append(j);i+=1
    assert i==n and all(any(row[:-1]) or not row[-1] for row in rows)
    x=[F(0)]*n
    for i,j in enumerate(pivots):x[j]=rows[i][-1]
    assert all(sum(F(a)*v for a,v in zip(row,x))==rhs for row,rhs in zip(A,b))
    return x

def main():
    rule_path=ROOT/'《明日方舟：终末地》游戏规则.txt'
    rules=rule_path.read_text();recipes=[];machine=None
    for line in rules.split('\n配方\n',1)[1].splitlines():
        line=line.strip()
        if not line:continue
        if '→' not in line:machine=line;continue
        body,ticks=line.rsplit('，',1)
        left,right=body.split('→');duration=int(ticks.split()[0])
        recipes.append({'machine':machine,'input':parse_side(left),'output':parse_side(right),'ticks':duration})
    items=sorted({i for r in recipes for part in ['input','output'] for i in r[part]})
    assert len(recipes)==18 and len(items)==19
    ores=['源矿','蓝铁矿'];target={'高容谷地电池':F(3,5),'精选荞愈胶囊':F(11,20)}
    A=[];rhs=[]
    for item in items:
        A.append([r['output'].get(item,0)-r['input'].get(item,0) for r in recipes]+[int(item==i) for i in ores])
        rhs.append(target.get(item,0))
    recycling=next(i for i,r in enumerate(recipes) if r['machine']=='精炼炉' and '蓝铁粉末' in r['input'])
    # 34 ore smelts + 17 dense-powder smelts already use all 51 refiners.
    A.append([int(i==recycling) for i in range(20)]);rhs.append(0)
    rates=solve(A,rhs);K={'蓝铁矿','源矿','蓝铁块','蓝铁粉末','源石粉末'}
    work=defaultdict(F);kappa=defaultdict(F);dur={}
    for r,rate in zip(recipes,rates):
        m=r['machine'];work[m]+=rate*r['ticks'];dur[m]=r['ticks']
        kin=sum(v for i,v in r['input'].items() if i in K)
        kout=sum(v for i,v in r['output'].items() if i in K)
        kappa[m]=max(kappa[m],F(kin,r['ticks']))
        r.update({'rate':str(rate),'K_input':kin,'K_output':kout,'K_net':kout-kin})
    counts={m:(v.numerator+v.denominator-1)//v.denominator for m,v in work.items()}
    unitareas={'粉碎机':9,'精炼炉':9,'塑形机':9,'配件机':9,'种植机':25,'采种机':25,'研磨机':24,'封装机':24,'灌装机':24}
    assert sum(counts.values())==217 and sum(counts[m]*a for m,a in unitareas.items())==3291
    min_rate={m:(v-counts[m]+1)/dur[m] for m,v in work.items()}
    assert all(v>0 for v in min_rate.values())
    assert [r['K_net'] for r in recipes]==[0]*7+[-2,-2]+[0]*9
    assert kappa=={'粉碎机':1,'精炼炉':1,'研磨机':2,'塑形机':0,'配件机':0,'种植机':0,'采种机':0,'封装机':0,'灌装机':0}
    dims={'粉碎机':(3,),'精炼炉':(3,),'研磨机':(4,6),'塑形机':(3,),'配件机':(3,),
          '种植机':(5,),'采种机':(5,),'封装机':(4,6),'灌装机':(4,6),'协议核心':(9,),'供电桩':(2,)}
    min_penalty={m:min(h-kappa.get(m,0) for h in hs) for m,hs in dims.items()}
    assert min(min_penalty.values())==2
    save('recipe_accounting.json',{'rules_sha256':hashlib.sha256(rule_path.read_bytes()).hexdigest(),
         'recipes':recipes,'items':items,'ore_rates':{m:str(v) for m,v in zip(ores,rates[-2:])},
         'counts':counts,'area':3291,'single_machine_min_rate':{m:str(v) for m,v in min_rate.items()},
         'kappa':{m:str(v) for m,v in kappa.items()},'min_h_minus_kappa':{m:str(v) for m,v in min_penalty.items()}})

    ports={}
    for gap in range(0,70,3):
        starts=list(range(0,gap,3))+list(range(gap+1,70,3))
        occupied=[t for s in starts for t in range(s,s+3)]
        assert sorted(occupied)==[i for i in range(70) if i!=gap]
        ports[gap]=[s+1 for s in starts]
    joint=[(left,bottom) for left in ports for bottom in ports if left==0 or bottom==0]
    assert len(joint)==47
    assert {sum(49<=x<=69 for x in ports[bottom]) for left,bottom in joint}=={7}
    # Finite geometric audit of every cut in each stated row band. Include
    # port-invalid bodies too; this is a larger domain than an operating layout.
    shapes=[(3,3),(5,5),(6,4),(4,6),(9,9),(2,2)]
    bands=[(b,1,b-1) for b in (6,7,9,17)]+[(9,62,69)]
    cut_counts=[]
    for b,lo,hi in bands:
        rect=(49,b,21,53)
        for a in range(49,70):
            count=0
            for w,h in shapes:
                for x in range(max(1,a-w+1),min(a,71-w)):
                    for y in range(1,71-h):
                        r=(x,y,w,h)
                        if overlap(r,rect) or y>hi or y+h-1<lo:continue
                        assert lo<=y and y+h-1<=hi,(b,lo,hi,a,r)
                        count+=1
            cut_counts.append({'b':b,'rows':[lo,hi],'a':a,'crossing_rectangles':count})
    # Relative geometry check of the powered-machine -> powered 3x3 block step.
    subblocks=0
    for w,h in shapes[:4]:
        machine=(0,0,w,h)
        blocks=[(x,y,3,3) for x in range(w-2) for y in range(h-2)]
        for px in range(-8,w+7):
            for py in range(-8,h+7):
                pole=(px,py,2,2);power=(px-5,py-5,12,12)
                if not overlap(machine,power) or overlap(machine,pole):continue
                assert any(overlap(s,power) for s in blocks)
                subblocks+=1
    for dx,dy in product(range(-2,3),repeat=2):
        assert overlap((0,0,3,3),(dx,dy,3,3))
    # Every possible input/output visit to an ordinary transport storage or
    # one bridge axis has distinct incoming/outgoing neighbor. Count a chosen
    # physical edge in that visit: never twice. Dwell times are handled in proof.
    visits=[]
    for entry,exit in product(range(4),repeat=2):
        if entry==exit:continue
        for edge in range(4):
            used=int(entry==edge)+int(exit==edge)
            assert used<=1
            visits.append([entry,exit,edge,used])
    # Three admissible P=10 occupancy patterns; original no-lower/no-upper
    # tests overlap on 00. The listed disjoint assignment removes redundancy.
    occupancy=[]
    for lower,upper in product((0,1),repeat=2):
        if lower and upper:
            assert 7+7>23*10-217
            status='excluded_by_power'
        elif not lower:status='no_lower_branch'
        else:status='lower_present_and_no_upper_branch'
        occupancy.append({'lower':lower,'upper':upper,'case':status})
    area_values=sorted({w*h for w in range(6,69) for h in range(w,69) if w*h<1113})
    assert area_values[-1]==1110
    save('cut_geometry.json',{'boundary_layouts':joint,'boundary_ports':ports,'source_count':7,
         'cuts':cut_counts,'cut_count':len(cut_counts),'subblock_relative_cases':subblocks,
         'edge_visit_cases':len(visits),'P10_disjoint_occupancy_cases':occupancy,'next_area':1110})
    print('PASS: 18 recipes, 19 items, 217 machines, 3291 cells; 47 boundary layouts; '
          f'{len(cut_counts)} finite cut domains; {subblocks} powered-body cases; {len(visits)} edge-visit cases')

if __name__=='__main__':main()
