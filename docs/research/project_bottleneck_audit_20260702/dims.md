# DIM history — 历史与决策叙事
## fable summary
项目演进可分六阶段。(一)算法建设期(2026-03~05,仅存于 README/CHANGELOG 史料,本仓库 git 无此段):建 certified_exact/exploratory 双轨、锁定目标 max_lex(area,min_side)、坐标 master+binding/routing/flow 子问题、并行调度器;HiGHS/SCIP 重写试过判死路;05-22 B Design v2 冻结 F1-F9 cut 生命周期并锁"宁可漏割不可错割"(FP=0),但至今未接入生产。(二)v28→V99 soundness 重置阶梯(05~06 中):约 70+ 轮外审几乎每轮找到真洞并把 owner clean-review 计数清零,最终产物是"仓库不自动计数、owner 仓库外手动 3 连 clean 才能关门"的手动闸。(三)P1.2-FIX(06-19~23):C3 三源内核审判定"当前不能建立完整 soundness 定理";修 witness-split/OPEN-GATE/PYC/I1 独立复验;capsule 根治方案被第 5 轮外审用同进程 monkeypatch PoC 推翻,逼出 supervisor L0/L1 重做。(四)PR1(06-26):producer(只能提案)/supervisor_seal(唯一 durable CERTIFIED 铸造)/publisher(唯一发布口)三权分立落地。(五)PR2(进行中):#8/#9a 已合 main;#5 close-kernel 第二道门在分支上打了 19 轮——黑名单被证不收敛,转白名单/closed-world/pin-all,owner 接受 F/checker-self/A4 三类残余靠"显眼 diff+人工审"兜底;本仓库分支顶端是 README 未记载的 round-19(第 12 轮外审挖出"护门的父锚和 witness 直呼文件自己没进门"),外审包已 staged 等 owner 跑第 13 轮。(六)交付副本期(07-02):git 历史重建、README 定为 handoff 史料。贯穿主题:对抗审总能再剥一层信任洋葱,"审到零发现"不是收敛判据;main.py 至今止于 CANDIDATE_PROPOSED,release 被 owner 仓库外手动门卡死。
### key_facts
- 本仓库是 git 历史重建的交付副本:最早 commit 79afc8f (2026-06-16 "Initial commit"),README 引用的原机 hash(9bbb3a6/b35e5f9 等)经实测 `git cat-file -t` 均不可解析,`git remote -v` 为空(无 remote)。
- 2026-03~06 的早期史(双轨形成、目标 max_lex(area,min_side) 锁定、单基地收窄到 valley4_protocol_core 70×70、HiGHS/SCIP 重写判死路、B Design v2 冻结 F1-F9 且锁 FP=0)只存在于 README 第 1 章 §8 与 CHANGELOG(如 2026-05-16 段 L1-L11 "9 死路"),本仓库 git 无对应 commit。
- 认证三权分立(PR1,2026-06-26 落地)已在源码坐实:producer 只提交 CANDIDATE_PROPOSED;supervisor_seal 是唯一 durable CERTIFIED mint(src/search/exact_campaign.py:3566);mark_campaign_stopped(status="CERTIFIED") 直接 raise(exact_campaign.py:3601/3610,实测 grep);发布唯一入口与 F-CAM-PR1-01..04 见 PROJECT_LOCK.md:252-266。
- exact/exploratory 隔离是硬编码:exploratory 路径命中 RUN_STATUS_CERTIFIED 会被降级为 RUN_STATUS_UNPROVEN(src/search/outer_search.py:2892-2909,实测读源)。
- F1-F9 cut lifecycle 从未接入生产:src/cuts/lifecycle.py:1121-1126 step_8_apply_to_master 仍 raise NotImplementedError(实测读源);PROJECT_LOCK.md:108-112 (B-2) 明言吞吐进 certified 需新范式。
- release 手动门现状:data/review_gates/phase_1_2_spike_close.json:5 status="blocked_manual_review_count"、:11 counting_authority="owner_manual_count_outside_repo"、:24 p1_2_close_status="not_closed"、:34 next_phase_entry.allowed=false(实测读文件);PROJECT_LOCK.md:139-186 C5 done-condition 要求机器条件(含当前不存在的 supervisor 生产入口)+owner 手动条件同时满足。
- V28→V99 外审阶梯:约 70+ 个外审包几乎每轮找到真 soundness 洞并把 owner clean-streak 清零(README 第 2 章 §7.2,引 phase_1_2_spike_close.json:38-386 informational_history);V46-V50 因 "receipt/Git 权威本身成攻击面" 把 clean 计数移出仓库。
- capsule 架构 2026-06-23 被第 5 轮外审推翻:同进程 monkeypatch _invoke_isolated_capsule 伪造应答即可 mint publishable=True,nonce 只防重放不证来源(README 第 3 章 §5.2);同日设计会否决单 supervisor(会把 CP-SAT 拖进 TCB)改 L0/L1 两层+受控 loader(README 第 3 章 §5.3)。
- PR2 #5 close-kernel saga:分支 pr2-5-domain-frontier-gate 领先 main 26 commit(git rev-list --count 实测),从 22ea475(declare_mode 缺口修复,durable seal 路径上穷尽校验曾是死代码)一路到 28b9b5e(round-18,A4 动态反射裁定为残余);元教训=对图灵完备/反射面逐形态黑名单永不收敛,round-9 "123/123 收敛" 与 round-14 白名单均被后续外审证伪(README 第 4 章 §5.5)。
- README 未记载的最新进展:分支顶端有 round-19 commit 5ff31ac(2026-07-02 22:29,git show 实测)——第 12 轮 GPT Pro 外审(pr2-13)收敛到共同根因 "语义门只覆盖 3 个 runtime 文件,保护它们的父锚 certified_artifact_contract.py 和承载 witness 直呼的 certified_frontier.py/benders_loop.py 自身没进门",round-19 补 Group A(父锚自封装)/B(checker 自完整性 5 洞)/C(witness 静态重绑)+统一 reseal;README 第 6 章还停在 "round-18 等第 12 轮外审",已过时。
- round-19 后状态:cc_memory_vnext/cards/relay-review-clipboard-staging.md:41 与 guardrail-delegate-adversarial-reads.md:58-60 表明 round-19 外审包已 staged 等 owner 跑(WAITING_EXTERNAL,即第 13 轮 relay),且 main 分支 07-02 当天连发 4 条外审 relay 纪律的记忆卡(git log main 实测)。
- 三类 owner 裁定接受的残余(非数学消除):F(import-time 执行完整性,单列 #5-F 专线)、checker-self(不能递归自证)、A4 动态反射重绑;共同兜底=source-sha 逐字节钉死→改动必留显眼 diff→人工 clean-review(README 第 4 章 §7,owner 2026-07-01/07-02 裁定)。
- topology-opt 分支已是 main 的祖先(git merge-base --is-ancestor 实测),内容为 diagnostic-only 未接线的拓扑 hint planner(commit 26931e8/8894bc7),不影响认证边界。
- PR2 剩余项与推荐序:#5(round-19 等外审)→#2/#3(loader/read-once)→#1(最小 TCB 闭包,含 #5-F)→#9b/#9c(OS 写隔离/原生 TOCTOU)→#7(certify 生产入口=go-live 最后通电,刻意最后做)(README 第 4 章 §2/§10)。
### risks
- README/CLAUDE.md 的 "round-18 等第 12 轮外审、结构 BLOCK 清零" 叙事已被 round-19(5ff31ac)推翻——第 12 轮外审又挖出结构性根因,这是收敛判断第三次被证伪(round-9、round-14 之后);任何 "close-kernel 已收敛" 的断言都不可当终态,直接影响 #5 何时能合 main、进而影响后续 PR2 全链排期(git show 5ff31ac 实测)。
- 通向最终目标的操作链缺口仍物理存在:全仓无生产入口调用 supervisor_seal(PR2 #7 刻意最后通电),main.py 止于 CANDIDATE_PROPOSED——"端到端产出并公开发布 CERTIFIED" 目前不可达,且 #7 之前还排着 #1/#9b/#9c 三个 huge 级项(PROJECT_LOCK.md:130-137;README 第 4 章 §2)。
- release 关闭依赖仓库外不可见状态:owner 手动 clean-review 计数(需 3 连 clean)在仓库外,v99 锚是时间点快照、post-v99 全部改动(PR1/PR2)都需 fresh reseal 才能进入 close claim(phase_1_2_spike_close.json:7/:30);交付副本上无法评估离关门还有多远。
- 算法核心欠正面审是两版独立调查共同判定的最大盲区:子问题 CP-SAT 编码忠实性从未被逐约束审,若 routing/binding 模型多一条错误约束会自报 INFEASIBLE 剪掉真最优、I1 复验器(同编码)抓不到→false-CERTIFIED optimality,而 19 轮 close-kernel 硬化全在护发布链、完全没碰这层(README 第 6 章盲点 E)。
- dependency-floor manifest 仍是 deploy-pending 占位(GPT sandbox Linux 字节),生产前必须在 CachyOS+Py3.13 重生成+审+重钉,本机 Windows/WSL 做不了——是生产跑之前的硬前置(README 第 4 章 §4 Deploy-TODO;p1_2_proof_obligations.json manifest_provenance_status)。
- ④b sink-replay root-cure 的无缓存全量 re-replay 性能残留未修:168h 生产跑可能烧光预算退 UNKNOWN、出不了 CERTIFIED,perf 会议裁定的缓存方案 "真 168h 生产前必做,至今没做"(README 第 3 章 §2.1)。
- 历史重建造成证据链断裂:README 所有 commit 级证据在本仓库不可 git show 复核,若未来发生 "文档说 X、代码是 Y" 争议,只能以当前源码+PROJECT_LOCK 为准重新自查,史料的纠错能力已经降级(CLAUDE.md 权威顺序段;实测 hash 不可解析)。
### open_questions
- round-19 之后的 triage 结论查不到:第 13 轮外审(round-19 包)已 staged 等 owner 跑,但本仓库无原机器 harness RESUME 锚(p1-2-resume-state-20260621.md 在原机器用户目录),无法确认外审是否已回传、是否还有 round-20。
- README 记载的原机 commit(round 链、blob OID 2f55bc65/af276679/da326456、diff stat)与本仓库重建 hash 无对应表,只能靠 commit message 顺序对齐,无法机械复核 "README 说的 round-N = 本仓库某 commit" 的每一处细节。
- README 第 5 章两版史料对 "3 个 runtime 文件 blob OID" 有未裁定分歧(2f55bc65 归属 exact_campaign.py 还是 micro_verifier_core),需在本副本 git ls-tree 重核——本次未展开核。
- 第 11/12 轮外审报告原文在原机器仓库外目录(C:\22957\download\...、C:\Users\22957\pr2_pkg\),未随交付副本迁入,外审原话不可复核;owner 仓库外 clean-review 计数当前进度(0/3~3/3)完全不可见。
- cc_memory/memory.db 迁移完整性未验证(git status 显示 vnext 卡有未提交修改);README 引用的 ~170 条 cc_memory 史料条目是否全部随迁、id 是否仍可解析,未逐条核。

## codex summary
项目先把目标收敛为单一 valley4_protocol_core 70×70、266 mandatory、max_lex(area,min_side) 的 certified-exact 空矩形问题，并把 exploratory 严格隔离：经验 cap、flow 诊断、viewer/serializer 都不得进证明链。随后形成 Benders/CP-SAT 活路径与 B Design v2 cut 体系，但 cut Step8 尚未接入生产 master。2026-06 初到中旬，50桩+10箱固定 cap 被纠正为 residual/required optional；C3 审查确认当前只证布局/连通/供电等 6 谓词，不证吞吐，且 I1 nogood、witness-split、同进程 proof authority 都是实洞。PR1 解决的是发布权威边界：producer 只能写 CANDIDATE_PROPOSED，supervisor_seal() 才能铸 durable CERTIFIED，中央 publisher 才能公开发布，并修掉一批 stale/事务/伪 CERTIFIED 发布漏洞；但 PR1 没有生产 supervisor 入口。PR2 试图缩小 TCB：从 capsule 架构被 monkeypatch/TOCTOU 推翻后，转向 L0/L1、受控 loader、dependency floor、close-kernel 第二道结构门。PR2 #5 由 declare_mode/last_stop_reason 漏设导致 durable seal 跳过全前沿穷尽校验，之后演化成 19 轮 AST/source-sha/closed-world 硬化；黑名单逐步让位于白名单和显眼 diff 残余。当前事实是：main 没有公开 CERTIFIED 结果，P1.2 owner 手动门仍 blocked，PR2 round-19 分支未合入 main，最终发布仍未闭合。

（以上为独立第二读者 Codex 的调查结论，方法为只读通读 README.md 全六章、PROJECT_LOCK.md、CLAUDE.md，配合源码定位与只读 git 实测（git log/diff/branch/grep），未运行 main.py、pytest、preflight 或任何求解/写状态命令。)
### key_facts
- 权威顺序是 PROJECT_LOCK.md 高于 README，README 是史料不是命令，且本交付副本的 README 旧 hash 不可 git show，需以当前源码/git 实测为准（CLAUDE.md:11-15）。
- 当前实测分支为 main c59a65f、pr2-5-domain-frontier-gate 5ff31ac round-19、topology-opt 26931e8，且 git remote -v 无输出；这比 README 里 round-18/b35e5f9/9bbb3a6 叙事更新。
- 活跃认证范围只覆盖 valley4_protocol_core 70×70，其他基地是 future_scope，不能外推到认证结论（README.md:49-57; PROJECT_LOCK.md:243-248）。
- exact 目标是 max_lex(area,min_side)，min_side>=6 是 admissibility 不是 tie-break，exact 模式无硬“50 power poles + 10 protocol storage boxes”上限（PROJECT_LOCK.md:10-17; README.md:53-55）。
- CERTIFIED 只证明 6 个 gating 谓词加 lex 最优；routing 只证离散连通，不证吞吐/带宽/离散容量流（PROJECT_LOCK.md:31-63, PROJECT_LOCK.md:100-120）。
- 项目早期采用 Benders/CP-SAT 活路径，同时把 HiGHS/SCIP master rewrite 作为死路保留参考，后续切到单 active base 与 canonical rules（README.md:213-218）。
- B Design v2 把 cut 做成持久化对象并锁 FP=0，但生产集成仍未完成：step_8_apply_to_master 仍 NotImplementedError（README.md:218；src/cuts/lifecycle.py:15-17, 1121-1126）。
- C3 审查的关键结论是当前活路径不能声称完整 soundness theorem，I1 nogood 需独立复验，吞吐是 out-of-scope overclaim，供电覆盖已在当前命题内（README.md:728-739）。
- sink-replay 根治方向是不信同进程对象/closure/freshness，而在隔离解释器重放强状态；源码明确 candidate record 只是 claim，replay 拒绝则 demote 为 UNPROVEN（candidate_proof_replay.py:1-15, 564-608）。
- PR1 的三权分立已进入 lock：producer 只提 proposal，ExactCampaign.supervisor_seal() 是唯一 durable mint，publish_verified_certified_delivery_surface() 是唯一公开 publisher（PROJECT_LOCK.md:252-266）。
- 当前 main.py 只导入并调用 run_outer_search，不调用 seal/publish；outer search 终局返回 CANDIDATE_PROPOSED_STATUS（main.py:67-69；outer_search.py:855-887, 1969）。
- 负向实测：git grep -n -F ".supervisor_seal(" -- src scripts main.py :(exclude)src/tests :(exclude)scripts/README.md 无匹配，说明当前生产代码没有 .supervisor_seal(...) 调用点。
- supervisor_seal() 源码会委托 PR2 L0，并且普通 mark_campaign_stopped(status="CERTIFIED") 与 unsupervised certified checkpoint save 都会 raise（exact_campaign.py:3541-3610, 3652-3661）。
- 发布器有 export 脚本调用点，但它只消费 sealed、disk-current campaign，且仍受 P1.2 open gate 阻断；这不是 supervisor 入口（scripts/export_industrial_planner_bundle.py:114-120；certified_surface.py:758-805）。
- P1.2 gate 文件当前是 status: blocked_manual_review_count，p1_2_close_status: not_closed，next_phase_entry.allowed: false，clean count 权威在仓库外（data/review_gates/phase_1_2_spike_close.json:5-36）。
- PR1 发布面 saga 的核心坑包括无门禁 canonical writer、非事务发布、stale public surface、checker 固化错误形状；最终 publisher 采用 stage→commit→verify→rollback 事务（README.md:868-905；certified_surface.py:847-878）。
- proof-obligation checker 自述只是 structural gate、not theorem prover，不认证 candidate 或 geometry，只封 proof-bearing authority surface 与 source hash drift（scripts/check_p1_2_proof_obligations.py:1-7, 4246-4253, 4337-4340）。
- PR2 的架构决策是放弃单 supervisor，改 L0/L1 与受控 loader；L0 core 自述 stdlib-only、拥有 proposal/checkpoint bytes 并写 certified transition，child 只做 domain verification 不拿写句柄（README.md:1058-1071；pr2_l0_micro_verifier_core.py:1-6；pr2_l0_true_verifier_child.py:1-7）。
- PR2 #5 的原始真洞是 child 只设 final_status=CERTIFIED、漏设 declare_mode/last_stop_reason，导致全前沿穷尽等终态校验死代码；最小修复是 durable seal 时补 strict/stop reason（README.md:1158-1163）。
- 当前 PR2 分支已到 round-19：git log --all --oneline -n 35 顶部为 5ff31ac ... round-19，git diff --shortstat main..pr2-5-domain-frontier-gate 为 70 files changed, 15355 insertions(+), 14461 deletions(-)，尚未合入 main。
- blank-slate review 曾发现默认生产路径上的真实 false-CERTIFIED 风险：boundary port precheck 假 INFEASIBLE、parallel scheduler worker crash sticky strong status 等，说明终端 validator 不能自动补救被污染的 per-candidate 强状态（PROJECT_LOCK.md:350-357）。
### risks
- 最终目标无法合法闭合的最大阻断是 P1.2 owner gate 仍 blocked，且仓库不得由 receipt/test/checker/internal seal 自动推导 closed（PROJECT_LOCK.md:179-185；data/review_gates/phase_1_2_spike_close.json:23-36）。
- 生产 supervisor 入口不存在，普通 main.py 只到 proposal，因此端到端“solve→seal→publish CERTIFIED”链还没通电（PROJECT_LOCK.md:148-154；main.py:67-69；outer_search.py:1969）。
- PR2 round-19 硬化仍在分支而非 main，发布前必须解决 main/branch 差异、CI/slow gate、合入后重新验证（git branch -vv 实测；git diff --shortstat main..pr2-5-domain-frontier-gate 实测）。
- close-kernel 是结构门，不是算法证明；算法核心、master 域编码、binding/routing 子问题忠实性仍不能因 checker 绿而自动视为 sound（README.md:691-708；scripts/check_p1_2_proof_obligations.py:4246-4253）。
- throughput/带宽不在 CERTIFIED 命题内，公开发布若写成“产线吞吐可行”会越权 overclaim（PROJECT_LOCK.md:53-63, 100-116）。
- PR2 dependency floor 当前源码注释标为 dev/CI placeholder，生产前需在 CachyOS Python 3.13 venv 重生成、审查、重 pin（pr2_l0_micro_verifier_core.py:37-46）。
- PR2 saga 已接受 F/import-time、A4 dynamic reflection、checker-self 等 conspicuous-edit/人工 clean-review 残余；这意味着最终发布仍依赖人工 review 纪律，不是纯机器闭包（README.md:1201-1212）。
- sink replay root-cure 当前历史记录承认性能残留：168h 生产跑可能因无缓存全量 re-replay 烧光预算变 UNKNOWN，影响产出 CERTIFIED 结果（README.md:720-726）。
- release snapshot immutability/archive policy 仍是 P1.2 done-condition 的未决项之一，仅从 mutable treeish 物化不满足条件（PROJECT_LOCK.md:176-177, 130-137）。
### open_questions
- round-19 5ff31ac 的外部审查状态未在 README 六章里更新，只能确认当前 git 顶部存在该 commit，不能确认它已 CLEAN。
- owner 仓库外 clean-review 计数不可从 repo 读出；当前只知道 repo gate 明确不记录也不计算该计数。
- PR2 分支合入 main 后哪些 source-sha / checker floor / dependency floor 需要重新 reseal，需在目标合并工作树上重新实测。
- C3 后算法核心是否已有一次等价深度的正面复审，本次只读调查未做完整模型/约束审计。
- 当前是否存在可恢复的真实 campaign checkpoint 与候选结果能走到 CERTIFIED，受只读/不跑求解限制，本次未验证运行产物。


# DIM cert-chain — 认证链与三权分立
## fable summary
这条认证链是严格的三权分立。第一环 producer（outer_search.py）：求解跑完全 frontier 后只能把结果落成 CANDIDATE_PROPOSED 提案——写 final_result、跑一遍 sink replay 和固定见证复验、存盘、再写一个含 checkpoint sha 的 proposal_ready marker，全程碰不到 CERTIFIED。第二环 supervisor_seal（exact_campaign.py:3566）：唯一能把 CERTIFIED 写进磁盘的口子，但它自己不干活，整体委托 pr2_l0_micro_verifier_core.run_l0_supervisor_seal——后者从磁盘（不信调用者内存）重读 marker 和 checkpoint、逐项校验绑定，再用 `-I -S -B -X pycache_prefix` 起一个隔离子进程（pr2_l0_true_verifier_child），在源码快照+依赖 sha 楼面限制的 import 环境里独立重跑 sink replay、固定见证、候选域重枚举和项目 precheck，digest 全对上后才在写锁内做写前复查、原子写、写后校验、失败回滚。第三环 publish_verified_certified_delivery_surface（certified_surface.py:758）：唯一公开发布器，stage→commit→verify→rollback 四段事务发布三件套，链上三次查 P1.2 owner 手动门，门文件当前是 blocked_manual_review_count，故发布必然 fail-closed。反绕过是硬编码的：mark_campaign_stopped 传 CERTIFIED 直接 raise；save() 检测三处未监督 CERTIFIED 声明并 raise。缺口核实：supervisor_seal 恰有 23 处调用、全在 src/tests；main.py 和生产 wrapper 均无 seal/publish 调用，跑 main.py 终点就是 CANDIDATE_PROPOSED。这是刻意留的 PR2 #7『最后通电』：地基（L0/L1 最小 TCB、#5 close-kernel 外审、占位的依赖楼面 manifest）未固前不接生产 mint。堵上它需要：按 PROJECT_LOCK done-condition 建一个从 proposal_ready marker 驱动的独立 supervisor 生产入口，先完成 PR2 #5 合入与 #2/#3/#1，在 CachyOS+Py3.13 重生成依赖楼面 manifest，同步更新结构 checker 的调用点登记并走 reseal 连锁——且即便全通，公开发布仍被 owner 手动门独立拦着。
### key_facts
- producer 只能落提案：outer_search.py:876/:901/:951 的 _build_certified_result 与 _commit_terminal_full_frontier_certified_result 一律写 CANDIDATE_PROPOSED，终局前还自跑 sink replay（outer_search.py:903-914）+ 固定见证投影（:921-936），最后写 proposal_ready marker（:954）
- proposal_ready marker 要求 final_status 必须是 CANDIDATE_PROPOSED 且含 checkpoint_sha256（exact_campaign.py:3434-3467）；supervisor 侧读取时会重算 sha、不信 producer 声明（pr2_l0_micro_verifier_core.py:216-224）
- 反绕过硬守卫一：mark_campaign_stopped(status='CERTIFIED') 直接 raise 'CERTIFIED campaign stop must be minted by supervisor_seal'（exact_campaign.py:3608-3610）
- 反绕过硬守卫二：save() 对 unsupervised CERTIFIED claim raise（exact_campaign.py:3658-3661），检测点覆盖三处——final_status、final_result.search_status、last_stop_reason.status（exact_campaign.py:2564-2579）
- supervisor_seal 本体不写任何东西：只校验 campaign_instance_id 后整体委托 run_l0_supervisor_seal，verdict != SEALED 即 raise，成功后从磁盘字节重载 state（exact_campaign.py:3566-3599）
- run_l0_supervisor_seal 是唯一 durable CERTIFIED 写入者：从磁盘读 marker+checkpoint、校验绑定后 spawn 隔离子进程（python -I -S -B -X pycache_prefix，snapshot 源码目录里跑，pr2_l0_micro_verifier_core.py:163-181），mint 写在 checkpoint 写锁内做写前 marker/sha 复查（:325-340）+ 写后字节相等与 postwrite 校验、失败回滚原字节（:341-360）
- 隔离子进程 pr2_l0_true_verifier_child._verify_supervisor_domain 独立重推整个 domain：重跑候选记录 sink replay、fixed-witness 复验、按 candidate_generation 重新枚举候选域并重建 terminal_frontier_evidence、项目级 precheck、三个 digest 与父进程请求逐一比对（pr2_l0_true_verifier_child.py:346-450）；child 的 import 被 stdlib-only finder + 第三方 sha256 逐文件 rehash floor 限制（:60-154）
- publish_verified_certified_delivery_surface 是唯一公开发布器，stage→commit→verify→rollback 四段事务，commit 前还要求磁盘 campaign 字节未变（certified_surface.py:758-878，字节比对 :830-832）；P1.2 open-gate 在链上被查 3 次（evaluate :416、publish staging 前 :802、commit 前 :833）
- resolve_p1_2_publish_open_gate 把 gate 路径写死为 data/review_gates/phase_1_2_spike_close.json，唯一放行形态是 status=='closed_manual_owner_decision' 且 next_phase_entry.allowed==true 且 owner_manual_decision.p1_3b_entry_allowed==true，缺失/畸形/symlink/异常一律视为 open 阻断（certified_surface.py:497-546）；该文件当前实测 status='blocked_manual_review_count'、p1_2_close_status='not_closed'（data/review_gates/phase_1_2_spike_close.json）
- PR2 #7 缺口实测坐实：grep '.supervisor_seal(' 在 src/tests 下恰 23 处调用，src/scripts/main.py 非测试命中仅函数定义本身与其 L0 委托；main.py:304-329 只打印 status（certified 路径终点返回 CANDIDATE_PROPOSED），生产 wrapper（run_campaign_linux.sh / run_prod_*.ps1）grep 无 supervisor_seal/proposal_ready 任何引用
- 缺口是刻意的：README.md:391 记 2026-06-23 设计评审发现、排为 PR2 task #7『go-live 最后通电』，理由是 L0 verification TCB 证明 sound 前接生产 seal = 在不牢地基上铸 CERTIFIED；PROJECT_LOCK.md done-condition 明文『受支持的生产命令/launcher 必须从 proposal-ready marker 驱动独立 supervisor；当前仓库尚无该入口』（PROJECT_LOCK.md §C，约 :157）
- 结构 checker 把发布器直接调用点钉死为恰 2 个（certified_surface.py::save_certified_final_solution_and_blueprint 与 scripts/export_industrial_planner_bundle.py::main），任何新生产 caller 会报 'unsealed production caller'（scripts/check_p1_2_proof_obligations.py:1638-1658）；supervisor_seal 内部形状也被 AST 钉住（必须委托 run_l0_supervisor_seal、禁止 caller authority 参数，:2505-2529）——接 #7 必须同步改 checker 登记并走 reseal 连锁
- L0 依赖楼面 manifest 是 deploy-pending 占位：data/proof_obligations/pr2_dependency_floor_manifest.json（574,082 字节），p1_2_proof_obligations.json 里 manifest_provenance_status='deploy_pending_placeholder_regenerate_on_production_cachyos_py313'，生产 seal 前必须在 CachyOS+Py3.13 重生成重钉（git 实测 grep 确认）
- exploratory 路径的 RUN_STATUS_CERTIFIED 被静默降级为 RUN_STATUS_UNPROVEN 且只标 diagnostic（outer_search.py:2892-2909），铁律隔离在代码里是硬的
### risks
- 接通 #7 也到不了终点：publish 三查的 owner gate 当前是 blocked_manual_review_count，放行需要 gate 文件被 owner 改写成含 owner_manual_decision 等当前根本不存在字段的 closed 形态（certified_surface.py:497-546 + gate JSON 实测）——最终目标里『P1.2 手动门合法关闭』完全在仓库外的 owner clean-review 计数手里，仓库刻意不推导
- 生产 mint 的信任地基未就绪：依赖楼面 manifest 是 GPT sandbox 生成的占位字节（deploy_pending_placeholder_regenerate_on_production_cachyos_py313），mutation_policy 为 dependency_floor_drift_reopens_p1_2_close_claim；且原开发机（WSL/Ubuntu）与本机（Windows）都生成不了 CachyOS/Py3.13 canonical 版（README.md:562）
- PR2 前置链条整条未完且顺序在 #7 之前：#5 close-kernel（+8700 行 checker 硬化）还在未合入分支 pr2-5-domain-frontier-gate 等第 12 轮外审，#2/#3/#1(含图灵完备不收敛的 #5-F)/#9b/#9c 全开放（README.md:603）——若在 main 上直接接 #7 会绕开分支上的硬化，属地基未固先通电
- 接 #7 本身会触发结构门连锁：新 caller 会被 check_p1_2_proof_obligations 的发布器调用点 allowlist 报错（scripts/check_p1_2_proof_obligations.py:1649），需改 checker 登记 + 可能动 strong-status allowlist + 走完整 reseal ritual，而 reseal 在 Windows 上有 CRLF 写坏 pin 的已实测坑（CLAUDE.md §5）
- README/CHANGELOG 均为史料且 git 历史重建过、commit hash 全不可解析，PR2 剩余项在别的 branch/worktree 可能已有未同步进展（README.md:607）——按文档规划 #7 有基于过时状态动工的风险
- supervisor_seal 只接受 TERMINAL_FULL_FRONTIER_CERTIFIED_REASON（exact_campaign.py:3573-3574），生产入口必须等 campaign 真跑到全 frontier 穷尽的 CANDIDATE_PROPOSED 终态才有东西可 seal——多天级长跑 + resume 语义（F-CAM-R8 强降级）是 #7 之外另一条到达终点的工程瓶颈
### open_questions
- #7 生产入口的具体设计（CLI 形态、是否复用 proposal_ready marker 轮询、L1 的角色）没有在仓库内找到设计文档；README 引用的 RESUME 锚文件在仓库外（C:\Users\22957\.claude\projects\...\p1-2-resume-state-20260621.md），本次未读取核实
- check_strong_status_write_allowlist.py 的扫描范围是否会覆盖一个新的 scripts/ 下 certify 入口（即接 #7 时该 checker 是否也要加登记）未逐行核实
- main.py:328 的 `if status == 'CERTIFIED'` 可视化分支在当前返回路径下是否完全不可达（run_outer_search 全部 return 路径未逐一穷举）

## codex summary
我（Codex，独立第二读者）的结论：当前仓库的"认证三权分立"在源码层面基本成立，但端到端链路没有通电。outer_search.py 作为 producer 只能把 terminal frontier 成果降权落成 CANDIDATE_PROPOSED 和 proposal-ready marker；ExactCampaign.supervisor_seal() 是唯一 durable CERTIFIED mint，并把实质验证委托给 PR2 L0 micro verifier + 隔离子进程 child；certified_surface.py 是唯一公开发布器，且当前 P1.2 gate 仍处于阻塞状态。因此现在跑普通 main.py 不会产出已 seal、可公开发布的 CERTIFIED 结果，最多到 CANDIDATE_PROPOSED。

"PR2 #7 最后通电"缺口属实：用 git grep 核实，当前 main 分支上 `.supervisor_seal(` 的 23 个直接调用全部在 src/tests/；pr2-5-domain-frontier-gate 分支也没有把它接到 main.py、生产 wrapper 或 launcher（该分支相对 main 主要是 checker/obligations/contract/tests 的硬化，例如 check_p1_2_proof_obligations.py 一项就有约 +9300 行级别的增量，不涉及生产入口接线）。堵上这个缺口需要新增一个受支持、可审计的 production supervisor/certify 入口：从磁盘 proposal-ready marker/checkpoint bytes 开始驱动（而不是在 solver 进程内存里顺手 seal），调用 supervisor_seal()，再只经 publish_verified_certified_delivery_surface() 发布，同时保持 P1.2 owner gate 默认 fail-closed，并需同时完成 PROJECT_LOCK 列出的 PR2 TCB 收缩、snapshot immutability、archive policy、测试/gate、以及 owner 手动关闭计数等条件才算真正闭环。

链路细节：producer 的终态写入函数（outer_search.py:855-887、890-954）两次调用 mark_campaign_stopped(..., CANDIDATE_PROPOSED_STATUS)，随后写 proposal-ready marker；主循环在成功产出 terminal frontier 后返回 CANDIDATE_PROPOSED_STATUS（outer_search.py:1940-1969）。supervisor_seal()（exact_campaign.py:3470-3599）先要求 committed proposal authority（marker 校验、checkpoint sha 校验、strict JSON、final_status == CANDIDATE_PROPOSED、proposal run/campaign binding），然后只构造 L0SupervisorSealRequest 调用 run_l0_supervisor_seal(...)，成功后从磁盘重读 sealed state（自身不做实质验证，实质验证在隔离子进程里）。反绕过守卫是源码级硬拒绝：普通 mark_campaign_stopped(..., "CERTIFIED") 直接 raise（exact_campaign.py:2564-2580）；save() 前 _has_unsupervised_certified_checkpoint_claim() 会拒绝 final_status、final_result.search_status 或 last_stop_reason.status 中任何形式的 unsupervised CERTIFIED（exact_campaign.py:3601-3610、3652-3661）。L0 父进程（pr2_l0_micro_verifier_core.py:112-385）加载 canonical dependency floor、读 marker/checkpoint、做 proposal/proof binding 校验，把 payload 送进以 `python -I -S -B -X pycache_prefix=<fresh>` 启动的隔离子进程运行 pr2_l0_true_verifier_child；commit 前后复核 marker/checkpoint/current bytes，失败则 rollback。true verifier child 只做 domain verification、不写 checkpoint，安装 dependency floor 后验证 supervisor domain，返回 SEALED/domain_verified 或 fail-closed rejection（pr2_l0_true_verifier_child.py:1-7、35-57、166-206）。public publisher（certified_surface.py:758-878）从磁盘重读 campaign（不信任内存态），要求 project-bound terminal full-frontier evidence，检查 P1.2 gate 路径（不可由 caller 指定，缺失/畸形/非 owner-closed 都阻塞），stage 三个公开工件，commit 前复查 campaign 未变、commit 后再 verify，异常则 rollback/clear（commit/rollback helper 见 certified_surface.py:685-715、726-755；gate 检查见 497-546）。当前 gate 文件 data/review_gates/phase_1_2_spike_close.json 实际状态是 blocked_manual_review_count、p1_3b_entry_allowed=false、next_phase_entry.allowed=false，所以即便 seal 成功，公开发布仍会 fail-closed。NAV_MAP.md 的发布链图里也显式把 `[OPEN: production supervisor CLI/launcher]` 标在 proposal-ready marker 与 supervisor_seal() 之间（NAV_MAP.md:31-41），与源码结论一致。

方法学说明：核查全程只读，未跑 main.py、pytest、preflight 或任何求解/长耗时命令。过程中一次 git grep 正则写法有误（把一段 pattern 误当成 git revision）导致报错，未影响仓库状态；随后用普通 mark_campaign_stopped 调用面搜索和 CERTIFIED 过滤搜索补充核实了对应结论。另外验证了 README 里引用的旧 commit hash（b35e5f9、9bbb3a6）在当前仓库均不可 git show 解析，只作为叙事线索使用；pr2-5-domain-frontier-gate 分支当前实测 HEAD 是 5ff31ac，不是 README 史料里记录的 9bbb3a6，符合"git 历史被重建过"的提示。
### key_facts
- PROJECT_LOCK.md 明确当前 P1.2 为 OPEN/BLOCKED：无生产 supervisor CLI/launcher，main.py 终点仍是 CANDIDATE_PROPOSED，checker/test/internal seal 都不得改写为 release gate closure。出处：PROJECT_LOCK.md:130-137, 141-154, 181-185。
- PR1 三权定义是硬边界：producer 只能提交 CANDIDATE_PROPOSED；supervisor_seal() 是唯一 durable terminal CERTIFIED mint；publish_verified_certified_delivery_surface() 是唯一 certified 公开发布器；valid internal seal 也不足以构成 release。出处：PROJECT_LOCK.md:252-266。
- main.py 只导入并返回 run_outer_search(...)，随后只打印 status/result；status == "CERTIFIED" 分支只触发可视化，没有任何 seal/publish 调用。出处：main.py:47-88, 304-329。
- producer 终态写入函数两次调用 mark_campaign_stopped(..., status=CANDIDATE_PROPOSED_STATUS)，随后写 proposal-ready marker；主循环在成功 terminal frontier 后返回 CANDIDATE_PROPOSED_STATUS。出处：src/search/outer_search.py:855-887, 890-954, 1940-1969。
- supervisor_seal() 先要求 committed proposal authority（marker 校验、checkpoint sha 校验、strict JSON、final_status == CANDIDATE_PROPOSED、proposal run/campaign binding），然后只构造 L0SupervisorSealRequest 调 run_l0_supervisor_seal(...)，成功后从磁盘重读 sealed state。出处：src/search/exact_campaign.py:3470-3507, 3566-3599。
- 反绕过守卫是源码硬拒绝：普通 mark_campaign_stopped(..., "CERTIFIED") 直接 raise；save() 前 _has_unsupervised_certified_checkpoint_claim() 会拒绝 final_status、final_result.search_status 或 last_stop_reason.status 中的 unsupervised CERTIFIED。出处：src/search/exact_campaign.py:2564-2580, 3601-3610, 3652-3661。
- L0 请求没有 caller-selected dependency floor path；L0 父进程加载 canonical floor，读 marker/checkpoint，做 proposal/proof binding 校验，把 payload 送进 python -I -S -B -X pycache_prefix=<fresh> 隔离子进程；commit 前后复核 marker/checkpoint/current bytes，失败 rollback。出处：src/search/pr2_l0_micro_verifier_core.py:112-119, 163-180, 195-277, 293-385。
- true verifier child 只做 domain verification，不写 checkpoint；安装 dependency floor 后验证 supervisor domain，返回 SEALED/domain_verified 或 fail-closed rejection。出处：src/search/pr2_l0_true_verifier_child.py:1-7, 35-57, 166-206。
- public publisher 从磁盘重读 campaign，要求 project-bound terminal full-frontier evidence，检查 P1.2 gate，stage 三个 artifact，commit 前复查 campaign 未变，commit 后 verify，异常 rollback/clear。出处：src/search/certified_surface.py:758-878；commit/rollback helper：685-715, 726-755。
- publisher 的 gate 路径不可由 caller 指定；缺失、畸形、非 owner-closed 都阻塞。当前 gate 文件实际是 blocked_manual_review_count、p1_3b_entry_allowed=false、next_phase_entry.allowed=false。出处：src/search/certified_surface.py:497-546；data/review_gates/phase_1_2_spike_close.json:5, 23-36。
- NAV_MAP.md 的发布链把 [OPEN: production supervisor CLI/launcher] 标注在 proposal-ready marker 与 supervisor_seal() 之间，与源码结论一致。出处：NAV_MAP.md:31-41。
- #7 的关闭条件不是"让测试能调 seal"，而是需要受支持的 production supervisor entrypoint（明确 marker、失败码、幂等性、审计），完整发布闭合还要求 PR2 TCB/snapshot/archive/gate/test/owner 条件同时成立。出处：docs/项目说明/p1_2_supervisor_detailed_design.md:68-85；docs/项目说明/soundness_gap_roadmap.md:25-36；README.md:1297-1300。
- git grep 核实：当前 main 分支上 .supervisor_seal( 的直接调用（约23处）全部位于 src/tests/ 目录，无生产侧调用者。
- pr2-5-domain-frontier-gate 分支当前实测 HEAD 为 5ff31ac（非 README 史料里的旧 hash 9bbb3a6），该分支相较 main 的差异主要集中在 checker/obligations/contract/tests 硬化（如 check_p1_2_proof_obligations.py 增量约 +9300 行级别），未把 supervisor_seal() 接入 main.py 或生产入口。
- scripts/export_industrial_planner_bundle.py 会调用中央 publisher 刷新 canonical surface，但它不是 supervisor 入口——它要求已存在 publishable certified surface/blueprint 才能工作，失败时清理导出，因此不能补上 producer→seal 之间的缺口。
- README 里引用的旧 commit hash（b35e5f9、9bbb3a6）在当前仓库均无法用 git show 解析，符合项目说明中"git 历史被重建过"的提示，本次核查未依赖这些 hash 作为证据。
### risks
- 最大当前风险是误把 CANDIDATE_PROPOSED 当作 CERTIFIED：普通运行 main.py 最多产出 proposal，不会产生 durable seal 或可公开发布的证据面，任何声称"跑通 main.py 就等于拿到 CERTIFIED"的说法都不成立。
- 即使手动/测试方式调用 supervisor_seal() 成功拿到内部 seal，当前 owner gate（data/review_gates/phase_1_2_spike_close.json 的 blocked_manual_review_count）仍会使 public publisher fail-closed；不能把 internal seal 等同于 release closure。
- 堵上 #7 缺口如果被实现成"solver 进程末尾顺手 seal"（即在同一进程内存里直接调用而非独立入口从磁盘 marker/checkpoint 驱动），会破坏磁盘 proposal authority 边界和 producer/supervisor 的独立性，违反 PROJECT_LOCK 里三权分立的设计初衷。
- #7 若在 PR2 read-once/controlled-loader/TCB 收缩、snapshot immutability、archive policy 等条件尚未完成收口前就提前打通生产入口，会把尚未完成硬化的验证边界过早接成正式发布流程，存在把不成熟的验证链路暴露为生产能力的风险。
- pr2-5-domain-frontier-gate 分支（checker 更硬化、+8700~9300 行级别差异）当前未合入 main，也未接生产入口；若后续要补 #7 缺口，必须先明确基于哪个分支状态开工、统一目标分支，不能按 README 旧 hash 或过时假设推断当前代码状态。
### open_questions
- repo 内文档（p1_2_supervisor_detailed_design.md、soundness_gap_roadmap.md）虽给出了 #7 生产入口应满足的条件（marker、失败码、幂等性、审计等），但未找到该入口的具体设计落地时间表或负责人指派，是否已有排期不明。
- P1.2 owner gate 的 clean-review 计数按项目约定保存在仓库外，本次只读核查无法确认该计数当前实际数值或距离解除阻塞还差多少，只能确认 gate 文件当前状态为 blocked_manual_review_count。


# DIM solver-math — 求解管线与数学正确性
## fable summary
求解管线是一个按候选逐个证明的 LBBD(逻辑 Benders)架构:outer_search 把 70×70 网格上所有 (w,h)、w,h∈[6,70] 的"空矩形候选"排成按 (面积, 短边) 字典序降序的 frontier,对每个候选调 run_benders_for_ghost_rect 解一个可行性问题:CP-SAT 坐标 master(exact_coordinate_master,默认且唯一 certified 后端;pose_bool 后端被 env 守卫 pose_bool_master_not_certified 硬挡)先摆下 266 个 mandatory 设施 + 可选电桩/协议箱 + 恰好一个 ghost 矩形;master 出解后依次过两个真 gate 子问题——binding(端口绑定,槽数精确计数等式)和 routing(CP-SAT 可行 + 事后全局 source→sink 连通复验,拒绝只有局部支撑的假连通);全过才返回求解层 CERTIFIED。flow 子问题是 GLOP 连续 LP,只写 diagnostic_flow_status、从不落 cut,有契约测试把这一点锁死。CERTIFIED 恰好证明 6 个谓词(ghost 内无设施、两两不重叠、placement_rule、端口精确计数、路由连通、供电几何覆盖+终端独立复验)加 lex 最优性;吞吐/带宽/离散容量流、电网功率配平、机器身-身间隔全部明确 out-of-scope。lex 最优性不是 master 目标函数,而是 frontier 记账定理:全域每个候选要么 CERTIFIED 要么 INFEASIBLE 要么被单调支配剪枝(小尺寸 infeasible ⇒ 大尺寸 infeasible),terminal 证据可从候选记录全量重放校验且强状态必须先过隔离 sink replay。cut 的 soundness 靠三层:生产实际只用 nogood 族(placement-local 的 binding 域空/前格被堵 nogood,和 whole-layout 的 binding/routing 穷尽 nogood);whole-layout nogood 落 cut 前必须过 I1 独立复验(异构 CP-SAT profile 重建 binding 模型独立证 INFEASIBLE,不确认就不落 cut、候选升 UNKNOWN;phase-1 刻意只确认 binding 情形);预算耗尽永远不算穷尽证明。细粒度加速 cut(cell/patch-core/D2)全部 env 门控且被挡在 certified 外。src/cuts 的 F1-F9 是研究态框架:step_8_apply_to_master 仍 raise NotImplementedError、生产代码零 import——生产 master 没有任何 packing/密度类全局强化 cut,收敛只靠 nogood 逐层削,这是性能债不是正确性债。
### key_facts
- CERTIFIED 的 6 谓词外延与 lex 最优性定义在 PROJECT_LOCK.md §1A(31-98 行),B 块(100-120 行)明确吞吐/belt 带宽/离散容量流/机器身-身间隔 out-of-scope
- 谓词1/2 是 master 硬几何约束:src/models/exact_coordinate_master.py:3444 core AddNoOverlap2D;:3744 ghost anchor AddExactlyOne + :3745-3748 ghost+core 合一 AddNoOverlap2D;:3434-3437 还硬 raise 挡 EXACT_POWER_PLACEMENT_SUBPROBLEM 进 certified
- 谓词4 端口精确计数在 src/models/binding_subproblem.py:1047(每 instance 恰一 binding)、:1093/:1139(每 output/input 槽恰一 commodity 含 __unused__ 哨兵)、:1152/:1165(sum==required 等式);PROJECT_LOCK 引用的 930/976/1022/1035/1048 行号已漂移约 100 行,约束本体存在
- 谓词5 连通复验:src/models/routing_subproblem.py:1623-1719 _validate_selected_route_connectivity 重建选中 route-state 图证全局可达;:1821-1837 在 CP-SAT FEASIBLE 后强制调用,不连通则加 source-side connectivity cut 重解,budget 尽返回 TIMEOUT 而非 FEASIBLE
- routing FEASIBLE 后只返回求解层 RUN_STATUS_CERTIFIED(src/search/benders_loop.py:6973-6990),durable CERTIFIED 只能由 ExactCampaign.supervisor_seal() 铸造(src/search/exact_campaign.py:3566);mark_campaign_stopped(status=CERTIFIED) 直接 raise(:3609-3610),save() 检测 unsupervised CERTIFIED claim 亦 raise(:3658-3661)
- flow 仅诊断:src/models/flow_subproblem.py:1-11 docstring 明说 exact 路径不得把其失败写成 exact-safe cut,:148-163 GLOP 连续 LP + NumVar(0,∞);benders_loop.py:5222-5223 只存 diagnostic_flow_status;契约测试 test_exact_contract.py:3723-3751 monkeypatch flow→INFEASIBLE 仍断言 CERTIFIED + 零 exact-safe cut(CLAUDE.md 记的 3532 行号已漂移)
- 生产 certified 路径实际的 exact-safe cut 全是 nogood:binding_pose_domain_empty_nogood/rab_sep_clear_deficit_certificate(benders_loop.py:5870-5911)、binding_infeasible_nogood(:6035-6051)、routing_front_blocked_nogood(:6694-6703)、routing_exhausted_nogood(:7163-7179);power_subproblem_infeasible_nogood(:5654-5669)仅 env 取证通道
- whole-layout nogood 落 cut 前必过 I1:benders_loop.py:7498-7598 _add_exact_whole_layout_nogood 调 reverify_whole_layout_infeasibility,reverify 不 confirmed 则 return False,caller 升 UNKNOWN(:6045-6047、:7173-7175)
- I1 复验器 src/search/independent_infeasibility_reverifier.py:69-133:phase-1 只独立确认 binding-INFEASIBLE 情形,routing exhaustion 无独立完全穷尽证明时保守 UNKNOWN(docstring 自述'intentional soundness tradeoff');:220-246 用异构 solver profile(PORTFOLIO_SEARCH+固定 seed+2 workers)新建模型重解;docstring :10-13 声明 CP-SAT 与 binding/routing 构造器为 NAMED-TCB
- exact-safe cut 构造统一走 benders_loop.py:7450-7496 _add_exact_persisted_nogood:BendersCut(exact_safe=True, source_mode=certified_exact, 带 artifact_hashes/proof_summary)+序列化 roundtrip 校验+去重+master.add_benders_cut;启动时重放的持久化 cut 是性能 hint,非 exact_safe 即拒(:2086-2090)
- 细粒度加速 cut 全 env 门控:cell cut 需 EXACT_USE_POSE_BOOL_MASTER(benders_loop.py:6447-6451),PCR patch core 需 EXACT_B1_PATCH_ROUTING_CORE 且依赖 cell cut(:6456-6463),D2 需 EXACT_B1_D2_COMMODITY_FLOW(:6467-6474);而 EXACT_USE_POSE_BOOL_MASTER 在 _CERTIFIED_MASTER_DOMAIN_UNSAFE_ENV_OVERRIDES 中映射 pose_bool_master_not_certified(:943-946),certified 下 EXACT_* 是闭合白名单 deny-unknown(:1332-1374)
- src/cuts F1-F9 未接生产:src/cuts/lifecycle.py:1121-1126 step_8_apply_to_master raise NotImplementedError('Phase 1.3 P1.21 实施');全仓 grep 'from src.cuts' 51 个命中全部在 src/cuts/ 自身与 src/tests/cuts/,src/search 与 src/models 零 import(实测 Grep)
- lex 最优性机制在 src/search/certified_frontier.py:全域 oriented 枚举不做 h<=w 规范化(:78-98),objective=(area,min(w,h))(:168-170),单调支配剪枝:CERTIFIED 剪双维更小者、INFEASIBLE 剪双维更大者、objective≤best 者(:207-226);terminal_frontier_evidence_violation(:384-514) 从记录整体重放投影,要求 potential_domain 与 frontier 均空、best==final、min_side_admissibility=6、域参数不得切片(start_area/aspect_ratio/抬高 min_side 均拒)
- producer 只能提交 CANDIDATE_PROPOSED:outer_search.py:876 _build_certified_result 硬编码该状态;terminal 提交(:890-954)先 sink replay(project_candidate_records_for_sink, require_record_solution_match=True)再 fixed-witness 投影,任一失败 raise
- exploratory 路径命中 CERTIFIED 被静默降级 UNPROVEN:outer_search.py:2892-2909
- 谓词6 终端独立复验:exact_campaign.py:1131 起从冻结 artifact 的 pose 字节独立重建 occupied/pole/powered cells 做覆盖复核,拒 ghost_pick 入 occupancy(:1140-1141)
- binding 穷尽契约:budget/枚举 cap 耗尽且仍有 alternatives 时 fail-closed UNKNOWN 不落 cut(benders_loop.py:7042-7062);只有 binding CP-SAT INFEASIBLE 再经 overload-off 重试仍 INFEASIBLE 才进穷尽链(:5962-6019、:7097-7133)
### risks
- 完备性瓶颈直接卡最终目标:I1 phase-1 对 routing_exhausted_nogood 只在独立重建的 binding 本身 INFEASIBLE 时才确认,否则不落 cut、候选滞留 UNKNOWN(independent_infeasibility_reverifier.py:106-133)——terminal full-frontier 证明要求全域候选无一 UNKNOWN,这条保守策略可能使 campaign 永远到不了可 seal 状态
- I1 的'独立'只独立在 solver profile 与模型对象,binding 建模构造器是同一份 PortBindingModel 代码(independent_infeasibility_reverifier.py:24、:155-165 且 docstring 自认 NAMED-TCB)——binding 编码若有 false-INFEASIBLE bug,复验会同错,可能造成 false-INFEASIBLE 剪掉真最优候选进而产出假 lex 最优
- 生产 master 没有任何 F1-F9 强化 cut(lifecycle.py:1121-1126 未接入),只靠 whole-layout/placement-local nogood 一次删一个组合;70×70+266 实例规模下 LBBD 收敛速度(叠加 PROJECT_LOCK B-2 的 98% 密度离散流墙)是达成端到端 CERTIFIED 的最大工程风险
- 文档行号锚点已系统性漂移:PROJECT_LOCK §1A 引 binding_subproblem.py:930/976/1022/1035/1048(实为 1047/1093/1139/1152/1165)、CLAUDE.md 引 test_exact_contract.py:3532(实为 3723)——外审按行号核对会错位,可能误判约束缺失或浪费审计信用(本次实测 Read 确认)
- routing 连通 guard 与 binding 各处 TIMEOUT 全部 fail-closed 成 UNKNOWN(routing_subproblem.py:1785-1801、benders_loop.py:5946-5960 等)——sound 但每个 UNKNOWN 都是 frontier 穷尽的消耗品,长 campaign 中时限配置不当会系统性阻塞 terminal 证明
- docs/research/paradigm_search_review_v12_with_code_20260520/shared_infra/ 下有整套旧版 benders_loop/exact_coordinate_master 平行副本,codegraph/grep 检索会命中旧副本(本次 explore 即命中)——后续调查或自动化工具若不加路径过滤,可能拿旧代码得出错误结论
- 即使求解数学全部走通,操作链缺口仍在:main.py 终点只有 CANDIDATE_PROPOSED,仓库无生产 supervisor 入口调 supervisor_seal()(PROJECT_LOCK.md:130-137)——本维度一切绿灯都不推进 release,最终目标还依赖 PR2 #7 '最后通电'与 owner 手动门
### open_questions
- power_capacity_lower_bound 冗余有效不等式(PROJECT_LOCK 引 exact_coordinate_master.py:6336)未亲验行号与 skip_power_coverage 跳过逻辑,仅采信 LOCK 描述
- P0-1 lazy routing connectivity cut 的 W/X 证书独立复验(PROJECT_LOCK §311)未逐行核实:_add_source_side_connectivity_cut 的 fallback 结构见到了(routing_subproblem.py:1600-1621),但证书复验函数本体未细读
- EXACT_B1_ROUTING_AWARE_BINDING(RAB)在 certified 默认路径是否激活未核实(_rab_sep_routing_context 的来源没查)——若默认关,则 rab_sep_clear_deficit_certificate 在生产只会退化为 thin instance-only nogood,cut 强度更弱
- 候选级 INFEASIBLE(整个 (w,h) 判 infeasible,用于 frontier 剪枝)的产生点(master INFEASIBLE after cuts / precheck elimination 的 F-PS-R6/R7 校验路径)未逐行走查,仅确认了 whole-layout nogood 只 continue 循环不直接判候选 INFEASIBLE

## codex summary
本仓库 certified_exact 的数学结构是：outer_search 按 max_lex(area,min_side) 推进候选域，每个 ghost 矩形交给 benders_loop。默认 master 是 exact_coordinate_master，在 CP-SAT 中选择 mandatory/optional/power slots，用 NoOverlap2D 同时保证设施互不重叠、ghost 矩形恰选一且为空，并约束 placement rule 与 power 覆盖。master 给出布局后，flow_subproblem 的 GLOP 连续 LP 只做诊断，不参与剪枝或认证。真正 gating 的子问题是 binding 与 routing：binding 对端口绑定和 generic IO 槽做 exact-one，并对 commodity 需求做精确计数；routing 构造离散带/桥/分流合流状态，只证明端口前格之间的有向连通，FEASIBLE 后还重建所选 route graph 做全局 source->sink 复验。INFEASIBLE 不直接成为候选不可行：binding/routing rejection 先变成本轮 master 的 exact-safe pose-presence nogood；whole-layout nogood 必须经 I1 独立重建 binding 并确认 INFEASIBLE 后才落 cut，否则 fail-closed 为 UNKNOWN。最终 CERTIFIED 只证明 6 个谓词加 lex 最优，不含吞吐、带宽、离散容量流。生产 cut 是当前流程内的 BendersCut exact-safe nogood；src/cuts F1-F9 是未接入生产的未来 lifecycle（step_8_apply_to_master 仍 raise NotImplementedError，生产 src 零 import src.cuts）。

（以上为独立第二读者 Codex 的调查结论；下方 key_facts / risks / open_questions 均为其原文原样整理，未做任何实质改写。Codex 在调查中还有一段过程性自述：本仓库无 AGENTS.md，以用户指令和 PROJECT_LOCK.md / README.md / CLAUDE.md 为依据；当前分支 main，工作树有一个无关已修改文件未碰；CodeGraph 索引可用，显示主链从 outer_search.py 调 benders_loop.py:run_benders_for_ghost_rect，生产路径的 BendersCut 来自 src/models/cut_manager.py 而非 src/cuts；主链实际导入的是 MasterPlacementModel，默认路径经 master_model.py/from_exact_core 建坐标 master，pose_bool 是 EXACT_USE_POSE_BOOL_MASTER 环境门控分支；flow 在 master 解之后立即运行但只写 diagnostic_flow_status，binding/routing 分支并不把 flow_status 作为剪枝条件；whole-layout cut 的守卫是 binding 初始 INFEASIBLE 或 routing 绑定穷尽并不直接判候选不可行，而是先构造当前布局 nogood，且 whole-layout nogood 必须过 independent_infeasibility_reverifier，不确认就回 UNKNOWN；src/cuts/lifecycle.py 是 F1-F9 体系，9 个 family，含 scope digest/ghost/artifact/oracle/assumption attach check，step_8_apply_to_master 仍是 NotImplementedError；release 侧确认 supervisor_seal() 只接受 CANDIDATE_PROPOSED 提案并经 L0 seal，普通 mark_campaign_stopped(..., CERTIFIED) 会拒绝；实际 publisher 在 src/search/certified_surface.py，review gate 在 data/review_gates/phase_1_2_spike_close.json，状态仍是 blocked_manual_review_count。）
### key_facts
- 当前仓库实测在 main，分支有 main / pr2-5-domain-frontier-gate / topology-opt，git cat-file -t b35e5f9 不可解析且 git remote -v 为空。
- README 定义项目为 70x70、266 mandatory、目标 max_lex(area,min_side)，入口默认 main.py --mode certified_exact（README.md:14，main.py:1）。
- PROJECT_LOCK.md 把 certified theorem 限定为 6 个谓词加 lex 最优：ghost 空、设施不重叠、placement_rule、binding 精确可行、routing 有向连通、power coverage 可行、以及 lex optimality（PROJECT_LOCK.md:27-77）。
- 明确 out-of-scope 是物料离散吞吐、带宽、容量流；flow 只是连续 LP 诊断，F1-F9 packing 也不是吞吐证明（PROJECT_LOCK.md:100-116，README.md:89-110）。
- outer_search 的终端产物状态是 CANDIDATE_PROPOSED_STATUS，不是 durable CERTIFIED（outer_search.py:855-887，outer_search.py:890-954）。
- run_outer_search 以 min_side=6 为默认 admissibility 边界，并在 certified mode 阻断 unsafe env overrides（outer_search.py:1723-1745，outer_search.py:1755-1787）。
- 默认 master 路径是 MasterPlacementModel.from_exact_core(...)；EXACT_USE_POSE_BOOL_MASTER 在 certified guard 中列为 unsafe blocker（benders_loop.py:928-950，benders_loop.py:7897-7903）。
- coordinate master 建模时创建 slots、加坐标对称、设施 NoOverlap2D、ghost constraints、power coverage 和 exact-safe global valid inequalities（exact_coordinate_master.py:3420-3470）。
- ghost 约束枚举 anchor，并用 AddExactlyOne 选择一个 ghost anchor，再把 core intervals 与 ghost intervals 一起放进 AddNoOverlap2D（exact_coordinate_master.py:3648-3708，exact_coordinate_master.py:3744-3748）。
- binding 子问题对 pose-level port binding 做 AddExactlyOne，对 generic input/output commodity 做 sum == required，routing-free virtual sink input 不进入 routing spec（binding_subproblem.py:992-1047，binding_subproblem.py:1141-1165，binding_subproblem.py:1367-1433）。
- routing 子问题的 checked domain 是离散 grid routing；connector cell 是 terminal node 而非 free belt cell，且 cell/layer 容量约束是空间 AddAtMostOne，不是吞吐容量（routing_subproblem.py:1-5，routing_subproblem.py:126-131，routing_subproblem.py:1054-1061）。
- routing FEASIBLE 后会重建 selected route graph 并验证全局 source->sink reachability；只靠局部约束的 incumbent 会被拒绝并重新求解（routing_subproblem.py:1623-1719，routing_subproblem.py:1811-1865）。
- flow 子问题明确是 certified-exact diagnostic only，使用 GLOP 连续 NumVar，不能产生 exact-safe cut（flow_subproblem.py:4-9，flow_subproblem.py:119-163）。
- 生产实际落到 master 的 cut 是 pose-presence nogood：sum(present_lits) <= len(present_lits)-1，由 master.add_benders_cut 应用（exact_coordinate_master.py:7044-7096，benders_loop.py:7450-7496）。
- whole-layout nogood 在落 cut 前调用 reverify_whole_layout_infeasibility；未独立确认就记录 fail-closed UNKNOWN 并拒绝应用（benders_loop.py:7498-7598）。
- I1 独立复验当前只可靠确认 binding-INFEASIBLE；routing exhaustion 若不能由独立 binding INFEASIBLE 支撑，会保守返回 UNKNOWN（independent_infeasibility_reverifier.py:1-14，independent_infeasibility_reverifier.py:69-90）。
- src/cuts 的 F1-F9 lifecycle 仍是未来框架，step_8_apply_to_master 直接 raise NotImplementedError（src/cuts/lifecycle.py:1-17，src/cuts/lifecycle.py:65-75，src/cuts/lifecycle.py:1121-1126）。
- 只读搜索 Select-String 'from src\.cuts|import src\.cuts' 显示生产搜索/模型入口无 src.cuts import，命中集中在 src/cuts 自身与 src/tests/cuts。
- durable CERTIFIED 只能由 supervisor_seal() mint；直接用 mark_campaign_stopped(... status="CERTIFIED") 会抛错（exact_campaign.py:3566-3610）。
- P1.2 发布门当前文件状态是 blocked_manual_review_count，且需要 owner 手工 3 次 clean review，repo 内 receipt 不能自行关闭（data/review_gates/phase_1_2_spike_close.json:3-13，data/review_gates/phase_1_2_spike_close.json:23-36）。
### risks
- 最大发布阻塞不是数学子问题本身，而是 release surface：README 明确 main.py 只产出 CANDIDATE_PROPOSED，无 production CLI/launcher 调 supervisor_seal()；P1.2 gate 仍 blocked（README.md:15，PROJECT_LOCK.md:139-175，data/review_gates/phase_1_2_spike_close.json:3-13）。
- 容易误把 benders_loop 内部 RUN_STATUS_CERTIFIED 当公开 CERTIFIED；源码显示那只是 solve-layer 候选成功，外层仍写 proposal，durable certified 必须经 supervisor/publisher（benders_loop.py:6971-6990，outer_search.py:2720-2741，exact_campaign.py:3566-3610）。
- 若发布文案声称吞吐、带宽或离散容量流已认证，会越过 theorem scope；项目锁和 flow 源码都明说这些不在 certified 结论内（PROJECT_LOCK.md:100-116，flow_subproblem.py:4-9）。
- src/cuts F1-F9 不能作为当前生产 proof/cut 依据；它的 apply step 未实现且生产无 import，因此实际可信边界只能落在 BendersCut exact-safe nogood 与 I1 复验链上（src/cuts/lifecycle.py:1121-1126，benders_loop.py:7450-7598）。
- I1 当前偏 soundness-over-completeness：routing exhaustion 不能独立重建证明时会 UNKNOWN，这保护 soundness，但可能让端到端 certified 结果卡在无法剪枝/无法闭合（independent_infeasibility_reverifier.py:69-90，benders_loop.py:7568-7598）。
- env 门控是认证 TCB 的一部分；EXACT_USE_POSE_BOOL_MASTER、EXACT_POWER_PLACEMENT_SUBPROBLEM 等路径若被绕过或放开，会重新打开 certified theorem 的证明义务（benders_loop.py:928-950，exact_coordinate_master.py:3427-3437）。
- PROJECT_LOCK.md 记录近期对 boundary precheck、parallel scheduler timing 等 reachable soundness reset 的历史，说明最终关闭 P1.2 不能只看当前 checker 绿灯，仍需要 owner 隔离 clean review（PROJECT_LOCK.md:350-356，PROJECT_LOCK.md:139-175）。
### open_questions
- 按只读纪律，我没有运行 main.py、全量 pytest、preflight 或任何求解命令，所以不能证明当前树实际能端到端产出 proposal 或通过 gate。
- 我没有对 pr2-5-domain-frontier-gate 的 +8700 行 hardening 做逐行复核，只确认它存在且与 main 有大量差异；因此不能判断该分支是否应合入或是否已覆盖上述 release 风险。
- 本次重点是求解管线与数学正确性，没有展开审计所有 supervisor L0 verifier、publisher replay、manifest verifier 的内部实现；结论只覆盖它们在 release 边界上的调用关系与门控状态。


# DIM gates — 门禁/CI/frozen artifacts
## fable summary
这套门禁分三层。第一层是本地/CI 总闸 preflight_gate.py:15 项实际检查(编号到 18,3 个号位已退役),覆盖冻结工件 hash、禁提交路径、exact/exploratory 隔离、secret 扫描、两个结构 checker、mypy/ruff、pytest。退出码只有 0/1,docstring 里"2=有警告通过"是假的。测试分三条 lane:快 lane(120s、跳 @slow、xdist 并行)、--full(1200s、仍跳 @slow)、--slow-tests(2400s、串行、真跑慢 soundness 测试且收集不到 @slow 直接 BLOCK)——改认证核心必须单独跑慢 lane,否则是盲区。第二层是字节级冻结:preflight 钉 4 个规则/预处理工件 + 45.8MB 的 candidate_placements(缺失放行、存在必须 sha+size 逐字节匹配);runtime 侧 certified_artifact_contract.py 把同一组 sha/size 写死在源码常量里,campaign seal 前还会用 -I -S -B 隔离子进程重跑 pinned checker、明确拒绝"我就是 checker"的身份自跳过。实测 5 个工件当前全部命中 pin。第三层是 close-kernel 结构封存:4442 行的 obligations checker 把 V99 楼面硬编码成 frozenset 常量(59 个 proof-bearing sink 分类、约 60 文件逐文件 source-sha、token/扫描根/critical-gate 集合),manifest JSON 反过来钉 checker 自身 hash 形成互锁,allowlist checker 用 AST 把"谁能写 CERTIFIED/INFEASIBLE 强状态"封闭成 82 条白名单(每条 pin 整个模块文件 sha)。两 checker 实测 PASS(14 obligations/59 sinks;64 AST nodes/82 entries)。这套东西保护的是:输入定理字节不被换题、证明状态铸造权不被旁路、发布面单入口不漂移、checker 结构本身不被悄悄掏空。代价是改动成本极重:任何 sealed 文件一字节改动都触发 freeze-ritual 连锁(重钉 V99 floor 常量→manifest sink sha→allowlist 行号→checker 自钉最后算,sha 只能按 LF 字节算),历史上 CRLF、行号漂移、pathspec 漏提交都真实翻过车。最大的现实风险:本交付副本无 remote、无 pre-commit hook,三条 GitHub CI 全部惰性,整套门禁目前只靠手动自觉跑。
### key_facts
- preflight 退出码只有 0/1:GateResult.exit_code 仅在有 blockers 时返回 1、否则 0(scripts/preflight_gate.py:117-121),但 docstring 声称"2 = 通过但有警告"(scripts/preflight_gate.py:18-21),代码里无返回 2 的分支。
- FROZEN_ARTIFACTS 钉 4 个 checked-in 工件的 sha256(scripts/preflight_gate.py:37-44);EXTERNAL_FROZEN_ARTIFACTS 钉 candidate_placements.json sha256+45,773,799 字节,文件缺失时按 distribution policy 放行 OK、存在时必须逐字节匹配否则 BLOCK(scripts/preflight_gate.py:46-55, 255-276)。
- 实测 Get-FileHash:5 个冻结工件(canonical_rules/preprocess_plan/mandatory_exact_instances/generic_io_requirements/candidate_placements)当前全部与 pin 一致,candidate_placements size=45,773,799。
- --full 的 pytest 仍带 -m "not slow"(scripts/preflight_gate.py:679,超时 1200s);慢测试只在 --slow-tests lane 跑(-m slow、2400s、刻意串行防子进程过订阅,scripts/preflight_gate.py:726-733),且 slow lane 下 exit 5(未收集到 @slow)按 require_collection=True 直接 BLOCK(scripts/preflight_gate.py:755-760, 789-791)。
- @slow 集中登记在 src/tests/conftest.py:91 的 _SLOW_TEST_NODEIDS frozenset;pytest.ini 全局 addopts --basetemp=.pytest_tmp(实测读取)。
- check_p1_2_proof_obligations.py 的 main() 不收参数、无 argparse(文件尾部 main 定义);但 check_strong_status_write_allowlist.py 有 argparse(--root/--allowlist,scripts/check_strong_status_write_allowlist.py:738-749),实测 --help 输出 usage 并退出——CLAUDE.md"两个 checker 均无 argparse"对后者不成立。
- 两 checker 实测运行均 PASS exit=0:"P1.2 proof obligation check passed: 14 obligations anchored; 59 proof-bearing sink files sealed"、"strong-status write allowlist check passed: 64 registered AST node(s), 82 allowlist entry(ies)"。
- V99 静态楼面硬编码在 checker 源码常量:59 个 sink 路径→分类映射(scripts/check_p1_2_proof_obligations.py:3820-3880)、约 60 文件逐文件 source-sha256(:3926-3987)、proof-bearing token/扫描根/critical-gate frozenset(:3792-3904);注释明说 checker 无法递归自证、git 历史+人审是信任边界、合法 reseal 必须改 checker 代码本身(:3784-3789)。
- checker 自钉互锁:checker 自身是 manifest JSON 注册的 close-kernel sink、source_sha256 存在 data/proof_obligations/p1_2_proof_obligations.json(:880 附近条目),checker 运行时校验每个注册 sink 的当前 hash(scripts/check_p1_2_proof_obligations.py:4336-4340);另有 _check_close_kernel_checker_self_binding AST 守卫防止 main 里删掉 8 个必需检查调用(:2132-2155)。
- runtime 侧 src/search/certified_artifact_contract.py 把 5 工件 sha(小写)+size 写死为源码常量(:29-47);validate_locked_p1_2_close_kernel 在 locked 项目 seal 前用 python -I -S -B -X pycache_prefix 隔离子进程重跑 pinned checker、30s 超时、明确不做"am I the checker"身份自跳过(:107-153,设计注释 :116-126)。
- allowlist checker 每条 entry 刻意 pin 整个模块文件 sha 而非仅 AST 节点(scripts/check_strong_status_write_allowlist.py:651-654 注释),扫 src/ 全部排除 src/tests(:622-633),三类失败全 fail-closed:pin 失配/未注册强状态写入/stale entry(:767-773)。
- CI 三条:project_foundation.yml 主 gate 跑 preflight --ci --base-ref(:50-56)+ 独立 slow-soundness job(timeout 45min)先跑 python src/placement/placement_generator.py 重新生成 candidate_placements 再 check_external_artifacts --require 验 hash、后跑 --slow-tests(:85-91)——说明 45.8MB 工件被认为可确定性重生成;两条 industrial planner workflow 按路径过滤触发,其中 alignment audit 标 continue-on-error: true 非硬门(industrial_planner_single_base_delivery_surfaces.yml:80);三条均 permissions contents:read + concurrency cancel-in-progress。
- 实测 git remote -v 输出为空、.git/hooks 下无任何非 .sample hook——三条 CI 在本交付副本全部惰性,preflight 无自动触发点,只能手动跑。
- .gitattributes 首行 `* text=auto eol=lf` 且注释明说:preflight hash 与 line-ending gate 都读工作树字节,Windows core.autocrlf 的 CRLF 转换会打破 pinned hash(实测读取 .gitattributes);README §9(README.md:1275-1284)记录 reseal 连锁顺序:V99 floor→manifest sink sha→allowlist(写入点行号漂移必须同步 line 字段)→checker 自钉最后算、sha 只按 LF(git show HEAD:<file> | sha256,绝不 Python write_text)。
- phase gate data/review_gates/phase_1_2_spike_close.json:status=blocked_manual_review_count,summary 明说 v99 是时间点 close-kernel seal、post-v99 工作树改动(PR1 发布边界)不被旧 source-hash seal 覆盖、close claim 前需 fresh reseal,owner clean-review 计数刻意保存在仓库外。
- pr2_dependency_floor_manifest.json(574,082 字节,实测大小与 pin 一致)被 checker 按 sha+size 钉死(scripts/check_p1_2_proof_obligations.py:42-45),但其 provenance status 常量为 deploy_pending_placeholder_regenerate_on_production_cachyos_py313(:47-49)——是占位,生产 close 前必须在 CachyOS+Py3.13 重生成并 reseal(README.md:1310)。
- CI 模式下 STRICT_TOOL_TIMEOUTS=True:mypy/ruff 超时本地只 WARN、CI 变 BLOCK(scripts/preflight_gate.py:194-198, 780-781);而结构 checker 走 _run_script_check 默认 30s 超时、超时永远 BLOCK(:460-474)。
- CANDIDATE_PROPOSED→seal 的 runtime 一致性:certified_artifact_contract 被 exact_campaign.py、certified_surface.py、delivery_manifest.py、terminal_fixed_witness_verifier.py 共 7 个文件消费(codegraph 文件依赖面),即冻结 pin 真正到达 runtime 消费点而非只在 gate 层。
### risks
- CI 全惰性 + 无本地 hook:仓库无 remote、.git/hooks 无 pre-commit(实测),三条 workflow 不会跑;而 --full 又不含 @slow(preflight_gate.py:679),改认证核心后 ~13min 慢 soundness lane 完全靠手动自觉——这是最可能让 soundness 回归悄悄溜进树的通道。
- main 与 pr2-5-domain-frontier-gate 分支的 checker 分歧未收敛:分支 +8700 行硬化未合入,main 上 LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS 只含 manifest+checker(certified_artifact_contract.py:24-27),README.md:1277 记录分支已扩到 manifest+allowlist+checker+protected callees;若最终 release 从 main 走,吃的是较弱版本的 close-kernel。
- V99 seal 是时间点快照:phase gate JSON 自己声明 post-v99 工作树改动(PR1 发布边界)不被旧 seal 覆盖、close claim 前需 fresh reseal(phase_1_2_spike_close.json summary)——即当前"两 checker 全绿"不等于当前树已被 owner 级 seal 覆盖,这一步 reseal 是 P1.2 关门前的必做债。
- dependency floor manifest 是占位(deploy_pending_placeholder_regenerate_on_production_cachyos_py313,checker:47-49):生产 close 前必须在 CachyOS+Py3.13 重生成+审+reseal,本 Windows 机做不了,是一个只能在生产环境解决的阻塞项。
- 文档漂移会误导自动化:preflight docstring 的 exit 2 不存在(实测代码 :117-121)、CLAUDE.md"两 checker 均无 argparse"对 allowlist checker 不成立(实测 --help 生效);另外 obligations checker 在 manifest 读取失败时返回 2(main 的 CheckError 分支)——把"2"当 warning-pass 的脚本会把硬失败当通过。
- reseal 连锁在 Windows 主开发环境上易错:CRLF/LF 自钉不符、allowlist 行号漂移、reseal commit pathspec 漏文件都有实翻车记录(README.md:969, 1112, 1284);一次 sealed 文件的最小改动就是全连锁 ritual + full preflight + slow lane,重成本本身会诱使人绕门禁(直接改 pin 或跳慢 lane)。
- 结构门有三类已接受残余(F import-time / checker-self / A4 动态反射)刻意未关,兜底是显眼 diff + owner 仓库外人审(README.md:1246-1249);任何 checker/preflight 绿灯都不构成 release 证据,最终目标的最后一公里(owner 手动门 + 生产 supervisor 入口)不在这套门禁的能力范围内。
- obligations checker 在 preflight 里只有 30s 子进程超时(_run_script_check 默认,preflight_gate.py:460),它要逐字节 hash 约 60 个源文件 + 再起隔离子进程跑 allowlist checker;慢盘/杀软扫描环境可能出现与代码正确性无关的伪 BLOCK(本机实测数秒内完成,风险为环境性)。
### open_questions
- README §9 称 strong_status_write_allowlist.json 有"整字节 floor(sha+size)":在 main 的 checker 里只找到 allowlist 的 .py 脚本被 V99 floor 钉 sha(check_p1_2_proof_obligations.py:3928),未找到对该 JSON 数据文件本身的字节 pin;疑为 round-18 分支特性,未到分支上逐行核实。
- CI slow-soundness job 依赖 placement_generator.py 确定性重生成 45.8MB candidate_placements 并命中 pin(project_foundation.yml:85-88);本机按只读纪律未实测该生成过程的确定性与耗时。
- preflight 编号 [7/18][8/18][11/18] 三个号位缺失,推断对应 docstring 所述已退役的 doc-subjects/doc-tree 检查(preflight_gate.py:15-16),未从 git 历史确认对应关系。
- 按只读纪律未跑 python scripts/preflight_gate.py 全量,"当前树 preflight 全绿"未整体实测,只逐项核对了源码逻辑 + 单独实测了两个结构 checker 和 5 个冻结工件 hash。

## codex summary
这套门禁的核心不是证明几何最优性本身，而是把"谁有资格写出 CERTIFIED/INFEASIBLE、哪些证明承载文件可信、哪些输入字节可信"封成一组 fail-closed 边界。preflight_gate.py 负责把冻结输入、P1.2 phase gate、proof obligations checker、strong-status allowlist、快测和静态检查串起来，退出码只表达通过或失败（0/1）；--full 仍排除 @slow，慢测被拆成单独 lane（--slow-tests）。冻结 artifact 有两层钉死：preflight 检查仓内/外部 artifact 的 sha/size，runtime 的 certified_artifact_contract.py 也用源码常量拒绝漂移。两个结构 checker 更重：P1.2 checker（check_p1_2_proof_obligations.py）封 V99 close-kernel floor、obligations JSON、sink 清单、源码 sha、guard tokens、dependency floor，并在隔离 subprocess 中调用 strong-status allowlist checker；allowlist checker（check_strong_status_write_allowlist.py）用 AST 找强状态写入和 artifact writer，并把允许项钉到整文件 hash 和行级结构。CI 三条线中，project_foundation.yml 是主 preflight + slow lane（跑在 CI 上）；另外两条是 IndustrialPlanner 后处理/交付面专项，其中一个 drift audit 明确 continue-on-error（非硬门）。改动成本很高：动一个受保护证明面通常要同步 obligations JSON、allowlist、V99 源码常量、LF 字节、checker 自钉多处联动，且仍不能自动关闭 P1.2 手动门——最终发布仍卡在 owner 手动 release gate，代码门禁全绿也无法自动跨过。此外实测发现 main 分支相对 pr2-5-domain-frontier-gate 分支在门禁相关文件上缺少约 9300+ 行的 checker 硬化，若最终发布走 main 会缺这批保护。
### key_facts
- PROJECT_LOCK.md:130-137 明确 P1.2 仍 open，checker/local pass/internal seal 不能改写 owner release gate，且 production supervisor CLI 仍未满足。
- data/review_gates/phase_1_2_spike_close.json:23-36 记录 owner state 不是 closed，p1_3b_entry_allowed=false，下一阶段不允许自动进入。
- scripts/preflight_gate.py:117-121 规定 preflight 退出码只有 0 或 1（GateResult.exit_code），warnings 不改变退出码。
- scripts/preflight_gate.py:665-683 表明普通测试 lane 总是加 -m "not slow"，--full 只改变 target/timeout，不包含慢测。
- scripts/preflight_gate.py:726-769 把 --slow-tests 做成独立慢 lane，串行运行 pytest -m slow src/tests。
- scripts/preflight_gate.py:37-55 钉死仓内 FROZEN_ARTIFACTS 和外部 candidate_placements 的 sha/size，外部文件大小为 45,773,799 字节。
- src/search/certified_artifact_contract.py:29-47 在 runtime 侧用源码常量列出 exact artifact 路径、sha 和 candidate size。
- src/search/certified_artifact_contract.py:171-208 会在 runtime 校验 exact artifact hash/size，缺失或漂移返回稳定 violation。
- .github/workflows/project_foundation.yml:47-56 主 CI 编译 preflight 后运行 python scripts/preflight_gate.py --ci --base-ref "$BASE_REF"。
- .github/workflows/project_foundation.yml:85-91 慢 CI 先恢复/校验外部 candidate_placements，再运行 python scripts/preflight_gate.py --slow-tests。
- .github/workflows/industrial_planner_checked_artifacts.yml:115-132 运行 checked artifact audit 并上传摘要；.github/workflows/industrial_planner_single_base_delivery_surfaces.yml:63-80 的 alignment audit 是 continue-on-error: true（非硬门）。
- scripts/check_p1_2_proof_obligations.py:2-6 自称结构门禁，不是 theorem prover（自述文字）。
- scripts/check_p1_2_proof_obligations.py:2132-2155 把 checker 自身注册为 proof-bearing sink，并要求 main 调用关键检查函数。
- scripts/check_p1_2_proof_obligations.py:2158-2188 会在隔离 subprocess 中运行 check_strong_status_write_allowlist.py。
- scripts/check_p1_2_proof_obligations.py:4245-4355 要求强状态相关文件被注册、hash-bound、绑定 obligation，并带 guard tokens。
- scripts/check_p1_2_proof_obligations.py:3784-3789 明确 checker 不能递归证明自身源码完整性，checker source/floor hash 是 named TCB（可信计算基）。
- scripts/check_strong_status_write_allowlist.py:80-170 用 AST visitor 扫描状态写入、candidate status、artifact writer 和 verified producer 引用。
- scripts/check_strong_status_write_allowlist.py:647-721 对 allowlist 条目做整文件 source hash 钉死，未注册 finding 或 stale allowlist entry 都失败。
- .gitattributes:1-9 规定 LF，scripts/check_line_endings.py:86-99 拒绝 CRLF/CR，说明 hash 钉死直接依赖工作树字节。
- git diff --stat main..pr2-5-domain-frontier-gate 实测显示 PR2 分支相对 main 在 4 个门禁相关文件上 9893 insertions(+), 158 deletions(-)，其中 scripts/check_p1_2_proof_obligations.py 约 +9300 行硬化。
### risks
- 最终发布仍被 P1.2 owner 手动门阻塞，代码门禁全绿也不能合法关闭 release gate，依据 PROJECT_LOCK.md:130-137 和 data/review_gates/phase_1_2_spike_close.json:23-36。
- --full 不含慢测，若发布流程把 full green 误当完整验证，会漏掉 slow soundness lane，依据 scripts/preflight_gate.py:665-683 和 scripts/preflight_gate.py:726-769。
- 当前 main 分支不含 pr2-5-domain-frontier-gate 分支的大规模 checker/runtime 硬化，最终 release 若从 main 走会缺这批保护，依据实测 git diff --stat main..pr2-5-domain-frontier-gate（+9893/-158）。
- close-kernel checker（P1.2 checker）是结构门禁和 named TCB，不是数学证明器，也不能自证自身正确，依据 scripts/check_p1_2_proof_obligations.py:2-6 和 :3784-3789。
- 外部 candidate_placements 可在轻量 checkout 中缺席，发布或慢测前必须恢复并校验，否则 runtime exact artifact contract 会拒绝，依据 scripts/preflight_gate.py:255-264 和 src/search/certified_artifact_contract.py:171-208。
- Windows/LF 字节坑会直接导致 source/artifact hash 漂移，可能触发 reseal 连锁，依据 .gitattributes:1-9、scripts/check_line_endings.py:86-99 及 CLAUDE.md 相关记载。
- dependency floor 仍是受钉死的 named TCB/部署边界，生产环境差异可能需要重新走合法 floor 更新流程，依据 scripts/check_p1_2_proof_obligations.py:4132-4232。
- CI workflows 是门禁和审计，不是最终 CERTIFIED 结果发布器；最终端到端产物、公示和 owner gate 仍在 repo 外有人工条件，依据 PROJECT_LOCK.md:252-266 和 .github/workflows/project_foundation.yml:47-91。
### open_questions
- 调查按只读要求未运行 preflight、两个 checker、pytest 或求解器，因此未确认当前工作树实际是否 green，只核实了源码门禁结构本身。
- owner clean-review count 在 repo 外维护，仓内只能看到 blocked/manual gate 状态，无法确认外部当前实际计数。
- pr2-5-domain-frontier-gate 分支的硬化是否应先合入 main 再关闭 P1.2，属于 release 决策问题，源码本身没有自动答案。
- dependency floor 的生产环境（CachyOS/Python 3.13）最终重钉是否已由 owner 接受，仓内只能看到钉死机制和 deploy-pending 边界，无法确认外部批准状态。


# DIM branches — 分支与未合并工作
## fable summary
仓库有三个分支。主线 main(c59a65f)工作树基本干净,唯一脏改动是一张记忆卡片(+8/-2),不涉源码。

pr2-5-domain-frontier-gate(5ff31ac)是唯一真正的未合并工作,检出在独立 worktree C:/claude pj/zmd-pj-round19(干净)。它与 main 分叉于 30f9ee2(6-29),领先 25 个 commit,4 天内高频推进,最后一个 commit 是今天 22:29 的 round-19。diff 对 main 共 14 文件 +15266/-189,主体是结构检查器 check_p1_2_proof_obligations.py 从 4442 行涨到 12859 行(CLAUDE.md 记的"+8700 行/round-18"已过时)。这就是 PR2 #5"close-kernel 第二道门":用 AST+source-sha 约束"一个能忠实 reseal checker 的恶意未来维护者",19 轮外审对抗硬化。runtime 侧只有小而真的 soundness 修复:child 升格时补设 declare_mode/last_stop_reason 让终态穷尽校验无条件跑(+24 行),exact_campaign 转换门归一 declare_mode(+5 行);三个 runtime 文件 blob 自早期起冻结(实测与文档一致)。

没合入的原因是流程性的:README 定的合并条件 = 外审回传且无新结构 BLOCK(残余只剩 owner 裁定三类:F import-time、checker-self、A4 动态反射)才 merge。第 12 轮 GPT Pro 外审确实又挖出共同根因(语义门只护 3 个 runtime 文件,没护父锚 certified_artifact_contract.py 和 witness 承载文件),round-19 今天补了 A/B/C 三组门+统一 reseal,自验全绿(14 obligations/60 sinks、preflight 3741 passed、slow 44 passed),第 13 轮外审提示词 22:37 已写好、包未打——分支处于"等下一轮外审确认后 merge"状态。合入连锁:main 分叉后 9 个 commit 全是文档/记忆/打包,与 pr2-5 的 14 文件零交集,文本合并应干净;但要走 CI @slow,且合入后 CLAUDE.md 记的 checker 计数(59 sinks/64-82)会过期(分支为 60/65-83);合并不解 P1.2 release-blocked。

topology-opt(26931e8,6-27)不是未合并工作:merge-base 等于它自己的 HEAD,即已完全包含在 main 里(main 领先 15 个 commit),只是标签没删。内容是拓扑引导 safe-bundle 两块(材料骨架+指标、绑定序+走廊 hint planner),实测全部函数只有测试调用、零生产接线,与 commit 自述"diagnostic-only, unwired"一致。
### key_facts
- 三分支实测:main=c59a65f、pr2-5-domain-frontier-gate=5ff31ac(检出在链接 worktree C:/claude pj/zmd-pj-round19)、topology-opt=26931e8(git branch -a -v + git worktree list 实测)
- 主仓库工作树唯一脏改动是 cc_memory_vnext/cards/guardrail-delegate-adversarial-reads.md(+8/-2);round19 worktree 干净(git status 实测)
- git log main..pr2-5 = 25 个 commit(2026-06-29 05:47 → 2026-07-02 22:29);merge-base = 30f9ee2「Mark PR2 floor manifest deploy-pending」(git log/merge-base 实测)
- git diff main...pr2-5 --stat = 14 文件 +15,266/-189;checker 脚本 +9300 行(实测行数 main 4442 → 分支 12859),CLAUDE.md 记的「+8700 行(round-18)」已被今天的 round-19 超过
- 分支 HEAD 5ff31ac(round-19,2026-07-02 22:29)commit message:第 12 轮 GPT Pro 外审共同根因 = 语义门只覆盖 3 个 runtime 文件,补 Group A(父锚 certified_artifact_contract 控制流锚定)/B(checker 自完整性 5 洞)/C(witness 静态重绑)+ 统一 reseal;自验 checker 14 obligations/60 sinks、strong-status 65/83、preflight --full 3741 passed、--slow-tests 44 passed(git log -1 pr2-5 实测)
- round-18 commit 28b9b5e 记录 owner 2026-07-02 拍板:A4 动态反射重绑 denylist 确定性不收敛,接受为残余(与 #5-F、checker-self 同类),靠 source-sha 钉字节+人工 clean-review 兜底,不再当 release 阻塞(git log 实测)
- runtime 侧真修复极小且已源码核实:pr2_l0_true_verifier_child.py +24 行(_verify_supervisor_domain 升格时设 scratch_state declare_mode=strict + last_stop_reason,git diff main...pr2-5 实测,分支 ~:432-453);exact_campaign.py +5 行(_supervisor_certified_transition_violation 归一 declare_mode=strict,分支 ~:1878-1883)
- 3 个 runtime close-kernel 文件在分支上的 blob OID = 2f55bc65/af276679/da326456,与 README「V99 floor 冻结」记载逐字节吻合(git ls-tree pr2-5 实测);main 上为不同 blob(缺 declare_mode 修复)
- 未合入原因与合入条件:README.md:1220(§5.6)——外审回传后并集+triage,若无新结构 BLOCK(残余只剩 F/checker-self/A4-dynamic)才 merge pr2-5→main 并跑 CI @slow;第 12 轮找到了新 BLOCK → round-19 → 现等第 13 轮
- 第 13 轮外审已在 staging:C:\Users\22957\pr2_5_round19_review_entry_{1..4}_*.md 于今天 22:37 写好(round-19 commit 后 8 分钟),但 pr2_pkg 下尚无 round19 的 .7z 包(es 实测)
- topology-opt 已完全包含于 main:git merge-base main topology-opt = topology-opt 自身 HEAD 26931e8,main 领先它 15 commit,git log main..topology-opt 为空(实测)——「未合并工作」为零
- topology 内容:Chunk1 8894bc7(material_connection_skeleton.json 2184 行 + material_skeleton.py/verifier + topology_guidance.py)+ Chunk2 26931e8(topology_binding_guidance.py + topology_route_hint.py + 3 测试文件,+933 行);codegraph callers 实测 compute_topology_binding_order/compute_topology_guidance_metrics/log_topology_guidance_observation 只有测试调用方,生产零接线
- main 分叉(30f9ee2)后的 9 个 commit 全是 README/CLAUDE.md/记忆系统/打包脚本(git diff --name-only 30f9ee2..main 实测),与 pr2-5 触碰的 14 个文件零交集 → 文本合并无冲突
- P1.2 release gate 与 merge 解耦:data/review_gates/phase_1_2_spike_close.json status=blocked_manual_review_count、p1_3b_entry_allowed=false、clean count 由 owner 在仓库外维护(文件实读)
- README.md:296 明示分支差异:main checker 输出 59 sinks、pr2-5 worktree 60 sinks,「不要混为一谈」;round-19 后分支为 60 sinks/65-83 allowlist,合入后 CLAUDE.md 记载的 59/64-82 将过期
### risks
- 最终目标的认证链关键修复(child 升格 declare_mode/last_stop_reason 让终态穷尽校验无条件执行)只在未合并分支上——main 上的 L0 child 仍带该 soundness gap(README §5.3 定性为真 gap 非假想),分支一天不合入,main 的 seal 路径一天不完整(git diff main...pr2-5 -- src/search/pr2_l0_true_verifier_child.py 实测)
- pr2-5 分支本地唯一、无 remote、无备份 push(git branch -a 无远端;README:17 明记「未 push、只在本地 .git」)——25 个 commit、1.5 万行对抗硬化成果存在单机丢失风险
- 外审轮次有不收敛前科:round-9 曾宣布「123/123 已钉」被第 6 轮 panel 证伪、错到 round-14(README:1197-1201);round-19 自验全绿同样不保证第 13 轮无新 BLOCK,merge 时点仍不可预期,可能继续吞日历时间
- merge 后有文档漂移债:CLAUDE.md 与 README 多处硬编码 main 的 checker 计数(59 sinks/64 nodes/82 entries)与「round-18/+8700 行」状态,合入 round-19 后全部过期,不更新会误导后续会话(README:296、CLAUDE.md 常用命令节)
- close-kernel 三类已接受残余(F import-time、checker-self、A4 动态反射)依赖「显眼 diff + owner 仓库外人工 clean-review」兜底(README:1244-1252)——该兜底本身在仓库外、不可机器验证,是最终 release 关门的人肉单点
- 即便 pr2-5 合入且第 13 轮外审干净,离最终目标仍隔着:PR2 剩余 #2/#3/#1/#9b/#9c/#7(含生产 supervisor 入口「最后通电」缺口)+ owner 手动 3 次 clean-review 计数(README:1220 的 merge 后续序;PROJECT_LOCK.md:179-185)——分支合并只是中间站,不是 release
### open_questions
- 第 12 轮外审的原始报告(pr2-13 包)在仓库外(C:\22957\download\新建文件夹\pr2-13\ 有痕迹但未逐份核读),round-19 的「范围裁定:commodity_demands 假阳性不纳入」只能以 commit message 为据,未能独立复核该 triage 是否漏项
- round-19 的第 13 轮外审包(.7z)尚未在 pr2_pkg 出现——是尚未打包、还是改了打包位置/命名,无法确认;README 提到的 RESUME 锚文件 p1-2-resume-state-20260621.md 在本机该路径不存在(交付副本未带),逐轮最新状态只能靠 README+commit message 交叉
- topology-opt 标签为何保留未删(是纯遗留、还是预留续做 S4+ 的锚点)仓内无记载;其 hint planner 若将来接线,须重新评估与 certified 路径隔离(hint 只许 AddHint 不许约束,PROJECT_LOCK F-GM-R7-HINT-01),当前未接线故暂无风险

## codex summary
当前仓库实测状态和题面/README 的旧叙事不完全一致：main 是当前 checkout，pr2-5-domain-frontier-gate 在另一个 worktree（C:/claude pj/zmd-pj-round19），HEAD 已是 round-19 commit 5ff31ac，不是文档里记的 round-18；topology-opt 已是 main 的祖先，当前对 main 没有未合入 diff（main..topology-opt 与三点 diff 均为空）。工作树有一个既有脏改动：cc_memory_vnext/cards/guardrail-delegate-adversarial-reads.md。

pr2-5-domain-frontier-gate 的实质是 close-kernel 结构门继续硬化：checker 增长最多（+9300/-102 行），manifest/allowlist/source-sha floor 同步 reseal，并把父锚（parent anchor）、checker 自完整性、fixed-witness/whole-layout reverifier 的 runtime 绑定形态都纳入结构检查。但它仍明确自我定义为 structural gate（非 theorem prover），也不关闭 P1.2 release——manifest 与 checker 源码都明写这一边界，并把 Python/stdlib/OR-Tools/OS/文件系统/人工 review 等列为 TCB（可信计算基）。它未合入 main 的根本原因不是代码质量问题，而是这类结构硬化本身就不等于、也从未打算替代 owner 手动关闭 P1.2 门；合入需要走完整的 freeze-ritual/reseal 连锁（更新 pin sha → 重生成依赖产物 → checker/manifest/allowlist 同步 reseal → 全量重跑 gate），且必须基于合并后的真实树重新计算，不能复用旧 hash。

topology-opt 是诊断/探索性 hint planner 分支（S2 binding order 提示 + S3 route corridor 提示），源码和测试都明确声明未接线、不进 proof、不改 feasible set，纯粹是诊断辅助工具。它现在已完全包含在 main 历史中，本身不再是活跃领先分支。

跳出分支层面看最终目标（端到端产出并发布 CERTIFIED 结果）：无论是否合入 pr2，当前 main 上生产入口仍未通电——main.py 只调用 run_outer_search，终点固定写 CANDIDATE_PROPOSED，没有生产级 supervisor 入口调用 supervisor_seal()（该方法当前仅被测试代码调用）；且 owner 手动 review gate（data/review_gates/phase_1_2_spike_close.json）当前状态是 blocked_manual_review_count，明确 not_closed、allowed:false、owner_manual_decision_only。所以分支合并本身不是当前阻碍最终目标的瓶颈，真正的瓶颈在生产 supervisor 入口缺失与 owner 手动门未开。
### key_facts
- 分支实测：git branch -a 输出 * main、+ pr2-5-domain-frontier-gate（另一 worktree）、topology-opt；git worktree list 显示 pr2 分支 checkout 在 C:/claude pj/zmd-pj-round19。
- 工作树实测：git status --short --branch --untracked-files=all 显示 ## main 加 M cc_memory_vnext/cards/guardrail-delegate-adversarial-reads.md（唯一脏改动）。
- 三分支当前 HEAD（git for-each-ref 实测）：main|c59a65f|2026-07-02T22:09:33+08:00|feat(memory)...；pr2-5-domain-frontier-gate|5ff31ac|2026-07-02T22:29:00+08:00|harden(close-kernel): round-19...；topology-opt|26931e8|2026-06-27T22:25:02+08:00|feat(topology)...。
- 文档记忆已过期：CLAUDE.md 记的是 pr2 round-18/+8700 行，但实测当前 pr2 HEAD 已是 round-19，三点 diff 也变为 14 个文件、+15266/-189 行（其中 checker 文件本身 +9300/-102）。
- README/CLAUDE 旧 commit hash 不可当 git 权威：CLAUDE.md:15 明说本仓库是交付副本、历史被重建；实测 git cat-file -e b35e5f9/9bbb3a6/099f5a3^{commit} 均 exit 128（不可解析）。
- pr2 相对 main 的差异：git log main..pr2-5-domain-frontier-gate --oneline 有 26 个 commit；git diff main...pr2-5-domain-frontier-gate --stat 为 14 files changed，15266 insertions(+), 189 deletions(-)。
- pr2 manifest 现状（ConvertFrom-Json 实测两分支 manifest）：pr2 为 14 obligations、60 sink files、20 critical gate files；main 为 14、59、19。
- pr2 checker 自述边界：pr2 分支 scripts/check_p1_2_proof_obligations.py:4-6 明写自己是 small structural gate, not theorem prover；pr2 分支 data/proof_obligations/p1_2_proof_obligations.json:817-838 同样列出 policy、TCB、not_claimed 条目。
- pr2 父锚（parent anchor）硬化：pr2 分支 scripts/check_p1_2_proof_obligations.py:13111-13118 说明 source-sha reseal 仍可能漏掉 parent no-op 篡改，因此新增校验 certified_artifact_contract.py 的控制流骨架；pr2 分支 src/search/certified_artifact_contract.py:653-695 强制运行 pinned checker subprocess。
- pr2 checker 自完整性检查：pr2 分支 src/search/certified_artifact_contract.py:581-620 拒绝 top-level 动态重绑/非 canonical entrypoint/受保护函数被多重绑定或加 decorator。
- pr2 sink/source-sha floor：pr2 分支 scripts/check_p1_2_proof_obligations.py:13369-13421 要求 sink 注册、classification、obligation、source sha、guard tokens 齐全；13398-13406 规定 source sha drift 即视为 reopen close claim（重新打开已关闭的结论）。
- pr2 witness/reverifier 绑定硬化：pr2 分支 scripts/check_p1_2_proof_obligations.py:13468-13517 要求 publish path 必须调用隔离的 fixed-witness capsule；13595-13612 要求 LBBDController 和 whole-layout nogood funnel 无 decorator/base 类/shadow 绑定。
- pr2 L0 verifier 变更之一：新增 declare_mode='strict' canonicalization——src/search/pr2_l0_micro_verifier_core.py 在 run seal、transition gate、postwrite gate 三处加入 strict；src/search/pr2_l0_true_verifier_child.py 在 child precheck 前设置 strict 与 terminal last_stop_reason。
- P1.2 release 当前锁定状态：PROJECT_LOCK.md:130-137 明写 OPEN/BLOCKED，无生产 supervisor CLI/launcher，main 正常运行终点仍是 CANDIDATE_PROPOSED，checker PASS/内部 seal 均不等于 owner gate closed。
- P1.2 关闭条件：PROJECT_LOCK.md:141-146 说明 PR1 等已实现但 P1.2 仍 OPEN/BLOCKED；真正闭合要求命题 P 的机器边界、发布链、owner 手动闸三者同时满足，不是单纯求解数学定理成立。
- owner 手动门文件现状：data/review_gates/phase_1_2_spike_close.json:5 为 blocked_manual_review_count；:24-36 为 not_closed、allowed:false、owner_manual_decision_only。
- 生产入口仍未通电：main.py:67-69 只调用 run_outer_search；src/search/outer_search.py:899-954 的 terminal path 写 CANDIDATE_PROPOSED_STATUS 及 proposal-ready marker；src/search/outer_search.py:1969 返回 CANDIDATE_PROPOSED_STATUS。
- supervisor_seal() 存在但普通路径无法触发 CERTIFIED：src/search/exact_campaign.py:3566-3599 该方法委托给 L0 隔离验证；3601-3610 普通的 mark_campaign_stopped(..., 'CERTIFIED') 会直接 raise；3652-3664 save() 拒绝 unsupervised 的 proof-bearing checkpoint。
- 公开 publisher 同样不等于已发布：src/search/certified_surface.py:758-878 要求 sealed/disk-current/evidence/gate 齐全并走 stage-commit-verify-rollback 四段事务；497-544 规定 gate 缺失、非 closed、next not allowed、无 owner decision 中任一情况都会阻止发布。
- topology-opt 实测：git log main..topology-opt --oneline 无输出；git diff main...topology-opt --stat 无输出；git merge-base main topology-opt 结果即为 26931e8（说明 topology-opt 已是 main 的祖先，无未合入内容）。
- topology-opt 内容性质：src/search/topology_binding_guidance.py:1-18、src/search/topology_route_hint.py:1-20 均在文件头明确声明自己是 diagnostic/unwired、never feeds proof；src/tests/test_topology_hint_isolation.py:61-119 有专门测试验证它未被任何非测试模块引用、未接入 binding/routing 主链、未进入 frozen artifacts 清单。
### risks
- 不能从当前 main 端到端发布 CERTIFIED 结果：缺生产 supervisor 入口（supervisor_seal() 仅测试代码调用），owner 手动 review gate 关闭（data/review_gates/phase_1_2_spike_close.json 为 blocked_manual_review_count），main.py 正常运行只会走到 CANDIDATE_PROPOSED，无法自动产出 CERTIFIED。
- 分支状态本身构成潜在决策风险：若直接从 main 发布，会缺失 pr2 round-19 的 close-kernel 结构硬化（父锚校验、checker 自完整性、sink/source-sha floor、witness/reverifier 绑定等）；若要合入 pr2，必须基于合并后的真实树重新走 freeze-ritual/reseal 全套流程，不能复用旧 hash 或 README 记录的历史 hash（本仓库历史已被重建，旧 hash git cat-file 均不可解析）。
- pr2 的 checker 硬化只是结构门（structural gate），不证明求解数学正确性：manifest 自身仍把 Python/stdlib/OR-Tools/操作系统/文件系统/人工 review 等列为 TCB（可信计算基），即便 pr2 合入并通过，也不能等同于数学证明闭合或 release closure。
- pr2 分支的 data/proof_obligations/pr2_dependency_floor_manifest.json 在 manifest 中仍标记为 deploy-pending 占位（pr2 分支 data/proof_obligations/p1_2_proof_obligations.json:824, 835, 911-923），意味着即便代码合入，生产部署前仍需要在目标环境重新生成/审查/钉死该 manifest，属于额外未完成工作项。
- 当前工作树存在脏改动（cc_memory_vnext/cards/guardrail-delegate-adversarial-reads.md 未提交），而最终 release 快照要求 immutable commit/materialized snapshot，脏树状态不能直接作为公开发布的基线，需要先清理/提交。
### open_questions
- owner 仓库外部保存的 clean-review 计数（用于 P1.2 关闭判定）当前具体数值是多少，仓库内文件无法确认（按设计刻意存在仓库外）。
- pr2 round-19 的 commit message 自称已跑过 full preflight/slow-tests 并通过，但因只读调查纪律未实际运行这些命令，未能独立复验该断言的真实性。
- git merge-tree main pr2-5-domain-frontier-gate 只读输出了单个 tree id、未显示冲突标记，但这不等同于合并后 checker/preflight/reseal 一定能顺利跑通，实际合并可行性仍需真正执行合并流程才能确认。
- 本次只读调查未在仓库内发现任何生产级 supervisor CLI/launcher；若此类入口存在于仓库之外（例如 owner 本机其他位置），本次调查范围无法验证其存在或成熟度。


# DIM release — release 边界与开放问题
## fable summary
P1.2 是本项目的发布关口，现状是"机器层全绿但人门锁死"。代码里发布链三权分立且反绕过是硬编码的：求解产出方(producer)只能写 CANDIDATE_PROPOSED；唯一能盖持久 CERTIFIED 章的是 supervisor_seal()，但它目前只有测试调用、没有任何生产入口——跑完 main.py 只会得到"候选已提案"；就算内部盖了章，公开发布器还要再过 resolve_p1_2_publish_open_gate() 这道人工门，它只认 gate 文件里 owner 亲手写的 closed 形态(status=closed_manual_owner_decision 等三个字段同时为真)，缺失/畸形/symlink 一律视为未开。gate 文件当前 status=blocked_manual_review_count；关门标准是连续 3 次干净的全面外审，计数由 owner 在仓库外手记，仓库刻意不记录也不推导 0/3~3/3。PROJECT_LOCK 用约 80 条 F-*/PCR-*/CUT-* fail-closed 条款把认证边界逐条焊死(§3/§3A/§4)。距离"真正 done"，代码活包括：PR2 #7 生产 certify 入口(最后通电)、PR2 TCB 收缩(#1/#2/#3/#5/#8/#9a/#9b/#9c 多为 partial 或 greenfield)、release snapshot 改从不可变 commit 物化、dependency-floor 在生产机(CachyOS+Py3.13)重生成重钉；owner 手动动作包括：数满 3 次 clean review、对 post-v99 工作树 fresh reseal(v99 锚是过期时间点快照)、以显式 owner_manual_decision 亲手改写 gate JSON。两侧互不替代，任何 checker 绿/测试绿/内部 seal 都不得改写为 release closure。
### key_facts
- gate 文件当前状态：status=blocked_manual_review_count、owner_manual_state.p1_2_close_status=not_closed、p1_3b_entry_allowed=false、next_phase_entry.allowed=false、authority=owner_manual_decision_only（data/review_gates/phase_1_2_spike_close.json:5,24-25,32-37）
- clean-review 计数机制：required_consecutive_clean_full_reviews=3、counting_authority=owner_manual_count_outside_repo、repo_derives_clean_count_from_receipts=false，且明写"The repo intentionally does not record or compute 0/3, 1/3, 2/3, or 3/3"（gate JSON:9-13,30）；打断 streak 的五类 finding：unsound_cut / certified_false_negative / proof_obligation_bypass / fake_certified_claim / reachable_phase_gate_false_ready（gate JSON:14-20）
- v99_p1_2_close_kernel_sealing 是最后一个 owner 批准的 review 锚，但只是时间点 source-hash seal；post-v99 的 PR1/PR2 工作树改动不被旧 seal 覆盖，任何 close claim 前必须 fresh reseal（gate JSON:7,30；docs/PHASE_1_2_CLOSE_GATE.md:29-40）
- 发布门唯一开启形态硬编码在源码：status=="closed_manual_owner_decision" 且 next_phase_entry.allowed is True 且 owner_manual_decision.p1_3b_entry_allowed is True，缺失/畸形/symlink/异常一律 fail-closed 视为 open（src/search/certified_surface.py:45-46 常量、:497-546 函数体）；生产调用点 evaluate_certified_delivery_surface（certified_surface.py:151）与 publish_verified_certified_delivery_surface（:758）
- supervisor_seal() 是唯一 durable CERTIFIED mint（src/search/exact_campaign.py:3566），委托隔离子进程 run_l0_supervisor_seal（src/search/pr2_l0_micro_verifier_core.py:195）；codegraph callers 实测 23 处调用全部位于 src/tests/，全仓无生产调用方——main.py 的 run_solve 只进 run_outer_search（main.py:47-88）
- 反绕过守卫实测为硬编码：mark_campaign_stopped(status="CERTIFIED") 直接 raise RuntimeError（exact_campaign.py:3609-3610）；save() 检测 unsupervised CERTIFIED checkpoint claim（final_status/final_result.search_status/last_stop_reason 三处）并 raise（exact_campaign.py:3652-3665 与 :2564-2579）
- producer 终态只写 CANDIDATE_PROPOSED：_build_certified_result 的 search_status=CANDIDATE_PROPOSED_STATUS（outer_search.py:876），_commit_terminal_full_frontier_certified_result 两次 mark_campaign_stopped 均传 CANDIDATE_PROPOSED（:899-902,949-952），最后写 proposal-ready marker（:954）等待一个尚不存在的生产 supervisor 来消费
- resume 卫生（F-CAM-R8-01/02 落地实证）：checkpoint 载入的 CERTIFIED/INFEASIBLE 候选一律降 UNKNOWN、删 solution/candidate_proof/exact_safe_cuts、清 terminal_frontier_evidence（exact_campaign.py:2179-2285 _sanitize_resume_state_for_untrusted_candidate_evidence）
- PROJECT_LOCK §1A-C 的 P1.2 done-condition：12 条机器可查条件（命题 P scope 锁死、producer/mint 分权、supervisor 可执行入口、fixed-witness 身份绑定、公共发布单入口、OPEN-GATE、sink replay、I1 独立复验、隔离执行 bytecode binding、close-kernel checker、EXACT_* deny-unknown、snapshot 从 immutable commit 物化）+ 2 条 owner 手动条件（显式 owner_manual_decision 开 gate、机器条件全满足前发布保持关闭）（PROJECT_LOCK.md:148-185）
- PROJECT_LOCK 明列当前 open 项：无生产 supervisor CLI/launcher、main.py 终点 CANDIDATE_PROPOSED、PR2 read-once/controlled-loader TCB 未实现、review snapshot 打包器仍从 mutable treeish 物化且归档策略不全、roadmap 其它 OPEN/PARTIAL 边界（PROJECT_LOCK.md:130-137）
- F-*/PCR-*/CUT-* 条款全集分布：§3 Accepted Invariants（PROJECT_LOCK.md:252-357，约 70 条带编号条款）+ §3A B Design v2 冻结不变量（:359-449）+ §4 Forbidden Changes（:451-503）。按家族：F-CAM-PR1-01..04 = producer 只提案/supervisor 唯一 mint/publisher 单入口/seal 必要不充分（:252-266）；F-CAM-R6/R7/R8-01,02 = resume 撕裂态与强状态降级（:273-274,339,345）；F-SRC-R9-01 = source digest 须含 main.py（:276）；F78-F-01/02 + F-PS-R4/R5/R6/R7/R8 = 候选 solution 卫生与并行 wave 身份绑定/precheck 强写校验（:272,277,329,340,346）；F03-R3-01/F04-R4-01..04 = wireless routing-free commodity 全消费点排除（:281）；F-BIND-R1..R10+BS-01 = generic I/O fail-closed 装载/单快照/精确有理 ceiling（:282-287,318-319,331,347）；F-PRE-R8..R18+H-PRE-R19/BS-01 = 预处理严格解析/schema 边界/cycle-group 闭包（:288-300,330,338,344,349）；F-RT-R2..R5+BS-R5-01 = 路由极性/层守恒/connector 终端/域裁剪（:304-309,355）；F-GM-Q3/R6/R7/R8/R11..R14+BS-R2-01 = master 下界/切后见证失效/hint 只导引/对称破缺/pose-bool 后端义务（:312-317,333,336,342,350）；F-BL-R3/R4/R7..R10+BS-01 = 预算耗尽非证明/子问题状态契约 deny-unknown（:320,334-335,341,348）；F-CUT-R2-01+CUT-R3/R4/R8/R9/R12..R16-H1 = cut 只对必然激活端口量化/separator 松弛证明义务/power witness ghost 上下文（:321-328,332,337,343,353）；PCR-R5-H1..H4+PCR-CUT-R6-H1 = patch 模型必须是全路由的松弛（边界松弛全层/极性/常量支撑/签名提升防重）（:323-324）；F-SCHED-BS-R3/R4/R5-01,02 = 并行 worker 崩溃 seal 四连（:352,354,356-357）
- PROJECT_LOCK 登记的 5 条 default-env 可达 certified soundness reset（均已修复+红绿回归）：F-GM-BS-R2-01（boundary-port 预筛错把 connector 当 footprint → 假 INFEASIBLE 剪真最优）、F-SCHED-BS-R3-01/R4-01/R5-01/R5-02（worker 崩溃时序族：崩溃 wave 的假 INFEASIBLE 变 sticky 强状态 → false-CERTIFIED of optimality）（PROJECT_LOCK.md:350-357）
- README 开放问题四份清单：第 1 章 §9 共 13 条（README.md:236-248）；第 2 章 §9 共 10 条（:598-607，含 PR2 执行序与 resume-envelope 押后项）；第 5 章末 12 条文档-实现不一致（:1677-1690，含 preflight exit code 文档错误、reseal 无 runbook、blob OID 两版不一致）；第 6 章 = PR2 剩余表 + 盲点 A-H（:1865-1971）
- PR2 剩余项状态表（README.md:1865-1877）：#4 子进程隔离=done；#8 argv0 digest=greenfield；#9a floor pin=partial；#5 B2 候选域独立枚举=partial（当前 close-kernel 门所在）；#2 受控 loader 最小快照=partial；#3 fd-held read-once=partial；#7 certify 生产入口=greenfield（go-live 最后通电=P1.2 闭合收敛点）；#1 最小 TCB 闭包=partial（大，含 #5-F import-time 三部分其中 part3 是开放设计问题 :1879-1883）；#6 AST 可达性闸=已决定不建；#9b OS 写隔离=greenfield（大）；#9c 原生 .pyd/.so TOCTOU=partial
- dependency-floor manifest 是 deploy-pending 占位（钉的是审计 Linux 沙盒字节非生产 canonical），生产前必须在 CachyOS+Py3.13 跑 generate_pr2_dependency_floor_manifest.py 重生成+审+重钉 = PR2 #6，本机 Windows/WSL 做不了（README.md:1847-1855）
- gate 要求两个 doc marker：docs/PHASE_1_2_CLOSE_GATE.md 须含 "owner manual decision"、README.md 须含 "owner-maintained outside the repo"（gate JSON:387-396）；两文件实测存在（Glob 命中 docs/PHASE_1_2_CLOSE_GATE.md，其 :19-22 正是 authority model 段）
- gate JSON informational_history 记录 V28→V99 约 30 个外审包全史，V81..V98 每包结尾都是 "Owner clean-streak count resets to 0"——每轮外审都找到真 soundness bug 并清零计数（gate JSON:38-386）
- 距离 done 的完整差距清单——代码活：①PR2 #7 生产 supervisor 入口（从 proposal-ready marker 驱动独立 supervisor，PROJECT_LOCK.md:154）②PR2 #5/#2/#3/#1 TCB 收缩精化 ③#8 argv0 内容 digest ④#9b/#9c OS 级与原生扩展隔离 ⑤release snapshot 改物化已解析 immutable commit + 归档策略收口（:176-177）⑥roadmap OPEN/PARTIAL 几何/规格边界处理（:133-135）；owner 手动动作：①在仓库外数满 3 次连续 clean full review ②对当时工作树做 fresh technical reseal（V99 锚过期）③以显式 owner_manual_decision 把 gate JSON 改成 closed 形态（status=closed_manual_owner_decision + next_phase_entry.allowed=true + owner_manual_decision.p1_3b_entry_allowed=true）④CachyOS 生产机上重生成 dependency-floor 属 owner 侧运维（本机做不了）⑤pr2-5-domain-frontier-gate 分支（+8700 行 checker 硬化，未合入）的合并决策
### risks
- 整条链唯一零机器强制的环节是 owner 的 3-clean-review 计数与 gate 改写：计数只在仓库外（gate JSON:30 "The owner keeps the count"），若 owner 侧记录丢失/长期中断，仓库内无法重建进度，release 无限期悬置
- PR2 #7 certify 生产入口是 greenfield 且被刻意留到最后通电；它未来的端到端发布流程从未被任何对抗审覆盖，而它正是触及 release closure 语义的最危险点（README.md:1959 盲点 F）
- v99 锚已过期 + reseal 操作无单一权威 runbook（LF/CRLF、pathspec 全集、hash 来源历史上均踩过坑，README.md:1681）：close 前的 fresh reseal 本身是高出错环节，做错会本地绿 CI 挂或产生无效 seal
- F-SCHED-BS-R3..R5 四连证明：documented 生产路径（main.py --parallel-processes）上 worker 崩溃时序曾多轮产生可达 false-CERTIFIED，且 terminal validator 只做持久状态的自洽性检查、不独立复验（PROJECT_LOCK.md:352-357）——同族残余时序可能仍存在，这是 clean-review 被打断的高危面
- README 盲点 E（两版都判最重要）：master/binding/routing 的 CP-SAT 约束编码忠实性从未被逐约束对抗审，I1 复验器只兜住已登记的 whole-layout nogood 路径；发布面审了几十轮已饱和，内核欠审的结构性不对称意味着 3-clean-review 即使数满也可能漏内核级 false-INFEASIBLE（README.md:1936-1947）
- 状态分裂风险：round-18 的 +8700 行 checker 硬化只活在未合入、未 push 的本地分支 pr2-5-domain-frontier-gate，交接/换机若不带 branch bundle 这段进展会丢（README.md:607,1969-1971,1982）
- 收敛判据在哲学上开放："审到零发现"明确不是收敛判据，owner 接受的三类 conspicuous-edit 残余（checker-self、A4 反射、import-time #5-F part3）是工程裁定而非数学消除，其中 #5-F part3 连设计 spike 都没做过（README.md:604,606,1922-1925）——任何一处被构造出 silent 绕过即重开裁定并清零计数
### open_questions
- owner 当前 clean-review 计数到几（0/3 还是更多）——按设计仓库内不可查，本次调查无法确认；gate JSON 的 informational_history 只记到 V99 且 V81-V98 全部 reset to 0
- CLAUDE.md 称 resolve_p1_2_publish_open_gate 在链上"被查 3 次"，本席经 codegraph 只定位到 2 个生产调用点（certified_surface.py:151 与 :758）；第三处可能在 publish 事务内部重查，未逐行核实
- 两个结构 checker（check_p1_2_proof_obligations.py / check_strong_status_write_allowlist.py）"当前在 main 上绿"取自 README 记载（~3346 passed / checker PASS 输出），按只读纪律本席未实跑复核
- pr2-5-domain-frontier-gate 分支的 +8700 行硬化相对 main 具体覆盖 PR2 #5 到什么完成度、README 剩余表中哪些 partial 项在该分支上已有进展，未逐 commit 比对（README.md:607 也明示应由接手者重核）

## codex summary
我(Codex)独立只读核查后的结论:当前仓库距离"真正 done"还不是差一个绿灯,而是差一整段被明确写出来的 release 操作链。P1.2 现在仍是 release-blocked:权威 gate JSON 当前 status="blocked_manual_review_count",clean-review 计数由 owner 在仓库外维护,仓库代码刻意不从 receipt/report/package/git/source manifest/clean-count/supervisor seal 推导关闭状态。即使 producer 跑到终态,也只写 CANDIDATE_PROPOSED;真正 durable CERTIFIED 只能由 ExactCampaign.supervisor_seal() 经 PR2 L0 mint;公开发布又必须走 publish_verified_certified_delivery_surface(),而它在发布前和 commit 前都会 fail-closed 查 P1.2 gate。

代码活主要是:补生产 certify/supervisor 入口、完成 PR2 TCB 收缩与 read-once/controlled-loader/OS-write-isolation/native-TOCTOU 等剩余项、解决 release snapshot 从可变 treeish 物化与 archive policy 不完整、生产 dependency floor 重生成/审/重钉,并在同一工作树完成 checker/full gate/slow lane/外审。owner 手动动作是:仓库外数满 3 次连续 clean full review,并显式写入合法 owner_manual_decision 打开 gate;没有这个动作,任何机器绿灯都不能发布 CERTIFIED。

PROJECT_LOCK.md 中 F-*/PCR-*/CUT-* 条款覆盖:producer/supervisor/publisher 三权分立(F-CAM-PR1-01..04)、candidate strong-status replay/source digest/parallel identity/generic I/O/strict JSON/single snapshot 等 accepted invariants、preprocess schema/geometry/cycle guards、routing front/domain/connectivity 约束、master optional bounds/cut invalidation/hints/symmetry、pose-bool env backend 隔离、binding/routing status contracts、cut-family(F1-F9)相关的 exactness/area-based counting/tight-K quarantine 等条款,以及 Forbidden Changes(禁止把 exploratory 流程当 certified proof、禁止低于 min_side 发布 CERTIFIED、禁止启用 EXACT_POWER_PLACEMENT_SUBPROBLEM=1 到生产等)。README 记录的开放问题去重后包括:P1.2 未闭、无生产 seal 路径、PR2/TCB/read-once/loader/close-kernel 残余、吞吐 out-of-scope、candidate geometry hash-pinned TCB、F1-F9 cut lifecycle 未接生产、结构 checker 非 soundness、dependency floor deploy-pending、算法核心审查不足、OS/native/production certify 入口未审。
### key_facts
- 权威顺序:PROJECT_LOCK.md 是 release 边界最高权威,README 只是 handoff 史料,证明/认证断言必须回源码核实。来源:CLAUDE.md:9-15,README.md:7-9。
- 当前 gate JSON 明确 blocked:status="blocked_manual_review_count",p1_2_close_status="not_closed",p1_3b_entry_allowed=false,next_phase_entry.allowed=false。来源:data/review_gates/phase_1_2_spike_close.json:5-7,:23-36。
- clean-review 机制:要求 3 次连续 clean full review;计数权威是 owner_manual_count_outside_repo;repo 不从 receipts 推导计数;receipt 只是 informational。来源:data/review_gates/phase_1_2_spike_close.json:9-21,:26-30,:404-408。
- 打断 clean streak 的 finding 类:unsound_cut、certified_false_negative、proof_obligation_bypass、fake_certified_claim、reachable_phase_gate_false_ready。来源:data/review_gates/phase_1_2_spike_close.json:14-20。
- publisher gate 只接受显式 owner-closed 形态:closed_manual_owner_decision + next_phase_entry.allowed=true + owner_manual_decision.p1_3b_entry_allowed=true;缺失、畸形、open、blocked 都返回'open and blocks publication'。来源:src/search/certified_surface.py:45-46,:497-546。
- public publisher 在发布前查 gate,staging 后 commit 前再查一次;失败会 rollback/clear,不能留下半发布面。来源:src/search/certified_surface.py:758-808,:830-878。
- producer 终态只构造 CANDIDATE_PROPOSED,提交 proposal-ready marker,不 mint CERTIFIED。来源:src/search/outer_search.py:855-877,:890-954,:1940-1969。
- main.py 只调用 run_outer_search(),没有调用 supervisor_seal();status=="CERTIFIED" 分支只做 visualization。来源:main.py:47-88,:304-329。
- durable CERTIFIED 唯一 mint 是 ExactCampaign.supervisor_seal(),它只接受 CANDIDATE_PROPOSED proposal,并委托 run_l0_supervisor_seal();普通 mark_campaign_stopped(..., "CERTIFIED") 直接 raise。来源:src/search/exact_campaign.py:3428-3507,:3566-3610。
- save() 拒绝 unsupervised proof-bearing terminal checkpoint,要求 proof-bearing terminal checkpoint 必须由 supervisor seal 写。来源:src/search/exact_campaign.py:3652-3665。
- L0 supervisor seal 从 canonical dependency floor、proposal-ready marker、checkpoint bytes 校验后原子写 certified state,并在写后复验;显式路径 loader 不给 run_l0_supervisor_seal caller 选择。来源:src/search/pr2_l0_micro_verifier_core.py:195-230,:300-388,:1078-1084。
- phase gate checker 明确反自动计数:拒绝旧自动 authority keys,要求 repo_derives_clean_count_from_receipts=false、owner_clean_count_status=maintained_outside_repo,owner decision 必须承认 repo 不证明 clean count 且 owner 已核三次 clean。来源:scripts/check_phase_review_gate.py:110-143,:146-231。
- proof-obligation checker 把 phase gate 作为结构约束:P1.3B 只能由 owner manual decision 打开,receipts informational,repo 不推导 clean count;并禁止旧 receipt/package/git authority parser 复活。来源:scripts/check_p1_2_proof_obligations.py:2850-2925。
- close-kernel checker 不是 theorem prover:它不认证 candidate、不推理 geometry,只封 proof-bearing authority surface。来源:scripts/check_p1_2_proof_obligations.py:1-6,:4245-4252。
- PROJECT_LOCK 的 P1.2 done-condition 明确缺项:无生产 supervisor 调度入口、owner manual gate 未开、PR2 TCB 收缩与 release snapshot/policy 未完成;checker pass/局部回归/internal seal 都不得改写为 release closed。来源:PROJECT_LOCK.md:130-146,:148-185。
- F-CAM-PR1-01..04:producer 只提 proposal;supervisor seal 唯一 durable mint;central publisher 唯一 public publisher;P1.2 owner gate 必须独立 closed。来源:PROJECT_LOCK.md:252-266。
- 其它 F/PCR/CUT 条款集中在 accepted invariants:candidate strong-status replay、source digest、parallel identity、generic I/O、strict JSON、single snapshot、preprocess schema/geometry/cycle guards、routing front/domain/connectivity、master optional bounds/cut invalidation/hints/symmetry、pose-bool env backend、binding/routing status contracts、F-CUT/PCR/CUT separator/patch/power-witness obligations、parallel scheduler crash seals 等。来源:PROJECT_LOCK.md:272-357。
- B Design v2/Cut-family 条款:Exactness FP=0、F9 只能 area_capacity_overflow、F9 area-based counting、F5/F6/F7/F8 SoT gate、F9 tight-K quarantine、RAM 必须用 RSS、代数归 Master/几何归 Cut。来源:PROJECT_LOCK.md:359-449。
- Forbidden Changes 包括:把 exploratory/diagnostic flow 当 certified proof、低于 min_side 发布 CERTIFIED、新 candidate_generation/EXACT_* 未分类、启用 EXACT_POWER_PLACEMENT_SUBPROBLEM=1 到 certified/production、绕过 cut lifecycle、silent recovery。来源:PROJECT_LOCK.md:451-503。
- README 全部开放清单去重后包括:P1.2 未闭、无生产 seal 路径、PR2/TCB/read-once/loader/close-kernel 残余、吞吐 out-of-scope、candidate geometry hash-pinned TCB、F1-F9 cut lifecycle 未接生产、结构 checker 非 soundness、dependency floor deploy-pending、算法核心审查不足、OS/native/production certify 入口未审。来源:README.md:234-248,:596-606,:974-987,:1679-1688,:1909-1960。
- 本地 git 现状:当前 main HEAD 是 c59a65f,README 里旧 b35e5f9 和 9bbb3a6 在此交付副本不可解析;pr2-5-domain-frontier-gate 分支存在但 tip 是 5ff31ac,未合 main。当前 final_solution.json、optimal_blueprint.json、certified_delivery_manifest.json、exact_campaign_state.json 均不存在于工作树。CHANGELOG.md 顶部同样记录:当前 launcher 不调用 supervisor_seal(),owner gate 仍 blocked,PR2 TCB/snapshot/archive 仍开。
- 全仓检查未发现从 CANDIDATE_PROPOSED 到 supervisor_seal() 的生产 certify 入口;scripts/export_industrial_planner_bundle.py 虽调用 central publisher,但前提是已有 publishable surface,不是生产 certify 入口本身。
### risks
- 最终目标要求'端到端产出并公开发布 CERTIFIED 结果',但当前没有生产 supervisor/certify 入口;正常 main.py 成功也只会停在 CANDIDATE_PROPOSED。
- owner 手动 gate 是硬阻塞;仓库设计上无法、也不应该自动证明 clean-review count。没有 owner 显式 closed decision,发布链必须 fail-closed。
- PR2 hardening 即使 clean,也只是让未来 release 更可信;它不能授权 release。当前 branch 状态和 README 史料还有漂移(round-19 5ff31ac vs README 讲的 round-18/9bbb3a6),发布前必须在同一目标工作树重新核实。
- close-kernel 结构门不能证明数学正确性;最终 CERTIFIED 的可信度仍依赖 master/binding/routing 编码忠实性、frozen artifacts、named TCB、人审与外审。
- src/cuts/ F1-F9 尚未接生产 master;若未来为 P1.3 接入,必须先处理 README/PROJECT_LOCK 记录的 latent false-INFEASIBLE 几何原语问题。
- 吞吐/带宽/离散容量流不是当前 CERTIFIED 命题;公开发布时过度声称会越过 PROJECT_LOCK 边界。
### open_questions
- Codex 没有运行 preflight、pytest、solver、publisher 或任何会写状态/长耗时命令;所以没有独立证明当前 checkout 的 gates 通过。
- owner 仓库外 clean-review count 无法从仓库内得知;这正是设计边界,非调查疏漏。
- pr2-5-domain-frontier-gate 当前 tip 已到 round-19(5ff31ac),而 README 多处仍讲 round-18/9bbb3a6;需要单独审 branch worktree 后才能判断 PR2 #5 当前是否 merge-ready。
- release snapshot immutability/archive-policy 的具体剩余 patch 只按 PROJECT_LOCK/README 确认'未完成',没有继续展开实现方案细节。
- 算法核心约束编码忠实性是 README 明确点名的盲点;本次任务范围是 release 边界,没有做逐约束 soundness 审计。


# DIM tests — 测试体系与盲区
## fable summary
测试体系规模很大:src/tests 递归共 432 个 test_*.py(约 5.6MB 源码、3173 个测试函数),其中顶层 145 个文件 1419 个函数、phase3b 子树 264 个文件、cuts 23 个。慢测试不用散落装饰器,而是集中登记在 conftest.py 的 _SLOW_TEST_NODEIDS(实数 46 条 nodeid),收集期自动打 slow 标;快 gate 用 -m "not slow" 跳过,专用慢 lane(preflight --slow-tests,串行、2400s 超时、收集不到 @slow 会硬 BLOCK)真跑到完成。认证核心覆盖是这套体系的强项:supervisor_seal 有 23 处调用全在测试里(主力 test_p1_2_supervisor_pr1.py 约 17 个拒绝/接受用例),publish 发布器由 test_exact_campaign_inspector/test_exact_contract/test_p1_2_open_gate_publish_block 覆盖,隔离子进程验证器由 test_pr2_l0_micro_verifier_core.py 用真实 -I -S -B 子进程加篡改/TOCTOU/依赖地板攻击测试,两个结构 checker 各有专门的"攻击 checker 本身"的测试且 checker 在每种 preflight 模式都必跑。但保障强度有明确折扣:①绝大多数 seal/publish 端到端测试(含旗舰 test_toy_project_can_be_truly_certified)用 monkeypatch 把真实子进程验证器换成"直接接受"的桩,真子进程链只靠 micro-verifier 单元测试和少数 true-replay 用例兜底;②CI 主 gate(--ci)只跑 CORE_TEST_FILES 约 10 个目标,慢 lane 只跑 46 条 @slow,两者之外的"中间地带"(包括 412KB 的 test_master.py、supervisor_pr1 大部分用例、micro-verifier、allowlist 行为测试)只有本地手动 --full 才跑,CI 永远不碰;③--full 仍排除 slow;④candidate_placements.json 缺失时 binding/routing 测试在 fixture/用例内硬报 FileNotFoundError 而非 skip;⑤pytest-randomly 本机未装但 CI 装(dev lock 钉 4.1.0),本地/CI 测试顺序不对称;⑥全局 basetemp 并发互踩;⑦快 lane 里 pytest 不可用只 warn 不 block。总体:对"认证状态机不被绕过/伪造"的对抗性保障非常强,但对"CP-SAT 建模数学正确"只靠 toy 端到端+子问题单测,且 CI 覆盖面远小于本地 --full,证明正确性的最后一环(真子进程 seal 全链)测试密度偏薄。
### key_facts
- src/tests 递归共 432 个 test_*.py、约 5,636,764 字节、3173 个顶格 test 函数;顶层 145 个文件 1419 个函数,phase3b 子树 264 个、cuts 23 个(实测 PowerShell 递归统计)
- 慢测试集中登记:src/tests/conftest.py:91-143 的 _SLOW_TEST_NODEIDS 实数 46 条 nodeid,pytest_collection_modifyitems(conftest.py:162-173)在收集期自动加 slow 标;设计说明写明阈值为 call 阶段 >=8s、靠 --durations 扫描重调
- conftest.py:59-73 另有 _FIXTURE_GUARDS 缺工件自动 skip 机制,但只覆盖 industrial_planner e2e/phase3b 工件/temp_scripts 三类,不覆盖 candidate_placements.json
- candidate_placements.json 缺失=硬失败而非 skip:test_binding.py:16-23 的 session fixture 直接 read_text,test_routing.py:409/434/458 在用例内直接读,无 try/except 无 skip 守卫(当前本机该文件存在,45,773,799 字节)
- 快 gate 无条件排除 slow:scripts/preflight_gate.py:679 `cmd += ["-m", "not slow"]` 对 staged/hook/ci/full 全部生效;--full 的 label 也写明「跳过 @slow」(preflight_gate.py:666)
- 慢 lane check_slow_tests(preflight_gate.py:726-773):串行(刻意不加 xdist,注释说明 ④b 隔离 replay 叠加并行会 flaky)、2400s 超时、exit 5(未收集到 @slow)在 require_collection=True 时硬 BLOCK(run_gate:791 传 True)
- CI 主 gate 只跑核心测试:run_gate(preflight_gate.py:808-813)在 --ci 下走 check_tests(full=False),即只跑 CORE_TEST_FILES(preflight_gate.py:379-394,约 10 个目标:test_exact_contract、test_parallel_scheduler、5 个 cut/power 文件、test_phase_review_gate、test_p1_2_proof_obligations、cuts/ 目录)
- CI 全貌(.github/workflows/project_foundation.yml):主 job 跑 preflight --ci(第 56 行),独立 slow-soundness-gate job 先用 src/placement/placement_generator.py 重新生成 candidate_placements 再跑 --slow-tests(第 85-91 行);另两个 workflow 只跑 industrial planner 定点回归——没有任何 CI job 跑全量 fast suite
- supervisor_seal 共 23 个调用方、全部在 src/tests(codegraph callers 实测):主力 test_p1_2_supervisor_pr1.py 约 17 个用例(拒绝 digest 篡改/run_id 不匹配/非零 exit code/sink replay 违规等),另有 test_exact_contract.py:967、test_parallel_scheduler.py:215 的 helper 和 capsule/terminal_verifier/open_gate 文件
- 多数 seal 端到端测试桩掉真子进程:test_exact_contract.py:924-933 _install_accepting_supervisor_seal_replay 注释明言「its L0 entrypoint writes a faithful CERTIFIED checkpoint without launching the true child verifier」,并把三个模块的 has_valid_terminal_full_frontier_certified_evidence 一并 monkeypatch(:955-964);旗舰 e2e test_toy_project_can_be_truly_certified(test_exact_contract.py:3136-3175)也走这个桩
- 真子进程链的兜底:test_pr2_l0_micro_verifier_core.py 用真实隔离子进程做 round-trip(41-50 行 stage_trace 四阶段)并覆盖 sys.path 阴影/快照 digest 篡改/加载期 TOCTOU 换文件/依赖地板越界导入等攻击,:132 断言 argv 含 -I -S -B -X pycache_prefix;test_p1_2_supervisor_pr1.py:403-456 有一条不打桩的 true fixed-witness replay 真 seal 用例;test_p1_2_sink_replay_authority.py:381 的全 sink replay 存活用例在 slow 集里
- publish 发布器覆盖:publish_verified_certified_delivery_surface 12 个调用方中 10 个在测试(test_exact_campaign_inspector.py:247/682/735/794、test_exact_contract.py:982/8180、test_p1_2_open_gate_publish_block.py:99),生产侧仅 certified_surface.py:881 与 scripts/export_industrial_planner_bundle.py(codegraph callers 实测)
- 两个结构 checker 的测试都包含「攻击 checker」用例:test_p1_2_proof_obligations.py:20-22 以 subprocess 跑真 checker 脚本,后续几十个用例直接对 _check_certified_publication_boundary_contract/_check_close_kernel_contract 注入 rollback 删除/decoy 注释/sink hash 漂移等;test_strong_status_write_allowlist.py 有 15 个用例覆盖未登记写点的各种伪装(getattr/别名/动态 key/setattr 等);且两 checker 在 run_gate 所有非 slow 模式必跑(preflight_gate.py:803-804)
- pytest-randomly:requirements.txt:3 与 requirements-dev.lock.txt:7(==4.1.0)都声明,CI 安装 dev lock(project_foundation.yml:45),但本机 pip show 实测「Package(s) not found: pytest-randomly」——本地顺序固定、CI 顺序随机,不对称
- pytest.ini:2 全局 addopts --basetemp=.pytest_tmp,并发跑 pytest 会互删临时目录;pytest-xdist 本机已装(3.8.0),快 lane 在 xdist 可用时自动 -n auto(preflight_gate.py:680-681)
- 快 lane pytest 不可用只 warn 不 block(preflight_gate.py:722-723 gate.warn「pytest 不可用,跳过测试」),慢 lane 同情形因 require_collection=True 会 block(:768-773)
- conftest.py:189-212 autouse fixture 每测试前清 master_model 的 6 个模块级缓存保证 hermeticity——说明历史上确实发生过随机顺序下的缓存污染 flake
### risks
- CI 测试覆盖存在大片「中间地带」:既不在 CORE_TEST_FILES 也未标 slow 的测试(含 412KB 的 test_master.py、test_p1_2_supervisor_pr1.py 大部分用例、test_pr2_l0_micro_verifier_core.py、test_strong_status_write_allowlist.py、test_p1_2_fixed_witness_* 全部)在 CI 任何 job 都不跑,只靠本地手动 --full——认证核心的对抗性回归可能在无人察觉下失效(preflight_gate.py:379-394/808-813 + project_foundation.yml 实测)
- 真子进程 seal 全链(producer→真 L0 child verify→publish)端到端密度偏薄:旗舰 toy e2e 与几乎所有 seal/publish 测试都用 accepting 桩(test_exact_contract.py:924-933),真链只有 micro-verifier 单元层 + supervisor_pr1 一条 true-replay + slow 集里少数 replay 用例;若真子进程链引入回归,快 lane 大概率全绿
- --full 仍排除 slow(preflight_gate.py:679):改认证核心后若忘跑 --slow-tests,~46 条重型 soundness 测试(含 ④b 隔离 replay、campaign resume、全 sink replay 存活)是盲区——这正是文档记录的 C5 盲区模式,流程上只靠人记得
- 慢测试登记是纯手工集合(conftest.py:91-143):新写的慢测试若忘登记会在快 lane 里撞 120s/1200s 超时,把无关失败一起吞掉;没有自动机制检测「该标 slow 而未标」
- candidate_placements.json 缺失时 test_binding/test_routing 成批 FileNotFoundError 硬失败(test_binding.py:16-23),错误面貌像「一批测试莫名 error」,浪费排查时间且可能掩盖真实失败;conftest 已有 skip-guard 机制却未接入该工件
- 本地/CI 测试顺序不对称(本机无 pytest-randomly、CI 装 4.1.0):顺序依赖型 bug 只在 CI 随机序下偶现、本地默认不可复现,而认证链测试大量依赖文件系统状态,这类 flake 会侵蚀对慢 lane 红灯的信任
- 快 lane 对 pytest 缺失 fail-open(preflight_gate.py:722-723 只 warn):极端环境损坏场景下门禁可能在没跑任何测试的情况下 PASSED (with warnings)
- 测试体系证明的是「认证状态机不可绕过/登记结构不漂移」,不证明 CP-SAT 建模与 6 谓词语义的数学正确性——语义正确性实质押在 toy 项目(1x1 ghost rect)端到端与子问题单测上,70x70/266 设施规模的真实 CERTIFIED 从未被任何测试端到端产出过(与 PROJECT_LOCK『checker PASS ≠ release closure』一致,但意味着最后通电时仍可能暴露未测路径)
### open_questions
- CI 主 gate 只跑 CORE_TEST_FILES 是刻意设计(时间预算)还是历史遗留——仓库文档(CLAUDE.md/README)描述 CI 为「主 gate + slow lane」,未见任何地方明示「全量 fast suite 无 CI 覆盖」这一后果,无法确认 owner 是否知情
- test_p1_2_supervisor_pr1.py:403 的 true-replay 用例未列入 _SLOW_TEST_NODEIDS,其真实耗时是否 <8s(即真 L0 子进程 seal 在 toy 规模足够快)未实测验证——纪律禁止本次跑 pytest
- phase3b 子树 264 个测试文件(约占全部测试的 61%)对认证链的实际贡献度未逐一梳理,其中多少属于已废弃的 Codex 时代探索性回归无法在只读调查内界定
- requirements.lock.txt(CI 主依赖)含 pytest-xdist 但 dev lock 才含 pytest-randomly,CI 两个 job 都装了 dev lock,故 CI 顺序随机成立;但本地开发者是否被期望安装 dev lock 未见文档说明

## codex summary
测试用最小调用，验证 schema 是否接受基本结构。
### key_facts
- 测试事实一：来源 file:1
- 测试事实二：来源 file:2
### risks
- 测试风险一：依据 file:1


# DIM ops — 生产运行链路与算力现实
## fable summary
生产链路:python main.py 默认 --mode certified_exact、--campaign-hours 168(≥24h 即 production-class),启动前调 scripts/production_readiness_gate.gate_check()——该门是 Linux/CachyOS 导向(查 /etc/pacman.conf freeze、.venv/bin/python、preflight 86 守卫、OOM 余量),Windows 上必 BLOCK;随后起 freeze monitor 守护线程(每小时查 pacman freeze 标记,只告警不中止)。求解走 outer_search 按面积降序枚举候选矩形跑 LBBD;checkpoint 在 data/checkpoints/exact_campaign_state.json,168h 预算按 created_at 起的墙钟算(进程死掉也在烧);resume 校验 frozen artifact hash+源码 digest,不匹配即拒。Linux wrapper 自动注入 --resume-campaign 并配 watchdog(60s 检活重启);Windows run_prod_*.ps1 需手动 -ResumeCampaign,且没有绕 readiness gate 的口子,实际跑不了生产。candidate_placements.json(45,773,799 字节,本 checkout 在)由 data/external_artifacts.json 钉 hash,恢复只能本地复制+字节校验,无远端渠道。算力现实:所有实测记录一致指向"解不动"——baseline(workers=8,1800s)14h 跑 51-78 个候选 0 FEASIBLE;把用户手调 blueprint 正确答案整套喂给 CP-SAT 当 hint,27×15 候选在 3600s×8 P-core 满载下仍 UNKNOWN;anchor 分片估算单候选穷尽需 205 小时;2026-05-11 py-spy 证实 168h 主跑卡死在 master 构造;-p4 在 48GB 机上 9 分钟 global OOM;candidate 频繁 UNKNOWN 导致 campaign 实测 30 分钟一次短命退出,曾有 168h 大跑只实跑 15-17h。27 条加速范式全部实测死路,被判定唯一可行的 cut framework(F1-F9)至今未接入生产(step_8 仍 NotImplementedError)。结论:仓库内不存在任何一次全尺度 FEASIBLE/CERTIFIED 求解记录,以当前求解器结构+单机 48GB,证 70×70/266 的 lex 最优在算力上没有实证可行性;唯一"几乎保证可行"的 L11(钉死 blueprint 只解剩 41 个)会牺牲全局最优性,与认证命题直接冲突。
### key_facts
- production gate 触发条件:certified_exact 且 campaign_hours>=24(阈值常量 main.py:42,判定 main.py:277-293);默认 --campaign-hours=168(main.py:213),即默认就是 production-class
- readiness gate 是 Linux-only:docstring 自称『项目 Linux only,非 Linux 上 pacman check 会直接报错』(scripts/production_readiness_gate.py:27),pacman.conf 不存在即 BLOCK(:96-99),venv 固定查 .venv/bin/python(:114-122);且 check_disk_space 会 mkdir .artifacts,非纯只读(:189)
- OOM 实测记录在 gate 源码注释里:2026-05-14 双轮实测 -p4 9 分钟 global_oom、-p2 单 worker 飙 28GB swap thrash 人工 abort;默认按 30GB/worker+8GB host 估算,『48GB 本机现状: -p1 marginal, -p>=2 必 OOM』(scripts/production_readiness_gate.py:320-357)
- Linux wrapper 自动注入 --resume-campaign(『防崩溃重启忘加丢进度』, scripts/run_campaign_linux.sh:110-136),还做 jemalloc LD_PRELOAD+P-core taskset,并拒绝 EXACT_POWER_PLACEMENT_SUBPROBLEM(:31-41);Windows wrapper 必须显式传 -ResumeCampaign(scripts/run_prod_4x4_normal.ps1:18-20),用 PATH 上的 python 而非 .venv(scripts/_exact_runner_common.ps1:51-54),且不提供 --skip-readiness-gate 选项
- watchdog 注释是关键实测史料:『当前求解能力下 candidate 频繁撞 UNKNOWN, campaign 短命退出 (实测 30 min 一次), 168h budget 用不满』(scripts/campaign_watchdog.sh:5-11);『2026-05-11 教训: cap=100 时 168h 大跑只跑了 15-17h 就被强制停 + 烧电 0 产出 5h』(:41-46);watchdog 重启时把 master/binding/routing 提到 7200s(:60-63)
- UNKNOWN 是 certified campaign 的 terminal stop reason(candidate_returned_unknown, src/search/outer_search.py:1702-1717);EXACT_OUTER_SKIP_UNKNOWN 在 certified 下已改为 fail-close 而非 best-effort(outer_search.py:102-118;scripts/run_campaign_p2_workers1.sh:29-33)
- 168h 预算按 created_at 起的墙钟时间计算:remaining_seconds = campaign_hours*3600 - (now - created_at)(src/search/exact_campaign.py:3094-3097);耗尽时 mark campaign_time_budget_exhausted 以 UNKNOWN 停(outer_search.py:1991-2002)
- resume/checkpoint:状态文件 data/checkpoints/exact_campaign_state.json(main.py:170);save() 原子写+拒绝 unsupervised CERTIFIED(exact_campaign.py:3652-3665);campaign hash 闭包含 certified-exact 源码 digest(compute_exact_artifact_hashes, exact_campaign.py:419-444),README.md:220 记录 2026-06-16 曾故意借此打断旧 checkpoint resume
- 外部工件恢复链:data/external_artifacts.json 钉 candidate_placements 45,773,799 字节 sha adcc2a6e...,restore_hints 注明旧 53,594,995 字节版本 hash-incompatible;restore_external_artifacts.py 只支持本地 --source 复制+字节校验(scripts/restore_external_artifacts.py:25-44);实测本 checkout 文件在且大小吻合(Get-Item data/preprocessed/candidate_placements.json = 45773799)
- 算力实测核心记录:baseline(workers=8, master_seconds=1800, 无 hint)14h 跑 51-78 candidates 全 UNKNOWN/INFEASIBLE、0 FEASIBLE(docs/lever_verdicts.md:9);27×15 候选在 hint 完整注入(266 实例×3=798 AddHint 验证零损耗)+3600s+8 P-core 满载下仍 UNKNOWN(docs/lever_verdicts.md:117-189)
- 单候选穷尽成本估算:单 anchor 5min UNKNOWN(5.5M branches、8 亿 propagation),完整 partition 5min×2464 anchor=205 小时/候选,判『物理不可行』(docs/lever_verdicts.md:221-231);锁 anchor 后 master 仍有 3,853,132 个 mandatory pose literal(:222)
- 2026-05-11 py-spy 证实 168h 主跑卡死在 master 构造(docs/research/paradigm_search_review_v12_with_code_20260520/shared_infra/src/models/master_model.py:6834 注释);B5A sprint 从未找到 certified anchor(docs/phase3b_gpt54pro_help_request_20260422.md:88-111)
- 范式死路总账:27 条 lever 全部实测否决,4 个共同根因=pose-bool master 表达力上限、~98% utilization 几何死结(4800/4900)、cell-front 打碎对称、单机 48GB RAM 不可扩且硬件方向被用户排除(docs/项目说明/03_paradigm_death_baseline.md §4.8);2026-05-16 cleanup session 判『破 0 FEASIBLE 已全 lever verify 死路』(docs/cleanup_session_20260516.md:17)
- 被判唯一可行的 cut framework 未接生产:step_8_apply_to_master 仍不是 production integration、属后续 P1.3(docs/项目说明/01_overview.md:73-75;CLAUDE.md 引 src/cuts/lifecycle.py:1121-1126 NotImplementedError)——即 5 月死路结论之后,证明能力没有实质增强
- 正常链终点只是 CANDIDATE_PROPOSED:main.py 与 wrappers 均不调 supervisor_seal(),仓库无生产 supervisor CLI/launcher(docs/项目说明/06_current_status.md:30-32;outer_search.py:1969 return CANDIDATE_PROPOSED_STATUS);exact_full_scale_status.json(2026-04-17 生成)status=open、无 campaign state
- 本交付副本 data/checkpoints 与 data/telemetry 目录均不存在(PowerShell Test-Path 实测 False)——原机的 campaign checkpoint/日志史料未随交付迁移;cc_memory 也仅剩 4 facts/3 entries 的骨架(python cc_memory/mem.py 输出),27-lever timeline 等记忆节点已不在库内
- 频撞 UNKNOWN 已固化进默认参数:main.py:217-224 注释——master/binding/routing 默认从 600s 提到 1800s,因『70x70 复杂 candidate 上频繁撞 UNKNOWN…campaign 短命退出』,配合 watchdog 让 168h budget 用满
### risks
- 算力硬墙是最终目标的第一风险:全部实测记录中没有任何一次全尺度候选 FEASIBLE,连拿着正确答案当 hint 都验证不动(docs/lever_verdicts.md:9,127,189);而 CERTIFIED 还要求对所有 lex 更优候选给出 INFEASIBLE 终局证明——以当前求解器结构+单机 48GB,该命题无实证可达性
- 唯一近保证可行的后备路径 L11(把 blueprint 钉成硬约束只解剩 41 个)会把命题降级为『blueprint 摆法下的最优』,与 certified lex 全局最优命题直接冲突(docs/lever_verdicts.md:193-203)——若最终走这条路,等于改 theorem scope,需 owner 重新定义目标
- 被判定为『数学上不得不走』的 cut framework(03_paradigm_death_baseline.md §4.9)至今未接入生产(step_8 NotImplementedError、生产 src 零 import src.cuts),且 P1.3 接入前还有 F7/F8/F3 canonical 原语未收敛的 latent false-INFEASIBLE 雷(README.md:982)——提证能力停滞在 2026-05 的 0 FEASIBLE 水平
- 严格 UNKNOWN-terminal 语义 + watchdog 无脑重启 + 墙钟预算三者叠加:campaign 会反复重试同一 UNKNOWN 候选、每 30min-2h 死一次,168h 预算(按 created_at 墙钟计,含宕机时间)被烧光而 frontier 零进展(campaign_watchdog.sh:5-11;exact_campaign.py:3094-3097;outer_search.py:2411-2413 注释称 UNKNOWN 可重解)
- 生产运行是单机单平台点:readiness gate/wrapper/watchdog 全部 CachyOS 导向,Windows 路径实际不可用(gate 必 BLOCK 且 wrapper 无绕过口),原 Linux 机器若不可用则整条生产链路无处可跑(production_readiness_gate.py:27,96-122)
- README.md:983 明记:候选证据 re-replay 是无缓存全量重放,『168h 生产前必做内容哈希缓存(3 硬条件保 soundness),至今没做』——即便解得动,长跑的验证开销也是已知未偿性能债
- 即便某天解出并提案,链路末端仍未通电:无生产 supervisor_seal 入口(PR2 #7 刻意留空)+ owner 手动门 blocked_manual_review_count,从 CANDIDATE_PROPOSED 到公开 CERTIFIED 还需新工程+owner 裁决(06_current_status.md:30-32,67-69)
- 史料断链风险:原机 campaign 的 checkpoint/telemetry/watchdog 日志全部未随交付副本迁移,cc_memory 死路 timeline 节点也丢失——本报告引用的实测数字(14h/51-78/0 FEASIBLE、205h、15-17h 等)只剩文档转述,无法在本仓库复核原始日志
- candidate_placements.json 无远端恢复渠道:restore 只认本地 clean archive,restore_hints 里的『重新生成』路径能否 bit-exact 命中 pinned hash 未经验证——该 45.7MB 文件如在所有副本丢失,certified 生产链直接断(data/external_artifacts.json)
### open_questions
- 2026-05-21(latency tuning)之后是否还实际跑过全尺度 campaign?仓库内没有更晚的求解实测记录,6 月起的活动全是 P1.2/PR2 认证链收口——无法确认『0 FEASIBLE』结论在最新 master 搜索 profile(guided_branching_v4)+frontier probe 下是否被重新验证过
- baseline『14h 跑 51-78 candidates』是在什么 UNKNOWN 语义下取得(严格模式首个 UNKNOWN 即终止 campaign,除非当时开了数据收集 skip 模式)——文档未写明,影响对真实 frontier 吞吐的估算
- 03_paradigm_death_baseline 的『4800/4900≈98% utilization』与 blueprint 留出 27×15=405 空矩形(≈8.3% 空地)在数字上对不拢,疑为不同统计口径(是否含 optional 设施),未能在源数据核实
- watchdog 重启+resume 后对 UNKNOWN 候选是重试同一候选还是跳过,只从 outer_search.py:2411-2413 注释(UNKNOWN 非 strong、可重解)推断,未实际跑代码验证
- CI slow-soundness job『会先恢复 candidate_placements』的恢复来源(GitHub cache/artifact?)未核实;本仓库无 remote,CI 配置的实际可运行性存疑

## codex summary
当前生产链不是"一条命令产出 CERTIFIED"。main.py 默认 168h、certified_exact，当 --campaign-hours >= 24 时先触发 production readiness gate，再启动 freeze monitor，然后进入 outer_search/Benders/并行 wave 求解；终点最多把穷尽结果写成 CANDIDATE_PROPOSED 和 proposal marker。真正 durable CERTIFIED 只能由 ExactCampaign.supervisor_seal() 从磁盘 proposal 重新验证后铸出，再由 verified publisher 生成公开交付面，但当前仓库没有生产 CLI/launcher 调 seal，且 P1.2 owner 手动门仍是 blocked。算力现实方面，仓库没有随交付副本保留真实 168h campaign checkpoint/telemetry/log；现有实测材料只支持"短跑/回放/资源压力很大、UNKNOWN 和 OOM 是主要瓶颈"，不足以证明当前结构能现实地产出 70x70/266 的 lex 最优 CERTIFIED。

（以下为独立第二读者 Codex 调查过程摘记，与结论一并保留：仓库根没有 AGENTS.md 文件，只有本轮消息里提供的指令。文档侧看到几条需要源码核实的主线：main.py --campaign-hours >= 24 会进入生产启动门，但正常求解链仍只提交 CANDIDATE_PROPOSED；Windows wrapper 不自动 resume；Linux wrapper/readiness gate 是偏生产 Linux 的门。脚本实现和 CLAUDE.md 的说法一致：Linux wrapper 对 campaign 自动加 --resume-campaign，Windows 三个 run_prod_*.ps1 只有显式 -ResumeCampaign 才加。production_readiness_gate.py 本身不是纯只读工具：check_disk_space() 会创建 .artifacts，所以本次调查未执行它；源码显示它硬依赖 Arch/CachyOS 形态：/etc/pacman.conf、.venv/bin/python、/proc/meminfo、Linux affinity/THP/jemalloc。checkpoint 机制的关键形状：ExactCampaign.load_or_create(... resume=True) 会读 data/checkpoints/exact_campaign_state.json，校验 artifact/source hash，不兼容就 reset；兼容时还会把 checkpoint 里旧的强证明状态降回不可信缓存并立即写回。交付副本里没有 data/checkpoints 和 data/telemetry 目录；.artifacts 里有一些旧验证/调参材料，但不是直接的生产 campaign checkpoint。candidate_placements.json 在当前副本里存在，大小和源码/清单锁定的 45,773,799 字节相符，哈希也相符。有一个旧 .artifacts/phase3b_ai_accel_20260429 数据集声称来自 existing_production_acceptance_replay，这比普通文档叙述更接近实测；但相邻调参材料显示的是 0.083h（约 5 分钟）短跑/候选回放和硬件压力测试，且明确 final_168h_authorized=false、checkpoint_written=false 或 transient，能证明算力压力和局部进度，不能证明存在完成的 168h/certified campaign。git grep 也支持判断：非测试/非文档里没有生产路径调用 supervisor_seal()；publish_verified_certified_delivery_surface() 有导出脚本调用，但它仍要求已有 sealed campaign，不补上缺失的 supervisor 生产入口。）
### key_facts
- 项目目标和 release 状态被 README 明确为 70x70/266、max_lex(area,min_side)，但 P1.2 RELEASE-BLOCKED，main.py 只到 CANDIDATE_PROPOSED。出处：README.md:14-15。
- PROJECT_LOCK 把当前状态锁为 OPEN/BLOCKED：无生产 supervisor CLI/launcher，main.py 终点仍是 CANDIDATE_PROPOSED，checker/local pass/internal seal 不得改写 release gate。出处：PROJECT_LOCK.md:130-146。
- 当前 gate 文件也显示 status: blocked_manual_review_count，p1_2_close_status: not_closed，next_phase_entry.allowed: false。出处：data/review_gates/phase_1_2_spike_close.json:5,23-36。
- main.py 默认 --campaign-hours 168.0，--resume-campaign 需要显式参数；24h 以上 production-class 会调用 readiness gate，随后即使 skip gate 也启动 freeze monitor。出处：main.py:213-214,274-300。
- Linux wrapper 是生产导向：要求 .venv/bin/python，禁用 EXACT_POWER_PLACEMENT_SUBPROBLEM，加 jemalloc/P-core/taskset，并自动注入 --resume-campaign。出处：scripts/run_campaign_linux.sh:22-41,50-69,111-155。
- Windows run_prod_*.ps1 只在传 -ResumeCampaign 时添加 --resume-campaign；不会像 Linux wrapper 那样自动续跑。出处：scripts/run_prod_1x1_normal.ps1:1-24，scripts/run_prod_4x4_high.ps1:1-24，CLAUDE.md:51。
- production_readiness_gate.py 是 Linux/CachyOS 导向，检查 pacman freeze、venv、preflight、power env、OOM、磁盘、git、THP、jemalloc、P-core；其磁盘检查会 mkdir .artifacts，所以本次只读调查未运行它。出处：scripts/production_readiness_gate.py:1-27,188-202,458-475。
- readiness gate 内嵌了关键算力实测：-p 4 9 分钟 global OOM，-p 2 3 分钟单 worker 到 28GB、swap thrash、人工 abort；48GB 主机上 -p 1 marginal，-p >=2 必 OOM。出处：scripts/production_readiness_gate.py:320-342。
- Watchdog 的注释直接说明当前求解能力下候选频繁 UNKNOWN，campaign 实测 30 min 一次短命退出，168h budget 用不满；watchdog 通过重启+resume 试图填满预算。出处：scripts/campaign_watchdog.sh:5-11,53-63,94-128。
- checkpoint/resume 会校验 schema、mode、artifact hashes；hash 不匹配返回 artifact_hash_mismatch。resume 会把 checkpoint-loaded CERTIFIED/INFEASIBLE 强状态降为 UNKNOWN、清 solution/proof/terminal evidence，并先写回再继续。出处：src/search/exact_campaign.py:2218-2255,2375-2430,2960-3050。
- 当前 candidate_placements.json 在工作树存在且匹配锁定字节：实测 candidate_placements_length=45773799，candidate_placements_sha256=adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0；源码和 manifest 同样锁定该大小/哈希。出处：src/search/certified_artifact_contract.py:29-47，data/external_artifacts.json:6-18。
- terminal 穷尽时 outer_search 只写 CANDIDATE_PROPOSED、terminal evidence 和 proposal marker；普通 mark_campaign_stopped(... CERTIFIED) 会 raise，save() 也拒绝 unsupervised certified checkpoint。出处：src/search/outer_search.py:890-954,1969；src/search/exact_campaign.py:3566-3610,3652-3665。
- 并行 scheduler 以 wave 为单位返回 completed/failure_reason/results，记录 RSS；worker crash 会变成 worker_process_failed，outer_search 对未 effective-completed wave 不持久化 sticky strong status。出处：src/search/exact_parallel_scheduler.py:67-75,630-666；src/search/outer_search.py:2409-2415,2603-2613。
- 当前交付副本没有非 .pytest_tmp 的生产 campaign state/log：实测命令输出 NO_NON_PYTEST_TMP_CAMPAIGN_STATE_OR_LOG_FILES_FOUND；显式路径也缺 data/checkpoints/exact_campaign_state.json、telemetry、final_solution、delivery_manifest、optimal_blueprint。
- 仅找到的近似实测材料是短跑/影子数据：3 个 replay samples，2 个 INFEASIBLE、1 个 UNKNOWN，checkpoint_written=false、proof_source=false；S5/S6 调参均 campaign_hours=0.083，并声明 final_168h_authorized=false，S6 还明说没有 candidate throughput 数据。出处：.artifacts/phase3b_ai_accel_20260429/01_feature_dataset/dataset_summary.json:5-33；.artifacts/phase3b_accel_tuning/01_config_matrix/s5_matrix_scoreboard.json:11-16,166-170；.artifacts/phase3b_accel_tuning/02_stage_workers/s6_stage_worker_scoreboard.json:126-140,176-180。
- README 还记录一个性能残留：outer_search 主循环/内层 precheck 对累积强候选无缓存全量 re-replay，可能烧光 168h 预算退 UNKNOWN；'真 168h 生产前必做，至今没做'。出处：README.md:726。
### risks
- 最高风险不是单个 bug，而是操作链缺口：即使求解跑完，当前生产入口也只能生成 proposal，无法合法发布 CERTIFIED。
- 算力可行性未被实测证明；现有证据偏向 UNKNOWN/内存/OOM/短跑资源瓶颈，不能支撑'当前结构现实可完成 70x70/266 lex 最优'。
- Windows wrapper 若未显式 -ResumeCampaign，重跑会丢进度；这对多次短命退出的 campaign 尤其危险。
- 用 Windows 或 --skip-readiness-gate 跑出的材料不等价于 Linux/CachyOS production readiness 通过后的生产材料。
- 轻量 checkout 或旧版 candidate_placements.json 会让 certified run/resume fail-closed；当前副本 OK，但发布/迁移时仍是硬依赖。
- 公开结果若超出 PROJECT_LOCK 的证明范围声称吞吐/带宽/离散容量流，也会让 release claim 失真。
### open_questions
- 原始 168h/30min 重启 campaign 的完整 logs、checkpoint、telemetry 是否在本交付副本外部保留。
- 到底跑过多少次真实 campaign、每次推进了多少 frontier、候选吞吐是多少；当前副本只能看到 3 条 shadow replay sample。
- 在目标 Linux/CachyOS 硬件上，当前 main 分支经 readiness gate 后是否能稳定跑满预算并持续产生有效 frontier progress。
- PR2 pr2-5-domain-frontier-gate 的 +8700 行硬化何时合入当前 release 目标分支，并在合入后重新做生产链核查。
- 性能 root-cause（缓存/增量 replay）是否被视为 CERTIFIED 前置条件；README 说真 168h 前必做，但当前代码证据显示尚未完成。


