# Gemini 数学评审核对与 Phase 1.2/P0 行动建议书

日期：2026-05-23  
对象：`phase1_1_gpt_pro_review_v8.zip` 解包后的项目、`MATHEMATICAL_FOUNDATIONS.md` / `PHASE_POST_1_1_REFACTOR_PLAN.md` redirect stub、依赖包 `zmd_deps_v3`。  
结论级别：**Gemini 的大方向基本对，但有 3 个地方需要降温或修正，否则会把“性能优化建议”误当成“数学定理”。**

---

## 0. 我实际核对到的当前状态

1. 你直接上传的 `MATHEMATICAL_FOUNDATIONS.md` 和 `PHASE_POST_1_1_REFACTOR_PLAN.md` 都只是 redirect stub，不是原 1580/1449 行正文。它们说明内容已拆到项目顶层 `docs/项目说明/`。但本次项目 zip 里没有这个新目录，主要可核对的是 `docs/research/p3_b_design_v2_20260521/` 下的 v2 设计文档和 `src/cuts/` 代码。
2. 现有 cut framework 单测通过：
   - `python -m pytest src/tests/cuts/ -q`：172 passed
   - `python -O -m pytest src/tests/cuts/ -q`：172 passed
3. 当前真正落地到 `src/cuts/` 的主要是：
   - F1 `region_capacity`：validator/evaluator/generator 已有
   - F2 `cutset`：validator/evaluator 已有，generator 仍是 stub
   - F3 `port_exposure`：validator/evaluator 已有，generator 仍是 stub
   - F4 `component_reach`：validator/evaluator 已有，generator 仍是 stub
   - F5/F6/F7/F8/F9：主要还在 spec/计划层，`src/cuts/families/` 没有对应实现
4. `src/cuts/lifecycle.py` 里 Step 2 minimization 和 Step 8 apply-to-master 都还是 `NotImplementedError`。也就是说，Gemini 讨论的 F5/F9/QX/注入策略确实属于下一阶段生死线，不是已经完成的能力。
5. 你包里的 OR-Tools 是 `9.15.6755`。我在这个版本里确认 `cp_model.CpModel()` 没有 `AddLazyConstraint`；现有项目也一直是“Benders 多轮求解，在两轮之间 Add/OnlyEnforceIf 加约束”，不是 CP-SAT 真 lazy callback。

---

## 1. 总判断：Gemini 哪些说得对，哪些有坑

| Gemini 观点 | 我的判断 | 说明 |
|---|---:|---|
| `132! manufacturing_3x3` 集群爆炸是 P0 | **基本对，但表述过猛** | 项目已经用 group/orbit + multiset 砍掉“实例标签排列”的一大块爆炸；剩下真正危险的是 **pose/几何窗口/局部冲突模式** 爆炸。F5 spec 也明确说 132 个 mfg_3x3 时 full no-good 会退化，Family 9 才是主解。 |
| 需要 orbit-aware/cardinality cut | **对，但必须带独立证书** | 线性基数 cut 很适合 CP-SAT，但不能从任意 routing/binding 失败直接 lift。只有当 validator 能证明“这一组 pose/window 的任意等价占用都必死”时，才能加 `sum x <= k-1`。 |
| QuickXplain/MUS 会超时，要 time-box fallback | **对，是最稳的 P0 工程措施之一** | 返回的 fallback core 必须是“最后一个已被 oracle 重新证明 infeasible 的 core”，不能返回未经验证的半成品。非最小 core 仍 sound，只是剪枝弱。 |
| F9 平凡界需要更强几何包络 | **对，但 Gemini 的 morphology 说法不够严谨** | 形态学腐蚀可以做“合法 anchor 域”和“走廊装不下 3x3”的强证据；但 `腐蚀后 anchor 数 = 真实容量` 一般不成立，它只是上界/域过滤，不等于 packing capacity。F9 现有 lock 要求 area-based `sum(|pose_cells ∩ W|)`，不能退回按 instance/origin/all-in-window 计数。 |
| F4 只做 BFS 缺容量，需要 max-flow/min-cut | **对，而且项目已有 F2 spec 正是这个方向** | 当前 F2 validator/evaluator 已有，但 generator 仍 stub。应把 Dinic/node-split 最大流作为 F2 generator 主路径，把 F4 看成“容量为 0 的断连特例”。 |
| CP-SAT 用 `AddLazyConstraint` 做 Tier2 Lazy | **不适用于当前项目依赖** | 你包里的 OR-Tools CP-SAT Python 没有 `AddLazyConstraint`。应继续走 LBBD 外循环：每轮 solve 后验证，生成 cut，重建/增量加普通 CP-SAT 约束，再 solve。真正 lazy separator 只能考虑 SCIP 那条线。 |
| Q1 完备性缺失会导致无限盲搜 | **有道理但不是第一 P0** | 只要 fallback no-good sound 且 master 域有限，正确性不依赖 F1-F9 完备；完备性影响的是性能和 168h 是否收敛。真正 P0 是：fallback 是否能落地、是否会被 132 集群拖爆、是否有 telemetry 抓未知死法。 |
| “数学上不存在低级漏洞” | **不能这么绝对** | 当前 spec 里 F9 自身还留有旧 wording（有些地方说 count instance，有些地方已锁 area-based），代码也尚未覆盖 F5-F9。说“整体方向严谨”可以，说“没有公式/逻辑漏洞”太满。 |

---

## 2. 当前最关键问题排序

### P0-A：F5 fallback 必须能生成、最小化、验证、入库、回放、注入

原因很简单：只要 subproblem 发现 infeasible，而 F1-F4/F6-F9 没给出更强证据，最后必须能学一条 no-good。没有 F5，LBBD 会重复踩同一个坑；F5 不 time-box，则会被 MUS/QuickXplain 拖死；F5 不 orbit-aware，则会被 mfg_3x3 集群拖爆。

但注意：**F5 的职责是保底，不是主力。**如果 F5 占比超过 50%，项目文档已经把它列为 stop-ship 信号。

### P0-B：F9 只能吃 `area_capacity_overflow`，不能从 routing/binding 死锁偷换成 density cut

`PROJECT_LOCK` 已经锁死：F9 只能由面积容量溢出凭证触发，binding/routing/PCR-CUT infeasible 必须 fallback 到 F5。这个锁非常关键，因为“局部 routing 死锁”常常依赖端口朝向、相对位置、障碍细节；把它泛化成“窗口里设施太密”很容易误剪合法解。

### P0-C：Step 8 apply-to-master 不能再悬空

现在 cut lifecycle 能 serialize/validate/replay，但 Step 8 仍未接 master。下一阶段如果不把 cut object 真正翻译为 CP-SAT 约束，数学再漂亮也不会剪枝。

### P0-D：F2/F4 generator 不能长期 stub

F4 的 BFS 连通性只回答“有没有路”，F2 才回答“路够不够宽”。当前代码里 F2/F4 validator/evaluator 做得比 generator 多，generator 还没产出真实 cut。这个是容量盲区的核心落地点。

### P0-E：必须有 “unknown infeasible / dark matter” 日志

F1-F9 不完备是正常的，但未知死法不能静默退化。每次 subproblem 判 infeasible，而所有 family 都返回空，应把完整状态、ghost、master solution、subproblem witness 落盘。否则永远不知道第 10 类 cut 应该长什么样。

---

## 3. 具体实施计划

### Phase 0：先补“防误剪测试”，再写新 cut

不要先写优化代码。先把红线测出来。

新增测试建议：

1. `test_f5_timeout_returns_last_verified_core`
   - 构造 oracle：full assignment infeasible；某些删减后 unknown/timeout。
   - 断言 timeout 返回的 core 必须是最后一个 verify infeasible 的 core。
2. `test_f5_multiset_orbit_no_instance_id`
   - 同一 group 3 个匿名 slot，slot index 改变后 evaluator 仍同结果。
3. `test_f9_rejects_routing_overflow`
   - 输入 `routing_overflow`/`binding_overflow` witness，generator 必须返回空，交给 F5。
4. `test_f9_area_overlap_counting`
   - 复现三类历史坑：any-overlap overcount、origin-in-window、all-in-window 漏算；唯一允许的是 area-based `sum(|pose_cells ∩ W|)`。
5. `test_cpsat_no_lazy_constraint_path`
   - 不要依赖 `AddLazyConstraint`；Step 8 只能调用普通 `Add` / `OnlyEnforceIf` / `AddBoolOr` / `AddLinearConstraint`。

验收：现有 172 个 cut 测试继续全部通过，新增测试先红后绿。

---

### Phase 1：F5 bounded core minimizer

#### 1.1 新增模块

- `src/cuts/families/pattern_nogood.py`
- `src/cuts/oracles/pattern_nogood_oracle.py`
- `src/cuts/helpers/bounded_core_minimizer.py`
- `src/tests/cuts/test_family_pattern_nogood.py`
- `src/tests/cuts/test_bounded_core_minimizer.py`

#### 1.2 minimizer 合同

输入：

```python
assignment: tuple[LiteralAssignment, ...]
oracle(core) -> INFEASIBLE | FEASIBLE | UNKNOWN | TIMEOUT
budget: max_calls, max_seconds
```

输出：

```python
CoreMinimizeResult(
    core=last_verified_infeasible_core,
    is_minimal=False | True,
    calls=n,
    stopped_reason="minimal" | "call_budget" | "time_budget" | "oracle_unknown",
)
```

硬规则：

- full assignment 先 verify infeasible；verify 不过则不生成 cut。
- 每次删除 literal 后，只有 oracle 返回 INFEASIBLE 才允许收缩 core。
- TIMEOUT/UNKNOWN/exception 一律 fail-closed：保留旧 core，不把新 core 当证据。
- 返回非最小 core 是允许的；返回未验证 core 是禁止的。

#### 1.3 F5 cert

建议 cert 至少包含：

```python
{
  "cert_kind": "bounded_deletion_core",
  "sub_problem_oracle_name": "binding_v3|routing_v2|pcr_cut_v1|...",
  "oracle_cert_hash": "...",
  "forbidden_pose_pattern": [["group_id", slot_idx, "pose_id"], ...],
  "core_minimization": {
    "size_before": 266,
    "size_after": 37,
    "calls": 104,
    "budget_seconds": 0.1,
    "stopped_reason": "time_budget",
    "last_verified": true
  },
  "sub_oracle_witness_blob_b64": "..."
}
```

#### 1.4 F5 apply-to-master

Literal no-good：

```text
sum(present(group, pose) for each literal in core) <= len(core) - 1
```

对 pose-bool delegate，可直接用 `x_vars[(group_id, pose_idx)]`。  
对 coordinate delegate，需要继续走 `_pose_present_literal(...)` 生成 presence literal。  
ghost-bound cut 用 `OnlyEnforceIf(condition_lits)` 或按 ghost candidate 重建模型注入；不要无条件跨 ghost 复用。

---

### Phase 2：Orbit-aware / cardinality cut，但只在证书足够强时启用

Gemini 的线性基数 cut 方向是对的，但要把它从 F5 黑盒 no-good 中拆出来，成为“有几何证据的 lift”。

#### 2.1 允许生成 cardinality cut 的证据

只接受这几类 witness：

1. **AreaCapacityOverflow**：窗口 W 内所需占用面积超过 `max_allowed_area`。
2. **Shape/Hall packing witness**：某设施形状在某区域的可放锚点/匹配容量不足。
3. **Min-cut capacity witness**：跨 cut 的需求大于切割容量。
4. 经过 validator 独立重算的其它数学证据。

不接受：

- “这一次 routing 失败，所以同样数量都失败。”
- “这几个具体 pose 冲突，所以邻近 pose 也应该冲突。”
- “腐蚀后 anchor 少，所以所有 overlap-W 的设施都不能放。”除非证书语义明确是 all-in-window，不是 overlap-window。

#### 2.2 建议 cut 形式

对 group `g` 和 pose 集合 `P`：

```text
sum_{p in P} x[g,p] <= U
```

其中 `U` 必须由 cert 证明。  
如果 `P` 是“窗口内所有合法 anchor pose”，这更像 F6/F9。  
如果 `P` 是“某一组具体冲突 pose”，这仍然是 F5 的弱化版，不应冒充几何定理。

---

### Phase 3：F9 density_envelope 正式实现

#### 3.1 新增模块

- `src/cuts/families/density_envelope.py`
- `src/cuts/oracles/density_envelope_oracle.py`
- `src/tests/cuts/test_family_density_envelope.py`

#### 3.2 cert 要坚持 area-based

```python
{
  "cert_kind": "area_capacity_overflow",
  "window_rect": [x, y, h, w],
  "group_id": "...",
  "max_allowed_area": 123,
  "oracle_witness_kind": "area_capacity_overflow",
  "oracle_assignment_witness": [["group_id", "pose_id"], ...],
  "ghost_rect_repr": [...]
}
```

Evaluator：

```python
occupied_in_window = sum(
    1
    for cell, (owner_group, _) in state.cell_owner.items()
    if owner_group == cert.group_id and cell in W
)
return occupied_in_window > cert.max_allowed_area
```

注意：这是“是否违反 cut”的 evaluator；Step 8 注入 master 时要把它翻译成等价的线性表达，不能在 Python callback 里动态算。

#### 3.3 morphology 的正确用法

形态学腐蚀可以加，但用途应写清楚：

- 用于计算某区域内“设施完全放入 W”的合法 anchor 域。
- 用于发现 `10×1` 走廊不能完整放入 `3×3` 设施。
- 用于 F6 shape packing/Hall 的候选域收缩。
- 可作为 F9 `area_capacity_overflow` oracle 的辅助证据，但不能直接把“anchor 数”当成“真实 packing 容量”。

一句话：**morphology 是强 helper，不是免证明的 density theorem。**

---

### Phase 4：F2/F4 容量桥接：Dinic/node-split min-cut

#### 4.1 为什么要 node-split

如果真实限制是“每个 cell 只能承载有限条 belt/物流”，单纯 edge cut 不够。应把每个 cell 拆成：

```text
v_in -> v_out  capacity = cell_capacity
```

相邻移动边：

```text
u_out -> v_in  capacity = edge_capacity
```

这样 min-cut 才能同时表达“窄通道 cell 容量”和“边通行容量”。

#### 4.2 生成器输出

当 `max_flow < demand`：

```python
CutsetCert(
    capacity_model_version="grid_node_split_v1",
    side_a_bitset_b64=...,
    side_b_bitset_b64=...,
    cut_edges_or_nodes=...,
    cut_capacity=max_flow_or_min_cut_capacity,
    commodity_demand=demand,
    contributing_commodities=(...),
    witness_blob_b64=...
)
```

Validator 独立重建同一个 node-split graph，重算 min-cut，不信 generator 的数字。

#### 4.3 F4 与 F2 的关系

- F4：BFS 不连通，等价于容量 0 的特殊 cut。
- F2：连通但容量不足，是主力容量 cut。
- 实施上可以 F4 先跑，F4 不触发再跑 F2 min-cut。

---

### Phase 5：CP-SAT 注入策略修正

不要按 Gemini 原话做 `AddLazyConstraint`。当前可行路径是：

1. Store/Watcher 选择当前 ghost、当前 source digest、当前 artifact hash 下可 attach 的 cut。
2. 在每轮 master solve 前，把 active cuts 用普通 CP-SAT constraints 注入。
3. ghost-bound cut 用 `OnlyEnforceIf(ghost_lit)` 或每个 ghost candidate 单独 build。
4. `GHOST_AGNOSTIC` cut 仍必须校验 `exterior_blocks_hash`，不能因为名字叫 agnostic 就跳过外部障碍。
5. Python callback 不做复杂推导；当前项目应保持“solve → verify → generate cut → rebuild/resolve → solve”的 LBBD 节奏。

Step 8 的最小实现清单：

| family | Step 8 约束形态 |
|---|---|
| F1 region_capacity | 线性容量约束或直接 infeasible bound |
| F2 cutset | `sum(crossing demand literals) <= cut_capacity`，或 no-good fallback |
| F3/F5/F7 literal | `sum(present_lits) <= n-1` |
| F4 component_reach | 更适合生成 F5/F2 派生约束；纯 BFS cut 若无法线性表达则保守 fallback |
| F6 shape Hall | `sum(x[g,p] for p in P_region) <= U` |
| F8 power reach | power network reachability 证书转 hitting/coverage cut，否则 fallback |
| F9 density | `sum(area_overlap[p,W] * x[g,p]) <= max_allowed_area` |

---

### Phase 6：Telemetry / dark matter

每次 subproblem 返回 INFEASIBLE 后：

1. 依次尝试强 family：F2/F4/F6/F8/F9。
2. 再尝试 F5 fallback。
3. 如果全部返回空，写入：

```text
data/cuts/telemetry/unexplained_infeasible.jsonl
```

每行字段：

```json
{
  "iter": 123,
  "ghost_rect": [x,y,h,w],
  "subproblem": "routing_v2",
  "status": "INFEASIBLE",
  "master_solution_hash": "...",
  "state_digest": "...",
  "families_tried": ["F2","F4","F6","F8","F9","F5"],
  "empty_reason_by_family": {"F9": "not_area_capacity_overflow", "F5": "oracle_timeout_no_verified_core"},
  "witness_blob_path": "data/cuts/telemetry/witnesses/..."
}
```

报警阈值：

- F5 cut ratio > 50%：stop-ship / 必须补强几何 lift
- F5 median core size > 40：需要 minimizer 或更强 family
- F9/F5 ratio 长期 < 0.2：说明 density lift 没接上
- unexplained infeasible 连续出现：人工复盘，提炼 F10
- cut_store RSS 逼近 5GB/worker：触发 capacity eviction，保留 audit trail

---

## 4. 不建议马上投入的方向

1. **证明 F1-F9 完备性**  
   这不是下一阶段最该做的。先保证 fallback 和 telemetry，完备性靠红队样例逐步逼近。
2. **二维 Hall 全面理论化**  
   重要，但不应压过 F5/F9/F2 generator + Step 8。可以先做局部 shape-Hall、窗口级 matching 上界。
3. **把 morphology 当 F9 主公式**  
   可作为 F6/F9 辅助，但必须明确语义，不要从 anchor 域直接跳到 overlap-area cut。
4. **CP-SAT callback 里做复杂 lazy separation**  
   当前依赖不支持 `AddLazyConstraint`，Python callback 高风险。继续 LBBD 外循环。

---

## 5. 进入 Phase 1.2 的 GO 标准

### 必须满足

- F5 能在 bounded time 内返回 sound fallback cut。
- F9 只接受 `area_capacity_overflow`，且 evaluator/validator/Step8 全 area-based。
- F2/F4 至少一个真实 generator 接通，不再只有 validator/evaluator。
- Step 8 对 F3/F5/F9 至少接入 master。
- 所有 cut replay 都遵守 HOLD vs QUARANTINE，不 silent recover。
- 新增红队测试覆盖历史 FP/FN 坑。
- `python -O` 下测试仍通过。

### 建议满足

- F5/F9 ratio telemetry 可视化。
- unexplained infeasible jsonl 接通。
- cut store RSS 使用 psutil 真实 RSS，不用逻辑估算。
- mypy strict 的现有 typing debt 单独建 cleanup，不要和数学 P0 混在一个 commit。

---

## 6. 最后结论

Gemini 的回复可以作为“问题雷达”，但不能直接当实现方案。最关键的修正是：

1. **F5 是保底，必须 time-box + last-verified-core；但不能指望 F5 扛 132 集群。**
2. **F9 是主力几何 lift，但只能吃面积容量溢出证书；不能把 routing/binding 死锁泛化成 density。**
3. **morphological erosion 可用，但不能把 anchor 数当真实容量。**
4. **CP-SAT 当前不能按 Gemini 说的 AddLazyConstraint 做；要走 LBBD 外循环普通约束注入。**
5. **完备性不是眼前第一 P0；未知死法 telemetry 才是可落地的完备性逼近方法。**

按这个顺序推进，比“先证明 9 大理论完备”更现实，也更符合你们 PROJECT_LOCK 里“宁可漏剪，不可误剪”的生存原则。
