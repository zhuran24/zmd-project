# 终末地 IndustrialPlanner 精确求解器 — Benders/LBBD 主循环面确认轮 (多批修复涟漪角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `{PACKAGE_NAME}`, sha256 `{PACKAGE_SHA256}`。**只认这个文件名, 文件区其它旧快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面历史与本轮定位

Benders/LBBD 主循环面 (`src/search/benders_loop.py` 的候选求解编排) 轮次史: 首轮抓 **A-1** (routing 局部连续 ≠ 全局连通 → false-CERTIFIED, 已修: post-solve 连通性 guard + lazy connectivity cut, 双独立零 finding 确认) 与 **A-2** (front_blocked 的 binding-local 证据跳过 binding 枚举直接铸 master pose-presence nogood → false-INFEASIBLE, 已修: 先 binding-level nogood 枚举替代 binding, 耗尽后才升 master-level)。修复确认 2 轮零 finding, **连零 2**。

**但**: 那两轮确认之后, `benders_loop.py` 又被多批其它面的修复反复改动 — wireless 链 (F03/F04-R4: routing-free sink 排除、RAB 过滤、deletion-core oracle 传参)、binding 面 (F-BIND: PortBindingModel 构造与 loader 链)、PCR-CUT hook、lazy cut 接线。**本轮 = 主循环涟漪确认轮**: 这些"别的面"的修复改没改坏主循环自己的状态机与证明语义。

## 审查重点 (按优先级)

### Q1 子问题状态消费矩阵穷举 (最重要)
对主循环单候选求解路径 (`_run_exact_binding_and_routing` 及其 caller 链), 穷举每个子问题状态组合的处置: binding {FEASIBLE, INFEASIBLE, TIMEOUT} × routing precheck {pass, front_blocked, relaxed_disconnected} × routing solve {FEASIBLE+guard-accept, FEASIBLE+guard-reject, INFEASIBLE, TIMEOUT} × guard {accept, reject, timeout}。对每个组合: 最终 candidate 状态 (CERTIFIED/INFEASIBLE/UNKNOWN/TIMEOUT) 是否唯一正确? 有没有组合落入"意外默认分支"被错误归类? TIMEOUT/UNKNOWN 在任何组合下都不得变成 INFEASIBLE 或 CERTIFIED (穷举验证, 不是抽查)。binding alternatives 枚举循环 (A-2 修复) 的终止条件与计数边界?

### Q2 nogood/cut 添加时机与作用域
主循环各分支添加的每种 nogood/cut (binding-level nogood / master placement nogood / lazy connectivity cut / deletion-core cut / lazy-demand / cell-cut): 添加条件是否都满足"被切对象已被证明不可行" (cut 有效性)? 同一候选多轮迭代中 cut 累积的单调性 — 有没有 cut 在后续迭代被错误复用到不同 binding 选择上? front_blocked 分支在 PCR-CUT env 关闭 (certified 默认) 时的回落链 (deletion-core → lazy_demand → cell_cut) 每一级的 fail-closed 衔接?

### Q3 多批修复的交互缝
逐对检查近期修复在主循环的交互: ① wireless routing-free 排除 (F03/F04) × A-2 binding 枚举 — routing-free 输出口被排除后, binding alternatives 的枚举域与 routing precheck 看到的端口集是否始终同步? ② F-BIND loader 链 × session 构造 — loader fail-closed 异常在 session/候选求解的哪一层被捕获, 会不会被 catch-all 吞成 UNKNOWN 而掩盖配置错误 (应该 loud fail)? ③ lazy connectivity cut × guard — cut 添加后重解的 incumbent 仍要过 guard, 这个循环的收敛保证 (cut 不命中新 incumbent 时的 fallback)?

### Q4 epsilon ladder 与 max_lex 语义抽查
候选按 area 降序扫描 + min_side 次序的 max_lex 实现: epsilon stage 推进逻辑在 UNKNOWN/TIMEOUT 候选存在时的 frontier 完备性主张 (一个 UNKNOWN 候选挡不挡得住比它小的 CERTIFIED 宣布 — 应该挡, 验证)? `best_certified_result` 与 frontier evidence 的一致性在主循环写入侧的保证?

## 明确不要报的

- A-1/A-2/lazy cut 修复本体 (已双轮确认; 但其与新修复的**交互缝**算)。
- 各子问题内部数学 (binding 面/routing 面/master 面/cuts 面各自有线; 本面只审主循环的**编排与状态消费**)。
- F-BIND/F78/wireless 系列修复本体 (各自线上已验收; 本面只审它们对主循环的涟漪)。
- 设计决策 (canonical/266/52-Port, owner 已定); 已 refuted 误判 (C-1/C-2/B-02)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2927 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (`-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 状态矩阵类 finding 给出构造该组合的最小实例; 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附 Q1 状态组合×处置矩阵全表。

## 范围边界

- 重点 = 主循环状态机/nogood 时机/修复交互/max_lex 编排; 其余面不审。
