---
id: p3-0-formal-verification-head-start
kind: decision
title: P3.0 形式化线推进至 59 条定理+Q1 分类学设计稿 v1(2026-07-05)——七 family 核心/框架层/W-完备骨架全落 main;四包送审已 staged;锁面不动
summary: owner 2026-07-05 授权把 Q14(框架形式化证明,原 P3 defer)提前开头,当日 Lean 侧排队项全部清空。①`formal/` **56 条定理**过机器检查、零 sorry、公理审计 56/56 仅经典三公理或无公理(fb771ff 9→5560c39 14→517dbda 30→37965f6 45→ba17355 56;fb771ff 提交信息"7 条"是笔误),五个模块:TnsCoverage+F5OrbitLift(core-only)=TNS 覆盖链+F5 轨道提升与反例;DesignStatements=盲方陈述+本方施工——**anon_lift_sound 全链落地**;CutFamilies=**七个 family 核心 17 条**(第一梯队 F9/F1/F7/F4/F6/F2 各 bound+infeasible+第二梯队 F3 带 all-ports-active 显式量化);FrameworkLemmas=**框架层 9 条**(F5 复合安全引理(零公理)+无 P-HOM 删光反例/frontier lex 剪枝保最优+max_lex 具体化/TP7-S 等式键 sound·不过切·选中集式过切反例)。陈述层修改仅两处(README 记录)。**mathlib v4.31.0 已接入**。②设计稿 v2:轴 B 修正+P3.0c 七阶段(第一落点=binding PB sidecar 4-8 周)。③三路审查归档 `p3_0_formal_reviews_20260705/`;④可开工地图归档 `p3_0b_family_formalizability_survey_20260705/`。**CutFamilies+FrameworkLemmas 26 条待独立复审**(陈述本方写,未走盲对拼)。**锁面不动**——16_workflow_review §6.4 政策继续有效。
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

== 下一批砖(2026-07-05 当日 Lean 侧排队项①-⑤全部清空,main 517dbda→37965f6→ba17355)==
已完成:~~①装 mathlib~~ ✓(v4.31.0,manifest 锁 rev;zmd_formal_dev 有 ~4.5GB 缓存)→ ~~②anon_lift_sound~~ ✓(DesignStatements.lean 全链)→ ~~③第一梯队 6 family 核心~~ ✓(CutFamilies 15 条)→ ~~④F3~~ ✓(all-ports-active 显式量化+frontCell 抽象参数)→ ~~⑤F5 复合安全(零公理)+frontier lex 剪枝+TP7-S 等式键边界~~ ✓(FrameworkLemmas 9 条,各带正反两面:无 P-HOM 删光反例/选中集式 nogood 过切反例)。
剩余(按序):❶**送审已 staged 四包**(2026-07-05)——`C:\Users\22957\pr2_pkg\p3_0b_formal_review\`(包1 盲形式化 26 条/包2 对抗审 CutFamilies 17 条/包3 对抗审 Framework 9 条/包4 对抗审 Q1 分类学设计稿),剪贴板 8/8(Win+V 顶→底=使用顺序),**盲包已刻意去掉 survey README(含本方抽象定理表,防污染)**;等 owner 跑 GPT Pro 回传后 triage(补丁不盲 apply,重编译+公理审计+对照原文三件套);❷~~完备性分类学设计稿~~ ✓ **v1 已落 main 954dafa**(`docs/research/q1_infeasibility_class_taxonomy_design_v1.md`):D_cut 定义/六类+F5 兜底/owner lemma 模板/**核心裁定 = Q1 拆 W-完备(近乎结构性成立,Lean 可及)与 S-完备(改判实验命题,telemetry 承载)**,待外审(包4);❸~~W-完备 Lean 骨架~~ ✓(WCompleteness.lean 3 条,main a611937;**自查发现:设计稿 v1 §5「扩展=自身」隐含两前提 Feasible⊆Complete + Complete 无真包含,已在 Lean 显式化,v2 修订时补 §5**——包4 CONTEXT 已把此发现交给 reviewer 复核);❹~~组合定理~~ ✓(oracle_nogood_compound_search_safety,main f3efa5c,formal/ 到 **60 条**整);❺F8 等 P1.3 stencil reconcile;❻TP7-D 周期日历证书验收语义。**Lean 侧不依赖外审回传的活已全部做完**——回传前无排队项。
Lean 施工经验(30 条趟出来的,后续照用):▸ 的 motive 搜索会丢类型 ascription→包 private def(castSnd 模式)走 unifier defeq;`{ι : Type*}` 在 def 里=下游定理的刚性 universe 参数→下游特化 .{u,v,max v w};依赖 cast 用「先 subst 后显式化」引理组(groupSlot_cast/atom_cast_eq);fiber 拼装用 Equiv.sigmaFiberEquiv+Embedding.sigmaMap(双参,第一个传 refl)全程 defeq,别用 generalize+subst 碰依赖上下文;native_decide 引 ofReduceBool 公理,小反例一律纯 decide(先 show 展开 def 才能合成 Decidable 实例)。

== 首轮审查回收要点(纪律沿用)==
盲形式化与本方全部抽象选择收敛零矛盾;对抗审 1 BLOCK=覆盖面夸大(教训:README 对应表别把核心引理写成完整定理);证书侧深研修正六处混桶。补丁不盲 apply——lean 补丁经本地重编译+公理审计采纳(实修一处:Lean core 无 Function.Bijective,改双侧逆)。陈述改动必须重过「编译+公理审计+对照设计稿原文」三件套。
