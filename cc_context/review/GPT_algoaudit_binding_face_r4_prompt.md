# 终末地 IndustrialPlanner 精确求解器 — binding 建模忠实度面 round 4 (F-BIND-R3 修复确认轮)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_audit_snapshot_6867b7ce.zip`, sha256 `6867b7ce75b5aa61efe9864572cc1b2781ea68d07bcf7efeca28a3ec8ee3487b`。**只认这个文件名, 文件区其它旧快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面收敛轨迹: r1 (2 HIGH) → r2 (r1 sound, 又 2 HIGH) → r3 (r2 sound, 又 5 HIGH) → 本轮 r4

前三轮报告在包内 `cc_context/review/archive/algoaudit_binding_face_r{1,2,3}_REVIEW_20260612.md` (r3 文件名为 algoaudit_binding_face_r3_REVIEW_20260612.md)。收敛主线 = 「binding/master/campaign 的 proof 输入装载与建模忠实度」:

- r1: generic output 槽缺 `__unused__` 哨兵 (52=52 巧合硬编码) + loader fail-open。
- r2: master loader 第二解析分叉进 proof surface + 默认 json.loads 收重复 key/NaN。
- r3: 五个「单解析/单快照」缝 — binding 重读磁盘 (两时间点快照) / master `_load_json` 默认 JSON / preprocess_context 槽数 `int()` 吞类型 / wireless 槽数用 import-time 默认 profile 不进 master 快照 / campaign helpers 私有解析绕过角色校验。

本包已落地 r3 修复 + CC 连带 (`6c70b7d` + `95ea3da`):
- `benders_loop._binding_generic_requirements_kwargs()`: certified 模式下 binding (主 + overload retry) 显式接收 `self.master.generic_io_requirements` normalized 快照, master 无快照属性时 RuntimeError fail-closed; 非 certified 返回空 kwargs。
- `master_model._load_json` strict 化 (mandatory/candidates/canonical 三工件)。
- `preprocess_context._strict_nonnegative_int` 槽数收紧 (strict JSON 半已由 preprocess 面 F-PRE-R8-01 先修, 共享 `src/io/strict_json.py`)。
- `infer_certified_optional_lower_bounds(wireless_sink_generic_input_slots=...)` 参数化; certified session 从 project-root plan 读槽数传给 master core / outer safe-area / campaign helpers / coordinate stats。
- `exact_campaign` proof helpers 委托 `load_generic_io_requirements_artifact`。
- **CC 连带**: 16 个 synthetic 工程测试 fixture 升级 (空 `{}` 需求工件→双 section / 补 commodity_metadata / 补 plan 文件 / mock master 补快照属性 / delivery_manifest stale 测试改为「过 loader 但 bytes 不同」的篡改物保持 hash-staleness 意图) — 方向为 fixture 跟上 fail-closed 契约, 未放松实现; mypy kwargs 类型修正。
- PROJECT_LOCK 新增 F-BIND-R3 单快照综合条款; specs/05 同步。

你的任务: 对抗式审查 r3 修复与 CC 连带——确认正确且没引入新缝, **并把同类问题最后一遍泛化穷举**。**若审完无残留, 明确报零** (本面饱和判据 = 连续 2-3 轮独立零 finding; r1-r3 连续出货, 本轮是首个潜在干净轮)。

## 审查重点 (按优先级)

### Q1 r3 修复本身 (最重要)
- R3-01: binding kwargs 注入后, `PortBindingModel.__init__` 收到显式 maps 时**跳过 loader 的 canonical 角色校验** (r2 设计: 显式传参 = test-fixture-only 只 normalize) — 但现在生产路径也显式传参了! master 快照本身来自 validated loader 所以语义上等价, 验证这个等价推理是否有洞 (master 快照在 session 生命周期内会不会被改写? `build_exact_core` 或其它代码有没有 mutate `generic_io_requirements` 的路径?)。overload retry (benders_loop:5851 附近) 与主 binding 用同一 kwargs helper — retry 时 master 快照还是同一个对象吗?
- R3-04: 槽数参数化的四个消费点 (master core / outer safe-area / campaign helpers / coordinate stats) 是否**全部**收到同一 project-root 值? 有没有第五个消费点仍用 import-time profile (穷举 `get_operation_port_profile("wireless_sink")` 与 `generic_input_slots` 的全部引用)? campaign helpers 在 required_generic_inputs 为**空**时跳过槽数读取 (传 None) — None 路径下 `infer_certified_optional_lower_bounds` 的行为与显式槽数路径在空需求时是否一致?
- CC 连带: 16 个 fixture 升级有没有**改变测试原意** (尤其 delivery_manifest stale 测试 — 新篡改物是否仍然有效触发 hash mismatch 这条具体防线)? mock master 补的快照属性会不会让该测试错过真实 master 缺属性的回归场景?

### Q2 终遍泛化: proof 输入链还有残留缝吗?
r3 已给出 5 工件×loader 矩阵。请独立重建这个矩阵并找它的盲区: r3 矩阵之外还有 proof-relevant 输入吗 (campaign checkpoint 自身的 strict 解析? terminal evidence 的重算输入? blueprint/manifest 读回路径? `_load_overload_classification` 虽 env 关但它的解析?)? 矩阵内每格的"已修"声明抽查 2-3 格实证。

### Q3 修复交互
r1+r2+r3 三批修复在同一文件密集落地 (binding_subproblem / master_model / exact_campaign): 哨兵逻辑 × 快照注入 (显式传参路径现在也用于生产 — 哨兵保留名校验在 normalize 路径上仍生效吗?); strict JSON × 委托链 (同一工件经 binding loader 与 master `_load_json` 两条 strict 路径 — 它们对同一坏工件的拒绝行为一致吗, 还是一个 KeyError 一个 ValueError 导致上游 catch 行为分叉?); F-PRE-R8 共享 strict_json 模块 × binding/master 各自私有 helper — 三套 strict 实现语义一致吗 (建议但不强制统一)?

### Q4 前轮"无 finding"复核抽查
r3 判了: 嵌套重复 key probe 过 / 大数精度无损 / 同形异码 fail-closed / BOM 拒收 / `add_nogood_cut` 含哨兵 selection 形状恰好。抽查最薄的 1-2 项独立验证或推翻。

## 明确不要报的

- r1/r2/r3 已修 finding 本体 (重复报不算; 修复的**新缝**算)。
- 三套 strict JSON helper 未统一**本身** (风格问题; 若语义不一致才是 finding)。
- 双 coordinator lockfile (face 7/8 r3 已挂账运维硬化); generic utility roster 扩展 guard (r2 已挂账)。
- 设计决策 (canonical/266/52-Port/omni_wireless, owner 已定); C-1 已 refuted。
- preprocess/campaign 状态机/scheduler/master 几何/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry (V82)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2941 passed, 0 failed)**; 跑不完就跑专项 (test_binding / test_exact_contract / test_master / test_preprocess_context) + 如实声明 (`-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 重建矩阵与 Q1 等价推理验证清单。

## 范围边界

- 重点 = R3 修复面 + CC 连带 + proof 输入终遍穷举 + 三批修复交互; 其余面不审。
