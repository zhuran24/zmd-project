---
name: audit-verify-before-archive
description: Audit (Gemini / GPT pro / 别人) 给的 finding 必先 reproduce 每条才 archive/commit/memory. 不能直接 archive 拿 verdict — 那是反向 GO 章 ritual.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-22 用户原话: "部队你还没有检查和确认过他指出的问题的具体情况"
("部队" 是 typo "不对"). round 1 GPT pro audit 我逐 finding reproduce 验,
round 2 我直接 archive + memory + commit, 用户当场指正.

## 现象

GPT pro round 2 audit 给 8 个新 finding (round 1 之外):
- python -O 删 assert / boundary 池 40+14+0 / 同 group 不同 pose / 530 ports
  N/S/E/W 分布 / F2/F3/F4 spec drift line cite / GHOST_AGNOSTIC watcher /
  pytest-randomly conflict

我看完直接:
1. cp response 到 docs/research/.../external_review/
2. write memory project_gpt_pro_p11_audit_not_go.md
3. write memory feedback_adversarial_soundness_audit.md
4. git commit archives

**没** 跑 specific reproduce verify 每条 finding 是不是真. 用户立刻指正.

## 为什么这是错

外部 reviewer (Gemini / GPT pro / 别 chat) 给的 finding 跟 ground truth 之
间永远有 verify gap. 历史: Gemini r29 "5 高光 / 0 finding" 后 r30 audit
推翻 — reviewer 不一定对.

不 verify 直接 archive 等于把 reviewer 的 claim 当 fact 进 long-term
memory. 下次 session 从 memory 拿这条 claim 当依据 → 错的根都不知道.

跟 [[gemini-prompt-audit-mode]] 反 GO 章 ritual 同一精神, 但**反向**:
- GO 章 ritual: reviewer 给 GO, 我不 verify 接受 GO
- 反 GO 章 ritual: reviewer 给 NOT GO + finding, 我不 verify 接受 finding

两者都是 reviewer-driven 不 reproducibility. 都该拒.

## 修法

任何 external audit (Gemini / GPT pro / 别 chat) 给 finding 后:

1. **每条 specific reproduce** — finding 含 file:line / 真数据 key/value /
   代码反例 → 用具体 case 跑 1 遍 verify (~5-15 min/finding)
2. **数字 finding 用 script 验** — e.g. "14/54 pose outside" → 写
   .venv/bin/python 跑 scan 看真 14
3. **行为 finding 用 reproducer 验** — e.g. "validator ok on fake cert" →
   构造同 cert 跑 validator 看 kind
4. **spec drift 用 grep 验** — e.g. "spec line X 写 Y" → grep -n 真在
5. **reproduce 失败 / 数字不 match** → 标 reviewer 误报, archive 时 cite
6. **reproduce 全 pass** → 才 archive + memory + commit

## 时间预算

round 1 + round 2 = 12 finding × ~5 min/finding = ~60 min verify time. 比
直接 archive + 后面 fix 错事再回滚 cheap 多.

## Apply when

任何 external review / cross-check / audit 收到 verdict + finding 后, 在
archive / write memory / commit / propose fix 之前. 不管 verdict 是 GO 还
是 NOT GO 还是 partial.

## 反例

2026-05-22 GPT pro round 2 audit. 我直接 cp + write memory + commit.
用户:"部队你还没有检查和确认过他指出的问题的具体情况". 立刻补 verify, 全
8 条 reproduce 真. 但 verify 之前 archive 是错 order.

## Refs

- [[gemini-prompt-audit-mode]] — 反 GO 章 ritual (reviewer 给 GO 时不轻信)
- [[adversarial-soundness-audit]] — Layer 1 vs Layer 2 audit
- [[external-review-reproducibility]] — GPT 两次跑 finding 不一定一致
- [[gpt-pro-p11-audit-not-go]] — 实际 reproduce 案例
