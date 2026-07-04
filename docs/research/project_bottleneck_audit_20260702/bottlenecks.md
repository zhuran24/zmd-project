## [critical] votes=4 | 算力硬墙：求解器从未在全尺度产出过一次 FEASIBLE，terminal full-frontier（约 4225 个 oriented 候选全部终局）物理上不可达——第一多米诺
lenses: chain, compute
evidence: docs/lever_verdicts.md:9（baseline 8 workers/1800s 跑 14h、51-78 候选 0 FEASIBLE）；:117-189（把用户手调正确答案整套 798 AddHint 喂给 27×15 候选，3600s×8 P-core 满载仍 UNKNOWN，三种配置矩阵全 UNKNOWN）；:209-231（2464 anchor 分片每片仍 UNKNOWN、5.5M branches、锁 anchor 后仍剩 3,853,132 个 mandatory pose literal，完整 partition 估 205h/候选，判『物理不可行』）；:5（27 条加速 lever 全部实测否决）；:348-364（真瓶颈=master 内 power_coverage/port/boundary 耦合：skip_power_coverage 后 65.9s 完成 vs 完整 master 30min UNKNOWN，src/models/exact_coordinate_master.py:3448-3452 默认仍加该约束）；src/search/certified_frontier.py:82-83（候选域 w,h∈[6,70] 不做规范化=4225 个候选全要终局）；交付副本 data/ 下无任何 checkpoints/telemetry 长跑证据（实测）
why: 最终目标不是找一个好布局，而是证明『所有 lex 更优候选全部 INFEASIBLE』——INFEASIBLE 证明比 FEASIBLE 更贵（timeout 只得 UNKNOWN）。现状是拿着正确答案都验证不完一个候选，而完整证明要成百上千个候选逐个穷尽；且 UNKNOWN=terminal stop 使 campaign 结构性无法推进（解不动→UNKNOWN→短命退出→watchdog 重启→撞同一个 UNKNOWN）。这是唯一没有已知工程路径的环节：其他缺口都是『排期未做』，这个是『做了 27 次都失败』。链上后面的 seal、publish、手动门再完美也没有东西可 seal——所有排期决策应先过这一关，否则后续工程都是给一个解不出的问题修发布管道。
fix: 三选一且都需 owner 拍板：① 把 F1-F9 cut 体系真正接入生产 master（见下条）并实测收敛；② 命题降级走 L11（钉死 blueprint 只解剩 41 个，lever_verdicts.md:193-203，等于改 theorem scope）；③ 换算力/求解范式（重构 power_coverage/port 编码、拆出可证明可 replay 的子问题链）。在单候选能稳定终局前不应扩大 168h campaign。
VERDICT: CONFIRMED | severity_opinion: critical
verify notes: 逐条核对结果（全部只读实测）：

【坐实的证据】
1. docs/lever_verdicts.md:9 — 原文即"baseline (workers=8, master_seconds=1800…) 14h 跑 51-78 candidates, 0 FEASIBLE. 全部 UNKNOWN 或 INFEASIBLE"。坐实。
2. lever_verdicts.md:115-127（L7）— 798 AddHint（266×3，telemetry 验证"一次不多一次不少"，:115），27×15 是"blueprint natural max empty rect 完美匹配"仍 UNKNOWN（:124）；:162-189（L10）— trial7 master_seconds=3600 + workers=8 满载（758% CPU）仍 UNKNOWN（:169-179），27×15 配置矩阵全 UNKNOWN（:181-188）。断言引 :117-189 基本准确；小出入：矩阵表列 3 个 trial（文件自称"4 种配置"，trial6 错配被停）。
3. lever_verdicts.md:207-237（L12）— 2464 anchor（:209）、单 anchor 5min UNKNOWN、5.5M branches、8 亿 propagation（:221）、锁 anchor 后仍 3,853,132 mandatory pose literal（:223）、完整 partition 5min×2464=205 小时"物理不可行"（:229-231）。全部坐实。
4. lever_verdicts.md:5 — "死路总计已到 27 条"（本文件 16 条 + 后续 ~11 条范式）。坐实；注意 L6（搁置）、L11（未试）不计入 27 条死路,与"27 条全部实测否决"口径一致。
5. lever_verdicts.md:340-366（L15，断言引 :348-364 略偏）— "真瓶颈: master 多余的 port_binding / power_coverage / boundary_port_feasibility / exact_safe_cuts"（:360），"skip_power_coverage=True 后 master.solve 65.9s 完整 2 LBBD iter (vs 30 min UNKNOWN)"（:364）。坐实。src/models/exact_coordinate_master.py:3446-3452 实测确认：build() 中 `not self.owner.skip_power_coverage and not delegate and not lazy_completion` 才跳过，否则调 _add_geometric_power_coverage_constraints()；skip_power_coverage 默认 False（src/models/master_model.py:2330），lazy completion 是 env 门控默认关 → 默认 certified 路径确实仍加该约束。坐实。
6. src/search/certified_frontier.py:78-83 — 注释明确"Do not canonicalize by h <= w…or a certified full-frontier proof can miss a feasible vertical rectangle"，双层循环 w,h ∈ [min_side=6, 70] → 65×65=4225 oriented 候选。坐实。
7. 交付副本 data/ 下无长跑证据 — 实测 data/ 只有 examples/exports/hints/preprocessed/proof_obligations/review_gates/solutions，无 checkpoints 目录（Test-Path False），es 在 data/ 下搜 checkpoint/telemetry/campaign 零命中。坐实。
8. "UNKNOWN=terminal stop 结构性停滞" — src/search/outer_search.py:1702-1717：_terminal_stop_reason_for_status 对 UNKNOWN 默认返回 "candidate_returned_unknown"（env 门 EXACT_OUTER_SKIP_UNKNOWN 默认关，且代码注释自述开了会"违反 max_lex 严格性"）；outer_search.py:687-689：frontier 默认不跳过 UNKNOWN 候选 → 重启后重选同一候选。代码注释（:1705-1708）自己就描述了"main 退出后 watchdog 重启"循环。坐实。
9. 修复方向的事实前提：L11 在 lever_verdicts.md:193-203（钉死 blueprint 只解剩 41 个，"当前唯一几乎保证出 FEASIBLE"）坐实；F1-F9 未接生产 — src/cuts/lifecycle.py:1121-1126 step_8_apply_to_master 确实 raise NotImplementedError。坐实。

【两处需限定的出入（不动摇结论）】
a. "4225 个候选全部终局"字面偏严：certified_frontier.py:207-226 与 outer_search.py:699-710 有 derived dominance 剪枝（显式 INFEASIBLE 剪所有 ⊇ 超集、CERTIFIED 剪 lex 更差候选），terminal exhaustion 不要求 4225 个逐一显式解，只需 frontier 阶梯 antichain 上有限个显式终局。但剪枝的前提是先产出显式 INFEASIBLE/CERTIFIED——现状大候选全 UNKNOWN、0 FEASIBLE，剪枝无源可剪，实质结论不变。
b. "从未产出过一次 FEASIBLE"需限定为"端到端 certified 链"：B1 pose-bool master（env 门控、非默认路径）单 master 层已实测 53s OPTIMAL（lever_verdicts.md:529-535，Phase 2 trial 里 PortBindingModel 也曾 FEASIBLE 0.1s），但端到端 certified FEASIBLE/INFEASIBLE 确实从未拿到（:471"端到端 certified FEASIBLE 没拿到"、:589"certified FEASIBLE/INFEASIBLE 未拿到"，B1 死于 cut 收敛而非 master 层）。断言在"全尺度"意义上成立，但"物理硬墙"对 master 单层已被 B1 打出跨数量级突破，墙真正卡的位置已移到 LBBD cut 收敛。

【严重度独立评估】维持 critical 合理：最终目标 = 端到端 certified 发布 + 关手动门，而实测拿着正确答案 hint 都无法让一个候选终局（4 配置全 UNKNOWN），27 条 lever 全实测死，UNKNOWN 默认 terminal stop 使 campaign 结构性原地打转，dominance 剪枝也因产不出终局状态而无从触发。其他缺口（supervisor 通电、手动门）是排期问题，此项是能力问题且无已知工程路径——"第一多米诺"定位准确，未见夸大；也不算低估（B1 已证 master 层可破，问题不是绝对物理不可解，而是当前范式下证明链闭合不了）。

## [critical] votes=4 | main 的 durable seal 路径上，frontier 穷尽/canonical 域/最优候选三项核心校验被静默跳过——修复与 1.5 万行 round-19 硬化全在未合入、无备份的本地分支 pr2-5 上
lenses: chain, soundness
evidence: main 上 src/search/pr2_l0_true_verifier_child.py:429-440 的 L0 child 升格时只设 final_status='CERTIFIED'，不补 declare_mode='strict' 和 last_stop_reason.status='CERTIFIED'；而 exact_campaign.py:2582-2611 的 terminal_certified_final_result_violation 在该证据谓词为 false 时直接 return None——诚实提案的 last_stop_reason 必然是 CANDIDATE_PROPOSED，所以穷尽/切片域/best-key 校验（certified_frontier.py:439-513）在 main 的铸造时刻是死代码：切片域（抬 min_side、加 start_area）或未穷尽 frontier 的提案能被盖上持久 CERTIFIED 章。git diff main...pr2-5-domain-frontier-gate 实测：child +24 行补齐该修复，commit 5ff31ac 注释自认 'a producer could otherwise seal a sliced domain or a non-exhausted frontier'；该分支领先 main 26 commit、+15266/-189 行（含 checker 从 4442 行到 12859 行的 round-19 Group A/B/C 结构硬化），git remote -v 为空、无 bundle、单机单副本。
why: 最终目标的定理主体就是 lex 最优性=全域候选穷尽证明，这道校验在 main 上被 producer 可控字段静默关闭，是分支作者自己坐实的真 soundness 洞。它比『入口没接』更前置：若在当前 main 上先补 PR2#7 通电，等于把会跳过穷尽校验的 seal path 接上生产链，在坏地基上铸 CERTIFIED。同时 main 的结构门也比 pr2-5 弱（第 12 轮外审挖出的父锚/witness 覆盖洞在 main 未补），而合入时点绑在外审收敛上、外审有三次收敛证伪前科，且 26 个 commit 的对抗硬化成果单机故障即全丢。
fix: 立即做零风险 git bundle/异地备份（不需任何审批）；把 pr2-5 的 declare_mode/last_stop_reason 最小修复（至少 runtime 三文件）合入 release 目标基线并补『sliced domain/未穷尽 frontier 不能被 seal』的红绿测试；合入后基于合并树重走完整 freeze-ritual/reseal（不能复用旧 hash）并手动跑 --full + --slow-tests（CI 惰性不会替跑）。合入前任何基于 main 的 seal 结果都不能当可信 CERTIFIED。
VERDICT: PARTLY | severity_opinion: major
verify notes: 【核心机制——全部坐实】(1) main 的 L0 child 升格时只设 final_status='CERTIFIED'：src/search/pr2_l0_true_verifier_child.py:429-434 的 scratch_state 只补 final_result/final_status/evidence/candidates，全文件零处出现 declare_mode 或 last_stop_reason（grep 无匹配）。(2) 门控早退坐实：exact_campaign.py:2610-2611，terminal_certified_final_result_violation 在 has_terminal_full_frontier_certified_evidence(state) 为 False 时直接 return None；该谓词（2585-2597）要求 declare_mode=='strict' 且 last_stop_reason.status=='CERTIFIED' 且 reason=='search_exhausted_all_candidates'。(3) 诚实提案必然过不了该谓词：mark_campaign_stopped 对 status='CERTIFIED' 直接 raise（exact_campaign.py:3609-3610），提案停机记录只能是 CANDIDATE_PROPOSED（3620-3623），故 child 的 scratch_state 在铸造时刻门控为 False。(4) 被跳过的正是穷尽/canonical 域/best-key 三项：certified_frontier.py:439-447（start_area/aspect/min_side 切片域拒绝）、504-509（best-key 一致）、510-513（potential_domain/frontier 穷尽），它们只经 terminal_frontier_evidence_violation ← terminal_certified_final_result_violation:2692-2701 这条被门控的链可达。child 调的 precheck（exact_campaign.py:2714-2761）里其余项（_validate_terminal_solution_against_project、ghost-pick 绑定）不受门控、仍在铸造时执行——即 6 谓词布局校验没死，死的仅是 frontier/最优性块，与断言表述一致。(5) 分支修复坐实：git diff main...pr2-5 对 child 为 +24 行（设 declare_mode='strict' + last_stop_reason CERTIFIED），注释原句 "(a producer could otherwise seal a sliced domain or a non-exhausted frontier)" 逐字存在。(6) 分支数据全对：26 commits、14 files、+15266/-189；checker scripts/check_p1_2_proof_obligations.py 4442 行(main)→12859 行(分支)；git remote -v 为空。
【出入一：引文归属错】该自认注释在分支首个 commit 22ea475（"close-kernel child 升格补全 declare_mode+last_stop_reason"），不在 5ff31ac（5ff31ac 是 round-19 三块结构门 + reseal，其 message 无此句）。
【出入二："无 bundle、单机单副本"夸大】实测 C:\claude pj\zmd-pj-old 是完整 git 仓库，含 pr2-5-domain-frontier-gate 分支（tip 9bbb3a6 = round-18），其 child 修复文件与当前分支字节一致（blob da32645 相同）；即 26 个 commit 里前 25 个（含核心 soundness 修复）在本机另有一份独立 object store 副本，仅 round-19（5ff31ac，checker 12235→12859 + reseal）为当前仓库独有。另有 C:\Users\22957\pr2_5_review_patches\ 下 ~112KB 补丁文件、以及共享 object store 的 worktree C:\claude pj\zmd-pj-round19。但所有副本都在同一台机器 C: 盘——"单机故障即全丢"对 round-19 成立、对整体成立（同盘不算异地备份），"单副本"不成立。
【严重度复核——两个被断言略去的缓冲层】(a) 洞只在铸造时刻：parent 侧 durable mint（pr2_l0_micro_verifier_core.py:294-307）写入的持久状态带 last_stop_reason CERTIFIED（:297-301）且继承默认 declare_mode='strict'（exact_campaign.py:2109），门控在下游为真——所有公开读取路径（delivery_manifest.py:819-829 → has_valid_terminal_full_frontier_certified_evidence_for_project exact_campaign.py:2887-2906 → :2805 precheck）都会对封印后状态完整重跑 frontier 穷尽/切片域/best-key 校验并 fail-closed。即：切片域提案在 main 上确实能拿到持久 CERTIFIED 章（铸造不健全，坐实），但该章过不了发布面（evaluate_certified_delivery_surface / best_certified_result 返回 None / 不可 publishable），到不了最终目标定义的"公开发布"。(b) seal 在 main 上本无生产入口（PR2#7 缺口，仅 23 处测试调用），当下没有任何生产跑会触发这个坏铸造。真实代价是：设计上的"隔离验证时刻 = 定理权威"被破坏（隔离 child 不查最优性/穷尽，这项校验退到进程内下游验证器），且若按断言警告的那样先在未修的 main 上通电 PR2#7，会得到"持久章不可信、靠下游兜底"的坏地基——这个前置性论点成立。综合：机制真、修复真、单机风险真（round-19 确无第二副本），但"critical"依赖"坏 CERTIFIED 能走到底"的隐含叙事，而下游多层 fail-closed 重验证 + 生产未通电两个事实把即时可利用性明显降级，故我评 major：合入前必须修（尤其通电前），但当前不构成可达最终目标面的活体 soundness 缺口。

## [critical] votes=4 | PR2 #7 通电缺口：proposal→seal 物理断路，全仓无任何生产入口调用 supervisor_seal()，且真隔离 seal→publish 链从未被任何不打桩的自动化端到端跑通
lenses: chain, process, soundness
evidence: main.py:67-88 只调 run_outer_search；outer_search.py:876/:899-954 终态硬编码 CANDIDATE_PROPOSED 并写 proposal_ready marker 后结束；grep 实测 .supervisor_seal( 的非测试调用为零（23 处全在 src/tests/）；PROJECT_LOCK.md:150-154 明文『当前仓库尚无该入口』；反绕过守卫是硬的（exact_campaign.py:3601-3610 mark_campaign_stopped(CERTIFIED) 直接 raise），不能顺手绕。测试侧：test_exact_contract.py:924-964 的 seal/publish 端到端测试用 _install_accepting_supervisor_seal_replay 桩掉真子进程验证器、并把三个模块的 terminal 证据校验 monkeypatch 成 accepting 桩——恰好就是上一条被 gated off 的那个函数；preflight CI 快门只跑约 10 个 CORE 测试目标且无条件 -m 'not slow'（scripts/preflight_gate.py:379-394,:679），真子进程对抗测试不在必跑集。
why: 即使求解跑完全 frontier，产物也只是磁盘上的 proposal marker——没有任何受支持命令能把它变成 durable CERTIFIED，这是刻意排在最后的『通电』缺口。更危险的是：能抓住 seal 缺口的校验在测试里被桩替换、真链测试 CI 又不跑，70×70 真实规模的 CERTIFIED 从未被任何测试产出过——将来 #7 通电时，第一次真链运行同时也是它的第一次集成测试。
fix: 按 PROJECT_LOCK.md:154 与 p1_2_supervisor_detailed_design.md 建独立生产 certify 入口（从磁盘 proposal-ready marker/checkpoint 驱动，seal 成功后再调唯一 publisher）；通电前先补至少一条不打桩的 toy 全真链端到端（真隔离子进程 seal→publish）并纳入必跑 lane；注意新 caller 会撞结构门（发布器调用点被 checker 钉死为恰 2 个），须同步改登记并走完整 reseal 连锁。
VERDICT: PARTLY | severity_opinion: critical
verify notes: 逐条核实（全部只读，file:line 为实测）：

【坐实的前提】
1. main.py:67-88 —— run_solve 确实只 import 并调用 run_outer_search，无任何 seal/publish 调用。✓
2. outer_search.py:876 终态 result 硬编码 `"search_status": CANDIDATE_PROPOSED_STATUS`；:899-902 与 :949-952 两次 `mark_campaign_stopped(..., status=CANDIDATE_PROPOSED_STATUS)`，:954 `write_proposal_ready_marker(...)` 后结束。✓
3. `.supervisor_seal(` 非测试调用为零：全仓 grep 实测代码调用共 23 处、全部在 src/tests/（test_p1_2_supervisor_pr1.py 16 处 + test_exact_contract.py:974 + test_parallel_scheduler.py:244 + test_v86…:265 + test_p1_2_open_gate_publish_block.py:205 + test_p1_2_fixed_witness_terminal_verifier.py:373 + test_p1_2_fixed_witness_capsule.py:285,343）；其余命中全是文档。CodeGraph 复核 run_l0_supervisor_seal 的生产 caller 只有 exact_campaign.py:3566 的 supervisor_seal 本身。✓（23 这个数精确吻合）
4. PROJECT_LOCK.md:154 原文"当前仓库尚无该入口，普通 main.py 完成不能被记成 seal 成功"；:130-131、:141-143 同义重申。✓（断言引 150-154，实际关键句在 154，範围吻合）
5. 反绕过守卫是硬的：exact_campaign.py:3608-3610 `mark_campaign_stopped(status="CERTIFIED")` 直接 raise "CERTIFIED campaign stop must be minted by supervisor_seal"；save() 侧 :3658-3661 检测 unsupervised CERTIFIED claim 并 raise。✓
6. test_exact_contract.py:924-964 `_install_accepting_supervisor_seal_replay` 确实调 install_accepting_l0_supervisor_seal 桩掉 L0 真子进程入口，并把 exact_campaign / delivery_manifest / certified_surface 三个模块的 `has_valid_terminal_full_frontier_certified_evidence_for_project` monkeypatch 成 accepting 桩（:955-964）；随后 :967-979 seal、:982-997 publish 全程建立在桩上。✓
7. preflight CI 快门：scripts/preflight_gate.py:379-394 CORE_TEST_FILES 恰 10 个条目、不含 test_p1_2_supervisor_pr1.py / test_pr2_l0_micro_verifier_core.py / test_p1_2_fixed_witness_capsule.py；:679 无条件 `cmd += ["-m", "not slow"]`；:808-813 `--ci` 走 check_tests(full=False) 即仅 CORE。CI 实际只有 `--ci`（project_foundation.yml:56）+ `--slow-tests`（:91），而 src/tests/conftest.py 的 _SLOW_TEST_NODEIDS 中无任何 supervisor/pr2/seal 条目 → 真子进程 seal 测试确实不在任何 CI 必跑 lane，只在本地 `--full` 或手动全量 pytest 跑到。✓

【与断言的出入（导致 PARTLY）】
"真隔离 seal→publish 链从未被任何不打桩的自动化端到端跑通"这半句被夸大：
- test_p1_2_supervisor_pr1.py 存在**不打桩的真子进程 seal 成功路径**：test_candidate_proposed_resume_is_nonterminal_until_supervisor_seal（:323-357，seal 在 :349）与 test_supervisor_seal_accepts_true_fixed_witness_replay…（:403-446，seal 在 :439）先用 `_run_toy_candidate_proposal`（:90-114）真跑 run_outer_search 产出 toy proposal，再调 supervisor_seal() 且**未桩 run_l0_supervisor_seal**——真隔离子进程 L0→true verifier 实跑并断言 final_status==CERTIFIED。唯一的 autouse patch（:77-87）只是把 dependency floor manifest 重钉到当前 host（宿主兼容性重钉常量，非校验逻辑桩）。
- test_p1_2_fixed_witness_capsule.py:252-301/:304-359 的对抗测试还实跑真子进程 round trip（counted_round_trip 包住原函数并断言 child_round_trips==1，:288/:346），证明 parent 侧 monkeypatch 伪造无法穿透隔离子进程。
- 但断言的另一半仍成立：**没有任何自动化把不打桩的 seal 接到 publish_verified_certified_delivery_surface**——publish 的测试 caller（test_exact_contract、test_p1_2_open_gate_publish_block、test_exact_campaign_inspector）全部建立在 accepting/forged 桩之上（CodeGraph caller 清单逐一核过）。且这些不打桩 seal 测试确实不在 CI 必跑 lane；70×70 真实规模从未被 seal 过也成立。
- 因此"第一次真链运行 = 第一次集成测试"的加重叙述应弱化为："producer→seal 真链在 toy 规模已有不打桩测试（仅本地 full lane），seal→publish 组合真链与真实规模确实从未跑通"。

【严重度独立评估】
维持 critical：以给定最终目标（端到端产出并公开发布 durable CERTIFIED + 合法关 P1.2 门）衡量，这是物理断路——受支持命令全部止于 proposal marker，且 PROJECT_LOCK.md:154 把"supervisor 可执行入口"明列为 P1.2 close 的机器可查条件之一，缺口本身无争议（刻意的 PR2 #7 '最后通电'）。修复方向中"新 caller 会撞发布器调用点结构门"未逐条核验 checker 钉数，但 seal→publish 单入口约束在 PROJECT_LOCK.md:158-163 有据。风险面比断言描述略小（seal 半段已有真子进程覆盖），但不改变"最大瓶颈"定性。

## [critical] votes=3 | P1.2 owner 手动发布门 fail-closed：放行形态在 gate 文件里根本不存在，clean-review 计数刻意存仓库外不可见，机器绿灯不能替代 owner 关门
lenses: chain, process
evidence: src/search/certified_surface.py:497-546（唯一放行形态=status=='closed_manual_owner_decision' 且 next_phase_entry.allowed 且 owner_manual_decision.p1_3b_entry_allowed 三者同真，任何异常视为 open）；publisher 在 :802-808/:833-839 两次遇 gate open 即 raise；data/review_gates/phase_1_2_spike_close.json:5 当前 status='blocked_manual_review_count'、:24-36 not_closed/allowed=false/authority=owner_manual_decision_only、:30 明写『repo 刻意不记录不推导 0/3...3/3，owner keeps the count』；PROJECT_LOCK.md:179-185 禁止从 receipt/checker 绿/internal seal 自动推导关闭。
why: 这是链条终点的合法性闸门：即便通电、seal 成功，公开发布仍被这道门独立拦死。解锁条件（连续 3 次 clean full review）的计数存放在仓库外，交付副本上完全无法评估进度是 0/3 还是 2/3。它是设计如此而非 bug，但意味着最终目标的最后一步不在任何工程动作的可达范围内，只在 owner 手里。
fix: 工程侧只能持续收窄打断 clean streak 的五类 finding 暴露面（推进 PR2 剩余项+外审轮次）；关门动作必须由 owner 仓库外数满 3 clean 后对当时工作树 fresh reseal 并亲手改写 gate JSON 为 closed 形态；可把 owner 最终决定做成仓库内可审计、不可机器生成的 signed decision/manifest。
VERDICT: CONFIRMED | severity_opinion: critical
verify notes: 逐条核对结果(全部只读):

1) 唯一放行形态 — 坐实。src/search/certified_surface.py:497-546 `resolve_p1_2_publish_open_gate()`:gate 路径硬绑定到 `<project_root>/data/review_gates/phase_1_2_spike_close.json`,调用方不可传路径(:503-509 docstring 明写防伪造);放行需三者同真:status == P1_2_PUBLISH_GATE_CLOSED_STATUS(常量 = "closed_manual_owner_decision",certified_surface.py:46;检查在 :527-529)+ next_phase_entry.allowed is True(:531-536)+ owner_manual_decision.p1_3b_entry_allowed is True(:538-542);缺失/非常规文件/symlink/strict-JSON 失败/gate_id 不符/任何异常一律视为 open(:515-525, :545-546)。

2) publisher 两次查门即 raise — 坐实。certified_surface.py:802-808(stage 前)与 :833-839(commit 前、且中间还比对 campaign 状态未变 :830-832)两处遇 gate open 直接 RuntimeError,外层 except 走 fail-closed 回滚(:856+)。PROJECT_LOCK.md:126 亦记录该函数"在人工 phase gate 未打开时 fail-closed"。

3) gate 文件现状 — 坐实。data/review_gates/phase_1_2_spike_close.json:5 status="blocked_manual_review_count";:24 p1_2_close_status="not_closed";:25 p1_3b_entry_allowed=false;:34 next_phase_entry.allowed=false;:35 authority="owner_manual_decision_only";:30 note 原文即"The repo intentionally does not record or compute 0/3, 1/3, 2/3, or 3/3. The owner keeps the count.";:11-13 counting_authority="owner_manual_count_outside_repo"、repo_derives_clean_count_from_receipts=false。放行形态(closed_manual_owner_decision + 两个 true)在该文件里确实完全不存在。

4) PROJECT_LOCK.md:179-185 — 坐实。"owner 手动条件"明文禁止从 receipt/报告/package metadata/source-tree manifest/clean-count/内部 supervisor seal 自动推导 P1.2 closed / P1.3 allowed;:136-137 另有"任何 checker PASS、局部回归 PASS 或内部 supervisor seal 都不得改写为 owner 已关闭 release gate"。

与原断言的出入:无实质出入。行号全部命中;唯一可补充的语境是 PROJECT_LOCK.md:130-133 同时列出另一个独立缺口(无生产 supervisor CLI 入口、main.py 终点 CANDIDATE_PROPOSED),即此门是"终点闸"但不是唯一未完成项。

严重度独立评估:同意 critical(作为"最终目标瓶颈"而非 bug)。理由:(a) 它是链条上唯一无法用任何工程动作解开的环节——supervisor 入口缺口可以写代码补,这道门只有 owner 能开;(b) 解锁进度(0/3~3/3)在交付副本上刻意不可见,连评估都做不到;(c) 经验证据显示 streak 极难攒满:gate JSON informational_history 记录 v81-v98 共 18 轮外审每轮都有 finding 且每轮"Owner clean-streak count resets to 0"(如 :234、:242、:370),v99 只是 sealing 锚点且 summary(:7)明说 post-v99 工作树改动还需 fresh reseal;(d) 断言正确定性了"设计如此而非 bug",不算夸大——它确实使最终目标的最后一步落在 owner 手里,任何机器绿灯都替代不了。

## [critical] votes=3 | binding/routing/master 的 CP-SAT 编码忠实性是全链唯一无冗余单点：I1『独立复验』与 fixed-witness 复验全用同一份建模构造器，编码错误 100% 相关联
lenses: chain, soundness
evidence: src/search/independent_infeasibility_reverifier.py:24 直接 import 同一个 PortBindingModel；:155-165 用同一构造器同一输入重建模型；:220-246 只是对同一个 CpModel 换 solver profile（PORTFOLIO_SEARCH+固定 seed+2 workers），注释只敢自称 'Heterogeneous profile'；docstring :10-13 明写 CP-SAT infeasibility+binding/routing 构造器是 NAMED-TCB。terminal_fixed_witness_verifier.py:18-28/:239-375 同样 import 同一份构造器重建。生产 exact-safe cut 全部基于 binding/routing 拒绝的 nogood 且落 cut 前仅过这个 I1（benders_loop.py:7450-7598）。负证明记录侧：candidate_proof_replay.py:890-920 的 replay 仍是同套求解代码重跑；PROJECT_LOCK.md:357 登记过 worker crash 时序让错误 INFEASIBLE 变 sticky 强状态污染 terminal frontier 的实证案例。checker 自述只是 structural gate（check_p1_2_proof_obligations.py:4245-4252），不证候选/几何。README 第 6 章盲点 E 明记编码从未被逐约束对抗审。
why: 若 binding/routing 编码多/漏一条约束（false-INFEASIBLE 方向），错误 nogood 会把真可行布局从 master 割掉，某个真实更优候选被判 INFEASIBLE→产出『假的 lex 最优』CERTIFIED；而复验用同一份构造代码+同一个 CP-SAT 库（连 presolve 都同源），必然同错同过。19 轮 close-kernel 硬化全在护『状态铸造权不被绕过』，没有任何机制护『编码本身正确』——这是整条证明链数学意义上最薄的一层，checker 全绿也抓不到。
fix: 对 binding/routing/master 做逐约束正面对抗审（每条约束形式化对应游戏规则条款）；给 INFEASIBLE 方向引入真正异构的第二编码（独立 SAT/MIP 或 assumptions-based unsat core），至少覆盖落 whole-layout cut 的关键场景；支撑 terminal frontier 的负候选记录应要求 proof-carrying replay，经历 crash/resume 的候选默认强制重算。
VERDICT: CONFIRMED | severity_opinion: critical
verify notes: 逐条核实结果(全部只读):

【坐实的事实前提】
1. I1 复验器与生产同构造器:src/search/independent_infeasibility_reverifier.py:24 `from src.models.binding_subproblem import PortBindingModel`(与生产同一构造器);:155-165 `_reverify_binding_infeasible` 用同一构造器、同一输入重建模型并 build();:220-246 `_solve_with_independent_cp_sat` 只换 solver 参数(PORTFOLIO_SEARCH + seed 8675309 + randomize + 2 workers),对象仍是同一个 `cp_model.CpModel`、同一个 OR-Tools 库(presolve 同源),:227 注释原文即 "Heterogeneous profile versus the production binding solve"——异构仅在搜索参数层;docstring :10-13 明写 NAMED-TCB 包含 "the binding/routing model constructors imported below"。断言原文坐实。
2. fixed-witness 复验同源:src/search/terminal_fixed_witness_verifier.py:19-28 import 同一份 PortBindingModel / RoutingSubproblem / run_exact_routing_precheck;:239-258(binding 重建+solve)、:324-375(routing 重建+solve)全用同一构造器。坐实。
3. benders_loop 落 cut 链:benders_loop.py:7498-7598 `_add_exact_whole_layout_nogood` 中 whole-layout nogood 落 cut 前唯一门是 :7538 `reverify_whole_layout_infeasibility`(I1),不 confirmed 则 fail-closed 返回 False。坐实,但有一处出入见下【出入】。
4. 负证明 replay 同套代码:candidate_proof_replay.py:890-922 `_replay_one_proof` 直接 `from src.search.benders_loop import run_benders_for_ghost_rect` 重跑生产求解栈,非独立编码。坐实。
5. PROJECT_LOCK.md:357 = F-SCHED-BS-R5-02,原文确实登记 crash 时序把假 INFEASIBLE 持久化为 sticky 强状态、毒化 compute_terminal_frontier_projection → 假 CERTIFIED,且明写 terminal validators 只是对已毒化记录的自洽检查、无独立复算(该案已修,但作为"false-INFEASIBLE→假 lex 最优链真实可走通、终端无兜底"的实证引用是准确的)。坐实。
6. checker 自述:scripts/check_p1_2_proof_obligations.py:4245-4253 docstring 原文 "deliberately remains a small structural gate. It does not certify a candidate and it does not reason about geometry."。坐实。
7. README 盲点 E:README.md:1936-1943 原文"子问题 CP-SAT 编码忠实性从未被逐约束审……I1 复验器(用同源/同编码)抓不到,gate 全绿",且两版外审都判其"最重要";README.md:931-932、:981 另确认 I1 仅覆盖 binding-INFEASIBLE、routing 穷尽 phase-1 保守、I2 master 域编码 PARTIAL。坐实。
8. 无异构第二编码:在 src/search 全量搜 unsat/assumption/z3/pywraplp 等,命中的只有 phase3b 探针(probe/advisory,取证性质)和 separator,无任何独立编码的 INFEASIBLE 校验;pose_bool_exact_master 虽是另一套 master 编码但被 env 守卫挡在 certified 路径外(CLAUDE.md/README 一致)。坐实"唯一无冗余单点"。

【出入(方向上反而强化断言)】
断言称"生产 exact-safe cut 全部……落 cut 前仅过这个 I1"不精确:`_add_exact_persisted_nogood` 共 4 个调用点(benders_loop.py:5654 power 子问题 nogood(env-gated,certified 路径不可达)、:5904 binding EMPTY_DOMAIN placement-local nogood、:6694 routing_front_blocked placement-local nogood、:7589 whole-layout),其中只有 whole-layout 一类过 I1;:5904 与 :6694 两类 placement-local exact-safe cut 连 I1 都不过,直接落 cut。即冗余比断言描述的还薄——出入方向是低估而非夸大问题。

【严重度独立评估】
同意 critical。理由:(a) 命中的正是"certified-exact"这一交付物的数学核心——正方向 6 谓词有非 CP-SAT 的独立终端校验兜底,但负方向(∀ 更大候选 INFEASIBLE = lex 最优性)完全依赖同一份编码+同一 CP-SAT 库,编码性 false-INFEASIBLE 会产出布局合法但最优性为假的 CERTIFIED,且 checker/preflight/终端 validator 全部结构性抓不到;(b) 项目自己的 README(盲点 E)和 C3 审计承认从未逐约束审、并判为最重要盲点,19 轮 close-kernel 硬化全在护状态铸造权、零机制护编码正确性;(c) false-INFEASIBLE→sticky→假最优的下游链已被 R3/R4/R5 三轮 reachable soundness reset(时序方向)反复证实真实可达、终端无兜底,编码方向只是同一链的另一个未被堵的入口。可辩空间仅在"这是未证伪的潜在风险而非已知缺陷",但按"挡住最终目标(合法关闭 P1.2 手动门)"的标准,编码忠实性未经对抗审本身就是关门的实质障碍,critical 成立、未见夸大。

## [critical] votes=3 | owner 单人单机零冗余：clean-review 计数、gate 拍板依据、26 个未推送 commit 的硬化成果全部只存在于一个人的脑子和一台机器上，不可恢复
lenses: process, chain
evidence: git shortlog -sn --all 实测 94 commits 全部 zhuran24 一人；git remote -v 输出为空（无远端、无 push）；.git/hooks 无任何生效 hook；pr2-5 分支领先 main 26 commit/+15266 行仅存于本地 .git 与 worktree（实测）；gate JSON:11-13 counting_authority=owner_manual_count_outside_repo 且 repo_derives_clean_count_from_receipts=false；README.md:514 记 v28 原始外审报告不留仓库；README 引用的全部原机 commit hash（b35e5f9/9bbb3a6/099f5a3）git cat-file 实测均不可解析，史料仲裁能力已断。
why: 最终目标的最后一步（手动门合法关闭）设计上只能由 owner 完成，而 owner 侧的计数、裁定依据、19 轮对抗硬化的最新成果都没有第二份副本。owner 中断/机器损坏/记录丢失任何一件都会让项目永久停在 blocked_manual_review_count——反自动推导是 soundness 控制、是设计要求，但零冗余不是，是纯粹流程债。
fix: 把『反自动推导』与『零冗余』解耦：pr2-5 与 main 立即 git bundle 或 push 私有远端（零审批、零风险）；owner 的 clean-review 计数与每轮裁定进一份仓库外有备份的人读日志（或仓库内 append-only 审查 ledger：记 scope、包 hash、结论、是否清零，但不让机器自动加 clean credit）；原始外审包至少以 hash+归档位置登记。
VERDICT: PARTLY | severity_opinion: major
verify notes: 逐条核实（全部只读实测，仓库根 C:\claude pj\zmd-pj）：

【坐实的前提】
1. `git shortlog -sn --all` = 94 commits 全部 zhuran24 ✓；`git rev-list --count --all` = 94。
2. 本仓库 `git remote -v` 输出为空 ✓。
3. `.git/hooks` 只有 14 个 *.sample，无任何生效 git hook ✓。
4. pr2-5 领先 main：`git rev-list --count main..pr2-5-domain-frontier-gate` = 26；`git diff --shortstat main...pr2-5` = 14 files, +15266/-189 ✓（主体是 scripts/check_p1_2_proof_obligations.py +9300 行；分支另有 worktree C:\claude pj\zmd-pj-round19，同一台机器同一 .git）。26 个 commit 日期 2026-06-29 至 07-02。
5. gate JSON（data/review_gates/phase_1_2_spike_close.json:11-13）：counting_authority="owner_manual_count_outside_repo"、repo_derives_clean_count_from_receipts=false ✓；:26-30 owner_clean_count_status="maintained_outside_repo"、"repo intentionally does not record or compute 0/3…" ✓。
6. README.md:514 记 v28"原始 review 报告不留仓库（owner 仓库外维护）" ✓；gate JSON:42 同证。
7. b35e5f9/9bbb3a6/099f5a3 在本仓库 `git cat-file -t` 全部 fatal ✓。

【被推翻/需修正的关键前提——断言遗漏了两份真实存在的冗余】
A. **私有 GitHub 远端存在且新鲜**：`gh auth status` 以 owner 本人（zhuran24，repo scope）登录，`gh repo list` 实测存在私有仓库 zhuran24/zmd_pj，pushed_at=2026-07-01T07:13:08Z（断言核查当天前一天）。`git ls-remote` 显示远端有 main(5ab006f)+topology-opt 两分支及 2 个已合并 PR。远端 main 的 scripts/check_p1_2_proof_obligations.py 大小 225,177 字节 = 本地 main 同文件字节数完全一致（本地 pr2-5 版本为 622,122 字节）——即 **main 主干内容已有机器外副本**，"全部只存在于一台机器"不成立。推送来自另一份工作副本 C:\codex pj\zmd_pj（其 origin 即该远端）。远端 main tip 的 commit message（"memory: PR2 #5 round-10/11/12…"）说明各轮硬化的记忆卡叙述也已上远端。
B. **原机 920-commit 完整历史有本地 bundle 备份**：C:\Users\22957\zmd_git_backup_2026-06-16\zmd_repo_all.bundle（162,358,410 字节，2026-06-16），克隆到 scratchpad 实测含 920 commits、含旧 origin 远端 refs。RESTORE_NOTES.txt:2-9 载明这是 owner 主动做的历史重建前备份。但两点限定：① 该 bundle 在同一台机器 C: 盘，不抗机器损坏；② RESTORE_NOTES:9 称"GitHub 远程 zhuran24/zmd 未被删除"，而现在以 owner 身份实测 `gh repo view zhuran24/zmd` = not found（**旧远端已被删除**），故 920-commit 原史料现确实只剩这台机器一份。③ README 引的 b35e5f9/9bbb3a6/099f5a3 在 920-commit bundle 里也解析不出——这三个 hash 的仲裁能力确实彻底断了，连 bundle 都救不回。

【仍然成立的核心风险】
- pr2-5 的 26 commit/+15266 行硬化：不在 GitHub（远端无此分支、远端 checker 文件是 main 版本）、不在 06-16 bundle（全部 commit 晚于 bundle 日期）、无 remote 无 hook——**确实零机器外冗余**，机器损坏即丢 19 轮对抗硬化的代码成果（叙述性记忆卡在远端，代码本体不在）。
- owner 仓库外的 clean-review 计数与原始外审报告：设计上就在仓库外，是否有备份从仓库无法核实（断言说"没有第二份副本"属不可证实的推断，非坐实事实）。

【严重度独立评估】
hunter 判 critical 依据的"最终目标会永久停摆、全部资产不可恢复"被夸大：主干内容+记忆叙述已有机器外私有远端副本（07-01 刚推过），计数丢失也只是清零重数（gate 本来就要求连续 3 次 clean，重置≠永久 blocked）；真正的单点是 pr2-5 未推送硬化和已删旧远端后仅存本机的 920-commit 史料 bundle。这是真实、廉价可修的流程债（把 pr2-5 push 到已存在的私有远端、把 bundle 拷去远端/E: 即可），但不构成"任何一件都永久停摆"级别。修复方向本身合理。判 major。

主要证据坐标：data/review_gates/phase_1_2_spike_close.json:11-13,26-30,42；README.md:514；C:\Users\22957\zmd_git_backup_2026-06-16\RESTORE_NOTES.txt:2-9；本地 git 实测（shortlog/rev-list/diff --shortstat/cat-file）；gh api 实测（zhuran24/zmd_pj 存在、zhuran24/zmd 已删、远端 checker 文件 size=225177）。

## [critical] votes=2 | 被判『数学上唯一出路』的 F1-F9 cut 体系至今未接入生产 master：step_8_apply_to_master 仍 raise NotImplementedError，生产代码零 import src.cuts
lenses: compute, chain
evidence: src/cuts/lifecycle.py:1121-1126 实测仍 raise NotImplementedError('Step 8 apply-to-master 在 Phase 1.3 P1.21 实施')；git grep 实测 src.cuts 的 51 个 import 命中全部在 src/cuts/ 自身与 src/tests/cuts/，main.py/src/search/src/models 生产代码零命中；docs/项目说明/03_paradigm_death_baseline.md:146-171 判定 F1-F9 是唯一满足四个根因约束的范式并列出必须覆盖的几何/物流 infeasibility；PROJECT_LOCK.md:108-112 亦明文登记未接入。
why: 生产 master 没有任何 packing/密度/区域容量类全局强化约束，LBBD 收敛只靠一次排除一个具体布局的 nogood——对百万级 pose literal 的空间是杯水车薪。27 条 lever 判死之后，全部工程投入都在护发布链，求解能力这条线一行生产代码没动：cut 不接入，算力墙没有任何理论破口，提证能力停滞在 2026-05 的 0 FEASIBLE 水平。
fix: 实现 lifecycle step 8，把 F1-F9 以 fail-closed、可 replay、可审计形式接入 benders_loop/生产 master；接入前先收敛 README 记载的 F7/F8/F3 latent false-INFEASIBLE 原语问题（FP=0 纪律使有效强度受限）；先用小规模 frontier 实证 cut store 能减少 UNKNOWN，再谈 168h。
VERDICT: CONFIRMED | severity_opinion: critical
verify notes: 核实过程（全部只读，file:line 证据）：

【证据逐条坐实】
1. step_8 仍 NotImplementedError：src/cuts/lifecycle.py:1121-1126 实读确认——`def step_8_apply_to_master(...)` 直接 `raise NotImplementedError("Step 8 apply-to-master 在 Phase 1.3 P1.21 (benders_loop integration) 实施.")`；1117-1118 的 `MasterModelLike` 只是空 Protocol 占位。
2. 生产代码零 import src.cuts：用 `^\s*(from src\.cuts|import src\.cuts)` 全仓 grep，src/ 内命中全部落在 src/cuts/** 与 src/tests/cuts/**；main.py、src/search/、src/models/ 零命中。仓外命中只有 scripts（外审打包器 build_phase1_1_gpt_pro_review_v2-v7、vulture 白名单、结构 checker check_p1_2_proof_obligations.py）、docs/research 复现脚本和 .artifacts 历史快照——均非求解生产路径。原断言说「51 个命中」，我按 import 语句数到 211 处/75 文件（计数口径不同），但「生产代码零命中」这一实质结论成立。
3. docs/项目说明/03_paradigm_death_baseline.md:146-157 确认：把 27 lever 的 4 个 root cause 翻成 paradigm 必须满足的四条约束（:150-155 表格，含「cut 必表达几何 INFEASIBLE (F1 capacity/F6 Hall) 跟物流 INFEASIBLE (F2 cutset/F4 reach)」），:157 明写「cut framework B Design v2 是这 4 个约束唯一满足的 paradigm……是项目数学上不得不走的路」。
4. PROJECT_LOCK.md:108-112 (B-2) 确认明文登记：「`src/cuts/` 尚未集成进生产 master（`lifecycle.py step_8_apply_to_master` 仍 `NotImplementedError`）」。
5. 「27 条 lever 判死」坐实：03_paradigm_death_baseline.md:182「27 lever 死路实测穷尽 7 类 attempt, 全死」；docs/项目说明/20_skip_directions.md:12；docs/lever_verdicts.md。
6. F7/F8/F3 latent false-INFEASIBLE 原语问题坐实：README.md:743-753（F7 power_cover.py:45 欧氏圆 vs 12×12 方形、F8 power_network.py:69、F3 candidate_placements.py:58-63 N/S 朝向反），且明写「设计推后到 P1.3，至今未做」——修复方向前提成立。

【与原断言的出入（不动摇结论）】
a. 「LBBD 收敛只靠一次排除一个具体布局的 nogood」略有夸张：benders_loop.py 实际有多种 nogood 变体——placement_local_nogood（:5904-5910、:6588「Tight cut 一次切大」conflict-core minimizer）、binding_pose_domain_empty_nogood（:5870）、signature-lifted master nogood（:6446-6454）、ghost-conditioned power nogood（:5654-5669）、whole-layout nogood（:7498+）。但这些全是排除式 nogood 族；grep density/region_capacity/packing/hall/cutset 在 benders_loop.py 仅 :8126 一处注释命中——「生产 master 无任何 F1-F9 类全局强化约束」这一核心事实成立。
b. 「0 FEASIBLE 水平」没找到字面统计，但方向被文档支撑：03:32-33 multi-anchor 0/8 CERTIFIED（PCR-CUT/D2）、03:66 cand C Phase 2 160/266 INFEASIBLE、03:129 98% utilization 几何死结；且 06_current_status.md:95 确认「P1.3：后续真正的 master/cut integration」未开放——2026-05 B Design v2 之后求解能力线确无生产代码落地。
c. 需补一个语境：这是 PROJECT_LOCK 登记在案、刻意排序到 P1.3 的推迟（先关 P1.2 认证链），不是隐藏缺陷；hunter 的表述基本如实反映了这点。

【严重度独立评估】critical 成立、未见夸大：最终目标要求端到端产出 CERTIFIED，而 terminal 状态要求 strict full-frontier exhaustion evidence（README:476 PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE）——即便 PR2 #7 通电、owner 开门，没有求解能力破口就产不出可 seal 的 proposal。项目自己的数学文档判定 cut framework 是唯一活路（03:157），而这条唯一活路的生产接入点（step 8）为空、且接入前置条件（F7/F8/F3 canonical 原语收敛）也未做——两级前置都未动，确为最终目标的最深瓶颈。唯一可争处是它被 P1.2 手动门刻意排在后面（顺序性推迟而非疏漏），但这不改变「求解能力线无理论破口」的事实。

## [critical] votes=2 | clean-review 关门循环结构上无终止保证：历史 18 次清零、收敛判断三次被证伪，每轮还要缴一笔无 runbook、易出错、税基单调上涨的 reseal 税，且门禁在本副本全靠手动自觉
lenses: process
evidence: gate JSON:10 要求连续 3 次 clean，但 informational_history 里 'clean-streak count resets to 0' 实测出现 18 次，约 70+ 轮外审从未连成 3 clean；round-9（'123/123 已钉'）、round-14、round-19（5ff31ac 自述第 12 轮外审挖出『语义门只护 3 个 runtime 文件、保护它们的父锚自己没进门』的共同根因）三次『自验全绿仍被挖出结构根因』；当前卡在 owner 手动逐条剪贴板 relay 第 13 轮外审（7 份提示词已 staged、外审包未打，es 实测）。reseal 侧：README:1681 自认无单一权威 runbook，README:1284 列出 CRLF/LF 自钉不符、pathspec 漏文件等真实事故；round-19 一轮 checker 从 4442 涨到 12859 行、sink/allowlist 计数全变——每轮外审修复的 reseal 面单调扩大。门禁侧：无 remote 使三条 CI（含唯一跑 --slow-tests 的 job）永远惰性，preflight --full 仍 -m 'not slow'（preflight_gate.py:679），改认证核心漏跑 slow lane 无任何机制提醒。
why: 这是通往关门的唯一路径，但它是『每轮都可能清零、清零后从头数』的循环：按 18 次清零的基准率，3 连 clean 没有可估完成日期。每轮迭代都要 owner 手动打包、relay、triage、再在 Windows/CRLF 环境无 runbook 地缴 reseal 税——reseal 做错本身可能变成下一轮 finding，门禁惰性又让回归可静默入树污染下一轮 clean 计数，形成『修复→reseal 出错→新 finding→再清零』的自耗环。项目最可能的死法不是某个 bug，而是这个循环在 owner 精力耗尽前不收敛。
fix: 把 README §9+cc_memory 事故收敛成单一权威 reseal runbook（命令级：LF hash 来源、pathspec 全集、必跑 gate 清单），甚至写成只对账不写入的脚本；外审 relay 的打包/staging/回传 triage 半自动化；加私有远端或 pre-push hook 强制 preflight，并对『diff 触碰认证核心但未跑 --slow-tests』硬 BLOCK；owner 层面重估五类 finding 全量清零的粒度是否过粗（近几轮 finding 已从 soundness 洞退化为结构门覆盖面问题）。
VERDICT: CONFIRMED | severity_opinion: critical
verify notes: 逐条核实结果（全部只读操作）：

【坐实】gate 三连 clean 要求与 18 次清零：`data/review_gates/phase_1_2_spike_close.json:10` 确有 `"required_consecutive_clean_full_reviews": 3`；"clean-streak count resets to 0" 在该文件精确出现 18 次（v81–v98 每包一条，Grep count 实测）。informational_history 覆盖 v28→v99 共 72 个编号包，加上 pr2-5 分支 12+ 轮 GPT Pro 外审，"约 70+ 轮从未连成 3 clean" 成立——v28–v80 各包分类几乎全是 `algorithmic_proof_obligation_reset`，gate 现状仍 `status: "blocked_manual_review_count"`（:5）。

【坐实】收敛判断三次被证伪：① round-8/9「123/123、收敛」被 round 10–14 证伪——README.md:1307 原文自认（"我们过早宣布收敛且错了"）；② round-14 后第 11 轮外审 BLOCK——commit 2d7dd09 "round-15: close-kernel 第二道门硬化(第11轮外审 BLOCK 后)"、fd7678d "codex 前置复审挖出 round-15 3 BLOCK"；③ 5ff31ac（pr2-5-domain-frontier-gate HEAD）commit message 逐字自述"第 12 轮 GPT Pro 外审(pr2-13)去重后收敛到一个共同根因:round-15..18 的语义门只覆盖 3 个被保护的 runtime 文件,但保护它们的机构…自己没进语义门"——与断言引文吻合。

【坐实】当前卡在第 13 轮外审 relay：`C:\Users\22957\pr2_5_round19_review_entry_*.md` 恰好 7 个文件（es 实测 count=7）；`C:\Users\22957\pr2_pkg\` 里最新审包止于 round-18（zmd_pr2_5_round18_9bbb3a6.7z），无 round-19/5ff31ac 的 .7z——"7 份提示词已 staged、外审包未打"逐字坐实。owner 手动逐条剪贴板 relay 规程见 `cc_memory_vnext/cards/relay-review-clipboard-staging.md`（Set-Clipboard 沙箱假成功、逐条 600ms 间隔等实测坑，佐证"手动、易出错"）。

【坐实】reseal 税：README.md:1681 原文"reseal 的 index/HEAD/working-tree 操作细则尚无单一权威 runbook"；README.md:1284 原文列 CRLF/LF 自钉不符、tuple unpack 破 7 测试、codex targeted -k 跑漏回归、ruff F401 reseal churn 等真实事故（pathspec 漏文件事故在 :1273 引 cc_memory `pathspec-must-cover-full-reseal-set`，位置与断言引 :1284 有一行级出入，不影响实质）。checker 行数实测：main 4442 行、分支 12859 行、round-18 12235 行。

【一处表述出入】"round-19 一轮 checker 从 4442 涨到 12859 行"：4442→12859 是**整条分支 19 轮相对 main 的累计**（与项目 CLAUDE.md 的"+8700 行"同一口径），round-19 单轮实际 12235→12859 = +624 行。按"到 round-19 为止"读则数字精确成立；按"单轮涨 8400"读则夸大。两个数字本身都真实。

【坐实】门禁惰性：`git remote -v` 无输出（无 remote）；`.github/workflows/` 恰好 3 个 yml，唯一 `--slow-tests` 在 project_foundation.yml:91——无 remote 则三条 CI 全惰性。preflight_gate.py:679 实证 `cmd += ["-m", "not slow"]` 且 `--full` 同走此分支（:666 标签"全量 · 跳过 @slow"）；:789-791 slow lane 只在显式 `--slow-tests` 时跑，全文件无任何"diff 触碰认证核心→强制 slow lane"的机制——"漏跑无机制提醒"坐实（仅 CLAUDE.md 文字约定）。

【严重度独立评估】维持 critical：① 该门是最终目标（合法关闭 P1.2）的唯一路径且 owner-manual-only（gate JSON:32-37），任何自动绿灯都不能开门；② 18 次实测清零 + 三次收敛误判 = "无可估完成日期"不是修辞而是基准率归纳；③ "reseal 出错变下一轮 finding" 有实锤先例（v83/v88 两次 reviewer patch 本身有缺陷、README:1284 的 tuple 破坏）；④ CI 全惰性 + slow lane 无机制强制 = 回归可静默入树。唯一可辩护的减轻因素：finding 严重度趋势确实在退化（v81-v98 从 soundness 洞退到伪造面/发布面问题，pr2-5 近轮退到结构门覆盖面），暗示渐近收敛——但断言自己已把这点写进修复方向（"重估五类 finding 全量清零的粒度"），且"趋势向好"不等于"有终止保证"，故不构成降级理由。

## [major] votes=3 | L0 隔离验证的信任锚——dependency floor manifest——是未经审查的 dev/CI 沙盒占位字节，重生成只能在 CachyOS+Py3.13 生产机上做，而整条生产链路 Linux-only 单点
lenses: chain, soundness
evidence: src/search/pr2_l0_micro_verifier_core.py:39-46 源码注释明写 pinned manifest bytes 是 'dev/CI placeholder from an audit Linux environment, not the production-reviewed canonical floor'，要求生产部署前在 CachyOS Python 3.13 venv 用 scripts/generate_pr2_dependency_floor_manifest.py 重生成、审字节、re-pin（pin 在 :45-46，574082 字节）；p1_2_proof_obligations.json:847-858 登记 manifest_provenance_status=deploy_pending_placeholder；scripts/production_readiness_gate.py:27 明写项目 Linux only、非 Linux 直接报错；Windows wrapper 需手动 -ResumeCampaign 否则丢进度。
why: 该 manifest 是隔离子进程里第三方模块逐文件 rehash 的楼面，即防止被篡改的 ortools/native 模块混进验证 TCB 的最后一道锁——三权分立中『验证不可伪造』的支点现在向一个没人审过的沙盒快照宣誓效忠，只要它还是占位字节，任何生产 seal 在证据学上都站不住（drift 会 reopen close claim）。而重生成这步在本机 Windows/WSL 物理做不了；生产跑、readiness gate、watchdog、绑核也全在那台 CachyOS 机器——原生产机若不可用，从 168h campaign 到合法 seal 的整段链路无处落地。
fix: 把『CachyOS+Py3.13 上重生成 manifest→人审→re-pin→走 reseal 连锁』列为生产前硬前置第一项并确认生产机可用性——这是少数不依赖外审进度、现在就能排期的实活。
VERDICT: CONFIRMED | severity_opinion: major
verify notes: 逐条核实结果（全部只读核对）：

【证据 1：源码注释】坐实。C:\claude pj\zmd-pj\src\search\pr2_l0_micro_verifier_core.py:39-44 注释原文确为 "these pinned manifest bytes are a dev/CI placeholder from an audit Linux environment, not the production-reviewed canonical floor"，并要求生产部署前用 scripts/generate_pr2_dependency_floor_manifest.py 在 CachyOS Python 3.13 venv 下重生成、人审字节、re-pin。pin 常量在 :45-46（SHA 41008dbb...240b90，574082 字节），与断言一致。同时注释末句明确说 "runtime byte-pin and fail-closed behavior below are host-independent soundness hardening"——即防篡改机制本身是好的，缺的是 provenance 审查。

【证据 2：obligations 登记】坐实。data/proof_obligations/p1_2_proof_obligations.json:847-859 的 dependency_floor_provenance 块：manifest_sha256/size 与源码 pin 一致；manifest_provenance_status = "deploy_pending_placeholder_regenerate_on_production_cachyos_py313"（断言略缩写但实质一致）；mutation_policy = "dependency_floor_drift_reopens_p1_2_close_claim"，坐实"drift 会 reopen close claim"。

【证据 3：Linux-only】坐实。scripts/production_readiness_gate.py:27 原文 "项目 Linux only — 不做 cross-OS skip，非 Linux 上 pacman check 会直接报错"。Windows wrapper 三个 run_prod_*.ps1（如 run_prod_4x4_normal.ps1:3,18-19）确实只有显式传 -ResumeCampaign 才加 --resume-campaign，而 scripts/campaign_watchdog.sh:20 注释确认 Linux wrapper 是 auto --resume-campaign。

【manifest 角色】坐实且比断言描述的更硬。src/search/pr2_l0_true_verifier_child.py:35-260：verify() 第一步就是 _install_third_party_floor(payload["dependency_floor"])；该函数校验 manifest 内嵌 digest、逐文件 read_bytes 后比对 sha256+size（:231-233），然后把 sys.meta_path 整体替换为 _RestrictedThirdPartyFinder（对每个 import 用 _RehashingSourceFileLoader/_RehashingExtensionFileLoader 装载时再 rehash，:144-151）+ _StdlibOnlyPathFinder。generate 脚本的 PROBE_IMPORTS（scripts/generate_pr2_dependency_floor_manifest.py:26-42）覆盖 ortools/protobuf/absl/jsonschema——确为"防篡改 ortools/native 模块混进验证 TCB 的最后一道锁"。

【磁盘实测】当前 tracked manifest 字节 SHA=41008dbb...240b90、574082 字节，与 pin 完全一致（Get-FileHash 实测）。

【与原断言的出入（两处措辞级）】
1. "重生成只能在 CachyOS+Py3.13 生产机上物理做"——字面偏强：generate 脚本本身跨平台可跑（floor_root 用 PYTHON_SYSCONFIG_PURELIB 哨兵、相对路径设计就是为了不钉死机器）。但实质正确：canonical floor 必须来自生产 venv 的 wheel 字节（Linux .so），Windows/WSL 生成的 manifest 对生产 seal 无意义；且 child 运行时按当前 host 的 purelib rehash，生产机 venv 与 audit 快照字节不一致时 seal 会直接失败。
2. "任何生产 seal 在证据学上都站不住"——需加一个缓冲：机制是 fail-closed 的，占位 manifest 与生产环境不匹配时 seal 会被挡死而不是铸出坏 seal；真正的残余风险是若生产环境恰好与未经人审的 audit 沙盒字节相同，seal 会向一个没人审过的快照宣誓——这正是 deploy_pending_placeholder 登记要堵的口。所以这是"挡路的硬前置 + provenance 审查缺口"，不是"静默不可靠"。

【严重度独立评估】major 判定合理，不夸大不低估。不到 critical：无静默 unsoundness，fail-closed 保护在，且该缺口已在 obligations JSON 里显式登记并绑定 reopen 政策——是已知、已排期形状的实活，不是暗雷。不止 minor：它是最终目标（合法 CERTIFIED seal + P1.2 关门）的硬前置，重生成+人审+re-pin 还要走完整 reseal 连锁（V99 floor、obligations JSON、allowlist、checker 自钉最后算），且确实只有那台 CachyOS 生产机能落地——机器可用性是本机无法核实的外部单点，断言把"确认生产机可用性"列为第一项排期实活是对的。

## [major] votes=2 | 168h 生产长跑执行层多重工程债：48GB 单机 -p≥2 必 OOM 且 watchdog 默认 -p4 与 gate 结论直接矛盾、UNKNOWN 短命退出+墙钟含死亡时间记账、无缓存全量 re-replay 性能债未偿、resume 清强状态且 Windows wrapper 不默认 resume
lenses: compute
evidence: scripts/production_readiness_gate.py:320-343（2026-05-14 双轮实测 -p4 9 分钟 global_oom、-p2 单 worker 飙 28GB swap thrash，『48GB 本机 -p1 marginal、-p≥2 必 OOM』）vs scripts/campaign_watchdog.sh:60-62 硬编码 --parallel-processes 4（按 gate 公式需 128GB，配置雷未对齐）；watchdog.sh:5-11/:41-46 实录『candidate 频繁撞 UNKNOWN、campaign 30min 一次短命退出，168h 大跑实跑 15-17h』；exact_campaign.py:3094-3097 remaining_seconds 按 created_at 墙钟算、进程死亡时间也在烧；README.md:726（root-cure 的无缓存全量 re-replay 每轮冷启子进程重解 Benders，『168h 生产跑可能被验证开销烧光预算退 UNKNOWN』，perf 会议已裁定缓存方案『真 168h 生产前必做，至今没做』）；PROJECT_LOCK.md:267-274 + exact_campaign.py 实现 resume 时强状态一律降 UNKNOWN 需 fresh replay；Windows run_prod_*.ps1 不默认 -ResumeCampaign；I1 保守策略使 routing-exhausted 候选滞留 UNKNOWN（independent_infeasibility_reverifier.py:83-133）。
why: 即使算力墙有破口，这一串执行层债也会让 168h 墙钟预算无法有效转化为证明进展：内存墙把实际并行度压到 1（横向扩展贡献近乎零）、watchdog 重启路径埋着 OOM 配置雷、re-replay 税随累积候选数乘性上涨、resume 语义正确地防 stale proof 但意味着历史算力不能自然累计成最终 CERTIFIED。交付副本内也没有任何可恢复的真实长跑 checkpoint/telemetry。
fix: 对齐 watchdog -p 默认值与 gate 的 OOM 公式；落地已裁定的内容哈希缓存方案（三硬条件，唯一方案明确只欠执行的一项）；所有生产 wrapper 默认安全 resume 并跨平台一致 fail-closed；预算记账改按实际推进时间；campaign 输出升级为可 replay 的证明工件包（候选证书+cut store+terminal evidence+hash+独立 replay 日志）。
VERDICT: CONFIRMED | severity_opinion: major
verify notes: 逐条核实（全部只读，file:line 均实测）：

【1. gate OOM 实测结论】坐实。scripts/production_readiness_gate.py:320-343 docstring 原文含 2026-05-14 双轮实测：-p4 「9 min global_oom kill」、-p2 retry「3 min 单 worker 飙到 28 GB, avail 跌到 1.8 GB, swap 5.5 GB → swap thrash 人工 abort」，:342 原句「48 GB 本机现状: -p 1 marginal, -p ≥ 2 必 OOM」。公式 needed = parallel × 30 GiB + 8 GiB（:348-349）。断言未提的细节：:344-356 有 EXACT_GATE_WORKER_PEAK_RSS_GIB 覆盖口（2026-05-15 spike#5 实测 workers=2 时 plateau 16.4 GB），即调低 CP-SAT workers 后 -p2 理论可过门——「-p≥2 必 OOM」是 baseline 默认口径而非绝对物理墙，但默认配置下成立。

【2. watchdog -p4 硬编码矛盾】坐实。scripts/campaign_watchdog.sh:60-62 硬编码 `--parallel-processes 4`。按 gate 公式 4×30+8=128 GiB，48 GB 机器必 BLOCK。补充核实的失败模式：run_campaign_linux.sh:137-140 会把 -p 值转发到 EXACT_PARALLEL_PROCESSES 供 gate 读，main.py:42,281-290 对 campaign-hours≥24 强制跑 readiness gate——所以 watchdog 重启在本机实际表现更可能是「gate BLOCK → 快速死亡 → 连续 5 次 quick death（watchdog.sh:45-46,116-121）→ watchdog 自杀退出」，是 fail-closed 拒启而非静默 OOM。配置矛盾本身坐实（且注意 Windows 侧 run_prod_4x4_normal.ps1:13 同样硬编码 -p4 + EXACT_CP_SAT_WORKERS=4）。

【3. UNKNOWN 短命退出 + 168h 实跑 15-17h】坐实。campaign_watchdog.sh:5-7 原文「candidate 频繁撞 UNKNOWN, campaign 短命退出 (实测 30 min 一次). 168h budget 用不满」；:41-42 原文「2026-05-11 教训: cap=100 时 168h 大跑只跑了 15-17h 就被强制停 + 烧电 0 产出 5h」（注：cap 已改 0，该特定病因已修，但作为历史实录准确）。

【4. 墙钟含死亡时间记账】坐实。src/search/exact_campaign.py:3094-3097 `remaining_seconds()` = campaign_hours×3600 − (now − created_at)，:3099-3102 `elapsed_seconds()` 同源；created_at 随 checkpoint 载入、resume/demote 路径不重置，进程死亡到 watchdog 重启之间的墙钟确实在烧预算。

【5. 无缓存全量 re-replay 债】坐实。README.md:726 原文：root-cure 在 outer_search 主循环每轮 + 内层 precheck 每圈对全部累积强候选无缓存全量 re-replay（每个冷启子进程重解 Benders）→「168h 生产跑可能烧光预算退 UNKNOWN」，perf 会议 4/4 裁定内容哈希缓存 + 3 硬条件方案「真 168h 生产前必做，至今没做」。源码侧核实：src/search/candidate_proof_replay.py 全文仅 pycache_prefix 隔离（:667-692），无任何内容哈希/结果缓存；全 src 无 replay cache 命中。债确实未偿。

【6. resume 清强状态】坐实。PROJECT_LOCK.md:267 + :272-274（F-CAM-R8-01/R8-02：checkpoint 载入的 CERTIFIED/INFEASIBLE 一律降 UNKNOWN、剥 solution/cut 计数/terminal evidence、先落盘再继续）；实现 exact_campaign.py:2179-2260 `_sanitize_resume_state_for_untrusted_candidate_evidence`（:2222 `record["status"] = "UNKNOWN"`）。语义上是刻意的 soundness 设计（防 stale/伪造 checkpoint 变正证明），断言也如实标注了「语义正确地防 stale proof」。

【7. Windows wrapper 不默认 resume】坐实。run_prod_4x4_normal.ps1:3 `[switch]$ResumeCampaign`（默认 off）、:18-20 仅显式传参才加 --resume-campaign；对照 run_campaign_linux.sh:111,127-135 自动注入 --resume-campaign（「audit F MED: 防崩溃重启忘加丢进度」）。跨平台不一致坐实。

【8. I1 保守策略滞留 UNKNOWN】坐实。src/search/independent_infeasibility_reverifier.py:83-89 docstring 原文「Legal routing-exhausted cuts may therefore be skipped and the candidate may remain open/UNKNOWN. That is an intentional soundness tradeoff」，:106-133 实现：routing-exhausted 仅在独立重建的 binding 模型自身 INFEASIBLE 时确认，否则返回 UNKNOWN。

【9. 交付副本无长跑 checkpoint/telemetry】坐实。data/telemetry 与 data/checkpoints 目录不存在，git ls-files 两路径零跟踪文件。

出入/夸大点（均属细节不动摇主干）：(a) 「watchdog 重启路径埋 OOM 雷」在本机默认链路上实际会被 readiness gate fail-closed 拦住（表现为跑不起来而非 OOM），只有 --skip-readiness-gate 或非 Linux /proc/meminfo 不可读时才真 OOM——「配置雷未对齐」成立，「必 OOM」措辞略过头；(b) 「-p≥2 必 OOM」是 30 GiB baseline 默认口径，gate 自带 worker-aware 覆盖口（spike#5 workers=2 → 16.4 GB）意味着存在已实测的缓解路径，断言未提。

严重度评估：hunter 判 major，我同意。这串债共同作用下 168h 墙钟无法有效转化为证明进展（并行度被压到 1、re-replay 税随候选数乘性涨、崩溃死时间烧预算、跨平台 resume 行为不一致），对「端到端产出 CERTIFIED」的最终目标是真实执行层阻塞。不到 critical 的理由：全部是工程债而非 soundness 洞（gate/resume/I1 的行为都是 fail-closed 方向、不会产出错误证明），且每项修复方向明确（配置对齐、已裁定的缓存方案、wrapper 默认值），无研究级不确定性；另外生产链本就存在更上游的刻意缺口（supervisor_seal 无生产入口，PR2 #7 未通电），执行层债并非当前唯一或最前置的闸门。

## [major] votes=2 | 冻结输入只被证明『没变』、从未被证明『正确』：candidate_placements pose 池完整性与规则语义是无人复核的 TCB，输入错则整个定理证的是错命题
lenses: soundness
evidence: src/search/certified_artifact_contract.py:29-47 只 pin 5 个工件的 sha256+size，:171-208 校验只比对 hash/size 不做任何 pose/footprint/port/power 语义检查；src/models/master_model.py:2256 该 45.8MB 文件是 master 全部 facility_pools 的唯一来源，I1 复验也从同一 pools 重建；CI 重生成只证明确定性、不证明枚举完整（project_foundation.yml:85-91）；canonical_rules.json 的 min_side/placement_rule 语义从未对照游戏实际规则独立验证；README.md:1679-1688 自己把 'candidate geometry hash-pinned TCB' 列为开放问题；PROJECT_LOCK.md:88-96 承认这些字节是 named TCB 而非代码自动证明的定理。
why: 整个 CERTIFIED 定理是『在这份 pose 枚举、这份规则字节下的最优』。若 placement_generator 少枚举任何合法摆位，每个候选的可行集被系统性低估→系统性 false-INFEASIBLE→lex 最优结论对真实游戏不成立；若某设施 footprint/端口生成时就写错，CP-SAT 会对错误输入求出数学自洽但对不上游戏的结果。hash 门、checker、I1、sink replay 全部消费同一份被 pin 字节，谁也发现不了——这是『证对了一个错定理』的风险。
fix: 对 placement_generator 枚举逻辑做独立正确性审（对照规则逐设施抽样穷举比对）；对 candidate_placements/mandatory_exact_instances 做独立重生成+逐 pose 语义校验（footprint/port/power coverage/互斥）并纳入 release gate；把『pose 池完整性』明确写进 PROJECT_LOCK 的 NAMED-TCB 清单，owner clean-review 必须覆盖它。
VERDICT: CONFIRMED | severity_opinion: major
verify notes: 逐条核对结果（全部只读核实）：

【坐实的前提】
1. pin 只有 hash/size、无语义校验 — 坐实。src/search/certified_artifact_contract.py:29-47 确实只钉 5 个工件的 sha256（LOCKED_EXACT_ARTIFACT_SHA256:37-43）+ size（LOCKED_EXACT_ARTIFACT_SIZE_BYTES:45-47，注意 size 只钉 candidate_placements 一个，断言说"sha256+size"略有夸张）；locked_exact_artifact_contract_violation（:171-208）只做 hash 字符串比对（:182-187）和字节数比对（:202-207），零 pose/footprint/port/power 语义检查。
2. 45.8MB 文件是 facility_pools 唯一来源 — 坐实。src/models/master_model.py:2256-2257（load_project_data 直接 `_load_json(data_dir / "candidate_placements.json")` → `facility_pools`）；快照变体 load_project_data_from_texts 同源（:2281-2282）。
3. I1 复验消费同一份 pools — 坐实且比断言更直接：src/search/benders_loop.py:7538-7541 调 reverify_whole_layout_infeasibility 时传的是 `facility_pools=self.master.facility_pools`——不是重读磁盘，而是 master 用过的同一 in-memory 对象；reverifier 内部只做 dict 深拷贝（independent_infeasibility_reverifier.py:155-164），独立性仅在求解器层面，输入完全同源。
4. CI 重生成只证确定性 — 坐实。.github/workflows/project_foundation.yml:85-91 是"跑 placement_generator.py 重生成 → check_external_artifacts.py --require candidate_placements"；scripts/check_external_artifacts.py:33 的 verify_artifact 只验 manifest 契约（存在性/hash），生成器若系统性少枚举，重生成出的字节照样命中 pin、照样过。
5. PROJECT_LOCK 自认 named TCB — 坐实。PROJECT_LOCK.md:92-98 原文："其余 candidate geometry 字节是命名 TCB……前提是 generation-time _validate_template_geometry_contract fail-closed 且 artifact hash-pin 锁住字节……它不是 P1.2 已由代码自动证明的定理"。
6. README 把它列为开放问题 — 实质坐实但引用坐标错：正确位置是 README.md:240（§9 开放问题 #5 "Candidate geometry is a hash-pinned TCB — the current theorem does not re-derive all candidate geometry from canonical rules"）和 :244（#9 named TCB 清单含 "frozen-geometry pose bytes"）、另见 :98-99。断言引的 :1679-1688 是第 5 章的另一份开放问题清单，那里只有 checker 自证边界（:1685-1686）和文件缺失坑（:1688），没有 geometry TCB 这条。

【有出入 / 需修正的细节】
a. "canonical_rules 语义从未独立验证"略有夸张：PROJECT_LOCK.md:91 明说 power 覆盖"游戏规则确认为 12×12 方形"、:96-98 说规则→几何映射是"owner 确认的规格事实"——即存在过人工对照游戏的确认，缺的是自动化/可复核的独立验证。方向对、措辞过强。
b. "谁也发现不了"对 footprint 错误类略过强：solve-time 存在两类独立重导（exact_coordinate_master.py:1043-1070 对实心矩形重算 occupied_cells==bbox；:5141-5175 重算 power pole 12×12 覆盖，PROJECT_LOCK.md:87-91 列明），外加生成时 _validate_template_geometry_contract fail-closed（placement_generator.py:161-277 实测存在，含 dims/rotatable/port_rule/radius=5/placement_rule 硬校验）。但这些只抓"与模板自身不一致"类错误——模板 dims 本身写错或规则理解错，重算用的还是同一模板，抓不到。
c. 断言最硬的核心——pose 枚举完整性（漏枚举 → 可行集系统性低估 → false-INFEASIBLE → lex 最优对真实游戏不成立）——确实无任何机制覆盖：hash 门、生成时契约、master 重导、I1、sink replay 全部检"已有 pose 对不对"，没有任何东西检"该有的 pose 在不在"。这一点无出入。

【严重度独立评估】
维持 major，不升 critical、不降 minor。理由：(1) 风险真实且是纯人工信任边界——枚举完整性零自动检查、全链同源消费（benders_loop.py:7540 直传 master pools 是铁证）；输入错则 CERTIFIED 是"证对了错定理"，对"结果须对真实游戏成立"的最终目标是实质威胁。(2) 但不够 critical：这是项目自己已命名、已文档化、刻意划界的 TCB（PROJECT_LOCK.md:92-98、README.md:240/:244），不是隐藏缺陷；关键规则映射有 owner 对照游戏的人工确认；且它不机械性阻塞管线（产出 CERTIFIED 和关 P1.2 门的更直接瓶颈是 supervisor 生产入口缺口 + owner 手动门）。(3) 断言的修复方向里"把 pose 池完整性写进 NAMED-TCB 清单"有一半已成立（geometry 字节已在清单），但"枚举完整性/exhaustiveness"作为独立轴确实未被显式命名，这半条建议有效。

## [major] votes=2 | 文档-代码-分支状态系统性漂移，而本项目的最终兜底恰恰是『显眼 diff + 人工审』——文档失真直接侵蚀人审兜底与交接能力
lenses: process
evidence: 项目 CLAUDE.md 记 pr2-5 为 round-18/+8700 行，实测已是 round-19 5ff31ac/+15266 行/26 commits，checker 计数 59/64-82 在分支上已是 60/65-83；README 自认多处不一致：preflight exit-2 文档谎言（实测 :117-121 只有 0/1）、strict_json 函数名两版分歧、三 runtime 文件 blob OID 不一致；README 全部 commit 锚引用原机 hash 且 git cat-file 实测均不可解析（历史重建后争议无史料仲裁）；NAV_MAP.md 仅 56 行、不含 pr2_l0_micro_verifier_core/certified_artifact_contract 等实际认证链模块；PROJECT_LOCK §1A 行号锚与实际差约 100 行。
why: owner 已裁定接受三类残余不做数学消除，兜底是『钉字节+显眼 diff+人工 clean-review』——人审是 TCB 的一部分。外审 GPT Pro 和任何接手者都依赖文档给出正确的行号锚、函数名、分支状态；漂移会让审计核对错位、浪费审计信用、把真问题误判为文档错误，最坏情况是按过期 handoff 在 release 边界上做错判断（把未合分支当 main、把旧 clean 当当前 clean）。
fix: 把『合并/reseal 后同步更新 CLAUDE.md 计数与 NAV_MAP』写进 reseal runbook 收尾清单；行号锚改为符号锚+可机器复核的 checker 自验输出断言；新增由只读命令生成、人工确认的 CURRENT_STATE.md/release-status manifest（当前 HEAD/分支/gate 状态/未合差异/已知过期段落），README 保持史料、不再承载当前门状态；pr2-5 合入时一次性清 README:1677-1690 的已知漂移清单。
VERDICT: PARTLY | severity_opinion: major
verify notes: 逐条核查结果（全部只读，main 工作树 + git 对象）：

【坐实的前提（占绝大多数）】
1. pr2-5 分支状态漂移：坐实。分支 tip 实测 `5ff31ac "harden(close-kernel): round-19 三块结构门补全 + 统一 reseal"`，`git rev-list --count main..pr2-5` = 26 commits，`git diff --shortstat main...pr2-5`（merge-base 30f9ee2 三点）= 14 files, **15266 insertions** —— 与断言的 "+15266/26 commits/round-19" 逐字吻合。checker 单文件两点 diff = +9198/-102。而项目 CLAUDE.md 仍写 "round-18，checker 相对 main +8700 行硬化"，确已过期。
2. checker 计数漂移：大部分坐实。sink 数来自 `data/proof_obligations/p1_2_proof_obligations.json` 的 `close_kernel_contract.sink_files`：main=59，分支=60（git show 两分支 JSON 实测）；allowlist：main=82，分支=83（同法实测）。main 基线还实跑了 `scripts/check_strong_status_write_allowlist.py`，输出 "64 registered AST node(s), 82 allowlist entry(ies)" 吻合。唯"分支上 AST nodes=65"无法不切分支静态验证（该数是运行时 AST 扫描产物），但与 allowlist +1 一致、判为可信但未直接坐实。
3. preflight exit-2 文档谎言：坐实。`scripts/preflight_gate.py:21` docstring 写 "2 = 通过但有警告"，但 `GateResult.exit_code`（`scripts/preflight_gate.py:117-121`）只有 `1`/`0` 两个返回分支。README:1680 自认此不一致。
4. strict_json 函数名两版分歧：坐实。README:1496 引用源码中不存在的 `load_strict_json_file()`/`load_strict_json_path()`，README:1501 自认分歧；实际公开名在 `src/io/strict_json.py:51/:70/:76`（`loads_strict_json`/`load_strict_json`/`load_strict_json_exact_decimal`）。
5. 三 runtime 文件 blob OID 两版不一致：README:1683 确有此自认条目（⚠ 标注，要求终审 `git ls-tree` 复核）——断言引用属实（是 README 自曝，非隐藏）。
6. README 原机 commit hash 不可解析：坐实。抽样 6 个（b35e5f9/9bbb3a6/099f5a3/c96a601/2ca6864/592ea13）`git cat-file -t` 全部 "Not a valid object name"。
7. NAV_MAP.md 覆盖缺口：坐实。实测 56 行（Measure-Object 口径，含空行 67 行），全文不含 `pr2_l0_micro_verifier_core`/`pr2_l0_true_verifier_child`/`certified_artifact_contract`/`candidate_proof_replay`/`exact_parallel_scheduler` 任何一个认证链模块名。

【有出入的前提】
8. "PROJECT_LOCK §1A 行号锚与实际差约 100 行"：**以偏概全**。实测抽查 §1A 全部约 20 个锚点：只有 binding_subproblem 一组整体漂移 +117 行（LOCK 记 `:930/:976/:1022` 三个 AddExactlyOne，实际在 `src/models/binding_subproblem.py:1047/:1093/:1139`），另 `benders_loop.py:5191 diagnostic_flow_status` 小幅错位（该行现为 power placement 调用，diagnostic_flow_status 存储在 :5178/:5206 邻域）；而其余多数锚**仍精确命中**：`exact_coordinate_master.py:3444/:3744-3748/:2717/:2796/:6284/:6336/:1557/:5141/:5827`、`flow_subproblem.py:149/:159`、`routing_subproblem.py:1623-1719/:1058`、`exact_campaign.py:1131-1157`（落在 `_validate_terminal_solution_against_project`（1107-1355）函数体内）全部对得上。"§1A 锚差约 100 行"作为整体陈述夸大了，准确说法是"谓词(4) binding 一组锚漂移 +117 行，其余基本仍准"。

【严重度独立评估】
断言遗漏了一个削弱自身的重要事实：所列漂移中相当一部分是**文档自曝、非隐藏**——README:1677-1690 整节就是"诚实收尾"清单（exit-2、blob OID、strict_json 分歧均在内），CLAUDE.md 自己就警告 NAV_MAP 不全并列出了缺失模块名、也警告原机 hash 不可解析只能当叙事线索。已标记的漂移对人审的侵蚀远小于未标记的。真正**未标记**的漂移是三处：① CLAUDE.md 的 round-18/+8700（实际 round-19/+15266/26 commits，且分支上 checker 计数已变 60/83）；② PROJECT_LOCK §1A 谓词(4) binding 锚 +117 行——这最要命，因为 PROJECT_LOCK 是最高权威、binding exact-count 恰是六谓词核心之一，外审按 :930 去核对会看到无关代码；③ preflight docstring 本体未修（虽 README 提了）。考虑到 owner 已裁定三类残余的最终兜底就是"钉字节+显眼 diff+人工 clean-review"（README:1685-1686 亦确认 checker 有自证边界、人审是 TCB），最高权威文档里认证谓词的锚点错位 + 无史料仲裁（hash 全断链）确实直接侵蚀这条兜底，major 判定成立、未见夸大（也不到 critical：漂移不机械阻塞任何 gate，机器门 checker/preflight 不依赖文档行号，且分支明确标注未合入、误当 main 的风险有 CLAUDE.md 分支说明兜着）。但 evidence 中"§1A 锚差约 100 行"的整体化表述本身就是它批评的那类失真，应修正为具体指认 binding 组。

