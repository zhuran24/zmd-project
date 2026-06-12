# 终末地 IndustrialPlanner 精确求解器 — binding 建模忠实度面 round 2 (F-BIND-R1 修复确认轮)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_fbind_r2_snapshot_6a9c241a.zip`, sha256 `6a9c241a88a65ed4fca755c6df5e50c1cfe1d051375856e8a59ecde434e7eb46`。**只认这个文件名, 文件区其它旧快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → **binding 端口绑定** → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 背景: round 1 爆 2 个 HIGH, 本包刚落地其修复

binding 建模忠实度面 round 1 报告在包内 `cc_context/review/archive/algoaudit_binding_face_r1_REVIEW_20260612.md`, 抓到:

- **F-BIND-R1-01**: generic output 槽 domain 只含真实商品变量 (无 `__unused__` 哨兵), 把当前基地「52 需求 = 52 槽满额」(specs/04 §4.5) 的数值巧合硬编码成 domain 结构假设 → 需求<槽数时合法空置 (specs/03 多处「多余端口允许空置」) 被判 INFEASIBLE = false-INFEASIBLE 方向。
- **F-BIND-R1-02**: `load_generic_io_requirements` / `load_wireless_sink_generic_input_slots` fail-open — 缺 section 静默当空需求 (真实需求消失 = false-FEASIBLE 方向); `int()` 收 bool/浮点截断/字符串; 不校验 canonical 商品角色 (中间品如 steel_block 可冒充无线终品被 wireless sink 吞掉, port_specs 为空, routing 不兜底)。

本包已落地修复 (`src/models/binding_subproblem.py` + 回归 `src/tests/test_binding.py` 尾部 6 条):
- generic output 槽 domain = 真实商品 ∪ `__unused__`, 槽内 ExactlyOne 保留; 真实商品的精确计数约束 (`_add_generic_output_requirements`, sum == 需求量) **未动** — 52=52 时计数逼满、哨兵恒 0, 当前基地行为零变化; `extract_port_specs()` 跳过哨兵。
- 双 loader fail-closed: 顶层/段必须是对象, 双 section 必须在场, 槽数严格非负 int (拒 bool/float/str), `__unused__` 保留名; 默认 artifact 装载路径 (`validate_against_canonical=True`) 校验 generic output 商品 canonical `source_kind == "external_boundary"`、generic input 商品 `sink_kind == "generic_input"`。构造器显式传参路径只做 normalize 不做角色校验 (test-fixture-only; 生产三调用点 benders_loop:4909/:5813、heuristic_feasible_finder 均不显式传参, 全走 loader 校验路径)。
- PROJECT_LOCK 新增 F-BIND-R1-01/02 两条款; specs/04 §4.5 加实现注记 (满额是计数推论非 domain 公理); specs/05 §5.4.3 加 generic output 对称段。

你的任务: 对抗式审查 r1 修复——确认正确且没引入新缝, **并把同类问题泛化穷举**。**若审完无残留, 明确报零** (本面饱和判据 = 连续 2-3 轮独立零 finding, 这是确认轮)。

## 审查重点 (按优先级)

### Q1 r1 修复本身
- F-01: 加了哨兵后, 当前基地 52=52 满额语义是否**可证明地**不变 (计数约束真的逼满? 有没有解空间里哨兵非 0 但计数仍满足的形态)? `extract_selection` 把哨兵写进 selection、`add_nogood_cut` 对含哨兵的 selection 取反 — nogood 形状会不会因哨兵参与而变宽/变窄? 哨兵会不会从任何路径漏进 routing/flow/master (查 `extract_port_specs` 之外的 selection 消费者)?
- F-02: canonical 角色校验的两个角色判据 (`source_kind == "external_boundary"` / `sink_kind == "generic_input"`) 是否恰好是正确的合法集 (canonical 里有没有第三种合法角色被误拒, 或不合法角色被漏放)? `validate_against_canonical=False` 的 toy 后门有没有被生产代码可达的路径 (穷举 `load_generic_io_requirements(` 与 `PortBindingModel(` 全部调用点)? 显式传参路径 normalize 拒了 bool/负数但不做角色校验 — 有没有生产侧能把显式 map 喂进来的缝?

### Q2 泛化: binding 还有哪些「当前 base 数值巧合被硬编码成结构假设」? (最重要)
F-BIND-R1-01 的本质 = 「用当前冻结数据的偶然性质替代规则的一般语义」。请在 binding_subproblem.py 全文穷举同类: fixed operation 的 pattern 枚举 (`_build_fixed_operation_domains` / `port_binding.enumerate_pose_level_port_bindings_with_cache_info`) 有没有依赖「当前 recipe 槽数 ≤ 当前 pose 端口数」之类的巧合? wireless sink 槽数 3 / pose-optional 物化 / storage overload 分类有没有把当前 base 形态当公理? `_ordered_generic_slot_commodities` 的排序假设? 哪些假设在 canonical 扩展 (新增 recipe/commodity/base) 时会静默变错而不是 fail-closed?

### Q3 泛化: 还有哪些 loader/数据入口 fail-open?
F-BIND-R1-02 的本质 = 「数据入口静默容错让坏数据变成错误模型」。binding 链上还有哪些 json/工件入口 (operation_profiles? preprocess_context 喂进来的字段? placement_solution/facility_pools 的字段读取 `.get(..., default)`)? **r1 已挂账**: `src/models/master_model.py` 的 `load_generic_io_requirements_artifact` / `_normalize_generic_io_requirements_payload` 仍宽松 — 请独立判定它的宽松行为是否真的到不了 certified 证明面 (master 拿 generic IO 需求做什么? 它的错误值会不会影响 master 的可行域或 objective, 从而间接影响认证结论?)。

### Q4 r1 "无 finding" 复核结论抽查
r1 判了: `_add_search_guidance` 只 AddDecisionStrategy 无硬约束 (AI 合同); `add_nogood_cut` 形状恰好否定当前投影; `solve()` 状态映射 TIMEOUT 不会被当 INFEASIBLE 消费; storage overload nogood env 默认关 + certified env guard 阻断; RAB 证书保守不更宽。抽查其中论证最薄的 1-2 项, 独立验证或推翻。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless 语义/52-Port 不变量本身, owner 已定); C-1 是已 refuted 误判 (其补丁改坏精确计数, 与 F-BIND-R1-01 修法不同——后者保留计数)。
- preprocess 面 r1-r7 已审结论; campaign/scheduler 面 (连零 1); master 几何面; cuts 机制面。
- master_model loader 宽松**本身**已挂账 — 只有当你论证它真能影响认证结论时才升报 finding。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2923 passed, 0 failed)**; 跑不完就跑专项 (test_binding / test_wireless_sink_binding_semantics / test_exact_contract / test_master) + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。最小 probe 可直接实例化 `PortBindingModel`。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 同批推进的登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2/Q3 实际穷举过的假设/入口清单。

## 范围边界

- 重点 = F-BIND 修复面 + Q2 结构假设穷举 + Q3 数据入口穷举; 其余面不审。
