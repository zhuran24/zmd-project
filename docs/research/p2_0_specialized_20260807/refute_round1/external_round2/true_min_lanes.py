"""核签独立验算 2：全网总车道数在所有合法占空分配上的真正可达最小值。

逐 (op, port) 下界 = max(n_op, ceil(c_p * x_op))：
  - Σ_i ceil(c·d_i) >= ceil(c·Σd_i) = ceil(c·x)   （ceil 次可加）
  - 每台 d_i > 0（n_op = ceil(x_op) ⇒ 不容闲置）⇒ 每台至少 1 条 ⇒ >= n_op
逐项下界同时可达 ⇒ 全网下界 = Σ 逐项下界。
"""
from fractions import Fraction as F
from math import ceil

OPS = {  # op: (n, x, ins{k:c}, outs{k:c})   —— 转自 rate_table_stdout.log 表B / v2 log Part A
    "crusher_blue_iron":        (34, F(34),     {"blue_iron_block": F(1)},   {"blue_iron_powder": F(1)}),
    "crusher_buckwheat":        (6,  F(11, 2),  {"buckwheat": F(1)},         {"buckwheat_powder": F(2)}),
    "crusher_sandleaf":         (11, F(21, 2),  {"sandleaf": F(1)},          {"sandleaf_powder": F(3)}),
    "crusher_source":           (18, F(18),     {"source_ore": F(1)},        {"source_powder": F(1)}),
    "filling_capsule":          (3,  F(11, 4),  {"fine_buckwheat_powder": F(2), "steel_bottle": F(2)}, {"qiaoyu_capsule": F(1, 5)}),
    "grinder_dense_blue_iron":  (17, F(17),     {"blue_iron_powder": F(2), "sandleaf_powder": F(1)},   {"dense_blue_iron_powder": F(1)}),
    "grinder_dense_source":     (9,  F(9),      {"sandleaf_powder": F(1), "source_powder": F(2)},      {"dense_source_powder": F(1)}),
    "grinder_fine_buckwheat":   (6,  F(11, 2),  {"buckwheat_powder": F(2), "sandleaf_powder": F(1)},   {"fine_buckwheat_powder": F(1)}),
    "molding_bottle":           (6,  F(11, 2),  {"steel_block": F(2)},       {"steel_bottle": F(1)}),
    "packaging_battery":        (3,  F(3),      {"dense_source_powder": F(3), "steel_part": F(2)},     {"valley_battery": F(1, 5)}),
    "parts_maker":              (6,  F(6),      {"steel_block": F(1)},       {"steel_part": F(1)}),
    "planter_buckwheat":        (11, F(11),     {"buckwheat_seed": F(1)},    {"buckwheat": F(1)}),
    "planter_sandleaf":         (21, F(21),     {"sandleaf_seed": F(1)},     {"sandleaf": F(1)}),
    "refinery_blue_iron":       (34, F(34),     {"blue_iron_ore": F(1)},     {"blue_iron_block": F(1)}),
    "refinery_steel":           (17, F(17),     {"dense_blue_iron_powder": F(1)}, {"steel_block": F(1)}),
    "seed_collector_buckwheat": (6,  F(11, 2),  {"buckwheat": F(1)},         {"buckwheat_seed": F(2)}),
    "seed_collector_sandleaf":  (11, F(21, 2),  {"sandleaf": F(1)},          {"sandleaf_seed": F(2)}),
}

def lanes_fill_first(rate): return ceil(rate) if rate else 0

total_lb = 0
uniform  = 0
stair    = 0
detail = []
for op, (n, x, ins, outs) in OPS.items():
    stair_duty = [F(1)] * (n - 1) + [x - (n - 1)] if x != n else [F(1)] * n
    assert sum(stair_duty) == x and all(F(0) < d <= 1 for d in stair_duty), op
    for side, ports in (("in", ins), ("out", outs)):
        for k, c in ports.items():
            lb = max(n, ceil(c * x))
            u  = sum(lanes_fill_first(c * (x / n)) for _ in range(n))
            s  = sum(lanes_fill_first(c * d) for d in stair_duty)
            total_lb += lb; uniform += u; stair += s
            if lb != u or lb != s:
                detail.append((op, side, k, lb, u, s))

print(f"制造端口车道数：逐项下界合计={total_lb}  均摊={uniform}  阶梯={stair}")
print(f"加 52 源口 + 2 终品汇口：下界={total_lb+54}  均摊={uniform+54}  阶梯={stair+54}")
print()
print("逐项下界 != 均摊 或 != 阶梯 的端口：")
for op, side, k, lb, u, s in detail:
    print(f"  {op:26s} {side:3s} {k:24s} 下界={lb:3d} 均摊={u:3d} 阶梯={s:3d}")
print()
print(f"阶梯是否处处达到逐项下界: {all(s == lb for _,_,_,lb,_,s in detail)}")
print(f"⇒ 全网总车道数在所有合法占空分配上的可达最小值 = {stair+54}（阶梯达到），不是 616。")
