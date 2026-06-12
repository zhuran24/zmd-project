# 终末地 IndustrialPlanner 精确求解器 — 证据持久化面 round 3 (饱和确认轮·崩溃时序与原子性角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_f78r3_snapshot_32a25b71.zip`, sha256 `32a25b711dcd9b35eb12fc0df1b1e17809492bf7a0a10228406f2dc896abe360`。**只认这个文件名, 文件区其它旧快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面历史: r1 (2 HIGH 已修) → r2 零 finding → 本轮 r3 饱和确认, 刻意换角度

证据持久化面 (campaign/resume 状态机 `src/search/exact_campaign.py` + 多进程波次合并 `src/search/exact_parallel_scheduler.py` / `src/search/outer_search.py`) 前两轮报告在包内 `cc_context/review/archive/algoaudit_campaign_scheduler_r{1,2}_REVIEW_20260612.md`:

- r1: **F78-F-01** (陈旧 candidate solution 穿越状态改写存活 → 可过 resume 边界撑 terminal 证据) + **F78-F-02** (波次合并只认 dispatch_seq 不绑候选身份) — 均已修复并经 r2 确认 sound。
- r2: 零 finding; 穷举了 campaign 全 writer (13 个写入点) 与队列/序列化边界 (8 类), 复验了 r1 的 resume-hash-fail-closed / terminal-export 守卫 / partial-failure fail-closed 三声明。

**本轮 r3 = 第 2 个干净轮确认, 换角度主攻崩溃时序与原子性** — 前两轮审的是"逻辑写入面", 本轮审"物理写入与时间轴": 进程在任意时刻被杀, 落盘状态的每一个可能形态, resume 都必须 fail-closed。

## 审查重点 (按优先级)

### Q1 原子写与部分写入状态 (最重要)
`ExactCampaign.save()` 的 atomic JSON write 实现: temp 文件 + rename 的原子性在 Windows/Linux 各自语义下是否真原子 (Windows 上 `os.replace` 对已存在目标的行为; 崩溃在 temp 写完 rename 前/rename 中)? fsync 缺失会不会让"rename 成功但内容没落盘"在断电场景出现, 留下半新半旧状态? resume 读到: ① 空文件 ② 截断 JSON ③ 完整但旧版本 ④ temp 残留文件 — 四种形态各自的处理路径是否全部 fail-closed (重建空 state 算 fail-closed, 静默吃截断不算)? checkpoint 之外还有哪些持久化文件 (telemetry/audit/frontier probe) 有部分写入风险, 它们的损坏会不会影响 proof 语义?

### Q2 崩溃-重跑时间轴穷举
对以下时刻逐一推演崩溃后 resume 的行为: ① `mark_candidate_started` 写入后 solve 前 (RUNNING 残留) ② worker 完成但 result 未消费 (队列内容丢失) ③ `mark_candidate_result(CERTIFIED)` 写入后 terminal commit 前 ④ `_commit_terminal_full_frontier_certified_result` 写入后 validator 抛错前 ⑤ `mark_campaign_stopped` 与 final save 之间。每个时刻: 落盘状态 resume 后会不会产生比崩溃前更强的证据主张? RUNNING 记录重跑时 attempts 计数与 audit 的一致性? 时刻 ④ 尤其关键: terminal evidence 写入与 project-bound 验证不是原子的, 崩溃夹缝中的 state 文件长什么样, resume 校验能不能抓住?

### Q3 多进程写入独占性
PROJECT_LOCK 说 "coordinator-only writer with disjoint candidate waves"。这个独占性是约定还是机制? worker 进程物理上能不能写 campaign state 文件 (它们持有路径吗)? 两个 campaign 进程 (operator 误启动双实例) 同时跑同一 state 文件会发生什么 — 有没有文件锁/pid 锁/启动检测? 若无, 交错写入的损坏形态 resume 能否全部识别 (这是纵深防御问题, 若靠 atomic write + resume 校验兜住则判可接受并说明理由)?

### Q4 audit_log 与 telemetry 的证据隔离复核
r2 判了 telemetry 不进 proof。本轮换角度: `audit_log` 呢 — F78-F-01 的强→弱阻断靠 audit event 记录, audit_log 截断/丢失会不会让阻断行为静默化 (阻断本身是 in-memory 行为还是依赖 audit 持久化)? `_validate_resume_state` 对 audit_log 字段的校验强度? frontier_probe 顶层字段 (r2 列为"调度 telemetry")在 resume 时被如何消费, 有没有它影响候选调度顺序从而影响 frontier 完备性主张的路径?

## 明确不要报的

- r1/r2 已修与已审结论 (报告在包内; F78 修复本体 r2 已确认, 重复报不算)。
- task_fingerprint 纵深防御建议 (r2 已挂账, 非缝)。
- 同 hash 旧版坏强记录无法自证 provenance (r2 已判固有限制)。
- binding/master/preprocess/routing/cuts 各面 (各自有线; 包内 lock 末尾的 F-BIND 条款是 binding 面在途工作)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2933 passed, 0 failed)**; 跑不完就跑专项 (test_exact_campaign_state_soundness / test_parallel_scheduler / test_v63 / test_exact_campaign_bound_state / test_exact_campaign_inspector) + 如实声明 (`-p no:randomly` 处理 seed 报错)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 崩溃时序类 finding 用"构造该落盘状态 + 跑 resume"的 probe 实证; 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 文件×损坏形态矩阵与 Q2 时间轴推演清单。

## 范围边界

- 重点 = 原子写/崩溃时序/写入独占/audit 隔离; 其余面不审。
