#!/usr/bin/env python3
"""
p2p.py —— 抬 L 侧受限类「点对点」（P2P）的精确格模型，联合求 摆放＋布线。

受限类（每条都是限制，登记覆盖损失）：
  P1 运输单位只用传送带和桥接器（不用分流器、汇流器、准入口、储存箱）。
  P2 每条通道承载一种「标签」＝(物品, 每 20 tick 件数)；一条路径从一个取货端口到一个存货端口，标签不变。
  P3 形成的每条通道都在用（自动接通按「当且仅当」：凡两端口相对就是一条在用的弧）。
  P4 桥接器每条在用轴两端都是在用弧（seat-opus-4 N4 的加强版），不用的轴两端不许有朝它的端口。
  P5 两座桥不相邻（桥先于传送带建成，两座桥的未定端口相遇时规则没给端口类型）。
这些限制下，格状态由弧唯一确定：传送带的进边、出边就是它的进弧、出弧所在边。

变量：
  x[p]      机器摆放（按角色×朝向×锚点，不编号）
  belt[c], br[c]  运输单位
  A[c,d]    c→c+d 的在用弧
  LH[c,l], LV[c,l]  格 c 水平/竖直层的标签（传送带两层相同，桥两轴各自）
  边界虚拟弧：来料从指定边界进，出料从任意边界出。
"""
import sys, json, time, argparse
from ortools.sat.python import cp_model

DX = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # E N W S
OPP = lambda d: (d + 2) % 4
AX = lambda d: d % 2  # 0 水平 1 竖直

SHAPE = {"小": (3, 3), "中": (5, 5), "大": (6, 4)}


def footprints(kind, W, H):
    """枚举 (朝向 Din, 占格, 存货端口格列表, 取货端口格列表)。Din 是存货边的外法向。"""
    a, b = SHAPE[kind]
    out = []
    for Din in range(4):
        if kind == "大":
            # 长边(6)为端口边：Din 为 N/S 时宽 6 高 4；E/W 时宽 4 高 6
            w, h = (6, 4) if Din in (1, 3) else (4, 6)
        else:
            w, h = a, b
        for ax in range(W - w + 1):
            for ay in range(H - h + 1):
                cells = [(ax + i, ay + j) for i in range(w) for j in range(h)]
                def side(d):
                    if d == 0: return [(ax + w - 1, ay + j) for j in range(h)]
                    if d == 2: return [(ax, ay + j) for j in range(h)]
                    if d == 1: return [(ax + i, ay + h - 1) for i in range(w)]
                    return [(ax + i, ay) for i in range(w)]
                out.append((Din, cells, side(Din), side(OPP(Din))))
    return out


def build(spec, W, H, threads=6, tlimit=60, minimize=True, seed=0, hint=None, fixed=None, fixlay=None):
    """fixed: 机器摆放清单 [(role, Din, x0, y0)]，给了就只解布线。"""
    t0 = time.time()
    m = cp_model.CpModel()
    labels = spec["labels"]
    L = len(labels)
    lid = {l: i for i, l in enumerate(labels)}
    cells = [(x, y) for x in range(W) for y in range(H)]
    inside = lambda c: 0 <= c[0] < W and 0 <= c[1] < H
    nb = lambda c, d: (c[0] + DX[d][0], c[1] + DX[d][1])

    belt = {c: m.NewBoolVar("") for c in cells}
    br = {c: m.NewBoolVar("") for c in cells}
    T = {c: belt[c] + br[c] for c in cells}
    for c in cells:
        m.Add(belt[c] + br[c] <= 1)
    # P5 两座桥不相邻：规则只说桥的端口类型由「先接上的那一端所接的单位」定，
    # 桥在传送带之前建成，两座桥相遇时两端都未定，规则没给结果；L 侧不用这种接法。
    for c in cells:
        for d in (0, 1):
            n = nb(c, d)
            if inside(n):
                m.Add(br[c] + br[n] <= 1)

    if fixlay is not None:
        # 把一张给定布局的运输格钉进模型（只钉「哪格是传送带、哪格是桥」），用来核它在模型的可行集里
        tb = {(t["x"], t["y"]): t["type"] for t in fixlay["transport"]}
        for c in cells:
            m.Add(belt[c] == (1 if tb.get(c) == "belt" else 0))
            m.Add(br[c] == (1 if tb.get(c) == "bridge" else 0))
    # 摆放
    cover = {c: [] for c in cells}
    OUTP = {(c, d): [] for c in cells for d in range(4)}  # c 是某机取货端口格、朝 d
    INP = {(c, d): [] for c in cells for d in range(4)}   # c 是某机存货端口格、朝 d
    OUTL = {(c, d, l): [] for c in cells for d in range(4) for l in range(L)}
    INL = {(c, d, l): [] for c in cells for d in range(4) for l in range(L)}
    places = []
    for ri, role in enumerate(spec["roles"]):
        fps = footprints(role["kind"], W, H)
        vs = []
        for (Din, fc, pin, pout) in fps:
            v = m.NewBoolVar("")
            vs.append(v)
            places.append((ri, Din, fc, pin, pout, v))
            for c in fc:
                cover[c].append(v)
            Dout = OPP(Din)
            for q in pout:
                OUTP[(q, Dout)].append(v)
                for l in role["out"]:
                    OUTL[(q, Dout, lid[l])].append(v)
            for q in pin:
                INP[(q, Din)].append(v)
                for l in role["in"]:
                    INL[(q, Din, lid[l])].append(v)
        m.Add(sum(vs) == role["count"])
        if fixed is not None:
            want = {(f[1], f[2], f[3]) for f in fixed if f[0] == role["name"]}
            for (Din, fc, pin, pout), v in zip(fps, vs):
                key = (Din, min(c[0] for c in fc), min(c[1] for c in fc))
                m.Add(v == (1 if key in want else 0))
    for c in cells:
        m.Add(sum(cover[c]) + T[c] <= 1)

    # 弧
    A = {}
    for c in cells:
        for d in range(4):
            n = nb(c, d)
            if inside(n):
                A[(c, d)] = m.NewBoolVar("")
    # 边界虚拟弧：VI[(c,d,l)] 从 c 的 d 侧外面进入 c；VO[(c,d,l)] 从 c 出到 d 侧外面
    VI, VO = {}, {}
    for (l, sides, k) in spec["supply"]:
        vs = []
        for c in cells:
            for d in sides:
                if not inside(nb(c, d)):
                    v = m.NewBoolVar("")
                    VI[(c, d, lid[l])] = v
                    vs.append(v)
        m.Add(sum(vs) == k)
    for (l, sides, k) in spec["demand"]:
        vs = []
        for c in cells:
            for d in sides:
                if not inside(nb(c, d)):
                    v = m.NewBoolVar("")
                    VO[(c, d, lid[l])] = v
                    vs.append(v)
        m.Add(sum(vs) == k)
    # 虚拟弧只接运输格
    for (c, d, l), v in list(VI.items()) + list(VO.items()):
        m.Add(v <= T[c])

    # 预先建 虚拟弧索引
    VIc = {}
    for k, v in VI.items():
        VIc.setdefault((k[0], k[1]), []).append((k[2], v))
    VOc = {}
    for k, v in VO.items():
        VOc.setdefault((k[0], k[1]), []).append((k[2], v))

    def ain(c, d):
        n = nb(c, d)
        if inside(n):
            return [A[(n, OPP(d))]]
        return [v for (_, v) in VIc.get((c, d), [])]

    def aout(c, d):
        n = nb(c, d)
        if inside(n):
            return [A[(c, d)]]
        return [v for (_, v) in VOc.get((c, d), [])]

    for c in cells:
        for d in range(4):
            n = nb(c, d)
            if not inside(n):
                continue
            a = A[(c, d)]
            # 至少一端是运输格；非运输端必须是对应端口
            m.Add(a <= T[c] + T[n])
            m.Add(a <= T[c] + sum(OUTP[(c, d)]))
            m.Add(a <= T[n] + sum(INP[(n, OPP(d))]))
            # 同一对格之间不能双向
            if d < 2:
                m.Add(a + A[(n, OPP(d))] <= 1)

    LH = {(c, l): m.NewBoolVar("") for c in cells for l in range(L)}
    LV = {(c, l): m.NewBoolVar("") for c in cells for l in range(L)}
    LA = lambda c, d, l: LH[(c, l)] if AX(d) == 0 else LV[(c, l)]

    for c in cells:
        inH = sum(ain(c, 0) + ain(c, 2))
        inV = sum(ain(c, 1) + ain(c, 3))
        outH = sum(aout(c, 0) + aout(c, 2))
        outV = sum(aout(c, 1) + aout(c, 3))
        # 传送带：进 1 出 1
        m.Add(inH + inV == 1).OnlyEnforceIf(belt[c])
        m.Add(outH + outV == 1).OnlyEnforceIf(belt[c])
        # 桥：每轴直通
        for d in range(4):
            m.Add(sum(ain(c, d)) == sum(aout(c, OPP(d)))).OnlyEnforceIf(br[c])
        m.Add(inH <= 1).OnlyEnforceIf(br[c])
        m.Add(inV <= 1).OnlyEnforceIf(br[c])
        # 标签层
        sH = sum(LH[(c, l)] for l in range(L))
        sV = sum(LV[(c, l)] for l in range(L))
        m.Add(sH == 1).OnlyEnforceIf(belt[c])
        m.Add(sV == 1).OnlyEnforceIf(belt[c])
        for l in range(L):
            m.Add(LH[(c, l)] == LV[(c, l)]).OnlyEnforceIf(belt[c])
        m.Add(sH == inH).OnlyEnforceIf(br[c])
        m.Add(sV == inV).OnlyEnforceIf(br[c])
        m.Add(sH + sV <= 2 * T[c])
        # 桥：不用的轴两端不许有朝它的端口（P4）；用的轴两端都是在用弧已由直通保证
        # 端口朝它：邻格是机器端口朝 c，或邻格是传送带且其进/出边朝 c（即有在用弧），
        # 后者已被「弧」覆盖；这里只禁机器端口挨着桥的不用轴。
        for d in range(4):
            n = nb(c, d)
            if inside(n):
                mp = sum(OUTP[(n, OPP(d))]) + sum(INP[(n, OPP(d))])
                used_axis = inH if AX(d) == 0 else inV
                m.Add(mp <= used_axis).OnlyEnforceIf(br[c])
        # P3 当且仅当：机器端口正对传送带时，只有传送带的进/出边朝它才成通道；
        # 传送带的进出边由弧定，所以若机器取货端口正对传送带而弧不在，传送带的进边就不朝它：无通道，合法。
        # 若机器端口正对桥的在用轴，则那一端必须是在用弧：
        for d in range(4):
            n = nb(c, d)
            if inside(n):
                used_axis = inH if AX(d) == 0 else inV
                # n 是取货端口朝 c：弧 n->c 必须在用（当 c 是桥且该轴在用）
                if OUTP[(n, OPP(d))]:
                    m.Add(sum(OUTP[(n, OPP(d))]) + br[c] + used_axis - 2 <= A[(n, OPP(d))])
                if INP[(n, OPP(d))]:
                    m.Add(sum(INP[(n, OPP(d))]) + br[c] + used_axis - 2 <= A[(c, d)])

    # 标签沿弧一致；机器端口处标签合规
    for c in cells:
        for d in range(4):
            n = nb(c, d)
            if not inside(n):
                continue
            a = A[(c, d)]
            for l in range(L):
                la, lb = LA(c, d, l), LA(n, d, l)
                m.Add(la - lb <= (1 - a) + (1 - T[n]))
                m.Add(lb - la <= (1 - a) + (1 - T[c]))
                # c 是机器取货端口：n 的标签须是该机产物之一
                m.Add(lb <= sum(OUTL[(c, d, l)]) + (1 - a) + T[c])
                # n 是机器存货端口：c 的标签须是该机原料之一
                m.Add(la <= sum(INL[(n, OPP(d), l)]) + (1 - a) + T[n])
    for (c, d, l), v in VI.items():
        m.Add(LA(c, d, l) >= v)
    for (c, d, l), v in VO.items():
        m.Add(LA(c, d, l) >= v)

    # 逐台通道数，以及多原料机器逐标签条数
    cnt_labels = set()
    for role in spec["roles"]:
        if len(role["in_count"]) > 1:
            cnt_labels |= set(lid[l] for l in role["in_count"])
    AL = {}
    for (c, d), a in A.items():
        n = nb(c, d)
        for l in cnt_labels:
            v = m.NewBoolVar("")
            la = LA(c, d, l)
            m.AddBoolAnd([a, la]).OnlyEnforceIf(v)
            m.AddBoolOr([a.Not(), la.Not()]).OnlyEnforceIf(v.Not())
            AL[(c, d, l)] = v
    for (ri, Din, fc, pin, pout, v) in places:
        role = spec["roles"][ri]
        Dout = OPP(Din)
        outs = [A[(q, Dout)] for q in pout if inside(nb(q, Dout))]
        ins = [A[(nb(q, Din), OPP(Din))] for q in pin if inside(nb(q, Din))]
        n_out = role["n_out"]
        n_in = sum(role["in_count"].values())
        if len(outs) < n_out or len(ins) < n_in:
            m.Add(v == 0)
            continue
        m.Add(sum(outs) == n_out).OnlyEnforceIf(v)
        m.Add(sum(ins) == n_in).OnlyEnforceIf(v)
        if len(role["in_count"]) > 1:
            for l, k in role["in_count"].items():
                m.Add(sum(AL[(nb(q, Din), OPP(Din), lid[l])] for q in pin
                          if inside(nb(q, Din))) == k).OnlyEnforceIf(v)

    nT = sum(T[c] for c in cells)
    if minimize:
        m.Minimize(nT)
    if spec.get("place_first"):
        m.AddDecisionStrategy([p[5] for p in places], cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE)
    build_s = time.time() - t0
    s = cp_model.CpSolver()
    s.parameters.num_workers = threads
    s.parameters.max_time_in_seconds = tlimit
    s.parameters.random_seed = seed
    t1 = time.time()

    class CB(cp_model.CpSolverSolutionCallback):
        def __init__(self):
            super().__init__(); self.first = None; self.trace = []
        def on_solution_callback(self):
            t = time.time() - t1
            if self.first is None:
                self.first = t
            self.trace.append((round(t, 1), self.ObjectiveValue() if minimize else 0))
    cb = CB()
    st = s.Solve(m, cb)
    wall = time.time() - t1
    res = dict(W=W, H=H, status=s.StatusName(st), wall=round(wall, 1), build_s=round(build_s, 1),
               nvars=len(m.Proto().variables), ncons=len(m.Proto().constraints),
               first_sol=None if cb.first is None else round(cb.first, 1), trace=cb.trace[-8:])
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res["T"] = int(s.ObjectiveValue()) if minimize else sum(s.Value(T[c]) for c in cells)
        res["bound"] = s.BestObjectiveBound() if minimize else None
        res["bridges"] = sum(s.Value(br[c]) for c in cells)
        # 画图
        g = [["." for _ in range(W)] for _ in range(H)]
        sym = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for (ri, Din, fc, pin, pout, v) in places:
            if s.Value(v):
                for (x, y) in fc:
                    g[y][x] = sym[ri].lower()
                for (x, y) in pin:
                    g[y][x] = sym[ri]
        arrow = {0: ">", 1: "^", 2: "<", 3: "v"}
        for c in cells:
            if s.Value(br[c]):
                g[c[1]][c[0]] = "#"
            elif s.Value(belt[c]):
                ds = [d for d in range(4) if any(s.Value(z) for z in aout(c, d))]
                g[c[1]][c[0]] = arrow[ds[0]] if ds else "?"
        res["grid"] = ["".join(r) for r in reversed(g)]
        res["roles"] = {sym[i]: r["name"] for i, r in enumerate(spec["roles"])}
        # 解的结构化输出（供独立检查器 check.py 用）
        lay = dict(W=W, H=H, machines=[], transport=[], vin=[], vout=[])
        for (ri, Din, fc, pin, pout, v) in places:
            if s.Value(v):
                xs = [c[0] for c in fc]; ys = [c[1] for c in fc]
                lay["machines"].append(dict(role=spec["roles"][ri]["name"], kind=spec["roles"][ri]["kind"],
                                            Din=Din, x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys)))
        for c in cells:
            if s.Value(belt[c]):
                ins = [d for d in range(4) if any(s.Value(z) for z in ain(c, d))]
                outs = [d for d in range(4) if any(s.Value(z) for z in aout(c, d))]
                lay["transport"].append(dict(x=c[0], y=c[1], type="belt", in_side=ins[0], out_side=outs[0]))
            elif s.Value(br[c]):
                axes = {}
                for axn, (d1, d2) in (("H", (0, 2)), ("V", (1, 3))):
                    ins = [d for d in (d1, d2) if any(s.Value(z) for z in ain(c, d))]
                    axes[axn] = ins[0] if ins else None
                lay["transport"].append(dict(x=c[0], y=c[1], type="bridge", H_in=axes["H"], V_in=axes["V"]))
        for (c, d, l), v in VI.items():
            if s.Value(v):
                lay["vin"].append(dict(x=c[0], y=c[1], side=d, label=labels[l]))
        for (c, d, l), v in VO.items():
            if s.Value(v):
                lay["vout"].append(dict(x=c[0], y=c[1], side=d, label=labels[l]))
        res["layout"] = lay
    return res


def iron_brick(k, allsides=False):
    """k 份：2 精炼-蓝铁矿、2 粉碎-蓝铁块、1 研磨-致密蓝铁、1 精炼-致密蓝铁。全部满速(20)。"""
    labels = ["蓝铁矿", "蓝铁块", "蓝铁粉末", "砂叶粉末", "致密蓝铁粉末", "钢块"]
    roles = [
        dict(name="精炼-蓝铁矿", kind="小", count=2 * k, **{"in": ["蓝铁矿"]}, out=["蓝铁块"], in_count={"蓝铁矿": 1}, n_out=1),
        dict(name="粉碎-蓝铁块", kind="小", count=2 * k, **{"in": ["蓝铁块"]}, out=["蓝铁粉末"], in_count={"蓝铁块": 1}, n_out=1),
        dict(name="研磨-致密蓝铁", kind="大", count=k, **{"in": ["蓝铁粉末", "砂叶粉末"]}, out=["致密蓝铁粉末"],
             in_count={"蓝铁粉末": 2, "砂叶粉末": 1}, n_out=1),
        dict(name="精炼-致密蓝铁", kind="小", count=k, **{"in": ["致密蓝铁粉末"]}, out=["钢块"], in_count={"致密蓝铁粉末": 1}, n_out=1),
    ]
    # 来料：矿从西边进（像左边带），砂叶粉末从北/南进；钢块从东边出
    supply = [("蓝铁矿", [2], 2 * k), ("砂叶粉末", [1, 3], k)]
    demand = [("钢块", [0], k)]
    if allsides:
        supply = [("蓝铁矿", [0, 1, 2, 3], 2 * k), ("砂叶粉末", [0, 1, 2, 3], k)]
        demand = [("钢块", [0, 1, 2, 3], k)]
    return dict(labels=labels, roles=roles, supply=supply, demand=demand)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--W", type=int, default=12)
    ap.add_argument("--H", type=int, default=12)
    ap.add_argument("--t", type=float, default=60)
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--nomin", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--tile", default="", help="把一个 k=1 解的机器摆放平铺成 k 份后固定，只解布线")
    ap.add_argument("--tx", type=int, default=12)
    ap.add_argument("--ty", type=int, default=12)
    ap.add_argument("--allsides", action="store_true")
    ap.add_argument("--place_first", action="store_true")
    ap.add_argument("--fixlay", default="", help="把这份结果文件的运输格钉进模型")
    a = ap.parse_args()
    spec = iron_brick(a.k, a.allsides)
    spec["place_first"] = a.place_first
    fixed = None
    if a.tile:
        base = json.load(open(a.tile))["layout"]["machines"]
        fixed = []
        nx = a.W // a.tx
        for i in range(a.k):
            ox, oy = (i % nx) * a.tx, (i // nx) * a.ty
            fixed += [(mc["role"], mc["Din"], mc["x0"] + ox, mc["y0"] + oy) for mc in base]
    fl = json.load(open(a.fixlay))["layout"] if a.fixlay else None
    r = build(spec, a.W, a.H, threads=a.threads, tlimit=a.t, minimize=not a.nomin, fixed=fixed, fixlay=fl)
    r["k"] = a.k
    r["allsides"] = a.allsides
    print(json.dumps({k: v for k, v in r.items() if k not in ("grid", "layout")}, ensure_ascii=False))
    for row in r.get("grid", []):
        print(row)
    if a.out:
        json.dump(r, open(a.out, "w"), ensure_ascii=False, indent=1)
