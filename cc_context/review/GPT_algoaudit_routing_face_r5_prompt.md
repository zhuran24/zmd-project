# 终末地 IndustrialPlanner 精确求解器 — routing 编码面 round 5 (饱和确认轮·R4 修复确认 + specs 规则文本独立对照 + 多修复叠加组合语义)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_70457b5e.zip`, sha256 `70457b5e6cd759fd0fd75873b12b61f444ad3e569bb26216cea7aa383b22b15a`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: routing 编码 (routing_subproblem + guard + precheck), r2-r4 收敛轨迹 2→1→2, 本轮目标首个干净轮

routing 面近 3 轮 (报告在包内 `cc_context/review/archive/algoaudit_routing_face_r{2..4}_REVIEW_2026061x.md`): r2 = F-RT-R2-01 (sink front 方向极性反向, fuzz oracle 同源反向 = 独立验证器盲区实证) + F-RT-R2-02 (单条有向边可喂两层 = 隐形 splitter/merger, 修 = 每商品每非 terminal 有向边送=收守恒); r3 = F-RT-R3-01 (port connector cell 从未从 routing 域剔除, 任意商品可穿别人的 connector, live false-FEASIBLE; 修 = 域解析扣除 + 外置 domain fail-closed 二次扣除 + terminal-side 禁止); **r4 = F-RT-R4-01 (`analyze_exact_routing_domain()` 把同商品全部 terminal fronts 强制压单连通分量 → 「双孤岛各自 source+sink 闭合」合法布局被误拒, false-INFEASIBLE; 修 = terminal fronts 按 component 分组, 双侧商品要求每个含 terminal 的 component 有 ≥1 source + ≥1 sink, domain 取满足 component 并集; 单侧商品保留旧保守行为) + F-RT-R4-02 (重复 terminal front key 折叠 multiplicity; canonical 构造不出 [几何论证+599382 端口扫描], 外置可构造; 修 = `_duplicate_terminal_front_keys()` analyze 返回 front_blocked + build 二次 fail-closed)**。**本轮 r5 = r4 修复确认 + 刻意换角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND 系列 / F-BL-R3/R4 / F-GM-Q3 系列 / F-CUT-R2 + CUT-R3-H1/CUT-R4-H1 / F-PRE-R8/R9 条款), 这些面各有自己的线, 别在本轮重报。差分对拍 fuzz 已累计 ~1200 routing 实例零不一致 (oracle 极性修正后 + connector 独立检查)。

## 审查重点 (按优先级)

### Q1 F-RT-R4-01/02 修复确认 (攻击面)
把 r4 修复当攻击面打: ① per-component 分组逻辑 — component 划分用的连通定义与实际 CP-SAT 可走域 (connector 剔除后) 是否同一口径 (口径不一致 = 分组与编码分叉)? 「双侧商品要求每 component ≥1 source + ≥1 sink」的有效性: 有没有合法布局是某 component 只有 source 没有 sink 但**该商品在该 component 的流量恰好为 0** (即 source 全部空置/unused) — 这种被误拒吗 (binding 决定空置在前还是 routing 域判定在前, 时序谁先)? ② 「domain 取满足 component 的并集 + 逐 component peel」— peel 顺序会不会让先 peel 的 component 把后续 component 需要的格子削掉 (peel 之间有共享格吗)? ③ 单侧商品 (只 source 或只 sink 在域内, wireless 局部语义) 保留旧保守行为的边界判读 — 新旧行为的切换判据是什么, 有没有商品被错误归类到单侧分支? ④ F-RT-R4-02 的 duplicate key 检查在 analyze 与 build 两层 — 两层的 key 构造是否同一函数 (复制实现 = 同源漂移风险)? fail-closed 方向确认 (front_blocked 是保守方向吗 — 它会触发 binding-local ladder 而不是直接 INFEASIBLE)?

### Q2 specs 规则文本独立对照 (新角度; 方法论要求: 先读规则再对照实现, 不从实现学语义)
本项目曾发生「验证器从实现学语义 → 同源错」(F-RT-R2-01, fuzz oracle 极性与实现一起反)。请**先读 `specs/06_*.md` / `specs/08_*.md` (传送带/桥/分流/汇流/端口 front/connector 规则) 与 `rules/canonical_rules.json` 相关字段, 自己写下每条规则的预期编码语义, 再对照 `src/models/routing_subproblem.py` 的 CP-SAT 编码逐条核**: ① 每个约束族 (cell 占用/层互斥/bridge 直行/方向连续性/送收守恒/terminal 邻接/容量) 的规则依据 — 实现更严 (false-INFEASIBLE) 或更松 (false-FEASIBLE) 或缺失? ② 规则里有而编码里没有的约束? ③ 特别核 bridge (L1) 语义: 规则文本对桥的进出方向/长度/与 L0 共存的完整约束集 vs 实现 — r2/r3 核过「L1 只直桥」「bridge 与 L0 non-straight 互斥」, 但请独立从文本再推一遍完整集合, 找文本有而实现漏的边角。

### Q3 三批修复叠加后的组合语义 (新角度)
r2 边守恒 × r3 connector 剔除 + terminal-side 禁止 × r4 per-component 分组三批修复叠加在同一编码上: ① 有没有组合场景使两个修复的前提互相破坏 (例: terminal-side 禁止假设 connector 在域外, 但某路径上 connector 剔除发生在禁止约束建立之后/之前的次序问题)? ② 多商品 + 多 component + bridge 跨越 + 共享 front 的复合场景: 构造 2-3 个中型 probe (10×10 级) 验证编码端到端行为 (FEASIBLE 的应 FEASIBLE / INFEASIBLE 的应 INFEASIBLE, 用手工可验证的布局); ③ guard (独立重验器) 对三批修复的同步性: guard 的图语义是否与修复后的编码语义严格同构 (guard 漏跟某批修复 = 验收边界形同虚设)?

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r4 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/master 几何/campaign/scheduler/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- r3 挂账已闭 (duplicate terminal key = r4 修); `routable_cells = free|port` stale 属性 (r4 已判无消费者, 未来启用须同步扣 — 已挂账)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2968 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 实际对照过的「规则条文 ↔ 约束族」清单与 Q3 端到端 probe 布局图。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R4 修复确认 + specs 文本独立对照 + 三修复叠加组合 + guard 同步性; 其余面不审。
