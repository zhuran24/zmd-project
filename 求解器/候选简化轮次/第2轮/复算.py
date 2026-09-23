#!/usr/bin/env python3
"""本轮局部算术与接口模型复算；不是全厂模拟器。只在自身目录写结果。"""
from pathlib import Path
from itertools import permutations
from math import ceil, floor
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXPECTED = {
    "《明日方舟：终末地》游戏规则.txt": "52df4c12ce90975b861a6a663bd37873e03c9549658d200dc7e95fabc4bc29f3",
    "求解任务.txt": "1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac",
    "求解约束.txt": "0c05976f6063f3332db6ee19d7746052ef35148d7c2a12dfa396c7bb8753f30f",
    "求解器/候选简化轮次/第1轮/推导.md": "c08c88dccab670fb3859c1b33dedfb54e8131849615fb9b2812291fe744bfc7e",
}
hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in EXPECTED}
assert hashes == EXPECTED
assert sum(s.lstrip().startswith("据：") for s in (ROOT / "求解约束.txt").read_text().splitlines()) == 72


def prefix_interval(initial, a, b, ia, ib):
    xa, xb = initial
    lo = max(0, ceil((xa + ia - 50) / a), ceil((xb + ib - 50) / b))
    hi = min(floor((xa + ia) / a), floor((xb + ib) / b))
    return [lo, hi]


def eager_fifo(initial, a, b, word, repeats=1):
    """只核查即时开工的宽松 FIFO 模型。失败即给出库存阻塞点。"""
    xa, xb = initial
    n = 0
    for pos, item in enumerate(word * repeats, 1):
        k = min(xa // a, xb // b)
        xa -= a * k
        xb -= b * k
        n += k
        if (xa if item == "A" else xb) == 50:
            return {"blocked_at": pos, "head": item, "stock": [xa, xb], "batches": n}
        if item == "A":
            xa += 1
        else:
            xb += 1
    k = min(xa // a, xb // b)
    return {"blocked_at": None, "stock": [xa-a*k, xb-b*k], "batches": n+k}


mix = {
    "round1_full": eager_fifo((50, 50), 2, 1, "A"*102 + "B"*51),
    "round1_low": eager_fifo((0, 50), 2, 1, "A"*102 + "B"*51, 10),
    "batch_residue": {
        "D_plus_Z_range": [595, 745],
        "legal_real_range": [-500, 750],
        "after_second_A_integer_N_interval": prefix_interval((49, 14), 10, 15, 2, 0),
        "replay": eager_fifo((49, 14), 10, 15, "A"*10 + "B"*15),
    },
    "arbitrary_stock_impossible_word": {
        "A_run": 152, "B_run": 76, "D_width": 152, "capacity_width": 150,
        "max_A_accepted_over_all_initial_stocks": max(50-xa + 2*(xb//1) for xa in range(51) for xb in range(51)),
    },
}
assert mix["round1_full"]["blocked_at"] == 101
assert mix["round1_low"] == {"blocked_at": None, "stock": [0,50], "batches":510}
assert mix["batch_residue"]["after_second_A_integer_N_interval"] == [1, 0]
assert mix["batch_residue"]["replay"]["blocked_at"] == 2
assert mix["arbitrary_stock_impossible_word"]["max_A_accepted_over_all_initial_stocks"] == 150


def fill(slots, kind):
    for i, item in enumerate(slots):
        if item is None:
            slots[i] = [kind, 1]
            return True
        if item[0] == kind and item[1] < 50:
            item[1] += 1
            return True
    return False


def take_x(slots):
    for i, item in enumerate(slots):
        if item:
            if item[0] != "X":
                return False
            item[1] -= 1
            if item[1] == 0:
                slots[i] = None
            return True
    return False


def transmit(slots):
    n = 0
    for i, item in enumerate(slots):
        if item and item[0] in ("P", "Q"):
            n += item[1]
            slots[i] = None
    return n


def box_case(order, pp, tp):
    slots = [["X",25]] + [None]*5
    received = sent = 0
    xmin, xmax, pmax = 25, 25, 0
    seen = {}
    for t in range(1000):
        key = (t % 5, tuple(None if x is None else tuple(x) for x in slots))
        if key in seen:
            oldt, olds = seen[key]
            assert (sent-olds)*5 == t-oldt
            return {"period": t-oldt, "delivered": sent-olds, "X_min":xmin, "X_max":xmax, "P_max":pmax}
        seen[key] = (t, sent)
        for e in order:
            if e == "in":
                assert fill(slots, "X")
            elif e == "out":
                assert take_x(slots)
            elif e == "p" and t % 5 == pp:
                assert fill(slots, "P")
                received += 1
            elif e == "tx" and t % 5 == tp:
                sent += transmit(slots)
            x = sum(item[1] for item in slots if item and item[0] == "X")
            p = sum(item[1] for item in slots if item and item[0] == "P")
            xmin, xmax, pmax = min(xmin, x), max(xmax, x), max(pmax,p)
            assert 24 <= x <= 26
            assert slots[0] and slots[0][0] == "X"
            assert not any(item and item[0] == "X" for item in slots[1:])
            assert received == sent+p
    raise AssertionError("no period")


cases = [box_case(order, pp, tp) for order in permutations(("in","out","p","tx")) for pp in range(5) for tp in range(5)]
assert len(cases) == 600

# 一次性先供后取：清空箱子也会在服务启动前再次被 X 占完。
burst = [None]*6
for _ in range(300):
    assert fill(burst, "X")
assert not fill(burst, "P")
for _ in range(1000):
    assert take_x(burst)
    assert fill(burst, "X")
    assert not fill(burst, "P")
assert burst == [["X", 50] for _ in range(6)]

# 小总量仍可多格碎片：物品格不可按总件数向上取整来数。
fragment = [None]*6
assert fill(fragment, "P")
assert fill(fragment, "X")
transmit(fragment)
assert fill(fragment, "X")
assert fragment == [["X",1],["X",1],None,None,None,None]

plant = {
    "bad_open_output_priority": {"outside_damping":1, "return_damping":3, "new_return_after_initial_queue_budget":0},
    "balance_target_example": {"A":10,"Z":20,"F":10,"seed_balance":2*10-20,"plant_balance":20-10-10},
    "prefix_example": {"seed_delta_min":-7,"seed_delta_max":4,"plant_delta_min":-5,"plant_delta_max":3,
                       "seed_initial_lower":7,"plant_initial_lower":5,"seed_capacity_required":11,"plant_capacity_required":8},
}

# 植物局部反例的实物摆放：端口由相邻格推导，不把画线当自动接通证明。
units = []
def block(name, x, y, w, h, intake, output):
    cells = {(xx,yy) for xx in range(x,x+w) for yy in range(y,y+h)}
    side = {"W": [(x,yy) for yy in range(y,y+h)], "E": [(x+w-1,yy) for yy in range(y,y+h)]}
    ins = [] if intake is None else [(p,intake) for p in side[intake]]
    outs = [] if output is None else [(p,output) for p in side[output]]
    units.append(dict(name=name,cells=cells,ins=ins,outs=outs))

block("种植",10,10,5,5,"W","E")
block("采种",22,18,5,5,"E","W")
block("粉碎",16,9,3,3,"W","E")
block("粉末传输箱",20,9,3,3,"W","E")
block("协议核心",40,40,9,9,None,None)
units[-1]["ins"] = [((x,y),d) for y,d in [(40,"S"),(48,"N")] for x in range(41,48)]
units[-1]["outs"] = [((x,y),d) for x,d in [(40,"W"),(48,"E")] for y in (41,44,47)]
for name,x,y in [("供电1",12,4),("供电2",24,8),("供电3",24,25)]:
    block(name,x,y,2,2,None,None)
vectors={"W":(-1,0),"E":(1,0),"N":(0,1),"S":(0,-1)}
opposite={"W":"E","E":"W","N":"S","S":"N"}
def direction(p,q):
    d=(q[0]-p[0],q[1]-p[1])
    return next(k for k,v in vectors.items() if v==d)
def route(name, path, before, after):
    for i,p in enumerate(path):
        prev = before if i==0 else path[i-1]
        nxt = after if i==len(path)-1 else path[i+1]
        kind = "准入口" if p==(17,16) else "带"
        units.append(dict(name=f"{name}{i}:{kind}",cells={p},ins=[(p,direction(p,prev))],outs=[(p,direction(p,nxt))]))

return_path=[(15,14),(16,14)]+[(17,y) for y in range(14,24)]+[(x,23) for x in range(18,28)]+[(27,22)]
seed_path=[(21,y) for y in range(18,14,-1)]+[(x,15) for x in range(22,29)]+[(28,y) for y in range(14,5,-1)]+[(x,6) for x in range(27,8,-1)]+[(9,y) for y in range(7,13)]
assert len(return_path)==23 and len(seed_path)==45
route("植株回种",return_path,(14,14),(26,22))
route("种子返种植",seed_path,(22,18),(10,12))
for y in (9,10,11):
    route(f"粉末{y}",[(19,y)],(18,y),(20,y))
units.append(dict(name="外送汇流器",cells={(15,10)},ins=[((15,10),d) for d in ("W","N","S")],outs=[((15,10),"E")]))
occupied={}
for u in units:
    for p in u["cells"]:
        assert 0<=p[0]<70 and 0<=p[1]<70
        assert p not in occupied,(u["name"],occupied.get(p),p)
        occupied[p]=u["name"]
inputs={(p,d):u["name"] for u in units for p,d in u["ins"]}
channels=[]
for u in units:
    for p,d in u["outs"]:
        v=vectors[d]
        q=(p[0]+v[0],p[1]+v[1])
        if (q,opposite[d]) in inputs:
            channels.append((u["name"],inputs[q,opposite[d]]))
assert len(channels)==24+46+3*2+2
for machine in ("种植","采种","粉碎","粉末传输箱"):
    mc=next(u for u in units if u["name"]==machine)["cells"]
    assert any(any(abs(x+0.5-(px+1))<6 and abs(y+0.5-(py+1))<6 for x,y in mc) for px,py in [(12,4),(24,8),(24,25)])
plant["geometry"]={"plant_return_transport_cells":23,"seed_return_transport_cells":45,"unit_count":len(units),"occupied_cells":len(occupied),"automatic_channels":len(channels),"channels":channels}
plant["extinction_budget"]={"initial_seed_plus_plant_upper":300,"extra_plants_to_return_upper":52,"seeding_completions_upper":352,"planting_completions_upper":1004,"crushing_completions_upper":1304,"powder_to_warehouse_upper":3912,"warehouse_capacity":80000}
assert 300+2*352==1004 and 300+1004==1304 and 3*1304==3912<80000

result = {
    "scope": "算术、即时 FIFO 宽松模型、箱体离散接口模型、植物局部几何；不生成混料词，不模拟全厂或植物逐事件运行。",
    "source_sha256": hashes,
    "mix": mix,
    "plant_arithmetic": plant,
    "box": {"enumerated_cases":len(cases),"periods":sorted(set(c["period"] for c in cases)),
            "X_min":min(c["X_min"] for c in cases),"X_max":max(c["X_max"] for c in cases),
            "P_max":max(c["P_max"] for c in cases),"safe_initial_interval_when_delta_is_minus1_to_1":[2,49],
            "restart_prefix_limits":{"q25_positive_upper":25,"q25_negative_magnitude":24,"q25_arrivals26_stock":51,"q25_departures25_stock":0},
            "burst_counterexample_final_slots":burst,"fragmentation_example":fragment,
            "three_input_ports_five_tick_inclusive_upper":3*6},
}
(HERE / "复算结果.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"passed":True,"box_cases":len(cases),"result":str(HERE / "复算结果.json")},ensure_ascii=False))
