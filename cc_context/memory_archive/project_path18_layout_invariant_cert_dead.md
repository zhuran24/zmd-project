---
name: path18-layout-invariant-cert-dead
description: "Path 18 (independent Claude brainstorm) Layout-invariant cert Phase 0 实测 NO-GO: m1=2 (target ≥100) — cell-front pattern 几乎决定 pose, cut lift 等同 pose-pair 不跨数量级"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-20 commit 65c9da6: 24 lever 全 verdict 死后用户 /goal 走两条 Phase 0 并行 cheap gate. **独立 Claude opus 不见 GPT v12 方案 brainstorm 出的方向 I "Layout-invariant infeasibility certificate from subproblem"** —— 攻 cut 强度而非 cut form / master form, 从 subproblem reject 信号反推 cell-front pattern 等价类, cut lift 到 cell-front 层而非 pose-tuple 层.

## Phase 0 实测 (anchor 22,28 27×15, B1 pose-bool master)

| metric | 实测 | threshold | 判定 |
|---|---|---|---|
| m1 equivalence class size (lower bound) | **2** | ≥ 100 | ❌ |
| m2 clone master solve | 60.3s | ≤ 60s | 🟡 边界 |
| m3 clone status | **UNKNOWN** | ≠ UNKNOWN | ❌ |
| m4 oracle consistency (binding) | 0/5 reject (5/5 FEASIBLE) | ≥ 3/5 reject | ❌ |

L₀ extracted: 296 instances, |occupied_cells|=3669, |active_ports|=1810.
m1 per-instance multiplicities: min=1 max=2 mean=1.74.

## Why dead (核心 finding)

Cell-front pattern P(L₀) 几乎决定 pose —— 每个 instance 平均只有 1.74 个 alternative pose 落同 P. Cut lift 到 cell-front 层强度 = lift 到 pose-pair 层, 没有跨数量级. 这正是独立 Claude 自己 Phase 0 self-flag 的最高风险 (前提错估 / failure mode #1: cell-front 决定 pose).

m4 数据有 nuance: probe 只跑 `PortBindingModel.solve()` 没跑 routing precheck. 5/5 binding FEASIBLE 跟 L₀ 同质 (B1 Phase 2 已证 master OPTIMAL + binding FEASIBLE, 死在 routing precheck 那一层). 不证 hypothesis 假, 只证 binding 不是 24 lever 死症的真 oracle.

## Why 1 day 杀完是 cheap gate 成功 design

独立 Claude 在 brainstorm 时把 Phase 0 GO 设为 atomic measurement: m1 一个 number 决定生死. 1 day 实测 m1=2 即可 verdict, 不需要 Phase 1-N 投资. 这是 Phase 0 cheap gate workflow 模板 ([[paradigm-phase0-cheap-gate]]) 的标准应用.

## Verdict

**第 25 lever 死**. Path 18 (Layout-invariant cert) 进 dead lever list. infrastructure (CellFrontPattern dataclass + clone master construction + m1 instance-multiplicity-lowerbound) 留作 future reference.

Commit 65c9da6 (probe land) + Phase 0 NO-GO verdict 2026-05-20 ~12:40.

## 跟 GPT v12 方案对比 (independent vs GPT)

GPT v12 给的 4 个 alive 候选 (IHS / Benders symmetry / CDCL warm-start / Column generation) 跟 Path 18 完全不撞 — 独立 brainstorm 选了不同攻击层. Path 18 ❌ verdict 让 next step pickup GPT lever 26 (Benders symmetry) 或 candidate C (Column generation) 主投资. 见 [[lever26-benders-symmetry-dead]] (lever 26 已 verdict 死).
