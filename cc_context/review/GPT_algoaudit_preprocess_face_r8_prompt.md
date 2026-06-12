# 终末地 IndustrialPlanner 精确求解器 — preprocess 链面 round 8 (饱和确认轮·枚举完备性与解析纵深角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_fbind_r3_snapshot_50360c1d.zip`, sha256 `50360c1d82504d4de5b5af026c00d8d235db8ded32304b293a3d0d8a7c550893`。**只认这个文件名, 文件区其它旧快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: preprocess 链 (candidate/instance/需求工件生成), r1-r7 已收敛, 本轮是饱和确认

preprocess 面历史 7 轮 (报告在包内 `cc_context/review/archive/algoaudit_preprocess_face_r{1..7}_REVIEW_20260612.md`): r1-r4 修掉 wireless routing-free 链 4 批 finding; r5 零 finding; r6 抓 R6-F-01 (preprocess_plan 静默覆盖 canonical + hash 闭包缺口, 已修: additive-only fail-closed + OPTIONAL_EXACT_HASH_FILES); r7 零 finding (R6-F-01 修复确认 + 16 类 runtime 输入面 hash 闭包穷举)。**当前连零 1, 本轮 r8 = 第 2 个干净轮确认, 刻意换角度**——前 7 轮主攻 port/front 语义与 hash 闭包, 本轮主攻**枚举完备性**与**解析纵深**。

注意: 包内 binding/master 侧带着 face 6 (binding 面) 刚落的 F-BIND-R1/R2 修复 (lock 末新增 4 条 F-BIND 条款); preprocess 链本身自 r7 后零代码变化。

## 审查重点 (按优先级)

### Q1 candidate_placements 生成器枚举完备性 (最重要)
`src/placement/placement_generator.py` 生成 `data/preprocessed/candidate_placements.json` (再生命令见下, 期望 sha `adcc2a6e…`)。这是 certified 搜索的**候选全集**——枚举漏掉合法 pose/anchor = 该 pose 永不被考虑 = false-INFEASIBLE 方向 (max_lex 下可漏真最大矩形 = objective 级 false-CERTIFIED)。请独立审查: 每类 facility 的 (orientation × port_mode × anchor) 枚举是否穷尽规则允许的全域? 边界处 anchor 裁剪是否恰好 (off-by-one 会剪掉贴边合法 pose)? 旋转/镜像对称的处理是否漏掉非对称 pose 变体? `occupied_cells`/port cell 推导对每个 orientation 是否正确 (错误的 footprint 会让 master 误判重叠)? 与 canonical `facility_metadata`/`port_rule` 对照, 有没有 facility 类型被静默跳过?

### Q2 preprocess 链解析纵深
face 6 r2 刚在 binding/master 链修了 F-BIND-R2-02 (默认 `json.loads` 接受重复 key last-write-wins 与 NaN/Infinity — 重复 key 可静默改写语义)。请穷举 **preprocess 链自己的** JSON 装载点 (canonical_rules 装载、preprocess_context 构建、operation_profiles、placement_generator 读规则、mandatory_exact_instances 生成与消费、generic_io_requirements 生成侧): 哪些用默认 `json.loads`? 对每一处判定: 重复 key/NaN 在该处是否构成实际语义改写路径 (该工件是否在 exact hash 闭包内不是免罪牌——hash 闭包挡 resume 漂移, 不挡首次构建时的坏工件)? 注意 binding/master 侧三处已修 (`_loads_strict_json`), 别重报。

### Q3 demand→instance 展开数学抽查 (换角度复核 r6 已审结论)
r6 审过 266=219+46+1 推导/池计数 66403/52 槽平衡。本轮换审: specs/04 §4.6 ceil 规则 (理论台数→整数台数) 与 `mandatory_exact_instances.json` 实际内容的一致性 — 每类机器的 N_m 是否恰好 = ceil(理论值)? 有没有"按单一工序向上取整"被实现成"按合并工序取整"之类的偏差? 取整后的冗余台数 (如灌装机 2.75→3) 在 binding/flow 的需求侧是否被正确处理 (冗余机器的端口需求会不会被错误强制满载)?

### Q4 preprocess→binding 新契约涟漪
F-BIND-R1-02/R2-01 给 binding/master 的 generic IO 装载加了 canonical 角色校验 (generic output 必须 `source_kind=external_boundary`, generic input 必须 `sink_kind=generic_input`)。请验证 preprocess **生成侧**与新消费契约无矛盾: `generic_io_requirements.json` 的生成路径产出的商品集是否保证满足角色约束 (生成器自己有没有校验, 还是只是当前数据恰好合法)? 若 canonical 未来 owner-gate 扩展新商品角色, 生成侧会先于消费侧报错还是静默产出将被消费侧拒绝的工件 (后者 = 可接受的 fail-closed, 前者更好, 都不是 = finding)?

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r1-r7 已修 finding 与已审结论 (报告在包内, 重复报不算); face 6 的 F-BIND 系列 (binding 面在另一条线收敛中, 本轮只审 preprocess 链)。
- binding/master/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- commodity_demands.json 不在 hash 闭包 (r7 已判 diagnostic-only 无需, 再审触发条件 = 未来 certified 分支依赖它)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2927 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。枚举完备性类 finding 给出具体被漏的 pose/anchor 实例。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉 candidate_placements 再生或登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 同批推进的登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 实际核过的 facility×orientation 枚举矩阵与 Q2 装载点清单。

## 范围边界

- 重点 = 枚举完备性 + preprocess 解析纵深 + 展开数学抽查 + 生成/消费契约涟漪; 其余面不审。
