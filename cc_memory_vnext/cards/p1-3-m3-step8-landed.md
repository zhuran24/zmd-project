---
id: p1-3-m3-step8-landed
kind: decision
title: P1.3 M3 落地(2026-07-08,四子批):step_8 通电+F1 首族接线+F8 删除+literal 缓存;cut framework 进 close-kernel 信任面(16 文件 V99 floor);EXACT_CUT_FRAMEWORK_ATTACH=unsafe 默认关待 owner 升格
summary: M3 四子批全落地、慢 lane 四过四绿:M3-1 F8 物理删除(-3099 行,63c3546);M3-2 presence literal content-addressed 三层缓存(5K cut 挡 add 116.9→61.4ms/条、solve proto 劈叉 70.5→8.6s(-88%)、50% 退化线推到 ~15-20K cut,879723e);M3-3 step_8_apply_to_master 通电——F1 region_capacity 翻译=物理恒真加权容量不等式 sum(cells_per_pose×presence)≤cap_R(attach soundness 不依赖 cert 新鲜度,门禁留 step5-7),master 侧 add_region_capacity_cut(all-or-nothing+witness 失效),其余族 fail-closed NotImplementedError(f3c91c1);M3-4 LBBD 接线(_build_cut_framework_state 从 master 材料组装 BState+_maybe_attach_framework_cuts 全关卡链,插 binding-INFEASIBLE/routing-exhausted 双分支)+env 五件套(f17866c)。**关键机制**:checker 的 close-kernel import 闭包检查在 benders_loop import cut framework 的瞬间强制 16 个 src/cuts 模块全部进 V99 source-hash floor——信任面扩张无法静默,通电即封印(此后改任何 cut framework 文件=reseal)。**当前状态**:EXACT_CUT_FRAMEWORK_ATTACH 在 unsafe map,certified 开启即 fail-closed(双红测);升格三条件=M4 阶梯落完+helper-vs-master 等价回归+owner 显式决定(PROJECT_LOCK 新 Forbidden Change 条款)。M4 待办见正文。
scope:
  domains:
    - p1-3-master-cut-integration
    - cut-framework
    - close-kernel
  paths:
    - src/cuts/lifecycle.py
    - src/search/benders_loop.py
    - src/models/exact_coordinate_master.py
    - src/tests/test_cut_framework_attach_wiring.py
  symbols:
    - step_8_apply_to_master
    - add_region_capacity_cut
    - _maybe_attach_framework_cuts
    - _build_cut_framework_state
status: active
priority: P0
triggers:
  intents:
    - implement-m4-ladder
    - wire-cut-family
    - promote-cut-framework
    - modify-cut-framework
  keywords:
    - step_8
    - M3
    - M4
    - EXACT_CUT_FRAMEWORK_ATTACH
    - cut framework
    - F1
    - region_capacity
    - 阶梯
    - 升格
  negative_keywords: []
  paths:
    - src/cuts/lifecycle.py
  symbols:
    - step_8_apply_to_master
  error_regex:
    - "cut_framework_attach_not_certified"
  examples:
    - M4 从哪开始
    - cut framework 什么时候能在 certified 里开
    - 改 src/cuts 文件要 reseal 吗
activation:
  layer_hint: L1
  must_know: false
  reason: M4 排程与实施、任何 src/cuts 改动(现在全部触 reseal!)、cut framework 升格裁定都要以本卡为基线;不知道「16 文件已进 floor」会重蹈 M2 时「src/cuts 不触 reseal」的误判(那时只有 8 个,现在 24 个)。
provenance:
  op: record
  reason: 2026-07-08 M3 四子批收口(owner 指示收口后停,M4 待发话),按 P1.3 大计划留档。
  evidence:
    - "commits: 63c3546(M3-1)/879723e(M3-2)/f3c91c1(M3-3)/f17866c(M3-4);慢 lane 30 passed×4 轮;双 checker 绿(14 obligations/64 sinks,V99 floor +16)。"
    - "M3-2 数据: docs/research/p1_3a_attach_sizing_spike_20260708/verdict.md §5b + raw_m32_after.jsonl。"
    - "F1 端到端: test_step_8_apply_to_master.py(真 master 容量 1 vs 需求 2→INFEASIBLE)/test_cut_framework_attach_wiring.py(真 oracle 全链,cap 137 权重 {boundary_io:3})。"
  updated_at: "2026-07-08"
---

P1.3 M3(step_8 落地大批)2026-07-08 收口。四子批 commit 与内容见 summary。

== M1 两硬前置的完成状态 ==

1. **literal content-addressed 复用 ✅**(M3-2):eq/match/present 三层缓存挂 delegate,cut_tag 退出 literal 身份。5K 挡实测 add -47%/solve 劈叉 -88%/RSS 增量 -75%。
2. **active cut 总量预算 ❌ 未做**——M4 必办:千级预算+CutStore eviction 最简版(原 P1.5+ 提前),配 F5 telemetry 阈值(>10^5 撞墙/<10^3 工作)。literal 缓存把余量推到 ~15-20K,但预算机制本身仍是升格前置。

== M3 刻意没做的(M4/M5 清单) ==

- **F2-F7+F9 的 step_8 翻译**:全部 fail-closed NotImplementedError。阶梯序(kickoff 卡):F4/F2→F9→F5(最大:orbit lift 七项+Q1a 五段合同+红测 R1-R10)→F6→F3→F7。
- **literal family 的 pose_id→pose_idx 映射**:F3/F5/F7 的 literal 是 (group_id, pose_id 字符串),master 按 pose_idx——映射层未建(M3-3 砍掉,接 literal 族时做)。
- **CutStore campaign 持久化**:V82 边界下跨 attempt 复用=「当前进程 fresh revalidated attach」,M3-4 只做同 attempt 内 attach;持久化+re-attach 流水线归 M4/M5。
- **helper-vs-master 等价回归**(M2 尾巴+升格前置):F7 stencil 的 attach 期一致性回归。
- **exterior_blocks**:生产无此输入,BState 填空集是正确值;若未来 outer_search 引入界外封锁概念要回来接。
- **收敛实测**:M5(全项目唯一无理论保证处,L11 退路挂 owner)。
- **生产 worker model 生命周期核查**(M1 暴露面):M1 v2 实测「同进程连续建 model 时旧 model 内存不即时回收」(del 后 RSS 滞留 13.9GB 起跑,whole 场景 1073s solve 数据因此作废)——M5 收敛实测前要查 campaign worker 的 per-attempt model 释放路径是否受同一问题影响。verdict.md 有记载,但属 M4/M5 待办,不查会在长 campaign 里累积成 OOM。

== 纪律要点(后续会话必知) ==

- **src/cuts 现在 24 个文件在 V99 floor**(原 8+新 16):改任何 families/helpers/replay/store/assumptions/lifecycle/cert_schema/oracles(部分) = 完整 reseal 三步(V99 dict→obligations JSON→checker 自钉)。「哪些被钉」以 grep obligations JSON+V99 dict 为准。
- **升格流程**(PROJECT_LOCK Forbidden Change 条款):EXACT_CUT_FRAMEWORK_ATTACH 出 unsafe map 需 M4 阶梯+等价回归+owner 决定,升格后继承 F-*/PCR-*/CUT-* 全部 fail-closed 义务。
- mypy gate(4 core 文件)在 reseal 之前跑——SOP「先清静态检查再 reseal」本批又实证一次(mypy 返工 = pin 重算一轮)。
