# 密集结点：分流器 S 一个出口直连汇流器 M，另一出口接带 D；M 另有一条普通来路 B（满载）。
# 按现行规则的一步：1 汇流器输入判定（轮出普通来路；只有 B 一条）；2 元件各组按级别依次移动判定；
# 3 汇流器再判一次输入；4 非运输单位（此处只有供料、收货，视为无限）；5、6 无制造。
# 滞留：运输物品格中停满 8 步才可移出。
# 枚举第 2 阶段三组（M 出货组、S 组、B 组）的全部先后、S 两条出口的接通先后、S 与 B 来货的相位差，
# 统计 40 tick 里 S 直入 M 的件数、S 走 D 的件数、B 进 M 的件数。
from itertools import permutations

STEPS = 8

def run(order, s_first_is_M, offset, warm=400, ticks=40):
    # 状态：每格 (有货, 进格步)。S、B 的上游一直满载：被取空的那一步同步由上游补一件（上游组级别更低，后判）。
    S = [True, 0]
    B = [True, offset]       # B 的货比 S 晚 offset 步进格
    M = [False, None]
    D_free_at = 0            # D 的接货格（D 之后一路通到收货箱，D 组次序 1，最先判）
    Mout_free_at = 0
    chans = ['M', 'D'] if s_first_is_M else ['D', 'M']   # 接通先后
    last = None              # 元件轮询：上次移动物品的通道
    cnt = {'S->M': 0, 'S->D': 0, 'B->M': 0}
    total = warm + ticks * STEPS
    for t in range(total):
        rec = t >= warm
        def movable(cell):
            return cell[0] and t - cell[1] >= STEPS
        # D 格、M 后带格：D 组次序 1 最先判，满载时它们每 8 步腾一次格
        D_empty = t >= D_free_at
        # 阶段 1：汇流器输入判定，B 有可移动物品时轮到 B
        selB = movable(B)
        # 阶段 2
        for g in order:
            if g == 'Mout':
                if movable(M) and t >= Mout_free_at:
                    M[0] = False
                    Mout_free_at = t + STEPS
            elif g == 'S':
                if movable(S):
                    if last is None:
                        seq = [chans[1], chans[0]]       # 都未移动过：从第 2 条接通的开始
                    else:
                        i = chans.index(last)
                        seq = [chans[(i + 1) % 2], chans[i]]
                    for c in seq:
                        if c == 'M' and not M[0]:
                            M[:] = [True, t]; S[:] = [True, t]; last = 'M'
                            if rec: cnt['S->M'] += 1
                            break
                        if c == 'D' and D_empty:
                            D_free_at = t + STEPS; D_empty = False
                            S[:] = [True, t]; last = 'D'
                            if rec: cnt['S->D'] += 1
                            break
            elif g == 'B':
                if selB and movable(B) and not M[0]:
                    M[:] = [True, t]; B[:] = [True, t]
                    if rec: cnt['B->M'] += 1
        # 阶段 3：再判一次输入（B 已在阶段 2 判过，本步不再动；只有一条普通来路，结果同阶段 1）
    return cnt

res = {}
for order in permutations(['Mout', 'S', 'B']):
    for sf in (True, False):
        for off in range(0, 8):
            c = run(list(order), sf, off)
            res[(order, sf, off)] = c

ratios = {}
for k, c in res.items():
    F = c['S->M'] + c['S->D']
    r = c['S->M'] / F if F else None
    ratios.setdefault((r, c['B->M']), []).append(k)
for (r, b), ks in sorted(ratios.items(), key=lambda x: (x[0][0] or 0, x[0][1])):
    print(f"直入比例={r}  B进M件数={b}  情形数={len(ks)}  例={ks[0]}")
# 同一相位（off=0）下只换组的先后
print('相位差 0：')
for order in permutations(['Mout', 'S', 'B']):
    for sf in (True, False):
        c = res[(order, sf, 0)]
        print(order, 'S先接M' if sf else 'S先接D', c)
