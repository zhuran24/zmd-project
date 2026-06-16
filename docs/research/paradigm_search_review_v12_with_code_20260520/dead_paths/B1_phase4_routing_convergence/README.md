# B1 Phase 4 — Routing Convergence Finding

## 当时项目情况

B1 Phase 0-3 ✅ paradigm 真 GO. master 端 50-100s OPTIMAL. 进 LBBD 上层端到端实测.

## 为什么走这条路

B1 paradigm 端到端 verification — 走完整 LBBD loop (master → binding → routing → cut → master), 看是否能拿 certified FEASIBLE.

## 实验过程

修 `infer_exact_required_pose_optional_counts(rules, generic)` 传给 master (之前 build_exact_core 不传 → ro_vars=0 → binding 必 INFEASIBLE). 修后 ro_vars=15980, binding 通.

实测 27×15 anchor (22,28) + 多 anchor + small candidate + warm start hint + bypass routing precheck 多种变体.

## 实验结果

| trial | result |
|---|---|
| 修 inferred counts 前 | binding INFEASIBLE × 10 iter (没 storage box) |
| 修 inferred counts 后 | binding FEASIBLE, **routing precheck `front_blocked` ~500-610 ports each iter** |
| 多 anchor (6 个 interior × 3 iter) | 全 front_blocked |
| 小 candidate (10×10 / 15×10 / 20×10 / 15×15) | 全 front_blocked |
| max_iter=15 长 trial | cuts 累积, blocked_ports 519-611 浮动, 没收敛 |
| bypass routing precheck (`EXACT_B1_BYPASS_ROUTING_PRECHECK=1`) | binding enumerate > 42 min stuck |

## 经验跟教训 (含瓶颈理解更新)

- **Root cause**: pose-bool master 不知 port direction. 它优化 cell exclusivity + power coverage, 但 **port 在 pose 内的 cell-front 方向 master 不约束**. 任何 master OPTIMAL layout 都 ~500-600 ports front_blocked.
- LBBD 加 `placement_local_nogood` 只 ban specific (instance, pose) tuple, 多 iter 累积仍找 alternative tuples 落同样 front_blocked geometry pattern.
- **PROJECT_LOCK 明禁 port_clearance hard constraint** ("严格精确路径不允许把所有端口前方都必须畅通这种近似假设当成正式剪枝").
- **瓶颈理解更新**: master 端 OK 后, **port-clearance cut form** 成为新 lever 方向 (后续 Phase 5).

## code/

- `code/` 含 phase4 hint_force / multi_anchor / small_candidate trial scripts
- 详 `code/README.md`
