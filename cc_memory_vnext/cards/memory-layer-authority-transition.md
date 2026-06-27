---
id: memory-layer-authority-transition
kind: open_obligation
title: 旧 cc_memory 是否整库冻只读=未解(按条 legacy vs 整库迁移,三处文档口径冲突)
summary: 记忆三层并存:旧 cc_memory(仍现役、还在被写)/ v-next cards / harness。"冻只读·绝不双活"是【按条】(某条做成卡后别再更新它旧库副本),不是整库冻。整库迁移成只读=未做的 V2 里程碑,且 MASTER_PLAN(上线即冻)vs council_B(迁移延后无表)vs CLAUDE.md(cc_memory=authoritative 活)三处口径冲突未解。问"旧库能不能写/是不是只读"时按此回答,别拍"已冻"。
scope:
  domains: [memory-layer-authority, cc-memory-freeze]
  paths: []
  symbols: []
status: active
priority: P1
validity:
  until: "三处文档(MASTER_PLAN/council_B/CLAUDE.md)口径对齐 + 整库迁移真相源的决策做出之前,本义务持续 open"
  invalidated_by: "owner/项目对'旧 cc_memory 何时整库冻只读'做出最终裁决并统一三处文档"
triggers:
  intents: [memory-layer-authority, cc-memory-write-allowed, freeze-status]
  keywords: [冻只读, 整库只读, 旧 cc_memory 能不能写, 旧库还能写吗, 旧的不是只读, authoritative, 双活, 迁移真相源, 三层并存, cc_memory 冻]
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 旧 cc_memory 不是冻只读了吗,为什么还往里写
    - v-next 上线后旧库是整库只读、还是还能写
    - 这条要写旧 cc_memory 还是 v-next 卡
activation:
  layer_hint: L0
  must_know: true
  arming: [冻只读, 整库只读, 旧 cc_memory 能不能写, 旧库还能写, 旧的不是只读, 双活, 迁移真相源, cc_memory 冻]
  reason: 误以为旧库已整库冻只读会写错地方/答错状态;实际是未解的过渡态。
provenance:
  op: record
  reason: owner 2026-06-27 当场问"旧的不是只读吗为什么还往里写",暴露这是未解过渡态;codex 判官也标为 open_obligation 缺口。
  evidence:
    - "cc_memory_vnext/HISTORY.md §4 (三处口径矛盾详述)"
    - "本会话 owner 提问:旧 cc_memory 不是只读吗,为何还更新"
updated_at: "2026-06-27"
---
当前记忆是**三层并存**:① 旧 `cc_memory`(SQLite,~108 条,**仍是现役主力、还在被写**,本会话+分支线程都写过);② v-next `cards/`(主动注入层,18 卡);③ harness `*.md`(跨项目 route-time 规则)。

**"冻只读 / 绝不双活"的准确含义是【按条】**:某条知识一旦做成 v-next 卡,就别再去更新它在旧 cc_memory 里的那份副本(防两份漂移)——**不是整个旧库都冻了**。旧库对所有还没迁成卡的知识、项目状态记忆,仍是活的写入处。

**整库把真相源迁成只读 = 未做的 V2 里程碑**,且上游有个**未解矛盾**:`MASTER_PLAN` 写"上线即冻只读"、`council_B` 写"memory.db 当 legacy、迁移延后无时间表"、`CLAUDE.md` 仍称 cc_memory 为 "authoritative collaboration memory(活)"。三处没对齐前,这条 open obligation 持续有效。

**使用**:有人问"旧 cc_memory 是不是只读了/还能不能写/这条写哪",别拍"已冻"——按上面答(按条 legacy、整库仍现役、迁移待裁决),详见 `HISTORY.md §4`。
