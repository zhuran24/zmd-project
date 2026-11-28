"""第二席独立复核「接通先后」修正版的两个算例，另加一例多格带子在离线重建中的带端重接。
坐标 x 向右、y 向下；方向 0北 1东 2南 3西，顺时针递增。
端口顺序照规则第 25-28 行：先存后取；分流器取货口/汇流器存货口从唯一异类口顺时针。
带端重接照 Lean 模型 格子/场地与建造.lean 的「重接通道」：建成一格带时，
沿上游、下游各走到带端，把带端原有的那条通道移到表尾。
"""
from itertools import permutations, combinations

V = [(0, -1), (1, 0), (0, 1), (-1, 0)]


def split(x, y, i):
    return dict(pos=(x, y), belt=False,
                ports=[(i, 'in')] + [((i + k) % 4, 'out') for k in (1, 2, 3)])


def merge(x, y, o):
    return dict(pos=(x, y), belt=False,
                ports=[((o + k) % 4, 'in') for k in (1, 2, 3)] + [(o, 'out')])


def belt(x, y, i, o):
    return dict(pos=(x, y), belt=True, ports=[(i, 'in'), (o, 'out')])


def at(L, built, cell):
    for n in built:
        if L[n]['pos'] == cell:
            return n
    return None


def new_channels(L, built, n):
    u = L[n]
    res = []
    for side, kind in u['ports']:
        dx, dy = V[side]
        m = at(L, built, (u['pos'][0] + dx, u['pos'][1] + dy))
        if m is None:
            continue
        want = 'in' if kind == 'out' else 'out'
        if ((side + 2) % 4, want) in L[m]['ports'] and (u['belt'] is False or True):
            res.append((n, m) if kind == 'out' else (m, n))
    return res


def belt_next(L, built, n, down):
    u = L[n]
    side = u['ports'][1][0] if down else u['ports'][0][0]
    dx, dy = V[side]
    m = at(L, built, (u['pos'][0] + dx, u['pos'][1] + dy))
    if m is None or not L[m]['belt']:
        return None
    ms = L[m]['ports'][0][0] if down else L[m]['ports'][1][0]
    return m if ms == (side + 2) % 4 else None


def rebuild(L, order, reconnect):
    built, table = [], []
    for n in order:
        table += new_channels(L, built, n)
        if reconnect and L[n]['belt']:
            for down in (False, True):
                m = belt_next(L, built, n, down)
                if m is None:
                    continue
                while True:
                    k = belt_next(L, built, m, down)
                    if k is None:
                        break
                    m = k
                for c in list(table):
                    if (down and c[0] == m) or (not down and c[1] == m):
                        if n not in c:
                            table.remove(c)
                            table.append(c)
        built.append(n)
    return tuple(table)


def bp_ok(L, order):
    f = [L[n]['belt'] for n in order]
    return f == sorted(f)


star = dict(P=split(0, 0, 0), E=split(1, 0, 3), S=belt(0, 1, 0, 2), W=belt(-1, 0, 1, 3))
for lab, cond in [('同图', lambda o: bp_ok(star, o)), ('离线', lambda o: True),
                  ('P最后', lambda o: o[-1] == 'P')]:
    os_ = [o for o in permutations(star) if cond(o)]
    outs = {tuple(c for c in rebuild(star, o, True) if c[0] == 'P') for o in os_}
    print('三出口', lab, len(os_), len(outs), sorted(outs))

sq = dict(A=split(0, 0, 0), B=split(1, 0, 3), D=split(0, 1, 0), C=merge(1, 1, 1))
res = {rebuild(sq, o, True) for o in permutations(sq)}
edges = sorted(res.pop() if False else next(iter(res)))
pairs = list(combinations(edges, 2))
rev = sum(len({s.index(a) < s.index(b) for s in res}) == 2 for a, b in pairs)
print('两支汇合 通道', edges, '可达序', len(res), '全排列 24', '可反序对', rev, '/', len(pairs))
print('  末两位为 AB、DC 的', sum(set(s[-2:]) == {('A', 'B'), ('D', 'C')} for s in res))

# 多格带：b1 -> b2 -> 汇流器 M（M 取货口朝东，b2 从西进）
chain = dict(M=merge(2, 0, 1), b1=belt(0, 0, 3, 1), b2=belt(1, 0, 3, 1))
diff = 0
for o in permutations(chain):
    a, b = rebuild(chain, o, False), rebuild(chain, o, True)
    if a != b:
        diff += 1
        print('  带端重接改序：单位序', o, '不重接', a, '模型', b)
print('多格带 6 种单位序中重接改变通道序的', diff)
