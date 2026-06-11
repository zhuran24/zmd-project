# 终末地 IndustrialPlanner 精确求解器 — 3 个 P0 soundness bug 修复任务

## 任务性质（新会话零历史，这是修复不是审查）

附件是完整项目快照 zip（zip 内 `project/` 为仓库根；ZIP_LZMA，用 `python -m zipfile -e <附件>.zip .` 解包）。依赖 wheels 在本 Project 文件区，离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。

一轮换方向算法 soundness 审查 + 独立对抗式代码核验已确认 **3 个真 P0 soundness bug 在默认 certified 路径上**，使 certified_exact 路径当前 unsound（会把不可行/不可路由布局当"已证明最优"，或误剪可行布局漏掉真最大矩形）。你的任务：**逐个修复这 3 个，产出补丁 + 回归测试 + 自验**。机制已坐实，定位精确，直接修。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器（目标 `max_lex(area, min_side)`，266 强制设施，OR-Tools CP-SAT 9.15 + Benders/LBBD 分解 master→binding→routing→flow）。宪法 `PROJECT_LOCK.md`；certified_exact 与 exploratory 严格分离；fail-closed 默认姿态。

## 关键约束（必读）

- 这 3 个 bug 都在 certified 求解核心。改动碰 PROJECT_LOCK 精确边界，**修改必须同步更新 `PROJECT_LOCK.md` / 相关 spec / 相关 test**（三件套）。
- **fail-closed 优先**：修复宁可让求解器在不确定时返回 `UNKNOWN`/`TIMEOUT`，绝不能让它把不可行当 CERTIFIED。完整建模重构（如把 reachability/flow 一等编码进 CP-SAT）可作为最终方向，但**保守 fail-closed guard 是可接受的第一步**。
- **不破坏 env-off / 默认路径之外的行为**（既有 lever、Path 12/13 等 verdict 不变）。
- **不引入 ruff / mypy 问题**（项目 CI 有 ruff + mypy core gate，会卡）。行尾 LF。
- 每个 finding：unified diff 补丁（基于包内原文件）+ 配套 regression 测试 + 修前/修后 probe 输出。

## 要修的 3 个 P0（机制已确认，定位精确）

### P0-1（A-1）routing CP-SAT 的 FEASIBLE 不蕴含 commodity 源→汇连通 → false CERTIFIED
- `src/models/routing_subproblem.py:864-937` `_add_continuity_constraints` / `_add_successor_constraints` / `_add_predecessor_constraints`：**只有局部** successor/predecessor 支撑约束。
- `:939-973` `_add_port_adherence`：只钉 source/sink front cell 各一个 state。
- **全文无 source→sink 全局连通 / 流守恒约束。**
- `:1005-1006` solve() CP-SAT FEASIBLE 即返回 FEASIBLE；`src/search/benders_loop.py:5609-5628` routing FEASIBLE 直接提升 `RUN_STATUS_CERTIFIED`。
- 机制：局部约束允许 source 侧孤立分量 + sink 侧孤立分量各自局部闭合但互不连通 → 报 FEASIBLE 但货没运到。实测反例：窄走廊 3-commodity，sink_reachable 全 False 却 FEASIBLE。
- **修法**：solve() 接受 CP-SAT incumbent 前，按 commodity 重建选中 route-state 有向图，检查所有 source front 到 sink front 可达；不可达则对该 incumbent 加 nogood 重解；预算内找不到可达 incumbent 则返回 `TIMEOUT`/`UNKNOWN`，绝不返回 false `FEASIBLE`。最终建议把 per-commodity reachability/flow 一等编码进 routing CP-SAT（注明为后续工作即可）。

### P0-2（B-01）coordinate master no-overlap/ghost/power 用模板固定尺寸而非候选 pose 真实 footprint → false CERTIFIED
- `src/models/exact_coordinate_master.py:2154/2170/2185/2194` slot.dims 取 `templates[tpl]["dimensions"]` 固定 (w,h)。
- `:2333-2354` 用固定 (w,h) 建 `NewIntervalVar`/`NewOptionalIntervalVar`；`:3047` `AddNoOverlap2D` 用这对 interval；`:4863/4872/4887/4893` power coverage witness 同样固定尺寸。
- mode 变量能在同 slot 选不同朝向（`gen_rect_manufacturing` 对 6x4 生成 o=0 真实 6x4、o=1 真实 4x6），**但 interval 尺寸不随 mode 变**；`ModeRectDomain` 只存 anchor 包围盒，无 footprint 维度。
- 机制：选竖向 4x6 pose 时 no-overlap 仍按 6x4 算 → 物理重叠布局通过（false-feasible），反向可 false-infeasible。命中 38×manufacturing_6x4 + 46×boundary_storage_port 真实强制实例。
- **修法**：coordinate backend 从每个候选 pose 的 `occupied_cells` 推导真实 footprint bounds，把 footprint shape 纳入 mode token；对每 slot 建 `mode → width/height` channel，用 variable-size interval 建 `AddNoOverlap2D`；power coverage witness 同改用 channelled span。非矩形 footprint 取 bounding box 作 fail-closed 保守 over-approximation。

### P0-3（A-2）front_blocked（binding-local 证据）跳过 binding 枚举直接铸 master pose-presence nogood → false INFEASIBLE → 漏真最大矩形
- `src/models/routing_subproblem.py:354-358` front_blocked 返回 `binding_selection_safe_reject=True`（语义=仅可拒当前 binding 选择，非 placement 不可行）。
- `src/models/binding_subproblem.py:408-456` binding_domains 是同 pose 多绑定枚举；`:770-785` 端口坐标由 binding_idx 决定 → "端口前格被占"是当前 binding 的局部事实。
- `src/search/benders_loop.py:5208-5524` front_blocked 进 cut；`:5428-5467` 默认 fallback 用 `placement_level_conflict_set` 铸 master pose-presence nogood；`:5503-5524` cut_added 后直接 return `MASTER_CUT_ADDED_CONTINUE`，**跳过 binding 枚举**。
- 对照 `:5526-5550` relaxed_disconnected 与 `:5660-5694` routing-INFEASIBLE 两分支都先 `binding_model.add_nogood_cut(selection)` + continue 枚举 binding 替代。master cut（`exact_coordinate_master.py:6567-6611`）是 pose-presence nogood，不带 binding literal。
- 机制：换 binding 端口可能朝向空闲格而可路由，但被投影成 placement-only nogood 误剪可行布局 → `max_lex` 下漏真最大矩形 → 对外 false CERTIFIED。
- **修法**：把 front_blocked 与 relaxed_disconnected 放同一 proof ladder——只要 `binding_selection_safe_reject` 为真且 binding_model 仍有替代 binding，就先只加 binding-level nogood 并重解 binding；只有所有 binding 替代穷尽、或有独立证明"此 placement 下任何 binding 都必 front-blocked"时，才允许写 master placement nogood。无法形成 exact 证明时 fail-closed 为 `UNKNOWN`。

## 明确不要动（已判定为误判 / 非公开路径，改了反而引入 bug）

- **binding generic output 的 `AddExactlyOne` 强制全占是正确的，不要改**：本 base R=52 需求恰 = S=52 供给（46 边界口 + 6 协议核心出口），spec `04_recipe_and_demand_expansion.md:118-132` 要求 output 100% 占满不容空置。**不要给 generic output 加 `__unused__` sentinel**——会破坏正确逻辑、引入 false-feasible。
- **routing port 坐标不要改**：certified routing 吃冻结产物 `candidate_placements.json`，端口坐标是"本体边缘格"，`front = port + dir` 是唯一一次正确偏移，没有二次偏移。不要改成"port 即 terminal"。
- **pose-bool exact master ghost domain 不在本次范围**：它被三处 fail-closed guard 拦在 certified 路径外。

## 可选（latent，有余力再做，否则跳过）

- `src/cuts/oracles/cutset_oracle.py:150-156` F2 edge_capacity=1 忽略 elevated bridge 层（真实 2 层容量）。F2 当前未接 master（dormant），但 P1.3B 接 `step_8` 前必修——可顺带把 edge_capacity 改成两层容量上界（含 validator `cutset.py` 对应 recompute）。
- `scripts/production_readiness_gate.py` 缺把 `EXACT_B1_D2_COMMODITY_FLOW` 列为 launch blocker（对比已列的 `EXACT_POWER_PLACEMENT_SUBPROBLEM`），可补。

## 自验基线

- `python scripts/check_p1_2_proof_obligations.py` 应 pass（8 obligations anchored）。
- `data/preprocessed/candidate_placements.json`（53.6MB）外置不在包内，**不准伪造**；已知环境性失败（非 finding）：test_binding 10 ERROR / test_regression 5 / test_routing 3 / test_master 1 / test_preprocess_golden 1；其余约 2833 应过。
- 你那边没有 candidate_placements 无法跑全量，但每个修复必须：给最小 probe（构造小输入实测 bug 修前 false-CERTIFIED/false-INFEASIBLE、修后正确）+ 跑 `check_p1_2_proof_obligations` + `py_compile` 改动文件 + 相关单元测试。

## 交付

- 每个 P0 一个 unified diff 补丁（基于包内原文件）+ regression 测试 + 修前/修后 probe 输出。
- `FIXES.md`：逐个说明改了什么、为什么 sound、fail-closed 边界在哪、对 env-off 行为无影响的论证、三件套（PROJECT_LOCK / spec / test）各同步了哪些。
- **所有关键说明写在回复正文**（不要只塞进附件——附件通道可能抓不全）。

包：附件即完整项目快照，解包方式见顶部。
