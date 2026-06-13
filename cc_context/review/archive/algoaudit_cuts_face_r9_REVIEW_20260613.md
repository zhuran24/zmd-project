# 终末地 IndustrialPlanner cuts 面 r9 审查报告

## 0. 输入校验

只使用题面指定快照：`/mnt/data/zmd_snapshot_13fbe643.zip`。

sha256 校验结果：

```text
13fbe6432947212e62304ddd2c7f199b7e4c3b0bb81e01ed3f9ff6ffe20e7430  /mnt/data/zmd_snapshot_13fbe643.zip
```

与题面给定值一致。文件区其它快照未使用。

## 1. 总结结论

本轮不是零 finding。发现 1 个 HIGH soundness finding，已给出修复补丁和回归测试。

R8 的 support-augmented conflict set 修复本身，在本轮按 Q1 四个角度审查后，没有发现残留 CUT-R8-H1 同类缝隙。新的问题来自 Q2 自由攻击角：`D2CommodityFlowCore` 的模型不是 production routing 的严格 relaxation，因此不能单独把 D2 `INFEASIBLE` 升级成 master no-good cut。原 separator 会在 D2 `INFEASIBLE` 且 core 非空时直接写 cut，存在 over-cut 风险。

补丁采取 fail-closed 策略：D2 只在同一 `occupied grid + port_specs` 已被 production routing precheck 判为 `front_blocked` 或 `relaxed_disconnected` 时，才允许继续作为 cut separator。否则 D2 可以作为诊断，但不再是 master-cut proof source。

## 2. Finding

### CUT-R9-H1: HIGH: D2 core 不是 production routing relaxation，原 separator 可对 production-feasible layout 写 master cut

位置：

- 原快照 `src/search/d2_separator.py:10-13`：文档前提声明 D2 是 production C2 routing 的 relaxation。
- 原快照 `src/search/d2_separator.py:188-258`：`run_d2_separation()` 由 placement 编译 `occupied`，D2 `INFEASIBLE` 且 raw core 非空后，直接构造 support-augmented `conflict_set` 并调用 `master_delegate.add_benders_cut(conflict_set)`。
- 原快照 `src/models/d2_commodity_flow_core.py:129-133`：D2 对同一 2D cell 的全部 commodities 加 `AddAtMostOne`。
- 原快照 `src/models/d2_commodity_flow_core.py:195-215`：D2 使用单位流守恒编码 terminal balance。

问题：

R8 修复解决的是“D2 proof context 中的常量障碍和非 core terminals 没有进入 master cut”的问题。但即使 support set 覆盖完整，如果 D2 模型本身比 production routing 更严格，D2 `INFEASIBLE` 也不能推出 production routing `INFEASIBLE`。此时 support-augmented cut 仍会禁止一个本可被 production routing 接受的 layout。

复现攻击 1：两层 crossing。

构造一条横向走廊和一条纵向走廊，只在中心 2D cell 相交。production routing 支持 ground/elevated bridge，可让两条不同 commodity 的线在同一 2D cell 跨层通过，因此 routing 可行。D2 只有 2D cell capacity，`sum_k u[k,c] <= 1`，会拒绝该交叉。

实证结果：

```text
production precheck: feasible
RoutingSubproblem: FEASIBLE
raw D2CommodityFlowCore: INFEASIBLE
原 run_d2_separation(): cut_added=True, conflict_set 包含 h_src/h_sink/v_src/v_sink/wall
```

复现攻击 2：splitter topology。

构造一个 T/Y 形通道，一个 `ore` out port 供给两个 `ore` in ports。production routing 可用 splitter/merger 拓扑表达一源多汇，因此 routing 可行。D2 使用单位流守恒，无法表达 splitter 分叉，判 `INFEASIBLE`。

实证结果：

```text
production precheck: feasible
RoutingSubproblem: FEASIBLE
raw D2CommodityFlowCore: INFEASIBLE
```

新增回归覆盖：

- `src/tests/test_d2_separator_support_context.py:137-201`：两层 crossing probe 构造。
- `src/tests/test_d2_separator_support_context.py:203-263`：splitter probe 构造。
- `src/tests/test_d2_separator_support_context.py:285-300`：证明 raw D2 会 reject。
- `src/tests/test_d2_separator_support_context.py:302-321`：production-feasible crossing 下 separator 必须拒绝写 cut。
- `src/tests/test_d2_separator_support_context.py:323-342`：production-feasible splitter 下 separator 必须拒绝写 cut。

修法：

- `src/search/d2_separator.py:10-15`：删除“D2 是 production routing relaxation”的安全前提，改为 D2 cut 只能在 production routing precheck 已证明同一上下文不可行时发出。
- `src/search/d2_separator.py:51-69`：`_placement_to_occupied()` 显式跳过 `ghost_pick`，与 support tuple 及 production routing 口径一致。
- `src/search/d2_separator.py:172-192`：新增 `_d2_precheck_status_for_cut_context()`，对同一 `occupied + port_specs` 跑 production routing precheck。
- `src/search/d2_separator.py:219-257`：无 owner port spec fail-closed；precheck 不是 `front_blocked` 或 `relaxed_disconnected` 时返回 `MODEL_INVALID`，不 build D2，不写 cut。
- `src/search/d2_separator.py:322-325`：写 cut metadata 时记录 `routing_precheck_status` 和 `routing_precheck_domain_stats`。

补丁文件：`d2_separator_r9.patch`。

## 3. Q1: CUT-R8-H1 修复确认

### 3.1 support 集合完备性

审查对象：

- `_placement_to_occupied()`：`src/search/d2_separator.py:51-69`
- `_build_occupancy_support_pose_terms()`：`src/search/d2_separator.py:94-131`

比对结论：修复后同口径。

逐条件比对：

- pool 取法：两者均由 `facility_type` 查 `facility_pools`。
- `pose_idx` 边界：两者均排除负数和超出 pool 长度的 pose。
- `occupied_cells`：两者均只由选中 pose 的 `occupied_cells` 得到贡献；support 只纳入非空 footprint owner。空 footprint 没有进入 D2 常量障碍，不进 support 只会保持精度，不会扩大 cut。
- `facility_type` 缺失：两者都落到空 pool，不贡献 occupied cells，也不进入 support。
- `ghost_pick`：补丁前 `_placement_to_occupied()` 没有显式 skip，support 有 skip。当前工件中 `data/preprocessed/candidate_placements.json` 没有 `ghost_rect` pool，实际不会让 ghost footprint 进入 D2；补丁仍把 `_placement_to_occupied()` 改为显式 skip，关闭未来数据形态变化带来的口径分叉。

本项结论：没有发现“贡献了 occupied cells 但 support 漏掉”的残留 CUT-R8-H1 缝。多纳入 support 只会弱化 cut，不是 soundness 问题。

### 3.2 非 core terminal owners 并入的必要性与充分性

审查对象：

- `_build_pose_assumptions_for_owners_with_ports()`：`src/search/d2_separator.py:72-91`
- `D2CommodityFlowCore.build()` terminal 处理：`src/models/d2_commodity_flow_core.py:151-193`

结论：非 core terminal owners 并入是必要的，补丁后 sufficient。

D2 对有 owner assumption 的 ports 使用 assumption literal 保护 terminal contribution，并且会把 `u[k,front_cell] == 1` 放在 owner assumption guard 下。raw UNSAT core 只会返回 solver 认为必要的一部分 owner literals，但其它 port owners 仍在当前模型中以 helper literals 参与 terminal context。因此把 assumptions 全集并入 conflict set 是必要的。

潜在第三形式是 `D2CommodityFlowCore` 里 owner 没有 assumption 时的 unconditional contribution 分支。补丁在 separator 层加入无 owner port spec fail-closed，返回 `unowned_port_spec_not_certified_for_d2_cut`，不再允许该第三形式进入 master cut proof path。

`blocked_port_count` 只是 D2 统计和 relaxation 侧效果，不生成更严格 terminal obligation。它被 D2 忽略会让模型更松，不会造成 over-cut。

### 3.3 cut 形态对接

审查对象：

- `_build_d2_supported_conflict_set()`：原快照 `src/search/d2_separator.py:120-144`，补丁后同函数逻辑未变。
- `master_delegate.add_benders_cut(conflict_set)` 调用：补丁后 `src/search/d2_separator.py:332-356`。
- master delegates：`src/models/exact_coordinate_master.py`、`src/models/pose_bool_exact_master.py`、`src/models/master_model.py`。

结论：dict 合并方向不构成 over-cut，presence-nogood 语义对接正确。

`conflict_set` 合并顺序为 assumptions 全集、occupancy contributors、raw core。raw core 来源于同一轮 assumptions，因此正常路径下同一 `instance_id` 的 `pose_idx` 恒一致。即便异常数据把 `pose_idx` 推成 `-1`，master 侧 cut 添加函数会拒绝或 fail-closed，不会生成更强的合法 cut。

三个 master cut 接口语义均是 presence conjunction no-good，即禁止 conflict set 中所有 `instance_id: pose_idx` 同时出现。这与“禁止该 D2/precheck support tuple 共现”的 intended semantics 一致。

### 3.4 fail-closed 行为维持

结论：维持，并新增一层 gate。

原有路径中 D2 `FEASIBLE`、`UNKNOWN`、`ERROR`、empty core、`master_add_cut_error` 均不写 cut。补丁新增：production precheck 非 `front_blocked` 或 `relaxed_disconnected` 时返回 `MODEL_INVALID`，不 build D2，不写 cut。metadata `support_conflict_size` 与 `support_owners` 仍直接取最终 `conflict_set`，不是估计值。新增 `routing_precheck_status` 和 `routing_precheck_domain_stats` 可追踪 gate 依据。

## 4. Q2: 自由攻击角

### 4.1 D2 relaxation 方向

选点理由：题面明确提示“D2 比 production 更松之外是否存在更严编码点”。这是 cut soundness 的根前提，比 core support 完备性更底层。

攻击过程：构造两个 production routing 可行但 D2 不可行的小模型：两层 crossing 和 splitter topology。两者都通过 production precheck 与 `RoutingSubproblem`，但 raw D2 判 `INFEASIBLE`。该攻击确认原 D2 separator 不能单独作为 proof source。

结论：成立，HIGH，已修。

### 4.2 benders_loop D2 rung wiring

选点理由：即使 separator 修好，如果上层状态机在错误 precheck 状态调用或 cut 成功后错误 skip 其它通道，也可能形成剪枝漏洞。

审查位置：`src/search/benders_loop.py:5381-5445`。

结论：当前上层只在 `precheck_status == "front_blocked"` 下调用 D2 rung。这个调用条件本身把 D2 限在 production precheck 已拒绝的上下文内，能遮住本轮 finding 的一部分 runtime 风险。补丁把相同 gate 下沉到 `run_d2_separation()`，使 standalone separator 也 fail-closed。D2 成功后 `_b1_d2_skip_other_cuts=True` 只跳过更慢的 fallback cut 通道；在新 gate 下，该 skip 不扩大 proof 范围。

## 5. 验证命令与结果

环境：Python 3.13，离线安装 `/mnt/data/zmd_py313_linux_x86_64.zip` wheels。

已执行：

```bash
python -m py_compile src/search/d2_separator.py src/tests/test_d2_separator_support_context.py
PYTHONPATH=. python -m pytest -q \
  src/tests/test_d2_separator_support_context.py \
  src/tests/test_benders_cut_condition_lits.py \
  src/tests/test_coordinate_benders_cut_presence_nogood.py \
  src/tests/test_routing.py::test_port_balance_analysis_identifies_dead_end_and_split_merge_needs \
  src/tests/test_routing.py::test_terminal_aware_peeling_prunes_non_terminal_dead_end_branch \
  -p no:randomly
PYTHONPATH=. python scripts/check_p1_2_proof_obligations.py
```

结果：

```text
11 passed in 1.72s
P1.2 proof obligation check passed: 8 obligations anchored.
```

单跑 D2 support-context 专项：

```bash
PYTHONPATH=. python -m pytest -q src/tests/test_d2_separator_support_context.py -p no:randomly
```

结果：

```text
4 passed in 0.39s
```

全量测试尝试：

```bash
PYTHONPATH=. python -m pytest -q src/tests -p no:randomly
```

结果：沙盒 600 秒超时，停在约 14% 进度，未完成。因此本报告不声称全量 `src/tests` 全绿。

## 6. 补丁摘要

补丁文件 `d2_separator_r9.patch` 是从干净解包目录 `/mnt/data/zmd_orig/project` 到修复目录 `/mnt/data/zmd_r9/project` 的 unified diff，LF 行尾。

变更文件：

- `src/search/d2_separator.py`
- `src/tests/test_d2_separator_support_context.py`

核心策略：

1. D2 separator 不再声称 D2 本身是 production routing relaxation。
2. D2 cut 只在 production routing precheck 已经对相同上下文给出不可行状态时发出。
3. 无 owner terminal contribution 在 separator cut path fail-closed。
4. `ghost_pick` 在 D2 occupied 编译中显式跳过。
5. 新增两类 production-feasible 但 raw-D2-infeasible 反例回归，确保 separator 不写 cut。
