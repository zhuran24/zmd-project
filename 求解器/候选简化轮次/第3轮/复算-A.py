#!/usr/bin/env python3
"""局部几何、轮询料序及库存算术。不是全厂模拟器或最优性证书。"""
from pathlib import Path
from fractions import Fraction
from itertools import permutations
from math import ceil, lcm
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
READS = [
    "《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt",
    "候选简化.txt", "求解器/候选简化轮次/第1轮/推导.md",
    "求解器/候选简化轮次/第2轮/推导.md",
]
DIR = {"E": (1, 0), "W": (-1, 0), "N": (0, 1), "S": (0, -1)}
OPP = {"E": "W", "W": "E", "N": "S", "S": "N"}


def cell(name, x, y, ins, outs, kind="传送带"):
    return {"name": name, "kind": kind, "cells": [(x, y)],
            "ports": [(x, y, d, "in") for d in ins]
            + [(x, y, d, "out") for d in outs], "transport": True}


def rect(name, kind, x, y, w, h, in_side=None, out_side=None):
    sides = {
        "W": [(x, v, "W") for v in range(y, y+h)],
        "E": [(x+w-1, v, "E") for v in range(y, y+h)],
        "S": [(u, y, "S") for u in range(x, x+w)],
        "N": [(u, y+h-1, "N") for u in range(x, x+w)],
    }
    ports = []
    for side, role in ((in_side, "in"), (out_side, "out")):
        if side:
            ports += [(*p, role) for p in sides[side]]
    return {"name": name, "kind": kind,
            "cells": [(u, v) for u in range(x, x+w) for v in range(y, y+h)],
            "ports": ports, "transport": False}


def path(points, previous, following, prefix):
    units = []
    for i, (x, y) in enumerate(points):
        prev = previous if i == 0 else points[i-1]
        nxt = following if i == len(points)-1 else points[i+1]
        ins = next(k for k, d in DIR.items() if d == (prev[0]-x, prev[1]-y))
        outs = next(k for k, d in DIR.items() if d == (nxt[0]-x, nxt[1]-y))
        units.append(cell(f"{prefix}{i}", x, y, ins, outs))
    return units


def inspect(units):
    occupied = {}
    ports = {}
    for u in units:
        for xy in u["cells"]:
            assert xy not in occupied, (xy, occupied.get(xy), u["name"])
            assert all(0 <= v < 70 for v in xy)
            occupied[xy] = u["name"]
        for x, y, d, role in u["ports"]:
            ports[(x, y, d)] = (u, role)
    edges = []
    for (x, y, d), (u, role) in ports.items():
        if role != "out":
            continue
        dx, dy = DIR[d]
        other = ports.get((x+dx, y+dy, OPP[d]))
        if other:
            v, vrole = other
            if vrole == "in" and (u["transport"] or v["transport"]):
                edges.append((u["name"], v["name"]))
    return occupied, sorted(edges)


def wrong_material_removal():
    units = [rect("源矿取货口", "仓库取货口", 0, 3, 1, 3),
             rect("蓝铁矿取货口", "仓库取货口", 0, 9, 1, 3),
             rect("源矿粉碎机", "粉碎机", 6, 1, 3, 3, "W", "E"),
             rect("蓝铁矿精炼炉", "精炼炉", 6, 5, 3, 3, "W", "E"),
             rect("供电桩", "供电桩", 10, 4, 2, 2),
             cell("分流器", 2, 4, "W", "ENS", "分流器")]
    units[0]["ports"] = [(0, 4, "E", "out")]
    units[1]["ports"] = [(0, 10, "E", "out")]
    units += path([(1, 4)], (0, 4), (2, 4), "源矿公共段")
    units += path([(2, 3), (2, 2), (3, 2), (4, 2), (5, 2)],
                  (2, 4), (6, 2), "源矿生产段")
    units += path([(9, 2)], (8, 2), (10, 2), "粉碎机输出")
    branch = path([(3, 4), (4, 4), (5, 4), (5, 5)],
                  (2, 4), (6, 5), "误料支路")
    branch[1]["kind"] = "物品准入口"
    units += branch
    units += path([(1, 10), (2, 10), (3, 10), (4, 10), (5, 10),
                   (5, 9), (5, 8), (5, 7)], (0, 10), (6, 7), "蓝铁矿生产段")
    units += path([(9, 6)], (8, 6), (10, 6), "精炼炉输出")
    before, before_edges = inspect(units)
    removed = {u["name"] for u in branch}
    after_units = [u for u in units if u["name"] not in removed]
    after, after_edges = inspect(after_units)
    assert len(before) == 49 and len(before_edges) == 24
    assert len(after) == 45 and len(after_edges) == 19
    assert set(after) < set(before)
    assert after_edges == [e for e in before_edges if not set(e) & removed]
    return {"before_cells": len(before), "after_cells": len(after),
            "before_units": len(units), "after_units": len(after_units),
            "before_channels": before_edges, "after_channels": after_edges,
            "removed_cells": sorted(set(before)-set(after)),
            "rectangle_certificate": "占格严格取子集；原有每一个空矩形完整保留",
            "scope": "第1轮明确局部的端口与占格，不是全厂达标检查"}


def priority_word_geometry():
    units = [rect("协议储存箱A", "协议储存箱", 10, 20, 3, 3, "W", "E"),
             rect("协议储存箱B", "协议储存箱", 14, 16, 3, 3, "S", "N"),
             cell("分流器", 13, 21, "W", "ENS", "分流器"),
             cell("汇流器", 14, 21, "WNS", "E", "汇流器"),
             rect("研磨机", "研磨机", 16, 19, 4, 6, "W", "E"),
             rect("供电桩", "供电桩", 20, 16, 2, 2),
             rect("收货协议储存箱", "协议储存箱", 21, 20, 3, 3, "W", "E")]
    units += path([(14, 19), (14, 20)], (14, 18), (14, 21), "B传送带")
    units += path([(15, 21)], (14, 21), (16, 21), "混线传送带")
    units += path([(20, 21)], (19, 21), (21, 21), "输出传送带")
    occupied, edges = inspect(units)
    expected = sorted([
        ("协议储存箱A", "分流器"), ("分流器", "汇流器"),
        ("协议储存箱B", "B传送带0"), ("B传送带0", "B传送带1"),
        ("B传送带1", "汇流器"), ("汇流器", "混线传送带0"),
        ("混线传送带0", "研磨机"), ("研磨机", "输出传送带0"),
        ("输出传送带0", "收货协议储存箱")])
    assert edges == expected
    # 源A共102件：箱101+分流器1；源B共51件：箱49+带2。
    # 初始运输格均已满足滞留。每次腾空，按最高可动级选择来源。
    left = {"A": 102, "B": 51}
    word = []
    while any(left.values()):
        selected = next(k for k in "AB" if left[k])
        word.append(selected)
        left[selected] -= 1
    assert "".join(word) == "A"*102 + "B"*51
    return {"units": units, "cells": len(occupied), "channels": edges,
            "source_materials": {"A": "蓝铁粉末", "B": "砂叶粉末"},
            "initial_box_A": [50, 50, 1, 0, 0, 0],
            "initial_box_B": [49, 0, 0, 0, 0, 0],
            "initial_transport": {"分流器": "A", "B传送带0": "B", "B传送带1": "B"},
            "transmission": "全部协议储存箱的传输关闭",
            "priority": "分流器直接接入的一级先接通，级别高于B来路",
            "offered_word_with_accepting_receiver": "A^102 B^51",
            "scope": "有限供料词的实际接法；不声称堵满起法必留下这个状态，亦非达标全厂反例"}


def eager_fifo(word, a, b, x, y):
    """制造瞬时且输出无限可排，仅核对整批与存货；不模拟游戏时间。"""
    batches = 0
    def consume(x, y, batches):
        n = min(x//a, y//b)
        return x-a*n, y-b*n, batches+n
    x, y, batches = consume(x, y, batches)
    for index, material in enumerate(word, 1):
        if (x if material == "A" else y) == 50:
            return {"blocked_at": index, "material": material,
                    "inventory": [x, y], "batches": batches}
        if material == "A":
            x += 1
        else:
            y += 1
        x, y, batches = consume(x, y, batches)
    return {"blocked_at": None, "inventory": [x, y], "batches": batches}


def word_checks():
    out = {}
    for base, a, b in [("AAB", 2, 1), ("AB", 10, 10)]:
        words = sorted({"".join(p) for p in permutations(base)})
        values = []
        z0 = 50*(b-a)
        lower = b*(a-1)-50*a
        upper = 50*b-a*(b-1)
        for word in words:
            d = 0
            ds = [0]
            for item in word:
                d += b if item == "A" else -a
                ds.append(d)
            assert d == 0
            assert lower < z0+min(ds) <= z0+max(ds) < upper
            # 是算术旁证；永久不堵的证明在报告中使用严格不变量。
            simulation = eager_fifo(word*100, a, b, 50, 50)
            assert simulation["blocked_at"] is None
            values.append({"word": word, "D_min": min(ds), "D_max": max(ds)})
        out[base] = {"words": values, "Z0": z0,
                     "safe_open_interval": [lower, upper]}
    longword = "A"*102+"B"*51
    full = eager_fifo(longword, 2, 1, 50, 50)
    low = eager_fifo(longword, 2, 1, 0, 50)
    assert full["blocked_at"] == 101
    assert low["blocked_at"] is None and low["inventory"] == [0, 50]
    out["priority_finite_word"] = {"full": full, "low": low,
        "scope": "即使放宽制造为瞬时，全满仍在第101件失败；不是全厂或通用调试证书"}
    variants = []
    for kind, a, b, na, nb in [("研磨机", 2, 1, 102, 51),
                               ("封装机", 10, 15, 40, 60),
                               ("灌装机", 10, 10, 60, 60)]:
        word = "A"*na+"B"*nb
        full = eager_fifo(word, a, b, 50, 50)
        low = eager_fifo(word, a, b, 0, 50)
        assert full["blocked_at"] == a*(50//b)+1
        assert low["blocked_at"] is None and low["inventory"] == [0, 50]
        variants.append({"machine": kind, "recipe": [a, b], "word_counts": [na, nb],
                         "full": full, "low": low,
                         "initial_source_A_box_total": na-1,
                         "initial_source_B_box_total": nb-2})
    out["priority_finite_word_variants"] = variants
    splits = []
    for word, k in [("AB", 2), ("AAB", 2), ("AAB", 3)]:
        period = lcm(len(word), k)
        repeated = (word*((period+len(word)-1)//len(word)))[:period]
        routes = [repeated[j::k] for j in range(k)]
        splits.append({"word": word, "outputs": k, "period": period, "route_words": routes})
    out["split_under_constraint_轮询均分"] = splits
    return out


def same_level_geometry():
    # 与长段料序接法相比，西入汇流器前改为传送带，增设北侧同级A来路。
    units = [rect("西协议储存箱A", "协议储存箱", 10, 20, 3, 3, "W", "E"),
             rect("南协议储存箱B", "协议储存箱", 14, 16, 3, 3, "S", "N"),
             rect("北协议储存箱A", "协议储存箱", 12, 24, 3, 3, "N", "S"),
             cell("西传送带", 13, 21, "W", "E"),
             cell("汇流器", 14, 21, "WNS", "E", "汇流器"),
             rect("研磨机", "研磨机", 16, 19, 4, 6, "W", "E"),
             rect("供电桩", "供电桩", 20, 16, 2, 2)]
    units += path([(14, 19), (14, 20)], (14, 18), (14, 21), "南传送带")
    units += path([(14, 23), (14, 22)], (14, 24), (14, 21), "北传送带")
    units += path([(15, 21)], (14, 21), (16, 21), "混线传送带")
    occupied, edges = inspect(units)
    assert len(edges) == 10
    assert sorted(a for a, b in edges if b == "汇流器") == ["北传送带1", "南传送带1", "西传送带"]
    return {"units": units, "channels": edges, "cells": len(occupied),
            "three_input_words": sorted({"".join(p) for p in permutations("AAB")}),
            "two_input_variant": "删除北协议储存箱和两格北传送带，研磨机原位换灌装机：AB或BA",
            "scope": "各箱有足量存货、入口持续就绪的有限料序段；无限续供未凭空假定"}


def capacity_checks():
    total_rate = Fraction(11, 20)
    max_rate = Fraction(1, 5)
    min_rate = total_rate-2*max_rate
    channels_each = 2*ceil(10*min_rate)
    assert min_rate == Fraction(3, 20)
    assert channels_each == 4 and 3*channels_each == 12
    return {
        "two_single_input_channels_max_batch_rate": {
            "研磨机": str(Fraction(1, 2)), "封装机": str(Fraction(1, 15)),
            "灌装机": str(Fraction(1, 10))},
        "three_filling_machines": {
            "total_rate": str(total_rate), "individual_rate_min": str(min_rate),
            "individual_rate_max": str(max_rate),
            "pure_channels_per_machine_min": channels_each, "pure_total_min": 3*channels_each,
            "mixed_constraint_min": 11},
        "packaging_at_minimum_machine_count": {"per_machine_A": 2, "per_machine_B": 3,
                                                "pure_channels_per_machine_min": 5},
        "plant": {"荞花": {"采种": "11/2", "种植": 11, "粉碎": "11/2"},
                  "砂叶": {"采种": "21/2", "种植": 21, "粉碎": "21/2"}},
    }


def main():
    sources = {}
    for filename in READS:
        data = (ROOT/filename).read_bytes()
        sources[filename] = {"sha256": hashlib.sha256(data).hexdigest(),
                             "lines": len(data.decode().splitlines())}
    constraints = (ROOT/"求解约束.txt").read_text()
    count = sum(line.strip().startswith("据：") for line in constraints.splitlines())
    assert count == 72, count
    result = {"scope": "局部证明的算术与几何复算；未验证全厂72条、全局最优或全部事件次序",
              "input_sources": sources, "constraint_count": count,
              "artifact_sha256": {name: hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                                  for name in ["复算-A.py", "推导-A.md"]},
              "wrong_material_removal": wrong_material_removal(),
              "priority_word_layout": priority_word_geometry(),
              "same_level_layout": same_level_geometry(),
              "word_checks": word_checks(), "capacity_checks": capacity_checks()}
    target = HERE/"复算结果-A.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"result": str(target), "constraint_count": count,
                      "removed_cells": result["wrong_material_removal"]["removed_cells"],
                      "priority_layout_channels": len(result["priority_word_layout"]["channels"]),
                      "checks": "passed; scope is local arithmetic and geometry"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
