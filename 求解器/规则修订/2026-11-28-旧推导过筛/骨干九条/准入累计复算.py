"""用现行规则的档位、段长与滞留时间复算单个物品准入口的数值。"""

import re
from fractions import Fraction
from pathlib import Path


RULES = (Path(__file__).resolve().parents[4]/"《明日方舟：终末地》游戏规则.txt")
lines = RULES.read_text(encoding="utf-8").splitlines()
gate = next(line for line in lines if line.lstrip().startswith("物品准入口："))


def numbers(pattern, source):
    match = re.search(pattern, source)
    if match is None:
        raise ValueError(f"现行规则中找不到 {pattern}")
    return tuple(map(int, match.groups()))


(steps_per_tick,) = numbers(r"每 1/(\d+) tick 为一步", "\n".join(lines))
(hold_ticks,) = numbers(r"运输单位的物品格中必须停留至少 (\d+) tick", "\n".join(lines))
total_min, total_max = numbers(r"累计收下上限（(\d+)～(\d+)）", gate)
rate_ticks, rate_min, rate_max = numbers(r"每 (\d+) tick 的收下上限（(\d+)～(\d+)", gate)
first_end, full_width = numbers(r"第 1～(\d+) 步为第 1 段、此后每 (\d+) 步", gate)
(previous,) = numbers(r"前面至多 (\d+) 段", gate)
window = previous + 1
period_steps = window * full_width
period_ticks = Fraction(period_steps, steps_per_tick)
hold_steps = hold_ticks * steps_per_tick
assert period_ticks == rate_ticks


def received_before_refusal(limit, initial):
    count = initial
    while count < limit:
        count += 1
    return count - initial


for limit in range(total_min, total_max + 1):
    for initial in {0, limit - 1, limit, total_max}:
        assert received_before_refusal(limit, initial) == max(0, limit - initial)
print(f"累计上限 {total_min}～{total_max} 逐档通过，含原计数高于现上限的情形。")


def segment(step):
    """实收步从建成后第 1 步算起，段也从 1 编号。"""
    if step <= first_end:
        return 1
    return 2 + (step - first_end - 1) // full_width


def allowed(steps, limit):
    """逐件检查滞留所需的最小间隔和收货判定前的占用。"""
    occupied = []
    last = None
    for step in steps:
        if last is not None and step - last < hold_steps:
            return False
        current = segment(step)
        occupied = [j for j in occupied if current - j < window]
        if len(occupied) >= limit:
            return False
        occupied.append(current)
        last = step
    return True


def ceiling_ratio(numerator, denominator):
    return (numerator + denominator - 1) // denominator


# 对任意起始步，数连续 N 步触及的段，再把它们每十段分一块。
# N 增加一个完整窗，所触段数恰增十。首段与所有常规起始相位都纳入。
for length in range(1, 2 * period_steps + 1):
    blocks = []
    for start in range(1, first_end + full_width + 1):
        touched = segment(start + length - 1) - segment(start) + 1
        blocks.append(ceiling_ratio(touched, window))
        assert segment(start + length - 1 + period_steps) == segment(start + length - 1) + window
    assert max(blocks) == ceiling_ratio(length + full_width - 1, period_steps)
print(f"N 步触及的段每 {window} 段分一块，最多 ⌈(N+{full_width - 1})/{period_steps}⌉ 块。")


print(f"首段 {first_end} 步，此后每段 {full_width} 步。{window} 个常规段合计 {period_steps} 步，即 {period_ticks} tick。")
for limit in range(rate_min, rate_max + 1):
    best = 0
    # 每个常规段只尝试在段首收一件。枚举是为了找达到上界的局部序列。
    # 一般序列的上界来自正文的逐窗计数证明，无需假定收件都在段首。
    for mask in range(1 << window):
        offsets = [i * full_width for i in range(window) if mask & (1 << i)]
        steps = [first_end + 1 + repeat * period_steps + offset
                 for repeat in range(3) for offset in offsets]
        if allowed(steps, limit):
            best = max(best, len(offsets))
    assert best == limit
    print(f"k={limit}：每 {period_steps} 步局部最多 {best} 件（段首周期序列），"
          f"平均 {Fraction(best, 1) / period_ticks} 件/tick")

# 第 2 段的末步与第 12 段的首步，分别按判定前的真实段号检查。
late = first_end + full_width
early = first_end + 1 + period_steps
assert segment(early) - segment(late) == window
assert allowed([late, early], 1) and early - late < period_steps
print(f"k=1：第 {late}、{early} 步可各收一件，相隔 {early - late} 步。")
