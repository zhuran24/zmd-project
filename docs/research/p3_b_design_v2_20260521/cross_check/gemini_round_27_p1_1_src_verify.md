**段名：任务 A: 验 src 跟 v3.2.2 spec 严格一致**

经过严格比对 `src/cuts/lifecycle.py` 与 Phase 0 Final Spec，一致性极高，具体核对结果如下：

1. **CutScope.exterior_blocks_hash 字段 & Step 3 dispatch**：**完全一致**。
   - 代码中 `step_6_attach_scope_check` 完美实现了 v3.2.2 的 dispatch 逻辑：`is_ghost_agnostic` 为 True 时仅校验 `exterior_blocks_hash`，否则校验全量 `blocked_cells_hash`。
   - 测试用例 `test_attach_scope_ghost_agnostic_passes_when_exterior_unchanged` 和 `test_attach_scope_ghost_agnostic_quarantine_when_exterior_changed` 精准覆盖了跨 ghost 复用的存活与隔离边界。未漏 edge case。
2. **9-family map (`_FAMILY_MODE_MAP`)**：**完全一致**。
   - 准确移除了 PoC 阶段的 `symmetry_lift`。
   - F1, F2, F4, F6, F8, F9 均正确映射为 `"geometric"`。
   - F3, F5, F7 均正确映射为 `"literal"`。
   - 强校验 `mode == "literal" and not has_lit` 等逻辑确保了契约的执行。
3. **`__post_init__` schema-first 强制**：**极其严格且正确**。
   - `has_lit == has_geo` 触发 ValueError，完美实现了 XOR 互斥。
   - 校验了 family 必须在 9-family map 中。
   - 强制 `self.scope is None` 和 `self.cert is None` 抛错，确保 Cut 对象生成即完整。
4. **Step 5 F1 validator**：**完全一致 (v1.2)**。
   - `blocked_in_region = (state.ghost_cells | state.exterior_blocks) & region_set` 严格遵循了 v1.2 的 static `cap_R` 定义（不减 `cell_owner`）。
   - `cells_per_pose` 的 source-of-truth 校验（防 source rotated）和 `demand_R > cap_R` 的 witness check 均已精确实现。
5. **Step 2 / Step 8 stub**：**措辞清晰，指针准确**。
   - 明确指向了 "Phase 1.1 P1.11 (F5 pattern_nogood)" 和 "Phase 1.3 P1.21 (benders_loop integration)"，为后续开发留下了清晰的锚点。

---

**段名：任务 B: 找 Phase 1 实施盲区**

在 P1.1 的框架基础上，展望 P1.2 - P1.4 的实施，发现以下几个工程与架构上的实施盲区（非当前代码 Bug，而是下一步的防坑提示）：

1. **`ASSUMPTION_VERIFIERS` 的函数签名与上下文盲区 (P1.4)**：
   - 当前签名是 `Callable[[BState, str], bool]`。但在 P1.4 真正实现 `_verify_boundary_saturation` 时，验证器需要读取 `canonical_rules` 的具体内容（例如判断 left_baseline 的 demand 是否真的是 46）。
   - **盲区**：目前的 `BState` 仅持有 `artifact_hashes`，不持有 rules 的内存对象。P1.4 实施时，要么需要将 `canonical_rules` 注入到 Verifier 的上下文中，要么 `BState` 需要持有 parsed rules 的只读引用，否则 Verifier 无法进行实质性的 source-of-truth 校验。
2. **`run_lifecycle` helper 的生命周期 (P1.2+)**：
   - **盲区**：正如你所预料，`run_lifecycle` 是一个同步的、端到端的 9 步直通车。在 P1.2 引入 `CutStore` 和 P1.21 引入 CP-SAT hook 后，Cut 的生成（Step 1-3）和 Cut 的回放/应用（Step 4-8）在时间线上是完全解耦的。
   - **建议**：在 P1.2 落地后，`run_lifecycle` 应该被移出 `src/cuts/lifecycle.py` 的 production 代码，降级并迁移到 `src/tests/fixtures/` 中，仅作为测试框架的 utility 使用，防止业务代码误调用同步链路。
3. **`AnonymousSlotRef` 与 `BState` 扩展时的 Multiset 语义盲区 (P1.7/P1.11)**：
   - 当前 `BState` 的 `selected_poses` 简单定义为 `List[Tuple[GroupId, int]]`。
   - **盲区**：在 P1.7/P1.11 实施 `evaluate_cut_literal_based` 时，必须严格遵循 `state_machine_v2.md` §5 的契约——**跨 Group Permutation Soundness**。即验证时必须将 `selected_poses` 转换为 Counter (Multiset) 进行子集包含判定，而**绝对不能**依赖 `slot_index` 的绝对位置进行 1对1 匹配。实施 Step 7 的 literal 分支时需极度小心此处的数学语义。

---

**段名：任务 C: P1.1 verdict**

无 finding，P1.1 GO。

**总结**：P1.1 的代码完美继承了 Phase 0 历经 22 轮锤炼的所有核心 Invariant（特别是 v3.2.2 的 Hash Dispatch 和 v1.2 的 Static Cap）。测试覆盖率极高，边界清晰。带着这份坚实的基座，请放心推进到 P1.2 (CutStore + 6 维 watcher)！