# 终末地 IndustrialPlanner 精确求解器 — 证据持久化面 round 2 (F78-F-01/F-02 修复确认轮)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_f78r2_snapshot_13dc4e59.zip`, sha256 `13dc4e596b5327a8fc888a39d89405553bffb7fb4c993538755580b3accd22af`。**只认这个文件名, 文件区其它旧快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 背景: round 1 爆 2 个 HIGH, 本包刚落地其修复

证据持久化面 (campaign/resume 状态机 + 多进程波次合并) round 1 审查报告在包内 `cc_context/review/algoaudit_campaign_scheduler_r1_REVIEW_20260612.md`, 抓到:

- **F78-F-01 (campaign 状态机)**: 陈旧 candidate `solution` 穿越状态改写存活 — `mark_candidate_started` 把旧记录连 solution 拷进 RUNNING; `mark_candidate_result` 仅在 status≠CERTIFIED 时 pop solution, 后续 CERTIFIED(solution=None) 直接继承旧 witness; `_validate_candidate_record` 不拒弱状态带 solution → 陈旧 witness 可过 resume 边界撑起 terminal 证据 (false-CERTIFIED 方向)。
- **F78-F-02 (波次合并)**: `results_by_seq` 只认 dispatch_seq 不校验候选身份 (setdefault 先到先得); outer_search 对未匹配结果走 `prune_fill` 兜底照写 campaign → 队列边界可注入"从未派发的候选"的结果。

本包已落地修复 (commit 链尾两个):
- `exact_campaign.py`: `STRONG_CANDIDATE_STATUSES = {CERTIFIED, INFEASIBLE}`; `_validate_candidate_record` 拒任何非 CERTIFIED 记录带 `solution` (`candidate_non_certified_solution_present:<key>`); `mark_candidate_started` 对同工件强记录 no-op (rerun 不降 RUNNING)、弱记录显式剥 solution; `mark_candidate_result` 前置校验 status 合法性、CERTIFIED 必须带新 solution mapping、非 CERTIFIED 拒带 solution、强状态冲突 (CERTIFIED vs INFEASIBLE) raise、强→弱降级审计阻断 (audit_log 事件 + 不改记录)。
- `exact_parallel_scheduler.py`: 每波 `tasks_by_seq`; 所有收割路径走 `_record_worker_result` (校验 dispatch_seq/attempt_index/candidate/candidate_key 与原 WorkerTask 全匹配, 拒重复 seq, 拒非法 status/solution 组合, errored 结果丢弃)。
- `outer_search.py`: 消费侧对每个 wave 结果独立再校验身份; 畸形波次 → completed=False + telemetry 记因 + 零错配写入 + `worker_process_failed`/UNKNOWN 停机。
- PROJECT_LOCK 新增 F78-F-01/F-02 两条款; 回归 `test_exact_campaign_state_soundness.py` (新) + `test_parallel_scheduler.py` 增补 + `test_v63` 改为直接篡改态构造非法态。

你的任务: 对抗式审查 r1 修复——确认正确且没引入新缝, **并把同类问题泛化穷举**。**若审完无残留, 明确报零** (本面饱和判据 = 连续 2-3 轮独立零 finding, 这是确认轮)。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 审查重点 (按优先级)

### Q1 r1 修复本身
- F-01: 强状态 no-op/单调语义有没有反向害处 — 工件换代后 (`artifact_hashes` 变) 强记录会被 resume 校验整体拒掉重置, 但**同 hash 内**有没有合法场景需要真正重跑一个已 CERTIFIED 候选 (如 owner 手动清单个候选)? no-op 会不会把"陈旧但同 hash 的坏证据"也保护起来 (它当初是怎么进来的——所有入口都走新校验吗)?
- F-01: `mark_candidate_result` 强→弱审计阻断路径**直接 return**, 跳过了 exact_safe_cuts/计数等字段更新 — 有没有调用方依赖这些副作用 (cuts 是 telemetry-only, 但计数器漂移会不会让别的校验误判)?
- F-02: `_record_worker_result` 的身份四元组校验有没有漏维度 (如 epsilon tag / solve_mode / master_search_profile 不同但 seq/candidate 相同的结果)? respawn 重派后 dispatch_seq 是否真正全波唯一?
- F-02: 错配波次把**同伴有效结果也丢弃** (实测比 r1 REVIEW 描述更保守) — 确认这只伤完整性不伤 soundness; 以及 telemetry 的 failure_reason 字符串会不会被任何上游当成强证据消费?

### Q2 泛化: campaign 还有哪些 writer 能让弱证据穿成强证据? (最重要)
F78-F-01 的本质 = 「writer 改写记录时字段残留/继承让历史强证据冒充新结果」。请穷举 `exact_campaign.py` **所有**写 state 的方法 (`update_candidate_bound_state` / `update_candidate_running_proof_summary` / `append_candidate_cuts` / `mark_campaign_stopped` / `set_final_result` 族 / frontier evidence 写入 / 任何直接改 `self.state` 的点), 对每一个判定: 它能否让陈旧/弱证据在改写后看起来更强? 残留字段 (proof_summary / bound_state / terminal evidence) 有没有 F-01 同类的继承缝? `_validate_resume_state` 对每个字段族是 deny-unknown 还是放行自由值?

### Q3 泛化: 队列/序列化边界还有哪些信任缺口?
F78-F-02 的本质 = 「跨进程边界的数据未经身份/完整性校验就当真」。multiprocessing queue 还传了什么 (task 下发方向 / heartbeat / telemetry)? worker 侧 `_worker_entry` 对收到的 WorkerTask 有没有对称校验? pickle round-trip 有没有字段语义漂移 (status 字符串 vs 枚举)?

### Q4 r1 "无新 finding" 复核结论抽查
r1 报告判了 resume hash fail-closed / atomic_write 崩溃一致性 / RUNNING 崩溃重跑 / terminal export 守卫 / 部分失败 fail-closed / max_lex 一致 / telemetry 隔离 七项干净。抽查其中你认为论证最薄的 1-2 项, 独立验证或推翻。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless, owner 已定); preprocess 面 (r1-r7 已审, 连零 1); persisted `exact_safe_cuts` 是 telemetry 不是 proof object (V82)。
- 旧 campaign state 因新校验被拒 (`candidate_non_certified_solution_present` 等) — 预期 fail-closed。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; 已 refuted 误判。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2917 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 同批推进的登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2/Q3 实际穷举过的 writer/边界清单。

## 范围边界

- 重点 = F78 修复面 + Q2 writer 穷举 + Q3 边界穷举; 其余面不审。
