---
name: gpt-error-types-taxonomy
description: "评估 GPT 外部 review 的 4 种错估 type (body 详): (1) 算法错估 = 关注点不对 (v3 看 build, v8 看 anchor choice) (2) 前提错估 = 假设我们 data 满足某 precondition 而我们没 (v10 要求 complete witness) (3) 数学能力错估 = 方法本身能力上限 (L14 weighted occupancy 数学不够) (4) L15 新增 paradigm 层错估. 区分这几类影响下一步策略: 算法/前提错估 = GPT 推理弱要 push; 数学能力错估 = GPT 推理对要承认 paradigm 限制."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## 四种 GPT 错估 (来自 2026-05-16/17 session 实测)

| Type | 例子 | 表征 | 怎么发现 |
|---|---|---|---|
| **算法错估** | v3 (5/13): 关注 build 慢 → 实际 solve 慢; v8 (5/16): 关注 ghost anchor 撑搜索树 → 实际 facility placement 是搜索主体 | GPT 攻错了点, 方法本身没问题但攻击对象错 | 实测 lever 跟 baseline 同 quality (5min UNKNOWN vs 1h UNKNOWN 跨数量级无 improvement) |
| **前提错估** | v10 (5/16): 算法要求 complete mandatory witness → 我们 community blueprint 缺 41 个, greedy 填的破坏空地, preflight 永不 trigger | GPT 方法本身 sound, 但 hidden assumption 我们 data 不满足 | 实测 fail-closed gate 在 trigger 之前就 fail, 0 anchor cert |
| **数学能力错估 (= GPT 没错估)** | L14 (5/16): weighted occupancy Farkas family 数学上 cover 不动 interior anchor (LP=1.0 exact) | GPT 推理正确, 方向 sound, 但**方法本身能力上限不够**; GPT 自己 caveat 列了 failure mode, 实测 hit caveat | LP optimum stable 在 1.0, 数学推理验证 family upper bound |
| **paradigm 攻错层** | L15 (5/17): set-packing prover paradigm 假设 set-packing 核心 stuck → 实测 minimum CP-SAT 几秒搞定, stuck 在 master 多余约束 (port/power/boundary) | GPT 选错了下手层, paradigm 本身可行但目标层不是 bottleneck | 拆分子问题 layer by layer 实测每层 wall-clock, 找出真 bottleneck 层 |

## 影响下一步策略

- **算法/前提错估**: GPT 推理弱, 应该 push (加料 prompt 让他诚实). 这种 GPT 给的方案 ROI 通常 0.
- **数学能力错估**: GPT 推理对了, 死的是方法上限. 这种 GPT 已经诚实, 不用 push, 应该接受 verdict, 考虑 paradigm 升级.

## 用法 — 拿到 GPT 新方案如何快速 categorize

1. 先 read GPT doc 看他**自己列的 caveat 数量**:
   - 0 caveat = 大概率算法/前提错估 (GPT 没 self-check)
   - 3+ caveat = 大概率数学能力错估 (GPT 自己审过)

2. 检查方案对准的**瓶颈描述**:
   - 跟项目真瓶颈对得上 → 大概率数学能力或前提错估
   - 跟项目真瓶颈对不上 → 大概率算法错估

3. PoC 后 verdict:
   - 实测改善很大但仍不破局 → 算法错估 (build/anchor 都加速但 solve 不动)
   - 实测 fail-closed 不 trigger → 前提错估 (data 不满足)
   - 实测 LP/bound 数学上 stuck → 数学能力错估

## 这次 session 累积

4 次 GPT 出招 (v8 / v10 / L14 / L15), 4 种错估 type 各 1 个例子:
- v8: 算法错估
- v10: 前提错估
- L14: 数学能力 (GPT 没错估但方法死)
- L15: paradigm 攻错层

加料 prompt 把 GPT 推到"诚实 caveat"状态 (L14 hit), 但还是有 paradigm 选择错估 (L15).

## 链

- [[gpt-review-prompt-armor]] — 加料 prompt 怎么写
- [[v8-anchor-slicing-dead]] — 算法错估
- [[v10-witness-preflight-dead]] — 前提错估
- [[l14-weighted-occupancy-dead]] — 数学能力上限
- [[l15-setpacking-prover-dead]] — paradigm 攻错层
- [[external-review-reproducibility]] — GPT review reproducibility
