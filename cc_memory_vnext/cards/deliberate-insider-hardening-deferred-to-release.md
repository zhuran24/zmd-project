---
id: deliberate-insider-hardening-deferred-to-release
kind: decision
title: 【策略】所有"仅防故意内鬼"的 verifier 硬化统一延期到发布时点、明确非 P1.2 闭合前提(owner 2026-07-06 拍板;判据=手滑/外部已被字节 sha floor 拦死,结构锚/TOCTOU/OS/import-time 残余只对能 reseal 的蓄意内鬼有意义)
summary: owner 2026-07-06 拍板:**所有"仅防故意内鬼(能执行 reseal 仪式的半可信/内部对手)"的硬化项,统一暂缓到发布时点再做,且明确【不作为 P1.2 闭合的必要条件】。** 判据(与 owner 当天亲自厘清的二分一致)：手滑/无心之失 + 纯外部篡改**早被第一层字节 sha floor 拦死**(改任一被钉文件→sha mismatch→fail-closed,当场红、轮不到人审);结构 AST 锚/TOCTOU/OS 隔离/import-time 完整性这些**只对"忠实 reseal 之后的蓄意内鬼"才有额外意义**(见 [[close-kernel-threat-model-reseal-adversary]] owner 2026-07-03 定性)。故这类在单 owner、自可信机器现实里防的是理论人物,真正变现实=发布/把 CERTIFIED 交给"不信任维护者本人"的第三方那一刻——所以放到发布时点做、正当。**延期桶(提取全集)**：#8 深化(父级锚点独立验 checker 的 byte-digest/projection/nucleus 镜像——现状父级信 checker 自报,补法有界见下)、#3 fd-held read-once/TOCTOU、#9b OS 写隔离、#9c 原生 .pyd/.so TOCTOU、#5-F(part1/2/3 import-time 完整性,part3 已被 V99 floor 兜到 TCB 线下)、#5 Option B(把 candidate_placements 移出证明权威=契约迁移)、#2(残余≡#3)。**不进桶(核心/防手滑外部/已做,常开不可延期)**：字节 sha floor 本身、#1 的 (a)(b)、#5-B2 Option A(16495f4)、#8 self-skip 删除(52c1e8d)、#4、#7；#9a 生产字节维持部署时点。**连带结论**：#1 剩余工程=阶段3 重构(=#5-F)+阶段④(=#3)+out-of-scope 硬地板,全在桶内或范围外→#1 无独立于桶外的前提工作;故此令一下,P1.2 的"编码类前提"实质清空,剩下=owner 手动 review 门+close-scope 拍板(≠P1.2 可关,关是手动门的事)。**这修订了 backlog 卡 07-06"收口前提=全 backlog 编码项"的说法**：现行=收口前提剔除全部"仅防故意内鬼"类,go_criteria:30"…或 owner 明确修改 close scope"正被行使。
scope:
  domains:
    - release-engineering
    - certified-exact
    - pr2
    - tcb
    - soundness
    - threat-model
  paths:
    - PROJECT_LOCK.md
    - docs/项目说明/12_go_criteria.md
    - docs/项目说明/soundness_gap_roadmap.md
    - scripts/check_p1_2_proof_obligations.py
    - src/search/certified_artifact_contract.py
  symbols: []
status: active
priority: P0
triggers:
  intents:
    - decide-if-item-is-p1-2-prerequisite
    - plan-p1-2-closeout
    - triage-deliberate-insider-hardening
    - decide-do-now-or-defer-to-release
  keywords:
    - 故意内鬼
    - 蓄意对手
    - 手滑 vs 故意
    - 字节 sha floor
    - 发布时点
    - 非 P1.2 前提
    - close scope 修改
    - 延期桶
    - checker-self 深化
    - fd-held read-once
    - OS 隔离
    - import-time 完整性
    - Option B
  negative_keywords: []
  paths:
    - PROJECT_LOCK.md
    - docs/项目说明/12_go_criteria.md
  symbols: []
  error_regex: []
  examples:
    - 某硬化项是不是 P1.2 收口前提 / 要不要现在做
    - "#8 深化 / #3 / #9b / #5-F / Option B 什么时候做"
    - P1.2 编码前提还剩什么
    - 手滑会不会被漏过 vs 故意才防不住
activation:
  layer_hint: L1
  must_know: true
  reason: 判"某硬化项是不是 P1.2 收口前提/现在做还是发布时做"时必读——owner 2026-07-06 把所有"仅防故意内鬼"类统一划到发布时点且非 P1.2 前提。不读会把已被 owner 明确降级的项重新当成收口阻塞、或分不清"手滑(floor 已拦)vs 故意(才是这类防的)"。P0 常驻:它改写了 P1.2 编码前提的边界。
provenance:
  op: record
  reason: 2026-07-06 owner 听完"内鬼=故意还是手滑"的厘清后拍板:所有仅防故意内鬼的硬化延期到发布、非 P1.2 前提,并令"提取全集写进文件与记忆"。
  evidence:
    - "2026-07-06:owner 问'内鬼指故意还是不小心'→ 我据 [[close-kernel-threat-model-reseal-adversary]](owner 2026-07-03 定性=半可信 reseal 对手)+ 三路 codex 对 checker 自绑的挖掘(workflow w3ya0tzqw:13 道自绑机制、绝大多数篡改 code-caught、唯一残余=保结构不变+重写函数体 return[]+reseal)厘清二分:手滑/外部被字节 sha floor 拦、结构锚只咬蓄意内鬼。owner 据此拍板延期全类到发布、非 P1.2 前提。#8 深化的可做项(父级独立验 checker byte-digest/projection/nucleus 镜像,现状父级信 checker 自报)由 workflow w3ya0tzqw constructive 路给出、判 few-reachable-hardenings。"
  updated_at: "2026-07-06"
---
2026-07-06 owner 拍板:**所有"仅防故意内鬼"的 verifier 硬化,统一暂缓到发布时点,且不作为 P1.2 闭合的必要条件。** 令我提取全集、写进文件与记忆。

== 判据:为什么这类能延、且非收口前提(手滑 vs 故意的二分)==
两层,各防各的,别混:
- **第一层 字节 sha floor(逐字节钉死)——管"手滑 + 外部篡改",拦得死、常开、不可延期。** 任何对被钉文件的改动(不管故意手滑)→ sha 对不上 → 当场 fail-closed。**手滑在这层就红了,根本轮不到人审。** 这是核心、不在延期范围。
- **第二层 结构 AST 锚 / TOCTOU / OS 隔离 / import-time 完整性——只对"忠实 reseal 之后的蓄意内鬼"才有额外意义。** 依据 owner 2026-07-03 定性 [[close-kernel-threat-model-reseal-adversary]]:这些锚对改不动被钉字节的纯外部对手毫无额外保护;唯一用武之地是"字节 sha 让改动可见、锚让改动即便被重钉也不能悄悄掏空语义"。**它们天生为蓄意 reseal 对手设计。**
- 在**单 owner + 自可信机器**的现实里,这个"蓄意内鬼"是理论人物(≈你会不会蓄意攻击自己+忠实重钉);它**真正变现实**=发布 / 把 CERTIFIED 交给"不信任维护者本人"的第三方(别人控制的 CI、有写权限的对抗审查者)。**所以放到发布时点做,正当。**

== 延期桶(提取全集)==
| 项 | 内容 | 为何仅防故意 |
|---|---|---|
| **#8 深化** | 父级锚点独立验 checker(byte-digest / projection recompute / 自绑 nucleus 镜像)——**现状父级信 checker 的 AST 自报 + JSON 声明 hash**,一个只改 checker 一个文件+重钉其自钉的内鬼当前只被人审抓;补法有界(见下) | 结构锚只咬 reseal 后蓄意掏空;手滑被字节 sha 拦 |
| **#3** | fd-held read-once / TOCTOU | 蓄意卡"检查到使用"之间掉包 |
| **#9b / #9c** | OS 级写隔离 / 原生 .pyd/.so load-time TOCTOU | 蓄意、需机器写权限 |
| **#5-F(part1/2/3)** | import-time 执行完整性;part3 已被 V99 whole-file floor 兜到 TCB 线下(非 release-blocking) | 只有蓄意攻击者钻 import 机制缺口/藏 import-time 副作用;手滑外部被 floor 兜 |
| **#5 Option B** | 把 candidate_placements 移出证明权威=契约迁移 | 残余=窄 TOCTOU(蓄意)+ governance;判据另见 [[pr2-5-b2-candidate-geometry-rederivation-landed]] |
| **#2** | 受控 loader 残余 | ≡ #3 |

已有分卡:#3/#9b/#9c 判据 [[deferred-verifier-hardening-toctou-os-isolation]];Option B 判据在 [[pr2-5-b2-candidate-geometry-rederivation-landed]];#5-F/#1 阶段3 [[stage3-spike-fused-5f-part3-findings]]。本卡是统辖这些的**策略层**。

== 不进桶(核心/防手滑外部/已做——常开,不可延期)==
字节 sha floor 本身;#1 的 (a) runtime 隔离 + (b)/① 白名单;#5-B2 Option A(`16495f4`);#8 self-skip 删除(`52c1e8d`);#4;#7。#9a 生产字节重钉维持**部署时点**(本就不是编码前提)。

== 连带结论:P1.2 编码前提实质清空 ==
- **#1 的剩余工程 = 阶段3 重构(吸收 #5-F)+ 阶段④(=#3)+ out-of-scope 求解器硬地板**——全在桶内或范围外。故 **#1 没有独立于延期桶之外、还等着做的前提工作**。
- 所以此令一下,原 backlog 卡(07-06)列的"收口前提=全 backlog 编码项(#8/#2/#3/#5-B2/#5-F/#1/#9b/#9c)"里,除已做的外**全部进了发布时点延期桶**。
- **净效果:P1.2 的编码类前提实质清空,剩下卡着的 = owner 手动 review 门 + close-scope 拍板。** `go_criteria:30`"…TCB 收缩完成,**或 owner 明确修改 close scope**"正被行使——本决定即那个 scope 修改。
- **不 overclaim**:这**不等于**"P1.2 可关"。关不关是 owner 手动门的事;绿灯/前提清 ≠ 已认证已发布(PROJECT_LOCK 铁律)。只是"被当作收口前提的编码 backlog"现在实质清了。

== #8 深化真到发布时做时、可做项已探明(免得届时重查)==
workflow w3ya0tzqw(3 路 codex)已挖清:checker 自绑有 13 道机制,绝大多数结构性掏空(重绑 main/删检查/缩必调 tuple/清 errors/提前 return/藏调用/局部遮蔽/import-time 命名空间写)**都 code-caught**;唯一 human-delegated 残余=**"保结构/名字/调用图不变,只把某必查函数体改成 return[] + 重钉"**(自证地板,只第四路能关)。可做的有界加固(few-reachable,非 theater)=把父级 `certified_artifact_contract.py` 对 checker 的信任从"信自报"升级为**独立验**:①父级自算 checker 源 byte-digest;②父级重算 manifest semantic projection;③父级镜像一小块自绑 nucleus。价值=把"改单文件+自重钉"升级成"必须协同改两个信任根"(更显眼/更贵),但不改最终地板。

== 何时翻转(发布时做)==
代码冻结进入发布流程、或 CERTIFIED 结果要交给不信任本机/本人的第三方时,按上表逐项做(阶段序仍参 [[p1-2-closeout-then-tcb-backlog-order]] 的轻→重:child 内容→child 闭包→OS 边界),各自一轮完整 reseal。

关联:威胁模型定性 [[close-kernel-threat-model-reseal-adversary]];主线排期 [[p1-2-closeout-then-tcb-backlog-order]];暂缓分卡 [[deferred-verifier-hardening-toctou-os-isolation]] / [[pr2-5-b2-candidate-geometry-rederivation-landed]] / [[stage3-spike-fused-5f-part3-findings]];ship-then-sweep [[ship-then-sweep-docs-for-stale-narrative]]。
