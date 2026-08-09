"""PCR-CUT Phase 3 — Patch conflict separator.

Pipeline that ties together: layout → patch candidates → patch belt CP-SAT →
extract + validate core → master signature-lifted nogood cut.

Caller (Phase 4 benders_loop hook) invokes `run_patch_conflict_separation` after
master OPTIMAL and before binding. A successful separation returns cut_added=True
and the master will resolve with the new constraint.

soundness gate: every accepted cut has passed Phase 2 replay validation; if any
core fails replay, fail-closed (no cut), and the loop falls through to the
existing binding/routing verifier.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from src.models.patch_routing_core import (
    PatchCoreValidationResult,
    PatchPortSpec,
    PatchRoutingCore,
    PatchSpec,
    PoseAssumption,
    extract_and_validate_patch_core,
)

GRID_W = 70
GRID_H = 70
DIR_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}


@dataclass
class PatchSeparationResult:
    """One full separator pass over a layout."""
    cut_added: bool
    cuts_attempted: int
    cuts_accepted: int
    cuts_rejected: int
    candidates_evaluated: int
    patch_results: List[Dict[str, Any]] = field(default_factory=list)
    cut_metadata: List[Dict[str, Any]] = field(default_factory=list)
    wall_s: float = 0.0
    reason: str = ""


def _placement_to_occupied(
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Tuple[Set[Tuple[int, int]], Dict[Tuple[int, int], str]]:
    occupied: Set[Tuple[int, int]] = set()
    owner_by_cell: Dict[Tuple[int, int], str] = {}
    for iid, sol in placement_solution.items():
        tpl = str(sol.get("facility_type", ""))
        pool = facility_pools.get(tpl, [])
        pose_idx = int(sol.get("pose_idx", -1))
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        for cell in pool[pose_idx].get("occupied_cells", []) or []:
            cell_t = (int(cell[0]), int(cell[1]))
            occupied.add(cell_t)
            owner_by_cell[cell_t] = str(iid)
    return occupied, owner_by_cell


def _collect_blocked_port_cells(
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    occupied: Set[Tuple[int, int]],
    grid_w: int = GRID_W,
    grid_h: int = GRID_H,
) -> Tuple[List[Set[Tuple[int, int]]], Set[Tuple[int, int]]]:
    """Group blocked-port front cells into 8-connected clusters (largest first)."""
    blocked: Set[Tuple[int, int]] = set()
    for iid, sol in placement_solution.items():
        tpl = str(sol.get("facility_type", ""))
        pool = facility_pools.get(tpl, [])
        pose_idx = int(sol.get("pose_idx", -1))
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        pose = pool[pose_idx]
        for side in ("input_port_cells", "output_port_cells"):
            for port in pose.get(side, []) or []:
                px = int(port["x"])
                py = int(port["y"])
                dx, dy = DIR_DELTA.get(str(port.get("dir", "")), (0, 0))
                fx, fy = px + dx, py + dy
                if not (0 <= fx < grid_w and 0 <= fy < grid_h):
                    continue
                if (fx, fy) in occupied:
                    blocked.add((fx, fy))

    clusters: List[Set[Tuple[int, int]]] = []
    visited: Set[Tuple[int, int]] = set()
    for cell in blocked:
        if cell in visited:
            continue
        cur: Set[Tuple[int, int]] = set()
        stack = [cell]
        while stack:
            c = stack.pop()
            if c in visited:
                continue
            visited.add(c)
            cur.add(c)
            cx, cy = c
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    n = (cx + dx, cy + dy)
                    if n in blocked and n not in visited:
                        stack.append(n)
        clusters.append(cur)
    clusters.sort(key=len, reverse=True)
    return clusters, blocked


def _make_strip_patch(sep_id: str, wall_cells: Iterable[Tuple[int, int]], r: int, grid_w: int, grid_h: int) -> Set[Tuple[int, int]]:
    if sep_id.startswith("V_"):
        x_center = int(sep_id[2:])
        return {(x, y) for x in range(max(0, x_center - r), min(grid_w, x_center + r + 1))
                for y in range(grid_h)}
    if sep_id.startswith("H_"):
        y_center = int(sep_id[2:])
        return {(x, y) for x in range(grid_w)
                for y in range(max(0, y_center - r), min(grid_h, y_center + r + 1))}
    if sep_id.startswith("GM_"):
        cells: Set[Tuple[int, int]] = set()
        for (wx, wy) in wall_cells:
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    nx, ny = wx + dx, wy + dy
                    if 0 <= nx < grid_w and 0 <= ny < grid_h:
                        cells.add((nx, ny))
        return cells
    return set()


def _make_cluster_patch(cluster: Set[Tuple[int, int]], r: int, grid_w: int, grid_h: int) -> Set[Tuple[int, int]]:
    if not cluster:
        return set()
    xs = [c[0] for c in cluster]
    ys = [c[1] for c in cluster]
    x0 = max(0, min(xs) - r)
    x1 = min(grid_w, max(xs) + r + 1)
    y0 = max(0, min(ys) - r)
    y1 = min(grid_h, max(ys) + r + 1)
    return {(x, y) for x in range(x0, x1) for y in range(y0, y1)}


@dataclass
class _PatchCandidateRecord:
    patch_id: str
    cells: FrozenSet[Tuple[int, int]]
    kind: str
    score: float
    source_witness: Dict[str, Any]


def select_patch_candidates(
    *,
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    instances_by_id: Mapping[str, Any],
    ghost_anchor: Tuple[int, int],
    ghost_size: Tuple[int, int],
    sac_violations: Optional[Sequence[Any]] = None,
    max_cells: int = 900,
    limit: int = 3,
    grid_w: int = GRID_W,
    grid_h: int = GRID_H,
) -> List[_PatchCandidateRecord]:
    """Select top-`limit` patch candidates by pressure coverage (SAC slack + blocked
    clusters). Patches with > max_cells cells are filtered out (resource cap).
    """
    occupied, _owner_by_cell = _placement_to_occupied(placement_solution, facility_pools)
    clusters, blocked = _collect_blocked_port_cells(placement_solution, facility_pools, occupied, grid_w, grid_h)
    total_blocked = len(blocked)

    if sac_violations is None:
        from src.search.separator_capacity_separator import analyze_layout_for_separator_violations
        sac_violations = analyze_layout_for_separator_violations(
            placement_solution=placement_solution,
            facility_pools=facility_pools,
            instances_by_id=instances_by_id,
            grid_w=grid_w, grid_h=grid_h,
            ghost_anchor=ghost_anchor, ghost_size=ghost_size,
            include_axis=True, include_ghost_moat=True,
            separator_limit=140,
        )
    total_sac_slack = sum(abs(v.slack) for v in sac_violations if getattr(v, "slack", 0) < 0)

    candidates: List[_PatchCandidateRecord] = []
    top_violations = sorted(sac_violations, key=lambda v: getattr(v, "slack", 0))[:10]
    for v in top_violations:
        sep = getattr(v, "separator", None)
        if sep is None:
            continue
        for r in (3, 5, 7):
            cells = _make_strip_patch(str(sep.sep_id), set(sep.wall_cells), r, grid_w, grid_h)
            if not cells or len(cells) > max_cells:
                continue
            sac_cov = sum(
                abs(vv.slack) for vv in sac_violations
                if getattr(vv, "slack", 0) < 0
                and any(wc in cells for wc in getattr(vv.separator, "wall_cells", []))
            )
            blocked_cov = sum(1 for bc in blocked if bc in cells)
            score = max(
                sac_cov / total_sac_slack if total_sac_slack > 0 else 0,
                blocked_cov / total_blocked if total_blocked > 0 else 0,
            )
            candidates.append(_PatchCandidateRecord(
                patch_id=f"strip_{sep.sep_id}_r{r}",
                cells=frozenset(cells), kind="separator_strip", score=score,
                source_witness={"sac_sep": str(sep.sep_id), "sac_slack": float(getattr(v, "slack", 0))},
            ))

    for ci, cluster in enumerate(clusters[:10]):
        for r in (4, 8, 12):
            cells = _make_cluster_patch(cluster, r, grid_w, grid_h)
            if not cells or len(cells) > max_cells:
                continue
            sac_cov = sum(
                abs(vv.slack) for vv in sac_violations
                if getattr(vv, "slack", 0) < 0
                and any(wc in cells for wc in getattr(vv.separator, "wall_cells", []))
            )
            blocked_cov = sum(1 for bc in blocked if bc in cells)
            score = max(
                sac_cov / total_sac_slack if total_sac_slack > 0 else 0,
                blocked_cov / total_blocked if total_blocked > 0 else 0,
            )
            candidates.append(_PatchCandidateRecord(
                patch_id=f"cluster_{ci}_r{r}",
                cells=frozenset(cells), kind="cluster", score=score,
                source_witness={"blocked_cluster": int(ci), "cluster_size": int(len(cluster))},
            ))

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:limit]


def _build_patch_inputs(
    candidate: _PatchCandidateRecord,
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    port_specs: Sequence[Mapping[str, Any]],
    grid_w: int = GRID_W,
    grid_h: int = GRID_H,
) -> Tuple[PatchSpec, Set[Tuple[int, int]], Dict[str, Set[Tuple[int, int]]], List[PatchPortSpec], List[PoseAssumption]]:
    patch_cells = set(candidate.cells)
    spec = PatchSpec.from_cells(candidate.patch_id, patch_cells, source_witness=dict(candidate.source_witness))

    occupied, _owner_by_cell = _placement_to_occupied(placement_solution, facility_pools)
    free_cells = {(x, y) for x in range(grid_w) for y in range(grid_h) if (x, y) not in occupied}
    commodities = {str(ps["commodity"]) for ps in port_specs}
    active_cells: Dict[str, Set[Tuple[int, int]]] = {c: set(free_cells) for c in commodities}

    patch_ports: List[PatchPortSpec] = []
    for ps in port_specs:
        cell = (int(ps["x"]), int(ps["y"]))
        if cell not in patch_cells:
            continue
        patch_ports.append(PatchPortSpec(
            instance_id=str(ps.get("instance_id", "")),
            x=int(ps["x"]),
            y=int(ps["y"]),
            direction=str(ps["dir"]),
            commodity=str(ps["commodity"]),
            type=str(ps["type"]),
            pose_idx=int(ps.get("pose_idx", placement_solution.get(str(ps.get("instance_id", "")), {}).get("pose_idx", -1))),
        ))

    seen: Set[str] = set()
    assumptions: List[PoseAssumption] = []
    for pp in patch_ports:
        if pp.instance_id in seen:
            continue
        seen.add(pp.instance_id)
        pose_idx = int(placement_solution.get(pp.instance_id, {}).get("pose_idx", -1))
        assumptions.append(PoseAssumption(
            instance_id=pp.instance_id,
            pose_idx=pose_idx,
            local_signature=f"{pp.instance_id}_p{pose_idx}",
            assumption_name=f"assum_{pp.instance_id}",
        ))

    return spec, occupied, active_cells, patch_ports, assumptions


def patch_core_to_master_terms(
    core: Sequence[PoseAssumption],
) -> List[Tuple[str, int]]:
    """Pose assumptions → list of (instance_id, pose_idx) for master cut."""
    return [(pa.instance_id, int(pa.pose_idx)) for pa in core]


def build_patch_certificate_metadata(
    *,
    patch_spec: PatchSpec,
    raw_core_size: int,
    minimized_core_size: int,
    validation: PatchCoreValidationResult,
    quickxplain_stats: Optional[Mapping[str, Any]] = None,
    signature_lift_counts: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    return {
        "kind": "patch_routing_core_signature_cut",
        "patch_id": patch_spec.patch_id,
        "patch_bbox": list(patch_spec.bbox),
        "boundary_relaxation": True,
        "validated_replay_status": validation.status,
        "raw_core_size": int(raw_core_size),
        "minimized_core_size": int(minimized_core_size),
        "signature_lift_counts": list(signature_lift_counts or []),
        "quickxplain": dict(quickxplain_stats or {}),
        "source_witness": dict(patch_spec.source_witness),
        "replay_wall_s": float(validation.replay_wall_s),
    }


def run_patch_conflict_separation(
    *,
    master_delegate: Any,
    placement_solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    instances_by_id: Mapping[str, Any],
    port_specs: Sequence[Mapping[str, Any]],
    ghost_anchor: Tuple[int, int],
    ghost_size: Tuple[int, int],
    sac_violations: Optional[Sequence[Any]] = None,
    top_k: int = 3,
    seconds_budget: float = 10.0,
    per_patch_solve_seconds: float = 5.0,
    quickxplain_call_cap: int = 32,
    max_patch_cells: int = 900,
    require_replay: bool = True,
    grid_w: int = GRID_W,
    grid_h: int = GRID_H,
) -> PatchSeparationResult:
    """End-to-end: candidates → patch CP-SAT → extract+validate → master cut.

    Stops at first accepted cut or when budget is exhausted (whichever first).
    Returns result describing what happened — caller adds cut_added=True case to
    `_EXACT_INTERNAL_STATUS_MASTER_CUT_ADDED_CONTINUE` flow.
    """
    t_start = time.perf_counter()
    candidates = select_patch_candidates(
        placement_solution=placement_solution,
        facility_pools=facility_pools,
        instances_by_id=instances_by_id,
        ghost_anchor=ghost_anchor, ghost_size=ghost_size,
        sac_violations=sac_violations,
        max_cells=max_patch_cells,
        limit=top_k,
        grid_w=grid_w, grid_h=grid_h,
    )

    cuts_attempted = 0
    cuts_accepted = 0
    cuts_rejected = 0
    patch_results: List[Dict[str, Any]] = []
    cut_metadata: List[Dict[str, Any]] = []

    for cand in candidates:
        if time.perf_counter() - t_start > seconds_budget:
            break
        spec, occupied, active_cells, patch_ports, assumptions = _build_patch_inputs(
            cand, placement_solution, facility_pools, port_specs, grid_w=grid_w, grid_h=grid_h,
        )
        if not assumptions or not patch_ports:
            patch_results.append({"patch_id": cand.patch_id, "skipped": "no_assumptions_or_ports"})
            continue
        core = PatchRoutingCore(
            patch_spec=spec,
            full_grid_occupied=occupied,
            full_grid_active_cells=active_cells,
            patch_port_specs=patch_ports,
            pose_assumptions=assumptions,
            boundary_relaxation=True,
        )
        core.build()
        status = core.solve(time_limit=per_patch_solve_seconds)
        result = core.build_result()
        rec = {
            "patch_id": cand.patch_id,
            "kind": cand.kind,
            "score": cand.score,
            "status": status,
            "var_count": result.var_count,
            "constraint_count": result.constraint_count,
            "wall_s": result.wall_s,
            "raw_core_size": len(result.core),
        }
        patch_results.append(rec)
        if status != "INFEASIBLE":
            continue

        cuts_attempted += 1
        lifecycle = extract_and_validate_patch_core(
            core,
            minimize=True,
            time_limit_per_call=per_patch_solve_seconds,
            oracle_call_cap=quickxplain_call_cap,
        )
        if not lifecycle["accepted"]:
            cuts_rejected += 1
            rec["cut_rejected_reason"] = lifecycle["reason"]
            continue

        minimized_validation = lifecycle["minimized_validation"]
        minimized_core = minimized_validation.candidate_core if minimized_validation else lifecycle["raw_validation"].candidate_core

        master_terms = patch_core_to_master_terms(minimized_core)
        cut_meta = build_patch_certificate_metadata(
            patch_spec=spec,
            raw_core_size=lifecycle["raw_core_size"],
            minimized_core_size=lifecycle["minimized_core_size"],
            validation=minimized_validation or lifecycle["raw_validation"],
            quickxplain_stats={
                "oracle_calls": getattr(lifecycle["quickxplain"], "oracle_calls", None),
                "capped": getattr(lifecycle["quickxplain"], "capped", None),
                "wall_s": getattr(lifecycle["quickxplain"], "wall_s", None),
            } if lifecycle["quickxplain"] else None,
        )

        add_outcome = master_delegate.add_patch_routing_core_cut(
            master_terms, spec.cells, certificate_metadata=cut_meta,
        )
        if add_outcome.get("added"):
            cuts_accepted += 1
            cut_meta["signature_lift_counts"] = list(add_outcome.get("signature_lift_counts", []))
            cut_meta["total_pose_terms"] = int(add_outcome.get("total_pose_terms", 0))
            cut_metadata.append(cut_meta)
            rec["cut_added"] = True
            rec["cut_signature_lift_counts"] = cut_meta["signature_lift_counts"]
            # First accepted cut is enough — return so master can re-solve.
            return PatchSeparationResult(
                cut_added=True,
                cuts_attempted=cuts_attempted,
                cuts_accepted=cuts_accepted,
                cuts_rejected=cuts_rejected,
                candidates_evaluated=len(patch_results),
                patch_results=patch_results,
                cut_metadata=cut_metadata,
                wall_s=round(time.perf_counter() - t_start, 3),
                reason="first_cut_accepted",
            )
        cuts_rejected += 1
        rec["cut_rejected_reason"] = add_outcome.get("reason")

    return PatchSeparationResult(
        cut_added=False,
        cuts_attempted=cuts_attempted,
        cuts_accepted=cuts_accepted,
        cuts_rejected=cuts_rejected,
        candidates_evaluated=len(patch_results),
        patch_results=patch_results,
        cut_metadata=cut_metadata,
        wall_s=round(time.perf_counter() - t_start, 3),
        reason="exhausted_no_accepted_cut",
    )
