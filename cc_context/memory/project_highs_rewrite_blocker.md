---
name: highs-rewrite-blocker
description: "2026-05-15 HiGHS 重写遇硬性瓶颈: minimum model -79% RAM (win), 加 power_coverage 后 +40% RAM (败). LP-MIP 对 dense linear constraint 不适合, RAM 反而比 OR-Tools 大"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-15 HiGHS 重写 Phase 1-3 PoC verdict**:

| 实测 | Build RSS | Build 时间 | 备注 |
|---|---|---|---|
| OR-Tools baseline (70x70 + 266 mandatory) | ~8-10 GB | similar | solve 阶段 ~30 GB peak |
| **HiGHS minimum** (no power coverage) | **4.81 GB** | 9.9s | solve plateau 6.34 GB, -79% vs OR-Tools |
| **HiGHS full** (include_power_coverage=True) | **42.15 GB** | 104.6s | swap 7.8 GB, host 几近 OOM |

**关键 finding**: HiGHS LP-MIP 对 dense linear constraint 不适合.

power_coverage 约束规模 (70x6 ghost, 70x70 grid):
- 3.85M rows (每 facility pose 一行)
- 787M nonzero sparse entries
- CSR 矩阵 explicit store: ~13 GB
- 加 z_var/pole_var arrays + col/row metadata = ~42 GB build

OR-Tools CP-SAT 用 propagation table + lazy clause generation, 不 explicit
store linear constraint matrix → RAM 紧凑.

**Hard verdict**: HiGHS 重写在 production-grade scope (含 power_coverage) RAM
反而比 OR-Tools 大. 不解 Phase 3B RAM 瓶颈.

**Phase 1-3 已 commit** (留代码 / tests / PoC 给未来参考):
- 9bee9f2: Phase 1 minimum translator + 4 tests
- a024589: cpsat mirror + equivalence + Phase 2 PoC script
- 0710730: power_coverage helper + 3 tests
- f0e9357: power_coverage integration to minimum model
- (latest): HighsCandidateEvaluator + Phase 3 PoC + evaluator tests

代码不删除 — Phase 1 minimum model 是 working production code, 未来如果做
HiGHS LBBD decomposition 重写 (power_coverage 拆 subproblem) 可复用.

**未试过的 HiGHS 救活路径** (Phase 4 工作, 未启动):
1. **LBBD-style decomposition**: 像 OR-Tools 那样把 power_coverage 拆 subproblem
   (lazy cut), 不 explicit 全 build. weeks 工作, 不确定 work
2. **HiGHS lazy callback API**: 如果 HiGHS 1.14 有 callback (待 verify), 可
   lazy 加 violated power constraint. 不确定 API 支持
3. **Aggregate cardinality**: 把 4M individual constraints 合并成 "5x5 区域至少
   1 pole" 这种弱化. **准确性受损, 用户排除**

**剩下真路径** (跟 [[p1-24-oom-blocked]] 路径累加):
- 168h `-p 1` 继续跑攒 AI cuts 数据 (当前 PID restarted)
- 等学术 Gurobi license (用户摸索中)
- multi-level LBBD on OR-Tools (silent corruption 风险 hard no)
- 等 GPT/社区出新方向

**链**:
- [[p1-24-oom-blocked]] 主上下文
- [[gpt-anchor-slicing-proposal]] anchor slicing 验过死透
- [[verify-solver-param-claims]] 这次又验了: 工程实现 mature 不等于 RAM 减

## 2026-05-15 PM SCIP pivot — Phase 4 实测数据

**HiGHS 1.14 lazy constraint API placeholder 不工作**:
- cbMipDefineLazyConstraints (type 8) 注册不报错但 C++ 不 fire
- 实测确认 (knapsack PoC fire 0 次)

**SCIP 6.2 separator callback 真工作**:
- includeSepa + sepaexeclp 实测 fire ✓ (knapsack 3 次, 加 cut 真生效)
- 关键 trick: model.setHeuristics(SCIP_PARAMSETTING.OFF) 让 LP search 启动
- License: SCIP 学术/非商业免费, 个人 dev 符合

**SCIP Phase 4 PoC 实测 (70x6 real data)**:

| Phase | Build | Solve | Peak | vs OR-Tools 30 GB |
|---|---|---|---|---|
| HiGHS minimum | 4.81 GB | 6.34 GB | -79% | 假 win (无 power) |
| HiGHS full | **42 GB** | 死 | **+40%** | 撞 OOM 失败 |
| **SCIP separator** | **7.95 GB** | **22.65 GB** | **-24%** | marginal win |

**判决**:
- SCIP path 真可行: 准确性保留 + RAM 减 24%
- 不到任务 #67 阈值 50%, **不解 -p 2 并行**
- -p 1 安全 buffer 从 10 GB 增到 17 GB
- Wall-time 慢 (291s vs OR-Tools 同 candidate, single-thread + LP)

**Code 已 land** (6 commits 总共):
- HiGHS Phase 1-3 (9bee9f2 → 51a9dbc): minimum + power + evaluator
- SCIP Phase 4 (a160f7c → 当前): minimum + lazy separator + PoC

**下一步选项 (留 user 决策)**:
A. 集成 SCIP separator 路径 production, 接受 -p 1 + 24% buffer 更稳
B. 接 OR-Tools baseline + 168h `-p 1` 长跑 (现状)
C. 放弃 重写, 等 Gurobi 学术 license / 等 GPT 新方向
