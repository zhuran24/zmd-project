#!/usr/bin/env python3
"""OB4 —— 电杆数真下界（P2.0 面积上界的 −4P 项配套）。

论证结构（布局无关）：
  1. 谓词 6：每个 needs_power 设施必须被某根电杆的覆盖窗（12×12，anchor−5..anchor+6，
     canonical semantics.power_coverage_stencil）覆盖；模型判据 = 覆盖窗与设施包围盒相交
     （src/master/exact_coordinate_master.py 的 stencil-bbox 相交语义；若模型判据更严，
     本上界只会更松，结论仍安全）。
  2. 把每个受电设施指派给任意一根覆盖它的电杆 ⇒ 每根电杆名下的设施两两不重叠、
     且包围盒都与该杆的 12×12 窗相交、且都不与杆身（2×2）重叠。
  3. 定义 K = 满足 2 的设施集合的机身格数最大值（对固定窗的装填最优化）。
     则 P · K ≥ 受电机身总格数 3,325 ⇒ P ≥ ceil(3325/K)。
  4. K 用 CP-SAT 精确求解（≈960 个候选位姿、484 格互斥），必须 OPTIMAL 才算数。

与旧弱下界的关系：MEMO §3.3 用「设施全落在 24×24=576 窗」的松计数得 P≥6。
本脚本把 576 换成真实装填最优值 K（几何上 22×22 dilated 区域 + 相交约束 + 杆身占位），
K < 576 ⇒ P_min 上升，A 上界每 +1P 收紧 4 格。

保守性清单（全部只会让真 P 更大、本下界仍成立）：
  - 允许设施位姿悬空在棋盘外（layout-free 松弛）；
  - 覆盖窗不做棋盘裁剪（边缘杆实际覆盖更少）；
  - 不限制杆与杆的互斥、不占用路由格位；
  - 普查台数上限（132/49/38）在单窗尺度不束缚（单窗最多装 ~50 台 3×3 当量）。

只读输入：rules/canonical_rules.json（stencil 尺寸/模板尺寸/needs_power）
        + ob2_body_budget_receipt.json（受电机身 3,325，脚本内重导出核对）
输出：ob4_pole_lower_bound_receipt.json
"""
from __future__ import annotations

import json
import math
from collections import defaultdict

from ortools.sat.python import cp_model

ROOT = "/home/zhuran24/zmd-pj"
CANON = f"{ROOT}/rules/canonical_rules.json"
INSTANCES = f"{ROOT}/data/preprocessed/mandatory_exact_instances.json"
OB2 = f"{ROOT}/.artifacts/p2_0_refresh_20260805/area_bound_work/ob2_body_budget_receipt.json"
OUT = f"{ROOT}/.artifacts/p2_0_refresh_20260805/area_bound_work/ob4_pole_lower_bound_receipt.json"


def main() -> None:
    canon = json.load(open(CANON))
    stencil = canon["semantics"]["power_coverage_stencil"]
    W = int(stencil["coverage_shape"]["width"])
    H = int(stencil["coverage_shape"]["height"])
    assert (W, H) == (12, 12), (W, H)
    radius = int(stencil["power_coverage_radius"])
    pole_w = int(stencil["anchor_footprint"]["w"])
    pole_h = int(stencil["anchor_footprint"]["h"])
    assert (pole_w, pole_h) == (2, 2)
    # 窗坐标系：窗 = [0..W-1]×[0..H-1]；anchor 在窗内 (radius, radius)
    pole_cells = {(radius + dx, radius + dy) for dx in range(pole_w) for dy in range(pole_h)}

    templates = canon["facility_templates"]
    powered_shapes = []  # (template, w, h)
    for tpl, t in templates.items():
        if not t["needs_power"]:
            continue
        w, h = t["dimensions"]["w"], t["dimensions"]["h"]
        dims = {(w, h)}
        if t["rotatable"]:
            dims.add((h, w))
        for (dw, dh) in sorted(dims):
            powered_shapes.append((tpl, dw, dh))

    # 受电机身总数（与 OB2 收据互证）
    instances = json.load(open(INSTANCES))
    census = defaultdict(int)
    for inst in instances:
        census[inst["facility_type"]] += 1
    powered_body = sum(
        n * templates[tpl]["dimensions"]["w"] * templates[tpl]["dimensions"]["h"]
        for tpl, n in census.items() if templates[tpl]["needs_power"])
    ob2 = json.load(open(OB2))
    assert powered_body == ob2["totals"]["powered_body_cells_total"], (
        powered_body, ob2["totals"]["powered_body_cells_total"])

    # ---------- 候选位姿：包围盒与窗相交（mandatory 里存在该模板才生成） ----------
    mandatory_templates = {tpl for tpl in census if templates[tpl]["needs_power"]}
    cands = []  # (tpl, w, h, x, y, cells)
    for (tpl, w, h) in powered_shapes:
        if tpl not in mandatory_templates:
            continue  # storage box 等非 mandatory 模板不进本下界（保守：少算覆盖需求）
        for x in range(1 - w, W):
            for y in range(1 - h, H):
                cells = frozenset((x + i, y + j) for i in range(w) for j in range(h))
                if cells & pole_cells:
                    continue  # 与杆身重叠的位姿非法
                cands.append((tpl, w, h, x, y, cells))

    # ---------- CP-SAT：最大化被覆盖机身格数 ----------
    model = cp_model.CpModel()
    b = [model.new_bool_var(f"c{i}") for i in range(len(cands))]
    by_cell = defaultdict(list)
    for i, (_, _, _, _, _, cells) in enumerate(cands):
        for c in cells:
            by_cell[c].append(b[i])
    for c, vs in by_cell.items():
        if len(vs) > 1:
            model.add_at_most_one(vs)
    model.maximize(sum(len(cands[i][5]) * b[i] for i in range(len(cands))))

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 8
    solver.parameters.max_time_in_seconds = 600
    status = solver.solve(model)
    status_name = solver.status_name(status)
    assert status_name == "OPTIMAL", f"K 未证最优: {status_name}（下界不成立，勿引用）"
    K = int(solver.objective_value)

    chosen = [
        {"template": cands[i][0], "w": cands[i][1], "h": cands[i][2],
         "x": cands[i][3], "y": cands[i][4]}
        for i in range(len(cands)) if solver.value(b[i])
    ]

    # ---------- 见证独立复验（不信任求解器展开，逐格重查） ----------
    used_cells: set[tuple[int, int]] = set()
    witness_area = 0
    for c in chosen:
        cells = {(c["x"] + i, c["y"] + j) for i in range(c["w"]) for j in range(c["h"])}
        assert not (cells & used_cells), f"见证重叠: {c}"
        assert not (cells & pole_cells), f"见证压杆身: {c}"
        assert any(0 <= x < W and 0 <= y < H for (x, y) in cells), f"见证不交窗: {c}"
        used_cells |= cells
        witness_area += len(cells)
    assert witness_area == K, (witness_area, K)

    P_min = math.ceil(powered_body / K)
    # 两档旧弱计数，供对照：
    #   MEMO §3.3 用「设施全落 24×24=576」（把最大边 6 直接加满两侧）→ P≥6；
    #   更紧的膨胀计数（最大边 6 ⇒ 每侧膨胀 6−1=5 ⇒ 22×22=484）→ P≥7；
    # 本脚本的 K 是真实装填最优（K=按形状装填 ≤ 484 的实际可达值）。
    weak_576 = (W + 2 * 6) * (H + 2 * 6)
    weak_484 = (W + 2 * 5) * (H + 2 * 5)
    receipt = {
        "ob": "OB4",
        "semantics_label": "P2.0 第七谓词语义配套（P 下界本身与吞吐无关，六谓词语义同样成立）",
        "date": "2026-08-06",
        "stencil_source": "rules/canonical_rules.json semantics.power_coverage_stencil "
                          "(12×12, anchor−5..anchor+6, 2×2 杆身) —— 与 "
                          "src/master/exact_coordinate_master.py 运行时语义核对记录见报告",
        "argument": "指派论证：每受电设施指派给一根覆盖杆 ⇒ 单杆名下设施互斥且包围盒交其 12×12 窗"
                    " ⇒ 单杆覆盖机身 ≤ K（CP-SAT 装填最优）⇒ P ≥ ceil(3325/K)",
        "K_single_pole_max_covered_body_cells": K,
        "K_solver_status": status_name,
        "K_candidates": len(cands),
        "powered_body_cells": powered_body,
        "P_min": P_min,
        "witness_independent_recheck": "逐格重查通过：互斥 / 不压杆身 / 逐台交窗 / 面积==K",
        "previous_weak_bounds": {
            "memo_24x24_576": {"area": weak_576, "P_min": math.ceil(powered_body / weak_576),
                               "note": "MEMO §3.3 原口径（最大边 6 两侧加满）"},
            "dilation_22x22_484": {"area": weak_484, "P_min": math.ceil(powered_body / weak_484),
                                   "note": "更紧的纯膨胀计数（每侧 6−1=5），仍不含装填结构"},
        },
        "area_bound_effect": {
            "single_layer_A_le": f"1051 - 4*P <= {1051 - 4 * P_min}",
            "double_layer_A_le": f"1203 - 4*P <= {1203 - 4 * P_min}",
            "note": "1051/1203 的来源与最终定值见 OB5 定理报告（依赖 OB1 的 305/153 与 OB2 的 3544）",
        },
        "conservativeness": [
            "位姿允许悬空棋盘外、窗不裁剪、不计杆间互斥/路由占位 —— 全部只会高估 K、低估 P_min，方向安全",
            "覆盖判据取包围盒相交（模型判据同）；若真实判据更严，P_min 只会更大",
        ],
        "optimal_packing_witness": chosen,
    }
    with open(OUT, "w") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=1)

    print("=== OB4 电杆真下界 ===")
    print(f"单杆覆盖机身上限 K = {K}（{status_name}；候选位姿 {len(cands)}；见证独立复验通过）")
    print(f"受电机身 = {powered_body} ⇒ P_min = ceil({powered_body}/{K}) = {P_min}"
          f"（对照：MEMO 576 口径 P≥{receipt['previous_weak_bounds']['memo_24x24_576']['P_min']}，"
          f"484 膨胀口径 P≥{receipt['previous_weak_bounds']['dilation_22x22_484']['P_min']}）")
    tally = defaultdict(int)
    for c in chosen:
        tally[f"{c['template']}({c['w']}x{c['h']})"] += 1
    print("最优装填构成:", dict(tally))
    print(f"receipt -> {OUT}")


if __name__ == "__main__":
    main()
