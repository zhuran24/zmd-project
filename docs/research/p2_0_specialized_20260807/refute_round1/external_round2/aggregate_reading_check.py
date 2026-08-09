"""核签独立验算：canonical 前件(ii)的「逐商品聚合最小 ceil(F_k/C)」读法是否可被任何合法占空分配满足。

若不可满足，则该读法是空读法，不能用来支撑「前件与结论互斥」。
输入全部转自我方已归档日志（rate_table_stdout.log 表D、split_free_probe_v2_stdout.log Part A）。
"""
from fractions import Fraction as F
from math import ceil

# op -> (n_op, x_op, {commodity: 满速系数}) 出口侧
OUT = {
    "filling_capsule":   (3,  F(11, 4), {"qiaoyu_capsule": F(1, 5)}),
    "packaging_battery": (3,  F(3),     {"valley_battery": F(1, 5)}),
}
# 商品总流量（件/tick），C=1
F_K = {"qiaoyu_capsule": F(11, 20), "valley_battery": F(3, 5)}

print("=== 逐商品聚合下界 ceil(F_k/C) vs 产侧结构性最少车道 ===")
for op, (n, x, outs) in OUT.items():
    for k, c in outs.items():
        agg_floor = ceil(F_K[k])
        # 每台机器占空必须 > 0（n_op = ceil(x_op)，少一台够不到产量），
        # 每台的出口速率 > 0 ⇒ 每台至少占 1 条产道 ⇒ 产侧车道数 >= n
        assert n == ceil(x), (op, n, x)
        structural_min = n
        print(f"{k:16s} F_k={F_K[k]}  ceil(F_k/C)={agg_floor}  机器台数 n_op={n} "
              f"⇒ 产侧车道数 >= {structural_min}  聚合读法可满足={structural_min <= agg_floor}")

print()
print("=== 结论 ===")
print("qiaoyu_capsule / valley_battery 各 3 台机器、每台占空必 > 0，")
print("每台的出口是独立物理端口 ⇒ 产侧至少 3 条道，而聚合下界只给 1 条。")
print("故『全网总车道数 = 616』对任何合法占空分配都不可达；")
print("按该读法，前件(ii) 的满足集为空 ⇒ 它不可能是 canonical 的本意，")
print("也就不能用它来论证『最满足前件(ii)的那份分配恰是破结论的那份』。")
print()
print("=== 阶梯 622 的超额分解（对照 616）===")
excess = {"qiaoyu_capsule(产侧)": 3 - 1, "valley_battery(产侧)": 3 - 1,
          "buckwheat(耗侧)": 12 - 11, "sandleaf(耗侧)": 22 - 21}
print(f"622 - 616 = {622-616}；逐项：{excess}；合计 {sum(excess.values())}")
print("其中 qiaoyu/valley 的 4 条超额是结构性不可消的（机器台数下限），")
print("buckwheat/sandleaf 的 2 条超额是定理 1 的强制分支 ⇒ 也不可消。")
print("⇒ 阶梯 622 已是聚合读法下的可达最小值；均摊 628 的 6 条超额才是真正『多用的道』。")
