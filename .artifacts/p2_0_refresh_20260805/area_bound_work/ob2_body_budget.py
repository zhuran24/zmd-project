#!/usr/bin/env python3
"""OB2 —— 机身预算脚本化复算收据（P2.0 第七谓词语义）。

不手抄任何数字：模板尺寸取 canonical facility_templates，实例数取
mandatory_exact_instances.json 普查，逐模板乘积求和。
同时产出 OB4 需要的「受电机身格数」（needs_power 模板的机身之和）。

只读输入：
  rules/canonical_rules.json                      (frozen)
  data/preprocessed/mandatory_exact_instances.json (266 实例)
输出：ob2_body_budget_receipt.json（同目录）
"""
from __future__ import annotations

import json
from collections import defaultdict

ROOT = "/home/zhuran24/zmd-pj"
CANON = f"{ROOT}/rules/canonical_rules.json"
INSTANCES = f"{ROOT}/data/preprocessed/mandatory_exact_instances.json"
OUT = f"{ROOT}/.artifacts/p2_0_refresh_20260805/area_bound_work/ob2_body_budget_receipt.json"


def main() -> None:
    canon = json.load(open(CANON))
    templates = canon["facility_templates"]
    grid = canon["globals"]["grid"]
    instances = json.load(open(INSTANCES))

    census = defaultdict(int)
    for inst in instances:
        census[inst["facility_type"]] += 1
    assert sum(census.values()) == 266, sum(census.values())
    unknown = set(census) - set(templates)
    assert not unknown, f"普查里有 canonical 之外的模板: {unknown}"

    rows = []
    total = 0
    powered_total = 0
    for tpl, n in sorted(census.items()):
        t = templates[tpl]
        area = t["dimensions"]["w"] * t["dimensions"]["h"]
        subtotal = n * area
        total += subtotal
        needs_power = bool(t["needs_power"])
        if needs_power:
            powered_total += subtotal
        rows.append({
            "template": tpl,
            "count": n,
            "w": t["dimensions"]["w"],
            "h": t["dimensions"]["h"],
            "body_cells_each": area,
            "body_cells_subtotal": subtotal,
            "needs_power": needs_power,
        })

    pole = templates["power_pole"]
    pole_area = pole["dimensions"]["w"] * pole["dimensions"]["h"]
    board = grid["width"] * grid["height"]

    receipt = {
        "ob": "OB2",
        "semantics_label": "P2.0 第七谓词语义（布局无关机身预算；六谓词语义下同样成立——机身占地与吞吐无关）",
        "date": "2026-08-06",
        "inputs": {
            "canonical_rules": "rules/canonical_rules.json (frozen) facility_templates.*.dimensions/needs_power",
            "mandatory_instances": "data/preprocessed/mandatory_exact_instances.json (266) facility_type 普查",
        },
        "census_by_template": rows,
        "totals": {
            "board_cells": board,
            "mandatory_body_cells_total": total,
            "powered_body_cells_total": powered_total,
            "board_minus_bodies": board - total,
            "power_pole_body_cells_each": pole_area,
        },
        "notes": [
            "受电机身 = needs_power 模板（三种制造机）的机身之和；protocol_core 与 boundary_storage_port 不需电。",
            "protocol_storage_box needs_power=true 但 mandatory 下界为 0（当前需求 2 已被 core 的 14 输入容量覆盖），不进本预算；"
            "若布局实际使用 box，其机身与受电需求只会进一步吃紧预算（保守方向）。",
            "power_pole 不在 266 mandatory 之列，其数量 P 是布局变量；每根占 4 格进上界的 −4P 项。",
        ],
    }
    with open(OUT, "w") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=1)

    print("=== OB2 机身预算（模板表驱动） ===")
    for r in rows:
        print(f"{r['template']:24s} {r['count']:3d} × {r['w']}×{r['h']}={r['body_cells_each']:2d}"
              f" -> {r['body_cells_subtotal']:5d}  needs_power={r['needs_power']}")
    print(f"合计机身 = {total} 格；受电机身 = {powered_total} 格；"
          f"棋盘 {board} − 机身 = {board - total} 格；电杆单根 {pole_area} 格")
    print(f"receipt -> {OUT}")


if __name__ == "__main__":
    main()
