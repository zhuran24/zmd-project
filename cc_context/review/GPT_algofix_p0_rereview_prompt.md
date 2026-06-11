# 终末地 IndustrialPlanner 精确求解器 — P0 修复再审（修复本身的 soundness 审查）

## 任务性质（新会话零历史，独立对抗审查）

附件是完整项目快照 zip（zip 内 `project/` 为仓库根；ZIP_LZMA，用 `python -m zipfile -e <附件>.zip .` 解包）。依赖 wheels 在本 Project 文件区，沙盒 Python 3.13，离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。

**本包已含一批刚落地的 P0 soundness 修复。你的任务不是重新找老 bug，而是对抗式审查这批修复本身**：修复是否真 sound？有没有引入新的 unsoundness？fail-closed 边界是不是真 fail-closed？修复的完整性代价（漏解面）有多大？

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器（目标 `max_lex(area, min_side)`，266 强制设施，OR-Tools CP-SAT 9.15 + Benders/LBBD 分解 master→binding→routing→flow）。宪法 `PROJECT_LOCK.md`；certified_exact 与 exploratory 严格分离；fail-closed 默认姿态。

## 背景：修了什么（修复说明在包内 `cc_context/review/algofix_p0_FIXES_20260611.md`，验收记录在 `cc_context/review/algoaudit_verification_results_20260611.md`）

此前一轮算法 soundness 审查确认 3 个真 P0（certified 路径 unsound），修复已落地：

1. **P0-1（routing 连通性）**：`src/models/routing_subproblem.py` —— routing CP-SAT 原本只有局部 successor/predecessor 约束，FEASIBLE 不蕴含 source→sink 连通。修复：`solve()` 接受 incumbent 前按 commodity 重建选中 route-state 有向图、检查所有 source front 到 sink front 可达；不可达则加 selected-route nogood 重解；预算耗尽返回 TIMEOUT，绝不返回 false FEASIBLE。
2. **P0-2（footprint 几何）**：`src/models/exact_coordinate_master.py` —— no-overlap/ghost/power 原本用模板固定尺寸而非候选 pose 真实 footprint（竖向 4x6 被当 6x4）。修复：从每个 pose 的 `occupied_cells` 推导 footprint token + 包围盒，`mode → (dx_min,dy_min,w,h)` 走 `AddAllowedAssignments`，`AddNoOverlap2D` 用 variable-size interval（footprint channel），power coverage witness 同改。缺 footprint 证据时构建期 raise（fail-closed），非矩形 footprint 取 bounding box 保守过近似。
3. **P0-3（front_blocked ladder）**：`src/search/benders_loop.py` —— front_blocked（binding-local 证据）原本跳过 binding 枚举直接铸 master pose-presence nogood（over-cut）。修复：`binding_selection_safe_reject=True` 且仍有 binding 替代时，先加 binding-level nogood 重解枚举；穷尽后才落入既有 whole-layout 路径；binding 重解超时返回 UNKNOWN。
4. **落地方连带修复（也要审）**：`exact_coordinate_master.py::_all_powered_slots` 现在过滤掉 `footprint_x_start is None` 的 slot —— 这些是 empty-domain slot，走 `_create_base_slot_geometry` 的快路径（`Add(0==1)` 强制 infeasible、从不建 footprint channel），新的 footprint-based power witness 会在它们身上崩 RuntimeError。理由：这些 slot 已使模型 UNSAT，跳过其 power coverage 几何不改变结论。**请专门审这条理由是否在所有调用上下文下成立**（两个调用点：`_add_geometric_power_coverage_constraints` 的两条路径）。

配套：PROJECT_LOCK + specs/07、09、10 已同步；回归测试 `src/tests/test_p0_certified_soundness_fixes.py`。

## 你要回答的问题（按优先级）

### Q1 修复有没有引入新的 unsoundness（最重要）
- **P0-1 的 connectivity guard 图重建对不对**：它从 `r_vars` 重建的选中 state 图、source/sink front 的判定（`_source_port_fronts`/`_sink_port_fronts`）、arc 的方向语义（flow_out → 邻格 flow_in），与 routing 模型的真实语义是否严格一致？有没有"guard 认为连通但物理不连通"的缝（guard 过松 → false FEASIBLE 复活）？特别审多 commodity 共存、双层（ground/elevated bridge）、splitter/merger state 下 guard 的图语义。
- **P0-1 的 incumbent nogood 形状**：nogood 是否只排除"恰好这组选中 state"？会不会意外排除其它合法 incumbent（over-cut → 误报 INFEASIBLE）？CP-SAT 重解循环的终止条件、预算分配、INFEASIBLE 与 TIMEOUT 的语义区分是否正确？
- **P0-2 的 footprint channel 编码**：`AddAllowedAssignments` 的 rows（mode → dx_min/dy_min/w/h）是否覆盖全部 mode？footprint_x_start/end 的链接等式、variable-size interval 的 size/end 一致性有没有边界错误（off-by-one）？bounding-box 过近似对非矩形 footprint 是否真保守（只可能拒真可行、不可能放真不可行）？power coverage witness 改用 footprint span 后，覆盖判定的几何语义是否仍与"pole 覆盖 powered facility 的占格"一致（过松/过紧各往哪边偏）?
- **P0-3 的 ladder**:binding nogood 枚举循环的终止性?"穷尽后落入 whole-layout 路径"时,whole-layout cut 的证明前提(所有 binding 都试过且都失败)是否真的被满足?front_blocked 与 routing-INFEASIBLE/relaxed_disconnected 三分支统一后有没有遗漏的路径仍直接铸 placement cut?
- **连带修复**:`_all_powered_slots` 过滤 `footprint_x_start is None` 的 slot——有没有"slot 没建 footprint channel 但模型并非 UNSAT"的第三种情形(过滤会让该 slot 逃过 power coverage 约束 → false FEASIBLE)?请穷举 `footprint_x_start` 为 None 的全部赋值路径验证。

### Q2 fail-closed 边界是否真 fail-closed
每个修复声称"不确定时 UNKNOWN/TIMEOUT、绝不 false-CERTIFIED"。请试图构造让它们违背这个声明的输入（伪造/极端 incumbent、退化 footprint、binding 枚举边界）。

### Q3 完整性代价（漏解面）评估
P0-1 的 guard 是保守急救：disconnected incumbent → nogood 重解 → 预算耗尽 TIMEOUT。请评估：在真实规模（70×70、多 commodity）下，CP-SAT 产出大量局部一致但不连通 incumbent 的可能性有多大？nogood-重解循环会不会实际退化为"几乎总是 TIMEOUT"（→ 候选大面积 UNKNOWN，搜索失去推进力）？如果会，给出把 per-commodity reachability/flow 一等编码进 CP-SAT 的具体方案（变量/约束设计 + 规模估算），这是已知的最终方向。

### Q4 回归测试的判别力
`test_p0_certified_soundness_fixes.py` 三个测试是否真判别（修前 fail / 修后 pass）？有没有测试本身放水的缝（mock 过度、断言过弱）？

## 自验环境与已知基线

- 先跑 `python scripts/check_p1_2_proof_obligations.py`（应 pass：8 obligations anchored）。
- `data/preprocessed/candidate_placements.json`（53.6MB）刻意外置不在包内，**不准伪造**。已知环境性失败（非 finding）：test_binding 10 ERROR / test_regression 5 / test_routing 3 / test_master 1 / test_preprocess_golden 1；其余约 2836 应过。
- finding 尽量带可复现 probe（构造输入实测修复后的代码出错）；实证推翻了你的怀疑就不要报。

## 交付物

- `REVIEW.md`：逐条 finding —— 严重度（**algorithmic/soundness** vs 工程 vs 文档）、`file:line`、论证/probe、建议修法；有把握的附 unified diff + regression。
- **所有 finding 完整论证直接写在回复正文**（不要只塞附件——附件通道可能抓不全）。
- 若审完认为这批修复 sound 且 fail-closed 边界成立，明确写"**本轮零 soundness finding**" + 列实际审过的修复面/构造过的攻击输入/论证依据。Q3 的完整性评估无论如何都要给（它不是 finding，是工程评估）。不要硬凑，也不要因"刚修过"就默认干净。

## 范围边界

- P1.3B（`src/cuts/lifecycle.py::step_8_apply_to_master`）仍被 owner gate 阻塞，不审。
- exploratory 路径不审。
- proof-carrying certificate 是已知 future work，不要把"缺独立重验"当 finding。
- 上一轮已 refuted 的三个误判（binding output 满占=52-port 不变量正确 / routing port 单次偏移正确 / pose-bool 被 guard 拦截）不要翻案重报，除非你有新的、能实证的理由。

包 sha256：`c71896e31d015f4a114a6f2fb309b342f359b9142bbf8f772479245faa188534`
