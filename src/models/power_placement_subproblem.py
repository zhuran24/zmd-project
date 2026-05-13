"""Deterministic power-pole placement subproblem.

When `EXACT_POWER_PLACEMENT_SUBPROBLEM=1`, the coordinate master no longer
carries the 220 residual `power_pole` optional slots or the geometric power
coverage witness constraints. After master solves for mandatory + required
optional + ghost layout, this subproblem picks `power_pole` poses so that:

- every powered facility in the master solution is covered by at least one
  selected pole (via the master-precomputed coverer table, so semantics are
  identical to the in-master coverage encoding),
- no two selected poles share a cell,
- no selected pole overlaps with master-placed facility cells or with the
  ghost rectangle.

Exact-preservation argument:

- `power_pole` has `needs_power=False`, `port_rule="none"`, zero input/output
  ports, and is not referenced by binding/routing as a port-bearing device.
  So it does not change mandatory facility coordinates or port modes.
- Coverage relation is taken verbatim from `_power_coverers_by_template_pose`,
  which is what the in-master coverage encoding consults. So an in-master
  solution and a (master+subproblem) solution describe the same set of
  feasible layouts.
- If the subproblem is INFEASIBLE for a given master layout, we feed a
  conservative presence-no-good back to the master via `add_benders_cut`,
  forbidding that exact powered-instance pose tuple from co-occurring again.
  That preserves exactness: the cut only rules out a layout proven
  uncoverable by *any* pole configuration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Sequence, Set, Tuple

from ortools.sat.python import cp_model

Cell = Tuple[int, int]


@dataclass(frozen=True)
class PowerPlacementResult:
    status: str  # "FEASIBLE" | "INFEASIBLE" | "TIMEOUT"
    selected_pose_indices: Tuple[int, ...] = ()
    uncovered_instance_ids: Tuple[str, ...] = ()
    stats: Mapping[str, Any] = field(default_factory=dict)


class PowerPlacementSubproblem:
    """Picks a feasible set of power poles for a given master layout."""

    def __init__(
        self,
        *,
        master_solution: Mapping[str, Mapping[str, Any]],
        facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
        powered_templates: Iterable[str],
        power_coverers_by_template_pose: Mapping[str, Mapping[int, Sequence[int]]],
        ghost_cells: Iterable[Cell] = (),
    ) -> None:
        self.master_solution = {str(k): dict(v) for k, v in master_solution.items()}
        self.facility_pools = facility_pools
        self._powered_templates: Set[str] = {str(t) for t in powered_templates}
        self._powered_templates.discard("power_pole")
        self._power_coverers_by_template_pose = power_coverers_by_template_pose
        self.ghost_cells: Set[Cell] = {
            (int(x), int(y)) for x, y in ghost_cells
        }
        # ortools .pyi 对 CpModel 的 PascalCase API (NewBoolVar/Add/...) 声明
        # 不全, mypy 报 attr-defined. CpModel 是 dynamic, 标 Any 让类型检查放过.
        self.model: Any = cp_model.CpModel()
        self.pole_vars: Dict[int, cp_model.IntVar] = {}
        self.candidate_pole_indices: List[int] = []
        self.coverers_by_instance: Dict[str, List[int]] = {}
        self.uncovered_instance_ids: List[str] = []

    def _cells_for_pose(
        self, tpl: str, pose_idx: int, key: str
    ) -> FrozenSet[Cell]:
        pool = self.facility_pools[str(tpl)]
        pose = pool[int(pose_idx)]
        raw = pose.get(key) or []
        return frozenset((int(x), int(y)) for x, y in raw)

    def _fixed_occupied_cells(self) -> Set[Cell]:
        occupied: Set[Cell] = set(self.ghost_cells)
        for entry in self.master_solution.values():
            tpl = str(entry.get("facility_type"))
            if tpl == "power_pole":
                continue
            pose_idx = int(entry["pose_idx"])
            occupied |= self._cells_for_pose(tpl, pose_idx, "occupied_cells")
        return occupied

    def _powered_instances(self) -> List[Tuple[str, str, int]]:
        # (instance_id, facility_type, pose_idx) for every needs_power facility
        # currently in the master solution. power_pole is excluded by construction.
        out: List[Tuple[str, str, int]] = []
        for instance_id, entry in self.master_solution.items():
            tpl = str(entry.get("facility_type"))
            if tpl not in self._powered_templates:
                continue
            out.append((str(instance_id), tpl, int(entry["pose_idx"])))
        return out

    def build(self) -> None:
        fixed = self._fixed_occupied_cells()
        pole_pool = list(self.facility_pools.get("power_pole", []))

        # 1. Candidate pole vars after fixed-occupancy filtering.
        cell_to_candidates: Dict[Cell, List[int]] = {}
        for pose_idx, pose in enumerate(pole_pool):
            occupied = {
                (int(x), int(y)) for x, y in (pose.get("occupied_cells") or [])
            }
            if occupied & fixed:
                continue
            var = self.model.NewBoolVar(f"select_power_pole__{pose_idx}")
            self.pole_vars[int(pose_idx)] = var
            self.candidate_pole_indices.append(int(pose_idx))
            for cell in occupied:
                cell_to_candidates.setdefault(cell, []).append(int(pose_idx))

        # 2. Pole-pole non-overlap by cell.
        for cell, pose_indices in cell_to_candidates.items():
            if len(pose_indices) > 1:
                self.model.Add(
                    sum(self.pole_vars[i] for i in pose_indices) <= 1
                )

        # 3. Coverage: every powered facility instance gets at least one
        # covering selected pole — using the master-precomputed coverer table.
        candidate_set = set(self.candidate_pole_indices)
        for instance_id, tpl, pose_idx in self._powered_instances():
            full_coverers = list(
                self._power_coverers_by_template_pose.get(tpl, {}).get(pose_idx, [])
            )
            available = [p for p in full_coverers if p in candidate_set]
            self.coverers_by_instance[instance_id] = available
            if not available:
                self.uncovered_instance_ids.append(instance_id)
                # Mark model infeasible immediately for clarity.
                self.model.Add(0 >= 1)
            else:
                self.model.Add(
                    sum(self.pole_vars[i] for i in available) >= 1
                )

    def solve(self, time_limit_seconds: float = 10.0) -> PowerPlacementResult:
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(time_limit_seconds)
        status = solver.Solve(self.model)
        stats = {
            "candidate_pole_count": len(self.candidate_pole_indices),
            "powered_instance_count": len(self.coverers_by_instance),
            "uncovered_instance_count": len(self.uncovered_instance_ids),
            "ghost_cell_count": len(self.ghost_cells),
        }
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            selected = tuple(
                sorted(
                    int(i)
                    for i, var in self.pole_vars.items()
                    if solver.Value(var) == 1
                )
            )
            stats["selected_pole_count"] = len(selected)
            return PowerPlacementResult(
                status="FEASIBLE",
                selected_pose_indices=selected,
                stats=stats,
            )
        if status == cp_model.INFEASIBLE:
            uncovered = tuple(self.uncovered_instance_ids) or tuple(
                instance_id
                for instance_id, coverers in self.coverers_by_instance.items()
                if not coverers
            )
            return PowerPlacementResult(
                status="INFEASIBLE",
                uncovered_instance_ids=uncovered,
                stats=stats,
            )
        return PowerPlacementResult(status="TIMEOUT", stats=stats)


def inject_power_poles_into_solution(
    solution: Mapping[str, Mapping[str, Any]],
    *,
    selected_pose_indices: Sequence[int],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    solve_mode: str = "certified_exact",
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {str(k): dict(v) for k, v in solution.items()}
    pole_pool = facility_pools["power_pole"]
    for pose_idx in sorted(int(i) for i in selected_pose_indices):
        pose = pole_pool[pose_idx]
        synthetic_id = f"pose_optional::power_pole::{pose['pose_id']}"
        out[synthetic_id] = {
            "instance_id": synthetic_id,
            "facility_type": "power_pole",
            "operation_type": "power_supply",
            "pose_idx": int(pose_idx),
            "pose_id": pose["pose_id"],
            "anchor": dict(pose["anchor"]),
            "is_mandatory": False,
            "bound_type": "exact_pose_optional",
            "solve_mode": solve_mode,
        }
    return out
