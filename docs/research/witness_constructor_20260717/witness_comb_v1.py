"""witness 构造器 v3：梳状走廊布局（research-grade，zero-sealed）。

结构：按模板分区成水平带（band），带间夹 1 行走廊（corridor）；设施
body 落带内、demand 数量的 front 落走廊行（共享走廊 = front 零碎片）。
边界件先占西/北边缘；protocol_core 单独首放。放完跑真机械审计
（port_front_status × demand SSOT）+ 可选真 binding 复核。

v0（散点贪心）容量上限 217/266，死因=碎片化；本版为结构化重试。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.io.strict_json import load_strict_json  # noqa: E402
from src.models.binding_subproblem import (  # noqa: E402
    PortBindingModel,
    load_generic_io_requirements,
)
from src.models.port_binding import (  # noqa: E402
    routing_free_sink_commodities_from_generic_inputs,
    routing_visible_port_demands,
    supports_exact_pose_level_binding,
)
from src.models.routing_binding_context import (  # noqa: E402
    _DIR_DELTA,
    build_routing_binding_context,
    port_front_status,
)
from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES  # noqa: E402

GRID = 70


def _cells(seq):
    return {(int(c[0]), int(c[1])) for c in (seq or [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ghost-x", type=int, default=1)
    ap.add_argument("--ghost-y", type=int, default=1)
    ap.add_argument("--ghost-w", type=int, default=6)
    ap.add_argument("--ghost-h", type=int, default=7)
    ap.add_argument("--skip-binding", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    payload = load_strict_json(
        PROJECT_ROOT / "data/preprocessed/candidate_placements.json"
    )
    pools = dict(payload["facility_pools"])
    instances = load_strict_json(
        PROJECT_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    io_req = load_generic_io_requirements(project_root=PROJECT_ROOT)
    rfsc = routing_free_sink_commodities_from_generic_inputs(
        io_req["required_generic_inputs"]
    )
    op_by_id = {str(i["instance_id"]): str(i["operation_type"]) for i in instances}

    def demand_of(iid: str):
        op = op_by_id[iid]
        try:
            if op in OPERATION_PORT_PROFILES and supports_exact_pose_level_binding(op):
                return routing_visible_port_demands(op, rfsc)
        except ValueError:
            pass
        return None  # 保守：全 front 保留

    ghost = {(x, y) for x in range(args.ghost_x, args.ghost_x + args.ghost_w)
             for y in range(args.ghost_y, args.ghost_y + args.ghost_h)}

    occupied: set = set()
    reserved: set = set()
    solution: dict[str, dict] = {}
    unplaced: list[str] = []

    def fronts_of(pose):
        sides = []
        for f in ("input_port_cells", "output_port_cells"):
            fs = []
            for p in pose.get(f) or []:
                dx, dy = _DIR_DELTA.get(str(p.get("dir", "")), (0, 0))
                fs.append((int(p["x"]) + dx, int(p["y"]) + dy))
            sides.append(fs)
        return sides

    def try_place(iid, tpl, pose_filter, front_rule):
        """pose_filter(pose,body)->bool; front_rule(cands,need)->picked|None"""
        dem = demand_of(iid)
        for idx, pose in enumerate(pools[tpl]):
            body = _cells(pose.get("occupied_cells"))
            if not pose_filter(pose, body):
                continue
            if body & occupied or body & ghost or body & reserved:
                continue
            sides = fronts_of(pose)
            if dem is None:
                need_in, need_out = len(sides[0]), len(sides[1])
            else:
                need_in, need_out = dem
            gi = front_rule(sides[0], need_in)
            if gi is None:
                continue
            go = front_rule(sides[1], need_out)
            if go is None:
                continue
            occupied.update(body)
            reserved.update(gi + go)
            solution[iid] = {"facility_type": tpl, "pose_idx": idx}
            return True
        return False

    def free_front(cands, need):
        got = [c for c in cands
               if 0 <= c[0] < GRID and 0 <= c[1] < GRID and c not in occupied]
        return got[:need] if len(got) >= need else None

    t0 = time.perf_counter()

    # ---- 1) 边界件：46 个，占边缘 ----
    binsts = [i for i in instances
              if str(i["facility_type"]) == "boundary_storage_port"]
    for i in binsts:
        if not try_place(str(i["instance_id"]), "boundary_storage_port",
                         lambda p, b: True, free_front):
            unplaced.append(str(i["instance_id"]))

    # ---- 2) protocol_core（81 格巨件）：放东南角 ----
    core = [i for i in instances if str(i["facility_type"]) == "protocol_core"]
    for i in core:
        if not try_place(str(i["instance_id"]), "protocol_core",
                         lambda p, b: min(c[0] for c in b) >= 55
                         and min(c[1] for c in b) >= 55,
                         free_front):
            # 松绑重试：任意位置
            if not try_place(str(i["instance_id"]), "protocol_core",
                             lambda p, b: True, free_front):
                unplaced.append(str(i["instance_id"]))

    # ---- 3) 梳状带布局 ----
    # 区划（行）：5×5 带区 + 6×4 带区 + 3×3 带区；每带上下夹走廊行。
    # 带定义：(body 起始行, body 高度)；走廊 = 带上一行与带下一行。
    bands: list[tuple[int, int, str]] = []
    y = 2  # 行 0/1 留给北边界件与其 connector
    for _ in range(4):            # 5×5 × 4 带
        bands.append((y + 1, 5, "manufacturing_5x5")); y += 6
    for _ in range(4):            # 6×4（4 行高姿态）× 4 带
        bands.append((y + 1, 4, "manufacturing_6x4")); y += 5
    while y + 4 <= 68:            # 3×3 带铺到底
        bands.append((y + 1, 3, "manufacturing_3x3")); y += 4

    corridor_rows = set()
    for (by, bh, _t) in bands:
        corridor_rows.add(by - 1)
        corridor_rows.add(by + bh)

    def band_filter(by, bh):
        def f(pose, body):
            ys = [c[1] for c in body]
            return min(ys) == by and max(ys) == by + bh - 1
        return f

    def corridor_front(cands, need):
        got = [c for c in cands
               if 0 <= c[0] < GRID and 0 <= c[1] < GRID
               and c not in occupied
               and (c[1] in corridor_rows or c in reserved)]
        return got[:need] if len(got) >= need else None

    remaining = [i for i in instances
                 if str(i["instance_id"]) not in solution
                 and str(i["instance_id"]) not in unplaced]
    # 模板分桶，依次填带
    by_tpl: dict[str, list] = {}
    for i in remaining:
        by_tpl.setdefault(str(i["facility_type"]), []).append(i)

    # N/S 型 pose 索引：(tpl, body_min_x, body_min_y) → pose idx 列表
    # （TB port_mode：in 全朝 N/out 全朝 S 或其翻转——两种口向都收，
    #   带内铺排时哪种 front 可用用哪种）
    ns_index: dict[tuple, list[int]] = {}
    for tpl in by_tpl:
        for idx, pose in enumerate(pools[tpl]):
            ind = frozenset(str(q["dir"])
                            for q in pose.get("input_port_cells") or [])
            outd = frozenset(str(q["dir"])
                             for q in pose.get("output_port_cells") or [])
            if {ind, outd} != {frozenset({"N"}), frozenset({"S"})}:
                continue
            body = _cells(pose.get("occupied_cells"))
            key = (tpl, min(c[0] for c in body), min(c[1] for c in body))
            ns_index.setdefault(key, []).append(idx)

    slot_fail = {"no_pose": 0, "body": 0, "front_in": 0, "front_out": 0}

    def try_slot(iid, tpl, x, by):
        cands = ns_index.get((tpl, x, by), [])
        if not cands:
            slot_fail["no_pose"] += 1
        for idx in cands:
            pose = pools[tpl][idx]
            body = _cells(pose.get("occupied_cells"))
            if body & occupied or body & ghost or body & reserved:
                slot_fail["body"] += 1
                continue
            sides = fronts_of(pose)
            dem = demand_of(iid)
            if dem is None:
                need_in, need_out = len(sides[0]), len(sides[1])
            else:
                need_in, need_out = dem
            gi = corridor_front(sides[0], need_in)
            if gi is None:
                if slot_fail["front_in"] == 0:
                    print("DEBUG 首次 front_in 失败:", iid, tpl, "x=", x,
                          "by=", by, "need=", need_in,
                          "sides[0][:6]=", sides[0][:6],
                          "corridor_rows=", sorted(corridor_rows))
                slot_fail["front_in"] += 1
                continue
            go = corridor_front(sides[1], need_out)
            if go is None:
                slot_fail["front_out"] += 1
                continue
            occupied.update(body)
            reserved.update(gi + go)
            solution[iid] = {"facility_type": tpl, "pose_idx": idx}
            return True
        return False

    tpl_w = {"manufacturing_5x5": 5, "manufacturing_6x4": 6,
             "manufacturing_3x3": 3}
    band_stats = []
    for (by, bh, tpl) in bands:
        queue = by_tpl.get(tpl, [])
        w = tpl_w[tpl]
        x = 0
        n0 = len(queue)
        while queue and x <= GRID - w:
            iid = str(queue[0]["instance_id"])
            if try_slot(iid, tpl, x, by):
                queue.pop(0)
                x += w          # 紧贴下一槽
            else:
                x += 1          # 本槽不可用，滑动一格再试
        band_stats.append([by, tpl, n0 - len(queue)])
    print("band 放置数:", band_stats)
    print("slot 失败分解:", slot_fail)

    # 带耗尽后仍剩的：自由位置兜底（front 不限走廊）
    for tpl, queue in by_tpl.items():
        for i in list(queue):
            iid = str(i["instance_id"])
            if iid in solution:
                queue.remove(i)
                continue
            if try_place(iid, tpl, lambda p, b: True, free_front):
                queue.remove(i)
            else:
                unplaced.append(iid)
                queue.remove(i)

    place_wall = round(time.perf_counter() - t0, 2)
    result = {
        "harness": "witness_comb_v1",
        "ghost": [args.ghost_x, args.ghost_y, args.ghost_w, args.ghost_h],
        "bands": [[b[0], b[1], b[2]] for b in bands],
        "placed": len(solution), "unplaced": unplaced,
        "occupied_cells": len(occupied), "reserved_front_cells": len(reserved),
        "place_wall_seconds": place_wall,
    }

    def _dump():
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    _dump()
    print(json.dumps({"placed": result["placed"],
                      "unplaced_n": len(unplaced),
                      "occupied": result["occupied_cells"],
                      "reserved": result["reserved_front_cells"],
                      "wall": place_wall}, ensure_ascii=False))

    # ---- 真机械审计 ----
    context = build_routing_binding_context(solution, pools,
                                            grid_w=GRID, grid_h=GRID)
    audit_fail = []
    checked = 0
    for iid, entry in solution.items():
        op = op_by_id.get(iid, "")
        if (not op or op not in OPERATION_PORT_PROFILES
                or not supports_exact_pose_level_binding(op)):
            continue
        req_in, vis_out = routing_visible_port_demands(op, rfsc)
        if req_in <= 0 and vis_out <= 0:
            continue
        pose = pools[entry["facility_type"]][entry["pose_idx"]]
        counts = []
        for field in ("input_port_cells", "output_port_cells"):
            free = 0
            for port in pose.get(field) or []:
                st = port_front_status(port, context, iid)
                if st.in_grid and st.is_free:
                    free += 1
            counts.append(free)
        checked += 1
        if counts[0] < req_in or counts[1] < vis_out:
            audit_fail.append({"instance": iid, "free": counts,
                               "demand": [req_in, vis_out]})
    result["front_clear_audit"] = {"checked": checked,
                                   "violations": len(audit_fail),
                                   "detail": audit_fail[:20]}
    _dump()
    print(f"front-clear 审计: checked={checked} violations={len(audit_fail)}")

    if not args.skip_binding and not unplaced:
        model = PortBindingModel(
            placement_solution=solution, facility_pools=pools,
            instances=instances,
            required_generic_outputs=io_req["required_generic_outputs"],
            required_generic_inputs=io_req["required_generic_inputs"],
            project_root=PROJECT_ROOT, routing_context=context,
        )
        model.build()
        empty = [str(e["instance_id"])
                 for e in model.extract_empty_binding_domain_instances()]
        result["binding_empty_domains"] = {"count": len(empty),
                                           "ids": empty[:20]}
        _dump()
        print(f"binding 空域: {len(empty)}")

    result["solution"] = solution
    _dump()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
