# 复核80：十七位置、P=10、J=1、唯一占边桩在第 1 列/第 1 行、S≤186 的边段投影模型（独立重写）
# 只保留接触 X、Y 计数格的制造单位、协议核心，以及可能为它们供电的桩和唯一占边桩。
# 桩的在产台数上限用本目录 pos_cap.py 的局部放松逐位置重算（不读推导席的容量表）。
import json, sys, time, os
from multiprocessing import Pool
from ortools.sat.python import cp_model

R = (49, 69, 17, 69)


def inR(c):
    return R[0] <= c[0] <= R[1] and R[2] <= c[1] <= R[3]


def legal(c):
    return 1 <= c[0] <= 69 and 1 <= c[1] <= 69 and not inR(c)


XR = [(69, y) for y in range(1, 17)]
XT = [(x, 69) for x in range(1, 49)]
YL = [(48, y) for y in range(17, 70)]
YB = [(x, 16) for x in range(49, 70)]
LINES = [XR, XT, YL, YB]
MULT = {}
for L in LINES:
    for c in L:
        MULT[c] = MULT.get(c, 0) + 1
assert sum(MULT.values()) == 138 and len(MULT) == 136


def rect(x, y, w, h):
    return [(x + i, y + j) for i in range(w) for j in range(h)]


def machine_options():
    opts = []
    for kind, w, h, ax in [("s", 3, 3, "H"), ("s", 3, 3, "V"), ("m", 5, 5, "H"), ("m", 5, 5, "V"),
                           ("l", 6, 4, "V"), ("l", 4, 6, "H")]:
        anchors = {(cx - i, cy - j) for (cx, cy) in MULT for i in range(w) for j in range(h)}
        for (x, y) in sorted(anchors):
            body = rect(x, y, w, h)
            if not all(legal(c) for c in body):
                continue
            if ax == "H":
                sides = [[(x - 1, y + j) for j in range(h)], [(x + w, y + j) for j in range(h)]]
            else:
                sides = [[(x + i, y - 1) for i in range(w)], [(x + i, y + h) for i in range(w)]]
            sides = [[c for c in s if legal(c)] for s in sides]
            if any(not s for s in sides):
                continue
            if kind == "l" and all(len(s) < 2 for s in sides):
                continue
            opts.append(dict(kind=kind, x=x, y=y, w=w, h=h, ax=ax, body=body, sides=sides))
    return opts


def core_options():
    opts = []
    anchors = {(cx - i, cy - j) for (cx, cy) in MULT for i in range(9) for j in range(9)}
    for (x, y) in sorted(anchors):
        body = rect(x, y, 9, 9)
        if not all(legal(c) for c in body):
            continue
        if x < 2 or y < 2 or (x <= 3 and y <= 3):
            continue
        for pick in ("LR", "TB"):  # 取货边为左右两边或上下两边
            if pick == "LR":
                if x <= 3:
                    continue  # 核心离带：x0≤3 时朝左带的边须为存货边
                take = [(x - 1, y + k) for k in (1, 4, 7)] + [(x + 9, y + k) for k in (1, 4, 7)]
                put = [(x + k, y - 1) for k in range(1, 8)] + [(x + k, y + 9) for k in range(1, 8)]
            else:
                if y <= 3:
                    continue
                take = [(x + k, y - 1) for k in (1, 4, 7)] + [(x + k, y + 9) for k in (1, 4, 7)]
                put = [(x - 1, y + k) for k in range(1, 8)] + [(x + 9, y + k) for k in range(1, 8)]
            if not all(legal(c) for c in take):
                continue
            put = [c for c in put if legal(c)]
            if len(put) < 2:
                continue
            opts.append(dict(kind="c", x=x, y=y, w=9, h=9, pick=pick, body=body, take=take, put=put))
    return opts


def pole_range_hits(u, v, body):
    return any(u - 5 <= a <= u + 6 and v - 5 <= b <= v + 6 for (a, b) in body)


def interior(u, v):
    # 该桩全部可能的机身与端口邻格（锚点至多离范围 5 格、邻格再 1 格）都在合法区内时，局部放松与无边界模型相同
    for a in range(u - 11, u + 13):
        for b in range(v - 11, v + 13):
            if not legal((a, b)):
                return False
    return True


def cap_worker(p):
    from pos_cap import solve
    r = solve(p)
    return (p, r["max"], r["optimal"])


def pole_caps(positions, procs=8):
    todo = [p for p in positions if not interior(*p)]
    caps = {p: 23 for p in positions if interior(*p)}
    with Pool(procs) as pool:
        for p, m, ok in pool.map(cap_worker, todo, chunksize=4):
            assert ok, p
            caps[p] = min(23, m)
    return caps


def build(mach, cores, poles, caps, walls, s_cap=186, seconds=600, workers=8):
    m = cp_model.CpModel()
    units = mach + cores
    xu = [m.NewBoolVar(f"u{i}") for i in range(len(units))]
    yp = {p: m.NewBoolVar(f"p{p}") for p in poles}
    occ = {}
    for i, o in enumerate(units):
        for c in o["body"]:
            occ.setdefault(c, []).append(xu[i])
    for p in poles:
        for c in rect(p[0], p[1], 2, 2):
            occ.setdefault(c, []).append(yp[p])
    for c, lst in occ.items():
        if len(lst) > 1:
            m.AddAtMostOne(lst)

    def free_count(cells):
        return sum(1 - sum(occ.get(c, [])) if c in occ else 1 for c in cells)

    freev = {}

    def fv(c):
        if c not in freev:
            v = m.NewBoolVar("")
            m.Add(v + sum(occ[c]) == 1)
            freev[c] = v
        return freev[c]

    exc = []
    for i, o in enumerate(units):
        if o["kind"] == "c":
            for c in o["take"]:
                if c in occ:
                    m.Add(fv(c) == 1).OnlyEnforceIf(xu[i])
            fr = [fv(c) if c in occ else 1 for c in o["put"]]
            m.Add(sum(fr) >= 2).OnlyEnforceIf(xu[i])
            continue
        for s in o["sides"]:
            if any(c not in occ for c in s):
                continue
            m.AddBoolOr([fv(c) for c in s]).OnlyEnforceIf(xu[i])
        if o["kind"] == "l":
            d = m.NewBoolVar("")  # 存货边取第 0 侧或第 1 侧
            e = m.NewBoolVar("")  # 唯一允许少于 3 格的例外
            m.AddImplication(e, xu[i])
            exc.append(e)
            for k, s in enumerate(o["sides"]):
                fr = [fv(c) if c in occ else 1 for c in s]
                lit = d if k == 0 else d.Not()
                m.Add(sum(fr) >= 3).OnlyEnforceIf([xu[i], lit, e.Not()])
                m.Add(sum(fr) >= 2).OnlyEnforceIf([xu[i], lit])
    if exc:
        m.Add(sum(exc) <= 1)
    m.Add(sum(xu[i] for i, o in enumerate(units) if o["kind"] == "c") <= 1)
    m.Add(sum(yp.values()) <= 10)
    m.Add(sum(yp[p] for p in walls) == 1)
    # 供电覆盖与收费：各桩亏额 + 保留机器实际重复覆盖次数 ≤ 13
    rep = []
    for i, o in enumerate(mach):
        cov = [yp[p] for p in poles if pole_range_hits(p[0], p[1], o["body"])]
        if not cov:
            m.Add(xu[i] == 0)
            continue
        m.Add(sum(cov) >= 1).OnlyEnforceIf(xu[i])
        r = m.NewIntVar(0, 10, "")
        m.Add(r >= sum(cov) - 1).OnlyEnforceIf(xu[i])
        rep.append(r)
    m.Add(sum(rep) + sum((23 - caps[p]) * yp[p] for p in poles) <= 13)
    # S = 158 + X + Y ≤ s_cap，即计数边被单位覆盖的计次 ≥ 138 − (s_cap − 158)
    covered = []
    for i, o in enumerate(units):
        k = sum(MULT.get(c, 0) for c in o["body"])
        if k:
            covered.append(k * xu[i])
    for p in poles:
        k = sum(MULT.get(c, 0) for c in rect(p[0], p[1], 2, 2))
        if k:
            covered.append(k * yp[p])
    m.Add(sum(covered) >= 138 - (s_cap - 158))
    return m, xu, yp, units


if __name__ == "__main__":
    s_cap = int(sys.argv[1]) if len(sys.argv) > 1 else 186
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 600
    t0 = time.time()
    mach = machine_options()
    cores = core_options()
    walls = [(1, t) for t in range(2, 68)] + [(t, 1) for t in range(2, 68)]
    # 非占边桩：桩身合法，不含第 1、69 列/行；只保留可能覆盖某个保留机器选项的桩位
    cand = []
    for u in range(2, 68):
        for v in range(2, 68):
            body = rect(u, v, 2, 2)
            if not all(legal(c) for c in body):
                continue
            if any(o for o in mach if pole_range_hits(u, v, o["body"])):
                cand.append((u, v))
    capfile = "proj80_caps.json"
    if os.path.exists(capfile):
        caps = {tuple(json.loads(k)): v for k, v in json.load(open(capfile)).items()}
    else:
        caps = {}
    need = [p for p in cand + walls if p not in caps]
    if need:
        caps.update(pole_caps(need))
        json.dump({json.dumps(list(k)): v for k, v in caps.items()}, open(capfile, "w"))
    poles = sorted(set(cand) | set(walls))
    print("机器选项", len(mach), "核心选项", len(cores), "桩位", len(poles), "占边桩位", len(walls),
          "非内部桩位容量计算", sum(1 for p in poles if not interior(*p)), flush=True)
    m, xu, yp, units = build(mach, cores, poles, caps, walls, s_cap)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = seconds
    s.parameters.num_workers = 8
    s.parameters.log_search_progress = True
    s.log_callback = lambda line: print(line, flush=True)
    st = s.Solve(m)
    out = dict(s_cap=s_cap, status=s.StatusName(st), seconds=time.time() - t0, n_machine_options=len(mach),
               n_core_options=len(cores), n_poles=len(poles))
    if st in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        out["units"] = [{k: v for k, v in units[i].items() if k in ("kind", "x", "y", "w", "h", "ax", "pick")}
                        for i in range(len(units)) if s.Value(xu[i])]
        out["poles"] = [list(p) + [caps[p]] for p in poles if s.Value(yp[p])]
    json.dump(out, open(f"proj80_S{s_cap}.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("units",)}, ensure_ascii=False))
