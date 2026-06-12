# 终末地 IndustrialPlanner 精确求解器 — binding 建模忠实度面 round 1

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_f78r2_snapshot_13dc4e59.zip`, sha256 `13dc4e596b5327a8fc888a39d89405553bffb7fb4c993538755580b3accd22af`。**只认这个文件名, 文件区其它旧快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → **binding 端口绑定** → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义: binding 子问题的数学建模是否忠实于规则真相

审查对象 = `src/models/binding_subproblem.py` (`PortBindingModel`, ~825 行) 的**内部建模数学**。这是 8 个滚动审查面里唯一从未单独审过的面: 此前轮次审了 Benders 主循环 (面 1)、几何 master (面 2)、routing/guard (面 3)、cuts 机制 (面 4)、preprocess 链 (面 5, r1-r7 连零 1)、campaign/scheduler (面 7/8, 连零 1)——binding 只在 preprocess 面被审过**外围** (port_specs 的下游消费、RAB `_filter_pose_binding_domain` 的 routing-visible 过滤), 它自己的 domain 构建/约束编码/解提取/状态判读从未被独立攻击过。

规则真相源 (binding 必须忠实的对象):
- `rules/canonical_rules.json` — recipe/端口/commodity 语义的唯一权威
- `data/preprocessed/generic_io_requirements.json` — generic IO 需求 (装载器 `load_generic_io_requirements`)
- `data/preprocessed/mandatory_exact_instances.json` — 266 强制实例
- `specs/` 下 binding 相关 spec 与 PROJECT_LOCK 条款

错误方向定义 (都算 soundness):
- **binding 比真实规则严** (多余约束 / domain 漏合法 pattern / nogood 过宽) → 砍掉合法布局 = false-INFEASIBLE → max_lex 下漏真最大矩形 = objective 级 false-CERTIFIED;
- **binding 比真实规则松** (约束缺失 / 计数语义错 / 提取失真) → 不合法端口配对放行 = false-FEASIBLE; 注意下游 routing 只验连通性, **不会**重验槽位/商品语义, 所以 binding 放水不能指望 routing 兜底。

## 审查重点 (按优先级)

### Q1 domain 构建忠实度
`_build_fixed_operation_domains` / `_build_generic_output_domains` / `_build_generic_input_domains` / `_materialize_pose_optional_instances` / `_wireless_sink_input_slot_count`: 对照 canonical_rules + generic_io_requirements, 每类实例 (fixed operation / generic output / generic input / wireless sink / pose-optional) 的 binding domain 是否恰好 = 规则允许的 pattern 集? 重点攻击: 槽数计算 (off-by-one / 方向混淆 input vs output)、商品集推导 (漏商品 = 过严, 多商品 = 过松)、pose 与 port_mode 的对应、空 domain 的语义 (空 = 该实例无法绑定 → 谁消费这个信号, 会不会把"建模缺陷造成的空"当成"几何不可行的证明")。

### Q2 约束编码忠实度 (最重要)
`_add_generic_input_requirements` / `_add_generic_output_requirements` / `_ordered_generic_slot_commodities` / `_add_storage_box_overload_nogoods` / build() 主体的 CP-SAT 约束: 逐条对照规则文本, 计数语义 (恰好 N / 至少 N / 至多 N) 有没有用错方向? 槽位排序/对称破缺有没有把合法解排除掉 (对称破缺只能删对称重复, 不能删非对称合法解)? storage overload nogood 的分类装载 (`_load_overload_classification`) 与 nogood 形状是否只禁真正过载的组合? 任何 `OnlyEnforceIf`/bool 通道的方向性 (单向蕴含够不够, 要不要双向)?

### Q3 解提取与 nogood 形状
`extract_selection` / `extract_port_specs` / `add_nogood_cut`: 提取是否忠实于 solver 赋值 (有没有提取时改写/默认值填充导致 spec 与解漂移)? `extract_port_specs` 是 routing 的输入契约 — 它生成的 port spec 与 binding 解的槽位语义是否一一对应 (这里审**生成端**; 消费端 preprocess 面已审)? `add_nogood_cut` 的割是否恰好否定该 selection (字段子集参与 = 过宽割 = 误杀同 selection 族的合法变体)?

### Q4 状态判读与 Benders 接口
`solve()` 的状态映射 (OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN/TIMEOUT): INFEASIBLE 在 Benders 链里会触发什么 (master cut? 候选淘汰?), TIMEOUT/UNKNOWN 有没有被任何调用方当成 INFEASIBLE 消费 (查 `src/search/benders_loop.py` 的 binding 调用点)? `_add_search_guidance` 必须只是 hint 不是约束 (AI Safety Contract: hints 不准变 constraints) — 验证它没有 Add() 任何硬约束。`extract_routing_aware_certificates` (RAB, env `EXACT_B1_ROUTING_AWARE_BINDING` 默认关) 的证书语义: 证书声称的"空 binding domain"是否真的对所有 routing-visible pattern 成立?

### Q5 装载器与数据契约
`load_generic_io_requirements` / `load_wireless_sink_generic_input_slots`: 装载时的 schema 校验是 fail-closed 还是静默容错 (缺 key 默认值 = 危险方向)? 装载结果与 canonical 的一致性有没有任何运行时校验, 还是纯信任 preprocess 工件?

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless 无线箱语义, owner 已定); preprocess 面 r1-r7 已审结论 (port_specs 消费端 / routing-free sink 排除集 / dual-role 守卫 / RAB routing-visible 过滤 F03-R3-01 已修——但 RAB **证书本体**的有效性属本面 Q4, 可审)。
- cuts 机制内部 (面 4 已审); campaign/scheduler (面 7/8 连零 1); master 几何 (面 2)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 路径不审; persisted `exact_safe_cuts` 是 telemetry 不是 proof object (V82)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2917 passed, 0 failed)**; 跑不完就跑专项 (test_binding* 等) + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。构造 probe 时可以直接实例化 `PortBindingModel` 喂最小实例。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 同批推进的登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1-Q5 实际逐条核过的 domain 构建器/约束/提取器清单。

## 范围边界

- 重点 = binding_subproblem.py 内部数学 + 它与 benders_loop 调用点的状态契约; 其余面不审。
