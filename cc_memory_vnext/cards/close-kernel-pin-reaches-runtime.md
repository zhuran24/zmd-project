---
id: close-kernel-pin-reaches-runtime
kind: constraint
severity: high
title: close-kernel 钉死要到 runtime 消费点 + 改动让文件成信任锚就必须钉
summary: 两条 soundness 工程判据(PR2 反复出现，GPT Pro 外审挖出我+codex 都漏的）：① pin 必须钉在真正被执行/信任的 runtime 消费点，不能只钉 gate（gate↔runtime 间"读但不再核"=TOCTOU 时序旁路）；② 改动让某文件成为信任锚就必须进源码 sha 楼面（"现状没钉"≠"不用钉"）。
scope:
  domains:
    - certified-exact
    - close-kernel
    - soundness
  paths:
    - scripts/check_p1_2_proof_obligations.py
    - src/search/pr2_l0_micro_verifier_core.py
    - src/search/certified_artifact_contract.py
  symbols:
    - _load_canonical_dependency_floor_manifest
    - CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH
status: active
priority: P1
triggers:
  intents:
    - seal
    - pin
    - reseal
    - soundness
    - close-kernel
  keywords:
    - 钉死
    - pin
    - reseal
    - 重封
    - close-kernel
    - 信任锚
    - runtime
    - gate
    - 时序
    - TOCTOU
    - 旁路
    - source_sha256
    - sha 楼面
    - floor
    - manifest
    - 源码楼面
    - provenance
    - 绕过
    - 绕过分支
    - 缺口
    - 缺口闭合
    - autogen
    - auto-generate
    - 没钉
    - 不用 reseal
    - 钉它
  negative_keywords: []
  paths:
    - scripts/check_p1_2_proof_obligations.py
    - src/search/pr2_l0_micro_verifier_core.py
  symbols: []
  error_regex: []
  examples:
    - 这文件没在 sha 楼面里，改它不用 reseal 吧
    - checker 已经钉了 manifest 字节，#9a 闭合了对吧
    - 把 floor 钉进 gate 就堵住 provenance 漂移了
activation:
  layer_hint: L1
  must_know: true
  claim_guards:
    - 不用 reseal
    - 不需要 reseal
    - 不用钉
    - 缺口闭合
    - 闭合了对吧
  reason: PR2 余项会复发这两类漏（gate 钉了 runtime 没钉 / 改动让文件成信任锚却没钉源码 sha 楼面），我和 codex 本地审都漏过、靠 GPT Pro 外审才抓到。这两条 mis-claim（"不用 reseal" / "缺口闭合了对吧"）是危险断言，claim_guard 命中即强推纠正。
provenance:
  op: record
  reason: GPT Pro 多会话外审挖出 #8-B（certified_artifact_contract 成信任锚却没钉）+ #9a-A（checker 钉了 manifest 但 runtime loader 没消费=时序旁路），两条我亲自判错/漏判。
  evidence:
    - python cc_memory/mem.py read pr2-8-9a-hardened-landed-099f5a3 --body
updated_at: "2026-06-29"
---
做 close-kernel / 认证核心的 seal/pin/reseal 时，过这两条判据（PR2 反复栽在这）：

**① 「现状没 sha-pin」≠「不需要 reseal / 不用钉」。** 改动一旦把某文件**提升为信任锚**（典型：删掉一个绕过分支、让某函数成为唯一验证权威），该文件**就必须**进 `CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH` 源码 sha 楼面钉死——否则有人能改回 `return None` 之类旁路、而 gate 只查文件存在、不查内容 hash、不响。**别把"它现在不在楼面里"当成"它不用钉"；问的是"这改动让它在信任链里扮什么角色，该不该钉"。**(实证：#8-B，我亲自判 certified_artifact_contract.py"不需 reseal"判错。)

**② gate 钉了 ≠ runtime 钉了——pin 必须钉在【真正被执行/被信任的 runtime 消费点】。** 把字节/sha 钉进 checker（gate）只保证"单独跑 checker 时抓漂移"；但**真正 mint/seal 的 runtime loader 若不消费同一个 pin**（读但不再核、或缺失就 auto-generate），gate 过后到 mint 之间就有**替换/再生成窗口** = TOCTOU/时序旁路，能让未审字节进认证相位。判据：**gate 与 runtime 之间任何"读但不再核"的窗口都要堵；钉死要落到 runtime 消费点 + fail-closed + 禁 runtime auto-generate。**(实证：#9a-A，checker 钉了 manifest 字节但 L0 runtime loader 没消费、缺失还自动生成 floor。)

这俩是 PR2 "gate-time vs runtime" 反复出现的根；详 cc_memory `pr2-8-9a-hardened-landed-099f5a3`。
