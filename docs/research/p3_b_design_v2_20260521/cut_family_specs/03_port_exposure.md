# Cut Family 3 — port_exposure (完整 spec, 复用 boundary_constraints)

> **Status**: Day 17a v1.0 (2026-05-21)
> **Mode**: literal (_FAMILY_MODE_MAP)
> **Family_version**: v1.0
> **复用**: cand C `boundary_constraints.py` per-(cell, dir) net flow equality

## 1. 数学定义

facility port: facility 边界上必须暴露的 cell (用于 belt/物流 IO). 每 port
有 direction (上/下/左/右). port 必须接到一个 free_cell ( "front cell") 跟该
direction 一致.

Family 3 cut 表达:

```
∃ facility A pose pA, port p_k @ cell c_k direction d_k,
  front cell c_k + dir(d_k) ∈ cell_owner OR ∉ free_cells
  ⇒ INFEASIBLE (port blocked)
```

literal-based: cut.literals = (facility A slot=pA) + 占 front cell 的 facility
B slots (类似 Family 7 cell_owner causation split).

## 2. Soundness proof

port-front cell 必须 belt-usable. 若 cell_owner 占 front → 不能放 belt → 不能
从 port 通流 → facility 无法供应/接收 commodity → INFEASIBLE.

scope: cell_owner change 影响 front cell, 必须多 literal carry blocking
facility. 类似 F7 finding #1 causation logic.

## 3. Cert payload schema

```python
@dataclass(frozen=True)
class PortExposureCert:
    """cert_kind = "port_exposure_blocked"."""
    facility_group: GroupId
    facility_pose_id: PoseId
    port_cell: Tuple[int, int]
    port_direction: Literal["up", "down", "left", "right"]
    front_cell: Tuple[int, int]              # = port_cell + dir
    blocking_facility: Tuple[GroupId, int, PoseId]  # (group, slot, pose_id)
                                              # 占 front_cell 的 facility
    active_port_witness_b64: str             # binding port active cert blob
                                              # (复用 cand C boundary_constraints
                                              # per-(cell, dir) net flow equality 结果)
```

## 4. Cut object 构造 (literal mode)

```python
cut = Cut(
    family="port_exposure",
    literals=(
        CutLiteral(slot_ref=AnonymousSlotRef(facility_group, 0),
                   pose_id=facility_pose_id),
        # blocking facility literal (cell_owner causation, F7 同 pattern)
        CutLiteral(slot_ref=AnonymousSlotRef(blocking_group, blocking_slot),
                   pose_id=blocking_pose_id),
    ),
    geometric_payload=None,
    scope=CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        ...,
        oracle_abstraction_version="port_exposure_v1",
        active_assumptions=(
            Assumption("facility_port_set",
                       value=f"{facility_group}#{facility_pose_id}=ports_list"),
        ),
    ),
    cert=OracleCert(cert_kind="port_exposure_blocked", ...),
)
```

## 5. Generator (复用 boundary_constraints)

```python
class PortExposureOracle:
    name = "port_exposure_v1"

    def generate(self, state, master_solution):
        from src.constraints.boundary_constraints import compute_port_active_set
        cuts = []
        for placed in master_solution.placed_facility_poses:
            ports = canonical_rules_facility_ports(placed.facility_group,
                                                    placed.pose_id)
            active_set = compute_port_active_set(placed, state)
            for port_cell, port_dir in ports:
                front_cell = (port_cell[0] + dir_offset(port_dir)[0],
                              port_cell[1] + dir_offset(port_dir)[1])
                if front_cell not in state.free_cells:
                    if front_cell in state.cell_owner:
                        # cell_owner 占 front, multi-literal cut
                        blocking = state.cell_owner[front_cell]
                        blocking_pose_id = state.groups[blocking[0]].selected_poses[blocking[1]][1]
                        cert = PortExposureCert(
                            facility_group=placed.facility_group,
                            facility_pose_id=placed.pose_id,
                            port_cell=port_cell,
                            port_direction=port_dir,
                            front_cell=front_cell,
                            blocking_facility=(blocking[0], blocking[1], blocking_pose_id),
                            active_port_witness_b64=encode_port_witness(active_set, port_cell),
                        )
                        cuts.append(construct_port_exposure_cut(state, cert))
                    else:
                        # ghost 占 front → 不需要 cut, ghost_rect 已限制 master OPTIMAL 不该选此 pose
                        pass
        return cuts
```

## 6. evaluate_cut (literal-based, 走 §5 multiset)

按 cut_lifecycle_v2 v3 §5 family-dispatch — literal-based 走
`evaluate_cut_literal_based` (multiset 包含). cut 含 2 literal:
facility A 的 pose pA + blocking facility B 的 pose pB. state 同时含两 pose
→ violate.

## 7. Validator

```python
class PortExposureValidator(CutValidator):
    family = "port_exposure"
    validator_version = "v1.0"

    def validate(self, cut, state) -> ValidationResult:
        cert = decode_port_exposure_cert(cut.cert.cert_payload)
        # 1. 验 port_cell 是 facility_pose 的 port (查 canonical_rules)
        actual_ports = canonical_rules_facility_ports(cert.facility_group, cert.facility_pose_id)
        if (cert.port_cell, cert.port_direction) not in actual_ports:
            return ValidationResult("unsound", ..., "port not in facility ports")
        # 2. 验 front_cell = port_cell + dir
        expected_front = (cert.port_cell[0] + dir_offset(cert.port_direction)[0],
                           cert.port_cell[1] + dir_offset(cert.port_direction)[1])
        if cert.front_cell != expected_front:
            return ValidationResult("unsound", ..., "front_cell mismatch")
        # 3. 验 blocking_facility pose 在 state.cell_owner[front_cell]
        bg, bs, bp = cert.blocking_facility
        if state.cell_owner.get(cert.front_cell) != (bg, bs):
            return ValidationResult("unsound", ..., "blocking facility not at front")
        # 4. 验 active_port_witness (复用 cand C boundary_constraints check)
        if not verify_port_witness(cert.active_port_witness_b64,
                                     cert.port_cell, cert.facility_group):
            return ValidationResult("unsound", ..., "port active witness fail")
        return ValidationResult("ok", ...)

    def evaluate_geometric(self, cut, state):
        raise NotImplementedError("Family 3 is literal-based")
```

## 8. Replay + watcher

watcher:
- by_cell_watcher (port_cell + front_cell)
- by_group_watcher (facility_group + blocking_group)
- by_pose_watcher (facility_group/pose_id + blocking_group/blocking_pose_id)

## 9. Open questions

1. **Active port subset**: facility 多 port 中只部分 active (binding 端决定),
   cut 是否覆盖. v1.0 假设 all ports active.
2. **ghost-occluded front 不发 cut**: master 端 ghost_rect_id 已通过 master
   constraint 应排除此 pose, 不需要 cut. v1.0 不发. Phase 1 验 trigger 路径.

## 10. 验收

- ✅ 数学 + soundness (port-front blocked → INFEASIBLE)
- ✅ Cert schema + cut 构造 + generator (boundary_constraints 复用) + evaluate + validator
- ✅ Multi-literal blocking (F7 同 pattern, 防 cell_owner 移走误剪)
- ⏸ Phase 1 实施 src/cuts/families/port_exposure.py
