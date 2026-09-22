# 供电覆盖：两种读法下，一个 2x2 供电桩最多能给多少台 3x3 制造单位供电
# 桩占格 (a,a+1)x(b,b+1)，中心 c=(a+1,b+1)（格交点）
# positive_area: 覆盖格集合 i in [a-5, a+6], j in [b-5, b+6]   （12x12）
# closed_touch : 覆盖格集合 i in [a-6, a+7], j in [b-6, b+7]   （14x14）
from itertools import product

def best(lo, hi, a, b):
    # 一维：3格机器起点 m 使 [m,m+2] 与 [lo,hi] 相交
    ms = [m for m in range(lo-2, hi+1)]
    # 贪心取最多两两不相交的
    picks=[]; cur=ms[0]
    while cur <= ms[-1]:
        picks.append(cur); cur += 3
    return picks

for name, lo_off, hi_off in [("positive_area",-5,6), ("closed_touch",-6,7)]:
    a=b=30
    lo, hi = a+lo_off, a+hi_off
    cols = best(lo, hi, a, b); rows = best(b+lo_off, b+hi_off, a, b)
    total=0; blocked=0
    for m,n in product(cols, rows):
        # 机器占 [m,m+2]x[n,n+2]，不得与桩 (a,a+1)x(b,b+1) 重叠
        ov = (m<=a+1 and m+2>=a) and (n<=b+1 and n+2>=b)
        if ov: blocked+=1
        else: total+=1
    print(f"{name}: 覆盖格 {hi-lo+1}x{hi-lo+1}, 每轴机位 {len(cols)}, 总格位 {len(cols)*len(rows)}, 被桩挡 {blocked}, 可供电台数 {total}")
