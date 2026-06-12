# 终末地 IndustrialPlanner 精确求解器 — preprocess 链面 round 9 (饱和确认轮·r8 修复确认 + 工件交叉一致性与再生确定性角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_pre_r9_snapshot_ec504afe.zip`, sha256 `ec504afe704b4a1cea6597a3956d7e68fd5adc195961cd4724e69cd354ffb50f`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: preprocess 链, r1-r8 已收敛, 本轮是第 2 个干净轮确认

preprocess 面历史 8 轮 (报告在包内 `cc_context/review/` 与其 `archive/`, 文件名 `algoaudit_preprocess_face_r{1..8}_REVIEW_20260612.md`): r1-r4 修掉 wireless routing-free 链 4 批; r5 零 finding; r6 抓 R6-F-01 (plan 静默覆盖 canonical + hash 闭包缺口, 已修); r7 零 finding; **r8 抓 F-PRE-R8-01 (再生成链 4 个装载点默认 `json.loads`, 重复 key 首次构建可静默改写; 已修 = 共享 strict loader `src/io/strict_json.py` 四处换用 + 生成侧 `allow_nan=False`)**。r8 已审过枚举完备性 (独立重建 66403 池零差) 与 ceil 展开数学 (17 operation 全表)。**本轮 r9 = r8 修复确认 + 刻意换新角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND-R1..R5 / F-BL-R3 / F-GM-Q3 / F-RT-R2 / F-CUT-R2 系列条款), 这些面各有自己的线, 别在本轮重报。preprocess 链自 r8 修复后零代码变化。

## 审查重点 (按优先级)

### Q1 F-PRE-R8-01 修复确认 (攻击面)
把 r8 修复当攻击面打: ① `src/io/strict_json.py` 本体实现对不对 — 重复 key 检测的 object_pairs_hook 是否覆盖**嵌套对象**与**数组内对象**? `parse_constant` 拒 NaN/Infinity 是否覆盖 `-Infinity`? 有没有绕过入口 (比如某调用方传了自定义 kwargs 把 hook 顶掉)? ② 四处换用是否真的完整 — 请独立全仓穷举 preprocess **再生成链**上的 JSON 装载点 (含间接: utility/profile/plan/canonical/machine_counts/parity 消费), 找还有没有第五处默认 `json.loads`; 注意 binding/master 侧已由 F-BIND-R2/R3 修过, campaign/checkpoint 侧是另一条线, 别重报。③ 生成侧 dump `allow_nan=False` 是否覆盖所有 preprocess 工件写出点 (漏一处 = 可写出 NaN 工件, strict 读入时才爆 = 至少是再生链可用性缺陷, 若有路径先于 strict 读消费则更重)。

### Q2 工件交叉一致性 (新角度)
preprocess 产出三件套 (`candidate_placements.json` / `mandatory_exact_instances.json` / `generic_io_requirements.json`) 与 canonical 之间的**引用完整性**: instance 引用的 facility template / operation type 是否全部存在于 canonical 且 port profile 一致? candidate pool 的 template 集与 instance 的 template 集是否对齐 (有 instance 无 pool = 必 INFEASIBLE 方向; 有 pool 无 instance = 死候选, 完整性噪声)? generic_io_requirements 的商品集与 canonical commodity_metadata 角色是否闭合? 这些一致性是**生成时保证、消费时校验、还是只是当前数据碰巧一致** (最后者 = finding, 给出能通过生成但被消费侧静默吞掉的构造)?

### Q3 再生确定性 (新角度)
certified 流程假设 `candidate_placements.json` 可由 `python src/placement/placement_generator.py` 再生且 sha256 恰为 `adcc2a6e…`。请审: 生成器是否存在非确定性源 (dict/set 迭代序依赖、并行、时间戳、浮点格式化、平台行尾)? json dump 的 key 序/分隔符/ensure_ascii 是否钉死? 若 Python 小版本升级 (3.13.x → 3.14) 或 ortools 升级, 字节级再现是否仍有保证 (没有 = 记录为已知限制还是缝, 取决于 hash 校验失败时流程是 fail-closed 还是有静默回退)?

### Q4 r8 修复与 hash 闭包交互
r8 修复改了读入与写出代码但声明「candidate_placements 再生 hash 不变」。请独立复核: strict loader 与 `allow_nan=False` 在**当前合法工件**上是否真的零行为差 (字节级)? 有没有合法工件含重复 key 而 r8 前被静默接受、r8 后再生即报错 (若有, 当前冻结工件是否恰好干净)?

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r1-r8 已修 finding 与已审结论 (报告在包内, 重复报不算)。
- binding/master/campaign/scheduler/routing/cuts 各面 (各自有线; lock 末新条款即它们的产物)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- commodity_demands.json 不在 hash 闭包 (r7 已判 diagnostic-only, 再审触发条件 = 未来 certified 分支依赖它)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2951 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉 candidate_placements 再生或登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 同批推进的登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 装载点穷举清单与 Q2 实际核过的交叉一致性矩阵。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = r8 修复确认 + 工件交叉一致性 + 再生确定性 + hash 闭包交互; 其余面不审。
