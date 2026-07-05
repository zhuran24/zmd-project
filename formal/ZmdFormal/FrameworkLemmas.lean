import Mathlib

/-!
# 搜索框架层引理（P3.0b 第四批，2026-07-05）

三块承重骨架，对应 formal/README「下一批砖」清单：
- **F5 复合安全引理**（`p1_3_f5_orbit_lift_soundness_design_v1.md` §2.4 引理原文，
  v2 §2.4 声明"同 v1"）：序保代表元 × 轨道 cut 删整类，复合不产生
  "类内代表被序删光而类未被证不可行"的 false-INFEASIBLE；
  外加 v1 点名的**反方向陷阱**的机器反例（无 P-HOM 则复合删光合法类）。
- **frontier lex 支配剪枝**：max_lex(area, min_side) 搜索下，已有 in-hand
  witness 时剪掉 lex 不优于它的候选不损失最优值。对任意线性序证明，
  lex 是 `ℕ ×ₗ ℕ` 特例。
- **TP7-S selected-solution nogood 等式键边界**
  （`p2_0_throughput_certification_paradigm_design_v2.md` v3 终审 BLOCK）：
  完整 0/1 等式键的排除集恰为 {S}（sound 且不过切）；
  "只禁选中集"式 nogood 的过切玩具反例（一条半容量路不够、加并行路就够）。

抽象边界同前批：P-HOM / 代表选择完备性 / Farkas verdict 正确性在这里是
**假设**，由设计稿的结构门与复验义务承担。
-/

namespace ZmdFormal.Framework

/-! ## F5 复合安全（orbit cut × master 对称序） -/

section CompoundSafety

variable {σ : Type*}

/-- 复合安全引理（F5 v1 §2.4）：P-HOM（可行性沿轨道不变）+ 代表选择
（每类至少留一个序代表）+ cut 逐点 sound（只删不可行，由轨道 lift
soundness 定理提供）⇒ 全空间有可行解，则「序代表 ∩ 未被 cut 删」的
搜索空间内也有可行解——复合不删光合法类。 -/
theorem f5_compound_safety
    (equiv : σ → σ → Prop) (Feasible : σ → Prop) (Sel Cut : σ → Prop)
    (hPHOM : ∀ {s t}, equiv s t → (Feasible s ↔ Feasible t))
    (hSel : ∀ s, ∃ r, equiv s r ∧ Sel r)
    (hcut_sound : ∀ s, Cut s → ¬ Feasible s)
    {s₀ : σ} (hs₀ : Feasible s₀) :
    ∃ r, Sel r ∧ ¬ Cut r ∧ Feasible r := by
  obtain ⟨r, hequiv, hsel⟩ := hSel s₀
  have hfr : Feasible r := (hPHOM hequiv).mp hs₀
  exact ⟨r, hsel, fun hc => hcut_sound r hc hfr, hfr⟩

/-- 反方向陷阱（F5 v1 §2.4 点名的红测，机器反例）：去掉 P-HOM（可行性
读标签），其余前提全保留——全关系轨道、代表存在、cut G-不变（删整类）、
cut 确由某个真不可行点 lift 而来——复合仍可删光合法类 ⇒ false-INFEASIBLE。
这就是「标签敏感 cut + 序 = 删光合法类」的最小构造。 -/
theorem f5_compound_needs_phom :
    ∃ (Feasible Sel Cut : Bool → Prop),
      (∃ r, Sel r) ∧
      (∀ s t, Cut s → Cut t) ∧
      (∃ w, ¬ Feasible w ∧ Cut w) ∧
      (∃ s, Feasible s) ∧
      ¬ ∃ r, Sel r ∧ ¬ Cut r ∧ Feasible r := by
  refine ⟨fun s => s = true, fun s => s = true, fun _ => True,
    ⟨true, rfl⟩, fun _ _ _ => trivial, ⟨false, by simp, trivial⟩,
    ⟨true, rfl⟩, ?_⟩
  rintro ⟨r, _, hc, _⟩
  exact hc trivial

end CompoundSafety

/-! ## frontier lex 支配剪枝 -/

section FrontierPrune

variable {ι β : Type*} [LinearOrder β] [DecidableEq ι]

/-- 剪枝支配：任何候选都被「严格优于 in-hand witness 的幸存集 ∪ {w₀}」中
某元素支配——被剪掉的候选（value ≤ value w₀）由 w₀ 本身支配。 -/
theorem frontier_prune_dominates
    (F : Finset ι) (value : ι → β) {w₀ : ι} (_hw₀ : w₀ ∈ F) :
    ∀ c ∈ F, ∃ c' ∈ F.filter (fun c' => value w₀ < value c') ∪ {w₀},
      value c ≤ value c' := by
  intro c hc
  by_cases h : value c ≤ value w₀
  · exact ⟨w₀, Finset.mem_union_right _ (Finset.mem_singleton_self w₀), h⟩
  · exact ⟨c, Finset.mem_union_left _ (Finset.mem_filter.mpr ⟨hc, not_le.mp h⟩),
      le_refl _⟩

/-- 剪枝保最优：幸存集 ∪ {w₀} 上的最大值 = 全候选集上的最大值——
剪枝不改变搜索问题的答案。对任意线性序成立。 -/
theorem frontier_prune_preserves_max
    (F : Finset ι) (value : ι → β) {w₀ : ι} (hw₀ : w₀ ∈ F) :
    (F.filter (fun c' => value w₀ < value c') ∪ {w₀}).sup'
        ⟨w₀, Finset.mem_union_right _ (Finset.mem_singleton_self w₀)⟩ value
      = F.sup' ⟨w₀, hw₀⟩ value := by
  apply le_antisymm
  · apply Finset.sup'_le
    intro c hc
    rcases Finset.mem_union.mp hc with h | h
    · exact Finset.le_sup' value (Finset.mem_filter.mp h).1
    · rw [Finset.mem_singleton.mp h]
      exact Finset.le_sup' value hw₀
  · apply Finset.sup'_le
    intro c hc
    obtain ⟨c', hc', hle⟩ := frontier_prune_dominates F value hw₀ c hc
    exact le_trans hle (Finset.le_sup' value hc')

/-- 具体化到项目目标：`max_lex(area, min_side)` 即 `β := ℕ ×ₗ ℕ` 的特例。 -/
theorem frontier_prune_preserves_max_lex {ι : Type*} [DecidableEq ι]
    (F : Finset ι) (area minSide : ι → ℕ) {w₀ : ι} (hw₀ : w₀ ∈ F) :
    (F.filter (fun c' =>
        toLex (area w₀, minSide w₀) < toLex (area c', minSide c')) ∪ {w₀}).sup'
        ⟨w₀, Finset.mem_union_right _ (Finset.mem_singleton_self w₀)⟩
        (fun c => toLex (area c, minSide c))
      = F.sup' ⟨w₀, hw₀⟩ (fun c => toLex (area c, minSide c)) :=
  frontier_prune_preserves_max F (fun c => toLex (area c, minSide c)) hw₀

end FrontierPrune

/-! ## TP7-S selected-solution nogood 等式键边界 -/

section Tp7sNogood

variable {V : Type*} [DecidableEq V]

/-- 完整 0/1 等式键 `Σ_{x∈S1}(1−x) + Σ_{x∈S0}x ≥ 1` 的**违反**条件：
S（选中集）全选中 ∧ U \ S（未选集）全未选。 -/
def EqKeyViolated (U S A : Finset V) : Prop :=
  (∀ x ∈ S, x ∈ A) ∧ (∀ x ∈ U \ S, x ∉ A)

/-- 等式键排除集刻画：在全集 U 内，等式键恰好排除 `A = S` 这一个赋值。 -/
theorem eq_key_violated_iff {U S A : Finset V} (hSU : S ⊆ U) (hAU : A ⊆ U) :
    EqKeyViolated U S A ↔ A = S := by
  constructor
  · rintro ⟨h1, h0⟩
    ext x
    constructor
    · intro hxA
      by_contra hxS
      exact h0 x (Finset.mem_sdiff.mpr ⟨hAU hxA, hxS⟩) hxA
    · exact h1 x
  · rintro rfl
    exact ⟨fun _ hx => hx, fun x hx => (Finset.mem_sdiff.mp hx).2⟩

/-- 等式键 sound：Farkas 证明了赋值 S 不可行 ⇒ 等式键排除的全部赋值不可行
（排除集被证据完全覆盖，无 false-INFEASIBLE）。 -/
theorem tp7s_eq_key_sound {U S : Finset V} (hSU : S ⊆ U)
    (Feasible : Finset V → Prop) (hS : ¬ Feasible S) :
    ∀ A ⊆ U, EqKeyViolated U S A → ¬ Feasible A := by
  intro A hAU hviol
  rw [eq_key_violated_iff hSU hAU] at hviol
  rwa [hviol]

/-- 等式键不过切：真超集不触发等式键——要排除超集必须另有独立
exact-rational 证明（稿 v3 回退循环第 2 条）。 -/
theorem tp7s_eq_key_no_overcut {U S A : Finset V} (hSU : S ⊆ U) (hAU : A ⊆ U)
    (hss : S ⊂ A) : ¬ EqKeyViolated U S A := by
  intro hviol
  rw [eq_key_violated_iff hSU hAU] at hviol
  exact hss.ne hviol.symm

/-- 选中集式 nogood 过切反例（v3 终审 BLOCK 玩具例的机器版）：
"一条半容量路不够、加一条并行路就够"——`¬Feasible S` 但存在可行超集，
`∨_{x∈S} ¬x` 式 nogood 会把该超集错剪 = false-INFEASIBLE。 -/
theorem tp7s_selected_set_nogood_overcuts :
    ∃ (Feasible : Finset Bool → Prop) (S A : Finset Bool),
      ¬ Feasible S ∧ S ⊆ A ∧ Feasible A := by
  refine ⟨fun X => 2 ≤ X.card, {false}, {false, true}, ?_, ?_, ?_⟩
  · decide
  · decide
  · decide

end Tp7sNogood

end ZmdFormal.Framework
