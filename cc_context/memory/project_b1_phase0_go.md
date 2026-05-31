---
name: b1-phase0-go
description: "2026-05-17: B1 Phase 0 prototype 实测 GO ✅ — pose-bool form 加 power_coverage 一次性可解, 5 anchor 全 fast verdict (49-53s OPTIMAL + corner 20.6s INFEASIBLE 正确判定), 跟 coordinate-based 30 min UNKNOWN 比快 ~34x, 跟 L16 master 81s + cut 不收敛比直接一次给出 power-feasible solution. solve time consistent ~50s across area 405-576 (与 area 几乎无关). Phase 0 prototype 在 docs/research/b1_pose_bool_phase0_20260517/."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## B1 Phase 0 prototype 实测 GO ✅ (2026-05-17)

跟 [[b1-pose-bool-master-rewrite-plan]] 配套. 在 L16 ❌ 死 (master 端 OK cut 端不收敛) + 14 lever 全 verdict 后, 用户授权 B1, ROI 自决. Phase 0 用 verdict-first 策略: 不直接重写生产 master, 先写 standalone prototype 验证 pose-bool form 加 power_coverage 后是否仍快, < 60s feasible 才 GO.

## 5 anchor 数据

| candidate | anchor | area | status | solve(s) | branches | poles |
|---|---|---|---|---|---|---|
| 27×15 | (0,0) corner | 405 | INFEASIBLE | 20.6 | 0 | - |
| 27×15 | (22,28) interior | 405 | **OPTIMAL** | **52.8** | 588K | 171 |
| 30×15 | (20,28) interior | 450 | **OPTIMAL** | **53.2** | 1.6M | 160 |
| 35×15 | (18,28) interior | 525 | **OPTIMAL** | **52.9** | 1.1M | 124 |
| 36×16 | (18,28) interior | 576 | **OPTIMAL** | **49.4** | 296K | 136 |

5/5 fast verdict (4 OPTIMAL + 1 正确 INFEASIBLE). solve time **几乎不随 area 变化** ~50s consistent.

## 跟 L16 / 现 coordinate 比

| lever | first master.solve | LBBD 是否需要回灌 | 总 wall |
|---|---|---|---|
| 现 coordinate (含 coverage) | 30 min UNKNOWN | - | 30 min UNKNOWN |
| L16 (coordinate skip + completion subproblem) | 81s OPTIMAL | 是 (10 iter loose / 6 iter tight 都不收敛) | 15 min 不收敛 |
| **B1 (pose-bool + coverage)** | **53s OPTIMAL** | **否** (master 一次给 power-feasible) | **53s** |

**核心区别**: L16 把 coverage 推给 subproblem cut 收敛失败; B1 把 coverage 装回 master 但 form 改成 pose-bool, AddAtMostOne cell exclusivity 让 CP-SAT propagator 直接 fire, 不依赖 AddNoOverlap2D (dense packing 弱).

## prototype 数据规模

每 anchor:
- bool vars: 270K-296K (mandatory ~270K + pole ~4300)
- cell exclusivity 约束: ~4500
- power coverage 约束: ~270K (每 powered pose 一条 linear)
- master core preprocess: 56-61s (coordinate legacy 预处理, Phase 1 生产路径要去掉)
- pose-bool model build: 21-25s (可优化但不在关键路径)
- solve: 49-53s

## 范围 (Phase 0 scope)

**包括**:
- mandatory 19 groups pose-bool
- required_optional protocol_storage_box pose-bool (1 slot)
- residual_optional power_pole pose-bool (无 demand 约束)
- demand + cell exclusivity + ghost forbidden + power_coverage

**不包括** (Benders subproblem 不在 master CP-SAT):
- port_binding (`binding_subproblem.py`)
- boundary_port_feasibility (precheck/screen spec)
- routing / flow

## ROI + next step

Phase 0 GO 给出 hard evidence master.solve 可解. 生产 Phase 1-5 路径:
1. **Phase 1: 写生产 pose-bool master 集成进 Benders** (2-3 day)
2. **Phase 2-3: 适配 layer (boundary_port precheck / extract_solution / cut replay)** (2-4 day)
3. **Phase 4: 测试 + regression** (1-2 day)
4. **Phase 5: 完整 LBBD 跑 27×15 anchor 验 production wall** (0.5 day)

## Risk

1. Build time 56-61s 是 coordinate legacy 预处理. 生产路径要么重用缓存 (`_power_coverers_by_template_pose` + `_template_pose_tuple_by_idx`) 跳坐标 slot 创建, 要么重写 build phase. Phase 1 决定.
2. binding/routing subproblem 拿的是 coordinate solution (instance_id → (x,y,mode)). pose-bool form 需要 `(group_id, pose_idx) → (instance_id, anchor_x, anchor_y, mode)` 转换, mechanical work.
3. Benders cut 现在表达成 coordinate literal, 要重写成 pose-bool literal. Cut 数量小, 可控.

## 文件位置

- `docs/research/b1_pose_bool_phase0_20260517/poc_pose_bool_with_power.py` — prototype 190 LOC
- `docs/research/b1_pose_bool_phase0_20260517/README.md` — verdict 详细
- `docs/research/b1_pose_bool_phase0_20260517/trial[1-6]*.log` — 6 trial 日志

## 链

- [[b1-pose-bool-master-rewrite-plan]] — B1 完整 plan (Phase 1-5)
- [[l16-lazy-power-completion-phase0]] — L16 ❌ master 端 OK cut 端死
- [[l15-setpacking-prover-dead]] — Step B 7.2s minimum 来源
- `docs/lever_verdicts.md` — B1 Phase 0 ✅ 已加入
