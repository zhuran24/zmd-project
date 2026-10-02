"""复核97M：§6 纯带传递的随机核对（多路、多原料、制造来源 Y、出口首格同步补入）。只写 dyn6.json。"""
import json, random
from pathlib import Path
from stepsim import Elem, Source, Sink, Machine, World, Item
OUT = Path(__file__).resolve().parent

class Probe(Elem):
    """记录首格被送走与被补入的步。"""
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.left = []; self.filled = []; self.world = None
    def pop(self):
        super().pop()
    def settle(self, t):
        before = self.cells[0]
        super().settle(t)
        if before is not None and self.cells[0] is None: self.left.append(t)
    def put(self, item, t):
        super().put(item, t); self.filled.append(t)

def case(rnd):
    # X：研磨类 2a+1s，d=1；a 两路（c_a=2，d*c_a>=a_a），s 一路
    X = Machine('X', [({'a': 2, 's': 1}, 'P', 1, 8)], slots=2)
    units = [X]; w = None
    routes = []
    for kind, nroute in (('a', 2), ('s', 1)):
        for i in range(nroute):
            if rnd.random() < 0.5:
                src = Source(f'src_{kind}{i}', kind)   # 仓库取货口（持续可得）
                pre = []
            else:
                feed = Source(f'feed_{kind}{i}', 'raw' + kind)
                fb = Elem(f'fb_{kind}{i}', rnd.randint(1, 3))
                src = Machine(f'Y_{kind}{i}', [({'raw' + kind: 1}, kind, rnd.choice([1, 2, 3]), 8)])
                pre = [feed, fb]
            belt = Elem(f'r_{kind}{i}', rnd.randint(1, 6))
            routes.append((src, pre, belt))
            units += [src, belt] + pre
    first = Probe('first', rnd.randint(1, 3)); k = Sink('k', (lambda t, p=rnd.random()*0.7+0.3, sd=rnd.randint(0, 10**6): (hash((t, sd)) % 1000) < p*1000))
    units += [first, k]
    w = World(units)
    for src, pre, belt in routes:
        if pre:
            feed, fb = pre
            w.connect(feed, fb); w.connect(fb, src)
        w.connect(src, belt); w.connect(belt, X)
    w.connect(X, first); w.connect(first, k)
    # 随机初态：路上随机放本线物品
    for src, pre, belt in routes:
        kind = 'a' if 'a' in belt.name else 's'
        for j in range(len(belt.cells)):
            if rnd.random() < 0.5: belt.cells[j] = Item(kind, -rnd.randint(0, 9))
    for _ in range(3000): w.step()
    ce = X.cache_empty_steps[1500:]
    # 首格：出口元件末格送走的步 = first.cells[-1] 被 pop；用 first 的收件日志判断同步补入
    return sum(ce), first

res = []
for seed in range(200):
    rnd = random.Random(seed)
    ce, first = case(rnd)
    res.append(ce)
bad = [i for i, v in enumerate(res) if v]
out = dict(cases=len(res), cases_with_empty_cache=len(bad), first_bad=bad[:5])

# 出口首格同步补入：X 单配方 1 tick、唯一出口首格为一格传送带
def out_case(seed):
    rnd = random.Random(seed)
    X = Machine('X', [({'o': 1}, 'p', rnd.choice([1, 2, 3]), 8)])
    src = Source('ore', 'o'); r = Elem('r', rnd.randint(1, 4))
    f = Elem('f', 1); nxt = Elem('n', 1)
    k = Sink('k', (lambda t, p=rnd.random()*0.7+0.3, sd=seed: (hash((t, sd)) % 1000) < p*1000))
    w = World([X, src, r, f, nxt, k])
    w.connect(src, r); w.connect(r, X); w.connect(X, f); w.connect(f, nxt); w.connect(nxt, k)
    leave, fill = [], []
    for _ in range(3000):
        before = f.cells[0]
        w.step()
        after = f.cells[0]
        # 本步 f 是否送走过：前后物品对象不同或变空
        if before is not None and after is not before: leave.append(w.t-1)
        if after is not None and after is not before: fill.append(w.t-1)
    leave = [t for t in leave if t >= 1000]; fill = [t for t in fill if t >= 1000]
    empty_end = 0
    return leave == fill
oc = [out_case(s) for s in range(100)]
out['出口首格同步补入成立例数'] = sum(oc); out['出口例数'] = len(oc)
(OUT/'dyn6.json').write_text(json.dumps(out, ensure_ascii=False, indent=1)+'\n')
print(json.dumps(out, ensure_ascii=False))
