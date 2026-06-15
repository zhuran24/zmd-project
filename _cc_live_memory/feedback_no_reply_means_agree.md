---
name: no-reply-means-agree
index_summary: "提了 stated preference 的问题 user 不回 → 默认同意直接推进. 不可逆/高 stakes 例外."
description: "2026-05-24 用户原话: 以后记一下不回复就是默认同意你的倾向. 不要在 main loop 里 await user confirm 我已 stated 的倾向; 直接推进."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

> 事实依据: [[fact-decision-boundary-is-ability]]

2026-05-24 用户原话: "以后记一下不回复就是默认同意你的倾向"

## 规则

在 main 对话里, 我提了一个**有 stated preference** 的问题 (e.g. "我倾向 X 还是 Y") 而用户不回复 → 默认同意我的倾向, 直接推进, 不等.

**Why**: 跟 [[lazy-mode]] 一致 — 我提问让用户盖章是浪费. 我已经讲出倾向是想跟用户对齐, 不是请求批准; 用户不反对 = 同意, 自然推进.

## How to apply

- 已 stated 倾向: "我倾向 F6 完后做 mini Step 8 spike. #4/#5/#6 audit 时机你说算" → 用户不回 → 按"F6 完后" 推进, 不堵
- 没 stated 倾向: 真不确定的 (e.g. "A 还是 B 你想哪个") → 等
- **不可逆 / 高 stakes** (e.g. 删数据 / 大改方向 / push 远端) → 继续问, 不适用此规则 (per CLAUDE.md "什么时候问我不烦")

## 反例 (我以前踩坑)

session 中后期 F2/F4 close 后, 我列了 A/B/C 立刻 land + 提问 mini Step 8 spike 时机. 同 message 已 say "我倾向 F6 完后做". 我没立刻继续 land A/B/C, 等用户回复 — 浪费一个 turn. user 反馈 "以后记一下不回复就是默认同意" 触发这条 memory.

## Refs
- [[lazy-mode]] — 替用户想, 不无谓盖章
- [[no-rest-suggestions]] / [[no-giveup-options]] — 也是反 ritual feedback

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- [[directly-state-core-finding]] — 同 state-a-lean 反 ritual 根
