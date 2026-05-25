# Path 13 — SAC-Hull (Separator-Aware Capacity Hull + L2)

## 当时项目情况

Path 12 RAB-SEP 死后. GPT v2 review.

## 为什么走这条路

GPT v2 plan: Menger / max-flow min-cut paradigm. 全局 corridor capacity necessary condition. 比 RAB-SEP 的 local cert tight 更全局.

## 实验过程

实施 (commits a64e406 → 71fb897, 6 个 phase):
- Phase 0 PoC (22 violations)
- Phase 1 static 64 separator land
- Phase 2 dynamic separator
- Phase 2a v3 (violations 22→7→8)
- Phase 3 L2 abstract routing layer
- Phase 5 multi-anchor

env: `EXACT_B1_SEPARATOR_HULL` / `EXACT_B1_SEPARATOR_HULL_DYNAMIC` / `EXACT_B1_ABSTRACT_ROUTING_LAYER`.

## 实验结果

violations **减 80%+** (22→4-5 floor). L2 工作 (0.08-0.10s) 让 master OPTIMAL layout 通 SAC 2 次. 但:
- **0/8 CERTIFIED** (Phase 5 multi-anchor 8 anchor uniform hardness)
- binding/routing 真 verifier 仍 reject L2-FEASIBLE layouts
- SAC necessary ≠ sufficient

## 经验跟教训 (含瓶颈理解更新)

- 同 Path 12 paradigm pattern: 端到端 land ✅ but breakthrough ❌. cut 是 necessary 不 sufficient.
- **瓶颈理解更新**: 不同 sub-problem 抽象层 (binding-side vs corridor capacity) 同质死法. paradigm framework 不论从哪层抽 necessary condition, 都不 sufficient to bridge from layout 到 routing-feasibility.

## code/

- `code/` 含 separator_capacity_hull.py + abstract_routing_layer.py + separator_capacity_separator.py + 6 phase trial scripts
