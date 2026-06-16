**段名：任务 A: 验 4 family src 跟 spec 严格一致**

经过对 Phase 1.1 (P1.5-P1.8) 提交的 4 个 Cut Family 源码与 Spec 的严格交叉比对，结论是：**代码实施极其精准，完美契合 Spec 且无妥协。** 具体核对细节如下：

1. **P1.5 F1 region_capacity**:
   - **5 步 Validator**：`validate_region_capacity` 完美实现了独立重算 cap_R (static)、placement_rule 映射校验、cells_per_pose source-of-truth 校验、demand_R 重算以及 witness (demand > cap) 校验。完全符合 v1.2 §7。
   - **Combinatorial Generator**：`generate_region_capacity_cuts` 仅枚举 `left_baseline` 和 `bottom_baseline` 是**完全合理且正确**的。Spec §10 open question #2 和 Phase 1.1 计划明确将 `interior_rect` (需 LP dual cluster) 和 `ghost_complement` defer 到 Phase 1.5+。
   - **GHOST_AGNOSTIC dispatch**：`_build_cut` 中 `ghost_intersects = bool(state.ghost_cells & region_cells)` 的判断极其精准，完美落实了 v1.2 解决 Round 18 致命 Bug 的核心规则。

2. **P1.6 F2 cutset**:
   - **3 步 Validator**：`validate_cutset` 严格执行了 partition disjoint 检查、基于当前 `free_cells` 的 cut_size 重算，以及 demand > cut_size 的 witness 检查。
   - **`_free_cells` 实施**：`all_cells - ghost_cells - cell_owner.keys()` 完美契合 `state_machine_v2` §3 I3 的数学定义。
   - **Oracle Stub**：返回 `[]` 且注释清晰指向 Phase 1.5+ 及 `patch_routing_core`，占位规范。

3. **P1.7 F3 port_exposure + multiset eval**:
   - **`evaluate_literal_multiset`**：这是本次提交的**高光代码**。利用 `collections.Counter` 聚合 cut demand，并与 `state.groups[gid].selected_poses` 进行 Multiset Subset Match，完美实现了 `state_machine_v2` §5 要求的“组内 Slot 匿名性 (Slot Anonymity)”，彻底消除了 10^134 标签对称性。
   - **4 步 Validator**：`validate_port_exposure` 严格校验了 port 归属、front_cell 坐标偏移数学计算、blocking_facility 占位，逻辑严密。
   - **Literal Schema (≥1 vs ≥2) 疑问解答**：这不是 Spec Gap，而是**绝佳的防御性设计**。`lifecycle.py` 作为底层框架，强制 `len(literals) > 0` (≥1) 是因为 F5 (pattern_nogood) 可能存在单 Literal 违规；而 `port_exposure.py` 作为 Family 业务层，在 Validator 中通过 `assert len(cut.literals) >= 2` 强制 F3 必须有 2 个 Literal。**框架宽松 + 业务严格**，此设计非常 Sound。

4. **P1.8 F4 component_reach**:
   - **3 步 Validator**：`validate_component_reach` 严格执行了 disjoint、membership 和 BFS 重算。
   - **Gemini r16 A1 修复**：代码中明确移除了对 `blocking_facilities` pose ID 的校验，并在注释中重申了 "geometric mode only verifies spatial invariants"，完美贯彻了 Geometric 哲学。
   - **BFS Helper**：`_bfs_component` 使用了标准的 4-conn deque BFS，与 D2 separator 逻辑一致，为 Phase 1.5+ 铺平了道路。

5. **FAMILY_VALIDATORS dispatch**:
   - `src/cuts/replay.py` 中 4 个 family 均已正确 register。
   - Round 28 提示的 `EXACT_FAMILY_VALIDATOR_STRICT=1` fail-closed 机制已完美实装。

---

**段名：任务 B: 找 Phase 1.2 P1.11-P1.15 实施盲区**

在 Phase 1.1 坚实落地的基础上，展望 Phase 1.2 (F5-F9) 的实施，存在以下几个需要提前规避的架构/实施盲区：

1. **F5 pattern_nogood (P1.11) - Minimization 与 Cert Hash 的时序盲区**：
   - **盲区**：Spec 提到 F5 会使用 QuickXplain 进行 Literal deletion minimize。由于 `Cut` 对象是 `@dataclass(frozen=True)`，且 `cert_hash` 依赖于 `cert_payload`。
   - **实施提示**：QuickXplain 必须在 Generator 内部、**构建 `OracleCert` 和 `Cut` 对象之前**完成。不能先生成一个大 Cut 再去 mutate 它。Minimize 后的最终 Literals 才能被打包进 Cert 并计算 Hash。`minimization_audit` 字段应在构建最终 Cut 时一并填入。

2. **F6 shape_packing_hall (P1.12) - Hall Condition 的 Cert Schema 盲区**：
   - **盲区**：F6 是 Geometric cut，依赖二分图匹配的 Hall 定理（子集 S 的需求大于其邻域 N(S) 的容量）。目前的 Spec 尚未详细定义 F6 的 `ShapePackingCert` 长什么样。
   - **实施提示**：在 P1.12 实施前，必须先定义好 Cert Schema，至少需要 carry `subset_S_bitset` (需求方区域) 和 `neighborhood_N_bitset` (供给方区域)，以便 Validator 能够独立重算 $|S|$ 和 $|N(S)|$ 并验证 $|S| > |N(S)|$。

3. **F7 power_hitting_set (P1.13) - Causation Split 的 Mode 冲突盲区**：
   - **盲区**：F7 既有 ghost 遮挡导致断电，又有 cell_owner 挤占导致断电。但 `_FAMILY_MODE_MAP` 强制 F7 是 `"literal"` mode。
   - **实施提示**：既然是 Literal mode，F7 的 Cut **不能**在 `geometric_payload` 中携带空间信息。对于 Ghost 导致的断电，必须依赖 `CutScope.ghost_rect_id` 来进行生命周期管理（Ghost 变了 Cut 就 HOLD）；对于 cell_owner 导致的断电，则编码进 `cut.literals`。Validator 验证时要注意区分这两种 Causation。

4. **F8 power_grid_reach (P1.14) - BFS Set 序列化排序盲区 (重申)**：
   - **盲区**：与 F4 类似，F8 也会用到 BFS 寻找连通分量。
   - **实施提示**：Python 的 `Set` 迭代无序。在将 Power Pole 的 Component 写入 Base64 Bitset 或 Tuple 之前，**必须** `tuple(sorted(list_of_poles))`，否则会导致 `cert_hash` 跨 Session 漂移，破坏 Step 10 的去重机制。

5. **F9 density_envelope (P1.15) - Exterior Blocks 遗漏盲区**：
   - **盲区**：F9 降级版只做 Area-based capacity overflow。
   - **实施提示**：在计算 `cap_area` 时，千万不要只减去 `ghost_cells`，必须像 F1 一样减去 `(ghost_cells | exterior_blocks)`，否则在地图边缘的 Density Cut 会出现 Soundness Bug（把不可用的墙体算作了可用面积）。

---

**段名：任务 C: Phase 1.1 verdict**

**Phase 1.1 GO，继续 Phase 1.2 P1.11+。**

**总结**：
Phase 1.1 的 4 个 Family 源码质量极高，不仅严格遵守了 Phase 0 的数学定义与 Soundness 证明，还在工程实现上（如 Multiset Eval、GHOST_AGNOSTIC 判定）展现了极强的鲁棒性。137/137 Tests PASS 证明了底层 Lifecycle 框架与业务 Family 之间的契合度完美。

没有任何阻碍，请直接推进到 Phase 1.2，开始实施 F5 (pattern_nogood) 及后续的 4 个高级 Family。