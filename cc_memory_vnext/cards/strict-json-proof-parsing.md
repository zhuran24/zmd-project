---
id: strict-json-proof-parsing
kind: constraint
title: Proof 相关 JSON 解析必须走 strict_json 入口
summary: 所有喂给 binding/master/preprocess 的 proof 输入路径都必须使用 src/io/strict_json.py 的严格解析入口，拒绝重复键和 NaN/Infinity，写出时显式 allow_nan=False。
scope:
  domains: [strict-json, proof-io]
  paths: [src/io/strict_json.py]
  symbols: [strict_json]
status: active
priority: P0
severity: high
triggers:
  intents: [edit-proof-io, parse-proof-json, add-certified-input-loader]
  keywords: [strict_json, strict JSON, proof JSON, json.loads, json.load, allow_nan, NaN, Infinity, 重复键, 证明输入, binding, master, preprocess]
  negative_keywords: [telemetry-only, debug-only, exploratory-only]
  paths: [src/io/strict_json.py, src/models/binding_subproblem.py, src/models/master_model.py, rules/canonical_rules.json, data/preprocessed/mandatory_exact_instances.json, data/preprocessed/candidate_placements.json]
  symbols: [strict_json, loads_strict_json, load_strict_json, json.loads, json.load]
  error_regex:
    - 'duplicate JSON key|invalid JSON constant|non-finite JSON number|NaN|Infinity|json\.loads'
  examples:
    - 我要给 binding_subproblem 新增一个读取 proof 输入 JSON 的路径
    - master 或 preprocess 要解析 canonical_rules / mandatory instances / candidate placements
    - 这里直接用 json.loads 读证明相关文件行不行
activation:
  layer_hint: L1
  must_know: true
  claim_guards:
    - json.loads
    - 重复键
    - NaN
    - 严格的入口
    - preprocess
  reason: 宽松 JSON 解析会让重复键或非有限数进入证明输入链，破坏 proof I/O 完整性。
provenance:
  op: record
  reason: 从项目 runbook 的 proof JSON 严格解析约束提炼为 v-next 主动记忆卡。
  evidence:
    - "CLAUDE.md:256-258 Conventions and gotchas / All proof-relevant JSON parsing is strict"
    - "src/io/strict_json.py:51-73 loads_strict_json and load_strict_json"
updated_at: "2026-06-26"
---
所有 proof 相关 JSON 输入都走 `src/io/strict_json.py` 的共享 strict 入口。这个入口拒绝重复 object key，拒绝 `NaN` / `Infinity` 这类非有限数；写出 proof 相关 JSON 时也要显式使用 `allow_nan=False`，避免把 Python 的宽松 JSON 行为带进证明链。

这条约束特别覆盖喂给 binding、master、preprocess 的 proof 输入路径，例如 canonical rules、mandatory exact instances、candidate placements，以及任何会影响 certified/exact proof 状态的 JSON 载入。不要在这些路径上裸用 `json.loads` 或 `json.load`，除非它只是严格入口内部实现的一部分，并且已经设置 duplicate-key 与 non-finite 拒绝逻辑。

如果新增 loader、迁移输入文件、或把某个诊断路径提升为 proof 相关路径，先把解析收敛到 `strict_json` 共享入口，再处理 schema 校验和业务语义。裸解析放过重复键会产生 last-write-wins，放过非有限数会污染数值语义；这不是格式小问题，而是 proof 输入完整性问题。
