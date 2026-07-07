---
id: runtime-isolation-verify-import-time-vs-runtime-gap
kind: pitfall
title: 验 runtime 模块隔离别只测 import 时——第二批误报"验收门满足"的根因(烟测漏 runtime replay 同进程拉 benders)+ 补正(replay 子进程化 + checker 结构强制才是硬保证)
summary: 2026-07-05 PR2-1 阶段③第二批(抽 replay/fixed-witness core, commit d05d242)做完,我向 owner 误报"child 主进程 runtime sys.modules 无三大禁模块、#1 验收门满足"——【错的】。根因:child `_project_candidate_records_direct`:557 **同进程直调** `_execute_isolated_replay_request`→函数内 import benders_loop→benders 顶层 import exact_campaign→拉 certified_frontier/candidate_proof_replay/verifier/capsule 五禁模块进 child 主进程;这些 import 是 **runtime(跑 replay 时)** 触发、不是 import child 时。验证 gap:第二批烟测 `import child+core` 看 sys.modules=[] 就误信"满足",但烟测**只测 import 时**(replay 没跑、benders 的函数内 import 没触发)、漏了 runtime。实测铁证:`import child`=[];`import benders_loop`(=replay runtime 那步)=六禁模块全进。三教训:①验 runtime 隔离不能只测 import 时、要测"真跑一遍后"或用 checker 结构强制(更硬);②函数名带 isolated≠真子进程(得读实际调用点 direct call vs subprocess.run);③自己笔记记过的事实(fused 校正明记"L0 child 同进程 direct 调 replay")没交叉核对、想当然当成子进程。补正=replay 子进程化(commit 4388494)+ checker 结构强制。
scope:
  domains:
    - certified-exact
    - pr2
    - close-kernel
    - verification-method
  paths:
    - src/search/pr2_l0_true_verifier_child.py
    - src/search/pr2_l0_replay_core.py
    - src/search/benders_loop.py
    - scripts/check_p1_2_proof_obligations.py
  symbols:
    - _execute_isolated_replay_request
    - _invoke_isolated_replay
    - _project_candidate_records_direct
status: active
priority: P1
error_regex:
  - "sys\\.modules"
  - "BANNED"
  - "验收门.{0,4}满足"
  - "runtime.{0,20}(exact_campaign|benders|禁模块)"
triggers:
  intents:
    - verify-runtime-module-isolation
    - check-child-tcb-sys-modules
    - assert-acceptance-gate-satisfied
  keywords:
    - runtime 隔离验证
    - import 时 vs runtime
    - 烟测漏 runtime
    - sys.modules 禁模块
    - 同进程直调
    - isolated 名字不等于子进程
    - checker 结构强制
    - 第二批误报
    - replay 子进程化
    - benders 拉 exact_campaign
  negative_keywords: []
  paths:
    - src/search/pr2_l0_true_verifier_child.py
  symbols:
    - _execute_isolated_replay_request
  error_regex: []
  examples:
    - "怎么验 child runtime sys.modules 无禁模块 / 验收门满足没"
    - 抽 core 后 child 主进程 runtime 到底还拉不拉大模块
    - 为什么烟测显示干净但实际 runtime 有禁模块
activation:
  layer_hint: L1
  must_know: false
  reason: 要断言"某进程 runtime 内存里没有某些模块 / TCB 隔离达成"时该先读——这条记录了一次真实的误判:只测 import 时的烟测给出假的"满足",漏了运行时函数内 import 触发的传递闭包。验 runtime 隔离照它做(测真跑后 / checker 结构强制),别再栽在"import 时看着干净"。
provenance:
  op: record
  reason: '2026-07-05 PR2-1 replay 子进程化(4388494)补正第二批(d05d242)误报的验收门满足,把这次验证方法失误的完整来龙去脉固化,防重蹈。'
  evidence:
    - "2026-07-05 实测:python -c 'import child; banned=[] ; import benders_loop; banned=[benders_loop,candidate_proof_replay,certified_frontier,exact_campaign,terminal_fixed_witness_capsule,terminal_fixed_witness_verifier]'。child:557 同进程直调 _execute_isolated_replay_request(replay_core:600,613 行 import benders_loop)。补正 4388494:child 改调 _invoke_isolated_replay(subprocess spawn),checker _check_child_project_candidate_records_direct_structure 结构强制 child 从它赋值 response、_execute_isolated_replay_request caller 只剩子进程入口 isolated_replay_main。四绿+red-line 9+2+--full 3819+--slow 28。"
  updated_at: "2026-07-05"
---
2026-07-05 #1 阶段③第二批(抽 replay/fixed-witness core, commit d05d242)做完,我向 owner **误报"child 主进程 runtime sys.modules 无三大禁模块、#1 验收门满足"——错的**。replay 子进程化(commit 4388494)补正。完整来龙去脉:

== 错在哪 ==
第二批让 child 源码不再直接 `import exact_campaign` 这类。我据此报"child 内存里没那些禁模块"。但 child 跑 replay 复验时,`_project_candidate_records_direct`(pr2_l0_true_verifier_child.py:557)**同进程直调** `_execute_isolated_replay_request`(pr2_l0_replay_core.py:600),那函数第 613 行 `from src.search.benders_loop import create_exact_search_session`(函数内 import),benders_loop 顶层 import exact_campaign,exact_campaign 顶层又拉 certified_frontier/candidate_proof_replay/terminal_fixed_witness_verifier/terminal_fixed_witness_capsule。**所以 child 一跑 replay,那五个禁模块全进主进程 sys.modules。** 这些 import 是 **runtime(跑 replay 时)** 触发,不是 import child 时。

== 为什么漏了(根因=验证方法 gap)==
第二批验收用烟测:`import child+core` 看 sys.modules → `BANNED=[]`,就信了。**这烟测只测"刚 import 那一刻"**——那时 replay 没跑、benders 的函数体内 import 没触发,所以干净。**没测"真跑一次 replay 后"**——一测就露。比喻:查"房间进没进人"只在开门那秒看了眼(空),没等到真会有人进来的时刻(跑 replay)再看。
实测铁证(补正时做的):`import child`=[];`import benders_loop`(=replay runtime 必经那步)=六禁模块全进。

== 三个教训(防重蹈)==
1. **验 runtime 模块隔离,不能只测 import 时**。要测"真跑一遍目标路径后"的 sys.modules,或——更硬——用 checker 结构强制该路径走隔离子进程。
2. **函数名带 isolated ≠ 真子进程**。`_execute_isolated_replay_request`/`isolated_replay_main` 名字都带 isolated,但 child 是**同进程直调**、根本没走那个子进程入口。判隔离要**读实际调用点**:是 direct function call 还是 subprocess.run spawn。
3. **自己笔记记过的事实没交叉核对**。fused 校正笔记([[stage3-spike-fused-5f-part3-findings]])明写"L0 child 已同进程 direct 调用 replay+fixed-witness",第二批却忘了、想当然当成走子进程。记过的关键事实动手前要回查。

== 怎么补正的(replay 子进程化, 4388494)==
- child `_project_candidate_records_direct` 从同进程 `_execute_isolated_replay_request` 改成走**真子进程 spawn** `_invoke_isolated_replay`(这套 spawn 机制一直存在、旧 sink 路径 `verify_candidate_records_at_sink` 在用,child 之前没用而已)。benders/exact_campaign 关子进程里,child 主进程干净。
- **不再靠烟测,靠 checker 结构强制**:`_check_child_project_candidate_records_direct_structure` 硬性要求 child 从 `_invoke_isolated_replay`(checker 验它 `.run` subprocess)赋值 response、required-call 必须含它;`_execute_isolated_replay_request` 的 caller 只剩子进程入口 `isolated_replay_main`。**child 一旦改回同进程调法,checker 立刻红。** 每次门禁自动验的硬保证,比一次性烟测靠谱得多。
- 验证:四绿 + red-line 9+2 + --full 3819 passed + --slow 28 passed。

== #1 现状(2026-07-05)==
- ✅ child 源码不直接 import 四大模块(抽 core 两批 342a32e/d05d242)
- ✅ child 主进程 runtime sys.modules 无三大禁模块(replay 子进程化 4388494,**验收门 (a) 真达成**,进程级隔离,checker 结构锁死)。fixed-witness 路径本就干净(binding/routing 闭包不拉禁模块)
- ⏳ **(b) 快照白名单**(#2):现状 `_discover_project_snapshot_modules` rglob 全 src/scripts(672 模块)。**架构结节**:replay 子进程从 child 快照 import benders,所以快照**必须含 benders/exact_campaign**,做不到"快照无禁模块"。三选一(owner 待定):①接受快照含 benders、只从 672 缩到最小;②replay 子进程用独立快照(再隔离一层);③重构 benders 不 import exact_campaign(大工程)
- ⏳ #3 fd-held read-once(TOCTOU)、阶段4 OS 隔离——更深硬化,没碰
- 挂账:第二批改过 governance gate(check_phase_review_gate)指向(同强度可回退),owner 说"继续做完"=默认认可,未明确拍

关联:抽 core SOP [[extracting-proof-core-from-close-kernel-sink-sop]];fused 校正(记过 replay 同进程 direct 却被第二批忽略)[[stage3-spike-fused-5f-part3-findings]];主线计划 [[p1-2-closeout-then-tcb-backlog-order]];reseal 实操 [[close-kernel-reseal-execution-sop]]。
