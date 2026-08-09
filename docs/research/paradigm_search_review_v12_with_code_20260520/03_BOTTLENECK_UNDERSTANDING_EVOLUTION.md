# 03 — 项目对瓶颈理解的演变

从 2025-12 项目第一个 lever 到 2026-05-20 的瓶颈理解过程. 每次 paradigm 尝试后更新对 bottleneck 的认知.

## 阶段 1 (2025-12 ~ 2026-02): "RAM 瓶颈"

**当时认知**: 单进程 OOM 是核心 blocker. P1 #24 4-parallel campaign 撞 OOM 9 min 退. 调优 jemalloc / P-core taskset / THP / spike 各种 RAM 优化.

**当时数据点**:
- Master peak RAM ~30 GB (8 workers × propagation buffer)
- 全 session L2 优化 减 worker 8→1 → master peak 12 GB plateau verified
- workers=2 spike plateau 16.4 GB (-45%)

**当时结论**: workers=1 + 减小 propagation buffer 是 wrapping scripts 重点.

**之后发现**: 14h trial 跑 51 candidate 全 UNKNOWN, baseline 8 workers 也 0 feasible. **真瓶颈非 RAM**.

## 阶段 2 (2026-02 ~ 2026-04): "wall (search) 瓶颈"

**认知更新**: RAM 优化已确认 ok, master.solve 本身解不动. master peak 12 GB but 14h trial UNKNOWN. **wall 是 NP-hard search 的指数难度**.

**当时数据点**:
- master_seconds 60s 是默认 budget, 但 trial 实测 1h 后仍 UNKNOWN
- D step 2 community blueprint hint 注入 798 AddHint 零损耗 (telemetry 验证), 但 master inherent 难解非 hint failure
- candidate 大 area (>1000) hint 几何不可能 match

**当时结论**: master form 自身 search 不动. hint 加再聪明也救不了.

**之后发现**: 换 master form (B1 pose-bool) 后 master.solve 53s OPTIMAL, 跟之前 30 min UNKNOWN 跨数量级. **wall 不是 fundamental, 是 master form 选择问题**.

## 阶段 3 (2026-04 ~ 2026-05-17): "master form 决定一切"

**认知更新**: pose-bool master form 比 coordinate-based master form 强 ~34x. 之前 30 min UNKNOWN 不是 problem 本质难, 是 model form 选错.

**当时数据点**:
- B1 pose-bool master 27×15 anchor (22,28) 50-100s OPTIMAL 持续
- coordinate-based master 30 min UNKNOWN
- 模型大小: pose-bool x_vars ~10K + 28×15 = 285K total vars

**当时结论**: 解锁 master 端瓶颈, 接下来 sub-problem + cut framework 应该能闭合 LBBD loop.

**之后发现**: 6 paradigm cut framework 撞同墙 (Path 12-17). 0/8 CERTIFIED rate. master OPTIMAL 但 cut 切空间 ≪ 1% 不收敛. **master 解锁了, cut 框架成为新瓶颈**.

## 阶段 4 (2026-05-17 ~ 2026-05-20): "cut form 表达力锁死"

**认知更新**: cut form 不是质量问题, 是**维度**问题. sub-problem 算法多丰富 (RAB-SEP binding-side / SAC-Hull corridor / PCR-CUT patch belt / PGW-UB witness / GOC-C2 全图 / D2 commodity flow), cut 翻译回 master 时只能写:

```
sum_{(i, p_i) in core} x_{i, p_i} <= |core| - 1
```

跟 master pose-bool 维度对齐. master 只认识 `x_{i, p_i}`, cut 不能表达 "因为 connectivity 是 X 所以你不能选这 layout", 只能表达 "不能同时选这几个 (instance, pose) tuple".

**当时数据点**:
- 6 paradigm 不同 sub-problem 抽象层, cut form 全退化 instance-pose conjunction (size 1)
- 10 iter cut 累加但切空间 < 1% per cut
- Path 16 GOC-C2 想跳出 pose-bool, 用全图 owner-optional master form → vars 爆 (1.5M, RSS 25 GB)

**当时结论**: cut 表达力被 master form 锁死. 想升 cut 表达力必须升 master form. 但升 master form 撞资源 dead end.

## 阶段 5 (2026-05-20, augmented master Candidate D 实测后): "pose-bool master scale 是 fundamental 限制"

**认知更新**: 验证之前 hypothesis. 用户 sharp 抓出 Path 17 D2 是 sub-problem 路线不是 augmented master 路线. **augmented master Candidate D Phase 0 cheap gate** 单 anchor (22,28) 27×15 single-commodity 实测:

- master baseline (pose-bool): 285K vars + 280K cstr (build 27.8s)
- augment Δ: +22K vars + **+2.4M cstr**
- total: 307K vars + 2.68M cstr
- **solve: 603.9s UNKNOWN** (超 600s budget)
- **RSS: 32 GB** (cap 12 GB 2.6x over)

**Root cause 实测**: pose-bool master 自身有 **280,444 pose vars**, 平均每 pose 8.4 个 ports → channel `u[front_cell] == 1 OnlyEnforceIf(x_var)` 展开为 **2,358,534 个 OnlyEnforceIf 约束**. CP-SAT 在 2.68M cstr scale 下 presolve+solve 不能 600s 收敛.

**multi-commodity 推算**: ~10 commodity × 2.36M = **~24M cstr**. 物理不可能解.

**当前结论**: pose-bool master 自身 scale (280K pose vars × 平均 8.4 ports) **是 fundamental 限制**. 任何 channel routing/flow info into master 的 paradigm 必撞这个乘积上限.

减 scale 的 lever 全 inactive:
- 减 pose_data_count → 破坏 exactness (PROJECT_LOCK 禁 master 内 pose 预筛)
- 减 ports_per_pose → 改 source-of-truth facility 定义 (不可)
- 减 commodity_count → single-commodity 实测已 dead

## 现在 (2026-05-20) 对瓶颈的最佳理解

可能的诊断 (待 GPT review 验证 / 反驳):

### (A) Pose-bool master form 是 fundamental scale 限制

- 280K pose vars 是 enumeration 代价 — 每个 facility × 每个可能 pose 全展开
- 想 channel routing info 进 master → 任意 N_pose × N_ports × N_commodity 乘积
- 实测 2 次 (Path 16 / Augmented Candidate D) 都撞这个上限

### (B) Cut form 表达力被 master 维度限制

- 6 paradigm 不同 sub-problem 但 cut 翻译都退化 instance-pose conjunction
- master 只认识 `x_{i, p_i}`, cut 不能表达 connectivity/flow specific 信息
- 即使 sub-problem 数学最丰富 (D2 commodity flow), cut form 退化让 paradigm 同质死

### (C) Production CP-SAT + LBBD framework 穷尽

- 24 lever + 32 调研方向 + 9 次 GPT review 全 dead end
- 同档 production tooling (Choco / Gecode / MZ+Chuffed / Z3 / SCIP / clingo etc.) paradigm 同质或更弱
- 真要 break 需要 paradigm-research 级投资 (1-3 月+) 不在现成 import 范畴

## 不确定性 (待 GPT 反驳)

- 是不是真 root cause 在 master scale, 还是另有他因 (e.g. binding+routing sub-problem 复杂度 dominant)?
- 6 paradigm 撞同墙是不是真 fundamental 论证, 还是 paradigm 选择 bias 没覆盖到 essential class?
- 24 lever 全死的 evidence 是否充分 close production tooling 范畴, 还是某条 lever 实施不对 / verdict 判错?

## 项目历史认知错误清单 (供 GPT 评估)

为了诚实展示, 列项目对瓶颈认知中**判断错过的点**:

1. **早期 (Q1 2026)** RAM 瓶颈认知: 后来发现 master.solve 解不动是 search 问题不是 RAM 不足
2. **Q2 2026** wall 瓶颈认知: 后来发现 master form 选错是 root cause, 不是 NP-hard 本质
3. **Q2 2026** 24 lever 死法被 verdict 当 "cut 不够好": 后来发现 cut 表达力被 master 锁死 (维度问题不是质量问题)
4. **2026-05-20 上午**: 把 Path 17 D2 当 augmented master 验, 用户抓出实际是 sub-problem 路线, 600s wall 完全没用上
5. **2026-05-20 下午** (此包发出前): augmented master Candidate D 真实施 Phase 0, 实测 UNKNOWN + RSS 32 GB. 数据告知 master form 自身是瓶颈, 不是 augment 不彻底

这些错误每次都让对瓶颈的理解推进一层. 当前对瓶颈的理解 (master form 是限制) 仍可能错, 需要 GPT 反驳验证.
