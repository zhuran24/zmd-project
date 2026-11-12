import Endfield.«证明».«基础»

/-!
证明组的时刻不同、级别不并列和按级别排不看先后。
每次事件至多使一个组开始有通道，故组的时刻唯一；级别继承这个唯一性。
最后利用排序的有序性及排列保持性证明排序结果唯一。
-/

namespace Endfield.«证明»

private theorem group_mem (L : «布局») (g : «组») (p : «通道» × «时刻») :
    p ∈ L.«组的通道» g ↔ p ∈ L.«通道表» ∧ L.«所在组» p.1 = some g := by
  simp [«布局».«组的通道»]

private theorem group_nonempty (L : «布局») (g : «组») :
    (!(L.«组的通道» g).isEmpty) = true ↔ ∃ p, p ∈ L.«通道表» ∧ L.«所在组» p.1 = some g := by
  simp only [Bool.not_eq_true', List.isEmpty_eq_false_iff_exists_mem, group_mem]

private theorem group_congr (L M : «布局») (c : «通道»)
    (ha : L.«种类» c.«起» = M.«种类» c.«起»)
    (hb : L.«种类» c.«止» = M.«种类» c.«止») :
    L.«所在组» c = M.«所在组» c := by
  simp only [«布局».«所在组», ha, hb]

private theorem new_group (L : «布局») (t : «时刻») (e : «事件») (g : «组»)
    (hr : L.«整齐») (he : L.«容得下» e = true)
    (hnew : (!((L.«加» t e).«组的通道» g).isEmpty) = true)
    (hold : (!(L.«组的通道» g).isEmpty) = false) :
    ∃ c, e = .«接通» c ∧ (L.«加» t e).«所在组» c = some g := by
  obtain ⟨p, hp, hg⟩ := (group_nonempty _ _).mp hnew
  have old_absent : ∀ p ∈ L.«通道表», L.«所在组» p.1 ≠ some g := by
    intro p hp hg
    have := (group_nonempty L g).mpr ⟨p, hp, hg⟩
    simp_all
  cases e with
  | «建成» u k =>
    have hu : L.«种类» u = none := by
      simp only [«布局».«容得下», Bool.and_eq_true, Option.isNone_iff_eq_none] at he
      exact he.1
    change p ∈ L.«通道表» at hp
    obtain ⟨ha, hb⟩ := hr.«两头都在» p hp
    have hne₁ : p.1.«起» ≠ u := by intro h; simp_all
    have hne₂ : p.1.«止» ≠ u := by intro h; simp_all
    have hc := group_congr (L.«加» t (.«建成» u k)) L p.1
      (by simp [«布局».«加建成_种类», hu, hne₁])
      (by simp [«布局».«加建成_种类», hu, hne₂])
    exact False.elim (old_absent p hp (hc ▸ hg))
  | «拆除» u =>
    simp only [«布局».«加», List.mem_filter, Bool.and_eq_true, bne_iff_ne] at hp
    have hc := group_congr (L.«加» t (.«拆除» u)) L p.1
      (by simp [«布局».«加拆除_种类», hp.2.1])
      (by simp [«布局».«加拆除_种类», hp.2.2])
    exact False.elim (old_absent p hp.1 (hc ▸ hg))
  | «接通» c =>
    simp only [«布局».«加», List.mem_append, List.mem_singleton] at hp
    rcases hp with hp | hp
    · have hc := group_congr (L.«加» t (.«接通» c)) L p.1 rfl rfl
      exact False.elim (old_absent p hp (hc ▸ hg))
    · subst p; exact ⟨c, rfl, hg⟩

private theorem born (H : «历史») (hH : H.«合规» = true) (g : «组») (t : «时刻»)
    (ht : H.«组的时刻» H.length g = some t) :
    ∃ c, H[t-1]? = some (.«接通» c) ∧ (H.«布局于» t).«所在组» c = some g := by
  unfold «时刻» at *
  obtain ⟨hle, hall, hb⟩ := «最近一次变成_spec» _ _ _ ht
  have hon := hall t (Nat.le_refl _) hle
  have ht0 : t ≠ 0 := by
    intro hz; subst t
    simp [«历史».«布局于零», «布局».«组的通道»] at hon
  have hoff : (!((H.«布局于» (t-1)).«组的通道» g).isEmpty) = false := hb.resolve_left ht0
  change t ≤ H.length at hle
  have hidx : t - 1 < H.length := by omega
  let e := H[t-1]
  have he : H[t-1]? = some e := List.getElem?_eq_some_iff.mpr ⟨hidx, rfl⟩
  have hstep := «历史».«布局于后继» H (t-1) e he
  have hsub : t - 1 + 1 = t := by omega
  rw [hsub] at hstep
  obtain ⟨c, hec, hc⟩ := new_group (H.«布局于» (t-1)) t e g
    («历史».«合规则整齐» H hH _) ((«历史».«合规_iff» H).mp hH _ _ he)
    (by simpa [hstep] using hon) hoff
  exact ⟨c, he.trans (congrArg some hec), by simpa [hstep] using hc⟩

/-- 据：组的时刻、组、接通

不同的组不在同一刻开始有通道。 -/
theorem «组的时刻不同» : «命题».«组的时刻不同» := by
  intro H g₁ g₂ t hH hne h₁ h₂
  obtain ⟨c, hc, hg⟩ := born H hH g₁ t h₁
  obtain ⟨d, hd, hh⟩ := born H hH g₂ t h₂
  have : c = d := by simpa [hc] using hd
  subst d
  exact hne (Option.some.inj (hg.symm.trans hh))

private theorem level_time (H : «历史») (now : «时刻») (g : «组»)
    (a : Nat × «时刻») (h : H.«级别» now g = some a) :
    H.«组的时刻» now g = some a.2 := by
  unfold «历史».«级别» at h
  split at h <;> (repeat' split at h) <;> simp_all <;> grind

/-- 据：级别、组的时刻

级别的时刻分量使不同组的级别不能相同。 -/
theorem «级别不并列» : «命题».«级别不并列» := by
  intro H g₁ g₂ a hH hne h₁ h₂
  exact «组的时刻不同» H g₁ g₂ a.2 hH hne
    (level_time H _ _ _ h₁) (level_time H _ _ _ h₂)

private def cmp (a b : «组» × (Nat × «时刻»)) : Bool :=
  !«历史».«级别高于» b.2 a.2

private theorem cmp_iff (a b : «组» × (Nat × «时刻»)) :
    cmp a b = true ↔ a.2.1 < b.2.1 ∨ (a.2.1 = b.2.1 ∧ a.2.2 ≤ b.2.2) := by
  unfold «时刻» at *
  simp [cmp, «历史».«级别高于»]
  omega

private theorem cmp_trans (a b c : «组» × (Nat × «时刻»)) :
    cmp a b = true → cmp b c = true → cmp a c = true := by
  unfold «时刻» at *
  simp only [cmp_iff]
  simp_all only [«时刻»]
  omega

private theorem cmp_total (a b : «组» × (Nat × «时刻»)) :
    (cmp a b || cmp b a) = true := by
  unfold «时刻» at *
  simp only [Bool.or_eq_true, cmp_iff]
  simp_all only [«时刻»]
  omega

/-- 据：判定顺序、级别

有级别的组按严格区分各组的级别排序，排列输入不会改变结果。 -/
theorem «按级别排不看先后» : «命题».«按级别排不看先后» := by
  intro H gs gs' hH hp
  let f := fun g => (H.«级别» H.length g).map fun lv => (g, lv)
  have hperm := hp.filterMap f
  have sorted_eq : (gs.filterMap f).mergeSort cmp = (gs'.filterMap f).mergeSort cmp := by
    apply List.Perm.eq_of_pairwise (le := fun a b => cmp a b = true)
    · intro a b ha hb hab hba
      have ha' := (List.mem_mergeSort.mp ha)
      have hb' := (List.mem_mergeSort.mp hb)
      obtain ⟨ga, _, hga⟩ := List.mem_filterMap.mp ha'
      obtain ⟨gb, _, hgb⟩ := List.mem_filterMap.mp hb'
      obtain ⟨la, hla, hea⟩ := Option.map_eq_some_iff.mp hga
      obtain ⟨lb, hlb, heb⟩ := Option.map_eq_some_iff.mp hgb
      have hv : a.2 = b.2 := by
        have hab' := (cmp_iff a b).mp hab
        have hba' := (cmp_iff b a).mp hba
        unfold «时刻» at *
        apply Prod.ext <;> omega
      have hga' : H.«级别» H.length a.1 = some a.2 := by
        cases hea; exact hla
      have hgb' : H.«级别» H.length b.1 = some b.2 := by
        cases heb; exact hlb
      have hg : a.1 = b.1 := by
        apply Classical.byContradiction
        intro hne
        exact «级别不并列» H a.1 b.1 a.2 hH hne hga' (hv ▸ hgb')
      exact Prod.ext hg hv
    · exact List.pairwise_mergeSort cmp_trans cmp_total _
    · exact List.pairwise_mergeSort cmp_trans cmp_total _
    · exact (List.mergeSort_perm _ _).trans (hperm.trans (List.mergeSort_perm _ _).symm)
  exact congrArg (List.map fun p => (p.1, ((H.«布局于» H.length).«组的通道» p.1).map (·.1))) sorted_eq

end Endfield.«证明»
