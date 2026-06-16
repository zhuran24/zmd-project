## Round 2 Verdict
**NOT_GO**

## Round 1 Fix Verification

- **BLOCKER (union semantics): PARTIAL / NEW_GAP**
  - **推理**: 你将 sum 改为 union (`occupied_cells.add(cell)`) 确实修复了跨 pose 共享 cell 导致的 double-counting 问题，大方向与 evaluator 的 `cell_owner` 去重逻辑对齐。**但是**，你的 union 逻辑只检查了 `if cell in window_cells`，漏掉了 evaluator 的另一个隐含物理约束：`cell_owner` 永远不会包含 ghost cells 或 exterior blocks。这导致了一个新的 divergence（详见下方 New Finding #2）。
- **HIGH #2 (total instances): CORRECT**
  - **推理**: 增加 `len(pairs) > group_demand` 成功阻挡了 attacker 用海量 distinct poses 堆砌面积的攻击。
  - *Sanity check (Prompt Q C/4)*: 修复正确且没有 reject sound case。当 total <= demand 满足时，任何单个 pose 的 count 必然 <= demand，因此下方的 per-pose check 实际上在数学上已经 redundant（但保留无害）。允许 witness 中 pose 互相 overlap 也是 sound 的，因为 union 面积只会 <= 实际物理面积，这让 validator 的校验更严格，不会放过 unsound cut。
- **HIGH #3 (canonical sort): CORRECT**
  - **推理**: `sorted([[g, p] for (g, p) in assignment_witness])` 对 list-of-list-of-str 进行字典序排序，Python 的内置 sort 在这里是 deterministic 且 stable 的。即使有重复的 pose (multiset)，stable sort 也会稳定保留它们。JSON `sort_keys=True` 处理了 payload 的其他字段，唯一需要 canonicalize 的 multiset 得到了正确处理。

---

## New Findings (round 2)

### 1. [BLOCKER] `src/cuts/families/density_envelope.py:333` — 动态 `safe_ub` 固化为静态 payload 导致全局 Soundness 破缺
- **问题描述**: `_compute_safe_max_allowed_area` 在计算 `safe_ub` 时，不仅减去了静态的 ghost/exterior cells，还减去了**当前状态下其他 group 占用的 cells** (`if owner_g != cert_group_id: blocked_other.add(cell)`)。
  然而，F9 是一个单组 cut（`watcher_keys` 只 watch `cert_group_id`，evaluator 只查 `cert_group_id`），其 payload 中的 `max_allowed_area` 是一个**静态常量**。
- **Attack / Reproduce**:
  1. 初始状态：Window W (100 cells)。Group B 临时占用了 80 个 cells。
  2. Oracle 针对 Group A 发出 F9 cut。Validator 计算 `safe_ub` = 100 - 80 = 20。
  3. Oracle 构造一个面积为 25 的 witness，并宣称 `max_allowed_area = 20`。Validator 校验通过 (20 <= 20 且 25 > 20)，Cut 被写入 CutStore。
  4. 状态演进：Group B 移出了 Window W，此时 W 物理上完全空闲 (100 cells 可用)。
  5. Master 尝试在 W 中放置 Group A，占用 30 个 cells（完全合法）。
  6. Evaluator 触发：`occupied (30) > max_allowed_area (20)`，直接 Reject！
  7. **结论**：Cut 错误地将 Group B 的临时占位永久固化成了对 Group A 的静态面积限制，切掉了合法的最优解。
- **Suggested fix**: 单组静态 Cut 的 `safe_ub` 只能基于静态物理障碍计算。移除对 `cell_owner` 的遍历：
  ```python
  def _compute_safe_max_allowed_area(...) -> int:
      blocked_other: set[Cell] = set(state.ghost_cells) | set(state.exterior_blocks)
      # 移除 for cell, (owner_g, _slot) in state.cell_owner.items(): ...
      return len(window_cells) - len(blocked_other & window_cells)
  ```

### 2. [HIGH] `src/cuts/families/density_envelope.py:368` — Validator Union 包含 Ghost Cells 导致面积膨胀 (Ghost Cell Inflation)
- **问题描述**: 承接 Round 1 的 Union 修复，Validator 在 `_recompute_assignment_area_overlap` 中只要 `cell in window_cells` 就将其加入 union 面积。但 `window_cells` 只是一个纯几何矩形，**包含了 ghost cells**。
  Evaluator 遍历的是 `state.cell_owner`，而 Master 永远不可能把 instance 放在 ghost cell 上，因此 Evaluator 的 `occupied` 永远不包含 ghost cells。
- **Attack / Reproduce**:
  1. Oracle 想要强行推一个极紧的 bound `max_allowed_area = 5`，但所有合法的 pose 组合最多只能提供 `recomputed_sum = 5`（无法满足 strict inequality `5 > 5`）。
  2. Oracle 恶意挑选一个**跨越 Ghost 边界**的非法 pose 作为 witness。该 pose 在 window 内覆盖了 4 个合法 cell 和 2 个 ghost cell。
  3. Validator 的 Union 逻辑盲目将这 2 个 ghost cell 计入，得出 `recomputed_sum = 6`。
  4. Validator 校验 `6 > 5` 通过，接受了 `max_allowed_area = 5`。
  5. **结论**：Oracle 利用 Validator 和 Evaluator 对 Ghost Cell 的认知差异（Divergence），成功走私了一个本不该被 justify 的紧 bound。
- **Suggested fix**: Validator 的 Union 必须扣除 ghost 和 exterior，与 Evaluator 的物理现实对齐：
  ```python
  if cell in window_cells and cell not in state.ghost_cells and cell not in state.exterior_blocks:
      occupied_cells.add(cell)
  ```

---

## Regression risk (round 1 fix 引入新 bug?)
Round 1 的 3 个 fix 本身没有引入 regression（没有 reject sound case）。
- Union 修复虽然漏了 ghost cell，但相比之前的 Sum 已经是向正确的方向迈进。
- Total demand check 逻辑严密，`len(pairs) <= group_demand` 不会误杀合法的 partial assignment。

## Sanity arguments (回应你的特定攻击向量提示)
- **A. Pose footprint vs cell_owner divergence**: 如果 Master 使用 partial assignment（不按 pose 填 cell_owner），确实会 drift。但 F9 的 witness 强制要求 `oracle_assignment_witness` (List of Poses)，这在契约上暗示了该 cut 仅适用于基于 Pose 求解的 Master 阶段。如果 Master 真的乱填，那是 Master 违反了 Pose 语义，而不是 Validator 的锅。
- **D. Sort 在 list of mixed-type 不稳**: 你的防御是有效的。Schema 校验了 `entry` 必须是 `len(entry) == 2` 且内部元素必须是 `_is_non_empty_str`。因此 `sorted` 面对的永远是纯 `List[List[str]]`，Python 的 lexicographic sort 绝对稳定，无 crash 风险。
- **E. `find_pose` 在 pose_domain 通过但 pool 不含**: 报 `unsound` 是完全正确的。`pose_domain` 宣称可用，但 `candidate_placements` 物理池里找不到，这属于 State Inconsistency。Validator 遇到无法 resolve 物理 footprint 的 witness，拒绝背书（fail-closed）并抛出 unsound 是最安全的做法。

## Gemini self-summary (round 2)
本轮 round 2 cross-check 重点在于 **Validator 与 Evaluator 的深层语义对齐 (Semantic Alignment)** 以及 **Cut 的全局有效性 (Global Soundness)**。
我假装 adversary 尝试了以下攻击：
1. 试图用 overlapping poses 绕过 demand check -> 失败，因为 union 面积会变小，反而让 validator 更难通过。
2. 试图用 mixed types 搞崩 `sorted()` -> 失败，前置 schema check 锁死了 str。
3. **成功攻击**：利用 `safe_ub` 混入了其他 group 的动态状态，构造了 Time-of-Check to Time-of-Use (TOCTOU) 攻击，证明了单组 Cut 固化多组状态会导致合法的解被切掉 (BLOCKER)。
4. **成功攻击**：利用 Validator 不查 Ghost Cell 的漏洞，通过非法 pose 膨胀面积，走私了更紧的 bound (HIGH)。