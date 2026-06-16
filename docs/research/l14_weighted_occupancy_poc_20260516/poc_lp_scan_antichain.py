"""L14 PoC step 3: 在 antichain × sample anchors 上跑 LP separation, 算 coverage 比例.

成功判据 (GPT 自己给):
- covered_anchors / total_anchors for area>405 antichain
- certified_infeasible_candidates / total_super-405_candidates

PoC 用 sample (每 candidate 5-9 个 anchor), 不跑全 anchor (那是几十小时).

输出 JSON 格式, 后续可整理.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ortools.linear_solver import pywraplp

from src.models.master_model import (
    MasterPlacementModel,
    infer_exact_required_pose_optional_counts,
    load_generic_io_requirements_artifact,
    load_project_data,
)


def build_mandatory_groups(model):
    delegate = model._coordinate_delegate
    groups = []
    for group in model._mandatory_groups:
        gid = str(group["group_id"])
        tpl = str(group["facility_type"])
        required = int(len(delegate.mandatory_slots.get(gid, [])))
        if required <= 0:
            required = int(len(list(group.get("instance_ids", []))))
        if required <= 0:
            continue
        tpl_poses = delegate._template_pose_tuple_by_idx.get(tpl, {})
        pose_cells = []
        for pose_idx in tpl_poses:
            cells = model._pose_cells(tpl, int(pose_idx))
            pose_cells.append([(int(c[0]), int(c[1])) for c in cells])
        groups.append({"group_id": gid, "demand": required, "pose_cells": pose_cells})
    return groups


def filter_feasible_poses(groups, forbidden: set):
    out = []
    for g in groups:
        feasible = [cells for cells in g["pose_cells"]
                    if not any((cx, cy) in forbidden for cx, cy in cells)]
        if not feasible:
            return None
        out.append({"group_id": g["group_id"], "demand": g["demand"], "feasible_poses": feasible})
    return out


def lp_separation_once(grid, forbidden, groups, max_iter=500, init_per_group=3, tol=1e-7):
    grid_w, grid_h = grid
    feas = filter_feasible_poses(groups, forbidden)
    if feas is None:
        return {"status": "trivial_infeasible", "lp_objective": float("inf"), "iterations": 0,
                "certifies": True}
    active = [(gi, cells) for gi, g in enumerate(feas) for cells in g["feasible_poses"][:init_per_group]]
    cells_uni = [(x, y) for x in range(grid_w) for y in range(grid_h) if (x, y) not in forbidden]
    lp_val = 0.0
    for it in range(max_iter):
        solver = pywraplp.Solver.CreateSolver("GLOP")
        if solver is None:
            return {"status": "solver_unavailable", "lp_objective": 0.0, "iterations": it,
                    "certifies": False}
        lam = {c: solver.NumVar(0.0, solver.infinity(), "") for c in cells_uni}
        mu = [solver.NumVar(-solver.infinity(), solver.infinity(), "") for _ in feas]
        norm = solver.Constraint(1.0, 1.0)
        for c in cells_uni:
            norm.SetCoefficient(lam[c], 1.0)
        for gi, pcells in active:
            ct = solver.Constraint(0.0, solver.infinity())
            ct.SetCoefficient(mu[gi], -1.0)
            for c in pcells:
                ct.SetCoefficient(lam[c], 1.0)
        obj = solver.Objective()
        for gi, g in enumerate(feas):
            obj.SetCoefficient(mu[gi], float(g["demand"]))
        obj.SetMaximization()
        st = solver.Solve()
        if st != pywraplp.Solver.OPTIMAL:
            return {"status": f"lp_status_{st}", "lp_objective": 0.0, "iterations": it,
                    "certifies": False}
        lp_val = solver.Objective().Value()
        lam_v = {c: lam[c].solution_value() for c in cells_uni}
        mu_v = [mu[gi].solution_value() for gi in range(len(feas))]
        viol = []
        for gi, g in enumerate(feas):
            best, bcells = None, None
            for cells in g["feasible_poses"]:
                s = sum(lam_v.get(c, 0.0) for c in cells)
                if best is None or s < best:
                    best = s
                    bcells = cells
            if mu_v[gi] - best > tol:
                viol.append((gi, bcells))
        if not viol:
            return {"status": "solved", "lp_objective": float(lp_val), "iterations": it + 1,
                    "certifies": lp_val > 1.0 + tol, "mu_values": [float(v) for v in mu_v]}
        for gi, cells in viol:
            active.append((gi, cells))
    return {"status": "max_iter", "lp_objective": float(lp_val), "iterations": max_iter,
            "certifies": lp_val > 1.0 + tol}


def generate_antichain(min_side, area_threshold, grid):
    out = []
    for w in range(min_side, grid + 1):
        for h in range(min_side, grid + 1):
            if w * h <= area_threshold:
                continue
            if (w - 1) * h <= area_threshold and w * (h - 1) <= area_threshold:
                out.append((w, h))
    return out


def sample_anchors(w, h, grid, n_samples):
    """Sample anchors: 4 corners + center + (n-5) on edges."""
    nx, ny = grid - w + 1, grid - h + 1
    if nx <= 0 or ny <= 0:
        return []
    samples = []
    samples.append((0, 0))                  # corner
    samples.append((nx - 1, 0))             # corner
    samples.append((0, ny - 1))             # corner
    samples.append((nx - 1, ny - 1))        # corner
    samples.append((nx // 2, ny // 2))      # center
    # 4 mid-edge
    if len(samples) < n_samples:
        samples.append((nx // 2, 0))
    if len(samples) < n_samples:
        samples.append((nx // 2, ny - 1))
    if len(samples) < n_samples:
        samples.append((0, ny // 2))
    if len(samples) < n_samples:
        samples.append((nx - 1, ny // 2))
    # dedup
    return list(dict.fromkeys(samples))[:n_samples]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--area-threshold", type=int, default=405)
    parser.add_argument("--min-side", type=int, default=6)
    parser.add_argument("--grid", type=int, default=70)
    parser.add_argument("--samples-per-shape", type=int, default=5)
    parser.add_argument("--max-iter", type=int, default=500)
    parser.add_argument("--max-shapes", type=int, default=0, help="0=all antichain shapes")
    parser.add_argument("--output", type=str, default="lp_scan_result.json")
    args = parser.parse_args()

    root = Path(".")
    print(f"[load] ... ", end="", flush=True)
    instances, pools, rules = load_project_data(root, "certified_exact")
    generic = load_generic_io_requirements_artifact(root)
    counts = infer_exact_required_pose_optional_counts(rules, generic)
    print("OK")
    print(f"[build core] ... ", end="", flush=True)
    t0 = time.perf_counter()
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True,
        generic_io_requirements=generic,
        exact_required_pose_optional_counts=counts)
    print(f"{time.perf_counter()-t0:.1f}s")
    m = MasterPlacementModel.from_exact_core(core, ghost_rect=(27, 15))
    groups = build_mandatory_groups(m)
    print(f"[groups] {len(groups)}")

    antichain = generate_antichain(args.min_side, args.area_threshold, args.grid)
    if args.max_shapes:
        antichain = antichain[: args.max_shapes]
    print(f"[antichain] {len(antichain)} shapes, sample {args.samples_per_shape}/shape")

    results = {"shapes": [], "summary": {}}
    total_anchors = 0
    total_cert = 0
    t_start = time.perf_counter()
    for shape in antichain:
        w, h = shape
        anchors = sample_anchors(w, h, args.grid, args.samples_per_shape)
        shape_total = 0
        shape_cert = 0
        anchor_results = []
        for anchor in anchors:
            ax, ay = anchor
            forbidden = {(ax + dx, ay + dy) for dx in range(w) for dy in range(h)}
            t_lp = time.perf_counter()
            r = lp_separation_once((args.grid, args.grid), forbidden, groups,
                                   max_iter=args.max_iter)
            lp_elapsed = time.perf_counter() - t_lp
            shape_total += 1
            if r.get("certifies"):
                shape_cert += 1
            anchor_results.append({
                "anchor": list(anchor),
                "status": r["status"],
                "lp_objective": r["lp_objective"],
                "iterations": r.get("iterations", 0),
                "certifies": r.get("certifies", False),
                "elapsed_seconds": float(lp_elapsed),
            })
        total_anchors += shape_total
        total_cert += shape_cert
        results["shapes"].append({
            "shape": [w, h],
            "area": w * h,
            "anchors": anchor_results,
            "certified": shape_cert,
            "total": shape_total,
        })
        pct = 100.0 * shape_cert / max(1, shape_total)
        print(f"  {w:2d}x{h:2d} (area {w*h:5d}): {shape_cert}/{shape_total} cert ({pct:.0f}%)")
    elapsed_all = time.perf_counter() - t_start
    pct_total = 100.0 * total_cert / max(1, total_anchors)
    print(f"\n[SUMMARY] {total_cert}/{total_anchors} cert ({pct_total:.1f}%), elapsed {elapsed_all:.1f}s")
    results["summary"] = {
        "total_anchors_sampled": total_anchors,
        "total_certified": total_cert,
        "cert_pct": pct_total,
        "elapsed_seconds": elapsed_all,
        "antichain_size": len(antichain),
        "samples_per_shape": args.samples_per_shape,
        "max_iter": args.max_iter,
        "area_threshold": args.area_threshold,
    }
    Path(args.output).write_text(json.dumps(results, indent=2))
    print(f"[output] {args.output}")


if __name__ == "__main__":
    main()
