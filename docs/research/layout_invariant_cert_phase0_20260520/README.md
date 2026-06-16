# LIC Phase 0 — Layout-Invariant Cert cheap-gate

**Date**: 2026-05-20  
**Status**: probe written + dry-run pass; measurement run pending  
**Lever**: candidate Path 18 (independent brainstorm, not from GPT review)

## TL;DR

24 个 lever 全 verdict 死的共同 pattern：master 每 iter OPTIMAL 选新 layout L_i，
subproblem reject，cut 翻译回 master 只能 ban (instance, pose) tuple ——
core size = 1 退化。所有 6 个 paradigm（RAB-SEP / SAC-Hull / PCR-CUT / D2
commodity / cell-cut / lazy demand）cut 都是 **layout-specific**。

**没人尝试过**：构造 routing-physics-grounded **but layout-independent**
的 cut。subproblem reject 信号是 "front_blocked 500-610 ports" —— 这是
cell-front 物理事实。若能从 subproblem 反推 "**这种 cell-front 几何形态**
无论 facility 选哪些 pose 都 routing-infeasible"，则 cut "这种 cell-front
pattern 全 ban" 强度跨数量级。

**Phase 0 hypothesis**：固定 B1 anchor (22,28) 27×15 OPTIMAL layout L₀ 的
**cell-front pattern P(L₀)**，枚举有多少其它 pose tuple 落同一 P(L₀)。
等价类大则 cut 强度跨数量级 (GO)，等价类小则 cut 退化回 pose no-good
跟 Path 17 D2 同质死 (NO-GO)。

## 核心 hypothesis 形式化

L₀ 是 master 出来的 OPTIMAL layout（266 instance → 各占一 pose）。
P(L) 是 layout L 的几何摘要：

- `occupied_cells` ⊂ grid：所有被 facility 占的 cell
- `active_ports` ⊂ grid × {N,S,E,W}：所有出现的 (input/output) port 的 (cell, direction)

P 抽掉的信息：**哪个 instance 占哪个 cell / 哪个 facility 模板提供哪个 port**。
只保留 "几何形态"。

**Hypothesis H₀**：若 L₁, L₂ 满足 P(L₁) = P(L₂)，则 binding/routing
subproblem 对 L₁ 和 L₂ verdict 相同 —— 因为 binding 决策只看 port 位置
+ 方向 + cell 占用，不看 facility 类型。

若 H₀ true，则 lift cut 到 P(·) 层是 sound 的。等价类 |{L : P(L) = P(L₀)}|
= 等价类大小，决定 cut 强度。

## Metrics

| 指标 | 含义 | 方法 |
|---|---|---|
| **m1** | pose tuple equivalence class size (lower bound) | per-instance multiplicity max（保守下界，see m1_method） |
| **m2** | clone master solve wall-time (seconds) | build standard B1 pose-bool master + 注入 cell-front pattern coverage 约束，cap 60s |
| **m3** | clone master status | OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN |
| **m4** | oracle consistency rate | 从等价类抽 5 个 alternative pose tuple 跑 `PortBindingModel.solve()`，count INFEASIBLE / 总数 |

### Clone master 构造（关键决策点）

不写新 master class；复用 `PoseBoolExactMasterDelegate` build 完后**额外**
注入：

```
对每个 (px, py, dir) ∈ pattern.active_ports:
    sum(pose_var for pose 提供 port at (px,py,dir)) >= 1

对每个 (cx, cy) ∈ pattern.occupied_cells:
    sum(pose_var for pose 占 cell (cx,cy)) >= 1
```

`_build_global_pose_cache` 已经索引好 `_poses_by_port_cell_dir_global` 和
`_poses_by_cell_global`，直接遍历即可。**不改 src**：约束注入是 probe-internal
对 `clone.model.Add(...)` 的调用，等价于在 model 外加约束。

cell exclusivity (`AddAtMostOne`) 已由 standard build 加上，"≥1" + "≤1" =
"=1"，所以 pattern.occupied_cells 是 exact cover；pattern.active_ports 则
"至少一个 pose 提供" + cell exclusivity 保证那个 pose 唯一。

### Cell-front pattern 怎么 encode（关键决策点）

`extract_solution` 出来的 placement_solution 里，`pose_idx` 指向
`facility_pools[tpl][pose_idx]`，pose 数据里 `occupied_cells` /
`input_port_cells` / `output_port_cells` 是 **GLOBAL 坐标**（不加 anchor 偏移
— 经验自 `pose_bool_exact_master.py:830` `_build_global_pose_cache` 注释 +
`extract_solution:660-705` 直接 dict-copy anchor 不加和）。所以
`CellFrontPattern.occupied_cells = ⋃ pose.occupied_cells` 和
`active_ports = ⋃ (p.x, p.y, p.dir)` 直接是 global 坐标，跟 `_poses_by_*_global`
cache 同 frame 配对。

## GO / NO-GO threshold

- **GO**：`m1 ≥ 100` AND `m2 ≤ 60s` AND `m4 = 5/5 reject` AND `m3 ≠ UNKNOWN`
- **NO-GO**：`m1 < 10` OR `m2 > 300s` OR `m4 ≤ 3/5` OR `m3 = UNKNOWN`
- **PARTIAL**：中间状态（10 ≤ m1 < 100，等等）— 继续审，不直接 verdict

## 怎么跑

```bash
# 1) dry-run 验 import / API resolution （已 pass）
.venv/bin/python docs/research/layout_invariant_cert_phase0_20260520/phase0_probe.py --dry-run

# 2) measurement run （后台跑, 估 5-10 min）
nohup .venv/bin/python docs/research/layout_invariant_cert_phase0_20260520/phase0_probe.py \
    > docs/research/layout_invariant_cert_phase0_20260520/phase0_probe.log 2>&1 &

# 3) 跑完看结果
cat docs/research/layout_invariant_cert_phase0_20260520/phase0_results.json
```

默认 anchor (22,28) 27×15，跟 B1 Phase 5 / Path 17 D2 / PCR-CUT 同一 anchor，
方便对照。

## 风险 / 失败模式 (5)

1. **H₀ false（即 P-equivalence 不蕴含 subproblem 同 verdict）**：
   m4 reject rate 不到 5/5，paradigm sound 性破产。
   - 缓解：m4 直接量化这个；若 ≤ 3/5，verdict NO-GO 立刻退。

2. **等价类太小（m1 < 10）**：cell-front pattern 几乎决定 pose tuple，cut
   lift 后跟 pose no-good 同质，跟 Path 17 D2 同质死。
   - 这是 *最可能* 的失败模式 —— mandatory pool 里若每 (cells, port-set)
     signature 都只对应 1-2 pose（典型 facility 1 个 instance 占 1 个 pose），
     等价类 = 1。

3. **m1 大但 m4 reject 不全**：等价类大却 routing-affecting 信息不在
   cell-front pattern 里（例如 mandatory facility 操作类型决定哪些 port 是 input
   / output，但 pattern 只记 (cell, dir) 不区分 in/out）。
   - 缓解：probe 把 input/output port 合并算 active port（最宽松）。若 m4
     破产，下版本 extension 区分 in/out 再测。

4. **clone master 撞 UNKNOWN（m3=UNKNOWN）**：cell-front coverage 约束让
   model 比 base B1 难解。
   - 缓解：clone time limit 60s 但 measurement run 可调大；m3 = UNKNOWN
     不等于 paradigm 死，只是 Phase 0 量化不出来 — 标 PARTIAL 走 Phase 1。

5. **B1 master 30 min UNKNOWN（base 都解不出）**：Phase 0 step 1 卡在
   master.solve，没 L₀ 也就没后续。
   - 缓解：Phase 5 production trial 已实测 27×15 (22,28) 53s OPTIMAL；这个
     anchor 是已知 fast verdict 入口。

## 关键不确定性 / debt

- m1 用 per-instance multiplicity max 作 lower bound（保守）。真等价类
  size 需 clone master enum 全 solution，不在 Phase 0 scope。若 m1 lower
  bound 已 ≥ 100，paradigm 信号强；若 ≤ 10，下界足以 verdict NO-GO。
- m4 sampling 用 single-instance-switch（保 cell exclusivity 不破）。
  k-instance-switch (k≥2) 更激进的 alternative pose tuple 留 Phase 1 探索。

## 跟既有 paradigm 区别

| paradigm | cut 层 | core size 退化? | 强度 |
|---|---|---|---|
| RAB-SEP | (owner, blocker) conjunction | yes | per-layout |
| SAC-Hull | (sep, commodity, capacity) | no but necessary≠sufficient | per-layout violation |
| PCR-CUT | patch-belt instance-pose no-good | yes | per-layout |
| Path 17 D2 | commodity cell-flow violation | size=1 | per-layout |
| **LIC (this)** | **cell-front pattern** | **若 m1 ≥ 100 则 size >>1** | **layout-invariant** |

## 不读

`docs/research/paradigm_search_review_v12_*` 和 `~/linwin_share/paradigm_search_review_v12_*`
是 GPT v12 review 给的方案 —— 本 Phase 0 是 *独立* brainstorm，不读避免污染
实现思路。

## 文件清单

- `phase0_probe.py` (~440 LOC) — probe 实现，支持 `--dry-run`
- `phase0_results.json` — 跑完结果（dry-run 写一次 placeholder）
- `phase0_probe.log` — measurement run 输出（measurement run 后产）
- `README.md` (本文件)
