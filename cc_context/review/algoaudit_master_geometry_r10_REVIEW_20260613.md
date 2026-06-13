# 终末地 IndustrialPlanner 几何 master round 10 审查报告

## 0. 输入校验

- 只使用指定快照: `/mnt/data/zmd_snapshot_2cd169b4.zip`
- sha256 已校验通过: `2cd169b46a12cc1e52e1915d89279be48fc0f6adbd02b1530d0994d18d1879eb`
- zip 内 `project/` 已作为仓库根解包。
- 离线依赖从 `/mnt/data/zmd_py313_linux_x86_64.zip` 安装到 Python 3.13 venv。
- `data/preprocessed/candidate_placements.json` 已校验:
  - size: `45,773,799`
  - sha256: `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`

## 1. 总结结论

**本轮零 soundness finding。**

几何 master 主体未发现 false-FEASIBLE / false-INFEASIBLE 级问题。Q2 深挖覆盖了 ghost rectangle 交互约束、power coverage witness 链、mandatory exactly-one 到 slot 装配链、delta/interval bbox 编码。Q3 自由攻击覆盖了“全局 x/y/mode 域裸用”风险和 exact-core ghost overlay 绑定链。

本轮另发现并修复 1 个非 soundness LOW hardening 残留: persisted master hint 旧入口仍可通过裸 `int()` 接受 numeric string / bool / float。它只影响 CP-SAT hint guidance, 不改变可行域或证明边界，因此不计入 soundness finding, 但属于 r9 LOW 修复口径下的入口一致性残留。

补丁文件: `zmd_r10_low_hint_patch.diff`。

## 2. Finding

### LOW-HINT-R10-01 - persisted master hints 仍绕过 strict parser

**Severity:** LOW, robustness / hint-ingress consistency, non-soundness

**原始位置:**

- `src/search/master_hint_persistence.py:80`: `write_master_hints()` 对 `var_values` 使用 `{str(k): int(v) ...}`。
- `src/search/master_hint_persistence.py:112`: `load_master_hints()` 对 JSON 中的 `var_values` 使用 `{str(k): int(v) ...}`。
- `src/models/master_model.py:11686` 和 `src/models/master_model.py:11695`: legacy `apply_master_hints()` 对 persisted hint value 使用 `int(hints[name])` 后传入 `AddHint()`。

**问题:**

r9 LOW 修复已经引入共享 parser, 其本体明确要求 `type(value) is int`, 拒绝 `bool`、float 和 numeric string: `src/models/solution_hint_parser.py:14-19`。但 persisted master hint IO 和 legacy apply 路径仍保留裸 `int()`。例如 JSON hint 中的 `"1"`、`true`、`1.0` 会被转换成整数并进入 hint 应用路径。

这不改变 CP-SAT 模型约束和可行域, 因此不是 soundness bug。但它违背“所有 hint 值入口共享 strict parser”的 r9 LOW 口径, 且会让外部可编辑的 checkpoint hint 文件与 solution/community hint 行为不一致。

**修复:**

- `src/search/master_hint_persistence.py:78-128`: `write_master_hints()` 和 `load_master_hints()` 改为调用 `parse_strict_int_hint_value()`。
  - load: 任一 value 非 exact int 时返回 `None`, 沿用坏 hint 文件 fail-closed/skip 的语义。
  - write: 任一 value 非 exact int 时抛 `TypeError`, 防止写出不合 schema 的 checkpoint。
- `src/models/master_model.py:11685-11697`: legacy `apply_master_hints()` 改为 parser 过滤, 仅 exact int 进入 `AddHint()`。
- `src/tests/test_master_hint_persistence.py:52-71`: 覆盖 load/write 对 `"1"`, `True`, `1.0`, `None` 的拒绝。
- `src/tests/test_master_hint_loop_integration.py:34-47,158-174`: 覆盖 legacy `apply_master_hints()` 只接受 exact int。

**Regression:**

```text
python -m pytest -q -p no:randomly \
  src/tests/test_master_hint_persistence.py \
  src/tests/test_master_hint_loop_integration.py \
  src/tests/test_solution_hint_malformed_defense.py \
  src/tests/test_community_hint_env_injection.py

64 passed in 1.48s
```

## 3. Q1: r9 LOW hint parser 轻确认

### 3.1 Parser 本体口径

`src/models/solution_hint_parser.py:14-19` 使用 `type(value) is int`, 因此 `bool` 不会因继承 `int` 被误收, numeric string 和 float 也不会被截断。

### 3.2 已确认使用 parser 的入口

- Coordinate master solution hint: `src/models/exact_coordinate_master.py:6783-6869`
- Pose-bool exact master solution hint: `src/models/pose_bool_exact_master.py:970-1000`
- Public `MasterPlacementModel.solve()` coordinate/legacy AddHint path: `src/models/master_model.py:11309-11323`
- Community hint + warm-start ghost anchor: `src/search/benders_loop.py:4175-4199,4447-4452`
- Persisted master hints: 本轮补丁后 `src/search/master_hint_persistence.py:78-128` 和 `src/models/master_model.py:11685-11697`

全仓复扫后, 剩余 `AddHint()` 裸整数均为内部常量或 parser 之后的坐标/模式派生值, 不是外部 hint value ingress。例如 `src/models/routing_subproblem.py:1057` 是内部 `AddHint(var, 0)`。

## 4. Q2 深角落 1: ghost rectangle 交互约束与 max_lex 目标

### 攻击点

检查 ghost 是否:

1. anchor 枚举漏格或越界;
2. `u_var` 与 anchor/cells 通道不一致;
3. 未与 core facilities 做 no-overlap;
4. 被隐式添加外部路径或其它额外要求;
5. power/signature tightening 对未选 ghost 生效, 造成 false-INFEASIBLE;
6. terminal objective 不是 `max_lex(area, min_side)`。

### 证据与判读

`src/models/exact_coordinate_master.py:3632-3732` 是 coordinate path 的 ghost 本体:

- ghost disabled 时直接返回: `3662-3665`。
- ghost 大于 grid 时 fail-closed UNSAT: `3667-3675`。
- anchor 枚举为 `range(grid_w - ghost_w + 1)` 和 `range(grid_h - ghost_h + 1)`: `3677-3683`。
- 每个 anchor 的 cells 由 `dx in range(ghost_w)`, `dy in range(ghost_h)` 精确枚举: `3684-3689`。
- 每个 anchor 创建一个 `u_var` 并登记到 `owner.u_vars` 与 `_ghost_domains`: `3690-3692`。
- ghost interval 是以同一个 `u_var` 为 presence 的 optional interval: `3693-3708`。
- 无可用 anchor 时 fail-closed UNSAT: `3710-3724`。
- `AddExactlyOne(owner.u_vars.values())`: `3728`。
- `AddNoOverlap2D([core intervals, ghost intervals])`: `3729-3732`。

ghost power capacity screen 只在选中 anchor 上生效或通过 big-M 解耦未选 anchor。关键条件:

- 只基于 ghost cells 与 power pole occupied cells 的相交来计算 blocked poles: `src/models/exact_coordinate_master.py:3820-3880`。
- 只有当 `max_capacity < demand` 时禁用 anchor: `3910-3928`。
- family upper bound 用 `OnlyEnforceIf(u_var)` 或 `+ global_upper_bound * (1 - u_var)` 解除未选 anchor: `3949-3975`。

signature bucket tightening 同样按 selected ghost 条件约束。fallback 精确扫描 dedupe blocked pose: `src/models/exact_coordinate_master.py:4654-4671,4770-4787`, 约束通过 `+ global_upper_bound * (1 - u_var)` 解除未选 anchor: `4815-4819`。

未发现 ghost 被添加外部路径要求。外部 routing/path 不在这条 master 约束链里。

max_lex 目标在 frontier 层编码:

- candidate oriented enumeration 不做 `h <= w` canonicalization, 避免漏掉转置候选: `src/search/certified_frontier.py:73-76`。
- objective key 是 `(area, min(w,h))`: `src/search/certified_frontier.py:163-165`。
- sort key 先 `-area`, 再 `-min_side`, 其它仅 tie-break: `168-172`。
- terminal projection 用 `candidate_objective()` 比较 best certified 并剪掉 objective 不优的候选: `194-198,216-220`。
- terminal validation 要求 best key 与 final key 一致且 potential/frontier 为空: `411-420`。

**结论:** 未发现 ghost 交互约束或 max_lex 编码的 soundness 问题。

## 5. Q2 深角落 2: power coverage witness 链

### 攻击点

检查 coverage witness 是否:

1. 矩形支持判断错误导致几何编码漏约束;
2. table fallback 与精确 coverer index 不一致;
3. witness 未受 active guard 约束;
4. pole capacity family 与 coverage 使用的 pose/cells 不一致;
5. no pole / no coverer 时未 fail-closed。

### 证据与判读

`src/models/exact_coordinate_master.py:5125-5159` 的 `_supports_rectangular_power_coverage()` 要求 powered non-pole footprint 为矩形, power pole coverage 为按 radius 裁剪后的矩形。若不支持, `_add_geometric_power_coverage_constraints()` 在 `5815-5826` 回退到 `_add_table_power_coverage_constraints()`。

Table fallback 在 `src/models/exact_coordinate_master.py:5161-5212` 中为每个 powered slot 与 pole slot 建 witness:

- coverer 来源为 `owner._power_coverers_by_template_pose`: `5167`。
- `cover_lit <= pole_slot.active` 与 `cover_lit <= powered_slot.active`: `5187-5192`。
- exact tuple 表只在 `cover_lit` 为真时强制: `5193-5197`。
- 每个 powered slot 要求 witness sum 覆盖 active 或 mandatory: `5202-5206`。
- 无 witness 时 optional powered slot forced inactive, mandatory powered slot forced UNSAT: `5207-5211`。

几何 selected witness 在 `src/models/exact_coordinate_master.py:5269-5336` 中受 powered active 和 selected guard 约束, interval overlap 的四个不等式为 `5316-5327`; delta encoding 分支同源于该函数。

power pole family/capacity 链:

- `_prepare_power_pole_families()` 在 `src/models/exact_coordinate_master.py:2044-2219` 用 exact local capacity coefficients 分组, shell lookup 只有唯一映射时使用, 冲突时回退 exact `(x,y,mode,family)` table。
- residual power pole slot family channel 在 `3290-3378`, exact tuple table 分支在 `3359-3363`。
- global capacity lower bound 只在 power coverage 未跳过时应用, 对每个 powered demand 加 `sum(coeff * family_count_var) >= demand`, 无 terms 时 fail-closed UNSAT: `6268-6322`。

### Probe

运行 `r10_geometry_probe.py` 对当前 candidate pool 与 coordinate delegate 做实证复核。关键输出:

```text
candidate_size 45773799
candidate_sha256 adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
build_skip_power_seconds 20.47
powered_templates ['manufacturing_3x3', 'manufacturing_5x5', 'manufacturing_6x4', 'protocol_storage_box']
powered_nonpole_rect_bad 0 []
power_radius_inferred 5
pole_coverage_rect_bad 0 []
coverer_index_bad 0 []
coverer_empty_by_template {}
coverer_total_edges 10385840
```

Probe 重新用 power pole coverage cells 建 `cell_to_poles`, 对每个 powered pose 的 occupied cells 做 brute-force coverer union, 并过滤与 powered occupied cells 相交的 pole occupied cells。结果与 `owner._power_coverers_by_template_pose` 全量一致。

**结论:** 未发现 power coverage witness 链 soundness 问题。完整 non-skip power coordinate build 在本沙盒 300s 内未完成, 因此本轮以源审计、coverer index probe 和专项测试作为证据。

## 6. Q2 深角落 3: mandatory exactly-one 到 slot 装配链

### 攻击点

r8/r9 的 signature/order 修复后, slot domain 最容易出现“IntVar 全局 x/y/mode 域比实际候选 pose 更大”的缝隙。攻击目标是证明每个 slot 要么有 direct table, 要么有 signature-region exactly-one, 不存在 naked global domain。

### 证据与判读

slot specs 构造在 `src/models/exact_coordinate_master.py:2243-2345`:

- mandatory slots 使用 group-specific candidate tuples: `2251-2269`。
- required optional slots 使用 template full tuples: `2275-2297`。
- residual optional slots 只为 `protocol_storage_box` 和 `power_pole` 建上界 slot: `2299-2345`。

base slot geometry 在 `2615-2705` 创建全局 x/y/mode/order channels, 但若 `slot.use_domain_table` 为真, 会添加 `[x,y,mode]` `AddAllowedAssignments()`。非 table 路径不靠裸全局域完成约束, 而是进入 signature-region channel:

- mandatory / required optional signature path: `2707-2782`, 对 bucket lits 与 region lits 加 exactly-one 和 `signature == sum(...)`。
- residual optional signature path: `2784-2860`, inactive sentinel 和 `sum(bucket_lits) == active`。
- mandatory slot 顺序和 `order_key` 单调约束在 `2874-2916`。

### Probe

同一个 `r10_geometry_probe.py` 输出:

```text
mandatory_instance_count 266
mandatory_group_count 19
mandatory_slot_count 266
required_optional_slot_count 0
residual_optional_slot_count 1307
residual_optional_by_template {'protocol_storage_box': 544, 'power_pole': 763}
slot_path_counts [("('mandatory', 'boundary_storage_port', 'signature_regions')", 46), ("('mandatory', 'manufacturing_3x3', 'signature_regions')", 132), ("('mandatory', 'manufacturing_5x5', 'signature_regions')", 49), ("('mandatory', 'manufacturing_6x4', 'signature_regions')", 38), ("('mandatory', 'protocol_core', 'signature_regions')", 1), ("('residual_optional', 'power_pole', 'power_pole_rect')", 763), ("('residual_optional', 'protocol_storage_box', 'signature_regions')", 544)]
unguarded_bad_count 0 []
```

为确认攻击面真实存在, probe 还计算了“若裸用全局 x/y/mode box 会多收多少非法 tuple”:

```text
naked_global_invalid boundary_storage_port 9114 of 9248
naked_global_invalid manufacturing_3x3 1088 of 18496
naked_global_invalid manufacturing_5x5 1056 of 17424
naked_global_invalid manufacturing_6x4 520 of 16900
naked_global_invalid power_pole 0 of 4761
naked_global_invalid protocol_core 0 of 6728
naked_global_invalid protocol_storage_box 0 of 4624
```

也就是说, 若 signature/table 链漏接, 该 probe 会抓到大量非法组合; 实际 slot path 中 `unguarded_bad_count == 0`。

**结论:** mandatory exactly-one 到 slot 装配链未发现 soundness 问题。

## 7. Q2 深角落 4: delta/interval 与 footprint bbox 编码

### 攻击点

检查 footprint bbox 是否正确跟随 mode, 以及 NoOverlap2D 是否挂到 footprint bbox interval 而不是裸 anchor/dims。

### 证据与判读

`src/models/exact_coordinate_master.py:2357-2480` 的 `_create_slot_footprint_intervals()`:

- 从 `slot.mode_rect_domains` 收集每个 mode 的 footprint bounds/width/height: `2363-2381`。
- 添加 `[mode, dx_min, dy_min, footprint_width, footprint_height]` allowed table: `2403-2422`。
- `footprint_x_start = x + dx_min`, `footprint_y_start = y + dy_min`, end = start + width/height: `2424-2447`。
- optional slot 使用 active presence interval, mandatory slot 使用普通 interval: `2449-2478`。
- interval 统一加入 core interval list: `2479-2480`。

core facility no-overlap 在 `src/models/exact_coordinate_master.py:3427-3428`; ghost overlay no-overlap 在 `3729-3732`。这说明 NoOverlap2D 看到的是 mode-channelled footprint bbox interval。非矩形 footprint 使用保守 bbox 是 lock 接受的设计口径, 本轮仅验证 bbox 推导和通道。

**结论:** delta/interval/bbox 编码未发现 soundness 问题。

## 8. Q3 自由攻击角

### 8.1 全局域裸用攻击

这个攻击与 Q2 slot 装配交叉, 但我把它作为独立 probe 处理: 先证明 full global x/y/mode 域会真实多收非法 tuple, 再检查每个实际 slot 是否都有 table/signature/family guard。结果见第 6 节, `unguarded_bad_count 0 []`。此攻击推翻了“base slot IntVar 域裸宽导致 false-FEASIBLE”的怀疑。

### 8.2 exact-core ghost overlay 绑定链

攻击点: core proto 是 ghost-free 构建, overlay 时若 slot vars 或 intervals 没有从 core binding 正确复原, `_add_ghost_constraints()` 可能只对 ghost intervals 做 no-overlap, 漏掉 core facilities。

证据:

- `build_exact_core()` 用 `ghost_rect=None` 构建 core, 捕获 proto 并 export coordinate binding: `src/models/master_model.py:2537-2558`。
- `from_exact_core()` 克隆 proto: `src/models/master_model.py:2716`。
- coordinate overlay 调 `bind_from_core()` 再 `_add_ghost_constraints()`: `src/models/master_model.py:2803-2811`。
- `bind_from_core()` 用 binding 复原每个 slot 的 active/x/y/mode/signature/family 和 interval, 并重建 `_core_x_intervals/_core_y_intervals`: `src/models/exact_coordinate_master.py:3479-3523`。
- `export_core_binding()` 导出 slot/interval/signature/family var indices: `src/models/exact_coordinate_master.py:3525-3553`。

**结论:** exact-core overlay 没有发现 ghost NoOverlap 漏接 core interval 的问题。

## 9. 验证命令

```text
sha256sum /mnt/data/zmd_snapshot_2cd169b4.zip
# 2cd169b46a12cc1e52e1915d89279be48fc0f6adbd02b1530d0994d18d1879eb

stat -c '%s %n' data/preprocessed/candidate_placements.json
sha256sum data/preprocessed/candidate_placements.json
# 45773799
# adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0

python -m pytest -q -p no:randomly \
  src/tests/test_master_hint_persistence.py \
  src/tests/test_master_hint_loop_integration.py \
  src/tests/test_solution_hint_malformed_defense.py \
  src/tests/test_community_hint_env_injection.py
# 64 passed in 1.48s

python -m pytest -q -p no:randomly \
  src/tests/test_exact_coordinate_protocol_bounds.py \
  src/tests/test_ghost_anchor_filter.py \
  src/tests/test_coordinate_benders_cut_presence_nogood.py \
  src/tests/test_v62_candidate_frontier_contract.py \
  src/tests/test_v87_terminal_ghost_anchor_validation.py \
  src/tests/test_v88_terminal_ghost_anchor_required.py \
  src/tests/test_v89_terminal_ghost_pick_protocol_validation.py \
  src/tests/test_highs_power_coverage.py \
  src/tests/test_power_placement_subproblem.py \
  src/tests/test_power_witness_cut_dilution.py \
  src/tests/test_v86_terminal_power_witness_validation.py \
  src/tests/test_v87_terminal_power_pole_irredundancy.py
# 74 passed in 1.81s

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored

cd /mnt/data/zmd_r10_orig_subset && patch -p1 --dry-run < /mnt/data/zmd_r10_low_hint_patch.diff
# checking file src/search/master_hint_persistence.py
# checking file src/models/master_model.py
# checking file src/tests/test_master_hint_persistence.py
# checking file src/tests/test_master_hint_loop_integration.py

PYTHONPATH=. python /mnt/data/zmd_r10_work/probes/r10_geometry_probe.py
# key output included in sections 5 and 6
```

Full suite attempt:

```text
python -m pytest -q -p no:randomly src/tests
```

This was attempted, but the sandbox run hit the 900s command timeout after reaching about 16% of the suite and had not reported a failure before timeout. Therefore I am not claiming an all-suite pass for this run.

## 10. 交付物

- `REVIEW.md`: 本文件。
- `zmd_r10_low_hint_patch.diff`: LOW-HINT-R10-01 的 unified diff。
- 代码改动文件:
  - `src/search/master_hint_persistence.py`
  - `src/models/master_model.py`
  - `src/tests/test_master_hint_persistence.py`
  - `src/tests/test_master_hint_loop_integration.py`
