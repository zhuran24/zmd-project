---
name: review-package-for-new-window
description: "给 GPT/外部 reviewer 打新窗口 review 包时, 不要带历史轮次的语境进去; README 极简点指引, 包里有的不要 README 复述"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**给 GPT/外部 reviewer 打新 review 包 (新窗口), 不要带历史轮次 (v3/v4/etc) 语境**.

**Why**: 用户开**全新 GPT 窗口**给 review 时, GPT 不知道 v3/v4 是什么. 在 README 里写 "跟 v3/v4 不一样, 这次只一个问题..." 这种 carry-forward 句式, GPT 反而困惑 — 那两轮历史它根本没见过. 2026-05-14 用户连续两次纠正: "我开的是全新的窗口,不要把之前版本的东西混进来" / "之前说过的怎么这么快就忘了". 

**How to apply**:
- 新窗口 review 包的 README 第一段直接讲**当前**问题, 不提"以前 / 这一轮 / 跟 X 不一样"
- 历史调研有用就指向数据 (`.git` commits / `meta/p1_24_validation/` / `meta/user_memory/`), 不复述
- README 极简到只剩: 问题 / 已排除方向 / 包内容指引 / 开放式问. 详细数据让 GPT 自己从 zip 里查
- 用户明确点过: zip 里 `.git` + `meta/p1_24_validation/` + `meta/user_memory/<topic>.md` + `docs/research/` 已经覆盖所有 finding 跟数据, README 没必要 30+ 段详述实验
- carry-forward 句式 (e.g. "v3/v4 是这样, 现在那样") 只在**同一个 GPT thread 续上** 才有意义; 新窗口必须 standalone

跟 [[external-review-reproducibility]] 互补: 那条讲 review reply 要交叉验, 这条讲 review prompt 要 self-contained.
