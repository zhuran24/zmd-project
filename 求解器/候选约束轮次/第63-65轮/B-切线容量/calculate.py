#!/usr/bin/env python3
"""第63轮：从当前正式文件复算窄条矿物切线；仅写入本脚本目录。"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
K = {"蓝铁矿", "源矿", "蓝铁块", "蓝铁粉末", "源石粉末"}
KINDS = ["粉碎机", "精炼炉", "研磨机", "塑形机", "配件机", "种植机", "采种机", "封装机", "灌装机"]
MINIMUM = dict(zip(KINDS, [68, 51, 32, 6, 6, 32, 16, 3, 3]))


def save(name, data):
    p = OUT / name
    assert p.parent == OUT and p.suffix in {".json", ".md", ".log"}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def digest(b):
    return hashlib.sha256(b).hexdigest()


def terms(s):
    d = {}
    for t in re.split(r"\s*[＋+]\s*", s.strip()):
        m = re.fullmatch(r"(\d+)\s+(.+)", t)
        assert m, t
        d[m[2]] = int(m[1])
    return d


def parse_recipes(text):
    current = None
    rows = []
    for line in text.split("\n配方\n", 1)[1].splitlines():
        line = line.strip()
        if line in KINDS:
            current = line
        elif "→" in line:
            a, b = line.split("→")
            m = re.fullmatch(r"(.+)，\s*(\d+)\s*tick", b.strip())
            assert current and m
            inp, prod, ticks = terms(a), terms(m[1]), int(m[2])
            ki = sum(inp.get(k, 0) for k in K)
            ko = sum(prod.get(k, 0) for k in K)
            rows.append(dict(kind=current, inputs=inp, outputs=prod, ticks=ticks,
                             K_in=ki, K_out=ko, K_net_consumption=ki-ko))
    return rows


def ports(gap):
    # 按3格取货口实际铺满70格，不用模数近似。
    blocks = [(x, x+1, x+2) for x in range(0, gap, 3)]
    blocks += [(x, x+1, x+2) for x in range(gap+1, 68, 3)]
    assert len(blocks) == 23
    assert set().union(*map(set, blocks)) == set(range(70)) - {gap}
    return [t[1] for t in blocks]


def body(x, y, w, h):
    return {(i, j) for i in range(x, x+w) for j in range(y, y+h)}


def edge_ports(x, y, w, h, axis, reverse):
    if axis == "vertical":
        low = {(i, y-1) for i in range(x, x+w)}
        high = {(i, y+h) for i in range(x, x+w)}
    else:
        low = {(x-1, j) for j in range(y, y+h)}
        high = {(x+w, j) for j in range(y, y+h)}
    return (high, low) if reverse else (low, high)


def shapes(kind):
    if kind in ["粉碎机", "精炼炉", "塑形机", "配件机"]:
        return [(3, 3, a) for a in ["vertical", "horizontal"]]
    if kind in ["种植机", "采种机"]:
        return [(5, 5, a) for a in ["vertical", "horizontal"]]
    return [(6, 4, "vertical"), (4, 6, "horizontal")]


def enumerate_units(b, gap):
    """所有碰右侧下条的单台制造单位。端口只要求两侧各有一个可用邻格，故是放宽。"""
    hole = body(49, b, 21, 53)
    ore = {(x, 1) for x in ports(gap)}
    whole, crossing = [], []
    for kind in KINDS:
        for w, h, axis in shapes(kind):
            for x in range(50-w, 71-w):
                for y in range(1, b-h+1):
                    cells = body(x, y, w, h)
                    if cells & (hole | ore):
                        continue
                    for reverse in [False, True]:
                        inp, prod = edge_ports(x, y, w, h, axis, reverse)
                        def allowed(p):
                            i, j = p
                            # 第0行/列唯一空格不能承载循环正流量，见报告证明。
                            return 1 <= i < 70 and 1 <= j < 70 and p not in hole
                        ip, op = sorted(filter(allowed, inp)), sorted(filter(allowed, prod))
                        if not ip or not op:
                            continue
                        rec = dict(kind=kind, x=x, y=y, w=w, h=h, axis=axis,
                                   input_side=("top" if reverse else "bottom") if axis == "vertical" else ("right" if reverse else "left"),
                                   input_neighbors=ip, output_neighbors=op)
                        (whole if x >= 49 else crossing).append(rec)
    return whole, crossing


def main():
    sources = ["《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt"]
    snapshots = ["游戏规则快照.md", "求解任务快照.md", "求解约束快照.md"]
    manifest = []
    contents = []
    for name, snap in zip(sources, snapshots):
        raw = (ROOT / name).read_bytes()
        contents.append(raw.decode())
        (OUT / snap).write_bytes(raw)
        manifest.append(dict(path=str(ROOT / name), sha256=digest(raw), bytes=len(raw), snapshot=snap))
    rules, task, constraints = contents
    for phrase in ["不会移回刚离开的单位", "一个物品格（桥接器例外），上限1", "两对平行边互不相干，各有一个物品格"]:
        assert phrase in rules
    assert "(49,6)、(49,7)、(49,9)、(49,17)" in constraints
    assert "没有协议储存箱且 P ≤12" in constraints
    recipes = parse_recipes(rules)
    assert len(recipes) == 18
    kappa = {k: max(Fraction(r["K_in"], r["ticks"]) for r in recipes if r["kind"] == k) for k in KINDS}
    for r in recipes:
        if r["K_net_consumption"]:
            assert r["kind"] == "研磨机" and r["K_net_consumption"] == 2
    assert sum(r["K_net_consumption"] != 0 for r in recipes) == 2

    # 按全厂配方批次，复算大制造单位逐机的最低平均批次率。
    large_total = {"研磨机": Fraction(63, 2), "封装机": Fraction(3, 5), "灌装机": Fraction(11, 20)}
    minimum_large_rate = {}
    minimum_large_inflow = {}
    for k, total in large_total.items():
        rr = [r for r in recipes if r["kind"] == k]
        cap = Fraction(1, rr[0]["ticks"])
        minimum_large_rate[k] = total - (MINIMUM[k]-1)*cap
        nin = {sum(r["inputs"].values()) for r in rr}
        assert len(nin) == 1
        minimum_large_inflow[k] = minimum_large_rate[k]*nin.pop()

    patterns = [(0, g) for g in range(0, 70, 3)] + [(g, 0) for g in range(3, 70, 3)]
    assert len(patterns) == 47
    enumerations = []
    valid_b7 = []
    tallies = []
    min_delta = []
    for b in [6, 7, 9, 17]:
        for lg, bg in patterns:
            whole, crossing = enumerate_units(b, bg)
            q = sum(x >= 49 for x in ports(bg))
            assert q == 7
            deltas = [Fraction(u["h"])-kappa[u["kind"]] for u in crossing]
            assert all(d >= 2 for d in deltas)
            min_delta += deltas
            big = [u for u in whole if u["kind"] in large_total]
            gr = [u for u in big if u["kind"] == "研磨机"]
            if b == 6:
                assert not gr and not big
            if b == 7:
                assert all((u["w"], u["h"], u["y"], u["axis"]) == (6, 4, 2, "vertical") for u in big)
                feasible_large = []
                for u in big:
                    m = sum(u["x"] <= p < u["x"]+u["w"] for p in ports(bg))
                    assert m in [1, 2]
                    # 一格高的端口前走廊，两个端部合计2件/tick，按真实最低流量收费。
                    load = minimum_large_inflow[u["kind"]] if u["input_side"] == "bottom" else minimum_large_rate[u["kind"]]
                    if m + load <= 2:
                        assert m == 1 and u["input_side"] == "top"
                        feasible_large.append(u)
                starts = sorted({u["x"] for u in feasible_large})
                assert all(abs(a-c) < 6 for a in starts for c in starts)
                if starts:
                    assert lg == 0
                    valid_b7.append(dict(left_gap=lg, bottom_gap=bg, grinder_x=starts,
                                         grinder_y=2, width=6, height=4,
                                         input_side="top", output_side="bottom",
                                         mineral_recipe_rate_min="1/2", total_recipe_rate_max="1"))
                tallies.append(dict(left_gap=lg, bottom_gap=bg,
                                    full_large_singleton_domain=len(big),
                                    corridor_survivor_count=len(feasible_large),
                                    corridor_survivor_starts=starts))
            enumerations.append(dict(b=b, left_gap=lg, bottom_gap=bg, raw_ore_sources=q,
                                     whole_by_kind=dict(Counter(u["kind"] for u in whole)),
                                     crossing_by_kind=dict(Counter(u["kind"] for u in crossing)),
                                     whole_grinder_count_in_singleton_domain=len(gr),
                                     crossing_delta_min=str(min(deltas)) if deltas else None))
    assert len(valid_b7) == 6
    assert [d["bottom_gap"] for d in valid_b7] == [51, 54, 57, 60, 63, 66]
    assert sum(len(d["grinder_x"]) for d in valid_b7) == 10

    result_rows = []
    for transpose in [False, True]:
        for b in [6, 7, 9, 17]:
            position = [b, 49] if transpose else [49, b]
            nominal = b-1
            result_rows.append(dict(position=position, rectangle_size=[53,21] if transpose else [21,53],
                                    cut="y=48.5" if transpose else "x=48.5",
                                    source_rate=7, geometric_capacity=nominal,
                                    corrected_margin_formula=f"{nominal-7} + 2G - D",
                                    other_arm_height=17-b,
                                    excluded=b == 6,
                                    excluded_P=[10,11,12] if b == 6 else [],
                                    decisive_deficit=7-nominal if b == 6 else None,
                                    strongest_remaining_statement=("G=0，D≥0，缺2件/tick" if b == 6 else
                                        "恰一台大制造单位且为研磨机，1/2≤G≤总批次率≤1，D=0；矿物切线余量0至1" if b == 7 else
                                        f"余量为{nominal-7}+2G-D；G、D须随布局重算，未得固定正缺口")))

    # 同一条带内其他直线的源数；入口线的7是对所有边带排列的恒等值。
    sweep = []
    for a in range(49, 70):
        counts = [sum(x >= a for x in ports(g)) for g in range(0,70,3)]
        sweep.append(dict(first_column=a, source_min=min(counts), source_max=max(counts)))

    save("input_manifest.json", dict(timestamp=datetime.now().astimezone().isoformat(), sources=manifest))
    save("recipe_accounting.json", dict(K=sorted(K), recipes=recipes,
         kappa={k:str(v) for k,v in kappa.items()},
         minimum_large_batch_rate={k:str(v) for k,v in minimum_large_rate.items()},
         minimum_large_input_rate={k:str(v) for k,v in minimum_large_inflow.items()}))
    save("enumeration.json", dict(pattern_count=len(patterns), cases=enumerations,
                                   b7_corridor_cases=tallies, b7_survivors=valid_b7,
                                   cut_source_sweep=sweep))
    save("mineral_cut_results.json", dict(status="仅矿物切线阶段结果；全物料切线最终结果另见results.json",
         formal_item_count=sum(bool(re.match(r"^\S[^：]*：.+", s)) for s in constraints.splitlines()),
         positions=result_rows, excluded_positions=[[49,6],[6,49]],
         remaining_positions=[[49,7],[49,9],[49,17],[7,49],[9,49],[17,49]],
         b7_surviving_joint_border_patterns=6,
         b7_removed_joint_border_patterns=len(patterns)-len(valid_b7),
         b7_grinder_gap_position_pairs=sum(len(d["grinder_x"]) for d in valid_b7),
         candidate_status="待审", area_upper_bound_after_this_cut=1113,
         proof_not_claimed=["剩余六位置的存在性", "任一完整循环态的达标", "无箱范围以外的本条推广"] ))
    changed = []
    for item in manifest:
        if digest(Path(item["path"]).read_bytes()) != item["sha256"]:
            changed.append(item["path"])
    save("integrity.json", dict(sources_unchanged=not changed, changed=changed,
         script_sha256=digest(Path(__file__).read_bytes()),
         assertions="passed", minimum_crossing_height_minus_K_intake=str(min(min_delta)),
         facts_checked=["47种共同边带", "188个位置与边带单体枚举组合", "18条配方", "两条且仅两条配方消耗K", "b=6完整大机域为空", "b=7完整大机为6×4且y=2", "六种边带及十个研磨机起点组合"]))
    assert not changed
    print(json.dumps(dict(excluded=[[49,6],[6,49]], remaining=6,
                          b7_border_patterns=6, b7_grinder_pairs=10,
                          assertions="passed", sources_unchanged=True), ensure_ascii=False))


if __name__ == "__main__":
    main()
