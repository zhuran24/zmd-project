---
name: gemini-review-algorithm-math
description: "2026-05-21 用户原话: 算法 / 数学 方面的工作都要提交给 Gemini 再看一下, 或让他独立做一遍. Phase 0 Family spec 也算 (1/6/7 三 family 全是数学+算法). 不是 hint, 是硬要求."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-21 / 2026-05-22 用户原话:
- 第一次 (5-21): "记一下算法方面或者数学方面都要提交给Gemini再看一下或者让他独立做一遍"
- 第二次加严 (5-21 Day 17 后): "先 check, 以后都是先 check 再继续"
- 第三次扩 scope (5-22 Phase 0 close 后, /goal): "一直保持推进, 遇到决策按
  稳健方向来选, 记得交给 Gemini 审查"
  - 加严 scope 从 "算法/数学" → **任何决策性输出** (governance / plan / lock
    update 都要 Gemini cross-check). 不只 Phase 0 spec 阶段, Phase 1 工程
    阶段也走.
  - "决策按稳健方向选" — implementation choice 默认走更保守 sound 的路, defer
    optimization 到后期 (跟 Gemini round 19 "宁可 FN 漏剪不可 FP 误剪" 同 spirit)

## 规则 (v2 加严)

任何算法层或数学层的设计 / spec / proof, **每 commit 后立刻** Gemini cross-check, **不堆几个 commit 后才一波 cross-check**. 修对后再写下一个 spec.

之前 Day 15/16a/16b 三 family spec 堆到 round 14 才 cross-check, Gemini 一次找出 3 致命 sound bug + 2 schema 漏. 堆得越多, finding 越多, 修起来越乱. 单 spec single-step cross-check 防 cascade 错估.

两种 cross-check 方式任选:
1. **再看一下** — Gemini 读 Claude 写的 spec, 找 bug / 漏掉的反例 / soundness 证错 / cert schema 漏字段 / generator 算法 corner case
2. **独立做一遍** — 不给 Gemini 看 Claude 写的, 让他独立给方案. Claude 跟 Gemini 方案对比找差异

## Prompt 模式硬规则 (v4 加严, 2026-05-24 用户提醒)

用户提醒原话: "那这个应该直接记在 Gemini 审查的 mem 里面". 起因是我说 "F2/F4 generator 用 state.commodity_routes 等 dynamic state 字段, 真数据 schema 跟我 design 假设是否一致没扫. 等 5 spawn return + merge + implement 后, Gemini cross-check round 1 我需补真数据 paths." — 这种"需补"应该是**协议硬规则**, 不靠我主动想起来.

**src phase Gemini cross-check prompt 必含**:
1. **真数据进 DOC_PATHS** (硬要求, 不是可选):
   - `rules/canonical_rules.json`
   - `data/preprocessed/candidate_placements.json`
   - `data/preprocessed/mandatory_exact_instances.json`
   - `data/preprocessed/generic_io_requirements.json`
   - (若涉及 commodity / routing: 真数据 commodity_routes + commodity_demands schema)
   - 不放真数据 → Gemini 不可能 catch spec ↔ data gap (e.g. hardcoded 字段名 vs schema 实际名)
2. **任务直接问 spec-data gap**: "src 跟真数据接合时哪步先 crash / FN / FP? 列具体 file:line + 假设字段名 vs 实际 schema."
3. **Armor strict mode** (per [[gpt-review-prompt-armor]]):
   - GO verdict 必先列 3 种最可能死法 + 反驳每一种
   - 不准 "looks fine / 完美 / 绝佳 / very solid" 等 vague hyperbole
   - critical claim 必 cite literature 或 code file:line
   - 找不到 critical 也必列 3 个 high-risk hypothesis
4. **明确反 GO 章 ritual** 在 prompt 末尾: "找 1 critical 比 100 surface comment 价值高 10×. 不接受 GO ritual unless 真只剩 nice-to-have / Phase X+ defer."

**反例 (历史踩坑)**: Phase 1 r27/r28/r29 三 round cross-check **全 GO**, 真问题在 prompt 模式 — 验 spec↔src 一致 (surface) 不 push spec↔data gap, DOC_PATHS 缺真数据. **不重写 prompt 别调** (浪费 token 拿一个 GO 章).

**Apply when**: 任何 src 阶段 cross-check (F2/F4/F6/F7/F8 generator / Phase 1.3+ propagator 集成 / Phase 1.4 ramp 前) 之前**重写 prompt** 满足上述 4 条.

详 [[gemini-prompt-audit-mode]] memory 看具体反例 (Phase 1 r27/r28/r29 GO 章 ritual 模式分析).

## 循环规则 (v3 加严, 2026-05-24)

用户原话: "Gemini 指出的问题修复完之后就直接进入下一个小环节了吗，正常来说应该再进行审查直到没有问题或者说只剩下小问题才行"

**单轮 Gemini cross-check + fix 不算完**. 一轮 fix 完必须 round 2 重 review:
- Round 1: Gemini 找 N 个 finding → Claude 修
- Round 2: Gemini 再看 (含 round 1 fix), 看 fix 是否引入新 bug / round 1 漏 finding / 修方向对不对
- ... 循环
- **stop 条件**: GO verdict, 或者只剩 nice-to-have / Phase 1.5+ defer 的 minor finding

类比外部 R 轮 reviewer (R1-R5 5 轮迭代直到 "1.1 gate 正式通过"). Gemini per-commit cross-check 同理 — round 1 一轮不够.

**⚠️ 这条不止 Gemini (2026-06-02 复发后加)**: "修完再审直到 clean" 是**通用 review/verify 规则**, 不是 Gemini 专属 —— GPT pro 外审 / 内部 backstop workflow / Claude 自审, 任何一种, 修完 finding 都要 **re-audit 那个修过的产物 (重建出来是新工件, 没审过)** 直到一轮零 finding / 只剩 minor。**别因为这条当初记在「Gemini」标题下, 就在别的 review 语境里漏掉它** —— 本 session 实例: v25 GPT-review workflow 报 3 瑕疵, 我修+重建成新 sha 后没再审就交付, 用户 catch ("修了一遍之后就默认好了, 没审到没问题为止"); 根因正是这条 siloed 在 Gemini、跑 GPT loop 时没 surface。同一规则也在 [[verification-independent-backstop]] 规则#4 + [[audit-verify-before-archive]]。

**Why**: round 1 fix 可能引入新 bug (e.g. R5 catch R4 加 strict int 但漏了 grid bound — R4 fix 的副作用), 或 round 1 Gemini 偶尔漏 finding (LLM 输出有 variance, per [[external-review-reproducibility]]).

成本: 每轮 ~30-60s Gemini API call + ~5-15 min 修. 多轮迭代 ROI 正向 (catch 隐性 bug, 避免后期 R 轮外部 reviewer 第 N 轮 catch 同样问题).

实操:
- Round 2 prompt 包含: "你 round 1 给了 X 个 finding, 我修了 Y 个 (列具体 commit + fix description). 再 review src — 看 fix 是否正确, 看是否有新 bug, 看 round 1 漏 finding."
- Round 3+ 同 pattern
- 中间 round 可能改 design 不只 implementation fix
- 实施前 prompt 必含先前 round Gemini finding 摘要 (上下文)

## Why

[[gemini-better-at-natural-tone]] 主要是写作 register. 但 algorithm/math 也是 Gemini 优势 ([[gemini-math-consultant]] 已记 API key). Claude 自己 land 的数学层有可能:
- 用 multi-shape Hall 当 single-shape 处理但忽略 PARTITION-reducible NP-hardness
- soundness proof 边界 case 漏 (e.g. v14 v14 boundary source-of-truth 错 perimeter vs left+bottom)
- cert schema 漏字段 (Gemini round 12 抓到 resolve_region_capacity double-count bug)

Phase 0 v14 review 走的就是这个 pattern (GPT pro + Gemini round 12 + round 13 cross-check), 但 Family 1/6/7 spec 是我 land 完没走 cross-check. 应该补.

## 怎么 apply 到现在

Phase 0 Day 15-16 已 land 3 family spec (1/6/7), 全是数学+算法:
- Family 1 region_capacity: LP dual / combinatorial / Farkas algebraic check / 4 region kind 数学
- Family 6 shape_packing_hall: Hall's marriage theorem / NP-hardness / multi-shape generalize / partition algorithm
- Family 7 power_hitting_set: hitting set / monotone soundness / CoverSet 单调保持 / ghost-conditioned scope

应该现在打包发 Gemini cross-check, 不能直接进 Day 17 Family 2/3/4/5.

## 未来 apply

任何 src 改动 (binding / routing / master) 涉及数学层 (sound 性证明 / cut schema / pose 几何) 都 Gemini 看一遍. 不算"无谓盖章" — 是 sound 性 second line of defense.

例外: 纯 implementation 细节 (变量重命名 / refactor / IO / test fixture data) 不算数学层, 不 Gemini 看.

## Refs

- [[gemini-better-at-natural-tone]] — register/写作层 Gemini 优势
- [[gemini-math-consultant]] — Gemini 3.1 pro API key + fat-context 用法
- [[gemini-prompt-audit-mode]] — **prompt 模式细节 + 反例 (Phase 1 r27/r28/r29 GO 章 ritual)**, v4 加严段引用此 memory
- [[gpt-review-prompt-armor]] — armor strict mode 通用 (3 死法 + 反 vague + cite file:line)
- [[v14-review-findings]] — Phase 0 v14 review pattern 实例 (Gemini round 12/13 抓到 critical bug)
