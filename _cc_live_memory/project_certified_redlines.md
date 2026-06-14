---
name: certified-redlines
description: "certified_exact 不可碰红线(PROJECT_LOCK §1+§3)的召回锚点:certified vs exploratory 严格隔离、max_lex(area,min_side)、min_side≥6 是 admissibility 非 tie-break、无 50桩+10箱 hard cap、globally-pooled 不可硬绑 per-line、ghost rectangle 不要求 exterior path、EXACT_* deny-unknown。要动 certified 边界/proof/schema/cut 前先读 PROJECT_LOCK。撞了=false-CERTIFIED/false-INFEASIBLE。"
metadata:
  node_type: memory
  type: project
---

**要改 certified_exact 路径、proof、schema、cut、或任何涉及 PROJECT_LOCK 边界的东西前,先读 `PROJECT_LOCK.md`(§1 Exactness Constitution + §3 Accepted Invariants)。** 这条是**召回锚点**——记忆树此前没有任何 description 会在"我要动 certified 边界"时把你拽到 lock,而新会话最可能撞、撞了代价最大(false-CERTIFIED / false-INFEASIBLE)的恰是这类。**why 的权威源在 lock + specs,这里不复述(能重读),只给召回触发 + 反面教材指针。**

## 5 条 Forbidden Changes(撞前必读 lock 原文)
1. 把 exploratory cap 当 exact-mode bound 重新引入(**无** 50桩+10箱 hard cap;那是 exploratory-only)
2. 把 exploratory 工件当 certified proof
3. 改 campaign/artifact/proof schema 却不同步 lock/spec/test
4. 把 globally-pooled 资源硬绑成 per-line binding 而无新 proof basis(global pooling 必须 commodity-aggregated)
5. 给 ghost rectangle 加 exterior-path 要求(全封闭合法空矩形**允许**;exterior connectivity **不在** exact 契约)

## 最易撞的几条 invariant(原文在 PROJECT_LOCK §1/§3)
- `max_lex(area, min_side)` 是 exact 目标;`min_side >= 6` 是 candidate **admissibility** 不是 tie-break;`Phi(w,h)` / `(area,w,h)` 都**不是** exact 真相源。
- routing-free wireless final(omni_wireless / generic_input sink)的 producer output port 必须从 routing surface 排除,且要在**每个**消费点排除(F03/F04 系列)——漏一处=orphan source→false-INFEASIBLE。
- terminal front polarity 朝 connector(F-RT-R2-01):每个独立 verifier 必须从规则自推极性,**不能抄 solver 的 key**(diff-fuzz 头 900 实例就栽在抄了反的 key)。
- `EXACT_*` env 在 certified 下 **deny-unknown**:只允许文档化 allowlist,未知名 block run。

## 3 个真 P0 反面教材(2026-06-11 换方向审算法挖出,certified 曾 unsound)
- **A-1**:routing 局部连续 ≠ 全局连通 → false-CERTIFIED
- **B-01**:no-overlap 用模板固定尺寸非真 footprint(命中 38+46 真实强制实例)→ false-CERTIFIED
- **A-2**:front_blocked over-cut 跳过 binding 枚举 → false-INFEASIBLE → max_lex 下漏真最大矩形

完整验收 = `cc_context/review/algoaudit_verification_results_20260611.md`;过夜审查弧线见 harness memory「overnight-certified-surface-review-arc」。

## 定位
纯导航 / 召回锚点,**不是 proof 真相源,不拓宽任何 proof 语义**。真相源 = `PROJECT_LOCK.md` + `rules/canonical_rules.json` + specs + 测试。身份根 [[endfield-solver]]。
