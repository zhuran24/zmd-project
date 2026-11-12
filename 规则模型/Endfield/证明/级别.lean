import Endfield.«证明».«基础»

/-!
证明合法基地上的每个组都有级别。先沿运输带找到末端，证明次序有值；
再逐条检查组内通道，用同组次序相同保证元件组的级别有值。
-/

namespace Endfield.«证明»

private theorem terminal_time (H : «历史») (now e x : Nat)
    (he : (H.«布局于» now).«是末端元件» e = true)
    (hx : (H.«布局于» now).«终点» e = some x) :
    (H.«终点的时刻» now x).isSome = true := by
  let L := H.«布局于» now
  change L.«是末端元件» e = true at he
  change L.«终点» e = some x at hx
  have he' : e ∈ L.«元件» ∧ (L.«出» e).isEmpty = false ∧
      (L.«出» e).all (fun p => L.«是非运输单位» p.1.«止») = true := by
    simpa [«布局».«是末端元件», Bool.and_eq_true, and_assoc] using he
  obtain ⟨hm, hn, ha⟩ := he'
  have ht : L.«是终点» x = true := by
    apply List.any_eq_true.mpr
    exact ⟨e, hm, by simp [hx]⟩
  have hh : L.«种类» x = some .«分流器» →
      (L.«出» x).any (fun p => L.«是非运输单位» p.1.«止») = true := by
    intro hk
    by_cases hs : L.«种类» e = some .«分流器»
    · have ex : e = x := by simpa [«布局».«终点», he, hs] using hx
      subst x
      cases ho : L.«出» e with
      | nil => simp [ho] at hn
      | cons p ps =>
        apply List.any_eq_true.mpr
        exact ⟨p, by simp, List.all_eq_true.mp ha p (by simp [ho])⟩
    · have ho : ∃ p, L.«出» e = [p] ∧ p.1.«止» = x := by
        simp only [«布局».«终点», he, Bool.not_true, Bool.false_eq_true,
          ↓reduceIte, beq_iff_eq, hs] at hx
        split at hx
        · exact ⟨_, by assumption, Option.some.inj hx⟩
        · contradiction
      obtain ⟨p, hp, hpx⟩ := ho
      have := List.all_eq_true.mp ha p (by simp [hp])
      simp [«布局».«是非运输单位», hpx, hk, «单位种类».«是运输单位»] at this
  unfold «历史».«终点的时刻»
  change (if !L.«是终点» x then none else if L.«种类» x == some .«分流器» then _ else _).isSome = true
  simp only [ht, Bool.not_true, Bool.false_eq_true, ↓reduceIte]
  split
  · rw [«最近一次变成_isSome»]
    exact hh (by simpa using ‹(L.«种类» x == some .«分流器») = true›)
  · rw [«最近一次变成_isSome»]
    exact ht

private theorem path_last (L : «布局») (fuel e : Nat) (P : List Nat)
    (hp : P ∈ L.«运输带从» fuel e) :
    ∃ z, P.getLast? = some z ∧ L.«是末端元件» z = true := by
  induction fuel generalizing e P with
  | zero => simp [«布局».«运输带从»] at hp
  | succ fuel ih =>
    simp only [«布局».«运输带从»] at hp
    split at hp
    · simp only [List.mem_singleton] at hp
      subst P
      exact ⟨e, rfl, by assumption⟩
    · obtain ⟨f, _, hf⟩ := List.mem_flatMap.mp hp
      obtain ⟨Q, hQ, rfl⟩ := List.mem_map.mp hf
      obtain ⟨z, hz, ht⟩ := ih f Q hQ
      refine ⟨z, ?_, ht⟩
      cases Q <;> simp_all

private theorem order_some («h终点» : «命题».«末端元件有终点»)
    (H : «历史») (now e : Nat)
    (hport : (H.«布局于» now).«端口数合» = true)
    (hpath : (H.«布局于» now).«运输带从» ((H.«布局于» now).«单位表».length + 1) e ≠ []) :
    (H.«次序» now e).isSome = true := by
  let L := H.«布局于» now
  obtain ⟨P, hp⟩ := List.exists_mem_of_ne_nil _ hpath
  obtain ⟨z, hz, ht⟩ := path_last L _ e P hp
  obtain ⟨x, hx⟩ := Option.isSome_iff_exists.mp («h终点» L z hport ht)
  obtain ⟨t, htime⟩ := Option.isSome_iff_exists.mp (terminal_time H now z x ht hx)
  have hm : (t, P.length) ∈ (L.«运输带从» (L.«单位表».length + 1) e).filterMap
      (fun P => ((P.getLast?.bind L.«终点»).bind (H.«终点的时刻» now)).map fun t => (t, P.length)) := by
    apply List.mem_filterMap.mpr
    exact ⟨P, hp, by simp [hz, hx, htime]⟩
  unfold «历史».«次序»
  dsimp only
  split
  · rename_i hh
    change (L.«运输带从» (L.«单位表».length + 1) e).filterMap _ = [] at hh
    rw [hh] at hm
    contradiction
  · rfl

private theorem walk (L : «布局») (hw : L.«走得通» = true) (u : Nat)
    (hu : L.«是运输单位» u = true)
    (hc : L.«进» u ≠ [] ∨ L.«出» u ≠ []) :
    ∃ e, L.«所在元件» (L.«单位表».length + 1) u = some e ∧
      L.«运输带从» (L.«单位表».length + 1) e ≠ [] := by
  have hconnected : ((L.«进» u).isEmpty && (L.«出» u).isEmpty) = false := by
    rcases hc with hi | ho
    · simp [hi]
    · simp [ho]
  unfold «布局».«是运输单位» at hu
  cases hk : L.«种类» u with
  | none => simp [hk] at hu
  | some k =>
    obtain ⟨p, hp, hpk⟩ := Option.map_eq_some_iff.mp hk
    have hm := List.mem_of_find?_eq_some hp
    have he : p.1 = u := by simpa using List.find?_some hp
    have hh := List.all_eq_true.mp hw p hm
    simp only [«布局».«走得通»] at hw
    simp only [hk] at hu
    simp only [hpk, hu, Bool.not_true, Bool.false_or, he, hconnected] at hh
    split at hh
    · exact ⟨_, by assumption, by simpa using hh⟩
    · contradiction

private theorem group_source (L : «布局») (hport : L.«端口数合» = true)
    (g : «组») (p : «通道» × Nat) (hp : p ∈ L.«组的通道» g)
    (hg : g.«是元件的» = true) :
    L.«是运输单位» p.1.«起» = true ∧
      L.«所在元件» (L.«单位表».length + 1) p.1.«起» = some p.1.«起» := by
  have hgroup : L.«所在组» p.1 = some g := by
    simpa [«布局».«组的通道»] using (List.mem_filter.mp hp).2
  have hmem : p ∈ L.«出» p.1.«起» := by
    simp [«布局».«出», (List.mem_filter.mp hp).1]
  unfold «布局».«所在组» at hgroup
  cases ha : L.«种类» p.1.«起» with
  | none => simp [ha] at hgroup
  | some a =>
    cases hb : L.«种类» p.1.«止» with
    | none => simp [ha, hb] at hgroup
    | some b =>
      simp only [ha, hb] at hgroup
      have htrans : a.«是运输单位» = true := by
        cases a <;> simp_all [«单位种类».«是运输单位», «组».«是元件的»]
        all_goals split at hgroup <;> simp_all [← Option.some.inj hgroup]
      refine ⟨by simp [«布局».«是运输单位», ha, htrans], ?_⟩
      cases a with
      | «传送带» =>
        have hb' : b ≠ .«传送带» := by intro he; simp [he] at hgroup
        have hlen := L.«端口数合_出» _ _ hport ha
        have hout : L.«出» p.1.«起» = [p] := by
          have : (L.«出» p.1.«起»).length ≤ 1 := hlen
          cases ho : L.«出» p.1.«起» with
          | nil => simp [ho] at hmem
          | cons q qs =>
            have : qs = [] := by simpa [ho] using this
            subst qs
            simpa [ho, eq_comm] using hmem
        simp [«布局».«所在元件», ha, hout, hb, hb']
      | «分流器» | «汇流器» | «物品准入口» | «桥接器格» =>
        simp [«布局».«所在元件», ha, «单位种类».«是运输单位»]
      | «协议储存箱» | «制造» k | «协议核心» | «仓库取货口» =>
        simp [«单位种类».«是运输单位»] at htrans

private theorem group_target (L : «布局») (hs : L.«整齐»)
    (g : «组») (p : «通道» × Nat) (hp : p ∈ L.«组的通道» g)
    (hg : g.«是元件的» = false) : L.«是运输单位» p.1.«止» = true := by
  have hgroup : L.«所在组» p.1 = some g := by
    simpa [«布局».«组的通道»] using (List.mem_filter.mp hp).2
  have hor := hs.«有运输的» p (List.mem_filter.mp hp).1
  suffices hn : L.«是运输单位» p.1.«起» = false by simp_all
  unfold «布局».«所在组» at hgroup
  cases ha : L.«种类» p.1.«起» with
  | none => simp [ha] at hgroup
  | some a =>
    cases hb : L.«种类» p.1.«止» with
    | none => simp [ha, hb] at hgroup
    | some b =>
      cases a <;> simp_all [«布局».«是运输单位», «单位种类».«是运输单位», «组».«是元件的»]
      all_goals grind [«组».«是元件的»]

private theorem all_values {α : Type} (f : α → Option Nat) (cs : List α)
    (hf : ∀ p ∈ cs, (f p).isSome = true) :
    ∃ ns, «全有» (cs.map f) = some ns ∧ ns.length = cs.length ∧
      ∀ n ∈ ns, ∃ p ∈ cs, f p = some n := by
  induction cs with
  | nil => exact ⟨[], rfl, rfl, by simp⟩
  | cons p ps ih =>
    obtain ⟨n, hn⟩ := Option.isSome_iff_exists.mp (hf p (by simp))
    obtain ⟨ns, hs, hl, hm⟩ := ih (by intro q hq; exact hf q (by simp [hq]))
    refine ⟨n :: ns, by simp [«全有», hn, hs], by simp [hl], ?_⟩
    intro m hmem
    rcases List.mem_cons.mp hmem with he | he
    · subst m; exact ⟨p, by simp, hn⟩
    · obtain ⟨q, hq, hqm⟩ := hm m he
      exact ⟨q, by simp [hq], hqm⟩

/-- 据：级别、次序、运输带

合法基地的每个现有组都能算出级别，因而不会在走步判定时被跳过。
-/
theorem «每个组都有级别» («h终点» : «命题».«末端元件有终点»)
    («h次序» : «命题».«同组次序相同») : «命题».«每个组都有级别» := by
  intro H hlegal g hg
  have hlegal' : H.«合规» = true ∧ H.«端口数合» = true ∧
      (H.«布局于» H.length).«走得通» = true := by
    simpa [«历史».«合法», Bool.and_eq_true, and_assoc] using hlegal
  obtain ⟨hreg, hports, hw⟩ := hlegal'
  let L := H.«布局于» H.length
  have hport := H.«端口数合_任一刻» hports H.length
  have hne : L.«组的通道» g ≠ [] := by
    have hmem : g ∈ L.«通道表».filterMap (fun p => L.«所在组» p.1) := by
      simpa [«布局».«各组»] using hg
    obtain ⟨p, hp, hpg⟩ := List.mem_filterMap.mp hmem
    have : p ∈ L.«组的通道» g := by simp [«布局».«组的通道», hp, hpg]
    intro he
    simp [he] at this
  have htime : (H.«组的时刻» H.length g).isSome = true := by
    rw [«历史».«组的时刻», «最近一次变成_isSome»]
    simpa using hne
  obtain ⟨t, ht⟩ := Option.isSome_iff_exists.mp htime
  let f : («通道» × Nat) → Option Nat := fun p =>
    if g.«是元件的» then H.«次序» H.length p.1.«起»
    else (L.«所在元件» (L.«单位表».length + 1) p.1.«止»).bind (H.«次序» H.length)
  have hf : ∀ p ∈ L.«组的通道» g, (f p).isSome = true := by
    intro p hp
    by_cases hge : g.«是元件的» = true
    · obtain ⟨hu, he⟩ := group_source L hport g p hp hge
      have hc : L.«出» p.1.«起» ≠ [] := by
        have hm : p ∈ L.«出» p.1.«起» := by
          simp [«布局».«出», (List.mem_filter.mp hp).1]
        intro he
        simp [he] at hm
      obtain ⟨e, he', hpath⟩ := walk L hw _ hu (Or.inr hc)
      have heq : e = p.1.«起» := Option.some.inj (he'.symm.trans he)
      subst e
      exact (show (f p).isSome = true from by
        simpa [f, hge] using order_some «h终点» H H.length _ hport hpath)
    · have hge' : g.«是元件的» = false := Bool.eq_false_iff.mpr hge
      have hu := group_target L (H.«合规则整齐» hreg H.length) g p hp hge'
      have hc : L.«进» p.1.«止» ≠ [] := by
        have hm : p ∈ L.«进» p.1.«止» := by
          simp [«布局».«进», (List.mem_filter.mp hp).1]
        intro he
        simp [he] at hm
      obtain ⟨e, he, hpath⟩ := walk L hw _ hu (Or.inl hc)
      simpa [f, hge', he] using order_some «h终点» H H.length e hport hpath
  obtain ⟨ns, hns, hlen, hmem⟩ := all_values f (L.«组的通道» g) hf
  cases ns with
  | nil =>
    have : L.«组的通道» g = [] := by simpa using hlen.symm
    contradiction
  | cons n rest =>
    have hlev : H.«级别» H.length g =
        if g.«是元件的» then
          (if rest.all (· == n) then some (n,t) else none)
        else some (rest.foldl max n,t) := by
      unfold «历史».«级别»
      have hmap : (if g.«是元件的» then
          (L.«组的通道» g).map (fun p => H.«次序» H.length p.1.«起»)
          else (L.«组的通道» g).map (fun p =>
            (L.«所在元件» (L.«单位表».length + 1) p.1.«止»).bind (H.«次序» H.length))) =
            (L.«组的通道» g).map f := by
        cases hh : g.«是元件的» <;> simp [f, hh]
      dsimp only
      change (match «全有» (if g.«是元件的» then
          (L.«组的通道» g).map (fun p => H.«次序» H.length p.1.«起»)
          else (L.«组的通道» g).map (fun p =>
            (L.«所在元件» (L.«单位表».length + 1) p.1.«止»).bind (H.«次序» H.length))),
          H.«组的时刻» H.length g with
        | some (a :: rs), some b =>
          if g.«是元件的» then (if rs.all (· == a) then some (a,b) else none)
          else some (rs.foldl max a,b)
        | _, _ => none) = _
      rw [hmap, hns, ht]
    rw [hlev]
    by_cases hge : g.«是元件的» = true
    · have hall : rest.all (· == n) = true := by
        obtain ⟨p, hp, hpn⟩ := hmem n (by simp)
        apply List.all_eq_true.mpr
        intro m hm
        obtain ⟨q, hq, hqm⟩ := hmem m (by simp [hm])
        have he := «h次序» H g hport hge p hp q hq
        simp only [f, hge, ↓reduceIte] at hpn hqm
        have : n = m := Option.some.inj (hpn.symm.trans (he.trans hqm))
        simp [this]
      simp [hge, hall]
    · simp [hge]

end Endfield.«证明»
