# 终末地 IndustrialPlanner 精确求解器几何 master round 7 审查报告

审查对象：`zmd_snapshot_38b57070.zip`  
快照 SHA256：`38b570700c77f3f1a7b3f6c2ac7e9c2f2ec6385c7a93c2ee34ca7ce857ab8abe`，已在开工前校验通过。  
仓库根：zip 内 `project/`。  
本轮范围：Q1 F-GM-R6-01 修复确认、Q2 exact-coordinate ghost 矩形编码本体、Q3 solution hint 通道。

## 总结

本轮零 soundness finding。

发现并修复 1 个 LOW availability / robustness 问题：直接 API 或 community hint 合并后传入的 malformed hint（非 int / 越界 pose_idx / 不存在 ghost anchor index）在原始快照的部分路径会在 `solve()` 前抛异常。该问题不会制造 false-FEASIBLE 或 false-CERTIFIED，因为 hint 通道只写入 CP-SAT `solution_hint` proto，不编码约束；但它会让一个本应“只影响速度”的性能提示中断 solve。已提供补丁，将 malformed hint entry 统一降级为 skip。

补丁文件：`zmd_r7_malformed_hint_hardening.patch`。补丁包：`zmd_r7_malformed_hint_hardening_patch.zip`。

## Finding

### F-GM-R7-HINT-01 — LOW availability：malformed direct/community solution hint 可中断 solve，已补丁

Severity：LOW（availability / robustness；非 soundness）。

位置：

- `src/models/exact_coordinate_master.py:6665-6678`：原始 exact hint bucketing 对 known mandatory instance 直接 `int(pose_idx)`，随后用 `self._template_pose_tuple_by_idx[tpl][pose_idx]` 取 tuple；非 int 会 `ValueError`，越界会在 sort / lookup 阶段 `IndexError` / `KeyError`。
- `src/models/exact_coordinate_master.py:6710-6718`：原始 ghost anchor hint 直接 `int(ghost_anchor_hint_idx)`，且不存在的 anchor index 会对所有 `u_var` 写 0 hint。它仍非约束，但属于 malformed hint 未被干净跳过。
- `src/models/master_model.py:11315-11319`：legacy path 对 `pose_idx` 直接 `int()`，非 int 会抛异常。
- `src/search/benders_loop.py:4174-4185`：community hint merge 只做 `int()` 归一化和覆盖，不验证 pose_idx 是否属于该 instance/template；因此 out-of-range community hint 可传播进 exact `apply_solution_hint()`。

复现 probe（原始快照上）：`/mnt/data/zmd_r7_review/probe_results_r7.json` 中 `q3_malformed_hints` 为：

```json
{
  "non_int_existing_instance": "ValueError",
  "out_of_range_existing_instance": "IndexError",
  "unknown_instance": {"hinted_literals": 0, "status": "OPTIMAL"}
}
```

soundness 判读：该问题不改变可行集。exact path 的 `apply_solution_hint()` 只调用 `model.AddHint(...)`，legacy path 也只调用 `self.model.AddHint(var, 1)`；没有 `Add(...)`、`AddBoolOr(...)`、`OnlyEnforceIf(...)` 等约束编码进入 hint path。OR-Tools 9.15 的 `CpModel.add_hint()` 实现仅向 `model_proto.solution_hint.vars/values` append 变量和值。因此 malformed hint 的坏方向是中断 solve，而不是接受非法解。

修法：

- exact mandatory / optional hint：先 `int()`，失败则 skip；再验证 pose_idx 是否存在于 `_template_pose_tuple_by_idx[tpl]`，不存在则 skip。
- exact ghost anchor hint：非 int 或不在 `owner.u_vars` 的 anchor index 直接 skip，不再写全 0 contradictory hint。
- legacy hint：非 int 直接 skip，仍保留未知 instance / out-of-range pose_idx 返回 `None` 后 skip 的原行为。
- 新增 regression：`src/tests/test_solution_hint_malformed_defense.py`。

修复后 probe：`/mnt/data/zmd_r7_review/probe_results_r7_after_patch.json` 中 `q3_malformed_hints` 为：

```json
{
  "non_int_existing_instance": "NO_EXCEPTION",
  "out_of_range_existing_instance": "NO_EXCEPTION",
  "unknown_instance": {"hinted_literals": 0, "status": "OPTIMAL"}
}
```

## Q1：F-GM-R6-01 修复确认

结论：R6-01 的 witness invalidation 修复有效，exact 与 legacy 双路径在成功 cut 后均清除 `_last_solution`、`_solver`、`_status`。cut 失败路径不清 witness，保留既有可用 incumbent。`extract_solution()` 与 `extract_bound_state()` 在 `_solver is None` 后不会静默重建旧解。

核心证据：

- exact cut 成功路径：`src/models/exact_coordinate_master.py:6884-6936`。最终 `model.Add(sum(present_lits) <= len(present_lits) - 1)` 成功后，更新 cut stats，并在 `6933-6935` 清 `owner._last_solution / owner._solver / owner._status`。
- legacy cut 成功路径：`src/models/master_model.py:11900-11944`。先完整解析所有 literals，失败直接 `return False`；成功添加 linear nogood 后，在 `11941-11943` 清 `_last_solution / _solver / _status`。
- exact/legacy 分流：`src/models/master_model.py:11906-11909` 对 exact delegate 透传，其余走 legacy。
- `extract_solution()`：`src/models/master_model.py:11826-11836` 先检查 `_solver is None` 或 status 非 FEASIBLE/OPTIMAL，直接 `{}`；只有通过 gate 才会用 `_last_solution` 或 delegate 读取 solver。
- `extract_bound_state()`：`src/models/master_model.py:11738-11783` 初始化 `lb/ub/gap=None`，`_solver is None` 时直接返回 no-incumbent state。
- `extract_master_hints()`：`src/models/master_model.py:11628-11646` 同样 gate `_solver is None` / status，cut 后不会从旧 solver 提取 hint。

solve 派生字段处置表：

| 字段 / 状态 | 来源 | cut 成功后处置 | cut 失败后处置 | 消费方向判读 |
|---|---|---|---|---|
| `_solver` | `solve()` 在 `src/models/master_model.py:11516` 写入 | exact `6934` / legacy `11942` 清为 `None` | 不清 | 所有 solution/bound 读取都需要 `_solver` gate；清后 loud no-incumbent |
| `_status` | `solve()` 在 `11517` 写入 | exact `6935` / legacy `11943` 清为 `None` | 不清 | status 非 FEASIBLE/OPTIMAL 时 `extract_solution()` 返回 `{}` |
| `_last_solution` | `solve()` 在 `11518` 清空；`extract_solution()` 在 `11832/11835/11886` 缓存 | exact `6933` / legacy `11941` 清为 `None` | 不清 | `_solver` gate 在 cache gate 之前，因此 cut 后不会返回旧 cache |
| `build_stats["last_solve"]` | `solve()` 在 `11519-11605` 写入 telemetry | 未清 | 未清 | stale telemetry，但不是 proof/witness channel；`extract_solution()` / `extract_bound_state()` 不读它。Benders 主循环每轮 cut 后立即 `continue` 重 solve，终态 proof summary 取的是后续 solve telemetry |
| `model.Proto().solution_hint` | 输入 hint，不是 solve witness | cut 时不清；下一次 `solve()` 开头 `11288` 调 `_clear_solution_hints()` 清 | 不清 | 只影响搜索起点；不参与 incumbent extraction |
| `extract_bound_state()` 返回值 | 临时返回，无缓存 | 无需清 | 无需清 | 每次从 `_solver` 现读；无 `_last_bound_state` 类缓存 |
| `extract_master_hints()` 输出 | 临时返回，无缓存；`_maybe_save_hints_to_persistence()` 只在 solve 末尾调用 | 无需清 | 无需清 | `_solver/_status` gate；cut 后若误调也返回 `{}` |
| `_ghost_domains` / `u_vars` / slot maps / intervals | build-time model structure | 不清 | 不清 | 不是 solve 派生；cut 不应破坏模型结构 |
| exact delegate `_ghost_*_stats` / `_coordinate_symmetry_stats` | build-time / tightening telemetry | 不清 | 不清 | 非 witness；不从旧 solver重建解 |
| precompute / feasibility caches（例如 `_exact_candidate_*_cache`） | build/precompute memo | 不清 | 不清 | 不含 solve assignment；不参与 cut 后 extraction |

实证 probe：`/mnt/data/zmd_r7_review/probe_results_r7_after_patch.json`。

关键输出：

```json
"q1_successful_cut_exact": {
  "add_cut_returned": true,
  "solver_is_none": true,
  "status_is_none": true,
  "last_solution_is_none": true,
  "extract_solution_after_cut": {},
  "bound_state_after_cut": {"lb": null, "ub": null, "gap": null, "epsilon_target": null, "prover": "master_cpsat"},
  "resolves_to_different_pose": true
}
```

legacy 同形输出同样为 `solver_is_none/status_is_none/last_solution_is_none=true`。失败 cut probe 对 exact 和 legacy 都为 `add_cut_returned=false`、`solver_retained=true`、`status_retained=true`、`solution_retained=true`。

补充判读：exact cut 在构造 presence literal 时可能先创建等价定义辅助变量，然后遇到某个 conflict member 无法表示而 `return False`；这些辅助定义不添加最终 nogood，不限制原始可行集，且不会清旧 solver/status。legacy path 在添加 bound 前先解析完全部 literal，失败路径无模型 cut mutation。

## Q2：ghost 矩形编码本体

结论：exact-coordinate ghost 编码与项目口径一致。ghost anchor 枚举没有裁掉合法 anchor，也不会引入越界 anchor；ghost 与 placement 的互斥基于 facility body 的 `occupied_cells` footprint，不纳入 port connector；目标 `max_lex(area, min_side)` 不在 CP-SAT 内做加权目标，避免权重溢出；未发现任何 exterior path / connectivity 要求。

### Q2.1 anchor / 尺寸域

- `src/models/exact_coordinate_master.py:3535-3548` 读取 `ghost_rect=(w,h)`；若 `w > grid_w` 或 `h > grid_h`，直接 `model.Add(0 == 1)` fail-closed。
- `3552-3553` 枚举 `anchor_x in range(grid_w - ghost_w + 1)`、`anchor_y in range(grid_h - ghost_h + 1)`，正好覆盖所有使 `[x, x+w)`、`[y, y+h)` 留在 grid 内的 anchor。
- `3558-3565` 记录 ghost cells 和 `_ghost_domains`；`3566-3579` 对每个 anchor 创建 fixed-start、fixed-size、fixed-end optional interval，以对应 `u_var` presence 控制。
- `3583-3597` 对 anchor_filter 排空 / 全排除 fail-closed；`3601` 要求 `AddExactlyOne(u_vars)`。

没有发现 false-FEASIBLE 方向：越界 anchor 不会生成。没有发现 false-INFEASIBLE 方向：无 filter 时完整枚举；有 filter 时只按显式 filter 缩域，空 filter 明确 INFEASIBLE。

### Q2.2 ghost × placement 互斥口径：body-only

- `src/models/exact_coordinate_master.py:962-976` 从 pose 的 `occupied_cells` 计算相对 body cells；未读取 `input_port_cells` / `output_port_cells` 作为 body。
- `978-987` 从 `occupied_cells` 计算 footprint bounds。
- `1553-1616` 为每个 pose index / mode 建立 `ModeRectDomain`，footprint width/height 来自 `occupied_cells` bounds。
- `2353-2476` 将选中 slot 的 footprint start/end/width/height channel 到 interval；optional slot 使用 active literal optional interval。
- `2509-2587` 对稀疏 `(x,y,mode)` 域添加 `AddAllowedAssignments`，避免 bbox-domain 留进非法 anchor/mode 组合。
- `3602-3605` 用 `AddNoOverlap2D([core intervals] + [ghost intervals])` 统一互斥 facility body footprint 与 ghost rectangle。

候选文件核验：`data/preprocessed/candidate_placements.json` SHA256 为 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`，与任务给定一致。抽样/全量 footprint 汇总保存在 `/mnt/data/zmd_r7_review/ghost_footprint_summary.txt`。全量结果：

| template | poses | body footprint | rectangular | port cells in occupied body |
|---|---:|---|---|---:|
| `boundary_storage_port` | 134 | `(1,3)` 67 个；`(3,1)` 67 个 | yes | 0 |
| `power_pole` | 4,761 | `(2,2)` | yes | 0 |
| `protocol_storage_box` | 4,624 | `(3,3)` | yes | 0 |
| `protocol_core` | 6,728 | `(9,9)` | yes | 0 |
| `manufacturing_3x3` | 17,408 | `(3,3)` | yes | 0 |
| `manufacturing_5x5` | 16,368 | `(5,5)` | yes | 0 |
| `manufacturing_6x4` | 16,380 | `(6,4)` / `(4,6)` | yes | 0 |

逐类别判读：boundary 1x3 / 3x1 仅三格 body 进入互斥；pole 2x2 仅四格 pole body 进入互斥；protocol storage box 3x3、protocol core 9x9、manufacturing 系列均为 body rectangle。port connector / terminal front 不进入 ghost 互斥，因此 connector 伸进 ghost 不会被 master ghost constraint 禁止。若未来引入非矩形 body，当前实现按 PROJECT_LOCK 接受的保守 bbox 口径处理，可能 false-INFEASIBLE（洞内 ghost 被 bbox 挡住）但不会 false-FEASIBLE。

### Q2.3 max_lex(area, min_side)

未发现 CP-SAT 加权单目标编码。outer/frontier 枚举固定 ghost size，master 只做该 `(w,h)` 的可行性。

- `src/search/certified_frontier.py:53-94` 生成 oriented candidate sizes，`77-78` 用 `min_side` 作为 admissibility lower bound。
- `candidate_objective()` 在 `163-165` 返回 Python tuple `(area, min(w,h))`。
- `candidate_sort_key()` 在 `168-172` 返回 `(-area, -min_side, -max_side, -ghost_w)`；area 严格优先，min_side 次之，后两项仅 deterministic order。
- `compute_terminal_frontier_projection()` 在 `216-221` 用 tuple objective 比较剪枝，`238` 按 objective reverse 排 frontier。
- `src/search/exact_campaign.py:1271-1272` 的 final objective 同样是 `(w*h, min(w,h))`。
- `src/search/exact_campaign.py:1660-1666` 验证 final result 不低于 canonical `min_side_admissibility`。
- `src/search/exact_campaign.py:517-538` 从 `canonical_rules.globals.empty_rectangle` 加载 objective 与 `min_side_admissibility`，要求 positive。

因此不存在 weighted objective overflow / area 被 min_side 权重反超的风险。`min_side >= 6` 是 candidate generation / final validation 的 admissibility，不是 tie-break。

### Q2.4 禁区：exterior path

PROJECT_LOCK 明确：`PROJECT_LOCK.md:110` 允许 fully enclosed legal empty rectangle，`PROJECT_LOCK.md:230` 禁止给 ghost 加 exterior-path requirement。代码搜索 `ghost.*(path|connect|reach|component|flood|exterior)`、`exterior`、`connectivity` 等，在 `exact_coordinate_master.py` 的 ghost enforcement 中没有发现 exterior reachability / connectivity / path 变量或约束。现实现 ghost 相关硬约束是 anchor exactly-one 与 body no-overlap，另有 ghost-conditioned capacity/signature tightening，但它们不是外部连通约束。

## Q3：solution hint 通道

结论：hint 通道本体不约束可行集。原始 malformed direct hint 会造成 availability 异常，已补丁改为 skip；错误但类型/范围合法的 hint 只影响搜索起点，不改变结论。cut 后重 solve 会清旧 model hint proto；旧 hint 不会自动粘在模型上。

### Q3.1 hint 永不约束

- exact path：`src/models/exact_coordinate_master.py:6654-6730` 只调用 `self.model.AddHint(...)`。
- legacy path：`src/models/master_model.py:11314-11320` 只调用 `self.model.AddHint(var, 1)`。
- 每次 solve 前：`src/models/master_model.py:11259-11265` 清 `solution_hint` proto；`11288` 在 solver 构造前调用。
- OR-Tools 9.15 `CpModel.add_hint()` 本地实现：`/opt/pyvenv/lib/python3.13/site-packages/ortools/sat/python/cp_model.py:1655-1661` 只向 `model_proto.solution_hint.vars/values` append。

错误 hint 实证：构造 2×1 toy，mandatory body 固定占 `(0,0)`，`ghost_rect=(1,1)`。合法 ghost 只能选 anchor `(1,0)`。故意传 `ghost_anchor_hint_idx=0`，即提示选与 body 重叠的 ghost anchor。结果：no-hint 与 bad-hint 均 `OPTIMAL`，最终 ghost anchor 均为 `{x:1,y:0}`；bad hint 被记录为 applied，但不约束解。

probe 输出：

```json
"q3_bad_hint_is_non_binding": {
  "no_hint_status": "OPTIMAL",
  "bad_hint_status": "OPTIMAL",
  "no_hint_ghost_anchor": {"x": 1, "y": 0},
  "bad_hint_ghost_anchor": {"x": 1, "y": 0},
  "bad_hint_build_stats": {"ghost_anchor_hint_applied": true, "ghost_anchor_hint_idx": 0}
}
```

### Q3.2 community hint merge 语义

`src/search/benders_loop.py:4148-4185`：先取 greedy warm-start dict，再加载 `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH` JSON；逐 `inst_id -> pose_idx` 做 `int()` 归一化，community 在 key overlap 上覆盖 greedy，并统计 override/addition。合并粒度是 instance/solution id，不是 `(slot.x, slot.y, mode)` 的半变量粒度；exact delegate 再按 group/template 排序后对 slot 写完整三元组 hint（x/y/mode），residual optional 额外写 active。即使 community 覆盖造成 hint 自相矛盾，CP-SAT 也只是把它当 search guidance；不会形成约束。

### Q3.3 malformed hint 防御

原始状态：unknown instance 已 skip；非 int existing instance / out-of-range existing pose 可能异常中断 solve；community loader 非 int 会 skip，但 out-of-range int 会传播到 exact hint application。见 Finding F-GM-R7-HINT-01。

补丁后：

- unknown instance：skip，`hinted_literals=0`，solve 正常。
- non-int pose_idx：skip，solve 正常。
- out-of-range pose_idx：skip，solve 正常。
- nonexistent ghost anchor idx：skip，`ghost_anchor_hint_applied=false`，solve 正常。

这把 malformed hint 的失败方向统一为“丢 hint 继续”，避免性能 hint 中断 certified solve。

### Q3.4 hint × cut 交互

cut 成功后模型新增 nogood 并清 `_solver/_status/_last_solution`；旧 hint proto 本身不在 cut 点清除，但下一次 `solve()` 的第一步会 `_clear_solution_hints()`。因此：

- 如果 caller 不再传旧 hint，旧 hint 不会粘在下一次 re-solve 上。
- 如果 caller 主动再次传入刚被 cut 禁掉的 hint，它仍只是 infeasible/poor search guidance，不会约束模型；CP-SAT 会寻找满足新 cut 的解或证明 infeasible。
- `build_stats["last_solve"]` 中 hint stats 会保留为 telemetry，但不参与 extraction/proof witness。

## 测试与命令

环境：Python 3.13.5；依赖从 `zmd_py313_linux_x86_64.zip` 离线安装；OR-Tools 9.15.6755。

执行过：

```bash
sha256sum /mnt/data/zmd_snapshot_38b57070.zip
python -m pip install --no-index --find-links "$WHEEL_DIR" -r requirements.lock.txt -r requirements-dev.lock.txt
python -m pytest -q -p no:randomly \
  src/tests/test_master_cut_solution_invalidation.py \
  src/tests/test_coordinate_benders_cut_presence_nogood.py \
  src/tests/test_ghost_anchor_filter.py \
  src/tests/test_community_hint_env_injection.py \
  src/tests/test_exact_contract.py::test_generate_candidate_sizes_orders_by_area_then_min_side \
  src/tests/test_solution_hint_malformed_defense.py
python scripts/check_p1_2_proof_obligations.py
python /mnt/data/zmd_r7_review/probes_r7.py
```

结果：

- targeted regression：`37 passed in 1.68s`。
- proof obligations：`P1.2 proof obligation check passed: 8 obligations anchored`。
- custom probes：Q1 exact/legacy cut invalidation、failed cut witness retention、Q3 bad hint non-binding、malformed hint after patch 均符合预期。
- full `python -m pytest -q -p no:randomly src/tests` 尝试运行过一次，但沙盒 300s 超时，进度约 14%，超时前未打印 failure；未声称全量完成。

## 交付物

- Review：`REVIEW.md`
- Unified diff：`zmd_r7_malformed_hint_hardening.patch`
- Patch zip：`zmd_r7_malformed_hint_hardening_patch.zip`
