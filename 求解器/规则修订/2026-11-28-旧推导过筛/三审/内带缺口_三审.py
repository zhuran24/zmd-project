"""主会话三审：内带缺口修正版里边带那一段的清点，自己从头写，不读席位的程序。
基地 70×70，左下角 (0,0)。左边界第 0 列、下边界第 0 行共 139 格，46 个 3×1 仓库取货口占 138 格，余一格 q。"""
from collections import Counter
N = 70
def arrangements():
    out = []
    # q 在角上
    out.append(('q=(0,0)', (0, 0), [(0, a) for a in range(1, 70, 3)], [(a, 0) for a in range(1, 70, 3)]))
    # 左带占角，q 在左边界 (0,y)
    for y in range(3, 70, 3):
        left = [(0, a) for a in range(0, y, 3)] + [(0, a) for a in range(y + 1, 70, 3)]
        out.append(('L%d' % y, (0, y), left, [(a, 0) for a in range(1, 70, 3)]))
    # 下带占角，q 在下边界 (x,0)
    for x in range(3, 70, 3):
        bot = [(a, 0) for a in range(0, x, 3)] + [(a, 0) for a in range(x + 1, 70, 3)]
        out.append(('B%d' % x, (x, 0), [(0, a) for a in range(1, 70, 3)], bot))
    return out
res = Counter(); detail = {}
for name, q, left, bot in arrangements():
    assert len(left) == 23 and len(bot) == 23
    occ = set()
    for (x, y) in left: occ |= {(0, y), (0, y + 1), (0, y + 2)}
    for (x, y) in bot: occ |= {(x, 0), (x + 1, 0), (x + 2, 0)}
    border = {(0, y) for y in range(N)} | {(x, 0) for x in range(N)}
    assert len(occ) == 138 and border - occ == {q}, (name, len(occ))
    srcL = [(1, y + 1) for (x, y) in left]; srcB = [(x + 1, 1) for (x, y) in bot]
    src = set(srcL) | set(srcB); assert len(src) == 46
    I = {(1, y) for y in range(1, N)} | {(x, 1) for x in range(1, N)}; assert len(I) == 137 and src <= I
    # 能碰内带、不压矿源、不出界、不压边界两列行的 3×3 子块在内带里占的格
    B = set()
    for x0 in range(1, N - 2):
        for y0 in range(1, N - 2):
            if x0 > 1 and y0 > 1: continue
            cells = {(x0 + i, y0 + j) for i in range(3) for j in range(3)}
            if cells & src: continue
            B |= cells & I
    # 矿源的两个切向（沿带方向）指向 B 的个数
    t = 0
    for (x, y) in srcL: t += sum(1 for c in ((1, y + 1), (1, y - 1)) if c in B)
    for (x, y) in srcB: t += sum(1 for c in ((x + 1, 1), (x - 1, 1)) if c in B)
    # 普通矿源：同带上下（左右）相隔 3 的格也都是矿源
    sL = set(srcL); sB = set(srcB)
    gL = [(x, y) for (x, y) in srcL if (1, y - 3) in sL and (1, y + 3) in sL]
    gB = [(x, y) for (x, y) in srcB if (x - 3, 1) in sB and (x + 3, 1) in sB]
    g = len(gL) + len(gB)
    # 普通矿源两侧的间隙格不在 B 里（放不下机身），且两带普通源取面用到的格互不相交
    for (x, y) in gL: assert not ({(1, y - 2), (1, y - 1), (1, y + 1), (1, y + 2)} & B) and not ({(1, y - 1), (1, y + 1)} & src)
    for (x, y) in gB: assert not ({(x - 2, 1), (x - 1, 1), (x + 1, 1), (x + 2, 1)} & B) and not ({(x - 1, 1), (x + 1, 1)} & src)
    usedL = set(); usedB = set()
    for (x, y) in gL: usedL |= {(1, y), (2, y), (1, y - 1), (1, y + 1)}
    for (x, y) in gB: usedB |= {(x, 1), (x, 2), (x - 1, 1), (x + 1, 1)}
    assert not (usedL & usedB)
    assert min(y for (x, y) in gL) >= 4 and min(x for (x, y) in gB) >= 4
    # 相邻两个普通源各自可能取的间隙格不同：o 取 (1,s±1)，下一个源 (1,s+3) 取 (1,s+2)、(1,s+4)
    d = max(q)
    total = (92 - t) + (91 - len(B - src)) + 2 * g + 3
    res[(d if d in (0, 3, 66, 69) else 'mid', t, len(B - src), g, total)] += 1
for k, v in sorted(res.items(), key=str): print(k, v)
print('排布数', sum(res.values()))
# 四机型权重：照正文给的四项，只核合计与进位
from fractions import Fraction as F
from math import ceil
w = F(123, 2) + 10 + 24 + 14; print('权重合计', w, '进位', ceil(w), '| 619+261+8+4+110 =', 619 + 261 + 8 + 4 + ceil(w))
