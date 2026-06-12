# 终末地 IndustrialPlanner 精确求解器 — routing 面确认轮 (网格编码双向保真角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `{PACKAGE_NAME}`, sha256 `{PACKAGE_SHA256}`。**只认这个文件名, 文件区其它旧快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → **routing 网格布线** → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面历史与本轮定位

routing 面 (`src/models/routing_subproblem.py` 网格布线 CP-SAT + 连通性验收) 轮次史: 首轮抓 **A-1** (routing CP-SAT FEASIBLE 只保证局部连续, 局部闭合孤岛可通过 → false-CERTIFIED), 双层修复已落地并双独立零 finding 确认: ① post-solve 连通性 guard (重建选中 per-commodity route-state graph, 证每个 source front 可达 sink front 且反向可达, 不连通 → 拒绝重解, 预算尽 → UNKNOWN/TIMEOUT 绝不 CERTIFIED, lock 条款); ② lazy connectivity cut (source-side component cut 加速, 每条 cut 独立重验 W/X 证书, 验不过回退 selected-positive nogood, lock 条款)。该面后续还有一轮完整性审查, 所发现项均已修复落地 (回归在 `src/tests/test_p0_certified_soundness_fixes.py`)。差分 fuzz (独立朴素验证器, 零共享被测代码) 已累计 900 routing 实例零不一致。

**本轮 = 该面干净确认轮, 刻意换角度**: 前几轮主攻"FEASIBLE 验收边界" (连通性/guard/cut); 本轮主攻 **routing CP-SAT 编码本体**对照 specs/09 的双向保真 — 编码比规则松 (非法路径被接受 = false-FEASIBLE, 虽有 guard 兜连通性但 guard 只验连通不验全部网格规则) 与编码比规则严 (合法布线被拒 = false-INFEASIBLE)。

规则真相源: specs/09 (exact grid routing 语义), `rules/canonical_rules.json` (belt/bridge 设施语义), specs/02 (单位与容量)。

## 审查重点 (按优先级)

### Q1 网格 cell/层语义双向保真 (最重要)
- cell capacity: 每个 2D cell 的占用规则 (belt 独占? elevated bridge 与 ground belt 同 cell 共存的合法形态?) 编码 vs specs/09 文本。**双层语义** (ground + elevated) 的状态空间: bridge 的进出坡道、跨越段、与 ground 的交互, 编码里哪些状态组合被允许/禁止, 与规则逐条对照。
- 方向性: belt 流向约束 (一进一出? 汇流/分流的合法性?) 编码是否恰好。转弯/直行状态机的完备性 — 有没有合法转弯形态不在状态集里 (= 过剪)?
- 与设施格的互斥: routing 不得穿越 occupied_cells 的编码; port cell 与 front cell 的可通行性规则。

### Q2 source/sink front 履行语义
port spec (binding 输出) → routing terminal 的转换: front cell 的进入方向约束 (front = port + dir, 必须从正面进入?) 编码是否与规则一致? 多 commodity 共享 front cell 的合法性? per-commodity 流的隔离 (不同 commodity 的 belt 不能混线?) 编码强度 vs 规则? capacity 1/Tick 的单位换算在 routing 层有没有体现, 还是纯拓扑 (若纯拓扑, 与 specs/02 容量审计的衔接在哪一层保证)?

### Q3 precheck 与完整 solve 的一致性
routing precheck (front_blocked / relaxed_disconnected 判定) 用的抽象 vs 完整 routing solve 的精确编码: precheck 判 blocked 但完整 solve 实际可行的形态存在吗 (precheck 必须保守 — 只能比完整 solve 更宽松, 不能更严, 否则 false front_blocked → 错误 nogood 链)? 时间预算切分 (precheck 超时算 pass 还是 blocked — 必须算 pass/UNKNOWN 方向)?

### Q4 guard 与编码的独立性复核
guard 重建验证器与 routing CP-SAT 的"严格同构"声明 (前轮已审): 抽查 1-2 个最可能漂移的点 — 编码改动后 guard 的图构建是否同步 (例如 bridge successor 豁免规则两边一致?); guard 的 budget 路径 (重解循环上限) 与 UNKNOWN 语义。

## 明确不要报的

- A-1/guard/lazy cut 修复本体 (已双轮确认 + fuzz 900 实例; 但编码本体的**新**缝算)。
- 该面历史完整性轮的已修项 (回归在 test_p0_certified_soundness_fixes.py, 重复报不算)。
- binding/master/preprocess/campaign/cuts 各面 (各自有线); flow_subproblem 是 diagnostic 不是 proof (不审)。
- 设计决策 (canonical/266/52-Port, owner 已定); C-2 已 refuted (port 坐标单次偏移正确)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2927 passed, 0 failed)**; 跑不完就跑专项 (test_routing* / test_p0_certified_soundness_fixes) + 如实声明 (`-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 过剪类给出被误拒的合法布线实例, 过松类给出被接受的非法路径实例; 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 状态/规则对照矩阵与 Q2/Q3 检查清单。

## 范围边界

- 重点 = routing CP-SAT 编码本体双向保真 + precheck 一致性; 其余面不审。
