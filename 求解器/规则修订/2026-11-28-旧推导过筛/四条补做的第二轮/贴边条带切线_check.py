#!/usr/bin/env python3
"""独立复核「贴边条带切线」：
 A. 跨线单位 κ 的最坏值（各机型、各朝向、各相对切线位置、配方）与 h−κ；
 B. 运输单位端口构型：同一条边上同时有存货端口和取货端口的只有桥接器；
 C. 切线一行（R 侧 n 格一直到右边界）的双向通过量 LP：双向合计 ≤1，且不能双向同时为正；
    对照：东端放开（条带不贴右边界）时可到 2；
 D. 整数推论 D ≤ H−m+2N、U ≤ N+⌊(H−m)/2⌋ 的穷举核对。
只用规则文件里的尺寸、端口和配方。"""
import itertools
from fractions import Fraction as Fr
import numpy as np
from scipy.optimize import linprog

FIVE = {"源矿", "蓝铁矿", "蓝铁块", "蓝铁粉末", "源石粉末"}
RECIPES = {
    "粉碎机": [({"源矿": 1}, {"源石粉末": 1}, 1), ({"蓝铁块": 1}, {"蓝铁粉末": 1}, 1),
             ({"荞花": 1}, {"荞花粉末": 2}, 1), ({"砂叶": 1}, {"砂叶粉末": 3}, 1)],
    "精炼炉": [({"蓝铁矿": 1}, {"蓝铁块": 1}, 1), ({"致密蓝铁粉末": 1}, {"钢块": 1}, 1),
             ({"蓝铁粉末": 1}, {"蓝铁块": 1}, 1)],
    "研磨机": [({"蓝铁粉末": 2, "砂叶粉末": 1}, {"致密蓝铁粉末": 1}, 1),
             ({"源石粉末": 2, "砂叶粉末": 1}, {"致密源石粉末": 1}, 1),
             ({"荞花粉末": 2, "砂叶粉末": 1}, {"细磨荞花粉末": 1}, 1)],
    "塑形机": [({"钢块": 2}, {"钢质瓶": 1}, 1)],
    "配件机": [({"钢块": 1}, {"钢制零件": 1}, 1)],
    "种植机": [({"荞花种子": 1}, {"荞花": 1}, 1), ({"砂叶种子": 1}, {"砂叶": 1}, 1)],
    "采种机": [({"荞花": 1}, {"荞花种子": 2}, 1), ({"砂叶": 1}, {"砂叶种子": 2}, 1)],
    "封装机": [({"钢制零件": 10, "致密源石粉末": 15}, {"高容谷地电池": 1}, 5)],
    "灌装机": [({"钢质瓶": 10, "细磨荞花粉末": 10}, {"精选荞愈胶囊": 1}, 5)],
}
KAPPA_STATED = {"粉碎机": 1, "精炼炉": 1, "研磨机": 2, "协议储存箱": 3}

# 五类集合在配方下的封闭性：没有配方由非五类产出五类；五类的汇只有研磨机矿物配方（每批 -2）
for mach, rs in RECIPES.items():
    for inp, out, t in rs:
        fi = sum(v for k, v in inp.items() if k in FIVE)
        fo = sum(v for k, v in out.items() if k in FIVE)
        if fo > 0:
            assert fi == fo, (mach, inp, out)
        if fi != fo:
            assert mach == "研磨机" and fi - fo == 2 and fo == 0, (mach, inp, out)
print("五类封闭性：只有粉碎/精炼在五类内一换一，研磨机矿物配方每批净减 2，其余配方不碰五类 —— 成立")

UNITS = {
    "粉碎机": (3, 3, "mfg"), "精炼炉": (3, 3, "mfg"), "配件机": (3, 3, "mfg"), "塑形机": (3, 3, "mfg"),
    "种植机": (5, 5, "mfg"), "采种机": (5, 5, "mfg"),
    "研磨机": (6, 4, "mfg"), "封装机": (6, 4, "mfg"), "灌装机": (6, 4, "mfg"),
    "协议储存箱": (3, 3, "mfg"), "协议核心": (9, 9, "core"), "供电桩": (2, 2, "none"),
}


def five_consume_bound(name):
    """循环态存货周期重复，收下=消耗；1 tick 配方每 tick ≤1 批。"""
    return max(Fr(sum(v for k, v in inp.items() if k in FIVE), t) for inp, _, t in RECIPES[name])


def footprints(name):
    w, h, kind = UNITS[name]
    for (W, Hh) in {(w, h), (h, w)}:
        if kind == "none":
            yield W, Hh, None
        elif kind == "mfg":
            if W == Hh:
                pairs = [("W", "E"), ("E", "W"), ("S", "N"), ("N", "S")]
            elif Hh > W:
                pairs = [("W", "E"), ("E", "W")]   # 存货在长边
            else:
                pairs = [("S", "N"), ("N", "S")]
            for ein, eout in pairs:
                yield W, Hh, {ein: "all"}
        else:  # 核心
            for inp_pair in (("W", "E"), ("S", "N")):
                yield W, Hh, {e: list(range(1, 8)) for e in inp_pair}


def count_r_ports(W, Hh, x0, edges):
    """切线在第 -1|0 列之间（R 为 x≥0），数外侧邻格在 R 内的存货端口。"""
    cnt = 0
    for e, which in edges.items():
        length = Hh if e in ("W", "E") else W
        idx = range(length) if which == "all" else which
        for i in idx:
            col = x0 - 1 if e == "W" else (x0 + W if e == "E" else x0 + i)
            if col >= 0:
                cnt += 1
    return cnt


print("\n=== A. 跨线单位 κ 最坏值 ===")
okA = True
for name in UNITS:
    best = Fr(0)
    hs = set()
    for W, Hh, ein in footprints(name):
        for x0 in range(-(W - 1), 0):  # 同时占第 a−1、a 列
            hs.add(Hh)
            if ein is None or name == "协议核心":
                val = Fr(0)   # 桩无端口；核心不收五类（矿系不入库），只往外送矿
            elif name == "协议储存箱":
                val = Fr(count_r_ports(W, Hh, x0, ein))
            else:
                val = min(five_consume_bound(name), Fr(count_r_ports(W, Hh, x0, ein)))
            best = max(best, val)
    ks = KAPPA_STATED.get(name, 0)
    ok = best <= ks
    if name == "协议储存箱":
        ok &= hs == {3}
    else:
        ok &= min(hs) - ks >= 2
    okA &= ok
    print(f"{name}: 最坏净收五类={best}/tick  条文κ={ks}  {'取到' if best == ks else '不紧'}  "
          f"h∈{sorted(hs)}  h−κ∈{sorted(x - ks for x in hs)}  {'OK' if ok else '有问题'}")
print("A 结论:", "全部成立" if okA else "有问题")
assert okA

E4 = ["N", "E", "S", "W"]
OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}
CFG = []
for i in E4:
    for o in E4:
        if o != i:
            CFG.append(("传送带", [({i}, {o})]))
for i in E4:
    CFG.append(("分流器", [({i}, set(E4) - {i})]))
    CFG.append(("汇流器", [(set(E4) - {i}, {i})]))
    CFG.append(("物品准入口", [({i}, {OPP[i]})]))
CFG.append(("桥接器", [({e}, {OPP[e]}) for e in E4]))

print("\n=== B. 同一条边上既有存货端口又有取货端口的单位 ===")
both = set()
for nm, cells in CFG:
    ins = set().union(*[c[0] for c in cells]); outs = set().union(*[c[1] for c in cells])
    if ins & outs:
        both.add(nm)
print("运输单位中只有：", both, "（非运输单位每条边只有一种端口或没有端口）")
assert both == {"桥接器"}
br = [c for nm, c in CFG if nm == "桥接器"][0]
assert [c for c in br if "W" in c[0]][0][1] == {"E"} and [c for c in br if "W" in c[1]][0][0] == {"E"}
print("桥接器西边进的货只能从东边出、西边出的货只能从东边进：一行双向正流量逐格东传到第 69 列出界，矛盾")

BLOBS = [("非运输", w, e) for w in ("in", "out", None) for e in ("in", "out", None)]
TYPES = CFG + BLOBS


def row_lp(seq, east_open=False):
    var = {}
    def v(key):
        if key not in var:
            var[key] = len(var)
        return var[key]
    A_eq, b_eq, A_ub, b_ub = [], [], [], []
    port_in, port_out = {}, {}
    for j, t in enumerate(seq):
        if t[0] == "非运输":
            _, w, e = t
            for edge, typ in (("W", w), ("E", e)):
                if typ == "in":
                    port_in.setdefault((j, edge), []).append(v(("blob", j, edge)))
                elif typ == "out":
                    port_out.setdefault((j, edge), []).append(v(("blob", j, edge)))
            continue
        for k, (ins, outs) in enumerate(t[1]):
            iv = [v(("in", j, k, e)) for e in sorted(ins)]
            ov = [v(("out", j, k, e)) for e in sorted(outs)]
            for e, x in zip(sorted(ins), iv):
                port_in.setdefault((j, e), []).append(x)
            for e, x in zip(sorted(outs), ov):
                port_out.setdefault((j, e), []).append(x)
            row = {x: 1 for x in iv}
            for x in ov:
                row[x] = row.get(x, 0) - 1
            A_eq.append(row); b_eq.append(0)               # 物品格守恒（周期平均）
            A_ub.append({x: 1 for x in iv}); b_ub.append(1)  # 上限 1、滞留 ≥1 tick
    n = len(seq)
    for d in (port_in, port_out):
        for xs in d.values():
            A_ub.append({x: 1 for x in xs}); b_ub.append(1)  # 端口速率
    for j in range(n - 1):
        for outs, ins in ((port_out.get((j, "E"), []), port_in.get((j + 1, "W"), [])),
                          (port_out.get((j + 1, "W"), []), port_in.get((j, "E"), []))):
            row = {x: 1 for x in outs}
            for x in ins:
                row[x] = row.get(x, 0) - 1
            A_eq.append(row); b_eq.append(0)
    if not east_open:  # 最后一格东边是基地边界
        for x in port_out.get((n - 1, "E"), []) + port_in.get((n - 1, "E"), []):
            A_eq.append({x: 1}); b_eq.append(0)
    east = port_in.get((0, "W"), []); west = port_out.get((0, "W"), [])
    tv = v(("t",)); N = len(var)
    def mat(rows):
        M = np.zeros((len(rows), N))
        for i, r in enumerate(rows):
            for x, c in r.items():
                M[i, x] += c
        return M
    Aeq = mat(A_eq) if A_eq else None
    beq = np.array(b_eq, dtype=float) if A_eq else None
    c1 = np.zeros(N)
    for x in east + west:
        c1[x] = -1
    r1 = linprog(c1, A_ub=mat(A_ub + [{tv: 1}]), b_ub=np.array(b_ub + [0], dtype=float),
                 A_eq=Aeq, b_eq=beq, bounds=[(0, None)] * N, method="highs")
    rr1 = {tv: 1}; rr2 = {tv: 1}
    for x in east: rr1[x] = rr1.get(x, 0) - 1
    for x in west: rr2[x] = rr2.get(x, 0) - 1
    c2 = np.zeros(N); c2[tv] = -1
    r2 = linprog(c2, A_ub=mat(A_ub + [rr1, rr2]), b_ub=np.array(b_ub + [0, 0], dtype=float),
                 A_eq=Aeq, b_eq=beq, bounds=[(0, None)] * N, method="highs")
    assert r1.status == 0 and r2.status == 0
    return -r1.fun, -r2.fun


print("\n=== C. 切线一行（R 侧到右边界，竖向邻格与切线西侧均放宽为自由源汇）LP ===")
for n in (1, 2, 3):
    ws, wm, cnt = 0.0, 0.0, 0
    for seq in itertools.product(TYPES, repeat=n):
        s, m = row_lp(seq)
        cnt += 1
        ws = max(ws, s); wm = max(wm, m)
    print(f"n={n}: 枚举 {cnt} 种，max(东+西)={ws:.6f}，max min(东,西)={wm:.6f}")
    assert ws <= 1 + 1e-9 and wm <= 1e-9
bridge = [t for t in TYPES if t[0] == "桥接器"][0]
s, m = row_lp((bridge, bridge), east_open=True)
print(f"对照（东端不封、两座桥接器串着）：max(东+西)={s:.3f}，max min={m:.3f} —— 贴右边界是双向合计 ≤1 的必要前提")
assert s > 1.5 and m > 0.5

print("\n=== D. 整数推论穷举 ===")
TYPES_HK = [(3, 1), (4, 2), (6, 2), (3, 0), (5, 0), (4, 0), (6, 0), (9, 0), (2, 0), (3, 3)]
bad = checked = 0
for H in range(1, 16):
    for N in range(0, 4):
        Gs = [Fr(k, 4) for k in range(0, 4 * N + 1)]
        for L in range(0, 4):
            for combo in itertools.combinations_with_replacement(TYPES_HK, L):
                if sum(h for h, _ in combo) > H:
                    continue
                D = sum(h - k for h, k in combo)
                U = sum(1 for hk in combo if hk != (3, 3))
                for m in range(0, H + 2 * N + 2):
                    for G in Gs:
                        if m <= H + 2 * G - D:
                            checked += 1
                            if not (D <= H - m + 2 * N and U <= N + (H - m) // 2):
                                bad += 1
print(f"核对 {checked} 组满足主式的 (H,N,G,m,跨线组合)，推论不成立 {bad} 组")
assert bad == 0
print("\n全部检查通过")
