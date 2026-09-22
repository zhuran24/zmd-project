#!/usr/bin/env python3
"""Inputs, dependency closure, finite geometric checks and original DP replay."""
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
from collections import Counter
import sys
from independent_boundary import patterns,targets,cells,loss,edge_cells,SHAPES

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
SOURCE=ROOT/'求解器/几何/1113放松'

def write(name,data): (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def entries(path):
    out={}; section=''; last=None
    for i,line in enumerate(path.read_text().splitlines(),1):
        if line and not line[0].isspace() and '：' in line:
            name,body=line.split('：',1)
            if body: out[name]=dict(line=i,text=body,deps=[],section=section); last=name
            else: section=name; last=None
        elif line.strip().startswith('据：') and last:
            out[last]['deps']=line.strip()[2:].split('、')
    return out

def main():
    names=['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']
    manifest={}
    for name in names:
        p=ROOT/name; data=p.read_bytes()
        manifest[name]=dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),text=data.decode())
    for p in SOURCE.rglob('*'):
        if p.is_file():
            manifest[str(p.relative_to(ROOT))]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
    write('input_manifest.json',manifest)
    old=entries(SOURCE/'input_snapshot/求解约束.txt'); new=entries(ROOT/'求解约束.txt')
    direct='空矩形上界 面积预算 内带缺口 供电下限 侧旁供电 矩形离带 矿石走廊 边带排布 角区 核心离带 核心邻格 取货口配置 端口对接 运输下限 通道下限 入库途径 机型下限'.split()
    closure=set(); external=set()
    def visit(n):
        if n not in new: external.add(n); return
        if n in closure: return
        closure.add(n)
        for d in new[n]['deps']: visit(d)
    for n in direct: visit(n)
    added={n:new[n] for n in new if n not in old}
    changed={n:dict(old=old[n],new=new[n]) for n in old.keys()&new.keys() if old[n]['text']!=new[n]['text'] or old[n]['deps']!=new[n]['deps']}
    write('dependencies.json',dict(direct=direct,closure={n:new[n] for n in sorted(closure,key=lambda n:new[n]['line'])},external=sorted(external),
          area_budget=new['面积预算'],added=added,changed=changed,
          counts=Counter(z['section'] for z in new.values()),
          rules_same=(ROOT/names[0]).read_bytes()==(SOURCE/'input_snapshot'/names[0]).read_bytes(),
          task_same=(ROOT/names[1]).read_bytes()==(SOURCE/'input_snapshot'/names[1]).read_bytes()))
    # Independent q test: neighboring warehouse cells expose no port toward q.
    q_counts=[]
    for body,ports in patterns():
        q=next(iter(({(0,k) for k in range(70)}|{(k,0) for k in range(70)})-body))
        neighbors={(q[0]+dx,q[1]+dy) for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]}
        usable={c for c in neighbors if 0<=c[0]<70 and 0<=c[1]<70 and c not in body}
        assert len(usable)<=1
        # Every warehouse port neighbor is internal (x=1 or y=1), hence never q.
        assert q not in ports
        q_counts.append(dict(q=q,possible_neighbors=sorted(usable)))
    # Area-otherwise branch: 4A+16P-2J<=4608. A+4P<=1182 bounds P<=17.
    p_bounds=[]
    for P in range(10,18):
        J=min(P,(23*P-217)//9)
        lhs=4*1113+16*P-2*J
        assert lhs>4608
        p_bounds.append(dict(P=P,J_max=J,lhs=lhs,limit=4608))
    # Every X/Y overlap counts two different directed missing interfaces.
    direction_checks=0; overlap_cells=0
    for W,H in [(21,53),(53,21)]:
        for a in range(4,71-W):
            for b in range(4,71-H):
                R=(a,b,W,H); X,Y,corner=targets(R); rc=cells(R)
                for x,y in X&Y:
                    outer=(1,0) if x==69 else (0,1)
                    toward=[(dx,dy) for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)] if (x+dx,y+dy) in rc]
                    assert len(toward)==1 and toward[0]!=outer
                    overlap_cells+=1
                direction_checks+=1
    # Independent single-pole bound versus original formula over all origins.
    spec=importlib.util.spec_from_file_location('original_dp',SOURCE/'filter_positions.py')
    f=importlib.util.module_from_spec(spec); spec.loader.exec_module(f)
    compared=0
    for R in [(49,5,21,53),(49,13,21,53),(49,17,21,53),(5,49,53,21),(13,49,53,21),(17,49,53,21)]:
        for x in range(1,69):
            for y in range(1,69):
                rr=(x,y,2,2)
                if cells(rr)&cells(R): continue
                assert loss(rr,R)[0]==f.pole_loss(rr,R)
                compared+=1
    # All full-block forbidden adjacencies in both directions block an obligatory port.
    adjacency_checks=0
    bad_pairs={('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}
    shapes=[('M',3,3),('M',4,6),('M',5,5),('C',9,9),('P',2,2)]
    for outer in [False,True]:
        for k,w,h in shapes:
            for K,W,H in shapes:
                if (k,K) not in bad_pairs: continue
                # Both sit on the same horizontal line; port edges run EW.
                r=(20,70-h if outer else 20,w,h)
                s=(20+w,70-H if outer else 20,W,H)
                bodies=cells(r)|cells(s)
                def blocked(kind,rect):
                    if kind=='P': return False
                    if kind=='C': return any(c in bodies for e in edge_cells(rect,0,[1,4,7]) for c in e)
                    return any(all(c in bodies for c in e) for e in edge_cells(rect,0))
                assert blocked(k,r) or blocked(K,s)
                adjacency_checks+=1
    write('geometry_checks.json',dict(q=q_counts,otherwise_branch=p_bounds,direction_rectangles=direction_checks,
          xy_overlap_cells=overlap_cells,pole_formula_comparisons=compared,full_block_adjacencies=adjacency_checks))
    # Replay original DP into our own subtree, not its source directory.
    f.ROOT=HERE/'dp_replay'; f.ROOT.mkdir(exist_ok=True)
    with (HERE/'dp_replay.log').open('w') as log,contextlib.redirect_stdout(log): f.main()
    replay=json.loads((f.ROOT/'positions.json').read_text())
    original=json.loads((SOURCE/'positions.json').read_text())
    assert replay['positions']==original['positions']
    assert replay['candidates']==original['candidates']
    write('dp_comparison.json',dict(position_records=len(replay['positions']),candidates=len(replay['candidates']),
          branches=sum(len(z['allowed_P']) for z in replay['candidates']),exact_match=True,seconds=replay['elapsed']))
    print('PASS',dict(added=len(added),changed=list(changed),recursive_constraints=len(closure),
          edge0_patterns=len(q_counts),dp_candidates=len(replay['candidates']),pole_comparisons=compared),flush=True)

if __name__=='__main__': main()
