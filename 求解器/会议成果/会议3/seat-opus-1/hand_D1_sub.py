"""手摆一张 D1 布局，用同一套格状态、自动通道与母图线性规划核它是否流量可行（证明 D1 本身可行）。"""
from toy import *
from fulllp import FullLP
inst = make_inst('D1')
M = Master(inst, subsets=True)
m = M.m
def find_pl(k, fp, inx):
    for i, p in enumerate(inst.pl):
        if p['type'] == k and p['fp'][:4] == fp and p['ins'] and p['ins'][0][0][0] == inx:
            return i
    raise KeyError((k, fp))
# crusher in-side W (s=2): fp (ax,ay,3,3); grinder 4x6 in-side W
want = {find_pl('crush', (2, 1, 3, 3), 1), find_pl('crush', (2, 4, 3, 3), 1), find_pl('crush', (2, 7, 3, 3), 1),
        find_pl('grind', (6, 2, 4, 6), 5)}
# check orientation: the crusher placements found must have ins at x=1
for i in want:
    print(inst.pl[i]['type'], inst.pl[i]['fp'], 'ins', inst.pl[i]['ins'][:2], 'outs', inst.pl[i]['outs'][:2])
belts = {(1, 2): ('B', 2, 0), (1, 5): ('B', 2, 0), (1, 8): ('B', 2, 0)}
for y in range(2, 8):
    belts[(5, y)] = ('B', 2, 0)
belts[(10, 7)] = ('B', 2, 1)
belts[(10, 8)] = ('B', 3, 1)
for i, v in enumerate(M.y):
    m.Add(v == (1 if i in want else 0))
for c in inst.free:
    st = belts.get(c)
    if st is not None:
        m.Add(M.st[c][st] == 1)
    else:
        # either covered by a machine or empty
        m.Add(sum(v for s, v in M.st[c].items() if s != 'E') == 0)
s, stt, dt = M.solve(60, 4)
print(s.StatusName(stt))
sol = M.extract(s)
print(draw(inst, sol))
F = FullLP(M)
res = F.solve(on_set(sol))
print('shortfall', res['value'])
