#!/usr/bin/env python3
"""S10 复核（自写模拟器）：原条文静止反例重现；修正版随机核对；单出口即时补货核对。"""
import json, random, sys
from stepsim import World, Machine, Sink, Source, Element

IB, IP, SL, SP, DIP, ST, PART, SO, SOP, DSO = ('蓝铁块', '蓝铁粉末', '砂叶', '砂叶粉末', '致密蓝铁粉末',
                                               '钢块', '钢制零件', '源矿', '源石粉末', '致密源石粉末')
CRUSHER = [({SO: 1}, SOP, 1, 8), ({IB: 1}, IP, 1, 8), ({'荞花': 1}, '荞花粉末', 2, 8), ({SL: 1}, SP, 3, 8)]
REFINER = [({'蓝铁矿': 1}, IB, 1, 8), ({DIP: 1}, ST, 1, 8), ({IP: 1}, IB, 1, 8)]
GRINDER = [({IP: 2, SP: 1}, DIP, 1, 8), ({SOP: 2, SP: 1}, DSO, 1, 8), ({'荞花粉末': 2, SP: 1}, '细磨荞花粉末', 1, 8)]
PARTS = [({ST: 1}, PART, 1, 8)]
PACKER = [({PART: 10, DSO: 15}, '高容谷地电池', 1, 40)]


def counterexample():
    """原 S10 反例：Y 只做 蓝铁块→蓝铁粉末，存货格里有 1 件蓝铁粉末，缓存里有完成的 1 件蓝铁粉末。"""
    w = World()
    Y = Machine('Y', CRUSHER, 1, rank=0)
    X = Machine('X', REFINER, 1, rank=1)
    w.nts = [Y, X]
    w.chain(Y, X, [2], name='YX')
    w.finalize()
    Y.inp = [[IP, 1]]
    Y.cache = ('done', IP, 1)
    rec = []
    for t in range(40):
        w.step()
        rec.append((t, Y.cache, X.cache, Y.out, X.inp))
    static = all(r[1:] == rec[0][1:] for r in rec)
    return dict(static=static, Y_cache_nonempty=all(r[1] is not None for r in rec),
                X_cache_empty=all(r[2] is None for r in rec), first=str(rec[0]))


def counterexample_reach():
    """可达性：Y 关机时存货有 1 件蓝铁块，另一条临时进料路末格停着 1 件蓝铁粉末；开机后自然进入反例态。"""
    w = World()
    Y = Machine('Y', CRUSHER, 1, rank=0, on=False)
    X = Machine('X', REFINER, 1, rank=1)
    src = Sink('dummy')
    w.nts = [Y, X]
    w.chain(Y, X, [2], name='YX')
    # 临时进料路：一个只有一格的元件，末格停着 1 件蓝铁粉末，没有上游
    tmp = Element('tmp', 1)
    tmp.dst = Y
    Y.in_routes.append(tmp)
    Y.in_rank[tmp] = 0
    w.elements.append(tmp)
    w.finalize()
    Y.inp = [[IB, 1]]
    tmp.cells = [[IP, -20]]
    for t in range(5):
        w.step()
    pre = (Y.inp, Y.cache, tmp.cells)
    Y.on = True
    log = []
    for t in range(30):
        w.step()
        log.append((w.t - 1, [list(c) for c in Y.inp], Y.cache, Y.out, X.cache))
    return dict(before_on=str(pre), log=[str(x) for x in log[:12]], final=str(log[-1]))


def build_x(rng, kind):
    """随机构造 X 及其专用进路来源。进路由连续带段与单格元件（不设上限的物品准入口）混合组成。"""
    w = World()
    nts = []
    rank = [0]

    def nr():
        rank[0] += 1
        return rng.randrange(10**6)

    def route_lengths():
        segs = []
        for _ in range(rng.randint(1, 3)):
            if rng.random() < 0.4:
                segs.append(1)  # 单格元件（准入口）
            else:
                segs.append(rng.randint(1, 4))
        return segs

    def feeder(prod):
        """1 tick 配方的来源机 Y，自身存货由无限源经一条带补给；或直接用仓库取货口（矿）。"""
        if prod == IP:
            Y = Machine(f'Y{rank[0]}', CRUSHER, 1, rank=nr()); mat = IB; mq = {IB: 1}
        elif prod == SP:
            Y = Machine(f'Y{rank[0]}', CRUSHER, 1, rank=nr()); mat = SL
        elif prod == PART:
            Y = Machine(f'Y{rank[0]}', PARTS, 1, rank=nr()); mat = ST
        elif prod == ST:
            Y = Machine(f'Y{rank[0]}', REFINER, 1, rank=nr()); mat = DIP
        else:
            raise ValueError(prod)
        src = Source(f'src{rank[0]}', mat, rank=nr())
        nts.extend([Y, src])
        w.chain(src, Y, [rng.randint(1, 3)], ranks=[nr()], name=f'in{rank[0]}')
        Y.inp = [[mat, rng.randint(1, 50)]]
        r = rng.random()
        if r < 0.3:
            Y.cache = None
        elif r < 0.7:
            Y.cache = ('run', rng.randint(1, 8), prod, Y.recipes[[x[1] for x in Y.recipes].index(prod)][2])
        else:
            Y.cache = ('done', prod, Y.recipes[[x[1] for x in Y.recipes].index(prod)][2])
        if rng.random() < 0.5:
            Y.out = [prod, rng.randint(1, 40)]
        return Y

    if kind == 'refiner':
        X = Machine('X', REFINER, 1, rank=nr()); mats = {IP: 1}; d = 1
    elif kind == 'grinder':
        X = Machine('X', GRINDER, 2, rank=nr()); mats = {IP: 2, SP: 1}; d = 1
    elif kind == 'packer':
        X = Machine('X', PACKER, 2, rank=nr()); mats = {PART: 10, DSO: 15}; d = 5
    nts.append(X)
    routes = []
    for m, a in mats.items():
        cmin = -(-a // d)
        c = rng.randint(cmin, cmin + 1)
        for j in range(c):
            if m == DSO:
                # 致密源石粉末来源：研磨机（1 tick），自身两种原料各一条无限源
                Y = Machine(f'Yg{rank[0]}', GRINDER, 2, rank=nr())
                s1 = Source(f'sa{rank[0]}', SOP, rank=nr()); s2 = Source(f'sb{rank[0]}', SP, rank=nr())
                nts.extend([Y, s1, s2])
                w.chain(s1, Y, [rng.randint(1, 3)], ranks=[nr()], name=f'ga{rank[0]}')
                s1b = Source(f'sa2{rank[0]}', SOP, rank=nr()); nts.append(s1b)
                w.chain(s1b, Y, [rng.randint(1, 3)], ranks=[nr()], name=f'ga2{rank[0]}')
                w.chain(s2, Y, [rng.randint(1, 3)], ranks=[nr()], name=f'gb{rank[0]}')
                Y.inp = [[SOP, rng.randint(2, 50)], [SP, rng.randint(1, 50)]]
                Y.cache = ('run', rng.randint(1, 8), DSO, 1)
                src = Y
            else:
                src = feeder(m)
            segs = route_lengths()
            routes.append(w.chain(src, X, segs, ranks=[nr() for _ in segs], out_rank=0,
                                  in_rank=nr(), name=f'R{m}{j}'))
    # X 初态：随机原料、缓存
    X.inp = []
    for m in mats:
        if rng.random() < 0.7:
            X.inp.append([m, rng.randint(1, 50)])
    r = rng.random()
    prod = X.recipes[[tuple(sorted(x[0].items())) for x in X.recipes].index(tuple(sorted(mats.items())))]
    if r < 0.4:
        X.cache = None
    elif r < 0.7:
        X.cache = ('run', rng.randint(1, 8 * d), prod[1], prod[2])
    else:
        X.cache = ('done', prod[1], prod[2])
    # X 下游：一条或多条取货通道到汇点，汇点随机停收（含长时间停收后恢复）或周期收
    nout = 1 if rng.random() < 0.6 else rng.randint(2, 3)
    sinks = []
    for j in range(nout):
        mode = rng.randrange(3)
        if mode == 0:
            pat = lambda t: True
        elif mode == 1:
            per = rng.randint(1, 20); ph = rng.randrange(per)
            pat = lambda t, per=per, ph=ph: t % per == ph
        else:
            stop0 = rng.randint(0, 2000); stop1 = stop0 + rng.randint(0, 3000)
            pat = lambda t, a=stop0, b=stop1: not (a <= t < b)
        sk = Sink(f'Z{j}', pat)
        w.chain(X, sk, [rng.randint(1, 3)], ranks=[nr()], out_rank=nr(), name=f'XZ{j}')
        sinks.append(sk)
    for e in w.elements:
        for i in range(len(e.cells)):
            if rng.random() < 0.3 and e.cells[i] is None:
                pass
    w.nts = nts
    w.finalize()
    return w, X, d, nout, [u for u in nts if isinstance(u, Machine) and u is not X]


def random_revised(nrun, steps, seed, warm):
    rng = random.Random(seed)
    res = dict(runs=0, skipped_Y_premise=0, X_empty_after_warm=0, examples=[],
               single_out_d1=0, refill_viol=0, last_empty_step=[])
    for r in range(nrun):
        kind = rng.choice(['refiner', 'grinder', 'packer'])
        w, X, d, nout, Ys = build_x(rng, kind)
        empt = []
        yviol = False
        # 即时补货：X 唯一取货通道首格在元件阶段空出后，同步由 X 补入
        xfirst = X.out_routes[0] if nout == 1 else None
        rv = 0
        for t in range(steps):
            if xfirst is not None:
                before_full = not xfirst.first_empty()
            w.step()
            if t >= warm:
                if X.cache is None:
                    empt.append(t)
                for Y in Ys:
                    if Y.cache is None:
                        yviol = True
                if xfirst is not None and d == 1:
                    # 步末首格应满（一旦首次收到货）
                    if xfirst.first_empty():
                        rv += 1
        if yviol:
            res['skipped_Y_premise'] += 1
            continue
        res['runs'] += 1
        res.setdefault('by_kind', {}).setdefault(kind, 0)
        res['by_kind'][kind] += 1
        if empt:
            res['X_empty_after_warm'] += 1
            if len(res['examples']) < 5:
                res['examples'].append(dict(r=r, kind=kind, n=len(empt), first=empt[:5]))
        if xfirst is not None and d == 1:
            res['single_out_d1'] += 1
            if rv:
                res['refill_viol'] += 1
    return res


if __name__ == '__main__':
    out = dict(counterexample=counterexample(), reach=counterexample_reach())
    print(out['counterexample'])
    print(out['reach']['final'])
    out['random'] = random_revised(600, 9000, 21, warm=5500)
    print(out['random'], flush=True)
    out['random2'] = random_revised(300, 9000, 22, warm=5500)
    print(out['random2'])
    json.dump(out, open('s10.json', 'w'), ensure_ascii=False, indent=1, default=str)
