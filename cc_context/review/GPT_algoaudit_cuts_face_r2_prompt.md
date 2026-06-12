# 终末地 IndustrialPlanner 精确求解器 — cuts 机制面 round 2 (live cut 族 exact-safe 性角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_cuts_r2_snapshot_db740254.zip`, sha256 `db740254b993c2c5870698e220b10c7110a6624dfe19405b67cae1df653bc144`。**只认这个文件名, 文件区其它旧快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面历史与本轮定位

cuts 机制面轮次史: 首轮 (C 角度) 审过 F1-F9 cut family 框架, 抓到 2 个 **latent** (C-3: F2 cutset oracle edge_capacity=1 忽略 elevated bridge 双层容量 — dormant, F2 未接 master, `src/cuts/lifecycle.py::step_8_apply_to_master` 仍是 NotImplementedError 的显式未接线边界, P1.3B 接线前必修已挂账; C-4: D2 hard separator 2D AddAtMostOne 比 routing 严 — 双 env 默认关)。这两个 latent 的处置是 owner 决策, **不在本轮范围**。

**本轮 = 公开 certified 路径上 live cut 族的 exact-safe 性专审** (该面首个针对 live 路径的完整轮)。certified 默认路径上实际会触发的 cut/nogood 族:
1. **binding-level nogood** (`PortBindingModel.add_nogood_cut` — binding 面已审其形状, 本轮审它在 cut 生命周期里的复用语义);
2. **master placement nogood** (binding alternatives 耗尽后/独立 placement 证据时);
3. **routing deletion-core cut** (front_blocked 时的最小核提取, env `EXACT_B1_DELETION_CORE_CUT` — 查其在 certified 默认下的开关状态并以实际为准);
4. **lazy-demand / cell-cut** (front_blocked 回落链);
5. **lazy connectivity cut** (P0-1, guard 拒绝不连通 incumbent 时的 source-side component cut — 已双独立零 finding, 本轮只审其与其它 cut 的交互不重审本体);
6. **exact_safe_cuts 持久化语义** (V82: persisted cuts 是 telemetry 不是 proof object — resume 后它们如何被重新使用, "telemetry-only"的边界在代码里如何强制)。

错误方向: cut 切掉真实可行解 = over-cut = false-INFEASIBLE → max_lex 漏真最大矩形 = objective 级 false-CERTIFIED。

## 审查重点 (按优先级)

### Q1 每族 live cut 的数学有效性 (最重要)
对上述 1-5 每族: cut 的形状 (变量集 + 不等式) 在什么前提下有效? 该前提在添加点是否被完整验证 (fail-closed: 验不过不加/回退更弱但有效的形状)? 逐族给出"cut 有效性定理 + 代码前提检查"的对照。特别审: deletion-core 最小化过程 (QuickXplain/deletion) 的 oracle 调用与原问题的一致性 — 最小化后的 core 仍然 INFEASIBLE 的 replay 验证在哪, 跳过 replay 的路径存在吗? lazy-demand/cell-cut 的 cell 集推导对 mixed visible+routing-free 输出侧的处理 (F04-R4-03 修复在 cut 生成侧的对应物)?

### Q2 cut 作用域与生命周期
cut 添加到哪个模型实例 (per-candidate master? 跨 candidate?)? PROJECT_LOCK 禁跨 instance signature lifting — 逐族验证作用域确实 within-instance/within-candidate。candidate 重试/epsilon 阶段推进时旧 cut 的存续 — binding 选择变化后, 基于旧 binding 的 cut 还挂在模型上吗 (挂着且仍有效 = OK, 挂着但前提失效 = over-cut 缝)? `exact_safe_cuts` 从 checkpoint 恢复后的使用路径: V82 说 telemetry-only — 验证 resume 后没有任何代码路径把 persisted cut 直接加回模型当约束 (穷举消费点)。

### Q3 cut 间交互
多族 cut 同时存在时的复合效应: binding nogood + master nogood + connectivity cut 是否可能联合切掉单独都不切的可行解 (理论上独立有效的 cut 联合仍有效 — 验证每族确实独立有效而非"在其它 cut 在场时才有效")? front_blocked 回落链 (deletion-core → lazy_demand → cell_cut) 各级生成的 cut 强度递减 — 回落时上一级的失败产物有没有残留影响?

### Q4 cut 框架边界复核
`src/cuts/` 的 F1-F9 框架: 哪些 family 真正接线到 certified 路径 (以代码为准列清单)? 未接线 family 的代码存在会不会被任何 certified 路径意外调用 (除 step_8 的 NotImplementedError 外还有别的隔离吗)? PCR-CUT (Phase 4 hook) 在 env 关闭时的零影响验证。

## 明确不要报的

- C-3/C-4 latent 本体 (owner 已挂账, P1.3B 前处置; 但若你发现它们**当前就可达公开路径**, 那是新 finding 要报)。
- lazy connectivity cut 本体 (已双独立零 finding; 其与其它 cut 的交互算)。
- binding nogood 形状本体 (binding 面 r2 已审; 其生命周期/复用语义算)。
- 各子问题内部数学 (binding/routing/master 面各自有线)。
- 设计决策 (canonical/266/52-Port, owner 已定); C-1/C-2/B-02 已 refuted。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区本身 (它是边界不是缝); exploratory 不审。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2949 passed, 0 failed)**; 跑不完就跑专项 (src/tests/cuts/ + test_p0_certified_soundness_fixes) + 如实声明 (`-p no:randomly`)。
- 注意: 包内带着同日其它面刚落的修复 (benders_loop 的 F-BL-R3 状态契约 / routing 的 F-RT-R2 极性与边守恒 / binding 的 F-BIND 系列) — 修复本体不在本面范围, 但它们与 cut 生成/replay 的交互在 Q3 范围内。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); over-cut 类 finding 给出被误切的可行解实例; 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 cut 族×有效性前提×前提检查对照表 + Q2 消费点穷举清单。

## 范围边界

- 重点 = live cut 族有效性/生命周期/交互/框架边界; 其余面不审。
