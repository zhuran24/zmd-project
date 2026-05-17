# B1 Phase 0 verdict — pose-bool master + power_coverage

**Date**: 2026-05-17  
**Lever**: B1 (唯一未试的 paradigm lever, 在 L1-L16 14 条全死 + L11 用户拒绝后)  
**Decision**: 用户授权走 B1, ROI 自决

## TL;DR

**✅ GO**. pose-bool form 让 power_coverage 直接可解, 5 个 anchor 全 fast verdict (49-53s OPTIMAL 或 fast INFEASIBLE), 跟 coordinate-based 30 min UNKNOWN 比快 **~34 倍**, 跟 L16 lazy completion (master 81s OPTIMAL + 10 iter cut 不收敛 = 15 min 总 wall) 比直接一次解出.

跟 Step B (minimum form 跳 power) 7.2s 比, 加 power_coverage 只多了 ~45s — 仍远在 60s gate 内.

## 5 anchor 实测数据

| candidate | anchor | area | status | solve(s) | branches | conflicts | poles | log |
|---|---|---|---|---|---|---|---|---|
| 27×15 | (0,0) corner | 405 | INFEASIBLE | 20.6 | 0 | 0 | - | trial3_corner_0_0.log |
| 27×15 | (22,28) interior | 405 | OPTIMAL | 52.8 | 588,150 | 487 | 171 | trial2_with_power_300s.log |
| 30×15 | (20,28) interior | 450 | OPTIMAL | 53.2 | 1,633,701 | 863 | 160 | trial4_30x15_interior.log |
| 35×15 | (18,28) interior | 525 | OPTIMAL | 52.9 | 1,143,577 | 1,049 | 124 | trial5_35x15.log |
| 36×16 | (18,28) interior | 576 | OPTIMAL | 49.4 | 296,266 | 116 | 136 | trial6_36x16.log |

**Sanity** (`--skip-power`, 等价 Step B): 6.7s OPTIMAL — prototype harness 自身无 regression.

## 关键 invariant

solve time 几乎不随 area 变化 (~50s consistent across 405-576). 推测: 大 candidate ghost 占走更多 cell 减少 facility 自由度, propagation 抵消 search space 增加.

## 跟 L16 (lazy completion) 对比

| lever | master 形式 | first master.solve | LBBD 是否需要回灌 | 总 wall (典型 anchor) |
|---|---|---|---|---|
| L16 (coordinate + skip coverage + completion subproblem) | coordinate-based | 81s OPTIMAL | 是 (loose cut 10 iter / tight cut 6 iter 都不收敛) | 15 min 不收敛 |
| **B1 (pose-bool + power_coverage)** | **pose-bool** | **53s OPTIMAL** | **否** (master 一次给出 power-feasible solution) | **53s** |
| 现 coordinate (含 coverage) | coordinate-based | 30 min UNKNOWN | - | 30 min UNKNOWN |

**核心区别**: L16 把 coverage 推给 subproblem, 但 cut 端 instance-level Benders 在 problem geometry 下不收敛. B1 把 coverage 装回 master, 但 form 改成 pose-bool, AddAtMostOne cell exclusivity 让 CP-SAT propagator 直接 fire — 不需要 AddNoOverlap2D (在 dense packing 弱).

## prototype 数据规模

每 anchor 一次 build + solve:
- bool vars: ~284K-296K (x_mandatory + y_pole)
- cell exclusivity 约束: ~4500
- power coverage 约束: ~270K (每 powered pose 一条 `x_{g,p} ≤ Σ y_pole_coverer`)
- master core (preprocess) build 56-61s — coordinate-based legacy 预处理, Phase 1 生产路径会去掉
- pose-bool model build 21-25s — 可优化但已不在关键路径

## prototype 范围 (Phase 0 scope)

**包括**:
- mandatory 19 groups (266 demand) pose-bool 表达
- required_optional protocol_storage_box pose-bool
- residual_optional power_pole pose-bool (无 demand 约束, 按需选)
- demand + cell exclusivity + ghost forbidden + power_coverage

**不包括** (在 Benders subproblem, 不在 master):
- port_binding (`src/models/binding_subproblem.py`)
- boundary_port_feasibility (precheck/screen spec, 不进 master CP-SAT)
- routing
- flow

## 跟前面 lever 比

| lever | 类型 | verdict |
|---|---|---|
| L1-L10 | 工程优化 / paradigm 早期 | ❌ |
| L11 | 牺牲严格性 | 🟡 用户拒绝 |
| L12 v8 anchor slicing | GPT 算法错估 | ❌ |
| L13 v10 witness preflight | GPT 前提错估 | ❌ |
| L14 weighted occupancy | GPT 数学能力上限 | ❌ |
| L15 set-packing prover | GPT paradigm 攻错层 | ❌ |
| L16 lazy power completion | master ✓ cut ❌ | ❌ |
| **B1 pose-bool master rewrite** | **paradigm: 改 representation** | **✅ Phase 0 GO** |

## ROI 分析 + next step

Phase 0 verdict 给出 hard evidence: pose-bool form 自身够快.

下一步 ROI 排序 (按"该不该现在做"):
1. **Phase 1: 写生产 pose-bool master 集成进 Benders 流程** (2-3 day) — 替换 coordinate-based master 在 LBBD 主循环, 跟 binding_subproblem / routing_subproblem 对接
2. **Phase 2-3: 适配各 layer** (2-4 day) — boundary_port_feasibility precheck / extract_solution / Benders cut replay
3. **Phase 4: 测试 + regression** (1-2 day)
4. **Phase 5: 完整 LBBD 跑 27×15 anchor 验 production wall** (0.5 day)

如果 Phase 5 verdict 仍 < 60s/anchor, B1 完整生产路径成立, 项目脱离 30 min UNKNOWN 死锁.

## Risk

1. **Build time 56-61s 是 coordinate legacy 预处理**: 生产路径要让 pose-bool master 不依赖这个. 选项 (a) 重用 `_power_coverers_by_template_pose` 缓存表 + `_template_pose_tuple_by_idx`, 跳过 coordinate slot var 创建 (b) 重写 build phase. Phase 1 决定.

2. **Benders subproblem 与 pose-bool extract_solution 适配**: 现 binding/routing subproblem 拿的是 coordinate-based solution (instance_id → (x, y, mode)). pose-bool 形式下需要 `(group_id, pose_idx) → (instance_id, anchor_x, anchor_y, mode)` 转换. 这是 mechanical adaptation.

3. **Cut replay**: 现 Benders cut 表达成 coordinate literals. pose-bool 形式下要重写成 pose-bool literals. 但 cut 数量小, work 可控.

## 操作文件

- `poc_pose_bool_with_power.py` — prototype script (~190 LOC)
- `trial1_skip_power_sanity.log` — 6.7s OPTIMAL sanity
- `trial2_with_power_300s.log` — 27×15 interior 52.8s OPTIMAL
- `trial3_corner_0_0.log` — 27×15 corner 20.6s INFEASIBLE
- `trial4_30x15_interior.log` — 30×15 interior 53.2s OPTIMAL
- `trial5_35x15.log` — 35×15 525area 52.9s OPTIMAL
- `trial6_36x16.log` — 36×16 576area 49.4s OPTIMAL

## Phase 2 code audit (代码 audit for production integration)

`src/models/master_model.py` **现有 pose-bool path 已 implemented 完整**:

| 方法 | 行号 | 状态 |
|---|---|---|
| `_create_variables` | 4414 | `z_vars[gid][pose_idx]` BoolVar — pose-bool form |
| `_add_assignment_constraints` | 4458 | `sum z_vars == demand` |
| `_add_set_packing_constraints` | 4502 | cell exclusivity |
| `_add_ghost_rect_constraints` | 4509 | ghost forbidden |
| `_add_power_coverage_constraints` | 4621 | **跟 prototype 数学等价** (`sum(pole_vars[idx] for idx in coverers) >= z_var`) |
| `_add_symmetry_breaking_constraints` | 4658 | 分组 encoding |
| `_add_global_valid_inequalities` | 4860 | valid inequalities |
| `_add_search_guidance` | 4696 | exact_mode-only |

**`exact_mode=True` 强制跳过 pose-bool path**, 走 coordinate_delegate (line 4385-4397).

外部代码 (`benders_loop.py` / `outer_search.py` / `exact_campaign.py`) **不直接调** `_coordinate_delegate` — 全走 `self.master.<method>`. 只有 test files 引用 `_coordinate_delegate`.

Phase 2 改动点 (5 处):

| 行号 | 方法 | bypass 难度 |
|---|---|---|
| 4385 | `build()` | low — 加 env flag if-else |
| 11522 | `extract_master_hints()` | medium — return {} fallback |
| 11551 | `apply_master_hints()` | medium — return 0 fallback |
| 11675 | `extract_solution()` | low — fall-through 到通用 path (line 11679+ 已存在) |
| 11743 | `add_benders_cut()` | low — fall-through 到通用 path (line 11747+ 已存在) |

加上 `build_exact_candidate_warm_start()` (line 9779) — 内部已有 `if self._coordinate_delegate is not None:` 保护, env flag on 时 coordinate_delegate=None 自然 fallback.

**Phase 2 总工作量重估**: ~30-50 LOC + 跑 2086 pytest 验回归. 比之前估的 2-3 day 缩到 1-2 Claude hour. 但仍需新 session 做 (master_model.py 改动面 + 全 test 验证).

## Phase 2 caveat: 现有 build path 性能未验证

`probe_existing_pose_bool_path.py` 实测 — master_model.py 现有 exploratory mode + ghost_rect 配置 master.build() **> 4 min 没出**. 推测瓶颈在 `_populate_cell_occupancy_terms` (line 4363) 之类 — 对所有 group × cell × pose 算 covering, 70x70 grid × 19 group × 17K pose 量级.

意义:
- 不影响 B1 paradigm — Phase 0 prototype 22s build + 53s solve 是真的
- Phase 2 真生产路径 = 写 `PoseBoolExactMasterDelegate` 跟 `CoordinateExactMasterDelegate` 平行, 模仿 Phase 0 prototype build 模式
- 不要直接复用 master_model.py 现有 build path (那是为 exploratory 设计未优化)

Phase 2 修正路径估时: 1-2 Claude day (写新 delegate + 集成 + 全 test).


## End-to-end trial (Phase 1 incremental, trial 7/8)

`poc_pose_bool_end_to_end.py` 扩展 prototype 加 binding + routing 调用. 跑 27×15 anchor (22,28):

| stage | status | time |
|---|---|---|
| master (pose-bool + power_coverage) | **OPTIMAL** | 52.9s |
| binding (PortBindingModel first solution) | **FEASIBLE** | 0.0s |
| routing precheck | **front_blocked** | < 1s |

**意义**:
- ✅ master 端 pose-bool + power_coverage 在 53s 解出 layout (438 instances: 266 mandatory + 1 ro + 171 pole)
- ✅ binding 0 秒 FEASIBLE — 438 instances 的 port match 自然成立, 没 empty domain
- 🟡 routing precheck 第一次 reject — binding 解出的 port choice 几何上不可路由 (某些 port 的 front cell 被设施挡住)

这是 LBBD 标准 inner-loop 信号: 第一个 binding solution 经常被 routing reject, 需要加 binding nogood cut 让 binding 选别的 port match, 直到 routing feasible 或 binding 穷尽. standalone prototype 没实现这个 inner loop (那是 Benders LBBD 主循环代码).

**不是 B1 paradigm 失败**: master + binding 一次过通过强力证明 pose-bool form 解 master 是真破局. routing precheck 是 binding 阶段的 quality 问题, 跟 master form (pose-bool vs coordinate) 无关 — coordinate master 解出 layout 也会撞同样的 routing precheck.

Phase 2+ 工作: 把 pose-bool master 接入 LBBD 主循环, 让现有 binding nogood loop + routing 自然 handle.

## 链

- [[project_b1_pose_bool_master_rewrite_plan]] — B1 完整 plan
- [[project_l16_lazy_power_completion_phase0]] — L16 ❌, master 端 OK cut 端死
- [[project_l15_setpacking_prover_dead]] — L15 paradigm 攻错层, Step B 来源
- `docs/research/setpacking_prover_poc_20260517/poc_minimum_setpacking.py` — Step B baseline (7.2s minimum)
- `docs/lever_verdicts.md` — B1 Phase 0 ✅ verdict 已加入
