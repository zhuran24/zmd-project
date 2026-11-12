import Endfield.«证明».«基础»

/-!
证明「变成终点那一刻是接通」和「终点的时刻不同」。
先把非分流器的终点刻画成一条通往非运输单位的通道，再考察建成、接通、拆除
怎样改变这样的通道。持续存在的单位种类不变，因此两类终点的时刻都能追溯到
唯一的接通事件；比较该事件的两端即可区分终点。
-/

namespace Endfield.«证明»

private theorem nontransport_ne_split (L : «布局») (x : «单位号»)
    (h : L.«是非运输单位» x = true) : L.«种类» x ≠ some .«分流器» := by
  intro he
  simp [«布局».«是非运输单位», he, «单位种类».«是运输单位»] at h

private theorem nontransport_present (L : «布局») (x : «单位号»)
    (h : L.«是非运输单位» x = true) : (L.«种类» x).isSome = true := by
  cases he : L.«种类» x <;> simp_all [«布局».«是非运输单位»]

private theorem kind_mem (L : «布局») (x : «单位号») (k : «单位种类»)
    (h : L.«种类» x = some k) : x ∈ L.«建成先后» := by
  obtain ⟨p, hp, _⟩ := Option.map_eq_some_iff.mp h
  have hm := List.mem_of_find?_eq_some hp
  have hx : p.1 = x := by simpa using List.find?_some hp
  exact List.mem_map.mpr ⟨p, hm, hx⟩

private theorem component_transport (L : «布局») (e : «单位号»)
    (h : e ∈ L.«元件») : L.«是运输单位» e = true := by
  have hs : L.«所在元件» 1 e = some e := by
    simpa [«布局».«元件»] using (List.mem_filter.mp h).2
  cases hk : L.«种类» e with
  | none => simp [«布局».«所在元件», hk] at hs
  | some k =>
    cases k <;> simp_all [«布局».«所在元件», «布局».«是运输单位»,
      «单位种类».«是运输单位»]

private theorem endpoint_cases (L : «布局») (x : «单位号»)
    (h : L.«是终点» x = true) :
    L.«种类» x = some .«分流器» ∨ L.«是非运输单位» x = true := by
  obtain ⟨e, _, he⟩ := List.any_eq_true.mp h
  have he : L.«终点» e = some x := by simpa using he
  unfold «布局».«终点» at he
  split at he
  · contradiction
  next ht =>
    have ht : L.«是末端元件» e = true := by simpa using ht
    split at he
    next hk =>
      have hx : e = x := Option.some.inj he
      exact Or.inl (by simpa [hx] using hk)
    next hk =>
      split at he
      next p hp =>
        have hx : p.1.«止» = x := Option.some.inj he
        have ha : (L.«出» e).all (fun q => L.«是非运输单位» q.1.«止») = true := by
          simp only [«布局».«是末端元件», Bool.and_eq_true] at ht
          exact ht.2
        simp only [hp, List.all_cons, List.all_nil, Bool.and_true] at ha
        exact Or.inr (by simpa [hx] using ha)
      next => contradiction

private theorem endpoint_present (L : «布局») (x : «单位号»)
    (h : L.«是终点» x = true) : (L.«种类» x).isSome = true := by
  rcases endpoint_cases L x h with h | h
  · simp [h]
  · exact nontransport_present L x h

private theorem singleton_of_mem {α : Type} (xs : List α) (p : α)
    (hl : xs.length ≤ 1) (hp : p ∈ xs) : xs = [p] := by
  cases xs with
  | nil => simp at hp
  | cons a as =>
    have hn : as = [] := List.eq_nil_of_length_eq_zero (by simpa using hl)
    subst as
    simpa using (List.mem_singleton.mp hp).symm

private theorem terminal_of_edge (L : «布局») (e x : «单位号»)
    (k : «单位种类») (p : «通道» × «时刻»)
    (hports : L.«端口数合» = true) (hk : L.«种类» e = some k)
    (htrans : k.«是运输单位» = true) (hns : k ≠ .«分流器»)
    (hp : p ∈ L.«出» e) (hx : p.1.«止» = x)
    (hn : L.«是非运输单位» x = true) :
    L.«是末端元件» e = true ∧ L.«终点» e = some x := by
  have hbound := L.«端口数合_出» e k hports hk
  have hkport : k.«取货端口数» = 1 := by
    cases k <;> simp_all [«单位种类».«是运输单位», «单位种类».«取货端口数»]
  have hout : L.«出» e = [p] := singleton_of_mem _ _ (by simpa [hkport] using hbound) hp
  have hntrans : L.«种类» x ≠ some .«传送带» := by
    intro he
    simp [«布局».«是非运输单位», he, «单位种类».«是运输单位»] at hn
  have hself : L.«所在元件» 1 e = some e := by
    cases k <;> simp_all [«布局».«所在元件», «单位种类».«是运输单位»]
  have hmem : e ∈ L.«元件» := by
    simp only [«布局».«元件», List.mem_filter, beq_iff_eq]
    exact ⟨kind_mem L e k hk, hself⟩
  have hterm : L.«是末端元件» e = true := by
    simp [«布局».«是末端元件», hmem, hout, hx, hn]
  refine ⟨hterm, ?_⟩
  simp [«布局».«终点», hterm, hk, hns, hout, hx]

private theorem endpoint_of_edge (L : «布局») (e x : «单位号»)
    (k : «单位种类») (p : «通道» × «时刻»)
    (hports : L.«端口数合» = true) (hk : L.«种类» e = some k)
    (htrans : k.«是运输单位» = true) (hns : k ≠ .«分流器»)
    (hp : p ∈ L.«出» e) (hx : p.1.«止» = x)
    (hn : L.«是非运输单位» x = true) : L.«是终点» x = true := by
  obtain ⟨ht, he⟩ := terminal_of_edge L e x k p hports hk htrans hns hp hx hn
  apply List.any_eq_true.mpr
  refine ⟨e, ?_, by simp [he]⟩
  simp only [«布局».«是末端元件», Bool.and_eq_true] at ht
  simpa using ht.1.1

private theorem endpoint_edge (L : «布局») (x : «单位号»)
    (h : L.«是终点» x = true) (hn : L.«种类» x ≠ some .«分流器») :
    ∃ e k p, L.«种类» e = some k ∧ k.«是运输单位» = true ∧ k ≠ .«分流器» ∧
      p ∈ L.«出» e ∧ p.1.«止» = x ∧ L.«是非运输单位» x = true := by
  obtain ⟨e, hm, he⟩ := List.any_eq_true.mp h
  have he : L.«终点» e = some x := by simpa using he
  have htr := component_transport L e hm
  unfold «布局».«终点» at he
  split at he
  · contradiction
  next ht =>
    have ht : L.«是末端元件» e = true := by simpa using ht
    split at he
    next hk =>
      have hx : e = x := Option.some.inj he
      exact False.elim (hn (by simpa [hx] using hk))
    next hk =>
      have hk : L.«种类» e ≠ some .«分流器» := by simpa using hk
      split at he
      next p hp =>
        have hx : p.1.«止» = x := Option.some.inj he
        have hnon : L.«是非运输单位» x = true := by
          simp only [«布局».«是末端元件», Bool.and_eq_true] at ht
          simpa [hp, hx] using ht.2
        cases hk' : L.«种类» e with
        | none => simp [«布局».«是运输单位», hk'] at htr
        | some k =>
          refine ⟨e, k, p, hk', ?_, ?_, by simp [hp], hx, hnon⟩
          · simpa [«布局».«是运输单位», hk'] using htr
          · simpa [hk'] using hk
      next => contradiction

private theorem edge_new_or_old (L : «布局») (t : «时刻») (ev : «事件»)
    (p : «通道» × «时刻») (htidy : L.«整齐»)
    (hok : L.«容得下» ev = true) (hp : p ∈ (L.«加» t ev).«通道表») :
    (ev = .«接通» p.1 ∧ p.2 = t) ∨
      (p ∈ L.«通道表» ∧
       (L.«加» t ev).«种类» p.1.«起» = L.«种类» p.1.«起» ∧
       (L.«加» t ev).«种类» p.1.«止» = L.«种类» p.1.«止») := by
  cases ev with
  | «建成» u k =>
    have hp : p ∈ L.«通道表» := hp
    have hnone : L.«种类» u = none := by
      simp only [«布局».«容得下», Bool.and_eq_true, Option.isNone_iff_eq_none] at hok
      exact hok.1
    have hb := htidy.«两头都在» p hp
    have hstart : p.1.«起» ≠ u := by intro he; simp [he, hnone] at hb
    have hstop : p.1.«止» ≠ u := by intro he; simp [he, hnone] at hb
    exact Or.inr ⟨hp, by simp [«布局».«加建成_种类», hnone, hstart],
      by simp [«布局».«加建成_种类», hnone, hstop]⟩
  | «接通» c =>
    have hp : p ∈ L.«通道表» ∨ p = (c, t) := by simpa [«布局».«加»] using hp
    rcases hp with hp | rfl
    · exact Or.inr ⟨hp, rfl, rfl⟩
    · exact Or.inl ⟨rfl, rfl⟩
  | «拆除» u =>
    have hp : p ∈ L.«通道表» ∧ p.1.«起» ≠ u ∧ p.1.«止» ≠ u := by
      simpa [«布局».«加»] using hp
    exact Or.inr ⟨hp.1, by simp [«布局».«加拆除_种类», hp.2.1],
      by simp [«布局».«加拆除_种类», hp.2.2]⟩

private theorem present_step (L : «布局») (t : «时刻») (ev : «事件»)
    (x : «单位号») (hok : L.«容得下» ev = true)
    (hbefore : (L.«种类» x).isSome = true)
    (hafter : ((L.«加» t ev).«种类» x).isSome = true) :
    (L.«加» t ev).«种类» x = L.«种类» x := by
  cases ev with
  | «接通» c => rfl
  | «建成» u k =>
    have hnone : L.«种类» u = none := by
      simp only [«布局».«容得下», Bool.and_eq_true, Option.isNone_iff_eq_none] at hok
      exact hok.1
    have hxu : x ≠ u := by intro he; simp [he, hnone] at hbefore
    simp [«布局».«加建成_种类», hnone, hxu]
  | «拆除» u =>
    have hxu : x ≠ u := by
      intro he
      simp [«布局».«加拆除_种类», he] at hafter
    simp [«布局».«加拆除_种类», hxu]

private theorem kind_constant (H : «历史») (hok : H.«合规» = true)
    (x : «单位号») (a b : Nat) (hab : a ≤ b) (hb : b ≤ H.length)
    (hall : ∀ i, a ≤ i → i ≤ b → ((H.«布局于» i).«种类» x).isSome = true) :
    (H.«布局于» a).«种类» x = (H.«布局于» b).«种类» x := by
  induction b with
  | zero =>
    have : a = 0 := by omega
    subst a
    rfl
  | succ b ih =>
    by_cases he : a = b + 1
    · subst a; rfl
    · have hab' : a ≤ b := by omega
      have hind := ih hab' (by omega) (fun i hi hj => hall i hi (by omega))
      have hi : b < H.length := by omega
      have hev : H[b]? = some H[b] := List.getElem?_eq_getElem hi
      have hstep := H.«布局于后继» b H[b] hev
      have ha := hall (b+1) (by omega) (by omega)
      rw [hstep] at ha
      have hs := present_step (H.«布局于» b) (b+1) H[b] x
        ((H.«合规_iff».mp hok) b H[b] hev) (hall b hab' (by omega)) ha
      rw [hstep, hs]
      exact hind

private theorem endpoint_step (L : «布局») (t : «时刻») (ev : «事件»)
    (x : «单位号») (htidy : L.«整齐») (hok : L.«容得下» ev = true)
    (hports : L.«端口数合» = true) (hports' : (L.«加» t ev).«端口数合» = true)
    (hb : L.«是终点» x = false) (ha : (L.«加» t ev).«是终点» x = true)
    (hns : (L.«加» t ev).«种类» x ≠ some .«分流器») :
    ∃ e, ev = .«接通» ⟨e, x⟩ ∧ (L.«加» t ev).«是末端元件» e = true ∧
      (L.«加» t ev).«种类» e ≠ some .«分流器» := by
  obtain ⟨e, k, p, hk, htr, hn, hp, hx, hnon⟩ := endpoint_edge _ x ha hns
  have hp' : p ∈ (L.«加» t ev).«通道表» := (List.mem_filter.mp hp).1
  have hs : p.1.«起» = e := by simpa using (List.mem_filter.mp hp).2
  rcases edge_new_or_old L t ev p htidy hok hp' with hnew | hold
  · refine ⟨e, ?_, (terminal_of_edge _ e x k p hports' hk htr hn hp hx hnon).1, ?_⟩
    · rw [hnew.1]
      congr 1
      cases p with
      | mk c time => cases c; simp_all
    · simpa [hk] using hn
  · have hkold : L.«种类» e = some k := by
      rw [hs] at hold
      exact hold.2.1.symm.trans hk
    have hnold : L.«是非运输单位» x = true := by
      unfold «布局».«是非运输单位» at *
      rw [hx] at hold
      rw [← hold.2.2]
      exact hnon
    have hpold : p ∈ L.«出» e := by simp [«布局».«出», hold.1, hs]
    have he := endpoint_of_edge L e x k p hports hkold htr hn hpold hx hnold
    simp [hb] at he

private def has_output (L : «布局») (x : «单位号») : Bool :=
  (L.«出» x).any fun p => L.«是非运输单位» p.1.«止»

private theorem output_present (L : «布局») (x : «单位号»)
    (htidy : L.«整齐») (h : has_output L x = true) :
    (L.«种类» x).isSome = true := by
  obtain ⟨p, hp, _⟩ := List.any_eq_true.mp h
  have hs : p.1.«起» = x := by simpa using (List.mem_filter.mp hp).2
  simpa [hs] using (htidy.«两头都在» p (List.mem_filter.mp hp).1).1

private theorem output_step (L : «布局») (t : «时刻») (ev : «事件»)
    (x : «单位号») (htidy : L.«整齐») (hok : L.«容得下» ev = true)
    (hb : has_output L x = false) (ha : has_output (L.«加» t ev) x = true) :
    ∃ z, ev = .«接通» ⟨x, z⟩ := by
  obtain ⟨p, hp, hn⟩ := List.any_eq_true.mp ha
  have hs : p.1.«起» = x := by simpa using (List.mem_filter.mp hp).2
  rcases edge_new_or_old L t ev p htidy hok (List.mem_filter.mp hp).1 with hnew | hold
  · refine ⟨p.1.«止», ?_⟩
    rw [hnew.1]
    congr 1
    cases p with
    | mk c time => cases c; simp_all
  · have hpold : p ∈ L.«出» x := by simp [«布局».«出», hold.1, hs]
    have hnold : L.«是非运输单位» p.1.«止» = true := by
      unfold «布局».«是非运输单位» at *
      rw [← hold.2.2]
      exact hn
    have he : has_output L x = true := List.any_eq_true.mpr ⟨p, hpold, hnold⟩
    simp [hb] at he

private theorem nonsplit_time (H : «历史») (x : «单位号») (t : «时刻»)
    (hok : H.«合规» = true) (hports : H.«端口数合» = true)
    (hn : (H.«布局于» H.length).«种类» x ≠ some .«分流器»)
    (htime : H.«终点的时刻» H.length x = some t) :
    ∃ e, 1 ≤ t ∧ H[t-1]? = some (.«接通» ⟨e, x⟩) ∧
      (H.«布局于» t).«是末端元件» e = true ∧
      (H.«布局于» t).«种类» e ≠ some .«分流器» := by
  change Nat at t
  have hr : «最近一次变成» (fun i => (H.«布局于» i).«是终点» x) H.length = some t := by
    unfold «历史».«终点的时刻» at htime
    dsimp only at htime
    split at htime
    · contradiction
    · simpa [hn] using htime
  obtain ⟨hle, hall, hboundary⟩ := «最近一次变成_spec» _ H.length t hr
  have hat := hall t (Nat.le_refl _) hle
  have hpos : 1 ≤ t := by
    by_cases h : 1 ≤ t
    · exact h
    · have hz : t = 0 := by omega
      simp [hz, «历史».«布局于零», «布局».«是终点», «布局».«元件», «布局».«建成先后»] at hat
  have hprev : (H.«布局于» (t-1)).«是终点» x = false := hboundary.resolve_left (Nat.ne_of_gt hpos)
  have hkind := kind_constant H hok x t H.length hle (by omega)
    (fun i hi hj => endpoint_present _ x (hall i hi hj))
  have hns : (H.«布局于» t).«种类» x ≠ some .«分流器» := by rw [hkind]; exact hn
  have hi : t-1 < H.length := Nat.lt_of_lt_of_le (Nat.sub_lt hpos (by decide)) hle
  have hev : H[t-1]? = some H[t-1] := List.getElem?_eq_getElem hi
  have hstep : H.«布局于» t = (H.«布局于» (t-1)).«加» t H[t-1] := by
    simpa [Nat.sub_add_cancel hpos] using H.«布局于后继» (t-1) H[t-1] hev
  have hp' := H.«端口数合_任一刻» hports t
  rw [hstep] at hat hns hp'
  obtain ⟨e, he, ht, hk⟩ := endpoint_step _ t H[t-1] x
    (H.«合规则整齐» hok (t-1)) ((H.«合规_iff».mp hok) (t-1) H[t-1] hev)
    (H.«端口数合_任一刻» hports (t-1)) hp' hprev hat hns
  refine ⟨e, hpos, by simpa [he] using hev, ?_, ?_⟩
  · simpa [hstep] using ht
  · simpa [hstep] using hk

private theorem split_time (H : «历史») (x : «单位号») (t : «时刻»)
    (hok : H.«合规» = true)
    (hk : (H.«布局于» H.length).«种类» x = some .«分流器»)
    (htime : H.«终点的时刻» H.length x = some t) :
    ∃ z, 1 ≤ t ∧ H[t-1]? = some (.«接通» ⟨x, z⟩) ∧
      (H.«布局于» t).«种类» x = some .«分流器» := by
  change Nat at t
  have hr : «最近一次变成» (fun i => has_output (H.«布局于» i) x) H.length = some t := by
    unfold «历史».«终点的时刻» at htime
    dsimp only at htime
    split at htime
    · contradiction
    · simpa [hk, has_output] using htime
  obtain ⟨hle, hall, hboundary⟩ := «最近一次变成_spec» _ H.length t hr
  have hat := hall t (Nat.le_refl _) hle
  have hpos : 1 ≤ t := by
    by_cases h : 1 ≤ t
    · exact h
    · have hz : t = 0 := by omega
      simp [hz, «历史».«布局于零», has_output, «布局».«出»] at hat
  have hprev : has_output (H.«布局于» (t-1)) x = false := hboundary.resolve_left (Nat.ne_of_gt hpos)
  have hkind := kind_constant H hok x t H.length hle (by omega)
    (fun i hi hj => output_present _ x (H.«合规则整齐» hok i) (hall i hi hj))
  have hkt : (H.«布局于» t).«种类» x = some .«分流器» := hkind.trans hk
  have hi : t-1 < H.length := Nat.lt_of_lt_of_le (Nat.sub_lt hpos (by decide)) hle
  have hev : H[t-1]? = some H[t-1] := List.getElem?_eq_getElem hi
  have hstep : H.«布局于» t = (H.«布局于» (t-1)).«加» t H[t-1] := by
    simpa [Nat.sub_add_cancel hpos] using H.«布局于后继» (t-1) H[t-1] hev
  rw [hstep] at hat
  obtain ⟨z, he⟩ := output_step _ t H[t-1] x (H.«合规则整齐» hok (t-1))
    ((H.«合规_iff».mp hok) (t-1) H[t-1] hev) hprev hat
  exact ⟨z, hpos, by simpa [he] using hev, hkt⟩

/-- 据：终点的时刻、接通

非运输单位最近一次变成终点时，发生的是某个末端元件与它接通的事件。 -/
theorem «变成终点那一刻是接通» : «命题».«变成终点那一刻是接通» := by
  intro H x t hok hp hn ht
  obtain ⟨e, hpos, he, hterm, _⟩ := nonsplit_time H x t hok hp
    (nontransport_ne_split _ x hn) ht
  exact ⟨e, hpos, he, hterm⟩

/-- 据：终点的时刻、次序

不同终点的时刻对应不同接通事件，因此两个不同的终点不能有同一个终点时刻。 -/
theorem «终点的时刻不同» : «命题».«终点的时刻不同» := by
  intro H x y t hok hp hxy hx hy
  by_cases hxs : (H.«布局于» H.length).«种类» x = some .«分流器»
  · obtain ⟨z, _, he, hxt⟩ := split_time H x t hok hxs hx
    by_cases hys : (H.«布局于» H.length).«种类» y = some .«分流器»
    · obtain ⟨z', _, he', _⟩ := split_time H y t hok hys hy
      have hc := Option.some.inj (he.symm.trans he')
      have hstart : x = y := by cases hc; rfl
      exact hxy hstart
    · obtain ⟨e, _, he', _, hns⟩ := nonsplit_time H y t hok hp hys hy
      have hc := Option.some.inj (he.symm.trans he')
      have hstart : x = e := by cases hc; rfl
      exact hns (by simpa [← hstart] using hxt)
  · obtain ⟨e, _, he, _, hns⟩ := nonsplit_time H x t hok hp hxs hx
    by_cases hys : (H.«布局于» H.length).«种类» y = some .«分流器»
    · obtain ⟨z, _, he', hyt⟩ := split_time H y t hok hys hy
      have hc := Option.some.inj (he.symm.trans he')
      have hstart : e = y := by cases hc; rfl
      exact hns (by simpa [hstart] using hyt)
    · obtain ⟨e', _, he', _, _⟩ := nonsplit_time H y t hok hp hys hy
      have hc := Option.some.inj (he.symm.trans he')
      have hstop : x = y := by cases hc; rfl
      exact hxy hstop

end Endfield.«证明»


