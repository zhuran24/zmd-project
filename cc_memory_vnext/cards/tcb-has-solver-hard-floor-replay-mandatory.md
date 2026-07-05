---
id: tcb-has-solver-hard-floor-replay-mandatory
kind: reference
title: certified-exact 认证 TCB 有"求解器硬地板"——replay 必须重跑 benders 证 frontier 耗尽/全局最优、fixed-witness 单独不够;所以 PR2-1 的 (a) 进程隔离 /(b) 快照白名单都不缩"语义 TCB",只缩暴露面+供应链 hygiene,真缩 TCB 要 proof-carrying 重构
summary: 2026-07-05 四路 codex 只读审计(workflow wo0qi75z3)得出的非显然架构约束,纠正"PR2-1=缩小 TCB"的误框定。核心事实：L0 child `verify()` 里 replay 是硬门(失败即拒,pr2_l0_true_verifier_child.py:383-405),child 主进程**不独立复核求解器语义**、只信任 replay 子进程返回的 replay_status==claimed(:572-579,CERTIFIED 再查 solution digest 一致但不重跑);replay 本质=隔离子进程重跑整套 certified_exact 求解器(_replay_one_proof→run_benders_for_ghost_rect,pr2_l0_replay_core.py:532)。**为什么非 replay 不可**：CERTIFIED 不只证 placement 可行,还要证 terminal frontier 已耗尽/该候选全局最优,这只能靠重跑求解器的 candidate records 状态(frontier_core.py:182-253/370-428,artifact_core.py:1387-1409);fixed-witness 单独不自足——只证给定 witness 的 binding/routing+几何/供电(fixed_witness_core.py:183),证不了"所有更大 ghost 矩形都不可行"。**推论**：只要认证靠 replay 重跑,benders/master/binding/routing 就永远在语义 TCB 里。故 PR2-1 两验收门都不缩语义 TCB——(a) 进程级隔离=防 import 副作用/全局污染/命名空间冲突弄脏裁决进程(真价值但 modest);(b) 快照白名单=让 child 代码供应链不能把旧大模块当可执行材料带进来(fail-closed 防未来意外 import,是 P1.2 close 技术必要条件),但不缩语义 TCB;选项②(孙进程独立快照)=有效 compartmentalization、非缩减,轻微安全剧场嫌疑;真缩 TCB 需第四条路=把 replay 换成小核可独立验证的全局最优/不可行 certificate(proof-carrying,比重构 benders 还大一个数量级,别轻启)。现状：(a) 基本达成(fresh 进程 import child 全套=三禁[],import benders 才三禁;完整 verify()=SEALED 前后[];AST checker 结构锁),三星号=fixed-witness 仍在 child 主进程内跑 binding/routing solver、checker 挡明显回退但不防语义等价绕法、replay 子进程缺 -S;(b) 未达成=snapshot 672 模块含三禁+367 scripts,red-line 两条 xfail(test_p1_min_tcb_closure_redlines.py:669/684)。定位：PR2-1 是 P1.2 close 技术必要条件(PROJECT_LOCK.md:130/134,soundness_gap_roadmap.md:17,12_go_criteria.md:18/30)但不 block 当前 release(直接闸=owner 手动门 blocked_manual_review_count,phase_1_2_spike_close.json)。
scope:
  domains:
    - certified-exact
    - pr2
    - close-kernel
    - tcb
  paths:
    - src/search/pr2_l0_true_verifier_child.py
    - src/search/pr2_l0_replay_core.py
    - src/search/pr2_l0_fixed_witness_core.py
    - src/search/pr2_l0_frontier_core.py
    - src/search/pr2_l0_micro_verifier_core.py
  symbols:
    - _project_candidate_records_direct
    - _invoke_isolated_replay
    - run_benders_for_ghost_rect
    - verify_terminal_fixed_witness
    - _discover_project_snapshot_modules
status: active
priority: P1
triggers:
  intents:
    - assess-tcb-minimization-value
    - decide-pr2-1-snapshot-whitelist-option
    - judge-if-b-shrinks-tcb
    - plan-real-tcb-reduction
  keywords:
    - 求解器硬地板
    - replay 必须重跑 benders
    - fixed-witness 单独不够
    - frontier 耗尽/全局最优
    - 语义 TCB vs 暴露面
    - compartmentalization 不是缩减
    - 安全剧场嫌疑
    - proof-carrying certificate
    - 快照白名单不缩 TCB
    - PR2-1 意义定位
    - child 信任 replay_status
  negative_keywords: []
  paths:
    - src/search/pr2_l0_true_verifier_child.py
    - src/search/pr2_l0_replay_core.py
  symbols:
    - _invoke_isolated_replay
    - run_benders_for_ghost_rect
  error_regex: []
  examples:
    - PR2-1 缩小 TCB 到底缩没缩 / (b) 快照白名单意义大不大
    - replay 能不能去掉 / fixed-witness 单独够不够 certify
    - 选项②孙进程独立快照是真缩 TCB 还是安全剧场
    - 真要缩认证 TCB 该怎么做
activation:
  layer_hint: L1
  must_know: false
  reason: 断言"PR2-1/最小TCB闭包缩小了可信基"或决定 (b)/选项②要不要做、值不值时该先读——这条记录了一个反直觉事实:认证靠 replay 重跑求解器,所以 benders/求解器是语义 TCB 的硬地板,(a)/(b) 都不缩语义 TCB(只缩进程暴露面+代码供应链)。不读会重蹈"把 (b) 当成缩 TCB 从而高估 soundness 收益"的误框定。
provenance:
  op: record
  reason: '2026-07-05 owner 问"这件事做完没/意义大不大",四路 codex 只读审计(wo0qi75z3)深查后得出的架构约束,固化以纠正 PR2-1 价值误框定、指导 (b) 该不该做的决策。'
  evidence:
    - "2026-07-05 workflow wo0qi75z3 四 codex 只读审计,全程 file:line 落证:child 信任模型(true_verifier_child.py:383-405/515-552/572-589)、replay 重跑求解器(replay_core.py:532-551/695-711)、fixed-witness 不自足(fixed_witness_core.py:183/233-260/318-377、artifact_core.py:850-1091 只证 terminal witness)、frontier 全域耗尽证明(frontier_core.py:182-253/370-428、artifact_core.py:1387-1409)。实测:fresh import child 全套三禁=[];import benders=三禁全进(污染确在 replay 子进程);完整 verify()=SEALED 前后三禁[];toy seal test_golden_toy_supervisor_seal_semantic_digests 1 passed;check_p1_2_proof_obligations 通过 14 anchored/64 sealed;snapshot 实测 672 模块含三禁+367 scripts;red-line 两条 xfail。均未改仓库源码。"
  updated_at: "2026-07-05"
---
2026-07-05 owner 问"PR2-1 这件事到底做完没、意义大不大",派四路 codex 只读审计(workflow wo0qi75z3:verify-a-done / tcb-trust-analysis / roadmap-position / adversarial)。核心发现纠正了一个我自己和 [[runtime-isolation-verify-import-time-vs-runtime-gap]] 卡里都默认的误框定——"PR2-1 = 缩小 TCB"。真相如下。

== 认证 TCB 有"求解器硬地板"(最关键)==
- L0 child `verify()` → `_verify_supervisor_domain()` 里 **replay 是硬门**(失败即拒,`pr2_l0_true_verifier_child.py:383-405`),fixed-witness 也是硬门。
- **child 主进程不独立复核求解器语义**:replay 路径先做 proof/response 形状+绑定检查,然后调 `_invoke_isolated_replay()`(:515-552),关键接受条件=replay 子进程返回的 `replay_status` 必须==claimed status(:572-579);CERTIFIED 情况再查本地 solution digest 与 proof digest 一致(:580-589),但**这不是重跑 benders、不是独立证明可行/不可行**。
- **replay 孙进程真在重跑整套求解器**:`_replay_one_proof()` import `run_benders_for_ghost_rect`,`solve_mode="certified_exact"` 重跑 master/binding/routing/flow(`pr2_l0_replay_core.py:532-551`);外层 `_execute_isolated_replay_request()` 建 exact search session(:695-711)。
- **为什么非 replay 不可**:CERTIFIED 不只证"最终 placement 可行",还要证 **terminal frontier 已耗尽、final candidate 全局最优**。这靠 candidate records 的 CERTIFIED/INFEASIBLE 状态算 frontier evidence(`pr2_l0_frontier_core.py:182-253`),再要求 domain/status/digest/best/frontier 全部和重算一致、无 remaining potential(:370-428);terminal final result 还会拒绝更优 certified candidate(`pr2_l0_artifact_core.py:1387-1409`)。
- **fixed-witness 单独不自足**:`verify_terminal_fixed_witness()`(`pr2_l0_fixed_witness_core.py:183`)只对**给定** terminal witness 建 binding model 并 solve(:233-260)、建 routing core/subproblem precheck 并 solve(:318-377),terminal precheck 再查几何/mandatory/power/ghost-empty-rect/best-rect(`artifact_core.py:850-1091`)。它证的是"这个已给 witness 满不满足谓词",**没证所有更大/更优 ghost 矩形都不可行**,没有全域耗尽证明。
- **推论**:只要认证还靠 replay 重跑求解器,**benders/master/binding/routing 就永远在语义 TCB 里**。这是硬地板。

== 所以 PR2-1 两验收门的真实意义(别高估)==
- **(a) child 主进程 runtime 无三禁模块** = **进程级隔离**:防 import 副作用/全局 monkeypatch/`sys.path` 影子/旧 bytecode/命名空间污染弄脏裁决进程。真价值,但 modest。
- **(b) 快照白名单** = **代码供应链闭包收窄**:当前 `_SnapshotFinder` 接受 manifest 里任意模块,禁模块只是"当前路径没 import"、不是"边界不存在";(b) 让将来某 helper/error path/debug 分支意外 import `scripts.*` 或 `exact_campaign` 时 loader 直接 `ModuleNotFoundError` fail-closed(而非只能靠回归测试发现)。真价值,是 **P1.2 close 技术必要条件**,但**不缩语义 TCB**。
- **选项②(replay 用孙进程独立快照)** = 审计定性为"有效 compartmentalization,不是真正缩小认证 TCB"——只把求解器从 child 主进程搬到隔离孙进程,分区、不是拿掉。**轻微安全剧场嫌疑**(把大代码从 child snapshot 挪到子进程 TCB、被信任代码总量没减)。
- **真缩语义 TCB 的唯一路(第四条)** = 把 replay 换成"小核可独立验证的全局最优/不可行 certificate"(proof-carrying certification)。比重构 benders(③)还大一个数量级,**不在 PR2-1 scope、别轻启**。

== 现状(2026-07-05,实测)==
- **(a) 基本达成**:fresh 进程 import child+replay_core+fixed_witness_core+binding+routing → 三禁=`[]`;一 import `benders_loop` → 三禁全进(证污染确被关进 replay 子进程);模拟 snapshot 后完整 `verify()`=`SEALED`、前后三禁`[]`;真实 toy seal `test_golden_toy_supervisor_seal_semantic_digests` 1 passed。checker `_check_child_project_candidate_records_direct_structure` 是 **AST 结构门**(把 child 改回同进程直调,codex 内存 AST 变异实测报红)。
- **(a) 三个诚实星号**:① fixed-witness 仍在 child 主进程内跑 binding/routing solver(闭包不含三禁,但那些 solver 本身也是被信任代码);② checker 挡明显回退、**不防语义等价绕法**(仍有 token/AST 形状成分,`check_p1_2_proof_obligations.py:10928`);③ replay 子进程命令行缺 `-S`(小残余)。
- **(b) 未达成**:`_discover_project_snapshot_modules()` 仍扫 `src`+`scripts` 全树(`pr2_l0_micro_verifier_core.py:421`),实测 **672 模块、含三禁、含 367 个 `scripts.*`**;red-line 两条(snapshot 不含三禁/不含 scripts/<120)仍 `xfail`(`test_p1_min_tcb_closure_redlines.py:669/684`)。

== roadmap 定位 ==
- PR2-1 是 **P1.2 close 的技术必要条件之一**:`PROJECT_LOCK.md:130/134`(P1.2 写成 OPEN/BLOCKED、点名"PR2 更小 read-once/controlled-loader verification TCB 尚未实现")、`soundness_gap_roadmap.md:17`(标 OPEN)、`12_go_criteria.md:18/30`(列为 close 必要条件)。
- **但不 block 当前 release**:直接闸=owner 手动门 `blocked_manual_review_count` / `p1_3b_entry_allowed=false`(`phase_1_2_spike_close.json`),不从测试/seal/checker 自动推导。所以"现在立刻做 (b)"没紧迫性。
- **文档漂移**:CLAUDE.md 权威顺序 §4 引的 `docs/项目说明/00_master_roadmap.md`(标"2026-07-05 立")在此分支工作区+git 均**不存在**(codex 如实报告、改用等价 authority);疑似并发会话今天刚建未提交到本分支。

== 决策指引 ==
- 目标=推 P1.2 收口 → 做 (b),选 **①(显式最小白名单,child 主进程 snapshot 只留必要 L0 core/artifact/frontier/fixed-witness core+真实依赖,保留 replay 孙进程隔离,不重构 benders)**;① 若因依赖闭包排不掉禁模块再升 ②;③ 不划算。状态须诚实标"runtime forbidden-import closure done;snapshot minimal closure deferred",**别叫 PR2-1 done**。
- 目标=soundness 边际最大化 → (a) 之后 **fd-held read-once/TOCTOU + 阶段4 OS 文件隔离**可能比 (b) 更值(child 自己在 response 里把 `os_process_file_isolation`/`windows_write_isolation_residual` 列为残余 TCB 项,`pr2_l0_true_verifier_child.py:490`)。

关联:批次2 验证方法失误(误报验收门满足)[[runtime-isolation-verify-import-time-vs-runtime-gap]];阶段3 以 #1 为枢纽的重构设计(fused + 5F-part3)[[stage3-spike-fused-5f-part3-findings]];主线排期(P1.2 收口 vs TCB backlog)[[p1-2-closeout-then-tcb-backlog-order]];抽 core SOP [[extracting-proof-core-from-close-kernel-sink-sop]]。
