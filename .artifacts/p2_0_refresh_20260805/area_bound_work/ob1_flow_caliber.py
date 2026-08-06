#!/usr/bin/env python3
"""OB1 —— F_route 口径钉死收据（P2.0 第七谓词语义）。

三口径并算（全部 Fraction 精确，零浮点）：
  (a) F_100      = 100% 占空 Σ（flow_account.json 的 F 口径：internal=min(prod,cons),
                   external=consumption, final=production）
  (b) F_balanced = min(prod,cons) 迭代不动点（flow_account.py §2b 同算法复刻）
  (c) F_target   = 钉死 production_targets 的精确平衡流量；
      F_route    = F_target − 无线终品交付流量（选定口径）

选定口径 = (c) 的 F_route（扣无线终品的进路由图流量）。
理由（写进 receipt）：
  - (a) 高估：mandatory 实例数是 ceil(精确机器当量) 的产物，100% 占空要求 49 台机器
    超过钉死目标运转，其流量不是目标语义下的必要流量；
  - (b) 低估且脱靶：min(prod,cons) 不动点产出 valley_battery < 18/min，
    是「目标不可行的一个状态」，引用它会低估必要流量；
  - (c) 是钉死目标下唯一精确平衡解（本脚本用 17 未知数 × 17 平衡方程的
    Fraction 高斯消元解出，零残差断言）；扣无线终品使上界论证不依赖任何
    终品交付语义（协议箱无线段 / hub 口贴放）的争议——保守方向，代价见 receipt。

只读输入：
  rules/canonical_rules.json                      (frozen, 事实来源)
  data/preprocessed/mandatory_exact_instances.json (266 实例普查交叉核对)
  .artifacts/band22_flow_account_20260805/flow_account.json (互证锚点, 08-06 复跑)
输出：ob1_flow_caliber_receipt.json（同目录）
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from fractions import Fraction

ROOT = "/home/zhuran24/zmd-pj"
CANON = f"{ROOT}/rules/canonical_rules.json"
INSTANCES = f"{ROOT}/data/preprocessed/mandatory_exact_instances.json"
FLOW_ACCOUNT = f"{ROOT}/.artifacts/band22_flow_account_20260805/flow_account.json"
OUT = f"{ROOT}/.artifacts/p2_0_refresh_20260805/area_bound_work/ob1_flow_caliber_receipt.json"


def load_canon():
    # Fraction 精确解析：float/int 字面量全部走 Fraction(str)
    with open(CANON) as f:
        return json.load(f, parse_float=Fraction, parse_int=Fraction)


def fstr(x: Fraction) -> str:
    x = Fraction(x)
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def main() -> None:
    canon = load_canon()
    tick_s = Fraction(canon["globals"]["time"]["tick_interval_seconds"])
    belt_per_tick = Fraction(canon["globals"]["logistics"]["belt_capacity_per_tick"])
    C_BELT = belt_per_tick * Fraction(60) / tick_s  # 件/分钟/格/层
    recipes = canon["recipes"]
    targets = canon["production_targets"]
    meta = canon["commodity_metadata"]

    ops = sorted(recipes)

    def rate_per_machine(op: str, table: str) -> dict[str, Fraction]:
        r = recipes[op]
        cycles_per_min = Fraction(60) / (Fraction(r["ticks_per_cycle"]) * tick_s)
        return {k: Fraction(q) * cycles_per_min for k, q in r[table].items()}

    out_rate = {op: rate_per_machine(op, "outputs") for op in ops}
    in_rate = {op: rate_per_machine(op, "inputs") for op in ops}

    # ---------- 目标速率：1 条满速线 = final_recipe 单机满速产出 ----------
    target_rate = {}
    for commodity, t in targets.items():
        assert t["mode"] == "equivalent_full_speed_lines", t["mode"]
        line_rate = out_rate[t["final_recipe_id"]][commodity]
        target_rate[commodity] = Fraction(t["value"]) * line_rate

    # ---------- 钉死目标精确解：17 未知数 (机器当量 x_op) × 17 方程 ----------
    # 方程：internal/cycle 商品 prod(x)=cons(x)；final 商品 prod(x)=target。
    commodities = sorted(meta)
    internal = [c for c in commodities if meta[c]["source_kind"] != "external_boundary"
                and meta[c]["sink_kind"] != "generic_input"]
    finals = [c for c in commodities if meta[c]["sink_kind"] == "generic_input"]
    externals = [c for c in commodities if meta[c]["source_kind"] == "external_boundary"]
    eq_comms = internal + finals
    assert len(eq_comms) == len(ops), (len(eq_comms), len(ops))

    A = [[Fraction(0)] * len(ops) for _ in eq_comms]
    b = [Fraction(0)] * len(eq_comms)
    for i, c in enumerate(eq_comms):
        for j, op in enumerate(ops):
            A[i][j] = out_rate[op].get(c, Fraction(0)) - (
                Fraction(0) if c in finals else in_rate[op].get(c, Fraction(0)))
        b[i] = target_rate.get(c, Fraction(0))

    # Fraction 高斯消元（部分选主元按非零即可，域是精确有理数）
    n = len(ops)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = next((r for r in range(col, n) if M[r][col] != 0), None)
        assert piv is not None, f"singular at col {col} ({ops[col]})"
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        M[col] = [v / pv for v in M[col]]
        for r in range(n):
            if r != col and M[r][col] != 0:
                f = M[r][col]
                M[r] = [v - f * w for v, w in zip(M[r], M[col])]
    x = {op: M[j][n] for j, op in enumerate(ops)}
    assert all(v > 0 for v in x.values()), "非正机器当量"

    # ---------- mandatory 普查交叉核对：n_op == ceil(x_op) ----------
    instances = json.load(open(INSTANCES))
    census_op = defaultdict(int)
    census_tpl = defaultdict(int)
    for inst in instances:
        census_tpl[inst["facility_type"]] += 1
        if inst["operation_type"] in recipes:
            census_op[inst["operation_type"]] += 1
    n_op = {op: math.ceil(x[op]) for op in ops}
    census_mismatch = {op: (n_op[op], census_op.get(op, 0))
                       for op in ops if n_op[op] != census_op.get(op, 0)}
    assert not census_mismatch, f"ceil(x) 与 mandatory 普查不符: {census_mismatch}"
    duty = {op: x[op] / n_op[op] for op in ops}

    # ---------- 逐商品流量的三份账 ----------
    def flows(duty_map: dict[str, Fraction], basis: str) -> dict[str, Fraction]:
        prod = defaultdict(Fraction)
        cons = defaultdict(Fraction)
        for op in ops:
            u = duty_map[op] * n_op[op]
            for k, r in out_rate[op].items():
                prod[k] += r * u
            for k, r in in_rate[op].items():
                cons[k] += r * u
        out = {}
        for c in commodities:
            if c in externals:
                out[c] = cons[c]
            elif c in finals:
                out[c] = prod[c]
            elif basis == "min":
                out[c] = min(prod[c], cons[c])
            else:  # exact: 断言零残差
                assert prod[c] == cons[c], (c, prod[c], cons[c])
                out[c] = prod[c]
        return out

    # (a) 100% 占空
    ones = {op: Fraction(1) for op in ops}
    flow_100 = flows(ones, "min")
    F_100 = sum(flow_100.values())

    # (b) min(prod,cons) 不动点（flow_account.py §2b 同算法）
    duty_bal = dict(ones)
    for _ in range(200):
        prod = defaultdict(Fraction)
        cons = defaultdict(Fraction)
        for op in ops:
            u = duty_bal[op] * n_op[op]
            for k, r in out_rate[op].items():
                prod[k] += r * u
            for k, r in in_rate[op].items():
                cons[k] += r * u
        worst = Fraction(1)
        scale = {op: Fraction(1) for op in ops}
        for k in commodities:
            if k in externals or cons[k] == 0:
                continue
            if prod[k] < cons[k]:
                s = prod[k] / cons[k]
                worst = min(worst, s)
                for op in ops:
                    if k in in_rate[op]:
                        scale[op] = min(scale[op], s)
        if worst == 1:
            break
        for op in ops:
            duty_bal[op] *= scale[op]
    flow_bal = flows(duty_bal, "min")
    F_bal = sum(flow_bal.values())

    # (c) 钉死目标精确解
    flow_target = flows(duty, "exact")
    F_target = sum(flow_target.values())
    F_finals = sum(flow_target[c] for c in finals)
    F_route = F_target - F_finals

    # ---------- 与 flow_account.json（08-06 复跑）互证 ----------
    fa = json.load(open(FLOW_ACCOUNT))
    fa_F = Fraction(fa["totals"]["F_items_per_min"])
    # flow_account.json 的 F_balanced_items_per_min 是 frac_str 的 4 位有效数字显示值
    # ("9084")，不是精确数；精确互证走 F_balanced_over_C（float，无损可比）。
    fa_Fbal_display = fa["totals"]["F_balanced_items_per_min"]
    fa_Fbal_over_C = fa["totals"]["F_balanced_over_C"]
    xcheck = {
        "flow_account_F_items_per_min": fstr(fa_F),
        "this_F_100": fstr(F_100),
        "F_100_matches_flow_account": F_100 == fa_F,
        "flow_account_F_balanced_display": fa_Fbal_display,
        "this_F_balanced_exact": fstr(F_bal),
        "this_F_balanced_float": float(F_bal),
        "F_balanced_matches_via_over_C": float(F_bal / C_BELT) == fa_Fbal_over_C,
        "display_rounding_finding": "flow_account.json 的 '9084' 是 frac_str 4 位有效数字舍入；"
                                    "精确值 = 290691/32 = 9084.09375（经 F_balanced_over_C=302.803125 无损互证）。"
                                    "凡引用 9,084 处应知其为显示值。",
        "note": "flow_account.json 走 IP faithful_mapping 配方；本脚本走 canonical 配方。"
                "两账相等 = 配方层互证（band22 faithful mapping 与 canonical 一致）。",
    }

    # ---------- 上界论证会用到的派生量 ----------
    derived = {
        "belt_capacity_items_per_min_per_cell_per_layer": fstr(C_BELT),
        "min_parallel_trunks_F_route": math.ceil(F_route / C_BELT),
        "route_cells_lb_single_layer_F_route": math.ceil(F_route / C_BELT),
        "route_cells_lb_double_layer_F_route": math.ceil(F_route / (2 * C_BELT)),
        "route_cells_lb_single_layer_if_finals_included": math.ceil(F_target / C_BELT),
        "route_cells_lb_double_layer_if_finals_included": math.ceil(F_target / (2 * C_BELT)),
        "caliber_cost_note": "扣无线终品使单层格位下界从 306 降到 305（差 1 格），"
                             "双层不变（153）。这 1 格是口径保守性的全部代价。",
    }

    receipt = {
        "ob": "OB1",
        "semantics_label": "P2.0 第七谓词语义（吞吐守恒）；与在案六谓词 U=(1188,18) conditional 并存不互斥",
        "date": "2026-08-06",
        "inputs": {
            "canonical_rules": "rules/canonical_rules.json (frozen)",
            "mandatory_instances": "data/preprocessed/mandatory_exact_instances.json (266)",
            "flow_account_cross_ref": ".artifacts/band22_flow_account_20260805/flow_account.json",
        },
        "chosen_caliber": {
            "name": "F_route = 钉死 production_targets 精确平衡流量 − 无线终品交付流量",
            "F_route_items_per_min": fstr(F_route),
            "F_target_items_per_min": fstr(F_target),
            "final_product_flows_excluded": {c: fstr(flow_target[c]) for c in finals},
            "why": "钉死目标是需求权威（前提 7）；扣无线终品使论证不依赖终品交付语义争议"
                   "（保守方向，代价 = 单层格位下界少 1 格）；(a) 超目标、(b) 脱靶，见 rejected_calibers",
        },
        "rejected_calibers": {
            "F_100_percent_duty": {
                "value": fstr(F_100),
                "reject_reason": "100% 占空要求 49 台机器超过钉死目标运转（duty 11/12 与 21/22 的两组），"
                                 "高估必要流量 0.83%；mandatory 台数本身是 ceil() 产物，满占空不是目标语义",
            },
            "F_balanced_fixed_point": {
                "value": fstr(F_bal),
                "reject_reason": "min(prod,cons) 不动点产出 valley_battery "
                                 f"{fstr(flow_bal['valley_battery'])}/min < 目标 {fstr(target_rate['valley_battery'])}/min，"
                                 "是目标不可行状态，低估必要流量",
            },
        },
        "pinned_target_solution": {
            "machine_equivalents_x": {op: fstr(x[op]) for op in ops},
            "mandatory_count_n": {op: n_op[op] for op in ops},
            "duty_x_over_n": {op: fstr(duty[op]) for op in ops},
            "duty_groups": {
                "full_speed_machines": sum(n_op[op] for op in ops if duty[op] == 1),
                "duty_11_12_machines": sum(n_op[op] for op in ops if duty[op] == Fraction(11, 12)),
                "duty_21_22_machines": sum(n_op[op] for op in ops if duty[op] == Fraction(21, 22)),
            },
            "zero_residual_assertion": "内部商品 prod==cons 逐项断言通过（exact basis）",
            "census_cross_check": "ceil(x_op) == mandatory 普查逐 op 相等（断言通过）",
        },
        "per_commodity_flow_at_pinned_target": {c: fstr(flow_target[c]) for c in commodities},
        "cross_check_flow_account": xcheck,
        "derived_for_area_bound": derived,
        "facility_census_by_template": dict(sorted(census_tpl.items())),
    }
    with open(OUT, "w") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=1)

    print("=== OB1 三口径（件/分钟，Fraction 精确） ===")
    print(f"(a) F_100      = {fstr(F_100)}   (flow_account 互证: {xcheck['F_100_matches_flow_account']})")
    print(f"(b) F_balanced = {fstr(F_bal)} (= {float(F_bal)}; flow_account 经 over_C 互证: "
          f"{xcheck['F_balanced_matches_via_over_C']}; json 里 '9084' 是 4 位有效数字显示值)")
    print(f"(c) F_target   = {fstr(F_target)}  F_route = {fstr(F_route)}  ← 选定口径")
    print(f"    扣除终品: {({c: fstr(flow_target[c]) for c in finals})}")
    print(f"占空组: 满速 {receipt['pinned_target_solution']['duty_groups']['full_speed_machines']} 台 / "
          f"11-12 {receipt['pinned_target_solution']['duty_groups']['duty_11_12_machines']} 台 / "
          f"21-22 {receipt['pinned_target_solution']['duty_groups']['duty_21_22_machines']} 台")
    print(f"单层格位下界 ceil(F_route/{fstr(C_BELT)}) = {derived['route_cells_lb_single_layer_F_route']}"
          f"（含终品则 {derived['route_cells_lb_single_layer_if_finals_included']}）")
    print(f"双层格位下界 = {derived['route_cells_lb_double_layer_F_route']}")
    print(f"receipt -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
