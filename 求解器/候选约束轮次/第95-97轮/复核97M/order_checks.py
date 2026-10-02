"""复核97M：§1、§2 的接通先后由单位建造次序导出的小核对（两种编码）。只写 order_checks.json。"""
import itertools, json, random
from pathlib import Path
OUT = Path(__file__).resolve().parent
res = {}
# 编码 A：通道接通时刻 = 两端单位建成时刻的较晚者；编码 B：逐个建造，建成时扫描新形成的通道
def times_A(order, chans):
    pos = {u: i for i, u in enumerate(order)}
    return {c: max(pos[c[0]], pos[c[1]]) for c in chans}
def times_B(order, chans):
    built, t = set(), {}
    for i, u in enumerate(order):
        built.add(u)
        for c in chans:
            if c not in t and c[0] in built and c[1] in built: t[c] = i
    return t
# §1：三个两两相邻的单位，三条通道；由建造次序能得到的严格先后
chans = [('U1', 'U2'), ('U2', 'U3'), ('U1', 'U3')]
strict = set(); tied = 0
for order in itertools.permutations(['U1', 'U2', 'U3']):
    ta, tb = times_A(order, chans), times_B(order, chans)
    assert ta == tb
    vals = sorted(ta.values())
    if len(set(vals)) < 3: tied += 1
    else: strict.add(tuple(sorted(chans, key=lambda c: ta[c])))
res['§1三角'] = dict(建造次序数=6, 含同刻接通的次序数=tied, 严格全序数=len(strict), 通道全排列数=6)
# §2：M 的两级，低级 kL 条、高级 kH 条通道，各接不同运输单位；另加若干无关单位
cases = []
for kL, kH, extra in [(1, 1, 1), (2, 1, 1), (1, 3, 0), (3, 2, 0), (2, 2, 1)]:
    VL = [f'VL{i}' for i in range(kL)]; VH = [f'VH{i}' for i in range(kH)]
    others = [f'Z{i}' for i in range(extra)]
    units = ['M'] + VL + VH + others
    ch = [('M', v) for v in VL + VH]
    both = {'低先': False, '高先': False}
    for order in itertools.permutations(units):
        ta, tb = times_A(order, ch), times_B(order, ch)
        assert ta == tb
        cL = min(ta[('M', v)] for v in VL); cH = min(ta[('M', v)] for v in VH)
        if cL < cH: both['低先'] = True
        if cH < cL: both['高先'] = True
    cases.append(dict(kL=kL, kH=kH, extra=extra, **both))
assert all(c['低先'] and c['高先'] for c in cases)
res['§2两级先后'] = cases
(OUT/'order_checks.json').write_text(json.dumps(res, ensure_ascii=False, indent=1)+'\n')
print(json.dumps(res, ensure_ascii=False))
