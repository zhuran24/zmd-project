#!/usr/bin/env python3
"""OB5 —— 面积上界总定理收据（机械组合 OB1/OB2/OB4 三份收据）。

定理链（P2.0 第七谓词语义；前提列表见 AREA_BOUND_THEOREM_REPORT.md）：
  [A] 格位分账（严格）：4900 = 机身 3544 + 4P + 非强制机身 N + 路由足迹 R + 空矩形 A + 空闲 S
      ⇒ A ≤ 1356 − 4P − R
  [B] 聚合吞吐唯一（严格）：钉死目标 ⇒ 17 操作的聚合活动/吞吐向量唯一
      （OB1 高斯消元非奇异；配方图含两个种子 SCC、非 DAG）⇒ F_route = 9135
  [C] 容量计数：state 数 L ≥ ceil(F_route/30) = 305
  [D] 足迹：每格至多 2 state（垂直交叉，owner 定谳真实机制）⇒ R ≥ ceil(L/2)
      （单层口径 R ≥ L 是【条件·待 OB6】——交叉密度上界未证）
  [E] 电杆：P ≥ 9（OB4 装填 IP，K=396；SCIP 双档交叉验证见 refute_20260806/）

历史（勿复活）：v2/v3 曾有 front-state 下界 L ≥ 308（「一个 state ≤1 产口 front
+1 耗口 front」引理），2026-08-06 被 refute 席以 canonical splitter/merger gadget
驳倒（一个 splitter state 可同时服务 1 产口+2 耗口，绑定模型 FEASIBLE），
反例与复跑记录在 refute_20260806/。本版基座退回 [C] 的 L ≥ 305。

输出：ob5_theorem_bound_receipt.json
"""
from __future__ import annotations

import json
import math
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

    board = ob2["totals"]["board_cells"]
    bodies = ob2["totals"]["mandatory_body_cells_total"]
    budget = board - bodies
    assert budget == ob2["totals"]["board_minus_bodies"] == 1356
    pole_cells = ob2["totals"]["power_pole_body_cells_each"]
    P_min = ob4["P_min"]
    F_route = parse_frac(ob1["chosen_caliber"]["F_route_items_per_min"])
    F_target = parse_frac(ob1["chosen_caliber"]["F_target_items_per_min"])
    C = parse_frac(ob1["derived_for_area_bound"]["belt_capacity_items_per_min_per_cell_per_layer"])

    L = math.ceil(F_route / C)                       # 305
    L_incl_finals = math.ceil(F_target / C)          # 306（G4 对照口径）

    fixed = budget - pole_cells * P_min              # 1320
    R_uncond = math.ceil(L / 2)
    A_uncond = fixed - R_uncond
    A_single = fixed - L
    A_single_incl_finals = fixed - L_incl_finals
    A_uncond_incl_finals = fixed - math.ceil(L_incl_finals / 2)

    # 敏感度：ℓ̄ = 逐件平均路径长度（state 数）；L(ℓ̄) ≥ ceil(304.5·ℓ̄)
    def bounds_at(mean_path: int) -> dict:
        Ll = math.ceil(F_route * mean_path / C)
        return {"L_ge": Ll, "A_single_le": fixed - Ll,
                "A_uncond_le": fixed - math.ceil(Ll / 2)}

    receipt = {
        "ob": "OB5（总定理收据）",
        "semantics_label": "P2.0 第七谓词语义（钉死 production_targets + 严格空地 + 吞吐守恒）。"
                           "与在案六谓词 U=(1188,18) conditional 语义不同、并存不互斥，禁止混写。",
        "date": "2026-08-06",
        "revision": "v8（五轮复核修正版；与报告版本号统一。v4=一轮撤引理退回 L≥305，"
                    "v5=二轮收敛修正，v6=三轮定义/引用级修正，v7=四轮 G1 等价性闭合，"
                    "v8=五轮 formal singleton 表述与记号统一——数值自 v4 起未变）",
        "component_receipts": {
            "F_route_9135": "ob1_flow_caliber_receipt.json",
            "bodies_3544_budget_1356": "ob2_body_budget_receipt.json",
            "P_min_9": "ob4_pole_lower_bound_receipt.json",
            "slot_census_diagnostic_only": "ob5_slot_census_receipt.json（MEMO 互证/诊断用，不进本界）",
        },
        "state_lower_bound": {
            "L_capacity_counting": L,
            "L_if_finals_included": L_incl_finals,
        },
        "area_bounds": {
            "unconditional_model_strict": {
                "A_le": A_uncond,
                "chain": f"A <= {budget} - {pole_cells}*{P_min} - {R_uncond} = {A_uncond}"
                         f"（R >= ceil(L/2) >= {R_uncond}，因 L >= {L}；对更大的真实 L 界只会更紧）",
                "grade": "【严格·模型内】（交叉最宽松口径：每格 2 state 无条件允许）",
            },
            "single_layer_conditional": {
                "A_le": A_single,
                "chain": f"A <= {budget} - {pole_cells}*{P_min} - {L} = {A_single}（R >= L >= {L}）",
                "grade": "【条件·待 OB6】（需证交叉密度上界；owner 定谳垂直交叉双满速真实存在）",
            },
            "finals_included_variant": {
                "A_single_le": A_single_incl_finals,
                "A_uncond_le": A_uncond_incl_finals,
                "note": "G4 对照：终品计入路由则 L≥306，单层收紧 1 格、无条件不变"
                        "（扣终品口径的全部保守代价）",
            },
        },
        "refuted_route_archive": {
            "claim": "front-state 下界 L≥308（引理：一个 route state ≤1 产口 front + 1 耗口 front）",
            "verdict": "REFUTED（refute 席 2026-08-06；canonical splitter/merger gadget，"
                       "绑定模型 FEASIBLE；本线亲手复跑复现）",
            "evidence": "refute_20260806/（探针+收据+复跑记录）",
            "premise_error": "把 route state 当成单向直通道；splitter/merger state 有多入/多出边，"
                             "可同时服务最多 4 个相邻口",
        },
        "sensitivity": {
            "per_extra_pole": -pole_cells,
            "per_extra_state": "单层 −1 格；无条件按奇偶交替 −1/0 格（R=ceil(L/2)）",
            "mean_path_length_table": {str(k): bounds_at(k) for k in (1, 2, 3)},
        },
    }
    with open(OUT, "w") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=1)

    print("=== OB5 面积上界总定理（v8，五轮复核修正版） ===")
    print(f"L（state 下界）: 容量计数 {L}（终品计入口径 {L_incl_finals}）")
    print(f"无条件【严格·模型内】: A ≤ {budget} − {pole_cells}·{P_min} − ⌈{L}/2⌉ = {A_uncond}")
    print(f"单层【条件·待OB6】  : A ≤ {budget} − {pole_cells}·{P_min} − {L} = {A_single}")
    print(f"终品计入对照: 单层 {A_single_incl_finals} / 无条件 {A_uncond_incl_finals}")
    print(f"ℓ̄ 敏感度表: {json.dumps(receipt['sensitivity']['mean_path_length_table'])}")
    print("front-state 路线: REFUTED，见 refute_20260806/")
    print(f"receipt -> {OUT}")


if __name__ == "__main__":
    main()
