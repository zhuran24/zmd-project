"""三审自写：1113 空矩形位于 (49,b) 时的边段投影模型（CP-SAT 编码）。

如果存在含该空矩形的达标布局，正式「面积预算」给出九机型恰为下限（小 131、中 48、大 38，共 217 台）、
没有协议储存箱、P<=12，且 S=16P-2J+X+Y<=187（X、Y、J 见正式「内带缺口」「供电下限」）。
217 台逐台在产（六种满载机型由「满载配置」；研磨、塑形、灌装少一台就不够正式产率），都要得电。

投影：只保留碰到 X、Y 计数格的制造单位和协议核心、全部相关供电桩，删去其余单位。保留的条件：
  1. 机身、核心、桩身落在列行 1..69、不碰空矩形、互不重叠；不占 47 种共同边带之一的 46 个矿石首运输格。
  2. 制造单位两条端口边外各至少一个可用且未被机身占用的邻格；大制造单位的进料边至少 2 个，
     且至多一台少于 3 个（研磨进料、封装进料：31 台研磨机、3 台封装机、3 台灌装机进料通道都 >=3，
     第 32 台研磨机 >=2，每条通道占进料边一个邻格）。
  3. 协议核心 6 个取货端口对面的格都空着（核心邻格），存货端口对面至少 2 格空着（成品入库至少 2 条存货通道，
     无箱时只能进核心）；核心离带取最弱形式 2+3δ<=2(x0-1)（m>=2、e<=2），下边同理；核心不在 x0<=3 且 y0<=3。
  4. 每台保留的制造单位至少被一根所选桩覆盖；逐桩亏额 L_p=23-c_p（c_p 为 site_power.py 求得的该桩
     局部最大在产台数），与保留机器的实际重复覆盖次数 sum(k_m-1) 合计 <= 23P-217。
  5. 所选桩数 <= P；全部占边桩都作为选项保留（J 按所选占边桩计），不相关的非占边桩删去（亏额非负，删去只放宽）。
  6. 机型台数上限 131/48/38，核心至多 1。
  7. S=16P-2J+X+Y <= cap，P 用真实桩数。
"""
import argparse
import json
import time

from ortools.sat.python import cp_model

import field as S
from geo import KINDS, body, port_sides, pole_body, pole_range, rect_intersects

CAT_CAP = {'S': 131, 'M': 48, 'L': 38}


def core_geometry(x, y, axis):
    """9x9 协议核心。axis='LR'：左右两边为取货边（偏移 1、4、7），上下两边为存货边（偏移 1..7）；'BT' 反之。"""
    cells = body(x, y, 9, 9)
    left = [(x - 1, y + k) for k in range(9)]
    right = [(x + 9, y + k) for k in range(9)]
    bot = [(x + k, y - 1) for k in range(9)]
    top = [(x + k, y + 9) for k in range(9)]
    if axis == 'LR':
        pick = [left[k] for k in (1, 4, 7)] + [right[k] for k in (1, 4, 7)]
        inp = [bot[k] for k in range(1, 8)] + [top[k] for k in range(1, 8)]
    else:
        pick = [bot[k] for k in (1, 4, 7)] + [top[k] for k in (1, 4, 7)]
        inp = [left[k] for k in range(1, 8)] + [right[k] for k in range(1, 8)]
    return cells, pick, inp


def core_allowed(x, y, axis):
    # 核心邻格：不能占 x0<=3 且 y0<=3
    if x <= 3 and y <= 3:
        return False
    # 核心离带最弱形式：m>=2、e<=2，m+3δ<=e(x0-1) ⇒ x0>=2，取货边朝左带时 x0>=4；下带同理
    dl = 1 if axis == 'LR' else 0   # 取货边是否朝左带
    db = 1 if axis == 'BT' else 0   # 取货边是否朝下带
    if 2 + 3 * dl > 2 * (x - 1):
        return False
    if 2 + 3 * db > 2 * (y - 1):
        return False
    return True


def build_instance(b, power):
    Xc, Yc, corner = S.count_cells(b)
    countset = set(Xc) | set(Yc)
    us = lambda c: S.usable(c, b)
    # 制造单位选项
    mach = []
    for kind, (cat, w, h, axis) in KINDS.items():
        for x in range(1, 70 - w + 1):
            for y in range(1, 70 - h + 1):
                cells = body(x, y, w, h)
                if not all(us(c) for c in cells):
                    continue
                if not any(c in countset for c in cells):
                    continue
                sa, sb = port_sides(x, y, w, h, axis)
                sa = [c for c in sa if us(c)]
                sb = [c for c in sb if us(c)]
                if not sa or not sb:
                    continue
                if cat == 'L':
                    for inp, other in ((sa, sb), (sb, sa)):
                        if len(inp) >= 2:
                            mach.append(dict(kind=kind, cat=cat, x=x, y=y, w=w, h=h, cells=cells,
                                             sides=[inp, other], inp=inp))
                else:
                    mach.append(dict(kind=kind, cat=cat, x=x, y=y, w=w, h=h, cells=cells, sides=[sa, sb], inp=None))
    # 协议核心选项
    cores = []
    for x in range(1, 70 - 9 + 1):
        for y in range(1, 70 - 9 + 1):
            for axis in ('LR', 'BT'):
                cells, pick, inp = core_geometry(x, y, axis)
                if not all(us(c) for c in cells):
                    continue
                if not any(c in countset for c in cells):
                    continue
                if not all(us(c) for c in pick):
                    continue
                inp = [c for c in inp if us(c)]
                if len(inp) < 2:
                    continue
                if not core_allowed(x, y, axis):
                    continue
                cores.append(dict(x=x, y=y, axis=axis, cells=cells, pick=pick, inp=inp))
    # 桩
    poles = []
    for (px, py) in S.pole_positions(b):
        c = power[f'{px},{py}']['c']
        rng = pole_range(px, py)
        covers = [i for i, m in enumerate(mach) if rect_intersects(m['x'], m['y'], m['w'], m['h'], rng)]
        cells = pole_body(px, py)
        touches = any(cc in countset for cc in cells) or (corner and (69, 69) in cells)
        edge = S.is_edge_pole(px, py)
        poles.append(dict(px=px, py=py, c=c, L=23 - c, edge=edge, cells=cells, covers=covers, touches=touches))
    return dict(b=b, X=Xc, Y=Yc, corner=corner, mach=mach, cores=cores, poles=poles,
                bands=S.band_arrangements())


def ore_cells(eL, eB):
    return [(1, r) for r in S.band_ports(eL)] + [(c, 1) for c in S.band_ports(eB)]


def solve(inst, P, jset, cap, seconds, workers, fix=None, log=False):
    budget = 23 * P - 217
    mach, cores = inst['mach'], inst['cores']
    poles = [p for p in inst['poles'] if p['L'] <= budget and
             (p['edge'] and max(jset) >= 1 or (not p['edge'] and (p['touches'] or p['covers'])))]
    m = cp_model.CpModel()
    u = [m.NewBoolVar(f'u{i}') for i in range(len(mach))]
    w = [m.NewBoolVar(f'w{i}') for i in range(len(cores))]
    v = [m.NewBoolVar(f'v{i}') for i in range(len(poles))]
    z = [m.NewBoolVar(f'z{i}') for i in range(len(inst['bands']))]
    m.AddExactlyOne(z)
    occ = {}
    for i, o in enumerate(mach):
        for c in o['cells']:
            occ.setdefault(c, []).append(u[i])
    for i, o in enumerate(cores):
        for c in o['cells']:
            occ.setdefault(c, []).append(w[i])
    for i, p in enumerate(poles):
        for c in p['cells']:
            occ.setdefault(c, []).append(v[i])
    ore = {}
    for a, (eL, eB) in enumerate(inst['bands']):
        for c in ore_cells(eL, eB):
            ore.setdefault(c, []).append(z[a])
    # 每个相关格一个占用布尔量：o_g = 覆盖它的所选机身之和（逐格至多一个），矿石首运输格不可占
    cells = set(occ)
    for o in mach:
        for side in o['sides']:
            cells.update(side)
    for o in cores:
        cells.update(o['pick']); cells.update(o['inp'])
    cells.update(inst['X']); cells.update(inst['Y'])
    ob = {}
    for c in cells:
        lst = occ.get(c, [])
        b_ = m.NewBoolVar(f'o{c}')
        ob[c] = b_
        if lst:
            m.Add(sum(lst) == b_)
        else:
            m.Add(b_ == 0)
        if c in ore:
            for zz in ore[c]:
                m.AddImplication(zz, b_.Not())
    occ_expr = lambda c: ob[c]
    # 端口边：选中时该侧至少一个邻格未被机身占用
    tflag = []
    for i, o in enumerate(mach):
        for side in o['sides']:
            m.AddBoolOr([ob[c].Not() for c in side]).OnlyEnforceIf(u[i])
        if o['cat'] == 'L':
            inp = o['inp']
            m.Add(sum(ob[c] for c in inp) <= len(inp) - 2).OnlyEnforceIf(u[i])
            t = m.NewBoolVar(f't{i}')
            m.AddImplication(t, u[i])
            m.Add(sum(ob[c] for c in inp) <= len(inp) - 3).OnlyEnforceIf([u[i], t.Not()])
            tflag.append(t)
    m.Add(sum(tflag) <= 1)
    for k, o in enumerate(cores):
        for c in o['pick']:
            m.AddImplication(w[k], ob[c].Not())
        m.Add(sum(ob[c] for c in o['inp']) <= len(o['inp']) - 2).OnlyEnforceIf(w[k])
    m.Add(sum(w) <= 1)
    for cat, capn in CAT_CAP.items():
        m.Add(sum(u[i] for i, o in enumerate(mach) if o['cat'] == cat) <= capn)
    # 供电
    covered_by = {i: [] for i in range(len(mach))}
    for k, p in enumerate(poles):
        for i in p['covers']:
            covered_by[i].append(v[k])
    rep = []
    for i in range(len(mach)):
        lst = covered_by[i]
        if not lst:
            m.Add(u[i] == 0)
            continue
        m.AddBoolOr(lst).OnlyEnforceIf(u[i])
        if len(lst) >= 2:
            r = m.NewIntVar(0, len(lst) - 1, f'r{i}')
            m.Add(r >= sum(lst) - 1 - len(lst) * (1 - u[i]))
            rep.append(r)
    m.Add(sum(p['L'] * v[k] for k, p in enumerate(poles)) + sum(rep) <= budget)
    m.Add(sum(v) <= P)
    J = sum(v[k] for k, p in enumerate(poles) if p['edge'])
    m.Add(J >= min(jset))
    m.Add(J <= max(jset))
    X = len(inst['X']) - sum(occ_expr(c) for c in inst['X'])
    if inst['corner']:
        cornerpoles = [v[k] for k, p in enumerate(poles) if (69, 69) in p['cells']]
        X = X + 2 - 2 * sum(cornerpoles)
    Y = len(inst['Y']) - sum(occ_expr(c) for c in inst['Y'])
    Sx = 16 * P - 2 * J + X + Y
    m.Add(Sx <= cap)
    if fix is not None:
        fix(m, dict(u=u, w=w, v=v, z=z, mach=mach, cores=cores, poles=poles))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = seconds
    s.parameters.num_workers = workers
    s.parameters.log_search_progress = log
    t0 = time.time()
    st = s.Solve(m)
    res = dict(b=inst['b'], P=P, J=sorted(jset), cap=cap, status=s.StatusName(st), seconds=round(time.time() - t0, 2),
               n_mach=len(mach), n_core=len(cores), n_poles=len(poles), budget=budget)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res['S'] = s.Value(Sx)
        res['X'] = s.Value(X)
        res['Y'] = s.Value(Y)
        res['Jval'] = s.Value(J)
        res['mach'] = [dict(kind=o['kind'], x=o['x'], y=o['y'], inp=(None if o['inp'] is None else o['inp'][0]))
                       for i, o in enumerate(mach) if s.Value(u[i])]
        res['core'] = [dict(x=o['x'], y=o['y'], axis=o['axis']) for k, o in enumerate(cores) if s.Value(w[k])]
        res['poles'] = [dict(px=p['px'], py=p['py'], c=p['c']) for k, p in enumerate(poles) if s.Value(v[k])]
        res['band'] = [inst['bands'][a] for a in range(len(z)) if s.Value(z[a])]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('b', type=int)
    ap.add_argument('P', type=int)
    ap.add_argument('--jmin', type=int, default=0)
    ap.add_argument('--jmax', type=int, default=0)
    ap.add_argument('--cap', type=int, default=187)
    ap.add_argument('--seconds', type=float, default=1800)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--name', default=None)
    ap.add_argument('--log', action='store_true')
    ap.add_argument('--caps', choices=['mine', 'r75', 'r66'], default='mine',
                    help='逐桩上限来源：本席 site_power；第 75 轮 capacities.json；第 66 轮格组证书（再与 23、占边 13 取小）')
    a = ap.parse_args()
    power = json.load(open(f'out/site_power_b{a.b}.json'))
    if a.caps == 'r75':
        assert a.b == 17
        th = json.load(open('../第75-77轮/推导75/capacities.json'))
        power = {f"{e['p'][0]},{e['p'][1]}": dict(c=e['cap']) for e in th}
    elif a.caps == 'r66':
        th = json.load(open('../第66-68轮/推导66/power_certificates.json'))[str(a.b)]
        power = {f"{e['x']},{e['y']}": dict(c=min(e['cap'], 13 if S.is_edge_pole(e['x'], e['y']) else 23)) for e in th}
    inst = build_instance(a.b, power)
    res = solve(inst, a.P, list(range(a.jmin, a.jmax + 1)), a.cap, a.seconds, a.workers, log=a.log)
    print(json.dumps({k: v for k, v in res.items() if k not in ('mach', 'core', 'poles', 'band')}, ensure_ascii=False))
    name = a.name or f'proj_b{a.b}_P{a.P}_J{a.jmin}-{a.jmax}_cap{a.cap}'
    json.dump(res, open(f'out/{name}.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
