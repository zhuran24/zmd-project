import Mathlib

/-!
# 搜索框架层引理（P3.0b 第四批，2026-07-05）

三块承重骨架（2026-07-05 首版；同日双路对抗审 + 盲对拼回收后修订——
修订记录见 formal/README）：
- **F5 复合安全引理**（`p1_3_f5_orbit_lift_soundness_design_v1.md` §2.4 引理原文，
  v2 §2.4 声明"同 v1"）：忠实版 `f5_compound_safety` 带"cut 删整类"前提
  （`hCutClass`）与类局部结论；弱化变体 `_from_pointwise_sound` 只消费已
  复验的逐点 sound cut（组合接口，非 lift 审计接口）。反例两条：
  `f5_compound_needs_cut_invariance` = v1 点名的红测（**非 G-不变/标签
  敏感 cut** + 序 = 删光合法类）；`f5_compound_needs_phom` = 相邻边界
  （P-HOM 破缺时同样删光——不是原文那条红测，是前提必要性的补充）。
- **frontier 剪枝**：纯 value 层（dominates / preserves_max，只保最大值）
  与发布级 certified-argmax 层（保 certified witness）分开陈述；
  `frontier_dominance_skip_not_migratable` = 谓词迁移时 skip 不可继承的
  机器红测。全部限定固定谓词。
- **TP7-S selected-solution nogood 等式键边界**
  （`p2_0_throughput_certification_paradigm_design_v2.md` v3 终审 BLOCK）：
  `EqKeyViolated` 内置全集约束；排除集恰为 {S}（sound 且 U 内不过切）；
  选中集式 nogood 的过切反例带显式容量/需求语义。

抽象边界同前批：P-HOM / 代表选择完备性 / Farkas verdict 正确性在这里是
**假设**，由设计稿的结构门与复验义务承担。
-/

namespace ZmdFormal.Framework

/-! ## F5 复合安全（orbit cut × master 对称序） -/

section CompoundSafety

variable {σ : Type*}

/-- 复合安全引理（F5 v1 §2.4 的忠实形态；2026-07-05 外审修订版）：
代表选择给每个轨道至少一个序代表；**orbit cut 的证据覆盖整类**——
一旦某点被 cut，其整个轨道均被 cut 且不可行（`hCutClass`，这正是
原文"轨道 cut 是 G-不变集合的删除：删的是整个等价类"）。结论是
**类局部**的：任意可行点 `s₀` 的同轨道内存在满足序、未被 cut、
仍可行的代表——"未被 cut 删的类，其序代表仍存活"。 -/
theorem f5_compound_safety
    (equiv : σ → σ → Prop) (Feasible : σ → Prop) (Sel Cut : σ → Prop)
    (hrefl : ∀ s, equiv s s)
    (hPHOM : ∀ {s t}, equiv s t → (Feasible s ↔ Feasible t))
    (hSel : ∀ s, ∃ r, equiv s r ∧ Sel r)
    (hCutClass : ∀ c, Cut c → ∀ t, equiv c t → Cut t ∧ ¬ Feasible t)
    {s₀ : σ} (hs₀ : Feasible s₀) :
    ∃ r, equiv s₀ r ∧ Sel r ∧ ¬ Cut r ∧ Feasible r := by
  obtain ⟨r, hequiv, hsel⟩ := hSel s₀
  have hfr : Feasible r := (hPHOM hequiv).mp hs₀
  refine ⟨r, hequiv, hsel, ?_, hfr⟩
  intro hcut
  exact (hCutClass r hcut r (hrefl r)).2 hfr

/-- 弱化变体（外审定位澄清）：**这不是 orbit-lift soundness 的审计接口**；
它只消费已经另行复验为逐点 sound 的 cut（如 `anon_lift_sound` 的产物）
做组合，不检查"cut 删整类"这座桥。结论也不保留类局部信息。 -/
theorem f5_compound_safety_from_pointwise_sound
    (equiv : σ → σ → Prop) (Feasible : σ → Prop) (Sel Cut : σ → Prop)
    (hPHOM : ∀ {s t}, equiv s t → (Feasible s ↔ Feasible t))
    (hSel : ∀ s, ∃ r, equiv s r ∧ Sel r)
    (hcut_sound : ∀ s, Cut s → ¬ Feasible s)
    {s₀ : σ} (hs₀ : Feasible s₀) :
    ∃ r, Sel r ∧ ¬ Cut r ∧ Feasible r := by
  obtain ⟨r, hequiv, hsel⟩ := hSel s₀
  have hfr : Feasible r := (hPHOM hequiv).mp hs₀
  exact ⟨r, hsel, fun hc => hcut_sound r hc hfr, hfr⟩

/-- 反方向陷阱（F5 v1 §2.4 点名红测的忠实版；2026-07-05 外审修订）：
**P-HOM 完全成立、代表选择完备**，但 cut 读标签（非 G-不变：删同轨道的
代表元、不删其 mate）——序删掉非代表、cut 删掉唯一代表，组合删光
可行轨道 ⇒ false-INFEASIBLE。这才是原文"标签敏感 cut + 序 = 删光
合法类"。 -/
theorem f5_compound_needs_cut_invariance :
    ∃ (Feasible Sel Cut : Bool → Prop) (equiv : Bool → Bool → Prop),
      (∀ {s t : Bool}, equiv s t → (Feasible s ↔ Feasible t)) ∧
      (∀ s : Bool, ∃ r : Bool, equiv s r ∧ Sel r) ∧
      (∃ s t : Bool, equiv s t ∧ Cut s ∧ ¬ Cut t) ∧
      (∃ s : Bool, Feasible s) ∧
      ¬ ∃ r : Bool, Sel r ∧ ¬ Cut r ∧ Feasible r := by
  refine ⟨fun _ => True, fun b => b = true, fun b => b = true, fun _ _ => True,
    fun _ => Iff.rfl, fun _ => ⟨true, trivial, rfl⟩,
    ⟨true, false, trivial, rfl, by simp⟩, ⟨false, trivial⟩, ?_⟩
  rintro ⟨r, hsel, hnotcut, _⟩
  exact hnotcut hsel

/-- 相邻边界（**不是** v1 §2.4 点名的红测——那是上一条）：P-HOM 本身
也是复合安全的必要前提。可行性读标签（P-HOM 破缺）时，即使 cut
G-不变且由某真不可行点 lift 而来，复合仍删光合法类。与上一条合起来
说明 `f5_compound_safety` 的前提集里 P-HOM 与 cut 类不变性缺一不可。 -/
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

/-- 纯序支配引理（外审定位澄清：**本条不单独构成剪枝 soundness**——
它不建模 witness 的 certified 状态、也不绑定谓词/schema 固定；那些在
`frontier_prune_preserves_certified_argmax`）：任何候选都被「严格优于
w₀ 的幸存集 ∪ {w₀}」中某元素按 value 支配。 -/
theorem frontier_prune_dominates
    (F : Finset ι) (value : ι → β) {w₀ : ι} (_hw₀ : w₀ ∈ F) :
    ∀ c ∈ F, ∃ c' ∈ F.filter (fun c' => value w₀ < value c') ∪ {w₀},
      value c ≤ value c' := by
  intro c hc
  by_cases h : value c ≤ value w₀
  · exact ⟨w₀, Finset.mem_union_right _ (Finset.mem_singleton_self w₀), h⟩
  · exact ⟨c, Finset.mem_union_left _ (Finset.mem_filter.mpr ⟨hc, not_le.mp h⟩),
      le_refl _⟩

/-- 剪枝保**纯 objective value**（外审收窄：只保最大值，不保 certified
argmax witness——发布级 soundness 见 `frontier_prune_preserves_certified_argmax`；
且仅限固定谓词，谓词迁移场景见 `frontier_dominance_skip_not_migratable`）。 -/
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

/-- 剪枝保 **certified argmax witness**（2026-07-05 外审补强，发布级
形态）：前提显式要求 `w₀` 是当前谓词下的 certified witness、且当前
谓词下存在 certified 最优；结论：幸存集内仍存在一个 certified argmax。
仅限固定谓词——谓词变化时 dominance skip 不得继承（设计稿迁移规则）。 -/
theorem frontier_prune_preserves_certified_argmax
    (F : Finset ι) (value : ι → β) (Certified : ι → Prop)
    {w₀ : ι} (_hw₀ : w₀ ∈ F) (hw₀cert : Certified w₀)
    (hopt : ∃ c ∈ F, Certified c ∧ ∀ d ∈ F, Certified d → value d ≤ value c) :
    ∃ c' ∈ F.filter (fun c' => value w₀ < value c') ∪ {w₀},
      Certified c' ∧ ∀ d ∈ F, Certified d → value d ≤ value c' := by
  obtain ⟨c, hcF, hcCert, hcMax⟩ := hopt
  by_cases hle : value c ≤ value w₀
  · refine ⟨w₀, Finset.mem_union_right _ (Finset.mem_singleton_self w₀),
      hw₀cert, ?_⟩
    intro d hdF hdCert
    exact le_trans (hcMax d hdF hdCert) hle
  · exact ⟨c, Finset.mem_union_left _ (Finset.mem_filter.mpr ⟨hcF, not_le.mp hle⟩),
      hcCert, hcMax⟩

/-- 具体化到项目目标：`max_lex(area, min_side)` 的 certified-witness 版。 -/
theorem frontier_prune_preserves_certified_argmax_lex {ι : Type*} [DecidableEq ι]
    (F : Finset ι) (area minSide : ι → ℕ) (Certified : ι → Prop)
    {w₀ : ι} (hw₀ : w₀ ∈ F) (hw₀cert : Certified w₀)
    (hopt : ∃ c ∈ F, Certified c ∧ ∀ d ∈ F, Certified d →
        toLex (area d, minSide d) ≤ toLex (area c, minSide c)) :
    ∃ c' ∈ F.filter (fun c' =>
        toLex (area w₀, minSide w₀) < toLex (area c', minSide c')) ∪ {w₀},
      Certified c' ∧ ∀ d ∈ F, Certified d →
        toLex (area d, minSide d) ≤ toLex (area c', minSide c') :=
  frontier_prune_preserves_certified_argmax F
    (fun c => toLex (area c, minSide c)) Certified hw₀ hw₀cert hopt

/-- 具体化到项目目标：`max_lex(area, min_side)` 即 `β := ℕ ×ₗ ℕ` 的特例
（纯 value 版；发布级用上一条）。 -/
theorem frontier_prune_preserves_max_lex {ι : Type*} [DecidableEq ι]
    (F : Finset ι) (area minSide : ι → ℕ) {w₀ : ι} (hw₀ : w₀ ∈ F) :
    (F.filter (fun c' =>
        toLex (area w₀, minSide w₀) < toLex (area c', minSide c')) ∪ {w₀}).sup'
        ⟨w₀, Finset.mem_union_right _ (Finset.mem_singleton_self w₀)⟩
        (fun c => toLex (area c, minSide c))
      = F.sup' ⟨w₀, hw₀⟩ (fun c => toLex (area c, minSide c)) :=
  frontier_prune_preserves_max F (fun c => toLex (area c, minSide c)) hw₀

/-- 迁移红测（2026-07-05 外审补强，对应设计稿"谓词变化时 dominance skip
不得继承"）：旧谓词下由 witness 触发的剪枝，在收紧后的新谓词下可以把
**唯一的新可行候选**剪掉——skip 记录不可迁移的最小机器构造。 -/
theorem frontier_dominance_skip_not_migratable :
    ∃ (F : Finset Bool) (value : Bool → ℕ) (Old New : Bool → Prop) (w₀ : Bool),
      w₀ ∈ F ∧ Old w₀ ∧
      (∀ x, New x → Old x) ∧
      (∃ x ∈ F, New x) ∧
      (∀ x ∈ F.filter (fun c => value w₀ < value c) ∪ {w₀}, ¬ New x) := by
  refine ⟨{false, true}, fun b => if b then 100 else 90,
    fun _ => True, fun b => b = false, true,
    by decide, trivial, fun _ _ => trivial, ⟨false, by decide, rfl⟩, ?_⟩
  intro x hx
  have : x = true := by
    rcases Finset.mem_union.mp hx with h | h
    · have hm := Finset.mem_filter.mp h
      rcases Finset.mem_insert.mp hm.1 with h' | h'
      · subst h'; simp at hm
      · exact Finset.mem_singleton.mp h'
    · exact Finset.mem_singleton.mp h
  subst this
  simp

end FrontierPrune

/-! ## TP7-S selected-solution nogood 等式键边界 -/

section Tp7sNogood

variable {V : Type*} [DecidableEq V]

/-- 完整 0/1 等式键 `Σ_{x∈S1}(1−x) + Σ_{x∈S0}x ≥ 1` 的**违反**条件
（2026-07-05 外审硬化：全集约束 `A ⊆ U`、`S ⊆ U` 内置进 def——否则
携带 U 外变量的 A 会让违反条件成立而 `A ≠ S`，def 单独被使用时是
foot-gun）。 -/
def EqKeyViolated (U S A : Finset V) : Prop :=
  A ⊆ U ∧ S ⊆ U ∧ (∀ x ∈ S, x ∈ A) ∧ (∀ x ∈ U \ S, x ∉ A)

/-- 等式键排除集刻画：等式键恰好排除 `A = S` 这一个赋值（完整赋值空间
= `A ⊆ U` 的 Finset 表示：`x ∈ A` 为真、`x ∈ U \ A` 为假）。 -/
theorem eq_key_violated_iff {U S A : Finset V} :
    EqKeyViolated U S A ↔ S ⊆ U ∧ A = S := by
  constructor
  · rintro ⟨hAU, hSU, h1, h0⟩
    refine ⟨hSU, ?_⟩
    ext x
    constructor
    · intro hxA
      by_contra hxS
      exact h0 x (Finset.mem_sdiff.mpr ⟨hAU hxA, hxS⟩) hxA
    · exact h1 x
  · rintro ⟨hSU, rfl⟩
    exact ⟨hSU, hSU, fun _ hx => hx, fun x hx => (Finset.mem_sdiff.mp hx).2⟩

/-- 等式键 sound：Farkas 证明了赋值 S 不可行 ⇒ 等式键排除的全部赋值不可行
（排除集被证据完全覆盖，无 false-INFEASIBLE）。调用方义务：`U` 必须是
完整 key 全集（binding choice / slot assignment / route use-vars + 语法版本）。 -/
theorem tp7s_eq_key_sound {U S : Finset V}
    (Feasible : Finset V → Prop) (hS : ¬ Feasible S) :
    ∀ A, EqKeyViolated U S A → ¬ Feasible A := by
  intro A hviol
  have hEq : A = S := (eq_key_violated_iff.mp hviol).2
  rwa [hEq]

/-- 等式键不过切：**U 内的**真超集不触发等式键——要排除超集必须另有
独立 exact-rational 证明（稿 v3 回退循环第 2 条）。U 外变量不属于
键空间，"超集"必须在完整赋值空间内理解。 -/
theorem tp7s_eq_key_no_overcut {U S A : Finset V}
    (hss : S ⊂ A) : ¬ EqKeyViolated U S A := by
  intro hviol
  exact hss.ne ((eq_key_violated_iff.mp hviol).2).symm

/-- 选中集式 nogood `∨_{x∈S} ¬x` 的**违反**条件：S 全被选中。 -/
def SelectedSetNogoodViolated (S A : Finset V) : Prop :=
  S ⊆ A

/-- 选中集式 nogood 过切反例（2026-07-05 外审语义化：显式容量/需求
结构——需求 2、每条并行路容量 1；单路 S 不满足需求，双路 A 满足；
但选中集式 nogood 因 `S ⊆ A` 把可行的 A 一并错剪 = false-INFEASIBLE。
即稿 v3"一条半容量路不够、加一条并行路就够"玩具例的机器版）。 -/
theorem tp7s_selected_set_nogood_overcuts :
    ∃ (cap : Bool → ℕ) (demand : ℕ)
      (Feasible : Finset Bool → Prop) (S A : Finset Bool),
      (∀ X, Feasible X ↔ demand ≤ X.sum cap) ∧
      ¬ Feasible S ∧
      SelectedSetNogoodViolated S A ∧
      Feasible A := by
  refine ⟨fun _ => 1, 2, fun X => 2 ≤ X.sum (fun _ => 1),
    {false}, {false, true}, fun _ => Iff.rfl, ?_, ?_, ?_⟩
  · decide
  · show ({false} : Finset Bool) ⊆ {false, true}
    decide
  · decide

end Tp7sNogood

end ZmdFormal.Framework
