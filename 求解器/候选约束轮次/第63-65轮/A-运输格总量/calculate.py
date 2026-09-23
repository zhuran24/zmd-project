#!/usr/bin/env python3
"""Exact rational accounting and checks of the retained distance witness."""
from pathlib import Path
from fractions import Fraction as Q
from math import ceil
import hashlib,json,platform
import importlib.metadata

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

def main():
    snapshot=json.loads((HERE/'input_snapshot.json').read_text())
    integrity=[]
    for item in snapshot['files']:
        digest=hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()
        integrity.append(dict(path=item['path'],sha256=digest,unchanged=digest==item['sha256']))
    assert all(r['unchanged'] for r in integrity)
    rules=(ROOT/'《明日方舟：终末地》游戏规则.txt').read_text()
    constraints=(ROOT/'求解约束.txt').read_text()
    assert '运输单位：一个物品格（桥接器例外），上限1' in rules
    assert '不会移回刚离开的单位' in rules
    assert '两对平行边互不相干，各有一个物品格' in rules
    names=['粉碎机','精炼炉','研磨机','塑形机','配件机','种植机','采种机','封装机','灌装机']
    counts=[68,51,32,6,6,32,16,3,3]
    areas=[9,9,24,9,9,25,25,24,24]
    machine_rows=[]
    for name,n,area in zip(names,counts,areas):
        assert f'{name} ≥{n}' in constraints
        machine_rows.append(dict(name=name,count=n,area_each=area,total_area=n*area))
    machine_area=sum(a['total_area'] for a in machine_rows)
    assert machine_area==3291 and sum(counts)==217
    battery=Q('0.6');capsule=Q('0.55')
    parts=10*battery;dense_rock=15*battery;bottle=10*capsule;fine_flower=10*capsule
    steel=parts+2*bottle;dense_iron=steel;iron_powder=2*dense_iron
    rock_powder=2*dense_rock;flower_powder=2*fine_flower
    leaf_powder=dense_iron+dense_rock+fine_flower
    flower_crushing=flower_powder/2;leaf_crushing=leaf_powder/3
    flower=flower_seed=2*flower_crushing;leaf=leaf_seed=2*leaf_crushing
    flow=dict(蓝铁矿=iron_powder,源矿=rock_powder,蓝铁块=iron_powder,蓝铁粉末=iron_powder,
              源石粉末=rock_powder,砂叶粉末=leaf_powder,砂叶=leaf,砂叶种子=leaf_seed,
              荞花=flower,荞花种子=flower_seed,荞花粉末=flower_powder,
              致密蓝铁粉末=dense_iron,钢块=steel,致密源石粉末=dense_rock,
              细磨荞花粉末=fine_flower,钢制零件=parts,钢质瓶=bottle,
              高容谷地电池=battery,精选荞愈胶囊=capsule)
    baseline=sum(flow.values());extra=8;lower=baseline+extra
    assert baseline==Q('305.65') and lower==Q('313.65')
    cp=json.loads((HERE/'full_boundary.json').read_text())
    assert len(cp)==47 and all(r['status']=='INFEASIBLE' for r in cp)
    other=json.loads((HERE/'verify_full_boundary.json').read_text())
    assert other['all_infeasible'] and len(other['cases'])==47
    witness=json.loads((HERE/'relaxation_witness.json').read_text())
    assert witness['assignment_excess']==8
    positions=[]
    for transpose in (False,True):
        for y in (6,7,9,17):
            x0,y0,w,h=(y,49,53,21) if transpose else (49,y,21,53)
            hole={(x,y) for x in range(x0,x0+w) for y in range(y0,y0+h)}
            machine_cells=set()
            for a in witness['assignment']:
                x,y=a['machine']
                cells={(xx,yy) for xx in range(x,x+3) for yy in range(y,y+3)}
                if transpose:
                    cells={(yy,xx) for xx,yy in cells}
                machine_cells|=cells
            assert not machine_cells&hole
            positions.append(dict(x=x0,y=y0,width=w,height=h,
                                  relaxed_cost_8_witness_avoids_hole=True))
    rows=[]
    base=machine_area+81+46*3
    for pos in positions:
        for p in (10,11,12):
            remainder=4900-1113-base-4*p
            active=remainder-1
            nominal=2*remainder
            cap=2*active-4
            rows.append(dict(**pos,P=p,nontransport_area=base+4*p,
                             T_plus_F=remainder,max_active_transport=active,
                             nominal_capacity=nominal,capacity_after_boundary_and_turns=cap,
                             lower=str(lower),gap_nominal=str(Q(nominal)-lower),
                             gap_strengthened=str(Q(cap)-lower),
                             min_bridges=ceil(lower)-active,
                             excluded_by_total_visits=False))
    result=dict(machine_counts=machine_rows,machine_area=machine_area,base_nonpole_area=base,
                material_flow={k:str(v) for k,v in flow.items()},base_visits=str(baseline),
                extra_visits=extra,visits_lower=str(lower),transport_slots_lower=ceil(lower),
                raw_ore_visits_lower=52+extra,non_ore_visits=str(baseline-52),
                nonbridge_lower=4,transport_count_from_visits_alone=ceil((ceil(lower)+4)/2),
                cp_cases=len(cp),highs_cases=len(other['cases']),
                relaxation_minimum_excess=extra,position_branches=rows,
                next_integer_area=max(w*h for w in range(6,67) for h in range(6,67) if w*h<1113),
                input_integrity=integrity,versions=dict(python=platform.python_version(),
                ortools=importlib.metadata.version('ortools'),scipy=importlib.metadata.version('scipy')))
    (HERE/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('position_branches','material_flow','input_integrity','machine_counts')},ensure_ascii=False,indent=2))
    print('All 24 position/P rows saved; input hashes unchanged.')

if __name__=='__main__':
    main()
