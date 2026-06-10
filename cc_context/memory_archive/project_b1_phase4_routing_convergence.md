---
name: b1-phase4-routing-convergence
description: "2026-05-18 commit c64d15f: B1 Phase 4 LBBD inner-loop 调优实测. 修 inferred counts (binding 通了); 但 routing precheck front_blocked ~500-610 ports 系统性, cuts 累积 15 iter 不收敛. paradigm + wiring 完整 ✅, certified FEASIBLE 待 cut convergence 强化 (port-direction-aware cut / deletion-core / routing-aware hint). PROJECT_LOCK 禁 port_clearance hard constraint."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## Phase 4 实测 routing 端 LBBD inner-loop 不 trivial converge

### 关键修复

`run_benders_for_ghost_rect` env on branch 加 `infer_exact_required_pose_optional_counts(rules, generic)` 传给 master. 之前用 `session.core.exact_required_pose_optional_counts` = empty (build_exact_core 不传这参数). 结果 master 不出 protocol_storage_box (ro_vars=0), binding 必 INFEASIBLE.

修后 ro_vars=15980, binding 通.

### Phase 4 实测数据 (27×15 anchor (22,28))

| trial | result |
|---|---|
| 修 inferred counts 前 | binding INFEASIBLE × 10 iter (没 storage box) |
| 修 inferred counts 后 | binding FEASIBLE, **routing precheck `front_blocked` ~500-610 ports each iter** |
| 多 anchor (6 个 interior × 3 iter) | 全 front_blocked |
| 小 candidate (10×10 / 15×10 / 20×10 / 15×15) | 全 front_blocked |
| 启用 warm_start hint | 同 pattern, 没改善 |
| max_iter=15 长 trial | cuts 累积, blocked_ports 519-611 浮动, 没收敛 |
| bypass routing precheck (env `EXACT_B1_BYPASS_ROUTING_PRECHECK=1`) | binding enumerate > 42 min stuck |

### Root cause

pose-bool master 不知 port direction. 它优化 cell exclusivity + power coverage, 但 **port 在 pose 内的 cell-front 方向 master 不约束**. 任何 master OPTIMAL layout 都 ~500-600 ports front_blocked.

LBBD 加 `placement_local_nogood` 只 ban specific (instance, pose) tuple, 多 iter 累积仍找 alternative tuples 落同样 front_blocked geometry pattern.

**PROJECT_LOCK 明禁 port_clearance hard constraint** (master_model.py line 4583 显式 `if exact_mode: return` — "严格精确路径不允许把'所有端口前方都必须畅通'这种近似假设当成正式剪枝").

### ROI 路径 (后续 session 调优)

1. **port-direction-aware cut family**: 不切 specific (instance, pose), 切"port direction pattern" — 同一 port direction × facility-in-fwd-cell 组合整类 ban. medium effort.
2. **deletion-based core minimizer for routing**: 复用 [[l16-lazy-power-completion-phase0]] 工具, 把 ~550 placement_local_nogood 缩到 ~10-20 tight core. medium effort.
3. **routing-aware master hint**: greedy 不只考虑 port_front, 还考虑 port direction × forward cell occupancy. medium effort.
4. **跑超长 trial** (60+ iter, 1-2h wall): 看 cuts 累积是否最终收敛. 风险一样不 converge.

### Phase 4 commit + 状态

- commit `c64d15f`: inferred counts fix + bypass env flag + 3 trial scripts
- 8 commit 累计 (12f5e64 → c64d15f) for B1
- Pytest 2207 全 pass
- 端到端**没**拿到 certified FEASIBLE — paradigm + wiring 完整, 但 cut convergence 是 Phase 5 工作

### B1 overall state

- ✅ Paradigm: pose-bool master 53s OPTIMAL (vs coordinate 30 min UNKNOWN)
- ✅ Production wiring: LBBD outer search + env flag 切换
- ✅ Binding 通: inferred counts 修后 binding FEASIBLE 0.1s
- 🟡 Routing 卡 front_blocked: cut convergence 没在 15 iter 内达成
- ❌ Certified FEASIBLE: 没拿到

### 链

- [[b1-phase3-lbbd-land]] — Phase 3 wiring
- [[b1-phase2-production-land]] — Phase 2 production
- [[b1-phase0-go]] — Phase 0 paradigm verify
- [[l16-lazy-power-completion-phase0]] — deletion-core minimizer (Phase 5 候选工具)
- `src/search/benders_loop.py` env on branches
- `docs/research/b1_pose_bool_phase0_20260517/` 全 phase trial scripts
