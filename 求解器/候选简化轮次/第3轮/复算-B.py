#!/usr/bin/env python3
"""B 席局部几何及算术复算；不是全厂可行性或最优性校验器。"""
from pathlib import Path
from fractions import Fraction
from itertools import permutations
from math import lcm
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
V = {"E": (1, 0), "W": (-1, 0), "N": (0, 1), "S": (0, -1)}
OPP = {"E": "W", "W": "E", "N": "S", "S": "N"}


def unit(name, kind, cells, ins=(), outs=(), transport=False):
    return dict(name=name, kind=kind, cells=set(cells), ins=set(ins),
                outs=set(outs), transport=transport)


def rect(x0, y0, w, h):
    return {(x, y) for x in range(x0, x0+w) for y in range(y0, y0+h)}


def belt(x, y, incoming, outgoing, kind="传送带"):
    return unit(f"{kind}({x},{y})", kind, {(x, y)}, {(x, y, incoming)},
                {(x, y, outgoing)}, True)


def machine(name, x, y, w, h, incoming, outgoing, kind):
    def edge(d):
        if d == "W": return {(x, yy, d) for yy in range(y, y+h)}
        if d == "E": return {(x+w-1, yy, d) for yy in range(y, y+h)}
        if d == "S": return {(xx, y, d) for xx in range(x, x+w)}
        return {(xx, y+h-1, d) for xx in range(x, x+w)}
    return unit(name, kind, rect(x, y, w, h), edge(incoming), edge(outgoing))


def geometry(units):
    occupied = {}
    for u in units:
        for c in u["cells"]:
            assert 0 <= c[0] < 70 and 0 <= c[1] < 70
            assert c not in occupied, (c, u["name"], occupied.get(c))
            occupied[c] = u["name"]
    channels = set()
    for u in units:
        for x, y, d in u["outs"]:
            dx, dy = V[d]
            for v in units:
                if u is not v and (u["transport"] or v["transport"]):
                    if (x+dx, y+dy, OPP[d]) in v["ins"]:
                        channels.add((u["name"], v["name"], x, y, d))
    return occupied, channels


def error_branch():
    us = [unit("源矿仓库取货口", "仓库取货口", rect(0, 3, 1, 3), outs={(0, 4, "E")}),
          unit("蓝铁矿仓库取货口", "仓库取货口", rect(0, 9, 1, 3), outs={(0, 10, "E")}),
          machine("源矿粉碎机", 6, 1, 3, 3, "W", "E", "粉碎机"),
          machine("蓝铁矿精炼炉", 6, 5, 3, 3, "W", "E", "精炼炉"),
          unit("供电桩", "供电桩", rect(10, 4, 2, 2)),
          unit("分流器(2,4)", "分流器", {(2, 4)}, {(2, 4, "W")},
               {(2, 4, "E"), (2, 4, "S"), (2, 4, "N")}, True)]
    paths = [([(0, 4), (1, 4), (2, 4)], False),
             ([(2, 4), (2, 3), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2)], False),
             ([(2, 4), (3, 4), (4, 4), (5, 4), (5, 5), (6, 5)], True),
             ([(0, 10), (1, 10), (2, 10), (3, 10), (4, 10), (5, 10),
               (5, 9), (5, 8), (5, 7), (6, 7)], False),
             ([(8, 2), (9, 2), (10, 2)], False),
             ([(8, 6), (9, 6), (10, 6)], False)]
    reverse = {v: k for k, v in V.items()}
    removed = set()
    for path, delete in paths:
        for prev, cur, nxt in zip(path, path[1:], path[2:]):
            incoming = reverse[(prev[0]-cur[0], prev[1]-cur[1])]
            outgoing = reverse[(nxt[0]-cur[0], nxt[1]-cur[1])]
            kind = "物品准入口" if cur == (4, 4) else "传送带"
            u = belt(*cur, incoming, outgoing, kind)
            us.append(u)
            if delete: removed.add(u["name"])
    after = [u for u in us if u["name"] not in removed]
    occ0, e0 = geometry(us)
    occ1, e1 = geometry(after)
    assert set(occ1) <= set(occ0)
    assert e1 == {e for e in e0 if e[0] not in removed and e[1] not in removed}
    assert (len(us), len(occ0), len(e0)) == (26, 49, 24)
    assert (len(after), len(occ1), len(e1)) == (22, 45, 19)
    return dict(before=dict(units=len(us), cells=len(occ0), channels=len(e0)),
                after=dict(units=len(after), cells=len(occ1), channels=len(e1)),
                removed=sorted(removed), channels_after=sorted(e1),
                scope="第1轮指定局部；外部只在原文两个出货接口接入；不证明全厂构造")


def merge_geometry():
    us = [machine("粉碎机-蓝铁粉末一", 16, 19, 3, 3, "W", "E", "粉碎机"),
          machine("粉碎机-蓝铁粉末二", 19, 24, 3, 3, "N", "S", "粉碎机"),
          machine("粉碎机-砂叶粉末", 19, 14, 3, 3, "S", "N", "粉碎机"),
          unit("汇流器(20,20)", "汇流器", {(20, 20)},
               {(20, 20, "W"), (20, 20, "N"), (20, 20, "S")}, {(20, 20, "E")}, True),
          unit("分流器(22,20)", "分流器", {(22, 20)}, {(22, 20, "W")},
               {(22, 20, "E"), (22, 20, "N"), (22, 20, "S")}, True),
          unit("供电桩一", "供电桩", rect(15, 23, 2, 2)),
          unit("供电桩二", "供电桩", rect(24, 12, 2, 2)),
          belt(19, 20, "W", "E"), belt(21, 20, "W", "E"),
          belt(23, 20, "W", "E"), belt(22, 21, "S", "N"), belt(22, 19, "N", "S")]
    us += [belt(20, y, "N", "S") for y in (23, 22, 21)]
    us += [belt(20, y, "S", "N") for y in (17, 18, 19)]
    occ, edges = geometry(us)
    poles = [(16, 24), (25, 13)]
    for u in us:
        if u["kind"] == "粉碎机":
            assert any(any(cx-6 <= x < cx+6 and cy-6 <= y < cy+6 for x, y in u["cells"])
                       for cx, cy in poles)
    return dict(cells=len(occ), channels=sorted(edges),
                scope="有真实粉碎机的混料局部；持续原料输入及下游腾空为边界条件，不是达标全厂")


def rr_and_split():
    answer = {}
    for labels in (("A", "B"), ("A", "A", "B")):
        words = sorted({"".join(labels[i] for i in p) for p in permutations(range(len(labels)))})
        answer["".join(labels)] = {}
        for k in (2, 3):
            cases = []
            for w in words:
                n = lcm(len(w), k)
                outs = ["".join(w[i % len(w)] for i in range(j, n, k)) for j in range(k)]
                cases.append(dict(word=w, outputs=outs,
                                  A_fraction=[str(Fraction(s.count("A"), len(s))) for s in outs]))
            answer["".join(labels)][str(k)] = cases
    return answer


def quota_merge():
    # 一种允许的固定事件安排：先收进物品准入口，再汇流，最后补空的准入口。
    # 汇流器每 tick 腾空一次；B 的首运输格始终就绪；A 只经 k=2 的物品准入口。
    item_tick, window_start, window_count, pointer = None, None, 0, 0
    trace = []
    def accept(t):
        nonlocal item_tick, window_start, window_count
        if item_tick is not None: return
        if window_start is None or t-window_start >= 5:
            window_start, window_count = t, 0
        if window_count < 2:
            item_tick = t
            window_count += 1
    for t in range(40):
        accept(t)
        ready = [item_tick is not None and t-item_tick >= 1, True]
        chosen = next(i for i in (pointer, 1-pointer) if ready[i])
        label = "AB"[chosen]
        if chosen == 0: item_tick = None
        pointer = 1-chosen
        accept(t)
        trace.append(dict(tick=t, sent=label, gate_item_tick=item_tick,
                          window_start=window_start, window_count=window_count, pointer=pointer))
    word = "".join(x["sent"] for x in trace)
    assert word == "BABAB" * 8
    # 后五个事件的全部计时字段与前五个相差五；其余状态相同。
    for p, q in zip(trace[:5], trace[5:10]):
        for field in ("sent", "window_count", "pointer"): assert p[field] == q[field]
        for field in ("gate_item_tick", "window_start"):
            assert (p[field] is None and q[field] is None) or q[field] == p[field]+5
    return dict(word=word, trace=trace[:10],
                scope="固定判定次序、持续就绪及出口每tick腾空下的一个可实现周期；不覆盖堵满释放")


def quota_merge_geometry():
    us = [machine("配件机-钢制零件", 15, 19, 3, 3, "W", "E", "配件机"),
          machine("研磨机-致密源石粉末", 18, 24, 6, 4, "N", "S", "研磨机"),
          unit("供电桩", "供电桩", rect(13, 23, 2, 2)),
          unit("汇流器(20,20)", "汇流器", {(20, 20)},
               {(20, 20, "W"), (20, 20, "N"), (20, 20, "S")}, {(20, 20, "E")}, True),
          belt(19, 20, "W", "E", "物品准入口"), belt(18, 20, "W", "E"),
          belt(21, 20, "W", "E")]
    us += [belt(20, y, "N", "S") for y in (23, 22, 21)]
    occ, edges = geometry(us)
    for u in us[:2]:
        assert any(8 <= x < 20 and 18 <= y < 30 for x, y in u["cells"])
    assert len(occ) == 44 and len(edges) == 8
    return dict(cells=len(occ), channels=sorted(edges),
                scope="ABABB 的局部坐标；输入持续供料、汇流器出口每tick腾空是边界条件")


def inventory_prefixes():
    result = []
    for name, a, b, word in [("研磨机", 2, 1, "AAB"),
                             ("封装机", 10, 15, "ABABB"),
                             ("灌装机", 10, 10, "AB")]:
        rows = []
        for shift in range(len(word)):
            w = word[shift:]+word[:shift]
            ds, d = [0], 0
            for c in w:
                d += b if c == "A" else -a
                ds.append(d)
            assert d == 0
            lower, upper = b*(a-51), a*(51-b)
            assert lower < min(ds) <= max(ds) < upper
            rows.append(dict(word=w, min_D=min(ds), max_D=max(ds)))
        result.append(dict(machine=name, a=a, b=b, rotations=rows,
                           exclude_permanent_head_block=dict(strict_lower=b*(a-51), strict_upper=a*(51-b)),
                           scope="单配方、唯一共用FIFO、输出最终可排走；只排永久带头堵塞，不证全厂产率"))
    return result


def two_channels():
    return {"研磨机": str(Fraction(2, 3)), "封装机": str(Fraction(2, 25)),
            "灌装机": str(Fraction(1, 10)),
            "scope": "每台恰两条存货通道时的总件数上界；分两种独立料路可以各有多条通道"}


def main():
    inputs = ["《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt", "候选简化.txt",
              "求解器/候选简化轮次/第1轮/推导.md", "求解器/候选简化轮次/第2轮/推导.md"]
    data = dict(input_sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs},
                constraints_count=sum(x.lstrip().startswith("据：") for x in (ROOT/"求解约束.txt").read_text().splitlines()),
                error_branch=error_branch(), mixed_geometry=merge_geometry(),
                round_robin=rr_and_split(), quota_merge=quota_merge(),
                quota_merge_geometry=quota_merge_geometry(),
                inventory_prefixes=inventory_prefixes(), two_channels=two_channels(),
                overall_scope="局部坐标、料序构造与必要/充分算式的复算；不运行全厂、不检验最优性、不读取另一席文件")
    assert data["constraints_count"] == 72
    target = HERE/"复算结果-B.json"
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(dict(result="PASS", output=str(target), constraints_count=72,
                          error_branch=data["error_branch"]["after"],
                          mixed_geometry_cells=data["mixed_geometry"]["cells"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
