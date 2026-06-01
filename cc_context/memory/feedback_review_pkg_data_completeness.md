---
name: review-pkg-data-completeness
description: "External review 打包原则: 数据完整性 default. spike-only code / Gemini archive / reproducer / telemetry raw 等 factual evidence 全入包 (作 code_context/ review-only mirror 子目录形式), 不 preempt 删. 之前 PR #1 verdict-only style 'reviewer 会 anchor 在 throw-away spike code' 担心 trade-off 错估. 跟 [[review-pkg-no-prompt-inside]] 互补 (那是禁主动性 priming, 这是要 factual 完整)."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8ce2a10d-50a6-4d5c-82bf-3c4414cb623f
---

## 规则

External review 打包原则: **数据完整性 default**. 包内**应包含** reviewer
源码级复核所需的全部 factual 材料, 即使某些代码是 throw-away spike / 子代
理 cross-check transcript / N=8 parallel design intermediate. **不 preempt
删** — reviewer 该自行判断要不要看, 不该 main 替他决定.

**Why**: 之前 PR #1 verdict-only style "spike-only code 故意不入包, 防 GPT
reviewer anchor 在 throw-away spike code 设计细节上" trade-off 错估:

- 担心 vs 实际: GPT pro 是经验 reviewer, 不会 anchor 在 toy translator
  设计细节. Reviewer 自己有判断能力, 看 code 跟做 verdict 不是同件事.
- 代价 vs 收益: 删 spike code 节省的 packaging effort < reviewer evidence
  gap 产生的 "不能源码级复核" finding 代价. Multi-round audit 时 evidence
  gap 累积 round.
- 反面 user 偏好: user 偏好 "F3 做完再让 gpt 审查, 直到没问题了再进入"
  — 多一轮 evidence-gap audit 是浪费, 不如 default 完整入包 cover.

跟 [[review-pkg-no-prompt-inside]] 互补: 那条禁**主动性 priming** (verdict
claim / "已闭环" / 审查指引), 本条要**factual 完整**. 两者不冲突 — README
写"含 X/Y/Z 文件" 是 factual ✓; 写"已 close 5 finding, 期望 reviewer
verify" 是 priming ✗.

## How to apply

包内应**含** factual evidence categories (default 入, 不 preempt 删):

1. **Spike / throw-away implementation code**: 作 `code_context/<phase>/`
   review-only mirror 子目录入包, **不入 master 路径** (forbidden_path_check
   仍 0 leak), 标注清楚是 review snapshot. 含 SHA256SUMS manifest 保
   integrity.
2. **Gemini / 子代理 cross-check archive**: prompt + raw response transcript
   全入 `docs/research/<phase>_<family>_gemini_round{N}_<date>/`. 不只 commit
   log claim, reviewer 该能读原始 transcript 判 cross-check 是真 catch 还
   是 ritual.
3. **Reproducer scripts**: 全入包 + 入口可跑 (per [[review-pkg-no-prompt-inside]]
   factual category 已 covered).
4. **Telemetry raw events + aggregate summaries**: 两者都入. Raw 让
   reviewer cross-validate aggregate (e.g. raw `rss_sample_after_solve`
   event vs `phase_b_results.json` snapshot 数字一致性).
5. **跨 branch overlay**: spike branch / experimental branch 工作时, 关
   键源码 + data overlay 进包 (从 git show 取). 标注 branch HEAD.
6. **External audit history**: 历次 GPT pro / Gemini cross-check audit
   report + patches 全入 `docs/research/<phase>_<audit_id>/`. 多 round
   audit 时 reviewer 能看到 previous finding + 我们怎么 fix 的.

包内**仍禁** (per [[review-pkg-no-prompt-inside]] 不变):

- PROMPT.md / audit prompt / "审查指引" — chat 单独给, 不入包
- 任何"主动性内容" verdict claim:
  - "已修 / 已 close / 通过 spike 验证 / 已 land" 等结论 framing
  - "请整 phase audit X / 期望反馈 Y" priming
  - "verify reproducibility cite file:line" 主动给"信"锚点
  - "Close: N P0 + M 必修" 这种 priming 分类

**判别**: factual evidence (data/src/spec/diff/archive) vs verdict-priming
(结论/期望/指引). 同样一段 README 文本:

- ✓ Factual: "5 commit 落地 + 包含 X/Y/Z 文件" / "实测 pytest 414 pass"
- ✗ Priming: "5 commit 修复了 X, 期望 reviewer verify 已 close"

## Anti-patterns (历史踩过, 全 catch by GPT pro audit)

- "PR #1 verdict-only style 不入 spike code" (2026-05-25 → 5-26 v14-v17
  设计) → v17 四审 Reviewer B F1 catch telemetry call site + A3 driver
  evidence gap → v18 修 (加 `code_context/spike/` mirror)
- "Gemini archive 只 commit log claim 不入 archive" → v17 四审 Reviewer
  A M3 catch evidence packaging gap → v18 修 (加
  `docs/research/p1_2b_f3_gemini_round{1,2}/`)
- "Telemetry aggregate 入包, raw event 不入" → v15 三审 reviewer catch
  1.03GB 复核不到 → v16/v17 修 (加 telemetry_*.jsonl overlay +
  `emit_rss_after_solve` event)

3 次踩坑都是同种 root cause: main 怕"reviewer anchor 在 trivial 上"过度
preempt 删 evidence. Reviewer 实际是经验丰富专家, 不需要 main 替他选看
什么.

## 跟 review pkg packaging 决策的 shorthand

每次 build review pkg, 决定某 file 入不入包时, 自问:

1. 是 factual evidence (data/code/spec/transcript/diff) 吗? → **入**
2. 是 verdict-priming (结论/期望/指引) 吗? → **不入**
3. 不确定? → **入** (default 数据完整, reviewer 自判)

不该自问 "reviewer 会不会 anchor 在这上面?" — 那是 reviewer 的判断不是
你的.

## plan docs carve-out (2026-06-01, v22 起)

`docs/项目说明/` (21 篇, 含 phase plan) 之前被 [[review-pkg-7z-strategy]] 列为 EXCLUDE (主动性内容), v22 起**翻转为默认入包**: 它们是 reviewer 背景 context, 讲 spike 之后的工作 (= 非被审对象), priming 风险低。这是化解「排除 plan doc」(见 [[plan-doc-strategic-layers]]) vs 本条「数据完整性 default」张力的**有意 carve-out** —— 判别仍按 factual-vs-priming, 不是无脑全入。

## Refs

- [[review-pkg-no-prompt-inside]] — 禁 prompt + 禁主动性 priming, 互补
  (一个说不放什么, 一个说要放什么)
- [[review-pkg-7z-strategy]] — 7z 压缩 mechanical 跟内容选择正交
- [[external-review-reproducibility]] — 同 prompt 两次结果不一致, 数据
  完整性帮 reviewer 自查
- [[adversarial-soundness-audit]] — Reviewer 5 验 (cert sound / ↔literals
  / ↔真数据 / ↔state / ↔不变量) 需要 factual evidence 复核
- [[review-package-for-new-window]] — 包不带 carry-forward / history ref
  (跟数据完整性不冲突 — factual evidence 入, 历史 narrative 不入)
- [[gpt-error-types-taxonomy]] — 区分 3 类 GPT 错估; reviewer 看 factual
  evidence 自己判错估在哪
