# 终末地 IndustrialPlanner 精确求解器 — routing 面 round 3 (饱和确认轮·F-RT-R2 修复攻击面 + 容量/多商品纵深角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_rt_r3_snapshot_b377a2a7.zip`, sha256 `b377a2a75e67697a38b2e46f8dc1407677a1f9936406b51695a7094487524531`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → **routing 网格布线** → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面历史与本轮定位

routing 面 (`src/models/routing_subproblem.py`) 轮次史: A-1 (局部连续≠全局连通) 双层修复 + 双独立零 finding; guard 完整性轮已修项 (回归 `test_p0_certified_soundness_fixes.py`); **r2 编码本体首攻爆 2 HIGH 已修**: **F-RT-R2-01** = sink front 方向极性反向 — front 朝 connector 送料应为 `Opp(dir)`, 旧编码要求朝外 → 3 格直线 corridor false-INFEASIBLE + 宽敞布局幻影状态绕路; solver 索引/adherence 与独立 guard 同源漂移一起错, 连 diff-fuzz oracle 的 sink front 键也同源反向 (900 历史实例对该类盲); 修 = `DIR_OPP[direction]` 全消费点 + guard + oracle 同步。**F-RT-R2-02** = L0/L1 合法重叠时局部 `>=1` 支撑允许单条有向边喂两层/两层并一边 = 隐形 splitter/merger 且连通性 guard 不可见; 修 = `_add_directed_edge_balance_constraints()` (每 commodity 每条**非 terminal** 有向边「选中发送态数 == 选中接收态数」)。r2 还核了 9 项规则对照矩阵 / precheck 保守性 / guard 同源更新。lock 新增 F-RT-R2 双条款。**本轮 r3 = F-RT-R2 修复确认 + 刻意换角度**。

规则真相源: specs/09, `rules/canonical_rules.json`, specs/02。注意包内带着其它面同期修复 (lock 末 F-BIND/F-BL/F-GM/F-CUT/F-PRE 系列), 各有线别重报。

## 审查重点 (按优先级)

### Q1 F-RT-R2 修复确认 (攻击面)
① **极性修复全覆盖**: `DIR_OPP` 修复是否覆盖 sink front 的**全部**消费点 (索引构建/adherence 约束/guard 图构建/precheck front 判定)? 有没有残留一处仍用原 dir 的 (两处不一致 = 新的同源漂移)? source front 侧 (`flow_in = Opp(dir)`) 与 sink front 侧的对称性? ② **边守恒约束形状**: 「选中发送态数 == 选中接收态数」对每条非 terminal 有向边 — 这个等式会不会**过强**: 有没有合法布线形态 (specs/09 允许的) 在同一有向边上发送/接收态数合法地不相等? terminal 边豁免的边界恰好吗 (豁免过宽 = 修复白做, 过窄 = 合法 terminal 流被拒)? ③ 守恒约束与 capacity/互斥约束的交互: 三者联立有没有把合法的 L0-straight + L1-bridge 共存形态变 INFEASIBLE (probe 一个跨越场景)?

### Q2 容量与多 commodity 语义纵深 (新角度)
① per-cell 容量在双层语义下的精确形状: 同 cell ground belt + elevated bridge 共存时, 各层各 commodity 的状态互斥/共存矩阵, 编码 vs specs/09 逐条。② 多 commodity 隔离: 不同 commodity 不得混线的编码强度 — 同一 cell 同一层两个 commodity 的状态是否被恰好互斥 (过松 = 幽灵混线, guard 看得见吗? 过严 = 不同层不同商品被误斥)? ③ 汇流/分流的 per-commodity 合法形态 (同 commodity 多 source 汇入一条 belt?) 编码 vs 规则。

### Q3 终端语义抽查
binding port specs → routing terminal 转换的方向/坐标约定在 F-RT-R2-01 修复后的一致性: front cell = port + dir 的坐标计算、进入方向约束、多 port 共享 front cell 的合法性 — 与 r2 已审结论对照抽查 2-3 处 (重点是修复改动半径内的)。

### Q4 guard/fuzz 同步维持
guard 与编码的同构声明在修复后是否仍成立 (guard 的边守恒有没有对应物 — 若 guard 看不见守恒违反, 编码层约束是唯一防线, 判读这是否可接受); fuzz oracle 修复后的独立性 (oracle 极性现在从规则文本推导而非复制实现?)。

## 明确不要报的

- A-1/guard/lazy cut 修复本体 (双轮确认 + fuzz); r2 已修 F-RT-R2 本体复述 (但其修复的**新**缝算); 历史完整性轮已修项。
- binding/master/preprocess/campaign/cuts 各面; flow_subproblem 是 diagnostic 不审。
- 设计决策 (canonical/266/52-Port); C-2 已 refuted。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2955 passed, 0 failed)**; 跑不完跑专项 (test_routing* / test_p0_certified_soundness_fixes) + 如实声明 (`-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 过剪类给被误拒的合法布线实例, 过松类给被接受的非法路径实例; 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 极性消费点清单与 Q2 双层×商品状态矩阵核验范围。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = F-RT-R2 修复确认 + 容量/多商品纵深 + 终端语义抽查; 其余面不审。
