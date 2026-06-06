---
name: b1-phase3-lbbd-land
description: "2026-05-18 commit f19b5a0: B1 Phase 3 wiring 完整 land. pose-bool master 接入 outer search 主循环 + 完整 LBBD 跑通 27×15 anchor (22,28) 10 iter. Master OPTIMAL each iter, binding INFEASIBLE each iter, nogood cut added per iter (constraints +9), final UNPROVEN (max iter). 项目从 30 min UNKNOWN → 10 iter active LBBD 跨数量级. Pytest 2207 全 pass."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## B1 Phase 3 wiring land — commit `f19b5a0`

3 处改动 (`src/search/benders_loop.py`):

1. **line 5154 from_exact_core**: env on 走 direct `MasterPlacementModel(...)` instantiation, 拿 `exact_session.core.source_instances/facility_pools/rules`. 不依赖 proto-sharing (那是 coordinate-only 设计).

2. **line 5408 mandatory_rectangle_precheck trigger**: env on 时 skip 提前 INFEASIBLE short-circuit. 这个 precheck 假设 master 用 (x,y,mode) IntVar 形式, 对 pose-bool master 误判.

3. **line 4416-4429 binding INFEASIBLE return**: env on 时 return cut-added-continue 让 LBBD 重选 layout. Coordinate path 一次 INFEASIBLE 即 final (空间太大加 cut 没用), pose-bool master 可以从 nogood cut 学习.

加 `src/models/pose_bool_exact_master.py` 2 处兼容性:
- `build()` 在 `ghost_rect=None` 时 graceful no-op (因为 build_exact_core 阶段 ghost_rect=None, pose-bool delegate 不参与 proto-sharing — 真 build 在 from_exact_core 后 ghost_rect set 时再来)
- 加 `export_core_binding()` return {} stub

## Phase 3 full LBBD verdict trial (27×15 anchor (22,28))

```
[session_create] 5.6s (build_exact_core, coordinate path 共享 setup)
[run_benders] start

10 iter LBBD loop:
- master.solve OPTIMAL each iter (~50-90s)
- binding INFEASIBLE each iter (real SAT port matching INFEASIBLE)
- nogood cut added per iter (constraints 263252 → 263261)

Final status: UNPROVEN at iter 10 (max iterations reached)
Total wall: 537.8s
```

跟 baseline 比:
- 现 coordinate path: 30 min UNKNOWN (master 卡)
- L16 lazy completion: master 81s + cut 不收敛
- **B1 Phase 3 production LBBD**: master 50s OPTIMAL × 10 iter + binding INFEASIBLE × 10 iter + 9 cut + UNPROVEN

UNPROVEN ≠ UNKNOWN. UNPROVEN 意味着 "试了 N 个 layout 都 fail, 没 prove 全空间 INFEASIBLE". UNKNOWN 是 "解不动". 跨数量级.

## Phase 3 verdict 分析

Master 端 (pose-bool form) 完整 verified work:
- 每 iter 解出 OPTIMAL layout
- 跟 nogood cut 兼容
- LBBD 主循环不卡

Binding 端 (port matching SAT) 跟当前 master 出的 layout 不匹配:
- 每 iter binding INFEASIBLE
- nogood cut 限制 1 个 layout 一次
- 10 iter 没找到 binding-friendly layout

这是 **LBBD inner-loop tuning 问题** (cut tightness / port-aware master constraint / different anchor), 不是 paradigm 验证问题. Phase 0/1/2 Phase 5 verdict trial 同 anchor binding FEASIBLE 0.1s — 不同 master 解 path 出不同 OPTIMAL 解, 只有部分 binding-friendly.

后续 Phase 4 调优方向 (不在当前 session):
- Master 加 port_clearance constraints (粗略 mimic binding feasibility)
- nogood cut 用 deletion-based core minimizer (L16 工具复用)
- 跑 不同 anchor 验是不是 (22,28) 这个 anchor 内部 binding-紧张

## Pytest 验证

2207 passed + 60 skipped, 0 fail. env off 完全不破现 coordinate path.

## 累积 commit (2026-05-17 + 2026-05-18)

- `12f5e64` Phase 0 prototype 5 anchor verdict
- `237a74b` Phase 1 end-to-end master+binding
- `7b8b31d` Phase 2 audit
- `8f7cb2c` Phase 2 caveat
- `31fb3ea` Phase 2 production land (PoseBoolExactMasterDelegate + env flag)
- `22cb862` lever_verdicts 加 B1 Phase 2 ✅
- **`f19b5a0`** **Phase 3 wiring**: outer search 接入 + 完整 LBBD 跑通

7 commit 总览. B1 paradigm 端 fully verified, LBBD 端 wiring 完整.

## 链

- [[b1-phase0-go]] — Phase 0 5 anchor 数据
- [[b1-phase1-findings]] — Phase 1 end-to-end + 代码 audit
- [[b1-phase2-production-land]] — Phase 2 production
- `src/models/pose_bool_exact_master.py` — delegate
- `src/search/benders_loop.py` — Phase 3 wiring (3 env-on branches)
- `docs/research/b1_pose_bool_phase0_20260517/phase3_full_lbbd_trial.py` — verdict trial
- `docs/lever_verdicts.md` — B1 Phase 0/1/2/3 ✅
