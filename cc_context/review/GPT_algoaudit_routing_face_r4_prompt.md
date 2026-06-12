# 终末地 IndustrialPlanner 精确求解器 — routing 面 round 4 (F-RT-R3-01 修复攻击面 + 域收缩/复用与 precheck 纵深角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_278e4d67.zip`, sha256 `278e4d67f97a88cab7bba697ec96df2f04d43ce1475bc65aef4a22519d1885a0`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → **routing 网格布线** → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面历史与本轮定位

routing 面 (`src/models/routing_subproblem.py`) 轮次史: A-1 双层修复 + 双独立零; guard 完整性轮已修; r2 编码本体爆 2 HIGH 已修 (**F-RT-R2-01** sink front 极性反向 → `DIR_OPP` 全消费点 + guard + fuzz oracle 同步; **F-RT-R2-02** 单边喂两层隐形 splitter → 非 terminal 有向边送收守恒); **r3 终端语义×域收缩交界爆 1 HIGH 已修 — F-RT-R3-01 (live false-FEASIBLE)**: routing 域从未剔除物理 port connector cell — 任意商品可把别的端口 connector 当普通 belt 格穿过 / 普通 belt 可复用 terminal 侧, CP-SAT 与 reachability guard 双放行 (probe: ore 线穿 water_src connector `(2,1)`, solve FEASIBLE + guard failure_count 0)。修 (lock 新增 F-RT-R3-01 条款) = ① `_port_connector_cells()` 在 `_resolve_routing_domain_context()` 从 free cells 扣除 + placement-core 复用路径重算连通组件; ② `_bind_domain_analysis()` 对外置 domain_analysis fail-closed 二次扣除; ③ successor/predecessor continuity 禁止普通态向 source front 的 connector 侧发送 / 从 sink front 的 connector 侧接收 (belt-and-suspenders); ④ diff-fuzz oracle 独立新增 connector 占用检查。修后 fuzz 200 实例零不一致。**本轮 r4 = F-RT-R3-01 修复确认 + 刻意换角度**。

规则真相源: specs/06 (port/front 定义, connector 非 routing cell), specs/08 (port-edge 与空间边分离), specs/09, `rules/canonical_rules.json`。包内带着其它面同期修复 (lock 末 F-BL-R4 / F-GM-Q3-01-R3-A / F-CUT-R3 系列), 各有线别重报。

## 审查重点 (按优先级)

### Q1 F-RT-R3-01 修复确认 (攻击面)

① **扣除完备性**: connector cell 进入「可放 route state 的集合」的入口是否全被堵 — `_resolve_routing_domain_context` 两条返回路径 / `_bind_domain_analysis` 外置 analysis / `RoutingGrid.routable_cells = free_cells | port_cells` 这个属性还有没有别的消费点把 connector 当可走格 (全文件 + 跨文件 grep 消费点) / precheck `analyze_exact_routing_domain` 的域与 solver 的域在扣除后是否同构 (precheck 用没扣的域会比 solve 松 = 漏报, 反向则误报)? ② **不过剪验证**: 按 specs/06/08 论证 connector cell 上永远不该有 belt — 有没有合法布局需要 belt 占 connector (例如 port A 的 front 恰是 port B 的 connector 的几何, 这种 pose 组合在 canonical 池里存在吗, 存在时修复前后判定各是什么)? ③ **terminal-side continuity 禁止项的恰好性**: 几何上 source front 的 `recv_dir` 侧邻格是否唯一 = connector (即禁止项只可能命中 connector 位置), 有没有合法普通态被它误杀的构形? ④ **placement-core 复用路径**: 扣除后重算组件 — 复用缓存里还有没有别的派生物 (neighbor map / component map / active cells) 残留未扣除的旧视图?

### Q2 域收缩/复用与 precheck 纵深 (新角度)

① routing 域 shrink/复用机制 (`_routing_shrink_summary` 及其生产者): shrink 后的域对 connector 扣除 / 商品 active cells / 守恒约束的一致性 — shrink 会不会把本应在域里的格剪掉 (false-INFEASIBLE) 或把扣掉的格带回来 (false-FEASIBLE)? ② precheck 三态 (`feasible` / `front_blocked` / `relaxed_disconnected`) 的保守性双向: precheck 拒绝的是否 solve 必拒 (不过严), precheck 放行的 solve 是否可能拒 (允许, 但消费侧把 precheck-feasible 当证明就是缝) — 消费侧 (benders_loop 的 precheck 分支) 对三态的处置逐个判读。③ 多 source/多 sink 同商品的 front 可用性判定与 adherence exact-one 的一致性。

### Q3 终端 key 折叠挂账复核

r3 备注: 两个 port 生成完全相同 `(front, direction, commodity, type)` key 时 adherence 会加重复 `sum==1` 而非 multiplicity=2 — canonical 非重叠 pose 构造不出。请独立复核这个「构造不出」: 在 canonical pose 池/binding port specs 语义下给出论证或反例; 若你能构造出 (含未来 port_specs 入口开放场景), 给 fail-closed 重复 key 检查的补丁。

### Q4 抽查维持

F-RT-R2-01 极性消费点 (六处 DIR_OPP) / F-RT-R2-02 边守恒形状 / guard reachability 语义 / fuzz oracle 独立性 (connector 检查是否从规则文本推导而非复制实现) — 各抽 1-2 处对照 r3 已审结论。

## 明确不要报的

- A-1/guard/F-RT-R2/F-RT-R3-01 已修本体复述 (但其修复的**新**缝算); 历史完整性轮已修项。
- binding/master/preprocess/campaign/cuts 各面 (lock 末 F-BL-R4/F-GM-R3A/F-CUT-R3 是同期修复, 各有线); flow_subproblem 是 diagnostic 不审。
- 设计决策 (canonical/266/52-Port); C-2 已 refuted。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2963 passed, 0 failed)**; 跑不完跑专项 (test_routing* / test_p0_certified_soundness_fixes) + 如实声明 (`-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- `python cc_context/verification/diff_fuzz/routing_connectivity_diff.py --self-test` pass (含 connector 场景)。
- finding 必须带可复现 probe 或严谨论证 (file:line); 过剪类给被误拒的合法布线实例, 过松类给被接受的非法路径实例; 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 connector 消费点清单与 Q2 precheck 三态×消费侧对照表。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = F-RT-R3-01 修复确认 + 域收缩/precheck 纵深 + 终端 key 挂账复核; 其余面不审。
