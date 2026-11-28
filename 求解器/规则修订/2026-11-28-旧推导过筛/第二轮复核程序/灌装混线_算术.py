# 灌装混线：灌装机 3 台、恰 2 台各 ≥4 条存货通道。每台至多 0.2 批/tick（配方 5 tick、无冷却），每批耗 20 件，
# 故 ≥4 条通道的两台合计至多收 8 件/tick；总需 0.55 批/tick×20=11 件/tick，第 3 台须收 ≥3 件/tick，
# 而它至多 3 条有通过量的通道、每条 ≤1 件/tick（端口速率），故恰 3 条且每条每 tick 1 件，批次率 0.15。
from fractions import Fraction as Fr
need = Fr(55, 100) * 20
assert need == 11
for n_big_max in [Fr(4)]:
    third = need - 2 * n_big_max
    assert third == 3
for m in range(1, 51):
    P = 20 * m                       # 周期倍数：周期是 20 tick 的倍数
    batches = Fr(15, 100) * P
    assert batches.denominator == 1
    bottles = powder = 10 * batches
    per_ch = P                       # 每条每 tick 1 件
    assert bottles + powder == 3 * per_ch
    # 每条通道一个周期内只送一种时，瓶数只能是 j*P（j=0..3）
    pure = {j * per_ch for j in range(4)}
    assert bottles not in pure, m
    # 两条纯、一条混的分法存在（说明「至少 1 条」不能加强为「至少 2 条」）
    ok = any(a * per_ch + x == bottles for a in range(3) for x in range(1, per_ch))
    assert ok
print('m=1..50 全部通过：第 3 台每周期', '3m 批、耗瓶 30m、粉 30m；三条纯线的瓶数只能是 0、20m、40m、60m')
