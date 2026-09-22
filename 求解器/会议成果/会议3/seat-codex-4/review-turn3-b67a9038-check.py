#!/usr/bin/env python3
"""
check.py —— 独立检查器：只从「每格放了什么、朝哪」出发，按规则重算全部通道，不看求解器的弧变量。

查的东西（P2P 受限类）：
  C1 占格：不重叠、不出界。
  C2 通道按「当且仅当」重算：u 朝 v 的边是取货端口、v 朝 u 的边是存货端口、且至少一端是运输单位（规则 通道、端口对接）。
     桥接器：每条轴两端的邻格若有端口朝它，按端口类型定该轴方向；两端都朝它且同为取货或同为存货 ⇒ 方向随接通先后变（报错，seat-opus-4 N4）；
     只一端有端口朝它 ⇒ 这条通道形成但走不通（报错，seat-opus-4 N5）。
  C3 从每个源（机器取货端口通道、边界来料）沿通道走，每个运输物品格恰一进一出（桥每轴），走到一个存货端口为止；
     查物品：源的产物 = 汇收的原料；逐台查存货通道条数（按物品）与取货通道条数；无源的闭环报警。
"""
import json, sys
from collections import defaultdict, Counter

DX = [(1, 0), (0, 1), (-1, 0), (0, -1)]
OPP = lambda d: (d + 2) % 4


def check(lay, spec):
    W, H = lay["W"], lay["H"]
    errs, warns = [], []
    roles = {r["name"]: r for r in spec["roles"]}
    occ = {}
    port = {}  # (cell, side) -> ('in'|'out', owner)
    mach = []
    for i, mc in enumerate(lay["machines"]):
        cells = [(x, y) for x in range(mc["x0"], mc["x1"] + 1) for y in range(mc["y0"], mc["y1"] + 1)]
        for c in cells:
            if not (0 <= c[0] < W and 0 <= c[1] < H):
                errs.append(f"C1 出界 {mc}")
            if c in occ:
                errs.append(f"C1 重叠 {c}")
            occ[c] = ("M", i)
        Din, Dout = mc["Din"], OPP(mc["Din"])
        def side(d):
            x0, y0, x1, y1 = mc["x0"], mc["y0"], mc["x1"], mc["y1"]
            if d == 0: return [(x1, y) for y in range(y0, y1 + 1)]
            if d == 2: return [(x0, y) for y in range(y0, y1 + 1)]
            if d == 1: return [(x, y1) for x in range(x0, x1 + 1)]
            return [(x, y0) for x in range(x0, x1 + 1)]
        for q in side(Din):
            port[(q, Din)] = ("in", ("M", i))
        for q in side(Dout):
            port[(q, Dout)] = ("out", ("M", i))
        mach.append(mc)
    tr = {}
    for t in lay["transport"]:
        c = (t["x"], t["y"])
        if c in occ:
            errs.append(f"C1 重叠 {c}")
        occ[c] = ("T", c)
        tr[c] = t
        if t["type"] == "belt":
            port[(c, t["in_side"])] = ("in", ("T", c))
            port[(c, t["out_side"])] = ("out", ("T", c))
    nb = lambda c, d: (c[0] + DX[d][0], c[1] + DX[d][1])
    # 边界虚拟来料/出料当作窗口外的一个端口
    for v in lay["vin"]:
        port[(nb((v["x"], v["y"]), v["side"]), OPP(v["side"]))] = ("out", ("VI", v["label"]))
    for v in lay["vout"]:
        port[(nb((v["x"], v["y"]), v["side"]), OPP(v["side"]))] = ("in", ("VO", v["label"]))
    # 桥：按两端邻格端口定方向
    bridge_axis = {}  # (c, axis) -> in_side
    for c, t in tr.items():
        if t["type"] != "bridge":
            continue
        for axis, (d1, d2) in ((0, (0, 2)), (1, (1, 3))):
            facing = {}
            for d in (d1, d2):
                p = port.get((nb(c, d), OPP(d)))
                if p:
                    facing[d] = p[0]
            if len(facing) == 2:
                a, b = facing[d1], facing[d2]
                if a == b:
                    errs.append(f"C2 桥 {c} 轴{axis} 两端同为 {a}，方向随接通先后变")
                    continue
                ins = d1 if a == "out" else d2  # 邻格取货端口朝它的那端是桥的存货端
                bridge_axis[(c, axis)] = ins
            elif len(facing) == 1:
                d = list(facing)[0]
                errs.append(f"C2 桥 {c} 轴{axis} 只 {d} 端有端口朝它：通道形成但走不通")
            # 与求解器声称的方向比对
            claim = t["H_in"] if axis == 0 else t["V_in"]
            got = bridge_axis.get((c, axis))
            if claim != got:
                errs.append(f"C2 桥 {c} 轴{axis} 求解器方向 {claim} 与重算 {got} 不符")
    for (c, axis), ins in bridge_axis.items():
        port[(c, ins)] = ("in", ("B", c, axis))
        port[(c, OPP(ins))] = ("out", ("B", c, axis))
    # 通道
    ch = []
    for (c, d), (typ, own) in port.items():
        if typ != "out":
            continue
        n = nb(c, d)
        p = port.get((n, OPP(d)))
        if p and p[0] == "in" and (own[0] != "M" or p[1][0] != "M"):
            ch.append((own, p[1], c, d))
    # 边界来料/出料：已作为端口参与通道重算
    src = []
    sinks_v = {}
    # 运输物品格的进出
    inc, outc = defaultdict(list), defaultdict(list)
    for (a, b, c, d) in ch:
        outc[a].append(b)
        inc[b].append(a)
    for (lab, b) in src:
        if b:
            inc[b].append(("V", lab))
    for a, lab in sinks_v.items():
        outc[a].append(("VO", lab))
    slots = [("T", c) for c, t in tr.items() if t["type"] == "belt"] + [("B", c, ax) for (c, ax) in bridge_axis]
    for s_ in slots:
        if len(inc[s_]) != 1 or len(outc[s_]) != 1:
            errs.append(f"C3 运输物品格 {s_} 进 {len(inc[s_])} 出 {len(outc[s_])}")
    # 沿路径走
    got_in = defaultdict(Counter)
    got_out = Counter()
    starts = []
    for (a, b, c, d) in ch:
        if a[0] == "M":
            starts.append((a, b, roles[mach[a[1]]["role"]]["out"]))
        elif a[0] == "VI":
            starts.append((a, b, [a[1]]))
    seen = set()
    for (a, b, items) in starts:
        if a[0] == "M":
            got_out[a] += 1
        cur, steps = b, 0
        while cur and cur[0] in ("T", "B"):
            seen.add(cur)
            nxt = outc.get(cur, [])
            if len(nxt) != 1:
                break
            cur = nxt[0]
            steps += 1
            if steps > 10000:
                errs.append("C3 环"); break
        if cur and cur[0] == "M":
            need = roles[mach[cur[1]]["role"]]["in_count"]
            it = [i for i in items if i in need]
            if not it:
                errs.append(f"C3 {a} 的产物 {items} 送进 {mach[cur[1]]['role']}，不是它的原料")
            else:
                got_in[cur][it[0]] += 1
        elif cur and cur[0] == "VO":
            if cur[1] not in items:
                errs.append(f"C3 出料标签 {cur[1]} 与源产物 {items} 不符")
    for s_ in slots:
        if s_ not in seen:
            warns.append(f"C3 运输物品格 {s_} 不在任何源出发的路径上（无源环或断头）")
    for i, mc in enumerate(mach):
        r = roles[mc["role"]]
        if dict(got_in[("M", i)]) != r["in_count"]:
            errs.append(f"C3 {mc['role']}@({mc['x0']},{mc['y0']}) 存货通道 {dict(got_in[('M', i)])} ≠ {r['in_count']}")
        if got_out[("M", i)] != r["n_out"]:
            errs.append(f"C3 {mc['role']}@({mc['x0']},{mc['y0']}) 取货通道 {got_out[('M', i)]} ≠ {r['n_out']}")
    cnt = Counter(mc["role"] for mc in mach)
    for r in spec["roles"]:
        if cnt[r["name"]] != r["count"]:
            errs.append(f"C1 台数 {r['name']} {cnt[r['name']]} ≠ {r['count']}")
    return dict(channels=len(ch), errors=errs, warnings=warns)


if __name__ == "__main__":
    import p2p
    r = json.load(open(sys.argv[1]))
    spec = p2p.iron_brick(r["k"], r.get("allsides", False))
    print(json.dumps(check(r["layout"], spec), ensure_ascii=False, indent=1))
