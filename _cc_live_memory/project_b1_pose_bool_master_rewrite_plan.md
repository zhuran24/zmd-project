---
name: b1-pose-bool-master-rewrite-plan
description: "2026-05-17 用户决策走 B1: pose-bool master rewrite. 在 L16 ❌ (lazy power completion) 死后唯一未试的 paradigm lever. 关键正信号: Step B minimum pose-bool 27×15 interior 7.2s FEASIBLE (vs coordinate-based 30 min UNKNOWN). 首次 verdict 估 3-4 Claude day. 完整 production 6-9 day. Phase 0 + Phase 3 已 commit (5d37321, 202bf09), 现处于 B1 起步前 checkpoint."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## 现状 (2026-05-17 压缩 context 前)

14 条 lever 全 verdict 死 (L1-L10 + L12-L16). 唯一未试 paradigm lever = **B1: pose-bool master rewrite**.

用户授权走 B1. 之前 ROI 自决授权, 但 B1 1-2 周大投资让用户最终拍板.

## B1 是啥

把 exact master 从**coordinate-based** (x, y, mode IntVar + AddNoOverlap2D) 改成**pose-bool** (x_{g,p} ∈ {0,1} + AddAtMostOne per cell).

两种 paradigm 的差别:
- Coordinate-based: 每 slot 有 (x, y, mode) 3 个 IntVar, 用 AddNoOverlap2D 几何约束保证不重叠
- Pose-bool: 每 (group, pose_idx) pair 一个 BoolVar, 用 cell-wise AddAtMostOne 保证不重叠

## 为啥试 B1

**关键正信号** (Step B 实测):
- 27×15 corner anchor minimum pose-bool: 2.4s INFEASIBLE (CP-SAT propagator 立即)
- 27×15 interior anchor (22,28) minimum pose-bool: 8 worker 7.2s **FEASIBLE** 12K branch
- 对比 coordinate-based 同 anchor master: 30 min UNKNOWN

**含义**: pose-bool 形式让 CP-SAT cell-exclusivity propagator 直接 fire, 不依赖 AddNoOverlap2D (CP-SAT 在 dense packing 弱).

## 关键 entry points (在 src/)

### 现 coordinate-based 入口
- `src/models/master_model.py:2418` `MasterPlacementModel.build_exact_core` — 主入口
- `src/models/master_model.py:2504` `from_exact_core` — overlay
- `src/models/exact_coordinate_master.py:3010` `CoordinateExactMasterDelegate.build()` — 现 build path
  - `_create_mandatory_slot_vars` — coordinate slot vars
  - `_create_required_optional_slot_vars`
  - `_create_residual_optional_slot_vars`
  - `_create_power_pole_slot_vars`
  - `AddNoOverlap2D(_core_x_intervals, _core_y_intervals)` ← 几何不重叠
  - `_add_ghost_constraints`
  - `_add_geometric_power_coverage_constraints` ← bottleneck, L16 lazy 已 skip 选项
- `src/models/exact_coordinate_master.py:6548` `add_benders_cut` — Benders cut API
- `src/models/exact_coordinate_master.py:5327` `_add_geometric_power_coverage_constraints`

### Step B pose-bool 参考实现 (可复用)
- `docs/research/setpacking_prover_poc_20260517/poc_minimum_setpacking.py` — minimum pose-bool 实现, ~150 LOC
- 关键 code 段:
  - `x_vars[(gi, pi)] = model.NewBoolVar(f"x_{gi}_{pi}")` — pose-bool vars
  - `model.Add(sum(group_vars) == g["demand"])` — demand
  - `model.AddAtMostOne(vars_in_cell)` — cell exclusivity

### Verdict 验证 (复用 Phase 0/3 工具)
- `scripts/phase0_lazy_power_completion_probe.py` — probe driver, 改 master entry 即可
- `scripts/phase3_core_minimizer.py` — deletion-based core (B1 也许不需要, 因 master 自身带 coverage)

## B1 实施 Plan (Claude pace 估时)

**Phase 1: 重写 master core** (2-3 day)
- 新建 `src/models/pose_bool_master.py` 或扩展 `master_model.py` 加新 representation
- 实现 pose-bool 形式: vars + demand + cell exclusivity + ghost forbid
- master_representation 字段从 "pose_bool_v1" (已有 placeholder) 改成真实
- 保留 coordinate-based 作 fallback / regression baseline

**Phase 2: 适配各 layer** (2-3 day, 每 layer 0.5-1 day)
- `port_binding`: input/output port matching in pose-bool 形式
- `boundary_port_feasibility`: boundary 设施约束
- `power_coverage`: 用 pose-bool 形式或继续 lazy completion (L16 master 端 OK 部分可复用)
- `exact_safe_cuts`: cut family 适配
- `symmetry_breaking`: pose-bool 形式的 symmetry

**Phase 3: 适配 extract_solution + Benders cut replay** (0.5-1 day)
- pose-bool → solution dict 转换
- add_benders_cut 用 pose-bool literals

**Phase 4: 测试 + regression** (1-2 day)
- 全套 pytest (现 108 core + 2086 full)
- 对 27×15 已知 feasible 验证 master 仍能找
- 现 v4 proof object lifecycle 不能 break

**Phase 5: 首次 verdict trial** (0.5 day)
- 跑 27×15 anchor (22,28) master.solve, 期望 < 30s OPTIMAL (类比 Step B 7s)
- 若 OK, 跑多 anchor + 大 candidate 验稳定性

## Go / no-go checkpoint

**Phase 5 verdict trial 数据决定 B1 死活**:
- ✓ Go: 27×15 anchor master.solve < 60s + feasible across multiple anchors
- ✗ No-go: 仍 30 min UNKNOWN (说明 port_binding / boundary_port 等 layer 加上后又 stuck, 同 master+coverage 同根因)

## Risk + caveat

**Step B 7s 是 minimum (无 port_binding/boundary_port/power_coverage)**. 加完整 master layers 后, 大概率会有部分 stuck. Phase 5 verdict 是关键真理时刻.

**5 连 lever 死的 base rate** 提示 P(B1 succeed) 可能 < 50%. 但 Step B 是 hard evidence, 不是凭空赌.

如果 B1 也死 (L17 ❌):
- 项目下一步: 接受 verdict, release area=405 best-known (非 certified), 或换 paradigm shift / 接受 strictness sacrifice (L11, 用户拒绝过) / 改数据扩 blueprint

## 当前 commit 状态

- `905a64d` Step D power_coverage 锁瓶颈
- `bad3a9c` L15 set-packing prover ❌
- `5d37321` Phase 0 + Lazy Power Completion 加 flag (L4a/L4b 边界)
- `b40bbe9` lever_verdicts L16 加入 🟡
- `202bf09` Phase 3 minimizer + tight cut ❌ L16 终态

Working tree clean. B1 起步前 checkpoint.

## 跟之前 lever 区别

| Lever | 死法 |
|---|---|
| L12-L15 | GPT 方向错估 (算法/前提/数学能力/paradigm 攻错层) |
| L16 | master 端 OK (81s OPTIMAL), cut 端 instance-level Benders 不够 |
| **B1 (未试)** | **paradigm 改 representation, 不是 GPT 推, 是用户基于 Step B 数据自己决定** |

## 接续

下次 session 进来直接:
1. 读这条 + [[l16-lazy-power-completion-phase0]] 跟上 context
2. 开始 Phase 1: 重写 master core
3. Step B PoC script 是关键 reference

## 链

- [[l16-lazy-power-completion-phase0]] — L16 完整 verdict
- [[l15-setpacking-prover-dead]] — L15 paradigm 攻错层 → Step B 数据来源
- [[30gb-real-culprit-power-coverage]] — power_coverage 是真大头 (Step D + RAM)
- [[highs-rewrite-blocker]] — 重写路径同根因警示
- [[work-time-estimates]] — Claude pace 估时不打人类 buffer
- `docs/lever_verdicts.md` — 14 条 lever 完整表
- `docs/research/setpacking_prover_poc_20260517/poc_minimum_setpacking.py` — Step B PoC 实现
- `docs/research/phase0_lazy_power_completion_20260517/` — Phase 0/3 完整数据归档
