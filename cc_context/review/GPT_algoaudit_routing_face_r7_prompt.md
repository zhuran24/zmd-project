# 终末地 IndustrialPlanner 精确求解器 — routing 编码面 round 7 (终饱和轮·CP-SAT 约束本体直审 + precheck 生产者本体 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_37b84be0.zip`, sha256 `37b84be0749893447ccab8113934d8a518237702de0e00ed8d64176a913c57dd`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: routing 编码 (routing_subproblem + guard + precheck), 收敛轨迹 2→1→2→1→0 (r6 零), 本轮 = 终饱和轮 (连零 2 达标轮)

本面近 4 轮 (报告在包内 `cc_context/review/archive/algoaudit_routing_face_r{3..6}_REVIEW_2026061x.md`): r3 = connector cell 当 belt 格穿过; r4 = 同商品多岛误拒 + 重复 terminal key; r5 = F-RT-R5-01 (外置 domain 不与 free_cells 求交可穿墙); **r6 = 零 soundness finding (首个干净轮)**: R5 修复三向确认 + guard 本体深审 (选中图直接来自 solver keys, 邻接与 CP-SAT successor/predecessor layer-agnostic 同构, 多源多汇 = existence/pooling, fail-closed) + 状态模式枚举完备性 (独立推导 48 pattern 封闭集合与实现 set-equality 相等)。差分对拍 fuzz 累计 ~1200 实例零不一致。**本轮 r7 = 终饱和轮: 三个此前未直审的本体角度, 目标确认连零 2**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL / F-GM 系列含 R7-HINT / F-CUT 系列含 PCR-CUT-R6-H1 / F-PRE 系列条款), 这些面各有自己的线, 别在本轮重报。routing_subproblem 主体自 r5 修复后零代码变化 (r6 零 finding 无补丁); PCR patch 模型是 cuts 面 (r6/r7 有自己的线), 本轮只审 full routing。

## 审查重点 (按优先级)

### Q1 CP-SAT 约束本体直审 (新角度; r6 是从 guard 侧证同构, 本轮直接从约束实现 vs specs 文本审)
先从 `specs/09_exact_grid_routing_subproblem.md` + `specs/03_rule_canonicalization.md:306-344` 独立写出 routing CP-SAT 模型应有的全部约束族清单, 再逐族对照实现 (`src/models/routing_subproblem.py` build 路径): ① **continuity (successor/predecessor)**: 每个选中 state 的每个 flow_out 必须有邻格接收者、每个 flow_in 必须有前驱发送者 — 实现的 AddBoolOr/OnlyEnforceIf 形态与「必须」语义等价吗 (遗漏方向 = false-FEASIBLE [必须查], 过强方向 = false-INFEASIBLE)? terminal 例外 (source ground side 无 predecessor / sink ground side 无 successor) 的实现边界精确吗 — 非 terminal 的同格其它 state 不被豁免? ② **per-edge channel conservation** (F-RT-R2-02 修复所在): 对每个有向格间边「发送数 == 接收数」— 求和的量化范围 (commodity × layer × state) 完整吗, 有没有某类 state (terminal 邻边/bridge 端点) 被漏在求和外? ③ **capacity AtMostOne per (cell, layer)**: 全部 state var 都进了对应 (cell,layer) 的 AtMostOne 吗 (漏一个 = 同格双组件)? ④ **bridge 共存约束**: 同格 L1 bridge + L0 限 straight belt — 「straight」的判据实现与 specs 一致吗, L0 empty 也合法吗? ⑤ **port adherence exact-one**: source/sink front 的 exact-one 量化的变量集 (`flow_in/out == Opp(dir)` 的全部 state) 与「恰好履行一次」语义一致吗 — splitter/merger state 含该方向时算不算履行?

### Q2 routing precheck 生产者本体 (新角度; 此前只审过它的消费侧)
`analyze_routing_domains` / precheck (`src/models/routing_subproblem.py` 前段 + benders_loop 调用点): ① **front_blocked 判定的两个方向**: 误报 blocked (实际可达) → 进 cut ladder → 每个 cut 自己有证明义务故不直接 unsound, 但请验证「precheck 结论本身从不被当证明消费」— 全仓搜 front_blocked/relaxed_disconnected 的消费点, 有没有任何点把 precheck 结论直接当 INFEASIBLE 证明 (不经 cut 证明义务) 用? ② **漏报 blocked (实际不可达却说可达)**: 后果链 = 进真 routing CP-SAT 慢证 — 纯性能, 验证这个论断; ③ **domain_stats/connected component 计算的口径**: 与 build 时 `_bind_domain_analysis` 的求交口径 (free_cells - connector, F-RT-R5-01 修复) 同源吗 — precheck 算的域比 build 用的域宽或窄各是什么后果; ④ **precheck 与 binding 选择的时序**: precheck 用的 port_specs 是 binding 选定后的吗 (selection 前的 port 全集会高估需求)?

### Q3 自由攻击角 (终饱和轮惯例: 你自己选最薄弱的缝)
以上两角之外, 用你自己的独立判断选 1-2 个你认为本面还没被审透的点深挖 (例: solve 循环的 incumbent/nogood 累积语义; TIMEOUT 边界上 witness 状态; extract_routes 输出对 blueprint 的保真; 多商品大实例的某个组合缝; 或对 r2-r5 某个历史修复设计你自己的新攻击)。说明你为什么选它、攻击了什么、结论是什么。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r6 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/master 几何/campaign/scheduler/cuts 各面 (各自有线); PCR patch 模型 (cuts 面)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- `routable_cells = free|port` stale 属性 (r4 已判挂账); splitter/merger 容量节点抽象 (r5 已判已接受口径); guard potential-graph oracle 的 source_fronts 显式传参 advisory (r6 已挂账, 非 soundness)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2988 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 你独立推导的约束族清单与逐族对照、Q2 消费点全扫结论、Q3 你的选点理由与攻击过程。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = 约束本体直审 + precheck 生产者 + 自由攻击角; 其余面不审。
