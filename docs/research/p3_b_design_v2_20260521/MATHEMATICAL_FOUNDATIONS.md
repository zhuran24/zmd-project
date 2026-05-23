# 项目核心数学思路 + 待定问题 (Mathematical Foundations & Open Questions)

终末地 (Arknights: Endfield) IndustrialPlanner 70×70 grid certified exact solver 的数学层全景. 不抄各 spec 详 (那是 `cut_lifecycle_v2.md` / `state_machine_v2.md` / `cut_family_specs/` 的事), 也不重复 plan doc 实施细则 (那是 `PHASE_POST_1_1_REFACTOR_PLAN.md` 的事). 本文档专注:

1. **已确定**的数学 paradigm 选择 + 各 family 数学根据 summary + 死路 paradigm 数学分类
2. **未确定**的 mathematical open questions — 数学层哪些问题当前没答案, 哪些是 frontier, 哪些是 defer 决策点

写给:
- 实施 Phase 1.2-1.5+ 的 implementer (理解为啥这么做)
- 外部 reviewer (GPT pro / Gemini / math consultant) — 验数学根据是否扛得住
- 未来 maintainer (数月后接手) — 快速 anchor 项目的 mathematical contour
- 用户 (审项目数学严肃性) — 看哪些是已 verify 哪些是 open

---

## 0. 文档目的 + 受众

### 0.1 目的

项目历史走过 27 个 paradigm 死路 (paradigm_death_timeline_27_lever.md) — 不是工程 bug, 是**数学根据不通**. 这教训让我们意识到: **paradigm 选择必先数学层 verify**, 不能"试着搞搞看". 但项目当前没集中文档讲清楚:

- 已选 paradigm 的数学根据**到底**是什么 (cut_family_specs/ 每个 family 各自详 spec, 但没整体跨 family 数学根据 summary)
- 各 paradigm 死路**数学上**为啥死 (paradigm_death_timeline_27_lever 列了 27 lever 但偏 chronological + verdict, 没按数学根据分类)
- 当前还有哪些数学问题**没答案** (各 spec 末尾各有 Open Questions, 没集中, 哪些是 critical 哪些是 defer 看不清)

这份文档**就是回答这三个问题**, 给项目数学层一个 SoT (Single Source of Truth) 索引.

### 0.2 受众分流

**implementer (Phase 1.2-1.5+ 接手)**
- 入口: §2 已确定 paradigm overview → §3 各 family 数学根据
- 实施 family X 前必读 §3.X (数学根据) + §5.3 X 的 open Q (实施时会遇到啥)
- §4 死路 paradigm 是 negative knowledge — 知道**不要做什么**

**外部 reviewer (GPT pro batch audit / Gemini per-commit cross-check / 数学 consultant)**
- 主战场: §3 各 family 数学根据是否扛得住 + §5 open Q 是否真 open
- context: §1 问题陈述 + §2.1 paradigm 选择 + §4 死路 paradigm baseline (为啥不重蹈)
- 我们对 reviewer 的期待: 验**数学层** soundness (不只 spec 一致), push adversarial 反例构造

**未来 maintainer (数月-数年后)**
- 进入: §1 问题陈述 → §2 paradigm overview → §7 跟相关 spec 关系
- 各 family 进 §3 锚 spec
- 决策时翻 §5 open Q 看当时为啥没定

**用户 (审 progress + 数学严肃性)**
- §1 数学问题陈述 — 项目目标的形式定义
- §4 死路 paradigm summary — 走过多少路确定不通
- §5 open Q — 哪些数学问题还没答案

### 0.3 文档原则

- **不重复 spec** — 各 family 详在 `cut_family_specs/0X.md`, 本文档只 summary + cite
- **不重复 plan** — 实施 timeline 在 `PHASE_POST_1_1_REFACTOR_PLAN.md`, 本文档只数学根据
- **不重复 death timeline** — 27 lever 详在 `paradigm_death_timeline_27_lever.md`, 本文档只按数学根据分类
- **数学 first, 工程 second** — 数学 paradigm 不通就不实施, 不"先试试看"
- **open Q 必标 (defer / critical / informational)** — 不混级别

### 0.4 cite 约定

- `[cite spec X §N]` — `cut_family_specs/0X_<name>.md` § N
- `[cite lifecycle §N]` — `cut_lifecycle_v2.md` § N
- `[cite state §N]` — `state_machine_v2.md` § N
- `[cite plan §N]` — `PHASE_POST_1_1_REFACTOR_PLAN.md` § N
- `[cite death-timeline LN]` — `paradigm_death_timeline_27_lever.md` lever N
- `[cite lock §3A]` — `PROJECT_LOCK.md` § 3A
- `[[memory-name]]` — Claude memory entry

---

## 1. 项目数学问题陈述

### 1.1 形式定义

**问题**: 在 `G = {0, 1, ..., 69} × {0, 1, ..., 69}` 70×70 grid 上, 给定:

- 266 个 mandatory facility instance, 每个 instance `i` 有 facility template `t(i)`, 占 `cells_per_pose(t)` cells
- 每 instance `i` 有有限的 candidate pose 集 `P(i) ⊆ Poses` (pose = (位置, 方向, port_mode) 三元组)
- canonical_rules: 17 recipe + facility templates + targets + commodity types
- generic_io_requirements: commodity flow demand 表
- mandatory_exact_instances: 必装 instance 列表 + per-instance placement_rule (e.g. boundary-only / power-zone-required)

**找**: 一个 (ghost rectangle, pose assignment) 二元组 `(R, π)` 使:

```
R 是 G 内的轴向 rectangle, π: instances → poses 满足 π(i) ∈ P(i)
       all_cells(π) ∩ R = ∅                        (1) ghost 内无 facility
       ∀ i ≠ j, occupied_cells(π(i)) ∩ occupied_cells(π(j)) = ∅   (2) 不重
       ∀ i, placement_rule(i) holds for π(i)        (3) per-instance rule
       port_binding(π) feasible                     (4) port 匹配可行
       routing(π) feasible                          (5) belts 能连
       power_coverage(π) feasible                   (6) 电力网覆盖
```

**objective**: `max_lex(area(R), min_side(R))` — 先大面积, 同 area 选 min_side 大的 (`min_side(R) ≥ 6` 是 admissibility 不是 tie-break).

**输出**: `(R*, π*)` + **certified proof** (sound 数学证明, 见 §1.3 "certified" 定义).

### 1.2 离散组合优化空间复杂度

**Pose enumeration**: 当前 production data `candidate_placements.json` ~81795 pose / 266 instance ≈ 平均 308 pose/instance.

**Ghost rectangle 候选**: 70×70 grid 内 rectangle 数 = `C(71, 2)² ≈ 6.4 million`. 加 min_side ≥ 6 admissibility 后 ~3 million; outer search frontier 实际 reach ~1000-10000 candidate (Phase 3A frontier 设计).

**Assignment 决策空间**: 266 instance × 平均 308 pose ≈ 8 × 10⁷ raw configuration, 含 placement_rule + port + routing + power 后 sound subspace 量级未定 (master.solve 解不动证).

**Hardness**: max empty rectangle in general grid with constraints 是 NP-hard (reduce from rectangle packing + bin packing). 项目用 CP-SAT exact (not approximation), 通过 LBBD + cut framework 工程 prune 收敛.

### 1.3 `certified_exact` 跟 `exploratory` 的形式区分

**certified_exact (项目主路径, 本文档全 scope)**
- **soundness**: 输出 `(R*, π*)` 必伴随 mathematical proof — π* 满足所有 constraint (1-6), 且对任何 R 更大的 `(R', π')` (即 lex(area(R'), min_side(R')) > lex(area*, min_side*)) 必 infeasible
- **completeness (current scope)**: 不要求绝对 complete — 168h campaign 内 prove 当前 best 是 optimum 即 done; 超 168h timeout 时报 UNPROVEN (不是 wrong)
- 输出 proof object 必包含: `(R*, π*)` + 各 instance assignment + binding + routing + power + 各 sub-problem certificate
- proof object 必 replay-validatable (跨 session / 跨 hardware)

**exploratory (历史路径, future_scope, 不在本文档)**
- 启发式 / approximation, 无 sound proof
- 历史 cap (e.g. 50 power_pole + 10 storage_box) 是 exploratory 用, 不进 certified_exact
- exploratory artifact 不算 certified proof, 跨 path 不混 `[cite lock §3A]`

**严格分离原则**: postprocess (adapter / render / export) 仅消费 certified proof, **不**重定义 solve schema. cut framework 完全在 certified_exact path 内.

### 1.4 跟 LBBD 的关系

项目核心 paradigm = **Logic-Based Benders Decomposition (LBBD)** + **cut framework**.

**LBBD 4 层 sub-problem**:
1. master — 找 `(R, π_placement)` (instance → pose), 含 ghost rectangle
2. binding — 验 port binding 是否可行 (per-instance ports 怎么 connect)
3. routing — 验 belt routing 是否可行 (grid path 连接所有 port 对)
4. flow — multi-commodity flow diagnostic (诊断 routing INFEASIBLE 时 why)

每层 INFEASIBLE → 出 nogood 信号 → master 加 lazy constraint → master re-solve.

**Cut framework** 是 LBBD nogood 的**累积 sound 知识层** — 不替代 master, 在 master 外把 sub-problem 历史 nogood 抽象成 reusable cut (across candidate, across ghost), 防 master 反复学同一个 lesson.

### 1.5 项目内 "sound" 的形式定义

**Soundness (cut framework 内)**:
> 一个 cut `c` 是 sound iff: 任何满足 cut.scope 条件的 master assignment, 加上 cut 后排除的 literal/geometry 都不可能延伸出 (1-6) 全部满足的 `(R, π)`.

形式化: `c.scope(R, π) ⇒ (c.excludes(π) ⇒ ¬feasible(R, π))`

**Soundness ≠ completeness**:
- sound = "排除的都该排除" (no over-prune)
- complete = "该排除的都排除了" (no under-prune)
- cut framework 当前只 verify sound (validator 重算 cert), 不 verify complete (complete 是 §5.1 open Q)

**Adversarial soundness** 加层: validator 不信 oracle (oracle 可 Byzantine 产假 cert), 必须独立从 BState + cert 重算 verify, 见 §2.6.

---

## 2. 已确定核心数学 paradigm

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
- 项目 4 层 sub-problem (binding / routing / flow / power) 跟 master 隔离, 各层 INFEASIBLE 独立 → cut framework 各 family 对应一类 nogood pattern

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
    if cut.scope.source_digest ≠ state.source_digest:
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
- 当前 Phase 1.1 placeholder `"poc_source_digest"`
- Phase 1.2 §10.3 改真 hash: `sha256(canonical_rules.json) + sha256(candidate_placements.json) + sha256(mandatory_exact_instances.json) + sha256(generic_io_requirements.json)`
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

cut 从产到 attach master 经 9 step [cite lifecycle §2]:

| Step | 名 | 数学职责 | 当前实施 |
|---|---|---|---|
| 1 | canonicalize | 跟产 cert 物理 (normalize bitset / sort literals) → 同 cert 哈希等 | Phase 1.1 闭环 |
| 2 | generate | oracle 产 cert (允许 Byzantine, 不信任) | Phase 1.1 4 family ready |
| 3 | minimize | 产最小 cut (deletion-based / QuickXplain, F5 用) | **defer Phase 1.2 P1.11** |
| 4 | serialize | cert + body → JSON | Phase 1.1 闭环 |
| 5 | deserialize | JSON → cut object (validate schema) | Phase 1.1 闭环 |
| 6 | validate | validator 重算 cert, 决定 sound/unsound | Phase 1.1 闭环, 4 family |
| 7 | attach-scope check + evaluate | scope.matches(state) + body 重算 sound | Phase 1.1 dispatch + 4 family evaluator |
| 8 | apply-to-master | cut.body → master.AddLinear / cp_sat lazy | **defer Phase 1.3 P1.21** |
| 9 | replay (on ghost/state change) | re-validate active/held cut, decide ATTACH/HOLD/QUARANTINE | Phase 1.1 闭环 (Step M fail-closed) |

**Step 8 missing 当前是为啥 cut framework 跑 unit test 但**没真接进 master** — Phase 1.3 实施.

**Step 3 missing 影响**: F5 deletion 当前不能产 minimal unsat core, F5 实施 (Phase 1.2 P1.11) 时同步落 step 3.

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

**LP relaxation 关系** [cite spec 01 §1c]: F1 是 master LP relaxation 的 valid inequality, 通过 Farkas dual ray 可**自动**被 identified (复用 cand C `farkas_certificate.py`). 这意味着 F1 oracle 不仅是启发式产 cert, 还有 LP dual 数学根据.

**P(g) ⊆ R 验证** (GPT pro v3 P0-1 真 bug):
- `demand_R` 定义要求 facility group `g` 的**所有** candidate pose 必 ⊆ R
- 反例: `boundary_io` group 46 instance, candidate_placements 含 BSP pose, 但 14 pose 占 cells **不在** boundary union — `placement_rule_for_group` 是必要不充分
- Step E (commit `8a38401`) 加 strict P(g) ⊆ R check: 对 group `g` 所有 pose 验 `occupied_cells(pose) ⊆ R`, 否则不算 contributing

**跟其他 family 边界**:
- 适用: region cap < demand 几何不可达
- 不适用: cap ≥ demand 但 routing/power/binding 不可行 → 走 F2/F4/F7
- 跟 F6 关系: F6 是 F1 的 stronger refinement (Hall theorem 检 interval cover, F1 只检 count)

**Phase status**: Phase 1.1 production validator + oracle + evaluator 闭环 (Step E/F/G/L/O 全 close); Phase 1.2 入门加 GHOST_AGNOSTIC 跟 source_digest hard binding (§10.3).

**Open Q (defer §5.3)**:
- F1 oracle 如何 enumerate 有用的 interior_rect region (NP-hard exhaustive)?
- LP dual Farkas certificate 是否可以**自动**触发 F1 cut 不需 oracle?

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

**触发条件**: oracle 在 flow_diagnostic / routing 子问题 detect src/sink 不连通时.

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

**Cut 形式** [cite spec 05 §1]: 最一般的 cut form. 给定 facility pose 组合 `π_partial = {(i₁, p₁), (i₂, p₂), ..., (iₖ, pₖ)}`, 若 sub-problem (binding / routing / flow / power) reject `π_partial` → cut `not(x[i₁, p₁] ∧ x[i₂, p₂] ∧ ... ∧ x[iₖ, pₖ])`.

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

**Phase status**: **defer Phase 1.2 P1.11** — minimize step (step 3) 实施 + QuickXplain 集成 + cert↔literal binding (复 F3 helper).

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

**Phase status**: **defer Phase 1.2 P1.12** — Hall theorem check + interval graph cover algorithm.

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

**Phase status**: **defer Phase 1.2 P1.13** — set cover schema + cell_owner causation split + literal binding.

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

**Phase status**: **defer Phase 1.2 P1.14** — Liang-Barsky 实施 + 退化 case (零长度 / 共线 / 正交).

**Open Q (defer §5.3)**:
- Liang-Barsky 退化 case (零长度 / 共线 / 正交) 数学边界?
- power network 拓扑跟 belt routing 是否独立? (当前假定独立)

### 3.9 F9 density_envelope — geometric upper bound

**数学根据**: geometric upper bound — 给定 region `R` 跟 facility group, region 内 facility 数密度 `cap_R / |R|` 必 ≤ 1.0 (trivial baseline). 若 oracle 找到更紧的 envelope (e.g. cell_owner 已占, 实际剩余 cap < trivial bound), 可作为 cut.

**Cut 形式** [cite spec 09 §1]: F9 是 F1 region_capacity 的弱化 / scope 扩展版 — 用 geometric density bound 代替 exact cap. cert 记 region + envelope cap (上界) + actual_cells_in_R (重算).

**触发条件**: Gemini round 15 Class C mitigation 推荐, 当 F1 cap_R 不紧 (e.g. cell_owner 占多但 F1 不能扣) 时 F9 提供更弱 bound.

**Ghost dependency**: 同 F1 (cap 含 ghost contribution).

**v1.1 关键 (L14 weighted occupancy 死路 verdict 教训)**: F9 density 不能用 `cap/area=1.0` interior LP relax (永不可 cert), 必须用真重算的 envelope. L14 死法详 §4.3.

**跟其他 family 边界**:
- 适用: F1 cap_R 不紧但 region 仍 over-demanded (geometric envelope catch)
- 不适用: cap_R 紧 → F1 直接 cert
- F9 是 F1 的 scope 扩展 (允许更弱 bound), 不是 stronger cut

**Phase status**: **defer Phase 1.2 P1.15** — envelope 重算 + baseline 紧度 catch.

**Open Q (defer §5.3)**:
- F9 envelope baseline=1.0 是否 trivial (永不 cert) 还是 stronger bound (L14 教训)?
- F9 跟 F1 数学上是否真独立 (F9 cap 严格 ≥ F1 cap)?

### 3.10 跨 family 数学关系 summary

| Family 对 | 关系 |
|---|---|
| F1 ↔ F6 | F6 是 F1 stronger refinement (interval cover vs count) |
| F1 ↔ F9 | F9 是 F1 scope 扩展 (允许更弱 envelope bound) |
| F2 ↔ F4 | F2 是 partition-level, F4 是 pointwise; F4 ⊆ F2 |
| F3 ↔ F5 | F3 是 2-literal pattern, F5 是 multi-literal generalization; F3 ⊆ F5 |
| F4 ↔ F8 | F4 是 cell 4-conn (belts), F8 是 line-of-sight (power); 独立 |
| F7 ↔ F8 | F7 是 cover existence, F8 是 grid connectivity; 互补 |

**完整性 question (§5.1 详)**:
- 9 family 是否 cover 所有 INFEASIBLE 类? — open
- 是否需 F10+ family? — defer Phase 2+ 决策

---

## 4. 已 verify 不通的 paradigm (数学死路 baseline)

本节按**数学根据 attempt** 分类 27 lever (paradigm_death_timeline.md 按时间 + 死因 axis 分 5 Class, 本节按"当时试什么数学方向"reorganize). 不重复 timeline 详, cite memory + timeline.

### 4.1 完整 master 重写 paradigm — pose-bool / augmented / GOC variant 全死

**数学 attempt**: 改 master variable basis, 让 master 自己解 pose-level + binding + routing + power 联合优化, 不依赖 sub-problem.

**lever**:
- **L11-L16 B1 pose-bool master** — 27×15 interior pose-bool 7.2s FEASIBLE (vs coord 30 min UNKNOWN). Phase 4 routing convergence 🟡 ~500-610 ports 系统性, pose-bool master 不知 port direction. Phase 5 cell cut 3 form 全 over-restrictive. Phase 6 path-1 4 form 全 verdict 死. [[project-b1-phase6-path1-dead]]
- **Lever 24 augmented master** — 280K pose × 8 ports = 2.36M OnlyEnforceIf, 603.9s UNKNOWN + RSS 32 GB. [[project-lever24-augmented-master-dead]]
- **GOC-C2** — 全图 owner-optional, RSS 25 GB > 12 GB cap. [[project-goc-phase0-verdict]]
- **PGW-UB** — positive witness + UB closure, locality 全 fail. [[project-pgw-phase0-verdict]]
- **L23 rewrite_path_exhausted** — 所有 viable 重写路径实测后 hard verdict. [[project-rewrite-path-exhausted]]

**数学根据失败的层**: 
- **Root cause 1** (Class A death timeline): pose-bool master 表达力 fundamental limit. master 不知 binding port-selection / routing path / power coverage 关联, 任何 master OPTIMAL 都让 sub-problem oracle 拒绝.
- 6 paradigm 撞同墙 (B1 path 1 / path 2 / Path 12 RAB-SEP / Path 13 SAC-Hull / Path 14 PCR-CUT / Path 17 D2)

**教训**: master variable basis 改不通. **不能再 propose master 重写**.

### 4.2 Sub-problem cut paradigm — over-restrictive / 不收敛 全死

**数学 attempt**: 在 sub-problem (routing / binding / flow) INFEASIBLE 时找 cut, master 不动.

**lever**:
- **Path 12 RAB-SEP** (routing-aware binding separation) — cert tight 8/8 UNPROVEN. 单独 binding-port cut 不 sufficient. [[paradigm-death-timeline LP12]]
- **Path 13 SAC-Hull** (separating axis capacity hull) — violations 减 80% 但 necessary ≠ sufficient. L2 工作但 binding/routing reject. [[paradigm-session-2026-05-18-19]]
- **Path 14 PCR-CUT** (patch belt CP-SAT min-cut) — Phase 0-4 GO, Phase 5 multi-anchor 0/8 CERTIFIED. cut 表达力被 pose-bool master 卡死. [[project-pcr-cut-phase5-verdict]]
- **D2 Path 17** (commodity cell-flow + arc + conditional flow) — multi-anchor 0/8 CERTIFIED 跟 Path 12-14 同质. [[project-d2-path17-verdict]]
- **B1 Phase 5 cell cut** — 3 种 cell-level cut 全 over-restrictive. [[project-b1-phase5-cell-cut-findings]]
- **B1 Phase 6 path-2 lazy demand cut** — UNPROVEN 778s 10 iter 不收敛. [[project-b1-phase6-path2-dead]]
- **L16 Lazy Power Completion** — master 端 81.8s OPTIMAL, 但 cut 端 loose 134→133 stuck / tight 134→123 振荡. [[project-l16-lazy-power-completion-phase0]]

**数学根据失败的层**:
- **Root cause 1**: cut 表达力被 pose-bool master 卡死 (master 不知 sub-problem 关联)
- **Root cause 2** (Class A): cut amplification 不够 — 单 cut sound 但不 sufficient
- **Root cause 3** (Class C): cut family abstraction 不够 — 等价 full no-good, 几何上不能 sub-linear

**教训**: 简单的 sub-problem nogood lift 跨 multi-anchor 必败. B Design v2 cut framework 不走这条 — 而是用 family-specific 数学根据 (Menger / Hall / pigeonhole) 作 sound deduction, 不是 ad-hoc cut form.

### 4.3 Cert lifting paradigm — symmetry / orbit lifting 死

**数学 attempt**: 学到 cert 后试 lift 跨 instance / 跨 orbit / 跨 candidate, 减 cut 数.

**lever**:
- **Path 18 LIC (layout-invariant cert)** — m1=2 远低于 ≥100 target. cell-front pattern 几乎决定 pose (per-instance mean=1.74), cut lift 不跨数量级. [[project-path18-layout-invariant-cert-dead]]
- **Lever 26 Benders symmetry** — typed automorphism graph + cut-orbit lifting, m5=1.0 (5/5 core 全 trivial orbit). symmetry 被 ghost/boundary/port_dir 打碎. [[project-lever26-benders-symmetry-dead]]

**数学根据失败的层**:
- **Root cause 3** (Class C): cell-front pattern 已 break symmetry. per-instance 几何 high-resolution 让 sub-pose 等价性消失.
- LIC m1=2 / Benders symmetry m5=1.0 都 measure 出 lifting "free lunch" 不存在.

**教训**: 项目 layout 是 anti-symmetry 的 (各 instance + ghost + boundary + port direction 全打碎对称). PROJECT_LOCK §3A 禁跨 instance lifting 是这一层的结论. **within-instance** lifting (PCR-CUT Phase 3 signature lifting) 可以 sound 但跨 instance 必死.

### 4.4 Column generation paradigm — cand C 96% utilization 几何死结

**数学 attempt**: 用 LP-based column generation, master 持 column (pose 子集) 不持 full pose-bool. Phase 0 Phase 1 m9 dual + m10 sound 性 8/8 GO.

**lever**:
- **cand C Phase 0** — 20-inst 8/8 metric GO, 唯一真换 master variable basis 方向 ✅ [[project-cand-c-column-generation-phase0-go]]
- **cand C Phase 1** (4-ramp) — 5/20/40/80 inst 全 GO ✅ [[project-cand-c-phase1-go]]
- **cand C Phase 2 v3 — 160/266 INFEASIBLE** — A1/A2/A3 3 fallback paradigm 全 land 但 160/266 实测仍 INFEASIBLE. [[v14-review-findings]] cand_c_phase2_v3

**数学根据失败的层**:
- **Root cause 2** (Class E): 96% utilization 几何死结. valley4_protocol_core 70×70 + 266 mandatory = 4800/4900 cells = 96%. boundary_storage_port × perimeter trap: 46 pose × 3 cells = 138 cells 必 100% saturation. cand C column gen 数学 sound 但底层几何不变.

**教训**: paradigm 数学 sound 不等于 instance 可行. 项目 instance 几何是 fundamental constraint, 任何 paradigm 在 instance 真 INFEASIBLE 时都 INFEASIBLE. column gen 是 master basis 改而不是 instance 改, 不能改 instance 几何.

### 4.5 Set-packing prover / IHS paradigm — 攻错层

**数学 attempt**: 抽出 set-packing 核心独立解, 不动 master.

**lever**:
- **L15 set-packing prover** — minimum set-packing 核心 CP-SAT 几秒搞定 (corner 2.3s INFEASIBLE, interior 7s feasible). 真瓶颈是 master **多余**约束 (port/power/connector). paradigm 攻错层. [[project-l15-setpacking-prover-dead]]
- **Lever 25 IHS (Implicit Hitting Set)** — Phase 0 cheap gate 10 iter 全 size=1 core (p50=1.0), offline HS compression=1.0 (HS=union 完全退化). [[project-lever25-ihs-dead]]

**数学根据失败的层**:
- L15: paradigm 攻的是 set-packing 子结构, 但 instance 主瓶颈不在 set-packing — 在 port + power + connector 约束的组合. 抽掉子结构不解原问题.
- L25: IHS Phase 0 core size 全 1, hitting set 数学退化 trivial.

**教训**: paradigm investment 前**必 Phase 0 cheap gate** 验前提. L15 用 3 小时 PoC catch "攻错层", L25 用 10 iter cheap gate catch "core 全 trivial". [[paradigm-phase0-cheap-gate]] 来源.

### 4.6 Witness / weighted occupancy / heuristic blueprint paradigm — 前提错估 死

**数学 attempt**: 用 witness / weighted bound / community blueprint 作 hint 加速 master.

**lever**:
- **v8 anchor slicing** — GPT v8 patch clean apply + 2211 pytest pass + build wall -92% 真实, 但单 anchor 5 min UNKNOWN 5.5M branches. 错估 — 关注 build 没量 solve. [[project-v8-anchor-slicing-dead]]
- **v10 witness preflight** — community blueprint 缺 41 mandatory, greedy 填位置破坏 27×15 空地, compatible anchor=0. [[project-v10-witness-preflight-dead]]
- **L14 weighted occupancy** — Farkas weighted-occupancy blocker oracle, interior anchor LP=1.000 exact 永远不可 cert. [[project-l14-weighted-occupancy-dead]]
- **D step 2 blueprint hint** — blueprint A 路径死, master inherent 难解非 hint failure. [[project-d-step2-hint-landed]] superseded

**数学根据失败的层**:
- v8/v10: paradigm 数学 sound 但**前提错估** — v8 关注 build wall 没量 solve quality; v10 假定 blueprint 含 41 mandatory 但实际缺. [[gpt-error-types-taxonomy]] 区分: 算法错估 vs 前提错估 vs 数学能力上限.
- L14: weighted occupancy LP=1.000 是**数学能力上限** — interior anchor 几何 inherent 不可 cert. L14 修不了, 是 paradigm 类不够强.

**教训**: paradigm 实施前必 verify 前提 (data 真满足 hidden assumption 吗?). GPT review 给方案带 hidden assumption 是常态, audit armor 要明确要求 reviewer 给出"该方案需 data 满足什么"清单. [[gpt-review-prompt-armor]] 来源.

### 4.7 Solver 替换 paradigm — HiGHS / LP-MIP 全死

**数学 attempt**: 换 OR-Tools CP-SAT 为 HiGHS / Gurobi / 其他 LP-MIP solver, 期待 RAM/wall 下降.

**lever**:
- **HiGHS rewrite blocker** — PoC 42 GB > OR-Tools 30 GB (Phase 3B repair5). LP-MIP 对 dense linear constraint 不适合. [[project-highs-rewrite-blocker]]
- **L23 rewrite path exhausted** — 所有 viable 重写路径实测/推理后 hard verdict: 单机 48 GB + 准确性必保 + 现 solver, 决定性收益物理不可达. [[project-rewrite-path-exhausted]]

**数学根据失败的层**:
- **Root cause 4** (Class D): single-machine RAM 不可扩. solver 之间差异 < 单机 cap 限制.
- LP-MIP 对项目这类 dense + indicator + cross-product constraint 不适合 — propagation cost CP-SAT 实测最优.

**教训**: solver 不是瓶颈. paradigm 是. **不能再 propose solver 替换**.

### 4.8 共同 root cause (4 axis 从 27 lever 抽)

paradigm_death_timeline §2 已整理. 重列以方便 reference:

**Root cause 1 — Pose-bool master 表达力 limits**
- B1 pose-bool master 280K pose vars × 8 ports/pose = 2.36M OnlyEnforceIf
- master 不知 port direction / pole selection / belt routing
- 任何 master OPTIMAL 都让 sub-problem oracle 拒绝
- master 端 cut 学习不到 binding port_active / routing path / power coverage 关联
- **6 paradigm 撞同墙**: Path 12/13/14/17/B1-path1/B1-path2

**Root cause 2 — 96% utilization 几何死结**
- valley4_protocol_core 70×70 grid + 266 mandatory facility ≈ 4800 cells / 4900 total → 96% utilization
- boundary_storage_port × perimeter trap: 46 pose × 3 cells = 138 cells 必 100% 铺满 left+bottom 138 cells
- 任何 ghost 切 left/bottom 都触发 Hall infeasibility
- cand C 160/266 全 INFEASIBLE 是这一层的下界

**Root cause 3 — Cell-front pattern 已 break symmetry**
- per-instance 几何 high-resolution 已让 sub-pose 等价性消失
- LIC m1=2 (cell-front 近 deterministic pose, mean=1.74)
- Benders symmetry m5=1.0 (orbit 全 trivial)
- Cut lift / symmetry 无 free lunch
- **PROJECT_LOCK §3A 禁跨 instance lifting** 是这一层结论

**Root cause 4 — Single-machine RAM 不可扩**
- 48 GB RAM + 现 solver 下, augmented master / GOC-C2 / PGW-UB 等 RAM scale 全撞 25-32 GB peak (Pre2 cap 12 GB) / 单机 48 GB 上界
- L23 audit 已确认重写路径全穷尽
- 硬件方向被用户排除 (1 主机 + 1 远程 WAN 延迟 ≥ 100ms)

### 4.9 cut framework paradigm 为啥选

把 27 lever 4 root cause 翻译成"paradigm 必须满足"清单:

| Root cause | Paradigm 要求 |
|---|---|
| 1. pose-bool master 表达力 limits | 不重写 master; 在 master 外累积知识 |
| 2. 96% utilization 几何死结 | cut 必表达几何 INFEASIBLE (F1 capacity / F6 Hall) 跟物流 INFEASIBLE (F2 cutset / F4 reach) |
| 3. cell-front break symmetry | cut 限 within-instance scope, 不跨 instance lift |
| 4. RAM 不可扩 | cut 累积 + replay, 不重新 build master; sub-problem 独立 oracle 不挤 master scale |

**cut framework B Design v2 是这 4 个约束唯一满足的 paradigm** (除非 paradigm shift, 但 set-packing / IHS / LIC 系列已证 paradigm shift 全死). 这是项目数学上**不得不**走的路, 不是"试着搞搞看".

### 4.10 5 unsolved issue cut framework 要处理 (timeline §3)

cut framework 不解上面 4 root cause, 但**explicit 处理**衍生的 5 issue:

| Issue | 来源 | cut framework 应对 |
|---|---|---|
| 1. 96% utilization 几何死结 | Root cause 2 | F1 region_capacity + F6 shape_packing_hall |
| 2. Boundary × perimeter 容量 (138 cells 100% saturation) | v14 review GPT pro catch | F1 left_baseline / bottom_baseline / boundary union region |
| 3. Manufacturing cluster trap (132 个最大类) | Class C insight | F5 pattern_nogood + F3 port_exposure (但 Day 16c-2 评估**不足**, Day 18-21 需 dedicated solution) |
| 4. Routing 反馈翻译成强 cut | Class A insight | F2 cutset + F4 component_reach, **不**翻译成 pose-level no-good |
| 5. m10 sound 性跨 scale 维持 | cand C ramp insight | Validator 每 family 独立重算 cert (adversarial soundness, §2.6) |

Issue 3 (manufacturing cluster trap) 是当前 cut framework 最弱点 — F5 pattern_nogood 退化成 full no-good 风险, 132! permutation 撞墙. Phase 1.2 P1.11 实施 + Day 18-21 dedicated solution (orbit-aware pattern lift) 是 open Q (§5.3).

---

## 5. 待定 mathematical questions (open problems)

本节列**当前没答案**的数学问题. 按级别标:

- **P0 (critical)** — 数学层 paradigm 决定性问题, 不解 Phase 1.2/1.3/1.5 推不动
- **P1 (defer-Phase)** — 实施时 verify, 不阻 paradigm 但阻具体 family
- **P2 (informational)** — 知识层问题, 答了好但不阻
- **P3 (defer-future)** — Phase 2+ 才碰

各 Q 必标: 数学层 vs 工程层 / 难度估 / dependency / 触发决策的 trigger / 当前最佳 understanding.

### 5.1 框架 completeness — sound but how complete?

#### Q1 — 9 family 是否 cover 所有 INFEASIBLE 类? **P0**

**问题**: cut framework 9 family (F1-F9) 数学上是否**充分** — 即任何 master partial assignment 若 INFEASIBLE, 必存在 F1-F9 之一可产 sound cut 排除该 assignment?

**当前 understanding**:
- F1-F9 各自针对一类 INFEASIBLE pattern, 数学根据独立 ([cite spec 01-09])
- 跨 family 覆盖度由 timeline §3 5 issue 推 (但 timeline 只列 5 issue, 没数学完整性证明)
- Issue 3 (manufacturing cluster trap, 132 instance) 现 spec **不足** — F5 pattern_nogood literal 全 facility full assignment no-good 退化, 132! permutation 撞墙. paradigm_death_timeline §3 自承

**verification trigger**:
- Phase 1.5+ 真生产 168h trial 后, 若仍有 INFEASIBLE candidate 不被任 F1-F9 拦 → 暗示 cover 不完整
- 长跑 telemetry 看 cut_count_by_family 分布 (§20.2) — 若某类 INFEASIBLE 反复 trigger 但无 cut 拦, 数学上需 F10+

**数学难度**: paradigm-level, 不能简单 verify. 需:
- 形式化"所有 INFEASIBLE 类"的 partition (proof system 层)
- 对每类构造拦截 family 或证明 ⊥

**defer trigger**: Phase 2+ 决策 (当前 Phase 1.2/1.3 实施前不解, 用 Phase 1.5+ telemetry 数据反推)

**最坏情况**: 9 family 不充分 → 加 F10+ (LOCK §3A 9 family frozen 的约束需重审, paradigm shift 入口)

#### Q2 — cut framework convergence guarantee? **P1**

**问题**: 给定足够 oracle compute, cut framework 累积 cut 后, 是否 finite step 内 master 收敛 OPTIMAL/INFEASIBLE?

**当前 understanding**:
- LBBD 经典结论: nogood cut 数有限 (有限 master assignment 空间), 每次 INFEASIBLE 必排除 ≥1 assignment → finite step 内 done
- 但项目空间 8×10⁷ raw assignment + cut framework lift (within-instance) 让 cut 表达力 enlarge — 单 cut 排除多 assignment, finite step 估算更紧 但具体未证
- 实际 168h budget 内不需 finite proof, "168h 内收敛比 baseline 多 N candidate" 即工程胜利

**数学难度**: theoretical, 不阻实施

**defer trigger**: Phase 1.5+ telemetry 数据足够后做经验估算 (cut 累积速率 + master.solve wall 关系)

#### Q3 — sound cut 跟 over-prune 的边界 **P0**

**问题**: cut framework 验 sound (`validator(cert, state) = OK ⇒ cut excludes only ¬feasible`), 但 over-prune (验 sound 同时排除 feasible) 怎么定义?

**当前 understanding**:
- adversarial soundness §2.6 验 cert 内 sound + cert↔literals/真数据/state/不变量 5 层
- 但 over-prune 是另一回事 — cert 可能 sound (cut.body 排除的 assignment 在该 cert 下 ¬feasible), 但 cert 跟 cut.scope 关系若错 → cut 在更广 scope 误剪 feasible (L14 weighted occupancy / v3 anchor slicing 死法)
- Step O F1 GHOST_AGNOSTIC ghost ∩ R == ∅ 检查就是防 over-prune (cap_R 跨 ghost 不变要求)

**数学难度**: 需 formalize scope 的 "cut sound 范围" 跟 "cut 适用范围" 是同一回事

**verification trigger**:
- 任 family 设计时必声明: cut 对 scope 内任意 state 是否仍 sound?
- Phase 1.2 F5-F9 实施时同步落

**defer trigger**: 每 family 实施时 case-by-case verify (不集中决)

### 5.2 cut 复用边界 — lifting 数学根据

#### Q4 — within-instance lifting sound 性边界 **P1**

**问题**: PCR-CUT Phase 3 signature lifting 已实施 within-instance lift ([cite lifecycle §9 复用 from cand C Phase 2 v3]). 跟 multiset eval slot anonymity 关系是?

**当前 understanding**:
- multiset eval (§2.5): slot 集 modulo S_n action 等价类
- PCR-CUT signature lifting: 同 instance 内不同 pose 若几何 signature 等价, cut 可 lift
- 二者是同一回事 (S_n 自然 act on signature 等价类) 还是独立?

**数学难度**: cheap (~1 day cheap gate verify 形式化二者等价 / 区分)

**defer trigger**: PCR-CUT Phase 1.5+ 整合时定 — multi-anchor 部分实施 (Phase 5 verdict 死) 跟 within-instance lift 关系

#### Q5 — cross-instance lifting 数学边界 **P0 frozen**

**问题**: 跨 instance lifting (e.g. 两个 boundary_storage_port instance 共享 cut) 数学 sound 性?

**当前 understanding**:
- Path 18 LIC (layout-invariant cert) verdict 死, m1=2 远低 ≥100 target — cell-front pattern 已 break instance 等价
- Benders symmetry m5=1.0 orbit 全 trivial
- PROJECT_LOCK §3A 禁跨 instance lifting 是这一层结论

**verification trigger**: **已 frozen** (LOCK §3A 锁), 不解. 任 paradigm propose 跨 instance lift 必 reject

**数学难度**: ❌ 死路 baseline, 不再 propose

#### Q6 — 跨 candidate / 跨 ghost lifting sound 性 **P1**

**问题**: 当前 cut.scope 含 ghost_rect_id (跨 ghost 不 lift 除非 GHOST_AGNOSTIC); cut 跨 candidate 怎么处理?

**当前 understanding**:
- source_digest 锁 data version → 跨 session reuse cut (替代 candidate 跨 session)
- 单 session 内多 candidate, cut 跨 candidate sound 性是: cut.scope.ghost_rect_id 跟 candidate ghost 一致 → 可 reuse; 不一致 → quarantine 或 replay
- GHOST_AGNOSTIC cut (e.g. F1 在 `ghost ∩ R == ∅`) 跨 candidate ghost 可 reuse, 这是数学根据 (cert 不含 ghost 变量)

**数学难度**: 已 Step O 部分解 (F1 ghost ∩ R 检查), 其他 family GHOST_AGNOSTIC 政策 Phase 1.2 实施时 align

**defer trigger**: Phase 1.2 F5-F9 实施时 per-family 定 GHOST_AGNOSTIC 政策

### 5.3 各 family 具体 open questions

#### F1 — LP dual Farkas 自动触发? **P2**

**问题**: F1 region_capacity 是 LP relax valid inequality, 可通过 Farkas dual ray identify ([cite spec 01 §1c]). 实施 Farkas 自动触发是否值得?

**当前 understanding**:
- 项目复用 cand C `farkas_certificate.py` (代码已 land)
- 但当前 F1 oracle 是启发式枚举 region, 不调用 Farkas
- Farkas 自动触发 → oracle 不需手写 region 列表, 但 LP relax solve 也要 cost

**defer trigger**: Phase 1.3 propagator 集成时 verify Farkas 是否有 dual ray 跟 F1 oracle 重合

#### F1 — interior_rect 枚举策略 **P1**

**问题**: F1 oracle 4 类 region 含 `interior_rect` (任意轴向 rectangle). 70×70 grid 上 rectangle 数 6.4M, oracle 不能枚举全部. 启发式策略?

**当前 understanding**:
- 当前 oracle 实施 4 类 region 但 `interior_rect` 没明确启发式 (spec 没定)
- 可能策略: facility-centered rect / boundary-adjacent rect / Farkas-driven (Q1 same)

**defer trigger**: F1 production trial 时按 telemetry 看 region 类型分布定

#### F2 — patch_routing_core 复用 sound 性 **P1**

**问题**: F2 oracle 是否复用 PCR-CUT (Path 14) 的 patch belt CP-SAT? 单 cut 数学 sound 但 multi-anchor 复用 (Phase 5 verdict 死 0/8 CERTIFIED) 是否影响 F2?

**当前 understanding**:
- PCR-CUT 死法是**multi-anchor cut 累积不收敛** — pose-bool master 不知 sub-problem 关联 (Root cause 1)
- F2 用 LBBD 标准 nogood lift (not multi-anchor cut), 数学根据是 Menger min-cut
- 单 cut 生成可复用 PCR-CUT helper, 不直接复用 multi-anchor convergence 设计

**verification trigger**: Phase 1.5+ F2 oracle 实施时复 verify (PCR-CUT Phase 0-4 GO 单 cut 数学层 sound)

#### F2 — max-flow LP dual algebraic witness **P2**

**问题**: Menger min-cut max-flow theorem dual 提供 algebraic witness (LP solve 后取 dual ray). F2 oracle 是否实施 LP-based witness verify (cite spec 02)?

**当前 understanding**: cite spec 02 提到 max-flow LP, 但 src 实施未明确

**defer trigger**: Phase 1.5+ §13.4 evaluate

#### F3 — multi-pose port chain (3+ facility 互 block) **P2**

**问题**: F3 当前是 2-literal pattern (两 facility 互 block). 是否扩展到 3+ facility 互 block 链?

**当前 understanding**:
- 数学根据: propositional logic 不限 literal 数, 但 2-literal 比 3+ 紧
- F5 pattern_nogood 是 multi-literal generalization, F3 是 2-literal 特例
- 实施 F3 (Phase 1.1 闭环) 加 multi-pose 是 F3 内扩展还是直接走 F5? 待 F5 实施后决

**defer trigger**: Phase 1.2 P1.11 (F5) 实施后决 F3 是否扩展

#### F3 — 跟 F5 subsume 关系 **P1**

**问题**: F5 pattern_nogood (multi-literal) 实施后, F3 (2-literal port) 数学上是 F5 特例 — 是否合并 (减 family 数 → 8)?

**当前 understanding**:
- PROJECT_LOCK §3A 9 family frozen
- 但 family 合并不动 LOCK invariant, 是 spec 层简化
- 合并好处: 减 dispatch 复杂; 不合并好处: F3 端口语义清晰, validator 重算更紧

**defer trigger**: Phase 1.2 P1.11 (F5) 实施后, 看 F5 validator 是否真覆盖 F3 cert↔literals binding 严格性

#### F4 — cell-flow capacity (cell 同时被多 commodity 用)? **P1**

**问题**: F4 当前只 binary connectivity (src reach sink 是/否). 是否引入 cell-flow capacity (cell 同时被多 commodity 用, capacity 上界)?

**当前 understanding**:
- D2 Path 17 试过 (conditional flow conservation), verdict 死 (multi-anchor 0/8)
- F4 走 connectivity 路径不走 flow 路径
- 但有 INFEASIBLE 案例: 2 commodity 共享单 path cell, capacity 1 不够 — F4 当前不拦

**defer trigger**: Phase 1.5+ F4 production trial telemetry 看是否有此类 INFEASIBLE 未拦, 若有则需 F4 扩展或新 family

#### F5 — QuickXplain 超时阈值 **P0**

**问题**: F5 minimize 用 QuickXplain (Junker 2004) 找 minimal unsat core, NP-complete. 实际 instance 上时间预算?

**当前 understanding**:
- L16 deletion-based 已 land helper (paradigm 死但 minimize 算法可复用)
- PCR-CUT QuickXplain helper 已 land (Phase 0-4 GO)
- 项目 instance 上 unsat core 大小未知 (mini PoC 50% reduction, production scale 未测)
- Open question §17.6 (plan doc) cite, defer Phase 1.2 P1.11 实施时定

**verification trigger**: Phase 1.2 P1.11 实施时跑 prod data, p95 core size + minimize 时间分布, 定 super-timeout fallback (deletion-only / 不 minimize)

#### F5 — Manufacturing cluster trap (132 instance) 退化 **P0**

**问题**: timeline §3 issue 3 — F5 pattern_nogood literal 全 facility full assignment no-good 退化, 132! permutation 撞墙. Day 18-21 需 dedicated solution (orbit-aware pattern lift).

**当前 understanding**:
- F5 default behavior 是 literal pattern, 132 instance 同 facility group 互相 permute → 132! pattern 数
- 已被识别为**当前 cut framework 最弱点**
- 可能 solution: orbit-aware pattern lift (multiset eval §2.5 自然扩展); 或 F5 + F6/F3 复合 cut; 或 instance-level instance partition

**defer trigger**: Phase 1.2 P1.11 (F5 实施) 必同步实施 orbit-aware pattern lift, 否则 P1.11 incomplete

#### F6 — Hall theorem interval graph 反例边界 **P1**

**问题**: F6 用 Hall's marriage theorem on interval graph (boundary interval cover). 各 length-k 反例覆盖率?

**当前 understanding**:
- spec 06 给一个反例 (Gemini 反例 B, length-3, ghost 切 [1-4]+[6-10])
- 其他 length-k 反例: length=2 / 4 / 5 各类 ghost 切, 反例分布未列
- production 几何上常见的 length-k facility: 2x1 / 3x1 / 3x3 / 5x5 / 6x4

**defer trigger**: Phase 1.2 P1.12 (F6 实施) 时枚举 length-k × ghost-cut 组合, 给反例 fixture 集

#### F6 — 2D interval cover (interior facility) **P2**

**问题**: F6 当前只 boundary 1D interval. 2D interior facility group (e.g. 3x3 mfg) 是否需 Hall 2D version?

**当前 understanding**:
- F1 region_capacity 已 cover interior facility count
- F6 2D 是 F1 stronger refinement (类比 boundary F1 → F6)
- 但 2D Hall 复杂度高, NP-complete (matching in bipartite graph polynomial, 但 2D 几何嵌入有约束)

**defer trigger**: Phase 1.5+ F6 真生产 trial 看 boundary 1D 是否足够; 若 interior 仍 over-demand 走 F1 不走 F6 2D

#### F7 — LP relax ln(n) approximation 实际紧度 **P1**

**问题**: F7 set cover NP-hard, LP relax + greedy 有 ln(n) approximation (Chvátal 1979). 项目实际 instance 上 approximation factor 多少?

**当前 understanding**:
- F7 oracle 是 set cover **必要条件**检查 (power_cover_domain ∅) 不解 set cover
- 但 Phase 1.5+ refine (power_cover_domain 非空但 hitting set unsat) 需解 set cover, 走 LP relax 还是 exact?
- 项目 instance n ~ 数百 (power_pole 候选数), ln(n) ~ 5-6 倍 — exact 时间 vs LP 速度 tradeoff

**defer trigger**: Phase 1.2 P1.13 (F7 实施) 决 LP 还是 exact, 用 Phase 1.5+ telemetry 验

#### F7 — 跟 master.solve power_coverage constraint 冲突 **P1**

**问题**: F7 是 cut layer 检查 power cover; master.solve 已有 power_coverage constraint (`src/models/master_model.py`). 二者关系?

**当前 understanding**:
- master power_coverage 是 hard constraint, F7 是 cut layer 检查 (sound deduction)
- 数学上 F7 sound = master 在该 cut 后必 INFEASIBLE
- 但实施上: F7 cut 加进 master 后是 redundant (master 已经会拒) 还是 amplify (master propagation 提前 cut)?

**defer trigger**: Phase 1.3 P1.21 propagator 集成时验

#### F8 — Liang-Barsky 退化 case **P1**

**问题**: F8 用 Liang-Barsky line-segment AABB intersection. 退化 case (零长度 / 共线 / 正交) 数学边界?

**当前 understanding**:
- Liang-Barsky 标准实施处理一般 case, 退化 case (segment 长度 0, segment 跟 AABB edge 共线, segment 正交于 AABB) 需 careful
- spec 08 v1.1 Gemini round 14 finding 改严格 line-segment AABB intersection (不是 cell-level 离散 block)
- 实施时若退化 case 处理不对, F8 cut 可能 unsound 或 over-prune

**verification trigger**: Phase 1.2 P1.14 实施时加退化 fixture (零长度 + 共线 + 正交)

#### F8 — power network 跟 belt routing 独立性 **P2**

**问题**: F8 假定 power network (pole 连接) 跟 belt routing (commodity flow) 独立. 是否真独立?

**当前 understanding**:
- 数学上独立: pole 不占 belt cell (pole 几何小 vs belt 用 free cell)
- 但实际 instance 几何上 pole + belt 共占 free_cells → 互相 block 可能
- 若不独立, F8 cut 跟 F4 cut 有交叉, 数学上需复合 family

**defer trigger**: Phase 1.5+ telemetry 看 pole / belt 共占冲突频率

#### F9 — envelope baseline 紧度 **P0**

**问题**: F9 density_envelope 用 `cap/area` ratio 作 envelope. baseline=1.0 (trivial, 每 cell 至多 1 facility) 是否 trivial 永不可 cert? L14 weighted occupancy verdict 死的教训说明 trivial bound 不够.

**当前 understanding**:
- L14 死法: interior anchor LP=1.000 exact 永远不可 cert
- F9 必须用真重算的 envelope (不是 LP relax 1.000), 即 oracle 真计算 region 内 facility 数 + cell_owner 已占
- spec 09 v1.0 表态: envelope ≠ trivial baseline, 必 stronger bound

**verification trigger**: Phase 1.2 P1.15 实施时, fixture 必含 envelope < trivial 的反例 (否则 F9 退化 F1)

#### F9 — 跟 F1 数学独立性 **P1**

**问题**: F9 cap 严格 ≥ F1 cap? 即 F9 是 F1 弱化 (允许更弱 envelope) 还是 F1 强化 (envelope 更紧)?

**当前 understanding**:
- spec 09 表态: F9 是 F1 scope **扩展** (允许更弱 envelope bound), 不是 stronger cut
- 但若 F9 envelope < F1 cap (e.g. cell_owner 已占), F9 反而更紧
- 数学边界: F9.cap = F1.cap - cell_owner_in_R × cells_per_pose? 还是其他公式?

**defer trigger**: Phase 1.2 P1.15 spec 写时数学 formula 明确

### 5.4 LBBD 集成的 open questions

#### Q7 — attach point 选择 **P0**

**问题**: cut framework Phase 1.3 接 benders_loop 时, cut 在哪 attach master? 当前 PCR-CUT (Path 14) 只在 front_blocked routing precheck branch attach. 其他 INFEASIBLE 来源 (binding / flow / power) wire 进 cut framework 怎么 sound?

**当前 understanding**:
- LBBD 经典: 每 sub-problem INFEASIBLE 出 nogood → master 加 lazy
- cut framework 是 nogood 的累积层, 每 sub-problem 触发 attach 点不同 (binding INFEASIBLE 触发 F3/F5/F7; routing INFEASIBLE 触发 F2/F4; power INFEASIBLE 触发 F7/F8)
- 每 attach 点必 sound 确认 (cert ↔ sub-problem reject 数据)

**defer trigger**: Phase 1.3 P1.21 propagator 集成时设计 (cite plan §12.1)

#### Q8 — lazy attach vs eager attach **P1**

**问题**: cut 在 master 是 lazy constraint (master.AddLazyConstraint) 还是 eager constraint (master.AddLinear 立即)?

**当前 understanding**:
- CP-SAT 支持 AddLinear eager + AddBoolOr lazy 但 lazy 用法限制 (callback 方式)
- eager attach: cut 立即影响 propagation, master 立即缩 search; lazy attach: cut 仅在 master solve 时触发, 不影响 propagation
- 项目 cut 数预期 ~thousands per candidate, eager 可能撞 propagation cost; lazy 可能 cut 不触发 (master 没 hit cut.scope)

**defer trigger**: Phase 1.3 P1.21 实施时 ab test eager vs lazy

#### Q9 — master OPTIMAL vs INFEASIBLE 触发路径 **P1**

**问题**: 当前 cut 只在 master OPTIMAL + sub-problem reject 触发 (PCR-CUT Phase 4 hook). 其他路径 (master UNPROVEN time-out / master 直接 INFEASIBLE) 是否触发 cut?

**当前 understanding**:
- master OPTIMAL: sub-problem reject 是 classic LBBD nogood path
- master UNPROVEN time-out: 没 best 答案, 不能产 sound cut (因为没确认 INFEASIBLE)
- master INFEASIBLE: 已经 ⊥, cut 没必要 (但 cut framework 累积 cut 可减后续 master.solve 时间)

**defer trigger**: Phase 1.3 P1.21 实施时设计

#### Q10 — cp_sat propagator vs master.AddLinear **P0**

**问题**: cut 用 CP-SAT propagator (custom propagation) 还是 master.AddLinear (constraint 加入 model)?

**当前 understanding**:
- propagator: custom Python callback, 控制 propagation; 但 thread-safety 风险, ortools 不保证多 worker 安全
- AddLinear: 简单, 但 build time 增, 重 build cost 高
- 项目 168h campaign 多 worker, propagator thread-safety 是 critical

**defer trigger**: Phase 1.3 P1.21 §12.4 propagator thread-safe 评估

### 5.5 schema / data 层 open questions

#### Q11 — commodity registry 级别 (commodity_id vs route_id) **P0**

**问题**: F2 / F4 cert 含 commodity_id (Step M registry require). 但 commodity_id 是流粒度 (e.g. "ore_iron") 还是路径粒度 (e.g. "ore_iron_route_A")?

**当前 understanding**:
- 流粒度: 1 commodity 对应 1 demand pair, 路径 fungible
- 路径粒度: 同 commodity 多路径, 各路径独立 cert
- 流粒度 simpler 但路径粒度精细; F2/F4 cert ↔ data pipeline 接合点决于此

**defer trigger**: Phase 1.5+ §13.1 commodity registry 真接 data pipeline 时决

**数学影响**: 流粒度 cut sound 性证明简单; 路径粒度 cut sound 性需额外 verify (路径独立性)

#### Q12 — ghost_rect tuple vs object schema **P1**

**问题**: 当前 ghost_rect 是 tuple `(x, y, w, h)`. 改 object schema `{x, y, w, h, anchor_id, ...}` 是否更好?

**当前 understanding**:
- tuple: 简单, hashable, serializable
- object: extensible (加 anchor_id / rotation / metadata 不破 backward compat)
- 实际 cut.scope.ghost_rect_id 用 hash(tuple) → 改 object 后 hash 不变 (用 sorted keys)

**defer trigger**: Phase 1.2 §10.4 实施时决 (加非方形 fixture 触发)

#### Q13 — source_digest hash 算法 **P1**

**问题**: source_digest 真 hash 用什么算法? sha256 还是 blake3? 覆盖范围 (canonical_rules + 哪些 preprocessed file)?

**当前 understanding**:
- sha256 标准, blake3 快但 nonstandard
- 覆盖范围: 必含 canonical_rules.json (data SoT); preprocessed file 含 candidate_placements / mandatory_exact_instances / generic_io_requirements
- 不含: telemetry / cache / 临时文件

**defer trigger**: Phase 1.2 §10.3 实施时决 (sha256 默认, blake3 fallback)

### 5.6 paradigm-level open questions

#### Q14 — 整体框架 completeness 形式 proof **P3**

**问题**: 形式化 proof 9 family 数学上 sound + complete (cover 所有 INFEASIBLE 类)?

**当前 understanding**:
- Soundness: per-family validator 重算 cert 已是 sound 工程证明 (但非形式化 proof system)
- Completeness: §5.1 Q1 open
- 形式化 proof 需 Coq / Lean / Isabelle 工具 — 项目当前不投资

**defer trigger**: Phase 2+ 决策 (paradigm 投资 ≥ 数月)

#### Q15 — 跨 base transfer 可行性 **P3**

**问题**: valley4_protocol_core cut framework 能 transfer 到其他 base (`valley4_infra_outpost` / `wuling_protocol_core` 等)?

**当前 understanding**:
- 各 base 几何 (grid size / mandatory instance / canonical_rules) 不同
- cut framework 数学 paradigm (LBBD + 9 family) 应 transfer, 但 oracle 实施 (region 枚举策略 / interval cover / power network 拓扑) 跟 base 几何耦合
- PROJECT_LOCK active_scope `valley4_protocol_core` only, 其他 base future_scope

**defer trigger**: future_scope, Phase 2+

#### Q16 — 多 base 联合 optimization **P3**

**问题**: 多 base 同时 optimize (e.g. valley4_protocol_core + valley4_infra_outpost 共用 commodity flow) 数学定义?

**当前 understanding**:
- 当前 PROJECT_LOCK active_scope 单 base, 多 base 联合是 future_scope
- 数学上需扩展 objective (max_lex 跨 base?) + 跨 base commodity 流定义

**defer trigger**: future_scope, Phase 3+

### 5.7 工程层 (数学 adjacent) open questions

#### Q17 — cut redundancy 跟 propagation cost tradeoff **P1**

**问题**: 加越多 cut, master.solve propagation 越慢 (CP-SAT BCP cost). Sound vs cost 怎么 tradeoff?

**当前 understanding**:
- 数学上 cut 越多越好 (排除更多 ¬feasible space)
- 工程上 propagation cost ~ cut 数 × literal 数, 项目 thousands cut 可能 master.solve wall +20%
- Phase 1.3 telemetry §20.2 看 cut_redundancy_rate + step_7_latency 决

**defer trigger**: Phase 1.3 P1.21 实施 + 24h shadow trial 后定 cut 上限策略 (LRU evict / cut score threshold)

#### Q18 — cut quality metric 形式定义 **P2**

**问题**: 什么 metric 衡量"好 cut"? active_rate / pruning_contribution / 还是其他?

**当前 understanding**:
- §20.2 列了 4 类 metric (cardinality / quality / latency / safety)
- 但"好 cut"定义模糊 — sound 是必要不充分; "cut 排除多 assignment" 直接量化困难
- 可能 proxy: cut.active_after_replay rate / cut.attached_count / cut.contribution_to_master_INFEASIBLE

**defer trigger**: Phase 1.3 telemetry 落地后用真数据归纳

#### Q19 — registry schema 跟 cut framework decoupling **P1**

**问题**: commodity registry (Q11) 跟 BState schema 强耦合. 改 registry schema 是否 break cut framework?

**当前 understanding**:
- 当前 Step M Stafe.commodity_demands + commodity_routes registry 是 BState field
- 若 registry 改 schema (e.g. 加 priority / 加 fungibility flag), cut framework 是否需同步改?
- 数学上 cut 不依赖 registry detail (只用 commodity_id 标识), 但 validator 实施依赖 schema

**defer trigger**: Phase 1.5+ §13.1 真接 data pipeline 时决

### 5.8 Issue 3 manufacturing cluster trap 单独深入 (timeline §3 自承不足)

**timeline 自承**: Issue 3 (manufacturing_3x3 132 instance) 现 spec **不足** — F5 pattern_nogood literal 全 facility full assignment no-good 退化, 132! permutation 撞墙. v14 review Pattern no-good >50% stop-ship signal 矛盾. Day 18-21 需 dedicated solution.

**已 propose solution (P0)**:

#### A. Orbit-aware pattern lift (优先)
- multiset eval §2.5 自然扩展: 132 instance 的 S_132 permutation orbit 等价类
- 单 cut 排除整 orbit, 不是 132! single literal
- 数学根据: slot anonymity invariant 已在 §2.5 verify, 扩展到 132 instance 是 cheap (lifting within-instance)
- **难度**: 中等 — orbit 计算 cheap, 但 cut.scope.orbit_id 加新字段 (state_machine 扩展)

#### B. F5 + F6/F3 复合 cut
- F5 single literal + F6 Hall theorem refinement (interval cover) + F3 port_exposure 跨 instance
- 复合 cut 单 cut 排除更多, 但 cert 复杂度高
- **难度**: 高 — 跨 family 复合 cert 是新 paradigm, 需 spec-level 决

#### C. Instance-level instance partition
- 132 instance partition into K group (e.g. 10 group 各 13 instance), 各 group 独立 cut
- 减 permutation 撞墙到 13! × 10 group (~10⁹ vs 132!)
- **难度**: 低 — 不动 cut framework, 加 instance partition layer; 但 partition 启发式需设计

**当前推荐**: A (orbit-aware pattern lift) 是数学上 cleanest. 实施 trigger: Phase 1.2 P1.11 (F5 实施) 必同步 land A, 否则 P1.11 incomplete.

**verification**: Phase 1.5+ trial 看 132 instance manufacturing_3x3 group F5 cut 数量是否撞墙 (>10⁵ cut → 撞; <10³ cut → A 工作).

---

## 5.9 Open Q summary 表

跨 5.1-5.8 列, 实施 priority order:

| Q | 主题 | 级别 | defer Phase | 数学/工程 |
|---|---|---|---|---|
| Q1 | 9 family completeness | P0 | Phase 2+ telemetry 反推 | 数学 |
| Q2 | convergence guarantee | P1 | Phase 1.5+ 经验估 | 数学 |
| Q3 | sound vs over-prune 边界 | P0 | per-family case-by-case | 数学 |
| Q4 | within-instance lifting sound | P1 | PCR-CUT 整合时 | 数学 |
| Q5 | cross-instance lifting (frozen) | P0 死 | LOCK §3A | 数学 |
| Q6 | 跨 candidate/ghost lifting | P1 | Phase 1.2 per-family | 数学 |
| F1-LP | LP dual Farkas 自动触发 | P2 | Phase 1.3 | 工程 |
| F1-int | interior_rect 启发式 | P1 | Phase 1.5+ telemetry | 工程 |
| F2-PCR | patch core 复用 sound | P1 | Phase 1.5+ F2 oracle | 数学 |
| F2-LP | max-flow LP dual | P2 | Phase 1.5+ §13.4 | 工程 |
| F3-multi | multi-pose chain | P2 | F5 实施后决 | 数学 |
| F3-F5 | 跟 F5 subsume | P1 | F5 实施后决 | 工程 |
| F4-cap | cell-flow capacity | P1 | Phase 1.5+ trial | 数学 |
| F5-QX | QuickXplain 时间预算 | P0 | Phase 1.2 P1.11 | 工程 |
| F5-mfg | 132! permutation 撞墙 | **P0 critical** | **Phase 1.2 P1.11 必同步** | 数学 |
| F6-len | Hall length-k 反例覆盖 | P1 | Phase 1.2 P1.12 | 数学 |
| F6-2D | 2D Hall (interior) | P2 | Phase 1.5+ trial 看必要 | 数学 |
| F7-LP | LP relax ln(n) factor | P1 | Phase 1.2 P1.13 | 工程 |
| F7-master | 跟 master.power_coverage | P1 | Phase 1.3 propagator | 工程 |
| F8-deg | Liang-Barsky 退化 case | P1 | Phase 1.2 P1.14 | 数学 |
| F8-ind | power/belt 独立性 | P2 | Phase 1.5+ telemetry | 数学 |
| F9-base | envelope baseline 紧度 | P0 | Phase 1.2 P1.15 | 数学 |
| F9-F1 | 跟 F1 数学独立性 | P1 | Phase 1.2 P1.15 spec | 数学 |
| Q7 | attach point 选择 | P0 | Phase 1.3 P1.21 | 工程 |
| Q8 | lazy vs eager attach | P1 | Phase 1.3 P1.21 ab test | 工程 |
| Q9 | OPTIMAL vs INFEASIBLE 路径 | P1 | Phase 1.3 P1.21 | 工程 |
| Q10 | propagator vs AddLinear | P0 | Phase 1.3 §12.4 | 工程 |
| Q11 | commodity_id vs route_id | P0 | Phase 1.5+ §13.1 | 数学+工程 |
| Q12 | ghost_rect tuple vs object | P1 | Phase 1.2 §10.4 | 工程 |
| Q13 | source_digest hash 算法 | P1 | Phase 1.2 §10.3 | 工程 |
| Q14 | 形式 proof completeness | P3 | Phase 2+ | 数学 |
| Q15 | 跨 base transfer | P3 | future_scope | 数学+工程 |
| Q16 | 多 base 联合 opt | P3 | future_scope | 数学 |
| Q17 | cut redundancy tradeoff | P1 | Phase 1.3 telemetry | 工程 |
| Q18 | cut quality metric | P2 | Phase 1.3 telemetry | 工程 |
| Q19 | registry schema decoupling | P1 | Phase 1.5+ | 工程 |

**当前 P0 critical (不解阻 Phase 推进)**:
- Q1 (9 family completeness — 用 telemetry 反推)
- Q3 (sound vs over-prune 边界 — per-family verify)
- F5-mfg (132! permutation — Phase 1.2 P1.11 必同步 orbit-aware lift)
- F5-QX (QuickXplain budget — Phase 1.2 P1.11)
- F9-base (envelope baseline 紧度 — Phase 1.2 P1.15)
- Q7 (attach point — Phase 1.3 P1.21)
- Q10 (propagator vs AddLinear — Phase 1.3 §12.4)
- Q11 (commodity_id vs route_id — Phase 1.5+ §13.1)

8 个 P0, 主要集中 Phase 1.2 P1.11 (F5 实施) 跟 Phase 1.3 P1.21 (propagator 集成) 两个 milestone.

---

## 6. 数学层验证 workflow

项目数学层验证 4 层. 各层独立 verify, 全 pass 才算 sound. 详 plan §22 (audit strategy).

### 6.1 Gemini per-commit cross-check (schema layer)

**频率**: 每 commit (cut framework src 改动) 立刻调.

**主战场**: schema ↔ src ↔ data gap. 验:
- spec 写 X 但 src 实施 Y → flag
- src 用 field A 但 BState schema 没有 A → flag
- real data path 数据 contradict cert claim → flag

**强项**: 自然口吻写作 + 快速 schema check ([[gemini-better-at-natural-tone]])

**弱项**: 不会 push adversarial 反例构造. 需 audit armor 强制 ([[gemini-prompt-audit-mode]])

**Phase 1.2 政策加严**: 每 commit 立刻 cross-check, 不堆 ([[gemini-review-algorithm-math]] R34 加严). 纯 implementation (refactor / rename) 不算数学层, 不必跑.

**输出**: `docs/research/.../cross_check/gemini_round_NN_<topic>.md` archive

### 6.2 GPT pro batch audit (adversarial soundness)

**频率**: 大节点 boundary — Phase 1.1 闭环 ✓ / Phase 1.2 入门 close / Phase 1.2 5 family land / Phase 1.3 propagator land / Phase 1.5+ pre-168h.

**主战场**: adversarial soundness §2.6 5 verification 层. 主 catch (3+4+5):
- cert ↔ 真数据 (oracle 凭空造的 cert)
- cert ↔ state (oracle 错绑 state field)
- cert ↔ 不变量 (oracle 违反 LOCK §3A invariant)

**强项**: deep cross-file consistency + paradigm check

**弱项**: 慢, 不能 per-commit; 不引用历史 GPT verdict (新窗口零 memory, [[gpt-review-no-history]])

**审查 armor**: 三段式 prompt ([[gpt-review-prompt-armor]]):
- 真瓶颈讲清 (项目是 latency-bound 不是 bandwidth-bound, 等)
- 死路黑名单 / 可接受方向白名单 (27 lever 死路 + cut framework paradigm 白名单)
- 不可达必须形式化证明 (complexity reduction / proof system lower bound / resource inequality / cite literature, 不准 "I believe / intuition")

**包 strategy**: 全项目 7z + zip 壳 + ship 7za binary ([[review-pkg-7z-strategy]]). plan/roadmap 不放包内 ([[review-pkg-no-prompt-inside]]).

**输出**: `docs/research/.../external_review/gpt_pro_phase{N}_v{V}_audit_round{R}_{VERDICT}.md` archive

### 6.3 真数据 reproduce (cheap gate)

**频率**: 任何 paradigm propose 新方向, 实施前 ≤ 1h cheap gate. ([[paradigm-phase0-cheap-gate]])

**主战场**: paradigm 前提**是否真满足 instance**.

**典型死法 catch**:
- v8 anchor slicing (关注 build 没量 solve)
- v10 witness preflight (假定 blueprint 满 41 mandatory 但实际缺)
- L14 weighted occupancy (interior LP=1.000 永不可 cert)
- L15 set-packing prover (攻错层)

**实施**:
- 写 Phase 0 PoC (~几百 LOC)
- 跑 production data subset (10-50 instance)
- 量 metric (m1-m10 各 paradigm 不同, 但通常含 sound 性 + cut 强度 + RAM/wall)
- pass 才进 Phase 1 实施 (full LOC)

**输出**: `docs/research/<paradigm_name>_<date>/phase0_*.md` archive

### 6.4 形式化 proof 跟工程 verify 的边界

**当前项目政策**: 数学 sound 用工程 verify (validator 重算 cert), 不用形式化 proof system (Coq / Lean / Isabelle).

**为啥**:
- 形式化 proof 投资 ≥ 数月 / family (Coq 项目典型 size)
- 项目 9 family 形式化需 ≥ 数年 — 不在 Phase 1-2 scope
- 工程 verify (validator 重算 + adversarial audit + telemetry 反推) 在项目 budget 内 sound 度足够

**何时 reconsider**:
- 项目交付后维护期 (Phase 3+) 若 data schema 大改, 形式化 proof 防 regression
- paradigm 投入 (defer Phase 2+) 时 formal proof 给最强 evidence

**当前 Q14 P3 defer**.

### 6.5 跨层一致性

3 层 verify 各自独立, 但**结果必一致**:
- Gemini per-commit pass + GPT pro NOT GO → 必查 Gemini 漏 audit layer (通常是 adversarial soundness 层 Gemini miss)
- 真数据 reproduce fail + Gemini/GPT pass → 必查 audit prompt 是否提供真数据 path
- GPT pro 多 round verdict 不一致 ([[external-review-reproducibility]]) → finding 必 reproduce verify, 不照搬

---

## 7. 跟相关 spec / doc 的关系

本节列项目数学相关 doc + 各自职责, 防 doc 间 cross-ref 混乱.

### 7.1 spec 系列 (B Design v2 framework 定义)

| Doc | 职责 | 跟本文档关系 |
|---|---|---|
| `cut_lifecycle_v2.md` | cut 9 step lifecycle + scope-aware replay 算法 + cut object schema + multiset eval 群论形式化 | 本文档 §2.4-§2.7 cite |
| `state_machine_v2.md` | BState schema + state invariants + trail+backtrack 算法 + group state ↔ port-binding cut 接口 | 本文档 §2.5 multiset eval cite |
| `cut_family_specs/01-09_*.md` | 各 family 完整 spec (数学定义 / cut 形式 / cert schema / validator contract / soundness proof) | 本文档 §3 各 family 数学根据 cite, 不重复 |
| `schema_update_v3.md` | schema 演进 v1 → v2 → v3 changelog | 本文档不直接 cite, 是 spec 版本史 |
| `red_fixtures/F1-F5*.md` | known-infeasibility 反例 + cut object hardcode + evaluate 期望 | 本文档 §3 各 family fixture cite |

### 7.2 paradigm / 死路 系列

| Doc | 职责 | 跟本文档关系 |
|---|---|---|
| `paradigm_death_timeline.md` | 27 lever 死路 chronological + 死因 axis (Class A-F) + 共同 root cause + 5 unsolved issue | 本文档 §4 cite, 按数学根据 attempt reorganize |
| `PHASE_0_CLOSE.md` | Phase 0 闭环验收 (B Design v2 spec 完整性) | 本文档不直接 cite |
| `PHASE_1_PLAN.md` | Phase 1 实施 plan (P1.1-P1.21 各 task) | 本文档 §3 phase status cite |

### 7.3 plan / roadmap 系列

| Doc | 职责 | 跟本文档关系 |
|---|---|---|
| `PHASE_POST_1_1_REFACTOR_PLAN.md` | Phase 1.1 闭环后重构 plan (含 18 section: 战略/数学原理/paradigm 决策/历史/GO 标准/依赖图/风险/rollout) | 本文档 §5 open Q defer trigger cite, 实施 timeline 不重复 |
| 本文档 (`MATHEMATICAL_FOUNDATIONS.md`) | 数学层 SoT — 已确定 paradigm + open mathematical questions | plan doc 是实施 SoT, 本文档是数学 SoT |

### 7.4 PROJECT_LOCK + 项目顶层

| Doc | 职责 | 跟本文档关系 |
|---|---|---|
| `PROJECT_LOCK.md` §3A | 数学/工程 invariant lock (family mode XOR / 9 family frozen / cert+literals XOR / GHOST_AGNOSTIC / multiset eval / source_digest / adversarial soundness) | 本文档 §2.2/§2.4/§2.6 cite, §5.5 Q5 (cross-instance lifting frozen) cite |
| `CLAUDE.md` (project) | 项目 instructions + maintenance runbook + Active scope + Forbidden changes | 本文档不直接 cite |

### 7.5 audit / cross-check archive

| Path | 职责 | 跟本文档关系 |
|---|---|---|
| `cross_check/gemini_round_NN_*.md` | Gemini per-commit audit response (22+ round) | 本文档 §6.1 cite workflow, 具体 finding 不重复 |
| `external_review/gpt_pro_phase{N}_v{V}_audit_*.md` | GPT pro batch audit response (11 round 跨 v1-v6) | 本文档 §6.2 cite workflow, 具体 finding 不重复 |

### 7.6 src / 工程实施

| Path | 职责 | 跟本文档关系 |
|---|---|---|
| `src/cuts/lifecycle.py` | 9 step lifecycle 实施 | 本文档 §2.7 数学职责 cite, 不抄 src |
| `src/cuts/families/{region_capacity,cutset,port_exposure,component_reach}.py` | F1-F4 validator + evaluator + oracle 实施 | 本文档 §3 各 family Phase 1.1 status cite |
| `src/cuts/store.py` | CutStore 6-dim watcher + held/active/quarantined state machine | 本文档 §2.4 replay cite |
| `src/cuts/replay.py` | scope-aware replay (Step M fail-closed) | 本文档 §2.4 replay 算法 cite |
| `src/tests/cuts/test_*.py` | 172 cuts test (unit / family / integration / adversarial 4 层) | 本文档 §6 验证 workflow cite, plan §21 测试 strategy 详 |

### 7.7 memory entries (Claude 持久知识)

| Memory | 跟本文档关系 |
|---|---|
| [[adversarial-soundness-audit]] | §2.6 数学根据 cite |
| [[paradigm-death-timeline-27-lever]] | §4 cite (consolidated) |
| [[gemini-review-algorithm-math]] | §6.1 workflow cite |
| [[big-milestone-gpt-pro-review]] | §6.2 workflow cite |
| [[gpt-review-prompt-armor]] | §6.2 prompt armor cite |
| [[paradigm-phase0-cheap-gate]] | §6.3 cheap gate cite |
| [[review-pkg-7z-strategy]] | §6.2 包 strategy cite |
| [[review-pkg-no-prompt-inside]] | §6.2 包内容政策 cite |
| [[workload-latency-bound-not-bandwidth]] | §2.1 paradigm 选择 cite |
| [[plan-doc-strategic-layers]] | §0 文档原则 cite |
| [[gpt-error-types-taxonomy]] | §4.6 v8/v10/L14 error type cite |
| [[subproblem-vs-augmented-master-default]] | §5.4 attach point cite |

### 7.8 文档 SoT 政策

各 doc 各管一摊, 不重复:

- **数学 paradigm + 数学根据 + open Q** → 本文档 (`MATHEMATICAL_FOUNDATIONS.md`)
- **实施 timeline + commit-level TODO + rollout policy** → `PHASE_POST_1_1_REFACTOR_PLAN.md`
- **family schema + cert 字段 + validator contract** → `cut_family_specs/0X.md`
- **lifecycle 9 step + scope replay 算法** → `cut_lifecycle_v2.md`
- **BState schema + state invariant** → `state_machine_v2.md`
- **27 lever 死路 chronological + axis 分类** → `paradigm_death_timeline.md`
- **invariant lock** → `PROJECT_LOCK.md` §3A
- **审查 archive (Gemini per-commit + GPT pro batch)** → `cross_check/` + `external_review/`

跨 doc cross-ref 用 `[cite spec X §N]` / `[cite lifecycle §N]` 等约定 (§0.4).

---

## 8. 文档维护

### 8.1 更新 trigger

本文档不是 frozen — 项目数学层有新 finding 时必同步:

- 新 family propose (F10+) → §3 加 family + §5.1 Q1 reevaluate
- 已 open Q 决策 → 从 §5 移出, 进 §3 (确定 paradigm) 或 §4 (死路)
- 新 paradigm 死路 → §4 加 lever + §5.6 reevaluate completeness
- spec / src / data schema 大改 → §2 + §7 同步
- PROJECT_LOCK §3A 改 → §2 + §5 frozen Q 重审

### 8.2 review 政策

本文档每大节点 (Phase 1.2 / 1.3 / 1.5+ boundary) audit:
- Gemini per-commit 改本文档时跑 (cross_check)
- GPT pro batch 整 phase 完时 review (external_review)
- 实施 implementer 进 Phase 时必读最新版

### 8.3 changelog

| Date | 版本 | 改动 |
|---|---|---|
| 2026-05-23 | v1.0 | 初版, 含 §1-§7 全, 跟 plan doc 高中 gap 补完同步落地 |

---

## 9. 引用 / refs

### 项目 doc
- `docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md`
- `docs/research/p3_b_design_v2_20260521/state_machine_v2.md`
- `docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md` ~ `09_density_envelope.md`
- `docs/research/p3_b_design_v2_20260521/paradigm_death_timeline.md`
- `docs/research/p3_b_design_v2_20260521/PHASE_POST_1_1_REFACTOR_PLAN.md`
- `docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md`
- `docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md`
- `docs/research/p3_b_design_v2_20260521/red_fixtures/README.md` + `F1-F5*.md`
- `PROJECT_LOCK.md` §3A
- `CLAUDE.md` (project + global)

### 学术 reference (paradigm 数学根据)
- Hooker, J. N. (2003). *Logic-based Benders decomposition*. Mathematical Programming 96(1).
- Bertsimas, D., & Tsitsiklis, J. N. (1997). *Introduction to Linear Optimization*. Athena Scientific. Ch.11 (LP duality).
- Menger, K. (1927). *Zur allgemeinen Kurventheorie*. Fundamenta Mathematicae 10. (min-cut max-flow theorem)
- Ford, L. R., & Fulkerson, D. R. (1956). *Maximal flow through a network*. Canadian Journal of Mathematics 8.
- Hall, P. (1935). *On representatives of subsets*. Journal of the London Mathematical Society 10. (marriage theorem)
- Garey, M. R., & Johnson, D. S. (1979). *Computers and Intractability: A Guide to the Theory of NP-Completeness*. (set cover NP-complete)
- Chvátal, V. (1979). *A greedy heuristic for the set-covering problem*. Mathematics of Operations Research 4. (ln n approximation)
- Liang, Y. D., & Barsky, B. A. (1984). *A new concept and method for line clipping*. ACM Transactions on Graphics 3. (AABB intersection)
- Liffiton, M. H., & Sakallah, K. A. (2008). *Algorithms for computing minimal unsatisfiable subsets of constraints*. Journal of Automated Reasoning 40. (MUS computation)
- Junker, U. (2004). *QuickXplain: Preferred explanations and relaxations for over-constrained problems*. AAAI. (QuickXplain divide-and-conquer)

### 工具 / 实现
- Google OR-Tools CP-SAT — `ortools.sat.python.cp_model`
- CPMpy 0.10.0 — MUS extraction PoC (P2 #18, [[cachyos-paste-and-nm]] 不相关)

---

*Last updated*: 2026-05-23 (initial version, synced with plan doc 高中 gap fill)
