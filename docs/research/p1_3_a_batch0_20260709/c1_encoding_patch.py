"""A 批 0：C1 供电编码原型（杆侧 pose 布尔 + 全局 cov 通道）——v1（codex 审查修复版）。

测量专用 monkeypatch——绝非 certified 旋钮。机制（设计工作流 C1 + 对抗审查修订）：
- 763 个坐标杆槽全拆，换 4761 个 pose 布尔 p_k（覆盖关系编译期静态——B1 34× 形态的直接对应物）。
- 杆体重叠：每 pose 一对常量 OptionalIntervalVar 顺势注入 _core_x/y_intervals →
  自动流进（唯一的）组合 no_overlap_2d 与 dedup 逻辑。
- 覆盖：cov[c] ≤ Σ_{k 覆盖 c} p_k（每格一条，纯静态系数）+ 每受电设施一个
  witness cell（wx/wy 钳在 footprint 内 + flat 索引 + AddElement(flat, cov, t) + t=1）。
- 容量族有效不等式经 6353 行空计数守卫干净跳过（valid-inequality，跳过=更弱但 sound）。
等价性引理（对抗审查）：等价性依赖「pose 池 = 完整格阵」——build 时 fail-closed 断言。

v1 修复（2026-07-09 codex 独立审查 4 发现，批 0 c1 cell 发射前拦截）：
1. 致命——bind_from_core 克隆路径把 _core_x/y_intervals 重置为「仅 slot specs」，
   C1 杆 interval 丢失；随后 ghost overlay 的组合 no_overlap 不含杆、修复 C 的
   dedup 又清掉含杆的 core-only 前身 → 杆完全裸奔（可叠设施/ghost → 假 FEASIBLE）。
   修复：patch bind_from_core，原逻辑后按名字从 proto 找回 c1pole interval/bool。
2. 池完整性断言只查数量 → 升级为「anchor 集合 == 域格阵格点集合」逐点比对。
3. required/mandatory 杆槽路径 C1 未处理 → fail-closed（生产 266 实例无此形态，出现即 raise）。
4. 生产的杆数 dominance 包络（exact_coordinate_master.py:6321-6339，Σ杆 ≤ 受电选择数）
   在 C1 下因 residual 杆槽消失而不触发 → 在 cov 构建尾部补对应物（保持头对头公平）。
"""
from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

import src.models.exact_coordinate_master as ecm

_ORIG_CREATE = ecm.CoordinateExactMasterDelegate._create_power_pole_slot_vars
_ORIG_COVER = ecm.CoordinateExactMasterDelegate._add_geometric_power_coverage_constraints
_ORIG_PREPARE = ecm.CoordinateExactMasterDelegate._prepare_slot_specs
_ORIG_BIND = ecm.CoordinateExactMasterDelegate.bind_from_core


def _prepare_slot_specs_c1(self: Any) -> None:
    """杆槽 spec 从不出生（build 与 clone 两条路径的绑定表保持一致）。"""
    _ORIG_PREPARE(self)
    self.residual_optional_slots.pop("power_pole", None)
    # 修复 3：C1 只实现 residual optional 杆的等价重编码；required/mandatory 杆
    # 槽若存在会留下「坐标杆 + 全池 p_k」混合语义，直接 fail-closed。
    if self.required_optional_slots.get("power_pole") or self.mandatory_slots.get(
        "power_pole"
    ):
        raise RuntimeError(
            "C1 前提破坏: 存在 required/mandatory power_pole 槽（C1 原型未实现该路径）"
        )


def _create_power_pole_slot_vars_c1(self: Any) -> None:
    self.power_pole_family_count_vars = {}
    self._power_pole_family_membership = {
        family_name: []
        for family_name in self._power_pole_family_name_by_int.values()
    }
    pool = list(self.owner.facility_pools.get("power_pole", []))
    # 修复 2 + 语义引理断言：pose 池 anchor 集合必须逐点等于域格阵（缺格/重复
    # 都是穷尽性破口——数量相等挡不住「缺 (68,68) 重复 (0,0)」）。
    domains = dict(self._template_full_mode_rect_domains.get("power_pole", {}))
    if pool and domains:
        dom = domains[min(domains)]
        expected_lattice = {
            (x, y)
            for x in range(int(dom.x_min), int(dom.x_max) + 1)
            for y in range(int(dom.y_min), int(dom.y_max) + 1)
        }
        anchors = [
            (int(p.get("anchor", {}).get("x")), int(p.get("anchor", {}).get("y")))
            for p in pool
        ]
        if len(anchors) != len(set(anchors)) or set(anchors) != expected_lattice:
            raise RuntimeError(
                f"C1 前提破坏: pole pose 池 anchor 集合 != 完整格阵"
                f"（池 {len(anchors)} 个/去重 {len(set(anchors))} 个，"
                f"格阵应 {len(expected_lattice)} 个）"
            )
    self._c1_pole_bools = []
    for pose_idx, pose in enumerate(pool):
        var = self.model.NewBoolVar(f"c1pole__{pose_idx}")
        cells = [(int(c[0]), int(c[1])) for c in pose.get("occupied_cells", [])]
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        x_iv = self.model.NewOptionalIntervalVar(
            min(xs), max(xs) - min(xs) + 1, max(xs) + 1, var, f"c1pole_x__{pose_idx}"
        )
        y_iv = self.model.NewOptionalIntervalVar(
            min(ys), max(ys) - min(ys) + 1, max(ys) + 1, var, f"c1pole_y__{pose_idx}"
        )
        self._core_x_intervals.append(x_iv)
        self._core_y_intervals.append(y_iv)
        coverage = frozenset(
            (int(c[0]), int(c[1])) for c in pose.get("power_coverage_cells", []) or []
        )
        self._c1_pole_bools.append((pose_idx, var, coverage))
    if self._c1_pole_bools:
        upper = int(getattr(self, "_power_pole_slot_upper_bound", 0) or 0)
        if upper > 0:
            self.model.Add(
                sum(var for _, var, _ in self._c1_pole_bools) <= upper
            )


def bind_from_core_c1(self: Any, coordinate_binding: Any) -> None:
    """修复 1：clone 重建 _core_x/y_intervals 时按名字从 proto 找回 C1 杆 interval。

    原 bind_from_core 只从 slot specs 重建（杆 spec 已被 pop → 杆 interval 丢失），
    随后 ghost overlay 组合 no_overlap 不含杆、dedup 清含杆前身 → 杆裸奔。
    这里在原逻辑后扫 proto，把 c1pole_x__N/c1pole_y__N interval 与 c1pole__N 布尔
    按 N 排序找回（非 C1 模型天然零命中 = no-op）。
    """
    _ORIG_BIND(self, coordinate_binding)
    proto = self.model.Proto()
    x_ivs: dict[int, Any] = {}
    y_ivs: dict[int, Any] = {}
    for idx, constraint in enumerate(proto.constraints):
        name = constraint.name
        if name.startswith("c1pole_x__"):
            x_ivs[int(name[len("c1pole_x__"):])] = self.model.GetIntervalVarFromProtoIndex(idx)
        elif name.startswith("c1pole_y__"):
            y_ivs[int(name[len("c1pole_y__"):])] = self.model.GetIntervalVarFromProtoIndex(idx)
    if set(x_ivs) != set(y_ivs):
        raise RuntimeError("C1 clone 恢复失败: x/y interval 集合不对齐")
    pool = list(self.owner.facility_pools.get("power_pole", []))
    bools: dict[int, Any] = {}
    for var_idx, var_proto in enumerate(proto.variables):
        name = var_proto.name
        if name.startswith("c1pole__"):
            bools[int(name[len("c1pole__"):])] = self.model.GetBoolVarFromProtoIndex(var_idx)
    if set(bools) != set(x_ivs):
        raise RuntimeError("C1 clone 恢复失败: 杆布尔与 interval 集合不对齐")
    self._c1_pole_bools = []
    for pose_idx in sorted(x_ivs):
        self._core_x_intervals.append(x_ivs[pose_idx])
        self._core_y_intervals.append(y_ivs[pose_idx])
        coverage = frozenset(
            (int(c[0]), int(c[1]))
            for c in (
                pool[pose_idx].get("power_coverage_cells", []) or []
                if pose_idx < len(pool)
                else []
            )
        )
        self._c1_pole_bools.append((pose_idx, bools[pose_idx], coverage))


def _add_geometric_power_coverage_constraints_c1(self: Any) -> None:
    powered_slots = self._all_powered_slots()
    pole_bools = list(getattr(self, "_c1_pole_bools", []))
    if not self._supports_rectangular_power_coverage():
        raise RuntimeError("C1 原型只支持矩形世界（非矩形回退未实现）")
    if not pole_bools:
        for powered_slot in powered_slots:
            if powered_slot.active is not None:
                self.model.Add(powered_slot.active == 0)
            else:
                self.model.Add(0 >= 1)
        self.owner.build_stats["power_coverage"] = {
            "representation": "coordinate_geometric",
            "encoding": "c1_pose_bool_cov_channel_v1_prototype",
            "powered_slots": len(powered_slots),
            "pole_slots": 0,
            "cover_literals": 0,
            "witness_indices": 0,
            "element_constraints": 0,
        }
        return

    grid_w, grid_h = int(self.grid_w), int(self.grid_h)
    coverers_by_cell: dict[tuple[int, int], list[Any]] = {}
    for _, var, coverage in pole_bools:
        for cell in coverage:
            coverers_by_cell.setdefault(cell, []).append(var)

    cov = []
    channel_constraints = 0
    for cy in range(grid_h):
        for cx in range(grid_w):
            lit = self.model.NewBoolVar(f"c1cov__{cx}_{cy}")
            coverers = coverers_by_cell.get((cx, cy))
            if coverers:
                self.model.Add(lit <= sum(coverers))
            else:
                self.model.Add(lit == 0)
            channel_constraints += 1
            cov.append(lit)

    witness_indices = 0
    element_constraints = 0
    for powered_slot in powered_slots:
        fx = self._slot_footprint_x_start(powered_slot)
        fy = self._slot_footprint_y_start(powered_slot)
        fw = self._slot_footprint_width(powered_slot)
        fh = self._slot_footprint_height(powered_slot)
        wx = self.model.NewIntVar(0, grid_w - 1, f"c1wx__{powered_slot.key}")
        wy = self.model.NewIntVar(0, grid_h - 1, f"c1wy__{powered_slot.key}")
        bounds = [
            self.model.Add(wx >= fx),
            self.model.Add(wx <= fx + fw - 1),
            self.model.Add(wy >= fy),
            self.model.Add(wy <= fy + fh - 1),
        ]
        flat = self.model.NewIntVar(0, grid_w * grid_h - 1, f"c1flat__{powered_slot.key}")
        flat_def = self.model.Add(flat == wx + wy * grid_w)
        target = self.model.NewBoolVar(f"c1cover__{powered_slot.key}")
        self.model.AddElement(flat, cov, target)
        if powered_slot.active is not None:
            for constraint in bounds:
                constraint.OnlyEnforceIf(powered_slot.active)
            self.model.Add(target == 1).OnlyEnforceIf(powered_slot.active)
        else:
            self.model.Add(target == 1)
        _ = flat_def
        witness_indices += 1
        element_constraints += 1

    # 修复 4：生产杆数 dominance 包络的 C1 对应物（照抄 6321-6339 语义：
    # Σ杆 ≤ mandatory 受电(非杆) + required optional 受电(非杆) + Σ residual 受电(非杆) active）。
    powered_templates = set(self.owner._powered_templates)
    mandatory_powered_nonpole = int(self.owner._mandatory_powered_nonpole_count())
    required_optional_powered_count = sum(
        len(slot_specs)
        for tpl, slot_specs in self.required_optional_slots.items()
        if str(tpl) in powered_templates and str(tpl) != "power_pole"
    )
    residual_powered_optional_terms = [
        slot.active
        for tpl, slot_specs in self.residual_optional_slots.items()
        if str(tpl) in powered_templates and str(tpl) != "power_pole"
        for slot in slot_specs
        if slot.active is not None
    ]
    self.model.Add(
        sum(var for _, var, _ in pole_bools)
        <= int(mandatory_powered_nonpole)
        + int(required_optional_powered_count)
        + sum(residual_powered_optional_terms)
    )

    self.owner.build_stats["power_coverage"] = {
        "representation": "coordinate_geometric",
        "encoding": "c1_pose_bool_cov_channel_v1_prototype",
        "powered_slots": len(powered_slots),
        "pole_slots": len(pole_bools),
        "cover_literals": int(channel_constraints),
        "witness_indices": int(witness_indices),
        "element_constraints": int(element_constraints),
        "dominance_bound_terms": int(mandatory_powered_nonpole)
        + int(required_optional_powered_count),
    }


def apply_c1_patch() -> None:
    ecm.CoordinateExactMasterDelegate._prepare_slot_specs = _prepare_slot_specs_c1
    ecm.CoordinateExactMasterDelegate._create_power_pole_slot_vars = (
        _create_power_pole_slot_vars_c1
    )
    ecm.CoordinateExactMasterDelegate._add_geometric_power_coverage_constraints = (
        _add_geometric_power_coverage_constraints_c1
    )
    ecm.CoordinateExactMasterDelegate.bind_from_core = bind_from_core_c1


def revert_c1_patch() -> None:
    ecm.CoordinateExactMasterDelegate._prepare_slot_specs = _ORIG_PREPARE
    ecm.CoordinateExactMasterDelegate._create_power_pole_slot_vars = _ORIG_CREATE
    ecm.CoordinateExactMasterDelegate._add_geometric_power_coverage_constraints = (
        _ORIG_COVER
    )
    ecm.CoordinateExactMasterDelegate.bind_from_core = _ORIG_BIND
