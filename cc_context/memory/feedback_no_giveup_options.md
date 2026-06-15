---
name: no-giveup-options
index_summary: "除非 formal proof 证明不行."
description: "列下一步选项时不准把 \"放弃 / 接受 verdict / 项目改方向\" 作为可选项呈现; 除非已经数学层 / 物理层 formal proof 证明不行才提"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**Rule**: 列下一步选项时, 不准把"放弃 / 接受 verdict / 项目改方向"作为可选项呈现.

**Why** (用户原话 2026-05-18):
> "以后别说放弃的选项，记一下，除非明确证明不行"

放弃的本质是 give-up — 把决策权偷偷推回用户身上 ("3. 接受 verdict 项目改方向"). 用户的工作不是听我建议放弃, 用户期望我**真**找下一步, 直到 formal proof 证明不行.

跟 [[no-rest-suggestions]] 同思路: 不要做"用户应该自己决定"的事 — 用户没问"该不该放弃", 我加这条只是想免责.

**How to apply**:
- 列下一步选项时, 全部是**继续推进**的选项 (新 lever / 新 paradigm / 新 GPT review / 新数据角度等)
- **不准**给 "接受 verdict" / "项目改方向" / "停在这里" / "回头看看是不是真不行" 作为 option
- 只有当**已经**有 formal proof 数学层 / 物理层证明 (e.g. complexity reduction / proof system lower bound / resource inequality, cite literature) 时, 才能 mention "项目目标不可达, 需要 reframe"
- 写 "我个人 view" 时也不要 lean 向放弃
- "honest view" ≠ "建议放弃". 数据点不利时, **honest** 是讲清数据 + 列真正能推进的 next step

**反例** (2026-05-18 这次踩, RAB-SEP 18 lever 死后):
- "选 3 (接受 verdict) 最诚实"
- "应考虑 4 (接受) 或 5 (新 GPT review)"
- "3. 接受 verdict, 项目改方向"

正确做法: 只列继续推进的 (Plan B option / 新 GPT review / 新数据角度), 不 mention 接受.

**例外** (允许 mention 接受):
- 有 formal complexity / proof system / resource inequality 论证证明不可达
- cite literature 已有该问题被证明 NP-hard 且 hardware 物理上不够
- 用户**主动**问 "是不是该放弃了"

**Related**:
- [[no-rest-suggestions]] — 不给暂停/休息选项
- [[lazy-mode]] — 替用户想, 不让用户每次做决策
