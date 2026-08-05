#!/usr/bin/env python3
"""band22 见证 × G1 房间分解的**单向必要条件排除检查**（只读，标准库）。

G1 把 70x70 切成 25 个 14x14 房间（``T[i,j] = [14i,14i+13] x [14j,14j+13]``，
见 ``docs/research/w0_front_aware_20260803/g1_region_model.py:5``），并把
R-BODY-IN-REGION（每个决策机身整体落在同一个房间内）、R-FRONT-IN-REGION（每个激活
front 落在其机身所在房间）、R-HOLE-IN-REGION、R-BOUNDARY-LAYOUT 等九条登记为**充分限制**
（`00_charter.md` §4 表；`g1_region_model.py:24-32`）。

**本脚本的定位（不要读大）**：它检查其中**部分**必要条件，只能做**单向排除**——
命中任一条即坐实「这份布局不可能被 G1 catalog 表达」；**没命中不等于可表达**。
本脚本不检查 catalog 成员资格、不检查 G1 fixed furniture 坐标是否与见证一致、
不重算 front（直接采信见证自报的 ``port.front``；front 的 628/628 独立重编译由
27 号验收工作流的两个复核席完成，不在本脚本内）。因此 verdict 的否定分支写作
``UNKNOWN_NOT_REJECTED_BY_CHECKED_CONDITIONS``，不是 ``EXPRESSIBLE``。

**口径**：见证的 266 个 mandatory body = 219 台决策制造机 + 46 个 boundary port
+ 1 个 protocol core。后 47 个在 G1 里是 **fixed furniture**（`g1_region_model.py:11-22`），
不属于 R-BODY-IN-REGION 管的 decision body；它们跨房命中的是 R-BOUNDARY-LAYOUT
（G1 把 core 钉在 ``(3,59)``、把 46 个 port 钉在左/下基线，而见证的 core 在 ``(60,36)``）。
所以收据把跨房数拆成 decision / fixed_furniture 两栏，别把 85 整个当 R-BODY 反例。

输入（都是只读的仓库内文件）：
  - 验收权威实例：.artifacts/w0_consult_packs_20260804/band22_holes/06_problem_instance.json
  - 见证：docs/research/cleanroom_rederivation_20260718/27_band22_witness_delivery_20260804/
          band22_repaired_design_witness_not_checker_schema.json

输出：默认只打印 stdout 摘要。**只有显式传 ``--write`` 才覆写同目录收据 json**
（后续只读审查可以直接跑，不会毁掉在案收据）。
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PROBLEM = REPO / ".artifacts/w0_consult_packs_20260804/band22_holes/06_problem_instance.json"
WITNESS = (
    REPO
    / "docs/research/cleanroom_rederivation_20260718/27_band22_witness_delivery_20260804"
    / "band22_repaired_design_witness_not_checker_schema.json"
)
RECEIPT = Path(__file__).with_suffix(".json")

REGION_SIZE = 14


def room(v: int) -> int:
    return v // REGION_SIZE


def straddles(x: int, y: int, w: int, h: int) -> bool:
    return room(x) != room(x + w - 1) or room(y) != room(y + h - 1)


def main() -> int:
    problem = json.loads(PROBLEM.read_text(encoding="utf-8"))
    witness = json.loads(WITNESS.read_text(encoding="utf-8"))
    templates = problem["facility_templates"]

    def dims(template: str, mode: str) -> tuple[int, int]:
        for entry in templates[template]["modes"]:
            if entry["id"] == mode:
                return entry["body"]["width"], entry["body"]["height"]
        raise KeyError((template, mode))

    facilities = witness["facilities"]

    def collect(items: list[dict], role: str) -> list[tuple[str, str, str, int, int, int, int]]:
        out = []
        for item in items:
            x, y = item["anchor"]
            w, h = dims(item["template"], item["mode"])
            out.append((item["instance_id"], item["template"], role, x, y, w, h))
        return out

    decision_bodies = collect(facilities["manufacturing"], "decision")
    fixed_bodies = collect(
        facilities["boundary_ports"] + [facilities["protocol_core"]], "fixed_furniture"
    )
    bodies = decision_bodies + fixed_bodies

    body_area = sum(w * h for *_, w, h in bodies)
    straddling = [b for b in bodies if straddles(*b[3:])]
    straddling_decision = [b for b in decision_bodies if straddles(*b[3:])]
    straddling_fixed = [b for b in fixed_bodies if straddles(*b[3:])]
    by_template = Counter(b[1] for b in straddling)

    poles = [(p["id"], p["anchor"][0], p["anchor"][1], 2, 2) for p in facilities["power_poles"]]
    straddling_poles = [p for p in poles if straddles(*p[1:])]

    hole = witness["hole"]
    hx0, hx1 = hole["x_range"]
    hy0, hy1 = hole["y_range"]
    hole_straddles = room(hx0) != room(hx1) or room(hy0) != room(hy1)

    # R-BOUNDARY-LAYOUT: G1 pins the fixed furniture at specific anchors
    # (g1_region_model.py:11-22).  Compare the witness's fixed furniture against it.
    g1_boundary_anchors = {(0, 1 + 3 * k) for k in range(23)} | {
        (1 + 3 * k, 0) for k in range(23)
    }
    witness_boundary_anchors = {tuple(p["anchor"]) for p in facilities["boundary_ports"]}
    core = facilities["protocol_core"]
    cx, cy = core["anchor"]

    # R-FRONT-IN-REGION: an active front outside its body's region.  Fronts are taken
    # verbatim from the witness (this script does not recompute them).  The subset whose
    # *body* lies wholly in one room is an R-FRONT counterexample independent of R-BODY.
    fronts_total = 0
    fronts_out_by_role: Counter[str] = Counter()
    front_only_violation_bodies: set[str] = set()
    front_only_violations = 0
    for role, items in (("decision", facilities["manufacturing"]), ("fixed_furniture", facilities["boundary_ports"])):
        for item in items:
            x, y = item["anchor"]
            w, h = dims(item["template"], item["mode"])
            body_in_room = not straddles(x, y, w, h)
            for port in item["active_ports"]:
                fronts_total += 1
                fx, fy = port["front"]
                if room(fx) != room(x) or room(fy) != room(y):
                    fronts_out_by_role[role] += 1
                    if body_in_room:
                        front_only_violations += 1
                        front_only_violation_bodies.add(item["instance_id"])
    for port in core["ports"]:
        if not port.get("active"):
            continue
        fronts_total += 1
        fx, fy = port["front"]
        if room(fx) != room(cx) or room(fy) != room(cy):
            fronts_out_by_role["fixed_furniture"] += 1
    fronts_out = sum(fronts_out_by_role.values())

    rejected_by = []
    if straddling_decision:
        rejected_by.append("R-BODY-IN-REGION")
    if front_only_violations or fronts_out:
        rejected_by.append("R-FRONT-IN-REGION")
    if hole_straddles:
        rejected_by.append("R-HOLE-IN-REGION")
    if straddling_fixed or witness_boundary_anchors != g1_boundary_anchors or (cx, cy) != (3, 59):
        rejected_by.append("R-BOUNDARY-LAYOUT")

    receipt = {
        "check_kind": "one_way_necessary_condition_rejection",
        "check_scope": (
            "checks R-BODY-IN-REGION / R-FRONT-IN-REGION / R-HOLE-IN-REGION / "
            "R-BOUNDARY-LAYOUT only; does NOT check catalog membership, pattern-level "
            "feasibility, or recompute fronts (witness port.front is trusted here)"
        ),
        "region_size": REGION_SIZE,
        "region_partition": "T[i,j] = [14i,14i+13] x [14j,14j+13]",
        "witness_variant": witness["variant_id"],
        "mandatory_bodies": len(bodies),
        "mandatory_body_area": body_area,
        "decision_bodies": len(decision_bodies),
        "fixed_furniture_bodies": len(fixed_bodies),
        "bodies_straddling_region_boundary": len(straddling),
        "decision_bodies_straddling_region_boundary": len(straddling_decision),
        "fixed_furniture_straddling_region_boundary": len(straddling_fixed),
        "bodies_straddling_by_template": dict(by_template),
        "poles": len(poles),
        "poles_straddling_region_boundary": len(straddling_poles),
        "straddling_pole_ids": [p[0] for p in straddling_poles],
        "hole_box": [hx0, hy0, hx1, hy1],
        "hole_straddles_region_boundary": hole_straddles,
        "active_fronts": fronts_total,
        "active_fronts_outside_anchor_region": fronts_out,
        "active_fronts_outside_anchor_region_by_role": dict(fronts_out_by_role),
        "fronts_outside_region_whose_body_is_in_one_room": front_only_violations,
        "bodies_with_front_only_violation": len(front_only_violation_bodies),
        "witness_boundary_anchors_matching_g1_fixed_furniture": len(
            witness_boundary_anchors & g1_boundary_anchors
        ),
        "witness_boundary_anchors": len(witness_boundary_anchors),
        "g1_core_anchor": [3, 59],
        "witness_core_anchor": [cx, cy],
        "rejected_by_restrictions": rejected_by,
        "verdict": (
            "NOT_EXPRESSIBLE_IN_G1_CATALOG"
            if rejected_by
            else "UNKNOWN_NOT_REJECTED_BY_CHECKED_CONDITIONS"
        ),
    }
    if "--write" in sys.argv[1:]:
        RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
