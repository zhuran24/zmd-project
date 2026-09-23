#!/usr/bin/env python3
"""
check_full.py —— seat-opus-4 的独立检查器（与 seat-opus-3/check.py 分开实现，用来对照）。

输入：候选 JSON（取其 "layout" 字段；没有就把整个文件当 layout），格式同 seat-opus-3：
  坐标 (x,y) 左下 (0,0)；方向 0=E 1=N 2=W 3=S，都指「从这格往外」的那条边。
  machines: [{role, kind(小/中/大), Din(存货边外法向), x0,y0,x1,y1}]，取货边是 Din 的对边。
  transport: belt{in_side,out_side} / bridge{H_in,V_in}（求解器声称的方向，只用来比对）
             / splitter{in_side} / merger{out_side} / gate{in_side, filter?, k5?, cum?}
  vin/vout: 边界虚拟来料/出料 {x,y,side,label}，当作窗口外一个只有一个端口的非运输单位。

只从「每格放了什么、朝哪」出发，按规则重算，不看求解器的弧变量：
  C1 占格：不重叠、不出界；大制造单位的端口边必须是长边。
  C2 结构通道（当且仅当）：u 朝 v 的边是取货端口、v 朝 u 的边是存货端口、至少一端是运输单位。
     桥每轴方向按两端邻格朝它的端口推（规则 桥接器：由先接上的一端所接单位决定）。
  N1 取货分级触发：非运输单位有 ≥2 条结构取货通道，且其中一条的运输端是汇流器。
     触发时按元件图逐个分叉取值 ξ 算各级阻尼（传送带按「沿通道相继」读连续，见 T4），报告是否对所有 ξ 严格同序。
  N2 存货分级触发：单位有 ≥2 条结构存货通道，且其中一条来自分流器（汇流器上即密集结点）。
  N3 准入口：设了累计上限的在承载路径上报错；设了放行种类的，上游无别的出路时要求能到达的只有那一种，
     上游是分流器或制造单位时要求每一种到达物品上游都另有接通出口。
  N4 桥：用到的轴两端邻格朝它的端口须一取一存；同型 ⇒ 方向随接通先后变；只一端 ⇒ 另一端没有通道。
  N5 空接：结构通道通向永远到不了存货端口的断头，或来自永远没有来料的运输格。
  种类：从来源（机器按角色的产物、vin 的标签）沿结构通道传播能到达的物品种类（分流器各支都到），
     机器收到不在本机型任何配方里的物品 ⇒ 错料（进存货格永不离开）；收到本机型别的配方原料 ⇒ 偏离设计的配方。
"""
import json, sys
from collections import defaultdict
from itertools import product

DX = [(1, 0), (0, 1), (-1, 0), (0, -1)]
OPP = lambda d: (d + 2) % 4
nb = lambda c, d: (c[0] + DX[d][0], c[1] + DX[d][1])

# 配方（据《明日方舟：终末地》游戏规则 配方一节）：机型 -> [(原料dict, 产物dict)]
RECIPES = {
    "粉碎": [({"源矿": 1}, {"源石粉末": 1}), ({"蓝铁块": 1}, {"蓝铁粉末": 1}),
           ({"荞花": 1}, {"荞花粉末": 2}), ({"砂叶": 1}, {"砂叶粉末": 3})],
    "精炼": [({"蓝铁矿": 1}, {"蓝铁块": 1}), ({"致密蓝铁粉末": 1}, {"钢块": 1}), ({"蓝铁粉末": 1}, {"蓝铁块": 1})],
    "研磨": [({"蓝铁粉末": 2, "砂叶粉末": 1}, {"致密蓝铁粉末": 1}), ({"源石粉末": 2, "砂叶粉末": 1}, {"致密源石粉末": 1}),
           ({"荞花粉末": 2, "砂叶粉末": 1}, {"细磨荞花粉末": 1})],
    "塑形": [({"钢块": 2}, {"钢质瓶": 1})],
    "配件": [({"钢块": 1}, {"钢制零件": 1})],
    "种植": [({"荞花种子": 1}, {"荞花": 1}), ({"砂叶种子": 1}, {"砂叶": 1})],
    "采种": [({"荞花": 1}, {"荞花种子": 2}), ({"砂叶": 1}, {"砂叶种子": 2})],
    "封装": [({"钢制零件": 10, "致密源石粉末": 15}, {"高容谷地电池": 1})],
    "灌装": [({"钢质瓶": 10, "细磨荞花粉末": 10}, {"精选荞愈胶囊": 1})],
}
KIND_OF = {"粉碎": "小", "精炼": "小", "配件": "小", "塑形": "小", "采种": "中", "种植": "中", "研磨": "大", "封装": "大", "灌装": "大"}


def role_recipes(role):
    """角色名「机型-X」：X 是某个配方原料或产物的前缀；没有 -X 就允许该机型全部配方。"""
    typ, _, x = role.partition("-")
    allr = RECIPES[typ]
    if not x:
        return typ, list(range(len(allr)))
    hit = [i for i, (a, b) in enumerate(allr) if any(k.startswith(x) for k in list(a) + list(b))]
    if len(hit) != 1:
        raise ValueError(f"角色 {role} 对不上唯一配方：{hit}")
    return typ, hit


def check(lay):
    W, H = lay["W"], lay["H"]
    errs, warns, info = [], [], []
    occ, port, units = {}, {}, {}   # port[(cell, side)] = ('in'|'out', unit_id)

    # ---- 非运输单位 ----
    for i, mc in enumerate(lay["machines"]):
        uid = ("M", i)
        typ, rec = role_recipes(mc["role"])
        units[uid] = dict(kind="M", typ=typ, rec=rec, name=f"{mc['role']}@({mc['x0']},{mc['y0']})")
        w, h = mc["x1"] - mc["x0"] + 1, mc["y1"] - mc["y0"] + 1
        need = {"小": (3, 3), "中": (5, 5), "大": (6, 4)}[KIND_OF[typ]]
        if sorted((w, h)) != sorted(need):
            errs.append(f"C1 {units[uid]['name']} 尺寸 {w}x{h} 与机型不符")
        Din = mc["Din"]
        if KIND_OF[typ] == "大":
            edge_len = h if Din in (0, 2) else w
            if edge_len != 6:
                errs.append(f"C1 {units[uid]['name']} 端口边不是长边")
        for x in range(mc["x0"], mc["x1"] + 1):
            for y in range(mc["y0"], mc["y1"] + 1):
                if not (0 <= x < W and 0 <= y < H):
                    errs.append(f"C1 出界 {units[uid]['name']}")
                if (x, y) in occ:
                    errs.append(f"C1 重叠 {(x, y)}")
                occ[(x, y)] = uid

        def edge(d, mc=mc):
            if d == 0: return [(mc["x1"], y) for y in range(mc["y0"], mc["y1"] + 1)]
            if d == 2: return [(mc["x0"], y) for y in range(mc["y0"], mc["y1"] + 1)]
            if d == 1: return [(x, mc["y1"]) for x in range(mc["x0"], mc["x1"] + 1)]
            return [(x, mc["y0"]) for x in range(mc["x0"], mc["x1"] + 1)]
        for q in edge(Din):
            port[(q, Din)] = ("in", uid)
        for q in edge(OPP(Din)):
            port[(q, OPP(Din))] = ("out", uid)
    for j, v in enumerate(lay.get("vin", [])):
        uid = ("VI", j)
        units[uid] = dict(kind="VI", label=v["label"], name=f"来料{v['label']}@({v['x']},{v['y']})")
        port[(nb((v["x"], v["y"]), v["side"]), OPP(v["side"]))] = ("out", uid)
    for j, v in enumerate(lay.get("vout", [])):
        uid = ("VO", j)
        units[uid] = dict(kind="VO", label=v["label"], name=f"出料{v['label']}@({v['x']},{v['y']})")
        port[(nb((v["x"], v["y"]), v["side"]), OPP(v["side"]))] = ("in", uid)

    # ---- 运输单位（桥先不定端口） ----
    tr = {}
    for t in lay["transport"]:
        c = (t["x"], t["y"])
        if not (0 <= c[0] < W and 0 <= c[1] < H):
            errs.append(f"C1 出界 {c}")
        if c in occ:
            errs.append(f"C1 重叠 {c}")
        uid = ("T", c)
        occ[c] = uid
        tr[c] = t
        ty = t["type"]
        units[uid] = dict(kind=ty, name=f"{ty}@{c}")
        if ty == "belt":
            if t["in_side"] == t["out_side"]:
                errs.append(f"C1 传送带 {c} 存取同一边")
            port[(c, t["in_side"])] = ("in", uid)
            port[(c, t["out_side"])] = ("out", uid)
        elif ty == "gate":
            port[(c, t["in_side"])] = ("in", uid)
            port[(c, OPP(t["in_side"]))] = ("out", uid)
        elif ty == "splitter":
            for d in range(4):
                port[(c, d)] = ("in", uid) if d == t["in_side"] else ("out", uid)
        elif ty == "merger":
            for d in range(4):
                port[(c, d)] = ("out", uid) if d == t["out_side"] else ("in", uid)
        elif ty != "bridge":
            errs.append(f"C1 未知运输单位 {ty}")

    # ---- 桥：按邻格定方向；邻格也是未定向的桥时迭代，仍定不下的报 ----
    bridges = [c for c, t in tr.items() if t["type"] == "bridge"]
    axis_dir = {}  # (c, axis) -> in_side 或 None（不用）
    pending = {(c, ax) for c in bridges for ax in (0, 1)}
    def facing_of(c, ax):
        ends = (0, 2) if ax == 0 else (1, 3)
        facing, waiting = {}, False
        for d in ends:
            n = nb(c, d)
            if n in tr and tr[n]["type"] == "bridge" and (n, ax) in pending:
                waiting = True
                continue
            p = port.get((n, OPP(d)))
            if p:
                facing[d] = p[0]
        return ends, facing, waiting
    progress = True
    while progress and pending:
        progress = False
        for (c, ax) in sorted(pending):
            ends, facing, waiting = facing_of(c, ax)
            if not facing and waiting:
                continue          # 只接着未定向的桥：等它先定
            pending.discard((c, ax))
            progress = True
            if not facing:
                axis_dir[(c, ax)] = None    # 两端都没有端口朝它：这条轴不用
                continue
            d, typ = sorted(facing.items())[0]
            ins = d if typ == "out" else OPP(d)   # 邻格取货端口朝它的那一端是桥的存货端
            axis_dir[(c, ax)] = ins
            uid = ("B", c, ax)
            units[uid] = dict(kind="bridge_axis", name=f"桥{c}轴{'横' if ax == 0 else '纵'}")
            port[(c, ins)] = ("in", uid)
            port[(c, OPP(ins))] = ("out", uid)
    # 定完以后逐轴核两端：同型 ⇒ 随接通先后变；只一端 ⇒ 另一端没有通道
    for (c, ax), ins in list(axis_dir.items()):
        if ins is None:
            continue
        ends = (0, 2) if ax == 0 else (1, 3)
        facing = {d: port[(nb(c, d), OPP(d))][0] for d in ends if (nb(c, d), OPP(d)) in port}
        if len(facing) == 2 and facing[ends[0]] == facing[ends[1]]:
            errs.append(f"N4 桥 {c} 轴{ax} 两端邻格都是{'取货' if facing[ends[0]] == 'out' else '存货'}端口朝它：方向随接通先后变")
        elif len(facing) == 1:
            warns.append(f"N4/N5 桥 {c} 轴{ax} 只 {list(facing)[0]} 端有端口朝它：另一端没有通道")
    for (c, ax) in pending:
        errs.append(f"N4 桥 {c} 轴{ax} 与相邻桥互相依赖，方向随接通先后变")
    # 桥串：两座桥在同一轴上相邻、且这对端口都定了型（按由外向内推定）。按规则 接通 的时刻定义，两桥之间的通道
    # 在较晚那座桥建成时就算接通，早于两头的传送带，此时两端端口都还没定型；规则没写这时怎么定（seat-opus-3 指出）。
    for c in bridges:
        for d in (0, 1):
            n = nb(c, d)
            if n in tr and tr[n]["type"] == "bridge":
                ax = 0 if d == 0 else 1
                if axis_dir.get((c, ax)) is not None and axis_dir.get((n, ax)) is not None:
                    errs.append(f"N4 桥串 {c}-{n} 轴{ax}：两桥相接时端口都未定型，规则未写怎么定（L 侧限制：相邻桥不在同一轴上共用端口）")
    for c in bridges:
        for ax in (0, 1):
            claim = tr[c].get("H_in" if ax == 0 else "V_in")
            got = axis_dir.get((c, ax))
            if claim != got:
                errs.append(f"C2 桥 {c} 轴{ax} 声称方向 {claim}，按邻格重算为 {got}")

    # ---- 结构通道 ----
    is_nt = lambda u: u[0] in ("M", "VI", "VO")
    ch = []
    for (c, d), (typ, own) in port.items():
        if typ != "out":
            continue
        p = port.get((nb(c, d), OPP(d)))
        if p and p[0] == "in" and not (is_nt(own) and is_nt(p[1])):
            ch.append((own, p[1]))
    outs, ins = defaultdict(list), defaultdict(list)
    for a, b in ch:
        outs[a].append(b)
        ins[b].append(a)
    slot_ids = [u for u in units if u[0] in ("T", "B")]
    for s in slot_ids:
        k = units[s]["kind"]
        if k in ("belt", "gate", "bridge_axis") and (len(ins[s]) > 1 or len(outs[s]) > 1):
            errs.append(f"C2 {units[s]['name']} 通道数异常 进{len(ins[s])} 出{len(outs[s])}")

    # ---- N1 / N2 ----
    for u in units:
        if u[0] == "M" and len(outs[u]) >= 2 and any(units[b]["kind"] == "merger" for b in outs[u]):
            errs.append(f"N1 {units[u]['name']} 有 {len(outs[u])} 条取货通道且直连汇流器：取货分级触发")
            info.append(damping_report(u, outs, units))
    for u in units:
        if len(ins[u]) >= 2 and any(units[a]["kind"] == "splitter" for a in ins[u]):
            tag = "（密集结点）" if units[u]["kind"] == "merger" else ""
            errs.append(f"N2 {units[u]['name']} 有 {len(ins[u])} 条存货通道且有一条来自分流器：存货分级触发{tag}")

    # ---- 前向可达（有来料）、后向可达（能到存货端口） ----
    def reach(start, nxt):
        seen, st = set(start), list(start)
        while st:
            x = st.pop()
            for y in nxt[x]:
                if y not in seen and not is_nt(y):
                    seen.add(y)
                    st.append(y)
        return seen
    fwd = reach([b for a, b in ch if is_nt(a) and not is_nt(b)], outs)
    bwd = reach([a for a, b in ch if is_nt(b) and not is_nt(a)], ins)
    for a, b in ch:
        if not is_nt(b) and b not in bwd:
            errs.append(f"N5 {units[a]['name']}→{units[b]['name']}：通向永远到不了存货端口的断头（装满即堵）")
        if not is_nt(a) and a not in fwd:
            warns.append(f"N5 {units[a]['name']}→{units[b]['name']}：来自永远没有来料的运输格（空通道）")

    # ---- 种类传播（不动点） ----
    arrive = defaultdict(set)   # 单位 -> 能到达它的物品种类
    emit = defaultdict(set)
    for u, d in units.items():
        if d["kind"] == "VI":
            emit[u] = {d["label"]}
    changed = True
    while changed:
        changed = False
        for u, d in units.items():
            if d["kind"] == "M":
                allr = RECIPES[d["typ"]]
                prod = set()
                for i, (a, b) in enumerate(allr):
                    if i in d["rec"] or set(a) <= arrive[u]:
                        prod |= set(b)
                new = prod
            elif d["kind"] in ("VI",):
                new = emit[u]
            elif d["kind"] == "VO":
                new = set()
            else:
                new = set(arrive[u])
                if d["kind"] == "gate" and tr[u[1]].get("filter"):
                    new &= {tr[u[1]]["filter"]}
            if new != emit[u]:
                emit[u] = new
                changed = True
            for b in outs[u]:
                if not emit[u] <= arrive[b]:
                    arrive[b] |= emit[u]
                    changed = True
    for u, d in units.items():
        if d["kind"] == "M":
            allr = RECIPES[d["typ"]]
            ok_all = set().union(*[set(a) for a, b in allr])
            ok_role = set().union(*[set(allr[i][0]) for i in d["rec"]])
            bad = arrive[u] - ok_all
            off = (arrive[u] & ok_all) - ok_role
            if bad:
                errs.append(f"种类 {d['name']} 会收到 {sorted(bad)}：不在本机型任何配方里，进存货格永不离开")
            if off:
                warns.append(f"种类 {d['name']} 会收到别的配方原料 {sorted(off)}：会做设计外的配方")
            miss = ok_role - arrive[u]
            if miss:
                errs.append(f"种类 {d['name']} 收不到设计配方原料 {sorted(miss)}")
        if d["kind"] == "VO" and arrive[u] - {d["label"]}:
            errs.append(f"种类 {d['name']} 会收到 {sorted(arrive[u] - {d['label']})}")

    # ---- N3 准入口 ----
    for c, t in tr.items():
        if t["type"] != "gate":
            continue
        uid = ("T", c)
        if t.get("cum") and uid in fwd and uid in bwd:
            errs.append(f"N3 准入口 {c} 在承载路径上却设了累计上限 {t['cum']}")
        f = t.get("filter")
        if not f:
            continue
        for a in ins[uid]:
            kinds = emit[a]
            if units[a]["kind"] in ("belt", "gate", "bridge_axis", "VI", "merger"):
                if kinds - {f}:
                    errs.append(f"N3 准入口 {c} 只放行 {f}，上游 {units[a]['name']} 没有别的出路却会来 {sorted(kinds - {f})}：永久堵死")
            else:
                for k in kinds - {f}:
                    alt = [b for b in outs[a] if b != uid and not (units[b]["kind"] == "gate" and tr[b[1]].get("filter") not in (None, k))]
                    if not alt:
                        errs.append(f"N3 准入口 {c} 挡住 {k}，上游 {units[a]['name']} 没有别的接通出口收它")

    return dict(structural_channels=len(ch),
                channels_excluding_virtual=sum(1 for a, b in ch if a[0] not in ("VI", "VO") and b[0] not in ("VI", "VO")),
                errors=errs, warnings=warns, info=info)


def damping_report(u, outs, units):
    """对触发 N1 的单位，逐个分叉取值 ξ 算每条取货通道的阻尼（元件数），按规则 取货优先级 分级比较。"""
    def paths(x, prev_kind):
        # 返回 [(选择元组, 从 x 起到下一个非运输单位的元件数)]
        k = units[x]["kind"]
        if x[0] in ("M", "VI", "VO"):
            return [((), 0)]
        add = 0 if (k == "belt" and prev_kind == "belt") else 1
        res = []
        nxts = outs[x]
        if not nxts:
            return [((("断头", x),), add)]
        if k == "splitter":
            for y in nxts:
                for ch_, dd in paths(y, k):
                    res.append((((x, y),) + ch_, add + dd))
        else:
            for ch_, dd in paths(nxts[0], k):
                res.append((ch_, add + dd))
        return res
    per = {}
    for b in outs[u]:
        per[b] = paths(b, None)
    levels = [[b] for b in outs[u] if units[b]["kind"] == "merger"]
    rest = [b for b in outs[u] if units[b]["kind"] != "merger"]
    if rest:
        levels.append(rest)
    # 枚举全部分叉取值：每个分流器一个取值
    splitters = sorted({s for b in per for chs, _ in per[b] for (s, y) in [c for c in chs if c[0] != "断头"]})
    choices = {s: sorted({y for b in per for chs, _ in per[b] for (s2, y) in [c for c in chs if c[0] != "断头"] if s2 == s}) for s in splitters}
    orders = set()
    for combo in product(*[choices[s] for s in splitters]) if splitters else [()]:
        xi = dict(zip(splitters, combo))
        def d_of(b):
            for chs, dd in per[b]:
                if all(xi.get(s) == y for (s, y) in [c for c in chs if c[0] != "断头"]):
                    return dd
            return None
        lv = [max(d_of(b) for b in L) for L in levels]
        orders.add(tuple(lv))
    strict = all(len(set(o)) == len(o) for o in orders) and len({tuple(sorted(range(len(o)), key=lambda i: o[i])) for o in orders}) == 1
    return f"阻尼 {units[u]['name']}：各级阻尼随 ξ 取值 {sorted(orders)}；对所有 ξ 严格同序={strict}"


if __name__ == "__main__":
    r = json.load(open(sys.argv[1]))
    lay = r.get("layout", r)
    print(json.dumps(check(lay), ensure_ascii=False, indent=1))
