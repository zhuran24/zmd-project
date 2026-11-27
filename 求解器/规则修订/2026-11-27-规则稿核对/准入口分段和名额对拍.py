# 规则「物品准入口」一行里每 5 tick 收下上限的写法（建成后第 1～3 步为第 1 段、此后每 4 步一段，
# 合计当前段和前面至多 9 段里开着上限时收下的件数）和 Lean 模型的名额（规则模型/Endfield/框架.lean 的
# 「用一个名额」：收下一件占 37 + (6 − 拍 % 4) % 4 步）并排跑，核两边每一步收不收都一样。
# 2026-11-27 核规则修订稿时席位写的；名额那一半是照 Lean 定义转写的，不是从 Lean 里导出来的。
# 覆盖：单件占用的逐步比较；随机来货、上限 0 到 5、中途改上限、关开上限、设和清累计上限、换放行物品
# （换物品时名额留着、清掉两种取法都跑）。末尾另有一个两步的例子：换物品以后模型允许旧名额在一段中间
# 到期，这是正文写「无法确定」的那种情况，不在等价的范围里。
# 跑法：python3 准入口分段和名额对拍.py
from collections import Counter
from random import Random

def segment(step):
    return 1 + step // 4

def hold(step):
    beat = step - 1
    return 37 + (6 - beat % 4) % 4

# Enumerate a single receipt and test membership at every subsequent decision.
for s in range(1, 161):
    for t in range(s + 1, s + 85):
        assert (t - s < hold(s)) == (segment(t) - segment(s) < 10)

def compare(seed, preserve):
    r = Random(seed)
    durations, buckets = [], Counter()
    rate, cap, item = None, None, 0
    mtotal = btotal = 0
    for t in range(1, 1201):
        current = segment(t)
        buckets.pop(current - 10, None)
        if r.random() < .12:
            rate = r.choice([None, 0, 1, 2, 3, 4, 5])
        if r.random() < .08:
            cap = r.choice([None, 1, 2, 5, 20])
        if r.random() < .03:
            item = 1 - item
            mtotal = btotal = 0
            if not preserve:
                durations.clear()
                buckets.clear()
        if cap is not None and r.random() < .05:
            mtotal = btotal = 0
        candidate = r.choice([None, 0, 1])
        # The cumulative-count parameter when only the rate changes is identity here.
        common = candidate == item
        model = common and (cap is None or mtotal < cap) and (rate is None or len(durations) < rate)
        draft = common and (cap is None or btotal < cap) and (rate is None or sum(buckets.values()) < rate)
        assert (len(durations), model, mtotal) == (sum(buckets.values()), draft, btotal)
        if model:
            if rate is not None:
                durations.append(hold(t))
            mtotal += cap is not None
        if draft:
            if rate is not None:
                buckets[current] += 1
            btotal += cap is not None
        durations = [n - 1 for n in durations if n > 1]

for seed in range(200):
    for preserve in [False, True]:
        compare(seed, preserve)
print('13440 single-receipt comparisons; 480000 random decision steps passed')

# Counterexample, first two successive steps in segment 1, limit 1.
# A->B before step 1; the legal unspecified result for remaining times is [1].
left = [1]
model = []
for t in (1, 2):
    admitted = not left
    model.append(admitted)
    if admitted:
        left.append(hold(t))
    left = [n - 1 for n in left if n > 1]
print('After item switch with [1]:', model)
for count in [0, 1, 2]:
    path = []
    for t in (1, 2):
        path.append(count < 1)
        count += path[-1]
    print('Segment count:', path)
