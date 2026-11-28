from fractions import Fraction

step = Fraction(1, 8)
print("传输相邻触发间隔（连续运行步数）", 5 / step)
# 一格容量为一，每件至少停一 tick。按周期首尾衔接取最密事件。
print("单运输格满速（件/tick）", Fraction(1, 1))
# 对现象11回放的两个读数核算分流：稳定边界供料每 tick 一件。
for straight in (20, 40):
    direct = 40 - straight
    print("直进汇流器占比、另一路进汇流器件数", Fraction(direct, 40), 40 - direct)
