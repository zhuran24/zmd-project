---
name: verify-solver-param-claims
description: agent 调研出的 CP-SAT/SAT/MIP 参数 "+N% 收益" 类 claim，进 P0/P1 之前必须读官方源码或 proto 验证数学行为，否则可能负 ROI
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

> 事实依据: [[fact-evidence-before-story]]

agent 调研产出的"求解器内部参数级金矿"（如 `shared_tree_num_workers`、`linearization_level`、`presolve_*` 类参数）进入路线图 P0/P1 **之前**，必须用一个 follow-up agent 直接读官方源码（GitHub `ortools/sat/*.cc`、`sat_parameters.proto`、issue tracker）核实参数的实际数学行为。**不能只信"agent 引用了某 benchmark 说 +N%"**。

**Why:** 用户 2026-05-08 让我开 follow-up agent 查 `shared_tree_num_workers` 的官方公式（P0 #1 实施前的"数学依据查证"）。结果**直接推翻了 R5 那个 🥇🥇 双金金矿**：

R5 调研报告："we currently have 0 shared_tree workers; explicit set = +10-30% UNSAT"，进路线图标 ROI ~1000×，列 P0 #1。

实际源码（`cp_model_solver_helpers.cc:2206-2218`）：
- auto 公式 `(num_workers - 16) / 2` 在 8 worker + max objective 下解出 -4，正确归 0
- shared_tree workers 从 `num_workers` **扣**不是叠加：8 = 4 portfolio + 4 shared_tree（portfolio 多样性砍半）
- Google implicit 启用阈值 `num_workers ≥ 26`（objective 模式）
- R5 引用的 "+10-30% UNSAT" 是 SAT/feasibility benchmark 数据，**不适用于 max problem**

也就是路线图 P0 #1（最高 ROI 项）实际是**负 ROI**——硬上等于砍掉一半 portfolio worker。如果不查源码直接实施，168h campaign 会跑得更慢，还以为在加速。

**How to apply:**

- 任何"调整 solver 内部参数 = +N% 性能"类 claim 进 P0/P1 之前，开一个 follow-up agent 任务：直接给 GitHub URL，让它读源码（`grep -n` 关键参数名 + 周围 20 行上下文 + 公式段）。**不要信 agent 一手 benchmark 引用**。
- 验证至少 3 件事：
  1. 参数的**默认行为**（auto/-1 是不是真在我们的配置下生效？很多 auto 公式有阈值，少 worker 时归零）
  2. 参数和 `num_workers` / 其他 worker 资源的**关系**（扣还是叠加？相互影响？）
  3. 参数对**目标类型**敏感性（max vs UNSAT vs feasibility 收益不同；R5 那条 benchmark 是 SAT，我们是 max_lex）
- 验证结果写进 INDEX.md 对应 round 段——`❌ REFUTED by 后续 agent`，给后续 session 留下记忆。
- 同步修订路线图（删除或降级金矿条目），保持 P0/P1 实施清单的可信度。
- 这条规则**只针对 solver 内部参数**——文档级、AI ordering、玩家 hint 这种没有"读源码就能精确验证"的 claim，不适用此规则，但要承认它们是软估计。

**Bonus**：每次按这个流程救回一次"伪金矿"，把节约的工程时间记录在 INDEX.md 对应 round 段——这是审查 + 调研的 ROI 兑现实证。

**2026-05-08 晚强化更新**：参数级 P0 救火率统计 **4/4 (100%)**——覆盖两类伪金矿：
1. **"benchmark citation" 型**（R5 shared_tree, R2 UNSAT subsolver, R7 AddCircuit）—— agent 引用真 benchmark 但没核实是否适用我们配置/目标类型
2. **"Claude inference" 型**（R11 presolve_extract_integer_enforcement）—— agent 自己拍 +N%（"30-50 处简化"），零 citation，且**事实描述错误**（agent 说参数 A 实际做 B）

这意味着规则要更严：**任何参数级 P0/P1 项的 ROI claim 如果不能 trace 到 primary source-code 或 proto 阅读，必须 follow-up audit**——agent transcript 里写的"+N%"哪怕看起来 plausible，统计上 100% 都翻了。

实操：路线图新增一项参数级条目时，提交人（agent or human）必须填一栏 "ROI provenance"：
- A. "verified source" + 引用 .cc/.proto 行号 → 可进 P0
- B. "benchmark citation only" → 必须 follow-up audit 才能进 P0
- C. "agent inference / vibes" → 默认 P3，只有审查证据足够才升级

**2026-05-10 第 5 个数据点（规则边界扩展）**：P1 #8 Combinatorial Benders Cuts (Codato-Fischetti) audit by `ae376dabbfd7a5096`：
- 路线图 claim: "master LP gap -30%+, ~1 week, ROI ~5×"
- 真实情况: 论文实际 claim 只是 "considerably tighter on **two MIP classes**"，**没有 -30% 数字**；论文 master 是 ILP，红利核心是消除 big-M LP relaxation——**CP-SAT 没 big-M 形式不直接适用**；项目当前 cut 已是 fine-grained subset（whole-layout 只是 INFEASIBLE 兜底）；CP-SAT CDCL 自动学 minimal-ish learnt clause
- 真实可改进窄到 "升级 INFEASIBLE 兜底走 unsat-core MIS"，ROI 1.3-1.8×、~2-3 天，被 demote 到 P2

**规则边界扩展**：原条目限定 "solver 内部参数"，CBC 是**算法级金矿**而非参数。但救火模式相同——**agent 给数字、primary source 不支持**。新规则覆盖范围：
- ✅ Solver 参数（必须读 .cc/.proto）
- ✅ 学术算法（必须读论文 abstract / 结果章节核实是否真有那个数字 + master/sub 类型是否对得上）
- ⚠ 模糊地带（如玩家 hint、AI ordering）仍用软估计、不强制 audit

5/5 的 audit 全部翻了原 claim（4 solver-param + 1 algorithm）——**任何"+N% 性能"金矿在没经过源码/论文 audit 之前不能进 P0/P1**，是经验法则不是过度防御。

**2026-05-10 晚 6 audit 批量（数据点 6-11，路线图 P1 全审）**：

并行跑了 P1 #25 / #24 / #13 / #12 / #9 / #11 6 个 audit，**全部 turn up issue**。累计 **11/11 = 100%** audit 翻盘率。新增的失败模式：

- **"raw grep -c without classification"**（#25）：R11 用 `grep -c "OnlyEnforceIf" exact_coordinate_master.py` 得到 52 (实际 44)，没分类就外推 "1.5-2× single wave"。改造类的 ROI 估值必须先把 grep 结果按改造模板分类，看每类活率多少。
- **"stack double-count"**（#24 / #12）：5 件套加和不打 stack-efficiency 折扣（典型 0.5-0.7×）。THP / malloc / PGO / L3 isolation 都改善内存子系统 → 同一份 stall 不能被多干预各削一遍。多件套 combined claim 必须乘 0.6 stack efficiency。
- **"scope-misnaming"**（#11）：实现的是 per-process RNG reseed，路线图叫"PT 多温度" → claim "10× 收益" 用错维度（实际是 portfolio diversity, marginal lift 1.1-1.3×）。命名跟实现脱钩时 ROI claim 也跟实现脱钩。
- **"soft hint roadmap drift"**（#9）：第 3 个 hint 在 commit 自审为 NO-OP 但路线图没同步更新，留下假"未完成"项。Commit message 里 "skipped X" / "refuted Y" 必须 sync 到路线图。
- **"hot path 数字源不可比"**（#13）：用编译器 / clangd / BOLT 的 PGO benchmark 数字 (+5-15%) 估 SAT solver PGO 收益——**SAT solver 已被 layout 优化过，I-cache 压力远低于 compiler 工作负载**，红利天花板 +2-5%。同类红利在不同工作负载上的天花板要 hot-path-specific 估。

**操作准则强化**：
- 路线图新增的"+N% 综合"类条目必须明示 individual breakdown + stack efficiency 假设
- "X 件套" 类 combined claim 自动触发 audit
- commit "skipped/refuted/NO-OP" message 必须配套 roadmap PR
- ROI claim 用第三方 benchmark 数字时，benchmark 工作负载与目标的 hot-path-similarity 必须显式 argue

## 链 (补连 2026-06-02 全覆盖审计 w5u712m2y)
- [[verification-independent-backstop]] — 别信单一信源/自报数, 必独立 verify (anti-self-trust 三元组)

## 链 (补连 2026-06-02 全覆盖审计 wnyzl1iwk)
- [[research-roi-metric]] — 调研 ROI 配套
