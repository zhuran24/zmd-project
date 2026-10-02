#!/usr/bin/env python3
"""从报告中的坐标、规则23--33、65、68--74独立建立密集结点见证。

不导入其他席脚本或内核。物品记录为(进入步数,刚离开的物理单位)。
包括有限仓库、实际端口生成的全部通道、建造形成时刻、运输格滞留、
准入口窗口、分流轮询及临时规则的实际可送者触发。
"""
from pathlib import Path
from collections import Counter
from fractions import Fraction
import json

OUT = Path(__file__).resolve().parent
D = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
REV = {"E": "W", "W": "E", "N": "S", "S": "N"}


def direction(a, b):
    delta = (b[0]-a[0], b[1]-a[1])
    return next(d for d, dv in D.items() if dv == delta)


def geometry(first):
    nodes = {}
    def node(name, cells, ins, outs):
        nodes[name] = {"cells": set(cells), "ins": set(ins), "outs": set(outs)}
    core = {(x, y) for x in range(13, 22) for y in range(9, 18)}
    node("C", core, [((13, y), "W") for y in range(10,17)] + [((21,y),"E") for y in range(10,17)],
         [((x,9),"N") for x in (14,17,20)] + [((x,17),"S") for x in (14,17,20)])
    node("WA", [(0,y) for y in range(9,12)], [], [((0,10),"E")])
    node("WB", [(0,y) for y in range(1,4)], [], [((0,2),"E")])
    positions = {"P":(9,10),"Q":(11,8),"S":(10,10),"U":(11,9),"M":(11,10),"N":(10,11)}
    for name in ("P", "Q", "U"):
        inp = "W" if name == "P" else "N"
        node(name, [positions[name]], [(positions[name],inp)], [(positions[name],REV[inp])])
    node("S", [positions["S"]], [(positions["S"],"W")], [(positions["S"],d) for d in ("N","S","E")])
    for name in ("M", "N"):
        node(name, [positions[name]], [(positions[name],d) for d in ("N","S","W")], [(positions[name],"E")])
    coords = {
        "LA": [(x,10) for x in range(1,5)] + [(4,y) for y in range(11,15)] + [(x,14) for x in range(5,9)] + [(8,y) for y in range(13,9,-1)],
        "LB": [(x,2) for x in range(1,12)] + [(11,y) for y in range(3,8)],
        "RA": [(12,10)], "RB": [(11,11),(12,11)],
    }
    endpoints = {"LA":((0,10),positions["P"]),"LB":((0,2),positions["Q"]),"RA":(positions["M"],(13,10)),"RB":(positions["N"],(13,11))}
    paths = {}
    for label, cells in coords.items():
        paths[label] = []
        for i, c in enumerate(cells):
            name = f"{label}{i}"
            paths[label].append(name)
            prev = cells[i-1] if i else endpoints[label][0]
            nxt = cells[i+1] if i+1<len(cells) else endpoints[label][1]
            node(name, [c], [(c,direction(c,prev))], [(c,direction(c,nxt))])
    occupied = {}
    for name, data in nodes.items():
        for c in data["cells"]:
            assert 0 <= c[0] < 70 and 0 <= c[1] < 70
            assert c not in occupied
            occupied[c] = name
    edges = []
    for name, data in nodes.items():
        for (x,y), d in data["outs"]:
            dx,dy = D[d]
            c = (x+dx,y+dy)
            other = occupied.get(c)
            if other and (c,REV[d]) in nodes[other]["ins"]:
                edges.append((name,other))
    expected = [("WA",paths["LA"][0]),("WB",paths["LB"][0]),("P","S"),("Q","U"),("S","M"),("S","N"),("U","M"),("M",paths["RA"][0]),("N",paths["RB"][0])]
    for label, path in paths.items():
        expected += list(zip(path,path[1:]))
        expected.append((path[-1], "P" if label=="LA" else "Q" if label=="LB" else "C"))
    assert set(edges) == set(expected) and len(edges) == 44
    order = ["M","U","S","N","P","Q"] if first == "U" else ["M","S","N","U","P","Q"]
    build = {"C":-3,"WA":-2,"WB":-1, **{name:i+1 for i,name in enumerate(order)}}
    for label, start in (("RA",100),("RB",101),("LA",110),("LB",130)):
        build.update({name:start+i for i,name in enumerate(paths[label])})
    times = {(a,b):max(build[a],build[b]) for a,b in edges}
    assert min(build[n] for p in paths.values() for n in p) > max(build[n] for n in positions)
    components = {**paths, **{k:[k] for k in positions}}
    component_of = {n:c for c,p in components.items() for n in p}
    successors = {c:[] for c in components}
    for a,b in edges:
        if a in component_of and component_of.get(b) != component_of[a]:
            successors[component_of[a]].append((a,b))
    def layers(c):
        downstream = [component_of[b] for _,b in successors[c] if b in component_of and successors[component_of[b]]]
        possible = {1} if not downstream else {1+x for d in downstream for x in layers(d)}
        assert len(possible)==1
        return possible
    levels = {c:next(iter(layers(c))) for c in components}
    base = sorted(components,key=lambda c:(levels[c],min(times[e] for e in successors[c])))
    splitter_order = sorted([b for _,b in successors["S"]],key=lambda b:times[("S",b)])
    assert splitter_order == ["M","N"]
    return nodes, paths, components, component_of, successors, base, splitter_order, levels, edges, times, len(occupied)


def run(first):
    nodes, paths, comps, comp_of, successors, base, sporder, levels, edges, times, used = geometry(first)
    goods = {n:None for n in comp_of}
    warehouse = 80000
    minimum = warehouse
    gate_due = {"P":0,"Q":0}
    pointer = 1 # first splitter attempt starts at the second connected channel
    counts = Counter()
    seen = {}
    traces = []
    upstream = {}
    for c, outgoing in successors.items():
        for a,b in outgoing:
            if c != "S":
                upstream.setdefault(b,[]).append(c)
    def eligible(a,b,s):
        token = goods[a]
        return token is not None and s-token[0]>=8 and token[1]!=b
    def send(a,b,s):
        nonlocal warehouse
        if not eligible(a,b,s):
            return False
        if b == "C":
            assert warehouse < 80000
            warehouse += 1
        else:
            if goods[b] is not None or (b in gate_due and s < gate_due[b]):
                return False
            goods[b] = (s,a)
            if b in gate_due:
                gate_due[b] = s+40
        goods[a] = None
        counts[(a,b)] += 1
        if a in ("S","U"):
            traces.append([s,a,b])
        return True
    def key(s):
        # One-outlet histories and core receipt history are safely omitted:
        # the former offer no choice; the core accepts every returned item.
        return (warehouse, pointer, tuple(max(0,gate_due[g]-s) for g in ("P","Q")),
                tuple(None if goods[n] is None else (min(8,s-goods[n][0]),goods[n][1]) for n in sorted(goods)))
    for s in range(2000):
        done = set()
        def plain(c):
            nonlocal pointer
            if c in done:
                return
            done.add(c)
            if c == "S":
                for j in range(len(sporder)):
                    index = (pointer+j)%len(sporder)
                    if send("S",sporder[index],s):
                        pointer = (index+1)%len(sporder)
                        break
            else:
                a,b = successors[c][0]
                send(a,b,s)
                path = comps[c]
                for i in range(len(path)-2,-1,-1):
                    send(path[i],path[i+1],s)
        for c in base:
            if c in done:
                continue
            a,b = successors[c][0]
            if c != "S" and eligible(a,b,s):
                # In this network only the always-accepting core has >1
                # non-splitter upstream, so every polling order has same result.
                for partner in sorted(upstream[b],key=base.index):
                    plain(partner)
            else:
                plain(c)
        assert len(done)==len(comps)
        for source,label in (("WA","LA"),("WB","LB")):
            n = paths[label][0]
            if goods[n] is None and warehouse:
                warehouse -= 1
                goods[n] = (s,source)
                counts[(source,n)] += 1
        minimum = min(minimum,warehouse)
        assert warehouse + sum(t is not None for t in goods.values()) == 80000
        k = key(s)
        if k in seen:
            previous, oldcounts = seen[k]
            period = s-previous
            rates = {f"{a}→{b}":str(Fraction(8*(counts[(a,b)]-oldcounts[(a,b)]),period)) for a,b in (("S","M"),("S","N"),("U","M"))}
            return {"first":first,"repeat_step_ends_zero_based":[previous,s],"completed_steps":[previous+1,s+1],"period_steps":period,
                    "rates_per_tick":rates,"minimum_warehouse":minimum,"occupied_cells":used,"channel_count":len(edges),
                    "belt_lengths":{k:len(v) for k,v in paths.items()},"levels":levels,"base_order":base,
                    "connection_times":{f"{a}→{b}":t for (a,b),t in sorted(times.items())},"events":traces,
                    "cycle_key_includes":"warehouse, all transport goods with capped age and physical previous unit, gate window remainders, splitter pointer"}
        seen[k] = (s,counts.copy())
    raise AssertionError("no cycle found")


answers = {first:run(first) for first in ("U","S")}
assert answers["U"]["repeat_step_ends_zero_based"] == [144,184]
assert answers["S"]["repeat_step_ends_zero_based"] == [128,208]
assert answers["U"]["rates_per_tick"] == {"S→M":"0","S→N":"1/5","U→M":"1/5"}
assert answers["S"]["rates_per_tick"] == {"S→M":"1/10","S→N":"1/10","U→M":"1/5"}
assert all(v["minimum_warehouse"] == 79966 for v in answers.values())
(OUT/"密集结点复算结果.json").write_text(json.dumps({"all_checks_passed":True,"cases":answers},ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"all_checks_passed":True, **{k:{x:v[x] for x in ("repeat_step_ends_zero_based","period_steps","rates_per_tick","minimum_warehouse","channel_count")} for k,v in answers.items()}},ensure_ascii=False))
