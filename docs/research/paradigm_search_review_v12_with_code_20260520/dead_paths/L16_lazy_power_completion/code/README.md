# Phase 0 mini-PoC verdict — Lazy Power Completion v1

GPT v11 提的 Lazy Power Completion 架构 (master 跳 coverage 留 pole slot + completion subproblem 解电杆) 的 Phase 0 止损 gate 实测.

## TL;DR

**❌ Phase 0 NO-GO**. Master gate PASS (81s OPTIMAL, 远小于 30 min UNKNOWN), 但 completion gate FAIL — 第一个 master layout 134/220 powered instance 无 pole 可覆盖. 加 loose nogood cut 跑 10 iter, uncovered 仅从 134 → 133 (-1) 然后 **stuck 7 iter 不动**. 同样 5 个 `crusher_blue_iron_001..005` 反复 uncovered.

跟 GPT v11 计划书 Plan B trigger 一致: "If status is INFEASIBLE on the first layout, Phase 0 no-go".

## 数据

### Master gate (PASS)

| 指标 | 阈值 | 实测 |
|---|---|---|
| first solve seconds | ≤ 90 | **81.8** ✓ |
| status | OPTIMAL/FEASIBLE | **OPTIMAL** ✓ |
| vars | ≤ 26,000 (GPT) | 54,616 ✗ (但 GPT 没算 pole slot, 实际 baseline 调整) |
| constraints | ≤ 75,000 (GPT) | 126,411 ✗ (同上) |

**Master solve speed 是真信号** — 81s OPTIMAL vs current production 30 min UNKNOWN. 证明 `_add_geometric_power_coverage_constraints` 确实是瓶颈, 跳了就快.

GPT v11 计划书的 var 阈值 26,000 错估了 — 假设 Step D `skip_power_coverage=True` (24,824 vars) 已含 pole slot. 实测 skip_power 模式 `_calculate_power_pole_slot_upper_bound` 早退, pole slot 不创建; lazy 模式必须留 pole slot, +30K vars 是必然的. 真信号是 solve time.

### Completion gate (NO-GO)

| 指标 | 阈值 | 实测 |
|---|---|---|
| status (first layout) | FEASIBLE | **INFEASIBLE** ✗ |
| uncovered instances | 0 | **134/220** |
| build seconds | ≤ 2 | 0.01 ✓ |
| solve seconds | ≤ 10 | 0.00 ✓ (trivially infeasible) |

### Cut loop convergence test (NO-GO)

加 loose nogood cut (禁全 220 powered pose 同时出现), 跑 10 LBBD iter:

| iter | master (s) | completion | uncovered |
|---|---|---|---|
| 1 | 81.8 | INFEASIBLE | 134 |
| 2 | 91.5 | INFEASIBLE | 134 |
| 3 | 87.0 | INFEASIBLE | **133** |
| 4 | 88.5 | INFEASIBLE | 133 |
| 5 | 90.8 | INFEASIBLE | 133 |
| 6 | 88.7 | INFEASIBLE | 133 |
| 7 | 92.0 | INFEASIBLE | 133 |
| 8 | 91.6 | INFEASIBLE | 133 |
| 9 | 94.5 | INFEASIBLE | 133 |
| 10 | 94.2 | INFEASIBLE | 133 |

10 iter, 总 wall 915s ≈ 15 min, **0 收敛**. 同样 5 个 `crusher_blue_iron_001..005` 反复 uncovered.

## 根因分析

Loose cut "禁全 220 pose 同时出现" 太松 — master 只需 swap 1 pose 即可绕开. 但 problem geometry 让大部分非 power 设施摆位都会 block 同一批 crusher 的可达 pole. 单点 swap 不破局.

GPT v11 计划书 Phase 3 "deletion-based core minimization" 设计的初衷正是解决这个 — 不禁全 220, 而是用 oracle 反向缩小 core 找出**关键 blocker subset** (~5-20 个 instance), tight cut 一次 prune 大块 search space.

但 deletion-based core 是 Phase 3 工作 (+2-3 Claude day), 且 GPT v11 自己 caveat 列了:
> 阈值: 同一 candidate anchor 下: > 6 条 full-layout power infeasible cut: 立刻启用 bounded deletion core; > 6 条且没进展: abort lazy route for this candidate, status UNKNOWN_POWER_CUT_STALL

实测 10 iter 0 进展, 完全 match **UNKNOWN_POWER_CUT_STALL** abort 条件.

## Phase 3 加跑: deletion-based core minimizer (tight cut)

GPT v11 Plan B Option A 实施 (`scripts/phase3_core_minimizer.py`, ~130 LOC).

### Minimizer 算法
- Linear deletion: 删 instance, oracle 验 trial INFEASIBLE → 接受删
- Deletion order v2: powered-first (实测 v1 boundary_port 先删浪费 oracle call, 因为 non-powered 删后 layout 仍 INFEASIBLE - 不影响 power coverage)
- Budget: 300 oracle calls × ≤10s each, 总 ≤60s

### Trial 4 数据 (powered-first, 6 iter)

| iter | master (s) | completion | uncovered | conflict_set_size |
|---|---|---|---|---|
| 1 | 80.4 | INFEASIBLE | 134 | - (no cut) |
| 2 | 83.0 | INFEASIBLE | 133 | **6** (minimized) |
| 3 | 86.6 | INFEASIBLE | 125 | 6 |
| 4 | 81.5 | INFEASIBLE | 133 | 6 |
| 5 | 88.4 | INFEASIBLE | 133 | 6 |
| 6 | 86.5 | INFEASIBLE | 123 | 6 |

Minimizer 收效: cut size 220 → **6** (-97%), wall 5.3s 267 oracle calls. **但 master 加 6-instance cut 仍选 categorically uncoverable layout, 6 iter uncovered 134→123, 振荡不收敛**.

### 根因 — instance-level cut 解决不了

master 不带 coverage 时选 powered facility pose 完全自由, 6-instance cut 只能禁特定 (instance_id, pose_idx) 6-tuple. master 换其他 instance 或换 pose_idx 都可绕开. Tight cut 一次 prune 6 自由度, 但 master 自由度上百万级, 远不够.

数学上, 真正需要禁的是 **几何位置上不可 cover 的 facility 摆位**, 跟 instance 身份无关. 现 Benders cut 在 instance × pose 维度做, 不在 几何位置 维度.

GPT v11 计划书 explicit reject 了 "lazy 加 coverage row 到 master" 方向, 而 instance-level Benders cut 在 problem geometry 下 doesn't propagate enough information.

### Verdict 触发 GPT v11 abort 条件

> 阈值: 同一 candidate anchor 下: > 6 条 full-layout power infeasible cut: 立刻启用 bounded deletion core; > 6 条且没进展: abort lazy route for this candidate, status UNKNOWN_POWER_CUT_STALL

实测命中: tight cut 6 iter 0 收敛 → **UNKNOWN_POWER_CUT_STALL → abort**.

**L16 verdict: ❌ 死路**.

---

## Verdict 选项

按 GPT v11 Plan B 决策树:

### Option A: 投资 Phase 3 deletion-based core (+2-3 day)

- 替换 loose 220-pose cut 为 tight ≤20-instance core cut
- Hope: tight cut 一次 prune 大块 search space, 5-10 iter 内收敛
- Risk: tight cut 也可能爆炸 cut 数量 (combinatorial uncoverable layouts), 仍 UNKNOWN_POWER_CUT_STALL
- 工作量: oracle 32× call × 10s = 320s budget per master iter, 加上 minimization 算法 ~300-500 LOC

### Option B: 转 Plan B1 — pose-bool exact master rewrite (1-2 周)

- 基于 Step B 数据 (27×15 interior pose-bool 7.2s FEASIBLE)
- 把 master 重写成 pose-bool 形式 (跟 coordinate-based 不一样)
- 工作量大 (1-2 周), 但 Step B 7s 是 hard evidence "pose-bool form 不 stuck"
- Risk: 完整 master pose-bool 形式可能加 port_binding 等 layer 后又 stuck

### Option C: 接受 Phase 0 verdict, 转 paradigm shift / 接受现状

- L11 牺牲严格性 (用户拒绝)
- 改数据扩 blueprint (1-2 周, ROI 未知)
- 接受 verdict, release area=405 best-known (注意 GPT 提醒: 这不是 certified, 是 exploratory/UNPROVEN)

## 操作记录

- `scripts/phase0_lazy_power_completion_probe.py` — probe driver, 含 master solve + completion + cut loop
- `src/models/exact_coordinate_master.py` 加 `_lazy_power_completion_enabled()` + build() 跳 coverage 留 pole slot + 旧 L4 flag certified mode raise
- 实测 commit 在 main branch (无单独 worktree)
- 总 PoC wall: ~25 min (含 build + 10 iter solve)
- 数据归档: `probe_27x15_anchor22_28.json` (iter 1) + `probe_27x15_anchor22_28_cutloop.json` (10 iter)

## 跟前面 lever 对比

| lever | 类型 | verdict |
|---|---|---|
| L12 v8 anchor slicing | 算法错估 | ❌ |
| L13 v10 witness preflight | 前提错估 | ❌ |
| L14 weighted occupancy | 数学能力上限 | ❌ |
| L15 set-packing prover | paradigm 攻错层 | ❌ |
| **L16 lazy power completion** | **cut 收敛速度** | **❌ (loose cut), 待验证 tight cut** |

L16 跟前面不一样的地方: master 端 paradigm 是对的 (skip coverage 让 master 解得动), 死的是 cut 端 — loose cut 不够 tight, 需要 deletion core 工作量 (+2-3 day). 如果 deletion core 也救不了, 是 paradigm 死, 不是 GPT 推荐方向错.

## 链

- [[project_l15_setpacking_prover_dead]] — 上一步 paradigm 攻错层
- [[lever_verdicts]] L16 待加 ❌
- GPT v10 review package `~/linwin_share/zmd_code_v10.zip`
- GPT v11 review prompt + GPT 详细计划书 (in conversation)
