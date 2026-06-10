---
name: b1-phase2-production-land
description: "2026-05-17 commit 31fb3ea: B1 Phase 2 production 完整 land. PoseBoolExactMasterDelegate (src/models/pose_bool_exact_master.py, ~280 LOC) 跟 CoordinateExactMasterDelegate 平行. env flag EXACT_USE_POSE_BOOL_MASTER=1 切. Phase 5 production trial: master 53.3s OPTIMAL + binding 0.1s FEASIBLE + 296 instances extract. Pytest 2207 passed + 60 skipped 0 fail. 14 lever 死 + B1 GO ✅, 项目从 30 min UNKNOWN → 53s OPTIMAL 跨数量级."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## B1 Phase 2 production land — commit `31fb3ea`

加 `src/models/pose_bool_exact_master.py` PoseBoolExactMasterDelegate 类, 跟 `CoordinateExactMasterDelegate` 平行实现 master_model.py delegate interface.

激活方式: env flag `EXACT_USE_POSE_BOOL_MASTER=1`. 默认 off 走现 coordinate delegate, 不破现 path.

## Phase 5 production verdict trial

`docs/research/b1_pose_bool_phase0_20260517/phase5_production_trial.py` 跑 27×15 anchor (22,28):

```
env: EXACT_USE_POSE_BOOL_MASTER=1, EXACT_MASTER_GHOST_ANCHOR_FILTER=22,28
[load] 0.5s
[master_init] 3.9s
  delegate type=PoseBoolExactMasterDelegate
[build] master.build() 23.7s
  x_vars=264,464, ro_vars=15,980, pole_vars=4,313
  cell_exclusivity_cells=4,493
  powered_mandatory_groups=17, powered_ro_templates=1
[solve] master.solve(time_limit=180.0)
  master status: OPTIMAL, solve elapsed: 53.3s
extract_solution: 296 instances
binding: FEASIBLE in 0.1s
🎯 B1 Phase 5 GO
```

## 跟 14 lever 全死对比

跨数量级突破:
- 现 coordinate-based master: 30 min UNKNOWN
- L16 lazy completion: master 81s OPTIMAL + cut 不收敛
- **B1 production**: master 53s OPTIMAL + binding 0.1s FEASIBLE ✅

## 兼容性 (pytest 2207 passed + 60 skipped)

env off 默认 path 完全不破:
- Delegate interface 完整模仿 CoordinateExactMasterDelegate 暴露的 attribute (空 dict 占位) + method
- 5 处 master_model.py `if exact_mode and coordinate_delegate is not None` 自动 dispatch

## 设计决策

PoseBool delegate 不参与 `build_exact_core` / `from_exact_core` proto-sharing 机制 (那是 coordinate-specific). 走 direct `MasterPlacementModel(...)` instantiation. 真生产 LBBD outer_search 适配是 **Phase 3** 工作:
- outer_search 现走 build_exact_core 一次, 然后 from_exact_core 多次 (每 candidate 一次)
- pose-bool path 不需要 proto sharing (build 23s 是 negligible vs solve 53s)
- Phase 3 = outer_search 加 env flag 路径走 direct instantiation when env on

但 Phase 2 已经端到端 verify production master + binding 工作. routing inner-loop 集成属于 LBBD 主循环 wiring, 跟 paradigm 验证无关.

## 6 commit today (2026-05-17 整 day)

- `12f5e64` Phase 0 prototype 5 anchor verdict GO (49-53s OPTIMAL × 4 + 20.6s INFEASIBLE × 1)
- `237a74b` Phase 1 end-to-end master+binding PASS
- `7b8b31d` Phase 2 code audit (5 改动点定位)
- `8f7cb2c` Phase 2 caveat (现有 build path 未优化)
- `31fb3ea` **Phase 2 production land** (delegate + env flag + Phase 5 verdict trial)
- `[待加]` memory + lever_verdicts 更新

## Phase 3 + 后续

- Phase 3: outer_search 适配 (直接 instantiation when env on, ~50 LOC)
- routing inner-loop 集成: 用现有 LBBD 主循环, 不需要新 code
- 完整 LBBD 跑 27×15 anchor 端到端验证 (1 candidate 5-10 min)

## 链

- [[b1-phase0-go]] — Phase 0 5 anchor 数据
- [[b1-phase1-findings]] — Phase 1 end-to-end + 代码 audit
- [[b1-pose-bool-master-rewrite-plan]] — 原 plan
- `src/models/pose_bool_exact_master.py` — 实现
- `docs/research/b1_pose_bool_phase0_20260517/phase5_production_trial.py` — verdict trial
- `docs/lever_verdicts.md` — B1 Phase 0/1/2 全 GO 已加入
