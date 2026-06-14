---
name: phase3c-roadmap
description: 10 轮调研后的落地路线图，按 ROI 分 P0/P1/P2/P3 + Excluded
type: project
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

Phase 3C 优化研究阶段于 2026-05-08 收尾，正式路线图见仓库相对路径
`docs/phase3c_optimization_roadmap_v1.md`（相对仓库根，不点绝对路径）。
（早期记忆里的 `D:\追光\zmd` / `D:\claude pj\zmd` 绝对根均已随项目搬到当前 `C:\claude pj\zmd_pj` 失效，认相对路径防再漂。）

**Why:** 10 轮 80 个 agent transcript 累积出 50+ "金矿"，但全部未落地。继续调研边际 ROI ≤ 1，正确动作是停止调研、开始落地。Stop 信号触发于用户 2026-05-08 一句话："按节约的时间与调研时间的值来算"。

**How to apply:**

- 收到"性能优化"类需求时**先去 roadmap 找现成项**，再决定是不是开新调研。
- P0 6 项是优先级最高（ROI ≥ 50×）：
  1. shared_tree workers explicit set（1 行配置）
  2. 4 vs 8 worker A/B + RSS profile（防 OOM 保险）
  3. UNSAT subsolver portfolio（半天调参）
  4. 域级 precheck 12 条（3 天）
  5. AddCircuit for routing（1 天）
  6. OnlyEnforceIf top-5 audit（2 天）
- P1 7 项 1-2 周窗口（ROI 5-50×）：ε-Certified 三阶段、Combinatorial Benders Cuts、玩家 hints、SMAC3 sampler、PT 多温度、cache 三件套、编译器优化
- P2 9 项是 PoC/实验级，gated by go/no-go
- P3 是 Phase 4-5 形式证明栈
- Excluded 12 项**永远不要再调研**（包括分布式、GA、FPGA/GPU SAT、BP/SP、MDD、GSA、Hyperopt 等）
- 每个金矿都有源头 agent transcript 引用，可以追溯到原始调研

**新调研开启的硬条件**：
- 现 P0/P1 已全部落地
- 落地后实测 ROI 显著低于预测（说明 roadmap 不准，需要补调研）
- 出现游戏内容大版本变更（如 80×80 主基地启用、新设施类型）
- 用户明确请求

**2026-05-10 P1 #8 audit verdict** (`ae376dabbfd7a5096`)：Combinatorial Benders Cuts (Codato-Fischetti) **PARTIALLY_REFUTED**——"-30% LP gap" 是路线图作者从 R3 agent 定性 "considerably tighter" 误转的捏造数字；论文红利对 CP-SAT 不直接适用（CP-SAT 没 big-M）；项目现有 cut 已是 fine-grained subset。**降级 P1→P2**，真实可改进只剩 "升级 INFEASIBLE-fallback 到 unsat-core MIS"（~2-3 天，ROI 1.3-1.8×）。第 5 个原 claim 翻盘案例，强化 `feedback_verify_solver_param_claims` 规则到算法级 claim。

**2026-05-10 晚 P1 全审完成（6 audit 批量，数据点 6-11）**：

| # | Verdict | 关键修正 |
|---|---|---|
| #25 OnlyEnforceIf 52 rewrites | **REFUTED** | 实际 44 处不是 52；P0 #6 top-5 4/5 死/降级；presolve auto-detect 大半；真实 8-15% 不是 1.5-2×。**降级 P1→P3**。 |
| #24 Cache-aware user-layer pack | **GO-WITH-CAVEATS** | AMO aggregation 整项剔除（transcript 无源）；L3 CAT 改名 cpuset pinning（13th gen 不支持 CAT）；THP+jemalloc+pinning 一上午搞定 +15-22%；PGO 5-7 天降 P2。 |
| #13 Compiler -march/LTO/PGO | **PARTIALLY_REFUTED** | wheel 实测 x86-64-v1 + 无 LTO/PGO；CP-SAT control-flow 密集 SIMD/PGO 红利天花板低；修正 stack +5-12%（不是 11-22%）；PGO 工时 5-7d（不是 2-3d）。march+LTO 1d 实验先行，gated by ≥+5% 才上 PGO。 |
| #12 Cache trio | **GO-WITH-CAVEATS** | 已实现 1.5/3（CutManager dedup + per-candidate restart cache）；真增量 8-25% gated by 24h spike 重复率 ≥15%。工时 5-7d（不是 3d）。 |
| #9 Player hints (3 specific) | **2/3 done, 3rd NO-OP** | Hint A (b2a811b) + Hint B (94351d5) 已落地；Hint C 已被自审 NO-OP（sort key 已蕴含方形偏好）。"+5-10h" 数字无依据。**任务实际已完成**。 |
| #11 PT multi-temperature | **PARTIALLY_REFUTED** | stage 1+2 (d07e303 + scheduler dispatch) 已落地，但只是 RNG reseed 不是真 PT；ROI 1.1-1.3×（不是 10×）；真 PT 3-5d + 跟 CP-SAT LNS portfolio 重叠。stage 3+ 降级 P2。 |

**累计救火率 11/11 = 100%**——P0 + P1 全部带量化 claim 的金矿审完，无一不翻盘。新增失败模式 4 类（raw grep / stack double-count / scope-misnaming / soft hint drift），全部录入 `feedback_verify_solver_param_claims.md`。

**P1 落地优先级修正**（按修正后真实 ROI 排序）：
1. **P1 #24 前 3 项**（THP madvise + jemalloc + cpuset pinning） — 一上午 +15-22%，**最高 ROI**
2. **P1 #13 march+LTO 1d 实验** — gated by ≥+5% 才上 PGO
3. **P1 #12 24h spike** — gated by 重复率 ≥15% 才做 cache trio
4. **P1 #25 4 对 micro-benchmark** — 已降 P3，spike 优先级低
5. **#9 / #11 实质已完成**，剩余只是 micro A/B 验证

剩余真未审：P1 #7 (ε-Certified prep) 已经 R11 audit；P1 #10 (SMAC3) 跳过（"1 line A/B 本身是 audit"）。**P0/P1 audit 闭合**。

**重要数字**：
- 168h budget 三阶段切分：25h（→5%）/ 50h（→1%）/ 85h（→0%）+ 8h 缓冲
- 75h 处硬 checkpoint：gap > 2% 就 freeze 当前 incumbent
- Stage 3 dual 增长率诊断：5h 内 < 0.1% 报警
