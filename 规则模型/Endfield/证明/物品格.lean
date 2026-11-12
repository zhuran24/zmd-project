import Endfield.«证明».«基础»

/-!
证明「走一步守物品格的规矩」。先证明拿货、按收货条件添货以及制造、传输保持各格的容量
和制造单位存货的物品种类不重复，再沿判定中的折叠逐段归纳。走步不改历史，因而布局固定。
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

private theorem goods_iff (L : «布局») (s : «状态») :
    goods L s ↔ s.«各格合规矩» L = true ∧ ∀ x, s.«仓库» x ≤ 80000 := by
  simp only [goods, «状态».«各格合规矩», List.all_eq_true]
  apply and_congr_left';
  apply forall_congr'; intro p
  apply imp_congr_right; intro _
  cases p.2 <;> simp [unitOK, List.all_eq_true, Bool.and_eq_true,
    List.mem_range, List.flatMap_map, and_assoc]

private theorem one_cases {cap : Nat} {l : List «一堆»} (h : «一格合规矩» cap l = true) :
    l = [] ∨ ∃ x n, l = [⟨x,n⟩] ∧ 1 ≤ n ∧ n ≤ cap := by
  cases l with
  | nil => exact Or.inl rfl
  | cons p l =>
    cases l with
    | nil => exact Or.inr ⟨p.«物», p.«件数», rfl, by simpa [«一格合规矩»] using h⟩
    | cons q l => simp [«一格合规矩»] at h

private theorem take_good {cap : Nat} {l : List «一堆»} (h : «一格合规矩» cap l = true)
    (x : «物品») (n : Nat) : «一格合规矩» cap («拿几件» l x n) = true := by
  rcases one_cases h with rfl | ⟨y,m,rfl,hm,hc⟩
  · simp [«拿几件», «一格合规矩»]
  · by_cases hy : y = x <;> by_cases hn : n < m <;>
      simp [«拿几件», hy, show (m - n > 0) ↔ n < m by omega, hn,
        show m > 0 by omega, «一格合规矩»] <;> omega

private theorem take_sub (l : List «一堆») (x : «物品») (n : Nat) :
    («拿几件» l x n).map (·.«物») <+ l.map (·.«物») := by
  induction l with
  | nil => simp [«拿几件»]
  | cons p l ih =>
    simp only [«拿几件», List.map_cons, List.filter_cons] at *
    by_cases hx : p.«物» = x <;> simp only [hx, beq_iff_eq, ↓reduceIte] at *
    all_goals split <;> try simp only [List.map_cons]
    all_goals first | exact ih.cons_cons _ | exact ih.cons _

private theorem flat_sub {α β : Type} (is : List α) (f g : α → List β)
    (h : ∀ i ∈ is, f i <+ g i) : is.flatMap f <+ is.flatMap g := by
  induction is with
  | nil => simp
  | cons i is ih =>
    simp only [List.flatMap_cons]
    exact (h i (by simp)).append (ih (fun j hj => h j (by simp [hj])))

private theorem unit_shrink (f g : «格位» → List «一堆») (u : «单位号») (k : «单位种类»)
    (h : unitOK f u k)
    (hc : ∀ name, name ≠ .«缓存» → ∀ cap, «一格合规矩» cap (f ⟨u,name⟩) = true →
      «一格合规矩» cap (g ⟨u,name⟩) = true)
    (hs : ∀ i, (g ⟨u,.«存货» i⟩).map (·.«物») <+ (f ⟨u,.«存货» i⟩).map (·.«物»)) :
    unitOK g u k := by
  cases k <;> simp only [unitOK] at *
  all_goals first
    | exact hc _ (by simp) _ h
    | exact trivial
    | exact fun i hi => hc _ (by simp) _ (h i hi)
    | exact ⟨fun i hi => hc _ (by simp) _ (h.1 i hi), hc _ (by simp) _ h.2.1,
        h.2.2.sublist (flat_sub _ _ _ (fun i _ => hs i))⟩

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

private theorem room_take {cap : Nat} {l : List «一堆»} {x : «物品»}
    (h : room cap l x) : room cap («拿几件» l x 1) x := by
  rcases h with rfl | ⟨n,rfl,hn⟩
  · exact Or.inl (by simp [«拿几件»])
  · by_cases hh : 1 < n
    · exact Or.inr ⟨n-1, by simp [«拿几件», show n-1>0 by omega], by omega⟩
    · exact Or.inl (by simp [«拿几件», show ¬n-1>0 by omega])

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

private def remove (s : «状态») (src : «货位») (x : «物品») : «状态» :=
  { s with «货» := fun g => if src = .«格» g then «拿几件» (s.«货» g) x 1 else s.«货» g }

private theorem remove_goods (L : «布局») (s : «状态») (src : «货位») (x : «物品»)
    (h : goods L s) : goods L (remove s src x) := by
  refine ⟨?_, h.2⟩
  intro p hp
  apply unit_shrink _ _ _ _ (h.1 p hp)
  · intro name _ cap hc
    dsimp only [remove]
    split
    · exact take_good hc x 1
    · exact hc
  · intro i
    dsimp only [remove]
    split
    · exact take_sub _ _ _
    · exact List.Sublist.refl _

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

private theorem grid_remove (L : «布局») (s : «状态») (src : «货位») (x : «物品»)
    (g : «格位») (h : gridRoom L s x g) : gridRoom L (remove s src x) x g := by
  rcases g with ⟨u,name⟩
  cases hk : L.«种类» u with
  | none => simp [gridRoom, hk] at h
  | some k =>
    cases k <;> cases name <;> simp only [gridRoom, hk] at h ⊢ <;> try contradiction
    all_goals first
      | (solve | rename_i i; cases i <;> simp_all [remove, «拿几件»])
      | (solve | refine ⟨h.1, ?_⟩; dsimp only [remove]; split <;> first | exact room_take h.2 | exact h.2)
      | (refine ⟨h.1, ?_, ?_⟩
         · dsimp only [remove]; split <;> first | exact room_take h.2.1 | exact h.2.1
         · intro j hj hji hm
           apply h.2.2 j hj hji
           dsimp only [remove] at hm
           split at hm
           · exact (take_sub _ _ _).subset hm
           · exact hm)

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

private theorem unless_some {α : Type} {b : Prop} [Decidable b] {a d : α}
    (h : (if b then none else some a) = some d) : a = d := by
  split at h
  · contradiction
  · exact Option.some.inj h

private theorem move_goods (L : «布局») (s : «状态») (c : «通道»)
    (port : «通道» → Nat) (x : «物品») (src dst : «货位»)
    (ht : (L.«单位表».map (·.1)).Nodup) (hs : goods L s)
    (hm : s.«能移» L port c = some (x,src,dst)) :
    goods L (s.«移一件» L c x src dst) := by
  have hp : s.«放进哪» L c x = some dst := by
    unfold «状态».«能移» at hm
    split at hm <;> try contradiction
    next y a ha =>
      split at hm <;> try contradiction
      next d hd =>
        have he := unless_some hm
        simp only [Prod.mk.injEq] at he
        rcases he with ⟨rfl,rfl,rfl⟩
        exact hd
  have hr := put_room L s c x dst hs hp
  have hs' := remove_goods L s src x hs
  refine ⟨?_,?_⟩
  · cases dst with
    | «仓库» => simpa only [«状态».«移一件», remove, reduceCtorEq, ↓reduceIte] using hs'.1
    | «格» g =>
      have hh := (add_grid_goods L (remove s src x) g x ht hs' (grid_remove L s src x g hr)).1
      simpa only [«状态».«移一件», addAt, remove, «货位».«格».injEq, eq_comm] using hh
  · intro y
    have hy := hs.2 y
    dsimp only [«状态».«移一件»]
    by_cases he : y = x
    · subst y
      cases dst <;> simp only [dstRoom] at hr <;>
        simp only [↓reduceIte, reduceCtorEq] <;> split <;> omega
    · simp [he, hy]

private theorem end_goods (L : «布局») (s : «状态») (u : «单位号») (r : «配方»)
    (hs : goods L s) : goods L (s.«结束一次制造» u r) := by
  refine ⟨?_, hs.2⟩
  intro p hp
  apply (unit_ext _ _ p.1 p.2 ?_).mpr (hs.1 p hp)
  intro name hn
  simp [«状态».«结束一次制造», «格位».mk.injEq, hn]

private theorem take_fold (ps : List («物品» × Nat)) (l : List «一堆») (cap : Nat)
    (h : «一格合规矩» cap l = true) :
    «一格合规矩» cap (ps.foldl (fun l p => «拿几件» l p.1 p.2) l) = true ∧
    (ps.foldl (fun l p => «拿几件» l p.1 p.2) l).map (·.«物») <+ l.map (·.«物») := by
  induction ps generalizing l with
  | nil => exact ⟨h, List.Sublist.refl _⟩
  | cons p ps ih =>
    have hh := ih _ (take_good h p.1 p.2)
    exact ⟨hh.1, hh.2.trans (take_sub _ _ _)⟩

private theorem take_fold_sub (ps : List («物品» × Nat)) (l : List «一堆») :
    (ps.foldl (fun l p => «拿几件» l p.1 p.2) l).map (·.«物») <+ l.map (·.«物») := by
  induction ps generalizing l with
  | nil => exact List.Sublist.refl _
  | cons p ps ih => exact (ih _).trans (take_sub _ _ _)

private theorem start_goods (L : «布局») (s : «状态») (u : «单位号») (r : «配方»)
    (hs : goods L s) : goods L (s.«开始一次制造» u r) := by
  refine ⟨?_,hs.2⟩
  intro p hp
  apply unit_shrink _ _ _ _ (hs.1 p hp)
  · intro name hn cap hc
    dsimp only [«状态».«开始一次制造»]
    split
    · cases name <;> try contradiction
      all_goals first | exact hc | exact (take_fold _ _ _ hc).1
    · exact hc
  · intro i
    dsimp only [«状态».«开始一次制造»]
    split
    · exact take_fold_sub _ _
    · exact List.Sublist.refl _

private theorem batch_good (s : «状态») (u : «单位号»)
    (hc : «一格合规矩» 50 (s.«货» ⟨u,.«取货»⟩) = true)
    (h : s.«进得去» u = true) :
    «一格合规矩» 50 ((s.«进取货格» u).«货» ⟨u,.«取货»⟩) = true := by
  simp only [«状态».«进得去», Bool.and_eq_true] at h
  obtain ⟨_,h⟩ := h
  dsimp only [«状态».«进取货格»]
  simp only [↓reduceIte]
  split at h <;> try contradiction
  next p he hc' =>
    simp only [he, hc', List.foldl_cons, List.foldl_nil]
    by_cases hn : p.«件数» = 0
    · simp [«添几件», hn, «一格合规矩»]
    · simp [«添几件», hn, «一格合规矩»]
      simpa only [decide_eq_true_eq] using And.intro (by omega : 1 ≤ p.«件数») (of_decide_eq_true h)
  next p q he hc' =>
    simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at h
    have hq := one_cases hc
    simp only [hc', «一格合规矩», Bool.and_eq_true, decide_eq_true_eq] at hc
    simp only [he, hc', List.foldl_cons, List.foldl_nil]
    by_cases hn : p.«件数» = 0
    · simpa [«添几件», hn, «一格合规矩»] using hc
    · simp [«添几件», hn, h.1, «一格合规矩»]
      omega

private theorem batch_goods (L : «布局») (s : «状态») (u : «单位号») (k : «制造单位»)
    (ht : (L.«单位表».map (·.1)).Nodup) (hk : L.«种类» u = some (.«制造» k))
    (hs : goods L s) (hb : s.«进得去» u = true) : goods L (s.«进取货格» u) := by
  refine ⟨?_,hs.2⟩
  rintro ⟨v,kind⟩ hp
  by_cases he : v = u
  · subst v
    have he := mem_kind L ht hp
    rw [hk] at he
    cases Option.some.inj he
    have ho := hs.1 (u,.«制造» k) hp
    refine ⟨?_,batch_good s u ho.2.1 hb,?_⟩
    · simpa [«状态».«进取货格», «格位».mk.injEq] using ho.1
    · simpa [«状态».«进取货格», «格位».mk.injEq] using ho.2.2
  · apply (unit_ext _ _ v kind ?_).mpr (hs.1 (v,kind) hp)
    intro name _
    simp [«状态».«进取货格», «格位».mk.injEq, he]

private theorem fold_preserve {α β : Type} (P : β → Prop) (f : β → α → β)
    (hf : ∀ b a, P b → P (f b a)) (as : List α) (b : β) (hb : P b) : P (as.foldl f b) := by
  induction as generalizing b with
  | nil => exact hb
  | cons a as ih => exact ih _ (hf b a hb)

private theorem transfer_result (s : «状态») (u : «单位号»)
    (hg : ∀ i < 6, «一格合规矩» 50 (s.«货» ⟨u,.«格» i⟩) = true)
    (hw : ∀ x, s.«仓库» x ≤ 80000) :
    (∀ i < 6, «一格合规矩» 50 ((s.«传输结果» u).1 i) = true) ∧
    (∀ x, (s.«传输结果» u).2 x ≤ 80000) := by
  unfold «状态».«传输结果»
  apply fold_preserve (fun acc : (Nat → List «一堆») × («物品» → Nat) => (∀ i < 6, «一格合规矩» 50 (acc.1 i) = true) ∧
    (∀ x, acc.2 x ≤ 80000)) _ _ _ _ ⟨hg,hw⟩
  intro acc i ha
  try dsimp only
  split
  next p he =>
    refine ⟨?_,?_⟩
    · intro j hj
      by_cases hji : j = i
      · subst j
        have hi := hg i hj
        rw [he] at hi
        simp only [«一格合规矩», Bool.and_eq_true, decide_eq_true_eq] at hi
        simp only [«换», ↓reduceIte]
        split
        · rfl
        next hn =>
          simp only [«一格合规矩», Bool.and_eq_true, decide_eq_true_eq]
          have hm := Nat.min_le_left p.«件数» (80000 - acc.2 p.«物»)
          simp only [beq_iff_eq] at hn
          omega
      · simpa only [«换», hji, ↓reduceIte] using ha.1 j hj
    · intro y
      dsimp only [«换»]
      split
      next heq =>
        subst y
        have hw := ha.2 p.«物»
        have hm := Nat.min_le_right p.«件数» (80000 - acc.2 p.«物»)
        omega
      next => exact ha.2 y
  next => exact ha

private theorem transfer_goods (L : «布局») (s : «状态») (u : «单位号»)
    (ht : (L.«单位表».map (·.1)).Nodup) (hk : L.«种类» u = some .«协议储存箱»)
    (hs : goods L s) : goods L (s.«传输一次» u) := by
  have ho := hs.1 (u,.«协议储存箱») (kind_mem L hk)
  have hh := transfer_result s u ho hs.2
  refine ⟨?_,hh.2⟩
  rintro ⟨v,k⟩ hp
  by_cases he : v = u
  · subst v
    have he := mem_kind L ht hp
    rw [hk] at he
    cases Option.some.inj he
    simpa [unitOK, «状态».«传输一次»] using hh.1
  · apply (unit_ext _ _ v k ?_).mpr (hs.1 (v,k) hp)
    intro name _
    simp [«状态».«传输一次», he]

private theorem forward_goods (T : «判定表») (port : «通道» → Nat) (s : «状态»)
    (ht : (T.«现布局».«单位表».map (·.1)).Nodup) (hs : goods T.«现布局» s) :
    goods T.«现布局» (s.«前移一遍» T port).1 := by
  unfold «状态».«前移一遍»
  apply fold_preserve (fun acc : «状态» × Bool => goods T.«现布局» acc.1) _ _ _ _ hs
  intro acc c ha
  try dsimp only
  split
  next x a b he => exact move_goods _ _ _ _ _ _ _ ht ha he
  next => exact ha

private theorem tidy_goods (T : «判定表») (port : «通道» → Nat) (fuel : Nat) (s : «状态»)
    (ht : (T.«现布局».«单位表».map (·.1)).Nodup) (hs : goods T.«现布局» s) :
    goods T.«现布局» («状态».«整理» T port fuel s) := by
  induction fuel generalizing s with
  | zero => exact hs
  | succ fuel ih =>
    have hh := forward_goods T port s ht hs
    simp only [«状态».«整理»]
    split
    · exact ih _ hh
    · exact hh

private theorem group_goods (T : «判定表») (port : «通道» → Nat) (sel : «通道» → Bool)
    (cs : List «通道») (s : «状态»)
    (ht : (T.«现布局».«单位表».map (·.1)).Nodup) (hs : goods T.«现布局» s) :
    goods T.«现布局» (s.«判一组» T port sel cs) := by
  unfold «状态».«判一组»
  apply fold_preserve (goods T.«现布局») _ _ _ _ hs
  intro s c hs
  try dsimp only
  split
  · exact hs
  · split
    next x a b he => exact tidy_goods _ _ _ _ ht (move_goods _ _ _ _ _ _ _ ht hs he)
    next => exact hs

private theorem components_goods (T : «判定表») (port : «通道» → Nat) (sel : «通道» → Bool)
    (s : «状态») (ht : (T.«现布局».«单位表».map (·.1)).Nodup) (hs : goods T.«现布局» s) :
    goods T.«现布局» (s.«元件的移动判定» T port sel) := by
  unfold «状态».«元件的移动判定»
  apply fold_preserve (goods T.«现布局») _ _ _ _ hs
  intro s p hs
  exact group_goods _ _ _ _ _ ht hs

private theorem select_goods (T : «判定表») (un : «未定») (todo : «待写»)
    (port : «通道» → Nat) (sel : «通道» → Bool) (s : «状态»)
    (p : «单位号» × List («组» × List «通道»))
    (ht : (T.«现布局».«单位表».map (·.1)).Nodup) (hs : goods T.«现布局» s) :
    goods T.«现布局» (s.«选取» T un todo port sel p) := by
  have trans (s : «状态») (hs : goods T.«现布局» s) : goods T.«现布局»
      (if s.«该传输» T.«现布局» un todo p.1 then s.«传输一次» p.1 else s) := by
    split
    next he =>
      have hk : T.«现布局».«种类» p.1 = some .«协议储存箱» := by
        simp only [«状态».«该传输», Bool.and_eq_true, beq_iff_eq] at he
        exact he.1.1.1.1
      exact transfer_goods _ _ _ ht hk hs
    next => exact hs
  have moves (s : «状态») (isM : Bool) (hs : goods T.«现布局» s) : goods T.«现布局»
      (p.2.foldl (fun s g => s.«判一组» T port sel
        (match g.1 with
        | .«出货的» _ => «出货先后» isM g.2 (s.«出货已移动» p.1)
        | _ => g.2)) s) := by
    apply fold_preserve (goods T.«现布局») _ _ _ _ hs
    intro s g hs
    exact group_goods _ _ _ _ _ ht hs
  unfold «状态».«选取»
  try dsimp only
  split
  · exact moves _ _ (trans s hs)
  · exact trans _ (moves s _ hs)

private theorem nontransport_goods (T : «判定表») (un : «未定») (todo : «待写»)
    (port : «通道» → Nat) (sel : «通道» → Bool) (s : «状态»)
    (ht : (T.«现布局».«单位表».map (·.1)).Nodup) (hs : goods T.«现布局» s) :
    goods T.«现布局» (s.«非运输单位的移动判定» T un todo port sel) := by
  unfold «状态».«非运输单位的移动判定»
  apply fold_preserve (goods T.«现布局») _ _ _ _ hs
  intro s p hs
  exact select_goods _ _ _ _ _ _ _ ht hs

private theorem endcheck_goods (L : «布局») (todo : «待写») (us : List «单位号») (s : «状态»)
    (ht : (L.«单位表».map (·.1)).Nodup) (hs : goods L s) :
    goods L (s.«结束制造判定» L todo us) := by
  unfold «状态».«结束制造判定»
  apply fold_preserve (goods L) _ _ _ _ hs
  intro s u hs
  try dsimp only
  split
  next k hk =>
    have hb (s : «状态») (hs : goods L s) : goods L
        (if s.«进得去» u then s.«进取货格» u else s) := by
      split
      next he => exact batch_goods _ _ _ _ ht hk hs he
      next => exact hs
    apply hb
    split
    · split
      · exact end_goods _ _ _ _ hs
      · exact hs
    · exact hs
  next => exact hs

private theorem startcheck_goods (L : «布局») (todo : «待写») (us : List «单位号») (s : «状态»)
    (hs : goods L s) : goods L (s.«开始制造判定» L todo us) := by
  unfold «状态».«开始制造判定»
  apply fold_preserve (goods L) _ _ _ _ hs
  intro s u hs
  try dsimp only
  split
  · split
    · split
      · exact start_goods _ _ _ _ hs
      · exact hs
    · exact hs
  · exact hs

private theorem step_goods (T : «判定表») (un : «未定») (todo : «待写») (s : «状态»)
    (ht : (T.«现布局».«单位表».map (·.1)).Nodup) (hs : goods T.«现布局» s) :
    goods T.«现布局» («一步于» T un todo s) := by
  unfold «一步于»
  change goods T.«现布局» («计时» un todo _)
  have clock (s : «状态») (hs : goods T.«现布局» s) :
      goods T.«现布局» («计时» un todo s) := hs
  apply clock
  apply startcheck_goods
  apply nontransport_goods _ _ _ _ _ _ ht
  apply components_goods _ _ _ _ ht
  apply endcheck_goods _ _ _ _ ht
  exact tidy_goods _ _ _ _ ht hs

/-- 据：物品格、运输单位、协议储存箱、存货/取货物品格

初态的货合规且历史合规时，走一步后每个物品格、制造单位存货的种类和仓库件数仍然合规。 -/
theorem «走一步守物品格的规矩» : «命题».«走一步守物品格的规矩» := by
  intro un todo s hh hs
  have ht := (s.«历史».«合规则整齐» hh s.«历史».length).«单位不重»
  have hg : goods s.«历史».«立表».«现布局» s := (goods_iff _ s).mpr hs
  have ho := (goods_iff _ _).mp (step_goods s.«历史».«立表» un todo s ht hg)
  have hl : («一步» un todo s).«布局» = s.«布局» := by
    unfold «状态».«布局»
    rw [«一步不改历史»]
  refine ⟨?_,ho.2⟩
  rw [hl]
  exact ho.1

end Endfield.«证明»
