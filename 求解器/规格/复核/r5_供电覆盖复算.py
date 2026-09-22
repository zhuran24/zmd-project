# 独立复算：一个供电桩在两种覆盖读法下至多能为多少台 3x3 制造单位供电
# 桩 2x2 占格 (a,a+1) x (b,b+1)，中心 (a+1,b+1)，12x12 范围 = [a-5, a+7]
def cover_cols(a, rule, lo, hi):
    if rule == 'positive':      # 格方块完全落在 [a-5,a+7] 内
        rng = range(a-5, a+7)
    else:                       # closed_touch：格方块与闭区间有交（含只碰边界线）
        rng = range(a-6, a+8)
    return [i for i in rng if lo <= i <= hi]

def max_machines(a, b, rule, lo=0, hi=69):
    cc = cover_cols(a, rule, lo, hi); rr = cover_cols(b, rule, lo, hi)
    if not cc or not rr: return 0
    best = 0
    # 3x3 机器左下角 p；与覆盖列集合有交即可被供电；机器须整体在基地内
    for offx in range(3):
        for offy in range(3):
            xs = [p for p in range(lo-2+offx, hi+1, 3) if p >= lo and p+2 <= hi
                  and any(p <= i <= p+2 for i in cc)]
            ys = [q for q in range(lo-2+offy, hi+1, 3) if q >= lo and q+2 <= hi
                  and any(q <= j <= q+2 for j in rr)]
            n = 0
            for p in xs:
                for q in ys:
                    # 不得与桩 2x2 占格重叠
                    if not (p <= a+1 and a <= p+2 and q <= b+1 and b <= q+2):
                        n += 1
            best = max(best, n)
    return best

for name, (a, b) in [('内部桩', (30, 30)), ('贴左边界桩 a=0', (0, 30)),
                     ('贴右边界桩 a=68', (68, 30)), ('角桩 a=b=0', (0, 0))]:
    print(f"{name}: positive_area={max_machines(a,b,'positive')}  closed_touch={max_machines(a,b,'touch')}")
