# 线索核对：若把第 31 行对桥接器按「整个单位」读（两轴的非分流器元件上游在其中最先判定者判定时一起判定），
# 跨线桥会不会让采种单元出问题。编码乙，满库存起态（修订版不断料前提），K 三口成熟就收。
# CA = 传送带U → 桥接器X（一轴）→ 准入口G1 → 准入口G2 → A（层数 G2=1、G1=2、X1=3、U=4）；
# 跨线 = 传送带V → 桥接器X（另一轴）→ 传送带W → 总能收（层数 W=1、X2=2、V=3）。
# 同层 3 的 V 与 X1 按接通先后，取 V 在前（离线后可能如此）。对照：按一轴读（两轴各自成组）。
import sys, json
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import sim_b as SB


class UnitNet(SB.Net):
    def __init__(self, reading, by_unit):
        super().__init__(reading)
        self.by_unit = by_unit

    def upstream_groups(self):
        g = {}
        for c in self.cells:
            for o in c.outs:
                g.setdefault(id(o), []).append(c)
        if self.by_unit:
            byu = {}
            for c in self.cells:
                for o in c.outs:
                    byu.setdefault(o.unit, []).append(c)
            for c in self.cells:
                for o in c.outs:
                    g[id(o)] = byu[o.unit]
        return g


def build(by_unit):
    net = UnitNet('cur', by_unit)
    C = SB.Machine('C', 'plant', 'seed', 2)
    A = SB.Machine('A', 'seed', 'plant', 1)
    B = SB.Machine('B', 'seed', 'plant', 1)
    K = SB.Machine('K', 'plant', 'powder', 3)
    net.machines = [A, B, C, K]
    U = SB.Cell('U')
    X1 = SB.Cell('X1', unit='X')
    X2 = SB.Cell('X2', unit='X')
    G1 = SB.Cell('G1', gate={'limit5': 10**9})
    G2 = SB.Cell('G2', gate={'limit5': 10**9})
    V = SB.Cell('V')
    W = SB.Cell('W')
    feed = SB.Sink('feed', lambda t: True)
    out = SB.Sink('out', lambda t: True)
    U.outs = [X1]; X1.outs = [G1]; G1.outs = [G2]; G2.outs = [A]
    V.outs = [X2]; X2.outs = [W]; W.outs = [out]
    net.cells += [U, X1, G1, G2, V, X2, W]
    C.outs.append(U); C.queue.append(U); C.never.add(id(U))
    CA = [U, X1, G1, G2]
    CB = SB.path(net, 'CB', 1, C, B)
    AC = SB.path(net, 'AC', 1, A, C)
    BK = SB.path(net, 'BK', 1, B, K)
    KP = [SB.path(net, f'K{i}', 1, K, SB.Sink(f's{i}', lambda t: True)) for i in range(3)]
    # 层 1：G2、W、CB0、AC0、BK0、K*；层 2：G1、X2；层 3：V（先接通）、X1；层 4：U
    net.order = [G2, W, CB[0], AC[0], BK[0]] + [p[0] for p in KP] + [G1, X2, V, X1, U]
    net.A, net.B, net.C, net.K = A, B, C, K
    net.CA, net.CB, net.AC, net.BK, net.KP = CA, CB, AC, BK, KP
    for m in (A, B, C, K):
        m.inp, m.out, m.busy, m.done = 50, 50, 8, 0
    prev = 'C'
    for c in CA:
        c.item, c.age, c.frm = 'seed', 8, prev
        prev = c.unit
    for p, it, src in ((CB, 'seed', 'C'), (AC, 'plant', 'A'), (BK, 'plant', 'B')):
        p[0].item, p[0].age, p[0].frm = it, 8, src
    # 跨线常满：V 每步一空就补
    def ext(n, t):
        if V.item is None:
            V.item, V.age, V.frm = 'ore', 0, 'src'
    return net, ext


def run(by_unit, steps=6000):
    net, ext = build(by_unit)
    viol = {}
    n_to_A = 0
    lastA = net.A.inp
    for _ in range(steps):
        net.step(ext)
        for nm, m in (('A', net.A), ('B', net.B), ('C', net.C), ('K', net.K)):
            if not m.cache_nonempty():
                viol[nm + '缓存空'] = viol.get(nm + '缓存空', 0) + 1
        if net.B.inp < 49 or net.K.inp < 49 or net.B.out < 49 or net.K.out < 47:
            viol['库存界'] = viol.get('库存界', 0) + 1
        if net.CB[0].item is None or net.BK[0].item is None:
            viol['CB/BK首格步末空'] = viol.get('CB/BK首格步末空', 0) + 1
    return {'按整个单位一起判定': by_unit, '违例计数': viol, 'Φ−L1−L2末值': SB.phi2(net) / 2 - 5}


if __name__ == '__main__':
    out = [run(False), run(True)]
    print(json.dumps(out, ensure_ascii=False))
    json.dump(out, open(__file__.rsplit('/', 1)[0] + '/s_cross.json', 'w'), ensure_ascii=False, indent=1)
