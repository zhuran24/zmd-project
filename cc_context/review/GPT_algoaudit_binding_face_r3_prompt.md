# 终末地 IndustrialPlanner 精确求解器 — binding 建模忠实度面 round 3 (F-BIND-R2 修复确认轮)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_fbind_r3_snapshot_50360c1d.zip`, sha256 `50360c1d82504d4de5b5af026c00d8d235db8ded32304b293a3d0d8a7c550893`。**只认这个文件名, 文件区其它旧快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 背景: 本面收敛轨迹 r1 (2 HIGH) → r2 (r1 修复 sound, 又 2 HIGH) → 本轮 r3

binding 建模忠实度面前两轮报告在包内 `cc_context/review/archive/algoaudit_binding_face_r{1,2}_REVIEW_20260612.md`:

- r1: **F-BIND-R1-01** (generic output 槽缺 `__unused__` 哨兵, 52=52 满额巧合被硬编码成结构假设) + **F-BIND-R1-02** (generic IO/无线槽数 loader fail-open + 无 canonical 角色校验) — r2 已确认其修复 sound (含 52=52 哨兵恒 0 代数证明)。
- r2: **F-BIND-R2-01** (master 侧 `load_generic_io_requirements_artifact` 保留第二个宽松解析分叉, 而 certified session 在 binding 之前就把它喂进 `build_exact_core` 做硬约束与 certified optional 下界 → 坏 artifact 可造 false-INFEASIBLE) + **F-BIND-R2-02** (proof 输入 JSON 用默认 `json.loads`, 重复 key last-write-wins 可静默清空需求段/改无线槽数, 且收 NaN/Infinity)。

本包已落地 r2 修复 (`src/models/binding_subproblem.py` + `src/models/master_model.py` + 回归 test_binding.py/test_exact_contract.py 尾部):
- `master_model.load_generic_io_requirements_artifact()` 委托 `binding_subproblem.load_generic_io_requirements(project_root=...)` (fail-closed + canonical 角色校验), master 自己的 `_normalize_generic_io_requirements_payload` 同步收紧 (strict int/非负/拒哨兵)。
- strict JSON helper `_loads_strict_json` (拒重复 object key + `NaN`/`Infinity`/`-Infinity` 常量), `load_generic_io_requirements` / `load_wireless_sink_generic_input_slots` / canonical commodity_metadata 角色读三处换用。
- PROJECT_LOCK 新增 F-BIND-R2-01 (proof-surface 单一装载入口, 禁第二解析分叉) / F-BIND-R2-02 (proof 输入 strict JSON) 两条款; specs/05 §5.4.3 同步。

你的任务: 对抗式审查 r2 修复——确认正确且没引入新缝, **并把同类问题泛化穷举**。**若审完无残留, 明确报零** (本面饱和判据 = 连续 2-3 轮独立零 finding)。

## 审查重点 (按优先级)

### Q1 r2 修复本身
- R2-01: master loader 委托后, master 与 binding 消费的 requirements 是否**字节级同源** (有没有委托后再加工/缓存导致两边漂移的路径)? `_normalize_generic_io_requirements_payload` 收紧后还有没有调用方依赖旧宽松行为 (grep 它的全部调用点)? 委托引入的 canonical 角色校验在 master 构造时机是否会对合法 synthetic/test 工程造成误拒 (查 master loader 的全部生产与测试调用点)?
- R2-02: `_loads_strict_json` 的 duplicate-key 检测实现 (object_pairs_hook) 是否覆盖**嵌套**对象的重复 key? `parse_constant` 拦截是否完整 (NaN/Infinity/-Infinity 三个都拦)? 还有没有 proof 输入装载点没换 strict (穷举 binding/master 链上所有 `json.loads`/`json.load` 调用)?

### Q2 泛化: 还有哪些 proof 输入存在第二解析分叉? (最重要)
F-BIND-R2-01 的本质 = 「同一 proof 工件存在两个解析器, 宽松的那个先到 proof surface」。请穷举 certified 链上所有读同一工件/同一规则源的多处装载: `mandatory_exact_instances.json` / `candidate_placements.json` / `canonical_rules.json` / `preprocess_plan.json` 各有几个独立 loader? 各 loader 的 schema 严格度是否一致? 有没有「A 处 fail-closed、B 处 .get(default) 宽松」的分叉对? 特别注意 `load_project_data` / preprocess_context / operation_profiles 与 binding/master 各自的读取路径。

### Q3 泛化: strict JSON 之外还有哪些解析层缝?
重复 key 之外: 整数精度 (JSON 大数→float 精度损失)? 字符串 NFC/NFKC 归一化差异 (commodity 名同形异码)? 编码 (BOM/UTF-8 严格性)? 这些对 proof 输入是否构成实际可达的语义改写路径 (有实证才报, 理论性的列出即可不算 finding)?

### Q4 前两轮 "无 finding" 复核结论抽查
r2 判了: fixed pattern 枚举端口数充足 (17 类 operation 全检) / generic utility roster 硬编码与当前 profile 一致 / pose-optional map 一致 / `_ordered_generic_slot_commodities` 仅 hint / overload+RAB env 被 certified guard 拦。抽查其中论证最薄的 1-2 项, 独立验证或推翻。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); C-1 已 refuted (其补丁改坏精确计数; F-BIND-R1-01 修法保留计数, 不同)。
- generic utility roster 的 owner-gate 扩展 guard 建议 (r2 已挂账, 扩展时才需要); preprocess 面 r1-r7 已审结论; campaign/scheduler 面; master 几何面; cuts 面。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2927 passed, 0 failed)**; 跑不完就跑专项 (test_binding / test_exact_contract / test_master) + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 同批推进的登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 实际穷举过的工件×loader 矩阵与 Q3 检查清单。

## 范围边界

- 重点 = F-BIND-R2 修复面 + Q2 解析分叉穷举 + Q3 解析层缝; 其余面不审。
