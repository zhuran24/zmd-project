#!/usr/bin/env python3
"""闸门第1轮修复试验：按B逐机端口需求分组摆放，另加52源单位容量首加工矿流筛子。
42个非角边界口和6核心口要求首格直供；4角口只保留前格，不声称通过全源可达检查。
只搜索219台/固定边带/固定24桩/6x6留白分支；结果不是布线或可行全厂证书。
"""
import argparse, time, sys, json
from ortools.sat.python import cp_model

ap = argparse.ArgumentParser()
ap.add_argument('--N', type=int, default=70)
ap.add_argument('--flow', type=int, default=1)
ap.add_argument('--rect', default='none')
ap.add_argument('--time', type=float, default=600)
ap.add_argument('--threads', type=int, default=6)
ap.add_argument('--power', type=int, default=0)
ap.add_argument('--tmax', type=int, default=0, help='T 上限（0 表示不限）')
ap.add_argument('--log', type=int, default=1)
ap.add_argument('--tu', type=int, default=1, help='1=全幺模版（不写逐台配方比例）')
ap.add_argument('--tb', type=int, default=0, help='T+b 下限（0 表示不加）')
ap.add_argument('--ore', type=int, default=0, help='1=另加矿石子集流（分开限容）')
ap.add_argument('--hint', default='', help='用某次解的 json 作提示')
ap.add_argument('--fixplace', type=int, default=0, help='1=把提示里的机器与核心位置固定')
ap.add_argument('--portcnt', type=int, default=0, help='1=每台端口边外运输格数下限（研磨全台≥3、灌装全台≥3 是限制，不是放松）')
ap.add_argument('--out', default='')
args = ap.parse_args()

N = args.N
CAP = 20
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # E N W S
OPP = [2, 3, 0, 1]

TYPES = {'s11':('S',111),'s13':('S',11),'s12':('S',5),'s21':('S',5),'m11':('M',32),'m12':('M',17),'l31':('L',30),'l41':('L',4),'l51':('L',3),'l21':('L',1)}

def inb(x, y):
    return 0 <= x < N and 0 <= y < N

# fixed outlets
fixed_blocked = set()
ore_cells = []  # (cell, dir index from cell toward outlet)
for j in range(23):
    for yy in range(1 + 3 * j, 4 + 3 * j):
        fixed_blocked.add((0, yy))
    ore_cells.append(((1, 2 + 3 * j), 2))  # outlet is to the W
    for xx in range(1 + 3 * j, 4 + 3 * j):
        fixed_blocked.add((xx, 0))
    ore_cells.append(((2 + 3 * j, 1), 3))  # outlet is to the S
fixed_blocked.add((0, 0))  # corner left empty (keep it empty for simplicity)

rect_cells = set()
if args.rect != 'none':
    rx, ry, rw, rh = map(int, args.rect.split(','))
    for x in range(rx, rx + rw):
        for y in range(ry, ry + rh):
            rect_cells.add((x, y))
fixed_poles=[(x,y) for x in (8,22,36,50,64) for y in (8,22,36,50,64) if (x,y)!=(64,64)]
pole_cells={(x+i,y+j) for x,y in fixed_poles for i in range(2) for j in range(2)}
blocked = fixed_blocked | rect_cells | pole_cells

spine=set()
m = cp_model.CpModel()
t0 = time.time()

cover = {(x, y): [] for x in range(N) for y in range(N)}
inport = {}   # (c,d) -> list of placement vars: unit at c+DIRS[d] has in-port facing c
outport = {}  # (c,d) -> list of placement vars: unit at c+DIRS[d] has out-port facing c

def footprint_ok(ax, ay, w, h):
    for x in range(ax, ax + w):
        for y in range(ay, ay + h):
            if not inb(x, y) or (x, y) in blocked or (x,y) in spine:
                return False
    return True

def edge_cells(ax, ay, w, h, side):
    if side == 0:
        return [(ax + w - 1, y) for y in range(ay, ay + h)]
    if side == 1:
        return [(x, ay + h - 1) for x in range(ax, ax + w)]
    if side == 2:
        return [(ax, y) for y in range(ay, ay + h)]
    return [(x, ay) for x in range(ax, ax + w)]

inport_k = {}
placements = {k: [] for k in TYPES}  # k -> list of (var, in_adj list[(c,d)], out_adj list[(c,d)])

def orientations(cls):
    if cls == 'S':
        return [(3, 3, s) for s in range(4)]
    if cls == 'M':
        return [(5, 5, s) for s in range(4)]
    # L: 6x4 with in side S/N ; 4x6 with in side W/E
    return [(6, 4, 3), (6, 4, 1), (4, 6, 2), (4, 6, 0)]

for k, (cls, cnt) in TYPES.items():
    for (w, h, s) in orientations(cls):
        so = OPP[s]
        for ax in range(N - w + 1):
            for ay in range(N - h + 1):
                if not footprint_ok(ax, ay, w, h):
                    continue
                v = m.NewBoolVar(f'{k}_{w}{h}{s}_{ax}_{ay}')
                for x in range(ax, ax + w):
                    for y in range(ay, ay + h):
                        cover[(x, y)].append(v)
                ina, outa = [], []
                for (ex, ey) in edge_cells(ax, ay, w, h, s):
                    c = (ex + DIRS[s][0], ey + DIRS[s][1])
                    if inb(*c) and c not in blocked:
                        inport.setdefault((c, OPP[s]), []).append(v)
                        inport_k.setdefault(k, {}).setdefault((c, OPP[s]), []).append(v)
                        ina.append((c, OPP[s]))
                for (ex, ey) in edge_cells(ax, ay, w, h, so):
                    c = (ex + DIRS[so][0], ey + DIRS[so][1])
                    if inb(*c) and c not in blocked:
                        outport.setdefault((c, OPP[so]), []).append(v)
                        outa.append((c, OPP[so]))
                if len(ina)!=(h if s%2==0 else w) or len(outa)!=(h if s%2==0 else w):
                    m.Add(v==0)
                placements[k].append((v, ina, outa, (ax, ay, w, h)))
    m.Add(sum(p[0] for p in placements[k]) == cnt)

# core: 9x9, orientation A: in-ports on W/E edges offsets 1..7, out-ports on S/N offsets 1,4,7; B swapped
core = []
for ori in range(2):
    for ax in range(N - 8):
        for ay in range(N - 8):
            if not footprint_ok(ax, ay, 9, 9):
                continue
            v = m.NewBoolVar(f'core{ori}_{ax}_{ay}')
            for x in range(ax, ax + 9):
                for y in range(ay, ay + 9):
                    cover[(x, y)].append(v)
            in_sides = [0, 2] if ori == 0 else [1, 3]
            out_sides = [1, 3] if ori == 0 else [0, 2]
            ina, outa = [], []
            for s in in_sides:
                ec = edge_cells(ax, ay, 9, 9, s)
                for i in range(1, 8):
                    ex, ey = ec[i]
                    c = (ex + DIRS[s][0], ey + DIRS[s][1])
                    if inb(*c) and c not in blocked:
                        inport.setdefault((c, OPP[s]), []).append(v)
                        ina.append((c, OPP[s]))
            okc = True
            for s in out_sides:
                ec = edge_cells(ax, ay, 9, 9, s)
                for i in (1, 4, 7):
                    ex, ey = ec[i]
                    c = (ex + DIRS[s][0], ey + DIRS[s][1])
                    if inb(*c) and c not in blocked:
                        outport.setdefault((c, OPP[s]), []).append(v)
                        outa.append((c, OPP[s]))
                    else:
                        okc = False  # 取货口配置：6 个取货端口都满速，外侧必须是基地内的运输格
            if not okc:
                m.Add(v == 0)
            core.append((v, ina, outa))
m.AddExactlyOne(p[0] for p in core)

# transport cells
t, b = {}, {}
for x in range(N):
    for y in range(N):
        c = (x, y)
        if c in blocked:
            continue
        t[c] = m.NewBoolVar(f't_{x}_{y}')
        b[c] = m.NewBoolVar(f'b_{x}_{y}')
        m.AddImplication(b[c], t[c])
        cover[c].append(t[c])

# power poles (optional): P poles, 2x2, cover machines within 12x12 range
poles = []
if args.power > 0:
    P = args.power
    for ax in range(N - 1):
        for ay in range(N - 1):
            if not footprint_ok(ax, ay, 2, 2):
                continue
            v = m.NewBoolVar(f'pole_{ax}_{ay}')
            for x in range(ax, ax + 2):
                for y in range(ay, ay + 2):
                    cover[(x, y)].append(v)
            poles.append((v, ax, ay))
    m.Add(sum(p[0] for p in poles) == P)
    # powered cell indicator: covered by some pole's range; range = [ax-5, ax+6] x [ay-5, ay+6]
    pw_terms = {}
    for (v, ax, ay) in poles:
        for x in range(max(0, ax - 5), min(N, ax + 7)):
            for y in range(max(0, ay - 5), min(N, ay + 7)):
                pw_terms.setdefault((x, y), []).append(v)
    pw = {}
    for c, lst in pw_terms.items():
        pv = m.NewBoolVar(f'pw_{c[0]}_{c[1]}')
        m.Add(pv <= sum(lst))
        pw[c] = pv
    for k in TYPES:
        for (v, ina, outa, fp) in placements[k]:
            ax, ay, w, h = fp
            cells = [pw[(x, y)] for x in range(ax, ax + w) for y in range(ay, ay + h) if (x, y) in pw]
            m.AddBoolOr(cells + [v.Not()])

for c, lst in cover.items():
    if len(lst) > 1:
        m.Add(sum(lst) <= 1)

stats = dict(placements=sum(len(v) for v in placements.values()), core=len(core), cells=len(t))

if args.flow:
    f = {}
    for c in t:
        for d in range(4):
            n = (c[0] + DIRS[d][0], c[1] + DIRS[d][1])
            if n in t:
                f[(c, d)] = m.NewIntVar(0, CAP, f'f_{c[0]}_{c[1]}_{d}')
                m.Add(f[(c, d)] <= CAP * t[c])
                m.Add(f[(c, d)] <= CAP * t[n])
    mi, mo = {}, {}
    for (c, d), lst in outport.items():
        mi[(c, d)] = m.NewIntVar(0, CAP, f'mi_{c[0]}_{c[1]}_{d}')
        m.Add(mi[(c, d)] <= CAP * sum(lst))
        m.Add(mi[(c, d)] <= CAP * t[c])
    for (c, d), lst in inport.items():
        mo[(c, d)] = m.NewIntVar(0, CAP, f'mo_{c[0]}_{c[1]}_{d}')
        m.Add(mo[(c, d)] <= CAP * sum(lst))
        m.Add(mo[(c, d)] <= CAP * t[c])
    src = {}
    for (c, d) in ore_cells:
        m.Add(t[c] == 1)
        src[c] = CAP
    for c in t:
        inflow = [f[(n, OPP[d])] for d in range(4)
                  for n in [(c[0] + DIRS[d][0], c[1] + DIRS[d][1])] if (n, OPP[d]) in f]
        inflow += [mi[(c, d)] for d in range(4) if (c, d) in mi]
        outflow = [f[(c, d)] for d in range(4) if (c, d) in f]
        outflow += [mo[(c, d)] for d in range(4) if (c, d) in mo]
        s0 = src.get(c, 0)
        m.Add(sum(inflow) + s0 == sum(outflow))
        m.Add(sum(outflow) <= CAP * (t[c] + b[c]))
    # machine recipes (per placement, enforced)
    rvars = {k: [] for k in TYPES}
    rin = {}
    fixed = {'crush': (CAP, None), 'refine': (CAP, CAP), 'parts': (CAP, CAP), 'plant': (CAP, CAP),
             'seed': (CAP, 2 * CAP), 'pack': (100, 4)}
    for k, lst in placements.items():
        for (v, ina, outa, fp) in lst:
            IN = sum(mo[e] for e in ina)
            OUT = sum(mi[e] for e in outa)
            if k in fixed:
                a_in, a_out = fixed[k]
                m.Add(IN == a_in).OnlyEnforceIf(v)
                if a_out is not None:
                    m.Add(OUT == a_out).OnlyEnforceIf(v)
                else:  # crush: OUT in [20,60]
                    r = m.NewIntVar(0, 3 * CAP, '')
                    m.Add(r <= 3 * CAP * v)
                    m.Add(OUT == r).OnlyEnforceIf(v)
                    m.Add(r >= CAP).OnlyEnforceIf(v)
                    rvars[k].append(r)
            elif args.tu:
                # 全幺模版：逐台只给流入、流出各自的上限，按机型给合计，不写逐台比例
                hi_out = {'grind': CAP, 'mold': CAP, 'fill': 4}[k]
                hi_in = {'grind': 3 * CAP, 'mold': 2 * CAP, 'fill': 80}[k]
                ro = m.NewIntVar(0, hi_out, '')
                ri = m.NewIntVar(0, hi_in, '')
                m.Add(ro <= hi_out * v)
                m.Add(ri <= hi_in * v)
                m.Add(OUT == ro).OnlyEnforceIf(v)
                m.Add(IN == ri).OnlyEnforceIf(v)
                rvars[k].append(ro)
                rin.setdefault(k, []).append(ri)
            else:
                hi = {'grind': CAP, 'mold': CAP, 'fill': 4}[k]
                mult = {'grind': 3, 'mold': 2, 'fill': 20}[k]
                r = m.NewIntVar(0, hi, '')
                m.Add(r <= hi * v)
                m.Add(OUT == r).OnlyEnforceIf(v)
                m.Add(IN == mult * r).OnlyEnforceIf(v)
                rvars[k].append(r)
    m.Add(sum(rvars['crush']) >= 1890)
    m.Add(sum(rvars['grind']) >= 630)
    m.Add(sum(rvars['mold']) >= 110)
    m.Add(sum(rvars['fill']) >= 11)
    if args.tu:
        m.Add(sum(rin['grind']) >= 1890)
        m.Add(sum(rin['mold']) >= 220)
        m.Add(sum(rin['fill']) >= 220)
    # core: 6 out-ports full speed; in-flow >= 23
    for (v, ina, outa) in core:
        for e in outa:
            m.Add(mi[e] == CAP).OnlyEnforceIf(v)
        m.Add(sum(mo[e] for e in ina) >= 23).OnlyEnforceIf(v)
    stats['flowvars'] = len(f) + len(mi) + len(mo)
    if args.ore:
        # 矿石子集流：分开限容，与不分物品流除共用布尔外无联系（全幺模直积）
        fo = {}
        for (c, d) in f:
            n = (c[0] + DIRS[d][0], c[1] + DIRS[d][1])
            fo[(c, d)] = m.NewIntVar(0, CAP, '')
            m.Add(fo[(c, d)] <= CAP * t[c])
            m.Add(fo[(c, d)] <= CAP * t[n])
        moo = {}
        for k in ('refine', 'crush'):
            for e, lst in inport_k[k].items():
                if e not in moo:
                    moo[e] = []
                moo[e] += lst
        moov = {}
        for e, lst in moo.items():
            moov[e] = m.NewIntVar(0, CAP, '')
            m.Add(moov[e] <= CAP * sum(lst))
            m.Add(moov[e] <= CAP * t[e[0]])
        # core out-ports supply ore
        core_src = {}
        for (v, ina, outa) in core:
            for e in outa:
                core_src.setdefault(e, []).append(v)
        mio = {}
        for e, lst in core_src.items():
            mio[e] = m.NewIntVar(0, CAP, '')
            m.Add(mio[e] == CAP * sum(lst))
        for c in t:
            inflow = [fo[(n, OPP[d])] for d in range(4)
                      for n in [(c[0] + DIRS[d][0], c[1] + DIRS[d][1])] if (n, OPP[d]) in fo]
            inflow += [mio[(c, d)] for d in range(4) if (c, d) in mio]
            outflow = [fo[(c, d)] for d in range(4) if (c, d) in fo]
            outflow += [moov[(c, d)] for d in range(4) if (c, d) in moov]
            m.Add(sum(inflow) + src.get(c, 0) == sum(outflow))
            m.Add(sum(outflow) <= CAP * (t[c] + b[c]))
        for k in ('refine', 'crush'):
            for (v, ina, outa, fp) in placements[k]:
                m.Add(sum(moov[e] for e in ina) <= CAP).OnlyEnforceIf(v)
        m.Add(sum(moov.values()) == 52 * CAP)
        stats['orevars'] = len(fo) + len(moov) + len(mio)
else:
    # port adjacency only: every machine's in-edge and out-edge has >=1 transport neighbour cell
    for k, lst in placements.items():
        for (v, ina, outa, fp) in lst:
            m.AddBoolOr([t[c] for (c, d) in ina] + [v.Not()])
            m.AddBoolOr([t[c] for (c, d) in outa] + [v.Not()])
    for (c, d) in ore_cells:
        m.Add(t[c] == 1)
    for (v, ina, outa) in core:
        for (c, d) in outa:
            m.AddImplication(v, t[c])

if args.portcnt:
    KIN = {'crush': 1, 'refine': 1, 'parts': 1, 'mold': 1, 'plant': 1, 'seed': 1, 'grind': 3, 'pack': 5, 'fill': 3}
    KOUT = {'crush': 1, 'refine': 1, 'parts': 1, 'mold': 1, 'plant': 1, 'seed': 2, 'grind': 1, 'pack': 1, 'fill': 1}
    for k, lst in placements.items():
        for (v, ina, outa, fp) in lst:
            if len(ina) < KIN[k] or len(outa) < KOUT[k]:
                m.Add(v == 0)
                continue
            m.Add(sum(t[c] for (c, d) in ina) >= KIN[k]).OnlyEnforceIf(v)
            m.Add(sum(t[c] for (c, d) in outa) >= KOUT[k]).OnlyEnforceIf(v)
for k,lst in placements.items():
    for v,ina,outa,fp in lst:
        m.Add(sum(t[cell] for cell,dr in ina)>=int(k[1])).OnlyEnforceIf(v)
        m.Add(sum(t[cell] for cell,dr in outa)>=int(k[2])).OnlyEnforceIf(v)
# All non-corner boundary ore cells must directly serve a small machine.
# Corner four ports retain longer routes. This is a candidate-only shape restriction.
for cell,toward_outlet in ore_cells:
    if max(cell)<8:continue
    options=[v for d in range(4) if d!=toward_outlet for v in inport_k['s11'].get((cell,d),[])]
    m.Add(sum(options)>=1)
# Each core mouth must feed a small machine directly through its front cell.
for cv, ina, outa in core:
    for cell, side in outa:
        opts=[v for dr in range(4) if dr!=side for v in inport_k['s11'].get((cell,dr),[])]
        m.Add(sum(opts)>=1).OnlyEnforceIf(cv)
# A small unit has batch capacity one; it cannot absorb two full ore mouths.
for v, ina, outa, fp in placements['s11']:
    fixed_touch=sum(any(cell==q and dr!=sd for q,sd in ore_cells) for cell,dr in ina)
    if fixed_touch>1:m.Add(v==0)
if args.tmax > 0:
    m.Add(sum(t.values()) <= args.tmax)
if args.tb > 0:
    m.Add(sum(t.values()) + sum(b.values()) >= args.tb)

if args.hint:
    H = json.load(open(args.hint))
    want = set()
    for (k, ax, ay, w, h, s_) in H['units']:
        want.add(f'{k}_{w}{h}{s_}_{ax}_{ay}')
    ori, cx, cy = H['core']
    want.add(f'core{ori}_{cx}_{cy}')
    tset = set(map(tuple, H['transport']))
    for k, lst in placements.items():
        for (v, ina, outa, fp) in lst:
            val = 1 if v.Name() in want else 0
            if args.fixplace:
                m.Add(v == val)
            else:
                m.AddHint(v, val)
    for (v, ina, outa) in core:
        val = 1 if v.Name() in want else 0
        if args.fixplace:
            m.Add(v == val)
        else:
            m.AddHint(v, val)
    for c, v in t.items():
        m.AddHint(v, 1 if c in tset else 0)
# Separate uncolored ore-flow necessary filter: 52 sources, distinct unit-capacity small consumers.
# Grid slots allow capacity two and arbitrary turns: a relaxation, not real belt routing.
from collections import defaultdict
ore_arc={}
for cell in t:
    for dr,(dx,dy) in enumerate(DIRS):
        q=(cell[0]+dx,cell[1]+dy)
        if q in t:
            fv=m.NewIntVar(0,1,'of');ore_arc[cell,dr]=fv
            m.Add(fv<=t[cell]);m.Add(fv<=t[q])
ore_sink={}
for e,lst in inport_k['s11'].items():
    if e[0] in t:
        vv=m.NewIntVar(0,1,'os');ore_sink[e]=vv
        m.Add(vv<=sum(lst));m.Add(vv<=t[e[0]])
for pv,ina,outa,fp in placements['s11']:
    m.Add(sum(ore_sink[e] for e in ina if e in ore_sink)<=1).OnlyEnforceIf(pv)
core_supply=defaultdict(list)
for cv,ina,outa in core:
    for cell,dr in outa:core_supply[cell].append(cv)
fixed_supply={cell:1 for cell,dr in ore_cells}
for cell,tv in t.items():
    incoming=[ore_arc[(cell[0]+dx,cell[1]+dy),OPP[dr]] for dr,(dx,dy) in enumerate(DIRS) if ((cell[0]+dx,cell[1]+dy),OPP[dr]) in ore_arc]
    outgoing=[ore_arc[cell,dr] for dr in range(4) if (cell,dr) in ore_arc]
    consume=[ore_sink[cell,dr] for dr in range(4) if (cell,dr) in ore_sink]
    supply=fixed_supply.get(cell,0)+sum(core_supply[cell])
    m.Add(sum(incoming)+supply==sum(outgoing)+sum(consume))
    m.Add(sum(incoming)+supply<=2*tv)
m.Add(sum(ore_sink.values())==52)

stats['build_s'] = round(time.time() - t0, 1)
print('stats', json.dumps(stats), flush=True)

solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = args.time
solver.parameters.num_workers = args.threads
solver.parameters.log_search_progress = bool(args.log)
t1 = time.time()
st = solver.Solve(m)
res = dict(status=solver.StatusName(st), wall=round(time.time() - t1, 1), stats=stats,
           rect=args.rect, flow=args.flow, power=args.power, tu=args.tu, threads=args.threads)
if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    res['T'] = int(sum(solver.Value(v) for v in t.values()))
    res['bridges'] = int(sum(solver.Value(v) for v in b.values()))
    grid = [['.'] * N for _ in range(N)]
    for c in fixed_blocked:
        grid[c[1]][c[0]] = 'o'
    letter = {k:k[0].upper() for k in TYPES}
    for k, lst in placements.items():
        for (v, ina, outa, fp) in lst:
            if solver.Value(v):
                name = v.Name().split('_')
                ax, ay = int(name[2]), int(name[3])
                w, h = int(name[1][0]), int(name[1][1])
                for x in range(ax, ax + w):
                    for y in range(ay, ay + h):
                        grid[y][x] = letter[k]
    for (v, ina, outa) in core:
        if solver.Value(v):
            nm = v.Name().split('_')
            ax, ay = int(nm[1]), int(nm[2])
            for x in range(ax, ax + 9):
                for y in range(ay, ay + 9):
                    grid[y][x] = 'Z'
    for c, v in t.items():
        if solver.Value(v):
            grid[c[1]][c[0]] = '#' if solver.Value(b[c]) else '+'
    res['grid'] = [''.join(row) for row in reversed(grid)]
    units = []
    for k, lst in placements.items():
        for (v, ina, outa, fp) in lst:
            if solver.Value(v):
                sside = int(v.Name().split('_')[1][2])
                units.append([k, fp[0], fp[1], fp[2], fp[3], sside])
    res['units'] = units
    res['poles']=fixed_poles
    for (v, ina, outa) in core:
        if solver.Value(v):
            nm = v.Name().split('_')
            res['core'] = [int(nm[0][4]), int(nm[1]), int(nm[2])]
    res['transport'] = [list(c) for c, v in t.items() if solver.Value(v)]
    res['bridge_cells'] = [list(c) for c, v in b.items() if solver.Value(v)]
print(json.dumps({k: v for k, v in res.items() if k not in ('grid', 'units', 'transport', 'bridge_cells')}), flush=True)
if args.out:
    with open(args.out, 'w') as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
