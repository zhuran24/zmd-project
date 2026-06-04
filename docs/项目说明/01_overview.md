# 01 — 项目概览 (战略 + 数学问题陈述 + paradigm 选择)

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


## 1. 战略 / 上下文 — 为什么需要 cut framework

终末地 (Arknights: Endfield) IndustrialPlanner 70×70 grid certified exact
solver. 目标 max_lex(area, min_side), 266 mandatory facility instance, OR-Tools
CP-SAT, Benders decomposition (master → binding → routing → flow). 跑 168h
campaign 求 production-ready blueprint.

### 真瓶颈不在硬件, 在 master.solve

跑了 Phase 3A → 3B 才看清: i9-13900KS + 47 GB RAM + 168h wall-clock 也压不
住 master.solve. 不是 CPU 慢, 不是内存不够, 不是磁盘 IO. CP-SAT BCP two-watched
literal 在 280K pose registry 上做随机指针追逐, working set 跨 L3 spill, 这是
**latency-bound** 工作负载 (`[[workload-latency-bound-not-bandwidth]]`). 换
HiGHS 实测 42 GB > 30 GB (Phase 3B repair5), 换 LP relax B1 pose-bool master
也死 — master.solve 解不动是 paradigm 层 inherent.

### 27 个 paradigm 死路告诉我们 master 自身不能 fix

`docs/research/p3_b_design_v2_20260521/paradigm_death_timeline.md`（27 lever；live 权威在 CC memory `paradigm-death-timeline-27-lever`）记录全部死法:
- B1 pose-bool master (L11)
- PCR-CUT patch routing (Phase 5 multi-anchor verdict NOT GO)
- SAC-Hull separator capacity (necessary ≠ sufficient)
- D2 commodity flow (Phase 2 verdict)
- cand C column generation (5/20/40/80 ramp GO 但单 paradigm)
- L01-L26 各 lever (cdcl warmstart / IHS / Benders symmetry / 各种 augmented master)

死法共同模式: 试图改 master 内部 — 改 schema, 改 var encoding, 改 constraint
表达. 都死. 因为 master.solve 解不动是 BCP+pose registry 这层 inherent, 不
是表达问题.

### cut framework 是另一个思路: master 外累积 sound 知识

不动 master schema, 不动 mandatory_exact_instances. 在 master 跑过程中:

1. 某状态 INFEASIBLE 时, oracle (subproblem solver) 产 cut: 证明这个状态
   组合不可行
2. cut 经 9-step lifecycle (generate → minimize → serialize → validate →
   attach-scope check → evaluate → apply-to-master) 进 master 当 lazy constraint
3. master 下次遇到同类组合直接跳过, search tree 不爆炸
4. cut 跨 candidate 复用 (GHOST_AGNOSTIC sentinel + scope versioning)

cut 是 **外部 sound 证据**, master 不知道它存在前就能跑; master 知道后剪
search tree. 168h campaign 期望: cut 累积让 master 收敛, 不依赖硬件升级.

### 跟 IndustrialPlanner 主流程的关系

cut framework 不替代 master, 是 master 之外的 prune 层. Phase 3B repair5 是
master oracle 改 30 GB → 47 GB (fits), cut framework 是接 repair5 之后的累积
sound 知识层. 真 168h campaign 拓扑:

```
main.py campaign
  └─ outer_search (Phase 3A delivery, 不动)
       └─ benders_loop (Phase 3B repair5 master)
              ├─ binding subproblem
              ├─ routing subproblem
              ├─ flow diagnostic
              └─ [Phase 1.3 P1.3B land] cut store accumulate
                  ├─ F1-F9 oracle on INFEASIBLE
                  ├─ cut lifecycle 9 step
                  └─ master 加 lazy constraint
```

cut framework 在 benders_loop 内 (Phase 1.3 真集成 = P1.3B 待接), **当前 Phase 1.2 spike close 闭关中**（Phase 1.1 已完成）; cut framework 仍跑独立
unit test (4900 cell grid + mock state), 真 master wire 属 P1.3B.

### 期望收益

不是把 168h campaign 缩到 24h. 是让 168h 内真收敛 (vs Phase 3B repair5 之前
168h 也跑不完). 具体不预测数字, 因为 master.solve 收敛跟 instance pattern
强相关; 但 27 lever 死路告诉我们没 cut framework 就只能撞硬件墙.

---

