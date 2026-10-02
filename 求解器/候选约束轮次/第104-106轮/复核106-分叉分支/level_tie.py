# 同刻接通的排法会长期改变分配的一个小构型（规则第 25—27、33 行，临时规则第 1 条）。
# 粉碎机 K（3×3，取货边朝东）先建两条下游：汇流器 X1、X2 各贴 K 的一个取货端口，各往东送进一格传送带 b1、b2，
# 再进协议核心（总能收）。最后建 K：K→X1、K→X2 同刻接通。
# 两条通道直接接汇流器，各自一级；X1、X2 层数都是 2（各送往还往下送货的 b1/b2，b1/b2 只送往协议核心，层数 1）；
# 两级接通时刻相同，第 33 行「层数相同时接通早的级别高」定不了谁高，只能由同刻两条的排法定。
# K 每 tick 做 1 批 1 源矿 → 1 源石粉末（原料假定一直够）。
# 本脚本逐步模拟（每步 1/8 tick；运输单位的物品停留至少 8 步），比较两种排法下 X1、X2 的长期收货量。
import json

STEPS_PER_TICK = 8


def sim(order, ticks=400):
    # order：K 的两级从高到低，例如 ['X1','X2']
    slot = {'X1': None, 'X2': None, 'b1': None, 'b2': None}  # 存「进格的步号」
    k_take = 0          # K 取货物品格里的件数
    k_batch_end = None  # 正在做的一批结束的步号
    got = {'X1': 0, 'X2': 0}
    core = {'b1': 0, 'b2': 0}
    for step in range(ticks * STEPS_PER_TICK):
        # 1. 结束到时的制造
        if k_batch_end is not None and step >= k_batch_end:
            k_take += 1
            k_batch_end = None
        # 2. 逐个判定：层数 1（b1、b2）→ 层数 2（X1、X2）→ 非运输单位 K
        for b in ('b1', 'b2'):
            if slot[b] is not None and step - slot[b] >= STEPS_PER_TICK:
                core[b] += 1
                slot[b] = None
        for x, b in (('X1', 'b1'), ('X2', 'b2')):
            if slot[x] is not None and step - slot[x] >= STEPS_PER_TICK and slot[b] is None:
                slot[b] = step
                slot[x] = None
        if k_take > 0:
            for x in order:  # 先按级别
                if slot[x] is None:
                    slot[x] = step
                    got[x] += 1
                    k_take -= 1
                    break
        # 3. 开始能开始的制造（取货格未满 50 且上一批已进格）
        if k_batch_end is None and k_take < 50:
            k_batch_end = step + STEPS_PER_TICK
    return got, core


if __name__ == '__main__':
    out = {}
    for order in (['X1', 'X2'], ['X2', 'X1']):
        got, core = sim(order)
        out['high_level=' + order[0]] = {'X1_received': got['X1'], 'X2_received': got['X2'],
                                         'core_from_b1': core['b1'], 'core_from_b2': core['b2']}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    json.dump(out, open('level_tie.json', 'w'), ensure_ascii=False, indent=1)
