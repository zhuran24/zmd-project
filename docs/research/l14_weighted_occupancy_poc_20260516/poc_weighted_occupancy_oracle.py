"""L14 PoC: weighted-occupancy blocker oracle (GPT 5/16 proposal).

证明 "70×70 + 266 mandatory + ghost rectangle B 在某位置塞不下" 用 Farkas 整数证书:

    lhs(λ, B) = sum_g d_g * m_g^B(λ) > cap_B(λ) = rhs(λ, B)

其中:
- d_g: group g 需求数 (266 个 mandatory 按 facility_type+operation_type 聚合)
- m_g^B(λ): group g 在不碰 B 的前提下, 所有合法 pose 中 sum_{c in F(p)} λ_c 的最小值
- cap_B(λ): sum_{c in C\B} λ_c

如果 lhs > rhs 严格成立, 则 B 下 mandatory placement 几何 infeasible.

证明 sound 因 mandatory 几何 relaxation 忽略 routing/flow/power 只会放松问题.

证书 dominance: B ⊆ G ⇒ G 也 infeasible (cap 减小 + per-group min 不减).

PoC 阶段只实现:
- antichain generator (area > 405 极小覆盖形状)
- λ=1 (uniform area cut) 验证 13 已知 INFEASIBLE
- λ=window (rectangle 内 1, 其他 0) 扫常见 sub-window 看 coverage
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.master_model import (
    MasterPlacementModel,
    infer_exact_required_pose_optional_counts,
    load_generic_io_requirements_artifact,
    load_project_data,
)


GridShape = Tuple[int, int]  # (W, H) ghost rect 尺寸
Anchor = Tuple[int, int]  # (x, y) bottom-left


def generate_antichain(min_side: int, area_threshold: int, grid_w: int, grid_h: int) -> List[GridShape]:
    """生成 area > area_threshold + w,h >= min_side + w,h <= grid 的最小超界形状.

    GPT claim: (w-1)h <= threshold AND w(h-1) <= threshold AND w*h > threshold.
    这是矩形 containment partial order 上的极小元 — 任何更大 (w'>=w, h'>=h) candidate
    都被它支配. 因此只需对 antichain 形状的 anchor 生成 blocker, dominance 自动覆盖更大.
    """
    out: List[GridShape] = []
    for w in range(min_side, grid_w + 1):
        for h in range(min_side, grid_h + 1):
            if w * h <= area_threshold:
                continue
            if (w - 1) * h > area_threshold and w * (h - 1) > area_threshold:
                continue  # 不是极小: 缩小任一边后仍超界
            if (w - 1) * h <= area_threshold and w * (h - 1) <= area_threshold:
                out.append((w, h))  # 极小 antichain 元素
    return out


def build_mandatory_groups(model: MasterPlacementModel) -> List[Dict]:
    """按 GPT 建议 19 group 聚合 (facility_type + operation_type), 不按 266 slot.

    返回 [{group_id, demand, footprint_w, footprint_h, poses: [(anchor_x, anchor_y, orientation, ...)]}, ...]
    每个 group 收集所有 pose 的 cell occupancy (对 NoOverlap2D 来说 only rectangle 重要).
    """
    delegate = model._coordinate_delegate
    if delegate is None:
        raise RuntimeError("coordinate delegate unavailable; need exact_mode build")

    groups_out: List[Dict] = []
    for group in model._mandatory_groups:
        group_id = str(group["group_id"])
        tpl = str(group["facility_type"])
        required = int(len(delegate.mandatory_slots.get(group_id, [])))
        if required <= 0:
            required = int(len(list(group.get("instance_ids", []))))
        if required <= 0:
            continue

        pose_cells: List[List[Tuple[int, int]]] = []
        # delegate._template_pose_tuple_by_idx[tpl] gives all pose_idx in template
        tpl_poses = delegate._template_pose_tuple_by_idx.get(tpl, {})
        for pose_idx in tpl_poses:
            cells = model._pose_cells(tpl, int(pose_idx))
            pose_cells.append([(int(c[0]), int(c[1])) for c in cells])
        if not pose_cells:
            continue
        groups_out.append({
            "group_id": group_id,
            "facility_type": tpl,
            "demand": required,
            "pose_cells": pose_cells,
        })
    return groups_out


def compute_min_weighted_pose(group: Dict, weights: Dict[Tuple[int, int], int], forbidden: set) -> int:
    """对 group 找一个不碰 forbidden, 加权占用最小的 pose. 返回最小权重和.

    如果 group 在 forbidden 下无任何合法 pose, 返回 None (caller 视为 infeasible 直接 lhs += inf).
    """
    best = None
    for cells in group["pose_cells"]:
        if any((cx, cy) in forbidden for cx, cy in cells):
            continue  # pose 碰 forbidden
        total = sum(weights.get((cx, cy), 0) for cx, cy in cells)
        if best is None or total < best:
            best = total
    return best


def verify_certificate(
    grid: Tuple[int, int],
    forbidden: set,
    weights: Dict[Tuple[int, int], int],
    groups: List[Dict],
) -> Dict:
    """Integer verifier: 重新计算 lhs/rhs/strict_margin. Sound, 不信任 LP 浮点.

    Returns dict with:
      - lhs: int (sum_g d_g * m_g)
      - rhs: int (cap_B(λ))
      - strict_margin: lhs - rhs (>0 means certificate valid)
      - per_group_minima: [{group_id, demand, min_weight, infeasible: bool}, ...]
      - infeasible_pose_groups: count of groups with no feasible pose under forbidden
    """
    grid_w, grid_h = grid
    cap = 0
    for x in range(grid_w):
        for y in range(grid_h):
            if (x, y) in forbidden:
                continue
            cap += int(weights.get((x, y), 0))
    lhs = 0
    per_group_minima = []
    infeasible_groups = 0
    for g in groups:
        m = compute_min_weighted_pose(g, weights, forbidden)
        if m is None:
            # 该组在 forbidden 下无合法 pose → certificate trivially valid
            # (mandatory placement 已经 infeasible, 不需 weighted argument)
            infeasible_groups += 1
            per_group_minima.append({
                "group_id": g["group_id"],
                "demand": g["demand"],
                "min_weight": None,
                "infeasible": True,
            })
            continue
        lhs += int(g["demand"]) * int(m)
        per_group_minima.append({
            "group_id": g["group_id"],
            "demand": int(g["demand"]),
            "min_weight": int(m),
            "infeasible": False,
        })
    return {
        "lhs": int(lhs),
        "rhs": int(cap),
        "strict_margin": int(lhs - cap),
        "per_group_minima": per_group_minima,
        "infeasible_pose_groups": infeasible_groups,
    }


def ghost_cells(w: int, h: int, anchor: Anchor) -> set:
    ax, ay = anchor
    return {(ax + dx, ay + dy) for dx in range(w) for dy in range(h)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--area-threshold", type=int, default=405,
                        help="Antichain 用 area>threshold 的最小形状. Default 405 = 27×15.")
    parser.add_argument("--min-side", type=int, default=6)
    parser.add_argument("--grid", type=int, default=70)
    parser.add_argument("--lambda-mode",
                        choices=["uniform", "window", "boundary", "boundary_thick", "ghost_ring", "boundary_plus_ring"],
                        default="uniform",
                        help="uniform=λ=1 all cells; window=λ=1 only in fixed center window; "
                             "boundary=λ=1 on棋盘 edge cells; boundary_thick=外圈 2 cells; "
                             "ghost_ring=ghost 周围 thick=2 cells; boundary_plus_ring=两者并")
    parser.add_argument("--window-w", type=int, default=10)
    parser.add_argument("--window-h", type=int, default=10)
    parser.add_argument("--ring-thick", type=int, default=2)
    parser.add_argument("--max-shapes", type=int, default=0, help="0=all antichain shapes")
    parser.add_argument("--max-anchors-per-shape", type=int, default=0, help="0=all anchors")
    args = parser.parse_args()

    project_root = Path(".")
    print(f"[load] project data ... ", end="", flush=True)
    instances, pools, rules = load_project_data(project_root, "certified_exact")
    generic = load_generic_io_requirements_artifact(project_root)
    counts = infer_exact_required_pose_optional_counts(rules, generic)
    print("OK")

    print(f"[build] exact core ... ", end="", flush=True)
    t0 = time.perf_counter()
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules,
        skip_power_coverage=True,
        generic_io_requirements=generic,
        exact_required_pose_optional_counts=counts,
    )
    print(f"OK ({time.perf_counter()-t0:.1f}s)")

    # 建一个简单 ghost 模型来 access mandatory groups (但其实 core 已含 mandatory)
    # 注意 ghost overlay 不影响 mandatory groups 定义, 用 27x15 当 throwaway overlay
    print(f"[build] overlay (27x15 dummy) ... ", end="", flush=True)
    t0 = time.perf_counter()
    m = MasterPlacementModel.from_exact_core(core, ghost_rect=(27, 15))
    print(f"OK ({time.perf_counter()-t0:.1f}s)")

    print(f"[groups] aggregate mandatory by (facility_type, operation_type) ... ", end="", flush=True)
    t0 = time.perf_counter()
    groups = build_mandatory_groups(m)
    total_pose = sum(len(g["pose_cells"]) for g in groups)
    print(f"OK ({time.perf_counter()-t0:.1f}s) → {len(groups)} groups, {total_pose} group-pose entries")
    print(f"[groups] per-group breakdown:")
    for g in groups[:5]:
        print(f"  {g['group_id']:50s} demand={g['demand']:3d} pose_count={len(g['pose_cells']):5d}")
    if len(groups) > 5:
        print(f"  ... ({len(groups)-5} more)")

    antichain = generate_antichain(args.min_side, args.area_threshold, args.grid, args.grid)
    print(f"\n[antichain] area > {args.area_threshold} + min_side >= {args.min_side}: {len(antichain)} shapes")
    print(f"  {antichain[:5]} ... {antichain[-3:] if len(antichain)>5 else ''}")

    if args.max_shapes:
        antichain = antichain[:args.max_shapes]
        print(f"[antichain] truncated to first {len(antichain)} shapes")

    # weights builder — anchor-aware (anchor 为 None 表示 anchor-independent λ)
    def build_weights(grid_w: int, grid_h: int, anchor=None, shape=None) -> Dict[Tuple[int, int], int]:
        mode = args.lambda_mode
        if mode == "uniform":
            return {(x, y): 1 for x in range(grid_w) for y in range(grid_h)}
        if mode == "window":
            ww, wh = args.window_w, args.window_h
            cx0 = (grid_w - ww) // 2
            cy0 = (grid_h - wh) // 2
            return {(cx0 + dx, cy0 + dy): 1 for dx in range(ww) for dy in range(wh)}
        if mode == "boundary":
            return {(x, y): 1 for x in range(grid_w) for y in range(grid_h)
                    if x == 0 or x == grid_w - 1 or y == 0 or y == grid_h - 1}
        if mode == "boundary_thick":
            t = args.ring_thick
            return {(x, y): 1 for x in range(grid_w) for y in range(grid_h)
                    if x < t or x >= grid_w - t or y < t or y >= grid_h - t}
        if mode == "ghost_ring":
            if anchor is None or shape is None:
                return {}
            ax, ay = anchor
            w, h = shape
            t = args.ring_thick
            # ring around ghost: cells within distance t of ghost, but not in ghost
            ghost = {(ax + dx, ay + dy) for dx in range(w) for dy in range(h)}
            ring = {}
            for dx in range(-t, w + t):
                for dy in range(-t, h + t):
                    cx, cy = ax + dx, ay + dy
                    if 0 <= cx < grid_w and 0 <= cy < grid_h and (cx, cy) not in ghost:
                        ring[(cx, cy)] = 1
            return ring
        if mode == "boundary_plus_ring":
            # boundary weights * 3, ring weights * 1 (heuristic: boundary 稀缺更重)
            w_b = {}
            for x in range(grid_w):
                for y in range(grid_h):
                    if x == 0 or x == grid_w - 1 or y == 0 or y == grid_h - 1:
                        w_b[(x, y)] = 3
            if anchor is not None and shape is not None:
                ax, ay = anchor
                w, h = shape
                t = args.ring_thick
                ghost = {(ax + dx, ay + dy) for dx in range(w) for dy in range(h)}
                for dx in range(-t, w + t):
                    for dy in range(-t, h + t):
                        cx, cy = ax + dx, ay + dy
                        if 0 <= cx < grid_w and 0 <= cy < grid_h and (cx, cy) not in ghost:
                            w_b[(cx, cy)] = w_b.get((cx, cy), 0) + 1
            return w_b
        raise ValueError(f"unknown lambda-mode: {mode}")

    # Iterate shapes × anchors
    print(f"\n[scan] λ_mode={args.lambda_mode}")
    if args.lambda_mode == "window":
        print(f"       window size {args.window_w}x{args.window_h}, fixed center")

    coverage = {}  # {(w,h): {"total":N, "certified":N, "by_pose_infeas":N, "max_margin":...}}
    t_start = time.perf_counter()
    for shape in antichain:
        w, h = shape
        n_anchors_x = args.grid - w + 1
        n_anchors_y = args.grid - h + 1
        if n_anchors_x <= 0 or n_anchors_y <= 0:
            continue
        anchors_list = [(ax, ay) for ax in range(n_anchors_x) for ay in range(n_anchors_y)]
        if args.max_anchors_per_shape:
            anchors_list = anchors_list[: args.max_anchors_per_shape]
        certified = 0
        pose_infeas = 0
        max_margin = -10**9
        for anchor in anchors_list:
            forbidden = ghost_cells(w, h, anchor)
            weights = build_weights(args.grid, args.grid, anchor=anchor, shape=(w, h))
            cert = verify_certificate((args.grid, args.grid), forbidden, weights, groups)
            if cert["infeasible_pose_groups"] > 0:
                pose_infeas += 1
                certified += 1
                continue
            if cert["strict_margin"] > 0:
                certified += 1
                if cert["strict_margin"] > max_margin:
                    max_margin = cert["strict_margin"]
        coverage[shape] = {
            "total": len(anchors_list),
            "certified": certified,
            "by_pose_infeas": pose_infeas,
            "by_weight": certified - pose_infeas,
            "max_margin": max_margin if max_margin > -10**9 else None,
        }
    elapsed = time.perf_counter() - t_start

    print(f"\n[coverage] scan complete in {elapsed:.1f}s")
    print(f"\n{'shape':>10s}  {'total':>8s}  {'certified':>10s}  {'by_pose_infeas':>16s}  {'by_weight':>10s}  {'max_margin':>10s}  {'%':>6s}")
    total_anchors = 0
    total_cert = 0
    for shape, stats in coverage.items():
        pct = 100.0 * stats["certified"] / max(1, stats["total"])
        total_anchors += stats["total"]
        total_cert += stats["certified"]
        margin_str = "n/a" if stats["max_margin"] is None else str(stats["max_margin"])
        print(f"  {shape[0]:2d}x{shape[1]:2d}    {stats['total']:8d}  {stats['certified']:10d}  {stats['by_pose_infeas']:16d}  {stats['by_weight']:10d}  {margin_str:>10s}  {pct:5.1f}%")
    pct_total = 100.0 * total_cert / max(1, total_anchors)
    print(f"\n  TOTAL     {total_anchors:8d}  {total_cert:10d}  {'':16s}  {'':10s}  {'':>10s}  {pct_total:5.1f}%")


if __name__ == "__main__":
    main()
