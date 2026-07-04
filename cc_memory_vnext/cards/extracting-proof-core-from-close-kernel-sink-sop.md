---
id: extracting-proof-core-from-close-kernel-sink-sop
kind: reference
title: 从 close-kernel sink 抽 proof-core 的完整 SOP(#1 阶段③第一批亲历,7 步连锁 + 三个反复踩的坑)—— 第二批/未来抽 core 直接照走
summary: 2026-07-04/05 #1 阶段③第一批(把 child 用的认证逻辑从 exact_campaign/certified_frontier 抽到 pr2_l0_artifact_core/frontier_core、让 L0 验证 child 不再 import 两大模块)踩出来的完整 SOP。抽 core 远不止"搬代码 + reseal"——它牵动一长串连锁,这一批因为没预见全、反复了三轮才干净落地。核心连锁:①抽取纯搬运(函数体逐字节不变)②red-line golden 必须归一化 source-tree 指纹(加文件必动 source_digest)③所有"打旧代码位置"的对抗测试/fixture 要扫全挪新位置(不只 preflight 首报的、必须跑整个测试文件暴露漏网,保持攻击同强度)④checker 的结构 lookup(FunctionDef/import/常量 pin 查找)要跟函数搬迁改指向=覆盖不逃逸⑤新 core 进 close-kernel 登记(sink p1_2_certified_path + V99 source floor + critical gate【必须,母体在 critical gate 则抽出逻辑不能逃出】)⑥修 ruff 改 core/checker 字节会连锁重新 reseal⑦验证门必须 --full 全套(不只三文件)+ --slow soundness lane。每步都别信子代理"说绿",leader 独立重跑/逐行读 diff。
scope:
  domains:
    - certified-exact
    - pr2
    - close-kernel
    - release-engineering
  paths:
    - src/search/pr2_l0_true_verifier_child.py
    - src/search/pr2_l0_artifact_core.py
    - src/search/pr2_l0_frontier_core.py
    - scripts/check_p1_2_proof_obligations.py
    - src/tests/test_p1_2_proof_obligations.py
    - src/tests/test_p1_min_tcb_closure_redlines.py
  symbols:
    - compute_exact_artifact_hashes
    - terminal_certified_final_result_project_precheck_violation
status: active
priority: P1
triggers:
  intents:
    - extract-proof-core-from-sink
    - do-min-tcb-closure-batch
    - refactor-close-kernel-sealed-file
  keywords:
    - 抽 core
    - proof-core
    - 最小 TCB 闭包
    - "#1 第二批"
    - 抽取纯搬运
    - golden source-tree 归一化
    - 对抗测试扫全
    - checker lookup 改指向
    - 覆盖不逃逸
    - critical gate
    - ruff 连锁 reseal
    - source_digest 漂移
  negative_keywords: []
  paths:
    - src/search/pr2_l0_true_verifier_child.py
    - scripts/check_p1_2_proof_obligations.py
  symbols:
    - compute_exact_artifact_hashes
  error_regex:
    - "assert old in source"
    - "must import authority name exactly once"
  examples:
    - "#1 第二批抽 replay/fixed-witness core 怎么做"
    - 从 sealed 文件抽函数到新模块要改哪些登记/测试
    - 抽 core 后一堆对抗测试红/golden 漂移怎么办
activation:
  layer_hint: L1
  must_know: false
  reason: 要抽 proof-core(把认证逻辑从 close-kernel sink 抽到新模块、缩 child TCB)时该先读——这条 SOP 覆盖抽 core 的全部连锁(golden 归一化、对抗测试扫全、checker lookup 改指向、新 core 登记、ruff 连锁 reseal、双门),第一批因没预见全反复了三轮;照它走能一次做对、不再踩。
provenance:
  op: record
  reason: 2026-07-04/05 #1 阶段③第一批抽 artifact/frontier core 落地(commit 342a32e),把踩出来的完整连锁固化成 SOP 给第二批/未来抽 core 复用。
  evidence:
    - "2026-07-04/05:#1 第一批 commit 342a32e(13 files,2387+/771-)。过程:抽取(双重证明纯搬运)→ red-line golden 漂移(source_digest 加文件变→归一化)→ reseal(checker diff 逐行验无 hollowing)→ 对抗测试三轮(红线 golden→13 个→4 个更多,因前两轮没扫全/只跑三文件)→ --full 3819 passed + --slow 28 passed。全程 leader 独立重跑双 checker、逐行读 checker diff、逐个验对抗测试 mutator 同强度。"
  updated_at: "2026-07-05"
---
从 close-kernel sink 抽 proof-core 的完整 SOP(#1 阶段③第一批亲历)。抽 core【远不止】"搬代码 + reseal",牵动一长串连锁;第一批因没预见全、反复三轮才干净。第二批(抽 replay/fixed-witness core)照这个走。

== 0. 先织安全网(动 sealed 前)==
先写 red-line 测试锁住当前验证语义(golden 语义锁 + 恶意 fixture fail-closed + 目标 xfail),**只加测试、不 reseal**。抽 core 后 golden 必须证明语义等价。见 [[postprocess-write-canonical-not-p1-2-soundness-hole]] 的收口审方法一节的思路。

== 1. 抽取 = 纯搬运,函数体逐字节不变 ==
把 child 用的函数从母体(exact_campaign/certified_frontier)抽到新 core,母体转 `from new_core import name` 兼容层(保向后兼容、别破坏母体其他使用者)。child 改 import 新 core。**只移动、不改逻辑**。两个独立印证:①red-line golden 双重证明(归一化 source-tree 后抽取前后 digest 一致)②checker 里搬走函数的 expected source-pin sha【不改】而 checker 仍绿 → 函数体逐字节没变。

== 2. red-line golden 必须归一化 source-tree 指纹(反复踩点之一)==
抽 core 往 src/ 加新文件 → `compute_exact_artifact_hashes()` 的 `certified_exact_source_tree`(全 src 扫描)变 → candidate proof 的 `source_digest` 变 → candidate records golden digest 漂移。**这不是语义变化**。修:golden 归一化里把 `certified_exact_source_tree`/`source_digest` 替占位(它归 reseal/V99 floor 管;source binding 的**验证**由 `source_digest_drift` 恶意 fixture 覆盖,归一化字段值不削弱检查)。诊断漂移根因:逐字段 diff 抽取前后 records + 反事实校验(只换 source-tree 字段 + 重算能否逐字节复现)。

== 3. 对抗测试/fixture 扫全挪新位置(反复踩点之二,最坑)==
close-kernel 的对抗测试(`test_p1_2_checker_rejects_pr2_5_*` round6/7/9/11、AST-pin、closed-world 等)的 mutator 在**旧文件**里找函数代码字符串注入 bypass;函数搬走 → `assert old in source` 失败。**铁律**:①mutator 打**新位置**(artifact_core/frontier_core)、**攻击强度完全不变**(bypass 语义/形态一字不改,绝不弱化成 checker 恰好能抓的软 bypass);②`source_kind="exact"` → `"artifact_core"`(测试框架加 artifact_core_source 支持);③expected message 更新到 checker **实际**拒绝文案(如 "must import authority name exactly once from …")。**必须扫全 + 跑整个测试文件**(如 test_p1_2_proof_obligations.py 全 347 测试,19min)暴露所有漏网——【别只修 preflight 首报的、别只跑三文件】,第一批就是这么反复了三轮(红线→13→4 更多)。leader 逐个读 mutator diff 验同强度 + checker 对新位置仍拒。

== 4. checker 结构 lookup 跟函数搬迁改指向 = 覆盖不逃逸 ==
checker 里对搬走函数/常量的结构查找(FunctionDef lookup、`_PR2_CHILD_AUTHORITY_IMPORT_MODULE`、importfrom allowlist 的 module key、child pinned body 文本、`_check_terminal_project_precheck_structure` 的输入 tree、cut-replay contract 的 needle source)要把**目标文件**从母体改到新 core。**只改"去哪个文件/tree 查"、绝不改"查什么/怎么查"**。leader 逐行读 checker diff:出现 `if` 条件改、检查函数体改、token 集合改(除新 core guard)、跳过/放宽 = 危险信号。

== 5. 新 core 进 close-kernel 登记 ==
新 core 是 child TCB,必须钉:①V99 source floor pin(`CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH`)②sink(`p1_2_certified_path` + proof-bearing,p1_2_proof_obligations.json sink_files,guard tokens = 文件实际认证关键导出)③**critical gate【必须】**——若母体(如 certified_frontier/exact_campaign,都在 critical_gate_files)在 critical gate,抽出的认证逻辑**不能逃出 critical gate 覆盖**,否则=偷偷削弱 close-kernel;④【不进】structural gate source paths(source floor 已钉字节,纯函数抽取无父门/镜像结构模式);⑤dependency floor 不动(无新第三方依赖时)。

== 6. 修 ruff 改 core/checker 字节 → 连锁重新 reseal ==
ruff 修 core(unused import 等)或 checker(F841 dead var)会动字节 → 所有依赖 sha 要重算。所以 ruff 该和抽取**一起**、一次 reseal。reseal 派生 hash 顺序(SOP):source sha → allowlist SHA/SIZE → semantic projection → contract → **checker 自钉最后**。sha 按 LF 字节算(git show :<path>,别 Python write_text/json.dump 写 tracked → Windows CRLF CI 挂)。见 [[close-kernel-reseal-execution-sop]]。

== 7. 验证门 + 提交 ==
双 checker(独立重跑,不信"说绿")→ red-line → **--full 全套【不只三文件】**(暴露所有受影响测试漏网)→ **--slow soundness lane**(改认证核心必跑)。全绿才提交:feature 分支(大工程隔离)+ 明确 pathspec 全集(core + reseal 文件 + 测试,避开共享 index)。

== 反复踩点总结(第二批别再犯)==
1. golden 会因加文件漂移 → 一开始就归一化 source-tree 指纹。
2. 对抗测试红不是 checker 削弱、是打旧位置 → 扫全 + 跑整个文件、别只修首报的。
3. 修 ruff 会连锁 reseal → 和抽取一起做、一次 reseal。
4. 每个子代理"说绿"都 leader 独立重跑/逐行读 diff 复核。

关联:reseal 实操 [[close-kernel-reseal-execution-sop]];主线计划 [[p1-2-closeout-then-tcb-backlog-order]];阶段3 spike(#1 目标/A 路径/fused 校正)[[stage3-spike-fused-5f-part3-findings]];分工(实现优先 codex、leader 验收)[[agent-role-division-and-codex-collaboration]]。
