from itertools import product
from pathlib import Path
import re

rules = (Path(__file__).resolve().parents[4] / '《明日方舟：终末地》游戏规则.txt').read_text()
steps = int(re.search(r'每 1/(\d+) tick 为一步', rules)[1])
recipes = re.findall(r'→ (\d+) ([^，]+)，(\d+) tick', rules.split('\n配方\n')[1])
multiple = [(int(k), name, int(duration)) for k, name, duration in recipes if int(k) >= 2]
print(steps, multiple, '所有配方最短时长', min(int(r[2]) for r in recipes))
for k in sorted({r[0] for r in multiple}):
    checked = partial = zero_start = 0
    # 两相邻截面均取最后一步阶段4后。阶段5的批次到下一步才可送。
    # 每路首次空出后，一直等到取件。本刻只关心总数，同步取货的次序不影响它。
    for first in product(range(steps), repeat=k):
        newly_ready = [first.count(t) for t in range(steps)]
        for initial in range(51):
            for arrival in range(steps + 1):  # steps 表示没有新批可送
                stock = initial
                waiting = taken = 0
                for t, n in enumerate(newly_ready):
                    if t == arrival:
                        stock += k
                        if stock > 50:
                            break
                    waiting += n
                    sent = min(waiting, stock)
                    taken += sent
                    stock -= sent
                    waiting -= sent
                else:
                    checked += 1
                    partial += 0 < taken < k
                    zero_start += initial == 0
                    assert taken == k or stock == 0
                    if initial % k == 0:
                        assert taken in (0, k)
                    if initial == 0:
                        assert stock == 0
    print(k, checked, partial, zero_start, '通过')
