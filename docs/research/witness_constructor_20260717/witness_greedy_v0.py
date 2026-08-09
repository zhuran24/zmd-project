"""witness 构造器 v0（下界侧，research-grade，zero-sealed）。

目标：构造一张放下全部 266 mandatory + 留出 W×H 空矩形、且每实例每侧
自由 front 计数 ≥ demand（front-clear 必要条件）的布局；随后用真实
binding（含 RAB filter）复核空域数。决策包 doc 07 牌 A 的第一铲。

策略 v0：贪心 + 全 front 保留（保守：保留全部端口 front 格不许后来者
的 body 压上——比 demand 计数更严，省实现；空间不够再降级为按需保留）。
实例按池稀缺度升序放置（boundary_storage_port 仅 136 姿态最先）。

诚实边界：产物是 research witness 候选，不是 certified 断言；
power/pole 覆盖与 routing 连通归后续版本。
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

GRID_W = GRID_H = 70


def _cells(seq) -> set[tuple[int, int]]:
    return {(int(c[0]), int(c[1])) for c in (seq or [])}


def _ports(pose) -> list:
    return list(pose.get("input_port_cells") or []) + list(
        pose.get("output_port_cells") or []
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-x", type=int, default=8)
    parser.add_argument("--ghost-y", type=int, default=8)
    parser.add_argument("--ghost-w", type=int, default=6)
    parser.add_argument("--ghost-h", type=int, default=7)
    parser.add_argument("--seed", type=int, default=0, help="姿态遍历次序种子（0=池原序）")
    parser.add_argument("--skip-binding", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

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

    ghost = {
        (x, y)
        for x in range(args.ghost_x, args.ghost_x + args.ghost_w)
        for y in range(args.ghost_y, args.ghost_y + args.ghost_h)
    }

    # 预处理池：每姿态的 body/front 集合。front = 端口 (x,y) 沿 dir 平移一格
    # （与 port_front_status 同一 _DIR_DELTA 口径；终审仍用真机械兜底）。
    pose_cache: dict[str, list[dict]] = {}
    for tpl, pool in pools.items():
        entries = []
        for idx, pose in enumerate(pool):
            body = _cells(pose.get("occupied_cells"))
            fronts = set()
            for port in _ports(pose):
                dx, dy = _DIR_DELTA.get(str(port.get("dir", "")), (0, 0))
                fronts.add((int(port.get("x", 0)) + dx, int(port.get("y", 0)) + dy))
            entries.append({"idx": idx, "body": body, "fronts": fronts})
        pose_cache[tpl] = entries

    # 实例排序：边界件（稀缺+边缘绑定）→ 体格降序（装箱大件优先）→ id 稳定
    def _order_key(i):
        tpl = str(i["facility_type"])
        body_n = len(pools[tpl][0]["occupied_cells"])
        is_boundary = 0 if tpl == "boundary_storage_port" else 1
        return (is_boundary, -body_n, str(i["instance_id"]))

    order = sorted(instances, key=_order_key)

    # 每实例每侧需求（demand SSOT；generic/未 profile op 保守=保全侧 front）
    op_by_id_pre = {str(i["instance_id"]): str(i["operation_type"]) for i in instances}
    demand_by_id: dict[str, tuple[int, int] | None] = {}
    for i in instances:
        iid = str(i["instance_id"])
        op = op_by_id_pre[iid]
        try:
            if op in OPERATION_PORT_PROFILES and supports_exact_pose_level_binding(op):
                demand_by_id[iid] = routing_visible_port_demands(op, rfsc)
            else:
                demand_by_id[iid] = None  # 保守：全保
        except ValueError:
            demand_by_id[iid] = None

    # 分侧 front 缓存（按需保留要区分 in/out 侧）
    for tpl, pool in pools.items():
        for e, pose in zip(pose_cache[tpl], pool):
            sides = []
            for field in ("input_port_cells", "output_port_cells"):
                fs = []
                for port in pose.get(field) or []:
                    dx, dy = _DIR_DELTA.get(str(port.get("dir", "")), (0, 0))
                    fs.append((int(port.get("x", 0)) + dx, int(port.get("y", 0)) + dy))
                sides.append(fs)
            e["sides"] = sides

    occupied: set[tuple[int, int]] = set()
    reserved: set[tuple[int, int]] = set()  # 被承诺保持自由的 front 格
    solution: dict[str, dict] = {}
    unplaced: list[str] = []
    t0 = time.perf_counter()

    def _pick_fronts(cands: list, need: int) -> list | None:
        """从候选 front 里挑 need 个可用格；已保留的共享格零成本优先。"""
        in_grid = [c for c in cands
                   if 0 <= c[0] < GRID_W and 0 <= c[1] < GRID_H
                   and c not in occupied]
        if len(set(in_grid)) < need and len(in_grid) < need:
            return None
        shared = [c for c in in_grid if c in reserved]
        fresh = [c for c in in_grid if c not in reserved]
        picked = shared[:need]
        picked += fresh[: need - len(picked)]
        return picked if len(picked) >= need else None

    for inst in order:
        iid = str(inst["instance_id"])
        tpl = str(inst["facility_type"])
        entries = pose_cache[tpl]
        if args.seed:
            rng_off = (hash((args.seed, iid)) % len(entries))
            entries = entries[rng_off:] + entries[:rng_off]
        demand = demand_by_id.get(iid)
        placed = False
        for e in entries:
            body = e["body"]
            if body & occupied or body & ghost or body & reserved:
                continue
            if demand is None:
                # 保守：全侧 front 都保
                need_sets = [e["sides"][0], e["sides"][1]]
                picks: list = []
                ok = True
                for cands in need_sets:
                    got = _pick_fronts(cands, len([c for c in cands
                                                   if 0 <= c[0] < GRID_W
                                                   and 0 <= c[1] < GRID_H])) or []
                    in_grid_n = len([c for c in cands if 0 <= c[0] < GRID_W
                                     and 0 <= c[1] < GRID_H])
                    if len(got) < in_grid_n:
                        ok = False
                        break
                    picks += got
                if not ok:
                    continue
            else:
                req_in, vis_out = demand
                got_in = _pick_fronts(e["sides"][0], req_in)
                if got_in is None:
                    continue
                got_out = _pick_fronts(e["sides"][1], vis_out)
                if got_out is None:
                    continue
                picks = got_in + got_out
            occupied |= body
            reserved |= set(picks)
            solution[iid] = {"facility_type": tpl, "pose_idx": e["idx"]}
            placed = True
            break
        if not placed:
            unplaced.append(iid)

    place_wall = round(time.perf_counter() - t0, 2)
    result = {
        "harness": "witness_greedy_v0",
        "ghost": [args.ghost_x, args.ghost_y, args.ghost_w, args.ghost_h],
        "seed": args.seed,
        "placed": len(solution),
        "unplaced": unplaced,
        "occupied_cells": len(occupied),
        "reserved_front_cells": len(reserved),
        "place_wall_seconds": place_wall,
    }

    def _dump():
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    _dump()
    print(json.dumps({k: result[k] for k in ("placed", "unplaced", "occupied_cells",
                                             "place_wall_seconds") if k in result},
                     ensure_ascii=False, default=str))

    if unplaced:
        print(f"UNPLACED x{len(unplaced)} — 构造未完成，front-clear 审计仍执行（部分布局）")

    # ---- 审计（真机械）：每实例每侧自由 front 计数 vs demand ----
    context = build_routing_binding_context(solution, pools, grid_w=GRID_W, grid_h=GRID_H)
    op_by_id = {str(i["instance_id"]): str(i["operation_type"]) for i in instances}
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
    result["front_clear_audit"] = {
        "checked": checked, "violations": len(audit_fail),
        "detail": audit_fail[:20],
    }
    _dump()
    print(f"front-clear 审计: checked={checked} violations={len(audit_fail)}")

    # ---- binding 复核（真 RAB 链）----
    if not args.skip_binding and not unplaced:
        model = PortBindingModel(
            placement_solution=solution,
            facility_pools=pools,
            instances=instances,
            required_generic_outputs=io_req["required_generic_outputs"],
            required_generic_inputs=io_req["required_generic_inputs"],
            project_root=PROJECT_ROOT,
            routing_context=context,
        )
        model.build()
        empty = [str(e["instance_id"])
                 for e in model.extract_empty_binding_domain_instances()]
        result["binding_empty_domains"] = {"count": len(empty), "ids": empty[:20]}
        _dump()
        print(f"binding 空域: {len(empty)}")

    result["solution"] = solution
    _dump()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
