---
name: gpt-review-no-history
description: "GPT review 每次都新开窗口零历史 memory; prompt + 包里**不准引用 GPT 上次给的内容** (e.g. \"参考 v11 计划书\", \"跟 L14 一样\"); 要 reference 必须把那东西完整打包进 zip 或在 prompt 里展开"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

每次给 GPT (5.5 Pro / 类似) 发 review 包都是**新窗口新 session**, GPT 完全没
有上次给我们的任何输出的记忆.

**Why**:
- 用户 quote 原话 "里面有提到上次他给出的内容, 但是你要知道的是每次都是新
  开一个窗口的, 完全没有上次的任何记忆"
- 实际场景: b1_phase6_review_prompt_v1.md 里写了 "跟之前 GPT v11 lazy
  power completion 计划书同等深度" — GPT 新窗口没看过 v11, 这指令空气
- 这种引用对新窗口 GPT 完全无意义, 反而 confusing

**How to apply**:
- 写给 GPT 的 prompt + review 包内文档时, **完全去除**对历史 GPT 输出的引用:
  - 不准 "参考 v11 计划书"
  - 不准 "跟 L14 同类"
  - 不准 "之前 GPT 给的方向"
- 如果某历史 GPT 输出确实关键 (e.g. v11 计划书有可参考 format), **两个办法**:
  1. **打包进 zip** — cp 那个 .md 文件进 review 包, prompt 里 reference 文件路径
  2. **展开 inline** — 在 prompt / 包内文档里把所需内容**直接重新写一遍**
- 包内**实测数据**引用 GPT 名字 OK (e.g. "L14 verdict: GPT 给的方向死路" 这是
  事实, 不是要 GPT 回忆它)
- 区分: "GPT 输出过 X" (历史事实, OK 写) vs "参考 GPT 上次给的 X" (要 GPT
  回忆, 不 OK)

**适用场景** (容易踩):
- 写 "跟你之前 v11 计划书相同 format / 深度"
- 写 "用 GPT v8 anchor slicing 同方法"
- 写 "复用 L16 思路"

**反例 (今天 5-18 犯过)**:
- prompt 里写 "参考你之前 GPT v11 lazy power completion 计划书" — GPT 新窗口
  完全不知 v11 是啥. 用户立刻指出. 修法: 把 v11 计划书 cp 进 zip, 或在 prompt
  里 inline 描述 "希望 format: Phase 0/1/.../N + 每 phase 含 implementation
  detail + verdict 标准 + 风险点", 不依赖 GPT 回忆.

**Related**:
- [[gpt-review-prompt-armor]] — 三段式 armor 框架
- [[external-review-reproducibility]] — 多次 review 交叉验信
