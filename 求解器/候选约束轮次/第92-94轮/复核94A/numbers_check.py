#!/usr/bin/env python3
"""复核94A：候选里的关键数字，每项两套独立算法互相核对。
N20 台数下界；N41 交替通道下界；N43 回路存量 64、22、42；N48 箱内 18 件（及步进下的精确值）；
N03 传输间隔 40 步；N51 混料分料公式；N56 箱头限存的小规模穷举。
"""
from fractions import Fraction as F
from math import ceil, gcd
import itertools, json, random

out = {}

# ---------- N20：由配方逐级推批次率（编码一：分数，每 tick） ----------
def rates_fraction():
    bat, cap = F(3, 5), F(11, 20)
    r = {}
    r['封装机'] = bat                      # 5 tick 配方
    r['灌装机'] = cap
    parts, dense_src = 10 * bat, 15 * bat
    bottles, fine = 10 * cap, 10 * cap
    r['配件机'] = parts
    r['塑形机'] = bottles
    steel = parts + 2 * bottles
    grind_src, grind_qf = dense_src, fine
    grind_fe = steel                       # 致密蓝铁粉末 → 钢块 1:1
    r['研磨机'] = grind_src + grind_qf + grind_fe
    sand_pow = grind_src + grind_qf + grind_fe
    src_pow, qf_pow, fe_pow = 2 * grind_src, 2 * grind_qf, 2 * grind_fe
    crush_ore, crush_qf, crush_fe, crush_sand = src_pow, qf_pow / 2, fe_pow, sand_pow / 3
    r['粉碎机'] = crush_ore + crush_qf + crush_fe + crush_sand
    r['精炼炉'] = grind_fe + fe_pow       # 致密蓝铁粉末→钢块 + 蓝铁矿→蓝铁块（r=0）
    # 植物回路：z = a + f, 2a = z
    a_qf, a_sand = crush_qf, crush_sand
    r['采种机'] = a_qf + a_sand
    r['种植机'] = 2 * a_qf + 2 * a_sand
    return r
per_machine_tick = {k: (F(1, 5) if k in ('封装机', '灌装机') else F(1)) for k in
                    ['粉碎机', '精炼炉', '研磨机', '塑形机', '配件机', '种植机', '采种机', '封装机', '灌装机']}
rf = rates_fraction()
lb1 = {k: ceil(rf[k] / per_machine_tick[k]) for k in per_machine_tick}

# 编码二：整数，20 tick=160 步一个周期，电池 12 个、胶囊 11 个；单机 160 步内至多 160/8 或 160/40 批
def batches_integer():
    B, C = 12, 11
    n = {}
    n['封装机'], n['灌装机'] = B, C
    parts, dsrc, bottles, fine = 10 * B, 15 * B, 10 * C, 10 * C
    n['配件机'], n['塑形机'] = parts, bottles
    steel = parts + 2 * bottles
    n['研磨机'] = dsrc + fine + steel
    n['精炼炉'] = steel + 2 * steel
    sand = dsrc + fine + steel
    assert sand % 3 == 0 and (2 * fine) % 2 == 0
    n['粉碎机'] = 2 * dsrc + (2 * fine) // 2 + 2 * steel + sand // 3
    n['采种机'] = (2 * fine) // 2 + sand // 3
    n['种植机'] = 2 * n['采种机']
    return n
nb = batches_integer()
cap160 = {k: (160 // 40 if k in ('封装机', '灌装机') else 160 // 8) for k in nb}
lb2 = {k: -(-nb[k] // cap160[k]) for k in nb}
out['N20'] = dict(rates=dict((k, str(v)) for k, v in rf.items()), batches_per_160_steps=nb,
                  lower_bounds_fraction=lb1, lower_bounds_integer=lb2, agree=lb1 == lb2,
                  expected=dict(粉碎机=68, 精炼炉=51, 研磨机=32, 塑形机=6, 配件机=6, 种植机=32, 采种机=16, 封装机=3, 灌装机=3))
out['N20']['match_expected'] = lb1 == out['N20']['expected']

# ---------- N41：交替时取货通道下界 ----------
pairs = {'砂叶×荞花': (3, 2), '砂叶×单件': (3, 1), '荞花×单件': (2, 1), '采种机': (2, 2)}
n41 = {}
for k, (a, b) in pairs.items():
    v1 = ceil(F(a + b, 2))
    v2 = (a + b + 1) // 2
    n41[k] = (v1, v2)
out['N41'] = dict(bounds=n41, agree=all(x == y for x, y in n41.values()))

# ---------- N43：32 台种植机任意相位，任一观察步的 (t, t+16] 内完成 64 批；平均存量 ----------
def n43_window(trials=2000):
    rng = random.Random(4301)
    mins = []
    for _ in range(trials):
        ph = [rng.randrange(8) for _ in range(32)]
        t = rng.randrange(8, 200)
        cnt = sum(1 for p in ph for c in range(t + 1, t + 17) if c % 8 == p)
        cnt2 = sum(1 for p in ph for c in range(t - 15, t + 1) if c % 8 == p)
        mins.append((cnt, cnt2))
    return sorted(set(mins))
out['N43'] = dict(window_counts_seen=n43_window(),
                  avg_lower=dict(荞花=str(F(11) * 2), 砂叶=str(F(21) * 2)),
                  avg_lower_steps=dict(荞花=11 * 16 // 8, 砂叶=21 * 16 // 8))

# ---------- N48：一个存货端口在两次传输之间至多收几件 ----------
def max_events_bruteforce(points):
    best = 0
    pts = list(points)
    # 贪心与穷举两种：这里穷举所有起点后按 8 步贪心（间隔≥8 的最大集合由贪心最优）
    for start in pts:
        c, last = 0, None
        for p in pts:
            if p >= start and (last is None or p - last >= 8):
                c += 1; last = p
        best = max(best, c)
    return best
def max_events_formula(n_points):
    return (n_points - 1) // 8 + 1
w40 = list(range(1, 41))      # 传输在第 s 步，下一次第 s+40 步；进箱在本箱判定前，故窗口 s+1..s+40
w41 = list(range(0, 41))      # 推导92A 用的闭区间 [s, s+40]
w41b = list(range(1, 42))     # 若冷却要到第 s+41 步才算结束
out['N48'] = dict(per_port_window_s1_s40=(max_events_bruteforce(w40), max_events_formula(40)),
                  per_port_closed_0_40=(max_events_bruteforce(w41), max_events_formula(41)),
                  per_port_if_cooldown_41=(max_events_bruteforce(w41b), max_events_formula(41)),
                  box_max_40step=3 * max_events_formula(40), box_bound_claimed=3 * max_events_formula(41))

# ---------- N03：传输间隔 ----------
out['N03'] = dict(steps_per_tick=8, cooldown_ticks=5, interval_steps=5 * 8)

# ---------- N51：混料轮询分料公式 ----------
def n51_check(trials=3000):
    rng = random.Random(5101)
    bad = 0
    for _ in range(trials):
        k = rng.randint(1, 6)
        L = rng.randint(1, 30)
        kinds = rng.randint(1, 4)
        lst = [rng.randrange(kinds) for _ in range(L)]
        h = gcd(L, k)
        # 直接：成功序号 n 的物品 lst[n % L]，走第 n % k 路；数 L*k 次成功（=联合周期的倍数）
        total = L * k
        direct = [[0] * kinds for _ in range(k)]
        for n in range(total):
            direct[n % k][lst[n % L]] += 1
        # 公式：每路每种 = 合计率 F·h·c(a, j mod h)/(L k)；换成件数：总件数 total 乘 h·c/(L k)
        for j in range(k):
            for a in range(kinds):
                c = sum(1 for s in range(L) if s % h == j % h and lst[s] == a)
                if direct[j][a] * L * k != total * h * c:
                    bad += 1
    return bad
out['N51'] = dict(trials=3000, mismatches=n51_check())

# ---------- N56：箱头限存，小规模穷举 ----------
def n56_check():
    """c 条通道（2 或 3），各自恰每 8 步收一件，相位互不相同（箱子每步至多送一件）。
    接受 x 的通道集合 S（|S|=c_x<c）。设第 s 步判定后 1 号格有 n 件 x（n≥c_x+1），
    之后 1 号格可任意补进 x。逐步检查 s+1..s+8 能否让每条通道都在自己的相位收到一件。"""
    viol = 0; cases = 0
    for c in (2, 3):
        for phases in itertools.permutations(range(8), c):
            for cx in range(0, c):
                for S in itertools.combinations(range(c), cx):
                    for n in range(cx + 1, cx + 4):
                        cases += 1
                        x_left = n
                        ok = True
                        for t in range(1, 9):
                            due = [j for j in range(c) if phases[j] == (t % 8)]
                            for j in due:
                                if x_left > 0:
                                    if j in S:
                                        x_left -= 1      # 送出一件 x
                                    else:
                                        ok = False       # 1 号格是 x，按身份拒收，这条通道这次收不到
                        if ok:
                            viol += 1
    return cases, viol
cs, vi = n56_check()
out['N56'] = dict(cases=cs, schedules_meeting_full_rate_with_head_over_cx=vi)

json.dump(out, open('numbers_check.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
