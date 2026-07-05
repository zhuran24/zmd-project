import ZmdFormal.DesignStatements
import ZmdFormal.FrameworkLemmas

/-!
# W-完备骨架（Q1 分类学设计稿 §7 的 Lean 化，2026-07-05）

对应 `docs/research/q1_infeasibility_class_taxonomy_design_v1.md` §5/§7：
D_cut 的每个成员（完整、良构、replay-verified 不可行的赋值）都有 F5
fallback 产生的 sound 匿名 multiset nogood 且排除自身——W-完备的单点见证。

**Lean 化自查发现（重要，给设计稿 v2 与外审对照）**：设计稿 v1 §5 的
证明骨架写"对完整赋值，『任何扩展』= 自身"——这个论证**隐含了两个
未点名的前提**，形式化立即暴露：
- `hFC`：Feasible 蕴含 Complete（可行布局必是完整布局——本项目语义下
  成立：266 个 mandatory 设施全放置才算可行，但必须作为前提显式进定理）；
- `hNoProperExt`：Complete 布局间无真包含（两个完整布局若一个包含另一个
  则相等——由"完整 = 每组每实例恰一 pose"的计数语义保证，同样必须显式）。
设计稿 v2 修订时应把这两条补进 §5 的工程条件清单。

抽象边界同前批：Complete 的具体语义（逐组实例计数）、P-HOM、well-formed
是假设，由结构门与 replay 义务承担。
-/

namespace ZmdFormal.WCompleteness

open ZmdDesignStatements ZmdDesignStatements.Orbit

universe u v w

variable {GroupId : Type u} {Slot : GroupId → Type v} {Pose : GroupId → Type w}

/-- 骨架引理：完整、不可行的赋值满足 liftable-reject——"扩展 = 自身"
论证的显式前提版（`hFC` + `hNoProperExt` 是 Lean 化暴露的隐含前提）。 -/
theorem complete_infeasible_liftable_reject
    (Feasible Complete : Layout GroupId Slot Pose → Prop)
    (hFC : ∀ A, Feasible A → Complete A)
    (hNoProperExt : ∀ s A, Complete s → Complete A → s ⊆ A → s = A)
    {s : Layout GroupId Slot Pose} (hsC : Complete s) (hsI : ¬ Feasible s) :
    LiftableReject Feasible s := by
  intro A hA hsub
  have hEq : s = A := hNoProperExt s A hsC (hFC A hA) hsub
  exact hsI (hEq ▸ hA)

/-- W-完备单点见证（设计稿 §5 W-完备命题的数学核）：D_cut 成员
（完整、良构、不可行）必有 F5 fallback 的匿名 multiset nogood，
sound（排除的都不可行）且排除自身（`AnonMultisetExtends s s` 自反）。
量化到全体成员即 W-完备。 -/
theorem w_completeness_f5_fallback
    [DecidableEq GroupId] [∀ g, DecidableEq (Slot g)] [∀ g, DecidableEq (Pose g)]
    (Feasible Complete : Layout GroupId Slot Pose → Prop)
    (hExtend : PartialSlotPermExtends.{u, v, max v w} (GroupId := GroupId) Slot)
    (hPHOM : P_HOM Feasible)
    (hFC : ∀ A, Feasible A → Complete A)
    (hNoProperExt : ∀ s A, Complete s → Complete A → s ⊆ A → s = A)
    (hWellFormed : ∀ A, Feasible A → NoDuplicateNamedSlots A)
    {s : Layout GroupId Slot Pose}
    (hsC : Complete s) (hsI : ¬ Feasible s) (hsWF : NoDuplicateNamedSlots s) :
    AnonMultisetNogood Feasible s ∧ AnonMultisetExtends s s := by
  refine ⟨?_, fun x => le_refl _⟩
  exact anon_multiset_lift_soundness_from_named_representative hExtend hPHOM
    hWellFormed
    (complete_infeasible_liftable_reject Feasible Complete hFC hNoProperExt hsC hsI)
    hsWF

/-- 反面警示（与设计稿 §5 工程条件①呼应）：去掉完整性语义
（存在可行真扩展），"扩展 = 自身"论证崩塌——不可行的 s 不再
liftable-reject，其 full nogood 会误剪可行扩展。最小构造。 -/
theorem incomplete_assignment_fallback_unsound :
    ∃ (Feasible : Layout Unit (fun _ => Bool) (fun _ => Unit) → Prop)
      (s : Layout Unit (fun _ => Bool) (fun _ => Unit)),
      ¬ Feasible s ∧ ¬ LiftableReject Feasible s := by
  refine ⟨fun A => A.card = 2, {⟨(), (true, ())⟩}, by decide, ?_⟩
  intro hLR
  have hsub : NamedExtends
      ({⟨(), (true, ())⟩} : Layout Unit (fun _ => Bool) (fun _ => Unit))
      {⟨(), (true, ())⟩, ⟨(), (false, ())⟩} := by
    show ({⟨(), (true, ())⟩} : Layout Unit (fun _ => Bool) (fun _ => Unit)) ⊆
      {⟨(), (true, ())⟩, ⟨(), (false, ())⟩}
    decide
  exact hLR {⟨(), (true, ())⟩, ⟨(), (false, ())⟩} (by decide) hsub

/-! ## 组合定理：oracle 判决 → cut 排除 → 搜索空间安全的全链 -/

/-- 全链组合定理：F5 lift 链（oracle 的 liftable reject → 匿名 multiset
nogood）与复合安全引理**弱化变体**（`f5_compound_safety_from_pointwise_sound`，
消费已复验的逐点 sound cut——本定理的 cut 恰好由 `anon_lift_sound`
现场复验，故弱化变体正是正确的接口；类不变性版本见
`Framework.f5_compound_safety`）的组装。结论：oracle 验证过的 pattern
nogood 作为 cut，与任何代表选择复合后，搜索空间（代表 ∩ 未被 cut
排除）内仍有可行解（只要全空间有）。 -/
theorem oracle_nogood_compound_search_safety
    [DecidableEq GroupId] [∀ g, DecidableEq (Slot g)] [∀ g, DecidableEq (Pose g)]
    (Feasible : Layout GroupId Slot Pose → Prop)
    (equiv : Layout GroupId Slot Pose → Layout GroupId Slot Pose → Prop)
    (Sel : Layout GroupId Slot Pose → Prop)
    (hEquivPHOM : ∀ {s t}, equiv s t → (Feasible s ↔ Feasible t))
    (hSel : ∀ s, ∃ r, equiv s r ∧ Sel r)
    {P : Layout GroupId Slot Pose}
    (hExtend : PartialSlotPermExtends.{u, v, max v w} (GroupId := GroupId) Slot)
    (hPHOM : P_HOM Feasible)
    (hWellFormed : ∀ A, Feasible A → NoDuplicateNamedSlots A)
    (hReject : LiftableReject Feasible P)
    (hPslots : NoDuplicateNamedSlots P)
    {s₀ : Layout GroupId Slot Pose} (hs₀ : Feasible s₀) :
    ∃ r, Sel r ∧ ¬ AnonMultisetExtends P r ∧ Feasible r := by
  have hnogood : AnonMultisetNogood Feasible P :=
    anon_multiset_lift_soundness_from_named_representative hExtend hPHOM
      hWellFormed hReject hPslots
  exact ZmdFormal.Framework.f5_compound_safety_from_pointwise_sound equiv Feasible Sel
    (fun A => AnonMultisetExtends P A)
    hEquivPHOM hSel
    (fun A hc hF => hnogood A hF hc)
    hs₀

end ZmdFormal.WCompleteness
