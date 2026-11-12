import Endfield.«证明».«基础»

/-!
证明格子层的放进单位守规矩。按一次添货证明容量和制造单位存货种类保持合规，
再沿临时表的折叠归纳；临时表不含缓存格，因而制造进度与缓存内容保持相符。
-/

namespace Endfield.«证明»

open List
set_option linter.unusedSimpArgs false
set_option linter.unnecessarySimpa false

private def unitOK (f : «格位» → List «一堆») (u : «单位号») : «单位种类» → Prop
  | .«传送带» | .«分流器» | .«汇流器» | .«物品准入口» | .«桥接器格» =>
    «一格合规矩» 1 (f ⟨u, .«格» 0⟩) = true
  | .«协议储存箱» => ∀ i < 6, «一格合规矩» 50 (f ⟨u, .«格» i⟩) = true
  | .«制造» k =>
    (∀ i < k.«存货物品格数», «一格合规矩» 50 (f ⟨u, .«存货» i⟩) = true) ∧
    «一格合规矩» 50 (f ⟨u, .«取货»⟩) = true ∧
    ((List.range k.«存货物品格数»).flatMap fun i => (f ⟨u, .«存货» i⟩).map (·.«物»)).Nodup
  | .«协议核心» | .«仓库取货口» => True

private def goods (L : «布局») (s : «状态») : Prop :=
  (∀ p ∈ L.«单位表», unitOK s.«货» p.1 p.2) ∧ ∀ x, s.«仓库» x ≤ 80000

private def cacheOK (s : «状态») (u : «单位号») (k : «制造单位») : Prop :=
  (match s.«制造中» u with
    | some (r, _) =>
      «配方表».contains r && r.«单位» == k
        && s.«货» ⟨u, .«缓存»⟩ == r.«原料».map fun q => ⟨q.1, q.2⟩
    | none =>
      (s.«货» ⟨u, .«缓存»⟩).isEmpty ||
        «配方表».any fun r =>
          r.«单位» == k && s.«货» ⟨u, .«缓存»⟩ == [⟨r.«产物».1, r.«产物».2⟩]) = true

private def progressOK (L : «布局») (s : «状态») : Prop :=
  ∀ p ∈ L.«单位表», match p.2 with
    | .«制造» k => cacheOK s p.1 k
    | _ => True

private theorem goods_iff (L : «布局») (s : «状态») :
    goods L s ∧ progressOK L s ↔ s.«各格合规矩» L = true ∧ ∀ x, s.«仓库» x ≤ 80000 := by
  have he : (∀ p ∈ L.«单位表», unitOK s.«货» p.1 p.2 ∧
      (match p.2 with | .«制造» k => cacheOK s p.1 k | _ => True)) ↔
      s.«各格合规矩» L = true := by
    simp only [«状态».«各格合规矩», List.all_eq_true]
    apply forall_congr'; intro p
    apply imp_congr_right; intro _
    cases p.2 <;> simp [unitOK, cacheOK, List.all_eq_true, Bool.and_eq_true,
      List.mem_range, List.flatMap_map, and_assoc]
    all_goals intros; cases s.«制造中» p.1 <;> rfl
  constructor
  · rintro ⟨⟨hg,hw⟩,hp⟩
    exact ⟨he.mp (fun p hm => ⟨hg p hm, hp p hm⟩),hw⟩
  · rintro ⟨hg,hw⟩
    have hp := he.mpr hg
    exact ⟨⟨fun p hm => (hp p hm).1,hw⟩,fun p hm => (hp p hm).2⟩

private theorem one_cases {cap : Nat} {l : List «一堆»} (h : «一格合规矩» cap l = true) :
    l = [] ∨ ∃ x n, l = [⟨x,n⟩] ∧ 1 ≤ n ∧ n ≤ cap := by
  cases l with
  | nil => exact Or.inl rfl
  | cons p l =>
    cases l with
    | nil => exact Or.inr ⟨p.«物», p.«件数», rfl, by simpa [«一格合规矩»] using h⟩
    | cons q l => simp [«一格合规矩»] at h

private theorem kind_mem (L : «布局») {u : «单位号»} {k : «单位种类»}
    (h : L.«种类» u = some k) : (u,k) ∈ L.«单位表» := by
  obtain ⟨p,hp,hk⟩ := Option.map_eq_some_iff.mp h
  have hu : p.1 = u := by simpa using List.find?_some hp
  have hm := List.mem_of_find?_eq_some hp
  have he : p = (u,k) := Prod.ext hu hk
  simpa [he] using hm

private theorem mem_kind (L : «布局») (ht : (L.«单位表».map (·.1)).Nodup)
    {u : «单位号»} {k : «单位种类»} (h : (u,k) ∈ L.«单位表») : L.«种类» u = some k := by
  unfold «布局».«种类»
  suffices hh : L.«单位表».find? (fun p => p.1 == u) = some (u,k) by simp [hh]
  generalize L.«单位表» = ps at *
  induction ps with
  | nil => simp at h
  | cons p ps ih =>
    simp only [List.map_cons, List.nodup_cons] at ht
    rcases List.mem_cons.mp h with he | he
    · subst p; simp
    · have hn : p.1 ≠ u := by
        intro e
        exact ht.1 (List.mem_map.mpr ⟨(u,k),he,by simpa [e]⟩)
      simp [hn, ih ht.2 he]

private def room (cap : Nat) (l : List «一堆») (x : «物品») : Prop :=
  l = [] ∨ ∃ n, l = [⟨x,n⟩] ∧ n < cap

private theorem add_good {cap : Nat} {l : List «一堆»} {x : «物品»}
    (hc : 0 < cap) (h : room cap l x) : «一格合规矩» cap («添几件» l x 1) = true := by
  rcases h with rfl | ⟨n,rfl,hn⟩ <;> simp [«添几件», «一格合规矩»] <;> omega

private theorem add_nodup {cap : Nat} {l : List «一堆»} {x : «物品»}
    (h : room cap l x) : ((«添几件» l x 1).map (·.«物»)).Nodup := by
  rcases h with rfl | ⟨n,rfl,_⟩ <;> simp [«添几件»]

private theorem add_mem {l : List «一堆»} {x y : «物品»}
    (h : y ∈ («添几件» l x 1).map (·.«物»)) : y = x ∨ y ∈ l.map (·.«物») := by
  simp only [«添几件», Nat.one_ne_zero, beq_iff_eq, ↓reduceIte] at h
  split at h
  · obtain ⟨p,hp,he⟩ := List.mem_map.mp h
    obtain ⟨q,hq,hqp⟩ := List.mem_map.mp hp
    by_cases hx : q.«物» = x <;> simp [hx] at hqp
    · subst p; exact Or.inl he.symm
    · subst p; exact Or.inr (List.mem_map.mpr ⟨q,hq,he⟩)
  · simpa [or_comm] using h

private theorem flat_update_nodup {α β : Type} [DecidableEq α]
    (is : List α) (f : α → List β) (i : α) (v : List β) (x : β)
    (hi : is.Nodup) (hf : (is.flatMap f).Nodup) (hv : v.Nodup)
    (hm : ∀ y ∈ v, y = x ∨ y ∈ f i)
    (hx : ∀ j ∈ is, j ≠ i → x ∉ f j) :
    (is.flatMap fun j => if j = i then v else f j).Nodup := by
  induction is with
  | nil => simp
  | cons a is ih =>
    simp only [List.nodup_cons] at hi
    simp only [List.flatMap_cons, List.nodup_append] at hf ⊢
    by_cases ha : a = i
    · subst a
      have he : (is.flatMap fun j => if j = i then v else f j) = is.flatMap f := by
        rw [List.flatMap_def, List.flatMap_def]
        congr 1
        apply List.map_congr_left; intro j hj
        simp [show j ≠ i by intro e; exact hi.1 (e ▸ hj)]
      simp only [↓reduceIte, he]
      refine ⟨hv,hf.2.1,?_⟩
      intro y hy z hz hyz
      subst z
      obtain ⟨j,hj,hyj⟩ := List.mem_flatMap.mp hz
      rcases hm y hy with rfl | hy
      · exact hx j (by simp [hj]) (by intro e; exact hi.1 (e ▸ hj)) hyj
      · exact hf.2.2 y hy y (List.mem_flatMap.mpr ⟨j,hj,hyj⟩) rfl
    · simp only [ha, ↓reduceIte]
      refine ⟨hf.1, ih hi.2 hf.2.1 (fun j hj => hx j (by simp [hj])), ?_⟩
      intro y hy z hz hyz
      subst z
      obtain ⟨j,hj,hyj⟩ := List.mem_flatMap.mp hz
      by_cases hj' : j = i
      · subst j; simp only [↓reduceIte] at hyj
        rcases hm y hyj with rfl | hyj
        · exact hx a (by simp) ha hy
        · exact hf.2.2 y hy y (List.mem_flatMap.mpr ⟨i,hj,hyj⟩) rfl
      · simp only [hj', ↓reduceIte] at hyj
        exact hf.2.2 y hy y (List.mem_flatMap.mpr ⟨j,hj,hyj⟩) rfl

private theorem unit_ext (f g : «格位» → List «一堆») (u : «单位号») (k : «单位种类»)
    (h : ∀ name, name ≠ .«缓存» → f ⟨u,name⟩ = g ⟨u,name⟩) :
    unitOK f u k ↔ unitOK g u k := by
  cases k <;> simp only [unitOK]
  all_goals simp [h]

private def addAt (s : «状态») (g : «格位») (x : «物品») : «状态» :=
  { s with «货» := fun q => if q = g then «添几件» (s.«货» q) x 1 else s.«货» q }

private theorem add_other (s : «状态») (g : «格位») (x : «物品») (u : «单位号»)
    (k : «单位种类») (hu : u ≠ g.«单位») :
    unitOK (addAt s g x).«货» u k ↔ unitOK s.«货» u k := by
  apply unit_ext
  intro name _
  simp [addAt, show (⟨u,name⟩ : «格位») ≠ g by intro e; exact hu (congrArg «格位».«单位» e)]

private theorem add_factory (s : «状态») (u : «单位号») (k : «制造单位») (i : Nat) (x : «物品»)
    (h : unitOK s.«货» u (.«制造» k))
    (hr : room 50 (s.«货» ⟨u,.«存货» i⟩) x)
    (hx : ∀ j < k.«存货物品格数», j ≠ i → x ∉ (s.«货» ⟨u,.«存货» j⟩).map (·.«物»)) :
    unitOK (addAt s ⟨u,.«存货» i⟩ x).«货» u (.«制造» k) := by
  refine ⟨?_,?_,?_⟩
  · intro j hj
    by_cases he : j = i
    · subst j; simpa [addAt] using add_good (by decide : 0 < 50) hr
    · simpa [addAt, «格位».mk.injEq, he] using h.1 j hj
  · simpa [addAt, «格位».mk.injEq] using h.2.1
  · have hh := flat_update_nodup (List.range k.«存货物品格数»)
        (fun j => (s.«货» ⟨u,.«存货» j⟩).map (·.«物»)) i
        ((«添几件» (s.«货» ⟨u,.«存货» i⟩) x 1).map (·.«物»)) x
        (List.nodup_range) h.2.2 (add_nodup hr) (fun _ hm => add_mem hm)
        (fun j hj => hx j (List.mem_range.mp hj))
    have he : (fun j => ((addAt s ⟨u,.«存货» i⟩ x).«货» ⟨u,.«存货» j⟩).map (·.«物»)) =
        (fun j => if j = i then («添几件» (s.«货» ⟨u,.«存货» i⟩) x 1).map (·.«物»)
          else (s.«货» ⟨u,.«存货» j⟩).map (·.«物»)) := by
      funext j
      by_cases he : j = i <;> simp [addAt, «格位».mk.injEq, he]
    rw [he]; exact hh

private theorem flat_unique {α β : Type} [DecidableEq α]
    (is : List α) (f : α → List β) (i j : α) (x : β)
    (h : (is.flatMap f).Nodup) (hi : i ∈ is) (hj : j ∈ is)
    (hxi : x ∈ f i) (hxj : x ∈ f j) : i = j := by
  induction is with
  | nil => simp at hi
  | cons a is ih =>
    simp only [List.flatMap_cons, List.nodup_append] at h
    rcases List.mem_cons.mp hi with rfl | hi_tail
    · rcases List.mem_cons.mp hj with rfl | hj
      · rfl
      · exact False.elim (h.2.2 x hxi x (List.mem_flatMap.mpr ⟨j,hj,hxj⟩) rfl)
    · rcases List.mem_cons.mp hj with rfl | hj
      · exact False.elim (h.2.2 x hxj x (List.mem_flatMap.mpr ⟨i,hi_tail,hxi⟩) rfl)
      · exact ih h.2.1 hi_tail hj

private def gridRoom (L : «布局») (s : «状态») (x : «物品») (g : «格位») : Prop :=
  match L.«种类» g.«单位», g.«名» with
  | some .«传送带», .«格» 0 | some .«分流器», .«格» 0
  | some .«汇流器», .«格» 0 | some .«物品准入口», .«格» 0
  | some .«桥接器格», .«格» 0 => s.«货» g = []
  | some .«协议储存箱», .«格» i => i < 6 ∧ room 50 (s.«货» g) x
  | some (.«制造» k), .«存货» i =>
    i < k.«存货物品格数» ∧ room 50 (s.«货» g) x ∧
    ∀ j < k.«存货物品格数», j ≠ i → x ∉ (s.«货» ⟨g.«单位»,.«存货» j⟩).map (·.«物»)
  | _, _ => False

private def dstRoom (L : «布局») (s : «状态») (x : «物品») : «货位» → Prop
  | .«仓库» => s.«仓库» x < 80000
  | .«格» g => gridRoom L s x g

private theorem find_room {cap : Nat} {l : List «一堆»} {x : «物品»}
    (hr : (match l with | [] => true | p :: _ => p.«物» == x && p.«件数» < cap) = true)
    (hc : «一格合规矩» cap l = true) :
    room cap l x := by
  rcases one_cases hc with rfl | ⟨y,n,rfl,_,_⟩
  · exact Or.inl rfl
  · simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at hr
    exact Or.inr ⟨n, by simp [hr.1], hr.2⟩

private theorem some_if {α : Type} {b : Prop} [Decidable b] {a d : α}
    (h : (if b then some a else none) = some d) : b ∧ a = d := by
  split at h
  · exact ⟨by assumption, Option.some.inj h⟩
  · contradiction

private theorem put_room (L : «布局») (s : «状态») (c : «通道») (x : «物品») (d : «货位»)
    (hs : goods L s) (h : s.«放进哪» L c x = some d) : dstRoom L s x d := by
  unfold «状态».«放进哪» at h
  cases hk : L.«种类» c.«止» with
  | none => simp [hk] at h
  | some k =>
    have hu := hs.1 (c.«止»,k) (kind_mem L hk)
    cases k with
    | «传送带» | «分流器» | «汇流器» | «桥接器格» =>
      simp only [hk] at h
      obtain ⟨he,rfl⟩ := some_if h
      simpa [dstRoom, gridRoom, hk] using he
    | «物品准入口» =>
      simp only [hk] at h
      obtain ⟨he,rfl⟩ := some_if h
      simp only [Bool.and_eq_true] at he
      simpa [dstRoom, gridRoom, hk] using he.1.1.1
    | «仓库取货口» => simp [hk] at h
    | «协议核心» =>
      simp only [hk] at h
      obtain ⟨he,rfl⟩ := some_if h
      exact he
    | «协议储存箱» =>
      simp only [hk] at h
      obtain ⟨i,hi,rfl⟩ := Option.map_eq_some_iff.mp h
      have him : i < 6 := List.mem_range.mp (List.mem_of_find?_eq_some hi)
      simp only [dstRoom, gridRoom, hk]
      have hr := List.find?_some hi
      exact ⟨him, find_room hr (hu i him)⟩
    | «制造» k =>
      simp only [hk] at h
      split at h
      next i hi =>
        have him := List.mem_range.mp (List.mem_of_find?_eq_some hi)
        have hix : x ∈ (s.«货» ⟨c.«止»,.«存货» i⟩).map (·.«物») := by
          simpa only [List.any_eq_true, beq_iff_eq, List.mem_map] using List.find?_some hi
        split at h
        next hn =>
          simp only [Option.some.injEq] at h
          subst d
          simp only [dstRoom, gridRoom, hk]
          refine ⟨him,?_,?_⟩
          · rcases one_cases (hu.1 i him) with he | ⟨y,n,he,_,_⟩
            · simp [he] at hix
            · have hy : y = x := by simpa only [he, List.map_cons, List.map_nil, List.mem_singleton, eq_comm] using hix
              subst y
              exact Or.inr ⟨n,he,by simpa [«状态».«件数», he] using hn⟩
          · intro j hj hji hxj
            exact hji (flat_unique _ _ j i x hu.2.2 (List.mem_range.mpr hj)
              (List.mem_range.mpr him) hxj hix)
        next => simp_all
      next hi =>
        obtain ⟨i,he,rfl⟩ := Option.map_eq_some_iff.mp h
        have him := List.mem_range.mp (List.mem_of_find?_eq_some he)
        have hem : s.«货» ⟨c.«止»,.«存货» i⟩ = [] := by
          simpa only [List.isEmpty_iff] using List.find?_some he
        simp only [dstRoom, gridRoom, hk]
        refine ⟨him, Or.inl hem, ?_⟩
        intro j hj _
        have hn := List.find?_eq_none.mp hi j (List.mem_range.mpr hj)
        simpa [List.any_eq_false, List.mem_map] using hn

private theorem add_grid_goods (L : «布局») (s : «状态») (g : «格位») (x : «物品»)
    (ht : (L.«单位表».map (·.1)).Nodup) (hs : goods L s) (hr : gridRoom L s x g) :
    goods L (addAt s g x) := by
  refine ⟨?_, hs.2⟩
  rintro ⟨u,k⟩ hp
  by_cases hu : u = g.«单位»
  · have hk := mem_kind L ht hp
    cases g with
    | mk v name =>
      dsimp at hu
      subst v
      have ho := hs.1 (u,k) hp
      cases k <;> cases name <;> simp only [gridRoom, hk] at hr <;> try contradiction
      all_goals first
        | (split at hr <;> try contradiction
           simp_all [unitOK, addAt, «添几件», «一格合规矩», «格位».mk.injEq])
        | (rename_i i
           intro j hj
           by_cases he : j = i
           · subst j; simpa [addAt] using add_good (by decide : 0 < 50) hr.2
           · simpa [addAt, «格位».mk.injEq, he] using ho j hj)
        | exact add_factory s u _ _ x ho hr.2.1 hr.2.2
  · exact (add_other s g x u k hu).mpr (hs.1 (u,k) hp)

private def names (L : «布局») (u : «单位号») : List «格名» :=
  match L.«种类» u with
  | some .«协议储存箱» => (List.range 6).map «格名».«格»
  | some (.«制造» k) => (List.range k.«存货物品格数»).map «格名».«存货»
  | _ => []

private def readTab (s : «状态») (tab : List («格位» × List «一堆»)) (g : «格位») :=
  match tab.find? (·.1 == g) with
  | some (_,ps) => ps
  | none => s.«货» g

private theorem selected_mem (L : «布局») (s : «状态») (u : «单位号»)
    (x : «物品») (g : «格位») (hne : (names L u).isEmpty = false)
    (h : s.«放进哪» L ⟨u,u⟩ x = some (.«格» g)) :
    g ∈ (names L u).map (fun a => («格位».mk u a)) := by
  unfold names at *
  unfold «状态».«放进哪» at h
  cases hk : L.«种类» u with
  | none => simp [hk] at hne
  | some k =>
    cases k <;> simp only [hk] at hne h ⊢ <;> try contradiction
    · obtain ⟨i,hi,he⟩ := Option.map_eq_some_iff.mp h
      cases he
      exact List.mem_map.mpr ⟨.«格» i, List.mem_map.mpr
        ⟨i,List.mem_of_find?_eq_some hi,rfl⟩,rfl⟩
    · split at h
      next i hi =>
        split at h
        · cases h
          exact List.mem_map.mpr ⟨.«存货» i, List.mem_map.mpr
            ⟨i,List.mem_of_find?_eq_some hi,rfl⟩,rfl⟩
        · contradiction
      next hi =>
        obtain ⟨i,hi,he⟩ := Option.map_eq_some_iff.mp h
        cases he
        exact List.mem_map.mpr ⟨.«存货» i, List.mem_map.mpr
          ⟨i,List.mem_of_find?_eq_some hi,rfl⟩,rfl⟩

private theorem read_initial (s : «状态») (gs : List «格位») :
    readTab s (gs.map fun g => (g,s.«货» g)) = s.«货» := by
  funext g
  unfold readTab
  split
  next p hp =>
    have hm := List.mem_of_find?_eq_some hp
    obtain ⟨q,_,he⟩ := List.mem_map.mp hm
    have hq : q = g := by
      have hx := List.find?_some hp
      rw [← he] at hx
      simpa using hx
    cases he
    simp_all
  next => rfl

private theorem read_update (s : «状态») (tab : List («格位» × List «一堆»))
    (g : «格位») (x : «物品») (hm : g ∈ tab.map (·.1)) :
    readTab s (tab.map fun (h,ps) => (h, if h == g then «添几件» ps x 1 else ps)) =
      fun q => if q = g then «添几件» (readTab s tab q) x 1 else readTab s tab q := by
  funext q
  simp only [readTab, List.find?_map, Function.comp_def]
  cases hf : tab.find? (fun p => p.1 == q) with
  | none =>
    have hq : q ≠ g := by
      intro he; subst q
      obtain ⟨p,hp,hpg⟩ := List.mem_map.mp hm
      have := List.find?_eq_none.mp hf p hp
      simp [hpg] at this
    simp [hq]
  | some p =>
    have hp : p.1 = q := by simpa using List.find?_some hf
    simp [hp, beq_iff_eq]

private theorem add_progress (L : «布局») (s : «状态») (g : «格位») (x : «物品»)
    (hn : g.«名» ≠ .«缓存») (hs : progressOK L s) : progressOK L (addAt s g x) := by
  intro p hp
  have hh := hs p hp
  cases hk : p.2 <;> simp only [progressOK, hk] at hh ⊢ <;> try trivial
  have he : (⟨p.1,.«缓存»⟩ : «格位») ≠ g := by
    intro h
    exact hn (congrArg «格位».«名» h).symm
  simpa [cacheOK, addAt, he] using hh

private theorem selected_not_cache (L : «布局») (s : «状态») (u : «单位号»)
    (x : «物品») (g : «格位») (hne : (names L u).isEmpty = false)
    (h : s.«放进哪» L ⟨u,u⟩ x = some (.«格» g)) : g.«名» ≠ .«缓存» := by
  have hm := selected_mem L s u x g hne h
  obtain ⟨a,ha,rfl⟩ := List.mem_map.mp hm
  unfold names at ha
  split at ha <;> simp_all
  all_goals obtain ⟨i,_,rfl⟩ := ha; simp

private theorem fold_preserve {α β : Type} (P : β → Prop) (f : β → α → β)
    (xs : List α) (b : β) (hf : ∀ b a, P b → P (f b a)) (hb : P b) :
    P (xs.foldl f b) := by
  induction xs generalizing b with
  | nil => exact hb
  | cons a xs ih => exact ih _ (hf b a hb)

/-- 据：物品格、协议储存箱、存货/取货物品格

合规历史和合规货物的状态里，玩家放入任意件货以后，货仍合规矩。 -/
theorem «格子层的放进单位守规矩» : «命题».«格子层的放进单位守规矩» := by
  intro F o bad s u x n hh hs
  change ({s with «货» := «格子».«放进单位» s u x n} : «状态»).«货合规矩»
  have ht := (s.«历史».«合规则整齐» hh s.«历史».length).«单位不重»
  let stock := ((names s.«布局» u).map fun a =>
    let g := «格位».mk u a
    (g,s.«货» g))
  let P := fun tab : List («格位» × List «一堆») =>
    tab.map (·.1) = (names s.«布局» u).map (fun a => «格位».mk u a) ∧
    goods s.«布局» {s with «货» := readTab s tab} ∧
    progressOK s.«布局» {s with «货» := readTab s tab}
  have hinit : P stock := by
    have hr : readTab s stock = s.«货» := by
      simpa [stock, List.map_map, Function.comp_def] using read_initial s
        ((names s.«布局» u).map (fun a => «格位».mk u a))
    refine ⟨by simp [stock, List.map_map], ?_⟩
    rw [hr]
    exact (goods_iff _ _).mpr hs
  have hfold := fold_preserve P
    (fun tab (_ : Nat) => if (names s.«布局» u).isEmpty then tab else
      match ({s with «货» := readTab s tab} : «状态»).«放进哪» s.«布局» ⟨u,u⟩ x with
      | some (.«格» g) => tab.map fun (h,ps) => (h, if h == g then «添几件» ps x 1 else ps)
      | _ => tab) (List.range n) stock ?_ hinit
  · have hout := (goods_iff _ _).mp hfold.2
    exact hout
  · intro tab a hp
    dsimp only
    split
    · exact hp
    next hn =>
      have hne : (names s.«布局» u).isEmpty = false := by simpa using hn
      split
      next g hg =>
        have hm := selected_mem s.«布局» {s with «货» := readTab s tab} u x g hne hg
        have hr := read_update s tab g x (by rw [hp.1]; exact hm)
        refine ⟨by simpa only [List.map_map, Function.comp_def] using hp.1, ?_⟩
        rw [hr]
        exact ⟨add_grid_goods _ _ _ _ ht hp.2.1 (put_room _ _ _ _ _ hp.2.1 hg),
          add_progress _ _ _ _ (selected_not_cache _ _ _ _ _ hne hg) hp.2.2⟩
      next => exact hp

end Endfield.«证明»
