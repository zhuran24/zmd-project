---
id: stage3-spike-fused-5f-part3-findings
kind: reference
title: 阶段3 spike 调查发现(2026-07-04)— fused=speedup-holds(本质省第二次 close-kernel 17s)+ #5-F part3 soundness 已被 V99 floor 兜住(TCB 线下)+ 阶段3 枢纽=#1
summary: 2026-07-04 owner 离线期做的阶段3 spike 前期调查(纯取证/设计、零代码改动)的客观发现。**fused child**:第二个隔离 child(standalone fixed-witness capsule)重复付固定税 ~22.14s/次(生产规模,n=5)→ speedup-holds;但构成关键——hash 段 18.14s 里 close-kernel checker 占 17.22s、source digest 0.87s、raw artifact SHA(含 45MB candidate_placements)仅 0.033s。所以 fused 省的**不是 SHA,是第二个 child 冗余重跑的 close-kernel checker**;它是"两个独立 child 验证职责能否安全合并而不失独立复验 soundness"的 TCB 结构判断,非纯性能,别走"第二 child 复用第一结果"的失独立性捷径。**#5-F part3**(非-import 的 import-time 副作用完整性):**soundness 已被 V99 whole-file floor 兜住**——插入任何 part3 副作用会改文件字节 → source hash mismatch → floor 抓到;残余只在 reseal diff 显眼度 + checker self-TCB 人审 → **TCB 线下**(非 release-blocking)。现状攻击面 60 manifest sink 里 53、92 V99 floor 文件里 74 有非平凡 import-time 执行面。三选一推荐 B(重构最小化,与 #1 联动)+ interim C(接受残余),不投 A(追全无界、不改底线);核实"#1 重构溶解大半 part3"成立。**综合:阶段3 枢纽=#1(最小 TCB 闭包)**——#1 往"child 不 import 项目域、快照不扫全 src"重构,顺带塌缩 #5-F part3 攻击面(B)+ child 结构简化容纳 fused;阶段3=一次以 #1 为核心的重构,#5-F-B + fused 是受益面,一批做。都属真·深化(改认证核心+reseal),**是 P1.2 收口的前提、现在就做**(owner 2026-07-04 晚:先做 #1 深化再收口,不是先收口);三选一 owner 2026-07-04 已拍板采纳(#5-F 选 B+interim C、fused 与 #1 同批、阶段3 以 #1 为枢纽)。
scope:
  domains:
    - certified-exact
    - pr2
    - close-kernel
    - test-performance
  paths:
    - src/search/pr2_l0_true_verifier_child.py
    - src/search/exact_campaign.py
    - scripts/check_p1_2_proof_obligations.py
  symbols:
    - compute_exact_artifact_hashes
    - validate_locked_p1_2_close_kernel
status: active
priority: P1
triggers:
  intents:
    - plan-stage3-tcb-refactor
    - decide-fused-child
    - decide-5f-part3-option
    - judge-if-5f-part3-is-release-blocking
  keywords:
    - fused child
    - 固定税
    - close-kernel 17s
    - speedup-holds
    - "#5-F part3"
    - V99 floor 兜底
    - import-time 副作用
    - 三选一
    - 最小 TCB 闭包
    - "#1 枢纽"
    - 阶段3 spike
    - compute_exact_artifact_hashes
  negative_keywords: []
  paths:
    - src/search/pr2_l0_true_verifier_child.py
    - scripts/check_p1_2_proof_obligations.py
  symbols:
    - compute_exact_artifact_hashes
  error_regex: []
  examples:
    - fused child 到底值不值 / 收益多大
    - "#5-F part3 是不是 release-blocking / 要不要追全 AST 扫描"
    - 阶段3 该怎么排 / #1 #5-F fused 什么关系
activation:
  layer_hint: L1
  must_know: false
  reason: 规划阶段3(#1/#5-F/fused)或判"#5-F part3 是不是 release-blocking soundness 洞"时该想起——这些是调查实测得出的非显然发现(fused 省的是 close-kernel 非 SHA;#5-F part3 已被 V99 floor 兜到 TCB 线下;三项其实是以 #1 为核心的一次重构),照它排能少走弯路、不误把 #5-F 当阻塞。
provenance:
  op: record
  reason: 2026-07-04 owner 离线期阶段3 spike 前期调查(fused 固定税实验 + hash 段补测 + #5-F 三选一设计,均零代码改动)的客观发现固化。
  evidence:
    - "2026-07-04:fused 固定税补测 n=5 生产规模,compute_exact_artifact_hashes median 18.14s(close-kernel 17.22s / source digest 0.87s / artifact SHA 0.033s),+~4s 启动 = ~22.14s → speedup-holds;调用点 pr2_l0_true_verifier_child.py:635。#5-F 调查:60 sink 里 53、92 V99 floor 里 74 有非平凡 import-time 执行;part3 被 V99 whole-file floor 字节兜底(TCB 线下);推荐 B+interim C。全程 git status -- src data 空。决策包 + #5-F 报告已 SendUserFile 给 owner。"
  updated_at: "2026-07-04"
---
阶段3 spike 调查发现(2026-07-04 owner 离线期,纯取证/设计、零代码改动)。三选一 owner 2026-07-04 已拍板采纳推荐;以下是客观发现 + 已采纳的推荐。

== fused child 收益 = speedup-holds(性质需看清)==
- 第二个隔离 child(standalone fixed-witness capsule)重复付固定税 **~22.14s/次**(median,n=5,生产规模真实输入)。
- 构成:启动+heavy import+snapshot ~4s(toy 实测,与规模无关) + hash 段 18.14s。hash 段拆:**close-kernel checker 17.22s**、source-tree digest(786 文件)0.87s、**raw artifact SHA(含 45MB candidate_placements)仅 0.033s**、contract 0.0002s。
- **本质:fused 省的是第二个 child 冗余重跑的 close-kernel checker(17s),不是 SHA。**
- 调用点:`pr2_l0_true_verifier_child.py:635` `_run_fixed_witness_direct()` → `compute_exact_artifact_hashes()`(`exact_campaign.py:419`)内部强制先跑 `validate_locked_p1_2_close_kernel()`(启动 `check_p1_2_proof_obligations.py` 子进程)。
- 架构:L0 内 replay/fixed-witness 是 **direct 调用**(非二次 spawn);重复付固定税的是**独立 standalone fixed-witness capsule child** 那次 spawn。
- **性质:fused 是"两个独立 child 的验证职责能否安全合并到一次 close-kernel 而不失独立复验 soundness"的 TCB 结构判断,不是纯性能。别走"第二 child 复用第一 child 结果"的捷径(失独立性)——正确方向是 fused(一个 child 一次独立验证承两份职责)。**

== #5-F part3(非-import 的 import-time 副作用完整性)==
- **关键:part3 soundness 已被 V99 whole-file floor 兜住。** 插入任何 part3 副作用(metaclass / `__init_subclass__` / descriptor / 类体执行 / 模块级调用 / def-time 隐式调用)会改文件字节 → source hash mismatch → floor fail-closed 抓到。part3 **不是"改了没人发现"的 soundness 洞**;残余只在:① reseal diff 显眼度(人工能否一眼看出恶意 vs 良性);② checker self-TCB(自钉、floor 兜不到自己、需人审)。→ **TCB 线下**(对半可信内部对手的强度选择,非 release-blocking)。
- 现状攻击面:60 manifest sink 里 **53** 有非平凡 import-time 执行;92 V99 floor 文件里 **74** 有。例:`exact_campaign.py`、`pr2_l0_true_verifier_child.py`(child import certified_frontier/exact_campaign)、`benders_loop.py`(OR-Tools+solver 域)。
- 三选一:**A 追全**(AST 穷举)—— 工作量无界、只加诊断细化、不改 soundness 底线(V99 已兜)、checker self-TCB 膨胀 → 不建议;**B 重构最小化**(与 #1 联动)—— 收益最高、核实"#1 重构溶解大半 part3"成立、attack surface 从"60~92 模块穷举"收敛为"小 allowlist" → 战略路线;**C 接受残余**(V99 floor + 人工 reseal)—— 现状、B 落地前 interim。
- **推荐(codex + Opus)→ owner 2026-07-04 已拍板采纳:B + interim C,不投 A。**

== 综合:阶段3 枢纽 = #1(最小 TCB 闭包)==
- 两调查殊途同归:**#1 是阶段3核心手术**。#1 往"child 不 import 项目域、快照不扫全 src"重构 → 顺带塌缩 #5-F part3 大半攻击面(#5-F 选 B)+ child 结构简化容纳 fused(省 ~22s/次)。
- 阶段3 **= 一次以 #1 为核心的重构**,#5-F-B + fused 是两个受益面,一批做(同一次 reseal)。
- 都属**真·深化**(改认证核心 sealed 代码 + reseal);**#1 是 P1.2 收口的前提,现在就做**(owner 2026-07-04 晚修正:先做 #1 再收口,不是先收口后深化;详见 [[review-convergence-tcb-line-not-zero-findings]] "再澄清"段)。#5-F part3 的 soundness 虽有 V99 floor 兜底(C interim),但 #1 最小 TCB 闭包本身是收口前提。
- **#1 实施(owner 2026-07-04 拍板 A + 认可 4 阶段)**:走 A 路径——只缩 child【执行面】到最小白名单、保留 source provenance floor 作 non-import digest(不改证明架构;理由:B 把 source floor 责任移到 checker self-TCB=更难自证的地方,长远更脆)。4 阶段:①冻验收+红线测试(只加测试不 reseal)→②抽 proof-core(pr2_l0_artifact_core/frontier_core/candidate_replay_core/fixed_witness_core,child 不再 import certified_frontier/exact_campaign/capsule)→③最小 execution snapshot(=#2,显式白名单替代扫全 src)→④fd-held read-once loader(=#3),每阶段一轮完整 reseal。验收硬门:child runtime sys.modules 无那三大模块 + snapshot 非全 src + replay/fixed-witness 语义等价或更强。**fused 校正**:当前 main 上 L0 child 已同进程 direct 调用 replay+fixed-witness、【无第二子进程可省】;之前测的 ~22s 是另一条公开 sink 路径的 standalone capsule child、跟 #1 不是一回事;fused 性能收益须在当前 main 重测,#1 收益以 TCB 从 668 模块/33 万行砍到最小为主。规划报告见 scratchpad/backlog_1_min_tcb_closure_plan.md。

报告(2026-07-04 session scratchpad,已 SendUserFile 给 owner):决策包 `p1-2-stage3-spike-decision-pack.md`;#5-F 详细 `5f-part3-tradeoff-investigation.md`;fused 脚本 `measure_fused_child_fixed_tax.py` / `measure_production_hash_segment.py`。

关联:主线计划 [[p1-2-closeout-then-tcb-backlog-order]];TCB 线判据 [[review-convergence-tcb-line-not-zero-findings]];close-kernel 威胁模型 [[close-kernel-threat-model-reseal-adversary]];reseal 实操 [[close-kernel-reseal-execution-sop]]。
