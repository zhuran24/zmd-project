# 核「采种单元不断料」修订相对原条目的改动是否必要：用规则内的单位构造下游，找原条目结论在步进规则下不成立的可达循环态。
# 编码乙（通用通道图、第 31 行两种读法）；甲（外部每 9 步收货的抽象下游）作对照。
# 例甲：荞花单元（k=2），K 两条取货通道各一格传送带同进一台研磨机 G；G 每批用 2 件荞花粉末，砂叶粉末每 10 步来 1 件
#       （来路较慢即可，例如经设了每 5 tick 收下上限的物品准入口）。起态取修订版的满库存。看循环态里 K 的首格是否有
#       「空了当步没补上」的步末——原条目说「每条的首运输物品格一空就在同一时刻取到 1 件」。
# 例乙：原条目低库存门槛 Φ(s)=L1+L2+5/2（L 全为 1，C 有 4 件植株、取货 1 粒种子，其余空），砂叶单元 K 三条取货通道，
#       每条为 传送带U→桥接器P⇄桥接器Q（同轴相邻）→传送带D→总能收。现行第 28、31 行下取次序 D、Q、P、U（层数无法确定时的一种），
#       Q 判定时把 P 的另一上游 U 一起判定；拟改读法下 Q 的物品不能回 P，不带动 U。看循环态里 C、A 缓存是否有步末空着。
# 例丙：同例乙的低库存起态，K 三条通道 U→物品准入口（每 5 tick 收下上限 m）→D→总能收，两种读法相同。
import sys, json
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import sim_b as SB
import sim_a as SA


class Grinder(SB.Machine):
    def __init__(self):
        super().__init__('G', 'powder', 'fine', 1, cap=50)
        self.sand = 0

    def can_start(self):
        return self.inp >= 2 and self.sand >= 1

    def do_start(self):
        self.inp -= 2
        self.sand -= 1

    def flow(self):
        self.done = 0   # 产物去向总能收


def sig(net, extra=()):
    ms = tuple((m.inp, m.out, m.busy, m.done, tuple(c.name for c in m.queue)) for m in net.machines)
    cs = tuple((c.item, min(c.age, 8) if c.item else 0, c.frm if c.item else None,
                (None if (c.win_start is None or net.t - c.win_start >= 40) else net.t - c.win_start, c.win_count if (c.win_start is not None and net.t - c.win_start < 40) else 0) if c.gate else None)
               for c in net.cells)
    return (ms, cs) + tuple(extra)


def find_cycle(net, steps, probe, extra=lambda n: ()):
    seen = {}
    rec = []
    for i in range(steps):
        net.step()
        rec.append(probe(net))
        key = sig(net, extra(net))
        if key in seen:
            j = seen[key]
            return {'进入循环的步': j + 1, '周期': i - j, 'rec': rec[j + 1:i + 1]}
        seen[key] = i
    return None


def full_start(net, k):
    for m in (net.A, net.B, net.C, net.K):
        m.inp, m.out, m.busy, m.done = 50, 50, 8, 0
    for p, it in ((net.CA, 'seed'), (net.CB, 'seed'), (net.AC, 'plant'), (net.BK, 'plant')):
        for c in p:
            c.item, c.age, c.frm = it, 8, 'prev'


def example_jia(mode='every10'):
    g = Grinder()
    net = SB.plant_unit(1, 1, 1, 1, 2, [(1, g), (1, g)])
    net.machines.append(g)
    full_start(net, 2)
    g.inp = 50
    def ext(n, t):
        if mode == 'every10':
            if t % 10 == 0:
                g.sand += 1
        else:
            # 砂叶粉末经「每 5 tick 收下上限 4」的物品准入口从常满来路过来：每 40 步里第 0、8、16、24 步各到 1 件
            if t % 40 in (0, 8, 16, 24):
                g.sand += 1
    orig = net.step
    net.step = lambda: orig(ext)
    def probe(n):
        return {'K首格步末空': [c.item is None for c in [p[0] for p in n.KP]],
                'G存货': g.inp, 'K批开始': n.K.busy == 8}
    cyc = find_cycle(net, 20000, probe, extra=lambda n: (n.t % 40, g.sand))
    rec = cyc['rec']
    holes = sum(sum(r['K首格步末空']) for r in rec)
    return {'周期': cyc['周期'], '进入循环的步': cyc['进入循环的步'],
            '周期内K首格「空了当步没补上」的步末次数': holes,
            '周期内K开批次数': sum(r['K批开始'] for r in rec),
            'G存货范围': [min(r['G存货'] for r in rec), max(r['G存货'] for r in rec)]}


def low_start(net):
    net.C.inp = 4
    net.C.out = 1


def unit_with_kpaths(reading, kind, m5=3):
    net = SB.Net(reading)
    C = SB.Machine('C', 'plant', 'seed', 2)
    A = SB.Machine('A', 'seed', 'plant', 1)
    B = SB.Machine('B', 'seed', 'plant', 1)
    K = SB.Machine('K', 'plant', 'powder', 3)
    net.machines = [A, B, C, K]
    CA = SB.path(net, 'CA', 1, C, A)
    CB = SB.path(net, 'CB', 1, C, B)
    AC = SB.path(net, 'AC', 1, A, C)
    BK = SB.path(net, 'BK', 1, B, K)
    order_k = []
    KP = []
    for i in range(3):
        sink = SB.Sink(f'S{i}', lambda t: True)
        if kind == 'bridge':
            U = SB.Cell(f'U{i}')
            P = SB.Cell(f'P{i}')
            Q = SB.Cell(f'Q{i}')
            D = SB.Cell(f'D{i}')
            U.outs = [P]
            P.outs = [Q]
            Q.outs = [D, P]
            D.outs = [sink]
            net.cells += [U, P, Q, D]
            K.outs.append(U)
            K.queue.append(U)
            K.never.add(id(U))
            order_k.append([D, Q, P, U])
            KP.append([U, P, Q, D])
        else:
            U = SB.Cell(f'U{i}')
            Gt = SB.Cell(f'G{i}', gate={'limit5': m5})
            D = SB.Cell(f'D{i}')
            U.outs = [Gt]
            Gt.outs = [D]
            D.outs = [sink]
            net.cells += [U, Gt, D]
            K.outs.append(U)
            K.queue.append(U)
            K.never.add(id(U))
            order_k.append([D, Gt, U])
            KP.append([U, Gt, D])
    base = SB.chain_order([CA, CB, AC, BK])
    ko = []
    for lay in range(4):
        for o in order_k:
            if lay < len(o):
                ko.append(o[lay])
    net.order = base + ko
    net.A, net.B, net.C, net.K = A, B, C, K
    net.CA, net.CB, net.AC, net.BK, net.KP = CA, CB, AC, BK, KP
    return net


def probe_unit(n):
    return {'空缓存': [not m.cache_nonempty() for m in (n.C, n.A, n.B, n.K)], '2Φ': SB.phi2(n),
            '批': [m.busy == 8 for m in (n.C, n.A, n.B, n.K)]}


def summarize(cyc):
    rec = cyc['rec']
    names = ['C', 'A', 'B', 'K']
    return {'周期': cyc['周期'], '进入循环的步': cyc['进入循环的步'],
            '周期内各机完成批数': {names[i]: sum(r['批'][i] for r in rec) for i in range(4)},
            '周期内各机步末空缓存次数': {names[i]: sum(r['空缓存'][i] for r in rec) for i in range(4)},
            '周期内Φ−L1−L2范围': [min(r['2Φ'] for r in rec) / 2 - 2, max(r['2Φ'] for r in rec) / 2 - 2]}


def example_yi(reading):
    net = unit_with_kpaths(reading, 'bridge')
    low_start(net)
    assert SB.phi2(net) == 2 * (2 + 2.5)
    cyc = find_cycle(net, 50000, probe_unit)
    return summarize(cyc)


def example_bing(m5):
    net = unit_with_kpaths('cur', 'gate', m5)
    low_start(net)
    cyc = find_cycle(net, 200000, probe_unit)
    return summarize(cyc) if cyc else None


def example_a_every9():
    # 编码甲：K 三条一格通道，末端外部每 9 步各收 1 件（推导席报告的抽象下游），与例乙现行读法对照
    cfg = SA.Cfg(k=3, cap=50)
    t0 = 100
    st = ((0, 0, -1), (0, 0, -1), (4, 1, -1), (0, 0, -1), (-1,), (-1,), (-1,), (-1,), ((-1,), (-1,), (-1,)),
          (SA.NEVER, SA.NEVER + 1), (SA.NEVER, SA.NEVER + 1, SA.NEVER + 2))
    last = [None, None, None]
    seen = {}
    rec = []
    t = t0
    while t < t0 + 50000:
        t += 1
        A, B, C, K, CA, AC, CB, BK, KCH, pc, pk = st
        rel = []
        for i in range(3):
            e = KCH[i][-1]
            ok = e >= 0 and t - e >= 8 and (last[i] is None or t - last[i] >= 9)
            rel.append(ok)
        st, sc, sk, left = SA.step(st, t, cfg, rel_k=tuple(rel))
        for i in range(3):
            if left[i]:
                last[i] = t
        A, B, C, K = st[0], st[1], st[2], st[3]
        rec.append({'空缓存': [x[2] == -1 for x in (C, A, B, K)], '2Φ': SA.phi2(st),
                    '批': [x[2] == t + 8 for x in (C, A, B, K)]})
        from s09_check import norm
        key = norm(st, t) + (tuple(None if l is None else min(t - l, 9) for l in last),)
        if key in seen:
            j = seen[key]
            return summarize({'周期': t - j, '进入循环的步': j - t0, 'rec': rec[j - t0:]})
        seen[key] = t
    return None


if __name__ == '__main__':
    out = {'例甲（两口同步腾空）': example_jia(),
           '例甲′（砂叶经准入口每5tick上限4）': example_jia('gate4'),
           '例乙（相邻桥，现行读法）': example_yi('cur'),
           '例乙（相邻桥，拟改读法）': example_yi('new'),
           '对照（编码甲，外部每9步收）': example_a_every9()}
    for m5 in (1, 2, 3, 4, 5):
        out[f'例丙（准入口每5tick上限{m5}）'] = example_bing(m5)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    json.dump(out, open(__file__.rsplit('/', 1)[0] + '/s09_orig.json', 'w'), ensure_ascii=False, indent=1)
