---
name: f9-area-only-not-density
index_summary: "F9 generator 只接受 area_capacity_overflow. 严格 > 才 cut."
description: 2026-05-23 PROJECT_LOCK §3A 锁: F9 density_envelope 只接受 area_capacity_overflow witness, 拒绝 routing/binding/pcr_cut overflow. Evaluator 必 area-based sum(|pose_cells ∩ W|), 不是 instance count. Gemini math review meta-audit invariant.
metadata:
  node_type: memory
  type: reference
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

> **⚠️ 现状 (2026-06-04, v28 GPT 外审): F9 整族已 QUARANTINE (fail-closed 停用)。** 外审 catch F9 `max_allowed_area` **量词倒置**: validator 只验 `K≤safe_ub` + `∃witness area>K`, 不证 `∀legal area≤K` → 伪 `K<safe_ub`(如 K=0) cert 过 validator → 误剪合法布局 = FP。NP-hard tight-K 无便宜中间地带, validator 现 fail-closed 拒 `K<safe_ub` → F9 只剩平凡 cut = 实质停用; **反转了 Gemini round-4 刻意 oracle-trust deferral** (r3 提出、r4 撤销并以 `test_validate_ok_cert_max_zero_exclusion_zone` 记录"信任 oracle tight-K、NP-hard 重验 defer P1.5+"; 外审新窗口零历史重撞 = gpt-error-types-taxonomy(已归档) "前提错估")。解封须 P1.5+ 给 cert 加 area-capacity proof-carrying 字段 + replay 校验。**下面的 area-based 不变量描述 F9 *active 时* 的正确语义 (仍是 area-only 真相), 但 F9 当前不产非平凡 cut。** 现状权威源 [[windows-ninth-review-pending]]。

2026-05-23 Gemini math review meta-audit catch: 原 Gemini 建议把 routing/binding 死锁泛化成 "窗口里设施太密" density cut. 但这会**误剪合法解** — local routing 死锁依赖端口朝向、相对位置、障碍细节, 不是 area capacity 问题.

## F9 invariant (PROJECT_LOCK §3A 锁)

F9 generator **只接受**:
- ✅ `area_capacity_overflow` witness

F9 generator **拒绝**:
- ❌ `routing_overflow` → 走 F2 cutset 或 F5 fallback
- ❌ `binding_overflow` → 走 F5 fallback
- ❌ `pcr_cut_overflow` → 走 F2 + F5 fallback

## F9 evaluator (area-based, 不是 instance count)

```python
occupied_in_window = sum(
    1
    for cell, (owner_group, _) in state.cell_owner.items()
    if owner_group == cert.group_id and cell in W
)
return occupied_in_window > cert.max_allowed_area
```

cell-level 计算, 跟 multiple unsound 变种区分:
- ❌ instance count (any-overlap → whole facility): 历史 FP, 误判 facility 在 W 边缘
- ❌ origin-in-window (anchor 在 W 内 → whole facility): 历史 FP
- ❌ all-in-window (整 facility 在 W 内才算): 历史 FN, 漏算 edge partial
- ✅ area-based `sum(|pose_cells ∩ W|)`: 唯一允许

## Step 8 注入 (CP-SAT)

```text
sum(area_overlap[p, W] * x[g, p]) <= max_allowed_area
```

`area_overlap[p, W]` 是预算好的线性系数 (per pose p), 不在 Python callback 动态算.

## Strict inequality

**等号不 cut**, 只有 `cert_density > max_density` 才 cut. proof obligation: `max_density` 必是安全上界, 不能经验估计 (L14 weighted occupancy 死路 verdict 教训, interior LP=1.000 永不可 cert).

## Morphology safe vs unsafe

morphological erosion **不是** density theorem.

**Safe**:
- 算 region 内 "facility 全装进 W" 的合法 anchor 域
- 证明 10×1 走廊装不下 3×3 facility
- F6 shape packing / Hall-style upper bound 候选域收缩
- 给 `area_capacity_overflow` oracle 找 tighter witness window

**Unsafe leap**:
- ❌ `capacity(W, 3x3) = number_of_eroded_anchors(W)` — anchor 数只是上界, 忽略 facility overlap. anchor outside W 仍可贡献 area inside W

morphology 产 cut 时, cert 必声明语义 (all-in-window placement / overlap-window area / anchor-domain empty / shape packing matching), validator 必独立重算同 semantic.

## Red fixture coverage (Phase 1.2 P0)

- `F9-reject-routing-overflow` — generator 拒 routing overflow witness
- `F9-any-overlap-overcount` — 历史 FP
- `F9-origin-in-window` — 历史 FP
- `F9-all-in-window-FN` — 历史 FN

## Refs

- `docs/项目说明/02_mathematical_foundations.md §3.9` F9 详
- `docs/项目说明/04_design_invariants.md §18` PROJECT_LOCK F9 area-only invariant
- `docs/research/p3_b_design_v2_20260521/external_review/gemini_math_review_bundle_20260523/notes/F9_MORPHOLOGY_CAUTION.md` (source)
- phase-1-1-go-blessed(已归档) / [[cp-sat-no-add-lazy-constraint]]
