"""复核97M：用本席 stepsim 核 §6（含桥接器交叉的反例）、§7、§8、§9。只写 dyn_checks.json。"""
import json, random, itertools, sys
from fractions import Fraction as Fr
from pathlib import Path
from stepsim import Elem, Source, Sink, Machine, World, Item
OUT = Path(__file__).resolve().parent
res = {}

# ---------------- §7 分流先判的首段带容量 ----------------
def splitter_case(n, pattern=None, steps=4000, s_first=True, side=lambda t: False):
    src = Source('src', 'x')
    inb = Elem('in', 1)
    S = Elem('S', 1, splitter=True)
    B = Elem('B', n)
    C = Elem('C', 1)
    D = Elem('D', 1); E = Elem('E', 1)
    k1 = Sink('k1', pattern or (lambda t: True)); k2 = Sink('k2', side); k3 = Sink('k3', side)
    units = [src, inb, S, B, C, D, E, k1, k2, k3]
    w = World(units)
    w.connect(src, inb); w.connect(inb, S)
    w.connect(S, D); w.connect(S, B); w.connect(S, E)
    w.connect(B, C); w.connect(C, k1); w.connect(D, k2); w.connect(E, k3)
    order = ([C, D, E, S, B, inb] if s_first else [C, D, E, B, S, inb]) + [src, k1, k2, k3]
    occ = []
    for _ in range(steps):
        w.step(order)
        occ.append(sum(c is not None for c in B.cells))
    # B 末格出货 = 进入 C 的件数：用 C 的收件近似（C 只从 B 收）
    return w, k1, occ, k2, k3, src

rows = []
for n in (1, 2, 3, 4, 6, 8):
    bound = Fr(8*n, 8*n+1)
    w, k1, occ, k2, k3, src = splitter_case(n, steps=2000+8*(8*n+1)*20)
    got = [t for t, _ in k1.got if t >= 2000]
    rate = Fr(len(got)*8, 8*(8*n+1)*20)
    rows.append(dict(n=n, case='其他支堵死', rate=str(rate), bound=str(bound), ok=rate <= bound))
    w, k1, occ, k2, k3, src = splitter_case(n, steps=2000+8*(8*n+1)*20, side=lambda t: True)
    span = 8*(8*n+1)*20
    got = [t for t, _ in k1.got if t >= 2000]
    oth = [t for t, _ in k2.got + k3.got if t >= 2000]
    rows.append(dict(n=n, case='其他支常收', B=str(Fr(len(got)*8, span)), others=str(Fr(len(oth)*8, span)), bound=str(bound),
                     ok=Fr(len(got)*8, span) <= bound + Fr(8, span) and (len(got)+len(oth)) * 8 / span > 0.99 and Fr(len(oth)*8, span) >= Fr(1, 8*n+1) - Fr(8, span)))
    # 随机阻断下游
    for seed in range(5):
        rnd = random.Random(seed*100+n)
        pat = {t: rnd.random() < 0.8 for t in range(6000)}
        w, k1, occ, k2, k3, src = splitter_case(n, lambda t, p=pat: p[t], steps=6000)
        got = [t for t, _ in k1.got if t >= 1000]
        rate = Fr(len(got)*8, 5000)
        rows.append(dict(n=n, seed=seed, rate=str(rate), bound=str(bound), ok=rate <= bound + Fr(8, 5000)))
res['§7'] = rows
assert all(r['ok'] for r in rows)
# 对照：B 先判时可满速
w, k1, occ, k2, k3, src = splitter_case(1, s_first=False)
res['§7对照B先判n=1'] = str(Fr(len([t for t, _ in k1.got if t >= 2000])*8, 2000))

# ---------------- §8 研磨单路换主料 ----------------
class SeqSource(Source):
    def __init__(self, name, seq):
        super().__init__(name, None); self.seq = seq; self.i = 0
    def ready(self, t): return Item(self.seq[self.i % len(self.seq)], t)
    def pop(self): self.i += 1

def grinder(seq, two_main=False, steps=3000):
    rec = [({'a': 2, 's': 1}, 'A', 1, 8), ({'b': 2, 's': 1}, 'B', 1, 8)]
    G = Machine('G', rec, slots=2)
    units = [G]
    w = World(units)
    if not two_main:
        sm = SeqSource('sm', seq); bm = Elem('bm', 1); units += [sm, bm]
        w.units = units
    else:
        sa = Source('sa', 'a'); sb = Source('sb', 'b'); ba = Elem('ba', 1); bb = Elem('bb', 1); units += [sa, sb, ba, bb]
    ss = Source('ss', 's'); bs = Elem('bs', 1); out = Elem('out', 1); k = Sink('k')
    units += [ss, bs, out, k]
    w = World(units)
    if not two_main:
        w.connect(sm, bm); w.connect(bm, G)
    else:
        w.connect(sa, ba); w.connect(ba, G); w.connect(sb, bb); w.connect(bb, G)
    w.connect(ss, bs); w.connect(bs, G); w.connect(G, out); w.connect(out, k)
    for _ in range(steps): w.step()
    st = G.starts
    gaps = [(b[0]-a[0], a[1] != b[1]) for a, b in zip(st, st[1:])]
    return gaps

g1 = grinder(['a', 'a', 'b', 'b'])
sw = [g for g, d in g1 if d]
res['§8单路混送稳态换料间隔最小'] = min(sw)
assert min(sw) >= 9

def switch_gap(nb, steps=200):
    """研磨机开始时 a 格 4 件、砂叶格 50 件；b 只经 nb 条通道进入，各通道末格已有成熟 b。返回各次开批时刻。"""
    rec = [({'a': 2, 's': 1}, 'A', 1, 8), ({'b': 2, 's': 1}, 'B', 1, 8)]
    G = Machine('G', rec, slots=2)
    G.slots[0] = ['a']*4; G.slots[1] = ['s']*50
    units = [G]; srcs = []; belts = []
    for i in range(nb):
        sb = Source(f'sb{i}', 'b'); bb = Elem(f'bb{i}', 3)
        bb.cells = [Item('b', -8), Item('b', -8), Item('b', -8)]
        srcs.append(sb); belts.append(bb)
    out = Elem('out', 1); k = Sink('k')
    w = World(units + srcs + belts + [out, k])
    for sb, bb in zip(srcs, belts):
        w.connect(sb, bb); w.connect(bb, G)
    w.connect(G, out); w.connect(out, k)
    for _ in range(steps): w.step()
    return G.starts[:6]
st1 = switch_gap(1); st2 = switch_gap(2)
res['§8单路换料开批时刻'] = st1; res['§8两路换料开批时刻'] = st2
gap1 = [b[0]-a[0] for a, b in zip(st1, st1[1:]) if a[1] != b[1]]
gap2 = [b[0]-a[0] for a, b in zip(st2, st2[1:]) if a[1] != b[1]]
assert gap1 == [9] and gap2 == [8], (st1, st2)
# 周期账：N=32、W 与 a 的整数核对（两种写法）
from fractions import Fraction as F
for N in (32, 33):
    Wmax_A = 8*(N - F(63, 2))
    Wmax_B = (8*N - 252)               # 每 tick：(NK-8B)/(K/8)，8B=31.5K -> 8N-252
    assert Wmax_A == Wmax_B
    amax = max(a for a in range(0, N+1) if (N - a) + F(8, 9)*a >= F(63, 2))
    res[f'§8 N={N}'] = dict(W每tick上限=str(Wmax_A), a上限=amax)
assert res['§8 N=32'] == dict(W每tick上限='4', a上限=4) and res['§8 N=33']['a上限'] == 13

# ---------------- §6 纯带传递与桥接器交叉 ----------------
def pure_chain(n, steps=3000):
    src = Source('ore', 'o'); belt = Elem('E', n)
    X = Machine('X', [({'o': 1}, 'p', 1, 8)])
    ob = Elem('ob', 2); k = Sink('k')
    w = World([src, belt, X, ob, k])
    w.connect(src, belt); w.connect(belt, X); w.connect(X, ob); w.connect(ob, k)
    for _ in range(steps): w.step()
    return X.cache_empty_steps

ok6 = {}
for n in (1, 2, 5, 9):
    ce = pure_chain(n)
    ok6[n] = sum(ce[500:])
assert all(v == 0 for v in ok6.values())
res['§6纯带缓存空步数(热身后)'] = ok6

def crossing(mode, slow=9, steps=6000):
    """R1: Y1->E1->K.h->E2->K2.h->E3->X1 ；R2: Y2->F1->K.v->F2->X2(每 slow 步才收一件)。"""
    Y1 = Source('Y1', 'o'); Y2 = Source('Y2', 'q')
    E1 = Elem('E1', 2); Kh = Elem('K.h', 1, unit='K'); E2 = Elem('E2', 2); K2h = Elem('K2.h', 1, unit='K2'); E3 = Elem('E3', 2)
    F1 = Elem('F1', 2); Kv = Elem('K.v', 1, unit='K'); F2 = Elem('F2', 2)
    X1 = Machine('X1', [({'o': 1}, 'p', 1, 8)]); ob = Elem('ob', 1); k1 = Sink('k1')
    k2 = Sink('k2', lambda t: t % slow == 0)
    units = [Y1, Y2, E1, Kh, E2, K2h, E3, F1, Kv, F2, X1, ob, k1, k2]
    w = World(units, unit_mode=mode)
    w.connect(Y1, E1); w.connect(E1, Kh); w.connect(Kh, E2); w.connect(E2, K2h); w.connect(K2h, E3); w.connect(E3, X1)
    w.connect(X1, ob); w.connect(ob, k1)
    w.connect(Y2, F1); w.connect(F1, Kv); w.connect(Kv, F2); w.connect(F2, k2)
    L = w.layers()
    for _ in range(steps): w.step()
    ce = X1.cache_empty_steps[1000:]
    got = [t for t, _ in k1.got if t >= 1000]
    return dict(layers={e.name: L[e] for e in w.elems}, cache_empty_steps=sum(ce), steps=len(ce),
                X1_rate=str(Fr(len(got)*8, steps-1000)))
cx = {}
for mode in ('axis', 'unit'):
    for slow in (9, 1000000):
        cx[f'{mode},X2每{slow}步收一件'] = crossing(mode, slow)
res['§6桥接器交叉'] = cx

# ---------------- §9 随机无分流网络换序 ----------------
def random_net(rnd):
    units = []
    nsrc = rnd.randint(1, 3); nmach = rnd.randint(1, 3); nsink = rnd.randint(1, 3)
    srcs = [Source(f's{i}', rnd.choice('ab')) for i in range(nsrc)]
    machs = [Machine(f'm{i}', [({'a': 1}, 'c', rnd.choice([1, 2]), 8), ({'b': 1}, 'd', 1, 8), ({'c': 1}, 'a', 1, 8)], slots=rnd.choice([1, 2])) for i in range(nmach)]
    sinks = [Sink(f'k{i}', (lambda t, p=rnd.random(), sd=rnd.randint(0, 10**6): (hash((t, sd)) % 1000) < p*1000)) for i in range(nsink)]
    receivers = machs + sinks
    elems = []
    # 树状：从收货端往上长元件
    frontier = []
    for R in receivers:
        for _ in range(rnd.randint(1, 3)):
            frontier.append(R)
    conns = []
    count = 0
    while frontier and count < 14:
        R = frontier.pop(rnd.randrange(len(frontier)))
        kind = rnd.choice(['belt', 'belt', 'gate', 'merger', 'bridge'])
        n = rnd.randint(1, 3) if kind == 'belt' else 1
        e = Elem(f'e{count}', n, unit=(f'B{count}' if kind == 'bridge' else None)); e.kind = kind
        count += 1
        elems.append(e); conns.append((e, R))
        # 上游：合流器 1-3 个，其他 1 个；上游可以是元件（继续长）或非运输单位
        nin = rnd.randint(1, 3) if kind == 'merger' else 1
        for _ in range(nin):
            if rnd.random() < 0.45 and count < 14:
                frontier.append(e)
            else:
                src = rnd.choice(srcs + machs)
                if src is R: continue
                # 每个运输单位至多一个非运输来源
                if any(c[1] is e and not c[0].transport for c in conns): continue
                conns.append((src, e))
    units = srcs + machs + sinks + elems
    w = World(units)
    rnd.shuffle(conns)
    used = set()
    for a, b in conns:
        if (a, b) in used: continue
        used.add((a, b)); w.connect(a, b)
    # 有元件送入的元件都有出口（构造保证）；随机初始物品
    for e in elems:
        for j in range(len(e.cells)):
            if rnd.random() < 0.5:
                e.cells[j] = Item(rnd.choice('abcd'), -rnd.randint(0, 9), None)
    for m in machs:
        for s in m.slots:
            if rnd.random() < 0.5: s.extend([rnd.choice('abc')]*rnd.randint(1, 3))
        if rnd.random() < 0.5: m.out = ['c']*rnd.randint(1, 5)
    return w

def same_layer_orders(w, rnd, k):
    L = w.layers()
    es = sorted(w.elems, key=lambda e: L[e])
    groups = {}
    for e in es: groups.setdefault(L[e], []).append(e)
    out = []
    for _ in range(k):
        o = []
        for l in sorted(groups):
            g = groups[l][:]; rnd.shuffle(g); o += g
        ns = w.nts[:]; rnd.shuffle(ns)
        out.append(o + ns)
    return out

import copy
mism = 0; tested = 0; checks = 0
for seed in range(400):
    rnd = random.Random(seed)
    w = random_net(rnd)
    # 热身若干步（默认次序）
    for _ in range(rnd.randint(0, 30)): w.step()
    for trial in range(3):
        base = None
        for o in same_layer_orders(w, rnd, 6):
            cc = w.conn; w.conn = None; w2 = copy.deepcopy(w); w.conn = cc
            # deepcopy 后次序对象要映射
            names = {u.name: u for u in w2.units}
            o2 = [names[u.name] for u in o]
            snaps = []
            for _ in range(3):
                w2.step(o2); snaps.append(w2.snapshot())
            if base is None: base = snaps
            else:
                checks += 1
                if snaps != base: mism += 1
        w.step()
    tested += 1
res['§9随机网络'] = dict(networks=tested, comparisons=checks, mismatches=mism)

# 结构外对照：死路例（G->D 两格无出口）与双轴桥接器在“按单位”读法下
def deadend(order_first):
    s = Source('s', 'a'); G = Elem('G', 1); Dd = Elem('D', 2); k = Sink('k')
    w = World([s, G, Dd, k])
    w.connect(s, G); w.connect(G, Dd)
    G.cells[0] = Item('a', -8); Dd.cells[0] = Item('a', -8)
    o = ([Dd, G] if order_first == 'D' else [G, Dd]) + [s, k]
    w.step(o); return w.snapshot()
res['§9死路例(本模拟为始终前移读法)'] = deadend('D') == deadend('G')

(OUT/'dyn_checks.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str)+'\n')
print(json.dumps({k: v for k, v in res.items() if k != '§7'}, ensure_ascii=False, default=str))
print('§7 rows ok', all(r['ok'] for r in res['§7']), [r for r in res['§7'] if 'seed' not in r])
