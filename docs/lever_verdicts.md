# Lever Verdicts — 提升 master FEASIBLE 率的所有路线及结果

**最后更新**: 2026-05-17 (B1 Phase 0 verdict ✅)

主线问题: 70×70 grid + 266 mandatory facility + ghost rect 几何约束的 `max_lex(area, min_side)` 严格证明.

baseline (workers=8, master_seconds=1800, default profile, 无 hint) 14h 跑 51-78 candidates, **0 FEASIBLE**. 全部 UNKNOWN 或 INFEASIBLE. 此文档记录所有尝试过的"破 0 FEASIBLE" lever 路线及实测 verdict.

---

## 主线 lever (按时间顺序)

### L1. RAM 优化路径

**假设**: master.solve 解不动是因为 30 GB RAM 把 CP-SAT 内部搜索压制, 减 RAM 应该 unlock 搜索深度.

**实验** (2026-05-15 整 session):
- `EXACT_MASTER_CP_SAT_WORKERS` 从 8 减到 1, 验证 RAM 30 GB → 12.78 GiB (-57%)
- spike#5/#6/#7 实测 workers=1/2/4/8 对应 RAM peak 12.78 / 16.4 / 20.44 / 30 GiB
- 解锁 `-p 2 + workers=1` 双 outer 并行 (32 GB fit 47 GB hardware)
- 14h trial 验证 (workers=1, -p 2)

**结果**: 51 candidate **全 UNKNOWN, 0 FEASIBLE**. 跟 baseline (workers=8, -p 1) 27 candidate 0 FEASIBLE 表现一致.

**Verdict**: ❌ **RAM 不是 lever**. 减 RAM -57% 但 FEASIBLE 数 0 → 0.

**链**: [[project_2026_05_15_ram_session_misdirected]], [[project_30gb_real_culprit_power_coverage]]

---

### L2. HiGHS / LP-MIP 重写

**假设**: CP-SAT 对 dense linear constraint 不高效, 换 HiGHS (LP solver) 应该减 RAM + 加速.

**实验** (2026-05-15):
- Phase 1: minimum model translator (无 power_coverage)
- Phase 3: 加 power_coverage 后真实跑

**结果**:
- Phase 1: RSS 39 → 8 GB (-79%) — 假 win (没 power)
- Phase 3 (含 power_coverage): 42 GB > OR-Tools 30 GB — 真败
- LP-MIP 对 dense linear (power coverage 是 dense) 不适合

**Verdict**: ❌ **重写死路**. 单机 48 GB + 准确性必保 + LP-MIP solver 物理不可达 -50% 决定性收益.

**链**: [[project_highs_rewrite_blocker]], [[project_rewrite_path_exhausted]]

---

### L3. Master model 局部优化 (一堆 spike)

**假设**: model size 是 lever, 减 model 应该减 propagation 工作.

**实验**:
- `ghost_anchor_filter` env-gated (#68-#70 #84): tight pole_slot upper bound 763 → ~100, -80% search space
- cover_lit aggregate (#77): KILL, wrong source path
- family_lit lazy materialize (#78)
- clause_cleanup_period / no_overlap_2d_boolean / presolve_extract_int (#75 第 3 批 spike)
- 一堆 CP-SAT 参数 env hook (TABLE_COMPRESSION_LEVEL / LINEAR_SPLIT_SIZE / etc)
- master build inspector dump real cover_literals + slot count (#83)
- 第 3 批 subagent 并行调研 param/constraint-reduce/CG/heuristic-cost (#76)

**结果**: 减了 build 阶段 RAM 少量 (build phase 3.10 GB), 但 **solve peak 30 GB 真大头是 worker propagation buffer, 不是 model size**. memray 验证 (#71). model size 优化只减 ≤15%.

**Verdict**: ❌ **model size 优化对 propagation buffer 几乎无影响**, marginal gains, 不破 0 FEASIBLE.

---

### L4. EXACT_POWER_PLACEMENT_SUBPROBLEM 重开 (#80)

**假设**: 这个 sub-problem 当前关闭 = certified path; 重开调研看是否能加进 certified 路径.

**实验**: subagent 调研.

**结果**: PROJECT_LOCK 明确禁止 — 这个 flag = exploratory only, production gate hard block.

**Verdict**: ❌ **不允许**, certified path 守卫 hard block.

---

### L5. OR-Tools git HEAD 未发布 fixes + 9.16 ETA (#81)

**假设**: OR-Tools 9.16 可能修了 9.15 的性能 bug.

**实验**: subagent 调研 OR-Tools git log + 9.16 release notes.

**结果**: 9.16 没明显性能改进, ETA 不明.

**Verdict**: ❌ **不值得等**.

---

### L6. AI sidecar 加速 (#82)

**假设**: shadow AI 模型预测可行 candidate 或给 master 智能 hint.

**实验**: subagent 调研, 给完整集成实操路径.

**结果**: 工作量大 (训数据 + 部署 + 边界 enforcement), 收益不确定. PROJECT_LOCK 有 AI safety contract 限制 (only shadow, no proof source, no formal pruning).

**Verdict**: 🟡 **暂搁置 long-term**, 不在当前主线.

---

### L7. Community blueprint hint 注入 (D step 2, #39-#40)

**假设**: 用户手调 IP v2 blueprint 给 master 当 hint, master 跳过早期 search 直接验证用户答案.

**实验** (2026-05-16):
- `scripts/blueprint_to_master_hint.py` 转换 blueprint 226 facility → 项目 225 instance_id + pose_idx
- env `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH` 注入 benders_loop._run_certified_exact
- 10 hand-verified sample 写 pytest, 9 edge case 写 pytest
- telemetry 验证: 266 instance × 3 (x/y/mode) = 798 AddHint 一次不多一次不少

**结果** (5 candidate trial3 + trial4):

| candidate | 备注 | 结果 |
|---|---|---|
| 35×14 | | UNKNOWN |
| 33×15 | | UNKNOWN |
| 31×16 | | UNKNOWN |
| **27×15** | **blueprint natural max empty rect 15×27 旋转, 完美匹配** | **UNKNOWN** |
| 24×17 | | UNKNOWN |

**Verdict**: ❌ **hint 单独不是 lever**. integration 完美工作 (telemetry 验证), 但 master 即使拿到正确答案也来不及在 master_seconds 内验证完.

**链**: [[project_d_step2_hint_landed]], commits 8395a27..6828a88, ef94fea

---

### L8. 换 master search profile (今天 D 路径, trial5)

**假设**: 项目内 3 个 profile (default `guided_branching_v4` / `ghost_first_v1` / `ghost_after_counts_v1`), 换 profile 可能突破 search deadlock.

**实验**: trial5 用 `exact_coordinate_ghost_first_v1` 跑同样 candidate.

**结果**:

| candidate | trial4 (default profile) | trial5 (ghost_first_v1) |
|---|---|---|
| 27×15 | UNKNOWN | UNKNOWN |
| 24×17 | UNKNOWN | UNKNOWN |

**Verdict**: ❌ **profile 切换不影响**, 结果完全一致.

---

### L9. Objective relaxation (C 路径, 假设错了)

**假设**: 把 `max_lex` objective 关掉, 让 master 只找 any FEASIBLE (找任意可行比找最优快).

**实验**: 读 src/models/exact_coordinate_master.py + master_model.py 源码.

**结果**: master 内部**本来就没 objective**. `max_lex(area, min_side)` 是 OUTER 循环驱动 — 外层按面积降序枚举 candidates 一个个问 master "能塞下吗?", master 本来就是纯 feasibility solver.

**Verdict**: ❌ **不适用, 假设错了**. 没东西可 relax.

---

### L10. 加长 master_seconds + 完整 worker 满载 (今天 A 路径, trial7)

**假设**: 给 CP-SAT 更多时间 + 全 8 P-core 满载, 能探完关键支路.

**实验** (2026-05-16):
- trial6: master_seconds=3600 + workers=1 (错配 — workers=1 是 RAM 优化遗留, A 路径无意义), 已停
- trial7: master_seconds=3600 + workers=8 + 27×15 (blueprint exact match)
- 实测: 60 min wall clock, 8 P-core 满载 (758% CPU 持续), CP-SAT 内部 max_time_in_seconds 实际 soft, overshoot 30s+

**结果** (trial7 telemetry):

```
solve_attempt_count: 1
hinted_instances_sum: 266 (全 mandatory hinted)
master_hinted_literals_sum: 798 (= 266 × 3, 整链零损耗)
status_counts: {UNKNOWN: 1}
27×15: UNKNOWN
```

**完整 27×15 数据矩阵 (同一 candidate 4 种配置)**:

| trial | master_seconds | workers | profile | 结果 |
|---|---|---|---|---|
| trial4 | 600 (10min) | 1 | default | UNKNOWN |
| trial5 | 600 (10min) | 1 | ghost_first_v1 | UNKNOWN |
| trial7 | **3600 (1h+实际)** | **8 满载** | default | UNKNOWN |

**Verdict**: ❌ **加资源不破局**. 3 种 axis (时间 ×6, worker ×8, profile 切换) 全 saturation, master 对 27×15 inherent 难解, 不是参数问题.

---

### L11. Hard constraint (B 路径, **未试**)

**假设**: 把 blueprint 当强制约束钉死 225 个 facility, master 只解剩下 41 个 mandatory + ghost rect. 搜索空间从 266 维断崖式降到 41 维, 大概率 1-2 min 出 FEASIBLE.

**实验**: 未试.

**代价**: 项目原本承诺"全局最优". 用 B 只能证"blueprint 摆法下的最优", 不能证"换种摆法是否能比 blueprint 留更大空矩形". 牺牲 certified path 全局严格性.

**实用价值**: 用户已认可 blueprint, 没人手算出更好的, 实用层面让步基本无影响.

**Verdict**: 🟡 **未试, 后备方案**. 当前唯一**几乎保证出 FEASIBLE** 的路径.

---

### L12. Ghost-anchor slicing (GPT-5.5 Pro v8 方案, 2026-05-16 实测)

**假设**: master 一次性展开所有 ghost anchor (2464 个 for 27×15) 导致搜索树先在 anchor-choice 这层撑开. 改成每次只锁单个 anchor (用 `EXACT_MASTER_GHOST_ANCHOR_FILTER=x,y`) 走原 LBBD 流程, 等价于 `feasible ⟺ ∃a: slice(a) feasible`. PROJECT_LOCK 兼容 + fail-closed.

**实验** (worktree `zmd_v8_test`, GPT v8 patch clean apply + 全套 pytest 2211 pass):

| 指标 | 结果 |
|---|---|
| Patch apply | clean (无 hunk fuzz) |
| Pytest 全套 | 2211 passed / 60 skipped / 0 failed |
| Build wall (full → slice) | 53.7s → 4.5s (**-92%**) |
| Proto vars 减幅 | -13% |
| Proto cons 减幅 | -32% |
| Build RAM 减幅 | -23% |
| 单 anchor solve (5 min cap) | UNKNOWN, 5.5M branches, 8 亿 propagation, 0 FEASIBLE |
| `mandatory_pose_literal_count` (post-slice) | 3,853,132 (跟 full overlay 一致) |

详细数据归档: `docs/research/v8_anchor_slicing_smoke_20260516/`

**根因**: 锁 ghost anchor 后 master 仍有 385 万 mandatory pose literal. **搜索难度的主体来自 266 个 facility 几何摆放, 不是 ghost anchor choice**. 锁 anchor 只剪掉搜索树最外层一层, 底下 facility placement 层没动.

**Path 计算**:
- "早命中" 策略: 单 anchor 5 分钟没结论, 后续 2463 个 anchor 没机会跑 ❌
- "完整 partition" 策略: 单 anchor 5 min × 2464 = **205 小时**, 物理不可行 ❌
- "锁 anchor 加速单 slice" 策略: 单 slice 5 min UNKNOWN 跟原 master 1h UNKNOWN 同 quality ❌

**跟 GPT v3 错估对比**: 同源 — 都是 build 加速漂亮 (v3 沙盒看 build 慢, v8 看 anchor choice 撑开), 但 solve 没改善. GPT 没量 solve 阶段. **build 改善 ≠ solve 改善** 的错估重演.

**Verdict**: ❌ **死路**. Build wall -92% 真实, 但不破 0 FEASIBLE. 工程上比 v3 干净 (fail-closed + PROJECT_LOCK 兼容), ROI 仍为负. v8 改动留在 worktree + patch 归档, 不进 main src.

**链**: [[project_v8_anchor_slicing_dead]]

---

### L13. Witness-only mandatory-placement preflight (GPT v10 方案, 2026-05-16 实测)

**假设**: v9 verdict 已确认搜索瓶颈在 mandatory facility placement (385万 pose), 不在 ghost anchor 外层. 因此用 complete mandatory hint **collapse** mandatory placement search tree — clone master, 固定 266 mandatory slot 的 x/y/mode + 1 个 compatible ghost anchor, residual optional 自由, 让 CP-SAT 找 positive witness. fail-closed: clone 不 FEASIBLE 不证 parent INFEASIBLE, 回退 normal master.

**实验** (worktree `zmd_v10_test`, GPT v10 patch clean apply + 全套 pytest 2212 pass):

| 指标 | 结果 |
|---|---|
| Patch apply | clean |
| Pytest 全套 | 2212 passed / 60 skipped / 0 failed |
| Patch size | 1013 行 (+782/-39), 7 文件改动 |
| Smoke (`MAX_ANCHORS=32`, 30s budget) | preflight 0 秒 fail-closed |
| `compatible_anchor_count` | **0/2464** |
| `mandatory_hint_occupied_cell_count` | 3122 (棋盘 64%) |
| `anchor_attempt_count` | 0 (没跑一次 forced clone solve) |
| `reason` | `no_compatible_ghost_anchor` |
| Fallback normal master | 5 min UNKNOWN, 5.57M branches, 8 亿 propagation |

详细数据归档: `docs/research/v10_witness_preflight_smoke_20260516/`

**根因 (前提错估)**: v10 假设 "complete 266-facility witness 跟 blueprint align". 实际:
- 用户 community blueprint 只有 225 mandatory, 缺 41 个
- Greedy heuristic 填充的 41 个跟 blueprint 留空 27×15 区域冲突
- Merge 后 266 facility 占 3122 格, 任何 27×15 ghost anchor 都跟这 3122 格 overlap

**Candidate-size 依赖**: greedy hint 下 compatible anchor 数随 candidate area 递减:

| Ghost rect | Compatible / Total | 比例 |
|---|---|---|
| 8×8 | 611 / 3969 | 15.4% |
| 10×10 | 469 / 3721 | 12.6% |
| 15×15 | 149 / 3136 | 4.8% |
| 20×15 | 0 / 2856 | **0.0%** |
| 27×15 | 0 / 2464 | **0.0%** |

**v10 preflight 在小 candidate 上能 trigger, 在 area ≥300 的大 candidate (项目真目标) 上永远 0**.

**跟 v8/v3 错估区分**:
- v3 / v8 = **算法错估** (关注 build / 关注 anchor choice, 但真瓶颈在 solve / facility placement)
- v10 = **前提错估 + data 不匹配** (算法本身 sound, 但要求 complete witness; 我们没 complete blueprint witness)

v10 算法本身比 v8 更可能有用 — 如果数据满足前提 (266/266 align blueprint), forced clone solve 至少能 trigger. 但当前 data 不满足, **无法验证 forced clone solve 是否能 FEASIBLE**.

**破解路径** (都不在 v10 patch 范围内, 全 data/heuristic 工程):
1. 用户手动加 41 个 mandatory facility 进 blueprint (几小时人工)
2. 改 greedy heuristic 尊重 blueprint 空地 (改 heuristic, 工作量大)
3. v10 加 partial witness mode (回到原 master 搜索难度)

**Verdict**: ❌ **死路 (data-bound, 非 algorithm-bound)**. 工程上 v10 比 v8 更干净 (代码量 1013 vs 1620, 算法逻辑更清晰, 严格性兼容), 但实测在我们 data 下 ROI=0. v10 改动留 worktree + patch 归档, 不进 main src.

**链**: [[project_v10_witness_preflight_dead]]

---

### L14. Proof-carrying weighted-occupancy blocker oracle (GPT 5/16 加料后方案, PoC 实测)

**假设**: 之前 v3/v8/v10 关注 build / anchor choice / hint, 没对准 upper-bound INFEASIBLE 排除. 直接攻"证 ghost B 下 mandatory 几何不可摆" 用 Farkas-style 整数证书:

```
lhs(λ, B) = sum_g d_g * m_g^B(λ) > cap_B(λ) = rhs(λ, B)
```

dominance: B ⊆ G ⇒ G infeasible. PROJECT_LOCK 兼容, fail-closed 设计正确, 引用真文献 (Clautiaux generalized energetic reasoning).

**PoC 实测** (worktree `zmd_l14_poc`, 3 个 script: integer verifier + LP separation + antichain scanner, ~70 min Claude pace):

| Candidate | Anchor | Ghost-Boundary 重叠 | LP optimum | Cert |
|---|---|---|---|---|
| 6×68 | (0,0) corner | 73 | 2.190 | ✓ |
| 27×15 | (22,28) interior | 0 | **1.000** exact | ❌ |
| 27×15 | (0,0) corner | 41 | 1.4375 | ✓ |
| 28×15 | (0,0) corner | 41 | 1.4375 | ✓ |
| 28×15 | (21,0) top edge | 28 | 1.2778 | ✓ |
| 28×15 | (21,27) interior | 0 | **1.000** exact | ❌ |

详细数据归档: `docs/research/l14_weighted_occupancy_poc_20260516/`

**数学 finding** (实测 + 推理):
- LP optimum > 1 当且仅当 ghost 切棋盘 boundary
- **Interior anchor LP = 1.000 严格** (boundary_storage_port 唯一 captive group, 其他 18 free group 自由摆对 LP 不贡献)
- antichain 30 shape 大多 interior anchor 占 90%+
- candidate-level INFEASIBLE 证明需 100% anchor cert → 数学不可达
- dominance 救不了 interior anchor (B 也必须 touch boundary, 但 B ⊆ G 的 interior 部分 B 也不 touch boundary → 链断)

**根因**: GPT 自己 caveat 列了 failure mode 1 ("真实不可行性依赖高阶组合结构, 不是 cell-weight capacity cut") **实测正好 hit**.

**跟 v3/v8/v10 错估区分**:
- v3/v8/v10 都是"GPT 错估关注点或前提"
- L14 = **GPT 没错估** — 方向 sound, fail-closed 设计正确, 诚实 caveat 列了 3 个 failure mode, PoC 实测 hit caveat #1
- 死的是 **数学 family 本身能力上限**, 不是 GPT 推理错

**升级路径** (GPT 自己推荐): set-packing branch-and-bound prover, 用 weighted LP 作 dual bound. 估 1-2 个月工作, **paradigm-level investment**. 不是 light-weight lever.

**Verdict**: ❌ **死路 (mathematical capability bound)**. PoC 数据 + 数学推理证 weighted occupancy proof family 在我们项目结构下不可达. 是 12 条 lever 里第一次 "GPT 给的方案 caveat 没错估, 实测如他自己预言 fail".

**链**: [[project_l14_weighted_occupancy_dead]]

---

### L15. Set-packing branch-and-bound prover (GPT L14 升级建议, 2026-05-17 PoC 实测)

**假设** (GPT 给的): L14 weighted-occupancy LP 太弱 → 升级到 dedicated set-packing prover, BnB 直接在 (x_{g,p}) 整数变量上搜, weighted LP 当 dual bound. 估 1-2 月工作 paradigm-level investment.

**PoC 实测** (docs/research/setpacking_prover_poc_20260517/, ~3 小时 Claude pace):

| Trial | 内容 | 结果 |
|---|---|---|
| A2 | 27×15 (22,28) full master.solve via LBBD 5min | UNKNOWN |
| A3 | 27×15 (0,0) full master.solve 10min | UNKNOWN |
| A4 | 27×15 (22,28) full master.solve **30min** | UNKNOWN |
| B1 | 27×15 (0,0) **minimum** set-packing CP-SAT 1w 60s | **INFEASIBLE 2.4s, 0 branch** |
| B3 | 27×15 (22,28) minimum 8w 5min | **OPTIMAL (feasible) 7.2s** |
| B4 | 27×15 (0,0) minimum 8w 2min | INFEASIBLE 2.3s |
| B5 | 27×15 (21,0) edge minimum 8w | INFEASIBLE 2.3s |
| B6 | 28×15 (0,0) minimum 8w | INFEASIBLE 2.3s |
| B7 | 28×15 (21,27) interior minimum 8w | OPTIMAL 7.1s |

**关键 finding**: **minimum set-packing 核心 CP-SAT 已经轻松搞定** — corner/boundary 2-3s INFEASIBLE (propagator instant), interior 8w 7s FEASIBLE. paradigm 攻的是已经 fast 的层.

**真瓶颈**: master 多余的 port_binding / power_coverage / boundary_port_feasibility / exact_safe_cuts. 这些约束让 CP-SAT 30 min 也 UNKNOWN. GPT 的 set-packing prover 不 cover 这些.

**Verdict**: ❌ **死路 — 攻错层**. paradigm 假设错: 假设 set-packing 核心难, 实测 CP-SAT 几秒搞定. 真瓶颈在 master 多余约束 (跟 [[project_highs_rewrite_blocker]] 同根因 — dense linear constraint), 不在 set-packing 部分. **不要投资 2 周/1-2 月写 prover**.

**Step D 加跑 layer isolation 锁定**: `skip_power_coverage=True` 后 master.solve 65.9s 完整 2 LBBD iter (vs 30 min UNKNOWN). power_coverage 加 +132% vars + 90% constraints, 是真 bottleneck. 真嫌疑精确锁到 `_add_geometric_power_coverage_constraints` (`src/models/exact_coordinate_master.py:5327`) — disjunctive coverage encoding (element_witness / table_pairwise_witness). 算法改进方向: column generation / lazy cut / 几何 pre-prune / lazy power_coverage 进 subproblem, 不是 set-packing prover.

**链**: [[project_l15_setpacking_prover_dead]]

---

### L16. Lazy Power Completion Phase 0 (GPT v11 详细计划书, 2026-05-17 mini-PoC 实测)

**假设**: GPT v11 推荐 — master 跳 `_add_geometric_power_coverage_constraints` 但保留 `power_pole` residual slots, completion subproblem 解电杆, Benders cut 回灌 master. 跟旧 L4 (`EXACT_POWER_PLACEMENT_SUBPROBLEM` 完全删 pole slot) 关键区别: pole slot 仍 materialized, downstream cut 可 resolve runtime literal. GPT v11 提议新 PROJECT_LOCK L4a/L4b 边界切开.

**Phase 0 mini-PoC 实施** (1 Claude day, commit `5d37321`):
- 加 `EXACT_LAZY_POWER_COMPLETION` env flag, 改 `exact_coordinate_master.build()`
- 写 `scripts/phase0_lazy_power_completion_probe.py` driver
- L4a runtime guard: 旧 flag certified mode raise (forensic test 加 bypass env)

**Phase 0 数据点** (27×15 anchor (22,28)):

| Gate | 实测 | 阈值 | 结果 |
|---|---|---|---|
| Master first solve seconds | **81.8** | ≤ 90 | ✓ PASS |
| Master status | **OPTIMAL** | OPTIMAL/FEASIBLE | ✓ |
| Completion (first layout) | **INFEASIBLE 134/220 uncovered** | FEASIBLE | ✗ NO-GO |
| Cut loop 10 iter 收敛 | 134→133 (-1) 然后 stuck 7 iter | 收敛 | ✗ NO-GO |

跟 GPT v11 计划书 **Plan B trigger 条件完全 match**:
- "If status is INFEASIBLE on the first layout: Phase 0 no-go"
- "UNKNOWN_POWER_CUT_STALL: > 6 条 cut 无进展"

**关键 finding**:
1. **Master 端方向对** — skip coverage 81s OPTIMAL vs production 30 min UNKNOWN, 跨数量级. 证实 coverage encoding 是真瓶颈, master 跳掉就快
2. **Cut 端死** — loose nogood cut (禁全 220 powered pose) 太松, master 只需 swap 1 pose 绕开. 同 5 个 `crusher_blue_iron` 反复 uncovered, geometry blocking 持续 reappear

**Phase 3 加跑** (2026-05-17 同日, commit 待补): deletion-based core minimizer 实施 + tight cut trial. Cut size 220 → 6 (minimizer 5.3s 267 oracle calls), 但 6 iter uncovered 134→125→133→133→133→123, **振荡不收敛**. Master 不带 coverage 选 categorically uncoverable layout, 6-instance cut 自由度上百万级远不够. 命中 GPT v11 `UNKNOWN_POWER_CUT_STALL` abort 条件.

**Verdict**: ❌ **死路 (master 端 PASS, cut 端 instance-level Benders cut 不 propagate 足够信息)**.

Plan B 选项:
| Option | 工作量 | Risk |
|---|---|---|
| ~~A. Phase 3 deletion-based core (tight cut)~~ | ~~+2-3 day~~ | ~~实测 6 iter 仍不收敛 ❌~~ |
| B. pose-bool master rewrite (Plan B1) | 1-2 周 | 完整 master + port_binding 后可能又 stuck |
| C. 接受 verdict, paradigm 死 | 0 | 项目目标妥协 (release area=405 best-known 非 certified) |

**链**: [[project_l16_lazy_power_completion_phase0]]

---

### B1. pose-bool master rewrite — Phase 0 prototype (2026-05-17 standalone PoC 实测)

**假设**: 把 master 从 coordinate-based (x, y, mode IntVar + AddNoOverlap2D) 改成 pose-bool form (x_{group,pose} BoolVar + AddAtMostOne per cell), 让 CP-SAT cell-exclusivity propagator 直接 fire, 跳过 AddNoOverlap2D 在 dense packing 下的弱点. L16 已证 master skip coverage 快 (81s OPTIMAL); B1 测的是加回 coverage 后 pose-bool form 是否仍快.

**正信号** (上游证据):
- Step B 同 form minimum (跳 power) 27×15 interior **7.2s FEASIBLE** 8w
- L16 master 跳 coverage 81s OPTIMAL (证 coverage 是真瓶颈)

**Phase 0 prototype** (`docs/research/b1_pose_bool_phase0_20260517/poc_pose_bool_with_power.py`):
- 加 mandatory 19 groups + required_optional protocol_storage_box + residual_optional pole 全 pose-bool 表达
- 加 power_coverage constraint: 对每 powered pose `x_{g,p} ≤ Σ y_{coverer_pole_pose}` (pose-bool form)
- 跳 port_binding / boundary_port (在 Benders subproblem, 不在 master)

**实测 5 anchor**:

| candidate | anchor | area | status | solve(s) | poles |
|---|---|---|---|---|---|
| 27×15 | (0,0) corner | 405 | INFEASIBLE | 20.6 | - |
| 27×15 | (22,28) interior | 405 | **OPTIMAL** | **52.8** | 171 |
| 30×15 | (20,28) interior | 450 | **OPTIMAL** | **53.2** | 160 |
| 35×15 | (18,28) interior | 525 | **OPTIMAL** | **52.9** | 124 |
| 36×16 | (18,28) interior | 576 | **OPTIMAL** | **49.4** | 136 |

跟 coordinate-based 30 min UNKNOWN 比 **快 ~34x**. 跟 L16 lazy completion (master 81s + cut 不收敛) 比 master 一次给出 power-feasible solution 不需要 Benders cut 回灌.

solve time 几乎不随 area 变化 (49-53s consistent), 推测大 candidate ghost 占走更多 cell 减少 facility 自由度抵消 search space 增加.

**Verdict**: ✅ **Phase 0 GO**. pose-bool form + power_coverage 一次性 master solve 在 < 60s 收敛.

**Next**: Phase 1-5 生产实现 (替换 coordinate-based master / 适配 binding/routing subproblem / extract_solution / cut replay / regression test). 估时 1-2 周.

**链**: [[project_b1_pose_bool_master_rewrite_plan]]

---

## 旁线工程改进 (verified land, 但不破 0 FEASIBLE)

这些路线虽然没破 0, 但项目质量真实提升:

| Task | 内容 | 状态 |
|---|---|---|
| #38 | readiness gate OOM headroom 数学公式 | ✅ |
| #41 | coordinate Benders cut 过切 bug 修 | ✅ |
| #44 | IP v2 blueprint 静态 validator | ✅ |
| #45 | IP v2 blueprint LP solver 验证用户摆法 | ✅ |
| #46 | P0 #1 ghost-conditioned power infeasible cut | ✅ |
| #47 | P0 #2 关 EXACT_POWER_PLACEMENT_SUBPROBLEM 进 certified path | ✅ |
| #48 | P1 #4 add_benders_cut 加 condition_lits | ✅ |
| #50 | P2 #5 pytest random-order flake seed sweep | ✅ |
| #54-#58 | F1-F5 v4 follow-up (replay resolver / power witness gate / dynamic probe / cache reset / untracked-tree block) | ✅ 全 land |
| #59 | bandit 4 MEDIUM 修 + PROJECT_LOCK 文案 | ✅ |
| #61-#65 | G1-G5 mypy + ruff hygiene 全过 gate | ✅ |
| #66 | P1 #24 cache trio (jemalloc + P-core + THP) +15-22% wall clock | ✅ |
| #67 | -p 2 + workers=1 解锁双并行 | ✅ 但不破 0 |
| #84 | tight pole_slot upper bound -80% search space | ✅ |
| **2026-05-16** | **community hint 整链 + 测试 + wrapper default + runbook** | ✅ |

---

## 当前状态

**已 verify 排除的 lever**: L1 / L2 / L3 / L4 / L5 / L7 / L8 / L9 / L10 / **L12** / **L13** / **L14** / **L15** / **L16** 共 **14** 条死路

**搁置 / 长期 option**: L6 (AI sidecar)

**Phase 0 GO 待生产实现**: **B1 (pose-bool master rewrite)** — Phase 0 prototype 5 anchor 全 fast verdict, 49-53s OPTIMAL. 生产路径 1-2 周.

**累积事实** (3 天 session + 14h trial + 多次 1h trial + v8/v10/L14/L15 PoC 实测):
- master.solve **不管喂什么资源都解不动这个 model**
- 不是单一 lever 缺失, 是 model 本身对 CP-SAT 来说**太难**
- 严格性兼容 + 算法层面的所有 algorithmic lever 全部 verdict 完毕 (L1-L10 + L12 + L13 + L14)
- v8 verdict: 算法错估 (anchor choice 不是搜索瓶颈)
- v10 verdict: 前提错估 (要求 complete witness, 我们 data 不匹配)
- L14 verdict: GPT 没错估方向, 实测 hit GPT 自己 caveat 列的 failure mode 1 (weighted occupancy 数学能力不够)
- **L15 verdict** (本次 PoC): paradigm 攻错层 — minimum set-packing CP-SAT 几秒搞定, 真瓶颈是 master 多余约束 (port/power/connector/boundary). prover 即使写出来也是 attack 已经 fast 的部分
- **GPT 已经在四个不同方向尝试**: 算法 (v8) → 数据 (v10) → 数学 family (L14) → paradigm (L15), 都未能破局
- 剩下选项: L11 牺牲严格性 / paradigm shift / 改数据 / 接受 verdict
- L11 是改 problem 本身, 是当前**唯一**几乎保证出 FEASIBLE 的路径

---

## Memory 引用

- [[project_endfield_solver]] — 项目总览
- [[project_2026_05_15_ram_session_misdirected]] — L1 整 session 跑偏教训
- [[project_30gb_real_culprit_power_coverage]] — L3 真大头 = worker propagation buffer
- [[project_highs_rewrite_blocker]] / [[project_rewrite_path_exhausted]] — L2 死路
- [[project_d_step2_hint_landed]] — L7 community hint 落地详细状态
- [[feedback_optimization_strategy]] — "优化必须 stack 所有方案, 不按 ROI 单选"
- [[feedback_avoid_micro_optimization_spiral]] — "占比 <5% 就停手换方向"
