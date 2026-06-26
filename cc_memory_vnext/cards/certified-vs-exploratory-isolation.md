---
id: certified-vs-exploratory-isolation
kind: constraint
title: certified_exact 与 exploratory 证明链绝不交叉
summary: certified_exact 是唯一可产生认证证明材料的 solve path；exploratory 的 caps、hints、probe、sidecar 只能指导或诊断，不能上抛为 CERTIFIED 证据；durable CERTIFIED 只能由 supervisor_seal mint，公开发布只能走中央 publisher。
scope:
  domains: [certified-exact, proof-isolation]
  paths: [src/search/certified_surface.py, src/search/exact_campaign.py]
  symbols: [publish_verified_certified_delivery_surface, supervisor_seal]
status: active
priority: P0
severity: critical
triggers:
  intents: [certified-run, proof-surface-change, campaign-seal, publish-certified-result, exploratory-tooling]
  keywords: [certified_exact, exploratory, CERTIFIED, CANDIDATE_PROPOSED, supervisor_seal, publish_verified_certified_delivery_surface, caps, hints, probe, sidecar, 发布, 认证, 探索]
  negative_keywords: []
  paths: [src/search/certified_surface.py, src/search/exact_campaign.py, src/search/outer_search.py, src/search/benders_loop.py]
  symbols: [publish_verified_certified_delivery_surface, supervisor_seal, ExactCampaign.supervisor_seal, resolve_p1_2_publish_open_gate]
  error_regex: [false-CERTIFIED, "exploratory.*certified", "certified.*exploratory"]
  examples:
    - 要把 exploratory probe 找到的候选写进 certified 结果里
    - solver 找到了候选或测试过了，能不能直接发布 CERTIFIED
    - 修改 supervisor_seal 或 publish_verified_certified_delivery_surface 的认证发布链
activation:
  layer_hint: L0
  must_know: true
  reason: 这条规则决定哪些产物有认证证明权，错用会直接造成 false-CERTIFIED。
  claim_guards:
    - 候选直接当成认证结果
    - 探索性那条路
    - 怎么就能算证据
    - 两条路不是说好不能混
    - 用例绿了归绿了
    - 对外公布
    - 探针那点提示
    - 往正式结论上凑
    - 该过封印的还没过
provenance:
  op: record
  reason: 从项目锁、运行手册和 PR1 发布面修复记忆合并记录为 v-next 主动记忆卡。
  evidence:
    - "CLAUDE.md §The single most important rule: certified vs exploratory"
    - "PROJECT_LOCK.md §1 Exactness Constitution / §1A Certified Theorem Scope / §3 Accepted Invariants / §4 Forbidden Changes"
    - "python cc_memory/mem.py read pr1-publication-blocks-abc-fixed --body"
updated_at: "2026-06-26"
---
`certified_exact` 和 `exploratory` 是两条严格隔离的 solve path。只有 `certified_exact` 有资格产生证明材料；`exploratory` 的 caps、hints、probe results、sidecars、诊断 flow 或 legacy cut 只能作为指导、排查或启发，绝不能被当作 certified evidence、frontier pruning 依据、terminal evidence 或公开发布依据。exact mode 也不能重新引入 exploratory 的硬 cap，例如 "50 power poles + 10 protocol boxes"。

认证发布链必须保持分权：producer 侧最多提交 `CANDIDATE_PROPOSED` 和绑定的 proposal/replay 材料；唯一 durable terminal `CERTIFIED` mint 是 `ExactCampaign.supervisor_seal()`；唯一公开 certified publisher 是 `publish_verified_certified_delivery_surface()`。任何 generic writer、viewer/report、adapter、compatibility exporter、测试 helper、函数对象、closure、当前进程 freshness stamp 或"solver 找到了候选"都不是证明权来源。

使用这张卡时，先问当前改动是在生产证明链还是探索/诊断链。凡是要把候选状态、cut、hint、sidecar、probe 结果、测试通过结论或已有输出文件推向 `CERTIFIED`、公开 manifest、blueprint、solution、frontier pruning 或 terminal proof，都必须回到 supervisor seal、sink replay、fixed-witness verification、P1.2 open-gate 和中央 publisher 的闭合路径；缺一项就 fail closed，而不是本地补一个发布捷径。
