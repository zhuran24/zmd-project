# 终末地 IndustrialPlanner 精确求解器 — parallel scheduler 面 round 8 (真 Pro 确认轮·F-PS-R7-01 共享 validator 修复验证 + precheck/elimination/campaign 强写入族第六实例猎取)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_0590f9ca.zip`, sha256 `0590f9ca30aac5bb7afe18945eb36d347ea8b0c5b467fd6baff4679eff8c5234`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD `7fec29a` — rounds 1+2 全部修复已合入, 这是**带修复的新树**)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

**本包变化**: `data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包, 已校验**, 无需再生。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **多进程 parallel scheduler 波次调度与 worker/precheck 结果合并写入 campaign**。核心文件 `src/search/exact_parallel_scheduler.py` + `src/search/outer_search.py` 的 coordinator 合并块 / serial+parallel precheck-elimination 强写入路径 / frontier 重建 / 终局判据, 以及本轮新进入审查面的 `src/search/benders_loop.py` solver-entry 侧 precheck short-circuit。**campaign 持久化 / resume 状态机本体是 face 7 单独审, 本轮不审。**

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = **并行调度/合并 soundness**: ① worker 结果合并身份绑定 (不把「从未派发候选」或「畸形波次」的结果写进 campaign records); ② 合并失败的完备性闸 (fail-closed 不绕过终局 CERTIFIED); ③ 并行下状态聚合 + 跨波/跨 respawn 候选不丢不串不重; ④ **precheck-elimination 强写入路径** (serial coordinator + parallel coordinator + solver-entry 三处) 把 candidate 直接标 `INFEASIBLE` 入 campaign 的契约完整性。历史 (同族「未校验结果流进 campaign 强记录」共五实例已修):

- r1 = F78-F-02 (HIGH, `results_by_seq` 只认 dispatch_seq 不校验候选身份 → 可注入「从未派发」结果), 已修。
- r4 = F-PS-R4-01 (HIGH, result-validation failure 后 `results_by_seq` 未清空 → 畸形波次的合法同伴 CERTIFIED 泄漏进 campaign), 已修。
- r5 = F-PS-R5-01 (HIGH, discard latch 非全路径 sticky + consumer 白名单裸 `startswith` 前缀碰撞), 已修。
- r6 = F-PS-R6-01 (precheck **入口**只信 `triggered=True` 就强写 INFEASIBLE; 修复新增 outer 侧 `_is_valid_pre_master_precheck_elimination()` 五项契约闸), 已修+入 LOCK。
- **r7 (round-2) = F-PS-R7-01 (本轮起点, 已修+入 LOCK)**:
  - **F-PS-R7-01** = r6 只补了 outer coordinator 的两个写入入口 (serial lookahead gate / parallel coordinator gate), 但**真正的 solver entry** `run_benders_for_ghost_rect()` 内部**自己又调一次** `evaluate_exact_candidate_pre_master_precheck()`, 而那条 short-circuit 当时只检查 `bool(pre_master_precheck.get("triggered", False))` 就无条件 `return RUN_STATUS_INFEASIBLE, None`。所以一个被 outer gate 正确拒掉、随后落进 serial solve 或派给 worker 的畸形 outcome, 会在 solver entry 内被**重新提升**成强 `INFEASIBLE` —— worker identity validation 只校验 worker result 身份/枚举/shape, 无法识别这个 INFEASIBLE 来自不自洽 precheck。这是 precheck→INFEASIBLE 强写入家族的**第五实例**, 入口在 solver entry 而非 coordinator。
  - **修复 (本包已含, HEAD 7fec29a)**: 把 r6 的 outer-only 校验**提升为跨模块共享 validator** `is_valid_pre_master_precheck_elimination(precheck_outcome: Any) -> bool` (`src/search/benders_loop.py:162-190`)。outer 的 `_is_valid_pre_master_precheck_elimination()` (`outer_search.py:1511-1514`) 现在**只代理**到这个共享 validator (避免 outer 与 solver-entry 两份契约再次分叉); solver entry `run_benders_for_ghost_rect()` 的 short-circuit 也改调同一共享 validator (`benders_loop.py:7033`), 只有满足下列**全部**契约才允许 short-circuit 成 `RUN_STATUS_INFEASIBLE`, 否则继续进真实 master/controller 路径 (fail-closed):
    - `precheck_outcome` 是 `Mapping`;
    - `triggered is True` (不是任意 truthy);
    - `status == RUN_STATUS_INFEASIBLE`;
    - `proof_summary` 是 `Mapping` 且 `proof_summary.master_status == RUN_STATUS_INFEASIBLE`;
    - `proof_summary.master_candidate_precheck` 是 `Mapping` 且 `triggered is True`、`master_solve_skipped is True`、`precheck_reason` 是非空字符串。
  - 接入点 (三处现已**同一闸**): serial precheck lookahead gate `outer_search.py:1991-1993`; parallel coordinator precheck gate `outer_search.py:2173-2175`; solver-entry short-circuit `benders_loop.py:7033`。
  - LOCK 登记: `PROJECT_LOCK.md` 的 F78-F-02 条款 (`:93`, 含 R4/R5) + F-PS-R6-01 precheck-elimination 条款 (3.2 区段)。F-PS-R7-01 作为 R6 同条款的「共享契约提升, 堵 solver-entry 旁路」收口。
  - 严重度定性 (照抄 r7 REVIEW + LOCK): canonical `evaluate_exact_candidate_pre_master_precheck` 在**每个** `triggered=True` 返回上硬绑 `status=INFEASIBLE` + `master_status=INFEASIBLE` + 自洽 `master_candidate_precheck` 三元组, 故畸形 shape 在 canonical 数据 + 默认 env 下**不可达**; F-PS-R7-01 是**针对未来 precheck-shape 漂移的 fail-closed 防漂移 hardening (conditional HIGH)**, 方向为 false-INFEASIBLE, 不是 canonical 默认 env 下可触发的 soundness reset。

**本轮 r8 = 真 Pro 确认轮。姿态:** **不重报已修的 F-PS-R7-01 / F-PS-R6-01 / F-PS-R5-01 / F-PS-R4-01 / F78-F-02 本身**; 任务 = ① 独立判定 F-PS-R7-01 的「共享 validator 提升」是否**真把所有把 precheck `triggered` 翻译成强 INFEASIBLE 的入口收口到同一个闸** (有没有第三/第四条仍裸信 `triggered` 或绕过共享 validator 的强写入缝); ② 把 precheck/elimination/campaign-write 当攻击面, 在**整条 coordinator + solver-entry 强写入链**上找同型残留契约缝 (**第六实例猎取**); ③ 确认这次「提升为共享 validator」**没有反向**误弃合法 precheck elimination (availability), 也没破坏 frontier 完备性闸; ④ 重审 r7 只半证过的 coordinator 合并块 precheck×worker 双写/串扰面 (本轮把它当独立核心怀疑点再压一遍)。包内带其它面同期修复, 别重报。

## 审查重点 (行号基于本包 HEAD 7fec29a, 以符号名为准)

### Q1 [验共享 validator `is_valid_pre_master_precheck_elimination` 的契约充分性 + 三入口收口完整性, 最高优先 false-INFEASIBLE 防漂移]

共享 validator `is_valid_pre_master_precheck_elimination()` (`benders_loop.py:162-190`) 现在是 precheck→强 INFEASIBLE 落地前的**唯一**契约闸 (outer 代理它, solver-entry 直接调它)。请逐项独立验:

- (a) **五项契约的必要性与联合充分性 (复核, 不是默认沿用 r7 结论)**: `isinstance(Mapping)` + `triggered is True` + `status==INFEASIBLE` + `proof_summary` 是 Mapping + `master_status==INFEASIBLE` + `master_candidate_precheck.{triggered is True, master_solve_skipped is True, precheck_reason 非空 str}` —— 这套校验是否穷尽了「一个被接受的 precheck elimination 必须满足的全部自洽条件」? 有没有某个字段/某条路径, 畸形或漂移时仍能让 short-circuit 写出语义错误的强 `INFEASIBLE` 而本校验放行? 特别独立判: 校验**没有**交叉核验 `precheck_reason` 取值属于已知合法 reason 集 (`empty_candidate_pool` / `mandatory_rect_group_all_anchors_infeasible` / `anchor119_row_domain_runtime_guard` / boundary-port 类 / coordinate-validation 类) —— 一个 `precheck_reason="anything_nonempty"` 的漂移返回会被放行。r7 REVIEW 判「reason 是 telemetry label, 强 INFEASIBLE 的语义授权来自 `status==INFEASIBLE` + `master_status==INFEASIBLE` + `master_solve_skipped is True` 三者联合, 未知 reason 不独立证明 INFEASIBLE, 故无害」。请**独立**复核这个判断是否成立 (有没有一条路径下游消费者**会**按 `precheck_reason` 取值分流, 让一个未知 reason 触发与真实 reason 不同的、不安全的处理)? 还是确实无害。给出你自己的结论, 别只复述 r7。

- (b) **三个接入点是否都真的拦在写入/返回之前, 且无第四条**: serial 路径 `outer_search.py:1991-1993` 的 `if not _is_valid_...: continue`、parallel 路径 `outer_search.py:2173-2175` 的 `if _is_valid_...:` 分支、solver-entry `benders_loop.py:7033` 的 `if is_valid_...:` short-circuit —— 请确认这三处之外, **全仓没有第四条**把 precheck `triggered` 翻译成强 `INFEASIBLE`/`CERTIFIED` 的路径绕过共享 validator。请**枚举全仓** `evaluate_exact_candidate_pre_master_precheck(` 的所有调用点 + 全仓 `is_valid_pre_master_precheck_elimination(` / `_is_valid_pre_master_precheck_elimination(` 的所有调用点, 逐一核对: 每个读 precheck `triggered`/`status` 并据此提前返回或写 campaign 的位置, 是否都**先过**共享 validator。重点排查: ① `run_benders_for_ghost_rect()` 里除 `:7033` 那处 short-circuit 外, 还有没有别的地方读 `pre_master_precheck` 字段后做强结果决策; ② 有没有别的函数 (例如 exploratory 路径、probe 路径、或某个 helper) 也调 `evaluate_exact_candidate_pre_master_precheck` 后自己判 `triggered` 写结果。

- (c) **outer 代理薄壳是否真无逻辑分叉**: `outer_search.py:1511-1514` 的 `_is_valid_pre_master_precheck_elimination()` 现在体内只有 `return is_valid_pre_master_precheck_elimination(precheck_outcome)`。请确认它**没有**任何额外的预处理/字段重写/异常吞没, 让 outer 看到的 outcome 与 solver-entry 看到的 outcome 在通过 validator 时口径不一致 (例如 outer 在调 validator 前对 `precheck_outcome` 做过 normalize 而 solver-entry 没有, 或反之)。

### Q2 [precheck 返回 shape 域核对 + canonical 不可达性再坐实]

LOCK + r7 把 F-PS-R7-01 定为 conditional hardening, 论据是「canonical `evaluate_exact_candidate_pre_master_precheck` 在每个 `triggered=True` 返回上硬绑 `status=INFEASIBLE` + 自洽三元组」。请把这条**当攻击面独立证伪或坐实** (不要默认沿用 r7 的枚举, 自己重走一遍):

- (a) 枚举 `benders_loop.py::evaluate_exact_candidate_pre_master_precheck` 的**全部** `triggered=True` 返回分支 (anchor119 runtime guard、empty candidate pool、boundary-port all anchors infeasible、mandatory rectangle complete group、coordinate validation infeasible, 以及任何其它), 逐一确认每个 triggered 返回都**同时**带 `status==INFEASIBLE` + `proof_summary.master_status==INFEASIBLE` + 自洽的 `master_candidate_precheck.{triggered, master_solve_skipped, precheck_reason}` 三元组。**有没有任何一个 triggered 分支**返回的 shape 通不过共享 validator 的五项 (例如某分支 triggered 但 `master_candidate_precheck.master_solve_skipped` 未置、或 `precheck_reason` 空、或 `master_candidate_precheck` 缺失)? 若有 → 那是合法 precheck **被共享 validator 误弃** (availability 缝, 反向缺陷, solver-entry 会多跑一次 master, serial/parallel coordinator 会多派一次 solve), 请标 severity 并给 probe。
- (b) 反过来: 有没有 canonical 路径让 `evaluate_exact_candidate_pre_master_precheck` 返回 `triggered=True` 但 `status != INFEASIBLE` (或 status==INFEASIBLE 但三元组不自洽)? 若能找到 → conditional 定性被推翻, 该缝在默认 env 下**可达**, severity 升为 false-INFEASIBLE soundness。若确认不可达 → 明确坐实 conditional 定性正确, 并指出**漂移触发条件** (什么样的 canonical edit / owner-gated 扩展 / env 会让 triggered 与 status/三元组解耦)。
- (c) `_evaluate_pre_master_precheck_best_effort()` (`outer_search.py` 内, 异常兜底返回 `{"triggered": False, ...}`) 与 solver-entry 直接调的裸 `evaluate_exact_candidate_pre_master_precheck()` 是**两条不同包装**: outer 走 best-effort 包装, solver-entry 不走。请确认: ① best-effort 包装层任何路径都不会把一个**真 triggered** 的 precheck 误降级成 `triggered=False` (那是反向: 合法 elimination 被吞 → 多余 solve, availability), 也不会把异常态伪造成通过 validator 的 `triggered=True`; ② solver-entry 直接调 `evaluate_exact_candidate_pre_master_precheck()` 时若该函数**抛异常**, 异常如何传播 —— 会不会被某层 `except` 吞成一个看起来合法的强结果, 或反过来让本该 short-circuit 的合法 elimination 丢失。两条包装在「同一畸形/异常 outcome」上是否给出**一致**的 validator 判定 (口径分叉本身就是潜在缝)。

### Q3 [**r8 核心怀疑点 (重压 r7 只半证过的面)**: coordinator 合并块对 precheck result 与 worker result 的 candidate_key 双写/串扰/prune_fill]

coordinator 合并块 (`outer_search.py:2334-2462`) 把 `coordinator_precheck_results` 与 `sorted_wave_results` 两类来源合并进 `wave_candidate_results_by_key`。r7 判此面无双写, 但只给了「precheck 命中即 `continue` 不进 `solve_wave_entries`」一句论证。请把这条**合并面当独立攻击面重压一遍**, 自己证伪或坐实:

- (a) `wave_candidate_results_by_key` 先由 `coordinator_precheck_results` 按 `result["candidate_key"]` 填充 (`:2334-2337`), 再被 worker results 按 `worker_result.candidate_key` 覆写/追加 (`:2338` 起, 落点 `:2418`)。在 parallel coordinator 路径里, valid precheck elimination 命中后立即 `continue` (`outer_search.py:2211`), 该 candidate **不进入** `solve_wave_entries` (`:2212` 起才 append), worker tasks 又只由 `solve_wave_entries` 构造 —— 请独立坐实「同一波次内一个 candidate 不可能既是 coordinator-precheck result 又被派 worker」这条互斥**真成立**, 没有任何 race / 重入 / 同 candidate 在 `lookahead_entries` 里出现两次 (一次命中 precheck、一次落 solve) 的路径。若**能**构造出同 key 既进 `coordinator_precheck_results` 又进 `solve_wave_entries` → 合并块会出现「同 candidate 两条记录」, precheck-INFEASIBLE 与 worker result 谁覆盖谁 (注意 worker 覆写在后, `:2418`)、是否让一个 precheck-INFEASIBLE 被 worker `UNKNOWN` 静默覆盖 (或反之), 请给触发链与 severity。
- (b) **`prune_fill` fallback (`outer_search.py:2348-2352`)**: 当 `next(...)` 在 `solve_wave_entries` 里找不到匹配 `worker_result.candidate_key` 的 entry 时, `selection_reason` 落 `"prune_fill"`, 且 `wave_slot_index` 退化成 `worker_result.dispatch_seq` (`:2432-2436`)、probe 字段全退化成默认。在 worker identity validation 已通过 (scheduler 侧 `:148-149` 已验 `result.candidate_key == task.candidate_key`, consumer 侧二次验 dispatch_seq 已派发 / candidate tuple / candidate_key) 的前提下, `matching_solve_entry is None` 是否**真的不可达**? 请独立判: ① worker tasks 既然只来自 `solve_wave_entries`, 一个身份合法的 worker result 的 candidate_key 是否**必然**在 `solve_wave_entries` 里? 有没有一条路径 (例如 coordinator precheck 已消费某 key 后又因某种原因收到同 key worker result; 或跨 respawn/跨 attempt 时 `solve_wave_entries` 被重建而 worker result 来自旧集合; 或 worker result 的 candidate 合法但其 `solve_wave_entries` entry 在某分支被剔除) 让 `prune_fill` 兜底把一个无对应 dispatch entry 的 result 经 `:2396` 强写 campaign? 坐实或证伪, 别只说「sound path 下不可达」。
- (c) candidate_key 口径一致性 (坐实): precheck 用 `_record_precheck_elimination` 产出的 `_candidate_result_entry` 里的 `candidate_key`, worker 用 `worker_result.candidate_key`, scheduler 身份校验用 `task.candidate_key`, 合并块外层重排用 `_candidate_key(tuple(entry["candidate"]))`。请确认这四处构造 candidate_key 的**最终都是同一函数语义** `f"{int(w)}x{int(h)}"` (`WorkerTask.candidate_key`/`WorkerResult.candidate_key` 在 `exact_parallel_scheduler.py:42-44,62-64`; `certified_frontier.candidate_key` 在 `:155-160`; `outer_search._candidate_key:455-456` 代理 certified_frontier)。若任一处对同一 (area,w,h) 算出**不同** candidate_key 字符串 → 本该互斥/去重的两条记录会在 `wave_candidate_results_by_key` 里并存成两个 key, 破坏「每 candidate 至多一条强记录」, 或让 `prune_fill` 误触发。坐实一致 / 找出分叉。

### Q4 [完备性闸 + 不误弃 + 同型第六实例]

- (a) **畸形 wave 完备性闸未被 r7 共享-validator 提升破坏**: 畸形 wave → `sorted_wave_results=()` → 合并后无 worker result 落地 → `effective_wave_completed=False` → campaign 以 `worker_process_failed`/`UNKNOWN` 停止; 已 `mark_candidate_started=RUNNING` 的候选留在 frontier potential_domain, 终局 CERTIFIED/INFEASIBLE 只在 domain 耗尽时触发。**r7 补丁 (solver-entry 也走共享 validator) 后**, 一个被共享 validator 拒掉的畸形 precheck: 在 outer 侧不进 `coordinator_precheck_results`/不 `continue` → 落 `solve_wave_entries` 派 worker; 在 solver-entry 侧不 short-circuit → 进真实 master/controller。请独立复核此链, 确认补丁没有引入「畸形 precheck 被拒后 candidate 既不落 INFEASIBLE 也不留 frontier → 直接消失」的丢候选缝, 也没引入「solver-entry 不再 short-circuit 后, 真实 master 路径对一个本应被合法 precheck 跳过的 candidate 跑出**别的**强结果」的越权 (completeness + 无越权)。
- (b) **反向误弃**: 一个完全合法、`triggered=True` 且全字段自洽的 precheck elimination, 会不会因共享 validator 五项校验**过严** (某项契约比 canonical 实际产出更紧) 被误判为「未消除」→ 在 serial/parallel 退化成多余 solve/dispatch, 在 solver-entry 退化成多跑一次 master (availability, 非 soundness, 但请明确标注严重度)。特别核: 共享 validator 把 bool 字段从「truthy」收紧成 `is True` (`:171,183,185`), canonical 当前产物是否**全是真实 `bool` 对象** (而非 `1`/`numpy.bool_`/字符串 `"true"` 这类 truthy-非-`True`)? 若 canonical 某分支产出 `numpy.bool_(True)` 之类 → `is True` 会误弃合法 elimination。结合 Q2(a) 的分支枚举给结论。
- (c) **同型第六实例猎取**: F78-F-02 / F-PS-R4-01 / F-PS-R5-01 (worker-result 入口) + F-PS-R6-01 (precheck coordinator 入口) + F-PS-R7-01 (precheck solver-entry 入口) 是同族「未校验/不自洽结果流进 campaign 强记录」五实例。请猎取**第六个**: 全仓还有没有别的路径让未通过身份/有效性/自洽校验的结果经 `mark_candidate_result` / `_record_precheck_elimination` / `run_benders_for_ghost_rect` 返回 / prune_fill / coordinator merge 落进 campaign 强记录 (`CERTIFIED`/`INFEASIBLE`)? 重点核: ① `outer_search.py` 内**所有** `mark_candidate_result(` 调用点 (含 `:1552`、`:2377`、`:2396`、serial 落点 `:2604/:2633/:2668/:2708` 等) 的前置校验, 逐一标注各自走的是哪道闸 (precheck→共享 validator; worker-result→scheduler identity + consumer 二次 identity; serial solver-result→`run_benders_for_ghost_rect` 内部契约); ② `_record_probe_candidate_dispatch` / probe 路径 (`outer_search.py:1996` 区) 有没有强写入或对 probe candidate 标强状态; ③ serial 非 parallel 路径 (`parallel_processes <= 1`) 的 precheck-INFEASIBLE 与 serial solver-result 落地, 与 parallel 路径是否走**同一**共享 validator + 同一身份校验 (确认没有 serial-only 旁路, 尤其 serial solver-result 不经 worker identity validation, 它的强结果自洽性**完全**依赖 `run_benders_for_ghost_rect` 内部契约 —— 这条 serial 强写入链是否还有 r7 没堵到的缝)。

## 明确不要报的

- **已修条款本身重复报不算**: F-PS-R7-01 / F-PS-R6-01 / F-PS-R5-01 / F-PS-R4-01 / F78-F-02 (本面 round-1/round-2 已 lock 的全部 finding); 只报修复**不完备 / 同型残留 (第六实例) / 反向缺陷 (误弃)**。
- 已 lock 条款 (本面): F78-F-02 + F-PS-R4-01 + F-PS-R5-01 (`PROJECT_LOCK.md:93`)、F-PS-R6-01 (precheck-elimination 条款, 3.2 区段)、**F-PS-R7-01 (共享 validator 提升, 同条款收口)**、F-BIND-R5-01 (worker artifact-hash 封印, `:103`); Accepted invariant (`:91` coordinator-only writer + 不相交候选波次)。
- **跨面边界**: ① campaign/resume 状态机本体 (持久化原子性 / resume 一致性 / 强状态单调 `mark_candidate_result` 的强→弱阻断, F78-F-01 `:92`) 是 **face 7 单独审, 本轮不审**; 怀疑「并行下 worker/precheck 结果覆盖已有强记录」时真正防线在 face 7 `exact_campaign.py`, 交叉引述而非在本面重证。② worker 进程内 Benders/cuts/binding/几何正确性、`evaluate_exact_candidate_pre_master_precheck` 内部各 trigger 判定的**算法正确性** (boundary-port / mandatory-rect / anchor119 / coordinate-validation 是否真 INFEASIBLE) 属各自面 —— 本面只审「precheck 返回 shape 自洽 + 写入路径契约 + 三入口收口」, 不审「precheck 判定本身对不对」。③ 终局 full-frontier evidence 重放属 `certified_frontier.py` (face 7/终局证据线)。
- **exploratory / env-gated 行为不属 P1.2 soundness**: `EXACT_USE_POSE_BOOL_MASTER` / `EXACT_POWER_PLACEMENT_SUBPROBLEM` / `EXACT_B1_BYPASS_*` 都 env-gated 非 certified, 别在本面报它们 (除非你发现一条 env-off 默认路径也走它们)。
- 设计决策 (canonical / 266 口径 / `min_side>=6` admissibility, owner 已定); master/routing/cuts/preprocess/benders 内部各面。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 严重度纪律 (硬规矩)

- **只有** canonical 数据 + 默认 env 下可触发的 false-CERTIFIED = soundness reset (最高), 直接说清触发链。
- canonical 数据 + 默认 env 下可触发的 **false-INFEASIBLE** (错剪真实可行候选) = soundness, HIGH; 必须给 canonical-可达的触发证据, 否则降级。
- env-gated / 仅 canonical-drift 可达 / 仅 hand-built 畸形输入 (monkeypatch precheck shape) 可达的缝 = **conditional hardening / 防漂移**, **必须明确标注「canonical 默认 env 下不可达」+ 触发前提**, 不得当 soundness reset 报。
- 反向误弃合法结果 / 多余 solve / 多跑 master = **availability**, 明确标, 与 soundness 分列。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3092, HEAD 7fec29a; 数目以实跑为准, 硬不变量 = 0 failed)。跑不完就跑本面专项 (`test_parallel*` / `test_exact_parallel*` / `test_outer_search*` / `test_exact_contract.py -k 'precheck or parallel or wave or frontier'`) + 如实声明哪些没跑 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- r7 已落地的 F-PS-R7-01 回归 probe (确认它们在新树存在且过):
  - `src/tests/test_exact_contract.py::test_pre_master_precheck_elimination_contract_rejects_truthy_non_bool` (覆盖 `triggered` 非 bool truthy 被共享 validator 拒)
  - `src/tests/test_exact_contract.py::test_run_benders_precheck_triggered_non_infeasible_falls_through` (覆盖 solver-entry 对畸形 precheck 不再直接返回 INFEASIBLE, 继续进真实 controller)
  - r6 遗留: `test_serial_precheck_triggered_non_infeasible_does_not_mark_strong_record` / `test_parallel_precheck_triggered_non_infeasible_is_dispatched_to_worker`
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。
- 契约: `PROJECT_LOCK.md:91,92,93` (coordinator-only / F78-F-01 / F78-F-02 含 R4/R5) + F-PS-R6-01/R7-01 (3.2 区段 precheck-elimination 共享契约)。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附四段判读: ① 共享 validator `is_valid_pre_master_precheck_elimination` 契约充分性 + 三接入点收口完整性 + 无第四写入缝 (Q1) / ② precheck 返回 shape 域核对 + canonical 不可达性坐实或推翻 (Q2) / ③ **coordinator 合并块 precheck×worker candidate_key 双写/串扰/prune_fill 的证伪或坐实 (Q3, 本轮核心)** / ④ 完备性闸 + 无误弃 + 同型第六实例猎取结论 (Q4)。
- 真 Pro 确认轮; 前轮修复点 (F-PS-R7-01 的共享 validator + 三接入点) 是攻击面起点, 按你自己的独立判断下结论, 别只复述 r7 REVIEW。

## 范围边界

- 重点 = F-PS-R7-01 修复 soundness (共享 validator 契约充分性 + 三入口收口无第四缝 + canonical 不可达性) + Q3 合并块 precheck/worker 双写串扰 + 同型第六实例 + 无误弃的真 Pro 确认; campaign/resume (face 7) 与其余面不审。
