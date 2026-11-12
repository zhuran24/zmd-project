import Endfield.«证明».«基础»

/-!
格子层的历史合规、单位与通道同步，以及位置上做得了的操作确实有结果。
历史合规沿里层作用的事件表和格子操作表归纳；同步性质沿场地的建造、拆除与重建保持。
-/

namespace Endfield.«证明»

private theorem foldlM_preserves {α β : Type} (P : β → Prop)
    (step : β → α → Option β)
    (hs : ∀ s a t, P s → step s a = some t → P t)
    (xs : List α) (s t : β) (h : P s) (he : xs.foldlM step s = some t) : P t := by
  induction xs generalizing s with
  | nil => simpa using (Option.some.inj he ▸ h)
  | cons x xs ih =>
    simp only [List.foldlM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff] at he
    obtain ⟨u, hu, ht⟩ := he
    exact ih u (hs s x u h hu) ht

private theorem execute_regular («h合规» : «命题».«操作保持合规»)
    (un : «未定») (todo : «待写») (es : «历史») (s t : «状态»)
    (hs : s.«历史».«合规» = true)
    (he : «格子».«执行事件» un todo s es = some t) : t.«历史».«合规» = true := by
  exact foldlM_preserves (fun s : «状态» => s.«历史».«合规» = true) _
    (fun s e t h h' => «h合规» un todo s t (.«改布局» e) h h') es s t hs he

private theorem grid_step_regular («h合规» : «命题».«操作保持合规»)
    (un : «未定») (o : «格子».«接通先后») (bad : «通道» → Nat)
    (s t : «格子».«状态») (a : «格子».«操作»)
    (hs : s.«模型».«历史».«合规» = true)
    (he : «格子».«作用» un o bad s a = some t) : t.«模型».«历史».«合规» = true := by
  cases a <;> simp only [«格子».«作用», Option.bind_eq_bind,
    Option.bind_eq_some_iff, Option.pure_def, Option.some.injEq] at he
  case «原样» b =>
    obtain ⟨u, hu, ht⟩ := he
    cases ht
    exact «h合规» un _ _ _ _ hs hu
  all_goals
    obtain ⟨r, hr, u, hu, ht⟩ := he
    cases ht
    first
      | exact execute_regular «h合规» un _ _ _ _ hs hu
      | exact «h合规» un _ _ _ _ hs hu

private theorem grid_steps_regular («h合规» : «命题».«操作保持合规»)
    (un : «未定») (o : «格子».«接通先后») (bad : «通道» → Nat)
    (as : List «格子».«操作») (s t : «格子».«状态»)
    (hs : s.«模型».«历史».«合规» = true)
    (he : «命题».«格子依次作用» un o bad s as = some t) :
    t.«模型».«历史».«合规» = true := by
  induction as generalizing s with
  | nil => cases he; exact hs
  | cons a as ih =>
    simp only [«命题».«格子依次作用», Option.bind_eq_some_iff] at he
    obtain ⟨u, hu, ht⟩ := he
    exact ih u (grid_step_regular «h合规» un o bad s u a hs hu) ht

/-- 据：通道、接通

格子层从空场地到达的每个状态，里层历史都合规。 -/
theorem «格子层的历史合规» («h合规» : «命题».«操作保持合规») : «命题».«格子层的历史合规» := by
  intro un o bad f hf
  obtain ⟨as, ha⟩ := hf
  exact grid_steps_regular «h合规» un o bad as _ f rfl ha

open «格子» («场地» «摆件»)

/-- 工具：Option 列表映射成功时的成员刻画。 -/
theorem mapM_mem {α β : Type} (f : α → Option β) (xs : List α) (ys : List β)
    (h : xs.mapM f = some ys) (y : β) :
    y ∈ ys ↔ ∃ x ∈ xs, f x = some y := by
  induction xs generalizing ys with
  | nil => simp only [List.mapM_nil, Option.pure_def, Option.some.injEq] at h; subst ys; simp
  | cons x xs ih =>
    simp only [List.mapM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at h
    obtain ⟨z, hz, zs, hzs, rfl⟩ := h
    simp only [List.mem_cons, ih zs hzs, exists_eq_or_imp]
    constructor
    · rintro (rfl | h); exact Or.inl hz; exact Or.inr h
    · rintro (h | h); exact Or.inl (Option.some.inj (hz.symm.trans h)).symm; exact Or.inr h

/-- 工具：Option 列表映射成功时，每个输入都有结果。 -/
theorem mapM_has {α β : Type} (f : α → Option β) (xs : List α) (ys : List β)
    (h : xs.mapM f = some ys) (x : α) (hx : x ∈ xs) : ∃ y, f x = some y := by
  induction xs generalizing ys with
  | nil => simp at hx
  | cons a xs ih =>
    simp only [List.mapM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at h
    obtain ⟨z, hz, zs, hzs, rfl⟩ := h
    rcases List.mem_cons.mp hx with rfl | hx
    · exact ⟨z, hz⟩
    · exact ih zs hzs hx

private theorem mapM_exists {α β : Type} (f : α → Option β) (xs : List α)
    (h : ∀ x ∈ xs, ∃ y, f x = some y) : ∃ ys, xs.mapM f = some ys := by
  induction xs with
  | nil => exact ⟨[], rfl⟩
  | cons x xs ih =>
    obtain ⟨y, hy⟩ := h x (by simp)
    obtain ⟨ys, hys⟩ := ih (fun x hx => h x (by simp [hx]))
    exact ⟨y :: ys, by simp [List.mapM_cons, hy, hys]⟩

private theorem piece_own_id (p : «摆件») : p.«号» ∈ p.«占号» := by
  simp only [«摆件».«占号»]
  split
  · exact List.mem_map.mpr ⟨0, by decide, by simp⟩
  · simp

private theorem piece_ids_nodup (p : «摆件») : p.«占号».Nodup := by
  simp only [«摆件».«占号»]
  split
  · simp [List.range_succ, List.nodup_cons]
  · simp

private def Separate (p q : «摆件») : Prop :=
  (∀ u ∈ p.«占号», u ∉ q.«占号») ∧
  (∀ cs ds, p.«占格» = some cs → q.«占格» = some ds →
    ∀ c ∈ cs, c ∉ ds) ∧
  (p.«是核心» = true → q.«是核心» = false)

/-- 工具：场地占格可计算，摆件之间占号和占格互不相交。 -/
def FieldGood (F : «场地») : Prop :=
  (∀ p ∈ F, ∃ cs, p.«占格» = some cs) ∧ F.Pairwise Separate

private theorem separate_symm {p q : «摆件»} (h : Separate p q) : Separate q p := by
  refine ⟨?_, ?_, ?_⟩
  · intro u hu hp; exact h.1 u hp hu
  · intro ds cs hq hp c hc hd; exact h.2.1 cs ds hp hq c hd hc
  · intro hq
    cases hp : p.«是核心»
    · rfl
    · have := h.2.2 hp; simp [hq] at this

private theorem pairwise_of_mem {α : Type} {R : α → α → Prop}
    (hsym : ∀ a b, R a b → R b a) {xs : List α} (h : xs.Pairwise R)
    (a b : α) (ha : a ∈ xs) (hb : b ∈ xs) (hne : a ≠ b) : R a b := by
  induction xs with
  | nil => simp at ha
  | cons x xs ih =>
    obtain ⟨hx, ht⟩ := List.pairwise_cons.mp h
    rcases List.mem_cons.mp ha with haeq | hat
    · subst a
      exact hx b (List.mem_cons.mp hb |>.resolve_left (Ne.symm hne))
    · rcases List.mem_cons.mp hb with hbeq | hbt
      · subst b
        exact hsym _ _ (hx a hat)
      · exact ih ht hat hbt

private theorem fits_new (F : «场地») (p : «摆件») (h : F.«摆得下» p = true) :
    (∃ cs, p.«占格» = some cs) ∧ (∀ q ∈ F, Separate q p) := by
  unfold «场地».«摆得下» at h
  split at h
  next cs old hp hF =>
    simp only [Bool.and_eq_true, Bool.not_eq_true', List.any_eq_false,
      Bool.or_eq_true] at h
    refine ⟨⟨cs, hp⟩, ?_⟩
    intro q hq
    refine ⟨?_, ?_, ?_⟩
    · intro u hu hup
      have hh := h.1.1.2 q hq
      exact hh (List.any_eq_true.mpr ⟨u, hu, by simpa using hup⟩)
    · intro ds es hqds hpes c hcd hce
      have hce' : c ∈ cs := by simpa [Option.some.inj (hp.symm.trans hpes)] using hce
      have hds : ds ∈ old := (mapM_mem _ _ _ hF ds).mpr ⟨q, hq, hqds⟩
      have hh := h.1.1.1.2 c (List.mem_flatten.mpr ⟨ds, hds, hcd⟩)
      exact (by simpa using hh : c ∉ cs) hce'
    · intro hqcore
      rcases h.1.2 with hpnot | hFnot
      · exact hpnot
      · have hh := hFnot q hq
        simp [hqcore] at hh
  next => cases h

private theorem fieldGood_add (F : «场地») (p : «摆件»)
    (hF : FieldGood F) (hp : F.«摆得下» p = true) : FieldGood (F ++ [p]) := by
  obtain ⟨hp, hsep⟩ := fits_new F p hp
  constructor
  · intro q hq
    rcases List.mem_append.mp hq with hq | hq
    · exact hF.1 q hq
    · simpa using (List.mem_singleton.mp hq ▸ hp)
  · exact List.pairwise_append.mpr ⟨hF.2, by simp, by simpa using hsep⟩

private theorem fieldGood_sublist {F G : «场地»} (h : List.Sublist G F) (hF : FieldGood F) : FieldGood G :=
  ⟨fun p hp => hF.1 p (h.subset hp), hF.2.sublist h⟩

private theorem fieldGood_build (F G : «场地») (o : «格子».«接通先后»)
    (p : «摆件») (es : «历史») (hF : FieldGood F)
    (h : F.«建成» o p = some (G, es)) : FieldGood G := by
  unfold «场地».«建成» at h
  split at h
  · cases h
  next hp =>
    have hp : F.«摆得下» p = true := by simpa using hp
    simp only [Option.bind_eq_bind, Option.bind_eq_some_iff, Option.pure_def,
      Option.some.injEq, Prod.mk.injEq] at h
    obtain ⟨fs, _, rfl, _⟩ := h
    exact fieldGood_add F p hF hp

private theorem fieldGood_remove (F G : «场地») (u : Nat) (es : «历史»)
    (hF : FieldGood F) (h : F.«收» u = some (G, es)) : FieldGood G := by
  unfold «场地».«收» at h
  split at h
  · cases h
    exact fieldGood_sublist List.filter_sublist hF
  · cases h

private theorem fieldGood_place (F G : «场地») (o : «格子».«接通先后»)
    (p : «摆件») (es : «历史») (hF : FieldGood F)
    (h : F.«建» o p = some (G, es)) : FieldGood G := by
  cases hk : p.«种类» <;> simp only [«场地».«建», hk] at h
  case «物品准入口» d =>
    split at h
    · simp only [Option.bind_eq_bind, Option.bind_eq_some_iff,
        Option.pure_def, Option.some.injEq, Prod.mk.injEq] at h
      obtain ⟨⟨F', es'⟩, hrem, ⟨G', fs⟩, hb, hG, _⟩ := h
      dsimp only at hG
      subst G'
      exact fieldGood_build F' G o p fs (fieldGood_remove F F' _ es' hF hrem) hb
    · cases h
  all_goals exact fieldGood_build F G o p es hF h

private theorem fieldGood_blueprint (F G : «场地») (o : «格子».«接通先后»)
    (ps : List «摆件») (es : «历史») (hF : FieldGood F)
    (h : F.«放蓝图» o ps = some (G, es)) : FieldGood G := by
  unfold «场地».«放蓝图» at h
  split at h
  · cases h
  · apply foldlM_preserves (fun r : «场地» × «历史» => FieldGood r.1) _ ?_ ps
      (F, []) (G, es) hF h
    intro r p t hr ht
    simp only [Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at ht
    obtain ⟨⟨G', fs⟩, hg, rfl⟩ := ht
    exact fieldGood_place r.1 G' o p fs hr hg

private theorem build_field_eq (F G : «场地») (o : «格子».«接通先后»)
    (p : «摆件») (es : «历史»)
    (h : F.«建成» o p = some (G, es)) : G = F ++ [p] := by
  unfold «场地».«建成» at h
  split at h
  · cases h
  · simp only [Option.bind_eq_bind, Option.bind_eq_some_iff, Option.pure_def,
      Option.some.injEq, Prod.mk.injEq] at h
    obtain ⟨fs, _, he, _⟩ := h
    exact he.symm

private theorem rebuild_fold_field (ps : List «摆件») (F G : «场地»)
    (es fs : «历史») (o : «格子».«接通先后») (hF : FieldGood F)
    (h : ps.foldlM (fun (s, hs) p => do
      let (s', hs') ← s.«建成» o p
      return (s', hs ++ hs')) (F, es) = some (G, fs)) :
    FieldGood G ∧ G = F ++ ps := by
  induction ps generalizing F es with
  | nil =>
    simp only [List.foldlM_nil, Option.pure_def, Option.some.injEq, Prod.mk.injEq] at h
    rcases h with ⟨rfl, rfl⟩
    exact ⟨hF, by simp⟩
  | cons p ps ih =>
    simp only [List.foldlM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at h
    obtain ⟨⟨F', es'⟩, ⟨⟨G', hs⟩, hb, he⟩, ht⟩ := h
    cases he
    obtain ⟨hg, hge⟩ := ih G' (es ++ hs) (fieldGood_build F G' o p hs hF hb) ht
    exact ⟨hg, by simpa [build_field_eq F G' o p hs hb, List.append_assoc] using hge⟩

private theorem fieldGood_rebuild (F : «场地») (o : «格子».«接通先后»)
    (ps : List «摆件») (es : «历史») (h : F.«重建» o ps = some es) : FieldGood ps := by
  unfold «场地».«重建» at h
  split at h
  · cases h
  · simp only [Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at h
    obtain ⟨⟨G, fs⟩, hg, rfl⟩ := h
    obtain ⟨hG, he⟩ := rebuild_fold_field ps [] G [] fs o ⟨by simp, by simp⟩ hg
    simpa only [he, List.nil_append] using hG

private theorem grid_step_fieldGood (un : «未定») (o : «格子».«接通先后»)
    (bad : «通道» → Nat) (s t : «格子».«状态») (a : «格子».«操作»)
    (hs : FieldGood s.«场地») (he : «格子».«作用» un o bad s a = some t) :
    FieldGood t.«场地» := by
  cases a <;> simp only [«格子».«作用», Option.bind_eq_bind,
    Option.bind_eq_some_iff, Option.pure_def, Option.some.injEq] at he
  case «原样» b =>
    obtain ⟨u, _, rfl⟩ := he
    exact hs
  all_goals
    obtain ⟨r, hr, u, _, rfl⟩ := he
    first
      | exact fieldGood_place _ _ o _ _ hs hr
      | exact fieldGood_remove _ _ _ _ hs hr
      | exact fieldGood_blueprint _ _ o _ _ hs hr
      | exact fieldGood_rebuild _ o _ _ hr

/-- 工具：格子层可达状态的场地满足几何不相交条件。 -/
theorem reachable_fieldGood (un : «未定») (o : «格子».«接通先后»)
    (bad : «通道» → Nat) (f : «格子».«状态») (h : «命题».«格子可达» un o bad f) :
    FieldGood f.«场地» := by
  obtain ⟨as, ha⟩ := h
  suffices ∀ as s t, FieldGood s.«场地» →
      «命题».«格子依次作用» un o bad s as = some t → FieldGood t.«场地» from
    this as _ f ⟨by simp [«格子».«状态».«空»], by simp [«格子».«状态».«空»]⟩ ha
  intro as
  induction as with
  | nil => intro s t hs he; cases he; exact hs
  | cons a as ih =>
    intro s t hs he
    simp only [«命题».«格子依次作用», Option.bind_eq_some_iff] at he
    obtain ⟨u, hu, ht⟩ := he
    exact ih u t (grid_step_fieldGood un o bad s u a hs hu) ht

open «格子» («端口» «接通先后» «朝向» «格» «同边先后» «排端口» «核心边格» «制造大小» «平行边»)

private theorem «mapM成员» {α β : Type} (f : α → Option β) (xs : List α)
    {ys : List β} (h : xs.mapM f = some ys) {y : β} (hy : y ∈ ys) :
    ∃ x ∈ xs, f x = some y := by
  induction xs generalizing ys with
  | nil => simp at h; subst ys; simp at hy
  | cons x xs ih =>
    simp only [List.mapM_cons, bind, Option.bind_eq_some_iff, pure] at h
    obtain ⟨z, hz, zs, hzs, he⟩ := h
    cases he
    rcases List.mem_cons.mp hy with rfl | hy
    · exact ⟨x, by simp, hz⟩
    · obtain ⟨a, ha, hf⟩ := ih hzs hy
      exact ⟨a, List.mem_cons_of_mem _ ha, hf⟩

private theorem «mapM映射» {α β γ : Type} (f : α → Option β) (g : β → γ)
    (k : α → γ) (xs : List α) {ys : List β} (h : xs.mapM f = some ys)
    (hk : ∀ x ∈ xs, ∀ y, f x = some y → g y = k x) : ys.map g = xs.map k := by
  induction xs generalizing ys with
  | nil => simp at h; subst ys; rfl
  | cons x xs ih =>
    simp only [List.mapM_cons, bind, Option.bind_eq_some_iff, pure] at h
    obtain ⟨z, hz, zs, hzs, he⟩ := h
    cases he
    simp only [List.map_cons]
    rw [hk x (by simp) z hz, ih hzs (by intro a ha; exact hk a (by simp [ha]))]

private def «端口样式» (p : «摆件») (o : «接通先后») : List (Bool × «朝向» × Nat) :=
  let ring := fun (d : «朝向») => [d.«顺时针», d.«对边», d.«对边».«顺时针»]
  let sides := fun (d : «朝向») =>
    let n := if d == .«上» || d == .«下» then p.«大小».1 else p.«大小».2
    let ns := «同边先后» d n
    ns.map (fun n => (false, d.«对边», n)) ++ ns.map (fun n => (true, d, n))
  match p.«种类» with
  | .«传送带» a b => [(false, a, 0), (true, b, 0)]
  | .«分流器» d => (false, d, 0) :: (ring d).map (fun d => (true, d, 0))
  | .«汇流器» d => (ring d).map (fun d => (false, d, 0)) ++ [(true, d, 0)]
  | .«物品准入口» d => [(false, d.«对边», 0), (true, d, 0)]
  | .«桥接器» d0 =>
    let ds := «朝向».«各边».map fun d => (d, 0)
    («排端口» (fun d _ => «格子».«桥接器存货先后» d0 d) ds).map (fun (d,n) => (false,d,n)) ++
      («排端口» (fun d _ => «格子».«桥接器取货先后» d0 d) ds).map (fun (d,n) => (true,d,n))
  | .«协议储存箱» d | .«制造» _ d => sides d
  | .«协议核心» a =>
    («排端口» o.«协议核心» («核心边格» a false)).map (fun (d,n) => (false,d,n)) ++
      («排端口» o.«协议核心» («核心边格» a true)).map (fun (d,n) => (true,d,n))
  | .«仓库取货口» d => [(true, d, 1)]
  | .«供电桩» => []

private theorem «端口展开» (p : «摆件») (o : «接通先后») :
    p.«端口» o = (do
      let _ ← p.«占格»
      if (match p.«种类» with | .«传送带» a b => a == b | _ => false) then none
      else ( «端口样式» p o).mapM fun (b,d,n) => p.«造端口» b d n) := by
  cases h : p.«种类» <;>
    simp [«摆件».«端口», «端口样式», h, List.mapM_append, List.mapM_map,
      List.mapM_cons, List.mapM_nil, Option.bind_assoc, Function.comp_def]

private theorem «端口来自造端口» (p : «摆件») (o : «接通先后») (ps : List «端口»)
    (h : p.«端口» o = some ps) (a : «端口») (ha : a ∈ ps) :
    ∃ b d n, p.«造端口» b d n = some a := by
  rw [«端口展开»] at h
  simp only [bind, Option.bind_eq_some_iff] at h
  obtain ⟨cs, _, h⟩ := h
  by_cases hi : (match p.«种类» with | .«传送带» a b => a == b | _ => false) = true
  · simp only [ite_eq_left hi] at h; contradiction
  · simp only [ite_eq_right hi] at h
    obtain ⟨⟨b,d,n⟩, _, hh⟩ := «mapM成员» _ _ h ha
    exact ⟨b,d,n,hh⟩

private theorem «mapM成员反向» {α β : Type} (f : α → Option β) (xs : List α)
    {ys : List β} (h : xs.mapM f = some ys) {x : α} (hx : x ∈ xs)
    {y : β} (hy : f x = some y) : y ∈ ys := by
  induction xs generalizing ys with
  | nil => simp at hx
  | cons a xs ih =>
    simp only [List.mapM_cons, bind, Option.bind_eq_some_iff, pure] at h
    obtain ⟨z, hz, zs, hzs, he⟩ := h
    cases he
    rcases List.mem_cons.mp hx with rfl | hx
    · have : y = z := Option.some.inj (hy.symm.trans hz)
      simp [this]
    · exact List.mem_cons_of_mem _ (ih hzs hx)

private theorem «端口展开成功» (p : «摆件») (o : «接通先后») (ps : List «端口»)
    (h : p.«端口» o = some ps) :
    (∃ cs, p.«占格» = some cs) ∧
    («端口样式» p o).mapM (fun (b,d,n) => p.«造端口» b d n) = some ps := by
  rw [«端口展开»] at h
  simp only [bind, Option.bind_eq_some_iff] at h
  obtain ⟨cs, hc, h⟩ := h
  by_cases hi : (match p.«种类» with | .«传送带» a b => a == b | _ => false) = true
  · simp only [ite_eq_left hi] at h; contradiction
  · exact ⟨⟨cs,hc⟩, by simpa only [ite_eq_right hi] using h⟩

/-- 工具：生成端口的单位、方向、取货标记和边格。 -/
theorem «造端口性质» (p : «摆件») (b : Bool) (d : «朝向») (n : Nat)
    (a : «端口») (h : p.«造端口» b d n = some a) :
    a.«单位» = (if p.«是桥接器» then
      p.«号» + (if b then d.«对边» else d).«编号» else p.«号») ∧
    a.«边» = d ∧ a.«取货» = b ∧ p.«边格» d n = some a.«格» := by
  simp only [«摆件».«造端口», Option.map_eq_some_iff] at h
  obtain ⟨c, hc, he⟩ := h
  subst a
  exact ⟨rfl, rfl, rfl, hc⟩

private theorem «大小为正» (p : «摆件») : 0 < p.«大小».1 ∧ 0 < p.«大小».2 := by
  cases hk : p.«种类» <;> simp [«摆件».«大小», hk]
  case «制造» k d => cases k <;> cases d <;> decide
  case «仓库取货口» d => cases d <;> decide

private theorem «边格在矩形里» (p : «摆件») (d : «朝向») (n : Nat) (c : «格»)
    (h : p.«边格» d n = some c) :
    ∃ i j, i < p.«大小».1 ∧ j < p.«大小».2 ∧
      «格».«坐标» (p.«位置».i.val + i) (p.«位置».j.val + j) = some c := by
  have hw := («大小为正» p).1
  have hh := («大小为正» p).2
  cases d <;> simp only [«摆件».«边格»] at h
  · split at h
    · exact ⟨n, 0, by assumption, hh, by simpa using h⟩
    · contradiction
  · split at h
    · refine ⟨p.«大小».1 - 1, n, by omega, by assumption, ?_⟩
      have he : p.«位置».i.val + (p.«大小».1 - 1) = p.«位置».i.val + p.«大小».1 - 1 := by omega
      simpa only [he] using h
    · contradiction
  · split at h
    · refine ⟨n, p.«大小».2 - 1, by assumption, by omega, ?_⟩
      have he : p.«位置».j.val + (p.«大小».2 - 1) = p.«位置».j.val + p.«大小».2 - 1 := by omega
      simpa only [he] using h
    · contradiction
  · split at h
    · exact ⟨0, n, hw, by assumption, by simpa using h⟩
    · contradiction

private theorem «端口格在占格里» (p : «摆件») (o : «接通先后»)
    (ps : List «端口») (cs : List «格») (hp : p.«端口» o = some ps)
    (hc : p.«占格» = some cs) (a : «端口») (ha : a ∈ ps) : a.«格» ∈ cs := by
  obtain ⟨b,d,n,hs⟩ := «端口来自造端口» p o ps hp a ha
  obtain ⟨i,j,hi,hj,hij⟩ := «边格在矩形里» p d n a.«格» («造端口性质» p b d n a hs).2.2.2
  apply «mapM成员反向» _ _ hc (x := (i,j)) _ hij
  simp only [List.mem_flatMap, List.mem_range, List.mem_map]
  exact ⟨i, hi, j, hj, rfl⟩

private theorem «端口同边同类同单位» (p : «摆件») (o : «接通先后»)
    (ps : List «端口») (hp : p.«端口» o = some ps)
    (a b : «端口») (ha : a ∈ ps) (hb : b ∈ ps)
    (hd : a.«边» = b.«边») (ht : a.«取货» = b.«取货») : a.«单位» = b.«单位» := by
  obtain ⟨ba,da,na,hsa⟩ := «端口来自造端口» p o ps hp a ha
  obtain ⟨bb,db,nb,hsb⟩ := «端口来自造端口» p o ps hp b hb
  have hpa := «造端口性质» p ba da na a hsa
  have hpb := «造端口性质» p bb db nb b hsb
  grind

/-- 工具：完整端口表中端口的单位属于其摆件。 -/
theorem «端口单位属于摆件» (p : «摆件») (o : «接通先后»)
    (ps : List «端口») (hp : p.«端口» o = some ps)
    (a : «端口») (ha : a ∈ ps) : a.«单位» ∈ p.«单位».map Prod.fst := by
  obtain ⟨b,d,n,hs⟩ := «端口来自造端口» p o ps hp a ha
  have hu := («造端口性质» p b d n a hs).1
  cases hk : p.«种类» <;>
    simp [«摆件».«单位», «摆件».«是桥接器», hk, hu, «朝向».«各边»]
  case «桥接器» => cases b <;> cases d <;> simp [«朝向».«编号», «朝向».«对边», «朝向».«顺时针»]
  case «供电桩» =>
    have hh := («端口展开成功» p o ps hp).2
    simp [«端口样式», hk] at hh
    subst ps
    simp at ha

private def «样式标签» (p : «摆件») (v : Bool × «朝向» × Nat) : Nat × Bool :=
  (if p.«是桥接器» then
    p.«号» + (if v.1 then v.2.1.«对边» else v.2.1).«编号» else p.«号», v.1)

private theorem «端口标签表» (p : «摆件») (o : «接通先后»)
    (ps : List «端口») (hp : p.«端口» o = some ps) :
    ps.map (fun a => (a.«单位», a.«取货»)) = («端口样式» p o).map («样式标签» p) := by
  apply «mapM映射» _ _ _ _ («端口展开成功» p o ps hp).2
  intro v _ a h
  have hh := «造端口性质» p v.1 v.2.1 v.2.2 a h
  exact Prod.ext hh.1 hh.2.2.1

private theorem «排端口映射筛长度» {α : Type} (f : «朝向» → Nat → Nat)
    (xs : List («朝向» × Nat)) (g : («朝向» × Nat) → α) (r : α → Bool) :
    (((«排端口» f xs).map g).filter r).length = ((xs.map g).filter r).length :=
  (List.Perm.filter r ((List.mergeSort_perm xs _).map g)).length_eq

private theorem «筛常数» {α : Type} (xs : List α) (b : Bool) :
    xs.filter (fun _ => b) = if b then xs else [] := by
  induction xs <;> cases b <;> simp_all

private theorem «标签相等» (u v : Nat) (a b : Bool) :
    ((u,a) == (v,b)) = ((u == v) && (a == b)) := by
  apply Bool.eq_iff_iff.mpr
  simp

private theorem «样式标签计数» (p : «摆件») (o : «接通先后»)
    (u : Nat) (k : «单位种类») (hu : (u,k) ∈ p.«单位») (b : Bool) :
    (((«端口样式» p o).map («样式标签» p)).filter (· == (u,b))).length =
      if b then k.«取货端口数» else k.«存货端口数» := by
  cases hk : p.«种类» <;>
    simp only [«摆件».«单位», hk, List.mem_cons, List.not_mem_nil, or_false,
      Prod.mk.injEq, List.mem_map] at hu
  case «传送带» a d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> simp [«端口样式», «样式标签», «摆件».«是桥接器», hk, «单位种类».«存货端口数», «单位种类».«取货端口数»]
  case «分流器» d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> simp [«端口样式», «样式标签», «摆件».«是桥接器», hk, «单位种类».«存货端口数», «单位种类».«取货端口数»]
  case «汇流器» d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> simp [«端口样式», «样式标签», «摆件».«是桥接器», hk, «单位种类».«存货端口数», «单位种类».«取货端口数»]
  case «物品准入口» d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> simp [«端口样式», «样式标签», «摆件».«是桥接器», hk, «单位种类».«存货端口数», «单位种类».«取货端口数»]
  case «桥接器» =>
    obtain ⟨d, _, rfl, rfl⟩ := hu
    simp only [«端口样式», hk, List.map_append, List.map_map, List.filter_append,
      List.length_append, «排端口映射筛长度»]
    cases b <;> cases d <;>
      simp [«样式标签», «摆件».«是桥接器», hk, «朝向».«各边», «朝向».«编号», «朝向».«对边», «朝向».«顺时针»,
        «单位种类».«存货端口数», «单位种类».«取货端口数»]
  case «协议储存箱» d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> cases d <;>
      simp [«端口样式», «样式标签», «摆件».«是桥接器», hk, «摆件».«大小», «同边先后»,
        «单位种类».«存货端口数», «单位种类».«取货端口数», List.filter_map, List.map_map, Function.comp_def, «标签相等», «筛常数»]
  case «制造» mk d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> cases d <;> cases mk <;>
      simp [«端口样式», «样式标签», «摆件».«是桥接器», hk, «摆件».«大小», «制造大小», «同边先后»,
        «单位种类».«存货端口数», «单位种类».«取货端口数», «制造单位».«端口边长», List.filter_map, List.map_map, Function.comp_def, «标签相等», «筛常数»]
  case «协议核心» a =>
    obtain ⟨rfl,rfl⟩ := hu
    simp only [«端口样式», hk, List.map_append, List.map_map, List.filter_append,
      List.length_append, «排端口映射筛长度»]
    cases b <;> cases a <;>
      simp [«样式标签», «摆件».«是桥接器», hk, «核心边格», «朝向».«各边», «平行边».«包含»,
        «单位种类».«存货端口数», «单位种类».«取货端口数», List.filter_map, List.map_map, Function.comp_def, «标签相等», «筛常数»]
  case «仓库取货口» d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> simp [«端口样式», «样式标签», «摆件».«是桥接器», hk, «单位种类».«存货端口数», «单位种类».«取货端口数»]

private theorem «每单位端口数» (p : «摆件») (o : «接通先后»)
    (ps : List «端口») (hp : p.«端口» o = some ps)
    (u : Nat) (k : «单位种类») (hu : (u,k) ∈ p.«单位») (b : Bool) :
    (ps.filter (fun a => a.«单位» == u && a.«取货» == b)).length =
      if b then k.«取货端口数» else k.«存货端口数» := by
  have hh := «样式标签计数» p o u k hu b
  rw [← «端口标签表» p o ps hp] at hh
  simpa [List.filter_map, Function.comp_def, «标签相等»] using hh


@[reducible] private def Snapshot := List («单位号» × «单位种类») × List «通道»

private def snapshot (L : «布局») : Snapshot := (L.«单位表», L.«通道表».map Prod.fst)

private def addSnapshot (s : Snapshot) : «事件» → Snapshot
  | .«建成» u k => (s.1 ++ [(u,k)], s.2)
  | .«接通» c => (s.1, s.2 ++ [c])
  | .«拆除» u => (s.1.filter (fun p => p.1 != u), s.2.filter (fun c => c.«起» != u && c.«止» != u))

private def replay (s : Snapshot) (es : «历史») : Snapshot := es.foldl addSnapshot s

private theorem replay_append (s : Snapshot) (es fs : «历史») :
    replay s (es ++ fs) = replay (replay s es) fs := by
  exact List.foldl_append

private theorem snapshot_add (L : «布局») (t : Nat) (e : «事件») :
    snapshot (L.«加» t e) = addSnapshot (snapshot L) e := by
  cases e <;> simp [snapshot, addSnapshot, «布局».«加», List.filter_map] <;> rfl

private theorem history_append_snapshot (H : «历史») (e : «事件») :
    snapshot ((H ++ [e]).«布局于» (H ++ [e]).length) =
    addSnapshot (snapshot (H.«布局于» H.length)) e := by
  rw [List.length_append, List.length_singleton,
    «历史».«布局于后继» (H ++ [e]) H.length e (by simp), snapshot_add]
  congr 2
  simp [«历史».«布局于»]

private theorem execute_snapshot (un : «未定») (todo : «待写») (s t : «状态») (es : «历史»)
    (h : «格子».«执行事件» un todo s es = some t) :
    snapshot t.«布局» = replay (snapshot s.«布局») es := by
  induction es generalizing s with
  | nil => cases h; rfl
  | cons e es ih =>
    simp only [«格子».«执行事件», List.foldlM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff] at h
    obtain ⟨u, hu, ht⟩ := h
    have hd : («操作».«改布局» e).«做得了» s = true := by
      rw [← «做得了才有结果» un todo s (.«改布局» e), hu]; rfl
    have hh : u.«历史» = s.«历史» ++ [e] := by
      cases e <;> simp only [«作用», hd, Bool.not_true, Bool.false_eq_true, ↓reduceIte] at hu <;>
        cases hu <;> rfl
    rw [ih u ht]
    simp only [replay, List.foldl_cons]
    congr 1
    simpa only [«状态».«布局», hh] using history_append_snapshot s.«历史» e

private theorem forms_swap (p q : «摆件») (a b : «端口») :
    «格子».«形成通道» p q a b = «格子».«形成通道» q p b a := by
  have hn : ¬ (a.«正对紧贴» b = true ∧ b.«正对紧贴» a = true) := by
    simp only [«端口».«正对紧贴», Bool.and_eq_true, Bool.not_eq_true']
    grind
  unfold «格子».«形成通道»
  have hid : (p.«号» == q.«号») = (q.«号» == p.«号») := by simp [BEq.beq, eq_comm]
  rw [hid, Bool.or_comm p.«是运输单位» q.«是运输单位»]
  split
  · rfl
  · split <;> split <;> simp_all

private def Between (o : «接通先后») (p q : «摆件») (c : «通道») : Prop :=
  ∃ ps qs, p.«端口» o = some ps ∧ q.«端口» o = some qs ∧
    ∃ a ∈ ps, ∃ b ∈ qs, «格子».«形成通道» p q a b = some c

private def Geometry (F : «场地») (o : «接通先后») (c : «通道») : Prop :=
  ∃ p ∈ F, ∃ q ∈ F, Between o p q c

private def PortsExist (F : «场地») (o : «接通先后») : Prop :=
  ∀ p ∈ F, ∃ ps, p.«端口» o = some ps

private def Synchronized (F : «场地») (o : «接通先后») (s : Snapshot) : Prop :=
  s.1 = F.flatMap «摆件».«单位» ∧ PortsExist F o ∧ ∀ c, c ∈ s.2 ↔ Geometry F o c

private theorem between_symm {o : «接通先后»} {p q : «摆件»} {c : «通道»}
    (h : Between o p q c) : Between o q p c := by
  obtain ⟨ps, qs, hp, hq, a, ha, b, hb, hc⟩ := h
  exact ⟨qs, ps, hq, hp, b, hb, a, ha, by rwa [forms_swap]⟩

private theorem between_irrefl (o : «接通先后») (p : «摆件») (c : «通道») :
    ¬ Between o p p c := by
  rintro ⟨ps, qs, _, _, a, _, b, _, h⟩
  simp [«格子».«形成通道»] at h

private theorem geometry_add (F : «场地») (o : «接通先后») (p : «摆件») (c : «通道») :
    Geometry (F ++ [p]) o c ↔ Geometry F o c ∨ ∃ q ∈ F, Between o p q c := by
  simp only [Geometry, List.mem_append, List.mem_singleton]
  constructor
  · rintro ⟨x, hx, y, hy, h⟩
    rcases hx with hx | rfl <;> rcases hy with hy | rfl
    · exact Or.inl ⟨x, hx, y, hy, h⟩
    · exact Or.inr ⟨x, hx, between_symm h⟩
    · exact Or.inr ⟨y, hy, h⟩
    · exact (between_irrefl o _ c h).elim
  · rintro (⟨x, hx, y, hy, h⟩ | ⟨q, hq, h⟩)
    · exact ⟨x, Or.inl hx, y, Or.inl hy, h⟩
    · exact ⟨p, Or.inr rfl, q, Or.inl hq, h⟩

/-- 工具：场地端口行表的成员刻画。 -/
theorem rows_mem (F : «场地») (o : «接通先后»)
    (rows : List («摆件» × List «端口»))
    (h : F.mapM (fun p => do return (p, ← p.«端口» o)) = some rows)
    (p : «摆件») (ps : List «端口») :
    (p, ps) ∈ rows ↔ p ∈ F ∧ p.«端口» o = some ps := by
  rw [mapM_mem _ _ _ h]
  simp only [Option.bind_eq_bind, Option.bind_eq_some_iff, Option.pure_def,
    Option.some.injEq, Prod.mk.injEq]
  constructor
  · rintro ⟨q, hq, qs, hqs, rfl, rfl⟩; exact ⟨hq, hqs⟩
  · rintro ⟨hp, hps⟩; exact ⟨p, hp, ps, hps, rfl, rfl⟩

private theorem select_connections (cs : List «通道») (es : «历史»)
    (h : (match cs with
      | [] => some ([] : «历史»)
      | [c] => some [«事件».«接通» c]
      | _ => none) = some es) : es = cs.map «事件».«接通» := by
  cases cs with
  | nil => cases h; rfl
  | cons c cs => cases cs with
    | nil => cases h; rfl
    | cons d cs => cases h

private theorem connections_spec (F : «场地») (o : «接通先后») (p : «摆件») (es : «历史»)
    (h : F.«接通事件» o p = some es) :
    PortsExist (F ++ [p]) o ∧
    ∀ e, e ∈ es ↔ ∃ c, e = .«接通» c ∧ ∃ q ∈ F, Between o p q c := by
  unfold «场地».«接通事件» at h
  simp only [Option.bind_eq_bind, Option.bind_eq_some_iff, Option.pure_def,
    Option.some.injEq] at h
  obtain ⟨ps, hps, rows, hrows, ess, hess, rfl⟩ := h
  constructor
  · intro q hq
    rcases List.mem_append.mp hq with hq | hq
    · obtain ⟨⟨q',qs⟩, hq'⟩ := mapM_has _ _ _ hrows q hq
      simp only [Option.bind_eq_some_iff, Option.some.injEq, Prod.mk.injEq] at hq'
      obtain ⟨bs, hbs, _, _⟩ := hq'
      exact ⟨bs, hbs⟩
    · have := List.mem_singleton.mp hq
      subst q
      exact ⟨ps, hps⟩
  · intro e
    constructor
    · intro he
      obtain ⟨hs, hhs, he⟩ := List.mem_flatten.mp he
      obtain ⟨a, ha, hh⟩ := (mapM_mem _ _ _ hess hs).mp hhs
      have heq := select_connections _ hs hh
      rw [heq] at he
      obtain ⟨c, hc, rfl⟩ := List.mem_map.mp he
      obtain ⟨⟨q,bs⟩, hq, hbs⟩ := List.mem_flatMap.mp hc
      obtain ⟨b, hb, hform⟩ := List.mem_filterMap.mp hbs
      obtain ⟨hqF, hqbs⟩ := (rows_mem F o rows hrows q bs).mp hq
      exact ⟨c, rfl, q, hqF, ps, bs, hps, hqbs, a, ha, b, hb, hform⟩
    · rintro ⟨c, rfl, q, hq, ps', bs, hp', hqbs, a, ha, b, hb, hform⟩
      have hep : ps' = ps := Option.some.inj (hp'.symm.trans hps)
      subst ps'
      obtain ⟨hs, hhs⟩ := mapM_has _ _ _ hess a ha
      apply List.mem_flatten.mpr
      refine ⟨hs, (mapM_mem _ _ _ hess hs).mpr ⟨a, ha, hhs⟩, ?_⟩
      rw [select_connections _ hs hhs]
      apply List.mem_map.mpr
      refine ⟨c, ?_, rfl⟩
      exact List.mem_flatMap.mpr ⟨(q,bs), (rows_mem F o rows hrows q bs).mpr ⟨hq,hqbs⟩,
        List.mem_filterMap.mpr ⟨b,hb,hform⟩⟩

private theorem replay_builds (s : Snapshot) (us : List («单位号» × «单位种类»)) :
    replay s (us.map fun (u,k) => «事件».«建成» u k) = (s.1 ++ us, s.2) := by
  induction us generalizing s with
  | nil => simp [replay]
  | cons u us ih =>
    simp only [List.map_cons, replay, List.foldl_cons]
    rw [← replay, ih]
    simp [addSnapshot, List.append_assoc]

private theorem replay_connections (s : Snapshot) (es : «历史»)
    (he : ∀ e ∈ es, ∃ c, e = «事件».«接通» c) :
    (replay s es).1 = s.1 ∧ ∀ c, c ∈ (replay s es).2 ↔ c ∈ s.2 ∨ «事件».«接通» c ∈ es := by
  induction es generalizing s with
  | nil => simp [replay]
  | cons e es ih =>
    obtain ⟨c, rfl⟩ := he e (by simp)
    have hh := ih (addSnapshot s (.«接通» c)) (fun e he' => he e (by simp [he']))
    simp only [replay, List.foldl_cons]
    refine ⟨hh.1, ?_⟩
    intro d
    change d ∈ (replay (addSnapshot s (.«接通» c)) es).2 ↔ _
    rw [hh.2]
    simp [addSnapshot, or_assoc, eq_comm]

private theorem sync_build (F G : «场地») (o : «接通先后») (p : «摆件»)
    (es : «历史») (s : Snapshot) (hs : Synchronized F o s)
    (h : F.«建成» o p = some (G,es)) : Synchronized G o (replay s es) := by
  unfold «场地».«建成» at h
  split at h
  · cases h
  · simp only [Option.bind_eq_bind, Option.bind_eq_some_iff, Option.pure_def,
      Option.some.injEq, Prod.mk.injEq] at h
    obtain ⟨cs, hcs, rfl, rfl⟩ := h
    obtain ⟨hports, hspec⟩ := connections_spec F o p cs hcs
    have hconn : ∀ e ∈ cs, ∃ c, e = .«接通» c := by
      intro e he
      obtain ⟨c, hc, _⟩ := (hspec e).mp he
      exact ⟨c, hc⟩
    rw [replay_append]
    rw [replay_builds]
    obtain ⟨hunits, hchan⟩ := replay_connections (s.1 ++ p.«单位», s.2) cs hconn
    refine ⟨?_, hports, ?_⟩
    · rw [hunits, hs.1]
      simp
    · intro c
      rw [hchan, hs.2.2, geometry_add]
      apply or_congr_right
      simpa using hspec («事件».«接通» c)

private theorem unit_id_reserved (p : «摆件») (u : Nat) (hu : u ∈ p.«单位».map Prod.fst) :
    u ∈ p.«占号» := by
  cases hk : p.«种类» <;> simp [«摆件».«单位», «摆件».«占号», «摆件».«是桥接器», hk, «朝向».«各边»,
    «朝向».«编号», List.range_succ] at hu ⊢ <;> exact hu

private theorem field_separate (F : «场地») (hF : FieldGood F) (p q : «摆件»)
    (hp : p ∈ F) (hq : q ∈ F) (hne : p ≠ q) : Separate p q :=
  pairwise_of_mem (fun _ _ => separate_symm) hF.2 p q hp hq hne

private theorem field_ids_injective (F : «场地») (hF : FieldGood F) (p q : «摆件»)
    (hp : p ∈ F) (hq : q ∈ F) (he : p.«号» = q.«号») : p = q := by
  by_cases h : p = q
  · exact h
  · exact ((field_separate F hF p q hp hq h).1 p.«号» (piece_own_id p)
      (he ▸ piece_own_id q)).elim

private theorem field_units_disjoint (F : «场地») (hF : FieldGood F) (p q : «摆件»)
    (hp : p ∈ F) (hq : q ∈ F) (hne : p ≠ q) (u : Nat)
    (hu : u ∈ p.«单位».map Prod.fst) : u ∉ q.«单位».map Prod.fst := by
  intro hq'
  exact (field_separate F hF p q hp hq hne).1 u
    (unit_id_reserved p u hu) (unit_id_reserved q u hq')

private theorem between_endpoints (o : «接通先后») (p q : «摆件») (c : «通道»)
    (h : Between o p q c) :
    (c.«起» ∈ p.«单位».map Prod.fst ∧ c.«止» ∈ q.«单位».map Prod.fst) ∨
    (c.«止» ∈ p.«单位».map Prod.fst ∧ c.«起» ∈ q.«单位».map Prod.fst) := by
  obtain ⟨ps,qs,hps,hqs,a,ha,b,hb,h⟩ := h
  have hpa := «端口单位属于摆件» p o ps hps a ha
  have hqb := «端口单位属于摆件» q o qs hqs b hb
  unfold «格子».«形成通道» at h
  split at h
  · cases h
  · split at h
    · cases h; exact Or.inl ⟨hpa,hqb⟩
    · split at h
      · cases h; exact Or.inr ⟨hpa,hqb⟩
      · cases h

private theorem between_avoids (F : «场地») (hF : FieldGood F) (o : «接通先后»)
    (p x y : «摆件») (hp : p ∈ F) (hx : x ∈ F) (hy : y ∈ F) (c : «通道»)
    (hc : Between o x y c) :
    (c.«起» ∉ p.«单位».map Prod.fst ∧ c.«止» ∉ p.«单位».map Prod.fst) ↔
      x.«号» ≠ p.«号» ∧ y.«号» ≠ p.«号» := by
  have he := between_endpoints o x y c hc
  constructor
  · rintro ⟨hs,ht⟩
    constructor
    · intro h
      have hxp := field_ids_injective F hF x p hx hp h
      subst x
      rcases he with he | he
      · exact hs he.1
      · exact ht he.1
    · intro h
      have hyp := field_ids_injective F hF y p hy hp h
      subst y
      rcases he with he | he
      · exact ht he.2
      · exact hs he.2
  · rintro ⟨hxid,hyid⟩
    have hxp : x ≠ p := fun h => hxid (congrArg «摆件».«号» h)
    have hyp : y ≠ p := fun h => hyid (congrArg «摆件».«号» h)
    rcases he with he | he
    · exact ⟨field_units_disjoint F hF x p hx hp hxp _ he.1,
        field_units_disjoint F hF y p hy hp hyp _ he.2⟩
    · exact ⟨field_units_disjoint F hF y p hy hp hyp _ he.2,
        field_units_disjoint F hF x p hx hp hxp _ he.1⟩

private theorem geometry_remove (F : «场地») (hF : FieldGood F) (o : «接通先后»)
    (p : «摆件») (hp : p ∈ F) (c : «通道») :
    Geometry (F.filter (fun q => q.«号» != p.«号»)) o c ↔
      Geometry F o c ∧ c.«起» ∉ p.«单位».map Prod.fst ∧ c.«止» ∉ p.«单位».map Prod.fst := by
  constructor
  · rintro ⟨x,hx,y,hy,hc⟩
    obtain ⟨hx, hxid⟩ := List.mem_filter.mp hx
    obtain ⟨hy, hyid⟩ := List.mem_filter.mp hy
    exact ⟨⟨x,hx,y,hy,hc⟩, (between_avoids F hF o p x y hp hx hy c hc).mpr
      ⟨by simpa using hxid, by simpa using hyid⟩⟩
  · rintro ⟨⟨x,hx,y,hy,hc⟩, hs,ht⟩
    obtain ⟨hxid,hyid⟩ := (between_avoids F hF o p x y hp hx hy c hc).mp ⟨hs,ht⟩
    exact ⟨x, by simp [List.mem_filter,hx,hxid], y, by simp [List.mem_filter,hy,hyid], hc⟩

private theorem replay_removes (s : Snapshot) (us : List Nat) :
    replay s (us.map «事件».«拆除») =
      (s.1.filter (fun p => !us.contains p.1),
       s.2.filter (fun c => !us.contains c.«起» && !us.contains c.«止»)) := by
  induction us generalizing s with
  | nil =>
    have h1 : s.1.filter (fun _ => true) = s.1 := List.filter_eq_self.mpr (by simp)
    have h2 : s.2.filter (fun _ => true) = s.2 := List.filter_eq_self.mpr (by simp)
    simp only [List.map_nil, replay, List.foldl_nil, List.contains_nil, Bool.not_false,
      Bool.and_self, h1, h2]
  | cons u us ih =>
    simp only [List.map_cons, replay, List.foldl_cons]
    rw [← replay, ih]
    simp only [addSnapshot, List.filter_filter, List.contains_cons, Bool.not_or, bne]
    congr 1 <;> apply List.filter_congr <;> intro x hx <;>
      simp [Bool.and_assoc, Bool.and_left_comm, Bool.and_comm, BEq.comm]

private theorem filtered_flatMap {α β : Type} (xs : List α) (f : α → List β)
    (p : α → Bool) (q : β → Bool)
    (h : ∀ x ∈ xs, (f x).filter q = if p x then f x else []) :
    (xs.flatMap f).filter q = (xs.filter p).flatMap f := by
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    simp only [List.flatMap_cons, List.filter_append, h x (by simp)]
    have ht := ih (fun y hy => h y (by simp [hy]))
    cases hp : p x <;> simp [hp, ht]

private theorem remove_units (F : «场地») (hF : FieldGood F) (p : «摆件») (hp : p ∈ F) :
    (F.flatMap «摆件».«单位»).filter (fun v => !(p.«单位».map Prod.fst).contains v.1) =
    (F.filter (fun q => q.«号» != p.«号»)).flatMap «摆件».«单位» := by
  apply filtered_flatMap
  intro q hq
  by_cases he : q.«号» = p.«号»
  · have hqp := field_ids_injective F hF q p hq hp he
    subst q
    simp only [bne_self_eq_false, Bool.false_eq_true, ↓reduceIte]
    apply List.filter_eq_nil_iff.mpr
    intro v hv
    have hm : v.1 ∈ p.«单位».map Prod.fst := List.mem_map.mpr ⟨v,hv,rfl⟩
    simpa using hm
  · simp only [bne_iff_ne, ite_eq_left he]
    apply List.filter_eq_self.mpr
    intro v hv
    have hneq : q ≠ p := fun h => he (congrArg «摆件».«号» h)
    have hn := field_units_disjoint F hF q p hq hp hneq v.1 (List.mem_map.mpr ⟨v,hv,rfl⟩)
    simpa using hn

private theorem sync_remove (F G : «场地») (o : «接通先后») (u : Nat)
    (es : «历史») (s : Snapshot) (hF : FieldGood F) (hs : Synchronized F o s)
    (h : F.«收» u = some (G,es)) : Synchronized G o (replay s es) := by
  unfold «场地».«收» at h
  split at h
  next p he =>
    cases h
    have hp : p ∈ F ∧ p.«号» = u := by
      have hm : p ∈ F.filter (fun p => p.«号» == u) := by rw [he]; simp
      simpa using hm
    rcases hp with ⟨hp,rfl⟩
    have hem : (p.«单位».map fun (v,_) => «事件».«拆除» v) =
        (p.«单位».map Prod.fst).map «事件».«拆除» := by simp [List.map_map]
    rw [hem, replay_removes]
    refine ⟨?_, ?_, ?_⟩
    · rw [hs.1]
      exact remove_units F hF p hp
    · intro q hq
      exact hs.2.1 q (List.mem_filter.mp hq).1
    · intro c
      simp only [List.mem_filter, Bool.and_eq_true, Bool.not_eq_true', List.contains_eq_mem, decide_eq_false_iff_not]
      rw [hs.2.2, geometry_remove F hF o p hp c]
  next => cases h

private theorem sync_place (F G : «场地») (o : «接通先后») (p : «摆件»)
    (es : «历史») (s : Snapshot) (hF : FieldGood F) (hs : Synchronized F o s)
    (h : F.«建» o p = some (G,es)) : Synchronized G o (replay s es) := by
  cases hk : p.«种类» <;> simp only [«场地».«建», hk] at h
  case «物品准入口» d =>
    split at h
    · simp only [Option.bind_eq_bind, Option.bind_eq_some_iff,
        Option.pure_def, Option.some.injEq, Prod.mk.injEq] at h
      obtain ⟨⟨F',es'⟩,hrem,⟨G',fs⟩,hb,hG,hE⟩ := h
      dsimp only at hG hE
      subst G' es
      rw [replay_append]
      exact sync_build F' G o p fs _ (sync_remove F F' o _ es' s hF hs hrem) hb
    · cases h
  all_goals exact sync_build F G o p es s hs h

private theorem sync_empty (o : «接通先后») : Synchronized [] o ([],[]) := by
  refine ⟨rfl, by simp [PortsExist], ?_⟩
  simp [Geometry]

private theorem fold_geometry_sync (step : «场地» → «摆件» → Option («场地» × «历史»))
    (o : «接通先后»)
    (hstep : ∀ F G p es s, FieldGood F → Synchronized F o s → step F p = some (G,es) →
      FieldGood G ∧ Synchronized G o (replay s es))
    (ps : List «摆件») (F G : «场地») (es fs : «历史») (s : Snapshot)
    (hF : FieldGood F) (hs : Synchronized F o (replay s es))
    (h : ps.foldlM (fun (F,es) p => do
      let (G,fs) ← step F p
      return (G,es ++ fs)) (F,es) = some (G,fs)) :
    FieldGood G ∧ Synchronized G o (replay s fs) := by
  apply foldlM_preserves (fun r : «场地» × «历史» =>
    FieldGood r.1 ∧ Synchronized r.1 o (replay s r.2)) _ ?_ ps (F,es) (G,fs) ⟨hF,hs⟩ h
  intro r p t hr ht
  simp only [Option.bind_eq_bind, Option.bind_eq_some_iff, Option.pure_def,
    Option.some.injEq] at ht
  obtain ⟨⟨G',fs'⟩,hg,rfl⟩ := ht
  obtain ⟨hG,hS⟩ := hstep r.1 G' p fs' (replay s r.2) hr.1 hr.2 hg
  exact ⟨hG, by simpa only [replay_append] using hS⟩

private theorem sync_blueprint (F G : «场地») (o : «接通先后») (ps : List «摆件»)
    (es : «历史») (s : Snapshot) (hF : FieldGood F) (hs : Synchronized F o s)
    (h : F.«放蓝图» o ps = some (G,es)) : Synchronized G o (replay s es) := by
  unfold «场地».«放蓝图» at h
  split at h
  · cases h
  · exact (fold_geometry_sync (fun F p => F.«建» o p) o
      (fun F G p es s hF hs hb => ⟨fieldGood_place F G o p es hF hb,
        sync_place F G o p es s hF hs hb⟩) ps F G [] es s hF hs h).2

private theorem sync_rebuild (F : «场地») (o : «接通先后») (ps : List «摆件»)
    (es : «历史») (h : F.«重建» o ps = some es) : Synchronized ps o (replay ([],[]) es) := by
  unfold «场地».«重建» at h
  split at h
  · cases h
  · simp only [Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at h
    obtain ⟨⟨G,fs⟩,hg,rfl⟩ := h
    have hF : FieldGood [] := ⟨by simp, by simp⟩
    obtain ⟨_,hS⟩ := fold_geometry_sync (fun F p => F.«建成» o p) o
      (fun F G p es s hF hs hb => ⟨fieldGood_build F G o p es hF hb,
        sync_build F G o p es s hs hb⟩) ps [] G [] fs ([],[]) hF (sync_empty o) hg
    have he := (rebuild_fold_field ps [] G [] fs o hF hg).2
    simpa only [he, List.nil_append] using hS

private theorem history_snapshot (H : «历史») :
    snapshot (H.«布局于» H.length) = replay ([],[]) H := by
  have hf : ∀ H (a : «布局» × Nat),
      snapshot (H.foldl (fun acc e => (acc.1.«加» (acc.2 + 1) e, acc.2 + 1)) a).1 =
      replay (snapshot a.1) H := by
    intro H
    induction H with
    | nil => intro a; rfl
    | cons e H ih =>
      intro a
      simp only [List.foldl_cons, ih, snapshot_add, replay]
  simpa [«历史».«布局于», snapshot] using hf H ({},0)

private theorem grid_step_sync (un : «未定») (o : «接通先后»)
    (bad : «通道» → Nat) (s t : «格子».«状态») (a : «格子».«操作»)
    (hF : FieldGood s.«场地») (hs : Synchronized s.«场地» o (snapshot s.«模型».«布局»))
    (he : «格子».«作用» un o bad s a = some t) :
    Synchronized t.«场地» o (snapshot t.«模型».«布局») := by
  cases a <;> simp only [«格子».«作用», Option.bind_eq_bind,
    Option.bind_eq_some_iff, Option.pure_def, Option.some.injEq] at he
  case «原样» b =>
    obtain ⟨u,hu,rfl⟩ := he
    have hh := «只有改布局和离线改历史» un _ _ _ _ hu
      (by cases b <;> intros <;> simp [«格子».«原样操作».«模型操作»])
      (by cases b <;> intros <;> simp [«格子».«原样操作».«模型操作»])
    simpa only [«状态».«布局», hh] using hs
  case «离线» ps =>
    obtain ⟨H,hH,u,hu,rfl⟩ := he
    have hd : («操作».«离线» H).«做得了» s.«模型» = true := by
      rw [← «做得了才有结果» un _ _ _, hu]; rfl
    have hh : u.«历史» = H := by
      simp only [«作用», hd, Bool.not_true, Bool.false_eq_true, ↓reduceIte] at hu
      cases hu; rfl
    simpa only [«状态».«布局», hh, history_snapshot] using sync_rebuild s.«场地» o ps H hH
  all_goals
    obtain ⟨⟨F,es⟩,hgeom,u,hu,rfl⟩ := he
    dsimp only
    rw [execute_snapshot un _ _ _ es hu]
    first
      | exact sync_place _ _ o _ es _ hF hs hgeom
      | exact sync_remove _ _ o _ es _ hF hs hgeom
      | exact sync_blueprint _ _ o _ es _ hF hs hgeom

private theorem reachable_sync (un : «未定») (o : «接通先后») (bad : «通道» → Nat)
    (f : «格子».«状态») (h : «命题».«格子可达» un o bad f) :
    Synchronized f.«场地» o (snapshot f.«模型».«布局») := by
  obtain ⟨as, ha⟩ := h
  suffices ∀ as s t, FieldGood s.«场地» → Synchronized s.«场地» o (snapshot s.«模型».«布局») →
      «命题».«格子依次作用» un o bad s as = some t → Synchronized t.«场地» o (snapshot t.«模型».«布局») from
    this as _ f ⟨by simp [«格子».«状态».«空»], by simp [«格子».«状态».«空»]⟩ (sync_empty o) ha
  intro as
  induction as with
  | nil => intro s t _ hs he; cases he; exact hs
  | cons a as ih =>
    intro s t hF hs he
    simp only [«命题».«格子依次作用», Option.bind_eq_some_iff] at he
    obtain ⟨u,hu,ht⟩ := he
    exact ih u t (grid_step_fieldGood un o bad s u a hF hu) (grid_step_sync un o bad s u a hF hs hu) ht

private theorem forms_has_output (p q : «摆件») (a b : «端口») (c : «通道»)
    (h : «格子».«形成通道» p q a b = some c) : a.«取货» = true ∨ b.«取货» = true := by
  cases ha : a.«取货» <;> cases hb : b.«取货» <;> simp_all [«格子».«形成通道», «端口».«正对紧贴»]

private theorem geometry_list (F : «场地») (o : «接通先后») (h : PortsExist F o) :
    ∃ cs, «命题».«场地该有的通道» F o = some cs ∧ ∀ c, c ∈ cs ↔ Geometry F o c := by
  obtain ⟨rows,hrows⟩ := mapM_exists (fun p => do return (p, ← p.«端口» o)) F (by
    intro p hp
    obtain ⟨ps,hps⟩ := h p hp
    exact ⟨(p,ps), by simp [hps]⟩)
  let cs := rows.flatMap fun (p,as) => (as.filter (·.«取货»)).flatMap fun a =>
    rows.flatMap fun (q,bs) => bs.filterMap fun b => «格子».«形成通道» p q a b
  refine ⟨cs, ?_, ?_⟩
  · unfold «命题».«场地该有的通道»
    change (F.mapM (fun p : «摆件» => do return (p, ← p.«端口» o))).bind _ = some cs
    rw [hrows]
    rfl
  · intro c
    change c ∈ rows.flatMap _ ↔ Geometry F o c
    constructor
    · intro hc
      obtain ⟨⟨p,ps⟩,hp,hc⟩ := List.mem_flatMap.mp hc
      obtain ⟨a,ha,hc⟩ := List.mem_flatMap.mp hc
      obtain ⟨⟨q,qs⟩,hq,hc⟩ := List.mem_flatMap.mp hc
      obtain ⟨b,hb,hform⟩ := List.mem_filterMap.mp hc
      obtain ⟨hpF,hps⟩ := (rows_mem F o rows hrows p ps).mp hp
      obtain ⟨hqF,hqs⟩ := (rows_mem F o rows hrows q qs).mp hq
      exact ⟨p,hpF,q,hqF,ps,qs,hps,hqs,a,(List.mem_filter.mp ha).1,b,hb,hform⟩
    · rintro ⟨p,hp,q,hq,ps,qs,hps,hqs,a,ha,b,hb,hform⟩
      rcases forms_has_output p q a b c hform with hat | hbt
      · exact List.mem_flatMap.mpr ⟨(p,ps),(rows_mem F o rows hrows p ps).mpr ⟨hp,hps⟩,
          List.mem_flatMap.mpr ⟨a,List.mem_filter.mpr ⟨ha,hat⟩,
            List.mem_flatMap.mpr ⟨(q,qs),(rows_mem F o rows hrows q qs).mpr ⟨hq,hqs⟩,
              List.mem_filterMap.mpr ⟨b,hb,hform⟩⟩⟩⟩
      · exact List.mem_flatMap.mpr ⟨(q,qs),(rows_mem F o rows hrows q qs).mpr ⟨hq,hqs⟩,
          List.mem_flatMap.mpr ⟨b,List.mem_filter.mpr ⟨hb,hbt⟩,
            List.mem_flatMap.mpr ⟨(p,ps),(rows_mem F o rows hrows p ps).mpr ⟨hp,hps⟩,
              List.mem_filterMap.mpr ⟨a,ha,by rwa [forms_swap]⟩⟩⟩⟩

/-- 据：通道、接通

格子层可达状态中，单位表按场地建成先后一致，通道集合恰好等于几何上形成的通道。 -/
theorem «格子层的单位和通道» : «命题».«格子层的单位和通道» := by
  intro un o bad f hf
  have hs := reachable_sync un o bad f hf
  refine ⟨hs.1, ?_⟩
  obtain ⟨cs,hcs,hgeom⟩ := geometry_list f.«场地» o hs.2.1
  exact ⟨cs,hcs,fun c => (hgeom c).trans (hs.2.2 c).symm⟩

private theorem «对边再对边» (d : «朝向») : d.«对边».«对边» = d := by
  cases d <;> rfl

private theorem «坐标成功» (i j : Nat) (c : «格») (h : «格».«坐标» i j = some c) :
    c.i.val = i ∧ c.j.val = j := by
  unfold «格».«坐标» at h
  split at h <;> try contradiction
  split at h <;> try contradiction
  cases h
  exact ⟨rfl,rfl⟩

private theorem «邻格反向» (a b : «格») (d : «朝向»)
    (h : a.«邻格» d = some b) : b.«邻格» d.«对边» = some a := by
  have hai := a.i.isLt
  have haj := a.j.isLt
  have hbi := b.i.isLt
  have hbj := b.j.isLt
  have hc (x y : Nat) (hx : x = a.i.val) (hy : y = a.j.val) :
      «格».«坐标» x y = some a := by
    subst x; subst y
    simp [«格».«坐标», hai, haj]
  cases d <;> simp only [«格».«邻格»] at h
  · split at h
    · contradiction
    · have hh := «坐标成功» _ _ b h
      simp only [«朝向».«对边», «朝向».«顺时针», «格».«邻格»]
      apply hc <;> simp_all <;> omega
  · have hh := «坐标成功» _ _ b h
    simp only [«朝向».«对边», «朝向».«顺时针», «格».«邻格»]
    have hn : ¬ b.i.val == 0 := by simp; omega
    simp only [hn, Bool.false_eq_true, ↓reduceIte]
    apply hc <;> omega
  · have hh := «坐标成功» _ _ b h
    simp only [«朝向».«对边», «朝向».«顺时针», «格».«邻格»]
    have hn : ¬ b.j.val == 0 := by simp; omega
    simp only [hn, Bool.false_eq_true, ↓reduceIte]
    apply hc <;> omega
  · split at h
    · contradiction
    · have hh := «坐标成功» _ _ b h
      simp only [«朝向».«对边», «朝向».«顺时针», «格».«邻格»]
      apply hc <;> simp_all <;> omega

/-- 工具：正对紧贴的端口具有相反的存取标记和对应的起止方向。 -/
theorem «正对性质» (a b : «端口») (h : a.«正对紧贴» b = true) :
    a.«取货» = true ∧ b.«取货» = false ∧ a.«边».«对边» = b.«边» ∧
      a.«格».«邻格» a.«边» = some b.«格» := by
  simp only [«端口».«正对紧贴», Bool.and_eq_true, Bool.not_eq_true', beq_iff_eq,
    bne_iff_ne] at h
  exact ⟨h.1.1.1.1, h.1.1.1.2, h.1.2, h.2⟩

private theorem grid_ext (a b : «格») (hi : a.i.val = b.i.val) (hj : a.j.val = b.j.val) : a = b := by
  cases a; cases b
  simp_all only [Fin.val_inj]

private theorem occupancy_iff (p : «摆件») (cs : List «格») (h : p.«占格» = some cs) (c : «格») :
    c ∈ cs ↔ p.«位置».i.val ≤ c.i.val ∧ c.i.val < p.«位置».i.val + p.«大小».1 ∧
      p.«位置».j.val ≤ c.j.val ∧ c.j.val < p.«位置».j.val + p.«大小».2 := by
  constructor
  · intro hc
    obtain ⟨⟨i,j⟩,hij,hc⟩ := (mapM_mem _ _ _ h c).mp hc
    simp only [List.mem_flatMap, List.mem_range, List.mem_map, Prod.mk.injEq] at hij
    obtain ⟨i',hi,j',hj,rfl,rfl⟩ := hij
    have hh := «坐标成功» _ _ c hc
    omega
  · intro hc
    have hi : c.i.val - p.«位置».i.val < p.«大小».1 := by omega
    have hj : c.j.val - p.«位置».j.val < p.«大小».2 := by omega
    apply (mapM_mem _ _ _ h c).mpr
    refine ⟨(c.i.val - p.«位置».i.val, c.j.val - p.«位置».j.val), ?_, ?_⟩
    · simp only [List.mem_flatMap, List.mem_range, List.mem_map]
      exact ⟨_, hi, _, hj, rfl⟩
    · have hei : p.«位置».i.val + (c.i.val - p.«位置».i.val) = c.i.val := by omega
      have hej : p.«位置».j.val + (c.j.val - p.«位置».j.val) = c.j.val := by omega
      simp [hei,hej,«格».«坐标»,c.i.isLt,c.j.isLt]

private theorem neighbour_coordinates (c v : «格») (d : «朝向») (h : c.«邻格» d = some v) :
    match d with
    | .«上» => v.i.val = c.i.val ∧ v.j.val + 1 = c.j.val
    | .«右» => v.i.val = c.i.val + 1 ∧ v.j.val = c.j.val
    | .«下» => v.i.val = c.i.val ∧ v.j.val = c.j.val + 1
    | .«左» => v.i.val + 1 = c.i.val ∧ v.j.val = c.j.val := by
  cases d <;> simp only [«格».«邻格»] at h
  · split at h
    · cases h
    next hz =>
      have hh := «坐标成功» _ _ v h
      simp only [beq_iff_eq] at hz
      exact ⟨hh.1, by omega⟩
  · exact «坐标成功» _ _ v h
  · exact «坐标成功» _ _ v h
  · split at h
    · cases h
    next hz =>
      have hh := «坐标成功» _ _ v h
      simp only [beq_iff_eq] at hz
      exact ⟨by omega,hh.2⟩

private theorem rectangle_neighbour_unique (p : «摆件») (cs : List «格»)
    (hcs : p.«占格» = some cs) (c a b : «格») (hc : c ∉ cs)
    (ha : a ∈ cs) (hb : b ∈ cs) (d e : «朝向»)
    (hda : c.«邻格» d = some a) (heb : c.«邻格» e = some b) : d = e := by
  have ha' := (occupancy_iff p cs hcs a).mp ha
  have hb' := (occupancy_iff p cs hcs b).mp hb
  have hc' : ¬ (p.«位置».i.val ≤ c.i.val ∧ c.i.val < p.«位置».i.val + p.«大小».1 ∧
      p.«位置».j.val ≤ c.j.val ∧ c.j.val < p.«位置».j.val + p.«大小».2) :=
    fun h => hc ((occupancy_iff p cs hcs c).mpr h)
  have hd := neighbour_coordinates c a d hda
  have he := neighbour_coordinates c b e heb
  cases d <;> cases e <;> simp_all <;> omega

private theorem transport_size (p : «摆件») (hp : p.«是运输单位» = true) : p.«大小» = (1,1) := by
  cases hk : p.«种类» <;> simp_all [«摆件».«是运输单位», «摆件».«单位», «摆件».«大小»,
    «单位种类».«是运输单位», «朝向».«各边»]

private theorem transport_port_cell (p : «摆件») (o : «接通先后») (ps : List «端口»)
    (hp : p.«端口» o = some ps) (ht : p.«是运输单位» = true) (a : «端口») (ha : a ∈ ps) :
    a.«格» = p.«位置» := by
  obtain ⟨cs,hcs⟩ := («端口展开成功» p o ps hp).1
  have hc := «端口格在占格里» p o ps cs hp hcs a ha
  have hb := (occupancy_iff p cs hcs a.«格»).mp hc
  rw [transport_size p ht] at hb
  apply grid_ext <;> dsimp only at hb <;> omega

private theorem port_neighbour (a b : «端口»)
    (h : a.«正对紧贴» b = true ∨ b.«正对紧贴» a = true) :
    a.«格».«邻格» a.«边» = some b.«格» ∧ a.«边».«对边» = b.«边» := by
  rcases h with h | h
  · have hh := «正对性质» a b h
    exact ⟨hh.2.2.2,hh.2.2.1⟩
  · have hh := «正对性质» b a h
    have hd : a.«边».«对边» = b.«边» := by rw [← hh.2.2.1, «对边再对边»]
    exact ⟨by simpa only [hh.2.2.1] using «邻格反向» b.«格» a.«格» b.«边» hh.2.2.2,hd⟩

/-- 工具：形成通道时的运输条件、端口接触和起止单位。 -/
theorem forms_properties (p q : «摆件») (a b : «端口») (c : «通道»)
    (h : «格子».«形成通道» p q a b = some c) :
    p.«号» ≠ q.«号» ∧ (p.«是运输单位» = true ∨ q.«是运输单位» = true) ∧
    ((a.«正对紧贴» b = true ∧ c = ⟨a.«单位»,b.«单位»⟩) ∨
     (b.«正对紧贴» a = true ∧ c = ⟨b.«单位»,a.«单位»⟩)) := by
  unfold «格子».«形成通道» at h
  split at h
  · cases h
  next hp =>
    have hp : p.«号» ≠ q.«号» ∧ (p.«是运输单位» = true ∨ q.«是运输单位» = true) := by
      constructor
      · intro he; simp [he] at hp
      · cases hpt : p.«是运输单位» <;> cases hqt : q.«是运输单位» <;> simp_all
    refine ⟨hp.1,hp.2,?_⟩
    split at h
    next ha => cases h; exact Or.inl ⟨ha,rfl⟩
    next =>
      split at h
      next hb => cases h; exact Or.inr ⟨hb,rfl⟩
      next => cases h

private theorem contacting_port_unique (F : «场地») (o : «接通先后») (hF : FieldGood F)
    (p q : «摆件») (hpF : p ∈ F) (hqF : q ∈ F) (ps qs : List «端口»)
    (hps : p.«端口» o = some ps) (hqs : q.«端口» o = some qs)
    (a a' b b' : «端口») (ha : a ∈ ps) (ha' : a' ∈ ps) (hb : b ∈ qs) (hb' : b' ∈ qs)
    (ht : a.«取货» = a'.«取货») (c d : «通道»)
    (hc : «格子».«形成通道» p q a b = some c)
    (hd : «格子».«形成通道» p q a' b' = some d) : a = a' := by
  have hc' := forms_properties p q a b c hc
  have hd' := forms_properties p q a' b' d hd
  have hpn : p ≠ q := fun h => hc'.1 (congrArg «摆件».«号» h)
  have hsep := field_separate F hF p q hpF hqF hpn
  obtain ⟨cs,hcs⟩ := hF.1 p hpF
  obtain ⟨ds,hds⟩ := hF.1 q hqF
  have hac := «端口格在占格里» p o ps cs hps hcs a ha
  have ha'c := «端口格在占格里» p o ps cs hps hcs a' ha'
  have hbc := «端口格在占格里» q o qs ds hqs hds b hb
  have hb'c := «端口格在占格里» q o qs ds hqs hds b' hb'
  have hpairs := port_neighbour a b (hc'.2.2.imp And.left And.left)
  have hpairs' := port_neighbour a' b' (hd'.2.2.imp And.left And.left)
  have hcellside : a.«格» = a'.«格» ∧ a.«边» = a'.«边» := by
    rcases hc'.2.1 with hpt | hqt
    · have hap := transport_port_cell p o ps hps hpt a ha
      have hap' := transport_port_cell p o ps hps hpt a' ha'
      have hcell : a.«格» = a'.«格» := hap.trans hap'.symm
      refine ⟨hcell,?_⟩
      apply rectangle_neighbour_unique q ds hds a.«格» b.«格» b'.«格»
        (hsep.2.1 cs ds hcs hds _ hac) hbc hb'c _ _ hpairs.1
      simpa only [hcell] using hpairs'.1
    · have hbp := transport_port_cell q o qs hqs hqt b hb
      have hbp' := transport_port_cell q o qs hqs hqt b' hb'
      have hcell : b.«格» = b'.«格» := hbp.trans hbp'.symm
      have hba := «邻格反向» a.«格» b.«格» a.«边» hpairs.1
      have hba' := «邻格反向» a'.«格» b'.«格» a'.«边» hpairs'.1
      have hside := rectangle_neighbour_unique p cs hcs b.«格» a.«格» a'.«格»
        ((separate_symm hsep).2.1 ds cs hds hcs _ hbc) hac ha'c _ _ hba
        (by simpa only [hcell] using hba')
      have hside' : a.«边» = a'.«边» := by
        simpa only [«对边再对边»] using congrArg «朝向».«对边» hside
      refine ⟨?_,hside'⟩
      rw [hcell,hside] at hba
      exact Option.some.inj (hba.symm.trans hba')
  have hunits := «端口同边同类同单位» p o ps hps a a' ha ha' hcellside.2 ht
  cases a; cases a'
  simp_all

private def rawStyles (p : «摆件»)  : List (Bool × «朝向» × Nat) :=
  let ring := fun (d : «朝向») => [d.«顺时针», d.«对边», d.«对边».«顺时针»]
  let sides := fun (d : «朝向») =>
    let n := if d == .«上» || d == .«下» then p.«大小».1 else p.«大小».2
    let ns := «同边先后» d n
    ns.map (fun n => (false, d.«对边», n)) ++ ns.map (fun n => (true, d, n))
  match p.«种类» with
  | .«传送带» a b => [(false, a, 0), (true, b, 0)]
  | .«分流器» d => (false, d, 0) :: (ring d).map (fun d => (true, d, 0))
  | .«汇流器» d => (ring d).map (fun d => (false, d, 0)) ++ [(true, d, 0)]
  | .«物品准入口» d => [(false, d.«对边», 0), (true, d, 0)]
  | .«桥接器» _ =>
    let ds := «朝向».«各边».map fun d => (d, 0)
    ds.map (fun (d,n) => (false,d,n)) ++
      ds.map (fun (d,n) => (true,d,n))
  | .«协议储存箱» d | .«制造» _ d => sides d
  | .«协议核心» a =>
    («核心边格» a false).map (fun (d,n) => (false,d,n)) ++
      («核心边格» a true).map (fun (d,n) => (true,d,n))
  | .«仓库取货口» d => [(true, d, 1)]
  | .«供电桩» => []

private theorem styles_perm (p : «摆件») (o : «接通先后») :
    («端口样式» p o).Perm (rawStyles p) := by
  cases hk : p.«种类» <;> simp only [«端口样式», rawStyles, hk]
  all_goals first
    | exact List.Perm.refl _
    | apply List.Perm.append <;> apply List.Perm.map <;> exact List.mergeSort_perm _ _

private theorem styles_nodup (p : «摆件») (o : «接通先后») : («端口样式» p o).Nodup := by
  apply (styles_perm p o).symm.nodup
  cases hk : p.«种类»
  case «传送带» a b => simp [rawStyles,hk]
  case «分流器» d => cases d <;> simp only [rawStyles,hk] <;> decide
  case «汇流器» d => cases d <;> simp only [rawStyles,hk] <;> decide
  case «物品准入口» d => simp [rawStyles,hk]
  case «桥接器» => simp only [rawStyles,hk]; decide
  case «协议储存箱» d =>
    cases d <;> simp only [rawStyles,hk,«摆件».«大小»] <;> decide
  case «制造» k d =>
    cases k <;> cases d <;> simp only [rawStyles,hk,«摆件».«大小»] <;> decide
  case «协议核心» a => cases a <;> simp only [rawStyles,hk] <;> decide
  case «仓库取货口» d => simp [rawStyles,hk]
  case «供电桩» => simp [rawStyles,hk]

private theorem edge_cell_index (p : «摆件») (d : «朝向») (i j : Nat) (c : «格»)
    (hi : p.«边格» d i = some c) (hj : p.«边格» d j = some c) : i = j := by
  cases d <;> simp only [«摆件».«边格»] at hi hj <;>
    split at hi <;> try contradiction
  all_goals split at hj <;> try contradiction
  all_goals
    have h1 := «坐标成功» _ _ c hi
    have h2 := «坐标成功» _ _ c hj
    omega

private theorem make_port_injective (p : «摆件») (v w : Bool × «朝向» × Nat) (a : «端口»)
    (hv : p.«造端口» v.1 v.2.1 v.2.2 = some a)
    (hw : p.«造端口» w.1 w.2.1 w.2.2 = some a) : v = w := by
  have h1 := «造端口性质» p v.1 v.2.1 v.2.2 a hv
  have h2 := «造端口性质» p w.1 w.2.1 w.2.2 a hw
  have hd : v.2.1 = w.2.1 := h1.2.1.symm.trans h2.2.1
  have hb : v.1 = w.1 := h1.2.2.1.symm.trans h2.2.2.1
  have hn := edge_cell_index p w.2.1 v.2.2 w.2.2 a.«格» (by simpa only [hd] using h1.2.2.2) h2.2.2.2
  exact Prod.ext hb (Prod.ext hd hn)

private theorem mapM_nodup {α β : Type} (f : α → Option β) (xs : List α) (ys : List β)
    (hx : xs.Nodup) (h : xs.mapM f = some ys)
    (hinj : ∀ x ∈ xs, ∀ y ∈ xs, ∀ z, f x = some z → f y = some z → x = y) : ys.Nodup := by
  induction xs generalizing ys with
  | nil => simp at h; subst ys; simp
  | cons x xs ih =>
    simp only [List.mapM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at h
    obtain ⟨y,hy,ys,hys,rfl⟩ := h
    obtain ⟨hnot,ht⟩ := List.nodup_cons.mp hx
    apply List.nodup_cons.mpr
    constructor
    · intro hm
      obtain ⟨z,hz,hfz⟩ := (mapM_mem _ _ _ hys y).mp hm
      have he := hinj x (by simp) z (by simp [hz]) y hy hfz
      exact hnot (he ▸ hz)
    · exact ih ys ht hys (fun x hx z hz => hinj x (by simp [hx]) z (by simp [hz]))

/-- 工具：成功生成的完整端口表没有重复端口。 -/
theorem ports_nodup (p : «摆件») (o : «接通先后») (ps : List «端口»)
    (h : p.«端口» o = some ps) : ps.Nodup := by
  exact mapM_nodup _ _ _ (styles_nodup p o) («端口展开成功» p o ps h).2
    (fun v _ w _ a hv hw => make_port_injective p v w a hv hw)

/-- 工具：同一场地中的单位号确定唯一摆件。 -/
theorem field_unit_owner (F : «场地») (hF : FieldGood F) (p q : «摆件»)
    (hp : p ∈ F) (hq : q ∈ F) (u : Nat)
    (hu : u ∈ p.«单位».map Prod.fst) (hu' : u ∈ q.«单位».map Prod.fst) : p = q := by
  by_cases he : p = q
  · exact he
  · exact (field_units_disjoint F hF p q hp hq he u hu hu').elim

/-- 工具：同一摆件形成同一通道时使用同一个端口。 -/
theorem same_channel_port (F : «场地») (o : «接通先后») (hF : FieldGood F)
    (p q r : «摆件») (hpF : p ∈ F) (hqF : q ∈ F) (hrF : r ∈ F)
    (ps qs rs : List «端口») (hps : p.«端口» o = some ps)
    (hqs : q.«端口» o = some qs) (hrs : r.«端口» o = some rs)
    (a a' b b' : «端口») (ha : a ∈ ps) (ha' : a' ∈ ps) (hb : b ∈ qs) (hb' : b' ∈ rs)
    (c : «通道») (hc : «格子».«形成通道» p q a b = some c)
    (hd : «格子».«形成通道» p r a' b' = some c) : a = a' := by
  have hau := «端口单位属于摆件» p o ps hps a ha
  have ha'u := «端口单位属于摆件» p o ps hps a' ha'
  have hbu := «端口单位属于摆件» q o qs hqs b hb
  have hb'u := «端口单位属于摆件» r o rs hrs b' hb'
  have hc' := forms_properties p q a b c hc
  have hd' := forms_properties p r a' b' c hd
  have howners : q = r ∧ a.«取货» = a'.«取货» := by
    rcases hc'.2.2 with ⟨hab,hec⟩ | ⟨hba,hec⟩ <;>
      rcases hd'.2.2 with ⟨ha'b',hed⟩ | ⟨hb'a',hed⟩
    · have he := congrArg «通道».«止» (hec.symm.trans hed)
      dsimp only at he
      have hqr := field_unit_owner F hF q r hqF hrF b.«单位» hbu (by simpa only [he] using hb'u)
      exact ⟨hqr, («正对性质» a b hab).1.trans («正对性质» a' b' ha'b').1.symm⟩
    · have he := congrArg «通道».«起» (hec.symm.trans hed)
      dsimp only at he
      have hpr := field_unit_owner F hF p r hpF hrF a.«单位» hau (by simpa only [he] using hb'u)
      exact (hd'.1 (congrArg «摆件».«号» hpr)).elim
    · have he := congrArg «通道».«止» (hec.symm.trans hed)
      dsimp only at he
      have hpr := field_unit_owner F hF p r hpF hrF a.«单位» hau (by simpa only [he] using hb'u)
      exact (hd'.1 (congrArg «摆件».«号» hpr)).elim
    · have he := congrArg «通道».«起» (hec.symm.trans hed)
      dsimp only at he
      have hqr := field_unit_owner F hF q r hqF hrF b.«单位» hbu (by simpa only [he] using hb'u)
      exact ⟨hqr, («正对性质» b a hba).2.1.trans («正对性质» b' a' hb'a').2.1.symm⟩
  rcases howners with ⟨rfl,ht⟩
  have heq : rs = qs := Option.some.inj (hrs.symm.trans hqs)
  subst rs
  exact contacting_port_unique F o hF p q hpF hqF ps qs hps hqs a a' b b' ha ha' hb hb' ht c c hc hd

private theorem mapM_flatten_nodup {α β : Type} (f : α → Option (List β)) (xs : List α)
    (ys : List (List β)) (hx : xs.Nodup) (h : xs.mapM f = some ys)
    (hn : ∀ x ∈ xs, ∀ zs, f x = some zs → zs.Nodup)
    (hinj : ∀ x ∈ xs, ∀ y ∈ xs, ∀ zs ws z, f x = some zs → f y = some ws →
      z ∈ zs → z ∈ ws → x = y) : ys.flatten.Nodup := by
  induction xs generalizing ys with
  | nil => simp at h; subst ys; simp
  | cons x xs ih =>
    simp only [List.mapM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at h
    obtain ⟨zs,hzs,ys,hys,rfl⟩ := h
    obtain ⟨hnot,ht⟩ := List.nodup_cons.mp hx
    apply List.nodup_append.mpr
    refine ⟨hn x (by simp) zs hzs,
      ih ys ht hys (fun y hy => hn y (by simp [hy]))
        (fun y hy z hz => hinj y (by simp [hy]) z (by simp [hz])), ?_⟩
    intro a ha b hb he
    subst b
    obtain ⟨ws,hws,haw⟩ := List.mem_flatten.mp hb
    obtain ⟨y,hy,hyf⟩ := (mapM_mem _ _ _ hys ws).mp hws
    have heq := hinj x (by simp) y (by simp [hy]) zs ws a hzs hyf ha haw
    exact hnot (heq ▸ hy)

private theorem select_connections_nodup (cs : List «通道») (es : «历史»)
    (h : (match cs with
      | [] => some ([] : «历史»)
      | [c] => some [«事件».«接通» c]
      | _ => none) = some es) : es.Nodup := by
  cases cs with
  | nil => cases h; simp
  | cons c cs => cases cs with
    | nil => cases h; simp
    | cons d cs => cases h

private theorem connections_nodup (F : «场地») (o : «接通先后») (p : «摆件») (es : «历史»)
    (hF : FieldGood (F ++ [p])) (h : F.«接通事件» o p = some es) : es.Nodup := by
  unfold «场地».«接通事件» at h
  simp only [Option.bind_eq_bind, Option.bind_eq_some_iff, Option.pure_def,
    Option.some.injEq] at h
  obtain ⟨ps,hps,rows,hrows,ess,hess,rfl⟩ := h
  apply mapM_flatten_nodup _ ps ess (ports_nodup p o ps hps) hess
  · intro a _ zs hz
    exact select_connections_nodup _ zs hz
  · intro a ha a' ha' zs ws e hz hw hez hew
    rw [select_connections _ zs hz] at hez
    rw [select_connections _ ws hw] at hew
    obtain ⟨c,hc,rfl⟩ := List.mem_map.mp hez
    obtain ⟨d,hd,he⟩ := List.mem_map.mp hew
    cases he
    obtain ⟨⟨q,qs⟩,hq,hc⟩ := List.mem_flatMap.mp hc
    obtain ⟨b,hb,hform⟩ := List.mem_filterMap.mp hc
    obtain ⟨⟨r,rs⟩,hr,hd⟩ := List.mem_flatMap.mp hd
    obtain ⟨b',hb',hform'⟩ := List.mem_filterMap.mp hd
    obtain ⟨hqF,hqs⟩ := (rows_mem F o rows hrows q qs).mp hq
    obtain ⟨hrF,hrs⟩ := (rows_mem F o rows hrows r rs).mp hr
    exact same_channel_port (F ++ [p]) o hF p q r (by simp) (by simp [hqF]) (by simp [hrF])
      ps qs rs hps hqs hrs a a' b b' ha ha' hb hb' _ hform hform'

private def snapshotLayout (s : Snapshot) : «布局» := ⟨s.1, s.2.map (fun c => (c,0))⟩

private def allowed (s : Snapshot) (e : «事件») : Bool := (snapshotLayout s).«容得下» e

private def Feasible (s : Snapshot) : «历史» → Prop
  | [] => True
  | e :: es => allowed s e = true ∧ Feasible (addSnapshot s e) es

private theorem allowed_snapshot (L : «布局») (e : «事件») : allowed (snapshot L) e = L.«容得下» e := by
  cases e <;> simp [allowed,snapshotLayout,snapshot,«布局».«容得下»,«布局».«种类»,
    «布局».«是运输单位»,List.any_map,List.map_map,Function.comp_def]

private theorem feasible_append (s : Snapshot) (es fs : «历史») :
    Feasible s (es ++ fs) ↔ Feasible s es ∧ Feasible (replay s es) fs := by
  induction es generalizing s with
  | nil => simp [Feasible,replay]
  | cons e es ih => simp [Feasible,replay,List.foldl_cons,ih,and_assoc]

private theorem feasible_execute (un : «未定») (todo : «待写») (s : «状态») (es : «历史»)
    (h : Feasible (snapshot s.«布局») es) : ∃ t, «格子».«执行事件» un todo s es = some t := by
  induction es generalizing s with
  | nil => exact ⟨s,rfl⟩
  | cons e es ih =>
    have hd : («操作».«改布局» e).«做得了» s = true := by
      simpa only [«操作».«做得了»,allowed_snapshot] using h.1
    have hsome : («作用» un todo s (.«改布局» e)).isSome = true := by
      rw [«做得了才有结果»]; exact hd
    cases hu : «作用» un todo s (.«改布局» e) with
    | none => simp [hu] at hsome
    | some u =>
      have hx := execute_snapshot un todo s u [e] (by simpa [«格子».«执行事件»] using hu)
      have hh : Feasible (snapshot u.«布局») es := by
        rw [hx]; exact h.2
      obtain ⟨t,ht⟩ := ih u hh
      exact ⟨t,by simpa [«格子».«执行事件»,hu] using ht⟩

private def UnitsGood (us : List («单位号» × «单位种类»)) : Prop :=
  us.Pairwise (fun a b => a.1 ≠ b.1 ∧ (a.2 = .«协议核心» → b.2 ≠ .«协议核心»))

private theorem piece_units_good (p : «摆件») : UnitsGood p.«单位» := by
  cases hk : p.«种类» <;> simp [UnitsGood,«摆件».«单位»,hk,«朝向».«各边»,«朝向».«编号»]

private theorem piece_core (p : «摆件») (u : Nat) (k : «单位种类»)
    (hu : (u,k) ∈ p.«单位») (hk : k = .«协议核心») : p.«是核心» = true := by
  subst k
  cases hp : p.«种类» <;> simp_all [«摆件».«单位»,«摆件».«是核心»,«朝向».«各边»,«朝向».«编号»]

private theorem field_units_good (F : «场地») (hF : FieldGood F) : UnitsGood (F.flatMap «摆件».«单位») := by
  apply List.pairwise_flatMap.mpr
  constructor
  · intro p _; exact piece_units_good p
  · apply hF.2.imp
    intro p q hsep a ha b hb
    refine ⟨?_,?_⟩
    · intro he
      exact hsep.1 a.1 (unit_id_reserved p a.1 (List.mem_map.mpr ⟨a,ha,rfl⟩))
        (by simpa only [he] using unit_id_reserved q b.1 (List.mem_map.mpr ⟨b,hb,rfl⟩))
    · intro haCore hbCore
      have hp := piece_core p a.1 a.2 ha haCore
      have hq := piece_core q b.1 b.2 hb hbCore
      have := hsep.2.2 hp
      simp [hq] at this

private theorem units_good_nodup (us : List («单位号» × «单位种类»)) (h : UnitsGood us) :
    (us.map Prod.fst).Nodup := List.pairwise_map.mpr (h.imp (fun {_ _} h => h.1))

private theorem kind_none_of (us : List («单位号» × «单位种类»)) (u : Nat)
    (h : ∀ v ∈ us, v.1 ≠ u) : («布局».mk us []).«种类» u = none := by
  unfold «布局».«种类»
  have hh : us.find? (fun p => p.1 == u) = none := List.find?_eq_none.mpr (by simpa using h)
  rw [hh]; rfl

private theorem kind_of_mem (us : List («单位号» × «单位种类»)) (u : Nat) (k : «单位种类»)
    (hn : (us.map Prod.fst).Nodup) (hu : (u,k) ∈ us) : («布局».mk us []).«种类» u = some k := by
  induction us with
  | nil => simp at hu
  | cons v us ih =>
    obtain ⟨hnot,ht⟩ := List.nodup_cons.mp hn
    rcases List.mem_cons.mp hu with hv | hu
    · subst v; simp [«布局».«种类»]
    · have hne : v.1 ≠ u := by
        intro he
        exact hnot (List.mem_map.mpr ⟨(u,k),hu,he.symm⟩)
      simpa [«布局».«种类»,hne] using ih ht hu

private theorem feasible_builds (s : Snapshot) (us : List («单位号» × «单位种类»))
    (h : UnitsGood (s.1 ++ us)) : Feasible s (us.map fun (u,k) => .«建成» u k) := by
  induction us generalizing s with
  | nil => trivial
  | cons uk us ih =>
    have hpair := (List.pairwise_append.mp h).2.2
    refine ⟨?_,?_⟩
    · have hn := kind_none_of s.1 uk.1 (fun v hv => (hpair v hv uk (by simp)).1)
      have hc : uk.2 = .«协议核心» → s.1.any (fun v => v.2 == .«协议核心») = false := by
        intro hk
        apply List.any_eq_false.mpr
        intro v hv
        have hh := (hpair v hv uk (by simp)).2
        have hneq : v.2 ≠ .«协议核心» := fun hcore => hh hcore hk
        simpa using hneq
      change ((snapshotLayout s).«种类» uk.1).isNone &&
        (uk.2 != .«协议核心» || !s.1.any (fun v => v.2 == .«协议核心»)) = true
      have hn' : (snapshotLayout s).«种类» uk.1 = none := hn
      rw [hn']
      by_cases hk : uk.2 = .«协议核心» <;> simp [hk,hc]
    · apply ih
      simpa [addSnapshot,List.append_assoc] using h

private theorem feasible_removes (s : Snapshot) (us : List Nat)
    (hn : us.Nodup) (hu : ∀ u ∈ us, u ∈ s.1.map Prod.fst) :
    Feasible s (us.map «事件».«拆除») := by
  induction us generalizing s with
  | nil => trivial
  | cons u us ih =>
    obtain ⟨hnot,ht⟩ := List.nodup_cons.mp hn
    refine ⟨?_,?_⟩
    · obtain ⟨uk,huk,he⟩ := List.mem_map.mp (hu u (by simp))
      have hm : (s.1.find? (fun v => v.1 == u)).isSome = true := by
        rw [List.isSome_find?]
        exact List.any_eq_true.mpr ⟨uk,huk,by simp [he]⟩
      simpa [allowed,snapshotLayout,«布局».«容得下»,«布局».«种类»] using hm
    · apply ih _ ht
      intro v hv
      obtain ⟨uk,huk,he⟩ := List.mem_map.mp (hu v (by simp [hv]))
      refine List.mem_map.mpr ⟨uk,?_,he⟩
      change uk ∈ s.1.filter (fun w => w.1 != u)
      apply List.mem_filter.mpr
      refine ⟨huk,?_⟩
      have hneq : v ≠ u := fun h => hnot (h ▸ hv)
      simpa [he] using hneq

private theorem piece_transport (p : «摆件») (u : Nat) (k : «单位种类»)
    (hu : (u,k) ∈ p.«单位») : k.«是运输单位» = p.«是运输单位» := by
  cases hp : p.«种类» <;> simp [«摆件».«单位»,hp,«朝向».«各边»,«朝向».«编号»] at hu <;>
    simp_all [«摆件».«是运输单位»,«摆件».«单位»,«单位种类».«是运输单位»,«朝向».«各边»]
  all_goals grind

private def Connectable (us : List («单位号» × «单位种类»)) (c : «通道») : Prop :=
  c.«起» ≠ c.«止» ∧ ∃ k l, (c.«起»,k) ∈ us ∧ (c.«止»,l) ∈ us ∧
    (k.«是运输单位» = true ∨ l.«是运输单位» = true)

private theorem geometry_connectable (F : «场地») (o : «接通先后») (c : «通道»)
    (h : Geometry F o c) : Connectable (F.flatMap «摆件».«单位») c := by
  obtain ⟨p,hp,q,hq,ps,qs,hps,hqs,a,ha,b,hb,hform⟩ := h
  obtain ⟨⟨u,k⟩,huk,hu⟩ := List.mem_map.mp («端口单位属于摆件» p o ps hps a ha)
  obtain ⟨⟨v,l⟩,hvl,hv⟩ := List.mem_map.mp («端口单位属于摆件» q o qs hqs b hb)
  dsimp only at hu hv
  subst u v
  have hptrans := piece_transport p a.«单位» k huk
  have hqtrans := piece_transport q b.«单位» l hvl
  have hh := forms_properties p q a b c hform
  have hm1 : (a.«单位»,k) ∈ F.flatMap «摆件».«单位» := List.mem_flatMap.mpr ⟨p,hp,huk⟩
  have hm2 : (b.«单位»,l) ∈ F.flatMap «摆件».«单位» := List.mem_flatMap.mpr ⟨q,hq,hvl⟩
  have htrans : k.«是运输单位» = true ∨ l.«是运输单位» = true := by
    simpa only [hptrans,hqtrans] using hh.2.1
  rcases hh.2.2 with ⟨hab,rfl⟩ | ⟨hba,rfl⟩
  · refine ⟨?_,k,l,hm1,hm2,htrans⟩
    simp only [«端口».«正对紧贴»,Bool.and_eq_true,bne_iff_ne] at hab
    exact hab.1.1.2
  · refine ⟨?_,l,k,hm2,hm1,htrans.symm⟩
    simp only [«端口».«正对紧贴»,Bool.and_eq_true,bne_iff_ne] at hba
    exact hba.1.1.2

private theorem allowed_connection (s : Snapshot) (c : «通道»)
    (hn : (s.1.map Prod.fst).Nodup) (hc : Connectable s.1 c) (hnew : c ∉ s.2) :
    allowed s (.«接通» c) = true := by
  obtain ⟨hne,k,l,hk,hl,ht⟩ := hc
  have hsrc : (snapshotLayout s).«种类» c.«起» = some k := kind_of_mem s.1 c.«起» k hn hk
  have hdst : (snapshotLayout s).«种类» c.«止» = some l := kind_of_mem s.1 c.«止» l hn hl
  simp only [allowed,«布局».«容得下»,«布局».«是运输单位»,hsrc,hdst]
  simp [snapshotLayout,List.any_map,List.any_eq_false,hne,ht]
  intro x hx he
  exact hnew (he ▸ hx)

private theorem feasible_connections (s : Snapshot) (es : «历史»)
    (hu : (s.1.map Prod.fst).Nodup) (hn : es.Nodup)
    (he : ∀ e ∈ es, ∃ c, e = .«接通» c ∧ Connectable s.1 c ∧ c ∉ s.2) : Feasible s es := by
  induction es generalizing s with
  | nil => trivial
  | cons e es ih =>
    obtain ⟨c,rfl,hc,hnew⟩ := he e (by simp)
    obtain ⟨hnot,ht⟩ := List.nodup_cons.mp hn
    refine ⟨allowed_connection s c hu hc hnew,?_⟩
    apply ih (addSnapshot s (.«接通» c)) hu ht
    intro e he'
    obtain ⟨d,rfl,hd,hdnew⟩ := he e (by simp [he'])
    refine ⟨d,rfl,hd,?_⟩
    change d ∉ s.2 ++ [c]
    intro hm
    rcases List.mem_append.mp hm with hm | hm
    · exact hdnew hm
    · have hdc : d = c := List.mem_singleton.mp hm
      exact hnot (hdc ▸ he')

private theorem fresh_connection (F : «场地») (o : «接通先后») (p : «摆件»)
    (hF : FieldGood (F ++ [p])) (q : «摆件») (_hq : q ∈ F) (c : «通道»)
    (hc : Between o p q c) : ¬ Geometry F o c := by
  intro hold
  obtain ⟨x,hx,y,hy,hxy⟩ := hold
  have he := between_endpoints o p q c hc
  have hxy' := between_endpoints o x y c hxy
  have hpn (r : «摆件») (hr : r ∈ F) : p ≠ r := by
    have sep := (List.pairwise_append.mp hF.2).2.2 r hr p (by simp)
    intro he
    subst r
    exact sep.1 p.«号» (piece_own_id p) (piece_own_id p)
  have hx' : x ∈ F ++ [p] := by simp [hx]
  have hy' : y ∈ F ++ [p] := by simp [hy]
  have hp' : p ∈ F ++ [p] := by simp
  rcases he with he | he <;> rcases hxy' with hxy' | hxy'
  · exact field_units_disjoint _ hF p x hp' hx' (hpn x hx) _ he.1 hxy'.1
  · exact field_units_disjoint _ hF p y hp' hy' (hpn y hy) _ he.1 hxy'.2
  · exact field_units_disjoint _ hF p y hp' hy' (hpn y hy) _ he.1 hxy'.2
  · exact field_units_disjoint _ hF p x hp' hx' (hpn x hx) _ he.1 hxy'.1

private theorem feasible_build (F G : «场地») (o : «接通先后») (p : «摆件»)
    (es : «历史») (s : Snapshot) (hF : FieldGood F) (hs : Synchronized F o s)
    (h : F.«建成» o p = some (G,es)) : Feasible s es := by
  have hG := fieldGood_build F G o p es hF h
  unfold «场地».«建成» at h
  split at h
  · cases h
  · simp only [Option.bind_eq_bind, Option.bind_eq_some_iff, Option.pure_def,
      Option.some.injEq, Prod.mk.injEq] at h
    obtain ⟨cs,hcs,rfl,rfl⟩ := h
    apply (feasible_append s _ cs).mpr
    have hgu : UnitsGood (s.1 ++ p.«单位») := by
      simpa [hs.1] using field_units_good (F ++ [p]) hG
    refine ⟨feasible_builds s p.«单位» hgu,?_⟩
    rw [replay_builds]
    apply feasible_connections _ cs (units_good_nodup _ hgu) (connections_nodup F o p cs hG hcs)
    intro e he
    obtain ⟨c,rfl,q,hq,hc⟩ := ((connections_spec F o p cs hcs).2 e).mp he
    refine ⟨c,rfl,?_,?_⟩
    · have hgeom : Geometry (F ++ [p]) o c := ⟨p,by simp,q,by simp [hq],hc⟩
      simpa [hs.1] using geometry_connectable (F ++ [p]) o c hgeom
    · intro hm
      exact fresh_connection F o p hG q hq c hc ((hs.2.2 c).mp hm)

private theorem feasible_remove (F G : «场地») (o : «接通先后») (u : Nat)
    (es : «历史») (s : Snapshot) (hs : Synchronized F o s)
    (h : F.«收» u = some (G,es)) : Feasible s es := by
  unfold «场地».«收» at h
  split at h
  next p he =>
    cases h
    have hp : p ∈ F := by
      have hm : p ∈ F.filter (fun q => q.«号» == u) := by rw [he]; simp
      exact (List.mem_filter.mp hm).1
    have hem : (p.«单位».map fun (v,_) => «事件».«拆除» v) =
        (p.«单位».map Prod.fst).map «事件».«拆除» := by simp [List.map_map]
    rw [hem]
    apply feasible_removes s _ (units_good_nodup _ (piece_units_good p))
    intro v hv
    obtain ⟨uk,huk,he⟩ := List.mem_map.mp hv
    rw [hs.1]
    exact List.mem_map.mpr ⟨uk,List.mem_flatMap.mpr ⟨p,hp,huk⟩,he⟩
  next => cases h

private theorem feasible_place (F G : «场地») (o : «接通先后») (p : «摆件»)
    (es : «历史») (s : Snapshot) (hF : FieldGood F) (hs : Synchronized F o s)
    (h : F.«建» o p = some (G,es)) : Feasible s es := by
  cases hk : p.«种类» <;> simp only [«场地».«建», hk] at h
  case «物品准入口» d =>
    split at h
    · simp only [Option.bind_eq_bind, Option.bind_eq_some_iff,
        Option.pure_def, Option.some.injEq, Prod.mk.injEq] at h
      obtain ⟨⟨F',es'⟩,hrem,⟨G',fs⟩,hb,hG,hE⟩ := h
      dsimp only at hG hE
      subst G' es
      apply (feasible_append s es' fs).mpr
      exact ⟨feasible_remove F F' o _ es' s hs hrem,
        feasible_build F' G o p fs _ (fieldGood_remove F F' _ es' hF hrem)
          (sync_remove F F' o _ es' s hF hs hrem) hb⟩
    · cases h
  all_goals exact feasible_build F G o p es s hF hs h

private theorem fold_geometry_feasible (step : «场地» → «摆件» → Option («场地» × «历史»))
    (o : «接通先后»)
    (hstep : ∀ F G p es s, FieldGood F → Synchronized F o s → step F p = some (G,es) →
      FieldGood G ∧ Synchronized G o (replay s es) ∧ Feasible s es)
    (ps : List «摆件») (F G : «场地») (es fs : «历史») (s : Snapshot)
    (hF : FieldGood F) (hs : Synchronized F o (replay s es)) (hfe : Feasible s es)
    (h : ps.foldlM (fun (F,es) p => do
      let (G,fs) ← step F p
      return (G,es ++ fs)) (F,es) = some (G,fs)) : Feasible s fs := by
  have hall : FieldGood G ∧ Synchronized G o (replay s fs) ∧ Feasible s fs := by
    apply foldlM_preserves (fun r : «场地» × «历史» =>
      FieldGood r.1 ∧ Synchronized r.1 o (replay s r.2) ∧ Feasible s r.2) _ ?_
      ps (F,es) (G,fs) ⟨hF,hs,hfe⟩ h
    intro r p t hr ht
    simp only [Option.bind_eq_bind, Option.bind_eq_some_iff, Option.pure_def,
      Option.some.injEq] at ht
    obtain ⟨⟨G',fs'⟩,hg,rfl⟩ := ht
    obtain ⟨hG,hS,hFe⟩ := hstep r.1 G' p fs' (replay s r.2) hr.1 hr.2.1 hg
    exact ⟨hG, by simpa only [replay_append] using hS, (feasible_append s r.2 fs').mpr ⟨hr.2.2,hFe⟩⟩
  exact hall.2.2

private theorem feasible_blueprint (F G : «场地») (o : «接通先后») (ps : List «摆件»)
    (es : «历史») (s : Snapshot) (hF : FieldGood F) (hs : Synchronized F o s)
    (h : F.«放蓝图» o ps = some (G,es)) : Feasible s es := by
  unfold «场地».«放蓝图» at h
  split at h
  · cases h
  · exact fold_geometry_feasible (fun F p => F.«建» o p) o
      (fun F G p es s hF hs hb => ⟨fieldGood_place F G o p es hF hb,
        sync_place F G o p es s hF hs hb,feasible_place F G o p es s hF hs hb⟩)
      ps F G [] es s hF hs True.intro h

private theorem feasible_rebuild (F : «场地») (o : «接通先后») (ps : List «摆件»)
    (es : «历史») (h : F.«重建» o ps = some es) : Feasible ([],[]) es := by
  unfold «场地».«重建» at h
  split at h
  · cases h
  · simp only [Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at h
    obtain ⟨⟨G,fs⟩,hg,rfl⟩ := h
    exact fold_geometry_feasible (fun F p => F.«建成» o p) o
      (fun F G p es s hF hs hb => ⟨fieldGood_build F G o p es hF hb,
        sync_build F G o p es s hs hb,feasible_build F G o p es s hF hs hb⟩)
      ps [] G [] fs ([],[]) ⟨by simp,by simp⟩ (sync_empty o) True.intro hg

private theorem feasible_prefix (s : Snapshot) (H : «历史») (h : Feasible s H)
    (i : Nat) (e : «事件») (he : H[i]? = some e) : allowed (replay s (H.take i)) e = true := by
  induction H generalizing s i with
  | nil => simp at he
  | cons a H ih =>
    cases i with
    | zero => simp only [List.getElem?_cons_zero,Option.some.injEq] at he; subst a; exact h.1
    | succ i =>
      simp only [List.getElem?_cons_succ] at he
      exact ih _ h.2 i he

private theorem feasible_regular (H : «历史») (h : Feasible ([],[]) H) : H.«合规» = true := by
  apply («历史».«合规_iff» H).mpr
  intro i e he
  have hp := feasible_prefix ([],[]) H h i e he
  have hsame : snapshot (H.«布局于» i) = replay ([],[]) (H.take i) := by
    simpa only [«历史».«布局于»,List.take_length] using history_snapshot (H.take i)
  rw [← hsame,allowed_snapshot] at hp
  exact hp

/-- 工具：满足几何不相交条件的场地没有重复摆件。 -/
theorem field_nodup (F : «场地») (hF : FieldGood F) : F.Nodup := by
  apply hF.2.imp
  intro p q hsep he
  subst q
  exact hsep.1 p.«号» (piece_own_id p) (piece_own_id p)

private theorem same_members_of_length {α : Type} (xs ys : List α) (hx : xs.Nodup)
    (hs : xs ⊆ ys) (hl : xs.length = ys.length) : ∀ x, x ∈ xs ↔ x ∈ ys := by
  intro x
  constructor
  · exact fun hx => hs hx
  · intro hy
    by_cases hm : x ∈ xs
    · exact hm
    · have hn : (x :: xs).Nodup := List.nodup_cons.mpr ⟨hm,hx⟩
      have hsub : x :: xs ⊆ ys := by
        intro y hmem
        rcases List.mem_cons.mp hmem with rfl | hmem
        · exact hy
        · exact hs hmem
      have hh := hn.length_le_of_subset hsub
      simp only [List.length_cons] at hh
      omega

private theorem rebuild_perm (F : «场地») (o : «接通先后») (ps : List «摆件»)
    (H : «历史») (hF : FieldGood F) (h : F.«重建» o ps = some H) : ps.Perm F := by
  have hp := fieldGood_rebuild F o ps H h
  unfold «场地».«重建» at h
  split at h
  · cases h
  next hcheck =>
    have hc : ps.length = F.length ∧ ∀ p ∈ ps, p ∈ F := by simpa using hcheck
    apply (List.perm_ext_iff_of_nodup (field_nodup ps hp) (field_nodup F hF)).mpr
    exact same_members_of_length ps F (field_nodup ps hp) (fun _ hm => hc.2 _ hm) hc.1

private theorem regular_append (H : «历史») (e : «事件»)
    (hH : H.«合规» = true)
    (he : (H.«布局于» H.length).«容得下» e = true) :
    (H ++ [e]).«合规» = true := by
  apply («历史».«合规_iff» _).mpr
  intro t a ha
  have ht : t < (H ++ [e]).length := (List.getElem?_eq_some_iff.mp ha).1
  have hprefix : ∀ n, n ≤ H.length → (H ++ [e]).«布局于» n = H.«布局于» n := by
    intro n hn
    simp [«历史».«布局于», List.take_append, Nat.sub_eq_zero_of_le hn]
  by_cases hlt : t < H.length
  · rw [hprefix t (by omega)]
    exact («历史».«合规_iff» H).mp hH t a
      (by simpa only [List.getElem?_append_left hlt] using ha)
  · have ht' : t = H.length := by simp only [List.length_append, List.length_singleton] at ht; omega
    subst t
    have hae : a = e := by simpa using ha.symm
    subst a
    rw [hprefix H.length (by omega)]
    exact he

private theorem model_regular (un : «未定») (todo : «待写»)
    (s s' : «状态») (o : «操作») (hs : s.«历史».«合规» = true)
    (h : «作用» un todo s o = some s') : s'.«历史».«合规» = true := by
  have hd : o.«做得了» s = true := by
    rw [← «做得了才有结果» un todo s o, h]
    rfl
  cases o with
  | «改布局» e =>
    have hh : s'.«历史» = s.«历史» ++ [e] := by
      cases e <;> simp [«作用», hd] at h <;> cases h <;> rfl
    rw [hh]
    exact regular_append _ _ hs hd
  | «离线» H =>
    have hh : s'.«历史» = H := by
      simp [«作用», hd] at h
      cases h
      rfl
    rw [hh]
    simp only [«操作».«做得了», Bool.and_eq_true] at hd
    exact hd.1.1.1.1
  | _ =>
    rw [«只有改布局和离线改历史» un todo s s' _ h (by intros; simp) (by intros; simp)]
    exact hs


private theorem offline_allowed (un : «未定») (o : «接通先后») (bad : «通道» → Nat)
    (f : «格子».«状态») (hf : «命题».«格子可达» un o bad f)
    (ps : List «摆件») (H : «历史») (h : f.«场地».«重建» o ps = some H) :
    («操作».«离线» H).«做得了» f.«模型» = true := by
  have hF := reachable_fieldGood un o bad f hf
  have hs := reachable_sync un o bad f hf
  have hH : H.«合规» = true := feasible_regular H (feasible_rebuild f.«场地» o ps H h)
  have hsync : Synchronized ps o (snapshot (H.«布局于» H.length)) := by
    rw [history_snapshot]
    exact sync_rebuild f.«场地» o ps H h
  have hperm := rebuild_perm f.«场地» o ps H hF h
  have hunits : (H.«布局于» H.length).«单位表».Perm f.«模型».«布局».«单位表» := by
    rw [show (H.«布局于» H.length).«单位表» = ps.flatMap «摆件».«单位» from hsync.1,
      show f.«模型».«布局».«单位表» = f.«场地».flatMap «摆件».«单位» from hs.1]
    exact List.Perm.flatMap_right «摆件».«单位» hperm
  have hreg : f.«模型».«历史».«合规» = true :=
    «格子层的历史合规» model_regular un o bad f hf
  have hnnew := («历史».«合规则整齐» H hH H.length).«通道不重»
  have hnold := («历史».«合规则整齐» f.«模型».«历史» hreg f.«模型».«历史».length).«通道不重»
  have hchan : ((H.«布局于» H.length).«通道表».map Prod.fst).Perm
      (f.«模型».«布局».«通道表».map Prod.fst) := by
    apply (List.perm_ext_iff_of_nodup hnnew hnold).mpr
    intro c
    change c ∈ (snapshot (H.«布局于» H.length)).2 ↔ c ∈ (snapshot f.«模型».«布局»).2
    rw [hsync.2.2,hs.2.2]
    simp only [Geometry,hperm.mem_iff]
  simp only [«操作».«做得了»,Bool.and_eq_true,beq_iff_eq,List.all_eq_true,
    List.contains_iff_mem,List.any_eq_true]
  refine ⟨⟨⟨⟨hH,hunits.length_eq⟩,?_⟩,?_⟩,?_⟩
  · intro uk huk
    exact hunits.symm.subset huk
  · simpa only [List.length_map] using hchan.length_eq
  · intro ct hct
    have hm : ct.1 ∈ (H.«布局于» H.length).«通道表».map Prod.fst :=
      hchan.symm.subset (List.mem_map.mpr ⟨ct,hct,rfl⟩)
    obtain ⟨d,hd,he⟩ := List.mem_map.mp hm
    exact ⟨d,hd,by simpa using he⟩

/-- 据：通道、接通、蓝图

可达场地上，几何层能生成事件的操作，里层都能完整执行；没有几何结果的操作返回空。 -/
theorem «格子层做得了才有结果» : «命题».«格子层做得了才有结果» := by
  intro un o bad f a hf
  have hF := reachable_fieldGood un o bad f hf
  have hs := reachable_sync un o bad f hf
  cases a with
  | «建» p =>
    cases hr : f.«场地».«建» o p with
    | none => simp [«格子».«作用»,«命题».«格子做得了»,hr]
    | some r =>
      obtain ⟨G,es⟩ := r
      obtain ⟨t,ht⟩ := feasible_execute un (G.«待写» o bad) f.«模型» es
        (feasible_place f.«场地» G o p es _ hF hs hr)
      simp [«格子».«作用»,«命题».«格子做得了»,hr,ht]
  | «收» u =>
    cases hr : f.«场地».«收» u with
    | none => simp [«格子».«作用»,«命题».«格子做得了»,hr]
    | some r =>
      obtain ⟨G,es⟩ := r
      obtain ⟨t,ht⟩ := feasible_execute un (G.«待写» o bad) f.«模型» es
        (feasible_remove f.«场地» G o u es _ hs hr)
      simp [«格子».«作用»,«命题».«格子做得了»,hr,ht]
  | «蓝图» ps =>
    cases hr : f.«场地».«放蓝图» o ps with
    | none => simp [«格子».«作用»,«命题».«格子做得了»,hr]
    | some r =>
      obtain ⟨G,es⟩ := r
      obtain ⟨t,ht⟩ := feasible_execute un (G.«待写» o bad) f.«模型» es
        (feasible_blueprint f.«场地» G o ps es _ hF hs hr)
      simp [«格子».«作用»,«命题».«格子做得了»,hr,ht]
  | «离线» ps =>
    cases hr : f.«场地».«重建» o ps with
    | none => simp [«格子».«作用»,«命题».«格子做得了»,hr]
    | some H =>
      have hd := offline_allowed un o bad f hf ps H hr
      have hsome : («作用» un («场地».«待写» ps o bad) f.«模型» (.«离线» H)).isSome = true := by
        rw [«做得了才有结果»]; exact hd
      cases ht : «作用» un («场地».«待写» ps o bad) f.«模型» (.«离线» H) <;>
        simp_all [«格子».«作用»,«命题».«格子做得了»]
  | «原样» b =>
    have hsome := «做得了才有结果» un (f.«场地».«待写» o bad) f.«模型» b.«模型操作»
    cases ht : «作用» un (f.«场地».«待写» o bad) f.«模型» b.«模型操作» <;>
      simp_all [«格子».«作用»,«命题».«格子做得了»]

end Endfield.«证明»
