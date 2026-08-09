"""PCR-CUT Phase 0 — patch candidate oracle.

验证: master OPTIMAL layout 上, SAC violations + blocked-port clusters 是否
集中在少数 patches (≤ 900 cells 覆盖 ≥ 70% 压力).

GO:
- top-3 patch covered_sac_negative_slack >= 70% 或 covered_blocked_ports >= 70%
- top-3 patch cells p90 <= 900
- oracle wall <= 5s

NO-GO:
- 需 > 1500 cells 才覆盖压力 → patch paradigm 无资源优势
- top-3 coverage < 40% → 压力均匀分散, patch 不 work

不改 production code, monkey-patch binding.build dump probe.
"""

from __future__ import annotations
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

OUT_FILE = Path("docs/research/pcr_cut_patch_routing_conflict_20260519/phase0_patch_oracle_stats.json")


@dataclass
class PatchCandidate:
    patch_id: str
    cells: Set[Tuple[int, int]]
    bbox: Tuple[int, int, int, int]
    kind: str  # "separator_strip" | "cluster" | "hybrid"
    sac_slack_covered: float = 0.0
    blocked_ports_covered: int = 0
    commodities_touched: Set[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "cell_count": len(self.cells),
            "bbox": list(self.bbox),
            "kind": self.kind,
            "sac_slack_covered": self.sac_slack_covered,
            "blocked_ports_covered": self.blocked_ports_covered,
            "commodities_touched_count": len(self.commodities_touched or set()),
        }


def collect_sac_pressure(placement_solution, facility_pools, instances_by_id, grid_w, grid_h, ghost_anchor, ghost_size):
    """Return List[(separator, required_crossings, free_wall_cells, slack)] sorted by slack asc."""
    from src.search.separator_capacity_separator import analyze_layout_for_separator_violations
    violations = analyze_layout_for_separator_violations(
        placement_solution=placement_solution,
        facility_pools=facility_pools,
        instances_by_id=instances_by_id,
        grid_w=grid_w, grid_h=grid_h,
        ghost_anchor=ghost_anchor, ghost_size=ghost_size,
        include_axis=True, include_ghost_moat=True,
        separator_limit=140,
    )
    return violations


def collect_blocked_clusters(placement_solution, facility_pools, port_specs, grid_w, grid_h):
    """8-neighbor cluster blocked port front_cells. Return List[Set[(x,y)]]."""
    # 从 placement_solution 计算 occupied
    occupied: Set[Tuple[int, int]] = set()
    for iid, sol in placement_solution.items():
        tpl = str(sol.get("facility_type", ""))
        pool = facility_pools.get(tpl, [])
        pose_idx = int(sol.get("pose_idx", -1))
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        for cell in pool[pose_idx].get("occupied_cells", []) or []:
            occupied.add((int(cell[0]), int(cell[1])))

    _DIR_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
    blocked_cells: Set[Tuple[int, int]] = set()
    for iid, sol in placement_solution.items():
        tpl = str(sol.get("facility_type", ""))
        pool = facility_pools.get(tpl, [])
        pose_idx = int(sol.get("pose_idx", -1))
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        pose = pool[pose_idx]
        for port_list in ("input_port_cells", "output_port_cells"):
            for port in pose.get(port_list, []) or []:
                px, py = int(port["x"]), int(port["y"])
                dx, dy = _DIR_DELTA.get(str(port["dir"]), (0, 0))
                fx, fy = px + dx, py + dy
                if not (0 <= fx < grid_w and 0 <= fy < grid_h):
                    continue
                if (fx, fy) in occupied:
                    blocked_cells.add((fx, fy))

    # 8-neighbor cluster
    clusters: List[Set[Tuple[int, int]]] = []
    visited: Set[Tuple[int, int]] = set()
    for cell in blocked_cells:
        if cell in visited:
            continue
        cluster: Set[Tuple[int, int]] = set()
        stack = [cell]
        while stack:
            c = stack.pop()
            if c in visited:
                continue
            visited.add(c)
            cluster.add(c)
            cx, cy = c
            for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
                n = (cx + dx, cy + dy)
                if n in blocked_cells and n not in visited:
                    stack.append(n)
        clusters.append(cluster)
    clusters.sort(key=len, reverse=True)
    return clusters, blocked_cells


def make_patch_from_separator(sep_id: str, wall_cells: Set[Tuple[int, int]], r: int, grid_w: int, grid_h: int) -> Set[Tuple[int, int]]:
    """Strip patch: wall cells dilated by r in perpendicular direction."""
    if sep_id.startswith("V_"):
        x_center = int(sep_id[2:])
        return {(x, y) for x in range(max(0, x_center - r), min(grid_w, x_center + r + 1))
                for y in range(grid_h)}
    if sep_id.startswith("H_"):
        y_center = int(sep_id[2:])
        return {(x, y) for x in range(grid_w)
                for y in range(max(0, y_center - r), min(grid_h, y_center + r + 1))}
    if sep_id.startswith("GM_"):
        # ghost moat — just take the wall and a 3-cell band
        cells: Set[Tuple[int, int]] = set()
        for (wx, wy) in wall_cells:
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    nx, ny = wx + dx, wy + dy
                    if 0 <= nx < grid_w and 0 <= ny < grid_h:
                        cells.add((nx, ny))
        return cells
    return set()


def make_patch_from_cluster(cluster: Set[Tuple[int, int]], r: int, grid_w: int, grid_h: int) -> Set[Tuple[int, int]]:
    """Cluster patch: bbox dilated by r."""
    if not cluster:
        return set()
    xs = [c[0] for c in cluster]
    ys = [c[1] for c in cluster]
    x0, x1 = max(0, min(xs) - r), min(grid_w, max(xs) + r + 1)
    y0, y1 = max(0, min(ys) - r), min(grid_h, max(ys) + r + 1)
    return {(x, y) for x in range(x0, x1) for y in range(y0, y1)}


def analyze_patches(placement_solution, facility_pools, instances_by_id, grid_w, grid_h, ghost_anchor, ghost_size):
    """Return List[PatchCandidate] sorted by coverage."""
    sac_violations = collect_sac_pressure(
        placement_solution, facility_pools, instances_by_id, grid_w, grid_h, ghost_anchor, ghost_size
    )
    blocked_clusters, blocked_cells = collect_blocked_clusters(
        placement_solution, facility_pools, None, grid_w, grid_h
    )
    total_sac_neg_slack = sum(abs(v.slack) for v in sac_violations if v.slack < 0)
    total_blocked = len(blocked_cells)

    candidates: List[PatchCandidate] = []

    # Separator strip patches: top-10 violations × r in {3, 5, 7}
    top_violations = sorted(sac_violations, key=lambda v: v.slack)[:10]
    for v in top_violations:
        for r in (3, 5, 7):
            cells = make_patch_from_separator(v.separator.sep_id, set(v.separator.wall_cells), r, grid_w, grid_h)
            if not cells:
                continue
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            bbox = (min(xs), min(ys), max(xs), max(ys))
            covered_neg_slack = sum(abs(vv.slack) for vv in sac_violations if vv.slack < 0 and any(wc in cells for wc in vv.separator.wall_cells))
            covered_blocked = sum(1 for bc in blocked_cells if bc in cells)
            candidates.append(PatchCandidate(
                patch_id=f"strip_{v.separator.sep_id}_r{r}",
                cells=cells, bbox=bbox, kind="separator_strip",
                sac_slack_covered=covered_neg_slack,
                blocked_ports_covered=covered_blocked,
                commodities_touched=set(v.crossing_commodities),
            ))

    # Cluster patches: top-10 clusters × r in {4, 8, 12}
    for ci, cluster in enumerate(blocked_clusters[:10]):
        for r in (4, 8, 12):
            cells = make_patch_from_cluster(cluster, r, grid_w, grid_h)
            if not cells:
                continue
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            bbox = (min(xs), min(ys), max(xs), max(ys))
            covered_neg_slack = sum(abs(vv.slack) for vv in sac_violations if vv.slack < 0 and any(wc in cells for wc in vv.separator.wall_cells))
            covered_blocked = sum(1 for bc in blocked_cells if bc in cells)
            candidates.append(PatchCandidate(
                patch_id=f"cluster_{ci}_r{r}",
                cells=cells, bbox=bbox, kind="cluster",
                sac_slack_covered=covered_neg_slack,
                blocked_ports_covered=covered_blocked,
                commodities_touched=set(),
            ))

    # filter to cells <= 900
    candidates = [c for c in candidates if len(c.cells) <= 900]
    # sort by coverage (SAC + blocked)
    def score(c):
        sac_frac = (c.sac_slack_covered / total_sac_neg_slack) if total_sac_neg_slack > 0 else 0
        blocked_frac = (c.blocked_ports_covered / total_blocked) if total_blocked > 0 else 0
        return max(sac_frac, blocked_frac)
    candidates.sort(key=score, reverse=True)

    return candidates, total_sac_neg_slack, total_blocked


def main() -> int:
    os.environ.setdefault("EXACT_USE_POSE_BOOL_MASTER", "1")
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    for k in (
        "EXACT_B1_SEPARATOR_HULL", "EXACT_B1_SEPARATOR_HULL_DYNAMIC",
        "EXACT_B1_ABSTRACT_ROUTING_LAYER",
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE", "EXACT_B1_ROUTING_AWARE_BINDING",
    ):
        os.environ.pop(k, None)

    print("=== PCR-CUT Phase 0 — patch candidate oracle ===")
    print("27×15 anchor (22,28), 1 master OPTIMAL layout")

    import src.models.binding_subproblem as bm
    orig_build = bm.PortBindingModel.build
    captured = {"done": False}

    def patched_build(self):
        orig_build(self)
        if captured["done"]:
            return
        captured["done"] = True
        from src.models.routing_subproblem import GRID_W, GRID_H
        t0 = time.perf_counter()
        candidates, total_sac, total_blocked = analyze_patches(
            self.placement_solution, self.facility_pools, self.instances_by_id,
            GRID_W, GRID_H, ghost_anchor=(22, 28), ghost_size=(27, 15),
        )
        analysis_wall = time.perf_counter() - t0

        top3 = candidates[:3]
        top3_sac_cov = sum(c.sac_slack_covered for c in top3)
        top3_blocked_cov = sum(c.blocked_ports_covered for c in top3)
        cells_p90 = sorted([len(c.cells) for c in top3])[-1] if top3 else 0

        out = {
            "total_sac_negative_slack": total_sac,
            "total_blocked_cells": total_blocked,
            "candidate_count": len(candidates),
            "analysis_wall_s": round(analysis_wall, 3),
            "top3_patches": [c.to_dict() for c in top3],
            "top3_sac_slack_coverage": top3_sac_cov,
            "top3_blocked_coverage": top3_blocked_cov,
            "top3_sac_coverage_frac": round(top3_sac_cov / total_sac, 3) if total_sac > 0 else None,
            "top3_blocked_coverage_frac": round(top3_blocked_cov / total_blocked, 3) if total_blocked > 0 else None,
            "top3_cells_max": cells_p90,
            "all_top10_candidates": [c.to_dict() for c in candidates[:10]],
        }
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_FILE, "w") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"[oracle] {len(candidates)} patches, top-3 sac cov={out['top3_sac_coverage_frac']}, blocked cov={out['top3_blocked_coverage_frac']}, cells_max={cells_p90}, wall={analysis_wall:.3f}s", flush=True)
        print(f"[oracle] dumped {OUT_FILE}", flush=True)

    bm.PortBindingModel.build = patched_build

    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=1,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=120.0,
        binding_seconds=10.0,
        routing_seconds=30.0,
        flow_seconds=10.0,
        campaign=None,
        session=None,
        disable_master_warm_start=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"\n=== Phase 0 PoC done: {status} in {elapsed:.1f}s ===")
    if not captured["done"]:
        print(">>> ❌ oracle 没 fire")
        return 1
    with open(OUT_FILE) as f:
        out = json.load(f)
    sac_frac = out.get("top3_sac_coverage_frac") or 0
    blocked_frac = out.get("top3_blocked_coverage_frac") or 0
    cells_max = out["top3_cells_max"]
    if (sac_frac >= 0.7 or blocked_frac >= 0.7) and cells_max <= 900:
        print(f">>> ✅ Phase 0 GO: top-3 patch sac cov={sac_frac} blocked cov={blocked_frac} cells_max={cells_max}")
        return 0
    if (sac_frac >= 0.4 or blocked_frac >= 0.4):
        print(f">>> 🟡 PARTIAL: top-3 coverage {max(sac_frac, blocked_frac)} (40-70%, marginal)")
        return 0
    print(f">>> ❌ NO-GO: top-3 sac cov={sac_frac} blocked cov={blocked_frac}, 压力均匀分散")
    return 1


if __name__ == "__main__":
    sys.exit(main())
