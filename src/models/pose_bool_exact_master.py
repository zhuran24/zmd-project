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

import os
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from ortools.sat.python import cp_model

from src.preprocess.operation_profiles import get_operation_port_profile


_DIR_DELTA: Dict[str, Tuple[int, int]] = {
    "N": (0, 1),
    "S": (0, -1),
    "E": (1, 0),
    "W": (-1, 0),
}


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
        # B1 Phase 5: cache for routing front_blocked cell-level cut.
        # Built lazily on first cut request (avoid build() overhead for
        # users that never need routing cuts).
        self._poses_by_cell: Dict[Tuple[int, int], List[cp_model.IntVar]] = {}
        self._poses_by_port_at_cell_dir: Dict[
            Tuple[int, int, str], List[cp_model.IntVar]
        ] = {}
        self._routing_visible_poses_by_port_at_cell_dir: Dict[
            Tuple[int, int, str], List[cp_model.IntVar]
        ] = {}
        self._port_lookup_built = False
        # Phase 6.2 v2: grid-level front_clear BoolVars 替代 per-port port_active.
        # 数量 ~19K (70x70x4 dir) vs ~2.3M per-port → 100x 小.
        # 语义: front_clear[(cell, dir)] = 1 iff (cell + dir_delta) 是 grid 内
        # 且没 facility 占. 不强制 = 1, 让 pose-level constraint enforce 至少
        # demand 个 cleared.
        self._front_clear: Dict[Tuple[int, int, str], cp_model.IntVar] = {}
        # Phase 6 路线 2: lazy demand cut 用 global-coord cache (pose data
        # occupied_cells / port_cells 是 GLOBAL 坐标 — 不加 anchor offset, 区别
        # 于 _build_port_lookup_cache 历史 phantom-offset bug).
        # 一次 build, 路径 1 (prebuild fc) 跟路径 2 (lazy cut) 共用.
        self._poses_by_cell_global: Dict[Tuple[int, int], List[cp_model.IntVar]] = {}
        self._poses_by_port_cell_dir_global: Dict[
            Tuple[int, int, str], List[cp_model.IntVar]
        ] = {}
        self._global_cache_built = False

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

    def _routing_free_sink_commodities(self) -> Set[str]:
        gen_io = getattr(self.owner, "generic_io_requirements", None) or {}
        return {
            str(commodity)
            for commodity, required in dict(
                gen_io.get("required_generic_inputs", {}) or {}
            ).items()
            if int(required) > 0
        }

    def _required_generic_output_slot_total(self) -> int:
        gen_io = getattr(self.owner, "generic_io_requirements", None) or {}
        return sum(
            int(required)
            for required in dict(gen_io.get("required_generic_outputs", {}) or {}).values()
        )

    def _required_generic_output_commodities(self) -> Set[str]:
        gen_io = getattr(self.owner, "generic_io_requirements", None) or {}
        return {
            str(commodity)
            for commodity, required in dict(
                gen_io.get("required_generic_outputs", {}) or {}
            ).items()
            if int(required) > 0
        }

    def _required_generic_outputs_are_all_routing_visible(self) -> bool:
        try:
            return not (
                self._required_generic_output_commodities()
                & self._routing_free_sink_commodities()
            )
        except Exception:
            return False

    def _mandatory_generic_output_capacity_total(self) -> Optional[int]:
        """Return the mandatory generic-output slot capacity if it is knowable.

        Generic-output slots are binding capacity: ``PortBindingModel`` may assign
        ``__unused__`` to any such physical output slot unless the global generic
        output demand saturates all mandatory generic-output slots.  Pose-level
        cell-pattern/front-clear cuts have no binding slot identity, so they may
        treat generic-output cells as necessarily active only when that global
        saturation proof is available from the master group's operation snapshot.
        """
        total = 0
        saw_generic_output_provider = False

        mandatory_groups = list(getattr(self.owner, "_mandatory_groups", []) or [])
        if mandatory_groups:
            for group in mandatory_groups:
                try:
                    operation_type = str(group.get("operation_type", ""))
                    profile = get_operation_port_profile(operation_type)
                    slots = int(profile.generic_output_slots)
                    count = int(group.get("count", len(group.get("instance_ids", []) or [])))
                except Exception:
                    return None
                if slots <= 0:
                    continue
                if count <= 0:
                    # A generic-output-providing group with an unknowable instance
                    # count makes the capacity total unknowable: an undercounted
                    # capacity could fake saturation and over-cut.
                    return None
                saw_generic_output_provider = True
                total += slots * count
            return total if saw_generic_output_provider else 0

        if not self._mandatory_operation_by_group:
            return None
        for group_id, operation_type in self._mandatory_operation_by_group.items():
            try:
                profile = get_operation_port_profile(str(operation_type))
                slots = int(profile.generic_output_slots)
            except Exception:
                return None
            if slots <= 0:
                continue
            instance_ids = self._instance_ids_by_group.get(str(group_id), [])
            if not instance_ids:
                # Same fail-closed rule as above: without the group's instance
                # list the capacity cannot be proven, so saturation must not be
                # claimed (assuming 1 instance undercounts multi-instance groups).
                return None
            saw_generic_output_provider = True
            total += slots * len(instance_ids)
        return total if saw_generic_output_provider else 0

    def _generic_output_slots_are_globally_saturated(self) -> bool:
        try:
            required = int(self._required_generic_output_slot_total())
            capacity = self._mandatory_generic_output_capacity_total()
        except Exception:
            return False
        return capacity is not None and capacity > 0 and required == int(capacity)

    def _profile_port_demands(self, operation_type: str) -> Tuple[int, int, int, int]:
        try:
            profile = get_operation_port_profile(operation_type)
        except KeyError:
            return 0, 0, 0, 0
        routing_free_outputs = self._routing_free_sink_commodities()
        concrete_input_demand = sum(int(v) for v in profile.input_slots.values())
        total_input = concrete_input_demand + int(profile.generic_input_slots)
        total_output = sum(int(v) for v in profile.output_slots.values()) + int(
            profile.generic_output_slots
        )
        generic_output_visible = (
            int(profile.generic_output_slots)
            if (
                self._generic_output_slots_are_globally_saturated()
                and self._required_generic_outputs_are_all_routing_visible()
            )
            else 0
        )
        visible_output = sum(
            int(count)
            for commodity, count in profile.output_slots.items()
            if str(commodity) not in routing_free_outputs
        ) + generic_output_visible
        # Generic-input slots are virtual wireless capacity (no physical front);
        # all concrete input requirements remain route-visible.  The validator
        # fails closed if a future generic-input target is also a recipe input.
        visible_input = concrete_input_demand
        return int(visible_input), int(visible_output), int(total_input), int(total_output)

    def _routing_visible_profile_demands(self, operation_type: str) -> Tuple[int, int]:
        visible_input, visible_output, _total_input, _total_output = self._profile_port_demands(
            operation_type
        )
        return int(visible_input), int(visible_output)

    def _mandatory_port_side_is_routing_visible(
        self, group_id: str, side_key: str
    ) -> bool:
        operation_type = self._mandatory_operation_by_group.get(str(group_id), "")
        input_demand, output_demand, _total_input, total_output = self._profile_port_demands(
            operation_type
        )
        if side_key == "input_port_cells":
            return input_demand > 0
        if side_key == "output_port_cells":
            # The hard/cache path indexes raw pose ports without binding-slot
            # identity.  It is only sound when every output-side slot is
            # routing-visible.  Mixed visible/routing-free output operations are
            # handled by the weaker demand-count cuts instead.
            return output_demand > 0 and output_demand == total_output
        return False

    def _mandatory_port_side_is_cell_pattern_exact(
        self, group_id: str, side_key: str, port_count: int
    ) -> bool:
        """Return True only when each physical port on this side is necessarily
        routing-visible whenever the pose is selected.

        Cell-pattern cuts are master-level cuts over pose variables.  They do not
        know which binding alternative will be chosen in a future subproblem, so a
        raw ``has a port at cell`` index is exact only for sides where the visible
        demand consumes every physical port on that side.  Otherwise the blocked
        physical port may be an inactive binding slot and banning the pose+blocker
        pattern would be an over-cut.
        """
        if port_count <= 0:
            return False
        try:
            (
                input_demand,
                output_demand,
                _total_input,
                total_output,
            ) = self._profile_port_demands(
                self._mandatory_operation_by_group.get(str(group_id), "")
            )
        except Exception:
            return False
        if side_key == "input_port_cells":
            # Concrete input slots are routing-visible.  Generic-input capacity is
            # virtual, so the per-cell pattern is exact only when concrete demand
            # covers every physical input port.
            return int(input_demand) >= int(port_count)
        if side_key == "output_port_cells":
            # Output sides that mix visible and routing-free sinks are handled by
            # demand-count cuts; raw per-cell output cuts are exact only when all
            # output demand is routing-visible and every physical output port must
            # be active.
            return (
                int(output_demand) > 0
                and int(output_demand) == int(total_output)
                and int(output_demand) >= int(port_count)
            )
        return False

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

        # B1 Phase 6.2 v2: grid-level front_clear + pose-level cleared-count
        # 约束替代 Phase 5b "所有 port front 必空" over-approximation.
        # 形式: front_clear[(c, d)] = 1 iff cell at (c + dir_delta) 在 grid 且
        # 没 facility 占; pose 选则 pose 的 port_cells 至少 demand 个 front 是
        # clear (binding 在 cleared 子集选 active port — sound).
        # env-gated EXACT_USE_PORT_ACTIVE (legacy 名称, semantic 已变).
        port_active_enabled = os.environ.get(
            "EXACT_USE_PORT_ACTIVE", ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        front_clear_count = 0
        pose_clearance_count = 0
        if port_active_enabled:
            # Step 1: build global cache (路径 1 + 路径 2 共用).
            self._build_global_pose_cache()

            # Step 2: build front_clear vars per (port_cell, dir).
            for (px, py, direction) in self._poses_by_port_cell_dir_global.keys():
                dx, dy = _DIR_DELTA.get(str(direction), (0, 0))
                fc_key = (int(px), int(py), str(direction))
                if fc_key in self._front_clear:
                    continue
                fx, fy = int(px) + dx, int(py) + dy
                if not (0 <= fx < self.grid_w and 0 <= fy < self.grid_h):
                    # front out of grid: 不可 clear, 直接 set var=0 (ban this port)
                    fc = self.model.NewBoolVar(f"fc__{px}_{py}_{direction}")
                    self.model.Add(fc == 0)
                    self._front_clear[fc_key] = fc
                    front_clear_count += 1
                    continue
                front_poses = self._poses_by_cell_global.get((fx, fy), [])
                fc = self.model.NewBoolVar(f"fc__{px}_{py}_{direction}")
                self._front_clear[fc_key] = fc
                front_clear_count += 1
                # 联动: front_clear + sum(poses 占 front) <= 1
                # (cell exclusivity 保 sum<=1; front_clear=1 → sum=0 → 无 facility)
                if front_poses:
                    self.model.Add(fc + sum(front_poses) <= 1)

            # Step 3: pose-level cleared-count 约束
            # mandatory: sum(front_clear at port_cells) >= demand × x_var
            for (gid_key, pose_idx), x_var in self.x_vars.items():
                op = self._mandatory_operation_by_group.get(gid_key, "")
                tpl_m = self._mandatory_template_by_group.get(gid_key, "")
                in_demand, out_demand = self._routing_visible_profile_demands(op)
                if in_demand <= 0 and out_demand <= 0:
                    continue
                pose = self.owner.facility_pools[tpl_m][int(pose_idx)]
                if in_demand > 0:
                    input_cells = pose.get("input_port_cells", []) or []
                    fc_terms_in: List[cp_model.IntVar] = []
                    for port in input_cells:
                        key_tup = (int(port.get("x", 0)),
                                   int(port.get("y", 0)),
                                   str(port.get("dir", "")))
                        fc = self._front_clear.get(key_tup)
                        if fc is not None:
                            fc_terms_in.append(fc)
                    if fc_terms_in:
                        self.model.Add(sum(fc_terms_in) >= in_demand * x_var)
                        pose_clearance_count += 1
                if out_demand > 0:
                    output_cells = pose.get("output_port_cells", []) or []
                    fc_terms_out: List[cp_model.IntVar] = []
                    for port in output_cells:
                        key_tup = (int(port.get("x", 0)),
                                   int(port.get("y", 0)),
                                   str(port.get("dir", "")))
                        fc = self._front_clear.get(key_tup)
                        if fc is not None:
                            fc_terms_out.append(fc)
                    if fc_terms_out:
                        self.model.Add(sum(fc_terms_out) >= out_demand * x_var)
                        pose_clearance_count += 1

            # Step 4: ro storage box (wireless_sink) cross-pose total cleared >= demand.
            gen_io = getattr(self.owner, "generic_io_requirements", None) or {}
            req_in = dict(gen_io.get("required_generic_inputs", {}) or {})
            storage_total_in = sum(int(v) for v in req_in.values())
            if storage_total_in > 0:
                effective_box_terms: List[cp_model.IntVar] = []
                for (tpl_key, pose_idx), ro_var in self.ro_vars.items():
                    if str(tpl_key) != "protocol_storage_box":
                        continue
                    pose = self.owner.facility_pools[str(tpl_key)][int(pose_idx)]
                    input_cells = pose.get("input_port_cells", []) or []
                    fc_terms_box: List[cp_model.IntVar] = []
                    for port in input_cells:
                        key_tup = (int(port.get("x", 0)),
                                   int(port.get("y", 0)),
                                   str(port.get("dir", "")))
                        fc = self._front_clear.get(key_tup)
                        if fc is not None:
                            fc_terms_box.append(fc)
                    if not fc_terms_box:
                        continue
                    max_count = len(fc_terms_box)
                    cleared_box = self.model.NewIntVar(
                        0, max_count, f"cb__{tpl_key}__{int(pose_idx)}"
                    )
                    self.model.Add(cleared_box == sum(fc_terms_box))
                    effective = self.model.NewIntVar(
                        0, max_count, f"eb__{tpl_key}__{int(pose_idx)}"
                    )
                    self.model.Add(effective <= cleared_box)
                    self.model.Add(effective <= ro_var * max_count)
                    effective_box_terms.append(effective)
                if effective_box_terms:
                    self.model.Add(sum(effective_box_terms) >= storage_total_in)

        # B1 Phase 5b: add cell-level port_clearance hard constraint.
        # 跟 routing precheck 等价 (sound, 不是 over-approximation): port 是
        # facility I/O 接口, belt 从 port_cell + dir 出. 如果 front_cell 被任何
        # facility 占, belt 出口被堵, port 不能 routing — 这是物理限制.
        # PROJECT_LOCK 禁的 coordinate path `_add_port_clearance_constraints` 是
        # over-approximation 设计; pose-bool delegate 的 cell-level 形式跟
        # routing precheck 语义等价.
        # env-gated via `EXACT_B1_PORT_CLEARANCE_HARD`.
        port_clearance_enabled = os.environ.get(
            "EXACT_B1_PORT_CLEARANCE_HARD", ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        port_clearance_added = 0
        if port_clearance_enabled:
            self._build_port_lookup_cache()
            # 对每 (port_cell, dir) 已知有 pose 配置, 加 "如果某 pose 在 cell 有
            # port 朝 dir 被选 → front_cell 必空".
            for (px, py, direction), port_poses in self._routing_visible_poses_by_port_at_cell_dir.items():
                if not port_poses:
                    continue
                dx, dy = _DIR_DELTA.get(str(direction), (0, 0))
                front = (int(px) + dx, int(py) + dy)
                if not (0 <= front[0] < self.grid_w and 0 <= front[1] < self.grid_h):
                    # front 出 grid: port 永远不通, ban pose
                    for v in port_poses:
                        self.model.Add(v == 0)
                    port_clearance_added += 1
                    continue
                front_poses = self._poses_by_cell.get(front, [])
                if not front_poses:
                    continue
                # Implication 形式: 用 channeled OR + 1 main constraint, 避免
                # K1 × (N front) propagator 爆炸.
                # any_port = OR(port_poses). port_poses 任一 true → any_port=1.
                # any_port + sum(front_poses) <= 1 → 主约束.
                any_port = self.model.NewBoolVar(f"any_port_{px}_{py}_{direction}")
                # any_port >= p_i (channel)
                for v_p in port_poses:
                    self.model.Add(any_port >= v_p)
                # any_port <= sum(port_poses) (channel upper)
                self.model.Add(any_port <= sum(port_poses))
                # 主约束
                self.model.Add(any_port + sum(front_poses) <= 1)
                port_clearance_added += 1

        # SAC-Hull: cache pose metadata + cell_poses for both static (Phase 1)
        # and dynamic (Phase 2) separator hull constraint generation.
        # Always built (cheap), only used when env on.
        from src.models.separator_capacity_hull import PoseVarMetadata
        self._sac_pose_metadata: List[Any] = []
        for (gid, pose_idx), var in self.x_vars.items():
            op = self._mandatory_operation_by_group.get(gid, "")
            tpl = self._mandatory_template_by_group.get(gid, "")
            pool = self.owner.facility_pools.get(tpl, [])
            if 0 <= pose_idx < len(pool):
                self._sac_pose_metadata.append(PoseVarMetadata(var=var, operation_type=op, pose=pool[pose_idx]))
        self._sac_cell_poses: Dict[Tuple[int, int], List[Any]] = {
            k: list(v) for k, v in cell_poses.items()
        }

        # SAC-Hull Phase 1: env-gated static separator capacity hull constraints
        sac_hull_stats: Dict[str, Any] = {"enabled": False}
        if os.environ.get("EXACT_B1_SEPARATOR_HULL", "").strip().lower() in {"1", "true", "yes", "on"}:
            from src.models.separator_capacity_hull import (
                build_static_separator_library,
                add_separator_capacity_hull_constraints,
            )
            try:
                limit = int(os.environ.get("EXACT_B1_SEPARATOR_HULL_STATIC_LIMIT", "64"))
            except ValueError:
                limit = 64
            include_axis = os.environ.get("EXACT_B1_SEPARATOR_HULL_INCLUDE_AXIS", "1").strip().lower() in {"1", "true", "yes", "on"}
            include_moat = os.environ.get("EXACT_B1_SEPARATOR_HULL_INCLUDE_GHOST_MOAT", "1").strip().lower() in {"1", "true", "yes", "on"}
            # ghost_rect format: tuple (w, h); ghost_anchor 从 forbidden cells 推回 (min x, min y)
            ghost_anchor: Optional[Tuple[int, int]] = None
            ghost_size: Optional[Tuple[int, int]] = None
            if self.owner.ghost_rect is not None and forbidden:
                ghost_size = (int(self.owner.ghost_rect[0]), int(self.owner.ghost_rect[1]))
                xs = [c[0] for c in forbidden]
                ys = [c[1] for c in forbidden]
                ghost_anchor = (min(xs), min(ys))
            seps = build_static_separator_library(
                grid_w=self.grid_w, grid_h=self.grid_h,
                ghost_anchor=ghost_anchor, ghost_size=ghost_size,
                include_axis=include_axis, include_ghost_moat=include_moat,
                limit=limit,
            )
            sac_hull_stats = add_separator_capacity_hull_constraints(
                model=self.model,
                separators=seps,
                pose_var_metadata=self._sac_pose_metadata,
                cell_poses=self._sac_cell_poses,
                grid_w=self.grid_w, grid_h=self.grid_h,
                routing_free_sink_commodities=self._routing_free_sink_commodities(),
            )
            sac_hull_stats["enabled"] = True
            sac_hull_stats["pose_metadata_count"] = len(self._sac_pose_metadata)

        self.owner.build_stats["master_representation"] = self.master_representation
        self.owner.build_stats["pose_bool_master"] = {
            "x_vars": len(self.x_vars),
            "ro_vars": len(self.ro_vars),
            "pole_vars": len(self.pole_vars),
            "cell_exclusivity_cells": sum(1 for v in cell_poses.values() if len(v) > 1),
            "powered_mandatory_groups": len(powered_group_keys),
            "powered_ro_templates": len(powered_ro_templates),
            "port_clearance_constraints": port_clearance_added,
            "front_clear_vars": front_clear_count,
            "pose_clearance_constraints": pose_clearance_count,
            "port_active_enabled": port_active_enabled,
            "sac_hull": sac_hull_stats,
        }

    def resolve_pose_var_for_instance(
        self,
        instance_id: str,
        pose_idx: int,
    ) -> Optional[cp_model.IntVar]:
        """Unified instance_id → master pose var lookup.

        Handles all three pose-bool var sources: mandatory x_vars (per group),
        protocol_storage_box ro_vars (per template), power_pole pole_vars. Returns
        None if the instance is unknown or its (gid, pose_idx) pair is not in any var
        dict — caller MUST fail-closed on None.
        """
        pose_idx_int = int(pose_idx)
        key = str(instance_id)
        if key in self._group_id_by_instance:
            gid = self._group_id_by_instance[key]
            return self.x_vars.get((gid, pose_idx_int))
        if key.startswith("pose_optional::power_pole::"):
            return self.pole_vars.get(pose_idx_int)
        if key.startswith("pose_optional::"):
            _, tpl, *_rest = key.split("::")
            return self.ro_vars.get((tpl, pose_idx_int))
        return None

    def _resolve_pose_pool_for_instance(
        self,
        instance_id: str,
    ) -> Optional[Tuple[str, str, str, List[Mapping[str, Any]]]]:
        """Return (kind, gid_or_template, operation_type, pose_pool) or None.

        kind is one of {'mandatory', 'ro', 'pole'} so callers can index the right
        var dict afterwards.
        """
        key = str(instance_id)
        if key in self._group_id_by_instance:
            gid = self._group_id_by_instance[key]
            tpl = self._mandatory_template_by_group[gid]
            op = self._mandatory_operation_by_group.get(gid, "")
            return ("mandatory", gid, op, self.owner.facility_pools.get(tpl, []))
        if key.startswith("pose_optional::power_pole::"):
            return ("pole", "power_pole", "", self.owner.facility_pools.get("power_pole", []))
        if key.startswith("pose_optional::"):
            _, tpl, *_rest = key.split("::")
            op = "wireless_sink" if tpl == "protocol_storage_box" else ""
            return ("ro", tpl, op, self.owner.facility_pools.get(tpl, []))
        return None

    def enumerate_pose_vars_with_patch_signature(
        self,
        instance_id: str,
        target_signature: Any,  # PoseLocalSignature
        patch_cells: FrozenSet[Tuple[int, int]],
    ) -> List[cp_model.IntVar]:
        """Return all master pose vars whose patch-local signature equals target.

        Used for signature lifting: a single core PoseAssumption nogood expands to
        a `sum(equivalent_vars)` term covering every interchangeable pose of the
        same owner. Within-instance lifting only (NEVER cross-owner — that would
        require independent symmetry proof).
        """
        from src.models.patch_routing_core import build_local_pose_signature
        resolved = self._resolve_pose_pool_for_instance(instance_id)
        if resolved is None:
            return []
        kind, gid_or_tpl, op, pool = resolved
        tpl: str
        if kind == "mandatory":
            tpl = self._mandatory_template_by_group[gid_or_tpl]
        else:
            tpl = gid_or_tpl
        results: List[cp_model.IntVar] = []
        for idx, pose in enumerate(pool):
            sig = build_local_pose_signature(
                facility_type=tpl, operation_type=op, pose=pose, patch_cells=patch_cells,
            )
            if sig != target_signature:
                continue
            var: Optional[cp_model.IntVar]
            if kind == "mandatory":
                var = self.x_vars.get((gid_or_tpl, idx))
            elif kind == "pole":
                var = self.pole_vars.get(idx)
            else:
                var = self.ro_vars.get((tpl, idx))
            if var is not None:
                results.append(var)
        return results

    def add_patch_routing_core_cut(
        self,
        core_terms: Sequence[Tuple[str, int]],
        patch_cells: FrozenSet[Tuple[int, int]],
        *,
        certificate_metadata: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add `sum_i sig_expr_i <= |core| - 1` where sig_expr_i = sum of all
        master pose vars equivalent to core_term i under patch-local signature.

        Returns metadata describing what was added. fail-closed: if ANY core_term
        cannot resolve to a non-empty equivalent var list, NO cut is added (caller
        sees added=False with reason).
        """
        from src.models.patch_routing_core import build_local_pose_signature
        accumulated_terms: List[List[cp_model.IntVar]] = []
        signature_lift_counts: List[int] = []
        seen_lifted_var_names: Set[str] = set()
        for (inst_id, pose_idx) in core_terms:
            resolved = self._resolve_pose_pool_for_instance(inst_id)
            if resolved is None:
                return {"added": False, "reason": "unknown_instance_kind", "instance_id": str(inst_id)}
            kind, gid_or_tpl, op, pool = resolved
            pi = int(pose_idx)
            if pi < 0 or pi >= len(pool):
                return {"added": False, "reason": "pose_idx_out_of_range", "instance_id": str(inst_id), "pose_idx": pi}
            tpl: str
            if kind == "mandatory":
                tpl = self._mandatory_template_by_group[gid_or_tpl]
            else:
                tpl = gid_or_tpl
            target_sig = build_local_pose_signature(
                facility_type=tpl, operation_type=op, pose=pool[pi], patch_cells=patch_cells,
            )
            equivalent_vars = self.enumerate_pose_vars_with_patch_signature(inst_id, target_sig, patch_cells)
            if not equivalent_vars:
                return {"added": False, "reason": "no_equivalent_vars", "instance_id": str(inst_id), "pose_idx": pi}
            lifted_var_names = {var.Name() for var in equivalent_vars}
            overlap = seen_lifted_var_names & lifted_var_names
            if overlap:
                return {
                    "added": False,
                    "reason": "overlapping_signature_lift_terms",
                    "instance_id": str(inst_id),
                    "pose_idx": pi,
                    "overlap_count": len(overlap),
                }
            seen_lifted_var_names.update(lifted_var_names)
            accumulated_terms.append(equivalent_vars)
            signature_lift_counts.append(len(equivalent_vars))
        if not accumulated_terms:
            return {"added": False, "reason": "empty_terms"}

        sig_exprs = [sum(vars_) for vars_ in accumulated_terms]
        K = len(accumulated_terms)
        self.model.Add(sum(sig_exprs) <= K - 1)
        cut_index = int(self.owner.build_stats.get("patch_routing_core_cut_count", 0))
        self.owner.build_stats["patch_routing_core_cut_count"] = cut_index + 1
        self.owner._last_solution = None
        return {
            "added": True,
            "reason": "ok",
            "core_size": K,
            "signature_lift_counts": signature_lift_counts,
            "total_pose_terms": int(sum(signature_lift_counts)),
            "new_bool_vars": 0,
            "certificate_metadata": dict(certificate_metadata or {}),
        }

    def add_separator_capacity_cut(self, violation: Any) -> bool:
        """SAC-Hull Phase 2a: dynamic separator capacity cut, full hull form.

        加单 separator 的 full capacity hull constraint. 用 source/sink OR aux +
        cross channeling. paradigm sound + strong (Phase 2 实测 violations 22→17→10).
        master 加 cut 后 CP-SAT 慢, max_per_iter 控制规模.
        """
        from src.models.separator_capacity_hull import add_separator_capacity_hull_constraints
        if not hasattr(self, "_sac_pose_metadata") or not hasattr(self, "_sac_cell_poses"):
            return False
        sep = getattr(violation, "separator", None)
        if sep is None:
            return False
        stats = add_separator_capacity_hull_constraints(
            model=self.model,
            separators=[sep],
            pose_var_metadata=self._sac_pose_metadata,
            cell_poses=self._sac_cell_poses,
            grid_w=self.grid_w, grid_h=self.grid_h,
            routing_free_sink_commodities=self._routing_free_sink_commodities(),
        )
        return bool(stats.get("capacity_constraints", 0) > 0)

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
        # Certified conflict members must map one-to-one to concrete literals.
        # If two distinct members alias to the same BoolVar, repeating or deduping
        # that literal would strengthen the cut into a one-member ban.
        present_lits: List[cp_model.IntVar] = []
        seen_lit_names: Set[str] = set()
        for inst_id, pose_idx in dict(conflict_set).items():
            try:
                pose_idx_int = int(pose_idx)
            except Exception:
                return False
            key = str(inst_id)
            var: Optional[cp_model.IntVar] = None
            if key in self._group_id_by_instance:
                gid = self._group_id_by_instance[key]
                var = self.x_vars.get((gid, pose_idx_int))
            elif key.startswith("pose_optional::power_pole::"):
                var = self.pole_vars.get(pose_idx_int)
            elif key.startswith("pose_optional::"):
                # ro: extract tpl
                parts = key.split("::")
                if len(parts) < 2 or not parts[1]:
                    return False
                tpl = parts[1]
                var = self.ro_vars.get((tpl, pose_idx_int))
            else:
                return False
            if var is None:
                return False
            lit_name = var.Name()
            if lit_name in seen_lit_names:
                return False
            seen_lit_names.add(lit_name)
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

    def _build_port_lookup_cache(self) -> None:
        """First-call build: pose 全索引按 (cell) 和 (port_cell, dir).
        O(N × cells_per_pose) one-time, 后续 cut add O(1)."""
        if self._port_lookup_built:
            return
        # mandatory + ro
        for (key, pose_idx), var in list(self.x_vars.items()) + list(self.ro_vars.items()):
            is_mandatory = key in self._mandatory_template_by_group
            if is_mandatory:
                tpl = self._mandatory_template_by_group[key]
            else:
                tpl = key  # ro key 是 template name
            pool = self.owner.facility_pools.get(tpl, [])
            if int(pose_idx) >= len(pool):
                continue
            pose = pool[int(pose_idx)]
            for cell in pose.get("occupied_cells", []):
                cell_xy = (int(cell[0]), int(cell[1]))
                self._poses_by_cell.setdefault(cell_xy, []).append(var)
            for port_list_key in ("input_port_cells", "output_port_cells"):
                ports = list(pose.get(port_list_key, []) or [])
                side_is_visible = (
                    self._mandatory_port_side_is_cell_pattern_exact(
                        str(key), port_list_key, len(ports)
                    )
                    if is_mandatory
                    else False
                )
                for port in ports:
                    key_tup = (
                        int(port.get("x", 0)),
                        int(port.get("y", 0)),
                        str(port.get("dir", "")),
                    )
                    self._poses_by_port_at_cell_dir.setdefault(key_tup, []).append(var)
                    if side_is_visible:
                        self._routing_visible_poses_by_port_at_cell_dir.setdefault(
                            key_tup, []
                        ).append(var)
        # pole
        for pose_idx, var in self.pole_vars.items():
            pool = self.owner.facility_pools.get("power_pole", [])
            if int(pose_idx) >= len(pool):
                continue
            pose = pool[int(pose_idx)]
            for cell in pose.get("occupied_cells", []):
                cell_xy = (int(cell[0]), int(cell[1]))
                self._poses_by_cell.setdefault(cell_xy, []).append(var)
        self._port_lookup_built = True

    def _build_global_pose_cache(self) -> None:
        """One-time build of GLOBAL-coord cache (pose data 是 global 坐标,
        不加 anchor offset — 区别于 _build_port_lookup_cache phantom-offset).

        Used by 路径 1 (prebuild fc) and 路径 2 (lazy demand cut)."""
        if self._global_cache_built:
            return
        all_vars: List[Tuple[Any, cp_model.IntVar]] = []
        for (gid, pose_idx), v in self.x_vars.items():
            all_vars.append(((gid, int(pose_idx), "x"), v))
        for (tpl_, pose_idx), v in self.ro_vars.items():
            all_vars.append(((str(tpl_), int(pose_idx), "ro"), v))
        for pose_idx, v in self.pole_vars.items():
            all_vars.append((("power_pole", int(pose_idx), "pole"), v))

        for key_, var in all_vars:
            carrier, pose_idx, kind = key_
            if kind == "x":
                tpl_lookup = self._mandatory_template_by_group.get(str(carrier), "")
            elif kind == "ro":
                tpl_lookup = str(carrier)
            else:
                tpl_lookup = "power_pole"
            pool = self.owner.facility_pools.get(tpl_lookup, [])
            if int(pose_idx) >= len(pool):
                continue
            pose = pool[int(pose_idx)]
            for cell in pose.get("occupied_cells", []) or []:
                cell_xy = (int(cell[0]), int(cell[1]))
                self._poses_by_cell_global.setdefault(cell_xy, []).append(var)
            for port_list_key in ("input_port_cells", "output_port_cells"):
                for port in pose.get(port_list_key, []) or []:
                    key_tup = (
                        int(port.get("x", 0)),
                        int(port.get("y", 0)),
                        str(port.get("dir", "")),
                    )
                    self._poses_by_port_cell_dir_global.setdefault(key_tup, []).append(var)
        self._global_cache_built = True

    def add_routing_port_lazy_demand_cut(
        self,
        *,
        pose_var: cp_model.IntVar,
        op_type: str,
        tpl: str,
        pose_idx: int,
    ) -> bool:
        """B1 Phase 6 路线 2: per-pose lazy demand cut for routing front_blocked.

        Form (per side with slack): `sum(blocker_count_k) <= K - demand`.OnlyEnforceIf(pose_var)
        - K = pose's port count on that side (input or output)
        - demand = profile.required slots on that side
        - blocker_count_k = sum(poses 占 front_cell_k) (cell exclusivity 保 <=1)

        语义: pose 选了, 则该 pose 的 K 个 port 中至多 K-demand 个 front 被占
        (即至少 demand 个 cleared, 跟 binding 端 active port 数量匹配 — sound).

        加 input + output 两边 cut (各自 K vs demand 看 slack). 无 slack 一边
        跳过. 至少一边 add 才 return True.
        """
        input_demand, output_demand = self._routing_visible_profile_demands(op_type)
        if input_demand <= 0 and output_demand <= 0:
            return False
        pool = self.owner.facility_pools.get(tpl, [])
        if int(pose_idx) >= len(pool):
            return False
        pose = pool[int(pose_idx)]

        self._build_global_pose_cache()
        cut_added = False
        for side_cells_key, side_demand in (
            ("input_port_cells", input_demand),
            ("output_port_cells", output_demand),
        ):
            port_cells = pose.get(side_cells_key, []) or []
            K = len(port_cells)
            if K == 0 or side_demand <= 0 or K <= side_demand:
                continue
            blocker_terms: List[cp_model.IntVar] = []
            const_blocked = 0
            for port in port_cells:
                dx, dy = _DIR_DELTA.get(str(port.get("dir", "")), (0, 0))
                fx = int(port.get("x", 0)) + dx
                fy = int(port.get("y", 0)) + dy
                if not (0 <= fx < self.grid_w and 0 <= fy < self.grid_h):
                    const_blocked += 1
                    continue
                blockers = self._poses_by_cell_global.get((fx, fy), [])
                for b in blockers:
                    if b is not pose_var:
                        blocker_terms.append(b)
            slack = K - side_demand - const_blocked
            if slack < 0:
                self.model.Add(pose_var == 0)
                cut_added = True
                continue
            if blocker_terms:
                self.model.Add(sum(blocker_terms) <= slack).OnlyEnforceIf(pose_var)
                cut_added = True
        if cut_added:
            cut_index = int(self.owner.build_stats.get("pose_bool_lazy_demand_cut_count", 0))
            self.owner.build_stats["pose_bool_lazy_demand_cut_count"] = cut_index + 1
            self.owner._last_solution = None
        return cut_added

    def _enumerate_poses_with_port_at(
        self, grid_cell: Tuple[int, int], direction: str
    ) -> List[cp_model.IntVar]:
        self._build_port_lookup_cache()
        return list(self._routing_visible_poses_by_port_at_cell_dir.get(
            (int(grid_cell[0]), int(grid_cell[1]), str(direction)), []
        ))

    def _enumerate_poses_occupying(
        self, grid_cell: Tuple[int, int]
    ) -> List[cp_model.IntVar]:
        self._build_port_lookup_cache()
        return list(self._poses_by_cell.get(
            (int(grid_cell[0]), int(grid_cell[1])), []
        ))

    def add_routing_port_blocking_cell_cut(
        self,
        *,
        port_cell: Tuple[int, int],
        direction: str,
        front_cell: Tuple[int, int],
        condition_lits: Sequence[cp_model.IntVar] = (),
    ) -> bool:
        """B1 Phase 5: cell-level generalized cut for routing front_blocked.

        Pattern: 任何 pose 占 port_cell 上有 port 朝 direction + 任何 pose 占 front_cell.
        Cut: sum(port_candidates) + sum(blocker_candidates) <= 1.

        比 instance-level placement_local_nogood 切得更狠 (整类 pattern), 但仍是
        from-Benders-derived (reactive, 不是 a priori), 符合 PROJECT_LOCK 边界.
        """
        port_candidates = self._enumerate_poses_with_port_at(port_cell, direction)
        blocker_candidates = self._enumerate_poses_occupying(front_cell)

        if not port_candidates or not blocker_candidates:
            return False

        all_lits = list(port_candidates) + list(blocker_candidates)
        bound = self.model.Add(sum(all_lits) <= 1)
        cond = [lit for lit in condition_lits if lit is not None]
        if cond:
            bound.OnlyEnforceIf(cond)

        cut_index = int(self.owner.build_stats.get("pose_bool_cell_pattern_cut_count", 0))
        self.owner.build_stats["pose_bool_cell_pattern_cut_count"] = cut_index + 1
        self.owner.build_stats["pose_bool_last_cell_pattern_cut"] = {
            "port_cell": list(port_cell),
            "direction": direction,
            "front_cell": list(front_cell),
            "port_candidates": len(port_candidates),
            "blocker_candidates": len(blocker_candidates),
        }
        self.owner._last_solution = None
        return True
