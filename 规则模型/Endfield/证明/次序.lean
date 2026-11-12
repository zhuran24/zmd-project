import Endfield.«证明».«基础»

/-!
证明末端元件有终点、同组次序相同。
端口数限制使非分流器运输单位的出口唯一。同组通道若不出自同一分流器，
便通往同一个单位；其运输带除第一个元件外一致，故终点和长度一致。
-/

namespace Endfield.«证明»

private theorem component_kind (L : «布局») (e : «单位号»)
    (h : e ∈ L.«元件») : ∃ k, L.«种类» e = some k ∧ k.«是运输单位» = true := by
  have hh : L.«所在元件» 1 e = some e := by
    simpa [«布局».«元件»] using (List.mem_filter.mp h).2
  cases hk : L.«种类» e with
  | none => simp [«布局».«所在元件», hk] at hh
  | some k =>
    refine ⟨k, rfl, ?_⟩
    cases k <;> simp_all [«布局».«所在元件», «单位种类».«是运输单位»]

private theorem one_port (k : «单位种类») (h : k.«是运输单位» = true)
    (hn : k ≠ .«分流器») : k.«取货端口数» = 1 := by
  cases k <;> simp_all [«单位种类».«是运输单位», «单位种类».«取货端口数»]

/-- 据：终点、运输带、端口

端口数合的布局中，每个末端元件都能确定终点。
-/
theorem «末端元件有终点» : «命题».«末端元件有终点» := by
  intro L e hp he
  have he' := he
  simp only [«布局».«是末端元件», Bool.and_eq_true] at he'
  have hm : e ∈ L.«元件» := by simpa using he'.1.1
  obtain ⟨k, hk, ht⟩ := component_kind L e hm
  by_cases hs : k = .«分流器»
  · simp [«布局».«终点», he, hk, hs]
  · have hl := L.«端口数合_出» e k hp hk
    rw [one_port k ht hs] at hl
    have hn : (L.«出» e).isEmpty = false := by simpa using he'.1.2
    cases ho : L.«出» e with
    | nil => simp [ho] at hn
    | cons p ps =>
      have hz : ps = [] := by simpa [ho] using hl
      simp [«布局».«终点», he, hk, hs, ho, hz]

private theorem group_split (L : «布局») (c : «通道») (s : «单位号»)
    (h : L.«所在组» c = some (.«分流器的» s)) : c.«起» = s := by
  unfold «布局».«所在组» at h
  cases ha : L.«种类» c.«起» <;> cases hb : L.«种类» c.«止» <;> simp_all
  split at h <;> simp_all
  split at h <;> simp_all
  split at h <;> simp_all

private theorem group_in (L : «布局») (c : «通道») (t : «单位号»)
    (h : L.«所在组» c = some (.«进同一个的» t)) :
    c.«止» = t ∧ ∃ k, L.«种类» c.«起» = some k ∧ k.«是运输单位» = true ∧
      k ≠ .«分流器» ∧ (k = .«传送带» → L.«种类» t ≠ some .«传送带») := by
  unfold «布局».«所在组» at h
  cases ha : L.«种类» c.«起» with
  | none => simp_all
  | some a =>
    cases hb : L.«种类» c.«止» with
    | none => simp_all
    | some b =>
      cases a <;> cases b <;>
        simp_all [«单位种类».«是运输单位»]

private theorem source_data (L : «布局») (p : «通道» × «时刻») (t : «单位号»)
    (hp : L.«端口数合» = true) (hm : p ∈ L.«通道表»)
    (hg : L.«所在组» p.1 = some (.«进同一个的» t)) :
    L.«出» p.1.«起» = [p] ∧
    L.«是末端元件» p.1.«起» = L.«是非运输单位» t ∧
    (L.«是非运输单位» t = true → L.«终点» p.1.«起» = some t) := by
  obtain ⟨hst, k, hk, hkt, hks, hkb⟩ := group_in L p.1 t hg
  have hl := L.«端口数合_出» p.1.«起» k hp hk
  rw [one_port k hkt hks] at hl
  have hmem : p ∈ L.«出» p.1.«起» := by simp [«布局».«出», hm]
  have ho : L.«出» p.1.«起» = [p] := by
    cases he : L.«出» p.1.«起» with
    | nil => simp_all
    | cons a as =>
      have hz : as = [] := by simpa [he] using hl
      simp_all
  have hb : p.1.«起» ∈ L.«建成先后» := by
    unfold «布局».«种类» at hk
    obtain ⟨v, hv, _⟩ := Option.map_eq_some_iff.mp hk
    have he := List.find?_some hv
    have hv' := List.mem_of_find?_eq_some hv
    simp only [beq_iff_eq] at he
    exact List.mem_map.mpr ⟨v, hv', he⟩
  have hc : L.«所在元件» 1 p.1.«起» = some p.1.«起» := by
    have hnb := hkb
    cases k <;> simp_all [«布局».«所在元件», «单位种类».«是运输单位»]
  have hcomp : p.1.«起» ∈ L.«元件» := by simp [«布局».«元件», hb, hc]
  have ht : L.«是末端元件» p.1.«起» = L.«是非运输单位» t := by
    simp [«布局».«是末端元件», hcomp, ho, hst]
  refine ⟨ho, ht, ?_⟩
  intro hn
  simp [«布局».«终点», ht, hn, hk, hks, ho, hst]

private theorem paths_nonempty (L : «布局») (n e : Nat) :
    ∀ P ∈ L.«运输带从» n e, P ≠ [] := by
  cases n with
  | zero => simp [«布局».«运输带从»]
  | succ n =>
    intro P hp
    simp only [«布局».«运输带从»] at hp
    split at hp
    · simp_all
    · obtain ⟨f, _, hq⟩ := List.mem_flatMap.mp hp
      obtain ⟨Q, _, rfl⟩ := List.mem_map.mp hq
      simp

private theorem filterMap_congr_on {α β : Type} (xs : List α) (f g : α → Option β)
    (h : ∀ x ∈ xs, f x = g x) : xs.filterMap f = xs.filterMap g := by
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    simp only [List.filterMap_cons, h x (by simp)]
    rw [ih (by intro y hy; exact h y (by simp [hy]))]

private theorem candidates_equal (H : «历史») (now n : Nat)
    (p q : «通道» × «时刻») (t : «单位号»)
    (hp : (H.«布局于» now).«端口数合» = true)
    (hpm : p ∈ (H.«布局于» now).«通道表»)
    (hqm : q ∈ (H.«布局于» now).«通道表»)
    (hpg : (H.«布局于» now).«所在组» p.1 = some (.«进同一个的» t))
    (hqg : (H.«布局于» now).«所在组» q.1 = some (.«进同一个的» t)) :
    let L := H.«布局于» now
    let ev := fun (P : List «单位号») =>
      ((P.getLast?.bind L.«终点»).bind (H.«终点的时刻» now)).map fun t => (t, P.length)
    (L.«运输带从» (n+1) p.1.«起»).filterMap ev =
      (L.«运输带从» (n+1) q.1.«起»).filterMap ev := by
  dsimp only
  let L := H.«布局于» now
  obtain ⟨hop, htp, hep⟩ := source_data L p t hp hpm hpg
  obtain ⟨hoq, htq, heq⟩ := source_data L q t hp hqm hqg
  let ev := fun (P : List «单位号») =>
    ((P.getLast?.bind L.«终点»).bind (H.«终点的时刻» now)).map fun t => (t, P.length)
  change (L.«运输带从» (n+1) p.1.«起»).filterMap ev =
    (L.«运输带从» (n+1) q.1.«起»).filterMap ev
  by_cases hn : L.«是非运输单位» t = true
  · simp [«布局».«运输带从», htp, htq, hn, ev, List.filterMap_cons, hep hn, heq hn]
  · have hdown : L.«下游元件» p.1.«起» = L.«下游元件» q.1.«起» := by
      have hsp := (group_in L p.1 t hpg).1
      have hsq := (group_in L q.1 t hqg).1
      simp [«布局».«下游元件», hop, hoq, List.filterMap_cons, hsp, hsq]
    simp only [«布局».«运输带从», htp, htq, hn, Bool.false_eq_true, ↓reduceIte,
      List.filterMap_flatMap, List.filterMap_map]
    rw [hdown]
    congr 1
    funext f
    apply filterMap_congr_on
    intro P hP
    have hne := paths_nonempty L n f P hP
    simp only [Function.comp_apply, ev, List.getLast?_cons_of_ne_nil hne, List.length_cons]

/-- 据：级别、次序、组

元件的同一组内，各条通道的起点次序相同。
-/
theorem «同组次序相同» : «命题».«同组次序相同» := by
  intro H g hp hg p hpm q hqm
  have hpg : (H.«布局于» H.length).«所在组» p.1 = some g := by
    simpa [«布局».«组的通道»] using (List.mem_filter.mp hpm).2
  have hqg : (H.«布局于» H.length).«所在组» q.1 = some g := by
    simpa [«布局».«组的通道»] using (List.mem_filter.mp hqm).2
  cases g with
  | «分流器的» s =>
    rw [group_split _ _ _ hpg, group_split _ _ _ hqg]
  | «进同一个的» t =>
    have he := candidates_equal H H.length (H.«布局于» H.length).«单位表».length p q t hp
      (List.mem_filter.mp hpm).1 (List.mem_filter.mp hqm).1 hpg hqg
    unfold «历史».«次序»
    dsimp only at he ⊢
    rw [he]
  | «出货的» u => simp [«组».«是元件的»] at hg
  | «进汇流器的» c => simp [«组».«是元件的»] at hg

end Endfield.«证明»
