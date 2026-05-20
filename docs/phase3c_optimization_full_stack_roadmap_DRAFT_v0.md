# Phase 3C — Optimization Full-Stack Roadmap

**Status:** Draft 2026-05-08
**Source decision:** 用户 2026-05-08 战略决策，问题规模会持续指数膨胀（70×70 → 80×80，1.0 → 1.2 流水线复杂度 2-3×），单一优化方向不足，必须 stack 所有可能的性能提升手段。

---

## 0. 背景：为什么必须 stack 所有方案

### 问题规模膨胀预测

| 维度 | 1.0 + 70×70（当前） | 1.2 + 80×80（预期） | 增长 |
|------|------------------|------------------|------|
| 网格单元数 | 4900 | 6400 | 1.31× |
| 流水线复杂度 | 1× | 2-3× | 2-3× |
| 强制设施数（估算） | 266 | 500-800 | 2-3× |
| 决策变量数 | ~10 万 | ~30-50 万 | 3-5× |
| **CP-SAT 搜索空间** | 现状 | **指数膨胀** | **10-100×** |

CP-SAT 求解时间和搜索空间是多项式甚至指数关系。问题规模 4× 可能意味着实际求解时间 50-500×。

### 关键认知

之前判断方案 D（换求解器）"风险高、破坏 proof source lock"——这个推理有问题。Proof source 是 `canonical_rules.json` 等数据，不是求解器本身。**当问题大到现有求解器根本得不出 proof 时，lock 失去意义**。

---

## 1. 五件套优化框架（A B C D E）

### A — Solution Hint 跨次持久化

**性质：** 跨进程复用**好**的部分解
**机制：** 每次 solver 跑出 feasible 部分解（即使最终 UNKNOWN），保存到 campaign state；下次 resume 时通过 `AddHint` 喂给 master CP-SAT
**工时：** 1-2 天
**风险：** 低（OR-Tools 官方机制）
**适用范围：** 至少找到过 FEASIBLE 部分解的候选
**对当前 8 个 RUNNING 硬候选的帮助：** 有限——它们都还没找到任何部分解

### B — 长 Budget + 单候选优先调度

**性质：** 让 solver 一次跑足够久
**机制：** 改 frontier 选择策略，给单个硬候选分配 30-60 min 时间预算，配合 1 GiB memory guardian 阈值
**工时：** 半天
**风险：** 低（只改调度，不动求解逻辑）
**适用范围：** 所有硬候选
**前提：** 需要内存够（48 GiB 现在 4 进程并发吃 ~38 GiB；改单候选 30 min，1 进程可能能跑到 ~45 GiB 物理上限）

### C — Clause Mining + Nogood 注入

**性质：** 跨次禁掉**坏**的部分解（CP-SAT 不让导出 learned clauses，那就从产物里挖）
**机制三种**：
1. **Benders cut 持久化**：master 方案被 binding/routing/flow 否决 → 存到 campaign state → 下次自动加 constraint 禁掉
2. **Solver 日志解析**：解析 CP-SAT verbose log 里的 conflict 信息，转成 boolean clauses
3. **失败模式聚类**：100 次失败 attempts 做特征聚类，提取"反模式"

**工时：** 1-2 周
**风险：** 中（要改证明语义但保持等价）
**适用范围：** 包括 UNKNOWN 候选——有失败信息就能挖
**对当前 8 个 RUNNING 硬候选的帮助：** **比 A 更关键**——它们的 100 次失败里全是可挖的信息

### D — 切换求解器：CaDiCaL/IPASIR 持久 Learned Clauses

**性质：** 让 solver 直接保留 learned clauses
**机制：** CaDiCaL 通过 Learner API 支持 export/import learned clauses，IPASIR 是行业接口标准
**工时：** 1-3 月
**风险：** 高
- 要把 CP 模型转成纯 CNF（PySAT 等库可用）
- 验证转换前后语义等价（要新一轮 Repair 级审查）
- 重新实现 Benders 分解
**收益：** 真正的"跨次完整学习记忆"，理论最大
**触发条件：** 1.2 + 80×80 内容上线后，A+B+C+E 仍然不够

### E — AI Ranker 跨问题实例学习

**性质：** 用 ML 在不同问题实例之间迁移知识
**机制：** S9-S12 已规划好的路径
- S9：候选排序 ranker（rule-based → LR/RF → LightGBM）
- S10：Order-only shadow（dry-run 验证）
- S11：A/B 实测（受控场景）
- S12：CP-SAT hint 注入（hint，不是 constraint）

**工时：** 持续，看数据积累速度
**风险：** 中（受 AI 安全合同约束，order_only/hint_only，不动证明）
**特殊价值：** 70×70 学到的能助力 80×80——A/B/C/D 都是单实例内优化，**只有 E 能跨问题实例**

---

## 2. 加成关系矩阵（为什么必须全上）

```
       │  A   │  B   │  C   │  D   │  E   │
───────┼──────┼──────┼──────┼──────┼──────┤
   A   │  -   │  +   │  +   │  +   │  +   │
   B   │  +   │  -   │ ++   │ ++   │  +   │
   C   │  +   │ ++   │  -   │  ?   │ ++   │
   D   │  +   │ ++   │  ?   │  -   │  +   │
   E   │  +   │  +   │ ++   │  +   │  -   │
───────┴──────┴──────┴──────┴──────┴──────┘
+  = 加成
++ = 强加成
?  = D 来了 C 的部分功能可能并入 D（CaDiCaL 已经能保留 clauses）
```

关键加成路径：
- **A → B**：A 给 B 提供 warm-start，30 min 跑得更深
- **B → C**：B 跑得久，挖出更多失败模式给 C 用
- **C → E**：C 的反模式数据是 E 的训练特征
- **E → A**：E 学到的"哪种 hint 有效"反过来精化 A
- **D → 所有**：D 取代了 A+C 的部分功能，但 B+E 仍需要

---

## 3. 实施优先级

### Phase 3C-1（立即，4 周内）

| 步骤 | 内容 | 验收 |
|------|------|------|
| **1.1** | A 实现：solution hint 持久化 | 至少 1 个候选 warm-start 后 wall_time 降 20%+ |
| **1.2** | B 实现：单候选 30 min budget 模式 | 至少 1 个硬候选 30-min 跑出 INFEASIBLE/FEASIBLE 终态 |
| **1.3** | 积累循环继续跑（收数据给 C/E） | 至少 100 个候选样本 |

### Phase 3C-2（1-2 月）

| 步骤 | 内容 | 验收 |
|------|------|------|
| **2.1** | C 实现：Benders cut 持久化（最直接） | 同候选 resume 后 attempts 数下降 30%+ |
| **2.2** | C 实现：solver 日志 conflict 解析 | 提取出可重用 boolean clauses 数 ≥ 100 |
| **2.3** | E 实现：S9 ranker 训练（用 100+ 样本） | offline replay 的 baseline_normalized_score ≥ 1.20 |

### Phase 3C-3（2-4 月，可选）

| 步骤 | 内容 | 触发条件 |
|------|------|--------|
| **3.1** | D POC：用 CaDiCaL 跑某个 70×70 候选 | A+B+C+E 后某些候选仍然 ≥1 小时不出结果 |
| **3.2** | D 全量评估：CP→CNF 转换语义等价证明 | POC 显示有效 |
| **3.3** | D 集成：与 Benders 框架对接 | 等价性证明通过 |

### Phase 3C-4（4-6 月）

| 步骤 | 内容 | 触发条件 |
|------|------|--------|
| **4.1** | 80×80 适配（数据预处理升级） | 1.2 版本上线 |
| **4.2** | E 二代：基于 80×80 数据继续训练 | 80×80 数据 ≥ 100 样本 |

---

## 4. 不在路线图里但要监控的方向

- **硬件升级**：64GB+ DDR5 内存条价格回落（2026 下半年预测）
- **Linux 迁移**：Linux 基线内存比 Windows 少 ~10 GiB，相当于直接给 solver 增容
- **新版 OR-Tools**：Google 可能在未来版本加 incremental solving API（已有 issue #2014），届时 D 复杂度大幅下降

---

## 5. 验证与安全约束

每个新方案上线必须：
1. 通过 `scripts/preflight_gate.py` 的 5 项检查
2. 86+ tests 全过
3. 不修改 frozen artifacts（canonical_rules.json 等 4 个）
4. AI 部分严格遵守 AI 安全合同（order_only / hint_only / 不动证明）
5. 加新方案要通过等价性测试：相同输入产生相同终态

特别地：
- **C 的 nogood 注入**：必须证明注入的 nogood 在数学上是当前模型的逻辑后承
- **D 的求解器切换**：必须通过新一轮 Repair 级审查才能进生产
- **B 的长 budget**：不影响最终 168h 生产 run 的预算分配
