import Endfield.«证明».«基础»

/-!
# 存货物品格至多符合一条配方

每格至多一堆货，所以存货里的物品种数受格数限制。够开工的配方所需的原料
都已在格中，而且恰有这么多种。因此凡是已在格中的物品都是这条配方的原料，
其余够开工的配方也只能用这些原料，再由配方表的唯一性得证。
-/

namespace Endfield.«证明»

private def «存货各格» (s : «状态») (k : «制造单位») (u : «单位号») : List (List «一堆») :=
  (List.range k.«存货物品格数»).map fun i => s.«货» ⟨u, .«存货» i⟩

private def «存货物品» (s : «状态») (k : «制造单位») (u : «单位号») : List «物品» :=
  («存货各格» s k u).flatMap fun l => l.map (·.«物»)

private theorem «各格至多一堆则物品表不长于格表» (slots : List (List «一堆»))
    (h : slots.all («一格合规矩» 50) = true) :
    (slots.flatMap fun l => l.map (·.«物»)).length ≤ slots.length := by
  induction slots with
  | nil => simp
  | cons l slots ih =>
    have ⟨hl, ht⟩ := Bool.and_eq_true_iff.mp h
    have hlength : l.length ≤ 1 := by
      cases l with
      | nil => simp
      | cons p tail =>
        cases tail with
        | nil => simp
        | cons q rest => simp [«一格合规矩»] at hl
    have htail := ih ht
    simp only [List.flatMap_cons, List.length_append, List.length_map, List.length_cons]
    omega

private theorem «存货物品表不长于格数» (s : «状态») (k : «制造单位») (u : «单位号»)
    (hrules : s.«货合规矩») (hkind : s.«布局».«种类» u = some (.«制造» k)) :
    («存货物品» s k u).length ≤ k.«存货物品格数» := by
  obtain ⟨p, hp, hk⟩ := Option.map_eq_some_iff.mp hkind
  have hu : p.1 = u := by simpa using List.find?_some hp
  have heq : p = (u, «单位种类».«制造» k) := Prod.ext hu hk
  have hmem : (u, «单位种类».«制造» k) ∈ s.«布局».«单位表» :=
    heq ▸ List.mem_of_find?_eq_some hp
  have hall := List.all_eq_true.mp hrules.1 _ hmem
  obtain ⟨hgoods, _⟩ := Bool.and_eq_true_iff.mp hall
  obtain ⟨hslotGoods, _⟩ := Bool.and_eq_true_iff.mp hgoods
  have hslots : («存货各格» s k u).all («一格合规矩» 50) = true :=
    (Bool.and_eq_true_iff.mp hslotGoods).1
  simpa [«存货物品», «存货各格»] using «各格至多一堆则物品表不长于格表» _ hslots

private theorem «存货有件数则物品在格中» (s : «状态») (k : «制造单位») (u : «单位号»)
    (x : «物品») (h : 0 < s.«存货件数» k u x) : x ∈ «存货物品» s k u := by
  unfold «状态».«存货件数» at h
  rw [← List.sum_eq_foldl_nat] at h
  obtain ⟨n, hn, hpos⟩ := List.sum_pos_iff_exists_pos_nat.mp h
  obtain ⟨i, hi, rfl⟩ := List.mem_map.mp hn
  have hnonempty : (s.«货» ⟨u, .«存货» i⟩).filter (·.«物» == x) ≠ [] := by
    intro hempty
    simp [«状态».«件数», hempty] at hpos
  obtain ⟨p, hp⟩ := List.exists_mem_of_ne_nil _ hnonempty
  obtain ⟨hpile, hx⟩ := List.mem_filter.mp hp
  have heq : p.«物» = x := beq_iff_eq.mp hx
  apply List.mem_flatMap.mpr
  exact ⟨_, List.mem_map.mpr ⟨i, hi, rfl⟩, List.mem_map.mpr ⟨p, hpile, heq⟩⟩

private theorem «配方用量为正» :
    ∀ r ∈ «配方表», ∀ p ∈ r.«原料», 0 < p.2 := by decide

private theorem «够用的原料都在存货中» (s : «状态») (k : «制造单位») (u : «单位号»)
    {r : «配方»} (hr : r ∈ «配方表»)
    (h : (r.«原料».all fun p => s.«存货件数» k u p.1 ≥ p.2) = true) :
    r.«原料种类» ⊆ «存货物品» s k u := by
  intro x hx
  obtain ⟨p, hp, rfl⟩ := List.mem_map.mp hx
  have hcount : p.2 ≤ s.«存货件数» k u p.1 := of_decide_eq_true (List.all_eq_true.mp h p hp)
  exact «存货有件数则物品在格中» s k u p.1 (Nat.lt_of_lt_of_le («配方用量为正» r hr p hp) hcount)

private theorem «够用的原料涵盖存货» (s : «状态») (k : «制造单位») (u : «单位号»)
    {r : «配方»} (hr : r ∈ «配方表») (hk : r.«单位» = k)
    (hbound : («存货物品» s k u).length ≤ k.«存货物品格数»)
    (hsub : r.«原料种类» ⊆ «存货物品» s k u) :
    «存货物品» s k u ⊆ r.«原料种类» := by
  obtain ⟨hlen, hnodup⟩ := «原料种数等于存货物品格数» r hr
  have hsize : r.«原料种类».length = k.«存货物品格数» := by
    simpa [«配方».«原料种类», hk] using hlen
  intro x hx
  apply Classical.byContradiction
  intro hmissing
  have hmore : (x :: r.«原料种类»).Nodup := List.nodup_cons.mpr ⟨hmissing, hnodup⟩
  have hmoreSub : x :: r.«原料种类» ⊆ «存货物品» s k u := by
    intro y hy
    rcases List.mem_cons.mp hy with rfl | hy
    · exact hx
    · exact hsub hy
  have hlong := hmore.length_le_of_subset hmoreSub
  simp only [List.length_cons] at hlong
  omega

private theorem «配方表无重复» : «配方表».Nodup := by decide

/-- 据：制造、存货/取货物品格

货合规矩时，一台制造单位的存货物品格至多能凑齐该种单位的一条配方的一次用量。 -/
theorem «存货物品格至多符合一条配方» : «命题».«存货物品格至多符合一条配方» := by
  intro s k u hrules hkind
  have hbound := «存货物品表不长于格数» s k u hrules hkind
  let fits : «配方» → Bool := fun r =>
    r.«单位» == k && r.«原料».all fun p => s.«存货件数» k u p.1 ≥ p.2
  change («配方表».filter fits).length ≤ 1
  have hsame : ∀ a ∈ «配方表».filter fits, ∀ b ∈ «配方表».filter fits, a = b := by
    intro a ha b hb
    obtain ⟨ha, hfa⟩ := List.mem_filter.mp ha
    obtain ⟨hb, hfb⟩ := List.mem_filter.mp hb
    obtain ⟨hka, hra⟩ := Bool.and_eq_true_iff.mp hfa
    obtain ⟨hkb, hrb⟩ := Bool.and_eq_true_iff.mp hfb
    have hka : a.«单位» = k := beq_iff_eq.mp hka
    have hkb : b.«单位» = k := beq_iff_eq.mp hkb
    have hsuba := «够用的原料都在存货中» s k u ha hra
    have hsubb := «够用的原料都在存货中» s k u hb hrb
    have hcover := «够用的原料涵盖存货» s k u hb hkb hbound hsubb
    exact «符合的配方至多一条» a ha b hb (hka.trans hkb.symm) (fun _ hx => hcover (hsuba hx))
  have hnodup := «配方表无重复».sublist (List.filter_sublist (p := fits))
  generalize «配方表».filter fits = eligible at hsame hnodup ⊢
  cases eligible with
  | nil => simp
  | cons a tail =>
    have hnoa := (List.nodup_cons.mp hnodup).1
    cases tail with
    | nil => simp
    | cons b rest =>
      have heq : a = b := hsame a (by simp) b (by simp)
      exact (hnoa (heq ▸ List.mem_cons_self)).elim

end Endfield.«证明»
