---
id: p3-0-formal-verification-head-start
kind: decision
title: P3.0 形式化证明已开头且 anon_lift_sound 已落地(2026-07-05)——formal/ 30 条 Lean 定理落 main(mathlib 已接入),双轴架构定稿;锁面不动
summary: owner 2026-07-05 授权把 Q14(框架形式化证明,原 P3 defer)提前开头,当日完成首轮闭环+P3.0b 第一砖。①`formal/` **30 条定理**过机器检查、零 sorry、公理审计 30/30 仅经典三公理(fb771ff 首批 9→5560c39 扩 14→517dbda 扩 30;fb771ff 提交信息"7 条"是笔误):首批两模块(core-only,谓词式)=TNS 覆盖/极小元/反链/标准域坍缩+F5 具名轨道提升与两组反例;`DesignStatements.lean`(需 mathlib,Finset 式)=盲形式化陈述原样+本方填 12 个 sorry——**anon_lift_sound(F5 定理 2 完整形态)全链落地**(multiset匹配→部分置换延拓→组内置换搬运→boolean presence attach),TNS Finset 版 8 条,BLOCK-2 反例 decide 化。陈述层修改仅两处(README 记录):hExtend universe 特化 max v w+native_decide→decide。**mathlib v4.31.0 已接入**(lake-manifest 锁 rev 入库,cache ~4.5GB)。②设计稿 v2(文件名仍 _v1.md):轴 B 六处修正+P3.0c 七阶段(第一落点=binding PB sidecar 4-8 周)。③三路审查归档 `p3_0_formal_reviews_20260705/`;④F1-F9+完备性可开工地图归档 `p3_0b_family_formalizability_survey_20260705/`(main 40f6941)——第一梯队 7 family 核心可立即进 Lean,F8 等几何 reconcile,完备性 Q1 缺定义先写分类学设计稿。**锁面不动**——16_workflow_review §6.4 政策继续有效。
scope:
  domains:
    - formal-verification
    - roadmap
  paths:
    - formal/README.md
    - docs/research/p3_0_formal_verification_head_start_design_v1.md
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - formal-proof-question
    - plan-next-work
  keywords:
    - 形式化
    - Lean
    - Coq
    - formal
    - Q14
    - P3.0
    - VeriPB
    - VIPR
    - 公理
    - sorry
    - lake
  negative_keywords: []
  paths:
    - formal/
  symbols: []
  error_regex: []
  examples:
    - 形式化证明做到哪了
    - Lean 定理怎么 build/扩展
    - 证书侧 proof logging 什么状态
activation:
  layer_hint: L1
  must_know: false
  reason: 谈形式化/Q14/Lean 时该想起——①这条线已开头且有实物,别再引「零投资纯 defer」旧口径;②扩展纪律=陈述改动必须对照设计稿原文过独立复审(formalization gap 是最大风险面);③锁面没动,别把 formal/ 说成认证 TCB 的一部分。
provenance:
  op: record
  reason: owner 原话「把这个形式化证明试着开个头,或者更好的话再进一步往前推进,记得 gpt pro 是跟你一起的」(2026-07-05)。
  evidence:
    - "main fb771ff(首批)→5560c39(三包回收)→517dbda(anon_lift_sound+mathlib);lake build 绿(8562 jobs);axiom_audit 30/30 仅 propext/Classical.choice/Quot.sound"
    - "GPT Pro 包:C:\\Users\\22957\\pr2_pkg\\p3_0_formal\\(3 zip+3 prompt),三包已回收归档"
updated_at: "2026-07-05"
---
== 这条线是什么 ==
Q14(框架 completeness/soundness 形式化)原判 P3 defer(投资数年级)。owner 2026-07-05 授权开头。策略=**双轴拆分**(详见设计稿):
- **轴 A 定理侧**(已开工):范式数学定理进 Lean。抽象边界纪律=形式化在抽象层,模型侧前提(反单调/P-HOM)作为**假设**接入,成立性由设计稿的机器可查义务(ghost inventory/逐谓词审计/结构门)承担。三层分工:抽象定理层(Lean)+前提审计层(结构门)+工程层(validator/replay)。
- **轴 B 证书侧**(只做了任务书):求解结果的 proof log+经形式化验证的检查器(VeriPB 3.0/VIPR/cake_lpr 方向,文献 R4/R6/R7 已裁定;OR-Tools 无原生 proof log,要旁路重解)。它是瓶颈审计「编码忠实性单点」的终极解,与 I1 异构第二编码是同一笔投资,待 GPT Pro 包 3 回收后合并设计。

== 工具链与工作方式(实操必读)==
- elan 经 scoop 装(`scoop install elan`),工具链钉 v4.31.0(formal/lean-toolchain);`cd formal && lake build` 即验证。
- **开发在仓库外做**:`C:\Users\22957\zmd_formal_dev\`(含 build 产物与 axiom_audit)——原因见 [[concurrent-session-untracked-file-wipe]],共享工作区的 untracked 文件会消失;改动经临时 worktree 以 tracked 提交落 main。
- 扩展纪律:任何定理**陈述**的修改必须对照设计稿定理原文,且过独立复审(设计稿修订版复审纪律的延伸;对应表在 formal/README.md)。
- formal/ 永不进 CI 硬门(设计稿 §6 开放问题 2 的预判)。

== 下一批砖(按序;①②已完成 2026-07-05 main 517dbda)==
P3.0b 开工顺序:~~①装 mathlib~~ ✓(v4.31.0 tag=工具链同版,manifest 锁 rev 入库;zmd_formal_dev 有 ~4.5GB 缓存,新环境 `lake exe cache get`)→ ~~②anon_lift_sound~~ ✓(DesignStatements.lean 全链,含 NoPresenceKeyAlias/boolean attach)→ ③第一梯队 family 核心 F9→F1→F7→F4→F6→F2(全是初等计数/图论,见可开工地图;F6 当前版不用 Hall、F2 只需弱方向不用 MFMC;Finset 基数工具链在 DesignStatements 里已趟熟)→ ④F5 复合安全引理/TNS lex 支配/TP7-S nogood 键边界。F8 等 P1.3 欧氏 vs 12×12 方形 stencil reconcile;F3 带显式 all-ports-active 前提做。完备性 Q1 = 先写「不可行类分类学」设计稿(走独立审查链),不是 Lean 任务(theorem domain 都没定义,八个定义层缺口列在 survey/completeness.md)。
Lean 施工经验(30 条趟出来的,后续照用):▸ 的 motive 搜索会丢类型 ascription→包 private def(castSnd 模式)走 unifier defeq;`{ι : Type*}` 在 def 里=下游定理的刚性 universe 参数→下游特化 .{u,v,max v w};依赖 cast 用「先 subst 后显式化」引理组(groupSlot_cast/atom_cast_eq);fiber 拼装用 Equiv.sigmaFiberEquiv+Embedding.sigmaMap(双参,第一个传 refl)全程 defeq,别用 generalize+subst 碰依赖上下文;native_decide 引 ofReduceBool 公理,小反例一律纯 decide(先 show 展开 def 才能合成 Decidable 实例)。

== 首轮审查回收要点(纪律沿用)==
盲形式化与本方全部抽象选择收敛零矛盾;对抗审 1 BLOCK=覆盖面夸大(教训:README 对应表别把核心引理写成完整定理);证书侧深研修正六处混桶。补丁不盲 apply——lean 补丁经本地重编译+公理审计采纳(实修一处:Lean core 无 Function.Bijective,改双侧逆)。陈述改动必须重过「编译+公理审计+对照设计稿原文」三件套。
