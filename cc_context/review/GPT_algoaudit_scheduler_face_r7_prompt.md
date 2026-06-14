# 终末地 IndustrialPlanner 精确求解器 — parallel scheduler 面 round 7 (真 Pro 确认轮·F-PS-R6-01 修复验证 + precheck/elimination 契约缝同型猎取)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_3b23181e.zip`, sha256 `3b23181e036be5daaf15d9166b76bb9d7b6acb49d81da3e046b8a07f1ec326b6`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD `eb5c012` — 本轮 r6 全部修复已合入, 这是**带修复的新树**)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

**本包变化**: `data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包, 已校验**, 无需再生。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **多进程 parallel scheduler 波次调度与 worker/precheck 结果合并写入 campaign**。核心文件 `src/search/exact_parallel_scheduler.py` + `src/search/outer_search.py` 的 coordinator 合并块 / serial+parallel precheck-elimination 强写入路径 / frontier 重建 / 终局判据。**campaign 持久化 / resume 状态机本体是 face 7 单独审, 本轮不审。**

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = **并行调度/合并 soundness**: ① worker 结果合并身份绑定 (不把「从未派发候选」或「畸形波次」的结果写进 campaign records); ② 合并失败的完备性闸 (fail-closed 不绕过终局 CERTIFIED); ③ 并行下状态聚合 + 跨波/跨 respawn 候选不丢不串不重; ④ **precheck-elimination 强写入路径** (serial + parallel coordinator 两处) 把 candidate 直接标 `INFEASIBLE` 入 campaign 的契约完整性。历史:

- r1 = F78-F-02 (HIGH, `results_by_seq` 只认 dispatch_seq 不校验候选身份 → 可注入「从未派发」结果)。
- r4 = F-PS-R4-01 (HIGH, result-validation failure 后 `results_by_seq` 未清空 → 畸形波次的合法同伴 CERTIFIED 泄漏进 campaign), 已修。
- r5 = F-PS-R5-01 (HIGH, discard latch 非全路径 sticky + consumer 白名单裸 `startswith` 前缀碰撞), 已修。
- r6 = 真 Pro 确认轮重审 r5, 抓 **F-PS-R6-01 (本轮已修+入 LOCK)**:
  - **F-PS-R6-01** = precheck-elimination 强写入路径只信 `triggered=True` 就把 candidate 标 `INFEASIBLE`。`_record_precheck_elimination()` 无条件写 `RUN_STATUS_INFEASIBLE` 并调 `exact_campaign.mark_candidate_result(...)`, 这条 coordinator-侧强结果写入路径**不经过** worker result 的 `_record_worker_result()` / `_parallel_wave_result_identity_failure()` 两道校验。所以一个 `triggered=True` 但 `status/master_status` 不自洽 (例如 `UNKNOWN`) 的畸形 precheck 返回会被提升为强 `INFEASIBLE` campaign record → false-INFEASIBLE, 错剪真实可行候选, frontier 耗尽时参与错误终局判断。是 F78-F-02 同族的「未校验结果流进强 campaign records」第四实例, 入口不是 worker RESULT 而是 coordinator precheck。
  - **修复 (本包已含, HEAD eb5c012)**: 新增 `_is_valid_pre_master_precheck_elimination()` (`outer_search.py:1510-1533`), 只有同时满足下列契约才允许 precheck elimination 落地, 否则视为「未消除」, serial 继续落 solver / parallel coordinator 继续派 worker (fail-closed):
    - `precheck_outcome` 是 `Mapping`;
    - `triggered == True`;
    - `status == RUN_STATUS_INFEASIBLE`;
    - `proof_summary` 是 `Mapping` 且 `proof_summary.master_status == RUN_STATUS_INFEASIBLE`;
    - `proof_summary.master_candidate_precheck` 是 `Mapping` 且其 `triggered == True`、`master_solve_skipped == True`、`precheck_reason` 非空。
  - 接入点: serial precheck lookahead gate `outer_search.py:2010-2013` (旧裸 `triggered` 检查改调 `_is_valid_...`); parallel coordinator precheck gate `outer_search.py:2192-2194` (同改)。
  - LOCK 登记: `PROJECT_LOCK.md` 已加 F-PS-R6-01 条款 (3.2 区段, 「Precheck-elimination campaign writes must re-verify the full INFEASIBLE precheck contract, not just `triggered=True`」)。
  - 严重度定性 (照抄 LOCK): canonical `evaluate_exact_candidate_pre_master_precheck` 在**每个** `triggered=True` 返回上硬绑 `status=INFEASIBLE` + `master_status=INFEASIBLE` (`benders_loop.py` 的 boundary-port / mandatory-rect / anchor119 / empty-pool 各 trigger 分支均如此), 故畸形 shape 在 canonical 数据 + 默认 env 下**不可达**; 这是**针对未来漂移的 fail-closed 防漂移 hardening (conditional)**, 不是 canonical 默认 env 下可触发的 false-INFEASIBLE soundness reset。

**本轮 r7 = 真 Pro 确认轮。姿态:** **不重报已修的 F-PS-R6-01 / F-PS-R5-01 / F-PS-R4-01 / F78-F-02 本身**; 任务 = ① 独立判定 F-PS-R6-01 的契约校验是否**真覆盖所有让畸形/未自洽 precheck 结果落进强 campaign record 的路径** (五条契约项是否各自必要且联合充分, 有没有第二条绕过 `_is_valid_...` 的强写入缝); ② 把 precheck/elimination/campaign-write 当攻击面, 在**整条 coordinator 强写入链**上找同型残留契约缝; ③ 确认修复**没有反向**误弃合法 precheck elimination (availability) 或破坏 frontier 完备性闸。包内带其它面同期修复, 别重报。

## 审查重点 (行号基于本包 HEAD eb5c012, 以符号名为准)

### Q1 [验 `_is_valid_pre_master_precheck_elimination` 契约充分性, 最高优先 false-INFEASIBLE 防漂移]

`_is_valid_pre_master_precheck_elimination()` (`outer_search.py:1510-1533`) 是 precheck elimination 落地前的唯一契约闸。请逐项独立验:

- (a) **五项契约的必要性与联合充分性**: `triggered` + `status==INFEASIBLE` + `master_status==INFEASIBLE` + `master_candidate_precheck.{triggered, master_solve_skipped, precheck_reason}` —— 这套校验是否穷尽了「一个被接受的 precheck elimination 必须满足的全部自洽条件」? 有没有某个字段, 畸形/漂移时仍能让 `_record_precheck_elimination()` 写出语义错误的强 `INFEASIBLE` 而本校验放行? 特别注意: 校验只看了 `master_candidate_precheck` 的三个 bool/str 字段, **没有**交叉校验 `precheck_reason` 取值是否属于已知合法 reason 集 (`empty_candidate_pool` / `mandatory_rect_group_all_anchors_infeasible` / `anchor119_row_domain_runtime_guard` / boundary-port 类) —— 一个 `precheck_reason="anything_nonempty"` 的漂移返回会被放行。这是否构成新缝, 还是「reason 自由文本不影响 INFEASIBLE 自洽性, 故无害」? 给出独立判断。

- (b) **两个接入点是否都真的拦在写入之前**: serial 路径 `2010-2013` 的 `if not _is_valid_...: continue` 与 parallel 路径 `2192-2194` 的 `if _is_valid_...:` 分支 —— 请确认这两处之外, `outer_search.py` 内**没有第二条** `_record_precheck_elimination()` 调用点 (或任何其它把 candidate 标 `INFEASIBLE`/`CERTIFIED` 直接写 `mark_candidate_result` 的 coordinator-侧路径) 绕过了 `_is_valid_...` 校验。请枚举全仓 `_record_precheck_elimination(` 调用点 + 全仓 `mark_candidate_result(` 调用点, 逐一核对各自前置是否有等价校验闸 (worker-result 路径走 `_record_worker_result`+`_parallel_wave_result_identity_failure`, precheck 路径走 `_is_valid_...`, terminal 路径走 full-frontier evidence)。

- (c) **`_record_precheck_elimination()` 自身的 payload 构造**: 它把 `precheck_outcome["proof_summary"]` 经 `_campaign_payload_from_precheck_proof` → `_augment_campaign_payload_with_selection` 加工后写入。校验闸只验了 proof_summary 的 `master_status` 与 `master_candidate_precheck`, 但**没有**约束 `exact_safe_cuts` 字段。precheck 路径产出的 `exact_safe_cuts` 是否可能畸形/被下游误读? (注: 按 lock, persisted `exact_safe_cuts` 是 telemetry 非 proof; 但请确认 precheck 路径没有别的字段被下游当终局判据。)

### Q2 [precheck 返回 shape 域核对 + canonical 不可达性坐实]

LOCK 把 F-PS-R6-01 定为 conditional hardening, 论据是「canonical `evaluate_exact_candidate_pre_master_precheck` 在每个 `triggered=True` 返回上硬绑 `status=INFEASIBLE`」。请把这条**当攻击面独立证伪或坐实**:

- (a) 枚举 `benders_loop.py::evaluate_exact_candidate_pre_master_precheck` (`:2114` 起) 的**全部** `triggered=True` 返回分支 (empty-pool group `:2164` 区、mandatory-rect `:1838/1855` 区、anchor119 runtime `:198-211` 区、boundary-port 类), 逐一确认每个 triggered 返回都同时带 `status==INFEASIBLE` + `proof_summary.master_status==INFEASIBLE` + 自洽的 `master_candidate_precheck` 三元组。**有没有任何一个 triggered 分支**返回的 shape 通不过 `_is_valid_...` 的五项 (例如某分支 triggered 但 `master_candidate_precheck.master_solve_skipped` 未置, 或 `precheck_reason` 空)? 若有 → 那是合法 precheck **被新校验误弃** (availability 缝, 反向缺陷), 请标 severity 并给 probe。
- (b) 反过来: 有没有 canonical 路径让 `evaluate_exact_candidate_pre_master_precheck` 返回 `triggered=True` 但 `status != INFEASIBLE`? 若能找到 → F-PS-R6-01 的「canonical-unreachable」定性被推翻, 该缝在默认 env 下**可达**, severity 应升为 false-INFEASIBLE soundness。若确认不可达 → 明确坐实 conditional 定性正确, 并指出**漂移触发条件** (什么样的 canonical edit / env 会让 triggered 与 status 解耦)。
- (c) `_evaluate_pre_master_precheck_best_effort()` (`outer_search.py:1477-1507`) 的异常兜底返回 `{"triggered": False, ...}` —— 确认 best-effort 包装层的任何路径都不会把一个**真 triggered** 的 precheck 误降级成 `triggered=False` (那是反向: 合法 elimination 被吞 → 多余 solve, availability), 也不会把异常态伪造成 `triggered=True`。

### Q3 [**r7 核心怀疑点**: coordinator 合并块对 precheck result 与 worker result 的 candidate_key 复用/串扰]

coordinator 合并块 (`outer_search.py:2350-2497`) 把 `coordinator_precheck_results` 与 `sorted_wave_results` 两类来源合并进 `wave_candidate_results_by_key`。请把这条**合并面当攻击面**:

- (a) `wave_candidate_results_by_key` 先由 `coordinator_precheck_results` 按 `result["candidate_key"]` 填充 (`:2353-2356`), 再被 worker results 按 `worker_result.candidate_key` 覆写/追加 (`:2357` 起)。同一波次内, 一个 candidate **既被 coordinator precheck 标 INFEASIBLE 又被派给 worker** 是否可能? 若可能, 同 key 的 precheck-INFEASIBLE 与 worker result 谁覆盖谁 / 是否产生「同 candidate 两条矛盾强记录」或「precheck INFEASIBLE 被 worker UNKNOWN 静默覆盖」? 请独立判这是设计上互斥 (precheck 命中即不派 worker) 还是存在 race/双写缝。注意 parallel coordinator 路径: precheck 命中时是否一定**从该波次的 dispatch 集合里剔除**该 candidate, 还是 precheck-INFEASIBLE 与 worker dispatch 可并存。
- (b) worker result 的 `matching_solve_entry` fallback `"prune_fill"` (`:2358-2370`): 当 `next(...)` 找不到匹配 `solve_wave_entries` 的 entry 时 selection_reason 落 `"prune_fill"`。在身份校验已通过 (consumer 第二道防线已验 dispatch_seq 已派发 / candidate tuple / candidate_key 匹配 task) 的前提下, `matching_solve_entry is None` 是否**真的不可达为 soundness 分支**? 还是存在一条 worker result 身份合法但其 candidate_key **不在** `solve_wave_entries` 里的路径 (例如 coordinator precheck 已消费该 key 后又收到同 key worker result), 让 `prune_fill` 兜底把一个无对应 dispatch entry 的 result 写进 campaign? 请坐实或证伪。
- (c) `wave_metrics_by_key` / `wave_candidate_results_by_key` 的 key 来源: precheck 用 `result["candidate_key"]`, worker 用 `worker_result.candidate_key` —— 两者构造 candidate_key 的函数是否同一? 若 precheck 与 worker 对同一 (area,w,h) 算出**不同** candidate_key 字符串, 会不会让本该互斥/去重的两条记录在 by_key 字典里并存成两个 key, 破坏「每 candidate 至多一条强记录」?

### Q4 [完备性闸 + 不误弃 + 同型第五实例]

- (a) **畸形 wave 完备性闸未被 r6 修复破坏**: 畸形 wave → `sorted_wave_results=()` → 合并后无 worker result 落地 → `effective_wave_completed=False` → campaign 以 `worker_process_failed`/`UNKNOWN` 停止; 已 `mark_candidate_started=RUNNING` 的候选留在 frontier potential_domain, 终局 CERTIFIED/INFEASIBLE 只在 domain 耗尽时触发。**r6 补丁后**, 被 `_is_valid_...` 拒掉的畸形 precheck 也**不再**进入 `wave_candidate_results_by_key` (serial `continue` / parallel 不进 `if` 分支)。请独立复核此链 + 确认 r6 补丁没有引入「畸形 precheck 被拒后 candidate 既不落 INFEASIBLE 也不留 frontier → 直接消失」的丢候选缝 (completeness)。
- (b) **反向误弃**: 一个完全合法、`triggered=True` 且全字段自洽的 precheck elimination, 会不会因 `_is_valid_...` 的五项校验**过严** (某项契约比 canonical 实际产出更紧) 被误判为「未消除」→ 合法剪枝退化成多余 solve/dispatch (availability, 非 soundness, 但请明确标注严重度)。结合 Q2(a) 的分支枚举给结论。
- (c) **同型第五实例猎取**: F78-F-02 / F-PS-R4-01 / F-PS-R5-01 (worker-result 入口) + F-PS-R6-01 (precheck 入口) 是同族「未校验结果流进 campaign 强记录」四实例。请猎取**第五个**: 全仓还有没有别的路径让未通过身份/有效性/自洽校验的结果经 `mark_candidate_result` / `_record_precheck_elimination` / prune_fill / coordinator merge 落进 campaign 强记录? 重点核: ① `outer_search.py` 内**所有** `mark_candidate_result(` 调用点 (CERTIFIED/INFEASIBLE/UNKNOWN 各分支) 的前置校验; ② `_record_probe_candidate_dispatch` / probe 路径有没有强写入; ③ serial 非 parallel 路径 (`parallel_processes <= 1`, `:1983` 起) 的 precheck-INFEASIBLE 落地与 parallel 路径是否走**同一** `_is_valid_...` 闸 (确认没有 serial-only 旁路)。

## 明确不要报的

- **F-PS-R6-01 / F-PS-R5-01 / F-PS-R4-01 / F78-F-02 本身已修, 重复报不算**; 只报修复**不完备 / 同型残留 / 反向缺陷**。
- 已 lock 条款 (本面): F78-F-02 + F-PS-R4-01 + F-PS-R5-01 (`PROJECT_LOCK.md:93`)、**F-PS-R6-01 (本轮新登记, 3.2 区段 precheck-elimination 条款)**、F-BIND-R5-01 (worker artifact-hash 封印, `:103`); Accepted invariant (`:91` coordinator-only writer + 不相交候选波次)。
- **跨面边界**: ① campaign/resume 状态机本体 (持久化原子性 / resume 一致性 / 强状态单调 `mark_candidate_result` 的强→弱阻断) 是 **face 7 单独审, 本轮不审**; 怀疑「并行下 worker/precheck 结果覆盖已有强记录」时真正防线在 face 7 `exact_campaign.py`, 交叉引述而非在本面重证。② worker 进程内 Benders/cuts/binding/几何 正确性、`evaluate_exact_candidate_pre_master_precheck` 内部各 trigger 判定的**算法正确性** (boundary-port / mandatory-rect / anchor119 是否真 INFEASIBLE) 属各自面 —— 本面只审「precheck 返回 shape 自洽 + 写入路径契约」, 不审「precheck 判定本身对不对」。③ 终局 full-frontier evidence 重放属 `certified_frontier.py` (face 7/终局证据线)。
- **exploratory / env-gated 行为不属 P1.2 soundness**: `EXACT_USE_POSE_BOOL_MASTER` / `EXACT_POWER_PLACEMENT_SUBPROBLEM` / `EXACT_B1_BYPASS_*` 都 env-gated 非 certified, 别在本面报它们。
- 设计决策 (canonical / 266 口径 / `min_side>=6` admissibility, owner 已定); master/routing/cuts/preprocess/benders/binding 各面。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 严重度纪律 (硬规矩)

- **只有** canonical 数据 + 默认 env 下可触发的 false-CERTIFIED = soundness reset (最高), 直接说清触发链。
- canonical 数据 + 默认 env 下可触发的 **false-INFEASIBLE** (错剪真实可行候选) = soundness, HIGH; 必须给 canonical-可达的触发证据, 否则降级。
- env-gated / 仅 canonical-drift 可达 / 仅 hand-built 畸形输入可达的缝 = **conditional hardening / 防漂移**, **必须明确标注「canonical 默认 env 下不可达」+ 触发前提**, 不得当 soundness reset 报。
- 反向误弃合法结果 / 多余 solve = **availability**, 明确标, 与 soundness 分列。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3074, HEAD eb5c012; 数目以实跑为准, 硬不变量 = 0 failed)。跑不完就跑本面专项 (`test_parallel*` / `test_exact_parallel*` / `test_outer_search*` / `test_exact_contract.py -k 'precheck or parallel or wave or frontier'`) + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- r6 已落地的 F-PS-R6-01 回归 probe (确认它们在新树存在且过):
  - `src/tests/test_exact_contract.py::test_serial_precheck_triggered_non_infeasible_does_not_mark_strong_record` (`:5608`)
  - `src/tests/test_exact_contract.py::test_parallel_precheck_triggered_non_infeasible_is_dispatched_to_worker` (`:6547`)
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。
- 契约: `PROJECT_LOCK.md:91,93` (coordinator-only / F78-F-02 含 R4/R5) + F-PS-R6-01 条款 (3.2 区段)。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附四段判读: ① `_is_valid_pre_master_precheck_elimination` 契约充分性 + 两接入点 + 无第二写入缝 (Q1) / ② precheck 返回 shape 域核对 + canonical 不可达性坐实或推翻 (Q2) / ③ **coordinator 合并块 precheck×worker candidate_key 串扰/双写/prune_fill 的证伪或坐实 (Q3, 本轮核心)** / ④ 完备性闸 + 无误弃 + 同型第五实例猎取结论 (Q4)。
- 真 Pro 确认轮; 前轮修复点 (F-PS-R6-01 的 `_is_valid_...` 闸 + 两接入点) 是攻击面起点, 按你自己的独立判断下结论。

## 范围边界

- 重点 = F-PS-R6-01 修复 soundness (契约充分性 + 无第二写入缝 + canonical 不可达性) + Q3 合并块 precheck/worker 串扰 + 同型残留 + 无误弃的真 Pro 确认; campaign/resume (face 7) 与其余面不审。
