---
name: big-milestone-gpt-pro-review
description: 大节点结束打包交 GPT pro 审查. Gemini per-commit fast feedback ≠ GPT pro batch 整 phase 找 architectural/paradigm 层问题. v14 review 模式延续到 Phase 1+.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-22 用户原话: "记一下大节点结束之后打包交给 GPT pro 审查一下".

## 规则

**大节点 = Phase 完成 / Phase ramp 关键点 / paradigm shift**:
- Phase 1.0 framework 完成 ✓ (已过 — 当时没打包, 下次类似时机补)
- Phase 1.1 整 4 family + 真数据接合 (P2 完成后) — **下个打包节点候选**
- Phase 1.2 5 family 完成
- Phase 1.3 integration smoke (P1.20)
- Phase 1.4 ramp 80/160/266 inst 节点
- 任何 paradigm shift (e.g. F1 数学从 per-side 改 union)

**大节点 ≠ per commit / 单 family / 单 module**. Gemini round 已 cover 细节层
(per-commit fast feedback, 算法/schema 一致性).

## 行动

整 phase deliverable 打包送 GPT pro window 审查 (zip 含):
- 全部 commit diff (git format-patch)
- 真数据 sample + spec 全文
- 所有 Gemini cross-check archive (rounds, with verdict + finding)
- 当前 task list + 已知 outstanding gap
- PHASE_x_PLAN.md + PROJECT_LOCK.md 现状

**完整打包操作规范见 hub [[index-packaging-cluster]]** —— prompt [[external-review-prompt-template]] + [[gpt-review-prompt-armor]], 包内容 [[review-pkg-no-prompt-inside]] + [[review-pkg-data-completeness]], 压缩 [[review-pkg-7z-strategy]]。注意 [[external-review-reproducibility]] — GPT 两次跑 finding 列表不一定一致, 立刻 cp sandbox 链接。

## 跟 Gemini 区别 (为啥需要 batch GPT pro)

| 维度 | Gemini per-commit | GPT pro 大节点 batch |
|---|---|---|
| 频次 | 每 commit / per-task | 整 phase 完成 |
| context | 单 spec + src snippet | 全 phase deliverable + 历史 |
| 找 | schema 一致性 / spec-data gap | architectural / paradigm 层 / cross-module invariant |
| 速度 | 30-70s | hours (人工 GPT pro window) |
| 成本 | API token | 用户的 GPT pro 额度 |
| **作用** | 防 cascade bug | 防 architectural 死路 (类 v14 找 4 必修) |

## 历史 reference

- [[v14-review-findings]] — GPT pro 整 B Design 框架审 → B GO + 4 必修
- [[gpt-v13-cut-language-thesis]] — GPT cut language 升级
- [[gpt-anchor-slicing-proposal]] — GPT v5 anchor slicing 方案
- [[external-review-reproducibility]] — GPT 同 prompt 两次跑 finding 不同
- [[gpt-review-prompt-armor]] — prompt 加 armor (死路 / 必须证明)
- [[gpt-review-no-history]] — 新窗口 0 history

## Apply when

任何 phase / 大子系统 完成时主动提醒用户 "建议打包交 GPT pro 整 phase 审查".
不该每次都问, 只在自然完成 milestone 时.

下个 trigger: Phase 1.1 Gap 6-10 全 fix + F1 真数据 production-exercised 后.
