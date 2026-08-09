"""witness 构造器 v5：CP-SAT 装箱小模型（research-grade，zero-sealed）。

判据 v2.1「两段式」思想的下界侧应用：把「纯装箱 + demand front 点」做成
独立 CP-SAT 可行性小模型（≈760 个矩形一个 NoOverlap2D，非 prod-scale，
内存 <2G，与 fc-lift-overnight 生产跑无资源冲突）。

建模（模型 A，全件固定 TB 口向）：
- 制造件 body = (x,y,w,h) interval 对；in front 须点 = body 大 y 侧外 2 行
  的 1×1 interval（数量 = demand），out 须点 = 小 y 侧外 2 行；全部矩形
  （含冻结的 boundary/core+其 front、ghost）进同一个 NoOverlap2D。
- 须共享被禁（比必要条件严）：只保 front 格时总足迹 ~4,100 < 4,900，
  账上装得下；解出后仍跑真机械审计终审。
- ghost 位置是变量（求解器自选 6×7 空矩形位置）。
- boundary + core 用贪心先放并冻结（贪心从未在此失败过）。

解 → 反查 pose_idx((tpl,'TB',x,y)) → 真机械审计（port_front_status ×
demand SSOT）→ binding 空域复核。审计才是权威，CP-SAT 模型只是构造器。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from ortools.sat.python import cp_model  # noqa: E402

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
         "manufacturing_6x4": (6, 4)}  # TB 形态 (w, h)


def _cells(seq):
    return {(int(c[0]), int(c[1])) for c in (seq or [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ghost-w", type=int, default=6)
    ap.add_argument("--ghost-h", type=int, default=7)
    ap.add_argument("--time-limit", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--free-orient", action="store_true",
                    help="放开四朝向（TB/BT/RL/LR 各 1 bool，exactly_one）")
    ap.add_argument("--hint-from", type=Path, default=None,
                    help="用某次贪心结果 JSON 的 solution 作 warm hint")
    ap.add_argument("--maximize", action="store_true",
                    help="件全 optional，maximize 放置数（观察卡点用；"
                         "非 266 全放时产物只是部分布局）")
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

    # ---- 冻结段：boundary + core 贪心放置（与 bl 系同逻辑）----
    occupied: set = set()
    reserved: set = set()
    solution: dict[str, dict] = {}

    def fronts_of(pose):
        sides = []
        for f in ("input_port_cells", "output_port_cells"):
            fs = []
            for q in pose.get(f) or []:
                dx, dy = _DIR_DELTA.get(str(q.get("dir", "")), (0, 0))
                fs.append((int(q["x"]) + dx, int(q["y"]) + dy))
            sides.append(fs)
        return sides

    def place_simple(iid, tpl):
        dem = demand_of(iid)
        for idx, pose in enumerate(pools[tpl]):
            body = _cells(pose.get("occupied_cells"))
            if body & occupied or body & reserved:
                continue
            sides = fronts_of(pose)
            if dem is None:
                ni, no = len(sides[0]), len(sides[1])
            else:
                ni, no = dem
            picks = []
            ok = True
            for cands, need_n in ((sides[0], ni), (sides[1], no)):
                got = [c for c in cands
                       if 0 <= c[0] < GRID and 0 <= c[1] < GRID
                       and c not in occupied]
                if len(got) < need_n:
                    ok = False
                    break
                picks += got[:need_n]
            if not ok:
                continue
            occupied.update(body)
            reserved.update(picks)
            solution[iid] = {"facility_type": tpl, "pose_idx": idx}
            return True
        return False

    t0 = time.perf_counter()
    frozen_fail = []
    for i in instances:
        if str(i["facility_type"]) == "boundary_storage_port":
            if not place_simple(str(i["instance_id"]),
                                "boundary_storage_port"):
                frozen_fail.append(str(i["instance_id"]))
    for i in instances:
        if str(i["facility_type"]) == "protocol_core":
            if not place_simple(str(i["instance_id"]), "protocol_core"):
                frozen_fail.append(str(i["instance_id"]))
    if frozen_fail:
        print("冻结段失败（boundary/core 没放下，中止）:", frozen_fail)
        return 1

    # ---- CP-SAT 模型 ----
    m = cp_model.CpModel()
    no2d_x, no2d_y = [], []

    # 封装：固定矩形与变量矩形
    def fixed_rect(x, y, w, h, tag):
        no2d_x.append(m.new_fixed_size_interval_var(x, w, f"fx_{tag}"))
        no2d_y.append(m.new_fixed_size_interval_var(y, h, f"fy_{tag}"))

    def var_rect(xv, yv, w, h, tag, pres=None):
        if pres is None:
            no2d_x.append(m.new_fixed_size_interval_var(xv, w, f"vx_{tag}"))
            no2d_y.append(m.new_fixed_size_interval_var(yv, h, f"vy_{tag}"))
        else:
            no2d_x.append(m.new_optional_fixed_size_interval_var(
                xv, w, pres, f"vx_{tag}"))
            no2d_y.append(m.new_optional_fixed_size_interval_var(
                yv, h, pres, f"vy_{tag}"))

    # 冻结格（boundary/core body + 其保留 front）：合并成 1×1 矩形集
    for (cx, cy) in sorted(occupied | reserved):
        fixed_rect(cx, cy, 1, 1, f"fz_{cx}_{cy}")

    # ghost（位置变量）
    gx = m.new_int_var(0, GRID - args.ghost_w, "gx")
    gy = m.new_int_var(0, GRID - args.ghost_h, "gy")
    var_rect(gx, gy, args.ghost_w, args.ghost_h, "ghost")

    manuf_insts = [i for i in instances if str(i["facility_type"]) in MANUF]
    mvars = {}
    pvars: dict = {}
    MODES = ("TB", "BT", "RL", "LR")
    for i in manuf_insts:
        iid = str(i["instance_id"])
        tpl = str(i["facility_type"])
        w, h = MANUF[tpl]
        pres = m.new_bool_var(f"p_{iid}") if args.maximize else None
        if pres is not None:
            pvars[iid] = pres
        dem = demand_of(iid)
        if dem is None:
            # 全侧保留对装箱太贵；mandatory 制造件全部 profiled（实测），
            # 若出现 None 直接按全口数保守处理
            ni, no = w, w
        else:
            ni, no = dem

        if not args.free_orient:
            # TB：out 口小 y 侧（front y-2），in 口大 y 侧（front y+h+1）
            xv = m.new_int_var(0, GRID - w, f"x_{iid}")
            yv = m.new_int_var(2, GRID - h - 2, f"y_{iid}")
            var_rect(xv, yv, w, h, f"body_{iid}", pres)
            ins, outs = [], []
            for k in range(ni):
                ox = m.new_int_var(0, GRID - 1, f"i{k}_{iid}")
                off = m.new_int_var(0, w - 1, f"io{k}_{iid}")
                m.add(ox == xv + off)
                syv = m.new_int_var(0, GRID - 1, f"iy{k}_{iid}")
                m.add(syv == yv + h + 1)
                var_rect(ox, syv, 1, 1, f"inf{k}_{iid}", pres)
                ins.append((ox, syv, off))
            for k in range(no):
                ox = m.new_int_var(0, GRID - 1, f"o{k}_{iid}")
                off = m.new_int_var(0, w - 1, f"oo{k}_{iid}")
                m.add(ox == xv + off)
                syv = m.new_int_var(0, GRID - 1, f"oy{k}_{iid}")
                m.add(syv == yv - 2)
                var_rect(ox, syv, 1, 1, f"outf{k}_{iid}", pres)
                outs.append((ox, syv, off))
            for grp in (ins, outs):
                for a in range(len(grp) - 1):
                    m.add(grp[a][2] < grp[a + 1][2])
            mvars[iid] = (tpl, xv, yv, ins, outs, None)
            continue

        # ---- 四朝向：body 尺寸随 mode 转置，须坐标 per-mode enforce ----
        mb = {md: m.new_bool_var(f"m_{md}_{iid}") for md in MODES}
        m.add_exactly_one(mb.values())
        vert = m.new_bool_var(f"vert_{iid}")   # TB/BT = True
        m.add_bool_or([mb["TB"], mb["BT"]]).only_enforce_if(vert)
        m.add_bool_and([~mb["TB"], ~mb["BT"]]).only_enforce_if(~vert)
        wv = m.new_int_var(min(w, h), max(w, h), f"w_{iid}")
        hv = m.new_int_var(min(w, h), max(w, h), f"h_{iid}")
        m.add(wv == w).only_enforce_if(vert)
        m.add(hv == h).only_enforce_if(vert)
        m.add(wv == h).only_enforce_if(~vert)
        m.add(hv == w).only_enforce_if(~vert)
        xv = m.new_int_var(0, GRID - min(w, h), f"x_{iid}")
        yv = m.new_int_var(0, GRID - min(w, h), f"y_{iid}")
        m.add(xv + wv <= GRID)
        m.add(yv + hv <= GRID)
        xe = m.new_int_var(0, GRID, f"xe_{iid}")
        ye = m.new_int_var(0, GRID, f"ye_{iid}")
        m.add(xe == xv + wv)
        m.add(ye == yv + hv)
        if pres is None:
            no2d_x.append(m.new_interval_var(xv, wv, xe, f"bx_{iid}"))
            no2d_y.append(m.new_interval_var(yv, hv, ye, f"by_{iid}"))
        else:
            # maximize + 变尺寸 optional interval 触发 ortools 9.15 原生
            # SIGSEGV（08:40 实测 core dump）——改用 4 个 per-mode
            # optional fixed-size interval 绕行
            for md in MODES:
                bw, bh = (w, h) if md in ("TB", "BT") else (h, w)
                act = m.new_bool_var(f"act_{md}_{iid}")
                m.add_implication(act, pres)
                m.add_implication(act, mb[md])
                m.add_bool_or([act, ~pres, ~mb[md]])
                m.add(xv + bw <= GRID).only_enforce_if(act)
                m.add(yv + bh <= GRID).only_enforce_if(act)
                no2d_x.append(m.new_optional_fixed_size_interval_var(
                    xv, bw, act, f"bx_{md}_{iid}"))
                no2d_y.append(m.new_optional_fixed_size_interval_var(
                    yv, bh, act, f"by_{md}_{iid}"))

        # 须点边界（front 需在图内）：
        m.add(yv >= 2).only_enforce_if(mb["TB"])   # out front y-2
        m.add(ye <= GRID - 2).only_enforce_if(mb["TB"])  # in front ye+1
        m.add(yv >= 2).only_enforce_if(mb["BT"])
        m.add(ye <= GRID - 2).only_enforce_if(mb["BT"])
        m.add(xv >= 2).only_enforce_if(mb["RL"])
        m.add(xe <= GRID - 2).only_enforce_if(mb["RL"])
        m.add(xv >= 2).only_enforce_if(mb["LR"])
        m.add(xe <= GRID - 2).only_enforce_if(mb["LR"])

        def whisker(kind, k):
            sx = m.new_int_var(0, GRID - 1, f"{kind}x{k}_{iid}")
            sy = m.new_int_var(0, GRID - 1, f"{kind}y{k}_{iid}")
            off = m.new_int_var(0, max(w, h) - 1, f"{kind}o{k}_{iid}")
            # 侧长上界 per-mode（口沿侧边分布：TB/BT 侧=wv，RL/LR 侧=hv）
            m.add(off <= wv - 1).only_enforce_if(vert)
            m.add(off <= hv - 1).only_enforce_if(~vert)
            # in 须：TB 大 y 外 / BT 小 y 外 / RL 大 x 外 / LR 小 x 外
            # out 须与 in 对侧
            far_y = kind == "in"   # TB: in 在 ye+1
            m.add(sx == xv + off).only_enforce_if(mb["TB"])
            m.add(sy == (ye + 1 if far_y else yv - 2)).only_enforce_if(
                mb["TB"])
            m.add(sx == xv + off).only_enforce_if(mb["BT"])
            m.add(sy == (yv - 2 if far_y else ye + 1)).only_enforce_if(
                mb["BT"])
            m.add(sy == yv + off).only_enforce_if(mb["RL"])
            m.add(sx == (xe + 1 if far_y else xv - 2)).only_enforce_if(
                mb["RL"])
            m.add(sy == yv + off).only_enforce_if(mb["LR"])
            m.add(sx == (xv - 2 if far_y else xe + 1)).only_enforce_if(
                mb["LR"])
            var_rect(sx, sy, 1, 1, f"{kind}f{k}_{iid}", pres)
            return (sx, sy, off)

        ins = [whisker("in", k) for k in range(ni)]
        outs = [whisker("out", k) for k in range(no)]
        for grp in (ins, outs):
            for a in range(len(grp) - 1):
                m.add(grp[a][2] < grp[a + 1][2])
        mvars[iid] = (tpl, xv, yv, ins, outs, mb)

    # 对称破除：同 operation_type 的件两两可交换 → 强制 (x,y) 字典序链
    by_op: dict[str, list] = {}
    for i in manuf_insts:
        by_op.setdefault(str(i["operation_type"]), []).append(
            str(i["instance_id"]))
    for op, ids in by_op.items():
        ids.sort()
        for a in range(len(ids) - 1):
            _t1, xa, ya, _i1, _o1, _m1 = mvars[ids[a]]
            _t2, xb, yb, _i2, _o2, _m2 = mvars[ids[a + 1]]
            m.add(xa * GRID + ya <= xb * GRID + yb)
            if args.maximize:
                # 同 op presence 对称：后件放置 ⇒ 前件放置
                m.add_implication(pvars[ids[a + 1]], pvars[ids[a]])

    m.add_no_overlap_2d(no2d_x, no2d_y)
    if args.maximize:
        m.maximize(sum(pvars.values()))

    # warm hint：贪心结果 solution → (x, y, mode) 提示
    if args.hint_from and args.hint_from.exists():
        seed_sol = json.loads(args.hint_from.read_text(
            encoding="utf-8")).get("solution", {})
        hinted = 0
        for iid, entry in seed_sol.items():
            if iid not in mvars:
                continue
            tpl, xv, yv, _ins, _outs, mb = mvars[iid]
            pose = pools[tpl][entry["pose_idx"]]
            body = _cells(pose.get("occupied_cells"))
            md = str((pose.get("pose_params") or {}).get("port_mode"))
            if mb is None and md != "TB":
                continue
            m.add_hint(xv, min(c[0] for c in body))
            m.add_hint(yv, min(c[1] for c in body))
            if mb is not None and md in mb:
                for name, b in mb.items():
                    m.add_hint(b, 1 if name == md else 0)
            hinted += 1
        print(f"warm hint: {hinted} 件")

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = args.time_limit
    solver.parameters.num_workers = args.workers
    solver.parameters.log_search_progress = False
    status = solver.solve(m)
    st_name = solver.status_name(status)
    build_solve_wall = round(time.perf_counter() - t0, 2)
    print(f"CP-SAT: {st_name} wall={solver.wall_time:.1f}s")

    result = {
        "harness": "witness_cpsat_v1",
        "cpsat_status": st_name,
        "cpsat_wall_seconds": round(solver.wall_time, 2),
        "total_wall_seconds": build_solve_wall,
        "frozen_items": len(solution),
    }

    def _dump():
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    _dump()
    if st_name not in ("OPTIMAL", "FEASIBLE"):
        print("装箱模型无解/超时——固定 TB 口向可能过约束，或时限不够")
        return 2

    # ---- 解 → pose_idx 反查 ----
    mode_index = {}
    for tpl in MANUF:
        for idx, pose in enumerate(pools[tpl]):
            md = str((pose.get("pose_params") or {}).get("port_mode"))
            if md not in ("TB", "BT", "RL", "LR"):
                continue
            body = _cells(pose.get("occupied_cells"))
            mode_index[(tpl, md, min(c[0] for c in body),
                        min(c[1] for c in body))] = idx

    lookup_fail = []
    dropped = []
    for iid, (tpl, xv, yv, ins, outs, mb) in mvars.items():
        if args.maximize and solver.value(pvars[iid]) == 0:
            dropped.append(iid)
            continue
        x, y = solver.value(xv), solver.value(yv)
        if mb is None:
            md = "TB"
        else:
            md = next(name for name, b in mb.items()
                      if solver.value(b) == 1)
        idx = mode_index.get((tpl, md, x, y))
        if idx is None:
            lookup_fail.append((iid, md, x, y))
            continue
        solution[iid] = {"facility_type": tpl, "pose_idx": idx}
    if args.maximize:
        result["dropped"] = dropped
        print(f"maximize: 放置 {len(mvars) - len(dropped)}/{len(mvars)} "
              f"制造件，未放 {len(dropped)}")
    result["ghost"] = [solver.value(gx), solver.value(gy),
                       args.ghost_w, args.ghost_h]
    result["pose_lookup_fail"] = lookup_fail
    result["placed"] = len(solution)
    _dump()
    print(f"放置: {len(solution)}/266, ghost={result['ghost']}, "
          f"反查失败={len(lookup_fail)}")
    if lookup_fail:
        return 2

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

    # ---- ghost 区复核：确为空矩形 ----
    gxv, gyv = result["ghost"][0], result["ghost"][1]
    gcells = {(x, y) for x in range(gxv, gxv + args.ghost_w)
              for y in range(gyv, gyv + args.ghost_h)}
    all_bodies = set()
    for iid, entry in solution.items():
        all_bodies |= _cells(
            pools[entry["facility_type"]][entry["pose_idx"]]
            .get("occupied_cells"))
    result["ghost_clear"] = not (gcells & all_bodies)
    _dump()
    print(f"ghost 区无 body: {result['ghost_clear']}")

    if not args.skip_binding:
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
