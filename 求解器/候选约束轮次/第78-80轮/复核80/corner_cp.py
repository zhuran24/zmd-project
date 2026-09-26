# 复核80：角区整组界 N+W_O ≤ 91 的独立重算（CP-SAT，自写几何，不导入推导席脚本）
# 边带：左边第 0 列、下边第 0 行各 23 个仓库取货口（3x1，端口在向内长边中点），每边一个空格，
#       空格在从角起第 3k+1 格（0 起算为 3k），且至少一边在角格。
# O：取货口端口正对的第 1 列/第 1 行运输格。N = 46（取货口通道）+ 法向接口 + 与贴空格小机的切向接口。
# 法向接口：O 格向内法向邻格是一台以该边为存货边的 3x3 粉碎机/精炼炉。
# 贴空格小机（a=3）：左边空格 g>0 时占 (1..3, g-1..g+1)，端口边上下；下边空格 h>0 时转置。
import json, itertools
from ortools.sat.python import cp_model


def band_middles(gap):
    """70 格的一条边，gap 为空格下标（取货口占其余 69 格，逐个 3 格），返回端口中点下标。"""
    cells = [i for i in range(70) if i != gap]
    mids = []
    for j in range(0, 69, 3):
        blk = cells[j:j + 3]
        assert blk[2] - blk[0] == 2
        mids.append(blk[1])
    return mids


def layouts():
    out = []
    for g in range(0, 70, 3):
        out.append((g, 0))          # 左边空格在 g（g=0 即角格）、下边在角格
    for h in range(3, 70, 3):
        out.append((0, h))          # 左边在角格、下边空格在 h
    return out


def solve_case(g, h, machine, shaper_w):
    # machine: 是否有贴空格小机；shaper_w: 该小机为塑形机且允许 W_O
    O_left = [(1, p) for p in band_middles(g)] if g != 0 or True else []
    O_left = [(1, p) for p in band_middles(g)]
    O_bot = [(p, 1) for p in band_middles(h)]
    O = set(O_left) | set(O_bot)
    assert len(O) == 46
    if machine:
        if g > 0:
            gm = {(x, y) for x in (1, 2, 3) for y in (g - 1, g, g + 1)}
        else:
            gm = {(x, y) for x in (h - 1, h, h + 1) for y in (1, 2, 3)}
    else:
        gm = set()
    m = cp_model.CpModel()
    cons = []  # (O 格, 机身格集合, 变量)
    occ = {}
    for (ox, oy) in O_left:
        for y0 in (oy - 2, oy - 1, oy):
            cells = {(x, y) for x in (2, 3, 4) for y in range(y0, y0 + 3)}
            if any(c[1] < 1 or c[1] > 69 for c in cells):
                continue
            if cells & O or cells & gm:
                continue
            v = m.NewBoolVar("")
            cons.append(((ox, oy), cells, v))
    for (ox, oy) in O_bot:
        for x0 in (ox - 2, ox - 1, ox):
            cells = {(x, y) for x in range(x0, x0 + 3) for y in (2, 3, 4)}
            if any(c[0] < 1 or c[0] > 69 for c in cells):
                continue
            if cells & O or cells & gm:
                continue
            v = m.NewBoolVar("")
            cons.append(((ox, oy), cells, v))
    for (o, cells, v) in cons:
        for c in cells:
            occ.setdefault(c, []).append(v)
    for c, lst in occ.items():
        m.AddAtMostOne(lst)
    byo = {}
    for (o, cells, v) in cons:
        byo.setdefault(o, []).append(v)
    for o, lst in byo.items():
        m.AddAtMostOne(lst)
    # 空格在第 3 格（g=3 或 h=3）时另一条边 23 个法向接口不能全有（第 1 行/列 24 件原矿只进 23 台）
    if g == 3:
        m.Add(sum(v for (o, c, v) in cons if o in set(O_bot)) <= 22)
    if h == 3:
        m.Add(sum(v for (o, c, v) in cons if o in set(O_left)) <= 22)
    extra = 0
    w_terms = []
    if machine:
        k = g if g > 0 else h
        # 两端各至多 1 个切向接口；k=3 时近角一端的两个接法合计至多 1
        if not shaper_w:
            extra = 2
        else:
            # 塑形机：存货端可有桥接器送钢块（接口 1）并记 W≤1，取货端可接收（接口 1）
            # k=3 时近角一端不能给塑形机进料也不能收其产物（见报告理由），只剩远端 1 个接口
            if k == 3:
                extra = 1
                ends = [k + 2]          # 仅远端可作存货端
            else:
                extra = 2
                ends = [k - 2, k + 2]
            wv = []
            for e in ends:
                # 存货端 O 格为 (1,e)（左边）或 (e,1)（下边）；另需同一存货边另一对接位置 (2,e)/(3,e) 未被机身占用
                if g > 0:
                    nb = [(2, e), (3, e)]
                else:
                    nb = [(e, 2), (e, 3)]
                nb = [p for p in nb if p not in O]
                if not nb:
                    continue
                w = m.NewBoolVar("")
                # w=1 需 nb 中至少一格空（不被法向消费机占用）
                frees = []
                for p in nb:
                    f = m.NewBoolVar("")
                    m.Add(f + sum(occ.get(p, [])) <= 1)
                    frees.append(f)
                m.AddBoolOr(frees).OnlyEnforceIf(w)
                wv.append(w)
            if wv:
                m.Add(sum(wv) <= 1)   # 只有一条存货边
                w_terms = wv
    obj = sum(v for (o, c, v) in cons) + sum(w_terms)
    m.Maximize(obj)
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    s.parameters.max_time_in_seconds = 60
    st = s.Solve(m)
    assert st == cp_model.OPTIMAL, (g, h, machine, shaper_w, s.StatusName(st))
    return 46 + extra + int(round(s.ObjectiveValue())), len(cons)


if __name__ == "__main__":
    res = []
    for g, h in layouts():
        k = max(g, h)
        branches = [(False, False)]
        if 0 < k <= 66:
            branches += [(True, False), (True, True)]
        for machine, sw in branches:
            b, n = solve_case(g, h, machine, sw)
            res.append(dict(g=g, h=h, machine=machine, shaper_w=sw, bound=b, options=n))
    mx = max(r["bound"] for r in res)
    json.dump(dict(cases=res, max_bound=mx, case_count=len(res)), open("corner_cp.json", "w"), indent=1)
    print("cases", len(res), "max N+W_O", mx)
    # 与推导席结果逐项比对（只读其 JSON 数值，不导入其程序）
    try:
        other = json.load(open("../推导78B/corner_independent.json"))["cases"]
        key = lambda d: (d["gaps"][0], d["gaps"][1], d["tangent"], d["weighted"])
        ob = {key(d): d["bound"] for d in other}
        mine = {(r["g"], r["h"], r["machine"], r["shaper_w"]): r["bound"] for r in res}
        diff = {str(k): (mine.get(k), ob.get(k)) for k in set(ob) | set(mine) if mine.get(k) != ob.get(k)}
        print("与推导席不同的分支数", len(diff), list(diff.items())[:10])
    except Exception as e:
        print("比对失败", e)
