# 终末地 IndustrialPlanner 精确求解器 — preprocess 链面 round 12 (饱和确认轮·R11 修复确认 + 实例展开器本体 + 工件交叉一致性)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_37b84be0.zip`, sha256 `37b84be0749893447ccab8113934d8a518237702de0e00ed8d64176a913c57dd`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: preprocess 链, r1-r11 收敛轨迹, 本轮目标干净轮

preprocess 面历史 11 轮 (报告在包内 `cc_context/review/` 与 `archive/`): r5/r7 零; r8 = strict JSON 四装载点 + 枚举完备性 66403 独立重建; r9 = 数字上溢; r10 = F-PRE-R10-01/02 (loader schema 校验 + generator 几何 contract) + pose 几何变换数学 9 行手算; **r11 = F-PRE-R11-01 (placement generator `load_templates()` 是第三个 canonical 文件入口, 只 strict-load 不 schema 校验; 修 = 入口处跑 canonical schema) + F-PRE-R11-02 (geometry contract 漏锁 `rotatable`/`is_solid_z`; 修 = per-family 锁双字段 + bool 类型守卫) + F-PRE-R11-03 (cycle group 只验 square/singular 不验非负, 负机器率被 demand 聚合 `>0` 过滤静默吞; 修 = net_export∈internal 校验 + 每 net-export 单位需求非负基解证明 + `_solve_cycle_group_exact()` 对任意 RHS 解逐项负值 fail-closed)**。r11 还手算了 17 操作完整 demand 链对照冻结工件全对 + 6 recipe vs vendored 上游逐字段忠实。**本轮 r12 = R11 修复确认 + 两个未深审角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL / F-GM 系列含 R7-HINT / F-RT / F-CUT 系列含 PCR-CUT-R6-H1 条款), 这些面各有自己的线, 别在本轮重报。preprocess 链自 r11 修复后零代码变化, 该修复在本包内。

## 审查重点 (按优先级)

### Q1 F-PRE-R11-01/02/03 修复确认 (攻击面)
① **R11-01**: `load_templates()` 的 schema 校验加载路径 — schema 文件自身缺失/损坏时 fail 方向? 校验加在入口后还有没有「绕过 `load_templates` 直接拿 `rules['facility_templates']`」的调用点 (全仓扫 strict-load canonical 的所有点, 对照 lock「any future reader inherits」义务)? ② **R11-02**: per-family 锁的 `rotatable`/`is_solid_z` 期望值表 — 逐 family 对照 canonical 当前真值 (boundary/6x4/core 应 rotatable=True, pole 应 False, …) 与 generator 实际行为, 期望值表本身写错会两边一起错, 请独立验证; bool 类型守卫对 truthy 非 bool (如 1/"true") 的 fail 方向? ③ **R11-03 数学**: 单位需求非负基解证明的充分性 — 解对 RHS 线性, 每个 net-export 单位方向非负 + 实际需求非负 ⇒ 任意非负组合解非负, 这个线性论证在「多 net-export 同组」时成立吗 (验证矩阵/解的线性性在实现里没被破坏); solve 时逐项负值 fail-closed 对「组合 RHS 出负但单位方向全正」的情形兜得住吗 (构造一个试试)? validation 的零 RHS solve 与单位 RHS solve 的 except 路径会不会把 singular 误报成负解?

### Q2 实例展开器本体 (新角度; machine_counts → mandatory_exact_instances 的展开从未独立深审)
`data/preprocessed/mandatory_exact_instances.json` 由 machine_counts 展开生成 (生成代码在 src/preprocess/ 或 scripts/, 自行定位): ① **数量保真**: 266 实例的构成 = 各 operation 的 ceil 机器数 + 固定设施 (core/pole/storage/boundary?) — 从 machine_counts.json 与 canonical 固定设施清单独立重算总数与分布, 与冻结工件逐 operation 对照; ② **operation profile 赋值**: 每实例的 facility_type/operation/port 需求 (输入输出 commodity 集) 与 canonical recipe 的 facility 指派一致吗 — 抽 5 个 operation 逐字段; ③ **实例 id 稳定性**: id 生成是确定性的吗 (排序/计数器), 同输入重生成 id 集合不变吗 (id 漂移会破坏 hint/campaign resume 的 instance 对应); ④ **wireless/generic IO 标注**: 哪些实例端口被标 routing-free/generic, 标注来源与 generic_io_requirements.json 同源吗?

### Q3 preprocess 工件交叉一致性 (新角度)
四个冻结工件 (machine_counts / generic_io_requirements / mandatory_exact_instances / candidate_placements) + plan hash 闭包之间的一致性: ① **哪些交叉断言被代码/测试锁住** (如 instances 的 operation 计数 == machine_counts; generic_io 的 52/34/18 == instances 端口聚合) — 找出每对工件间的一致性检查点, 没有检查点的对 = 靠生成时序假设, 列出来; ② **部分再生的撕裂风险**: 只再生其中一个工件 (如只跑 placement_generator) 时, 哪些一致性可能撕裂, hash 闭包/频 preflight 能不能拦住; ③ **频 hash 闭包的覆盖面**: 哪些工件在闭包内、哪些 (commodity_demands 已判 diagnostic-only) 在外 — 在外的工件有没有被 certified 路径消费的缝 (有 = finding)。

## 明确不要报的

- 设计决策 (canonical 17-recipe 口径/266/omni_wireless/52-Port, owner 已定); r1-r11 已修 finding 与已审结论 (重复报不算)。
- binding/master/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审; commodity_demands.json 不在 hash 闭包 (diagnostic-only 已判, Q3③ 是确认无 certified 消费缝不是重判设计)。
- DOC-LOW-01 plan metadata 措辞 (已挂账)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2988 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉冻结工件再生或登记 hash, 交付必须含再生步骤 + 期望 sha256/字节数 + 同批推进的登记位置清单。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 期望值表独立验证、Q2 266 重算对照、Q3 交叉断言矩阵 (有检查点/无检查点)。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R11 修复确认 + 实例展开器 + 工件交叉一致性; 其余面不审。
