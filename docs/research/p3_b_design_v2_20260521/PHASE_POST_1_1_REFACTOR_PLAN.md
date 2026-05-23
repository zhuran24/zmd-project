# Phase 1.1 闭环后重构计划

到 commit `c8fb7ef` (Step O) 为止 Phase 1.1 4 family (F1-F4) validator / oracle /
evaluator / lifecycle / replay / store 全部 sound 闭环, 通过 11 轮 GPT pro audit
+ 22 轮 Gemini cross-check + 15 步 Step A-O 修复. 这份文件不只列后面要做哪几
步, 也讲清楚: 为什么走到这里, 为什么选 cut framework 不选 B1/PCR-CUT 这类
27 lever 死路, 各段的 GO 标准是什么, 各 family/step 之间怎么依赖, 风险怎么
兜底. 让看到这份文件的人, 不只知道 "做什么", 还知道 "为什么这么做" + "做到
什么程度算 done" + "走偏怎么回头".

---

## 0. 受众 / 怎么读这份 plan

这份文件 1400+ line, 不要求一口气读完. 不同身份 focus 不同段. 数学原理 + 死路 paradigm 详另在 `MATHEMATICAL_FOUNDATIONS.md` (1580 line, plan §3 + §4 是 overview cite 它).

**implementer (下个 session 接手的 Claude / 人)**
- 入口: §6 现状细则 → §10 Phase 1.2 入门 7 项 → §11 P1.11-P1.15 5 family
- 实施前必读: §2 invariants + §3 数学原理 (那 family 那段) + §18 PROJECT_LOCK §3A
- 每段做完前 verify: §8 GO 标准 + §21 测试 strategy + §22 审查 trigger
- 出错回头: §14 风险 mitigation + §14.3 rollout policy

**reviewer (GPT pro batch audit / Gemini per-commit cross-check)**
- 主战场: §2.4 adversarial soundness + §3 各 family 数学原理
- context: §4 paradigm 决策 + §5 历史回顾 (为啥不选 27 lever 死路 / 为啥 cut framework)
- 我们对你的 audit 怎么定义 GO/NOT GO: §8 GO 标准 + §22.3 audit verdict criteria
- 不必读: §10/§11 commit-level 实施细则 (那是 implementer 的事)

**未来 maintainer (Phase 1.2/1.3/1.5 接手, 数周-数月后)**
- context 恢复: §1 战略 + §4 paradigm + §5 历史
- 改某 family 牵动哪些: §9 依赖图 + §19 环境变量 (各 family 是否独立 toggle)
- 边界: §18 PROJECT_LOCK §3A (不能跨)
- 术语 anchor: Appendix A Glossary

**用户 (审 progress, 不实施)**
- 现在到哪了: §6 现状细则 + §20 telemetry (Phase 1.3 接进后看 metric)
- 各 phase 还多久: §16 排期估算
- 待定决策点: §17 Open questions
- 出错怎么 revert: §14.3 rollout / migration policy

不同 audience 通用 skip 段: 数学 deep dive (§3.1-§3.13) 仅 reviewer + 实施那 family 时读; commit-level 细则 (§10/§11) 仅 implementer 读.

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

### 24+ 个 paradigm 死路告诉我们 master 自身不能 fix

`paradigm_death_timeline_27_lever.md` 记录全部死法:
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
              └─ [Phase 1.3 P1.21 land] cut store accumulate
                  ├─ F1-F9 oracle on INFEASIBLE
                  ├─ cut lifecycle 9 step
                  └─ master 加 lazy constraint
```

cut framework 在 benders_loop 内 (Phase 1.3 真集成), 当前 Phase 1.1 跑独立
unit test (4900 cell grid + mock state), 不跟 master 真 wire.

### 期望收益

不是把 168h campaign 缩到 24h. 是让 168h 内真收敛 (vs Phase 3B repair5 之前
168h 也跑不完). 具体不预测数字, 因为 master.solve 收敛跟 instance pattern
强相关; 但 27 lever 死路告诉我们没 cut framework 就只能撞硬件墙.

---

## 2. 设计哲学 + 核心 invariants

cut framework 的数学基础 + 工程边界. 这些是 PROJECT_LOCK §3A 锁定的, 不是
review 时谁不爽改一改就行.

### 2.1 9 family 怎么定的 + 各 family 解决什么 INFEASIBLE 类

INFEASIBLE 不是单一现象. cut framework 拆成 9 类, 每类对应一个 cert schema +
validator + evaluator + oracle:

| Family | Mode | INFEASIBLE 类型 | spec |
|---|---|---|---|
| F1 region_capacity | geometric | 某 region R 内 cells per pose × demand > 可用 cap | spec §1-§9 |
| F2 cutset | geometric | partition (A, B) 上跨 partition demand > min-cut size (Menger) | 02_cutset.md |
| F3 port_exposure | literal | facility A 的 port 被 facility B 占, A+B 同选不可行 | 03_port_exposure.md |
| F4 component_reach | geometric | src/sink commodity 在 free_cells 图上 disconnected | 04_component_reach.md |
| F5 pattern_nogood | literal | 已知 INFEASIBLE 组合的最小化 (deletion / QuickXplain) | 05_pattern_nogood.md |
| F6 shape_packing_hall | geometric | Hall's marriage theorem 推 region 内 pose 数下界 | 06_shape_packing_hall.md |
| F7 power_hitting_set | literal | 电源 hitting set 不可满足 (sub-NP-hard) | 07_power_hitting_set.md |
| F8 power_grid_reach | geometric | Liang-Barsky AABB 推电网不可达 | 08_power_grid_reach.md |
| F9 density_envelope | geometric | region density 上界违反 (单位 cell pose count) | 09_density_envelope.md |

geometric vs literal 是核心 axis. geometric cut cert 含 region/partition/BFS
component 等几何对象 (用 bitset 编码), validator 重算几何 check. literal cut
cert 含 (group, pose) 对的 multiset, validator 验 multiset match. 两种 mode
互斥, family ↔ mode 锁定 (PROJECT_LOCK §3A invariant 3, `lifecycle.py:_FAMILY_MODE_MAP`).

9 个是 Phase 0 final 锁定的 (Gemini r26 GO). 不再加 / 不再删 / 不再改 mode.
Phase 1.2 实施 F5-F9, 不改这 9 个 list.

### 2.2 为什么 lifecycle 是 9 step

不是 7 step 也不是 11 step. 9 step 是不同 trust boundary 的最小拆分:

```
0. canonicalize     raw dict → canonical bytes (cert hash 确定性)
1. generate         oracle 产 cert + scope
2. minimize         literal-based deletion / QuickXplain (Step 2 defer Phase 1.1 P1.11)
3. serialize        Cut → JSON bytes
4. deserialize      JSON bytes → Cut (schema invariant 重检)
5. validate         独立重算 cert (oracle 不可信, validator 是 trust boundary)
6. attach-scope     6-step scope verify (source_digest / ghost / blocked / artifact / oracle / assumption)
7. evaluate         family-dispatch 验当前 state 是否仍 violate
8. apply-to-master  push 进 CP-SAT (Phase 1.3 P1.21 实施)
9. regression       re-validate on new replay state (Step 5 re-entry)
```

为啥 step 5 跟 step 7 必拆: step 5 是 oracle-time 重算 (cert 本身 sound), step
7 是 evaluator 重算 (当前 state 仍 violate). 这两个 trust boundary 不同 —
step 5 不通过 → cert 本身错 (quarantine), step 7 不通过 → cert 过期 (退场,
不 quarantine). 合并就丢这个区分.

为啥 step 6 必拆: source_digest / ghost / blocked / artifact / oracle /
assumption 6 个 sub-check 各有 fail-closed 语义. 任一漏验 = lifecycle 失控
(GPT v6 P0 反例正是 on_ghost_rect_changed 把 step 6 当全部验证, 漏了 step 7).

### 2.3 核心 invariants (PROJECT_LOCK §3A)

不能跨这些边界:

1. **family ↔ mode XOR** — literal-based vs geometric-based 互斥, 改一行 family 表也得跨
   spec/src/test 同步
2. **cut.scope + cert + literals XOR geometric_payload 必填** — __post_init__ 强制
3. **GHOST_AGNOSTIC sentinel** — 不能跟普通 ghost_id 混用, validator 必验
   scope.ghost_rect_id 是否真合法 (Step O P0 修)
4. **9 family list frozen** — 无 symmetry_lift (Phase 0 final), 含 F1-F9
5. **ASSUMPTION_VERIFIERS dispatch** — 必经 verifiers module, 不准 inline
6. **multiset eval 不看 slot index** — state_machine §5 anonymity, slot 是
   group 内 anonymous reorderable; 但 validator 内部 binding 阶段 slot
   必 resolve 到具体 pose (GPT v2 P0-2 修)
7. **source_digest 锁 data version** — 当前 placeholder `"poc_source_digest"`,
   Phase 1.2 切真 hash; 锁定后 cross-session cert 才可信

### 2.4 adversarial soundness 假设

`[[adversarial-soundness-audit]]` memory 总结: validator audit 分两层. Layer 1
spec ↔ src ↔ data 接合 (Gemini r27-32 覆盖). Layer 2 adversarial — 假 cert
能 pass 吗 (GPT pro r1-r6 覆盖).

cut framework 默认 oracle **不可信** (oracle 可以是 stub / 外部 import / disk
load / 旧 schema). validator 是 trust boundary, 必须能 reject 任何不 sound 的
cert. 这导致 validator 比 oracle 重 (radon D 级), 这是 by design — Step J/L/
M/N/O 5 轮 audit 反复加 validator binding 都是 adversarial soundness 拉紧.

---

## 3. 核心数学原理 (overview, 详 MATHEMATICAL_FOUNDATIONS.md)

**SoT 政策**: 数学原理 SoT = `MATHEMATICAL_FOUNDATIONS.md` (1580 line, 含 9 family 数学根据详 / sound deduction 形式系统 / scope replay 群论 / adversarial soundness 5 验). plan doc 本段只给 implementer reading-flow overview, **不重复数学根据详**.

### 3.1 整体 paradigm (cite math §2)

cut framework = LBBD nogood 的累积 sound 知识层. master 不动, sub-problem INFEASIBLE 出 nogood → cut framework 抽象成 family-specific cert + scope + literals/geometric_payload → 跨 candidate / 跨 ghost 累积复用. 数学根据是 sound deduction system (validator 必独立重算 cert, oracle Byzantine 假设).

详: math §2.1 paradigm 选择 + §2.2 sound deduction 形式系统.

### 3.2 9 family 数学根据 (cite math §3)

9 family frozen [cite lock §3A], 各 family 一类 INFEASIBLE pattern, 数学根据独立:

| Family | Name | 数学根据 | Mode | math §详 |
|---|---|---|---|---|
| F1 | region_capacity | pigeonhole + set covering | geometric | §3.1 |
| F2 | cutset | Menger min-cut max-flow theorem | geometric | §3.2 |
| F3 | port_exposure | propositional logic + slot anonymity | literal | §3.3 |
| F4 | component_reach | 4-conn graph BFS connectivity | geometric | §3.4 |
| F5 | pattern_nogood | minimal unsat core + QuickXplain | literal | §3.5 |
| F6 | shape_packing_hall | Hall's marriage theorem | geometric | §3.6 |
| F7 | power_hitting_set | set cover NP-hard + LP relaxation | literal | §3.7 |
| F8 | power_grid_reach | Liang-Barsky AABB intersection | geometric | §3.8 |
| F9 | density_envelope | geometric upper bound | geometric | §3.9 |

跨 family 关系 (subsume / refinement / 独立) 详 math §3.10.

### 3.3 关键 invariants (cite math §2.4-§2.6)

- **Scope versioning + replay**: GHOST_AGNOSTIC sentinel + source_digest content addressing; replay fail-closed (canonical_rules=None → HOLD). 详 math §2.4.
- **Multiset eval slot anonymity**: S_n 群作用 on slot 集; cut.body literal slot_id 是 placeholder 不 carry semantic. 详 math §2.5.
- **Adversarial soundness 5 层**: cert 内 sound + cert↔literals + cert↔真数据 + cert↔state + cert↔不变量. validator 是 trust boundary, oracle Byzantine. 详 math §2.6.

### 3.4 9-step lifecycle 数学职责 (cite math §2.7)

canonicalize → generate → minimize → serialize → deserialize → validate → attach-scope check + evaluate → apply-to-master → replay. 当前 Phase 1.1 实施 1+3-7+9, step 2 minimize defer Phase 1.2 P1.11 (F5 QuickXplain), step 8 apply-to-master defer Phase 1.3 P1.21. 详 math §2.7 各 step 数学职责.





## 4. paradigm 决策 (overview, 详 MATHEMATICAL_FOUNDATIONS.md §4 + paradigm_death_timeline.md)

**SoT 政策**: 死路 paradigm baseline 详 `MATHEMATICAL_FOUNDATIONS.md` §4 (按数学根据 attempt 分类) + `paradigm_death_timeline.md` (按时间 + 死因 axis 分类). plan doc 本段只给 implementer "为啥选 cut framework" 决定性 summary + 实施层衔接.

### 4.1 paradigm 选择 summary

27 lever 死路实测穷尽 7 类 attempt, 全死 (math §4.1-§4.7 + paradigm_death_timeline §1):

| Attempt | 代表 lever | 数学根据失败 |
|---|---|---|
| 完整 master 重写 | B1 pose-bool / augmented master / GOC-C2 / PGW-UB / HiGHS | pose-bool master 表达力 fundamental 限制 (Root cause 1) |
| Sub-problem cut | PCR-CUT / SAC-Hull / RAB-SEP / D2 / B1 lazy demand / L16 lazy power | over-restrictive 或不收敛, multi-anchor 0/8 (Root cause 1+2) |
| Cert lifting | Path 18 LIC / Lever 26 Benders symmetry | cell-front pattern 已 break symmetry (Root cause 3) |
| Column generation | cand C Phase 0+1 GO, Phase 2 160/266 INFEASIBLE | 96% utilization 几何死结 (Root cause 2) |
| Set-packing / IHS | L15 / Lever 25 IHS | 攻错层 / IHS core 全 trivial |
| Witness / weighted | v8 / v10 / L14 / D step 2 blueprint | 前提错估 或 数学能力上限 |
| Solver 替换 | HiGHS / Gurobi propose | single-machine RAM 不可扩 (Root cause 4) |

详死法 + cheap gate metric 各 lever cite math §4.1-§4.7. paradigm_death_timeline §2 列 4 共同 root cause.

### 4.2 cut framework 是 4 root cause 唯一满足的 paradigm

4 个约束 (从 4 root cause 翻译):
- 不重写 master (Root cause 1)
- 表达几何 + 物流 INFEASIBLE 各类 (Root cause 2)
- 限 within-instance scope, 不跨 instance lift (Root cause 3)
- cut 累积 + replay, 不挤 master scale (Root cause 4)

详 math §4.9.

### 4.3 跟 Phase 3B 衔接

Phase 3B repair5 (commit 7eb6e7f) master oracle 30 GB → 47 GB 是 cut framework 跑前提 — master 跑不起来 cut 没意义.

Phase 1.3 P1.21 真集成时 cut framework wire 到 benders_loop 内 (`src/search/benders_loop.py`), env flag (§19) 切新框架. 不动 Phase 3A outer_search 跟 Phase 3B master/binding/routing/flow 架构.

---

## 5. 历史回顾 — 怎么走到 Step O

不是天降一份 4 family validator. 是 22+ commit + 11 GPT pro audit + 22
Gemini round 一轮轮调过来的. 看完这段知道为啥某些 invariant 这样设计, 为啥
某些 fix 反复在同一函数加.

### 5.1 Phase 0 (B Design v2 spec + invariants)

22 commit + 26 round Gemini cross-check. 锁定:
- 9 family final list (无 symmetry_lift — round 18 decide)
- cut_lifecycle_v2 v3.2.2 (round 21 exterior_blocks_hash 加)
- 5 fixture frozen (red_fixtures/)
- 8 invariant frozen (PROJECT_LOCK §3A)
- 10 exit criterion (PHASE_1_PLAN.md)

Gemini r26 GO, 不再 Phase 0 layer cross-check. Step 跨 Phase 0 → 1.0.

### 5.2 Phase 1.0 (framework migration)

P1.1 carry PoC b_core_lifecycle_poc.py 14/14 PASS 到 production
`src/cuts/lifecycle.py`. 9 step + Cut/CutScope/BState schema + 6-dim watcher
+ replay store. F1 region_capacity 作 framework reference (其他 F2-F9 stub).

### 5.3 Phase 1.1 P1.5-P1.8 (F1-F4 production validator + oracle)

每 family 实施: validator + evaluator + oracle (F2-F4 oracle stub). F1 P(g)⊆R
strict / F2 partition / F3 cert↔literal / F4 BFS component 各自 spec land
(cut_family_specs/01-04.md).

Gemini r27-29 三轮 cross-check, r29 GO. 但 GO 后立刻 r30 catch 5 critical
gap — 全因 prompt mode 只验 spec↔src 没 push spec↔data (`[[gemini-prompt-audit-mode]]`).

### 5.4 Phase 1.1 Gap fixing (r30-r32)

Gemini audit mode 改 prompt: 真数据 inline + armor + 反 GO 章. r30-r32 三轮
catch 15 gap:
- Gap 6 union region (left ∪ bottom)
- Gap 7-8 cells_per_pose / placement_rule helper lookup
- Gap 9 direction N/S/E/W 真数据 vs spec up/down 漂移
- Gap 10 PoseId = str 替 int
- Gap 11 direction offset N=(0,-1) vs (-1,0)
- Gap 12 GroupState.selected_poses 类型 List[PoseId] 跟 spec align
- Gap 13 cut_family_specs/01 fixture drift
- Gap 14 find_pose O(N) → O(1) cache
- (5 个 high-risk follow-up 进 #239)

### 5.5 GPT pro round 1+2 (Phase 1.1 v1 audit)

大节点打包给 GPT pro. r1+r2 一致 NOT GO + 4 P0 + 7 必修. 引出 Step A-H 8
commit (3d35a62 → e5c41b9):
- A `python -O` 防线 (assert → explicit if)
- B F3 cert ↔ literal multiset 绑定
- C F2 partition enclosure + cut_edges canonical
- D F4 cert.bitset == BFS 严等
- E F1 P(g)⊆R strict (核心数学层)
- F F1 evaluate 真重算 (Gemini r33 P0)
- G lru_cache(256) + F4 commodity_id spec align (Gemini r34)
- H Phase 1.3 perf opt TODO + Gemini r33-35 archive

期间 Gemini r33-r35 catch 4 升级 P0/High 全在 Step F/G 修.

### 5.6 GPT pro v2 audit + Step I/J/K (bdaa303)

v2 r1+r2 catch 3 新 P0:
- I `step_7_evaluate_cut` 接 family dispatch (Step F family 函数永远 bypass)
- J F3 blocking_slot → selected_poses[slot] → blocking_pose_id 真绑定
- K F4 separator_cells in-grid + ∈ owner∪ghost 显式验

### 5.7 GPT pro v3 audit + Step L (a38620c)

v3 catch F1 duplicate `contributing_groups` P0: cert 同 group 重复列让
demand_R 双算. Step L 加 seen_gids 去重 + tuple demand 真等 + gap consistency.
顺手清 ruff F401 12 个 (但因 ruff.toml ignore 没真清, Step M 才真清).

### 5.8 GPT pro v4 audit + Step M (273fbff)

v4 r1+r2 catch 3 新 critical:
- M.1 `replay_cut(canonical_rules=None)` silent ATTACH 绕 validator → fail-closed
  (state.canonical_rules fallback → 没就 HOLD)
- M.2 F2 commodity_demand 无 source-of-truth registry → BState 加
  commodity_demands 字段, validator require
- M.3 F4 commodity_id pass-through → BState 加 commodity_routes 字段,
  validator require registry route src/sink == cert
- ruff F401 force-fix 真清

### 5.9 GPT pro v5 audit + Step N (afef8f1)

v5 r1+r2 catch 2 新 P0:
- N.1 F2 commodity registry 仍不 sound — duplicate contributing + same-side
  route 不跨 partition 全允过 → contributing 去重 + commodity_routes require +
  cross-partition route check
- N.2 `CutStore.add_cut` 直接 active 注册 silent attach window → default
  `initial_state="held"`, caller (replay 成功) 必显式 reactivate

### 5.10 GPT pro v6 audit + Step O (c8fb7ef)

v6 r1+r2 catch 3 新 P0, 同一 ghost lifecycle 漏口两端:
- O.1 (round 2) validator 不验 `scope.ghost_rect_id == GHOST_AGNOSTIC` 合法性
  → F1 验 `ghost ∩ R == ∅`, F2/F4 直接 reject GHOST_AGNOSTIC
- O.2 (round 1) `on_ghost_rect_changed` accept scope-only replay_fn 绕 family
  validator → `replay_fn` 改 Optional, default lazy import `replay_cut` 走
  full gate
- O.3 (round 1) add_cut 非法 `initial_state` raise 后 cut 残留 store →
  validate 移到所有 mutation 前

### 5.11 累积现状 (Step O 结束)

- 14 commit src/ 改动 (Step A-O)
- 5 commit infra (build script v2-v7)
- 11 GPT pro audit (v1 r1/r2 + v2 r1/r2 + v3 + v4 r1/r2 + v5 r1/r2 + v6 r1/r2)
- 22 Gemini round (r14-r35)
- 172 cuts test (从 v1 包的 139 累计 +33 regression)
- 8 高位 invariant 全 close (没 unsolved P0)

---

## 6. 现状细则 (commit `c8fb7ef` 起算)

### 已闭环
- F1 region_capacity / F2 cutset / F3 port_exposure / F4 component_reach
  validator + oracle + evaluator
- Lifecycle 9 step (gen / minimize / serialize / deserialize / validate /
  attach-scope check / evaluate / apply-to-master / replay)
  - Step 2 minimize defer Phase 1.2 P1.11 (F5 deletion + QuickXplain)
  - Step 8 apply-to-master defer Phase 1.3 P1.21 (CP-SAT 真集成)
- CutStore 6-dim watcher (by_cell / by_group / by_pose / by_commodity /
  by_region / by_ghost), quarantine / hold / on_ghost_rect_changed 状态机
- Replay fail-closed (canonical_rules=None → state.canonical_rules fallback
  → HOLD)
- CutStore.add_cut 默认 `initial_state="held"` (production 必经 replay /
  validator gate 才 active, test fixture 可 bypass)
- on_ghost_rect_changed 默认 lazy import replay_cut 走 full family validator
- F1 GHOST_AGNOSTIC 验 `ghost ∩ R == ∅`; F2/F4 GHOST_AGNOSTIC 直接 reject

### 测试 / 静态 gate 状态
- pytest: 172 cuts test pass (普通模式 + `python -O` 防线 regression)
- ruff: clean (default config + `--config "lint.per-file-ignores={}"` 都 clean)
- mypy --strict: 37 errors (typing hygiene, 非 runtime fatal — Dict/Callable
  缺泛型 + Any return + unused ignore)
- vulture: `evaluate_literal_port_exposure` 仍标 unused (走 generic multiset path)
- bandit: 5 Low B101 assert (lifecycle/replay 内部, validator 入口已改 explicit guard)
- radon: average A; `validate_cutset` D(27), `validate_component_reach` D(24),
  `validate_port_exposure` D(23) — 5 轮 audit 反复加 binding 后升级, P1 拆 helper

### Audit archive (包内 ship)
- `external_review/gpt_pro_phase1_1_v{1,2,3,4,5,6}_audit_*.md` (11 GPT pro audit)
- `cross_check/gemini_round_{14..35}*.md` (22 Gemini cross-check)
- `PHASE_POST_1_1_REFACTOR_PLAN.md` (本文件)

---

## 7. 默认 skip 的方向 (历史死路 baseline)

后续重构不再 propose 这些. 详 `paradigm_death_timeline_27_lever.md`.

- **HiGHS / Gurobi 替 OR-Tools**: PoC 42 GB > 30 GB OR-Tools (Phase 3B repair5)
- **多机分布式**: 硬件 1 主机 + 1 远程, WAN 延迟 ≥ 100 ms
- **LP relaxation 替 CP-SAT**: B1 pose-bool master 已 verdict 死, master.solve
  解不动是 inherent
- **27 lever 死路**: B1 / PCR-CUT / SAC-Hull / D2 / cand C / L01-L26 — 各
  paradigm_death_timeline.md cite 死法
- **Step A-O 已 close 的 finding**: GPT v1-v6 + Gemini r33-35 catch + 8 invariant
  全 close, 不重复 (除非加新 evidence)

---

## 8. GO 标准 / 验收准则

每段 done 怎么定义. 不只 "代码改完 commit pass test", 而是要过 reviewer audit.

### 8.1 Phase 1.2 P1.11 入门 GO

7 项 factual fix 全 land:
1. strict gate default ON
2. spec drift 7 处全清 (PoseId / family list / F3 direction / F1 region_kind /
   F2 cert schema / F4 commodity_id / source_digest spec)
3. source_digest 真 hash
4. ghost_rect tuple 语义 lock + 非方形 fixture
5. mypy strict 37 errors → 0 (typing hygiene 收尾)
6. radon D(27)/D(24)/D(23) → C(15) 或以下 (helper 拆)
7. `evaluate_literal_port_exposure` 决定 (删 or 接 dispatch)

验收:
- 172+ cuts test pass (现 172, P1.11 入门后 +5-10)
- ruff/mypy/vulture/bandit/radon 全 clean
- GPT pro v8 audit 收 GO 或最多 P1 finding (不再 P0)
- Gemini cross-check round 36+ 通过

### 8.2 Phase 1.2 P1.11-P1.15 (F5-F9 实施) GO

5 family 各自完整:
- validator + evaluator + oracle (oracle 可 stub)
- ≥ 10 unit test (sound + ≥ 3 attack 反例 + schema_err + adversarial scope)
- spec ↔ src ↔ 真数据 三层 align
- 每 family Gemini cross-check 通过
- 跨 family invariant test (e.g. F5 接 lifecycle step 2 minimize, F6 跟 F1 region 重叠 case, F7 跟 F3 port 重叠 case, F8 复用 F4 BFS helper, F9 跟 F6 density)
- F5-F9 全 register FAMILY_VALIDATORS, strict gate ON

验收:
- 总 cuts test ~250+ (172 baseline + 5 family × 10-15 each)
- 大节点 GPT pro batch audit 通过 (整 Phase 1.2 vs 单 family)
- production smoke 真数据 F5-F9 oracle 跑通 (各 oracle 真 emit cut 或合理
  fail-closed)
- 跟 PROJECT_LOCK §3A 不冲突 (family list 仍 9 个, mode 不变)

### 8.3 Phase 1.3 P1.21 (CP-SAT propagator 集成) GO

- step_8_apply_to_master 真接 master CP-SAT (env flag `EXACT_B_DESIGN_V2=1`)
- lazy → hard constraint 转化 sound (cut attach 后 master state 跟 cut violate
  一致)
- 168h smoke (24h 短跑 subset) 真跑 prune 减 search tree (跟 baseline 比节点
  数 / 时间)
- hot path perf 优化:
  - json.loads cache on Cut (避 evaluator 反复 parse)
  - F4 BFS incremental connectivity (替 O(|Grid|) 全图 BFS)
  - by_exterior_watcher 实施 (减 evaluator 调用频次)
- thread-safe 验证 (multiprocess.spawn worker 各 cache 独立 + GIL-safe)

验收:
- 24h smoke 比 Phase 3B repair5 baseline prune ratio improve ≥ 10%
- propagator 10K calls/sec scale evaluator latency ≤ 100 µs / call
- 真 168h campaign 跑通至少 1 个 candidate full search (不只 timeout)
- GPT pro audit Phase 1.3 整 phase 通过

### 8.4 Phase 1.5+ (production integration) GO

- commodity registry production inject 路径 unique builder (一函数从真 data
  build BState)
- 各 family oracle 真实施 (不再 stub `return []`)
- F3 active_port_witness verify
- F2 max_flow_LP algebraic witness
- F4 commodity registry 改 route_id 级别 schema (支持同 commodity 多 route)
- 168h 真 campaign 跑通 + 比 baseline (Phase 3B repair5 without cut framework)
  收敛 ≥ 30%

验收:
- 真 168h campaign 1+ candidate 真 OPTIMAL (不 timeout 不 UNKNOWN)
- GPT pro batch audit Phase 1.5 production GO
- 跟 Phase 3A delivery (r20260416) 衔接验证

---

## 9. 依赖图 — family / step / phase 之间怎么 chain

各段不是平行做的. 错顺序就走死路.

### 9.1 Family 内部 dependency

```
F1 region_capacity
   └─ Phase 1.1 闭环 ✓

F2 cutset
   └─ commodity_demands + commodity_routes registry (Step M+N)
   └─ patch_routing_core (Phase 1.5+ 复用 PCR-CUT 单 anchor 部分)

F3 port_exposure
   └─ candidate_placements pose ports lookup (Step E candidate_placements helper)
   └─ active_port_witness (Phase 1.5+ boundary_constraints LP)

F4 component_reach
   └─ commodity_routes registry (Step M+N)
   └─ d2_separator BFS helper (Phase 1.5+ 复用 D2 单 anchor 部分)

F5 pattern_nogood
   └─ F1-F4 任一 INFEASIBLE 后 fallback (literal pattern catch geometric 漏掉的)
   └─ lifecycle step 2 minimize (F5 driver)
   └─ L16 core_minimizer 复用 (deletion + QuickXplain)

F6 shape_packing_hall
   └─ F1 region helper 复用 (region_cells / capacity)
   └─ Hall theorem 实施 (greedy match 后 LP)

F7 power_hitting_set
   └─ F3 port_exposure 跟 power 版本同 dispatch
   └─ power_network helper (现 src/cuts/helpers/power_network.py stub)

F8 power_grid_reach
   └─ F4 BFS helper 复用 (component reach)
   └─ Liang-Barsky helper (现 src/cuts/helpers/ghost_geometry.py)
   └─ ghost_rect tuple 语义 lock (§8.1 Phase 1.2 入门必先)

F9 density_envelope
   └─ F6 跟 F9 都 region-density 约束, F6 land 后 F9 复用 region helper
```

### 9.2 Phase 间 dependency

```
Phase 1.2 P1.11 入门 (7 factual fix)
   ↓
Phase 1.2 P1.11-P1.15 (F5-F9 实施)
   依赖: 入门 strict gate default ON / spec drift 清 / source_digest 真 hash
   ↓
Phase 1.3 P1.21 (CP-SAT propagator 集成)
   依赖: F5-F9 全 register (lifecycle step 8 接 9 family dispatch)
   ↓
Phase 1.5+ (production integration)
   依赖: Phase 1.3 propagator 集成验 lifecycle 闭环
   依赖: BState production builder (Phase 1.2 入门 +/或 Phase 1.5 起做)
```

### 9.3 关键 ordering decision

- **source_digest 真 hash 必先** (Phase 1.2 §8.1 §3) — 不然 Phase 1.3 production
  data 轮换识别不出, cross-session cert replay 不可信
- **ghost_rect tuple 语义 lock 必先 F8** — F8 实施前不 lock 会让 Liang-Barsky
  跟 ghost_rect 横竖反
- **strict gate default ON 必先 F5-F9** — 新 family 漏 register 时 silent
  attach
- **BState production builder 必先 Phase 1.5+** — 真生产 inject 各 family
  validator 需要的字段, 不统一 builder 会让一处漏 inject 拖崩全 framework

### 9.4 跨 phase invariant

Phase 1.2 / 1.3 / 1.5+ 全 share 这些 invariant (PROJECT_LOCK §3A):
- 9 family list 不变 (不加 / 不删 / 不改 mode)
- cut schema 字段 invariant (cut.scope + cert + literals XOR geometric_payload)
- multiset eval slot anonymity (state_machine §5)
- adversarial soundness (validator trust boundary, oracle 不可信)

任一 phase 想改 invariant 必先 PROJECT_LOCK 更新 + spec/src/test 跨同步.

---

## 10. Phase 1.2 P1.11 入门 (低风险 factual 收尾)

进 F5-F9 实施前必清这几项. 全是 schema / spec / static hygiene, 不动 paradigm.
GO 标准见 §8.1.

### 10.1 strict registration gate default ON
- 文件: `src/cuts/replay.py:122`
- 改: `EXACT_FAMILY_VALIDATOR_STRICT` default `"0"` → `"1"`
- 影响: 未注册 family 进 replay → `NotImplementedError` 不 silent attach
- F1-F4 已注册, 切换不影响当前
- F5-F9 实施时每加 1 个必 register, 测试覆盖
- **风险**: 若任何调用方依赖默认非 strict (e.g. 半实施 fixture), 切换会破.
  mitigation: grep 现 codebase 看 strict env 使用; 切换前 dev env 显式
  `EXACT_FAMILY_VALIDATOR_STRICT=0` override

### 10.2 spec docs align (必修 #7)
- `state_machine_v2.md:42-45`: PoseId 改 `str` (src `lifecycle.py:42-49` 已是 str)
- `cut_lifecycle_v2.md:225-241 / 365-374 / 740-747`: 删 `symmetry_lift`, 加
  `power_grid_reach` / `density_envelope`
- `cut_family_specs/03_port_exposure.md:39-44`: direction 改 `N / S / E / W`
- `cut_family_specs/01_region_capacity.md:139-145`: region_kind 加 `left_or_bottom_union`
- `cut_family_specs/02_cutset.md:64-77 / 156-159`: cert schema 加 `contributing_commodities`
  集合语义 + cross-partition route 描述 (Step M+N)
- `cut_family_specs/04_component_reach.md:48-77 / 145-150`: commodity_id /
  commodity_route assumption 改 registry require, separator in-grid + ∈
  owner∪ghost 描述
- **风险**: spec 改完未跟 src 跨同步则下次 audit 反复触发 spec drift finding.
  mitigation: 每 spec 改加单元 test grep spec line vs src 值

### 10.3 source_digest 真 hash
- 当前 `lifecycle.py:635-637` + `oracles/region_capacity_oracle.py:179-186`
  写死 `"poc_source_digest"`
- 改: hash `canonical_rules.json + candidate_placements.json + mandatory_exact_instances.json
  + generic_io_requirements.json + oracle_versions` 内容
- spec 已 require: `cut_lifecycle_v2.md:881-903 / 80-86 / 146-154`
- 不修则 replay 不能识别 data source 轮换, 跨 session cert 可信度差
- **风险**: hash 函数选错 (e.g. mtime instead of content) 导致 cert 跨 session
  失效. mitigation: 内容 sha256, 不用 mtime

### 10.4 ghost_rect tuple 语义 lock
- 当前 `lifecycle.py:216` 注释 `(x, y, h, w)`, `helpers/ghost_geometry.py:108-116`
  返回 `(x, y, x+h, y+w)` — h/w 跟常规 (x+w, y+h) 反
- F8 power_grid_reach 实施前必锁:
  - 写明 schema: `(x, y, height, width)` 或改 object `{"x", "y", "height", "width"}`
  - 加非方形 fixture, e.g. `(10, 20, 3, 7)` verify AABB
- 否则 F8 接真 ghost_rect 时横竖反
- **风险**: 改 object schema 影响多处 helper + 测试; 改名 `x_span/y_span`
  减名 confusion 但仍是 tuple. mitigation: 倾向 object schema, 一次性改清

### 10.5 mypy strict 收尾
- 37 errors / 10 files, 主要泛型缺参 + Any return + unused ignore
- 重点收: `lifecycle.py` (`BState`) + `replay.py` + 4 family validator
- 让 schema 类型契约真在 type system 内 enforce
- **风险**: 收 strict 时改 type signature 影响 callers. mitigation: 小步 commit
  每次改 1 file mypy clean

### 10.6 拆 validator helper (radon D 级降)
- `validate_cutset D(27)` 拆: parse_cert / partition_disjoint / partition_subset_free /
  enclosure / cut_edges / commodity_registry / cross_partition / witness
- `validate_component_reach D(24)` 拆: components_disjoint / membership /
  recompute_bfs / separator / commodity_registry
- `validate_port_exposure D(23)` 拆: parse_cert / front_cell_math /
  blocking_pose_binding / literal_multiset / port_exists
- `validate_region_capacity C(20)` 顺手拆 cells_per_pose / demand /
  gap_consistency
- 不只是好看 — Step J/K/L/M/N/O 反复在最大函数里漏接线 invariant, 拆开后下次
  audit reviewer 更易定位
- **风险**: 拆后破坏现有 regression test. mitigation: 每拆一个 validator 跑
  完整 cuts test 不变

### 10.7 evaluate_literal_port_exposure 决定
- vulture 标 unused (走 generic `evaluate_literal_multiset`)
- 选项 a: 删 (统一 generic path)
- 选项 b: 接进 `step_7_evaluate_cut` literal dispatch 作 F3 specific evaluator
- 倾向 a (factual simpler, sound 不变), Phase 1.2 入门一行决定

---

## 11. Phase 1.2 P1.11-P1.15 实施 (5 new family)

入门完后进 5 family 实施. 每 family 单独 commit (≥ 5 commit), 跟 Phase 1.1
同样 cross-check rhythm. GO 标准见 §8.2.

### 11.1 P1.11 F5 pattern_nogood
- 用途: literal-based cut, 拒已知 unsat 状态. lifecycle step 2 minimize 入口
- 实施: `src/cuts/families/pattern_nogood.py` (validator + evaluator) +
  `src/cuts/oracles/pattern_nogood_oracle.py` (从 master infeasible witness 提)
- 复用: L16 `core_minimizer.py` deletion / QuickXplain helper
- spec: `cut_family_specs/05_pattern_nogood.md`
- **风险**: deletion+QuickXplain perf 是 NP-hard. mitigation: 限 ≤ N literal,
  超 N 不 minimize 直接 emit 原 cut

### 11.2 P1.12 F6 shape_packing_hall
- 用途: geometric cut, Hall's marriage theorem 推 region 内 pose 数下界
- 实施: validator (cert.required_count vs region.available_slots) + oracle
  (greedy bipartite match)
- 复用: F1 region helper (region_cells / capacity)
- spec: `cut_family_specs/06_shape_packing_hall.md`
- **风险**: Hall theorem 实施复杂. mitigation: 先 greedy 后 LP

### 11.3 P1.13 F7 power_hitting_set
- 用途: literal-based cut, 必选 power pole set
- 实施: hitting-set greedy minimize + multiset evaluate (复用 F3 path)
- 复用: F3 generic literal evaluator
- spec: `cut_family_specs/07_power_hitting_set.md`
- **风险**: hitting-set NP-hard. mitigation: LP relax 找近似 hitting set,
  validator 验 set 真覆盖

### 11.4 P1.14 F8 power_grid_reach
- 用途: geometric cut, Liang-Barsky AABB + BFS 电网可达
- 实施: `helpers/ghost_geometry.py` 已有 Liang-Barsky helper, 复用
- 前置: ghost_rect tuple 语义必先 lock (§10.4)
- 复用: F4 BFS helper
- spec: `cut_family_specs/08_power_grid_reach.md`
- **风险**: ghost_rect tuple 横竖反 bug. mitigation: §10.4 lock spec + 非方形
  fixture 必先

### 11.5 P1.15 F9 density_envelope
- 用途: geometric cut, region density 上界 (单位 cell pose count)
- 实施: validator (cert.density vs region.area × max_density) + oracle
- 复用: F6 region density helper
- spec: `cut_family_specs/09_density_envelope.md`
- **风险**: 数学 sound 边界 (max_density 怎么算). mitigation: 加 negative test
  覆盖 density 临界

### 11.6 P1.15+ test fixture 补全
- F3 direction E / W synthetic fixture (真数据只 N=273 S=257, E=W=0)
- F8 直接复用 E / W fixture
- ghost_rect 非方形 fixture
- F5-F9 各 family 7-10 test (sound case + ≥ 3 attack 反例 + schema_err +
  adversarial scope)

---

## 12. Phase 1.3 P1.21 (CP-SAT propagator 真集成)

F5-F9 落地后, evaluator 才进真 hot path (10K calls/sec). 这阶段 perf opt
必要. GO 标准见 §8.3.

### 12.1 step_8_apply_to_master 实施
- 当前 `lifecycle.py:743-751` NotImplementedError
- 接 `benders_loop` hook (env flag `EXACT_B_DESIGN_V2=1` 切新框架)
- Lazy → hard constraint 转化, 跟 master CP-SAT model 真集成
- **风险**: master 加 lazy constraint 可能影响 master.solve 收敛 (constraint
  push 太多导致 propagator overhead). mitigation: 阶梯式启用, 先 F1 single
  family 跑通后逐步 F2-F9 wire

### 12.2 evaluate hot path perf opt
GPT v3 Gemini r35 已识别, Step H 加 TODO docstring 留好:

- **cache parsed cert_dict on Cut**: 避 hot path `json.loads` 每次 ~2µs,
  10K calls 累 20-50ms/sec. 修法: attach 阶段 eager parse 挂内存
- **F4 evaluate 改 incremental connectivity**: 当前 `_bfs_component`
  O(|Grid|) per call. Phase 1.3 propagator 10K/sec 数量级退化. 修法 union-find
  with rollback / cache last-known component bitset + dirty flag
- **lru_cache(256) on _decode_region_bitset**: Step G land OK, 但 Phase 1.3
  跨 cut 反复调时 cache miss risk. 修法 attach-time eager decode 持 FrozenSet
  于 Cut.scope
- **风险**: cache invalidation bug. mitigation: 每 cache key 必 content-addressed
  (cert hash / source_digest), 不依赖 mtime / mutable state

### 12.3 by_exterior_watcher 实施
- GPT v3 Gemini r35 P0, Step H 暂 defer (sound 不需要, evaluate 重算保 — Step F)
- Phase 1.3 lazy → hard constraint 后, evaluator 不再被自动调, watcher 必必
- 实施: `CutStore` 加 `by_exterior_watcher: Dict[Cell, Set[CutId]]`, 跟
  exterior_blocks 变化时 trigger affected cut re-replay
- F1 GHOST_AGNOSTIC cut 注册到此 watcher
- **风险**: watcher 跟 ghost_watcher 重复 invalidate 浪费. mitigation: cut 只
  入一个 watcher (GHOST_AGNOSTIC → exterior_watcher, else → ghost_watcher)

### 12.4 propagator thread-safe 评估
- 当前 `lru_cache(256)` multiprocess.spawn 各 worker 一份, 不共享
- Phase 1.3 propagator 如果 master CP-SAT 内部多线程 callback, lru_cache 是
  thread-safe (GIL + functools 实施) 但 cache pollution 跨决策回溯仍要 verify
- HR1 thread-safe 是 Phase 1.3 评估项
- **风险**: multi-thread propagator callback 跨 worker 共享 store. mitigation:
  现 CP-SAT propagator 是单线程 callback, Phase 1.3 直接验; 多线程时再加 lock

---

## 13. Phase 1.5+ (production integration)

Phase 1.3 framework 跑通后接真生产 data + 真 oracle. GO 标准见 §8.4.

### 13.1 commodity registry production inject
- 当前 `BState.commodity_demands` / `commodity_routes` Phase 1.1 mock 注入
- Phase 1.5+ 真 inject 路径: 从 `data/preprocessed/commodity_demands.json` +
  routing planner output + master_solution.commodities 真 build
- 设计 `build_bstate_from_production_inputs()` 统一入口, 覆盖:
  - canonical_rules + facility_templates
  - mandatory_exact_instances + instance_to_facility_type
  - candidate_placements
  - commodity demand / routes (从 production data)
  - source_digest 真 hash

### 13.2 registry schema 评估 (route_id vs commodity_id)
GPT v5 / v6 提出: 当前 `{commodity_id: {"src", "sink", "demand"}}` 只支撑
"一 commodity 一 route". 真生产同 commodity 可能多 src/sink pair (e.g.
`blue_iron_ore` 多 mining tile → 多 refinery).

候选 schema:
```python
commodity_routes: {
    route_id: {
        "commodity_type": str,
        "src": (x, y),
        "sink": (x, y),
        "demand": int,
    }
}
```

cert 改用 `contributing_route_ids` 不是 `contributing_commodities`.

**决策点**: Phase 1.5+ 真生产 commodity registry data 设计时定. 不提前 refactor
— 当前 Phase 1.1 / 1.2 / 1.3 不需要多 route 语义, 提前改 schema 风险 over-engineer.

### 13.3 各 family oracle 真实施
当前 F2 / F3 / F4 oracle 是 stub `return []`. Phase 1.5+ 接真 generator:

- **F2 cutset**: 复用 PCR-CUT `patch_routing_core.run()` (Phase 0-1 GO 但 Phase
  5 multi-anchor verdict NOT GO — 仍可作 generator 模板, paradigm 死的部分是
  跨 anchor 收敛, 单 cut 生成本身 OK)
- **F3 port_exposure**: 直接遍历 `state.cell_owner` + `candidate_placements`
  pose ports, 找 front_cell 被占的 case
- **F4 component_reach**: 复用 `src/search/d2_separator.py` BFS components +
  find_separator
- **F5 pattern_nogood**: deletion / QuickXplain 复用 L16 `core_minimizer.py`
- **F6 / F8 / F9**: 各自 spec §5 generator pseudocode

### 13.4 F3 active_port_witness verify
- spec `03_port_exposure.md:144-147` 要求 verify `active_port_witness_b64`
- 当前 validator 没查 (Phase 1.1 v1.0 假设 "all listed ports active")
- Phase 1.5+ 真 production data 时可能有 port 被 boundary_constraints LP
  disable, 必加 witness 验

### 13.5 F2 max_flow_LP algebraic witness
- spec `02_cutset.md:156-159` 要求 verify max-flow LP dual
- 当前 defer Phase 1.5+
- 接真 commodity routes + LP solver 后实施

---

## 14. 风险评估 + mitigation

defer / 已知 risk + 失败回滚策略.

### 14.1 GPT pro v5 verdict 排序 (最先爆 → 后)

1. **source_digest placeholder** — Phase 1.2 §10.3 必修
   - mitigation: hash 真 file content + replay 时验证 + cross-session test
   - rollback: 退到 placeholder, production 不 ship

2. **strict default 0** — Phase 1.2 §10.1 必修
   - mitigation: F5-F9 实施每加 1 family 加 register + missing-validator test
   - rollback: env override 显式 strict=0 (dev only)

3. **F2 commodity_demand registry** — Step M+N 已 partial close
   - mitigation: registry schema 评估 (Phase 1.5+ §13.2)
   - rollback: 暂时 F2 oracle stub 不 emit

4. **HR5 GHOST_AGNOSTIC exterior_blocks invalidate watcher** — Phase 1.3 §12.3
   - mitigation: Step F evaluate 重算保 sound, watcher 是 efficiency
   - rollback: Phase 1.3 没 propagator 集成时不需要

5. **HR1 thread-safe** — Phase 1.3+ §12.4 评估
   - mitigation: 现 CP-SAT propagator 单线程
   - rollback: multi-thread 时 cache invalidate 跨 worker

6. **HR3 free-placement / HR4 non-rect ghost** — Phase 1.5+ 真生产 data
   pattern 出现时再决策

### 14.2 Phase 1.2/1.3 实施风险

- **F5 deletion+QuickXplain perf**: NP-hard. mitigation 限 ≤ N literal
- **F6 Hall theorem 实施复杂**: mitigation 先 greedy 后 LP
- **F7 power hitting-set NP-hard**: mitigation LP relax 近似
- **F8 ghost_rect tuple 反惯例 bug**: mitigation Phase 1.2 §10.4 lock 必先
- **F9 density sound 边界**: mitigation 加 negative test
- **Phase 1.3 lazy → hard constraint master 性能**: mitigation 阶梯启用 (F1
  单 family 跑通后 F2-F9)
- **propagator hot path perf**: mitigation parsed cert cache + incremental
  BFS + watcher 三件套 (Step H TODO)

### 14.3 rollout / migration policy

cut framework 从 Phase 1.1 (4 family 单测) → 1.2 (5 family 加) → 1.3 (真接 benders_loop 主流程) → 1.5+ (production 168h campaign 含 cut store) 是渐进, 每阶段切换政策:

**Phase 1.1 → 1.2 切换 (strict gate default ON, Phase 1.2 first commit)**
- 切换点: §10.1 `EXACT_FAMILY_VALIDATOR_STRICT` 默认 `"0"→"1"` 是 Phase 1.2 **first commit**, 不是 5 family 都加完才开
- 理由: Phase 1.2 加 F5-F9 时, 新 family 在 strict gate 下若 dispatch 表漏注册会立刻 fail-closed → 不会沉默漏 cut. 5 family 全加完才开 = 漏注册的 family 沉默通过 4-5 commit, 等回头加 strict 测时已经堆 5 commit debug 难.
- revert criterion: 若 strict ON 后真生产 trial 30 min 内 ≥ 1% cut 被 schema_err reject 且非 spec drift → 临时 OFF + 排查 schema 跟 src 的 drift, 不是 framework bug
- revert 方法: 单 commit revert `EXACT_FAMILY_VALIDATOR_STRICT` default (env 一行改), 不影响其他

**Phase 1.2 → 1.3 切换 (cut framework 接进 benders_loop)**
- 切换点: §13 P1.21 step_8 apply_to_master 真集成 master.AddLinear 时, env-gated 默认 OFF
- 渐进 ramp:
  - Phase 1.3 first commit: env-gated 默认 OFF, unit test 在 mock master 上验
  - 1 candidate trial OFF baseline + ON enable 各 1 次, 对比 outcome
  - 24h shadow trial (env ON 但 cut 不真 attach, telemetry-only) → 看 §20 metric (cut count / valid rate / replay reject rate)
  - 24h half-trial (env ON + cut 真 attach + telemetry full) → metric 健康 + outcome 不退化 → GO 168h
- revert criterion: 真生产 168h trial 出现 (a) 168h-campaign-time wall-clock ≥ baseline + 20% / (b) outcome FEASIBLE → INFEASIBLE 反向 / (c) telemetry replay reject rate ≥ 5% → 立刻 env OFF + 单 commit revert master integration line
- revert 方法: env OFF 即可瞬时 disable; 不需要 git revert (framework 仍在 src/, 只是 master 不调用)

**Phase 1.3 → 1.5+ 切换 (production integration, commodity registry 真接 data pipeline)**
- 切换点: §13.1 commodity_demands / commodity_routes 从 mock fixture 切真生产 data pipeline 注入
- 不开关 toggle, 直接切 — 但 fallback: registry 若 None → §6 现状的 fail-closed HOLD (per Step M)
- revert criterion: 真 data pipeline 注入后 F2/F4 cut quarantine count ≥ Phase 1.3 baseline × 2 → registry schema 跟 src 不 align, 回到 §13.2 决策 (commodity_id vs route_id) 重审

**全 phase 通用 (任何 Step / Phase 通不过 GO)**
- 任 phase 通不过 GO 标准 → 不推下一 phase, 单独 debug commit
- 每 Step (A-O 跟未来 P+) commit 独立, git revert 单 step 不影响其他
- Audit verdict NOT GO 不 archive 假数据, reproduce verify 真才 commit ([[audit-verify-before-archive]])
- 大节点 audit 不通过 → 打包 next round, 不强推

**hot-roll (env toggle) vs phase-roll (src 改) 区分**
- env toggle (`EXACT_FAMILY_VALIDATOR_STRICT` / `EXACT_USE_POSE_BOOL_MASTER` 等): 瞬时切, 不需 git revert, 反复 toggle 不留 audit trail
- src 改 (新 family / 新 step / 新 watcher): git commit, revert 走 `git revert <SHA>`, 留完整 trail
- 政策: 任何 paradigm 决策 (B Design v2 invariant) 改动必 phase-roll (src 改 + PROJECT_LOCK 同步), 不准 env toggle 绕

---

## 15. 实施 rhythm (Phase 1.1 经验)

每 commit 后立刻 Gemini cross-check ([[gemini-review-algorithm-math]]).
大节点 (Phase 1.2 入门收尾 / Phase 1.2 5 family 全 land / Phase 1.3 集成 land)
打包给 GPT pro batch audit ([[big-milestone-gpt-pro-review]]).

每轮 audit:
- prompt 跟 zip 单独给 ([[review-pkg-no-prompt-inside]])
- 包内只放事实素材, 不放 verdict claim / Close 列表 / 引导 reviewer 句
- response 收到立刻 cp 进 `docs/research/.../external_review/`
  ([[external-review-reproducibility]])
- finding 必先 reproduce verify 才 archive
  ([[audit-verify-before-archive]])

---

## 16. 排期估算 (Claude pace, 不按人类工程师)

per `[[work-time-estimates]]` Claude 节奏估:

- Phase 1.2 §10 入门 7 项 — 单步 30-60 min Claude, 累计 ~5-7 commit, ~3-4 小时
- Phase 1.2 §11 5 family 实施 — 每 family ~1-2 commit + Gemini cross-check,
  累计 ~10-15 commit, ~6-10 小时 Claude work
- Phase 1.3 §12 propagator 集成 + perf opt — paradigm work, ~10-20 小时 Claude
  + master CP-SAT 真集成 wall-clock 死时间 (build / 测时间不可压)
- Phase 1.5+ §13 production integration — 跟真生产 data schema 设计耦合, 估
  随 Phase 1.5 data pipeline 进度

实际 wall-clock 主要消耗在 168h campaign 长跑 (cut framework 修改不直接影响
campaign 时间), 不在 Claude implementation 时间.

---

## 17. Open questions (待定)

1. Phase 1.5+ commodity registry schema (commodity_id vs route_id 级别) 何时
   决策? — Phase 1.5 真生产 data pipeline 设计时
2. F2 patch_routing_core 复用是否真 sound (paradigm 死在 multi-anchor 收敛,
   单 cut 生成仍 OK)? — Phase 1.5+ F2 oracle 实施时复 verify
3. evaluate_literal_port_exposure 删 vs 接进 dispatch — Phase 1.2 §10.7 一行决定
4. ghost_rect tuple 改 object schema vs 保留 tuple + 明确文档 — Phase 1.2 §10.4
   F8 实施前
5. Phase 1.3 propagator integration 跟 Phase 3B repair5 master 兼容性 — Phase 1.3
   §12.1 实施时验
6. F5 minimize NP-hard 超时阈值 — Phase 1.2 §11.1 实施时定

---

## 18. PROJECT_LOCK §3A 边界

后续重构不能跨这些边界 (per `PROJECT_LOCK.md` §3A):
- family ↔ mode XOR (literal vs geometric) 不可改
- cut.scope + cert + literals XOR geometric_payload 必填
- GHOST_AGNOSTIC sentinel 不能跟普通 ghost_id 混用 (Step O 加 validator 验)
- 9 family list frozen (无 symmetry_lift, 含 F1-F9)
- ASSUMPTION_VERIFIERS dispatch 必经 verifiers module, 不准 inline
- multiset eval slot anonymity (state_machine §5)
- source_digest 锁 data version (Phase 1.2 真 hash)
- adversarial soundness — validator trust boundary, oracle 不可信

任何 §3A 边界改动必先 PROJECT_LOCK 更新 + 跨 spec / src / test 同步.

---

## 19. 环境变量 / 配置清单

cut framework 用 env 做 phase/feature toggle, 不用 config file (跟项目其他 EXACT_* env 一致, 避免新 config schema). 本节列当前 cut framework 自己 + 跟主流程 cut 相关 env 的 interaction.

### 19.1 cut framework 自身 env (现状)

| Env | 当前默认 | Phase 1.2 默认 | Phase 1.3 默认 | 用途 |
|---|---|---|---|---|
| `EXACT_FAMILY_VALIDATOR_STRICT` | `"0"` | `"1"` (§10.1) | `"1"` | strict gate: 未注册 family / dispatch 漏注册 → fail-closed (replay HOLD). `"0"` 时 unknown family 走 schema_err 但不 hard-fail (Phase 1.1 调试模式). |

### 19.2 Phase 1.3 propagator 集成预留 env (实施时定名)

下面 env 在 §12 / §13 实施时加, 当前未实施. 命名前缀按项目惯例 `EXACT_CUT_STORE_*`:

| Env (拟) | 默认 | 用途 |
|---|---|---|
| `EXACT_CUT_STORE_ENABLE` | `"0"` | 总开关. OFF 时 master.solve 不接 cut, 框架仅 unit test 跑 (Phase 1.3 first commit) |
| `EXACT_CUT_STORE_SHADOW_ONLY` | `"0"` | shadow 模式: framework run 但 cut 不真 attach master, 仅 telemetry (24h shadow trial 用, §14.3) |
| `EXACT_CUT_STORE_TELEMETRY_PATH` | (unset) | telemetry jsonl 落盘路径. unset 时不落盘 |
| `EXACT_CUT_STORE_MAX_HELD_CUTS` | `"10000"` | held queue 上限. 超 → 拒新 cut 入 held (LRU evict 暂不做, 简单 cap) |
| `EXACT_CUT_STORE_REPLAY_REJECT_KILL_PCT` | `"5.0"` | replay reject rate 超此 % → 整 candidate trial abort (§14.3 revert criterion) |

最终名以 §13 实施时 commit 为准, 此表是 placeholder; 加 env 时同步更新本节.

### 19.3 跟主流程 cut/master 相关 env (cut framework 不直接读, 但 interaction matters)

| Env | 默认 | 跟 cut framework 关系 |
|---|---|---|
| `EXACT_USE_POSE_BOOL_MASTER` | OFF | B1 pose-bool master paradigm. cut framework 不绑 master 形态, OFF/ON 均工作 (Phase 1.3 接进时验) |
| `EXACT_B1_PATCH_ROUTING_CORE` | OFF | PCR-CUT (Path 14). 当前是独立 cut 生成路径 (env-gated front_blocked branch), 跟 B Design v2 cut store 不直接共享. Phase 1.5+ 可能 merge (TBD) |
| `EXACT_B1_PATCH_ROUTING_CORE_TOP_K` | `"3"` | PCR-CUT 同上 |
| `EXACT_B1_PATCH_ROUTING_CORE_SECONDS` | `"10"` | PCR-CUT 同上 |
| `EXACT_B1_PATCH_ROUTING_CORE_PER_PATCH_SECONDS` | `"5"` | PCR-CUT 同上 |
| `EXACT_B1_PATCH_ROUTING_CORE_MAX_CELLS` | `"900"` | PCR-CUT 同上 |
| `EXACT_B1_PATCH_ROUTING_CORE_QX_CAP` | `"32"` | PCR-CUT 同上 |
| `EXACT_B1_ABSTRACT_ROUTING_LAYER` | OFF | L2 abstract routing (SAC-Hull). cut framework 独立 |
| `EXACT_B1_SEPARATOR_HULL` | OFF | SAC-Hull L1 static separator. cut framework 独立 |
| `EXACT_B1_SEPARATOR_HULL_DYNAMIC` | OFF | SAC-Hull L2 dynamic separator. cut framework 独立 |
| `EXACT_B1_D2_COMMODITY_FLOW` | OFF | D2 Path 17 (paradigm 死). cut framework 独立 |
| `EXACT_B1_ROUTING_AWARE_BINDING` | OFF | routing-aware binding. 跟 F2/F4 commodity registry 可能交互 (Phase 1.5+ §13.1 决) |
| `EXACT_MASTER_GHOST_ANCHOR_FILTER` | (unset) | ghost anchor 限缩. 跟 cut.scope GHOST_AGNOSTIC 不冲突 (前者限 master, 后者限 cut applicability) |
| `EXACT_OUTER_SKIP_UNKNOWN` | OFF | outer search skip UNKNOWN candidate. 跟 cut framework 不直接交互 |

### 19.4 toggle 政策

- 任意 cut framework env 改 default 必走 §14.3 phase-roll (src commit, 不准 hot env override 绕)
- Phase 1.2/1.3 之前不准把 `EXACT_FAMILY_VALIDATOR_STRICT="0"` permanently 配进生产 wrapper (`scripts/run_campaign_*.sh`) — strict OFF 仅本地调试 / 测试时临时 export, 不入生产
- env 冲突检测: implementer 加新 env 时必在 spec / plan 19.1 表加一行 (避免散落)

---

## 20. Observability / telemetry plan

cut framework 跑起来后, 我们怎么知道在跑正常? Phase 1.1 当前只有单测 (`pytest src/tests/cuts/`) 验 sound, Phase 1.3 真接进 benders_loop 后必须有 runtime metric, 不能等 168h trial 结束才看. 本节定 metric / 落盘 / trigger.

### 20.1 现状 telemetry (已实施)

`src/cuts/store.py::CutStore.stats()` 返 snapshot:
```
{
  "total_cuts": int,       # 总 cut 数 (含 active + held + quarantined)
  "active": int,           # 当前 attach master 的 cut 数
  "held": int,             # held queue 待 replay 的 cut 数
  "quarantined": int,      # validator reject 进隔离的 cut 数
  "by_cell_keys": int,     # 6 dim watcher 各自 key 集合大小
  "by_group_keys": int,
  "by_pose_keys": int,
  "by_commodity_keys": int,
  "by_region_keys": int,
  "by_ghost_keys": int,
}
```
单测里被 exit_criteria ramp report 用. Phase 1.3 接 benders_loop 后要在每 outer iter / benders 内 iter 后 snapshot.

### 20.2 Phase 1.3 加的 metric (P1.21 实施时)

按 §22 review 实践拆 4 类 (cardinality / quality / latency / safety):

**cardinality (cut 数量/分布)**
- `cut_count_by_family`: dict[F1-F9 → int], 当前 store 中各 family 数
- `cut_count_by_state`: dict[active/held/quarantined → int] (现 stats 已有)
- `cut_generation_rate`: cut 加入速度 / outer iter (诊断 oracle 产 cut 是否健康)
- `cut_per_candidate_dist`: 各 candidate 累积 cut 数分布 (诊断 cut share 是否跨 candidate)

**quality (cut 是否真有用)**
- `cut_active_to_total_ratio`: active / total, 太低 (< 50%) 暗示 quarantine 多 / replay 不通过
- `replay_reject_rate`: replay_cut 返 QUARANTINE / HOLD 占总 replay 比例 (§14.3 revert criterion ≥ 5% → abort)
- `cut_pruning_contribution`: 每 cut attach 后 master.solve UNKNOWN→INFEASIBLE 比例 (Phase 1.5+ 数据)
- `cut_redundancy_rate`: 同 scope/cert 的重复 cut 占比 (high → minimize step 失效)

**latency (hot path)**
- `step_7_evaluate_latency_p50/p95/p99`: evaluate dispatch 延迟 (§12.2 perf target: p95 < 50 ms)
- `replay_latency_p50/p95/p99`: on_ghost_rect_changed 内 replay 延迟
- `validator_latency_by_family`: 各 F1-F4 validator 入口延迟 (诊断哪个 family 拖)
- `watcher_query_latency`: 6 dim watcher lookup 延迟 (诊断 by_cell 是否散到 4900 key)

**safety (adversarial soundness 指标)**
- `schema_err_count_by_field`: validator schema_err 按字段分布 (high → spec drift)
- `cert_literal_mismatch_count`: F3 cert↔literal multiset 不绑事件 (Step B / Step J 验, 应 0)
- `ghost_agnostic_reject_count`: F2/F4 GHOST_AGNOSTIC reject (Step O 验, 应 0 if no oracle bug)
- `canonical_rules_none_hold_count`: replay 因 canonical_rules None 走 HOLD 的事件 (Step M, 应 0 in production)

### 20.3 落盘 schema (Phase 1.3 落地)

类比 `data/telemetry/subproblem_repeat_<pid>.jsonl` (§P1 #12 cache-trio spike) 的 worker-per-file jsonl:

`data/telemetry/cut_store_<pid>.jsonl` — append 每 5 min snapshot
```jsonl
{"ts":"2026-MM-DDTHH:MM:SS","pid":12345,"outer_iter":47,"benders_iter":3,
 "cardinality":{"total":120,"active":85,"held":30,"quarantined":5,
   "by_family":{"region_capacity":40,"cutset":25,...}},
 "quality":{"active_ratio":0.71,"replay_reject_rate":0.012,...},
 "latency":{"step_7_p95_ms":34,"replay_p95_ms":12,...},
 "safety":{"schema_err":0,"cert_literal_mismatch":0,...}}
```

aggregate 工具 (类比 `scripts/analyze_subproblem_repeat_rate.py`):
- `scripts/analyze_cut_store_telemetry.py` (Phase 1.3 加) — 跨 worker pid 合并 + 各 metric 分布报告

### 20.4 trigger / alerting

168h campaign 内不做 push alerting (Phase 3B 项目政策无 telemetry receiver), 但 implementer / 用户主动看的 trigger:

- **24h shadow trial 完**: 必看 cardinality + quality, 若 `replay_reject_rate ≥ 5%` → 不进真 attach trial (§14.3 revert criterion)
- **168h 启动后每 6h 心跳检查**: 看 `cut_count_by_family` 是否各 family 都产, 不是只 F1 / F2 占 99% (oracle 偏 / spec drift 暗号)
- **168h 结束**: 跑 aggregate 脚本, 进 `docs/research/.../telemetry_aggregate/` archive 跟 outcome 关联

### 20.5 设计原则 (避免 metric bloat)

- 加 metric 必能回答 "出问题 我怎么定位" — 不加只 "好看不动" 的 metric
- 每 metric 写入 § 20.2 表时必标 unit + 触发看的 condition + 期望 range
- telemetry 落盘 overhead 必量 (Phase 1.3 perf opt §12.2): 写盘 < 0.1% wall, 否则 batch-flush
- worker-per-file jsonl 不 SQL / 不集中 db — 跨 worker 合并是 offline analyze 脚本的事

---

## 21. 测试 strategy + fixture 清单

172 cuts test 不是平铺, 按目标分 4 层. 本节定层 + 各层覆盖哪些 family + fixture 清单 + Phase 1.2 加 F5-F9 时怎么扩展.

### 21.1 测试 4 层

| 层 | 目标 | 文件 | 数量 |
|---|---|---|---|
| **Unit** | 单 function/class 行为 (helpers / store / lifecycle 各 step 各分支) | `test_store.py` / `test_lifecycle.py` / `test_helpers_*.py` / `test_assumptions_verifiers.py` | ~80 test |
| **Family** | 单 family validator + evaluator + oracle 端到端 (per family schema + 真数据反例) | `test_family_{region_capacity,cutset,port_exposure,component_reach}.py` | ~70 test |
| **Integration** | replay flow / on_ghost_rect_changed / add_cut 多 family 串 (跨 family interaction) | `test_replay.py` + 部分 `test_lifecycle.py` | ~15 test |
| **Adversarial** | 假 cert / cert↔literal 不绑 / GHOST_AGNOSTIC 非法 / canonical_rules=None bypass 等 (Step A-O 全部) | 散在各 `test_family_*.py` (e.g. test_*_p_g_outside_R / test_*_ghost_agnostic_rejected) | ~7 test |

具体 count 以 `pytest --collect-only -q src/tests/cuts/` 为准.

### 21.2 helper / fixture 当前组织

- **无 conftest.py / 无独立 fixture file** — 各 test 文件内 inline `_make_state` / `_make_<family>_cut` helper, 按 family 独立
- 主要 helper:
  - `test_family_component_reach.py::_make_state` + `_make_component_reach_cut`
  - `test_family_cutset.py::_make_enclosed_state` + `_make_cutset_cut`
  - `test_family_port_exposure.py::_make_state` + `_make_port_exposure_cert` + `_make_port_exposure_cut`
  - `test_family_region_capacity.py::_make_state`
  - `test_replay.py::_make_state` + `_make_f1_cut`
  - `test_store.py::_make_state` + `_make_cut`
  - `test_lifecycle.py::make_state_with_crusher_on_left_baseline` + `make_clean_state`
- 政策: Phase 1.2 加 F5-F9 时新 family test 沿用 inline helper 模式, **不**抽 conftest.py (避免跨 family 共享状态意外耦合, adversarial 测试主战场要的就是各 family 独立反例)

### 21.3 red fixture 清单 (docs/research/.../red_fixtures/)

`docs/research/p3_b_design_v2_20260521/red_fixtures/` 5 个 known-infeasibility 反例 (schema-level, 跑 evaluate_cut_as_multiset 验拦截):

| ID | 文件 | 反例几何 | 应拦 family | 来源 |
|---|---|---|---|---|
| **F1** | `F1_boundary_saturation.md` | 138 left+bottom cells 必 100% 铺满, 缺格 → INFEASIBLE | F1 region_capacity + F3 port_exposure | v14 review boundary correction (commit 976bc10) |
| **F2** | `F2_shape_packing_hall.md` | 长度 10 boundary 被 ghost 切 [1-4]+[6-10], 9 cell ≥ demand 9 pass capacity 但 length-3 `⌊4/3⌋+⌊5/3⌋=2<3` infeasible | F1 + F6 shape_packing_hall (Phase 1.2 P1.12) | Gemini 反例 B |
| **F3** | `F3_power_no_cover.md` | pose p 在 G1 ghost 下无 power_pole 候选覆盖 → INFEASIBLE | F1 region_capacity + F7 power_hitting_set (Phase 1.2 P1.13) | GPT 反例 power_cover + L16 lazy power |
| **F4** | `F4_ghost_scoped_replay.md` | G1 学 cut `not(A=pA ∧ B=pB)`; G2 移挡后 A=pA∧B=pB 合法 → 旧 pose-id-only replay 误剪 | F5 pattern_nogood (Phase 1.2 P1.11) + scope-aware replay HOLD | cut_lifecycle_v2 §4 walk-through |
| **F5** | `F5_power_grid_disconnect.md` | power network 断连, source → sink 4-conn 不连通 → INFEASIBLE | F8 power_grid_reach (Phase 1.2 P1.14) | GPT power cover ext |

每 fixture .md 文件结构: 反例几何 + MasterStateV2 表达 + 期待结果 + Hardcode cut object + evaluate 期望.

Phase 1.2 加 F5-F9 时按 §11 各 family 步骤每加 1 family 至少 1 red fixture (含反例几何 + cert + literal binding).

### 21.4 测试 strategy by phase

**Phase 1.2 入门 (§10, 7 项 factual fix)**
- 不加新 family, 强 strict gate / spec align / source_digest 真 hash
- test 要求: §10.1 strict gate 加 regression (未注册 family OFF→fail-closed)
- §10.4 ghost_rect tuple 改 object 加非方形 fixture e.g. `(10, 20, 3, 7)`

**Phase 1.2 P1.11-P1.15 (§11, 5 family)**
- 每 family 至少: 1 unit (helper) + 3 family (validator schema + cert binding + evaluator 真重算) + 1 adversarial (假 cert) + 1 red fixture 拦
- F5 deletion + QuickXplain test 单独 (复杂, 加 minimize step)
- F6 Hall theorem 加 4-5 反例 (interval graph 各类)
- F7 set cover 加 LP relax 边界 + ln(n) approximation 上限
- F8 Liang-Barsky AABB 加非方形 + 正交 + 退化 (零长度) 反例
- F9 density envelope 加 baseline `cap/area=1.0` 边界

**Phase 1.3 (§12, propagator 真集成)**
- 加 integration test: master.AddLinear mock + cut store apply_to_master + cp_sat propagator round-trip
- 加 perf test: step_7 / replay latency p95 < §20.2 阈值
- 加 telemetry test: jsonl schema validate (§20.3)

**Phase 1.5+ (§13, production integration)**
- 接 real benders_loop, 加端到端 24h shadow trial (test 不跑, 是 trial)
- regression: 历史 168h baseline outcome (UNPROVEN candidate 列表) 不退化

### 21.5 viewer sample vs production 全集

cut framework 测试用 **viewer sample** (~273 pose, BSP=54), production 168h 用 **全集** (~81795 pose, BSP=134). Sample 是单测 + 反例 reproduce 用 (上传 review pkg 时也是 sample, 大小 < 1 MB), 全集仅生产 trial 用 (53 MB).

差异:
- sample F1 14 outside-pose 反例数字 (GPT v3 cite) 来自 viewer sample, **production 全集 outside count 不同**
- adversarial 反例若 cite 具体 pose_id, 测试 fixture 必显式声明 sample-only, 不假定全集 reproduce

review pkg 默认 ship 全集 (53 MB), README 提醒 reviewer 反例数字 vs sample 关系 (build_v8 script 已加).

### 21.6 静态 gate (lint / type / dead code / security / complexity)

随测试一起 enforce, 不只 `pytest` pass:

| 工具 | 当前 strict | Phase 1.2 入门 (§10.5/10.6) | 用途 |
|---|---|---|---|
| `ruff check` | clean (default + `--config "lint.per-file-ignores={}"` 都 clean) | 维持 | F401 / import order |
| `mypy --strict` | 37 errors | → 0 (§10.5) | 类型 hygiene |
| `vulture` | 1 unused (`evaluate_literal_port_exposure`) | 决定 (§10.7) | dead code |
| `bandit` | 5 Low B101 assert (内部, validator 入口已 explicit guard) | 维持 | security |
| `radon cc` | D(27/24/23) 3 处 | 拆 helper (§10.6) | complexity |

每 commit 必跑 `pytest src/tests/cuts/ -q` + `ruff check src/cuts/`; 大 commit (新 family / 改 step) 必跑全套 5 工具.

---

## 22. 审查策略 (Gemini per-commit + GPT pro 大节点)

Phase 1.1 经验: Gemini 11 round Day 15/16a/16b 堆到 round 14 才 cross-check, 找出 3 致命 bug + 2 schema 漏 — 单 spec single-step cross-check 防 cascade ([[gemini-review-algorithm-math]]). GPT pro 11 round v1-v6 audit catch 4 critical blocker (F1 demand P(g)⊆R / F2 partition / F3 cert↔literal / F4 commodity) Gemini 全 miss — 那是 adversarial soundness 层 ([[adversarial-soundness-audit]]). 两层分工互补, Phase 1.2 不可少.

### 22.1 Gemini per-commit cross-check (fast, narrow, schema layer)

**触发条件 (每 commit 必经)**
- 任何 src/cuts/ 改动 commit 后立刻调 ([[gemini-review-algorithm-math]] 用户原话: "先 check, 以后都是先 check 再继续", 不堆)
- 纯 implementation 不算 (refactor / rename / IO / docstring 改); 数学/算法/spec/schema 层必跑
- helper 拆 / radon D 级降 (§10.6) 算 refactor 但若动 validator 路径仍跑

**模式 (per [[gemini-prompt-audit-mode]])**
- audit 模式, 不是 GO 章 ritual: 验 spec ↔ src ↔ data gap, push find problem
- prompt 含 real data path (`data/preprocessed/candidate_placements.json` 等), 不只 sample
- armor: 强制 3 死法 + 反 vague hyperbole + 不重写 prompt 别调
- "GO" 不是 verdict 目标; "specific finding + reproducer" 才是

**频率 / 工时**
- 单 commit ~5-10 min round-trip (free-tier API key, [[gemini-math-consultant]])
- Gemini round number 在 archive 文件名连号 (当前 r35, 下个 r36...)
- archive 立即 cp 进 `docs/research/.../cross_check/gemini_round_NN_*.md` ([[archive-research-transcripts]])

**Phase 1.2 加严 (R34 round 加严)**
- 每 commit 立刻 cross-check, **不堆**. 不准 "5 commit 后一起跑" — Day 15 累积 cascade 教训
- finding 必先 reproduce (script / grep) 才 archive 进 cross_check/, 不准 archive 假 finding ([[audit-verify-before-archive]])

### 22.2 GPT pro 大节点 batch audit (deep, broad, adversarial layer)

**触发条件 (大节点 boundary)**
- Phase 1.1 闭环 ✓ (v1-v6 已经跑过 11 round)
- Phase 1.2 入门 7 项 (§10) close — next trigger
- Phase 1.2 5 family 全 land (P1.11-P1.15) — next next trigger
- Phase 1.3 propagator land + 24h shadow trial — next³
- Phase 1.5+ production integration — final pre-168h

**模式 (per [[big-milestone-gpt-pro-review]] + [[review-pkg-no-prompt-inside]])**
- 打包 7z + zip 壳 + ship 7za binary (per `[[review-pkg-7z-strategy]]`, ~5-7 MB 全项目)
- prompt 不放包里, 通过 chat message 单独给 ([[review-pkg-no-prompt-inside]])
- armor 三段式 ([[gpt-review-prompt-armor]]): 真瓶颈 + 死路黑名单/白名单 + 不可达必须形式化证明 (不准 "I believe / intuition")
- 包 standalone — 不引用历史 GPT verdict ("跟 v3/v4 不一样" 这类不写, 详 [[review-package-for-new-window]])

**adversarial soundness check 清单 (主战场, GPT pro 主要 catch 这层)**

按 [[adversarial-soundness-audit]] 5 验:
1. **cert 内 sound**: cert 本身字段一致 (region cells ⊆ free / partition A∪B==free / commodity_id ∈ registry / src/sink_component bitset 真 BFS)
2. **cert ↔ literals 绑定**: F3 cert blocking_pose_id == literal multiset; F5 cert ↔ literal pattern 严等
3. **cert ↔ 真数据**: cert region 跟 canonical_rules.json 的 placement_rule_for_group 同源; cert commodity 跟 generic_io_requirements.json 真存在
4. **cert ↔ state**: cert 跟 BState `pose_domain` / `cell_owner` / `commodity_demands` 一致, 不是 oracle 凭空造
5. **cert ↔ 不变量**: cert 跟 PROJECT_LOCK §3A invariant 一致 (GHOST_AGNOSTIC sentinel / family-mode XOR / source_digest)

GPT pro 主要 catch (3+4+5) — Gemini 倾向 catch (1+2) schema 层. 实施 family validator 必主动想: "假 cert 能不能 pass?" Step A-O 教训.

**频率 / 工时**
- 1 大节点 ~ 1-2 round (打包 + 等 GPT pro verdict + close P0). Phase 1.1 用了 11 round 是因为反复 NOT GO + 我修 + 再打包. 正常 1-3 round
- 单 round 工时: 打包 5 min + 等 GPT 几 min + close finding ~30 min - 数小时 / P0
- archive: `docs/research/.../external_review/gpt_pro_phase{N}_v{V}_audit_*.md`

### 22.3 audit verdict criteria — GO / NOT GO

我们对 reviewer 的 verdict 怎么定义:

**GO 准则 (大节点过 audit)**
- 0 P0 (critical, soundness 破坏 / 生产 crash)
- ≤ 3 P1 (high, soundness 减弱 / 非生产路径 bug), 各有 mitigation 计划
- P2/P3 (medium/low, cosmetic / cleanliness / nice-to-have) 不卡 GO, 进 followup queue (#239)

**NOT GO 准则 (不推下一 phase)**
- ≥ 1 P0 → 必 close (Step A-O 模式) 才下一 round
- > 3 P1 → 排序 close top-3, 余进 followup
- 同 round 重复 catch 同 finding → spec drift, 必同步 spec/src/test 三层

**P 分级判定 (跟 GPT pro / Gemini 沟通时怎么定)**
- P0: validator 可被假 cert 骗过 (Step A-O 全部 P0 都属此); 生产 crash; data corruption; soundness 数学根据被否定
- P1: validator 不验某 sub-invariant 但当前数据不触 (Phase 1.2 加 fixture 触发); 静态工具 strict 不通过 (mypy/radon 严警); spec 跟 src drift 不致 soundness 破
- P2: dead code / 注释错 / docstring 旧; lint 非 fail
- P3: cosmetic / 风格

### 22.4 review 输入 / 输出 (各 reviewer 各自要看的)

**Gemini per-commit 输入**
- diff (commit SHA) + 改动 file 全文 + 相关 spec section (e.g. cut_family_specs/F1.md)
- 真数据 path (e.g. data/preprocessed/candidate_placements.json) — 让 Gemini 跑 reproduce
- 不放: full project, 历史 GPT verdict, 多 commit 累积 diff

**GPT pro batch 输入**
- 全项目 zip (v8 模式, 7z 壳 + ship 7za)
- 真数据 production 全集 (53 MB)
- audit archive 累积 (cross_check/ + external_review/) — 给 reviewer context 知道之前怎么修
- spec 完整 (cut_lifecycle_v2 / state_machine_v2 / cut_family_specs/)
- 不放: plan doc (主动性引导, per [[review-pkg-no-prompt-inside]]); prompt; verdict claim / Close 列表

**输出 archive 政策 ([[archive-research-transcripts]] + [[audit-verify-before-archive]])**
- Gemini response 立即 cp 进 `cross_check/gemini_round_NN_<topic>.md`
- GPT pro response 立即 cp 进 `external_review/gpt_pro_phase{N}_v{V}_audit_round{R}_{VERDICT}.md`
- 每 finding 必 reproduce verify (~5-15 min, cheap) 才算数; reproduce fail 标记 "unverified" 不计入 verdict P 列表
- archive 进 git, 不准只本地 — review pkg 给下个 reviewer 时也带上 archive

### 22.5 Gemini vs GPT pro 分工 summary

| 层 | Gemini | GPT pro |
|---|---|---|
| 频率 | per-commit (高频, 1-2/day) | 大节点 (低频, 1-2 round/phase) |
| 输入 size | diff + 单 spec section + 真数据 path | 全项目 zip |
| 主战场 | schema ↔ src ↔ data gap | adversarial soundness (假 cert 能 pass 吗) |
| 强项 | 自然口吻写作 + 快速 schema check ([[gemini-better-at-natural-tone]]) | deep cross-file consistency + paradigm check |
| 弱项 | 不会 push adversarial 反例构造 ([[gemini-prompt-audit-mode]] armor 补) | 慢, 不能 per-commit |
| 工时 | ~5-10 min/round | ~打包 5 min + GPT 等 + close 30 min-小时 |
| Phase 1.2 政策 | 加严: 每 commit 立刻, 不堆 | 大节点 trigger, 5 family land / Phase 完 |

---

## Appendix A. 术语表 / Glossary

按字母 / 类别归. 术语首次在 plan 出现时不展开, 来此 anchor.

### A.1 项目顶层

- **终末地 (Arknights: Endfield)** — 鹰角网络游戏, 项目目标为其工业规划解题
- **IndustrialPlanner** — 终末地游戏内工业规划玩法, 70×70 grid + 266 facility instance
- **70×70 grid certified exact solver** — 本项目, 求 `max_lex(area, min_side)` 最大空矩形 + 全 facility placement 可行性证明
- **valley4_protocol_core** — 当前 active scope 单 base; 其他 base (`valley4_infra_outpost` 等) future_scope
- **certified_exact mode** — 项目主路径, 跟 `exploratory` 路径严格分离; 本 plan 全 scope 在 certified_exact

### A.2 Cut Framework (B Design v2)

- **B Design v2** — cut framework spec 第二版, 含 9 family + 9-step lifecycle + state machine v2. (v1 早期 spec 死, 详 §4.7)
- **F1-F9** — 9 个 cut family (frozen, PROJECT_LOCK §3A):
  - F1 `region_capacity` (geometric) — 区域容量 pigeonhole / set covering
  - F2 `cutset` (geometric) — Menger min-cut max-flow
  - F3 `port_exposure` (literal) — 命题逻辑 + slot anonymity
  - F4 `component_reach` (geometric) — 4-conn graph BFS connectivity
  - F5 `pattern_nogood` (literal) — minimal unsat core + QuickXplain
  - F6 `shape_packing_hall` (geometric) — Hall's marriage theorem
  - F7 `power_hitting_set` (literal) — set cover NP-hard / LP relaxation
  - F8 `power_grid_reach` (geometric) — Liang-Barsky AABB intersection
  - F9 `density_envelope` (geometric) — 上界几何 (≥ area baseline=1.0 trivial)
- **family mode (literal vs geometric)** — F1/F2/F4/F6/F8/F9=geometric (sound deduction from geometry), F3/F5/F7=literal (proposition over pose assignments). PROJECT_LOCK §3A XOR
- **9-step lifecycle** — canonicalize → generate → minimize → serialize → deserialize → validate → attach-scope check → evaluate → apply-to-master
  - 当前 Phase 1.1: step 1/3-7 sound 闭环; step 2 (minimize) defer Phase 1.2 P1.11 (F5 deletion+QuickXplain); step 8 (apply-to-master) defer Phase 1.3 P1.21
- **cert (certificate)** — cut 的 mathematical 证明对象, 含 region/partition/component/commodity 等 family-specific 字段. validator 重算 cert 验 sound
- **literal** — cut 中排除的具体 pose assignment (`x[instance_id, pose_id]` boolean). literal-mode cut 用; geometric-mode cut 不直接持 literal
- **blocker** — F3 cert 中 blocking 一个 port slot 的另一 pose; F5 cert 中 "如果这些 literal 都 true 则 INFEASIBLE" 的支撑集
- **multiset eval** — slot anonymity 的形式化: slot 集合上 S_n permutation 群作用不变. evaluate 不绑具体 slot id, 看 multiset 计数 (state_machine v2 §5)
- **watcher** — `CutStore` 6 维 index (by_cell / by_group / by_pose / by_commodity / by_region / by_ghost), state 变化时 O(查询命中) 而非 O(总 cut) 找 affected cut
- **replay** — ghost rectangle 变 / state 变 / canonical_rules 变 → 触发 `on_ghost_rect_changed`, 已 active/held cut re-validate. fail-closed: canonical_rules=None → HOLD (Step M)
- **state machine (held / active / quarantined)** — cut 入 store 默认 held (per Step N); replay 通过 validator → active; validator reject → quarantined (隔离, 不再 try)
- **GHOST_AGNOSTIC** — sentinel scope value, 标记 cut 对 ghost rectangle 不敏感. F1 必验 ghost ∩ region == ∅ (Step O); F2/F4 直接 reject GHOST_AGNOSTIC scope
- **scope versioning** — `cut.scope` 含 `ghost_rect` + `source_digest`; ghost/data 变 → scope 失效 → cut 进 replay path
- **source_digest** — `canonical_rules.json` + preprocessed data 的 content hash. 当前 Phase 1.1 placeholder `"poc_source_digest"`, Phase 1.2 入门 §10.3 改真 hash
- **adversarial soundness** — validator 必须扛 "假 cert 攻击" — oracle 不可信 (Byzantine), validator 是 trust boundary. Step A-O 主要 close 的层
- **strict gate** — `EXACT_FAMILY_VALIDATOR_STRICT="1"` 时未注册 family / dispatch 漏 → fail-closed. Phase 1.2 default ON

### A.3 Solver / Master 拓扑

- **CP-SAT** — Google OR-Tools Constraint Programming SAT solver (`ortools.sat.python.cp_model`). 项目 master / binding / routing 都用 CP-SAT
- **LBBD** — Logic-Based Benders Decomposition. master 出主决策 → sub-problem 验 (binding/routing/flow) → INFEASIBLE 出 nogood 回 master → master 加 cut. 项目核心 paradigm
- **master / binding / routing / flow** — 项目 4 层 solve 拓扑:
  - master — placement (各 instance 选 pose) + ghost rectangle
  - binding — port binding (每 port 出/入 connect 哪条带)
  - routing — grid routing (belts 怎么连)
  - flow — multi-commodity flow diagnostic (诊断 routing INFEASIBLE 时为啥)
- **outer search** — 枚举 (area, min_side) candidate 矩形, frontier-based, Phase 3A delivery
- **candidate** — outer search 一次 try 的 (area, min_side, anchor) 三元组. ~1000-10000 candidate / 168h
- **benders_loop** — `src/search/benders_loop.py` 的 LBBD 主循环. cut framework Phase 1.3 接进的 attach point
- **ghost rectangle** — 70×70 grid 中 candidate 选中的目标 max empty rect, master 必保留其内部空
- **pose** — 一个 facility instance 在 grid 上的具体 (位置, 方向, port mode). 项目 production data 81795 pose / 266 instance
- **anchor** — ghost rectangle 的锚定 cell (左下角 / 旋转中心 等, 视 family 定)
- **BSP** — `boundary_storage_port` (边界存储口 facility). production 134 BSP, sample 54 BSP
- **mfg_3x3 / mfg_5x5 / mfg_6x4** — manufacturing facility 尺寸变体 (3x3 / 5x5 / 6x4 grid cell)
- **power_pole** — 50 个 (exploratory cap 旧值, certified_exact 无 hard cap) 电力柱 facility
- **power_coverage** — power network 用 power_pole 覆盖各 facility 的几何 + topology constraint
- **commodity** — multi-commodity flow 中一个 (source, sink, demand) 三元组. F2/F4 cert 含 commodity_id, Phase 1.5 真接 data pipeline (§13.1)

### A.4 Paradigm 死路 (历史)

详 `paradigm_death_timeline_27_lever.md` (memory)

- **B1 (pose-bool master)** — L11 paradigm, 27×15 interior pose-bool 7.2s FEASIBLE 但 master.solve INFEASIBLE 不收敛. **L11-L16 ❌**
- **PCR-CUT (Patch-Certified Routing Conflict Core)** — Path 14, env-gated. Phase 0-4 GO, Phase 5 multi-anchor marginal. 详 §4.2
- **SAC-Hull** — Path 13, separator capacity. L2 工作但 binding/routing reject 不收敛. **❌** §4.3
- **RAB-SEP** — Path 12, routing abstraction binding-separator. cert tight 8/8 UNPROVEN. **❌**
- **D2 commodity flow / arc** — Path 17, Phase 2 multi-anchor. **❌** §4.4
- **cand C column generation** — Phase 1 4-ramp GO 但 master basis 真换后 reservation **superseded** by paradigm shift. §4.5
- **L01-L26 + L27 IHS / L26 Benders symm / L25 layout-invariant** — paradigm_death_timeline cite, **全 ❌**

### A.5 审查 / 工具

- **Gemini per-commit cross-check** — 每 commit 调 Gemini 3.1 pro 验 schema/spec/data gap. 详 §22.1
- **GPT pro batch audit** — 大节点打包 GPT pro 验 adversarial soundness. 详 §22.2
- **v1-v8 review package** — Phase 1.1 audit 累积包. v1-v7 cut-only 0.3 MB; v8 全项目 7z 6 MB
- **7z + zip 壳 + 7za binary** — 大 review pkg 压缩 strategy. 详 [[review-pkg-7z-strategy]]
- **audit armor** — GPT review prompt 三段式: 真瓶颈 + 死路黑名单/白名单 + 不可达必须形式化证明. 详 [[gpt-review-prompt-armor]]
- **adversarial soundness audit** — Step A-O 主战场. 5 验: cert 内 sound + cert↔literals + cert↔真数据 + cert↔state + cert↔不变量. 详 [[adversarial-soundness-audit]]
- **red fixture** — known-infeasibility 反例 .md, 在 `docs/research/.../red_fixtures/`. 5 个 F1-F5. 详 §21.3

### A.6 Data sources (`data/preprocessed/`)

- **canonical_rules.json** — 项目 SoT, 含 17 recipe + facility templates + targets + commodity types. 详 `rules/canonical_rules.json`
- **candidate_placements.json** — 全 pose 枚举 (instance, pose_idx, occupied_cells, ports, orientation, port_mode). Production 53 MB / 81795 pose; viewer sample ~273 pose
- **mandatory_exact_instances.json** — 266 必装 facility instance
- **generic_io_requirements.json** — commodity flow demand (per recipe / target)
- **all_facility_instances.json** — 全 facility instance 详 (含可选 deployment)

### A.7 项目 invariants / locks

- **PROJECT_LOCK §3A** — 数学 / 工程 invariant lock; cut framework 边界 (family mode XOR / 9 family frozen / cert+literals XOR geometric_payload / GHOST_AGNOSTIC sentinel / multiset eval slot anonymity / adversarial soundness). 改任一必先 PROJECT_LOCK 更新 + 跨 spec/src/test 同步. 详 §18
- **`certified_exact` vs `exploratory`** — 严格分离, 不混路径. exploratory artifacts 不算 certified proof; exploratory 的 `50 power pole + 10 storage box` cap 不进 certified_exact
- **postprocess-only** — `src/adapters/` / `src/render/` / `data/exports/` / `data/examples/` 不重定义 solve schema; 仅消费 certified proof
- **`max_lex(area, min_side)`** — 项目 objective; `min_side >= 6` 是 admissibility 不是 tie-break

### A.8 Phase 命名

- **Phase 3A** — productization, release `r20260416`, complete
- **Phase 3B** — full-scale exact proof, in progress (repair5 master 30→47 GB fits)
- **Phase 3C** — Linux migration + CachyOS 调优 + observability + 路线图 22 P0/P1/P2 项
- **Phase 0/1.0/1.1/1.2/1.3/1.5+** — B Design v2 phase 命名 (cut framework 内):
  - Phase 0 — B Design v2 spec + invariants frozen
  - Phase 1.0 — framework migration (Day 13-17)
  - Phase 1.1 — F1-F4 production validator + oracle + lifecycle + replay + Step A-O (**当前闭环**)
  - Phase 1.2 — F5-F9 5 family 加 + 入门 7 项 factual fix
  - Phase 1.3 — propagator 真接 master.AddLinear / step_8 apply_to_master / by_exterior_watcher / perf opt
  - Phase 1.5+ — production integration, commodity registry 真接 data pipeline


