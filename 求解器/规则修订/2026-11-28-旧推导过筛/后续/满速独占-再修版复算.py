from fractions import Fraction as F

battery, capsule = F(18, 30), F(33, 60)
parts, bottles = 10*battery, 10*capsule
steel = parts + 2*bottles
blue, ore = 2*steel, 30*battery
flower = 10*capsule
sand = (steel + 15*battery + flower)/3
print("蓝铁矿、源矿、总需、出口上界", blue, ore, blue+ore, 2*(70//3)+6)
print("钢块、荞花粉碎批、砂叶粉碎批", steel, flower, sand)
for r in (0, 1):
    print("r、粉碎、精炼、配件、种植", r, blue+r+ore+flower+sand, blue+steel+r, parts, 2*(flower+sand))

# 逐步推进段窗口，先走完首段 3 步，此后每 4 步新开一段。
from collections import deque
for k in range(6):
    first_refusals = set()
    for start in range(1, 9):
        segments = deque([0], maxlen=10)
        first = None
        for step in range(1, start+8*100):
            if step % 4 == 0:
                segments.append(0)
            if step < start or (step-start) % 8:
                continue
            if sum(segments) < k:
                segments[-1] += 1
            elif first is None:
                first = (step-start)//8 + 1
        first_refusals.add(first)
    assert first_refusals == {k+1 if k<5 else None}
    print("k、八个首件步位的首次拒收件次", k, first_refusals)
