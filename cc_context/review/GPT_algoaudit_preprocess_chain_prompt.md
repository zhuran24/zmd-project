# 终末地 IndustrialPlanner 精确求解器 — certified 根基审查: preprocess 链 / 候选摆位枚举的正确性与完备性

## 任务性质 (新会话零历史, 独立对抗审查)

附件是完整项目快照 zip (zip 内 `project/` 为仓库根; ZIP_LZMA, 用 `python -m zipfile -e <附件>.zip .` 解包)。依赖 wheels 在本 Project 文件区, 沙盒 Python 3.13, 离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。

求解器内核 (master/binding/routing/cuts) 近期已多轮对抗审查并修complete 3 个 P0。**本轮把审查面移到此前从未独立审过的最上游: preprocess 链**——certified 路径吃的全部「事实」(候选 pose 几何、强制实例集、IO 需求) 都由它生成。这一层错 = 求解器在错误的世界里证明定理:
- **错编码** (占格/端口/电力覆盖几何错) → 下游一切 soundness 证明作废 = false CERTIFIED;
- **漏枚举** (合法 pose 没进池 / 过滤过严) → certified `max_lex(area, min_side)` 的「穷尽所有合法摆位」前提破产 = 最优性主张不成立 (找到的"最优"可能不是真最优)。

若审完确认无残留, 明确报零——这是 owner 判定该面「第一轮干净」的输入。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 审查面 (preprocess 链全体)

代码:
- `src/placement/placement_generator.py` — 候选摆位枚举器 (`load_templates` / `generate_all_pools` / `get_occupied_cells` / `get_edge_ports` 等): 从 `rules/canonical_rules.json` 模板出发, 枚举全场绝对坐标合法 pose (anchor / orientation / port_mode → occupied_cells / input_port_cells / output_port_cells / power_coverage_cells)。对应规格 `specs/06_candidate_placement_enumeration` 与几何章 `specs/02`。
- `src/preprocess/demand_solver.py` — 产能/需求求解 (`solve_demands` / `generate_ceil_machine_counts` / `generate_generic_io_requirements` / `generate_port_budget` / `normalize_json_numbers`)。
- `src/preprocess/instance_builder.py` — 强制实例集构建 (`build_core_instance` / `build_manufacturing_instances` / `build_boundary_ports` / `build_exploratory_optional_instances` / `TEMPLATE_MAPPING`)。
- `src/preprocess/operation_profiles.py` (`count_operations` / `aggregate_port_slots`)。
- `scripts/build_current_preprocess_context.py` 与 `src/interchange/preprocess_context.py` (artifact 装订)。

事实源: `rules/canonical_rules.json` (17-recipe canonical 投影) + `third_party_snapshots/` (vendored 上游数据)。
冻结产物: `data/preprocessed/mandatory_exact_instances.json`、`generic_io_requirements.json` (在包内, 可直接对账); `candidate_placements.json` (53.6MB **外置不在包内, 不准伪造**)——但生成链全在包内, 你可以**自己跑 `generate_all_pools` 现场重新生成**再审。

## 审查重点 (按优先级)

### Q1 几何编码正确性 (错一格 = 全链 false CERTIFIED)
- `get_occupied_cells` 的锚点/包围盒约定 (左下角 (x,y), 右上 (x+w-1, y+h-1)) 与 specs/02 及下游消费者 (master no-overlap 用 pose 真实 occupied_cells、routing 障碍格) 是否严格一致? orientation 旋转时 w/h 交换与 occupied_cells 投影是否同步?
- `get_edge_ports` 四边端口的**外侧格坐标 + 向外法向**: top 边 y+h / bottom 边 y-1 / left 边 x-1 / right 边……逐边核对。端口格在本体外一格、dir 指向离开本体的方向——这个约定与 routing 的 front 推导 (`front = port + DIR_DELTA[dir]`) 复合后, 材料实际流动格是否正确? (注意: routing 侧对 output port 用 `DIR_OPP` 收料, 这是**单次偏移、已审过是正确的**, 不要在那一侧报; 要审的是 preprocess 侧给出的 port 格/法向本身对不对。)
- power_coverage_cells 的覆盖半径展开 (含边界裁剪) 是否与模板 `power_coverage_radius` 语义一致? 协议箱 omni_wireless 不生成端口的规则是否被正确实现 (只免端口, 不免供电/占格)?
- port_mode / 端口 indices 过滤: 同一 orientation 不同 port_mode 的 pose, 端口子集选取是否与规格一致?

### Q2 枚举完备性 (漏 pose = 最优性主张破产)
- anchor 扫描范围: x ∈ [0, 70-w], y ∈ [0, 70-h] 这类边界是否 off-by-one? 旋转后用的是旋转前还是旋转后的 w/h?
- orientation × port_mode 组合是否穷尽 (有没有合法组合被静默跳过)? 跳过的条件 (如重复 pose 去重) 会不会误杀几何上不同的 pose?
- 模板覆盖: `load_templates` 从 canonical_rules 读模板时有没有模板被静默丢弃 (缺字段 fallback / continue)?

### Q3 实例集与需求数学
- `solve_demands` / `generate_ceil_machine_counts` 的产能链算术 (ceil 的方向、上下游速率匹配) 是否会**少算**强制机器数 (少算 = 解空间被错误放宽 = false CERTIFIED 风险) 或**多算** (= 过约束 = 假 INFEASIBLE/丢最优)?
- `build_manufacturing_instances` / `build_boundary_ports` / `build_core_instance` 生成的 266 强制实例: bound_type/solve_modes 标记、TEMPLATE_MAPPING 映射有没有错位? 与包内冻结 `mandatory_exact_instances.json` 对账。
- `generate_generic_io_requirements` 的全局池化 IO 需求与 binding 侧消费语义是否一致 (全局池 vs per-line)?

### Q4 可机检不变量 (建议实跑)
现场 `generate_all_pools` 后, 对生成池跑你自己写的不变量检查: 每个 pose occupied_cells 全在 70×70 内且互不重复、cell 数 = w×h (本体矩形模板)、端口格全在本体外一格且法向背离本体、power_coverage 含本体投影区、pool key 与 canonical 模板 key 一一对应、每模板 pose 数与 anchor×orientation×port_mode 组合数的解析公式吻合 (差额要能逐条解释)。任何不变量破 = finding。

## 明确不要报的

- 52-Port 不变量 (R=S=52, output 满占是 by-design, 上轮已 refuted 的 C-1 误判)。
- routing 侧 front 推导的"二次偏移"怀疑 (已 refuted, 单次偏移正确)。
- `candidate_placements.json` 不在包内这件事本身 (已知外置)。`test_preprocess_golden` 在包内会环境性失败 (对比目标缺失), 非 finding。
- exploratory-only 的 cap/路径; proof-carrying certificate (future work)。

## 自验环境与已知基线

- `python scripts/check_p1_2_proof_obligations.py` 应 pass (8 obligations anchored)。
- `python -m pytest -q src/tests/test_p0_certified_soundness_fixes.py` 基线 **12 passed**。
- 已知环境性失败 (非 finding): test_binding 10 ERROR / test_regression 5 / test_routing 3 / test_master 1 / test_preprocess_golden 1; 其余约 2845 应过。
- finding 必须带可复现 probe (现场生成 + 不变量违例实证 = 金标准) 或严谨数学论证 (具体到 file:line); 实证推翻了你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression; **关键论证写在回复正文**。
- **若审完确认该面 sound, 明确写「本轮零 soundness finding」** + 列实际审过的面、跑过的不变量检查、论证依据。

## 范围边界

- 只审 preprocess 链 (上列模块) 及其与冻结 artifact / canonical_rules 的契约; 求解器内核 (master/binding/routing/cuts) 已多轮收口, 只在「preprocess 产物语义与内核消费语义错位」时才越界报。
- P1.3B `step_8_apply_to_master` 禁区; exploratory 不审。

包 sha256: `324156a68d340c651c334f23220e9b6554f433b4fb5dec6bba3924c8a3d769a7`
