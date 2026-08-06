#!/usr/bin/env python3
"""OB5 —— 面积上界总定理收据（机械组合 OB1/OB2/OB4/slot 普查四份收据）。

定理链（P2.0 第七谓词语义；前提列表见 AREA_BOUND_THEOREM_REPORT.md）：
  [A] 格位分账（严格）：4900 = 机身 3544 + 4P + 非强制机身 N + 路由足迹 R + 空矩形 A + 空闲 S
      ⇒ A ≤ 1356 − 4P − R
  [B] 流量唯一（严格）：钉死目标 ⇒ 商品流向量唯一（OB1 高斯消元非奇异）⇒ F_route = 9135
  [C1] 容量计数：state 数 L ≥ ceil(F_route/30) = 305
  [C2] front-state 匹配（本批新增，更强）：620 个进路由 slot 各需 front state；
       一个 state 至多服务一对 rate 相等的正对产耗口 ⇒ 配对数 ≤ Σ_c min(#out_c,#in_c)
       ⇒ L ≥ 620 − Pmax
  [D] 足迹：每格至多 2 个 state（垂直交叉，owner 定谳为真实机制）⇒ R ≥ ceil(L/2)
      （单层口径 R ≥ L 是【条件·待 OB6】——交叉密度上界未证）
  [E] 电杆：P ≥ 9（OB4 装填 IP）
输出：ob5_theorem_bound_receipt.json
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from fractions import Fraction

ROOT = "/home/zhuran24/zmd-pj"
WORK = f"{ROOT}/.artifacts/p2_0_refresh_20260805/area_bound_work"
OUT = f"{WORK}/ob5_theorem_bound_receipt.json"


def parse_frac(s) -> Fraction:
    s = str(s)
    if "/" in s:
        a, b = s.split("/")
        return Fraction(int(a), int(b))
    return Fraction(s)


def main() -> None:
    ob1 = json.load(open(f"{WORK}/ob1_flow_caliber_receipt.json"))
    ob2 = json.load(open(f"{WORK}/ob2_body_budget_receipt.json"))
    ob4 = json.load(open(f"{WORK}/ob4_pole_lower_bound_receipt.json"))
    slots = json.load(open(f"{WORK}/ob5_slot_census_receipt.json"))
    canon = json.load(open(f"{ROOT}/rules/canonical_rules.json"),
                      parse_float=Fraction, parse_int=Fraction)

    board = ob2["totals"]["board_cells"]
    bodies = ob2["totals"]["mandatory_body_cells_total"]
    budget = board - bodies
    assert budget == ob2["totals"]["board_minus_bodies"] == 1356
    pole_cells = ob2["totals"]["power_pole_body_cells_each"]
    P_min = ob4["P_min"]
    F_route = parse_frac(ob1["chosen_caliber"]["F_route_items_per_min"])
    C = parse_frac(ob1["derived_for_area_bound"]["belt_capacity_items_per_min_per_cell_per_layer"])

    # [C1] 容量计数
    L_capacity = math.ceil(F_route / C)

    # [C2] front-state 下界：L ≥ Σ_c max(#out_c, #in_c)，
    # 其中 #side_c = Σ_op ceil(x_op · q_op,c,side)（端口最小数）。
    # 关键修正（v2，自攻发现）：端口最小数不是 slot 数 × 机器数——
    # 亚满占空 op 可把占空集中（floor(x) 台满速 + 1 台残速），
    # 每 op 的端口需求下界只有 ceil(总流/tick) = ceil(x·q)，对占空集中与
    # slot 不均分均鲁棒（口容量 1 件/tick 是硬帽）。
    x_op = {op: parse_frac(s) for op, s in ob1["pinned_target_solution"]["machine_equivalents_x"].items()}
    recipes = canon["recipes"]
    meta = canon["commodity_metadata"]
    finals = {c for c in meta if meta[c]["sink_kind"] == "generic_input"}
    out_ports = defaultdict(Fraction)
    in_ports = defaultdict(Fraction)
    for op, r in recipes.items():
        ticks = Fraction(r["ticks_per_cycle"])
        for c, qty in r["outputs"].items():
            if c in finals:
                continue  # 终品不进路由图（OB1 口径）
            out_ports[c] += math.ceil(x_op[op] * Fraction(qty) / ticks)
        for c, qty in r["inputs"].items():
            in_ports[c] += math.ceil(x_op[op] * Fraction(qty) / ticks)
    ext = slots["totals"]["external_saturated_slot_equivalents"]
    for c, k in ext.items():
        out_ports[c] += k  # 外部源供给口当量（46 boundary + 6 core，总数恰 = 需求 52）

    pair_table = {}
    L_matching = 0
    for c in sorted(set(out_ports) | set(in_ports)):
        m = int(max(out_ports[c], in_ports[c]))
        pair_table[c] = {"out_ports_min": int(out_ports[c]),
                         "in_ports_min": int(in_ports[c]), "states_min": m}
        L_matching += m
    L = max(L_capacity, L_matching)

    # [D] 足迹两口径
    R_uncond = math.ceil(L / 2)              # 交叉最宽松（无条件·严格）
    R_single = L                              # 单层口径（条件·待 OB6）
    A_uncond = budget - pole_cells * P_min - R_uncond
    A_single = budget - pole_cells * P_min - R_single
    A_capacity_only_uncond = budget - pole_cells * P_min - math.ceil(L_capacity / 2)
    A_capacity_only_single = budget - pole_cells * P_min - L_capacity

    receipt = {
        "ob": "OB5（总定理收据）",
        "semantics_label": "P2.0 第七谓词语义（钉死 production_targets + 严格空地 + 吞吐守恒）。"
                           "与在案六谓词 U=(1188,18) conditional 语义不同、并存不互斥，禁止混写。",
        "date": "2026-08-06",
        "component_receipts": {
            "F_route_9135": "ob1_flow_caliber_receipt.json",
            "bodies_3544_budget_1356": "ob2_body_budget_receipt.json",
            "P_min_9": "ob4_pole_lower_bound_receipt.json",
            "slots_620": "ob5_slot_census_receipt.json",
        },
        "state_lower_bounds": {
            "L_capacity_counting": L_capacity,
            "L_front_state_matching": L_matching,
            "L_used": L,
            "matching_detail": {
                "formulation": "L ≥ Σ_c max(#out_c, #in_c)，#side_c = Σ_op ceil(x_op·q)（端口最小数）。"
                               "核心引理：一个 route state 至多充当 1 个产口 front 与 1 个耗口 front"
                               "（belt 方向性 + 通道死端于机身 + 门口排他 ⇒ 同商品才可共享），"
                               "故逐商品 front state ≥ max(out,in)。"
                               "鲁棒性：对『多开口摊薄速率』（多一口 ⇒ 至少多一 front state）、"
                               "『机器间占空集中』与『slot 不均分』（端口最小数取 ceil(x·q) 已是"
                               "这两个自由度下的最小值，口容量 1 件/tick 硬帽）全部免疫。",
                "v1_overcount_note": "v1 曾用 slot×机器数 得 L≥313——被『占空集中到 floor(x) 台』"
                                     "反例攻破（多算 5），本版 308 为修正值。",
                "per_commodity": pair_table,
            },
        },
        "area_bounds": {
            "unconditional_model_strict": {
                "A_le": A_uncond,
                "chain": f"A <= {budget} - {pole_cells}*{P_min} - ceil({L}/2)={R_uncond}",
                "grade": "【严格·模型内】（交叉最宽松口径：每格 2 state 无条件允许）",
            },
            "single_layer_conditional": {
                "A_le": A_single,
                "chain": f"A <= {budget} - {pole_cells}*{P_min} - {R_single}",
                "grade": "【条件·待 OB6】（需证交叉密度上界；owner 定谳垂直交叉双满速真实存在）",
            },
            "capacity_only_for_reference": {
                "unconditional": A_capacity_only_uncond,
                "single_layer": A_capacity_only_single,
                "note": "不用 C2 匹配、只用 C1 容量计数的对照值（= MEMO §3.3 口径 + P_min 升级）",
            },
        },
        "sensitivity": {
            "per_extra_pole": -pole_cells,
            "per_extra_state": "单层 −1 / 无条件 −0.5 格",
            "per_unit_mean_path_length": "ℓ̄ 每 +1 ⇒ 所需 state +ceil(304.5) ⇒ 单层 A −305",
        },
    }
    with open(OUT, "w") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=1)

    print("=== OB5 面积上界总定理 ===")
    print(f"L（state 下界）: 容量 {L_capacity} / front-state Σmax {L_matching} → 取 {L}")
    print(f"无条件【严格·模型内】: A ≤ {budget} − {pole_cells}·{P_min} − ⌈{L}/2⌉ = {A_uncond}")
    print(f"单层【条件·待OB6】  : A ≤ {budget} − {pole_cells}·{P_min} − {L} = {A_single}")
    print(f"对照（仅容量计数）  : 无条件 {A_capacity_only_uncond} / 单层 {A_capacity_only_single}")
    print(f"receipt -> {OUT}")


if __name__ == "__main__":
    main()
