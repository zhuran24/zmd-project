---
id: p1-3-kickoff-recon-facts
kind: reference
title: P1.3 开工侦察硬事实(2026-07-07)+M1 attach sizing spike verdict=GO(2026-07-08):生产 master 是增量 add 不是每轮 rebuild;旧 spike 设计过时未实施;EXACT_B_DESIGN_V2 不存在;literal 零复用是首要瓶颈(50% 退化线在裸实现 ~2.5-3K cut)
summary: P1.3 开工前五路侦察(cuts 代码/锁条款/排期 gap/新规格/master 接口面)+基线实测的硬事实集。【M1 verdict 2026-07-08,docs/research/p1_3a_attach_sizing_spike_20260708/verdict.md】attach spike 判 GO(增量 add 形态)带两硬前置:①presence literal 必须 content-addressed 复用(_pose_present_literal 零复用是 add 66→252ms/条超线性+RSS 0.9MB/条+solve proto 劈叉 2.8→232s 的共同根因);②active cut 总量预算(裸实现 50% 退化线在 ~2.5-3K cut,literal 复用落地后复测再放宽)。三 PoC 裁决:增量 add=主路线/rebuild=退路/C++ propagator 维持 defer。【更正 07-08】「src/cuts 不触 reseal」是错的:两个 obligation 另钉 8 个 src/cuts 文件 hash(含 lifecycle.py/power_cover_oracle.py),改任何字节=reseal;M3 动 lifecycle.py 必然 reseal;判断钉面用 grep obligations JSON 而非只看 sink 名单(正文更正段)。核心纠偏三条:①09_phase_1_3_plan 假设的"每轮 rebuild master"不符现状——生产是 per-attempt build_exact_core→from_exact_core 克隆+LBBD 轮内 add_benders_cut 增量加约束(exact_coordinate_master.py:7044-7078,presence nogood sum≤N-1+OnlyEnforceIf,带 witness 失效 :7088-7095),whole-layout nogood 已是"cut 进 master"的活生产先例,与 F3/F5/F7 literal family 翻译形态同构→attach 的 API 风险已被生产验证,剩规模问题;②2026-05 prod-scale spike(8 路设计+MERGER+3 轮 Gemini)最终收窄成 sizing-only 但从未实施,且针对 PoseBoolExactMaster(81K BoolVar)——该 master 已被 CoordinateExactMasterDelegate 取代,全部 sizing 数字作废;③EXACT_B_DESIGN_V2 只存在于 docs,src 里没有,P1.3 的 cut 开关要按 env 白名单五件套新建(known_names+分类 map+3 测试+checker+锁,语义开关必须 canonical-default false 不能进 operational)。coordinate master 0-cut 基线(2026-07-07 实测):build_exact_core 38.9s,64,103 var/108,024 constr(coordinate_exact_v2),RSS 2.4GB;from_exact_core 克隆 26.8s(8x8)/35.7s(12x10)/53.6s(20x16)——per-attempt 固定成本已 27-54s,cut 注入退化与此同轴比。
scope:
  domains:
    - p1-3-master-cut-integration
    - cut-framework
    - attach-spike
  paths:
    - src/cuts/lifecycle.py
    - src/models/exact_coordinate_master.py
    - src/models/master_model.py
    - src/search/benders_loop.py
    - docs/research/prod_scale_spike_design_20260525/MERGER.md
  symbols:
    - step_8_apply_to_master
    - add_benders_cut
    - build_exact_core
    - from_exact_core
status: active
priority: P1
triggers:
  intents:
    - plan-p1-3
    - implement-step-8
    - design-attach-spike
    - wire-cut-family
  keywords:
    - step_8
    - attach spike
    - P1.3
    - cut 接入
    - add_benders_cut
    - EXACT_B_DESIGN_V2
    - coordinate master
    - sizing
    - 挡位
  negative_keywords: []
  paths:
    - src/cuts/lifecycle.py
    - src/models/exact_coordinate_master.py
  symbols:
    - step_8_apply_to_master
  error_regex: []
  examples:
    - step_8 该怎么接 master
    - attach spike 用什么规模数字
    - P1.3 的 env flag 叫什么
activation:
  layer_hint: L1
  must_know: false
  reason: P1.3 全程(M1 spike→M3 step_8 落地→M4 逐 family)都会消费这些事实;不知道①会照 09 号过时假设设计 rebuild 型 attach,不知道②会误用 81K BoolVar 旧数字,不知道③会以为开关已存在。
provenance:
  op: record
  reason: 2026-07-07 P1.3 正式开工,五路并行侦察(workflow wf_30d2d244-8c3)+0-cut 基线实测(m1_baseline_0cut.py)后登记,给 M1 spike 与后续 step_8 实施防跑偏。
  evidence:
    - "侦察 workflow wf_30d2d244-8c3(5 codex agents):cuts 代码/PROJECT_LOCK 条款/排期卡+soundness_gap/F5+Q1a+F7F8 规格/master 接口面。"
    - "基线实测 m1_baseline_0cut.py(2026-07-07,本机):build 38.931s,64103 var,108024 constr,clone 26.8/35.7/53.6s,RSS 2443MB(core)→4650MB(3 clones)。"
    - "src/cuts↔src/search 双向零 import(grep 0 命中);step_8 NotImplementedError=lifecycle.py:1121-1126;step_2 minimize 也是 NotImplementedError(非关键路径)。"
  updated_at: "2026-07-08"
---

P1.3 开工侦察(2026-07-07)的硬事实集,全部实测/源码坐实,不依赖 owner 拍板。

== 三条纠偏(照旧文档做会跑偏) ==

1. **生产 master 不是每轮 rebuild**。真实结构:`build_exact_core`(一次,38.9s)→ 每 attempt `from_exact_core` 克隆(27-54s,ghost 越大越贵)→ LBBD 轮内 `add_benders_cut` 增量加约束、每轮新 CpSolver(master_model.py:11471,solve 默认 60s 预算)。whole-layout nogood 全链已在生产:binding/routing INFEASIBLE→`_add_exact_whole_layout_nogood`(benders_loop.py:7498)→I1 独立复验→`add_benders_cut`(exact_coordinate_master.py:7044-7078)= presence literal `sum≤N-1`+可选 `OnlyEnforceIf(cond)`+witness 失效(:7088-7095,F-GM-R6-01 义务的现成实现)。F3/F5/F7 literal family 的 CP-SAT 翻译与此同构→**attach API 风险已被生产验证,M1 spike 只需答规模问题**。
2. **旧 spike 材料全部过时**:docs/research/prod_scale_spike_design_20260525/(8 路+MERGER,3 轮 Gemini 外审)最终 scope-shrink 成 sizing-only spike 且**从未实施**(无 verdict.md);目标是 PoseBoolExactMaster 81K BoolVar——现已换 CoordinateExactMasterDelegate(64K var/108K constr)。旧 MERGER 仍可复用的:G6a/G6b feasible-vs-random 负载设计、N1-N13 abort 判据框架、8 项 off-limits 清单、「spike GO≠paradigm GO」边界纪律。
3. **EXACT_B_DESIGN_V2 不存在于代码**(只在 docs/research+09 号计划文本里)。新开关走五件套:`_CERTIFIED_KNOWN_ENV_NAMES`(benders_loop.py:1007)+分类 map(语义开关→unsafe/canonical-default map,**不能**直接进 `_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST`)+test_exact_contract.py:9063+test_ghost_anchor_filter.py:175+test_v62_candidate_frontier_contract.py:98+checker(check_p1_2_proof_obligations.py:12459)+PROJECT_LOCK L199/L331/L485。参考门控模式=pose_bool(`EXACT_USE_POSE_BOOL_MASTER` 在 unsafe map,blocker=pose_bool_master_not_certified,direct benders+outer search 双 red test)。

== 更正(2026-07-08,M2 批 A 亲历):「src/cuts 不触 reseal」是错的 ==

60 条 close-kernel sink 名单确实不含 src/cuts,但 obligations JSON 里 **PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS / PO-STEP7-ATTACH-MIRROR 两个 obligation 另钉了 8 个 src/cuts 文件的 source_sha256**(cert_schema.py / families/pattern_nogood.py / helpers/bounded_core_minimizer.py / **lifecycle.py** / oracles/pattern_nogood_oracle.py / **oracles/power_cover_oracle.py** / oracles/region_capacity_oracle.py / oracles/shape_packing_hall_oracle.py),mutation_policy=source_sha256_drift_reopens_p1_2_close_claim。改这 8 个文件任何字节=走 reseal 三步(V99 dict→obligations JSON→checker 自钉,见 [[close-kernel-reseal-execution-sop]])。**直接推论:M3 实现 step_8 要改 lifecycle.py=必然 reseal**,比「只有 benders_loop/master_model 才触」的旧预期早一步。M2 批 A 已为 power_cover_oracle.py 走过一轮(commit 03c7f4e)。判断某文件是否触 reseal 的正确方法=grep obligations JSON 的 path 字段,不是只看 sink 名单。

== cut 框架现状(比预期完整) ==

九 family validator/replay/evaluator 全部已实现;缺口只在:step_8(NotImplementedError)、step_2 minimize(NotImplementedError,非关键)、CutStore disk persist(明确 deferred P1.3)、部分 generator 默认关(F3/F7/F8 env-gated;F5 registry 默认空需 real subproblem adapter;F6 需 region_demand_overrides;F1 只 left_or_bottom_union)。certified persisted cut replay 被硬关(benders_loop.py:7941-7958,persisted exact_safe_cuts 只是性能 hint)——cut 跨 attempt 复用是 P1.3 的独立决策点,默认维持关。

== P1.3 语义前置(soundness_gap_roadmap:21 钉死) ==

canonical→geometry 语义半:F1-F9 helper 用旧欧氏覆盖/方向模型,certified 主链用 owner-confirmed 12×12 stencil——「helper 欧氏、master stencil」双语义是 F7/F8 的 non-certified 地雷,reconcile 是 P1.3-before-F1-F9 前置,也是形式化 F8 解锁条件。owner 裁定点:选 stencil(推荐,与主链一致)还是欧氏(则 F7/F8 永不 attach)。

== M1 基线数字(挡位设计以此为准) ==

| 量 | 值 |
|---|---|
| build_exact_core | 38.9s |
| proto | 64,103 var / 108,024 constr (coordinate_exact_v2) |
| from_exact_core | 26.8s(8×8) / 35.7s(12×10) / 53.6s(20×16) |
| RSS | 2.4GB(core) / +~0.7GB per clone |
| solve 生产预算 | 60s/轮(master_model.py:11424 默认) |

== M1 attach sizing spike verdict(2026-07-08,GO) ==

完整数据与边界声明见 `docs/research/p1_3a_attach_sizing_spike_20260708/verdict.md`(commit 47540ea)。核心:pattern 型(8-literal)注入挡位 0/100/1K/5K/10K → add 66.7/94.3/116.9/252ms/条(超线性),solve 的 python↔C++ proto 劈叉 2.8/3.5/8.7/70.5/232s,RSS 0.9MB/条。根因=\_pose_present_literal(exact_coordinate_master.py:6949)每 cut 每 pose 重建 literal+channeling(名字带 cut_tag)。**step_8 两硬前置**:content-addressed literal 复用(key=(slot 集合,pose_tuple),cut_tag 只留 telemetry;与 alias fail-closed 纪律正交)+active cut 千级总量预算(配 CutStore held/eviction 最简版提前到 F5 接线批)。已作废数据别引用:v1 whole 型 99.99% 被拒=合成负载 alias(组内撞 pose,生产不会);v2 whole 0-cut solve 1073s=内存滞留污染(del 后 proto 不即时回收——生产 worker 连续 task 有同暴露面,M3 检查)。updated_at 同步 07-08。
