import Endfield.«证明».«基础»

/-!
证明操作守物品格的规矩、可达状态货合规矩。逐类检查操作：新建清空、拆除删项、
收货只删去一格，离线由单位表等长且包含推出反向包含。最后沿操作表归纳，
同时保持历史合规与货合规矩。
-/

namespace Endfield.«证明»

open List

private def unitOK (s : «状态») (u : «单位号») : «单位种类» → Prop
  | .«传送带» | .«分流器» | .«汇流器» | .«物品准入口» | .«桥接器格» =>
    «一格合规矩» 1 (s.«货» ⟨u, .«格» 0⟩) = true
  | .«协议储存箱» => ∀ i < 6, «一格合规矩» 50 (s.«货» ⟨u, .«格» i⟩) = true
  | .«制造» k =>
    (∀ i < k.«存货物品格数», «一格合规矩» 50 (s.«货» ⟨u, .«存货» i⟩) = true) ∧
    «一格合规矩» 50 (s.«货» ⟨u, .«取货»⟩) = true ∧
    ((List.range k.«存货物品格数»).flatMap fun i => (s.«货» ⟨u, .«存货» i⟩).map (·.«物»)).Nodup ∧
    (match s.«制造中» u with
      | some (r, _) =>
          «配方表».contains r && r.«单位» == k
            && s.«货» ⟨u, .«缓存»⟩ == r.«原料».map fun q => ⟨q.1, q.2⟩
      | none =>
          (s.«货» ⟨u, .«缓存»⟩).isEmpty ||
            «配方表».any fun r =>
              r.«单位» == k && s.«货» ⟨u, .«缓存»⟩ == [⟨r.«产物».1, r.«产物».2⟩]) = true
  | .«协议核心» | .«仓库取货口» => True

private theorem all_iff (L : «布局») (s : «状态») :
    s.«各格合规矩» L = true ↔ ∀ p ∈ L.«单位表», unitOK s p.1 p.2 := by
  simp only [«状态».«各格合规矩», List.all_eq_true]
  apply forall_congr'; intro p
  apply imp_congr_right; intro _
  cases p.2 <;> simp [unitOK, List.all_eq_true, List.mem_range,
    Bool.and_eq_true, List.flatMap_map, and_assoc]
  all_goals intros; cases s.«制造中» p.1 <;> rfl

private theorem unit_congr (s t : «状态») (u : «单位号») (k : «单位种类»)
    (hf : ∀ n, t.«货» ⟨u,n⟩ = s.«货» ⟨u,n⟩)
    (hm : t.«制造中» u = s.«制造中» u) : unitOK s u k → unitOK t u k := by
  cases k <;> simp_all [unitOK]

private theorem empty_unit (s : «状态») (u : «单位号») (k : «单位种类»)
    (hf : ∀ n, s.«货» ⟨u,n⟩ = []) (hm : s.«制造中» u = none) : unitOK s u k := by
  cases k <;> simp [unitOK, hf, hm, «一格合规矩»]
  rw [show (List.range _).flatMap (fun _ => ([] : List «物品»)) = [] from
    List.flatMap_eq_nil_iff.mpr (by simp)]
  exact List.nodup_nil

private theorem flat_sub {α β : Type} (is : List α) (f g : α → List β)
    (h : ∀ i ∈ is, f i <+ g i) : is.flatMap f <+ is.flatMap g := by
  induction is with
  | nil => simp
  | cons i is ih =>
    exact (h i (by simp)).append (ih (fun j hj => h j (by simp [hj])))

private theorem collect_unit (s : «状态») (g : «格位») (hg : g.«名» ≠ .«缓存»)
    (u : «单位号») (k : «单位种类») (h : unitOK s u k) :
    unitOK { s with «货» := «换» s.«货» g [] } u k := by
  have hc (n : «格名») (cap : Nat) (ho : «一格合规矩» cap (s.«货» ⟨u,n⟩) = true) :
      «一格合规矩» cap («换» s.«货» g [] ⟨u,n⟩) = true := by
    unfold «换»
    split
    · rfl
    · exact ho
  have hs (i : Nat) : («换» s.«货» g [] ⟨u,.«存货» i⟩).map (·.«物») <+
      (s.«货» ⟨u,.«存货» i⟩).map (·.«物») := by
    unfold «换»
    split
    · simp
    · exact List.Sublist.refl _
  have he : (⟨u,.«缓存»⟩ : «格位») ≠ g := by
    intro e
    exact hg (congrArg «格位».«名» e.symm)
  cases k <;> simp only [unitOK] at h ⊢
  all_goals first
    | exact trivial
    | exact hc _ _ h
    | exact fun i hi => hc _ _ (h i hi)
    | exact ⟨fun i hi => hc _ _ (h.1 i hi), hc _ _ h.2.1,
        h.2.2.1.sublist (flat_sub _ _ _ (fun i _ => hs i)),
        by simpa [«换», he] using h.2.2.2⟩

private theorem append_layout (H : «历史») (e : «事件») :
    (H ++ [e]).«布局于» (H.length + 1) =
      (H.«布局于» H.length).«加» (H.length + 1) e := by
  rw [«历史».«布局于后继» _ _ e (by simp)]
  simp [«历史».«布局于»]

private theorem reverse_subset {α : Type} {xs ys : List α}
    (hn : xs.Nodup) (hl : ys.length = xs.length) (hs : xs ⊆ ys) : ys ⊆ xs := by
  classical
  intro a ha
  by_cases hnmem : a ∈ xs
  · exact hnmem
  apply False.elim
  have hh : (a :: xs).Nodup := List.nodup_cons.mpr ⟨hnmem, hn⟩
  have hsub : a :: xs ⊆ ys := by
    intro b hb
    rcases List.mem_cons.mp hb with rfl | hb
    · exact ha
    · exact hs hb
  have := hh.length_le_of_subset hsub
  simp only [List.length_cons] at this
  omega

/-- 据：物品格、运输单位、协议储存箱、存货/取货物品格、缓存格

历史合规且玩家放货守规矩时，每个成功操作都保持货合规矩。 -/
theorem «操作守物品格的规矩» (hstep : «命题».«走一步守物品格的规矩») :
    «命题».«操作守物品格的规矩» := by
  intro un todo s t o hp hh hg ho
  have hd : o.«做得了» s = true := by
    rw [← «做得了才有结果» un todo s o, ho]; rfl
  have hu := (all_iff s.«布局» s).mp hg.1
  cases o with
  | «走一步» =>
    simp [«作用», hd] at ho
    cases ho
    exact hstep un todo s hh hg
  | «改布局» e =>
    cases e with
    | «建成» u k =>
      simp [«作用», hd] at ho
      cases ho
      refine ⟨(all_iff _ _).mpr ?_, hg.2⟩
      intro p hm
      simp only [«状态».«布局», List.length_append, List.length_singleton, append_layout, «布局».«加», List.mem_append,
        List.mem_singleton] at hm
      rcases hm with hm | rfl
      · have hn : p.1 ≠ u := by
          have hk : s.«布局».«种类» u = none := by
            simp only [«操作».«做得了», «布局».«容得下», Bool.and_eq_true,
              Option.isNone_iff_eq_none] at hd
            exact hd.1
          intro he
          have hf := List.find?_eq_none.mp (show s.«布局».«单位表».find? (fun q => q.1 == u) = none from
            by simpa [«布局».«种类»] using hk)
          have := hf p hm
          simp [he] at this
        apply unit_congr s _ p.1 p.2 (fun n => by simp [hn]) (by simp [«换», hn])
        exact hu p hm
      · apply empty_unit <;> simp [«换»]
    | «接通» c =>
      simp [«作用», hd] at ho
      cases ho
      refine ⟨?_,hg.2⟩
      apply (all_iff _ _).mpr
      intro p hm
      apply unit_congr s _ p.1 p.2 (fun _ => rfl) rfl
      apply hu p
      simpa only [«状态».«布局», List.length_append, List.length_singleton, append_layout, «布局».«加»] using hm
    | «拆除» u =>
      simp [«作用», hd] at ho
      cases ho
      refine ⟨(all_iff _ _).mpr ?_, ?_⟩
      · intro p hm
        have hm' : p ∈ s.«布局».«单位表» ∧ p.1 ≠ u := by
          simpa [«状态».«布局», List.length_append, List.length_singleton, append_layout, «布局».«加»] using hm
        apply unit_congr s _ p.1 p.2 (fun n => by simp [hm'.2]) (by simp [«换», hm'.2])
        exact hu p hm'.1
      · intro x
        dsimp
        split
        · exact Nat.max_le.mpr ⟨hg.2 x, Nat.min_le_left _ _⟩
        · exact hg.2 x
  | «放货» u x n =>
    simp [«作用», hd] at ho
    cases ho
    exact hp s u x n hh hg
  | «收货» g =>
    have hname : g.«名» ≠ .«缓存» := by
      simp only [«操作».«做得了», Bool.and_eq_true, bne_iff_ne] at hd
      exact hd.1.2
    simp [«作用», hd] at ho
    cases ho
    exact ⟨(all_iff _ _).mpr (fun p hm => collect_unit s g hname p.1 p.2 (hu p hm)), hg.2⟩
  | «入库» x n =>
    have hc : s.«仓库» x + n ≤ 80000 := by simpa [«操作».«做得了»] using hd
    simp [«作用», hd] at ho
    cases ho
    refine ⟨hg.1, ?_⟩
    intro y
    change (if y = x then _ else _) ≤ _
    split
    · exact hc
    · exact hg.2 y
  | «出库» x n =>
    simp [«作用», hd] at ho
    cases ho
    refine ⟨hg.1, ?_⟩
    intro y
    change (if y = x then _ else _) ≤ _
    split
    · exact Nat.le_trans (Nat.sub_le _ _) (hg.2 x)
    · exact hg.2 y
  | «离线» H =>
    have hlen : (H.«布局于» H.length).«单位表».length = s.«布局».«单位表».length := by
      simp only [«操作».«做得了», Bool.and_eq_true, beq_iff_eq] at hd
      exact hd.1.1.1.2
    have hsub : s.«布局».«单位表» ⊆ (H.«布局于» H.length).«单位表» := by
      intro p hm
      have ha : s.«布局».«单位表».all ((H.«布局于» H.length).«单位表».contains ·) = true := by
        simp only [«操作».«做得了», Bool.and_eq_true] at hd
        exact hd.1.1.2
      simpa using List.all_eq_true.mp ha p hm
    have hn : s.«布局».«单位表».Nodup :=
      List.Pairwise.of_map (·.1) (by intros a b hab he; exact hab (congrArg Prod.fst he))
        (s.«历史».«合规则整齐» hh s.«历史».length).«单位不重»
    have hr := reverse_subset hn hlen hsub
    simp [«作用», hd] at ho
    cases ho
    exact ⟨(all_iff _ _).mpr (fun p hm => hu p (hr hm)), hg.2⟩
  | _ =>
    simp [«作用», hd] at ho
    cases ho
    exact hg

private theorem sequence_preserves (hop : «命题».«操作守物品格的规矩»)
    (hlegal : «命题».«操作保持合规») (un : «未定») (todo : «待写»)
    (hp : «命题».«放进单位守规矩» todo) (os : List «操作») (s t : «状态»)
    (hh : s.«历史».«合规» = true) (hg : s.«货合规矩»)
    (ho : «命题».«依次作用» un todo s os = some t) :
    t.«历史».«合规» = true ∧ t.«货合规矩» := by
  induction os generalizing s with
  | nil =>
    simp only [«命题».«依次作用», Option.some.injEq] at ho
    subst t
    exact ⟨hh,hg⟩
  | cons o os ih =>
    simp only [«命题».«依次作用»] at ho
    cases he : «作用» un todo s o with
    | none => simp [he] at ho
    | some v =>
      simp only [he, Option.bind_some] at ho
      exact ih v (hlegal un todo s v o hh he) (hop un todo s v o hp hh hg he) ho

/-- 据：物品格、运输单位、协议储存箱、存货/取货物品格、缓存格

从空状态执行任意一串成功的操作后，货仍合规矩。 -/
theorem «可达状态货合规矩» (hop : «命题».«操作守物品格的规矩»)
    (hlegal : «命题».«操作保持合规») : «命题».«可达状态货合规矩» := by
  intro un todo os s hp ho
  exact (sequence_preserves hop hlegal un todo hp os «状态».«空» s rfl
    ⟨by rfl, by intro x; exact Nat.zero_le _⟩ ho).2

end Endfield.«证明»
