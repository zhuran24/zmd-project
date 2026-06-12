# 终末地 IndustrialPlanner 精确求解器 — preprocess 面 round 6 (非 wireless 角度全面续审, 饱和轮)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_v80_impl_full_20260612_single.zip`, sha256 `e676c94dcc8477d087c916299486bea08c0d5a23dfd31d20b2c4c5842684fa52`。**开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。

## 背景: 本面前 5 轮已收口 wireless 弧线, 本轮换角度

preprocess 面 (candidate 池生成 + 需求/IO 推导链) 此前 5 轮全部聚焦 wireless/routing-free 修复链 (r1 F-01/F-02 协议箱几何 → r2 F-03 生产端泄漏 → r3 RAB 侧门 → r4 四组 raw port/front 侧门 → r5 零 finding 确认收口; 归档在包内 `cc_context/review/algoaudit_preprocess_face_r{1,2,3,4}_REVIEW_20260612.md`, r5 报告打包后归档不在包内——其结论: 4 组 r4 修复正确完整, 全部 raw port/front 消费点穷举无第五处缝)。

**本轮任务: 用全新视角审 preprocess 面的"其余部分"** — wireless 链已审透, 不要再当主攻面 (除非你发现非 wireless 部分与它交互出新缝)。目标是确认这个面除了已修的 wireless 弧线之外没有别的 soundness 问题。**若审完无 finding, 明确报零** (本面饱和判据 = 连续 2-3 轮独立零 finding, 这是第 2 轮)。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。certified 路径事实根基 = `rules/canonical_rules.json` + `data/preprocessed/` 三件 (candidate_placements / mandatory_exact_instances / generic_io_requirements)。

## 审查重点 (按优先级)

### Q1 需求/IO 推导数学 (demand_solver 链)
`src/preprocess/demand_solver.py` 及其输出 `data/preprocessed/generic_io_requirements.json` 与 `mandatory_exact_instances.json`:
- production_targets (`equivalent_full_speed_lines` 等 mode) → 各 recipe 实例数 → 266 强制设施清单的推导是否数学正确 (速率/配比/上下游平衡)?
- `required_generic_outputs` / `required_generic_inputs` 的计数语义与 binding 侧消费 (`binding_subproblem` 的池化绑定数学) 是否一致 — 多算 = 过约束 (false-INFEASIBLE 风险), 少算 = 漏需求 (false-CERTIFIED 风险), 两个方向都要看?
- 取整/向上取整位置: 任何 fractional line count 的处理是否在 soundness 正确的方向?

### Q2 candidate 池生成 (非 wireless 设施类型)
`src/placement/placement_generator.py` 对 manufacturing / power pole / boundary_storage_port 等其余设施类型:
- pose 枚举完备性: orientation × port_mode × anchor 范围有没有漏 (漏枚举 = 破坏 max_lex 最优性前提"候选域穷尽合法摆位")?
- `occupied_cells` / port cell / routing front 几何对非 wireless 类型是否正确 (F-02 的 front 越界修复只对齐了检查位置, 其它类型的边界判定独立看)?
- `is_edge_starved` 等过滤器会不会**错杀合法 pose** (过滤过强 = 漏枚举)?
- 与 canonical `port_rule` / facility 定义的一致性 (生成器是否忠实投影 canonical 几何契约)?

### Q3 operation profiles 与 canonical 投影
`src/preprocess/operation_profiles.py` + `rules/canonical_rules.json` 17-recipe 投影:
- 每个 operation 的 input/output slots (commodity → 口数) 与 canonical recipe 定义一致吗? 任何 slot 数/commodity 错位都会顺着 binding/routing 传播。
- `rules/preprocess_plan.json` 的消费 (utility_operations 等) 有没有 plan 与 canonical 冲突时静默偏向一边的点 (应 fail-closed)?

### Q4 工件确定性与冻结纪律
- `candidate_placements.json` 再生确定性: 生成器有没有非确定性源 (set/dict 迭代序进输出、平台相关浮点) 会破坏 bit 级可复现 (登记 hash `adcc2a6e…`, 45,773,799B)?
- resume 撞 stale 工件 hash 的 fail-closed 路径是否完备 (任何绕过 hash 检查直接读工件的入口?)。

### Q5 交互缝 (轻量)
preprocess 输出三件 (placements / instances / io_requirements) 之间的一致性约束有没有校验缺口 (例: instances 引用的 facility_type 不在 placements 池 / io_requirements 引用的 commodity 不在 canonical)? 不一致时是 fail-closed 还是静默?

## 明确不要报的

- wireless/routing-free 链主体 (r1-r5 已收口; 只有当非 wireless 部分与它交互出**新**缝才报)。
- 设计决策 (canonical 17-recipe 投影范围 / 266 实例口径 / omni_wireless, owner 已定)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); data/hints stale (已档); 根目录裸 pytest 误收集 `补丁包/` 归档 (已知, 用 `src/tests` 限定); 已 refuted 误判。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2908 passed, 0 failed)**; 任何 failed 都值得查 (沙盒跑不完全量就跑专项 + 声明, 别假装跑完)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾); 关键论证写正文。
- **冻结工件条款 (本轮范围特别相关)**: 若修复牵涉 `data/preprocessed/` 三件或 `rules/canonical_rules.json` (登记 hash 的冻结工件), 交付必须包含: ① 工件再生命令与步骤; ② 再生后的期望 sha256 与字节数; ③ 明确列出哪些登记位置要同批推进 (`scripts/preflight_gate.py::FROZEN_ARTIFACTS` / PROJECT_LOCK / specs 中的 hash 引用)。漏了这个 = 落地即 CI 红。canonical_rules 的内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列实际复核过的推导链/生成器路径/一致性面清单。

## 范围边界

- 重点 = preprocess 面非 wireless 部分 (Q1-Q5); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; postprocess/adapter (`src/adapters` `src/render` `data/exports`) 不审。
