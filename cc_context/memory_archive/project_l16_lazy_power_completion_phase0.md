---
name: l16-lazy-power-completion-phase0
description: "2026-05-17: GPT v11 推荐的 Lazy Power Completion 架构 Phase 0 mini-PoC 实测. Master 端 PASS (skip coverage 留 pole slot, 81.8s OPTIMAL, vs production 30 min UNKNOWN). Completion 端 NO-GO — 第一个 master layout 134/220 powered instance 无可用 pole. 加 loose nogood cut 10 iter 后 uncovered 134→133 (-1) 然后 stuck 7 iter, 同样 5 个 crusher_blue_iron 反复 uncovered. 跟 GPT v11 Plan B trigger 条件 'INFEASIBLE on first layout + UNKNOWN_POWER_CUT_STALL' 完全 match. Plan B 选项待 user 决策: A. Phase 3 deletion-based core (+2-3 day) / B. pose-bool master rewrite (1-2 周) / C. 接受 verdict."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-17 Phase 0 mini-PoC verdict** (commit `5d37321`):

GPT v11 详细计划书推荐 Lazy Power Completion 架构 (master 跳 coverage 留 pole slot + completion subproblem 解电杆 + Benders cut 回灌). Phase 0 mini-PoC 止损 gate 实测.

## 实施 (1 个 Claude day)

- 加 `EXACT_LAZY_POWER_COMPLETION` env flag (PROJECT_LOCK L4b)
- 改 `exact_coordinate_master.build()`: 跳 `_add_geometric_power_coverage_constraints`, 但留 pole slot
- 加 L4a runtime guard: 旧 `EXACT_POWER_PLACEMENT_SUBPROBLEM` 在 certified_exact 模式 raise RuntimeError (forensic test 用 bypass env opt-in)
- 写 `scripts/phase0_lazy_power_completion_probe.py`: probe driver 含 master solve + completion + cut loop

## 数据点

### Master gate: PASS ✓

| 指标 | 实测 | GPT 阈值 |
|---|---|---|
| first solve seconds | **81.8** ✓ | ≤ 90 |
| status | **OPTIMAL** ✓ | OPTIMAL/FEASIBLE |
| vars | 54,616 (GPT 错估 ≤ 26K, pole slot 不算) | ≤ 26K |
| constraints | 126,411 (同上错估) | ≤ 75K |

Master 真信号: solve time. **81s OPTIMAL 远小于 production 30 min UNKNOWN**, 证实 coverage encoding 是真瓶颈 — 跳掉就快.

### Completion gate: NO-GO ✗

| 指标 | 实测 | 阈值 |
|---|---|---|
| status (first layout) | **INFEASIBLE** ✗ | FEASIBLE |
| uncovered instances | **134/220** | 0 |
| build seconds | 0.01 ✓ | ≤ 2 |
| solve seconds | 0.00 ✓ (trivially infeasible) | ≤ 10 |

Master 选 layout 时不带 coverage knowledge, 容易选 134 个 powered facility 在 "所有 coverer 都被非 power 设施占住的位置" — 5 个 `crusher_blue_iron_001..005` 反复 uncovered.

### Cut loop 收敛 test: NO-GO ✗

加 loose nogood cut (禁全 220 powered pose 同时出现) 跑 10 LBBD iter:

| iter | master (s) | uncovered |
|---|---|---|
| 1 | 81.8 | 134 |
| 2 | 91.5 | 134 |
| 3 | 87.0 | **133 (-1)** |
| 4-10 | 88-94 | **133 (stuck 7 iter)** |

总 wall 915s, **0 收敛**. Loose cut 太松 — master 只需 swap 1 pose 就绕开, 但 geometric blocking 立刻 reappear.

## Phase 3 加跑 verdict (2026-05-17 同日)

实施 GPT v11 Plan B Option A: `scripts/phase3_core_minimizer.py` linear deletion-based core minimizer. 算法: 删 instance, oracle (PowerPlacementSubproblem) 验 trial INFEASIBLE → 接受删. Deletion order: powered-first (实测 v1 boundary_port 先删浪费 oracle call - non-powered 删后 layout 仍 INFEASIBLE 不影响 power coverage).

**Trial 4** (powered-first, 300 oracle budget, 60s cap, 6 iter):

| iter | master(s) | completion | uncovered | conflict_set_size |
|---|---|---|---|---|
| 1 | 80.4 | INFEASIBLE | 134 | - |
| 2 | 83.0 | INFEASIBLE | 133 | **6** |
| 3 | 86.6 | INFEASIBLE | 125 | 6 |
| 4 | 81.5 | INFEASIBLE | 133 | 6 |
| 5 | 88.4 | INFEASIBLE | 133 | 6 |
| 6 | 86.5 | INFEASIBLE | 123 | 6 |

**Minimizer 收效**: cut size 220 → 6 (-97%), wall 5.3s. **但 master 加 6-instance cut 仍选 categorically uncoverable layouts, 6 iter 振荡不收敛**.

**根因**: instance-level Benders cut 在 problem geometry 下 doesn't propagate enough information. Master 不带 coverage 选 powered pose 自由度上百万级, 禁 6 instance × pose 组合远远不够. 数学上需要禁 "几何位置不可 cover 的 facility 摆位" 跨所有 instance, 但这是 paradigm-level 改动, GPT v11 explicit reject ("豪猪式约束").

命中 GPT v11 abort 条件: `UNKNOWN_POWER_CUT_STALL: > 6 条 cut 无进展 → abort lazy route`.

**最终 verdict**: ❌ **L16 死路**. master 端方向正确 (skip coverage 81s vs 30 min) 但 cut 端 paradigm 限制 — instance-level Benders 不解决 geometric uncoverable layout.

## Plan B 选项 (Option A 实测死, 剩余两条)

GPT v11 Plan B 决策树 trigger 条件命中:
- "If status is INFEASIBLE on the first layout, Phase 0 no-go"
- "UNKNOWN_POWER_CUT_STALL: > 6 条 cut 无进展"

| Option | 描述 | 工作量 | Risk |
|---|---|---|---|
| ~~A. Phase 3 deletion-based core~~ | ~~+2-3 day~~ | **实测死 ❌** (6 iter 振荡不收敛, instance-level cut 不够) |
| **B. pose-bool exact master rewrite (Plan B1)** | 把 master 从 coordinate-based 改 pose-bool 形式. Step B 数据 (27×15 interior 7.2s FEASIBLE) 支撑 | 1-2 周 | 完整 master pose-bool + port_binding 等 layer 后可能又 stuck |
| **C. 接受 verdict, paradigm 死** | release area=405 best-known (注意非 certified), 或转 L11/改数据 | 0 | 项目目标妥协 |

## Verdict 实质

**L16 不同于 L12-L15**: 前面 4 条是"GPT 方向错估", L16 是 **master 端方向对 (81s OPTIMAL 是 hard evidence), 但 cut 端 instance-level Benders 在 problem geometry 下 fundamental 不够**.

Option A 实测后 L16 确认 **❌ 死路**: 即使 tight cut (cut size 6, -97%) 仍 6 iter 振荡不收敛. 跟 [[highs-rewrite-blocker]] 同根因 — 跟 solver / encoding 选择无关, 是 problem 本身 geometric 结构 + 47 GB 单机 + certified 严格性 的组合 hard.

跟 [[l15-setpacking-prover-dead]] 不同: 那次是 paradigm 攻错层 (set-packing core 不是瓶颈); 这次 master 跳 coverage 真破局 (81s vs 30 min), 但 cut convergence 是新瓶颈.

## 累积 lever verdict

L1-L10 + L12 (v8) + L13 (v10) + L14 (weighted occupancy) + L15 (set-packing prover) + **L16 🟡 (lazy power completion, master 端 OK, cut 端待 Phase 3 验)** = **13 死路 + 1 待定**.

## 归档位置

- `docs/research/phase0_lazy_power_completion_20260517/`
  - `README.md` — verdict + 数据
  - `probe_27x15_anchor22_28.json` — iter 1 数据
  - `probe_27x15_anchor22_28_cutloop.json` — 10 iter 完整
  - `logs/probe_trial1.log`, `logs/probe_trial2_cutloop.log`
- `scripts/phase0_lazy_power_completion_probe.py`
- `src/models/exact_coordinate_master.py` 加 lazy flag + L4a guard (commit `5d37321`)

## 链

- [[l15-setpacking-prover-dead]] — 上一步 paradigm 攻错层
- [lever verdicts](docs/lever_verdicts.md) L16 待加 🟡
- GPT v10/v11 review prompt + 详细计划书 (conversation history)
- `~/linwin_share/zmd_code_v10.zip` (GPT v10 input)
