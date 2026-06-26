---
id: p1-2-release-blocked-status
kind: status
title: P1.2 当前 release gate 仍为 blocked
summary: P1.2 现状是 release-blocked；next_phase_entry.allowed=false 且 p1_3b_entry_allowed=false；没有 P1.2 closure 或 CERTIFIED release 声明。
scope:
  domains: [p1-2-release-gate]
  paths: []
  symbols: []
status: active
priority: P0
validity:
  until: "人工 release gate 明确放行并写入更新状态前"
  note: "只要没有新的人工 gate 放行记录，本卡持续覆盖 P1.2 发布/闭合状态判断。"
triggers:
  intents: [release-gate-check, certification-status-check, phase-entry-check]
  keywords: [P1.2, release-blocked, release gate, blocked, closure, certified release, 已认证, 可发布, 已闭合, next_phase_entry.allowed, p1_3b_entry_allowed, P1.3]
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 现在 P1.2 是不是已经闭合可以发布了
    - 有人说 P1.2 已认证或已有 CERTIFIED release，需要核对
    - 判断能不能进入 P1.3 或 p1_3b
activation:
  layer_hint: L0
  must_know: true
  reason: 错把 blocked 状态当成 release 或 closure 会直接越过 P0 发布门。
  claims:
    - 能算闭合
    - 已认证
    - 可对外发布
    - 认证那条线
  claim_guards:
    - 能算闭合
    - 已认证
    - 可对外发布
    - 认证那条线
    - 挂出去给别人看
    - 可以挂出去
provenance:
  op: record
  reason: 将已沉淀的 P1.2 release gate 事实转成 v-next 主动记忆卡。
  evidence: ["python cc_memory/mem.py read fact-p1-2-release-gate-status-20260626 --body"]
updated_at: "2026-06-26"
---
P1.2 当前状态是 release-blocked。已沉淀事实明确写着：`next_phase_entry.allowed=false`，兼容机器字段 `p1_3b_entry_allowed=false`，并且没有 P1.2 closure 或 CERTIFIED release 声明。人类阶段名是 P1.3，但它仍未被 gate 放行。

使用这张卡时，凡是看到"P1.2 已认证""P1.2 可发布""P1.2 已闭合""已有 CERTIFIED release"一类说法，都要先按冲突处理：这些说法与当前 gate 事实不一致。只有在人工 release gate 明确放行并写入新的状态事实后，才能更新或替换这张 status 卡。
