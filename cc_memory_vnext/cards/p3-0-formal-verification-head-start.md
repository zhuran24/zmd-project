---
id: p3-0-formal-verification-head-start
kind: decision
title: P3.0 形式化证明已开头(owner 2026-07-05)——formal/ 9 条 Lean 定理落 main,双轴架构定稿,GPT Pro 三包已 staged;锁面不动
summary: owner 2026-07-05 授权把 Q14(框架形式化证明,原 P3 defer)提前开头。已落地——①`formal/`(Lean 4.31 core,零 mathlib,零 sorry,公理审计仅经典三公理)9 条定理过机器检查(main fb771ff+计数修正 7a3f1ff;fb771ff 提交信息里的"7 条"是笔误,实为 9)——TNS 覆盖论证/乘积序极小元/一般域反链证书/标准域 (6,6) 单点坍缩 + F5 具名轨道提升(发现只需单向 P-HOM)/匿名 multiset 搬运/「禁重复」前提的机器反例;②双轴设计稿 `docs/research/p3_0_formal_verification_head_start_design_v1.md`(轴A定理侧 Lean/轴B证书侧 VeriPB-VIPR 按文献 R4/R6/R7 裁定;抽象边界纪律=模型侧前提作假设接入;P3.0a-d 阶梯);③GPT Pro 三包 staged(盲形式化/陈述保真对抗审/证书侧路线深研)。**锁面不动**——16_workflow_review §6.4「不用形式化 proof system」政策继续有效,本线是前瞻投资不改任何 gate 验收标准。
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
    - "main fb771ff(formal/ 9 文件+419 行)+7a3f1ff(计数修正);lake build 绿;axiom_audit 输出仅 propext/Classical.choice/Quot.sound"
    - "GPT Pro 包:C:\\Users\\22957\\pr2_pkg\\p3_0_formal\\(3 zip+3 prompt),剪贴板 6/6 staged"
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

== 下一批砖(按序,README「下一批砖」一致)==
anon_lift_sound(需 mathlib Equiv/Fintype:部分单射延拓成有限群置换)→ F5 复合安全引理 → TNS lex 序 frontier 支配骨架 → TP7-S nogood 完整键过切/欠切边界。

== GPT Pro 三包(staged 待 owner 跑)==
剪贴板 Win+V 顶→底=包1路径/提示词1/包2路径/提示词2/包3路径/提示词3。包1盲形式化(只给设计稿,回收对拼抓 formalization gap);包2陈述保真对抗审(审 Lean 陈述 vs 设计稿原文,含「σ 任意函数 vs 同组约束是发现还是错译」这类点);包3证书侧路线深研(可联网,2026 生态现状+接口可行性)。回收处理=对拼 triage→修订→(若改陈述)重编译+公理审计+复审。
