"""复核97M：接通先后的可实现集合（§1、§2 及正式「接通先后」抽查），本席独立编码。
通道在两端单位都建成时形成；同一单位建成时一起形成的通道记同刻，同刻先后按规则未定、逐一展开。
编码 A：按单位建造排列取「两端建成序号最大值」为接通时刻。
编码 B：逐个建造单位，每建一个就把新相遇的通道作为一个同刻组追加。
"""
import itertools, json
from pathlib import Path
OUT = Path(__file__).resolve().parent


def orders_A(units, chans):
    strict, with_ties = set(), set()
    for perm in itertools.permutations(units):
        pos = {u: i for i, u in enumerate(perm)}
        t = {c: max(pos[c[0]], pos[c[1]]) for c in chans}
        if len(set(t.values())) == len(chans):
            strict.add(tuple(sorted(chans, key=t.get)))
        groups = {}
        for c in chans:
            groups.setdefault(t[c], []).append(c)
        keys = sorted(groups)
        for combo in itertools.product(*[list(itertools.permutations(groups[k])) for k in keys]):
            with_ties.add(tuple(c for g in combo for c in g))
    return strict, with_ties


def orders_B(units, chans):
    strict, with_ties = set(), set()
    for perm in itertools.permutations(units):
        built, seq = set(), []
        for u in perm:
            built.add(u)
            new = [c for c in chans if u in c and c[0] in built and c[1] in built]
            seq.append(new)
        seq = [g for g in seq if g]
        if all(len(g) == 1 for g in seq):
            strict.add(tuple(g[0] for g in seq))
        for combo in itertools.product(*[list(itertools.permutations(g)) for g in seq]):
            with_ties.add(tuple(c for g in combo for c in g))
    return strict, with_ties


cases = {
    '三角 X-Y-Z': (['X', 'Y', 'Z'], [('X', 'Y'), ('Y', 'Z'), ('X', 'Z')]),
    '四环 A-B-D-C-A': (['A', 'B', 'C', 'D'], [('A', 'B'), ('B', 'D'), ('C', 'D'), ('A', 'C')]),
    '链 X-Y-Z-W': (['X', 'Y', 'Z', 'W'], [('X', 'Y'), ('Y', 'Z'), ('Z', 'W')]),
}
res = {}
for name, (u, c) in cases.items():
    sA, tA = orders_A(u, c)
    sB, tB = orders_B(u, c)
    assert sA == sB and tA == tB, name
    allp = set(itertools.permutations(c))
    missing = sorted(allp - tA)
    res[name] = dict(通道全排列=len(allp), 无同刻可实现=len(sA), 同刻任意拆开后可实现=len(tA),
                     不可实现例=['<'.join(a + b for a, b in m) for m in missing[:4]])

# §2：源单位 M，低级一条通道接 V低，高级 k 条通道各接 V高i；问能否严格让低级最早通道先于高级全部通道，及反之
sec2 = []
for kL in (1, 2, 3):
    for kH in (1, 2, 3):
        units = ['M'] + [f'L{i}' for i in range(kL)] + [f'H{i}' for i in range(kH)]
        chans = [('M', f'L{i}') for i in range(kL)] + [('M', f'H{i}') for i in range(kH)]
        low_first = high_first = False
        for perm in itertools.permutations(units):
            pos = {x: i for i, x in enumerate(perm)}
            t = {c: max(pos[c[0]], pos[c[1]]) for c in chans}
            cL = min(t[c] for c in chans if c[1][0] == 'L')
            cH = min(t[c] for c in chans if c[1][0] == 'H')
            low_first |= cL < cH
            high_first |= cH < cL
        sec2.append(dict(kL=kL, kH=kH, 低级可严格先接通=low_first, 高级可严格先接通=high_first))
res['§2两级最早接通'] = sec2
(OUT / 'orders2.json').write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n')
print(json.dumps(res, ensure_ascii=False))
