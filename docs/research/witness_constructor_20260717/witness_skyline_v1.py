"""witness 构造器 v4：skyline 装箱 + 点状须保留（research-grade，zero-sealed）。

几何事实（07-17 实测）：口格悬在 body 外 1 行、front 再外 1 行——每件是
「矩形 body + 两条对侧须（每须 2 格纵深）」。整行留空的规则带式布局固有
需求 ~5,400 格 > 4,900 总格，算术判死；点状须（只保 demand 数量的口+front
共 4-6 格/件）总足迹 ~4,750，余量 3%——必须不规则密铺。

算法：bottom-left skyline。TB/BT 变体二选（demand 小的一侧朝下），朝下的
须优先沉进 skyline 孔隙（浪费格回收），朝上的须 reserve 后由后续件避让。
boundary 边缘件先放，protocol_core 与 ghost 预置。
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
MANUF = {"manufacturing_3x3": (3, 3), "manufacturing_5x5": (5, 5),
         "manufacturing_6x4": (6, 4)}  # (w, h) 的 TB 形态


def _cells(seq):
    return {(int(c[0]), int(c[1])) for c in (seq or [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ghost-x", type=int, default=62)
    ap.add_argument("--ghost-y", type=int, default=2)
    ap.add_argument("--ghost-w", type=int, default=6)
    ap.add_argument("--ghost-h", type=int, default=7)
    ap.add_argument("--seed", type=int, default=0,
                    help="非 0 时对同尺寸组内实例顺序做确定性 shuffle")
    ap.add_argument("--skip-binding", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    payload = load_strict_json(
        PROJECT_ROOT / "data/preprocessed/candidate_placements.json")
    pools = dict(payload["facility_pools"])
    instances = load_strict_json(
        PROJECT_ROOT / "data/preprocessed/mandatory_exact_instances.json")
    io_req = load_generic_io_requirements(project_root=PROJECT_ROOT)
    rfsc = routing_free_sink_commodities_from_generic_inputs(
        io_req["required_generic_inputs"])
    op_by_id = {str(i["instance_id"]): str(i["operation_type"])
                for i in instances}

    def demand_of(iid):
        op = op_by_id[iid]
        try:
            if op in OPERATION_PORT_PROFILES and \
                    supports_exact_pose_level_binding(op):
                return routing_visible_port_demands(op, rfsc)
        except ValueError:
            pass
        return None

    # TB/BT pose 索引：(tpl, mode, body_min_x, body_min_y) -> pose_idx
    # mode 语义按实测：TB = in 口在 body 大 y 侧（y=max+1，front y=max+2），
    # out 口在小 y 侧（y=min-1，front y=min-2）；BT 相反。以实际坐标为准，
    # 索引时直接记录每个 pose 的 in/out 须坐标（口格+front 格成对）。
    pose_index: dict[tuple, list] = {}
    for tpl in MANUF:
        for idx, pose in enumerate(pools[tpl]):
            mode = str((pose.get("pose_params") or {}).get("port_mode"))
            if mode not in ("TB", "BT", "RL", "LR"):
                continue
            body = _cells(pose.get("occupied_cells"))
            key = (tpl, mode, min(c[0] for c in body), min(c[1] for c in body))
            whisk = {}
            for f, tag in (("input_port_cells", "in"),
                           ("output_port_cells", "out")):
                pts = []
                for q in pose.get(f) or []:
                    px, py = int(q["x"]), int(q["y"])
                    dx, dy = _DIR_DELTA[str(q["dir"])]
                    pts.append(((px, py), (px + dx, py + dy)))
                whisk[tag] = pts
            pose_index.setdefault(key, []).append((idx, whisk))

    ghost = {(x, y) for x in range(args.ghost_x, args.ghost_x + args.ghost_w)
             for y in range(args.ghost_y, args.ghost_y + args.ghost_h)}

    occupied: set = set()
    reserved: set = set()   # 须点（口格 + front 格）——body 不许压
    solution: dict[str, dict] = {}
    unplaced: list[str] = []

    def blocked(c):
        return c in occupied or c in reserved or c in ghost

    def free_in_grid(c):
        return 0 <= c[0] < GRID and 0 <= c[1] < GRID and not blocked(c)

    def pick_fronts(cands, need):
        """挑 need 个 front 格：已保留的共享格零成本优先，其次贴墙格
        （少制造新碎片），最后才用开阔格。不够返回 None。"""
        avail = [fr for fr in cands
                 if 0 <= fr[0] < GRID and 0 <= fr[1] < GRID
                 and fr not in occupied and fr not in ghost]
        if len(avail) < need:
            return None

        def score(c):
            if c in reserved:
                return 0
            x, y = c
            touch = sum((nx, ny) in occupied or not (0 <= nx < GRID
                                                     and 0 <= ny < GRID)
                        for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)))
            return 2 - min(touch, 1)   # 贴墙=1，开阔=2
        avail.sort(key=score)
        return avail[:need]

    # ---- 1) boundary + core（老式贪心，全 front 保留） ----
    def fronts_of(pose):
        sides = []
        for f in ("input_port_cells", "output_port_cells"):
            fs = []
            for q in pose.get(f) or []:
                dx, dy = _DIR_DELTA.get(str(q.get("dir", "")), (0, 0))
                fs.append(((int(q["x"]), int(q["y"])),
                           (int(q["x"]) + dx, int(q["y"]) + dy)))
            sides.append(fs)
        return sides

    def place_simple(iid, tpl, need=None):
        dem = demand_of(iid) if need is None else need
        for idx, pose in enumerate(pools[tpl]):
            body = _cells(pose.get("occupied_cells"))
            if any(blocked(c) for c in body):
                continue
            sides = fronts_of(pose)
            if dem is None:
                ni, no = len(sides[0]), len(sides[1])
            else:
                ni, no = dem
            picks = []
            ok = True
            for cands, need_n in ((sides[0], ni), (sides[1], no)):
                got = pick_fronts([fr for (_p, fr) in cands], need_n)
                if got is None:
                    ok = False
                    break
                picks += got
            if not ok:
                continue
            occupied.update(body)
            reserved.update(picks)
            solution[iid] = {"facility_type": tpl, "pose_idx": idx}
            return True
        return False

    t0 = time.perf_counter()
    for i in instances:
        if str(i["facility_type"]) == "boundary_storage_port":
            if not place_simple(str(i["instance_id"]), "boundary_storage_port"):
                unplaced.append(str(i["instance_id"]))
    for i in instances:
        if str(i["facility_type"]) == "protocol_core":
            if not place_simple(str(i["instance_id"]), "protocol_core"):
                unplaced.append(str(i["instance_id"]))

    # ---- 2) 制造件主循环：大件 bottom-left 首可行，3×3 best-fit 评分 ----
    def snugness(body):
        s = 0
        for (x, y) in body:
            for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if (nx, ny) in body:
                    continue
                if not (0 <= nx < GRID and 0 <= ny < GRID) or \
                        (nx, ny) in occupied:
                    s += 1
        return s

    def try_manuf(iid, tpl, best_fit=False):
        dem = demand_of(iid)
        best = None  # (-snug, yb, x0) -> (idx, whisk, body)
        for yb in range(0, GRID):
            for x0 in range(0, GRID):
                for mode in ("TB", "BT", "RL", "LR"):
                    cands = pose_index.get((tpl, mode, x0, yb))
                    if not cands:
                        continue
                    idx, whisk = cands[0]
                    body = _cells(pools[tpl][idx].get("occupied_cells"))
                    if any(blocked(c) for c in body):
                        continue
                    if dem is None:
                        ni, no = len(whisk["in"]), len(whisk["out"])
                    else:
                        ni, no = dem
                    sel = []
                    ok = True
                    for tag, need_n in (("in", ni), ("out", no)):
                        got = pick_fronts([fr for (_p, fr) in whisk[tag]],
                                          need_n)
                        if got is None:
                            ok = False
                            break
                        sel += got
                    if not ok:
                        continue
                    if not best_fit:
                        occupied.update(body)
                        reserved.update(sel)
                        solution[iid] = {"facility_type": tpl,
                                         "pose_idx": idx}
                        return True
                    key = (-snugness(body), yb, x0)
                    if best is None or key < best[0]:
                        best = (key, idx, sel, body)
        if best is None:
            return False
        _k, idx, sel, body = best
        occupied.update(body)
        reserved.update(sel)
        solution[iid] = {"facility_type": tpl, "pose_idx": idx}
        return True

    manuf_insts = [i for i in instances if str(i["facility_type"]) in MANUF]
    # 小件先（3×3 先自组织共享 front 走廊网，大件后进整块区——
    # comb 兜底 241 vs 大件先 BL 226 的实测教训）
    manuf_insts.sort(key=lambda i: (
        MANUF[str(i["facility_type"])][0] * MANUF[str(i["facility_type"])][1],
        str(i["instance_id"])))
    if args.seed:
        import hashlib

        def _h(iid):
            return hashlib.sha256(f"{args.seed}:{iid}".encode()).hexdigest()
        manuf_insts.sort(key=lambda i: (
            MANUF[str(i["facility_type"])][0]
            * MANUF[str(i["facility_type"])][1],
            _h(str(i["instance_id"]))))
    for i in manuf_insts:
        iid = str(i["instance_id"])
        tpl = str(i["facility_type"])
        if not try_manuf(iid, tpl, best_fit=(tpl == "manufacturing_3x3")):
            unplaced.append(iid)

    place_wall = round(time.perf_counter() - t0, 2)
    result = {
        "harness": "witness_skyline_v1",
        "ghost": [args.ghost_x, args.ghost_y, args.ghost_w, args.ghost_h],
        "placed": len(solution), "unplaced": unplaced,
        "occupied_cells": len(occupied),
        "reserved_whisker_cells": len(reserved),
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
                      "reserved": result["reserved_whisker_cells"],
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
