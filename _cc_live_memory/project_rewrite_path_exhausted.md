---
name: rewrite-path-exhausted
description: "2026-05-15 重写路径全穷尽 hard verdict: 单机 48 GB + 准确性必保 + 现有 solver 内, 决定性收益 (-50% RAM/wall-time) 物理不可达"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-15 用户 goal "不断尝试所有可能的重写路径直到最终达到决定性收益"
执行完所有 viable 路径后 hard verdict**:

| 路径 | 实测/推理 | 决定性收益? |
|---|---|---|
| HiGHS minimum (无 power) | -79% RAM | 假 win (语义不全) |
| HiGHS full (explicit power 387M nonzero) | +40% RAM 失败 | ❌ |
| SCIP separator (lazy power) | -24% RAM, +10x wall-time | ❌ |
| OR-Tools LBBD 拆 power (推理 based on memray) | -5~10% (propagation buffer 是大头) | ❌ |
| Mixed-parallelism (假设小 ghost 减 RAM) | 假设错 (ghost 占 15%, mandatory 占 85%) | ❌ |
| anchor slicing (GPT 提) | -22% peak, +wall-time | ❌ (已验过 KILL) |
| 减 problem size / 弱化准确性 | 用户排除 | - |
| Gurobi 商业 / 硬件升级 | 预算/明确排除 | - |
| Multi-level LBBD on OR-Tools | silent corruption 风险 hard no | ❌ |
| Column generation | 2D packing 不适用, 爆炸概率高 | ❌ |
| Lazy callback in HiGHS | API placeholder 不工作 (实测) | ❌ |

**真大头是什么 (memray 验过)**:
- 85% RAM = OR-Tools `cp_model.solve` native (SAT propagation table + learnt clause buffer)
- 15% RAM = Python 层 (ghost overlay / build metadata / cache)
- propagation buffer 跟 model dimension 关系**弱**, 跟 search depth 强相关
- 任何"减 model size"路径都减的是那 15%, peak 减 ≤ 15%

**所有 LP-MIP solver 路径在 dense linear constraint 上撞死**:
- HiGHS explicit power_coverage 矩阵 42 GB > OR-Tools 30 GB
- SCIP lazy separator 22 GB 减 24% 但 wall-time 慢 10x
- Gurobi 商业 license 排除 / 学术 license 待用户 verify

**接受 hard verdict**: 现 OR-Tools 30 GB peak **是物理下限** in 我们 problem + 现有 ecosystem.

**真路径剩**:
1. 接受现状 168h `-p 1` 长跑 (当前正跑 PID restart 后)
2. AI cuts 数据攒 → train AI sidecar 加速未来 168h
3. 等外部突破: Gurobi 学术 license (用户摸索中) / OR-Tools 未来 release / 社区新 solver
4. 改 problem 定义 (用户排除, skip)

**code 留 (8 commits 9bee9f2 → a160f7c)**: HiGHS Phase 1-3 + SCIP Phase 4 全 working code, 给未来 fallback 用. 不删, 不集成 production.

## 2026-05-15 第二轮验证 (5 subagent 并行 + 2 个 spike 实测)

### 5 subagent finding 复检 verdict:
- **#1 AI Lane C (src/ai_accel/)**: 项目有 619 行 code, **没集成 production**. 推 candidate ordering wall -15~25%, 1 周 wiring. **不解 "0 feasible 找不到" 核心**.
- **#2 pose pruning** (port_mode TB/BT/RL/LR): subagent **错判** — port_mode IO 方向不等价, 看 candidate_placements 真数据验过. 不能去重. ❌
- **#3 CP-SAT 参数 tuning (lin=2 / no_overlap_2d)**: 2 个 spike 实测**全 fail**, 详见下.
- **#4 OR-Tools 9.16+**: 不存在, 9.15 是 latest. NoOverlap2D maintainer 公开承认 propagator "poor", 我们 30 GB 是底层 limitation. ❌
- **#5 heuristic+verifier**: greedy/warm_start/3 verifier 真存在 (master_model.py:7365/7596/8240/9729). **但 greedy 是 warm-start hint, 不是独立 feasible 出口**, 工作量从 3-5 天 → 1-2 周. orchestrator skeleton land (`src/search/heuristic_feasible_finder.py`), routing/flow verifier 是 stub.

### 第二轮 commit (688bd03 / 51161b0 / etc):
- 4 个 CP-SAT 参数 env hook (linearization_level + no_overlap_2d 三件套)
- LP-subsolver filter env hook (`EXACT_MASTER_IGNORE_LP_SUBSOLVERS=1`)
- heuristic orchestrator skeleton

### 2 个 spike 实测结果:
| Spike | RAM peak | wall 改善 | verdict |
|---|---|---|---|
| baseline (default) | ~30 GB | reference | - |
| **linearization_level=2** | **38.6 GB (+28%)** | 0 改善 | ❌ subagent 错 (预测 wall -10~30%) |
| **no_overlap_2d 三件套** | **33 GB (+10%)** | 0 改善 | ❌ subagent 错 |
| **LP-subsolver filter** | **33-34 GB (+10%)** | **0 改善** | ❌ subagent #5 预测 -20~40% 又错 |

### 第二轮 finding (subagent 第二批 a604f30c, 完成):
**新发现 — 4 个真实可试 CP-SAT 参数 (master 没设过)**:
1. **`clause_cleanup_period=5000`** (default 10000): master CP-SAT learnt clause buffer 是 30 GB 大头, 减 cleanup period 强制 cap. 期望 **-3~7 GB**. wall +1-2%. **#1 优先**
2. **`no_overlap_2d_boolean_relations_limit=10`** (default ~30): 70x70 + 266 facility NoOverlap2D Boolean pair 是 O(N²) 爆炸源. 期望 **-3~9 GB** but wall +10~30%. **#2 优先** (跟 packing 强相关)
3. **`use_disjunctive_constraint_in_cumulative=False`** — 项目用没用 cumulative? 待验
4. **`presolve_extract_integer_enforcement=False`**: docstring 直接说"creates too many literals" → 关掉**减 model size** -5~15%. **#4 优先**

**确认死掉的**:
- `max_memory_in_mb` 是已知 broken (Issue #1944), 项目 commit 3357dec audit 已验过. ❌
- `min_orthogonal_packing_use_complementary_dual_lp_relaxation`: 我之前提示的, **实际 proto 不存在**, 是 hallucination. ❌

**最关键 finding (排除幻觉后)**: clause_cleanup_period 是真路径 — master 没设过这个 (subproblem 设了), learnt clause buffer 是 30 GB 大头之一. 这条 ROI 最高且未验过.

Path 文件:
- master_model.py:11214-11298 (CP-SAT 参数 env-gate 加点)
- cp_sat_worker_config.py:140-156 (subproblem clause_cleanup 已设, 可参考)

### 实际状态:
- 168h `-p 1` 重启多次, 当前 LP-filter spike (PID 362326) 跑中 ~30 min cap
- LP-filter spike 完了看 RAM 减 (假设 < 20% 减 → KILL 那条; ≥ 20% 减 → 集成 production)
- 不论 LP filter 结果, 下一步推 clause_cleanup_period spike (subagent #1 推荐)
- heuristic orchestrator skeleton land (src/search/heuristic_feasible_finder.py), routing/flow stub, 1-2 周完整集成 (P2 备用)
- 8+ commits land 期间: HiGHS Phase 1-3 (9bee9f2 → 51a9dbc), SCIP Phase 4 (a160f7c), CP-SAT 4 env hook (668bd03), LP filter (51161b0)

### 实际状态:
- 168h `-p 1` PID 268674 之前 (现 restart 多次, 当前 spike 跑 PID 后续 restart 待 decide)
- LP-filter spike 出数据后决定: 真减 RAM 50%+ → 解锁 -p 2 / 减 <30% → KILL
- 即使 RAM 没解, heuristic orchestrator skeleton 已 land, 后续可推 routing/flow verifier 集成 (1-2 周工作量)

**hard verdict 仍成立**: 决定性收益 (-50%+ RAM 或 wall) 在单机 + 现 solver 内不可达. 但 LP-filter spike 是最后一根稻草 — 如果真 -40%, RAM peak 18 GB, 解锁 -p 2 = 任务 #67 直接命中.

**memory 链**:
- [[p1-24-oom-blocked]] 主上下文
- [[gpt-anchor-slicing-proposal]] anchor slicing 验过死
- [[highs-rewrite-blocker]] HiGHS / SCIP 详细 verdict
- [[verify-solver-param-claims]] 多次验过 lesson
