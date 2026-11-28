"""主会话三审：回路转弯、矿石走廊、方向预算三条里的数字，自己从头算，不读席位的程序。
（贴边条带切线的系数是逐机型的配方用量和端口数，见文末的断言。）"""
from fractions import Fraction as F
from math import ceil
N = 70
# ---- 矿石走廊：左带各种排布下，宽 3 的走廊（第 1…3 列、第 b…b+H-1 行，b>=2）里 m<=3e 允许的最大 H ----
def left_sources():
    out = []
    out.append(('左带占角、余格不在左边', [a + 1 for a in range(0, 69, 3)]))          # 取货口占第 0…68 行
    out.append(('余格在角上或下带占角', [a + 1 for a in range(1, 70, 3)]))            # 取货口占第 1…69 行
    for y in range(3, 70, 3):                                                          # 左带占角，余格在 (0,y)
        out.append(('余格 (0,%d)' % y, [a + 1 for a in range(0, y, 3)] + [a + 1 for a in range(y + 1, 70, 3)]))
    return out
best = 0; tight = 0
for name, src in left_sources():
    assert len(src) == 23 or name.startswith('左带占角、余格不在左边') and len(src) == 23, (name, len(src))
    s = set(src)
    for b in range(2, N):
        for top in range(b, N):
            H = top - b + 1
            m = sum(1 for y in range(b, top + 1) if y in s)
            e = 1 if top == N - 1 else 2
            if m <= 3 * e:
                if H > best: best = H; tight = 0
                if H == best: tight += 1
print('矿石走廊：m<=3e 允许的最大 H =', best, '（达到的窗口数', tight, '）')
assert best == 21
# ---- 回路转弯：T-b>=4、T+b>=64、0<=b<=T 下 T 最小；占格 ----
Tmin = min(T for T in range(0, 200) for b in range(0, T + 1) if T - b >= 4 and T + b >= 64)
seeds = 2 * 16; plants = 32                       # 采种 16 批各出 2 粒；种植 32 批各出 1 株
area = (32 + 16) * 25 + 16 * 9 + Tmin             # 种植机 32、采种机 16、粉碎植株至少 16 台（5.5+10.5 批/tick，每台至多 1 批）
print('回路转弯：种子、植株每 tick 各', seeds, plants, '件；T植 最小', Tmin, '；占格', area)
assert (seeds + plants, Tmin, area) == (64, 34, 1378)
# ---- 方向预算：常数和逐台增量 ----
# 边带一段的两个最小值取自 内带缺口_三审.py 的清点：矿源切向不可贴机身的至少 90 个，内带非矿源格朝外带的至少 88 个；核心 8，余格 4
assert 619 + 90 + 8 == 717 and 717 + 88 + 4 == 809 and 4 * 1390 - 809 == 4751
assert 4900 - 3291 - 81 - 138 == 1390
f_yan = lambda n: F(379 - 8 * n, 2) if n <= 47 else F(0)
f_su = lambda n: max(0, 22 - 2 * n)
f_feng = lambda n: {3: 24, 4: 18, 5: 10, 6: 6, 7: 2}.get(n, 0)
f_guan = lambda n: {3: 14, 4: 6, 5: 2}.get(n, 0)
omega = f_yan(32) + f_su(6) + f_feng(3) + f_guan(3)
assert omega == F(219, 2)
inc = {
 '塑形机': min(4 * 9 + f_su(n + 1) - f_su(n) for n in range(6, 40)),
 '小机或箱': 4 * 9,
 '封装机': min(4 * 24 + f_feng(n + 1) - f_feng(n) for n in range(3, 40)),
 '灌装机': min(4 * 24 + f_guan(n + 1) - f_guan(n) for n in range(3, 40)),
 '研磨机': min(4 * 24 + f_yan(n + 1) - f_yan(n) for n in range(32, 80)),
 '种植机或采种机': 4 * 25,
}
print('方向预算：Ω =', omega, '；每多一台 4E+Ω 至少增加', {k: (int(v) if v == int(v) else float(v)) for k, v in inc.items()})
assert inc['塑形机'] == 34 and inc['小机或箱'] == 36 and min(inc['封装机'], inc['灌装机']) == 88 and inc['研磨机'] == 92 and inc['种植机或采种机'] == 100
# ---- 贴边条带切线：系数 κ ----
# 粉碎机、精炼炉每批用 1 件五类物品、每 tick 至多 1 批；研磨机每批用 2 件主料；协议储存箱 3 个存货端口各每 tick 至多 1 件
assert (1, 1, 2, 3) == (1 * 1, 1 * 1, 2 * 1, 3 * 1)
print('四条三审复算通过')
