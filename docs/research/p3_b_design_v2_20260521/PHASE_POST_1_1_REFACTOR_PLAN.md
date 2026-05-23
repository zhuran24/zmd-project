# Phase 1.1 闭环后重构计划

到 commit `c8fb7ef` (Step O) 为止 Phase 1.1 4 family (F1-F4) validator / oracle /
evaluator / lifecycle / replay / store 全部 sound 闭环, 通过 11 轮 GPT pro audit
+ 22 轮 Gemini cross-check + 15 步 Step A-O 修复. 这份文件不只列后面要做哪几
步, 也讲清楚: 为什么走到这里, 为什么选 cut framework 不选 B1/PCR-CUT 这类
27 lever 死路, 各段的 GO 标准是什么, 各 family/step 之间怎么依赖, 风险怎么
兜底. 让看到这份文件的人, 不只知道 "做什么", 还知道 "为什么这么做" + "做到
什么程度算 done" + "走偏怎么回头".

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

## 3. paradigm 决策 + 死路分析

为什么选 B Design v2 cut framework 不选别的. 27 lever 死路在 `paradigm_death_timeline_27_lever.md`
有完整 timeline, 这里只讲 cut framework 跟它们的边界关系.

### 3.1 vs B1 pose-bool master (L11)

B1 试图把 cut 表达成 master CP-SAT 内部 pose-bool var. master.solve 解不动
inherent — 加 cut 当 hard constraint 让 master 更大更慢. **Phase 6 path-1
master/binding port-selection 死, path-2 lazy demand cut 死**.

cut framework 走相反方向: cut 不进 master schema, 在 master 外 lazy attach.
master 看到的还是原 30 GB model, cut 经 propagator 在 search 过程动态 push.

### 3.2 vs PCR-CUT (Path 14)

PCR-CUT patch-belt routing 复用 SAC slack. Phase 0 GO + Phase 1 GO 单 anchor
21/21 INFEASIBLE, 但 **Phase 5 multi-anchor 8 anchor 0/8 CERTIFIED**. paradigm
单 anchor sound 多 anchor 不收敛.

cut framework F2 cutset 复用 PCR-CUT 的 patch belt min-cut 做单 cert 生成 (单
anchor sound 部分), 但不依赖 multi-anchor 跨 anchor 复用 — F2 cut 各自独立
进 store, 每 cut 自己 sound, 不要求一组 cut 跨 anchor 收敛.

### 3.3 vs SAC-Hull (Path 13)

SAC-Hull abstract routing layer + separator capacity. Phase 1 master static
hull 验过, Phase 2 dynamic separator 跑通, 但 **L2 工作 binding/routing reject —
"separator violation 减 80% 但 necessary ≠ sufficient"**.

cut framework 的 F4 component_reach 借鉴 SAC-Hull 的 separator 概念但不依赖
hull 充分性 — F4 separator 只作几何证明 (separator ⊆ owner ∪ ghost), 不当
sufficient INFEASIBLE 信号. 充分性靠 BFS exact recompute (cert.src/sink_component
== BFS, Step D land).

### 3.4 vs D2 commodity flow + arc (Path 17)

D2 把 commodity flow 当 master 内部 var. Phase 0 candidate D2 probe GO,
Phase 1 LBBD GO 单 anchor, **Phase 2 multi-anchor verdict NOT GO**.

cut framework 也用 commodity (F2/F4 都需 commodity registry), 但 commodity
是 BState.commodity_demands/routes registry, validator 时验 cert.commodity_id
存在 + src/sink 等 registry. 不当 master var, 不解 commodity flow LP.

### 3.5 vs cand C column generation

cand C Phase 0 GO (8/8) + Phase 1 GO (4-ramp 5/20/40/80 instance), 是真换
master basis 的 paradigm. 但单一 paradigm — 一个 column generation master 跑
全 problem, 跟 cut framework orthogonal.

cut framework + cand C 可叠加用: cand C 是 master 内部 column basis, cut
framework 是 master 外的 sound prune 层. Phase 1.5+ 真集成时考虑.

### 3.6 vs cdcl warmstart / IHS / Benders symmetry / etc

L01-L26 散布的 lever (25-27 等). 各有 verdict 死法. 详 `paradigm_death_timeline_27_lever.md`.

cut framework 跟它们的区别: cut framework 不是 paradigm shift (不替代 CP-SAT,
不换 master schema), 是 **paradigm extension** — 在 CP-SAT solve 过程中累积外部
sound 证据, paradigm-internal 跑不动的部分用 paradigm-external 知识补.

### 3.7 B Design v2 vs v1

B v1 在 Phase 0 早期 GHOST_AGNOSTIC dispatch 不严, exterior_blocks 不进 scope
hash. Gemini r21 catch — v1 cut 跨 ghost 复用时 exterior 变了但 cut 不
invalidate. v2 加 exterior_blocks_hash 跟 ghost_agnostic dispatch (round 21
fix), 跨 candidate 复用 sound.

`cut_lifecycle_v2.md v3.2.2` 是当前 spec 版本. 不再回退到 v1.

### 3.8 跟 Phase 3B 的衔接

Phase 3B repair5 (commit 落地 7eb6e7f 那波) 是 master oracle 改 30 GB → 47 GB,
让 master 真 fit i9-13900KS + 47 GB. 这是 cut framework 跑得起来的前提 —
master 跑不起来 cut 也没意义.

Phase 1.3 P1.21 真集成时 cut framework wire 到 benders_loop 内 (`src/search/
benders_loop.py`), env flag `EXACT_B_DESIGN_V2=1` 切新框架. 不动 Phase 3A
outer_search 跟 Phase 3B 的 master/binding/routing/flow 现有架构.

---

## 4. 历史回顾 — 怎么走到 Step O

不是天降一份 4 family validator. 是 22+ commit + 11 GPT pro audit + 22
Gemini round 一轮轮调过来的. 看完这段知道为啥某些 invariant 这样设计, 为啥
某些 fix 反复在同一函数加.

### 4.1 Phase 0 (B Design v2 spec + invariants)

22 commit + 26 round Gemini cross-check. 锁定:
- 9 family final list (无 symmetry_lift — round 18 decide)
- cut_lifecycle_v2 v3.2.2 (round 21 exterior_blocks_hash 加)
- 5 fixture frozen (red_fixtures/)
- 8 invariant frozen (PROJECT_LOCK §3A)
- 10 exit criterion (PHASE_1_PLAN.md)

Gemini r26 GO, 不再 Phase 0 layer cross-check. Step 跨 Phase 0 → 1.0.

### 4.2 Phase 1.0 (framework migration)

P1.1 carry PoC b_core_lifecycle_poc.py 14/14 PASS 到 production
`src/cuts/lifecycle.py`. 9 step + Cut/CutScope/BState schema + 6-dim watcher
+ replay store. F1 region_capacity 作 framework reference (其他 F2-F9 stub).

### 4.3 Phase 1.1 P1.5-P1.8 (F1-F4 production validator + oracle)

每 family 实施: validator + evaluator + oracle (F2-F4 oracle stub). F1 P(g)⊆R
strict / F2 partition / F3 cert↔literal / F4 BFS component 各自 spec land
(cut_family_specs/01-04.md).

Gemini r27-29 三轮 cross-check, r29 GO. 但 GO 后立刻 r30 catch 5 critical
gap — 全因 prompt mode 只验 spec↔src 没 push spec↔data (`[[gemini-prompt-audit-mode]]`).

### 4.4 Phase 1.1 Gap fixing (r30-r32)

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

### 4.5 GPT pro round 1+2 (Phase 1.1 v1 audit)

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

### 4.6 GPT pro v2 audit + Step I/J/K (bdaa303)

v2 r1+r2 catch 3 新 P0:
- I `step_7_evaluate_cut` 接 family dispatch (Step F family 函数永远 bypass)
- J F3 blocking_slot → selected_poses[slot] → blocking_pose_id 真绑定
- K F4 separator_cells in-grid + ∈ owner∪ghost 显式验

### 4.7 GPT pro v3 audit + Step L (a38620c)

v3 catch F1 duplicate `contributing_groups` P0: cert 同 group 重复列让
demand_R 双算. Step L 加 seen_gids 去重 + tuple demand 真等 + gap consistency.
顺手清 ruff F401 12 个 (但因 ruff.toml ignore 没真清, Step M 才真清).

### 4.8 GPT pro v4 audit + Step M (273fbff)

v4 r1+r2 catch 3 新 critical:
- M.1 `replay_cut(canonical_rules=None)` silent ATTACH 绕 validator → fail-closed
  (state.canonical_rules fallback → 没就 HOLD)
- M.2 F2 commodity_demand 无 source-of-truth registry → BState 加
  commodity_demands 字段, validator require
- M.3 F4 commodity_id pass-through → BState 加 commodity_routes 字段,
  validator require registry route src/sink == cert
- ruff F401 force-fix 真清

### 4.9 GPT pro v5 audit + Step N (afef8f1)

v5 r1+r2 catch 2 新 P0:
- N.1 F2 commodity registry 仍不 sound — duplicate contributing + same-side
  route 不跨 partition 全允过 → contributing 去重 + commodity_routes require +
  cross-partition route check
- N.2 `CutStore.add_cut` 直接 active 注册 silent attach window → default
  `initial_state="held"`, caller (replay 成功) 必显式 reactivate

### 4.10 GPT pro v6 audit + Step O (c8fb7ef)

v6 r1+r2 catch 3 新 P0, 同一 ghost lifecycle 漏口两端:
- O.1 (round 2) validator 不验 `scope.ghost_rect_id == GHOST_AGNOSTIC` 合法性
  → F1 验 `ghost ∩ R == ∅`, F2/F4 直接 reject GHOST_AGNOSTIC
- O.2 (round 1) `on_ghost_rect_changed` accept scope-only replay_fn 绕 family
  validator → `replay_fn` 改 Optional, default lazy import `replay_cut` 走
  full gate
- O.3 (round 1) add_cut 非法 `initial_state` raise 后 cut 残留 store →
  validate 移到所有 mutation 前

### 4.11 累积现状 (Step O 结束)

- 14 commit src/ 改动 (Step A-O)
- 5 commit infra (build script v2-v7)
- 11 GPT pro audit (v1 r1/r2 + v2 r1/r2 + v3 + v4 r1/r2 + v5 r1/r2 + v6 r1/r2)
- 22 Gemini round (r14-r35)
- 172 cuts test (从 v1 包的 139 累计 +33 regression)
- 8 高位 invariant 全 close (没 unsolved P0)

---

## 5. 现状细则 (commit `c8fb7ef` 起算)

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

## 6. 默认 skip 的方向 (历史死路 baseline)

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

## 7. GO 标准 / 验收准则

每段 done 怎么定义. 不只 "代码改完 commit pass test", 而是要过 reviewer audit.

### 7.1 Phase 1.2 P1.11 入门 GO

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

### 7.2 Phase 1.2 P1.11-P1.15 (F5-F9 实施) GO

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

### 7.3 Phase 1.3 P1.21 (CP-SAT propagator 集成) GO

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

### 7.4 Phase 1.5+ (production integration) GO

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

## 8. 依赖图 — family / step / phase 之间怎么 chain

各段不是平行做的. 错顺序就走死路.

### 8.1 Family 内部 dependency

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
   └─ ghost_rect tuple 语义 lock (§7.1 Phase 1.2 入门必先)

F9 density_envelope
   └─ F6 跟 F9 都 region-density 约束, F6 land 后 F9 复用 region helper
```

### 8.2 Phase 间 dependency

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

### 8.3 关键 ordering decision

- **source_digest 真 hash 必先** (Phase 1.2 §7.1 §3) — 不然 Phase 1.3 production
  data 轮换识别不出, cross-session cert replay 不可信
- **ghost_rect tuple 语义 lock 必先 F8** — F8 实施前不 lock 会让 Liang-Barsky
  跟 ghost_rect 横竖反
- **strict gate default ON 必先 F5-F9** — 新 family 漏 register 时 silent
  attach
- **BState production builder 必先 Phase 1.5+** — 真生产 inject 各 family
  validator 需要的字段, 不统一 builder 会让一处漏 inject 拖崩全 framework

### 8.4 跨 phase invariant

Phase 1.2 / 1.3 / 1.5+ 全 share 这些 invariant (PROJECT_LOCK §3A):
- 9 family list 不变 (不加 / 不删 / 不改 mode)
- cut schema 字段 invariant (cut.scope + cert + literals XOR geometric_payload)
- multiset eval slot anonymity (state_machine §5)
- adversarial soundness (validator trust boundary, oracle 不可信)

任一 phase 想改 invariant 必先 PROJECT_LOCK 更新 + spec/src/test 跨同步.

---

## 9. Phase 1.2 P1.11 入门 (低风险 factual 收尾)

进 F5-F9 实施前必清这几项. 全是 schema / spec / static hygiene, 不动 paradigm.
GO 标准见 §7.1.

### 9.1 strict registration gate default ON
- 文件: `src/cuts/replay.py:122`
- 改: `EXACT_FAMILY_VALIDATOR_STRICT` default `"0"` → `"1"`
- 影响: 未注册 family 进 replay → `NotImplementedError` 不 silent attach
- F1-F4 已注册, 切换不影响当前
- F5-F9 实施时每加 1 个必 register, 测试覆盖
- **风险**: 若任何调用方依赖默认非 strict (e.g. 半实施 fixture), 切换会破.
  mitigation: grep 现 codebase 看 strict env 使用; 切换前 dev env 显式
  `EXACT_FAMILY_VALIDATOR_STRICT=0` override

### 9.2 spec docs align (必修 #7)
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

### 9.3 source_digest 真 hash
- 当前 `lifecycle.py:635-637` + `oracles/region_capacity_oracle.py:179-186`
  写死 `"poc_source_digest"`
- 改: hash `canonical_rules.json + candidate_placements.json + mandatory_exact_instances.json
  + generic_io_requirements.json + oracle_versions` 内容
- spec 已 require: `cut_lifecycle_v2.md:881-903 / 80-86 / 146-154`
- 不修则 replay 不能识别 data source 轮换, 跨 session cert 可信度差
- **风险**: hash 函数选错 (e.g. mtime instead of content) 导致 cert 跨 session
  失效. mitigation: 内容 sha256, 不用 mtime

### 9.4 ghost_rect tuple 语义 lock
- 当前 `lifecycle.py:216` 注释 `(x, y, h, w)`, `helpers/ghost_geometry.py:108-116`
  返回 `(x, y, x+h, y+w)` — h/w 跟常规 (x+w, y+h) 反
- F8 power_grid_reach 实施前必锁:
  - 写明 schema: `(x, y, height, width)` 或改 object `{"x", "y", "height", "width"}`
  - 加非方形 fixture, e.g. `(10, 20, 3, 7)` verify AABB
- 否则 F8 接真 ghost_rect 时横竖反
- **风险**: 改 object schema 影响多处 helper + 测试; 改名 `x_span/y_span`
  减名 confusion 但仍是 tuple. mitigation: 倾向 object schema, 一次性改清

### 9.5 mypy strict 收尾
- 37 errors / 10 files, 主要泛型缺参 + Any return + unused ignore
- 重点收: `lifecycle.py` (`BState`) + `replay.py` + 4 family validator
- 让 schema 类型契约真在 type system 内 enforce
- **风险**: 收 strict 时改 type signature 影响 callers. mitigation: 小步 commit
  每次改 1 file mypy clean

### 9.6 拆 validator helper (radon D 级降)
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

### 9.7 evaluate_literal_port_exposure 决定
- vulture 标 unused (走 generic `evaluate_literal_multiset`)
- 选项 a: 删 (统一 generic path)
- 选项 b: 接进 `step_7_evaluate_cut` literal dispatch 作 F3 specific evaluator
- 倾向 a (factual simpler, sound 不变), Phase 1.2 入门一行决定

---

## 10. Phase 1.2 P1.11-P1.15 实施 (5 new family)

入门完后进 5 family 实施. 每 family 单独 commit (≥ 5 commit), 跟 Phase 1.1
同样 cross-check rhythm. GO 标准见 §7.2.

### 10.1 P1.11 F5 pattern_nogood
- 用途: literal-based cut, 拒已知 unsat 状态. lifecycle step 2 minimize 入口
- 实施: `src/cuts/families/pattern_nogood.py` (validator + evaluator) +
  `src/cuts/oracles/pattern_nogood_oracle.py` (从 master infeasible witness 提)
- 复用: L16 `core_minimizer.py` deletion / QuickXplain helper
- spec: `cut_family_specs/05_pattern_nogood.md`
- **风险**: deletion+QuickXplain perf 是 NP-hard. mitigation: 限 ≤ N literal,
  超 N 不 minimize 直接 emit 原 cut

### 10.2 P1.12 F6 shape_packing_hall
- 用途: geometric cut, Hall's marriage theorem 推 region 内 pose 数下界
- 实施: validator (cert.required_count vs region.available_slots) + oracle
  (greedy bipartite match)
- 复用: F1 region helper (region_cells / capacity)
- spec: `cut_family_specs/06_shape_packing_hall.md`
- **风险**: Hall theorem 实施复杂. mitigation: 先 greedy 后 LP

### 10.3 P1.13 F7 power_hitting_set
- 用途: literal-based cut, 必选 power pole set
- 实施: hitting-set greedy minimize + multiset evaluate (复用 F3 path)
- 复用: F3 generic literal evaluator
- spec: `cut_family_specs/07_power_hitting_set.md`
- **风险**: hitting-set NP-hard. mitigation: LP relax 找近似 hitting set,
  validator 验 set 真覆盖

### 10.4 P1.14 F8 power_grid_reach
- 用途: geometric cut, Liang-Barsky AABB + BFS 电网可达
- 实施: `helpers/ghost_geometry.py` 已有 Liang-Barsky helper, 复用
- 前置: ghost_rect tuple 语义必先 lock (§9.4)
- 复用: F4 BFS helper
- spec: `cut_family_specs/08_power_grid_reach.md`
- **风险**: ghost_rect tuple 横竖反 bug. mitigation: §9.4 lock spec + 非方形
  fixture 必先

### 10.5 P1.15 F9 density_envelope
- 用途: geometric cut, region density 上界 (单位 cell pose count)
- 实施: validator (cert.density vs region.area × max_density) + oracle
- 复用: F6 region density helper
- spec: `cut_family_specs/09_density_envelope.md`
- **风险**: 数学 sound 边界 (max_density 怎么算). mitigation: 加 negative test
  覆盖 density 临界

### 10.6 P1.15+ test fixture 补全
- F3 direction E / W synthetic fixture (真数据只 N=273 S=257, E=W=0)
- F8 直接复用 E / W fixture
- ghost_rect 非方形 fixture
- F5-F9 各 family 7-10 test (sound case + ≥ 3 attack 反例 + schema_err +
  adversarial scope)

---

## 11. Phase 1.3 P1.21 (CP-SAT propagator 真集成)

F5-F9 落地后, evaluator 才进真 hot path (10K calls/sec). 这阶段 perf opt
必要. GO 标准见 §7.3.

### 11.1 step_8_apply_to_master 实施
- 当前 `lifecycle.py:743-751` NotImplementedError
- 接 `benders_loop` hook (env flag `EXACT_B_DESIGN_V2=1` 切新框架)
- Lazy → hard constraint 转化, 跟 master CP-SAT model 真集成
- **风险**: master 加 lazy constraint 可能影响 master.solve 收敛 (constraint
  push 太多导致 propagator overhead). mitigation: 阶梯式启用, 先 F1 single
  family 跑通后逐步 F2-F9 wire

### 11.2 evaluate hot path perf opt
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

### 11.3 by_exterior_watcher 实施
- GPT v3 Gemini r35 P0, Step H 暂 defer (sound 不需要, evaluate 重算保 — Step F)
- Phase 1.3 lazy → hard constraint 后, evaluator 不再被自动调, watcher 必必
- 实施: `CutStore` 加 `by_exterior_watcher: Dict[Cell, Set[CutId]]`, 跟
  exterior_blocks 变化时 trigger affected cut re-replay
- F1 GHOST_AGNOSTIC cut 注册到此 watcher
- **风险**: watcher 跟 ghost_watcher 重复 invalidate 浪费. mitigation: cut 只
  入一个 watcher (GHOST_AGNOSTIC → exterior_watcher, else → ghost_watcher)

### 11.4 propagator thread-safe 评估
- 当前 `lru_cache(256)` multiprocess.spawn 各 worker 一份, 不共享
- Phase 1.3 propagator 如果 master CP-SAT 内部多线程 callback, lru_cache 是
  thread-safe (GIL + functools 实施) 但 cache pollution 跨决策回溯仍要 verify
- HR1 thread-safe 是 Phase 1.3 评估项
- **风险**: multi-thread propagator callback 跨 worker 共享 store. mitigation:
  现 CP-SAT propagator 是单线程 callback, Phase 1.3 直接验; 多线程时再加 lock

---

## 12. Phase 1.5+ (production integration)

Phase 1.3 framework 跑通后接真生产 data + 真 oracle. GO 标准见 §7.4.

### 12.1 commodity registry production inject
- 当前 `BState.commodity_demands` / `commodity_routes` Phase 1.1 mock 注入
- Phase 1.5+ 真 inject 路径: 从 `data/preprocessed/commodity_demands.json` +
  routing planner output + master_solution.commodities 真 build
- 设计 `build_bstate_from_production_inputs()` 统一入口, 覆盖:
  - canonical_rules + facility_templates
  - mandatory_exact_instances + instance_to_facility_type
  - candidate_placements
  - commodity demand / routes (从 production data)
  - source_digest 真 hash

### 12.2 registry schema 评估 (route_id vs commodity_id)
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

### 12.3 各 family oracle 真实施
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

### 12.4 F3 active_port_witness verify
- spec `03_port_exposure.md:144-147` 要求 verify `active_port_witness_b64`
- 当前 validator 没查 (Phase 1.1 v1.0 假设 "all listed ports active")
- Phase 1.5+ 真 production data 时可能有 port 被 boundary_constraints LP
  disable, 必加 witness 验

### 12.5 F2 max_flow_LP algebraic witness
- spec `02_cutset.md:156-159` 要求 verify max-flow LP dual
- 当前 defer Phase 1.5+
- 接真 commodity routes + LP solver 后实施

---

## 13. 风险评估 + mitigation

defer / 已知 risk + 失败回滚策略.

### 13.1 GPT pro v5 verdict 排序 (最先爆 → 后)

1. **source_digest placeholder** — Phase 1.2 §9.3 必修
   - mitigation: hash 真 file content + replay 时验证 + cross-session test
   - rollback: 退到 placeholder, production 不 ship

2. **strict default 0** — Phase 1.2 §9.1 必修
   - mitigation: F5-F9 实施每加 1 family 加 register + missing-validator test
   - rollback: env override 显式 strict=0 (dev only)

3. **F2 commodity_demand registry** — Step M+N 已 partial close
   - mitigation: registry schema 评估 (Phase 1.5+ §12.2)
   - rollback: 暂时 F2 oracle stub 不 emit

4. **HR5 GHOST_AGNOSTIC exterior_blocks invalidate watcher** — Phase 1.3 §11.3
   - mitigation: Step F evaluate 重算保 sound, watcher 是 efficiency
   - rollback: Phase 1.3 没 propagator 集成时不需要

5. **HR1 thread-safe** — Phase 1.3+ §11.4 评估
   - mitigation: 现 CP-SAT propagator 单线程
   - rollback: multi-thread 时 cache invalidate 跨 worker

6. **HR3 free-placement / HR4 non-rect ghost** — Phase 1.5+ 真生产 data
   pattern 出现时再决策

### 13.2 Phase 1.2/1.3 实施风险

- **F5 deletion+QuickXplain perf**: NP-hard. mitigation 限 ≤ N literal
- **F6 Hall theorem 实施复杂**: mitigation 先 greedy 后 LP
- **F7 power hitting-set NP-hard**: mitigation LP relax 近似
- **F8 ghost_rect tuple 反惯例 bug**: mitigation Phase 1.2 §9.4 lock 必先
- **F9 density sound 边界**: mitigation 加 negative test
- **Phase 1.3 lazy → hard constraint master 性能**: mitigation 阶梯启用 (F1
  单 family 跑通后 F2-F9)
- **propagator hot path perf**: mitigation parsed cert cache + incremental
  BFS + watcher 三件套 (Step H TODO)

### 13.3 全 phase 通用回滚策略

- 任 phase 通不过 GO 标准 → 不推下一 phase, 单独 debug commit
- 每 Step (A-O 跟未来 P+) commit 独立, git revert 单 step 不影响其他
- Audit verdict NOT GO 不 archive 假数据, reproduce verify 真才 commit
  ([[audit-verify-before-archive]])
- 大节点 (Phase 1.2 入门 / Phase 1.2 5 family / Phase 1.3) audit 不通过 →
  打包 next round, 不强推

---

## 14. 实施 rhythm (Phase 1.1 经验)

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

## 15. 排期估算 (Claude pace, 不按人类工程师)

per `[[work-time-estimates]]` Claude 节奏估:

- Phase 1.2 §9 入门 7 项 — 单步 30-60 min Claude, 累计 ~5-7 commit, ~3-4 小时
- Phase 1.2 §10 5 family 实施 — 每 family ~1-2 commit + Gemini cross-check,
  累计 ~10-15 commit, ~6-10 小时 Claude work
- Phase 1.3 §11 propagator 集成 + perf opt — paradigm work, ~10-20 小时 Claude
  + master CP-SAT 真集成 wall-clock 死时间 (build / 测时间不可压)
- Phase 1.5+ §12 production integration — 跟真生产 data schema 设计耦合, 估
  随 Phase 1.5 data pipeline 进度

实际 wall-clock 主要消耗在 168h campaign 长跑 (cut framework 修改不直接影响
campaign 时间), 不在 Claude implementation 时间.

---

## 16. Open questions (待定)

1. Phase 1.5+ commodity registry schema (commodity_id vs route_id 级别) 何时
   决策? — Phase 1.5 真生产 data pipeline 设计时
2. F2 patch_routing_core 复用是否真 sound (paradigm 死在 multi-anchor 收敛,
   单 cut 生成仍 OK)? — Phase 1.5+ F2 oracle 实施时复 verify
3. evaluate_literal_port_exposure 删 vs 接进 dispatch — Phase 1.2 §9.7 一行决定
4. ghost_rect tuple 改 object schema vs 保留 tuple + 明确文档 — Phase 1.2 §9.4
   F8 实施前
5. Phase 1.3 propagator integration 跟 Phase 3B repair5 master 兼容性 — Phase 1.3
   §11.1 实施时验
6. F5 minimize NP-hard 超时阈值 — Phase 1.2 §10.1 实施时定

---

## 17. PROJECT_LOCK §3A 边界

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
