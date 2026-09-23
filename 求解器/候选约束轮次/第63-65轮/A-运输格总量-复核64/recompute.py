#!/usr/bin/env python3
"""Round 64 independent reconstruction; does not import derivation scripts.

All generated files are confined to this script's directory.
Use PYTHONDONTWRITEBYTECODE=1 when running.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import platform
import time

from ortools.sat.python import cp_model
import ortools

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OFFICIAL = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']


def save(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def footprint(x, y):
    return tuple((x + u, y + v) for u in range(3) for v in range(3))


def boundary(left_gap, bottom_gap):
    """Construct warehouses as actual triples; zero-based gap coordinates."""
    warehouses = set()
    sources = []
    for axis, gap in [('left', left_gap), ('bottom', bottom_gap)]:
        cells = [p for p in range(70) if p != gap]
        for k in range(23):
            a, b, c = cells[3*k:3*k+3]
            assert b == a+1 and c == b+1
            block = {(0,p) for p in (a,b,c)} if axis == 'left' else {(p,0) for p in (a,b,c)}
            assert not (warehouses & block)
            warehouses.update(block)
            sources.append((1,b) if axis == 'left' else (b,1))
    assert len(warehouses) == 138 and len(set(sources)) == 46
    assert not warehouses.intersection(sources)
    edge = {(0,k) for k in range(70)} | {(k,0) for k in range(70)}
    q, = edge - warehouses
    return warehouses, sources, q


def candidate_domain(left_gap, bottom_gap, cap):
    warehouses, sources, q = boundary(left_gap, bottom_gap)
    blocked = warehouses | set(sources)
    bodies = []
    # Include row/column zero initially and exclude them by actual occupied cells.
    for x in range(68):
        for y in range(68):
            cells = footprint(x,y)
            if blocked.isdisjoint(cells):
                assert x >= 1 and y >= 1
                bodies.append((x,y,cells))
    choices = []
    for sx,sy in sources:
        row = []
        for j,(x,y,cells) in enumerate(bodies):
            d = max(x-sx,0,sx-x-2) + max(y-sy,0,sy-y-2)
            assert d >= 1
            if d-1 <= cap:
                # Validate the shortcut against distances to all nine cells.
                assert d == min(abs(sx-u)+abs(sy-v) for u,v in cells)
                row.append((j,d-1))
        choices.append(row)
    return warehouses,sources,q,bodies,choices


def solve(left_gap, bottom_gap, cap, limit, workers):
    start = time.monotonic()
    warehouses,sources,q,bodies,choices = candidate_domain(left_gap,bottom_gap,cap)
    model = cp_model.CpModel()
    used_by_cell = defaultdict(list)
    all_vars, costs, arcs = [], [], []
    for i,row in enumerate(choices):
        src_vars = []
        for j,cost in row:
            x = model.new_bool_var(f'a_{i}_{j}')
            src_vars.append(x)
            all_vars.append(x)
            costs.append(cost)
            arcs.append((i,j,cost,x))
            for cell in bodies[j][2]:
                used_by_cell[cell].append(x)
        model.add_exactly_one(src_vars)
    for cell,variables in used_by_cell.items():
        if len(variables) > 1:
            model.add_at_most_one(variables)
    model.add(sum(c*x for c,x in zip(costs,all_vars)) <= cap)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = limit
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = 64
    status = solver.solve(model)
    result = dict(left_gap=left_gap,bottom_gap=bottom_gap,cap=cap,
                  status=solver.status_name(status),
                  legal_bodies=len(bodies),variables=len(all_vars),
                  cell_constraints=len(used_by_cell),
                  elapsed_seconds=time.monotonic()-start,
                  branches=solver.num_branches,conflicts=solver.num_conflicts,
                  response_stats=solver.response_stats())
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        result['assignment'] = [dict(source=list(sources[i]),body=list(bodies[j][:2]),extra=c)
                                for i,j,c,x in arcs if solver.value(x)]
        result['checked_assignment'] = check_assignment(left_gap,bottom_gap,result['assignment'])
    return result


def check_assignment(left_gap,bottom_gap,assignment):
    warehouses,sources,q = boundary(left_gap,bottom_gap)
    assert sorted(tuple(a['source']) for a in assignment) == sorted(sources)
    occupied = set()
    total = 0
    for a in assignment:
        x,y = a['body']
        cells = set(footprint(x,y))
        assert all(0 <= u < 70 and 0 <= v < 70 for u,v in cells)
        assert not cells.intersection(warehouses | set(sources) | occupied)
        occupied.update(cells)
        sx,sy = a['source']
        extra = min(abs(sx-u)+abs(sy-v) for u,v in cells)-1
        assert extra == a['extra'] and extra >= 0
        total += extra
    assert len(occupied) == 414
    holes = []
    for transpose in (False, True):
        selected = {(v,u) if transpose else (u,v) for u,v in occupied}
        for k in (6,7,9,17):
            x,y,w,h = (k,49,53,21) if transpose else (49,k,21,53)
            conflict = sorted((u,v) for u,v in selected if x<=u<x+w and y<=v<y+h)
            holes.append(dict(rectangle=[x,y,w,h],transpose=transpose,
                              conflicts=conflict,clear=not conflict))
    return dict(extra=total,body_cells=len(occupied),holes=holes,q=list(q))


def audit():
    # Backwards recipe calculation, all values rational (no copied total).
    battery, capsule = F(18,30),F(33,60)
    parts,dense_source,bottle,fine = 10*battery,15*battery,10*capsule,10*capsule
    steel = parts+2*bottle
    dense_blue = steel
    blue_powder,source_powder,flower_powder = 2*dense_blue,2*dense_source,2*fine
    leaf_powder = dense_blue+dense_source+fine
    flower_crushed,leaf_crushed = flower_powder/2,leaf_powder/3
    amounts = {'蓝铁矿':blue_powder,'源矿':source_powder,'蓝铁块':blue_powder,
               '蓝铁粉末':blue_powder,'源石粉末':source_powder,
               '砂叶粉末':leaf_powder,'砂叶':2*leaf_crushed,'砂叶种子':2*leaf_crushed,
               '荞花':2*flower_crushed,'荞花种子':2*flower_crushed,'荞花粉末':flower_powder,
               '致密蓝铁粉末':dense_blue,'钢块':steel,'致密源石粉末':dense_source,
               '细磨荞花粉末':fine,'钢制零件':parts,'钢质瓶':bottle,
               '高容谷地电池':battery,'精选荞愈胶囊':capsule}
    def ceil(q): return -(-q.numerator//q.denominator)
    batches = {'粉碎机':source_powder+blue_powder+flower_crushed+leaf_crushed,
               '精炼炉':blue_powder+steel,'研磨机':dense_blue+dense_source+fine,
               '塑形机':bottle,'配件机':parts,'种植机':2*(flower_crushed+leaf_crushed),
               '采种机':flower_crushed+leaf_crushed,'封装机':5*battery,'灌装机':5*capsule}
    sizes = {'粉碎机':9,'精炼炉':9,'研磨机':24,'塑形机':9,'配件机':9,
             '种植机':25,'采种机':25,'封装机':24,'灌装机':24}
    counts = {name:ceil(rate) for name,rate in batches.items()}
    area = sum(counts[name]*sizes[name] for name in counts)
    base = sum(amounts.values())
    lower = base+8
    assert base == F(6113,20) and area == 3291 and sum(counts.values()) == 217
    layouts = [(l,b) for l in range(0,70,3) for b in range(0,70,3) if l==0 or b==0]
    assert len(layouts) == 47
    geometry = []
    for l,b in layouts:
        warehouse,sources,q = boundary(l,b)
        neighbors = {(q[0]+u,q[1]+v) for u,v in [(1,0),(-1,0),(0,1),(0,-1)]}
        free_neighbors = {p for p in neighbors if 0<=p[0]<70 and 0<=p[1]<70 and p not in warehouse}
        assert len(free_neighbors) <= 1
        # No 2x2 non-transport body can occupy q, hence no larger body either.
        for x in range(max(0,q[0]-1),min(68,q[0])+1):
            for y in range(max(0,q[1]-1),min(68,q[1])+1):
                assert warehouse.intersection({(x+u,y+v) for u in (0,1) for v in (0,1)})
        geometry.append(dict(gaps=[l,b],q=list(q),possible_neighbors=len(free_neighbors)))
    branches = []
    for transpose in (False,True):
        for k in (6,7,9,17):
            rect = [k,49,53,21] if transpose else [49,k,21,53]
            for p in (10,11,12):
                budget = 70*70-21*53-area-9*9-46*3-4*p
                active = budget-1
                cap = 2*active-4
                branches.append(dict(rectangle=rect,P=p,T_plus_F=budget,
                                     active_units_max=active,capacity=cap,
                                     lower=str(lower),gap=str(F(cap)-lower),
                                     bridges_min=ceil(lower)-active,excluded=lower>cap))
    areas = sorted({w*h for w in range(6,69) for h in range(6,69) if w*h<=1113}, reverse=True)
    assert areas[:2] == [1113,1110]
    snapshot = {}
    for name in OFFICIAL:
        raw = (ROOT/name).read_bytes()
        snapshot[name] = dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),text=raw.decode())
    save('official_snapshot.json',snapshot)
    result = dict(python=platform.python_version(),ortools=ortools.__version__,
                  materials={k:str(v) for k,v in amounts.items()},total=str(base),
                  raw_ore=str(amounts['蓝铁矿']+amounts['源矿']),
                  other_materials=str(base-amounts['蓝铁矿']-amounts['源矿']),
                  counts=counts,total_count=sum(counts.values()),machine_area=area,
                  V_lower=str(lower),slots_min=ceil(lower),weak_T=ceil((lower+4)/2),
                  edge_cases=geometry,branches=branches,next_areas=areas[:6])
    save('arithmetic.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('edge_cases','branches')},ensure_ascii=False),flush=True)


def witness_check():
    # Read coordinates only, not the derivation's programs or solver results.
    original = HERE.parent/'A-运输格总量'/'relaxation_witness.json'
    raw = original.read_bytes()
    data = json.loads(raw)
    converted = [dict(source=a['source'],body=a['machine'],extra=a['distance']-1)
                 for a in data['assignment']]
    check = check_assignment(data['gap_left'],data['gap_bottom'],converted)
    assert check['extra'] == 8 and all(h['clear'] for h in check['holes'])
    own = json.loads((HERE/'witness_3_0.json').read_text())[0]
    own_check = check_assignment(3,0,own['assignment'])
    assert own_check['extra'] == 8 and all(h['clear'] for h in own_check['holes'])
    result = dict(original_coordinate_file_sha256=hashlib.sha256(raw).hexdigest(),
                  original=check,independently_found=own_check)
    save('witness_checked.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode',choices=['audit','bound','witness','witness-check','hash-check'])
    ap.add_argument('--left',type=int)
    ap.add_argument('--bottom',type=int)
    ap.add_argument('--limit',type=float,default=120)
    ap.add_argument('--workers',type=int,default=4)
    args = ap.parse_args()
    if args.mode == 'audit':
        audit()
    elif args.mode == 'witness-check':
        witness_check()
    elif args.mode == 'hash-check':
        snap = json.loads((HERE/'official_snapshot.json').read_text())
        checked = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==snap[name]['sha256'] for name in OFFICIAL}
        save('input_unchanged.json',checked)
        print(checked)
        assert all(checked.values())
    else:
        cap = 7 if args.mode == 'bound' else 8
        gaps = [(args.left,args.bottom)] if args.left is not None else [(l,b) for l in range(0,70,3) for b in range(0,70,3) if l==0 or b==0]
        output = []
        for l,b in gaps:
            result = solve(l,b,cap,args.limit,args.workers)
            output.append(result)
            label = f'{args.mode}_{l}_{b}.json' if args.left is not None else f'{args.mode}_all.json'
            save(label,output)
            print(json.dumps({k:v for k,v in result.items() if k not in ('assignment','response_stats','checked_assignment')},ensure_ascii=False),flush=True)
        if args.mode == 'bound':
            assert all(r['status']=='INFEASIBLE' for r in output), 'Not all instances proved infeasible'


if __name__ == '__main__':
    main()
