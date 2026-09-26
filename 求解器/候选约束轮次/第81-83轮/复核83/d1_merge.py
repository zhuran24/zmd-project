#!/usr/bin/env python3
"""复核83：81D 第1条（一批k件配k条取货通道的均分）缺“首运输格只从这个取货格收货”前提时的反例。
整数 tick。采种机 C 每 tick 一批 2 粒种子（输入充足），取货格上限 50，两条取货通道：
  ch1 的首运输单位是汇流器 G，G 另有一条输入：一条总是满的传送带 X；G 的出口传送带每 tick 收走 1 件；
  ch2 的首运输单位是传送带 Y，每 tick 被下游收走 1 件。
汇流器存货侧两条通道按接通先后轮流取得尝试权，尝试后立刻传给下一条（规则“轮询”）。
每刻结束时检查：两条通道本刻是否“就绪”（首格在本刻某时点为空）、是否取到。"""
import json

def run(T=200, order=('ch1', 'X')):
    slot = 50          # C 取货格
    pending = True     # C 缓存里有做好的一批（上一刻开工、本刻完成或在等）
    G = None           # 汇流器格：到达时刻
    Y = None
    turn = 0           # 汇流器存货侧轮询指针：0->ch1, 1->X
    took = {'ch1': 0, 'ch2': 0}
    ready_all = True
    started_at = None
    for t in range(1, T + 1):
        rdy = {'ch1': False, 'ch2': False}
        if started_at is not None and started_at <= t - 1:
            pending = True; started_at = None
        # 下游收走（G、Y 的旧货各每 tick 出 1 件）
        if G is not None and G <= t - 1:
            G = None
        if Y is not None and Y <= t - 1:
            Y = None
        changed = True
        while changed:
            changed = False
            if pending and slot + 2 <= 50:
                slot += 2; pending = False; started_at = t; changed = True  # 入格后立即开下一批（输入充足）
            if G is None:
                rdy['ch1'] = True
                # 轮到谁尝试
                src = order[turn]
                turn = 1 - turn
                if src == 'ch1':
                    if slot > 0:
                        slot -= 1; G = t; took['ch1'] += 1; changed = True
                else:
                    G = t; changed = True  # X 总是有货
            if Y is None:
                rdy['ch2'] = True
                if slot > 0:
                    slot -= 1; Y = t; took['ch2'] += 1; changed = True
        ready_all &= rdy['ch1'] and rdy['ch2']
    return {'ticks': T, 'took': took, 'both_ready_every_tick': ready_all}

print(json.dumps({'order_ch1_first': run(), 'order_X_first': run(order=('X', 'ch1'))}, ensure_ascii=False))
