---
id: forbidden-staged-paths
kind: constraint
title: 禁止提交生成的 proof/blueprint 产物
summary: data/checkpoints/、optimal_blueprint.json、final_solution.json、certified_delivery_manifest.json 是生成产物，进入 staged set 会被 preflight hard block。
scope:
  domains: [git-staging, forbidden-paths]
  paths: [data/checkpoints/, data/blueprints/optimal_blueprint.json, data/solutions/final_solution.json, data/solutions/certified_delivery_manifest.json]
  symbols: []
status: active
priority: P0
severity: high
triggers:
  intents: [git-staging, commit-preflight, proof-artifact-handling]
  keywords: [staged, git add, preflight, 禁止路径, 生成产物, proof, blueprint, checkpoint, certified_delivery_manifest]
  negative_keywords: []
  paths: [data/checkpoints/, data/blueprints/optimal_blueprint.json, data/solutions/final_solution.json, data/solutions/certified_delivery_manifest.json]
  symbols: []
  error_regex: []
  examples:
    - 准备提交前发现 data/checkpoints 里有新文件要不要一起 git add
    - preflight 报禁止提交 optimal_blueprint.json 或 final_solution.json
    - 打包认证结果时想把 certified_delivery_manifest.json 放进这次 commit
activation:
  layer_hint: L1
  must_know: true
  claim_guards: [跑出来的蓝图, 最终方案, 跑出来的检查点, 交付清单, 暂存区]
  reason: 这些生成产物一旦被提交会破坏证明/交付边界并被 preflight 硬拦截。
provenance:
  op: record
  reason: 从 CLAUDE.md 的 Forbidden staged paths 约定和 preflight_gate.py 的强制检查提炼。
  evidence: ["CLAUDE.md:238-249 Conventions and gotchas / Forbidden staged paths", "scripts/preflight_gate.py:57-62 FORBIDDEN_STAGED_PATHS", "scripts/preflight_gate.py:279-297 check_forbidden_paths", "scripts/preflight_gate.py:99-121 GateResult.block exit_code"]
updated_at: "2026-06-26"
---
`data/checkpoints/`、`data/blueprints/optimal_blueprint.json`、`data/solutions/final_solution.json`、`data/solutions/certified_delivery_manifest.json` 是运行/认证/蓝图交付过程中生成的 proof 或 blueprint 产物，不是要进入 git 历史的源文件。它们可以作为本地输出、检查材料或外部交付包的一部分存在，但绝不能被加入 staged set。

`preflight_gate.py` 明确维护 `FORBIDDEN_STAGED_PATHS`，并在 `check_forbidden_paths()` 中扫描 staged/CI 变更范围；命中后调用 `gate.block(...)`，最终以非零退出码 hard block。也就是说，这不是风格建议，而是提交门禁：只要这些路径被 staged，preflight 就应失败。

使用时，在提交前先看 `git status --short` 和 staged diff；如果这些路径已经被加入索引，应从 staged set 移除，而不是修改 preflight 规则来放行。若确实需要交付这些产物，走项目允许的发布/打包流程，把说明、commit、hash 和验证信息放在 manifest 或消息里，不把这些生成文件直接提交进仓库。
