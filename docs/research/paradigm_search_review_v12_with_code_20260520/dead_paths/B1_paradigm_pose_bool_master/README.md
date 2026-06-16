# B1 — Pose-Bool Master Rewrite Paradigm (paradigm 真 GO, 但 LBBD 上层 dead)

## 当时项目情况

L16 lazy power completion 后. master 端方向对 (81s 解锁 power_coverage) 但 cut 端 instance-level Benders 不够. 项目 14 条 lever 全死, **唯一未试 paradigm = master form 切换**.

## 为什么走这条路

User 决策走 B1. 关键 hard evidence:
- **Step B 实测** (L15 中间): minimum pose-bool set-packing 27×15 interior anchor (22,28) 8 worker **7.2s FEASIBLE 12K branch**
- 对比 coordinate-based 同 anchor master 30 min UNKNOWN

含义: pose-bool 形式让 CP-SAT cell-exclusivity propagator 直接 fire, 不依赖 AddNoOverlap2D (CP-SAT 在 dense packing 弱).

## 实验过程

5 个 Phase (用户决策 3-4 day verdict + 6-9 day production):

- **Phase 0 prototype** (1 Claude day): 5 anchor PoC verdict
- **Phase 1 end-to-end** (master + binding + routing precheck): single-anchor 跑通
- **Phase 2 production land**: 写 `PoseBoolExactMasterDelegate` (~280 LOC) 接 master_model.py
- **Phase 3 LBBD wiring**: 接 outer search 主循环 + 完整 LBBD 跑通

## 实验结果

### Phase 0 GO ✅
- 5 anchor 全 fast verdict (49-53s OPTIMAL × 4 + corner 20.6s INFEASIBLE 正确)
- solve time 几乎不随 area 变化 (consistent ~50s area 405-576)
- 跟 coordinate 30 min UNKNOWN 比快 **~34x**

### Phase 1-3 ✅ (端到端 land)
- master 53.3s OPTIMAL + binding 0.1s FEASIBLE + 296 instances
- Pytest 2207 passed + 60 skipped 0 fail
- LBBD 10 iter master OPTIMAL + binding INFEASIBLE + cut added + UNPROVEN

## 经验跟教训 (含瓶颈理解更新)

- **B1 paradigm 自身真 GO** — master form 切换跨数量级解锁 master 端瓶颈. 这是 24 lever 累积里**唯一 paradigm-level 真 GO**.
- **但 LBBD 上层 dead** — Phase 4 routing convergence 实测 routing precheck `front_blocked` ~500-610 ports 系统性, cuts 累积不收敛. master 解开了, cut 端成了新瓶颈.
- **瓶颈理解更新**: master form 选错确实是 problem, B1 修复了; 但 master 修复后**暴露下一层瓶颈** (LBBD cut 表达力). 单一 paradigm shift 不够 — 多层 cascade 瓶颈.

## code/

- `code/` 含 Phase 0 PoC (poc_pose_bool_end_to_end / poc_pose_bool_with_power / probe_existing_pose_bool_path) + Phase 3 LBBD trial scripts + README + production code `shared_infra/src/models/pose_bool_exact_master.py`
