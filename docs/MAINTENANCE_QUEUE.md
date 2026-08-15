# 文档维护队列

> 本页由周期审计注册表、policy、知识账本和生命周期真源自动生成；禁止手工修改。
> 文档系统版本：`2.6.0`；快照日期：`2026-08-13`；profile：`phase_close`。

本页只投影维护触发器。它不建立第二套 current 状态、claim、review、triage 或 owner authority。接受某条 finding 后，仍须通过原有 intake、knowledge 或 policy 写入路径完成修复。

## 总览

| 严重度 | 数量 |
|---|---:|
| error | 0 |
| warning | 0 |
| info | 70 |

## Findings

| 严重度 | 检查 | 对象 | 触发器 | 后续动作 |
|---|---|---|---|---|
| `info` | `DOC-AUDIT-ACTIVE-DOSSIER-AGE` | `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-FRESH-AUTHORITY-20260727-EA260C6D6B` | active dossier 已打开 17 天；应继续工作、更新 next action，或以 typed outcome 关闭。 | `docsystem.intake`<br>`knowledge.build` |
| `info` | `DOC-AUDIT-ACTIVE-DOSSIER-AGE` | `DOSSIER-B1-SIDEWISE-MARKED-MEMBRANE-STRICT-20260724-F275CFCFE2` | active dossier 已打开 20 天；应继续工作、更新 next action，或以 typed outcome 关闭。 | `docsystem.intake`<br>`knowledge.build` |
| `info` | `DOC-AUDIT-ACTIVE-DOSSIER-AGE` | `DOSSIER-P1-2-V99-CLOSE-KERNEL-SEALING-207F650E44` | active dossier 没有可用于年龄计算的 opened_at/date；保持显式人工复核。 | `docsystem.intake`<br>`knowledge.build` |
| `info` | `DOC-AUDIT-ACTIVE-DOSSIER-AGE` | `DOSSIER-P2-0-AREA-BOUND-20260806-6016501B5F` | active dossier 已打开 7 天；应继续工作、更新 next action，或以 typed outcome 关闭。 | `docsystem.intake`<br>`knowledge.build` |
| `info` | `DOC-AUDIT-ACTIVE-DOSSIER-AGE` | `DOSSIER-P2-0-SPECIALIZED-20260807-C40266E222` | active dossier 已打开 6 天；应继续工作、更新 next action，或以 typed outcome 关闭。 | `docsystem.intake`<br>`knowledge.build` |
| `info` | `DOC-AUDIT-ACTIVE-DOSSIER-AGE` | `DOSSIER-RULE-SYSTEM-REDESIGN-20260807-9B23FA19D2` | active dossier 已打开 6 天；应继续工作、更新 next action，或以 typed outcome 关闭。 | `docsystem.intake`<br>`knowledge.build` |
| `info` | `DOC-AUDIT-ACTIVE-DOSSIER-AGE` | `DOSSIER-RULES-AUDIT-20260718-A447D60E10` | active dossier 已打开 26 天；应继续工作、更新 next action，或以 typed outcome 关闭。 | `docsystem.intake`<br>`knowledge.build` |
| `info` | `DOC-AUDIT-ACTIVE-DOSSIER-AGE` | `DOSSIER-WITNESS-CONSTRUCTOR-20260717-5F04E123B3` | active dossier 已打开 27 天；应继续工作、更新 next action，或以 typed outcome 关闭。 | `docsystem.intake`<br>`knowledge.build` |
| `info` | `DOC-AUDIT-DEPRECATED-KNOWLEDGE-REFERENCES` | `deprecated-reference-summary` | 扫描 106 份 current 手写文档，没有发现无语境的失效 claim 引用。 | `docsystem.intake`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-EPHEMERAL-EXPIRY` | `ephemeral-registry` | 当前没有登记中的临时文档。 | `docsystem.intake`<br>`docsystem.doctor` |
| `info` | `DOC-AUDIT-LIVING-FRESHNESS` | `living-freshness-summary` | 按 review_policy 检查了 103 份 current 文档；Git 日期仅作为重审触发器。 | `docsystem.intake`<br>`docsystem.doctor` |
| `info` | `DOC-AUDIT-OPEN-CLAIM-QUEUE` | `CLAIM-CERTIFIED-EXISTENCE-OPEN` | 现行语义下 whole-layout 认证级存在性仍为 OPEN | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-OPEN-CLAIM-QUEUE` | `CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN` | 通用 CP-SAT 传播不能替代领域分离的正式命题仍开放 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-OPEN-CLAIM-QUEUE` | `CLAIM-P2-MIN-SIDE-UPPER-OPEN` | P2.0 的 min_side 上界仍未建立 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-PHASE-BOUNDARY-SURFACE` | `phase-boundary-inventory` | 阶段边界必须逐项处置 active workflow、语义未决项、长尾分诊、开放命题与临时材料；清单不自动授予 close。 | `docsystem.audit_deep`<br>`docsystem.gate_full` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-AB16-ARMS-BATCH3` | current review 保留 1 个未决项；重审触发：新的 AB16 successor experiment 或 artifact 迁入 tracked evidence。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-B1-CONDITIONAL-HALO-BATCH2` | current review 保留 1 个未决项；重审触发：conditional halo 被接入新的候选族、出现 formal band separation，或 all-selected-poles scope 变化时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-B1-QMH-BATCH2` | current review 保留 1 个未决项；重审触发：QMH 被组合进新的正式 band、边界 pattern 语义变化，或需要单独登记 double-counting 负结果时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-BAND22-CLEANROOM-V0A-BATCH2` | current review 保留 1 个未决项；重审触发：开始 cleanroom 专题回填，或 band22 产生新的 tracked strict witness 时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-BAND22-STRICT-HOLE-PROBE-BATCH2` | current review 保留 1 个未决项；重审触发：出现新的 band22 strict witness、单列拓扑坐标化，或可选 artifact 被迁入 tracked evidence。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-BATCH-CE-ATTACH-HOST-BATCH3` | current review 保留 1 个未决项；重审触发：新的 B6 promotion 议案或 attach-host 全专题回填。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-CANONICAL-BATCH-20260807` | current review 保留 1 个未决项；重审触发：canonical rules 再次 freeze，或开始 rules-semantics 全量回填。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-CANONICAL-BATCH-20260808` | current review 保留 1 个未决项；重审触发：处理 simulator provenance 或 model-stricter 候选墙时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-COLUMN-GENERATION-PHASE2-BATCH4` | current review 保留 1 个未决项；重审触发：column generation 以新 design version 重启，或需要逐项复用 Phase 2 诊断组件时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-F7-ROUND1-BATCH4` | current review 保留 1 个未决项；重审触发：F7 family 重新进入 active production 路线时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-F7-ROUND2-BATCH4` | current review 保留 1 个未决项；重审触发：F7 schema、assumption tracking 或 cut authority 重新开放时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-FRONT-OFFSET-ARTIFACT-BATCH4` | current review 保留 1 个未决项；重审触发：恢复该 artifact payload 或新增 repaired-result receipt 时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-FRONT-OFFSET-INCIDENT-BATCH4` | current review 保留 1 个未决项；重审触发：任一历史 front-dependent 结果完成新的修正语义复验，或 front 语义 authority 再次变化时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-HISTORY-TOOLCHAIN-ORIGIN-BATCH3` | current review 保留 1 个未决项；重审触发：cut framework 起源文档被迁移或产生新的 provenance package 时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-IHS-PHASE0-BATCH4` | current review 保留 1 个未决项；重审触发：IHS 使用新的 core 语义、一般化粒度或候选 anchor 重启时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-LAZY-POWER-PHASE0-BATCH4` | current review 保留 1 个未决项；重审触发：lazy power 路线更换 cut language、master representation 或 candidate anchor 后。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-M5-CONVERGENCE-BATCH4` | current review 保留 1 个未决项；重审触发：资源条款、wrapper cpuset 或默认参数再次改变时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-MIXFLOW-FIXTURE-CORRECTION-BATCH4` | current review 保留 1 个未决项；重审触发：恢复本地 artifact、延长受控预算或把 demix 结果提升为更高 authority 时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-NONCERT-CUTS-AB16` | current review 保留 1 个未决项；重审触发：出现新的可归因 activation/control 证据。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-P1-2-V99-CLOSE-KERNEL` | current review 保留 1 个未决项；重审触发：开始 P1.2 proof-chain 专题回填。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-P2-AREA-BOUND-BATCH2` | current review 保留 1 个未决项；重审触发：OB6 被 discharge、P2.0 口径改变、或开始负结果/超边 packing 专题时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-P2-SPECIALIZED-BATCH4` | current review 保留 1 个未决项；重审触发：P2.0 专题 Batch 5 或新增反例/构造时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-PARADIGM-LEVER-HISTORY-BATCH4` | current review 保留 1 个未决项；重审触发：Batch 5 长尾收口或任一 lever 在新 revision 下重启时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-R3-UPPER-BOUND-PB-BATCH2` | current review 保留 1 个未决项；重审触发：R3 几何引理被重新审判，或需要把 cleanroom 的上游几何证书拆为独立 claim 时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-R4-RESPONSE-BATCH2` | current review 保留 1 个未决项；重审触发：A004 admission 变化、local access geometry 被反例击中，或新 marked family 复用该链时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-RAB-SEP-PROMOTION-BATCH4` | current review 保留 2 个未决项；重审触发：启动 corrected-front RAB/FCL 对照、恢复旧效果 claim，或在 Batch 5 做长尾 dossier 收口时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-RULE-SYSTEM-REDESIGN-BATCH3` | current review 保留 1 个未决项；重审触发：相关规则引擎、closure scanner 或 derived-rule registry 真正落地时重审。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-RULES-AUDIT-BATCH4` | current review 保留 1 个未决项；重审触发：rules-semantics Batch 5 或认证链完成 strict occupant 实现修复时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-SMT-MT-PHASE0-BATCH4` | current review 保留 1 个未决项；重审触发：SMT-MT 使用新 inner、proof policy 或 candidate lattice 重跑时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-SMT-MT-PHASE1-BATCH4` | current review 保留 1 个未决项；重审触发：真实 inner 的 terminal mix 或 proof closure 发生实质变化时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-SOLVER-RETHINK-BATCH3` | current review 保留 1 个未决项；重审触发：owner 正式立线、否决该架构，或 local artifact 迁入 tracked evidence 时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-W0-POWER-COUNTEREXAMPLE-BATCH4` | current review 保留 1 个未决项；重审触发：纯装定理完成重证，或 27 号完整 routing/port 层获得独立复核时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260811-WITNESS-CONSTRUCTOR-BATCH4` | current review 保留 1 个未决项；重审触发：出现 geometry_ready attempt、完整 witness，或 pole candidate inventory 实质变化时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260812-GHOST-STRICT-FIX-BATCH5` | current review 保留 2 个未决项；重审触发：ghost occupancy、routing digest、blocked-port cut 通道、canonical empty-rectangle 语义或 owner reseal 边界变化时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260812-P2-REFRESH-BATCH5` | current review 保留 2 个未决项；重审触发：P2.0 area ledger、OB6 条件、route-state 计数或本地 receipt provenance 发生变化时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-REVIEW-FOLLOWUPS` | `REVIEW-20260812-SMM4-LOCAL-AUTHORITY-AVAILABILITY-BATCH5` | current review 保留 1 个未决项；重审触发：外部 authority root 可用、其 manifest/hash 变化，或六谓词 research ledger 的 authority 链被重开时。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-SNAPSHOT-AGE` | `maintenance-snapshot` | 维护投影快照日期为 2026-08-13，距本次审计 0 天。 | `docsystem.render_maintenance`<br>`docsystem.audit` |
| `info` | `DOC-AUDIT-TERMINOLOGY-COLLISION` | `terminology-summary` | 27 个 term 的 canonical label 与 alias 没有跨 ID 碰撞。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TOPIC-COVERAGE` | `topic-summary` | 13 个 topic 的 claim、term、entry 与 open-claim 坐标完整。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-CUT-SOLVER-TRACKED-LONGTAIL` | 14 个 dossier 处于 historical_semantic_queue，优先级 normal。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-DOCUMENTATION-GOVERNANCE-TRACKED-LONGTAIL` | 2 个 dossier 处于 historical_semantic_queue，优先级 low。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-FORMAL-VERIFICATION-TRACKED-LONGTAIL` | 7 个 dossier 处于 historical_semantic_queue，优先级 normal。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-LOCAL-CUT-SOLVER-EXPERIMENTS` | 1 个 dossier 处于 local_optional_queue，优先级 low。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-LOCAL-DELIVERY` | 1 个 dossier 处于 local_optional_queue，优先级 low。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-LOCAL-OPTIONAL-MISC` | 24 个 dossier 处于 local_optional_queue，优先级 low。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-LOCAL-P2-THROUGHPUT` | 2 个 dossier 处于 local_optional_queue，优先级 normal。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-LOCAL-RULES-SEMANTICS` | 3 个 dossier 处于 local_optional_queue，优先级 normal。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-LOCAL-UPPER-BOUND-AND-BAND22` | 10 个 dossier 处于 local_optional_queue，优先级 normal。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-LOCAL-WITNESS` | 6 个 dossier 处于 local_optional_queue，优先级 normal。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-OTHER-TRACKED-LONGTAIL` | 18 个 dossier 处于 historical_semantic_queue，优先级 low。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-P1-2-PROOF-CHAIN-FAMILY` | 67 个 dossier 处于 family_context_only，优先级 normal。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-P2-THROUGHPUT-TRACKED-LONGTAIL` | 2 个 dossier 处于 historical_semantic_queue，优先级 normal。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-UPPER-BOUND-TRACKED-LONGTAIL` | 5 个 dossier 处于 family_context_only，优先级 normal。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `TRIAGE-WITNESS-TRACKED-LONGTAIL` | 3 个 dossier 处于 historical_semantic_queue，优先级 normal。 | `knowledge.build`<br>`knowledge.check` |
| `info` | `DOC-AUDIT-TRIAGE-BACKLOG` | `backfill-triage-ledger` | triage ledger 最近复核于 2026-08-15，当前包含 15 个分组。 | `knowledge.build`<br>`knowledge.check` |

## 维护边界

- `info` 是显式队列，不自动变成失败；`warning` 与 `error` 是否阻断由所选 profile 的 `fail_on` 决定。
- Git 最近触达日期只是重审触发器，不证明语义已复核。
- inventory coverage 不等于 semantic review；open claim 也不是机械故障。
- 周期审计只发现遗漏、陈旧、碰撞和待办；所有修复都回到同一事件驱动写入管道。

重建与复核：

```bash
.venv/bin/python devtools/docctl.py render-maintenance --write
.venv/bin/python devtools/docctl.py audit --profile weekly
.venv/bin/python devtools/docctl.py audit --profile deep
```
