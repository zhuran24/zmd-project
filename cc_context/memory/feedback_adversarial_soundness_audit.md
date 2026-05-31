---
name: adversarial-soundness-audit
description: "Validator audit 必须 adversarial — 不只验 happy path 跟数据接合, 必问 '假 cert 能 pass 吗'. Gemini audit mode 漏 4 critical, GPT pro catch."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-22 lesson: GPT pro 两次 Phase 1.1 audit verdict NOT GO 后总结.

## 现象

我之前 Phase 1.1 走了:
- Gemini r27/28/29 (spec↔src 一致性 mode) — 全 GO, 漏 critical
- Gemini r30/31/32 (audit mode + 真数据 + armor) — catch 15 个 critical/gap
- 但 GPT pro audit 仍 catch **4 个新 critical** Gemini 全漏

Gemini 漏的:
1. F1 demand_R 跟真 pose_domain 接合 sound 性 (我 prompt 给 aggregate 数据,
   GPT 跑全 pose pool 扫描出 14/54 outside)
2. F3 validator cert ↔ literal 绑定一致性
3. F2 validator A∪B 覆盖 graph universe
4. F4 validator commodity_id 真存在 production data

## 共同根因: audit 模式分两层, Gemini 只 cover 第一层

### Layer 1: spec ↔ src ↔ data 接合 (happy path)
- src 跟 spec schema 一致吗?
- src 跟真数据 schema 一致吗 (字段名 / 类型 / 数据真值)?
- 数据进 src 不 crash, 出现期望输出?

**这层 Gemini audit mode 有效**. 真数据进 DOC_PATHS + armor + 强制 cite
file:line — r30/31/32 这层 catch 15 个.

### Layer 2: adversarial — 假 cert 能 pass validator 吗?
- 构造一个 fake cert (字段语法合法, 但 cert 的 claim 跟真证明对象不一致)
- validator 通过吗?
- 通过 → cut 假证, 误剪合法状态

**这层 Gemini audit mode 漏**. GPT pro 强 — 历史 v14 review 也是这种 falsify
风格. 因为:
1. Gemini RLHF 倾向"找 spec/data 对不上的地方"
2. GPT pro 倾向"构造反例 falsify each soundness claim"
3. 两者训练 doctrine 不同

## 2026-05-25 Phase 1.2 reinforcement case (强化, 不只 Phase 1.1)

Phase 1.2 走了:
- 20 round Gemini per-commit cross-check (7 family, F8 最严 5 round 12 finding,
  F5 3 round 10 finding, F6 3 round 7 finding, F2/F4 3 round 3 finding, F7 2 round
  5 finding, F9 4 round)
- 全 Gemini GO + mini Step 8 spike GO → 标"Phase 1.2 ALL CLOSED"
- 但包 `cb8e347` 送 GPT pro 后 catch **2 BLOCKER + 1 HIGH**, **全是 Layer 2
  adversarial pattern**, Gemini 20 round 0 catch:

5. **F7 power_hitting_set** (BLOCKER): validator 不验 `facility_cells ↔
   candidate_placements[facility_pose_id].occupied_cells`. 真 pose 在 (0,0),
   cert 写 (30,30), validator `ok None`, evaluator `True` → false-positive cut
6. **F8 power_grid_reach** (BLOCKER): 同 pattern, fake (60,60) cells 也 pass
7. **7 oracle source_digest** (HIGH): scope 写 `state.source_digest or
   compute_source_digest(state)`. state 字段是 caller-side note 不是 source of
   truth. stale 时 step 6 立刻 QUARANTINE 刚生成的 cut.

Gemini 0 catch 的根因: F7/F8 都过 Gemini "需 power 校验 / cert 字段 sound /
disconnect witness 重算" 但**没问 "假 facility_cells 能 pass 吗"** — 正是
adversarial Layer 2.

## 加强 rule (2026-05-25): Gemini close 不等于 audit close

任何 family validator 经 Gemini multi-round close 后, **仍必经 GPT pro 一次
adversarial pass 才能宣 close**. 不论 Gemini round 多少、catch finding 多少.
Gemini layer 1 + GPT pro layer 2 是叠加不是替代.

实操 trigger: 大节点结束 (per [[big-milestone-gpt-pro-review]]) 打包送 GPT pro,
verdict GO 才能正式 close. Gemini-only close 是 "工程 close", GPT pro 后才是
"audit close".

## 4 个 adversarial soundness 反例 (Phase 1.1)

1. **F1**: cert claim "boundary 46 instance 全占 R 138 cell". 真数据 14 pose
   能放 R 外 → cert claim 不是已证下界.
2. **F3**: cert 证 (A pose blocked). cut.literals 写 C pose. validator 不
   binding → 拿 A 证剪 C.
3. **F2**: cert 写 partition (A, B) + cut_size=0 + demand=1. A∪B 只 2 cell
   vs 4900 grid. validator 不验 partition 覆盖 → 假 partition pass.
4. **F4**: cert 写 commodity_id="fake". validator 不验 commodity 存在.

每个共同模式: **cert 内字段语法对, 但 cert claim 跟实际证明对象/数据/不变量
不绑**. 这是经典 schema-only validator 漏洞.

## 修法 (apply when writing 任何 family validator)

每个 validator 入口列必验:

1. **Cert 内字段 sound** (e.g. cap_R 重算 / direction offset 正确) — schema
   level
2. **Cert ↔ cut.literals 绑定** — multiset 精确等于 cert 引用的 (group,
   pose_id) 组合
3. **Cert ↔ 真数据 source-of-truth 绑定** — commodity_id / facility_pose_id /
   port (cell, dir) 必查 production data 存在 + 真值 match
4. **Cert ↔ state invariant 绑定** — state.cell_owner / selected_poses 等
   跟 cert claim 一致
5. **Cert ↔ 不变量** — partition 覆盖 / hash equal / sum constraint 等
   全 invariant 都必检查 (不只 disjoint)

不只 1, 必须 1-5 全跑. 每条都得在 validator code 里有 specific check.

## 实施 enforcement

写新 family validator 时:
- 先列 spec §X 全部 cert ↔ X 绑定关系 (e.g. spec §3 cert schema + §6
  evaluate semantics)
- validator 入口对每条 cert 字段问: "假数值能 pass 吗?" — 必加 negative
  test (assert validator 拒掉)
- adversarial test: 故意构造 cert/literal/state 不一致 case, validator 必
  schema_err 或 unsound

## Apply when

任何 cut family validator + audit. 不论 Gemini 还是 GPT pro 还是 self-audit.

## Refs

- [[gpt-pro-p11-audit-not-go]] — 4 critical 反例完整 cite
- [[gemini-prompt-audit-mode]] — Gemini audit mode (covers Layer 1 only)
- [[v14-review-findings]] — GPT pro 历史 review 也用 falsify 风格
- [[gpt-error-types-taxonomy]] — 算法错估 / 前提错估 / 数学能力上限.
  adversarial soundness 是新一类 — "validator 完整性"层
