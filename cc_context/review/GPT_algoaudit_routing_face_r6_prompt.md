# 终末地 IndustrialPlanner 精确求解器 — routing 编码面 round 6 (饱和确认轮·R5 修复确认 + guard 本体深审 + 状态模式枚举完备性)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_3f4ceebb.zip`, sha256 `3f4ceebb5606d2d2b054b5af82899202fc1dcdae8cee9c97626bbaf57b8e58b9`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。
注意: 包基点之后仓库又落了 master 几何面 F-GM-R6-01 与 cuts 面 PCR-R5 系列修复, 都不在 routing_subproblem 主体; 本面主体文件与包一致。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: routing 编码 (routing_subproblem + guard + precheck), r2-r5 收敛轨迹 2→1→2→1, 本轮目标首个干净轮

本面近 4 轮 (报告在包内 `cc_context/review/archive/algoaudit_routing_face_r{2..5}_REVIEW_2026061x.md`): r2 = F-RT-R2-01 (sink front 极性反向, fuzz oracle 同源反 = 独立验证器盲区) + R2-02 (单边喂两层 = 隐形 splitter, 修 = 边守恒); r3 = F-RT-R3-01 (connector cell 可当 belt 格穿过, live false-FEASIBLE; 修 = 域剔除三层); r4 = F-RT-R4-01 (同商品多岛误拒) + R4-02 (重复 terminal key); **r5 = F-RT-R5-01 (外置 `domain_analysis` 只减 connector 不与 `grid.free_cells` 求交 — 障碍排斥 = 「只在 active domain 建变量」, 陈旧分析含 occupied 格可穿墙 FEASIBLE; 修 = `_bind_domain_analysis()` 与 `free_cells - connector` 求交, occupied/出界/connector 三类同口径挡回, front 被裁出走 `0==1` adherence fail-closed)**。r5 已做 specs/06/08/09 10 行文本对照 + 4 端到端 probe + 三修复叠加组合判读。差分对拍 fuzz 累计 ~1200 实例零不一致。**本轮 r6 = R5 修复确认 + 两个未深审角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL / F-GM / F-CUT / F-PRE 系列条款), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-RT-R5-01 修复确认 (攻击面)
① 求交 `& (free_cells - connector)` 的两个集合的时点: `grid.free_cells` 与 `_port_connector_cells(grid.port_specs)` 都来自构造时的 grid — 有没有 grid 在 bind 之后被改的路径 (导致求交基准过时)? ② 三类格 (occupied/出界/connector) 同口径挡回的完备性 — 还有没有第四类「不该走但在 free_cells 里」的格 (例: ghost 矩形格? 其它商品的 terminal front?) 按规则不该被该商品走但求交不掉? 逐类判读规则依据。③ front 被裁出 active domain 后 `_add_port_adherence()` 的 `0==1` fail-closed — 验证这条兜底对 source 和 sink front 都生效, 且不会被「该 port 不在 patch/域内就跳过」的早退绕过。

### Q2 guard (`_validate_selected_route_connectivity`) 本体深审 (新角度)
guard 是 CP-SAT FEASIBLE 之上的最终验收边界 (specs/09:100-128: FEASIBLE 不能直接认证)。此前轮次核过 guard 与各修复的同步性, 但 guard **本体**从未被独立深审: ① guard 的选中图构建 (`_route_state_adjacency`): 从 selected route states 建 `flow_out -> neighbor flow_in=Opp(dir)` 边 — 这个邻接定义与 CP-SAT successor/predecessor 语义是否**严格同构** (guard 更宽 = 假验收 false-FEASIBLE [必须查]; guard 更窄 = 误拒收敛风险)? 特别核 layer 交叉边 (L0↔L1 receiver/sender) 与 terminal 例外的两侧一致性。② 逐商品可达性判定: 每 source front 达某 sink front + 每 sink front 被达 — guard 对「多 source 多 sink 部分配对」的判定与 specs/08 pool 语义一致吗 (是要求完美匹配还是存在性)? ③ guard 的输入是 `extract_routes()` 的产物 — extract 与 guard 之间有没有信息丢失 (state 字段裁剪) 使 guard 看到的图弱于 CP-SAT 的解? ④ guard 自身的 fail 处理: 图构建异常/字段缺失时是 fail-closed (拒) 还是 fail-open (过)?

### Q3 状态模式枚举完备性 (新角度; 方法论: 从规则文本独立推导)
`_iter_state_patterns()` 枚举每 (cell, layer) 的合法 (d_in, d_out, component_type) 集合。请**先从 specs/03:306-344 + specs/09:43-64 + canonical routing_rules 独立写出**全部合法 state pattern 的封闭集合 (L0: 12 belt [d_in≠d_out] + splitter 1-in-多-out + merger 多-in-1-out 的全部方向组合; L1: 直桥), 再与实现枚举逐个对照: ① 实现**漏**的合法 pattern (= false-INFEASIBLE 方向: 某合法布线形态不可表达); ② 实现**多**的非法 pattern (= false-FEASIBLE 方向: 规则禁止的形态可被选); ③ splitter/merger 的方向组合数学 (1-in-2-out 选 2 出口的 C(3,2) 组合 × 入口方向 = 多少种, 实现数对吗)? ④ 每个 pattern 的 component_type 标注与下游消费 (guard/extract/边守恒) 对 component_type 的语义假设一致吗?

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r5 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/master 几何/campaign/scheduler/cuts 各面 (各自有线); PCR patch 模型 (cuts 面 r5 刚修过四义务)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- `routable_cells = free|port` stale 属性 (r4 已判无消费者挂账); splitter/merger 按容量节点抽象 (r5 已判已接受口径)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2980 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 guard↔CP-SAT 同构性逐项与 Q3 你独立推导的 pattern 集合及对照结果。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R5 修复确认 + guard 本体 + 状态模式枚举完备性; 其余面不审。
