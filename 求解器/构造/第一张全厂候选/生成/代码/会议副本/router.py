#!/usr/bin/env python3
"""
router.py —— P2P 类的启发式布线器（拥塞协商式，PathFinder 一类），机器摆放固定。
不用 CP-SAT，不作任何证明；输出和 p2p.py 同格式的 layout，交两份检查器判。

一格的合法占用：一条路径（任意进出边 → 传送带）；或两条路径一横一竖都直穿（→ 桥，P1/P4）。
P5（两座桥不相邻）用罚分逼，最后由检查器判。
路径端点：机器取货边外侧一格（从机器那边进）→ 机器存货边外侧一格（出到机器）；边界来料/出料从窗口外进出。
源和汇先按曼哈顿距离做一次最小费用指派（L 侧固定接法，是限制，不是必要条件）。
"""
import json, heapq, time, random, argparse
from collections import defaultdict
import numpy as np
from scipy.optimize import linear_sum_assignment
import p2p

DX = p2p.DX
OPP = p2p.OPP


def machines_from_tiles(tile_json, k, W, tx, ty):
    base = json.load(open(tile_json))["layout"]["machines"]
    out = []
    nx = W // tx
    for i in range(k):
        ox, oy = (i % nx) * tx, (i // nx) * ty
        for mc in base:
            m = dict(mc)
            m["x0"] += ox; m["x1"] += ox; m["y0"] += oy; m["y1"] += oy
            out.append(m)
    return out


def side_cells(mc, d):
    x0, y0, x1, y1 = mc["x0"], mc["y0"], mc["x1"], mc["y1"]
    if d == 0: return [(x1, y) for y in range(y0, y1 + 1)]
    if d == 2: return [(x0, y) for y in range(y0, y1 + 1)]
    if d == 1: return [(x, y1) for x in range(x0, x1 + 1)]
    return [(x, y0) for x in range(x0, x1 + 1)]


def route(spec, machines, W, H, allsides=True, iters=60, seed=0, verbose=False):
    rng = random.Random(seed)
    inside = lambda c: 0 <= c[0] < W and 0 <= c[1] < H
    nb = lambda c, d: (c[0] + DX[d][0], c[1] + DX[d][1])
    occm = set()
    for mc in machines:
        for x in range(mc["x0"], mc["x1"] + 1):
            for y in range(mc["y0"], mc["y1"] + 1):
                occm.add((x, y))
    free = lambda c: inside(c) and c not in occm
    roles = {r["name"]: r for r in spec["roles"]}
    # 终端
    src, snk = defaultdict(list), defaultdict(list)   # label -> [(starts, center)]
    for i, mc in enumerate(machines):
        r = roles[mc["role"]]
        Din, Dout = mc["Din"], OPP(mc["Din"])
        cen = ((mc["x0"] + mc["x1"]) / 2, (mc["y0"] + mc["y1"]) / 2)
        starts = [(nb(q, Dout), Dout) for q in side_cells(mc, Dout) if free(nb(q, Dout))]
        goals = [(nb(q, Din), OPP(Din)) for q in side_cells(mc, Din) if free(nb(q, Din))]
        for _ in range(r["n_out"]):
            src[r["out"][0]].append((("M", i), starts, cen))
        for l, kcnt in r["in_count"].items():
            for _ in range(kcnt):
                snk[l].append((("M", i), goals, cen))
    bstarts, bgoals = [], []
    for x in range(W):
        for y in range(H):
            c = (x, y)
            if not free(c):
                continue
            for d in range(4):
                if not inside(nb(c, d)):
                    bgoals.append((c, d))
                    bstarts.append((c, OPP(d)))
    for (l, sides, kcnt) in spec["supply"]:
        for _ in range(kcnt):
            src[l].append((("V", l), [s for s in bstarts if OPP(s[1]) in sides], None))
    for (l, sides, kcnt) in spec["demand"]:
        for _ in range(kcnt):
            snk[l].append((("VO", l), [g for g in bgoals if g[1] in sides], None))

    def dist_to_boundary(p):
        return min(p[0], p[1], W - 1 - p[0], H - 1 - p[1])
    nets = []
    for l in src:
        S, T = src[l], snk[l]
        assert len(S) == len(T), (l, len(S), len(T))
        C = np.zeros((len(S), len(T)))
        for i, s in enumerate(S):
            for j, t in enumerate(T):
                if s[2] is None and t[2] is None:
                    C[i, j] = 0
                elif s[2] is None:
                    C[i, j] = dist_to_boundary(t[2])
                elif t[2] is None:
                    C[i, j] = dist_to_boundary(s[2])
                else:
                    C[i, j] = abs(s[2][0] - t[2][0]) + abs(s[2][1] - t[2][1])
                if s[0] == t[0]:
                    C[i, j] = 1e6
        ri, ci = linear_sum_assignment(C)
        for i, j in zip(ri, ci):
            nets.append(dict(label=l, starts=S[i][1], goals=T[j][1], src=S[i][0], dst=T[j][0]))

    # 占用：cell -> {net: usage}；usage 'H' 'V' 直穿，'X' 转弯或端点
    occ = defaultdict(dict)
    hist = defaultdict(float)
    paths = {}

    def usage(din, dout):
        if din == dout:
            return "H" if din % 2 == 0 else "V"
        return "X"

    def cell_cost(c, u, ni, pres):
        others = [(n2, u2) for n2, u2 in occ[c].items() if n2[0] != ni]
        if not others:
            return 1.0 + hist[c]
        if len(others) == 1 and {u, others[0][1]} == {"H", "V"}:
            # 成桥：看四邻有没有别的桥（P5）
            pen = 0.3
            for d in range(4):
                n = nb(c, d)
                o = occ.get(n)
                if o and len(o) >= 2:
                    pen += 2.0 * pres
            return 1.0 + hist[c] + pen
        return 1.0 + hist[c] + pres * (len(others) + 1)

    def astar(ni, net, pres):
        goals = {}
        for (c, dout) in net["goals"]:
            goals.setdefault(c, []).append(dout)
        gl = list(goals)
        def h(c):
            return min(abs(c[0] - g[0]) + abs(c[1] - g[1]) for g in gl) if len(gl) < 40 else 0
        pq, best, prev = [], {}, {}
        import itertools
        tie = itertools.count()
        for (c, din) in net["starts"]:
            st = (c, din)
            best[st] = 0.0
            heapq.heappush(pq, (h(c), 0.0, next(tie), st))
        # 对边界这种大终端集，退化成 Dijkstra
        while pq:
            f, g, _, st = heapq.heappop(pq)
            if st[0] == "GOAL":
                _, c, din, dout, pst = st
                path = [(c, din, dout)]
                s2 = pst
                while s2 in prev:
                    s1, d_out = prev[s2]
                    path.append((s1[0], s1[1], d_out))
                    s2 = s1
                path.reverse()
                return g, path
            if g > best.get(st, 1e18) + 1e-9:
                continue
            c, din = st
            if c in goals:
                for dout in goals[c]:
                    if dout != OPP(din):
                        cost = g + cell_cost(c, usage(din, dout), ni, pres)
                        heapq.heappush(pq, (cost, cost, next(tie), ("GOAL", c, din, dout, st)))
            for d in range(4):
                if d == OPP(din):
                    continue
                n = nb(c, d)
                if not free(n):
                    continue
                ng = g + cell_cost(c, usage(din, d), ni, pres)
                ns = (n, d)
                if ng < best.get(ns, 1e18) - 1e-9:
                    best[ns] = ng
                    prev[ns] = (st, d)
                    heapq.heappush(pq, (ng + h(n), ng, next(tie), ns))
        return None, None

    def rip(ni):
        for j, (c, din, dout) in enumerate(paths.get(ni, [])):
            occ[c].pop((ni, j), None)

    def add(ni, path):
        paths[ni] = path
        for j, (c, din, dout) in enumerate(path):
            occ[c][(ni, j)] = usage(din, dout)

    def conflicts():
        bad = 0
        bridges = set()
        for c, o in occ.items():
            if len(o) == 0:
                continue
            if len(o) == 1:
                continue
            us = sorted(o.values())
            if len(o) == 2 and us == ["H", "V"]:
                bridges.add(c)
                continue
            bad += len(o) - 1
        p5 = 0
        for c in bridges:
            for d in (0, 1):
                if nb(c, d) in bridges:
                    p5 += 1
        return bad, p5, bridges

    t0 = time.time()
    pres = 0.5
    order = list(range(len(nets)))
    hist_log = []
    for it in range(iters):
        rng.shuffle(order)
        for ni in order:
            rip(ni)
            cost, path = astar(ni, nets[ni], pres)
            if path is None:
                return dict(status="NO_PATH", net=nets[ni]["label"], it=it, wall=round(time.time() - t0, 1))
            add(ni, path)
        bad, p5, bridges = conflicts()
        hist_log.append((it, bad, p5, round(time.time() - t0, 1)))
        if verbose:
            print(it, bad, p5, round(time.time() - t0, 1), flush=True)
        if bad == 0 and p5 == 0:
            break
        for c, o in occ.items():
            if len(o) >= 2 and not (len(o) == 2 and sorted(o.values()) == ["H", "V"]):
                hist[c] += 0.5 * (len(o) - 1)
            if c in bridges:
                for d in (0, 1):
                    if nb(c, d) in bridges:
                        hist[c] += 0.5
        pres *= 1.4
    bad, p5, bridges = conflicts()
    dbg = []
    for c, o in occ.items():
        if len(o) >= 2 and not (len(o) == 2 and sorted(o.values()) == ["H", "V"]):
            dbg.append((c, [(nets[ni]["label"], str(nets[ni]["src"]), str(nets[ni]["dst"]), j, len(paths[ni]), u) for (ni, j), u in o.items()]))
    res_dbg = dbg[:10]
    res = dict(dbg=res_dbg, status="ROUTED" if bad == 0 and p5 == 0 else "CONGESTED", overuse=bad, p5=p5,
               iters=len(hist_log), wall=round(time.time() - t0, 1), nets=len(nets), log=hist_log[-10:])
    # 输出 layout
    lay = dict(W=W, H=H, machines=machines, transport=[], vin=[], vout=[])
    for c, o in occ.items():
        if not o:
            continue
        if len(o) == 1:
            (ni, j), = list(o)
            cc, din, dout = paths[ni][j]
            lay["transport"].append(dict(x=c[0], y=c[1], type="belt", in_side=OPP(din), out_side=dout))
        else:
            Hin = Vin = None
            for (ni, j) in o:
                cc, din, dout = paths[ni][j]
                if din % 2 == 0:
                    Hin = OPP(din)
                else:
                    Vin = OPP(din)
            lay["transport"].append(dict(x=c[0], y=c[1], type="bridge", H_in=Hin, V_in=Vin))
    for ni, net in enumerate(nets):
        pth = paths[ni]
        if net["src"][0] == "V":
            c, din, _ = pth[0]
            lay["vin"].append(dict(x=c[0], y=c[1], side=OPP(din), label=net["label"]))
        if net["dst"][0] == "VO":
            c, _, dout = pth[-1]
            lay["vout"].append(dict(x=c[0], y=c[1], side=dout, label=net["label"]))
    res["layout"] = lay
    res["T"] = len(lay["transport"])
    res["bridges"] = sum(1 for t in lay["transport"] if t["type"] == "bridge")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--W", type=int, default=64)
    ap.add_argument("--H", type=int, default=64)
    ap.add_argument("--tx", type=int, default=16)
    ap.add_argument("--ty", type=int, default=16)
    ap.add_argument("--tile", default="r_k1_12.json")
    ap.add_argument("--iters", type=int, default=60)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    spec = p2p.iron_brick(a.k, True)
    ms = machines_from_tiles(a.tile, a.k, a.W, a.tx, a.ty)
    r = route(spec, ms, a.W, a.H, iters=a.iters, verbose=True)
    r["k"] = a.k; r["allsides"] = True
    print(json.dumps({k: v for k, v in r.items() if k != "layout"}, ensure_ascii=False))
    if a.out:
        json.dump(r, open(a.out, "w"), ensure_ascii=False, indent=1)
