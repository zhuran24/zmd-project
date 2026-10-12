#!/usr/bin/env python3
"""规则级几何见证和拆点流探针；不是游戏内核运行证书。"""
import hashlib
import json
from pathlib import Path

import networkx as nx

BASE = Path(__file__).resolve().parent
units = []
for x0 in (10, 17):
    for y0 in (10, 17):
        for dx in (0, 3):
            for dy in (0, 3):
                units.append({"id": f"墙-{x0+dx}-{y0+dy}", "kind": "粉碎机", "box": [x0+dx, y0+dy, 3, 3], "input": "west", "output": "east"})
units += [
    {"id": "源-西", "kind": "精炼炉", "box": [7, 15, 3, 3], "output": "east"},
    {"id": "源-北", "kind": "精炼炉", "box": [15, 7, 3, 3], "output": "south"},
    {"id": "汇-东", "kind": "粉碎机", "box": [23, 15, 3, 3], "input": "west"},
    {"id": "汇-南", "kind": "粉碎机", "box": [15, 23, 3, 3], "input": "north"},
    {"id": "核心", "kind": "协议核心", "box": [40, 40, 9, 9]},
]
occupied = set()
for u in units:
    x, y, w, h = u["box"]
    cells = {(a, b) for a in range(x, x+w) for b in range(y, y+h)}
    assert not occupied & cells
    assert all(0 <= a < 70 and 0 <= b < 70 for a, b in cells)
    occupied |= cells
free = {(x, y) for x in range(70) for y in range(70)} - occupied
graph = nx.DiGraph()
for cell in sorted(free):
    graph.add_edge((cell, "in"), (cell, "out"), capacity=1)
    x, y = cell
    for next_cell in ((x+1,y), (x-1,y), (x,y+1), (x,y-1)):
        if next_cell in free:
            graph.add_edge((cell,"out"), (next_cell,"in"), capacity=2)
sources, sinks = [(10,16), (16,10)], [(22,16), (16,22)]
for cell in sources:
    graph.add_edge("S", (cell,"in"), capacity=1)
for cell in sinks:
    graph.add_edge((cell,"out"), "T", capacity=1)
flow = nx.maximum_flow_value(graph, "S", "T")
cut_value, (reachable, unreachable) = nx.minimum_cut(graph, "S", "T")
graph_no_center = graph.copy()
graph_no_center.remove_nodes_from([((16,16),"in"), ((16,16),"out")])
assert not nx.has_path(graph_no_center, "S", "T")

# 两条进路同运蓝铁块，中心桥分别西->东、北->南；其余格为直带。
paths = [[(x,16) for x in range(10,23)], [(16,y) for y in range(10,23)]]
assert all(set(p) <= free for p in paths)
assert set(paths[0]) & set(paths[1]) == {(16,16)}
assert all(len(p) == len(set(p)) for p in paths)
assert flow == cut_value == 1
cut_arcs = [
    [repr(a), repr(b), d["capacity"]]
    for a,b,d in graph.edges(data=True)
    if a in reachable and b in unreachable
]
record = {
    "scope": "静态规则见证；未运行游戏内核；不声称是达标整厂",
    "coordinates": "0-based; x right; y down; box=[x,y,width,height]",
    "units": units,
    "item": "蓝铁块",
    "paths": paths,
    "bridge": {"cell": [16,16], "used": ["west->east", "north->south"], "unused": ["east->west", "south->north"]},
    "split_node_max_flow": flow,
    "minimum_cut": cut_value,
    "cut_arcs": cut_arcs,
    "center_removal_disconnects_all_sources_and_sinks": True,
    "legal_geometric_routes_with_bridge": 2,
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
(BASE / "同组桥交叉核验.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({k: record[k] for k in ["split_node_max_flow", "minimum_cut", "legal_geometric_routes_with_bridge", "center_removal_disconnects_all_sources_and_sinks"]},ensure_ascii=False))
