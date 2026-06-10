---
name: gemini-prompt-audit-mode
description: "Gemini cross-check prompt 模式陷阱 — 验 spec↔src 一致 ≠ audit, 容易降级 GO 章 ritual. src phase 必须把真数据进 DOC_PATHS + armor 强制找 critical bug."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-22 用户原话提醒 + 我自查的真问题:

## 现象

Phase 1 三个 cross-check (r27 P1.1 / r28 framework / r29 4 family) **全 GO**,
r29 还 "0 finding 在本 phase"。对比 Phase 0 spec phase: r14/r18/r21/r24 都 catch
致命 (cap_R vs GHOST_AGNOSTIC 矛盾 / dispatch dead-lock / 48GB OOM 致命 / 3 致命 +
2 schema 漏)。反差太大该警惕。

## 真原因 — 不是 src 没问题, 是 prompt 模式太窄

三个 prompt 共通点:
1. 角度全 "验 spec↔src 一致", **不是** "找 critical bug"
2. DOC_PATHS 全是 spec + src, **没**:
   - rules/canonical_rules.json (真数据)
   - data/preprocessed/mandatory_exact_instances.json
   - data/preprocessed/candidate_placements.json
   → Gemini 不可能 catch spec-data gap (e.g. 我 hardcoded `ports_by_pose` 字段
     根本没在 canonical_rules.json 里, validator 沉默 skip)
3. 任务 B 是 "找 P1.5+/P1.11+ **forward** 盲区", 不是 "找当前 src **backward**
   hidden bug"
4. 完全没用 [[gpt-review-prompt-armor]] armor

模式效果: src 翻译紧贴 spec → surface 一致 → Gemini GO. 真 spec ↔ data / spec ↔
runtime / hidden assumption 的 bug 全没扫到。

## Phase 0 vs Phase 1 prompt 模式分野

- **Phase 0 spec phase**: 验 spec mathematics 本身 (新创造, design 决策).
  Gemini 找 design flaw 容易 — 这是它强项.
- **Phase 1 src phase**: 验 spec → src 翻译. 翻译紧的话 surface 一致 → GO 自然.
  真 bug 在 spec ↔ data / spec ↔ runtime 层. **必须换 prompt 模式才能 catch**.

## 修法 (next round 用)

src phase cross-check 必须:

1. **真数据进 DOC_PATHS**:
   - rules/canonical_rules.json
   - data/preprocessed/*.json (mandatory_exact_instances + candidate_placements
     + generic_io_requirements)
   - canonical_rules 的源 schema 文件
2. **任务直接问 spec-data gap**: "src 跟真数据 (canonical_rules.json) 接合时
   哪步先 crash / FN / FP? 列具体 file:line + 假设字段名 vs 实际 schema."
3. **Armor strict mode** (借 [[gpt-review-prompt-armor]] / [[gpt-review-no-history]]):
   - GO verdict 必须先列 3 种最可能死法 + 反驳每一种
   - 不准 "looks fine / 完美 / 完全一致 / 绝佳" 等 vague hyperbole
   - critical claim 必须 cite literature 或 code file:line
   - 找不到 critical 也必须列 3 个 high-risk hypothesis
4. **明确反 "GO 章 ritual"**: 在 prompt 里直接说 "不要给 GO 章 — GO 章本身
   是 ritual, 我要 audit. 找 1 critical 比 100 surface comment 价值高 10×."

## Why 重要 — 这是 RLHF bias 应用反例

Gemini 默认温和倾向夸 (跟 [[gemini-better-at-natural-tone]] 一致 — Gemini 自然
口吻好, 但反面是 RLHF bias 倾向 positive verdict). prompt 不 push hard → 自然
GO. 用户原话: "Gemini 是用来找问题的, 不要被他夸傻了".

这条比 [[gemini-review-algorithm-math]] (验数学层 must Gemini) 更深一层: 不仅
**要** Gemini 验, 还要**怎么**验 — prompt 模式决定 audit 还是 ritual.

## Apply when

任何 src 阶段 cross-check (Phase 1.2+ / Phase 1.3+ / Phase 1.4 ramp 前) 之前
重写 prompt 模式. 不重写就**别调** — 浪费 token 拿一个 GO 章.

## Refs

- [[gemini-review-algorithm-math]] — 算法层必 cross-check, 但**不指定**怎么验
- [[gpt-review-prompt-armor]] — GPT review armor 通用 — 死路黑名单 / 必须形式化
  证明 / cite literature
- [[gpt-review-no-history]] — 新窗口 0 history 跟 prompt 模式独立
- 反例 commits: 0b7b29e (r27) + 2d275f8 (r28) + a4e9279 (r29) 三 prompt 全 GO
  章模式
