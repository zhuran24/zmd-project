# 终末地 IndustrialPlanner 精确求解器 — binding 建模忠实度面 round 7 (饱和确认轮·规则文本独立对照 + routing-free/generic IO 语义边界纵深)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_70457b5e.zip`, sha256 `70457b5e6cd759fd0fd75873b12b61f444ad3e569bb26216cea7aa383b22b15a`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: binding 建模忠实度, r1-r6 收敛轨迹 2→2→5→1→1→0, 本轮目标第 2 个干净轮

binding 面历史 6 轮 (报告在包内 `cc_context/review/` 与其 `archive/`, 文件名 `algoaudit_binding_face_r{1..6}_REVIEW_20260612.md`): r1 = `__unused__` 哨兵 + loader fail-closed; r2 = master loader 分叉 + strict JSON; r3 = 单解析/单快照族五连; r4 = wireless 槽数漏注入 binding; r5 = outer 候选域封印 + worker hash 校验; **r6 = 零 soundness finding (R5 修复四向确认 + 50+ 行消费点终验矩阵 + 枚举/对称数学: 置换对称穷尽实证、`__unused__`+ExactlyOne+精确计数对任意 R<=S 成立)**。**本轮 r7 = 确认轮, 刻意换两个此前未用过的角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BL-R3/R4 / F-GM-Q3 系列 / F-RT-R2..R4 / F-CUT-R2 + CUT-R3-H1/CUT-R4-H1 / F-PRE-R8/R9 系列条款), 这些面各有自己的线, 别在本轮重报。binding_subproblem.py 自 r4 修复后零代码变化 (r5/r6 改的是 outer/worker 侧)。

## 审查重点 (按优先级)

### Q1 规则文本 → 实现独立对照 (新角度; 方法论要求: 从 specs 推导, 不从实现学语义)
本项目曾发生过「验证器从实现学语义 → 与实现同源错」的真实缺陷 (routing 面 F-RT-R2-01: fuzz oracle 的 sink front 方向键复制了实现的反向极性, 900 实例对该缺陷类全盲)。因此本轮要求: **先读 specs (`specs/03_*.md` / `specs/04_*.md` / `specs/05_*.md` 中 binding/端口/commodity 相关章节) 与 `rules/canonical_rules.json`, 自己写下每条约束的预期语义, 再对照 `src/models/binding_subproblem.py` 的 CP-SAT 编码逐条核**: ① 每个 binding 约束族 (ExactlyOne / 精确计数 / fixed pattern / overload / wireless sink 槽) 在规则文本里的依据是什么 — 有没有实现比规则**更严** (排掉规则允许的配置 = false-INFEASIBLE 方向) 或**更松** (接受规则禁止的配置 = false-FEASIBLE 方向)? ② 规则文本里有而实现里**没有**编码的约束 (静默缺失 = binding 声称 FEASIBLE 但规则不允许)? ③ 端口侧别/商品方向 (输入口收什么/输出口发什么) 的极性在 binding 编码与 `extract_port_specs()` 输出之间是否一致且与规则同向?

### Q2 routing-free / generic IO 语义边界 binding 侧纵深 (新角度; 与 cuts 面 CUT-R4-H1 相邻但攻 binding 侧)
背景: cuts 面 r4 刚修了 CUT-R4-H1 — 「正数 required generic-output commodity 同时在 routing-free generic-input sink 集」时, binding 可把物理输出槽赋给该无线商品, `extract_port_specs()` 按 routing-free 丢弃它; cut 侧已 fail-closed, **cut 侧的修不要重报**。本轮从 binding 侧攻这条语义边界: ① `routing_free_sink_commodities` 的产生链 (canonical `sink_kind == generic_input` → demand 生成 → binding 构造参数) 与消费点 (extract_port_specs / 其它?) 是否语义一致 — 有没有第二个消费点用了不同的 routing-free 判定 (集合不同步 = 同一商品在 A 点被当 routed、B 点被当 free)? ② validator 不强制 `source_kind == external_boundary` 与 `sink_kind == generic_input` 两角色 disjoint (CUT-R4-H1 review 已确认) — 若未来 canonical 扩展真的引入重叠商品, binding 自身的编码 (不只 cut 侧) 还有哪些点会语义错乱 (required_generic_outputs 与 required_generic_inputs 同商品时: 计数约束互相独立吗? 同一物理槽会不会被两边重复计数? selection 提取会不会歧义)? 逐点判读「现在就错 (finding) / 重叠出现才错 (须挂 owner-gate 扩展守卫) / 永远不错 (论证)」。③ wireless sink 虚拟槽与物理 generic 槽在 binding 内的隔离: 虚拟槽永不进 port_specs 的保证在所有路径上成立吗?

### Q3 selection/nogood 表示完备性抽查 (r6 Q3 的余角)
r6 已证 nogood 恰排当前 selection 不漏邻近、置换对称穷尽收敛。本轮补抽: ① `extract_selection()` 的 key 集是否覆盖**全部** CP-SAT 决策自由度 (有没有 binding 里的自由变量不进 selection tuple — 两个不同解折叠成同一 selection = nogood 一次误排两个, 其中一个未证伪)? ② fixed/常量化的选择不进 nogood 的省略论证在 overload retry 场景下仍成立吗 (retry model 的 fixed 集与初始 model 可能不同)?

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r1-r6 已修 finding 与已审结论 (重复报不算)。
- preprocess/master 几何/campaign/scheduler/routing/cuts 各面 (各自有线); **CUT-R4-H1 的 cut 侧修复本体** (face 4 已修已验收)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- generic utility roster 扩展时的 profile-driven guard 建议 (r2 已挂账; 但 Q2② 若发现**具体**会错乱的编码点, 指明点位算新信息, 要报)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2968 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 实际对照过的「规则条文 ↔ 约束族」清单与 Q2 的三类判读表。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = 规则文本独立对照 + routing-free/generic IO 边界 binding 侧 + selection/nogood 完备性抽查; 其余面不审。
