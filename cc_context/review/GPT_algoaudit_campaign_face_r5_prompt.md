# 终末地 IndustrialPlanner 精确求解器 — campaign/resume 状态机面 round 5 (真 Pro 第二次全面 soundness 重审·换角度往深挖)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_b4041f3e.zip`, sha256 `b4041f3eb065e9756a1dbd21f3e513479dfd504e2024b74fb08a2d235af08893`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD `8c61e1e`)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包**, 已校验, 不准伪造/重生覆盖。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **campaign 持久化 / resume 状态机** (`src/search/exact_campaign.py` 为核, 配 `src/search/certified_frontier.py` 终局证据 + `src/search/outer_search.py` 的 frontier 重建/终局提交)。**并行 scheduler 合并是 face 8 单独审, 本轮不审。**

## 本面定义 + 本轮性质 (关键, 必读)

本面 = **状态机 soundness**, 不重新证明 LBBD 子问题正确性 (那是 master/routing/cuts/preprocess/binding 各面的事)。它把单个候选的 CERTIFIED/INFEASIBLE 判定当作「在同一冻结 artifact hash 下已正确」来信任, 只校验: ① 持久化落盘原子性 + 崩溃时序; ② resume 一致性 (候选不重复消费 / 不丢已证候选 / 陈旧 witness 不穿越状态改写); ③ 终局证据 (full-frontier potential_domain 空 + frontier 空) 不被错误升格成更强主张。

**历史轨迹** (本面此前与 face 8 同包审, 后独立成面):
- r1 = **F78-F-01** (HIGH, false-CERTIFIED: 陈旧 candidate solution 穿越状态改写存活 — 已修, lock:92)。
- r2 = 零 finding (F-01 逐处复核 + 全 writer 清单穷举, thinking 模型)。
- r3 = 零 finding (崩溃时序/原子性矩阵 + 五时刻推演 + 多进程独占, thinking 模型)。
- **r4 = 零 finding (真 Pro 首轮全面重审)**。Q1-Q6 六块逐块判 sound: 终局只回放 best 解 (Q1, 委托子问题信任边界)、CERTIFIED→CERTIFIED 覆盖 (Q2, 重判后 resume/export 被 `terminal_certified_final_result_solution_mismatch` fail-closed)、projection 与活跃 frontier 严格等价 (Q3, 1000 随机 strict-mode 探针零失配)、非终局 CERTIFIED 不几何回放 (Q4, containment/objective 剪枝不能藏更优终局)、双 coordinator 无 lockfile (Q5, atomic write + terminal validate 兜住)、time_budget 续跑清 stop (Q6, 先 validate 后清, 无洗白窗口)。

**本轮 r5 = 真 Pro 第二次独立全面 soundness 重审。姿态铁律:**
- r4 是真 Pro 首轮零 finding, **但前轮 clean 不构成任何先验**。同期真 Pro 一切到其它面屡次抓出 thinking 漏了多轮、甚至自己上一轮漏掉的真 finding (cuts CUT-R12/R13、preprocess R15/R16、几何 master)。请当作从未深审重走。
- **不要复读 r4 的 Q1-Q6 判读路径**。r4 已把那六条主路各跑过一遍探针并判 sound; 本轮要求**换全新角度往更深处挖** —— 攻击 r4 判读里**被当作前提没有自己证**的那些不变量本身 (见下「本轮新攻击面」)。若你重走 Q1-Q6 原路得到同结论, 那只是复制 r4, 没有增量。
- 本轮 attack surface = 本面核心 soundness 不变量在**更细的实现层**是否真成立, 尤其是 r4 信任为「兜底」的那几个 guard (`terminal_certified_final_result_solution_mismatch`、`terminal_certified_frontier_evidence_invalid`、artifact-hash 封印、digest 校验) 是否真的覆盖了它们声称覆盖的全部形态。

注意行号: 下面给的 `file:line` 基于 HEAD `8c61e1e` 包内源码, **以你解包后实读为准**, 函数名稳定 (`compute_terminal_frontier_projection` / `terminal_certified_final_result_violation` / `_validate_resume_state` / `load_or_create` / `mark_candidate_result` / `atomic_write_json` 等); 若行号微漂以函数体为准, 别因行号差一两位就当代码变了。

## 本轮新攻击面 (6 块, 全部是 r4 没有正面深挖、或被 r4 当前提信任的层)

### N1 [终局证据完备性 — projection 用什么 domain 重建?] artifact-hash 封印是否覆盖 projection 的全部输入
`compute_terminal_frontier_projection` (`certified_frontier.py:175-246`) 在 resume/终局时, 用**当前进程重建的 candidate domain** 配 records 推 `potential_domain==[]` 作完备性硬判据。resume 把 records 绑到当前 artifact 靠 exact artifact hash (`exact_campaign.py:1501-1504` 附近)。请深查: **projection 实际枚举/迭代的候选域** (它从哪里拿全量 candidate 列表来判「都被剪了」) 是否与「写入 records 时所处的那个 candidate domain」**逐元素同源**? artifact hash 封印的是 artifact 字节, 但 F-BIND-R5-01 (lock:103) 明示 candidate domain 还依赖 generic_io_requirements snapshot + wireless slot count + 候选定向 (both (w,h) and (h,w))。构造怀疑: 若 resume 进程重建的 domain 比写 records 时**少了某些候选** (例如某个候选键在两次 domain 构造下规范化不同、或某 env/默认值差异使一侧多/少一个定向), 则 `potential_domain` 可能**本来非空却被算成空** → 终局完备性 false-CERTIFIED。请确认 projection 的 domain 来源是否被同一 hash 封印强制等同, 还是存在「records 在 domain A 下产生、projection 在 domain B 下判完备」的缝。**这是 r4 Q3 只对比了 projection vs 活跃 frontier 的剪枝规则, 但没问『两侧枚举的候选全集是否同一个』。**

### N2 [digest 兜底是否真兜] `terminal_frontier_candidate_status_digest` / best_candidate 校验的实际绑定强度
r4 在 Q5 论证「stale 第二 coordinator 写出 final_status=CERTIFIED 但 best record 已非 CERTIFIED 的自相矛盾态会被 terminal validation 拒」, 兜底之一是 digest/best_candidate 校验。请**独立验证这个 digest 实际算了什么、校验时比的是什么**: 它是否真的对「参与终局判定的每条 record 的 (candidate_key, status)」做了不可绕过的指纹, 还是只覆盖了 best_candidate 一条 / 只覆盖了 status 集合的某个摘要而漏了某类 record? 具体追: ① digest 计算函数遍历的 record 集合, 与 projection 实际消费的 record 集合是否一致 (有没有 record 进了 projection 但没进 digest, 反之亦然); ② digest 对 `INFEASIBLE` record 的覆盖 —— 一条被悄悄翻成 UNKNOWN/删除的 INFEASIBLE record 会改变 projection 的剪枝结果, digest 是否能侦测? ③ digest 比对在 resume 路径上是 hard-fail 还是 warn。若 digest 漏覆盖某类参与剪枝的 record, 则「record 集合被改写但 digest 不变」→ 终局证据通过校验但实际已失真。

### N3 [record 键规范化 / 定向去重] candidate_key 与 (w,h)/(h,w) 双定向在 record 与 projection 间是否一致
项目 candidate domain 现已**全定向** (both (w,h) and (h,w))。`candidate_objective` (`certified_frontier.py:163`) 与 projection 的 containment 剪枝 (`:210-216`) 用 `ghost_w <= cert_w and ghost_h <= cert_h` 这类**有序**比较。请查: ① 一个 CERTIFIED record 以 (w,h) 落盘, 其旋转伴 (h,w) 是否被视作**同一候选还是不同候选**? 若 projection 把 (h,w) 当独立候选但该候选实际已被 (w,h) 的证书覆盖 (或反之), 会不会 (a) 漏剪 → potential_domain 非空但其实已被覆盖 (保守, availability), 或 (b) **误剪** → 用一个 (w,h) 的 CERTIFIED 去 containment-prune 掉一个几何上并不被它包含的 (h,w) 候选 (soundness)。② `record` 字典的 key 规范化 (mark_candidate_result 用 `(ghost_w, ghost_h)` 还是规范化键存) 与 projection 枚举键是否同一规范, 错位会让一条 record「在 projection 里查不到」从而被当未证候选 (保守) 或一条 record 被双计。重点判 **containment 剪枝方向 + 定向语义**有没有 soundness 向的误剪。

### N4 [objective 比较 + min_side admissibility 在 projection 边界] `<=` 剪枝与 max_lex 的实现一致性
projection best 剪枝用 `candidate_objective(candidate) <= candidate_objective(best_certified_candidate)` (`certified_frontier.py:216-219`), 活跃用 `_is_objectively_worse_or_equal` (`outer_search.py:468`)。r4 Q3 已比对二者「同序」, 但**没有逐字节比对两个比较函数的实现细节**。请查: ① `candidate_objective` 返回的 tuple 是 `(area, min_side)` 还是 `(area, ...)`, 与活跃侧 `_is_objectively_worse_or_equal` 的比较元组**完全同构**吗 (元组元素顺序/正负号/是否含 min_side)? 一处比 area-then-min_side, 另一处只比 area, 会让两侧剪掉不同候选集 → 终局 evidence 通过但活跃漏候选 (false-CERTIFIED 完备性)。② `min_side >= 6` admissibility 是 owner 已定的**录取门**不是 tie-break —— 确认 projection/活跃两侧对 sub-admissible 候选 (min_side<6) 的处理一致 (都不进 explicit_certified、都按规则处理), 且 best 剪枝不会因把 admissibility 误当 objective 维度而误剪。**注意**: 别报「min_side>=6 是 admissibility 非 tie-break」这个设计本身 (owner 已定), 只报两侧**实现不一致**。

### N5 [rerun preamble 的强状态单调真值] mark_candidate_started 降级守卫 + 弱结果覆盖守卫的完备性
lock:92 (F78-F-01) 要求强状态 (CERTIFIED/INFEASIBLE) 在同 artifact hash 下单调: rerun preamble 不得降级为 RUNNING, 弱结果不得覆盖强结果, 矛盾强状态 loud-fail。r4 Q2 只验了 CERTIFIED→CERTIFIED 覆盖路径。请深查**降级方向**与**弱覆盖方向**: ① `mark_candidate_started` (`exact_campaign.py:2008` 附近) 对已是 CERTIFIED/INFEASIBLE 的 record 是否**所有进入路径**都 early-return 不改状态 (含 resume 后 records 与 live domain 不一致、同一候选键被不同定向重新 dispatch 的情形)? ② `mark_candidate_result` (`:2039`) 写弱结果 (UNKNOWN/UNPROVEN/RUNNING) 时, 若 existing 是强状态, 是否**确实**走 audited-block 拒绝, 还是有某条 status 取值绕过了那个 if 链 (例如大小写、别名、None、空串)? ③ 矛盾强状态 (CERTIFIED↔INFEASIBLE) 的 loud-fail 是否对**两个方向**都成立。任一守卫有缝 → 一条真 CERTIFIED 被悄悄降级/覆盖, 或一条 false 强状态混入 records 参与终局剪枝。

### N6 [evidence schema 版本迁移 / 非权威域值] 终局证据的 schema-version 与 domain 权威性 fail-closed 是否真闭
lock:118 要求终局证据是 closed project-bound 契约: unknown `candidate_generation` keys、non-authoritative domain values、stale evidence schema versions、sub-admissible terminal best 都必须在任何 public CERTIFIED 面之前 fail-closed。请查 `certified_frontier.py` 里 evidence 的**消费侧校验** (`:278-381` 一带的 `potential_domain_size` / digest / schema 比对): ① 一份**旧 schema 版本**的 terminal evidence 在 resume 时是被 hard-reject 还是被静默接受/部分迁移? 若存在「旧版 evidence 缺某字段 → 该字段按默认值填 → 校验通过」的路径, 就是 stale-evidence 洗白。② `candidate_generation` / domain 权威值校验是 deny-unknown 还是 allow-unknown: 一个未知/被改的 domain 描述字段能否让 evidence 仍判完备? ③ 这些 fail-closed 检查是在「写 public CERTIFIED 面之前」就拦, 还是只在某条主路上拦、另有旁路 (best_certified_result/manifest export) 绕过。重点是**契约声称 fail-closed 的四类**在实现里是否真的每条公开面入口都拦。

## 明确不要报的 (重复报不算 finding)

- **已修条款**: **F78-F-01** (lock:92, 候选 solution 卫生 + 强状态单调) —— 本轮可把它**钉成攻击面找同型残留/反向缺陷** (见 N5), 但不重报条款本身。Accepted invariants (lock:87/88/91, best certified 跨持久化单调 + final_solution/manifest 同源 + coordinator-only writer 不相交波次)。**F-BIND-R5-01** (lock:103, worker/domain artifact-hash 单快照封印) —— N1 可质询其覆盖范围, 但不重报封印机制本身。
- **r2/r3/r4 已审结论别当新 finding**: 「同 hash 旧坏强 record 无法自证 provenance」属固有限制 (人为篡改 checkpoint / 旧 bug 产物) —— 这是 accepted 信任边界, 除非你能给出**不依赖人为篡改、纯状态机自身逻辑**就能产生 false-CERTIFIED 的新路径, 否则别报。直接 API misuse 存盘 (save 是 writer 非 validator) 在 resume/export 被 fail-closed, 不算 finding。
- **跨面边界 (别误判为本面缝)**: ① **F78-F-02 / F-PS-R4-01 / F-PS-R5-01 worker 身份绑定 + 并行波次合并/discard latch 是 face 8 (parallel scheduler) 单独审, 本轮不审** (lock:93); 本面只验状态机/持久化/resume/终局证据, 不验 scheduler 的 worker 结果合并与 discard 逻辑。② worker 进程内 Benders/cuts/binding/几何 master 正确性属各自面, 本面只假设 worker 返回 status 语义与 sequential 同源。③ **N1/N5 若怀疑落到「某个被信任的子问题判定其实是 false-INFEASIBLE/false-CERTIFIED」** —— 那是 routing/binding/cuts/preprocess/master 面的事, 本面状态机会忠实持久化并据此剪枝, 这是**跨面信任不是本面缝**; 交叉引述 PROJECT_LOCK 相应条款指明归属面, 别在本面重证子问题。
- **设计决策 (owner 已定, 别报)**: canonical 口径 / 266 强制设施口径 / `min_side>=6` 是 admissibility 录取门非 tie-break / 全封闭合法空矩形不要求外部连通 (lock:117) / max_lex 目标定义。
- preflight `phase_1_2_spike_close` BLOCKED 是 owner gate (别报); P1.3B `step_8_apply_to_master` 是禁区 (别动别报); exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry **非 proof object** (别当证据缝报)。

## 自验环境与已知基线

- candidate 已随包, 全量应跑得动: `python -m pytest -q src/tests` 期望 **0 failed** (passed ≈3058, 具体数目以实跑为准; **硬不变量 = 0 failed**)。沙盒 pytest-randomly 报 seed 错就加 `-p no:randomly`。跑不完全量就跑 campaign 专项 (`test_exact_campaign*` / `test_v62*` / `test_v63*` / `test_v97*` / `test_v98*` / `test_p0_certified_soundness_fixes*` 等) + 如实声明跑了哪些。
- `python scripts/check_p1_2_proof_obligations.py` 应 pass (**8 obligations**)。
- finding **必须**带可复现 probe (最好是能跑的 .py / pytest) **或** 严谨 file:line 论证; **实证推翻你的怀疑就不要报**。把怀疑写成探针先自我证伪, 证不伪再报。
- 契约锚点: `PROJECT_LOCK.md:85-119` (Accepted Invariants 区, 含 F78-F-01/F-02、F-BIND-R5-01、终局证据 closed 契约、deny-unknown EXACT_*)。终局证据契约测试: `test_v62_candidate_frontier_contract.py` / `test_v63_terminal_evidence_contract.py` / `test_v97_canonical_campaign_state_authority.py` / `test_v98_b5a_symlink_campaign_path_authority.py`。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / 可复现 probe 或严谨论证 / 修法), 有把握附 unified diff + regression 测试 (**LF 行尾**)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附分段判读, 按本轮 N1-N6 六块各给真 Pro 复核结论 (不是复制 r4 的 Q1-Q6, 要体现你在 N1-N6 这些**新角度**上各自查了什么、为什么判 sound)。
- 真 Pro 第二次独立重审, 前轮 (含 r4 真 Pro) 零 finding **不代表本轮默认干净**; 按你自己的独立判断下结论。

## 严重度纪律

- **false-CERTIFIED = soundness** (P1.2 闭环只认这个): 终局把不完备搜索/失真证据/误剪当成 CERTIFIED 完备主张。这是本轮唯一的 HIGH/critical 类。
- **false-INFEASIBLE / 保守失败 = availability** (漏真矩形但不谎称完备): 标 **LOW** 加固建议, 不是闭环阻断项。
- 区分清楚: 一个缝若只会让搜索**多保留候选 / 回退进度 / 拒绝合法态** = availability (LOW); 只有会让**不该 CERTIFIED 的态通过公开面**才是 soundness。

## 范围边界

重点 = campaign 持久化 / resume 状态机 / 终局证据 soundness 的真 Pro 第二次复核 (N1-N6 新角度); **parallel scheduler 合并 (face 8) 与其余面 (master/routing/cuts/preprocess/binding/benders) 不审**, 怀疑跨面时交叉引述 PROJECT_LOCK 契约指明归属面而非在本面重证。
