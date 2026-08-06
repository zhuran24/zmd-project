#!/usr/bin/env python3
"""OB5 支撑收据 —— 端口 slot 普查与满带宽计数（脚本化，替代 MEMO 引理 1 的手抄数）。

slot 模型（前提 3）：slots = ceil(rate_per_tick / belt_capacity_per_tick)，
每 slot 均分：r_slot = duty · rate_per_tick / slots；满带宽 ⟺ r_slot == 1 件/tick。

产出（供面积上界 gap 分析引用）：
  - 制造机 slot 总数（含终品输出）/ 进路由图 slot 数（扣终品输出）
  - 钉死目标占空下的满带宽制造 slot 数
  - 外部源饱和 slot 当量（source_ore + blue_iron_ore 的 /tick 需求）
交叉核对 MEMO §2.1 引理 1 的 574 / 568 / 401 / 52。

只读输入：rules/canonical_rules.json + OB1 receipt（占空）
输出：ob5_slot_census_receipt.json
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from fractions import Fraction

ROOT = "/home/zhuran24/zmd-pj"
CANON = f"{ROOT}/rules/canonical_rules.json"
OB1 = f"{ROOT}/.artifacts/p2_0_refresh_20260805/area_bound_work/ob1_flow_caliber_receipt.json"
OUT = f"{ROOT}/.artifacts/p2_0_refresh_20260805/area_bound_work/ob5_slot_census_receipt.json"


def parse_frac(s: str) -> Fraction:
    if "/" in s:
        a, b = s.split("/")
        return Fraction(int(a), int(b))
    return Fraction(s)


def fstr(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def main() -> None:
    canon = json.load(open(CANON), parse_float=Fraction, parse_int=Fraction)
    ob1 = json.load(open(OB1))
    recipes = canon["recipes"]
    meta = canon["commodity_metadata"]
    belt = Fraction(canon["globals"]["logistics"]["belt_capacity_per_tick"])
    assert belt == 1
    duty = {op: parse_frac(s) for op, s in ob1["pinned_target_solution"]["duty_x_over_n"].items()}
    n_op = ob1["pinned_target_solution"]["mandatory_count_n"]
    finals = {c for c in meta if meta[c]["sink_kind"] == "generic_input"}
    externals = {c for c in meta if meta[c]["source_kind"] == "external_boundary"}

    rows = []
    total_slots = 0
    routed_slots = 0
    full_routed_slots = 0
    residual_bins = defaultdict(int)
    for op in sorted(recipes):
        r = recipes[op]
        ticks = Fraction(r["ticks_per_cycle"])
        n = int(n_op[op])
        for side, table in (("input", r["inputs"]), ("output", r["outputs"])):
            for commodity, qty in table.items():
                rate_per_tick = Fraction(qty) / ticks
                slots = math.ceil(rate_per_tick / belt)
                r_slot = duty[op] * rate_per_tick / slots  # 件/tick/slot
                is_final_out = side == "output" and commodity in finals
                total_slots += slots * n
                if not is_final_out:
                    routed_slots += slots * n
                    if r_slot == 1:
                        full_routed_slots += slots * n
                    else:
                        residual_bins[fstr(1 - r_slot)] += slots * n
                rows.append({
                    "operation": op, "side": side, "commodity": commodity,
                    "machines": n, "slots_per_machine": slots,
                    "rate_per_tick_per_machine": fstr(rate_per_tick),
                    "r_slot_at_pinned_duty": fstr(r_slot),
                    "full_bandwidth": bool(r_slot == 1),
                    "excluded_final_output": is_final_out,
                })

    # 外部源饱和 slot 当量：钉死目标下外部流入 / (1 件/tick/slot)
    flows = {c: parse_frac(v) for c, v in ob1["per_commodity_flow_at_pinned_target"].items()}
    ext_slots = {}
    ext_total = 0
    for c in sorted(externals):
        per_tick = flows[c] / 30  # 件/tick
        assert per_tick.denominator == 1, (c, per_tick)
        ext_slots[c] = int(per_tick)
        ext_total += int(per_tick)

    expected = {"total_slots": 574, "routed_slots": 568, "full_routed": 401, "ext_saturated": 52}
    got = {"total_slots": total_slots, "routed_slots": routed_slots,
           "full_routed": full_routed_slots, "ext_saturated": ext_total}
    assert got == expected, (got, expected)

    receipt = {
        "ob": "OB5-支撑（slot 普查）",
        "semantics_label": "P2.0 第七谓词语义；slot 模型 = 前提 3（slots=ceil(rate)，均分）",
        "date": "2026-08-06",
        "inputs": {"canonical_rules": "rules/canonical_rules.json (frozen)",
                   "ob1_receipt": "ob1_flow_caliber_receipt.json（占空 / 流量）"},
        "totals": {
            "manufacturing_slots_total": total_slots,
            "manufacturing_slots_routed": routed_slots,
            "final_output_slots_excluded": total_slots - routed_slots,
            "full_bandwidth_routed_slots": full_routed_slots,
            "external_saturated_slot_equivalents": ext_slots,
            "external_saturated_total": ext_total,
            "full_bandwidth_grand_total": full_routed_slots + ext_total,
            "sub_unity_routed_slots": routed_slots - full_routed_slots,
            "sub_unity_residual_bins_items_per_tick": dict(residual_bins),
        },
        "cross_check": "574/568/401/52 与 MEMO §2.1 引理 1 逐数字断言相符（本脚本独立从 canonical 重导）",
        "usage_caveat": "本普查是均分 slot 模型（前提 3）的口径，用于 MEMO 互证与 gap 分析。"
                        "端口『最小』数不是 slots×机器数：亚满占空 op 可占空集中，最小值 = ceil(x_op·q)"
                        "——定理收据 ob5_theorem_bound_receipt.json 用的是后者，勿混用（v1 曾因此超算 5 个 state）。",
        "per_stream": rows,
    }
    with open(OUT, "w") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=1)

    print("=== OB5 slot 普查 ===")
    print(f"制造机 slot 总数 = {total_slots}（进路由 {routed_slots}，扣终品输出 {total_slots - routed_slots}）")
    print(f"满带宽进路由 slot = {full_routed_slots}；外部源饱和 slot 当量 = {ext_total} {ext_slots}")
    print(f"满带宽合计 = {full_routed_slots + ext_total}；亚满带宽进路由 slot = {routed_slots - full_routed_slots}")
    print(f"亚满带宽残余分布（1−r_slot 件/tick -> slot 数）: {dict(residual_bins)}")
    print(f"receipt -> {OUT}")


if __name__ == "__main__":
    main()
