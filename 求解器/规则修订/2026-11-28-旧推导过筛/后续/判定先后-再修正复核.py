# 协议储存箱取货边 3 个端口：0 不接，1 接汇流器，2 接非汇流器（运输单位）
# 组：通往非汇流器的合为一组，通往汇流器的每条一组（规则第 43 行）
# 每步本箱每条通道至多判一次（第 59 行），传输位置 = 传输前已判次数 0..k
from itertools import product
from collections import Counter
byg, byc, pos_ch, pos_gr = Counter(), Counter(), Counter(), Counter()
worst = 0
for p in product(range(3), repeat=3):
    c = sum(1 for x in p if x)
    g = sum(1 for x in p if x == 1) + (1 if any(x == 2 for x in p) else 0)
    assert g <= c
    byg[g] += 1; byc[c] += 1
    pos_ch[c + 1] += 1; pos_gr[g + 1] += 1
    worst = max(worst, c + 1)
print("g分布", dict(sorted(byg.items())), "c分布", dict(sorted(byc.items())))
print("逐次读位置上界 c+1 分布", dict(sorted(pos_ch.items())), "最大", worst)
print("按组读位置上界 g+1 分布", dict(sorted(pos_gr.items())))
# 单组三条带、箱内 3 件、仓库全收：传输前已判 k 次 -> 无线入库 3-k
print("单组三带 无线入库", [3 - k for k in range(4)])
# g+1 与 c+1 不同的接法数
print("c>g 的接法数", sum(1 for p in product(range(3), repeat=3)
      if sum(1 for x in p if x) > sum(1 for x in p if x == 1) + (1 if 2 in p else 0)))
