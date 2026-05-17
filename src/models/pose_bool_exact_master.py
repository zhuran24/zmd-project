"""Pose-bool exact master delegate — parallel to CoordinateExactMasterDelegate.

Implements the same `MasterPlacementModel` delegate interface
(build/extract_solution/add_benders_cut/apply_solution_hint/...) but uses
pose-bool variables (x_{group_id, pose_idx} BoolVar + AddAtMostOne cell
exclusivity + power coverage `x_{g,p} <= sum y_{coverer_pole_pose}`) instead
of coordinate-based (x, y, mode IntVar + AddNoOverlap2D + element-witness
power coverage).

Phase 0 prototype verdict (2026-05-17, docs/research/b1_pose_bool_phase0_20260517/):
  27×15 anchor (22,28) single-anchor master.solve 52.8s OPTIMAL
  vs CoordinateExactMasterDelegate 30 min UNKNOWN — ~34x speedup.

Activated via env `EXACT_USE_POSE_BOOL_MASTER=1`. Production uses CoordinateExact
by default (env off) to preserve current behavior; new env opts into the new
delegate.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from ortools.sat.python import cp_model


class PoseBoolExactMasterDelegate:
    master_representation = "pose_bool_exact_v1"

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.model = owner.model
        self.grid_w = int(owner.grid_w)
        self.grid_h = int(owner.grid_h)

        self.mandatory_signature_count_vars: Dict[str, Dict[str, Any]] = {}
        self.required_optional_signature_count_vars: Dict[str, Dict[str, Any]] = {}
        self.residual_optional_signature_count_vars: Dict[str, Dict[str, Any]] = {}
        self.power_pole_family_count_vars: Dict[str, Any] = {}
        self.required_optional_slots: Dict[str, List[Any]] = {}
        self.residual_optional_slots: Dict[str, List[Any]] = {}

        self.x_vars: Dict[Tuple[str, int], cp_model.IntVar] = {}
        self.pole_vars: Dict[int, cp_model.IntVar] = {}
        self.ro_vars: Dict[Tuple[str, int], cp_model.IntVar] = {}
        self._group_id_by_instance: Dict[str, str] = {}
        self._instance_ids_by_group: Dict[str, List[str]] = {}
        self._mandatory_template_by_group: Dict[str, str] = {}
        self._mandatory_operation_by_group: Dict[str, str] = {}
        self._ro_demand: Dict[str, int] = {}
        self._ro_templates: List[str] = []
        self._chosen_assignment: Dict[str, int] = {}
        self._chosen_pole_indices: List[int] = []
        self._chosen_ro_pose: Dict[str, List[int]] = {}

    def _forbidden_cells(self) -> Set[Tuple[int, int]]:
        if not self.owner.ghost_rect:
            return set()
        gw, gh = self.owner.ghost_rect
        anchor_filter = self.owner.ghost_anchor_filter
        if anchor_filter:
            cells: Set[Tuple[int, int]] = set()
            for ax, ay in anchor_filter:
                for dx in range(int(gw)):
                    for dy in range(int(gh)):
                        cells.add((int(ax) + dx, int(ay) + dy))
            return cells
        return set()

    def _pose_cells(self, tpl: str, pose_idx: int) -> List[Tuple[int, int]]:
        pose = self.owner.facility_pools[tpl][int(pose_idx)]
        return [(int(c[0]), int(c[1])) for c in pose.get("occupied_cells", [])]

    def _feasible_poses(
        self, tpl: str, forbidden: Set[Tuple[int, int]]
    ) -> List[Tuple[int, List[Tuple[int, int]]]]:
        feas: List[Tuple[int, List[Tuple[int, int]]]] = []
        pool = self.owner.facility_pools.get(tpl, [])
        for pose_idx, pose in enumerate(pool):
            cells = [(int(c[0]), int(c[1])) for c in pose.get("occupied_cells", [])]
            if not cells:
                continue
            if any(not (0 <= c[0] < self.grid_w and 0 <= c[1] < self.grid_h) for c in cells):
                continue
            if any(c in forbidden for c in cells):
                continue
            feas.append((pose_idx, cells))
        return feas

    def build(self) -> None:
        # ghost_rect=None 出现在 build_exact_core 的 "build core proto" 阶段,
        # pose-bool delegate 不参与 proto-sharing (走 direct instantiation),
        # 所以这种 case graceful no-op, 等真 build 在 ghost_rect 设上后再来.
        if self.owner.ghost_rect is None:
            self.owner.build_stats["master_representation"] = self.master_representation
            self.owner.build_stats["pose_bool_master"] = {
                "no_op_reason": "ghost_rect_none_at_build_exact_core_stage",
            }
            return
        forbidden = self._forbidden_cells()

        cell_poses: Dict[Tuple[int, int], List[cp_model.IntVar]] = {}
        powered_group_keys: List[Tuple[str, str]] = []  # (group_id, tpl) for mandatory
        powered_ro_templates: List[str] = []
        ro_templates_seen: List[str] = []

        # Mandatory groups
        for group in self.owner._mandatory_groups:
            gid = str(group["group_id"])
            tpl = str(group["facility_type"])
            instance_ids = [str(x) for x in list(group.get("instance_ids", []))]
            demand = int(group.get("count", len(instance_ids)))
            if demand <= 0:
                continue
            self._mandatory_template_by_group[gid] = tpl
            self._mandatory_operation_by_group[gid] = str(group.get("operation_type", ""))
            self._instance_ids_by_group[gid] = instance_ids
            for iid in instance_ids:
                self._group_id_by_instance[iid] = gid

            feas = self._feasible_poses(tpl, forbidden)
            if len(feas) < demand:
                self.model.Add(0 >= 1)  # immediate infeasible
                return

            is_powered = (tpl in self.owner._powered_templates and tpl != "power_pole")
            if is_powered:
                powered_group_keys.append((gid, tpl))

            group_vars: List[cp_model.IntVar] = []
            for pose_idx, cells in feas:
                v = self.model.NewBoolVar(f"pbx__{gid}__{int(pose_idx)}")
                self.x_vars[(gid, int(pose_idx))] = v
                group_vars.append(v)
                for c in cells:
                    cell_poses.setdefault(c, []).append(v)
            self.model.Add(sum(group_vars) == demand)

        # Required optional (e.g. protocol_storage_box) — fixed demand
        ro_counts: Mapping[str, Any] = getattr(
            self.owner, "_exact_required_pose_optional_counts", {}
        ) or {}
        for tpl, demand_raw in dict(ro_counts).items():
            try:
                demand = int(demand_raw)
            except (TypeError, ValueError):
                continue
            if demand <= 0:
                continue
            if tpl == "power_pole":
                continue  # power_pole 走 residual_optional path
            ro_templates_seen.append(str(tpl))
            self._ro_demand[str(tpl)] = demand
            feas = self._feasible_poses(str(tpl), forbidden)
            if len(feas) < demand:
                self.model.Add(0 >= 1)
                return
            is_powered = (tpl in self.owner._powered_templates and tpl != "power_pole")
            if is_powered:
                powered_ro_templates.append(str(tpl))
            ro_vars_for_tpl: List[cp_model.IntVar] = []
            for pose_idx, cells in feas:
                v = self.model.NewBoolVar(f"pbro__{tpl}__{int(pose_idx)}")
                self.ro_vars[(str(tpl), int(pose_idx))] = v
                ro_vars_for_tpl.append(v)
                for c in cells:
                    cell_poses.setdefault(c, []).append(v)
            self.model.Add(sum(ro_vars_for_tpl) == demand)
            self.required_optional_slots[str(tpl)] = list(range(demand))  # placeholder

        self._ro_templates = ro_templates_seen

        # Residual optional power_pole — no demand fix, ≥ 0 ≤ upper bound
        pole_pool = self.owner.facility_pools.get("power_pole", [])
        for pose_idx, pose in enumerate(pole_pool):
            occ = pose.get("occupied_cells", [])
            cells = [(int(c[0]), int(c[1])) for c in occ]
            if not cells:
                continue
            if any(not (0 <= c[0] < self.grid_w and 0 <= c[1] < self.grid_h) for c in cells):
                continue
            if any(c in forbidden for c in cells):
                continue
            v = self.model.NewBoolVar(f"pbpole__{int(pose_idx)}")
            self.pole_vars[int(pose_idx)] = v
            for c in cells:
                cell_poses.setdefault(c, []).append(v)
        self.residual_optional_slots["power_pole"] = list(range(len(self.pole_vars)))

        # Cell exclusivity
        for vars_in_cell in cell_poses.values():
            if len(vars_in_cell) > 1:
                self.model.AddAtMostOne(vars_in_cell)

        # Power coverage: x_{g,p} <= sum y_{coverer_pole}
        coverers_table = self.owner._power_coverers_by_template_pose
        # mandatory powered groups
        for gid, tpl in powered_group_keys:
            tpl_cov = coverers_table.get(tpl, {})
            for (gid_in_key, pose_idx), x_var in self.x_vars.items():
                if gid_in_key != gid:
                    continue
                coverer_pole_indices = tpl_cov.get(int(pose_idx), [])
                cov_vars = [self.pole_vars[int(p)] for p in coverer_pole_indices if int(p) in self.pole_vars]
                if cov_vars:
                    self.model.Add(x_var <= sum(cov_vars))
                else:
                    self.model.Add(x_var == 0)
        # required_optional powered tpls
        for tpl in powered_ro_templates:
            tpl_cov = coverers_table.get(tpl, {})
            for (tpl_in_key, pose_idx), v in self.ro_vars.items():
                if tpl_in_key != tpl:
                    continue
                coverer_pole_indices = tpl_cov.get(int(pose_idx), [])
                cov_vars = [self.pole_vars[int(p)] for p in coverer_pole_indices if int(p) in self.pole_vars]
                if cov_vars:
                    self.model.Add(v <= sum(cov_vars))
                else:
                    self.model.Add(v == 0)

        self.owner.build_stats["master_representation"] = self.master_representation
        self.owner.build_stats["pose_bool_master"] = {
            "x_vars": len(self.x_vars),
            "ro_vars": len(self.ro_vars),
            "pole_vars": len(self.pole_vars),
            "cell_exclusivity_cells": sum(1 for v in cell_poses.values() if len(v) > 1),
            "powered_mandatory_groups": len(powered_group_keys),
            "powered_ro_templates": len(powered_ro_templates),
        }

    def extract_solution(self) -> Dict[str, Any]:
        solver = self.owner._solver
        if solver is None:
            return {}
        solution: Dict[str, Any] = {}
        # Mandatory: collect selected pose_idx per group; pair with instance_ids
        chosen_by_group: Dict[str, List[int]] = {}
        for (gid, pose_idx), v in self.x_vars.items():
            if solver.Value(v) == 1:
                chosen_by_group.setdefault(gid, []).append(int(pose_idx))
        for gid, pose_indices in chosen_by_group.items():
            tpl = self._mandatory_template_by_group[gid]
            op = self._mandatory_operation_by_group[gid]
            instance_ids = sorted(self._instance_ids_by_group.get(gid, []))
            for inst_id, pose_idx in zip(instance_ids, sorted(pose_indices)):
                pose = self.owner.facility_pools[tpl][int(pose_idx)]
                solution[inst_id] = {
                    "instance_id": inst_id,
                    "facility_type": tpl,
                    "operation_type": op,
                    "pose_idx": int(pose_idx),
                    "pose_id": pose["pose_id"],
                    "anchor": dict(pose["anchor"]),
                    "is_mandatory": True,
                    "bound_type": "exact",
                    "solve_mode": self.owner.solve_mode,
                }
        # Required optional
        ro_by_tpl: Dict[str, List[int]] = {}
        for (tpl, pose_idx), v in self.ro_vars.items():
            if solver.Value(v) == 1:
                ro_by_tpl.setdefault(tpl, []).append(int(pose_idx))
        for tpl, indices in ro_by_tpl.items():
            for pose_idx in indices:
                pose = self.owner.facility_pools[tpl][int(pose_idx)]
                synthetic_id = f"pose_optional::{tpl}::{pose['pose_id']}"
                solution[synthetic_id] = {
                    "instance_id": synthetic_id,
                    "facility_type": tpl,
                    "operation_type": "wireless_sink" if tpl == "protocol_storage_box" else "",
                    "pose_idx": int(pose_idx),
                    "pose_id": pose["pose_id"],
                    "anchor": dict(pose["anchor"]),
                    "is_mandatory": False,
                    "bound_type": "exact_pose_optional",
                    "solve_mode": self.owner.solve_mode,
                }
        # Poles
        for pose_idx, v in self.pole_vars.items():
            if solver.Value(v) == 1:
                pose = self.owner.facility_pools["power_pole"][int(pose_idx)]
                synthetic_id = f"pose_optional::power_pole::{pose['pose_id']}"
                solution[synthetic_id] = {
                    "instance_id": synthetic_id,
                    "facility_type": "power_pole",
                    "operation_type": "power_supply",
                    "pose_idx": int(pose_idx),
                    "pose_id": pose["pose_id"],
                    "anchor": dict(pose["anchor"]),
                    "is_mandatory": False,
                    "bound_type": "exact_pose_optional",
                    "solve_mode": self.owner.solve_mode,
                }
        return solution

    def add_benders_cut(
        self,
        conflict_set: Mapping[str, int],
        *,
        condition_lits: Sequence[cp_model.IntVar] = (),
    ) -> bool:
        # nogood: sum(present(pose) for pose in conflict_set) <= N - 1
        present_lits: List[cp_model.IntVar] = []
        for inst_id, pose_idx in dict(conflict_set).items():
            pose_idx_int = int(pose_idx)
            key = str(inst_id)
            var: Optional[cp_model.IntVar] = None
            if key in self._group_id_by_instance:
                gid = self._group_id_by_instance[key]
                var = self.x_vars.get((gid, pose_idx_int))
            elif key.startswith("pose_optional::power_pole::"):
                var = self.pole_vars.get(pose_idx_int)
            elif key.startswith("pose_optional::"):
                # ro: extract tpl
                _, tpl, *_rest = key.split("::")
                var = self.ro_vars.get((tpl, pose_idx_int))
            if var is not None:
                present_lits.append(var)
        if not present_lits:
            return False
        cond = [lit for lit in condition_lits if lit is not None]
        constraint = self.model.Add(sum(present_lits) <= len(present_lits) - 1)
        if cond:
            constraint.OnlyEnforceIf(cond)
        cut_index = int(self.owner.build_stats.get("pose_bool_benders_cut_count", 0))
        self.owner.build_stats["pose_bool_benders_cut_count"] = cut_index + 1
        self.owner._last_solution = None
        return True

    def apply_solution_hint(
        self,
        solution_hint: Mapping[str, int],
        *,
        ghost_anchor_hint_idx: Optional[int] = None,
        hint_inactive_residual_optionals: bool = True,
    ) -> Dict[str, Any]:
        # Simple AddHint for matching pose-bool var. ghost_anchor_hint_idx 不适用 (single-anchor mode).
        # hint_inactive_residual_optionals 在 pose-bool form 下不强制 zero hint poles (CP-SAT 自找).
        hinted = 0
        for inst_id, pose_idx in dict(solution_hint or {}).items():
            pose_idx_int = int(pose_idx)
            key = str(inst_id)
            var: Optional[cp_model.IntVar] = None
            if key in self._group_id_by_instance:
                gid = self._group_id_by_instance[key]
                var = self.x_vars.get((gid, pose_idx_int))
            elif key.startswith("pose_optional::power_pole::"):
                var = self.pole_vars.get(pose_idx_int)
            elif key.startswith("pose_optional::"):
                _, tpl, *_rest = key.split("::")
                var = self.ro_vars.get((tpl, pose_idx_int))
            if var is not None:
                self.model.AddHint(var, 1)
                hinted += 1
        return {
            "hinted_literals": int(hinted),
            "ghost_anchor_hint_applied": False,
            "ghost_anchor_hint_idx": None,
            "residual_optional_zero_hinting_enabled": False,
            "residual_optional_zero_hints": 0,
        }

    def extract_master_hints(self, solver: Any) -> Dict[str, int]:
        # Persistence not supported in pose-bool delegate (Phase 2 scope).
        return {}

    def apply_master_hints(self, hints: Mapping[str, int]) -> int:
        return 0

    def export_core_binding(self) -> Dict[str, Any]:
        # PoseBool delegate 不参与 proto sharing (build_exact_core / from_exact_core),
        # 返回空 binding 让 build_exact_core 不 crash.
        return {}
