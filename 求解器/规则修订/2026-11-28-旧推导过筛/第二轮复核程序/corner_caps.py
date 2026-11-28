"""第二轮独立复算「角区」93：47 种边带排布，逐矿石格逐方向检查能否贴一个 3x3 子块。
坐标：左下角格 (0,0)，x 向右、y 向上。第 0 列、第 0 行除 q 外全是仓库取货口机身。
另复核 (2,2) 结论用到的事实：L 形区 {第1列行1..5} ∪ {第1行列1..5} 内矿石格数 >=4。
"""
N = 70
def layouts():
    # q 在角格
    yield ('corner', (0, 0), [2 + 3 * i for i in range(23)], [2 + 3 * i for i in range(23)])
    for k in range(1, 24):
        g = 3 * k
        left = [1 + 3 * i for i in range(k)] + [g + 2 + 3 * i for i in range(23 - k)]
        bottom = [2 + 3 * i for i in range(23)]
        yield ('left%d' % g, (0, g), left, bottom)
        yield ('bottom%d' % g, (g, 0), bottom, left)  # 转置：左边从第 1 行起，下边含角
def check(name, q, lm, bm):
    assert len(lm) == 23 and len(bm) == 23 and lm[-1] <= 68 and bm[-1] <= 68
    ore = {(1, y) for y in lm} | {(x, 1) for x in bm}
    assert len(ore) == 46
    pick_dir = {}
    for y in lm: pick_dir[(1, y)] = (-1, 0)
    for x in bm: pick_dir[(x, 1)] = (0, -1)
    def block_ok(x0, y0):
        if x0 < 1 or y0 < 1 or x0 + 2 > N - 1 or y0 + 2 > N - 1:
            return False
        return not any((x0 + i, y0 + j) in ore for i in range(3) for j in range(3))
    def coverable(c):
        x, y = c
        return any(block_ok(x - i, y - j) for i in range(3) for j in range(3))
    total = 0
    for o in ore:
        cnt = 1
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if d == pick_dir[o]:
                continue
            n = (o[0] + d[0], o[1] + d[1])
            if coverable(n):
                cnt += 1
        total += cnt
    L = {(1, y) for y in range(1, 6)} | {(x, 1) for x in range(1, 6)}
    return total, len(ore & L)
res = {}
for name, q, lm, bm in layouts():
    res[name] = check(name, q, lm, bm)
print('排布数', len(res))
print('最大', max(v[0] for v in res.values()), [k for k, v in res.items() if v[0] == max(x[0] for x in res.values())][:6])
print('角格无人占', res['corner'])
print('L 形区矿石格最少', min(v[1] for v in res.values()))
from collections import Counter
print(Counter(v[0] for v in res.values()))
