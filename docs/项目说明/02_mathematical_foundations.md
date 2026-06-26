# 02 — 核心数学原理 (9 family + sound deduction + scope/replay/multiset/adversarial)

> **阅读边界（2026-06-26）**：本文保留 cut-family 的数学背景与历史设计。当前默认 certified 路径、发布 authority 和 phase 状态以 `01_overview.md`、`06_current_status.md`、`11_dependency_graph.md` 与 `PROJECT_LOCK.md` 为准；“family 已实现”不等于“已接入 production master”或“P1.2 已关闭”。


### 2.1 paradigm 选择 — LBBD + cut framework 累积外部知识

**为啥选这个 paradigm**:

项目走过 27 个其他 paradigm 死路 [cite death-timeline], 实测后归出 4 个共同 root cause (详 §4.8):
1. **master.solve 自身解不动** — 不是 worker 数 / RAM / OS 调优问题, 是 CP-SAT BCP propagation 在 dense linear constraint + 8 × 10⁷ pose 空间上 inherent latency-bound [[workload-latency-bound-not-bandwidth]]
2. **替换 solver / 重写 master 不工作** — HiGHS / LP relax / B1 pose-bool 全 verdict 死, 单机 48 GB + 准确性必保前提下 inherent
3. **sub-problem cut 路径必须 sound** — over-restrictive 单 cut 就 break optimality (Phase 5 cell_cut 教训)
4. **跨 instance lifting 必死** — pose anonymity 限于 within-instance, 跨 instance lift 必 unsound (PROJECT_LOCK §3A 锁)

paradigm 选择落点: **不改 master, 在 master 外累积 sound 知识层**. 这是 cut framework 数学根据.

**LBBD topology** (paper: Hooker 2003, Logic-Based Methods for Optimization):
- master 出主决策, sub-problem 验, 失败 → 出 nogood → master 加 lazy
- 当前候选证明主链以 placement / binding / routing / power 与终端复验为准；`flow_subproblem.py` 仅诊断，不能把其 INFEASIBLE 独立提升为 proof-bearing cut

**Cut framework** 不是 LBBD 的发明 — 是 LBBD nogood 的工程抽象层. 类比 SAT solver CDCL (Conflict-Driven Clause Learning) 学到的 clause 全程累积, 项目 cut framework 让 LBBD sub-problem 学的 nogood 跨 candidate / 跨 ghost 累积 (within-instance scope).

### 2.2 Cut 的形式系统 — sound deduction

**Cut 4 元组定义** [cite lifecycle §3]:

```
Cut = (
    family,           # F1-F9 (cut family, 见 §3)
    scope,            # 适用范围: (ghost_rect_id, source_digest)
    cert,             # certificate: mathematical proof object
    body              # cut body: literals[] XOR geometric_payload (mode 决, §2.7)
)
```

**Sound deduction rule** (cut framework 不变量):

> 给定 BState `s` 跟 cut `c`: 若 `c.scope.matches(s)`, 则
>     `validator(c.cert, s) = OK` ⇒ `evaluator(c.body, s) excludes assignments that ¬feasible`

形式化:
```
∀ c, s. matches(c.scope, s) ∧ validator(c.cert, s) = OK
  ⇒ ∀ π. evaluator(c.body, s, π) = exclude ⇒ ¬feasible(s, π)
```

**关键**: validator 必**独立**重算 cert (不信 oracle 产的 cert), 见 §2.6.

### 2.3 9 family 数学根据 overview

cut framework 9 family frozen [cite lock §3A]:

| Family | Name | 数学根据 | Mode |
|---|---|---|---|
| F1 | region_capacity | pigeonhole + set covering | geometric |
| F2 | cutset | Menger min-cut max-flow theorem | geometric |
| F3 | port_exposure | propositional logic + slot anonymity | literal |
| F4 | component_reach | 4-conn graph BFS connectivity | geometric |
| F5 | pattern_nogood | minimal unsat core + QuickXplain | literal |
| F6 | shape_packing_hall | Hall's marriage theorem (interval graph) | geometric |
| F7 | power_hitting_set | set cover NP-hard + LP relaxation (ln n approx) | literal |
| F8 | power_grid_reach | Liang-Barsky AABB intersection | geometric |
| F9 | density_envelope | geometric upper bound (cap/area ratio) | geometric |

详 §3.

**Mode XOR invariant** [cite lock §3A]:
- **literal mode** (F3/F5/F7): cut body = list of (instance_id, pose_id) tuples, 排除 conjunction `x[i₁,p₁] ∧ x[i₂,p₂] ∧ ...`
- **geometric mode** (F1/F2/F4/F6/F8/F9): cut body = geometric_payload (bitset / region / partition / commodity), 跟 BState 几何重算
- 不可混 — cert 跟 body 必 mode-consistent, validator dispatch 按 family → mode 查表

**Per-family ghost dependency** (Phase 1.2 严格化):
- 各 family validator 必声明对 ghost_rect 的依赖. F1 必 GHOST_AGNOSTIC 只在 `ghost ∩ R == ∅` 时合法 (Step O); F2/F4 直接 reject GHOST_AGNOSTIC scope (cutset 跟 connectivity 都依赖 ghost)
- 详 [cite spec 01 §2a] (F1 cap_R 跨 ghost 不 invariant 的反例)

### 2.4 Scope versioning + replay 形式化

**Scope** 是 cut 适用的 frame [cite lifecycle §4]:

```
Scope = (
    ghost_rect_id,    # int | GHOST_AGNOSTIC sentinel
    source_digest,    # str (canonical_rules + data content hash)
)
```

**Replay 触发**: 当 BState 的 ghost_rect_id / source_digest 变, 已 active/held cut 必 re-validate.

**Replay semantic** (Phase 1.1 Step M 加严):
```
replay_cut(cut, state, store) =
    if cut.scope.source_digest ≠ compute_source_digest(state):
        return QUARANTINE  # data 版本变, cut 失效
    if cut.scope.ghost_rect_id ≠ GHOST_AGNOSTIC ∧ ≠ state.ghost_rect_id:
        return HOLD        # ghost 不匹配, 暂不 attach
    if canonical_rules is None:
        if state.canonical_rules is None:
            return HOLD    # fail-closed, 不 trust orphan replay
        canonical_rules = state.canonical_rules
    decision = validator(cut.cert, state, canonical_rules)
    if decision = OK:
        return ATTACH
    else:
        return QUARANTINE
```

**GHOST_AGNOSTIC sentinel** [cite lock §3A]:
- 标记 cut 对 ghost rectangle 不敏感 (e.g. F1 在 `ghost ∩ R == ∅` 时)
- F2/F4 直接 reject GHOST_AGNOSTIC scope — cutset 跟 connectivity inherent 依赖 ghost
- 数学根据: cert 重算时若 cert 公式不含 ghost_cells 变量, 则 cut 跨 ghost reuse sound; 否则必绑特定 ghost_rect_id

**source_digest content addressing**:
- 当前 Phase 1.1 已落地 sha256 content hash；`BState.source_digest` 只当外部备注/缓存，replay 以当前注入 source 重新计算为准
- 当前算法: sha256 over normalized source payloads (`canonical_rules`, `candidate_placements`, `mandatory_exact_instances`, `facility_templates`, `generic_io_requirements`, `commodity_routes`)；`__*` runtime cache key 不入 hash
- 数学不变量: data 不变 → digest 不变 → cut sound 跨 session reuse; data 变 → digest 变 → 旧 cut 全 quarantine

### 2.5 Multiset eval — slot anonymity 群论形式化

**Problem**: 一个 facility group `g` 有 `g.demand` 个相同 instance (e.g. `boundary_storage_port` 46 instance 全 identical). 每个 instance 占一个 "slot". Cut literal 含 `(slot_id, pose_id)` — 但 **slot 是匿名的**: instance `slot=0 pose=p1` 跟 `slot=1 pose=p2` 与 `slot=0 pose=p2 ∧ slot=1 pose=p1` 是同一个 assignment.

**形式化** [cite state §5]:

设 `g` 有 `n = g.demand` 个 slot, slot 集 `S_g = {0, 1, ..., n-1}`. 对称群 `S_n` 自然 act on `S_g` via permutation. Cut body (slot, pose) tuple 集 modulo `S_n` action 等价类 — 即 **multiset of poses**.

**evaluate_cut_as_multiset** 数学根据:
```
evaluate(cut.body, state) = ∀ slot_assignment ∈ orbit(S_n, cut.body),
    if slot_assignment ⊆ state.placement: violate = True
```

即 cut.body 的某 permutation 在 state 中实例化 → violate. validator 必验 cut.body 跟 cert 在 multiset 层 binding (Step B + Step J close 的 F3 P0-2).

**Slot anonymity invariant** [cite lock §3A]:
- Cut body literal 的 slot_id 是 placeholder, 不 carry semantic — evaluate 不绑具体 slot id
- 实施: `_make_port_exposure_cert` 等 helper 必产 multiset binding, validator 必 reject 单 slot binding (Step B)

### 2.6 Adversarial soundness 5 verification 层

**假设** [[adversarial-soundness-audit]]:
- **oracle Byzantine**: oracle (cut generator) 可产假 cert. oracle bug / oracle 误改 / oracle 数学错都可能
- **validator trust boundary**: validator 是 cut framework 唯一 trust point. validator 通过 = cut sound, validator reject = cut unsound (quarantine)
- **validator 不调用 oracle**: validator 必**独立**从 BState + cert 数据重算, 不调用 oracle 提供的"sound" claim

**5 verification 层** (Step A-O 主要 close 的):

1. **Cert 内 sound**:
   - cert 各字段一致 (region cells ⊆ free / partition A∪B == free / commodity_id ∈ registry / src/sink_component bitset 真 BFS)
   - 例: F1 cert.cap_R 重算 vs cert 声明
   - 例: F4 cert.src_component == BFS(state, src) (Step D)

2. **Cert ↔ literals 绑定** (literal-mode family):
   - F3 cert.blocking_pose_id ↔ literal multiset 严等 (Step B)
   - F5 cert.pattern_blockers ↔ literal pattern 严等
   - **反例**: 拿 p13 cert 证 p14 (literal multiset 不绑) — Step A-O P0-2 真 bug 来源

3. **Cert ↔ 真数据 (canonical_rules + preprocessed)**:
   - F1 cert.region cells 跟 canonical_rules.placement_rule_for_group 同源
   - F4 cert.commodity_id ∈ generic_io_requirements (Step M)
   - **反例**: oracle 推 `viewer::boundary_required_output_source_ore_005` 占 (31,69) ∉ R, 但 cert 声明 ⊆ R — 真数据反查 catch (GPT pro v3 P0-1)

4. **Cert ↔ state**:
   - cert 跟 BState.pose_domain / cell_owner / commodity_demands 一致
   - cert 不能凭空造 BState 没有的 entity
   - **反例**: F2 cert 声明 commodity_id "ore_X" 但 state.commodity_demands 不含 (Step M registry require)

5. **Cert ↔ 不变量 (PROJECT_LOCK §3A)**:
   - GHOST_AGNOSTIC sentinel 跟 family ghost dependency 一致 (Step O F1 ghost ∩ R == ∅ check; F2/F4 reject AGNOSTIC)
   - family mode XOR (cert + literals XOR cert + geometric_payload)
   - source_digest 跟 cert 同版本 data

**实施分布**:
- 1+2 主要 Gemini per-commit catch (schema/spec layer)
- 3+4+5 主要 GPT pro batch catch (adversarial soundness layer)
- 详 plan doc §22 (review strategy)

### 2.7 9-step lifecycle 数学职责

cut 从产到 attach master 经 lifecycle [cite lifecycle §2]。**编号 0-indexed 对齐源码 `src/cuts/lifecycle.py` (`step_0_canonicalize` … `step_8_apply_to_master`) + 04 §2.2 / PROJECT_LOCK §4**：Step 0 canonicalize 是共用哈希/序列化基础（非业务步），业务链 = Step 1-9。

| Step | 名 (源码 step_N) | 数学职责 | 当前实施 |
|---|---|---|---|
| 0 | canonicalize | 跟产 cert 物理 (normalize bitset / sort literals) → 同 cert 哈希等 | 共用基础工具 (非业务步) |
| 1 | generate | oracle 产 cert (允许 Byzantine, 不信任) | Phase 1.1 4 family ready |
| 2 | minimize | 产最小 cut (deletion-based / QuickXplain, F5 用) | Phase 1.2 **P1.2B-F5**（原误名 P1.11）|
| 3 | serialize | cert + body → JSON | Phase 1.1 闭环 |
| 4 | deserialize | JSON → cut object (validate schema) | Phase 1.1 闭环 |
| 5 | validate | validator 重算 cert, 决定 sound/unsound | Phase 1.1 闭环, 4 family |
| 6 | attach-scope check | scope.matches(state) (source_digest/ghost/blocked/artifact/oracle/assumption) | Phase 1.1 dispatch |
| 7 | evaluate | body 重算当前 state 是否仍 violate (family dispatch) | Phase 1.1 4 family evaluator |
| 8 | apply-to-master | cut.body → master.AddLinear（**CP-SAT 无真 lazy callback**，累积切面+重新求解）| **defer 后续 P1.3**（原名 P1.21；`step_8_apply_to_master` 仍 NotImplementedError）|
| 9 | replay/regression (on ghost/state change) | re-validate active/held cut, decide ATTACH/HOLD/QUARANTINE | Phase 1.1 闭环 (Step M fail-closed) |

**Step 8 missing 当前是为啥 cut framework 跑 unit test 但**没真接进 master** — Phase 1.3 实施.

> **(2026-06-26 现状提示)** 上表的 "Phase 1.1 闭环 / defer Phase 1.2" 是 Phase 1.1 时代口径。当前工作树已经实现并审计 F5–F9 的 generator/validator（含 F3 special-case；F9 后被 tight-K **quarantine** 实质停用），但这不表示 Phase 1.2 已闭合。`step_8_apply_to_master()` 仍抛出 `NotImplementedError`，真实 master 集成属于 **P1.3** 未完成项。当前状态以 `06_current_status.md`、`soundness_gap_roadmap.md`、`CLAUDE.md` 和 `PROJECT_LOCK.md` 为准。

**Step 2 (minimize) missing 影响**: F5 deletion 当前不能产 minimal unsat core, F5 实施 (Phase 1.2 **P1.2B-F5**, 原误名 P1.11) 时同步落 step 2 (minimize, 0-indexed)。

---

## 3. 各 family 数学基础详

本节每 family 一段, summary 数学根据 + cite spec 详. 不重复 spec 的 cert 字段 schema (那是 spec 的事), focus 数学 paradigm + 该 family 跟其他 family 的边界.

### 3.1 F1 region_capacity — pigeonhole / set covering

**数学根据**: pigeonhole principle + set covering (Hooker 2003, Bertsimas-Tsitsiklis Ch.11 LP duality).

**Cut 形式** [cite spec 01 §1a]: 给定 region `R ⊆ G` 跟两个量
```
cap_R = |R| − |ghost ∩ R| − |exterior_blocks ∩ R|      (region 内 facility 容量上界, static)
demand_R = ∑_{g : P(g) ⊆ R} g.demand × cells_per_pose(g)  (region 内 mandatory demand)
```
若 `demand_R > cap_R` → 任何 master assignment 必 INFEASIBLE (pigeonhole).

**触发条件**: oracle 选 region `R` 使 `demand_R > cap_R`. 4 类 region [cite spec 01 §1b]:
- `left_baseline` (`x=0` 列)
- `bottom_baseline` (`y=0` 行)
- `interior_rect` (任意轴向 rectangle)
- `ghost_complement` (ghost 内 cells, `cap_R = 0`)

**Ghost dependency**: cap_R 含 `|ghost ∩ R|` 项 → 跨 ghost 不 invariant. GHOST_AGNOSTIC 只在 `ghost ∩ R == ∅` 时合法 (Step O Gemini round 18 finding B1 + GPT pro v6 P0 close). 否则 generator 必绑 compute_ghost_rect_id.

**LP relaxation 关系（设计层）** [cite spec 01 §1c]: F1 可被解释为 master LP relaxation 的 valid inequality；理论上可由 dual/Farkas 证据识别。当前工作树没有 `farkas_certificate.py`、dual-ray generator 或 algebraic verifier，现役 F1 oracle 仍是组合枚举，且 F1-F9 Step 8 尚未接入 production master。

**P(g) ⊆ R 验证** (GPT pro v3 P0-1 真 bug):
- `demand_R` 定义要求 facility group `g` 的**所有** candidate pose 必 ⊆ R
- 反例: `boundary_io` group 46 instance, candidate_placements 含 BSP pose, 但 14 pose 占 cells **不在** boundary union — `placement_rule_for_group` 是必要不充分
- Step E (commit `8a38401`) 加 strict P(g) ⊆ R check: 对 group `g` 所有 pose 验 `occupied_cells(pose) ⊆ R`, 否则不算 contributing

**跟其他 family 边界**:
- 适用: region cap < demand 几何不可达
- 不适用: cap ≥ demand 但 routing/power/binding 不可行 → 走 F2/F4/F7
- 跟 F6 关系: F6 是 F1 的 stronger refinement (Hall theorem 检 interval cover, F1 只检 count)

**Phase status**: Phase 1.1 production validator + oracle + evaluator 闭环 (Step E/F/G/L/O 全 close); GHOST_AGNOSTIC 与 source_digest hard binding 已在 1.1 exit hardening 落地，可进入 Phase 1.2。

**Open Q (defer §5.3)**:
- F1 oracle 如何 enumerate 有用的 interior_rect region (NP-hard exhaustive)?
- 未来是否值得实现独立可复验的 LP-dual/Farkas 证书来触发 F1 cut？当前答案仍是“未实现”。

### 3.2 F2 cutset — Menger min-cut max-flow theorem

**数学根据**: Menger's theorem (1927) — 给定 graph G 跟 source-sink (s, t), s-t 不连通 iff 存在 cutset (顶点集) separates s 跟 t. Dual: max flow = min cut (Ford-Fulkerson 1956).

项目用 Menger 的 "顶点 cutset" 版本 (不是 edge cutset), 因为 routing 是 cell-grid (顶点) 不连通.

**Cut 形式** [cite spec 02 §1a]: 给定 free_cells 上的 graph (4-conn), partition `(A, B, S)` 使 `A ∪ B ∪ S = free_cells`, `S` 是 separator 顶点集. 若 commodity `c` 有 `src ∈ A`, `sink ∈ B`, `S` 内**所有** cell 都 forbidden (e.g. ghost / exterior / cell_owner) → s-t 无 path → INFEASIBLE.

具体 cert:
- partition (A, B)
- cut_edges 集合 (A 跟 B 之间所有 4-conn 边的 cell-cell pair)
- contributing commodities (source ∈ A ∧ sink ∈ B 或反之)
- commodity_demands (Step M registry require)

**触发条件**: oracle 在 routing INFEASIBLE 时 (front_blocked / sub-problem reject) 找 partition 使 separator 不可穿透.

**Ghost dependency**: partition 跟 separator 都依赖 ghost (ghost cells 是 cut S 的成员). GHOST_AGNOSTIC **直接 reject** (Step O).

**Soundness 关键**: 
- partition `A ∪ B == free_cells \ S` 必 verify (Step C `eaed85c`)
- contributing commodities 必跨 partition (src ∈ A ∧ sink ∈ B), 不能同侧 (Step N `afef8f1`)
- cut_edges canonical (sorted, dedup) (Step C)

**跟其他 family 边界**:
- 适用: routing INFEASIBLE due to **几何 separator** (ghost / exterior 切 grid)
- 不适用: routing INFEASIBLE due to **port matching / belt capacity** → 走 F3/F4
- F4 是 F2 的 cell-level 弱化 (verify single src reaches single sink), F2 是 partition-level 强化 (verify 全 graph separated)

**Phase status**: Phase 1.1 闭环 (Step C/N/O 全 close, GHOST_AGNOSTIC reject); commodity registry Phase 1.5+ 真接 data pipeline (§13.1).

**Open Q (defer §5.3)**:
- F2 oracle 是否复用 PCR-CUT (Path 14) 的 patch_routing_core? 单 cut 数学 sound 但 multi-anchor 复用是否 sound?
- max-flow LP dual algebraic witness (defer §13.4)

### 3.3 F3 port_exposure — propositional logic + slot anonymity

**数学根据**: propositional logic (Boolean unsatisfiability) + S_n symmetric group action on slot set (§2.5).

**Cut 形式** [cite spec 03 §1]: 给定 facility port — facility 边界上必须暴露 (用于 belt IO) 的 cell. 每 port 在某方向必 reach free cell. 若两个 facility 互相 block 对方的 port direction (e.g. crusher 出口对着 storage 入口但中间无 free cell), 则二者**互斥**.

cert: 
- (facility_group, facility_pose_id, facility_blocking_dir)
- (blocking_group, blocking_pose_id) — block 上面那个 facility 的 pose

cut.body: `not (x[facility_instance, facility_pose] ∧ x[blocking_instance, blocking_pose])`

**触发条件**: oracle 在 cell-front 检查时发现 port 被 facility 的某 pose 物理 block.

**Slot anonymity** (Step B `45c44d2` close P0-2): cut.body literal 不绑具体 slot id, 必 multiset binding (S_n permutation 不变). validator 必验 cert ↔ literal multiset 严等, 不只 schema check.

反例 (GPT pro v1 round 1 P0-2 真 bug):
- cert blocker `viewer::mfg_crusher_source_013`, cut.literals 错放 `viewer::mfg_crusher_source_014` (同 group 不同 pose)
- 旧 validator 只 schema OK 不绑 → 拿 p13 cert 证 p14, unsound
- Step B 加 multiset binding check: cert.blocking_pose_id == literal multiset entry

**Ghost dependency**: port blocking 取决于 free_cells (= grid \ ghost \ exterior \ cell_owner), 间接依赖 ghost. cut.scope 必绑当前 ghost_rect_id (GHOST_AGNOSTIC reject in Phase 1.2).

**跟其他 family 边界**:
- 适用: 两 facility 互相 block 对方 port direction (literal 互斥)
- 不适用: 单 facility 自己 port 找不到方向 → routing 子问题报 F2 cutset 或 F4 component_reach
- F5 是 F3 的 generalization (任意 multi-literal pattern_nogood); F3 是 F5 的 2-literal 特例

**Phase status**: Phase 1.1 闭环 (Step A/B/J 全 close); evaluate_literal_port_exposure 决定 (defer §10.7).

**Open Q (defer §5.3)**:
- F3 是否可以扩展到 multi-pose port chain (3+ facility 互 block 链)?
- F5 实施后 F3 是否可 subsume 进 F5 (减 family 数)?

### 3.4 F4 component_reach — 4-conn graph BFS connectivity

**数学根据**: 4-connected graph connectivity (BFS / DFS reachability).

**Cut 形式** [cite spec 04 §1]: 给定 commodity `c` (源 src, 汇 sink, demand > 0), free_cells 上 4-conn graph 中 src 跟 sink 必在同一连通分量. 若 ghost / exterior / cell_owner 隔断 → INFEASIBLE.

cert:
- commodity_id (registry require, Step M)
- src_component (bitset, BFS from src)
- sink_component (bitset, BFS from sink)
- separator_cells (cell 集, ghost / exterior / cell_owner 内, 隔断 src 跟 sink)

**触发条件**: oracle 从可独立验证的 routing/geometry witness 检出 src/sink 不连通时；flow diagnostic verdict 本身不构成证书.

**Soundness 关键** (Step D `5c06dff` + Step K close):
- cert.src_component **真**等于 BFS(free_cells, src) 重算 (validator 不信 oracle)
- cert.sink_component 同上
- separator_cells **真**在 grid 内 + ∈ (cell_owner ∪ ghost ∪ exterior)
- src_component ∩ sink_component == ∅
- separator 真 block src 跟 sink (validator 重算 BFS verify)

**Ghost dependency**: separator 含 ghost cells → 直接依赖 ghost. GHOST_AGNOSTIC **直接 reject** (Step O).

**commodity registry** (Step M close): cert.commodity_id ∈ state.commodity_routes 必 require. Phase 1.5+ 真接 generic_io_requirements.json data pipeline (§13.1).

**跟其他 family 边界**:
- 适用: 单 commodity src-sink 不连通 (cell-level)
- 不适用: 多 commodity 共用 cell 导致 routing capacity 不够 → 走 F2 cutset (partition-level)
- F4 是 cell-level pointwise reachability, F2 是 graph-level partition. 一对 src/sink 不连通 → F4; 全 graph 几何 split → F2

**Phase status**: Phase 1.1 闭环 (Step D/F/K/M/O 全 close); Phase 1.5+ commodity registry 真接 data pipeline.

**Open Q (defer §5.3)**:
- F4 是否需引入 cell-flow capacity (cell 同时被多 commodity 用) 概念? 当前只 binary connectivity
- 跨 commodity F4 cut 复用 sound 性?

### 3.5 F5 pattern_nogood — minimal unsat core + QuickXplain

**数学根据**: minimal unsatisfiable subset (MUS) — 给定 unsat conjunction `C = c1 ∧ c2 ∧ ... ∧ cn`, MUS 是 C 的最小子集 `M ⊆ C` 仍 unsat. Computing MUS 是 NP-complete (Liffiton-Sakallah 2008). QuickXplain (Junker 2004) 是 divide-and-conquer minimization, O(k log(n/k)) oracle 调用 where k = |MUS|.

**Cut 形式** [cite spec 05 §1]: 最一般的 cut form. 给定 facility pose 组合 `π_partial = {(i₁, p₁), (i₂, p₂), ..., (iₖ, pₖ)}`, 若受当前 theorem 接纳且可独立复验的 binding / routing / power 或 whole-layout 路径 reject `π_partial` → cut `not(x[i₁, p₁] ∧ x[i₂, p₂] ∧ ... ∧ x[iₖ, pₖ])`.

QuickXplain minimize: 找最小 `π_partial' ⊆ π_partial` 仍被 reject.

**触发条件**: 任何 sub-problem reject master partial assignment 时 (即 LBBD 标准 nogood path).

**复用** [cite spec 05]:
- L16 deletion-based core minimizer (PoC 已 land, paradigm 死但 minimize 算法可复用)
- PCR-CUT (Path 14) QuickXplain helper (Phase 0-4 GO)

**Soundness 关键**:
- π_partial 必真 reject (oracle replay sub-problem 验)
- minimize 后 π_partial' 仍 reject (QuickXplain 每步 verify)
- literal multiset binding (跟 F3 同, §2.5)

**Ghost dependency**: pattern_nogood 跟 ghost 关系取决于 sub-problem. 若 sub-problem 不依赖 ghost (e.g. binding) → GHOST_AGNOSTIC 合法; 若依赖 ghost (e.g. routing) → 必绑.

**跟其他 family 边界**:
- 适用: sub-problem reject 但无明显数学结构 (不是 capacity / cutset / port / connectivity / power)
- 不适用: 已知数学结构 → 走 F1/F2/F3/F4/F6/F7/F8/F9 (更紧)
- F5 是 "兜底" family, 数学上是 LBBD nogood 的直接抽象

**Phase status**: **defer Phase 1.2 P1.2B-F5** — minimize step (step 3) 实施 + QuickXplain 集成 + cert↔literal binding (复 F3 helper).

**Open Q (defer §5.3, critical)**:
- QuickXplain 超时阈值 (NP-complete, 实际 instance 上多大 budget?)
- F5 是否 subsume F3? (F3 是 2-literal 特例)
- minimize 后 sub-problem replay 多大开销?

### 3.6 F6 shape_packing_hall — Hall's marriage theorem

**数学根据**: Hall's marriage theorem (Hall 1935) — 二部图 G = (X, Y, E) 有 perfect matching iff `∀ S ⊆ X, |N(S)| ≥ |S|` (Hall's condition). 反之, 存在 `S ⊆ X` 使 `|N(S)| < |S|` → 无 matching → INFEASIBLE.

项目用 interval graph 版本: facility group of length `k` 需 `k` 连续 cell, 若 boundary 被 ghost 切成多个 interval `I₁, I₂, ...`, 每 interval 长 `Lⱼ` 能容纳 `⌊Lⱼ/k⌋` 个 length-k facility. 总容量 `∑ ⌊Lⱼ/k⌋` 必 ≥ demand `k`.

**Cut 形式** [cite spec 06 §1a]: 给定 boundary `B` 跟 length-k facility group, ghost 切 `B` 成 partition `{I₁, ..., Im}` (各 interval), 总容量 = `∑ⱼ ⌊|Iⱼ|/k⌋`. 若 < demand → INFEASIBLE.

反例 (Gemini 反例 B): boundary length 10, ghost 切成 [1,2,3,4] + [6,7,8,9,10], 总 cell 9 ≥ demand 9 (pass F1 capacity), 但 length-3 facility `⌊4/3⌋ + ⌊5/3⌋ = 1 + 1 = 2 < 3` (Hall 失败).

**触发条件**: oracle 检查 length > 1 facility group 在 boundary 上的 interval cover.

**Ghost dependency**: partition 直接由 ghost 决 → 必绑 ghost_rect_id (GHOST_AGNOSTIC reject).

**跟其他 family 边界**:
- 适用: length > 1 facility (boundary interval cover)
- 不适用: length = 1 (单 cell facility) → 走 F1 (F6 退化成 F1 count)
- F6 是 F1 的 stronger refinement: F1 检 total cell count, F6 检 interval-level cover

**Current status**: F6 implementation exists in `src/cuts/`, but production Step 8 integration remains future P1.3 work — Hall theorem check + interval graph cover algorithm.

**Open Q (defer §5.3)**:
- F6 是否扩展到 2D (interior facility group 占多 row/col)?
- interval graph 反例边界分类 (各 length-k 反例覆盖率)?

### 3.7 F7 power_hitting_set — set cover NP-hard + LP relaxation

**数学根据**: set cover (Garey-Johnson 1979 NP-complete), LP relaxation + greedy ln(n) approximation (Chvátal 1979).

项目用对偶版: hitting set — 给定 cover requirement (各 facility 必被至少一 power_pole 覆盖) + power_pole candidate 集 (每 pole pose 覆盖一个 cell 集), 找最小 power_pole assignment cover 所有 facility.

**Cut 形式** [cite spec 07 §1]: 若 facility group `g` 的 power_cover_domain (即覆盖 g 所有 pose 的 power_pole 候选集) **空** → INFEASIBLE.

Phase 1.5+ refine: 即使 power_cover_domain 非空, 但所有 power_pole candidate 都被其他 facility 占 cell → INFEASIBLE (hitting set 实际 unsat).

cert:
- (facility_group, facility_pose_id) — 被 block 的 facility
- power_cover_witnesses (空 list, 标记 cover_domain == ∅)
- cell_owner causation split (v1.1 Gemini round 14)

**触发条件**: oracle 在 master partial assignment 检查时 detect 某 facility 找不到 power_pole 覆盖.

**Ghost dependency**: power_cover_domain 含 ghost cells → 必绑 ghost_rect_id.

**LP relaxation 关系**: set cover LP relax 有 ln(n) approximation, 项目用 exact CP-SAT 不是 LP relax. F7 是 oracle 检查 set cover 必要条件 (power_cover_domain ∅), 不解 set cover 本身.

**跟其他 family 边界**:
- 适用: facility 找不到 power_pole 覆盖
- 不适用: power_pole 不连通 → 走 F8 (power_grid_reach)
- F7 是 set-level cover existence, F8 是 graph-level grid connectivity

**Phase status**: **defer Phase 1.2 P1.2B-F7** — set cover schema + cell_owner causation split + literal binding.

**Open Q (defer §5.3, critical)**:
- LP relax ln(n) approximation 实际 instance 上是否紧?
- F7 跟 master.solve 的 power_coverage constraint 冲突? (master 已有 power constraint, F7 是 cut layer)

### 3.8 F8 power_grid_reach — Liang-Barsky AABB intersection

**数学根据**: Liang-Barsky line clipping algorithm (Liang-Barsky 1984) — 2D 线段跟轴向 rectangle (AABB, Axis-Aligned Bounding Box) intersection 的 closed-form 解.

项目用: power_pole 之间需 line-of-sight 连接 (不被 ghost / facility 阻挡). 若 ghost 的 AABB block 两 power_pole 之间所有可能 line segment → power network 不连通.

**Cut 形式** [cite spec 08 §1]: 给定 power_pole `p₁`, `p₂`, 两 pole 之间 4-conn path 必须穿过若干 cell. 若所有 path 都被 ghost AABB block (Liang-Barsky 严格 line-segment intersection, **不**是 cell-level 4-conn block) → INFEASIBLE.

v1.1 关键 (Gemini round 14 finding): `ghost_blocks_line` 改严格 line-segment AABB intersection, 不是 cell-level 离散 block (后者会假阳).

**触发条件**: oracle 在 power network connectivity 检查时 detect 两 pole 之间无 viable line-of-sight.

**Ghost dependency**: 直接由 ghost AABB block → 必绑 ghost_rect_id.

**跟其他 family 边界**:
- 适用: power_pole 之间 line-of-sight 被 ghost block
- 不适用: power_pole 找不到 cover facility → 走 F7
- F8 跟 F4 同是 connectivity, 但 F4 是 cell-level 4-conn (belts), F8 是 line-of-sight (power network)

**Phase status**: **defer Phase 1.2 P1.2B-F8** — Liang-Barsky 实施 + 退化 case (零长度 / 共线 / 正交).

**Open Q (defer §5.3)**:
- Liang-Barsky 退化 case (零长度 / 共线 / 正交) 数学边界?
- power network 拓扑跟 belt routing 是否独立? (当前假定独立)

### 3.9 F9 density_envelope — geometric upper bound (**area-only**)

**数学根据**: geometric upper bound — 给定 region (window) `W` 跟 facility group, 该 group 在 W 内**占用面积**之和必有上界. 形式化:

```
∑_{i ∈ g, π(i) placed} |occupied_cells(π(i)) ∩ W| ≤ max_allowed_area(W, g)
```

其中 `max_allowed_area(W, g)` 必是**安全上界** (e.g. `|W| - |ghost ∩ W| - |exterior ∩ W| - |cell_owner_other ∩ W|`), 由 oracle 用 area_capacity_overflow witness 提供. **等号不 cut, 严格 `>` 才 cut**.

**关键 invariant (PROJECT_LOCK §3A + Gemini math review meta-audit 2026-05-23)**:

F9 generator **只接受** `area_capacity_overflow` witness, **拒绝**:
- `routing_overflow` (走 F2 cutset 或 F5 fallback)
- `binding_overflow` (走 F5 fallback)
- `pcr_cut_overflow` (走 F2 + F5 fallback)

理由: routing/binding 死锁依赖端口朝向、相对位置、障碍细节; 泛化成 "窗口里设施太密" 会**误剪**合法解 (PROJECT_LOCK 锁死).

**Cut 形式** [cite spec 09 §1]: cert 含 `window_rect (x,y,h,w)` + `group_id` + `max_allowed_area` + `oracle_witness_kind="area_capacity_overflow"` + `oracle_assignment_witness` + `ghost_rect_repr`.

**Evaluator (area-based)**: 
```python
occupied_in_window = sum(
    1
    for cell, (owner_group, _) in state.cell_owner.items()
    if owner_group == cert.group_id and cell in W
)
return occupied_in_window > cert.max_allowed_area
```

不是 instance count (any-overlap → whole facility 算法历史 unsound FP), 不是 origin-in-window (anchor 在 W 内算 whole), 不是 all-in-window (整 facility 在 W 内才算, 漏算 edge partial). **必须** `sum(|pose_cells ∩ W|)`.

**Step 8 注入**: master `sum(area_overlap[p, W] * x[g, p]) <= max_allowed_area`, 把 area overlap 当线性系数, 不在 Python callback 动态算.

**Morphology safe/unsafe (Gemini math review meta-audit notes)**:

morphological erosion 是 strong helper, **不是** density theorem.

- ✅ **Safe use**:
  - 算 region 内 "facility 全装进 W" 的合法 anchor 域
  - 证明 10×1 走廊装不下 3×3 facility
  - F6 shape packing / Hall-style upper bound 候选域收缩
  - 给 area_capacity_overflow oracle 找 tighter witness window
- ❌ **Unsafe leap**: `capacity(W, 3x3) = number_of_eroded_anchors(W)` — anchor 数只是上界, 忽略 facility 之间 overlap. anchor outside W 仍可贡献 area inside W (F9 area-based 不是 anchor-based).

如 morphology 产 cut, cert 必声明语义 (all-in-window placement / overlap-window area / anchor-domain empty / shape packing matching), validator 必独立重算同 semantic.

cite: `docs/research/p3_b_design_v2_20260521/external_review/gemini_math_review_bundle_20260523/notes/F9_MORPHOLOGY_CAUTION.md`

**Ghost dependency**: max_allowed_area 含 `|ghost ∩ W|` → 跨 ghost 不 invariant, 必绑 ghost_rect_id.

**跟其他 family 边界**:
- 适用: window 内总占用 area 超 safe upper bound (F1 capacity 跟 demand 不紧时 F9 catch)
- 不适用: routing / binding / power 死锁 → 走 F2 / F4 / F7 / F5
- F9 跟 F1 数学关系: F9 area-based (sum pose ∩ W), F1 cap_R cell-based (整 region 容量). 不是 F1 的 scope 扩展, 是**互补 family** (area vs count semantics)

**Current status**: F9 implementation exists but tight-K remains quarantined; it is not current production proof authority — area-based evaluator + area_capacity_overflow witness only + morphology helper. 历史 L14 weighted occupancy 死路 (interior LP=1.0 永不可 cert) 教训已 freeze 到 area-only invariant.

**Open Q (defer §5.3)**:
- F9 area-based vs F1 cell-based 哪些 INFEASIBLE 二者都拦? 哪些只有一个能拦?
- morphology erosion 给 area_capacity_overflow oracle 找 tighter window 的算法?

### 3.10 跨 family 数学关系 summary

| Family 对 | 关系 |
|---|---|
| F1 ↔ F6 | F6 是 F1 stronger refinement (interval cover vs count) |
| F1 ↔ F9 | **互补 family**（F9 area-based vs F1 cell-based；**非** F1 scope 扩展，见 §3.9）|
| F2 ↔ F4 | F2 是 partition-level, F4 是 pointwise; F4 ⊆ F2 |
| F3 ↔ F5 | F3 是 2-literal pattern, F5 是 multi-literal generalization; F3 ⊆ F5 |
| F4 ↔ F8 | F4 是 cell 4-conn (belts), F8 是 line-of-sight (power); 独立 |
| F7 ↔ F8 | F7 是 cover existence, F8 是 grid connectivity; 互补 |

**完整性 question (§5.1 详)**:
- 9 family 是否 cover 所有 INFEASIBLE 类? — open
- 是否需 F10+ family? — defer Phase 2+ 决策

---

