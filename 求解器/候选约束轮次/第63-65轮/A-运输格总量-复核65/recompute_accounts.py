#!/usr/bin/env python3
"""Exact arithmetic, independent coordinate checks, and input evidence for review 65.

No derivation scripts are read/imported. The derivation witness is data to be checked.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from fractions import Fraction as F
from math import ceil
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def save(name, data):
    (OUT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def exact(x):
    x = F(x)
    return {"fraction": str(x), "decimal": float(x)}


def independently_check_witness(gleft, gbottom, assignments):
    # Construct outlets by walking 0..69, skipping each missing cell.
    outlets = []
    sources = []
    for side, gap in (("left",gleft),("bottom",gbottom)):
        p = 0
        while p < 70:
            if p == gap:
                p += 1
                continue
            assert p+2 < 70 and not p <= gap <= p+2
            coords = [(0,t) if side=="left" else (t,0) for t in range(p,p+3)]
            outlets.extend(coords)
            sources.append((1,p+1) if side=="left" else (p+1,1))
            p += 3
    assert len(outlets) == len(set(outlets)) == 138
    assert len(sources) == len(set(sources)) == 46
    assert set(assignments) == set(sources)
    bodies = set()
    cost = 0
    for source in sources:
        x,y = assignments[source]
        body = {(x+i,y+j) for i in range(3) for j in range(3)}
        assert min(x,y)>=1 and max(x,y)<=67
        assert not body & bodies and not body & set(sources) and not body & set(outlets)
        # Independently enumerate the nine cells, no rectangle distance formula.
        d = min(abs(source[0]-a)+abs(source[1]-b) for a,b in body)
        assert d>=1
        cost += d-1
        bodies.update(body)
    assert len(bodies)==414
    tests = []
    for transpose in (False,True):
        used = {(y,x) if transpose else (x,y) for x,y in bodies}
        for b in (6,7,9,17):
            a,c,w,h = (b,49,53,21) if transpose else (49,b,21,53)
            overlap = sorted((x,y) for x,y in used if a<=x<a+w and c<=y<c+h)
            assert not overlap
            tests.append({"rectangle":[a,c,w,h], "body_overlap":len(overlap)})
    return {"cost":cost,"sources":len(sources),"bodies":46,"body_cells":414,"rectangle_checks":tests}


def main():
    battery, capsule = F(18,30), F("16.5")/30
    parts, bottles, dense_source, fine_flower = 10*battery,10*capsule,15*battery,10*capsule
    steel = parts + 2*bottles
    dense_iron = steel
    iron_powder, source_powder, flower_powder = 2*dense_iron,2*dense_source,2*fine_flower
    sand_powder = dense_iron+dense_source+fine_flower
    crush_sand, crush_flower = sand_powder/3, flower_powder/2
    # Periodic seed and plant balance: seed-making batches = crushing batches.
    sand, flower = 2*crush_sand,2*crush_flower
    flows = {"蓝铁矿":iron_powder, "源矿":source_powder, "蓝铁块":iron_powder,
             "蓝铁粉末":iron_powder,"源石粉末":source_powder,"砂叶粉末":sand_powder,
             "砂叶":sand,"砂叶种子":sand,"荞花":flower,"荞花种子":flower,
             "荞花粉末":flower_powder,"致密蓝铁粉末":dense_iron,"钢块":steel,
             "致密源石粉末":dense_source,"细磨荞花粉末":fine_flower,
             "钢制零件":parts,"钢质瓶":bottles,"高容谷地电池":battery,"精选荞愈胶囊":capsule}
    total = sum(flows.values())
    assert total == F(6113,20)
    raw = flows["蓝铁矿"]+flows["源矿"]
    assert raw == 52
    batch_rates = {"粉碎机":source_powder+iron_powder+crush_flower+crush_sand,
                   "精炼炉":iron_powder+dense_iron,"研磨机":dense_iron+dense_source+fine_flower,
                   "塑形机":bottles,"配件机":parts,"种植机":sand+flower,
                   "采种机":crush_sand+crush_flower,"封装机":battery,"灌装机":capsule}
    sizes = {"粉碎机":9,"精炼炉":9,"研磨机":24,"塑形机":9,"配件机":9,
             "种植机":25,"采种机":25,"封装机":24,"灌装机":24}
    machines = {name:ceil(rate*(5 if name in ("封装机","灌装机") else 1))
                for name,rate in batch_rates.items()}
    machine_area = sum(machines[name]*sizes[name] for name in machines)
    assert sum(machines.values())==217 and machine_area==3291
    new = total+8
    assert new == F(6273,20) and ceil(new)==314 and ceil(total)==306
    cases=[]
    for transpose in (False,True):
        for y in (6,7,9,17):
            rect = [y,49,53,21] if transpose else [49,y,21,53]
            for p in (10,11,12):
                budget=70*70-rect[2]*rect[3]-machine_area-81-46*3-4*p
                active=budget-1
                capacity=2*active-4
                cases.append({"rectangle":rect,"P":p,"T_plus_F":budget,
                              "capacity_before_q_turns":2*budget,"positive_flow_units_at_most":active,
                              "capacity":capacity,"V_lower_bound":exact(new),
                              "gap":exact(capacity-new),"bridge_count_at_least":ceil(new)-active,
                              "excluded_by_this_account":new>capacity})
    assert len(cases)==24 and not any(c["excluded_by_this_account"] for c in cases)
    shapes={a: [(w,h) for w in range(6,69) for h in range(w,69) if w*h==a]
            for a in range(1110,1114)}
    assert shapes=={1110:[(30,37)],1111:[],1112:[],1113:[(21,53)]}

    # Independently check the one unused boundary cell in every joint packing.
    gap_checks=[]
    for gl in range(0,70,3):
        for gb in range(0,70,3):
            if gl and gb:
                continue
            left={(0,y) for y in range(70) if y!=gl}
            bottom={(x,0) for x in range(70) if x!=gb}
            assert not left&bottom
            boundary={(0,y) for y in range(70)}|{(x,0) for x in range(70)}
            free=boundary-left-bottom
            assert len(free)==1
            q=next(iter(free))
            neighbors={(q[0]+dx,q[1]+dy) for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))}
            possible={z for z in neighbors if min(z)>=0 and max(z)<70 and z not in left|bottom}
            assert len(possible)<=1
            gap_checks.append({"gap_left":gl,"gap_bottom":gb,"q":q,"possible_neighbors":sorted(possible)})
    assert len(gap_checks)==47
    author_path=ROOT/"求解器/候选约束轮次/第63-65轮/A-运输格总量/relaxation_witness.json"
    author=json.loads(author_path.read_text())
    author_map={tuple(a["source"]):tuple(a["machine"]) for a in author["assignment"]}
    assert len(author_map)==len(author["assignment"])==46 and not author["dummy_sources"]
    author_check=independently_check_witness(author["gap_left"],author["gap_bottom"],author_map)
    own=json.loads((OUT/"independent_witness.json").read_text())
    own_map={tuple(a["source"]):tuple(a["body"]) for a in own["witness"]["assignments"]}
    own_check=independently_check_witness(own["gap_left"],own["gap_bottom"],own_map)
    assert author_check["cost"]==own_check["cost"]==8
    geometry=json.loads((OUT/"geometry_all.json").read_text())
    assert len(geometry["cases"])==47 and all(r["status"]=="INFEASIBLE" for r in geometry["cases"])
    materials=["《明日方舟：终末地》游戏规则.txt","求解任务.txt","求解约束.txt",
               "候选约束.txt","求解器/候选约束轮次/第63-65轮/A-运输格总量-推导.md",
               "求解器/老项目/上界可用性.md",str(author_path.relative_to(ROOT))]
    snapshots={}
    for name in materials:
        data=(ROOT/name).read_bytes()
        snapshots[name]={"sha256":hashlib.sha256(data).hexdigest(),"text":data.decode()}
    for name,h in geometry["inputs"].items():
        assert snapshots[name]["sha256"]==h
    formal=snapshots["求解约束.txt"]["text"]
    flowline=next(line for line in formal.splitlines() if line.startswith("物料流量："))
    for name,rate in flows.items():
        match=re.search(re.escape(name)+r" ([0-9.]+)",flowline)
        assert match and F(match[1])==rate
    formal_count=sum(1 for line in formal.splitlines() if line and not line[0].isspace()
                     and "：" in line and not line.endswith("："))
    assert formal_count==72
    save("inputs_snapshot.json",{"captured_at":datetime.now(timezone.utc).isoformat(),"materials":snapshots})
    result={"flows":{k:exact(v) for k,v in flows.items()},"total":exact(total),"raw_ores":exact(raw),
            "non_raw":exact(total-raw),"new_lower_bound":exact(new),"old_slots":ceil(total),"new_slots":ceil(new),
            "machine_batch_rates":{k:exact(v) for k,v in batch_rates.items()},"machine_counts":machines,
            "machine_area":machine_area,"T_from_slots_and_four_turns":ceil((new+4)/2),
            "area_shapes":shapes,"cases":cases,"boundary_gap_checks":gap_checks,
            "author_witness_check":author_check,"independent_witness_check":own_check,
            "formal_constraint_count":formal_count,"geometry_infeasible_cases":47,
            "geometry_solver_seconds":sum(r["seconds"] for r in geometry["cases"])}
    save("accounts.json",result)
    print(json.dumps({"flow_total":str(total),"new_lower_bound":str(new),"slots":ceil(new),
                      "machines":machines,"machine_area":machine_area,
                      "geometry_infeasible_cases":47,"author_and_own_witness_cost":8,
                      "position_P_cases":len(cases),"excluded":sum(c["excluded_by_this_account"] for c in cases),
                      "formal_constraints":formal_count},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
