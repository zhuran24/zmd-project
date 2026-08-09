#!/usr/bin/env python3
"""P2.0 特化设计稿的速率常数表（2026-08-07）。

目的：把「钉死 production_targets ⇒ 每种商品的稳态速率是常数」这条特化命题
算成一张可直接当建模系数用的表，全程 Fraction 精确、零浮点。

产出五张表：
  A. 逐商品聚合速率（19 商品）+ F_route 复算（与 OB1 收据互证）
  B. 逐 (operation, 侧, 商品) 的单机端口速率与**车道分解**（满道数 + 残道速率）
  C. 车道速率多重集 + **两两共道合法性矩阵**（判定哪些车道对可以共用一格）
  D. 每商品的全局最小车道数 L_k = ceil(F_k / C)
  E. 生产规模下的约束行数量级估算

用法：python docs/research/p2_0_specialized_20260807/rate_table.py
输出：rate_table_receipt.json + stdout（同目录 rate_table_stdout.log）

只读输入（全部 frozen 或 tracked）：
  rules/canonical_rules.json
  data/preprocessed/mandatory_exact_instances.json
  data/preprocessed/generic_io_requirements.json
  .artifacts/p2_0_refresh_20260805/area_bound_work/ob1_flow_caliber_receipt.json（互证锚点）
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
CANON = f"{ROOT}/rules/canonical_rules.json"
INSTANCES = f"{ROOT}/data/preprocessed/mandatory_exact_instances.json"
GENERIC_IO = f"{ROOT}/data/preprocessed/generic_io_requirements.json"
OB1 = f"{ROOT}/.artifacts/p2_0_refresh_20260805/area_bound_work/ob1_flow_caliber_receipt.json"
OUT = f"{os.path.dirname(os.path.abspath(__file__))}/rate_table_receipt.json"


def fstr(x: Fraction) -> str:
    x = Fraction(x)
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def ceil_frac(x: Fraction) -> int:
    return -((-x.numerator) // x.denominator)


def main() -> int:
    with open(CANON) as f:
        canon = json.load(f, parse_float=Fraction, parse_int=Fraction)

    tick_s = Fraction(canon["globals"]["time"]["tick_interval_seconds"])
    belt_cap = Fraction(canon["globals"]["logistics"]["belt_capacity_per_tick"])
    port_cap = Fraction(canon["globals"]["logistics"]["port_max_throughput_per_tick"])
    ticks_per_min = Fraction(60) / tick_s
    C_min = belt_cap * ticks_per_min  # 件/分钟/格/层

    recipes = canon["recipes"]
    targets = canon["production_targets"]
    meta = canon["commodity_metadata"]
    ops = sorted(recipes)
    commodities = sorted(meta)

    # ---------- 单机满速速率（件/tick） ----------
    def per_machine_full(op: str, table: str) -> dict[str, Fraction]:
        r = recipes[op]
        return {k: Fraction(q) / Fraction(r["ticks_per_cycle"])
                for k, q in r[table].items()}

    out_rate = {op: per_machine_full(op, "outputs") for op in ops}
    in_rate = {op: per_machine_full(op, "inputs") for op in ops}

    # ---------- 目标速率（件/tick） ----------
    target_rate: dict[str, Fraction] = {}
    for commodity, t in targets.items():
        assert t["mode"] == "equivalent_full_speed_lines", t["mode"]
        target_rate[commodity] = (Fraction(t["value"])
                                  * out_rate[t["final_recipe_id"]][commodity])

    # ---------- 17x17 精确解：机器当量 x_op ----------
    internal = [c for c in commodities
                if meta[c]["source_kind"] != "external_boundary"
                and meta[c]["sink_kind"] != "generic_input"]
    finals = [c for c in commodities if meta[c]["sink_kind"] == "generic_input"]
    externals = [c for c in commodities
                 if meta[c]["source_kind"] == "external_boundary"]
    eq_comms = internal + finals
    assert len(eq_comms) == len(ops), (len(eq_comms), len(ops))

    n = len(ops)
    M = []
    for c in eq_comms:
        row = [out_rate[op].get(c, Fraction(0))
               - (Fraction(0) if c in finals else in_rate[op].get(c, Fraction(0)))
               for op in ops]
        row.append(target_rate.get(c, Fraction(0)))
        M.append(row)
    for col in range(n):
        piv = next((r for r in range(col, n) if M[r][col] != 0), None)
        assert piv is not None, f"singular at {ops[col]}"
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        M[col] = [v / pv for v in M[col]]
        for r in range(n):
            if r != col and M[r][col] != 0:
                fac = M[r][col]
                M[r] = [v - fac * w for v, w in zip(M[r], M[col])]
    x = {op: M[j][n] for j, op in enumerate(ops)}
    assert all(v > 0 for v in x.values()), "非正机器当量"

    # ---------- mandatory 普查交叉核对 ----------
    with open(INSTANCES) as f:
        instances = json.load(f)
    census = defaultdict(int)
    for inst in instances:
        if inst["operation_type"] in recipes:
            census[inst["operation_type"]] += 1
    n_op = {op: ceil_frac(x[op]) for op in ops}
    mismatch = {op: (n_op[op], census.get(op, 0))
                for op in ops if n_op[op] != census.get(op, 0)}
    assert not mismatch, f"ceil(x) 与普查不符: {mismatch}"
    duty = {op: x[op] / n_op[op] for op in ops}

    # ================= 表 A：逐商品聚合速率 =================
    prod = defaultdict(Fraction)
    cons = defaultdict(Fraction)
    for op in ops:
        for k, r in out_rate[op].items():
            prod[k] += r * x[op]
        for k, r in in_rate[op].items():
            cons[k] += r * x[op]

    table_a = {}
    for c in commodities:
        if c in externals:
            flow, role = cons[c], "external_boundary"
        elif c in finals:
            flow, role = prod[c], "final_generic_input"
        else:
            assert prod[c] == cons[c], (c, prod[c], cons[c])
            flow, role = prod[c], "internal"
        table_a[c] = {
            "role": role,
            "cycle_group": meta[c]["cycle_group"],
            "production_per_tick": fstr(prod[c]),
            "consumption_per_tick": fstr(cons[c]),
            "routed_flow_per_tick": fstr(flow),
            "routed_flow_per_min": fstr(flow * ticks_per_min),
            "min_lanes_global": ceil_frac(flow / belt_cap),
        }

    F_target = sum(
        (cons[c] if c in externals else prod[c]) for c in commodities)
    F_finals = sum(prod[c] for c in finals)
    F_route = F_target - F_finals

    # 与 OB1 收据互证
    with open(OB1) as f:
        ob1 = json.load(f)
    ob1_F_route = ob1["chosen_caliber"]["F_route_items_per_min"]
    ob1_F_target = ob1["chosen_caliber"]["F_target_items_per_min"]
    xcheck = {
        "ob1_F_route_items_per_min": ob1_F_route,
        "this_F_route_items_per_min": fstr(F_route * ticks_per_min),
        "F_route_agrees": fstr(F_route * ticks_per_min) == ob1_F_route,
        "ob1_F_target_items_per_min": ob1_F_target,
        "this_F_target_items_per_min": fstr(F_target * ticks_per_min),
        "F_target_agrees": fstr(F_target * ticks_per_min) == ob1_F_target,
    }
    assert xcheck["F_route_agrees"] and xcheck["F_target_agrees"], xcheck

    # ================= 表 B：逐端口车道分解 =================
    # 单机某侧某商品速率 r = qty * duty / tpc；占用车道 = ceil(r/cap)，
    # 前 lanes-1 条满载 cap，末条残余 r-(lanes-1)*cap。
    table_b = []
    lane_multiset: dict[Fraction, int] = defaultdict(int)   # 车道速率 -> 条数
    lane_owner: dict[Fraction, set] = defaultdict(set)      # 车道速率 -> 商品集
    total_slots = 0
    for op in ops:
        for side, tbl in (("in", in_rate), ("out", out_rate)):
            for commodity, full in sorted(tbl[op].items()):
                r = full * duty[op]
                lanes = ceil_frac(r / belt_cap)
                residual = r - (lanes - 1) * belt_cap
                assert Fraction(0) < residual <= belt_cap
                table_b.append({
                    "operation": op,
                    "side": side,
                    "commodity": commodity,
                    "machines": n_op[op],
                    "duty": fstr(duty[op]),
                    "rate_per_machine_per_tick": fstr(r),
                    "slots_per_machine": lanes,
                    "full_lanes_per_machine": lanes - 1,
                    "residual_lane_rate": fstr(residual),
                    "slots_total": lanes * n_op[op],
                })
                total_slots += lanes * n_op[op]
                if lanes - 1 > 0:
                    lane_multiset[belt_cap] += (lanes - 1) * n_op[op]
                    lane_owner[belt_cap].add(commodity)
                lane_multiset[residual] += n_op[op]
                lane_owner[residual].add(commodity)

    # ================= 表 C：两两共道合法性 =================
    # 一格一层的聚合容量 = belt_cap。两条车道可共用一格 <=> 速率之和 <= belt_cap。
    distinct = sorted(lane_multiset)
    pair_rows = []
    illegal_intermediate_pairs = 0
    legal_pairs = []
    terminal_set = set(finals)
    for i, a in enumerate(distinct):
        for b in distinct[i:]:
            fits = (a + b) <= belt_cap
            owners_a, owners_b = lane_owner[a], lane_owner[b]
            only_terminal = (owners_a <= terminal_set) and (owners_b <= terminal_set)
            pair_rows.append({
                "rate_a": fstr(a), "rate_b": fstr(b),
                "sum": fstr(a + b),
                "co_resident_legal": fits,
                "both_sides_terminal_only": only_terminal,
            })
            if fits:
                legal_pairs.append((a, b, only_terminal))
                if not only_terminal:
                    illegal_intermediate_pairs += 1
    # 引理断言：任何合法共道对，两侧车道的商品必须全部是终端成品
    assert illegal_intermediate_pairs == 0, (
        "存在涉及中间品的合法共道对 —— 速率引理的纯流强制被推翻", legal_pairs)

    # 终端成品自身的合并上限：两条终端**全流**车道能否共道
    term_full = {c: prod[c] for c in finals}
    term_pair_sum = sum(term_full.values())
    terminal_full_merge_legal = term_pair_sum <= belt_cap

    # ================= 表 D：全局最小车道数 =================
    table_d = {c: table_a[c]["min_lanes_global"] for c in commodities}
    total_min_lanes = sum(table_d.values())
    total_min_lanes_route = sum(v for c, v in table_d.items() if c not in finals)

    # ================= 表 E：行数量级估算 =================
    GRID = 70
    LAYERS = 2
    cell_layers = GRID * GRID * LAYERS
    K = len(commodities)
    K_route = K - len(finals)
    table_e = {
        "grid_cells": GRID * GRID,
        "cell_layer_slots": cell_layers,
        "commodities_total": K,
        "commodities_excluding_finals": K_route,
        "row_family_P1_purity_upper_bound": {
            "form": "每 (cell, layer)：Σ_{k∈中间品} u[c,l,k] ≤ 1",
            "rows_upper_bound": cell_layers,
            "coeff": "全部 1（纯组合行，无有理系数）",
            "note": "上界按整棋盘算；实际只需在候选 free cell 上建行，"
                    "机身 3,544 格与空矩形 A 格不建行",
        },
        "row_family_P2_terminal_capacity": {
            "form": "每 (cell, layer)：Σ_{k∈终品} ρ_k·u[c,l,k] ≤ cap（有理系数）",
            "rows_upper_bound": cell_layers,
            "integerized_multiplier_lcm": None,  # 下面填
        },
        "row_family_P3_per_commodity_congestion": {
            "form": "每商品 k：在 k 占用的格子上存在容量 cap 的单商品流（割集/最大流）",
            "count": K,
            "note": "不是静态行，是每商品一个单商品流可行性子问题；"
                    "不可行证书 = 最小割（组合，非 Farkas）",
        },
        "port_slots_total_from_recipes": total_slots,
    }

    # 终品系数整数化的公分母
    term_rates = [prod[c] for c in finals]
    lcm_den = 1
    for r in term_rates + [belt_cap]:
        lcm_den = lcm_den * r.denominator // math.gcd(lcm_den, r.denominator)
    table_e["row_family_P2_terminal_capacity"]["integerized_multiplier_lcm"] = lcm_den

    # 全体车道速率的公分母（若要把全部行整数化）
    lcm_all = 1
    for r in distinct:
        lcm_all = lcm_all * r.denominator // math.gcd(lcm_all, r.denominator)
    table_e["all_lane_rate_common_denominator"] = lcm_all

    receipt = {
        "artifact": "p2_0_specialized_rate_table",
        "date": "2026-08-07",
        "semantics_label": "P2.0 第七谓词特化语义（钉死 production_targets + 最小车道分配前件）；"
                           "与在案六谓词 U=(1188,18) conditional 并存不互斥",
        "constants": {
            "tick_interval_seconds": fstr(tick_s),
            "belt_capacity_per_tick": fstr(belt_cap),
            "port_max_throughput_per_tick": fstr(port_cap),
            "belt_capacity_items_per_min": fstr(C_min),
        },
        "table_A_per_commodity": table_a,
        "aggregate": {
            "F_target_per_tick": fstr(F_target),
            "F_target_per_min": fstr(F_target * ticks_per_min),
            "F_route_per_tick": fstr(F_route),
            "F_route_per_min": fstr(F_route * ticks_per_min),
            "cross_check_ob1": xcheck,
        },
        "duty_solution": {
            "machine_equivalents_x": {op: fstr(x[op]) for op in ops},
            "mandatory_counts_n": {op: n_op[op] for op in ops},
            "duty": {op: fstr(duty[op]) for op in ops},
            "machines_at_full_duty": sum(n_op[op] for op in ops if duty[op] == 1),
            "machines_total": sum(n_op.values()),
        },
        "table_B_port_lane_decomposition": table_b,
        "table_C_lane_sharing": {
            "distinct_lane_rates": [
                {"rate": fstr(r), "lane_count": lane_multiset[r],
                 "commodities": sorted(lane_owner[r])}
                for r in distinct
            ],
            "total_lanes": sum(lane_multiset.values()),
            "pairwise": pair_rows,
            "intermediate_pure_flow_forcing": {
                "claim": "任何速率之和 ≤ 1 的车道对，其两侧车道的商品必须全部是终端成品",
                "counterexamples": illegal_intermediate_pairs,
                "verified": illegal_intermediate_pairs == 0,
            },
            "terminal_full_merge": {
                "rates": {c: fstr(term_full[c]) for c in finals},
                "sum": fstr(term_pair_sum),
                "legal_on_one_cell": terminal_full_merge_legal,
                "note": "两条终品**全流**车道之和；若 > cap，则 canonical rate_lemma_scope 里"
                        "「终端成品段可混流」只对**未完全汇聚**的子段成立，最后一段不成立",
            },
        },
        "table_D_min_lanes": {
            "per_commodity": table_d,
            "total_all_commodities": total_min_lanes,
            "total_excluding_finals": total_min_lanes_route,
            "note": "L_k = ceil(F_k / belt_cap)：这是**全局**最小车道数（允许跨机器汇聚）；"
                    "表 B 的 slots_total 是**逐端口**车道数（模型内由 binding 钉死）。"
                    "两者的差 = 前件 (ii) 真正起作用的自由度所在。",
        },
        "table_E_row_estimates": table_e,
    }
    with open(OUT, "w") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=1)

    # ---------------- stdout ----------------
    print("=== 常数 ===")
    print(f"tick={fstr(tick_s)}s  belt_cap={fstr(belt_cap)} 件/tick = {fstr(C_min)} 件/分钟/格/层")
    print()
    print("=== 表 A：逐商品聚合速率（钉死目标下的常数）===")
    print(f"{'商品':<24}{'角色':<22}{'件/tick':>10}{'件/分钟':>10}{'最小车道':>9}")
    for c in commodities:
        a = table_a[c]
        print(f"{c:<24}{a['role']:<22}{a['routed_flow_per_tick']:>10}"
              f"{a['routed_flow_per_min']:>10}{a['min_lanes_global']:>9}")
    print(f"\nF_target = {fstr(F_target * ticks_per_min)} 件/分钟   "
          f"F_route = {fstr(F_route * ticks_per_min)} 件/分钟")
    print(f"OB1 互证: F_route {xcheck['F_route_agrees']} / F_target {xcheck['F_target_agrees']}")
    print()
    print("=== 表 B：逐端口车道分解（单机）===")
    print(f"{'operation':<26}{'侧':<4}{'商品':<24}{'台':>4}{'占空':>7}"
          f"{'单机速率':>9}{'槽/台':>6}{'残道':>8}{'总槽':>6}")
    for row in table_b:
        print(f"{row['operation']:<26}{row['side']:<4}{row['commodity']:<24}"
              f"{row['machines']:>4}{row['duty']:>7}{row['rate_per_machine_per_tick']:>9}"
              f"{row['slots_per_machine']:>6}{row['residual_lane_rate']:>8}"
              f"{row['slots_total']:>6}")
    print(f"端口槽合计 = {total_slots}")
    print()
    print("=== 表 C：车道速率多重集 ===")
    for r in distinct:
        print(f"  速率 {fstr(r):>6}  条数 {lane_multiset[r]:>4}  商品 {sorted(lane_owner[r])}")
    print(f"车道总数 = {sum(lane_multiset.values())}")
    print()
    print("  两两共道合法（和 ≤ cap）的对：")
    any_legal = False
    for a, b, only_term in legal_pairs:
        any_legal = True
        print(f"    {fstr(a)} + {fstr(b)} = {fstr(a + b)} ≤ {fstr(belt_cap)}"
              f"   [仅终品={only_term}]")
    if not any_legal:
        print("    （无）")
    print(f"  涉及中间品的合法共道对 = {illegal_intermediate_pairs} "
          f"⇒ 中间品逐道纯流强制 {'成立' if illegal_intermediate_pairs == 0 else '被推翻'}")
    print(f"  终品全流合并 {' + '.join(fstr(v) for v in term_full.values())} "
          f"= {fstr(term_pair_sum)}  一格合法={terminal_full_merge_legal}")
    print()
    print("=== 表 D：全局最小车道数 ===")
    print(f"  合计（全部 19 商品）= {total_min_lanes}；扣终品 = {total_min_lanes_route}")
    print(f"  对照：逐端口槽数合计 = {total_slots}")
    print()
    print("=== 表 E：行数量级 ===")
    print(f"  格-层位 = {cell_layers}（70×70×2）")
    print(f"  P1 纯度行上界 = {table_e['row_family_P1_purity_upper_bound']['rows_upper_bound']}（系数全 1）")
    print(f"  P2 终品容量行上界 = {cell_layers}，整数化公分母 = {lcm_den}")
    print(f"  P3 单商品流子问题 = {K} 个")
    print(f"  全部车道速率公分母 = {lcm_all}")
    print(f"\nreceipt -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
