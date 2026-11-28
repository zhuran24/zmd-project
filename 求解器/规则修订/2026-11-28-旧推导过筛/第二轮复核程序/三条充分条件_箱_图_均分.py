"""第二轮独立复核：协议储存箱单种非成品保格、调试期后状态图交付核验、整批k件配k条取货通道的均分。
按现行规则的步进：每步 1 汇流器输入、2 元件移动、3 汇流器再输入、4 非运输单位移动、5 结束制造、6 开始制造，然后计时。
1 tick = 8 步。滞留：进格那一步已停从 0 记，步末 +1，满 8 才能移（规则模型 物品格.lean 移一件 / 框架.lean 计时）。
"""
from fractions import Fraction as F
import random, itertools, sys

TICK = 8

# ---------- 二：交付率系数 ----------
def part_rates():
    r_e = F(18, 30); r_c = F(33, 2) / 30
    assert r_e == F(12, 20) == F(3, 5) and r_c == F(11, 20)
    # 势差相消：沿 N 个周期求和 20D-12T >= -(hmax-hmin)
    # 周期 P、每周期交付 D，若 20D-12P < 0，N 足够大时必违反
    D, P, Delta = F(59, 10), F(10), F(1000)  # 例：0.59/tick
    N = 1
    while 20 * N * D - 12 * N * P >= -Delta:
        N += 1
    return dict(电=str(r_e), 胶=str(r_c), 反例周期数=N)

# ---------- 一：箱子 ----------
def max_arrivals(window, spacing=TICK):
    # 半开窗 window 步里、相邻至少隔 spacing 步，最多几件
    best = 0
    for start in range(spacing):
        best = max(best, len(range(start, window, spacing)))
    return best

def box_sim(trials=3000, steps=1200, seed=1):
    """协议储存箱：第1格放 x；三个存货口各由一格运输单位喂货（滞留 8 步）；
    传输每 40 步一次（第 4 阶段），仓库随机停收再恢复；取货口只取 x。
    核：x 只在第 1 格（在前提 1<=计数<=50 成立的轨迹上），恢复后第一次传输清空第 2-6 格，
    此后每次传输前每种成品只占一格、没有成品因格满被拒。"""
    rnd = random.Random(seed)
    stats = dict(轨迹=0, 前提成立=0, x越格=0, 恢复后成品被挡=0, 成品占两格=0, 每周期最多进箱=0)
    for _ in range(trials):
        cells = [None] * 6  # (物, 件数)
        q = rnd.randint(1, 50)
        cells[0] = ('x', q)
        for i in range(1, 6):
            if rnd.random() < 0.5:
                cells[i] = (rnd.choice('AB'), rnd.randint(1, 50))
        cool = rnd.randint(0, 39)
        feed_last = [-100] * 3  # 各口上次送货步
        accept = True
        recovered_at = None  # 恢复后第一次全清的步
        cleared = False
        since = 0
        premise_ok = True
        stats['轨迹'] += 1
        for t in range(steps):
            # 仓库停收/恢复（玩家拿取成品在两步之间）
            if rnd.random() < 0.01:
                accept = not accept
                cleared = False
            # 阶段2：各口到货（相邻至少隔 8 步）
            for p in range(3):
                if t - feed_last[p] >= TICK and rnd.random() < 0.8:
                    it = rnd.choice('xAB') if rnd.random() < 0.3 else rnd.choice('AB')
                    if it == 'x' and cells[0][1] >= 50:
                        it = rnd.choice('AB')  # 来路保证前提：计数满 50 时这一口不送 x
                    # 放进编号最小的能放它的格
                    placed = False
                    if it == 'x' and cells[0][1] == 50:
                        premise_ok = False  # 参考计数将到 51
                        break
                    for i in range(6):
                        c = cells[i]
                        if c is None or (c[0] == it and c[1] < 50):
                            if it == 'x' and i != 0:
                                # 参考过程：计数将到 51，前提不成立
                                premise_ok = False
                            cells[i] = (it, (c[1] if c else 0) + 1)
                            placed = True
                            break
                    if placed:
                        feed_last[p] = t
                        since += 1
                        if cleared and it != 'x':
                            pass
                    else:
                        if cleared and it != 'x':
                            stats['恢复后成品被挡'] += 1
            if not premise_ok:
                break
            # 阶段4：取货口取 x（编号最小非空格）；传输
            if rnd.random() < 0.3 and cells[0][1] >= 2:  # 下游保证前提：计数到 1 不再取
                c = cells[0]
                if c is not None and c[0] == 'x':
                    if c[1] == 1:
                        premise_ok = False  # 参考计数将到 0
                        break
                    cells[0] = ('x', c[1] - 1)
            if cool == 0:
                if cleared:
                    stats['每周期最多进箱'] = max(stats['每周期最多进箱'], since)
                if accept:
                    for i in range(6):
                        if cells[i] and cells[i][0] != 'x':
                            cells[i] = None
                    if all(cells[i] is None for i in range(1, 6)):
                        cleared = True
                since = 0
                cool = 40
            # 核：x 只在第 1 格；清空后每种成品至多一格
            for i in range(1, 6):
                if cells[i] and cells[i][0] == 'x':
                    stats['x越格'] += 1
            if cleared:
                kinds = [c[0] for c in cells[1:] if c]
                if len(kinds) != len(set(kinds)):
                    stats['成品占两格'] += 1
            cool -= 1  # 步末计时
        if premise_ok:
            stats['前提成立'] += 1
    return stats

# ---------- 三：整批 k 件配 k 条取货通道 ----------
def batch_sim(k, trials, steps, seed, spacing=TICK, start_mode='before'):
    rnd = random.Random(seed)
    viol_diff = viol_allnone = segs = 0
    for _ in range(trials):
        P = rnd.choice([0, k, 2 * k, rnd.randint(0, 50 - k)])
        # 首格：None 或 (进格步, 离开步)
        cells = []
        for i in range(k):
            if rnd.random() < 0.5:
                a = -rnd.randint(0, 10)
                cells.append([a, a + spacing + rnd.choice([0, 0, 0, 1, 3, 9])])
            else:
                cells.append(None)
        making = rnd.choice([None, rnd.randint(1, 8)])  # 还剩几步
        cache = rnd.random() < 0.2 and making is None  # 缓存里有一批做好的
        slow = rnd.random()
        ready = []  # 每步：各路第 4 阶段前首格是否空
        took = []   # 每步：各路取没取
        Pbefore = []  # 每步判定之前的件数
        Pafter = []   # 每步全部判定之后的件数
        for t in range(steps):
            Pbefore.append(P)
            # 步初整理 / 阶段2：首格到期的货可能离开（下游随机堵）
            for i in range(k):
                c = cells[i]
                if c is not None and t >= c[1]:
                    if rnd.random() < 0.85:
                        cells[i] = None
                    else:
                        c[1] = t + 1
            ready.append([cells[i] is None for i in range(k)])
            # 阶段4：本机各组按随机先后判（覆盖轮询、级别、汇流器单独成组）
            order = list(range(k)); rnd.shuffle(order)
            tk = [0] * k
            for i in order:
                if P == 0:
                    break
                if cells[i] is None:
                    P -= 1; tk[i] = 1
                    d = t + spacing + (0 if rnd.random() < slow else rnd.randint(1, 12))
                    cells[i] = [t, d]
            took.append(tk)
            # 阶段5：结束制造
            if making == 0:
                making = None; cache = True
            if cache and P + k <= 50:
                P += k; cache = False
            # 阶段6：开始制造（原料随机断续）
            if making is None and not cache and rnd.random() < 0.7:
                making = TICK
            Pafter.append(P)
            # 计时
            if making is not None:
                making -= 1
        # 按每个相位切刻
        for th in range(TICK):
            n = (steps - th) // TICK
            kready = []; ktake = []
            for m in range(n):
                rng = range(th + m * TICK, th + (m + 1) * TICK)
                kready.append(all(any(ready[s][i] for s in rng) for i in range(k)))
                ktake.append([sum(took[s][i] for s in rng) for i in range(k)])
            m = 0
            while m < n:
                if not kready[m]:
                    m += 1; continue
                e = m
                while e < n and kready[e]:
                    e += 1
                for a in range(m, e):
                    cum = [0] * k
                    s0 = th + a * TICK
                    p0 = Pbefore[s0] if start_mode == 'before' else Pafter[s0]
                    mult = p0 % k == 0
                    for b in range(a, e):
                        cum = [cum[i] + ktake[b][i] for i in range(k)]
                        segs += 1
                        if max(cum) - min(cum) > 1:
                            viol_diff += 1
                        if mult and len(set(ktake[b])) != 1:
                            viol_allnone += 1
                            mult = False  # 每段只记一次
                m = e
    return dict(k=k, 段数=segs, 差超过1=viol_diff, 整倍数却部分取=viol_allnone)

if __name__ == '__main__':
    print('二 交付率:', part_rates())
    print('一 每口 40 步半开窗最多到货:', max_arrivals(40), ' 41 步:', max_arrivals(41), ' 三口合计:', 3 * max_arrivals(40))
    print('一 箱子模拟:', box_sim())
    for k in (2, 3):
        print('三 现行滞留 8 步:', batch_sim(k, 1500, 240, 10 + k))
    # 对照（检验程序有没有牙）：滞留若只有 7 步、或段首件数按判定之后读
    for k in (2, 3):
        print('三 对照 滞留7步:', batch_sim(k, 600, 240, 20 + k, spacing=7))
        print('三 对照 段首按判定后读:', batch_sim(k, 1500, 240, 30 + k, start_mode='after'))
