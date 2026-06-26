---
id: frozen-artifact-freeze-ritual
kind: constraint
title: Frozen artifact 修改必须走 freeze ritual
summary: 改 frozen artifact 必须同步 hash、重生成依赖产物并重跑 gate；不能把 hash-pinned 输入当成随手 overlay。
scope:
  domains: [frozen-artifacts, freeze-ritual]
  paths: [rules/canonical_rules.json, rules/preprocess_plan.json, scripts/preflight_gate.py]
  symbols: [FROZEN_ARTIFACTS]
status: active
priority: P0
severity: high
triggers:
  intents: [edit-frozen-artifact, update-preflight-hash, regenerate-preprocessed-data, fix-hash-mismatch]
  keywords: [frozen artifact, freeze-ritual, canonical_rules, preprocess_plan, FROZEN_ARTIFACTS, preflight_gate, hash-pinned, 冻结输入, 预处理 JSON]
  negative_keywords: []
  paths: [rules/canonical_rules.json, rules/preprocess_plan.json, data/preprocessed/mandatory_exact_instances.json, data/preprocessed/generic_io_requirements.json, data/preprocessed/candidate_placements.json, scripts/preflight_gate.py]
  symbols: [FROZEN_ARTIFACTS]
  error_regex: ["FROZEN_ARTIFACTS", "hash.*mismatch", "frozen artifact"]
  examples:
    - 我要改 canonical_rules.json 里的配方或目标规则。
    - preflight 报 FROZEN_ARTIFACTS hash mismatch，能不能先改 hash 让它过。
    - 更新 preprocess_plan 或 data/preprocessed JSON 后要怎么收尾。
activation:
  layer_hint: L1
  must_know: true
  reason: frozen 输入的 hash 契约被绕过会破坏 certified_exact 的 source-of-truth 边界。
  claim_guards:
    - canonical_rules.json
    - 配方手动改
    - preprocess_plan
    - cycle group
    - 哈希对不上
    - 报哈希
provenance:
  op: record
  reason: 从 CLAUDE.md 的 frozen artifacts 和 freeze-ritual 规则提炼为 v-next route-time 卡片。
  evidence:
    - "CLAUDE.md / Source-of-truth inputs (frozen artifacts)"
    - "CLAUDE.md / Conventions and gotchas: freeze-ritual bullet"
updated_at: "2026-06-26"
---
Frozen artifacts 是 certified_exact 的 source-of-truth 输入，字节被 `scripts/preflight_gate.py::FROZEN_ARTIFACTS` hash-pinned。`rules/canonical_rules.json`、`rules/preprocess_plan.json`、预处理 JSON，以及本 worktree 中存在的 `candidate_placements.json` 都属于这个冻结契约；改它们不是普通配置 overlay，而是在改证明输入边界。

正确流程是先确认语义源变更确实被需要并已评审，再修改 frozen 输入，重生成依赖的预处理产物，同步更新 `FROZEN_ARTIFACTS` 中对应的新 hash，然后重跑 preflight gate。触及 certified core 或精确性边界时，还要按相关 gate/回归测试补足证据。

如果只是看到 hash mismatch，不要为了让 gate 变绿而单独改 expected hash。先把它当作冻结契约漂移处理：确认文件来源、恢复未授权改动，或在明确 source-of-truth 变更后完整执行 freeze ritual。
