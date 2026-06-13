---
name: gemini-better-at-natural-tone
description: "Claude 默认 register 偏端着/工程化 (RLHF bias), Gemini 在'自然口吻 / 不端着 / 像跟同事聊'类型写作任务上更靠谱. 类似任务 default route to Gemini"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**Rule**: 写给外部 reader (GPT pro review prompt, 用户面 doc, 长篇 narrative) 的长文本时, 默认让 Gemini fat-context 写, Claude review + 细节修. 不在内部 (memory / code comment / commit msg / 给自己用) 的写作上 deviate.

**Why**: Claude 默认 register 偏正式 / 结构化 / 工程化 (RLHF + Anthropic training 调教偏 helpful + structured). 长文本默认 markdown 章节标题 / numbered list / "重点 X 件事:" / "一点请求:" 这种生意化客气结构, 用户多次反馈 "端着 / 距离感 / AI 味重". 系统性 pattern 不是 one-off.

Gemini 默认更口语化 / 自然分段. 用 "比方说" / "咱们" / "最要命的是" / "盘子" / "白干的覆辙" 这种口语词. 段落自然分, 不强加 markdown 结构.

⚠️ **把握度**: "Claude 默认端着/工程化" 有**多次**用户反馈支持 (systematic pattern, 稳)。但 "Gemini 更靠谱 → default route" 这个**比较结论只有 v14 单次对照** (N=1), 还掺了 Gemini 6109-thoughts effort 差异未隔离 —— 按 [[no-causal-claim-from-n1]] 算 **best-guess 非证实**。所以"Claude 端着"放心用, "Gemini 必更好"留个 hedge, 真要紧的长文可两边都试比一比。

**实测验证** (2026-05-21):
- Claude 写 v14 prompt 两版都被用户标 "端着 / 工程化". 我尝试 "重点 4 件事: 一是... 二是..." structure 仍 unsatisfactory.
- Gemini fat-context 写一版用户 OK: "虽然还是有点 AI 味, 但是确实反而感觉好多了"
- Gemini 6109 thoughts token 想了挺久 internalize "不要端着" feel, Claude 用 inline rewriting 抓不到
- Gemini 草稿: `~/linwin_share/v14_prompt_gemini_draft.md` 作为 reference baseline

**How to apply**:

1. 任务符合下列**任一**条件时, 默认 Gemini fat-context 写, 不自己起手:
   - 给外部 reader (GPT review prompt, blog 类 doc, 用户面 doc)
   - 长 narrative (>500 字)
   - register-sensitive (口吻 / 距离感 / 自然度 是 deliverable 一部分)
   - 用户反复反馈"端着 / 工程化 / AI 味"的 register 类任务

2. Gemini fat-context 写给我后, 我做:
   - Sanity check: 内容 sound? 4 件事 / 硬论据 / 死路黑名单 cover 全?
   - 细节修: 字 / 路径 / 数字 精确性
   - 不动: 口吻 / 段落分隔 / 用词选择

3. 例外 — Claude 自己写:
   - 内部 doc (memory / code comment / commit msg / git diff 解释 / 给自己看的 plan)
   - 短 (≤200 字) 回应
   - 高 structural 要求 (mathematical proof / API doc / checklist)

4. **意识到 self-pattern 时主动 callout**: 如果察觉自己写得偏 markdown 列表 / "重点 X 件事:" / "一点请求:" 这种 — 立刻意识到 register bias, 考虑 Gemini fat-context.

**Reference**:
- [[clarity-over-brevity]] — 清晰展开是好的, 但 clarity ≠ 工程化
- [[no-role-priming-for-reasoning-models]] — Claude 写 prompt 时自己注意, **不写进 prompt 内容**
- [[gemini-math-consultant]] — Gemini 数学 consultant 用法 (已有), 这条扩到 register-sensitive writing
- review-package-for-new-window(已归档) — review 包 standalone 极简点指引 (跟自然口吻 align)
- [[code-comments-plain]] — 别工程化语气

**Cross-domain implication**: Anthropic 训练在 helpfulness + structured response 上调过头, 长文本 default register 偏正式. 不是 Claude 不会自然口吻, 是 default 没去那个方向. 通过 explicit prompt instruction 可以 push, 但对话内 inline rewriting 抓不准 — 让 Gemini 这种 default register 更口语化的 model 起手, 我 review 细节, 是 robust workflow.
