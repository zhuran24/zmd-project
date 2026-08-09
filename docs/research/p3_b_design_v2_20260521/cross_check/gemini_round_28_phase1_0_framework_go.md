**段名：任务 A: 验 src 跟 v3.2.2 spec 严格一致**

经过对 Phase 1.0 框架 4 件核心源码的严格比对，代码与 B Design v2 Phase 0 Final Spec 保持了极高的一致性，具体核对结果如下：

1. **P1.2 `src/cuts/store.py` (CutStore)**：**完全一致**。
   - **6 维 watcher**：`by_cell`, `by_group`, `by_pose`, `by_commodity`, `by_region`, `by_ghost` 全部精确定义。
   - **GHOST_AGNOSTIC 排除**：`add_cut` 中明确判断 `if ghost_id != GHOST_AGNOSTIC` 才加入 `by_ghost_watcher`，严格遵循 §7 footnote。
   - **Quarantine 终态**：`hold_cut` 拦截了已 quarantine 的 cut，`on_ghost_rect_changed` 遍历时也主动 `continue` 跳过 quarantine 状态，确保其不参与 active 传播。
   - **状态机流转**：`on_ghost_rect_changed` 的 4 个分支（旧 ghost 移入 held；新 ghost 跑 replay 后分发 ATTACH/HOLD/QUARANTINE）逻辑完美闭环。
2. **P1.3 `src/cuts/replay.py` (replay_cut)**：**完全一致**。
   - **6 步 verify**：完美 delegate 给 `lifecycle.step_6_attach_scope_check`，保持了 pure function 与 side-effect 的清晰边界。
   - **Post-attach validation**：通过 `FAMILY_VALIDATORS` 字典实现了 family-dispatched，当前仅 F1 wired，符合 Phase 1.0 进度。
   - **Fail-closed**：`unsound`, `timeout`, `schema_err` 被精准映射为 `post_attach_validation_unsound` 等 reason code，并调用 `store.quarantine_cut`，严格遵守 PROJECT_LOCK §3A。
3. **P1.4 `assumptions/verifiers.py`**：**修 Round 27 B1 finding 完全正确**。
   - `BState` 成功注入了 `canonical_rules` 字段。
   - `verify_placement_rule` 和 `verify_boundary_saturation` 均实现了 `if rules is None: return False` 的 fail-closed 逻辑。
   - `lifecycle.py` 中的 `assumption_holds` 采用了 lazy import `lookup_verifier`，优雅解耦了循环依赖。
4. **P1.4 `helpers` 算法**：**Sound 且与 Spec 一致**。
   - **`ghost_geometry.py`**：Liang-Barsky 裁剪算法实现极其标准。完美 cover 了退化线段 (`dx==0 and dy==0`)、端点 inside、平行边外 reject 等 edge case。`cell_aabb_from_rect` 加 1.0 转换为 float 边界的做法在 grid 坐标系下是绝对 sound 的。
   - **`baseline_partition.py`**：严格移除了 `cell_owner`，仅依赖 `ghost_cells | exterior_blocks`，彻底修复了 Gemini round 14 finding #2 的跨层 quarantine 致命 Bug。
   - **`power_network.py`**：`_canonical_edge` 保证了无向图边去重，`build_power_network` 严格调用了 Liang-Barsky AABB 检查，BFS 连通性算法标准无误。

---

**段名：任务 B: 找新 finding (P1.5+ 实施盲区提示)**

Phase 1.0 框架已极其坚固，但在向 Phase 1.1+ (P1.5-P1.18) 推进并接入具体 Family Validator 时，存在以下几个工程实施盲区（非当前 Bug，为防坑提示）：

1. **`replay.py` 中 `FAMILY_VALIDATORS` 的静默跳过陷阱 (P1.5+ 漏注册风险)**：
   - **盲区**：在 `replay_cut` 中，如果 `canonical_rules` 不为 None（即 P1.4 之后框架已解锁），但 `validator = FAMILY_VALIDATORS.get(cut.family)` 找不到对应的 validator，代码会直接 `store.reactivate_cut(cut.cut_id)` 并返回 `"ATTACH"`。
   - **风险**：在 P1.5+ 开发中，如果开发者写完了 F2 的 validator 但**忘了**在 `FAMILY_VALIDATORS` 字典中注册，F2 的 cut 将会静默跳过 Step 7 验证直接生效。这违背了 fail-closed 原则。
   - **建议**：在 P1.5 之后，可以加一个防御性断言：`if cut.family in _FAMILY_MODE_MAP and validator is None: raise NotImplementedError(f"Forgot to register {cut.family} validator?")`。
2. **`assumptions/verifiers.py` 的扁平命名空间冲突风险**：
   - **盲区**：`_VERIFIERS` 是一个全局扁平字典。如果 F2 和 F4 的开发者碰巧都注册了一个名为 `boundary_shape` 的 assumption，但两者的校验逻辑不同，后注册的会静默覆盖前者。
   - **建议**：在 P1.5+ 各 family 注册 verifier 时，强制要求 key 带有 family 命名空间前缀（例如 `F2:boundary_shape`），或者在 `register_verifier` 中加入 `if key in _VERIFIERS: raise ValueError("Duplicate verifier key")` 的防重保护。
3. **`CutStore` 中 `held` 集合的内存泄漏隐患 (P1.22 Ramp 预警)**：
   - **盲区**：`store.py` 中，`quarantined` 的 cut 会被从所有 watcher 中 `_unregister_from_watchers`，这很好。但是，`held` 状态的 cut 依然留在 `by_ghost_watcher` 中。如果某个 ghost 形状在后续的 168h 搜索中**再也没有出现过**，这些 held cuts 将永远驻留在内存中无法被释放。
   - **建议**：这印证了 Phase 1.3 P1.22 计划中 "capacity-based eviction (LRU)" 的绝对必要性。在实现 P1.22 时，必须确保 LRU 淘汰机制能够清理长期不活跃的 `held` cuts。
4. **`power_network.py` BFS 返回 `Set` 的序列化不确定性**：
   - **盲区**：`bfs_component` 返回的是 `Set[Pole]`。Python 的 Set 迭代顺序是随机的。
   - **建议**：在 P1.14 实施 F8 Generator 时，务必记得在将 component 写入 `PowerGridReachCert` 之前调用 `tuple(sorted(pc_component))`，否则会导致 `cert_hash` 跨 Session 不稳定（Spec §3 中已标明 `tuple(sorted(...))`，实施时切勿遗漏）。

---

**段名：任务 C: Phase 1.0 framework verdict**

**Phase 1.0 GO，继续 Phase 1.1 P1.5 (Family 1)。**

**总结**：
4 件核心源码（`store.py`, `replay.py`, `verifiers.py`, `helpers`）的实现质量极高，不仅完美契合了 v3.2.2 的复杂状态机与 Dispatch 逻辑，还在几何算法（Liang-Barsky）和图论算法上展现了扎实的工程功底。Round 27 的历史遗留问题已被彻底清零。

基座已成，请放心进入 Phase 1.1，开始逐个击破 Family 1-4 的 Validator 与 Oracle 实施！