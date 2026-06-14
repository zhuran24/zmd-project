# 终末地 IndustrialPlanner 精确求解器 — campaign/resume 状态机面 round 6 (真 Pro 第三次全面 soundness 重审·攻持久化原子性/提交时序层)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_3b23181e.zip`, sha256 `3b23181e036be5daaf15d9166b76bb9d7b6acb49d81da3e046b8a07f1ec326b6`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照, HEAD `eb5c012` —— **这是带本轮全部修复合入的新树** (上一轮 r5 的树是 `8c61e1e`)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包**, 已校验, 不准伪造/重生覆盖。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **campaign 持久化 / resume 状态机** (`src/search/exact_campaign.py` 为核, 配 `src/search/certified_frontier.py` 终局证据 + `src/search/outer_search.py` 的 frontier 重建/终局提交)。**并行 scheduler 合并是 face 8 单独审, 本轮不审。**

## 本面定义 + 本轮性质 (关键, 必读)

本面 = **状态机 soundness**, 不重新证明 LBBD 子问题正确性 (那是 master/routing/cuts/preprocess/binding 各面的事)。它把单个候选的 CERTIFIED/INFEASIBLE 判定当作「在同一冻结 artifact hash 下已正确」来信任, 只校验: ① **持久化落盘原子性 + 崩溃时序**; ② **resume 一致性** (候选不重复消费 / 不丢已证候选 / 陈旧 witness 不穿越状态改写); ③ **强状态单调 mark_candidate_result/mark_candidate_started 不变量** (强状态不降级、弱不覆盖强、矛盾 loud-fail、CERTIFIED solution 卫生); ④ 终局证据 (full-frontier potential_domain 空 + frontier 空) 不被错误升格成更强主张。

**历史轨迹** (本面此前与 face 8 同包审, 后独立成面):
- r1 = **F78-F-01** (HIGH, false-CERTIFIED: 陈旧 candidate solution 穿越状态改写存活 — 已修, lock:92)。
- r2 = 零 finding (F-01 逐处复核 + 全 writer 清单穷举)。
- r3 = 零 finding (崩溃时序/原子性矩阵 + 五时刻推演 + 多进程独占)。
- r4 = 零 finding (真 Pro 首轮全面重审, Q1-Q6 六块逐块判 sound)。
- **r5 = 零 finding (真 Pro 第二次重审)**。N1-N6 六块换角度判 sound: terminal projection 的 domain 同源性 (从 evidence 内 `candidate_generation` contract 重生 domain, artifact-hash 封 `candidate_placements/canonical_rules/generic_io_requirements/preprocess_plan` + safe-bound + authority)、digest 覆盖每条参与剪枝 record 的 `(key,w,h,area,status[,solution_digest])`、`(w,h)/(h,w)` 全定向有序键无误剪、`candidate_objective` 返回 `(area,min_side)` 两侧同构、强状态单调 (started 不降级 / 弱覆盖 audit-block / 双向矛盾 loud-fail)、evidence schema==2 不迁移 + deny-unknown domain authority 在所有 public CERTIFIED 面前 hard-fail。

**本轮 r6 = 真 Pro 第三次独立全面 soundness 重审。姿态铁律:**
- r4/r5 都是真 Pro 零 finding, **但前轮 clean 不构成任何先验**。同期真 Pro 一切到其它面屡次抓出 thinking 漏了多轮、甚至自己上一轮漏掉的真 finding (cuts CUT-R12/R13、preprocess R15/R16、几何 master)。请当作从未深审重走。
- **不要复读 r5 的 N1-N6 判读路径**。r5 已把「projection domain 同源 / digest 覆盖 / orientation 键 / objective 同构 / 强状态单调表层 / evidence schema」这六条主路各跑过探针并判 sound; 本轮要求**换全新角度下沉到「字节落盘 + 内存改写时序 + 提交顺序」这一层** —— r4/r5 一直把「`atomic_write_json` 真原子」「save 是 writer、validate 在 resume/export 兜底」「mark_candidate_result 的内存改写顺序无缝」当**已成立的前提**, 本轮就攻这些前提本身。若你重走 N1-N6 原路得到同结论, 那只是复制 r5, 没有增量。
- 本轮 attack surface = **持久化原子性 / 崩溃时序 / 内存状态改写顺序 / 提交-校验时序**。核心问题: 一次崩溃 (kill -9 / 断电 / 磁盘满 / 进程被抢占在两次 write 之间) 能否留下一个**自洽得能通过 resume validation、但语义上已 false-CERTIFIED / 已丢失已证候选 / 已让弱结果实际覆盖了强结果**的盘上状态? 以及 `mark_candidate_result` / `mark_candidate_started` 的**内存内改写本身**有没有顺序缝 (先改后校验、改了一半 return、字段残留)。

注意行号: 下面给的 `file:line` 基于 HEAD `eb5c012` 包内源码 (与上轮 `8c61e1e` 相比这几个核心函数行号未动), **以你解包后实读为准**, 函数名稳定 (`atomic_write_json` / `_fsync_directory` / `save` / `mark_candidate_result` / `mark_candidate_started` / `_validate_resume_state` / `load_or_create` / `_validate_candidate_record` / `terminal_certified_final_result_violation`); 若行号微漂以函数体为准, 别因行号差一两位就当代码变了。

## 本轮新攻击面 (6 块, 全部是 r4/r5 当前提信任、未正面深挖的「落盘/时序/内存改写」层)

### M1 [落盘原子性的真实粒度] `atomic_write_json` + 崩溃在 write 之间能留下什么自洽坏态
`atomic_write_json` (`exact_campaign.py:1304-1324`) 用 `mkstemp` → `json.dump` → `flush` → `os.fsync(fd)` → `os.replace` → `_fsync_directory(parent)` 的标准 tmp-swap 模式, 单文件写是原子的。但本面真正的状态不是「一个 JSON 文件内部的原子性」, 而是「**一次 `save()` 调用 + 它依赖的内存 self.state**」是否在崩溃时序下整体一致。请深查: ① `save()` (找到它的全部调用点) 是不是**只写一个 checkpoint 文件**, 还是写多个文件 (主 state + sidecar / manifest / final_solution)? 若是多文件, 它们之间**没有跨文件原子性** —— 崩溃落在「主 state 已 `os.replace` 但 sidecar 还没写」之间, resume 读到的主 state 与 sidecar 是否会被当作一致的 CERTIFIED 证据组? ② `os.replace` 后紧接 `_fsync_directory`, 但若进程在 `os.replace` 成功**但 `_fsync_directory` 之前**崩溃 + 随后断电, POSIX 下目录项可能未持久 → 旧文件复活。旧 state 是不是一定 hash-incompatible 或一定 fail-closed, 还是存在「旧 state 是上一轮合法 CERTIFIED、artifact 没变」从而旧坏态被当合法 resume? ③ tmp 文件用固定 dir + `os.replace` 同目录, 跨文件系统不会触发 —— 但若 `dir` 是 symlink/不同 mount (lock:V98 b5a symlink campaign path), `os.replace` 的原子性是否仍成立? **重点: 找一个崩溃时刻, 使盘上留下的状态既通过 `_validate_resume_state` 又在语义上 false-CERTIFIED 或丢已证候选。** 实证不出来就明说原子性这层是 sound。

### M2 [save vs validate 时序] save 是 writer 非 validator —— 写进盘的坏态靠谁在何时拦
r4/r5 反复用「`save()` 是 writer 不是 validator, 坏态在 resume/export 被 fail-closed」当兜底。请**独立验证这个兜底的时序完整性**: ① `save()` 把 `self.state` 直接序列化落盘, 它**写之前不做任何 validation**对吗? 那么唯一的拦截点是 `_validate_resume_state` (resume 时) 和 `best_certified_result` / terminal evidence 校验 (export 时)。请追: 一个进程在**同一次运行内** (不经过 resume) 写出 CERTIFIED final_result 后, 直接调 export / `best_certified_result` —— 这条「**不重启就出证**」的热路径上, 是否每个 public CERTIFIED 出口都强制过了与 resume 同强度的 terminal evidence 校验, 还是热路径信任内存态、只有冷启 resume 才全校验? 若热路径有一个出口 (manifest writer / final_solution writer / `best_certified_result` 某分支) 在内存态下绕过了 resume 级校验, 那 save 的「writer 非 validator」论证就有一条不经 validator 的公开面。② `_validate_resume_state` 里 `final_result is not None and final_status != "CERTIFIED"` (`:1517-1518`) 等结构校验, 与 export 侧校验是否**同一套**还是两套可能漂移的实现? 重点判**写盘后到出证之间, 是否真有恰好一道不可绕过的 validator**。

### M3 [mark_candidate_result 内存改写顺序] 改写中途的字段残留 / 提前 return 的半改写态
`mark_candidate_result` (`exact_campaign.py:2039-2146`) 的内存改写顺序值得逐行盯: 它先 `normalized_status` 校验 → 矛盾强状态 raise (`:2065-2073`) → existing-strong 遇 weak 时**追加 audit-log 后 early-return** (`:2074-2090`) → 否则 `record = _candidate_defaults(...)` 然后 `record.update(dict(existing))` (`:2091-2093`) → 改 status/时间戳 → CERTIFIED 写 solution / 非 CERTIFIED `record.pop("solution", None)` (`:2130-2143`) → `candidates[key] = record`。请攻这几个**顺序缝**: ① existing-strong 遇 weak 的 early-return (`:2089-2090`) 只 append audit-log 并设 `updated_at` 就 return, **没碰 record 本身** —— 对吗? 确认它**绝不会**在 return 前已经把 record 改了一半 (例如别处提前 mutate)。② `record = _candidate_defaults()` 再 `record.update(existing)`: 若 existing 是个**带 solution 的旧 CERTIFIED**、incoming 是**另一个 CERTIFIED** (同状态不矛盾、不触发 downgrade-block), 走到 `:2136 record["solution"] = dict(solution)` 用**新** solution 覆盖 —— 但中间 `record.update(dict(existing))` 已经先把**旧 solution** 灌进 record 了, 若某条路径 incoming CERTIFIED 却 (反常地) 没走到 `:2136` 的覆盖, 旧 solution 会不会残留? (incoming CERTIFIED 必带 solution 在 `:2054-2055` 已挡, 但请确认没有别的 CERTIFIED-写-record 路径绕过 `:2136`。) ③ 非 CERTIFIED 分支 `record.pop("solution", None)` (`:2143`): 这一步把继承自 existing 的 solution 清掉 —— 但前提是**走到了**这一步; 弱结果若 existing 是 strong 早在 `:2089` return 了, 那条 return 路径上 record 没被 pop (因为 record 还没建), existing record 的 solution 原样留在盘上。existing 是 CERTIFIED 带 solution 时这是对的 (CERTIFIED record 本就该带 solution); 但请确认**不存在** existing 是某种「strong 但按契约不该带 solution」的态 (如 INFEASIBLE 带残留 solution) 被 early-return 放行而 solution 没被清。**逐字节追 record 在每条 return/fall-through 路径上的 solution 字段终态。**

### M4 [resume 后 attempts/started 单调与候选重复消费] 崩溃在 started 与 result 之间的去重
`mark_candidate_started` (`:2008-2037`) 对 strong record early-return 不动 (`:2012-2020`); 否则 `attempts += 1`、status=RUNNING、清 `last_stop_reason`、`final_status` 条件清空。请攻 resume 一致性的**重复消费 / 漏消费**向: ① 进程在 `mark_candidate_started` 写盘 (RUNNING, attempts=N) 后、`mark_candidate_result` 之前崩溃。resume 后这个候选是 RUNNING 态。outer search 重新 dispatch 它 → 再 `mark_candidate_started` → attempts=N+1。这是**正常重试**还是会**双计 / 漏掉**该候选? 确认 RUNNING 态候选在 resume 后被**恰好重新消费一次**, 既不被当已完成跳过 (漏证 → availability), 也不会因键错位被当**新候选**追加导致 frontier 双计 (这会不会污染终局 potential_domain 判空?)。② `mark_candidate_started` 在 `final_result is None` 时清 `final_status=None` (`:2035-2036`): 若 final_result 已是某个 CERTIFIED (非 None), 这步**不清** —— 即新一轮候选重跑时旧的 terminal CERTIFIED final_result 仍挂着。请确认这不会让「**一个旧终局 CERTIFIED final_result + 一批新 RUNNING 候选**」的混合态在 resume 时被 `_validate_resume_state` 当作合法终局 (terminal evidence 要求 potential_domain 空, 新 RUNNING 候选应当让 frontier 非空 → 应 fail; 但请确认这条 fail 真的拦得住, 而不是 final_result 的存在让某个 short-circuit 跳过了 frontier 非空检查)。

### M5 [resume validation 的字段级容错是否制造洗白窗口] 缺字段/默认填充/类型放宽
`_validate_resume_state` (`:1472-1574`) 是 resume 唯一总闸。请逐项查它的**容错方向**有没有把「不完整/被截断的盘上态」默默补成合法: ① schema_version / proof_summary_schema_version 走 `_strict_resume_int` (`:1479-1499`), 缺/非 int 直接 reason-fail —— 确认无默认填充。② `REQUIRED_STATE_FIELDS.difference(state.keys())` (`:1486-1488`) 只查 key 在不在, **不查值是否被截断成 null** —— 一个 torn-write 让某 required 字段值为 `null` 但 key 在, 会不会绕过 missing 检查后在下游被当默认值? 具体追 `final_result`/`final_status`/`declare_mode`/`artifact_hashes`/`candidates` 任一被截成 null 时, 是落到各自的 `is not None`/`isinstance` 拦截 (`:1501-1521`), 还是有一条 null→默认的滑路。③ `last_stop_reason` 只在 `is not None` 时校验结构 (`:1507-1510`): 一个 stop 中途崩溃留下**半写的 last_stop_reason** (有 reason key 但语义是 time-budget 未清) 会不会被 resume 当作干净续跑而漏掉「上次是非终局 stop」的语义? ④ 候选 record 逐条过 `_validate_candidate_record` (`:1547-1556`) —— 确认一条**字段被截断的 record** (如 CERTIFIED 但 solution 字段 null / status 字段缺) 是 hard-fail 而非补默认。**重点: 找一个『key 齐全但某值被 torn-write 截断』的盘上态, 看 resume 是 fail-closed 还是补默认放行。**

### M6 [audit-log / 时间戳 / updated_at 的非证据性确认] 改写副作用不能反向影响证据判定
`mark_candidate_result` 的 downgrade-block 路径 (`:2074-2090`) 和正常路径都会改 `audit_log` / `updated_at` / 各种时间戳。这些是**遥测不是证据**, 但请确认它们**真的**不参与任何 CERTIFIED 完备性判定, 且它们的改写不会**反向**破坏证据: ① `audit_log` 是 `setdefault("audit_log", [])` 然后 append (`:2078-2088`): 它进不进 artifact hash / terminal evidence digest / `_validate_resume_state` 的任何判定? 若一条被注入的 audit_log entry 能改变 resume 通过性或 digest, 那它就从遥测升格成了证据。确认它纯旁路。② `updated_at`/`finished_at`/`started_at` 时间戳 (`now_iso()`): terminal evidence 完备性判定 (potential_domain 空 + frontier 空 + digest) **完全不读时间戳**对吗? 若某处用 `updated_at` 排序或选 best, 一个被改的时间戳能否换掉 best record? ③ `last_stop_reason` 与 `final_status` 的清空时机 (`mark_candidate_started:2034-2036`、`mark_candidate_result` 不碰 last_stop_reason): 确认「stop_reason 已清但 final 未真终局」或反之的中间态不会被某出口读成「干净的完备终局」。**这块判 sound 的标准是: 所有遥测字段对『是否 CERTIFIED 完备』零影响, 且改写副作用不反噬证据。**

## 明确不要报的 (重复报不算 finding)

- **已修条款 (含本轮新登记的)**: **F78-F-01** (lock:92, 候选 solution 卫生 + 强状态单调) —— 本轮 M3/M4 可把它**钉成攻击面找同型残留/时序缝**, 但不重报条款本身。Accepted invariants: lock:87/88/91 (best certified 跨持久化单调 + final_solution/manifest 同源 + coordinator-only writer 不相交波次)、**F-BIND-R5-01** (lock:103, worker/domain artifact-hash 单快照封印)、**lock:118** (终局证据 closed project-bound 契约)、**lock:119** (deny-unknown `EXACT_*`)。**F-PS-R6-01** (lock:145, precheck-elimination 写前重验完整 INFEASIBLE 契约) 与 **V97/V98** (canonical/symlink campaign path authority) 已登记, 别重报机制本身; 可质询其覆盖边界但要给新路径。
- **r2/r3/r4/r5 已审结论别当新 finding**: 「同 hash 旧坏强 record 无法自证 provenance」属固有信任边界 (人为篡改 checkpoint / 旧 bug 产物) —— 除非你能给出**不依赖人为篡改、纯崩溃时序 + 状态机自身逻辑**就能产生 false-CERTIFIED 的新路径, 否则别报。直接 API misuse 存盘 (save 是 writer 非 validator) 在 resume/export 被 fail-closed, 不算 finding —— 但 M1/M2 若能给出**一个真实崩溃时刻**让坏态恰好通过 resume validation, 那是新 finding。
- **跨面边界 (别误判为本面缝)**: ① **F78-F-02 / F-PS-R4-01 / F-PS-R5-01 worker 身份绑定 + 并行波次合并/discard latch 是 face 8 (parallel scheduler) 单独审, 本轮不审** (lock:93)。② worker 进程内 Benders/cuts/binding/几何 master 正确性属各自面, 本面只假设 worker 返回 status 语义与 sequential 同源。③ M1/M4 若怀疑落到「某个被信任的子问题判定其实是 false-INFEASIBLE/false-CERTIFIED」 —— 那是 routing/binding/cuts/preprocess/master 面的事, 本面状态机会忠实持久化并据此剪枝, 这是**跨面信任不是本面缝**; 交叉引述 PROJECT_LOCK 相应条款指明归属面, 别在本面重证子问题。
- **设计决策 (owner 已定, 别报)**: canonical 口径 / 266 强制设施口径 / `min_side>=6` 是 admissibility 录取门非 tie-break / 全封闭合法空矩形不要求外部连通 (lock:117) / max_lex 目标定义。
- **env-gated 行为不属 P1.2 certified soundness**: `EXACT_USE_POSE_BOOL_MASTER` / `EXACT_POWER_PLACEMENT_SUBPROBLEM` / `EXACT_B1_BYPASS_*` 全 env-gated 且被 `pose_bool_master_not_certified` 等 guard 挡在 certified 公开面外 (lock:132/143/144/149/150), **非默认 certified 路径**, 不在本面 soundness 范围。
- preflight `phase_1_2_spike_close` BLOCKED 是 owner gate (别报); P1.3B `step_8_apply_to_master` 是禁区 (别动别报); exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry **非 proof object** (别当证据缝报)。

## 自验环境与已知基线

- candidate 已随包, 全量应跑得动: `python -m pytest -q src/tests` 期望 **0 failed** (passed ≈3074, 具体数目以实跑为准; **硬不变量 = 0 failed**)。沙盒 pytest-randomly 报 seed 错就加 `-p no:randomly`。跑不完全量就跑 campaign 专项 (`test_exact_campaign*` / `test_v62*` / `test_v63*` / `test_v97*` / `test_v98*` / `test_p0_certified_soundness_fixes*` / `test_exact_campaign_state_soundness*` 等) + 如实声明跑了哪些。
- `python scripts/check_p1_2_proof_obligations.py` 应 pass (**8 obligations**)。
- finding **必须**带可复现 probe (最好是能跑的 .py / pytest) **或** 严谨 file:line 论证; **实证推翻你的怀疑就不要报**。把怀疑写成探针先自我证伪, 证不伪再报。本轮 M1/M5 尤其鼓励**模拟崩溃时序的盘上态构造探针** (手工造一个 torn / half-committed checkpoint JSON, 喂给 `_validate_resume_state` 看是 fail-closed 还是放行)。
- 契约锚点: `PROJECT_LOCK.md:85-119`/`:145` (Accepted Invariants 区, 含 F78-F-01/F-02、F-BIND-R5-01、终局证据 closed 契约、deny-unknown EXACT_*、F-PS-R6-01)。终局证据/状态机契约测试: `test_v62_candidate_frontier_contract.py` / `test_v63_terminal_evidence_contract.py` / `test_v97_canonical_campaign_state_authority.py` / `test_v98_b5a_symlink_campaign_path_authority.py` / `test_exact_campaign_state_soundness.py`。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / 可复现 probe 或严谨论证 / 修法), 有把握附 unified diff + regression 测试 (**LF 行尾**)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附分段判读, 按本轮 M1-M6 六块各给真 Pro 复核结论 (不是复制 r5 的 N1-N6, 要体现你在 M1-M6 这些**落盘/时序/内存改写新角度**上各自查了什么、构造了什么崩溃/截断探针、为什么判 sound)。
- 真 Pro 第三次独立重审, 前两轮 (含 r4/r5 真 Pro) 零 finding **不代表本轮默认干净**; 按你自己的独立判断下结论。

## 严重度纪律

- **false-CERTIFIED on canonical + 默认 env = soundness reset** (P1.2 闭环只认这个 HIGH/critical): 终局把不完备搜索/失真证据/误剪/崩溃坏态当成 CERTIFIED 完备主张通过公开面。这是本轮唯一的 HIGH/critical 类。
- **env-gated / conditional / false-INFEASIBLE / 保守失败 = hardening/availability** (漏真矩形/回退进度/拒绝合法态, 但不谎称完备): 标 **LOW** 加固建议并**明确标注是 env-gated 还是 conditional 还是 availability**, 不是闭环阻断项。
- 区分清楚: 一个缝若只会让搜索**多保留候选 / 回退进度 / 拒绝合法态 / 重跑一个候选** = availability (LOW); 只有会让**不该 CERTIFIED 的态通过公开面**才是 soundness (HIGH)。崩溃时序缝若只导致「重新跑一遍候选」是 availability; 若导致「漏证候选却判终局完备」或「弱结果实际覆盖了强结果而 resume 没拦」才是 soundness。

## 范围边界

重点 = campaign 持久化 / resume 状态机 / 终局证据 soundness 的真 Pro 第三次复核, **本轮专攻持久化原子性 + 崩溃时序 + 内存状态改写顺序 + 提交-校验时序 (M1-M6 新角度)**; **parallel scheduler 合并 (face 8) 与其余面 (master/routing/cuts/preprocess/binding/benders) 不审**, 怀疑跨面时交叉引述 PROJECT_LOCK 契约指明归属面而非在本面重证。
