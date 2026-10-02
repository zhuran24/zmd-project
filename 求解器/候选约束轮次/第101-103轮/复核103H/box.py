#!/usr/bin/env python3
"""复核103H：H01 传输相位、H08 传输箱不满。自写，不导入推导席脚本。

编码甲：逐步模拟。协议储存箱有 3 个存货端口，每口来货间隔 >=8 步（上游运输格滞留 1 tick）。
  每步：元件阶段先把本步到达的物品放进箱子，然后箱子判定；剩余冷却为 0 时传输（仓库全收，箱子清空），
  剩余冷却设为 40；每步开头剩余冷却减 1（不低于 0）。离线发生在两步之间：保留读法不动剩余冷却，
  清空读法把剩余冷却设为 0。
编码乙：先独立算出传输步号表（保留：p+40；清空：离线后第一步），再对相邻两次传输之间 (p, p'] 的
  到达数直接计数，取最大值。两种编码逐例比较最大库存与传输步号。
另有：40 步窗口内每口最多几件（穷举所有间隔>=8 的到达集合），H01 的程序例。
"""
import itertools, json, random, sys, bisect

def sim_A(arrivals, horizon, cd0, offlines):
    """arrivals: 每口到达步号集合；offlines: {步号x: 'keep'|'clear'}，离线在第 x 步之前。"""
    rem = cd0
    box = 0
    maxbox = 0
    transfers = []
    inflow = 0
    for t in range(horizon):
        if t > 0:
            rem = max(0, rem - 1)
        if offlines.get(t) == 'clear':
            rem = 0
        # 元件阶段到达
        for port in arrivals:
            if t in port:
                box += 1
                inflow += 1
        maxbox = max(maxbox, box)
        # 箱子判定
        if rem == 0:
            transfers.append(t)
            box = 0
            rem = 40
    return maxbox, transfers, inflow

def transfers_B(horizon, cd0, offlines):
    """独立写的传输步号：第一次在 cd0 步（剩余冷却 cd0 在第 0 步开头已给定，第 0 步不减），
    之后每次 +40；清空离线在 x 前时，若 x 早于下一次计划步，则下一次改为 x。"""
    out = []
    nxt = cd0
    clears = sorted(x for x, m in offlines.items() if m == 'clear')
    t = 0
    while True:
        # 找 [t, nxt) 中最早的清空离线
        cands = [x for x in clears if x > (out[-1] if out else -1) and x < nxt]
        if out == [] and cd0 == 0:
            cands = []
        if cands:
            nxt = min(cands)
        if nxt >= horizon:
            break
        out.append(nxt)
        nxt = nxt + 40
    return out

def maxbox_B(arrivals, transfers, horizon):
    arr = sorted(x for port in arrivals for x in port if x < horizon)
    best = 0
    prev = -1
    ends = transfers + [horizon - 1]
    for p2 in ends:
        # (prev, p2] 内到达数；p2 时刻元件先到、箱子后传输
        c = bisect.bisect_right(arr, p2) - bisect.bisect_right(arr, prev)
        best = max(best, c)
        prev = p2
    return best

def window_max(length, gap=8):
    """长度 length 的连续步内，间隔 >= gap 的到达最多几件（穷举）。"""
    best = 0
    def rec(start, cnt):
        nonlocal best
        best = max(best, cnt)
        for x in range(start, length):
            rec(x + gap, cnt + 1)
    rec(0, 0)
    return best

def main():
    rng = random.Random(103)
    res = {}
    # 1. 40 步窗口（两次传输之间 (p,p+40] 共 40 步）每口最多件数
    res['window40_per_port'] = window_max(40)
    res['window41_per_port'] = window_max(41)
    res['window40_three_ports'] = 3 * res['window40_per_port']
    # 2. 满速相位穷举：三口各自模 8 相位，冷却初值 0..39，离线三种（无、保留、清空，各在若干时点）
    horizon = 400
    n = 0; mism = 0; gmax = 0; mismT = 0
    offl_opts = [None] + [('keep', x) for x in (17, 93, 201)] + [('clear', x) for x in (17, 93, 201, 205, 206)]
    for ph in itertools.product(range(8), repeat=3):
        arrivals = [set(range(p, horizon, 8)) for p in ph]
        for cd0 in range(0, 40, 3):
            for oo in offl_opts:
                offl = {} if oo is None else {oo[1]: oo[0]}
                mA, trA, infl = sim_A(arrivals, horizon, cd0, offl)
                trB = transfers_B(horizon, cd0, offl)
                mB = maxbox_B(arrivals, trB, horizon)
                n += 1
                if trA != trB: mismT += 1
                if mA != mB: mism += 1
                gmax = max(gmax, mA)
    res['fullspeed_cases'] = n
    res['fullspeed_max'] = gmax
    res['fullspeed_mismatch_max'] = mism
    res['fullspeed_mismatch_transfers'] = mismT
    # 3. 随机到达（间隔>=8 的任意间隔）＋随机多次离线（保留/清空混合）
    n2 = 0; mism2 = 0; gmax2 = 0; mismT2 = 0
    for it in range(4000):
        horizon = 600
        arrivals = []
        for _ in range(3):
            s = set(); x = rng.randrange(0, 10)
            while x < horizon:
                s.add(x); x += 8 + (0 if rng.random() < 0.7 else rng.randrange(0, 12))
            arrivals.append(s)
        offl = {}
        for _ in range(rng.randrange(0, 15)):
            offl[rng.randrange(1, horizon)] = rng.choice(['keep', 'clear'])
        cd0 = rng.randrange(0, 41)
        mA, trA, infl = sim_A(arrivals, horizon, cd0, offl)
        trB = transfers_B(horizon, cd0, offl)
        mB = maxbox_B(arrivals, trB, horizon)
        n2 += 1
        if trA != trB: mismT2 += 1
        if mA != mB: mism2 += 1
        gmax2 = max(gmax2, mA)
        # 相邻传输间隔 <= 40
        gaps = [b - a for a, b in zip(trA, trA[1:])]
        assert all(g <= 40 for g in gaps), gaps
        # 无清空时间隔恰 40
        if all(m == 'keep' for m in offl.values()):
            assert all(g == 40 for g in gaps)
    res['random_cases'] = n2
    res['random_max'] = gmax2
    res['random_mismatch_max'] = mism2
    res['random_mismatch_transfers'] = mismT2
    # 4. H01 程序例：第 17 步前离线
    res['H01_example_keep'] = sim_A([set(), set(), set()], 120, 0, {17: 'keep'})[1]
    res['H01_example_clear'] = sim_A([set(), set(), set()], 120, 0, {17: 'clear'})[1]
    # 5. 两箱相位：清空读法下离线后两箱同步
    a = sim_A([set()] * 3, 200, 0, {57: 'clear'})[1]
    b = sim_A([set()] * 3, 200, 23, {57: 'clear'})[1]
    res['two_boxes_clear_after_offline_57'] = {'box1': a, 'box2': b}
    a = sim_A([set()] * 3, 200, 0, {57: 'keep'})[1]
    b = sim_A([set()] * 3, 200, 23, {57: 'keep'})[1]
    res['two_boxes_keep_after_offline_57'] = {'box1': a, 'box2': b}
    json.dump(res, open(sys.argv[1] if len(sys.argv) > 1 else 'box.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))

if __name__ == '__main__':
    main()
