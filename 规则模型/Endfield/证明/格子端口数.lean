import Endfield.«证明».«基础»

/-!
证明格子层的历史端口数合。把端口列表还原为各摆件的边格枚举，
按单位和存取方向计数；占格互斥使每个端口至多对应一条通道。
事件前缀通过建造期间的通道子集、拆除期间的通道递减处理。
-/

namespace Endfield.«证明»

open «格子»

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
  | .«桥接器» =>
    let ds := «朝向».«各边».map fun d => (d, 0)
    («排端口» (fun d _ => o.«桥接器存货» d) ds).map (fun (d,n) => (false,d,n)) ++
      («排端口» (fun d _ => o.«桥接器取货» d) ds).map (fun (d,n) => (true,d,n))
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

private theorem «造端口性质» (p : «摆件») (b : Bool) (d : «朝向») (n : Nat)
    (a : «端口») (h : p.«造端口» b d n = some a) :
    a.«单位» = (if p.«种类» == .«桥接器» then
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

private theorem «端口单位属于摆件» (p : «摆件») (o : «接通先后»)
    (ps : List «端口») (hp : p.«端口» o = some ps)
    (a : «端口») (ha : a ∈ ps) : a.«单位» ∈ p.«单位».map Prod.fst := by
  obtain ⟨b,d,n,hs⟩ := «端口来自造端口» p o ps hp a ha
  have hu := («造端口性质» p b d n a hs).1
  cases hk : p.«种类» <;>
    simp [«摆件».«单位», hk, hu, «朝向».«各边»]
  case «桥接器» => cases b <;> cases d <;> simp [«朝向».«编号», «朝向».«对边», «朝向».«顺时针»]
  case «供电桩» =>
    have hh := («端口展开成功» p o ps hp).2
    simp [«端口样式», hk] at hh
    subst ps
    simp at ha

private def «样式标签» (p : «摆件») (v : Bool × «朝向» × Nat) : Nat × Bool :=
  (if p.«种类» == .«桥接器» then
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
    cases b <;> simp [«端口样式», «样式标签», hk, «单位种类».«存货端口数», «单位种类».«取货端口数»]
  case «分流器» d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> simp [«端口样式», «样式标签», hk, «单位种类».«存货端口数», «单位种类».«取货端口数»]
  case «汇流器» d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> simp [«端口样式», «样式标签», hk, «单位种类».«存货端口数», «单位种类».«取货端口数»]
  case «物品准入口» d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> simp [«端口样式», «样式标签», hk, «单位种类».«存货端口数», «单位种类».«取货端口数»]
  case «桥接器» =>
    obtain ⟨d, _, rfl, rfl⟩ := hu
    simp only [«端口样式», hk, List.map_append, List.map_map, List.filter_append,
      List.length_append, «排端口映射筛长度»]
    cases b <;> cases d <;>
      simp [«样式标签», hk, «朝向».«各边», «朝向».«编号», «朝向».«对边», «朝向».«顺时针»,
        «单位种类».«存货端口数», «单位种类».«取货端口数»]
  case «协议储存箱» d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> cases d <;>
      simp [«端口样式», «样式标签», hk, «摆件».«大小», «同边先后»,
        «单位种类».«存货端口数», «单位种类».«取货端口数», List.filter_map, List.map_map, Function.comp_def, «标签相等», «筛常数»]
  case «制造» mk d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> cases d <;> cases mk <;>
      simp [«端口样式», «样式标签», hk, «摆件».«大小», «制造大小», «同边先后»,
        «单位种类».«存货端口数», «单位种类».«取货端口数», «制造单位».«端口边长», List.filter_map, List.map_map, Function.comp_def, «标签相等», «筛常数»]
  case «协议核心» a =>
    obtain ⟨rfl,rfl⟩ := hu
    simp only [«端口样式», hk, List.map_append, List.map_map, List.filter_append,
      List.length_append, «排端口映射筛长度»]
    cases b <;> cases a <;>
      simp [«样式标签», hk, «核心边格», «朝向».«各边», «平行边».«包含»,
        «单位种类».«存货端口数», «单位种类».«取货端口数», List.filter_map, List.map_map, Function.comp_def, «标签相等», «筛常数»]
  case «仓库取货口» d =>
    obtain ⟨rfl,rfl⟩ := hu
    cases b <;> simp [«端口样式», «样式标签», hk, «单位种类».«存货端口数», «单位种类».«取货端口数»]

private theorem «每单位端口数» (p : «摆件») (o : «接通先后»)
    (ps : List «端口») (hp : p.«端口» o = some ps)
    (u : Nat) (k : «单位种类») (hu : (u,k) ∈ p.«单位») (b : Bool) :
    (ps.filter (fun a => a.«单位» == u && a.«取货» == b)).length =
      if b then k.«取货端口数» else k.«存货端口数» := by
  have hh := «样式标签计数» p o u k hu b
  rw [← «端口标签表» p o ps hp] at hh
  simpa [List.filter_map, Function.comp_def, «标签相等»] using hh

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

private theorem mapM_mem {α β : Type} (f : α → Option β) (xs : List α) (ys : List β)
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

private theorem mapM_has {α β : Type} (f : α → Option β) (xs : List α) (ys : List β)
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

private def FieldGood (F : «场地») : Prop :=
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

private theorem reachable_fieldGood (un : «未定») (o : «格子».«接通先后»)
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

open «格子» («端口» «接通先后» «朝向» «格» «同边先后» «排端口» «核心边格»)

private theorem «关系计数界» {α β : Type} (xs : List α) (ys : List β)
    (R : α → β → Prop) (hn : xs.Nodup)
    (he : ∀ x ∈ xs, ∃ y ∈ ys, R x y)
    (hi : ∀ x ∈ xs, ∀ x' ∈ xs, ∀ y ∈ ys, R x y → R x' y → x = x') :
    xs.length ≤ ys.length := by
  classical
  induction xs generalizing ys with
  | nil => simp
  | cons x xs ih =>
    obtain ⟨hnx, hns⟩ := List.nodup_cons.mp hn
    obtain ⟨y, hy, hr⟩ := he x (by simp)
    have hall : ∀ z ∈ xs, ∃ w ∈ ys.erase y, R z w := by
      intro z hz
      obtain ⟨w, hw, hzw⟩ := he z (by simp [hz])
      have hne : w ≠ y := by
        intro h; subst w
        have hxz := hi x (by simp) z (by simp [hz]) y hy hr hzw
        exact hnx (hxz ▸ hz)
      exact ⟨w, (List.mem_erase_of_ne hne).mpr hw, hzw⟩
    have hlen := ih (ys.erase y) hns hall (by
      intro z hz z' hz' w hw
      exact hi z (by simp [hz]) z' (by simp [hz']) w (List.mem_of_mem_erase hw))
    have hylen : 0 < ys.length := List.length_pos_of_mem hy
    rw [List.length_erase_of_mem hy] at hlen
    simp only [List.length_cons]
    omega

private theorem «单位号在占号里» (p : «摆件») (u : Nat)
    (hu : u ∈ p.«单位».map Prod.fst) : u ∈ p.«占号» := by
  cases hk : p.«种类» <;> simp [«摆件».«单位», hk, «摆件».«占号»] at * <;> try assumption
  case «桥接器» =>
    obtain ⟨d, _, rfl⟩ := hu
    cases d <;> simp [«朝向».«编号»]

private theorem «同号归属同摆件» (F : «场地») (hF : FieldGood F)
    (p q : «摆件») (hp : p ∈ F) (hq : q ∈ F) (u : Nat)
    (hu : u ∈ p.«占号») (hv : u ∈ q.«占号») : p = q := by
  by_cases hn : p = q
  · exact hn
  · exact False.elim ((pairwise_of_mem (fun _ _ => separate_symm) hF.2 p q hp hq hn).1 u hu hv)

private theorem «同格端口同单位» (F : «场地») (o : «接通先后») (hF : FieldGood F)
    (p q : «摆件») (hp : p ∈ F) (hq : q ∈ F)
    (ps qs : List «端口») (hps : p.«端口» o = some ps) (hqs : q.«端口» o = some qs)
    (a b : «端口») (ha : a ∈ ps) (hb : b ∈ qs)
    (hc : a.«格» = b.«格») (hd : a.«边» = b.«边») (ht : a.«取货» = b.«取货») :
    a.«单位» = b.«单位» := by
  have he : p = q := by
    by_cases hn : p = q
    · exact hn
    apply False.elim
    obtain ⟨cs,hcs⟩ := hF.1 p hp
    obtain ⟨ds,hds⟩ := hF.1 q hq
    have ha' := «端口格在占格里» p o ps cs hps hcs a ha
    have hb' := «端口格在占格里» q o qs ds hqs hds b hb
    exact (pairwise_of_mem (fun _ _ => separate_symm) hF.2 p q hp hq hn).2.1
      cs ds hcs hds a.«格» ha' (hc ▸ hb')
  subst q
  have he : ps = qs := Option.some.inj (hps.symm.trans hqs)
  subst qs
  exact «端口同边同类同单位» p o ps hps a b ha hb hd ht

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

private theorem «正对性质» (a b : «端口») (h : a.«正对紧贴» b = true) :
    a.«取货» = true ∧ b.«取货» = false ∧ a.«边».«对边» = b.«边» ∧
      a.«格».«邻格» a.«边» = some b.«格» := by
  simp only [«端口».«正对紧贴», Bool.and_eq_true, Bool.not_eq_true', beq_iff_eq,
    bne_iff_ne] at h
  exact ⟨h.1.1.1.1, h.1.1.1.2, h.1.2, h.2⟩

private def «端口对应通道» (F : «场地») (o : «接通先后»)
    (out : Bool) (a : «端口») (c : «通道») : Prop :=
  ∃ q ∈ F, ∃ qs, q.«端口» o = some qs ∧ ∃ z ∈ qs,
    if out then a.«正对紧贴» z = true ∧ c = ⟨a.«单位», z.«单位»⟩
    else z.«正对紧贴» a = true ∧ c = ⟨z.«单位», a.«单位»⟩

private def «通道来自场地» (F : «场地») (o : «接通先后») (c : «通道») : Prop :=
  ∃ p ∈ F, ∃ ps, p.«端口» o = some ps ∧ ∃ a ∈ ps, «端口对应通道» F o true a c

private theorem «同端口通道唯一» (F : «场地») (o : «接通先后») (hF : FieldGood F)
    (out : Bool) (a : «端口») (c d : «通道»)
    (hc : «端口对应通道» F o out a c) (hd : «端口对应通道» F o out a d) : c = d := by
  obtain ⟨p,hp,ps,hps,b,hb,hc⟩ := hc
  obtain ⟨q,hq,qs,hqs,z,hz,hd⟩ := hd
  cases out <;> simp only [Bool.false_eq_true, ↓reduceIte] at hc hd
  · obtain ⟨hc,rfl⟩ := hc
    obtain ⟨hd,rfl⟩ := hd
    have hbc := «正对性质» b a hc
    have hzc := «正对性质» z a hd
    have he : b.«边» = z.«边» := by
      have := congrArg «朝向».«对边» (hbc.2.2.1.trans hzc.2.2.1.symm)
      simpa only [«对边再对边»] using this
    have hc : b.«格» = z.«格» := by
      have h1 := «邻格反向» b.«格» a.«格» b.«边» hbc.2.2.2
      have h2 := «邻格反向» z.«格» a.«格» z.«边» hzc.2.2.2
      rw [he] at h1
      exact Option.some.inj (h1.symm.trans h2)
    have hu := «同格端口同单位» F o hF p q hp hq ps qs hps hqs b z hb hz hc he
      (hbc.1.trans hzc.1.symm)
    rw [hu]
  · obtain ⟨hc,rfl⟩ := hc
    obtain ⟨hd,rfl⟩ := hd
    have hbc := «正对性质» a b hc
    have hzc := «正对性质» a z hd
    have hc : b.«格» = z.«格» := Option.some.inj (hbc.2.2.2.symm.trans hzc.2.2.2)
    have he : b.«边» = z.«边» := hbc.2.2.1.symm.trans hzc.2.2.1
    have hu := «同格端口同单位» F o hF p q hp hq ps qs hps hqs b z hb hz hc he
      (hbc.2.1.trans hzc.2.1.symm)
    rw [hu]

private theorem «通道端点有端口» (F : «场地») (o : «接通先后»)
    (hF : FieldGood F) (p : «摆件») (hp : p ∈ F) (ps : List «端口»)
    (hps : p.«端口» o = some ps) (u : Nat) (hu : u ∈ p.«占号»)
    (out : Bool) (c : «通道») (hc : «通道来自场地» F o c)
    (he : (if out then c.«起» else c.«止») = u) :
    ∃ a ∈ ps, a.«单位» = u ∧ a.«取货» = out ∧ «端口对应通道» F o out a c := by
  obtain ⟨q,hq,qs,hqs,a,ha,r,hr,rs,hrs,b,hb,hc,rfl⟩ := hc
  have hrel := «正对性质» a b hc
  cases out <;> simp only [Bool.false_eq_true, ↓reduceIte] at he ⊢
  · have hbu : b.«单位» ∈ r.«占号» := «单位号在占号里» r _ («端口单位属于摆件» r o rs hrs b hb)
    have hrp : r = p := «同号归属同摆件» F hF r p hr hp u (he ▸ hbu) hu
    subst r
    have hlist : rs = ps := Option.some.inj (hrs.symm.trans hps)
    subst rs
    refine ⟨b,hb,he,hrel.2.1,?_⟩
    exact ⟨q,hq,qs,hqs,a,ha,hc,rfl⟩
  · have hau : a.«单位» ∈ q.«占号» := «单位号在占号里» q _ («端口单位属于摆件» q o qs hqs a ha)
    have hqp : q = p := «同号归属同摆件» F hF q p hq hp u (he ▸ hau) hu
    subst q
    have hlist : qs = ps := Option.some.inj (hqs.symm.trans hps)
    subst qs
    refine ⟨a,ha,he,hrel.1,?_⟩
    exact ⟨r,hr,rs,hrs,b,hb,hc,rfl⟩

private theorem «几何通道计数界» (F : «场地») (o : «接通先后»)
    (hF : FieldGood F) (p : «摆件») (hp : p ∈ F) (ps : List «端口»)
    (hps : p.«端口» o = some ps) (u : Nat) (k : «单位种类»)
    (hu : (u,k) ∈ p.«单位») (out : Bool) (cs : List «通道»)
    (hn : cs.Nodup)
    (hc : ∀ c ∈ cs, «通道来自场地» F o c ∧ (if out then c.«起» else c.«止») = u) :
    cs.length ≤ if out then k.«取货端口数» else k.«存货端口数» := by
  rw [← «每单位端口数» p o ps hps u k hu out]
  apply «关系计数界» cs _ (fun c a => «端口对应通道» F o out a c) hn
  · intro c hmem
    have hown : u ∈ p.«占号» := «单位号在占号里» p u (List.mem_map.mpr ⟨(u,k),hu,rfl⟩)
    obtain ⟨a,ha,hau,hab,hca⟩ := «通道端点有端口» F o hF p hp ps hps u hown out c
      (hc c hmem).1 (hc c hmem).2
    exact ⟨a,List.mem_filter.mpr ⟨ha,by simp [hau,hab]⟩,hca⟩
  · intro c _ d _ a _ hc hd
    exact «同端口通道唯一» F o hF out a c d hc hd

private theorem «形成通道来自两端口» (F : «场地») (o : «接通先后»)
    (p q : «摆件») (hp : p ∈ F) (hq : q ∈ F)
    (ps qs : List «端口») (hps : p.«端口» o = some ps) (hqs : q.«端口» o = some qs)
    (a b : «端口») (ha : a ∈ ps) (hb : b ∈ qs) (c : «通道»)
    (hc : «形成通道» p q a b = some c) : «通道来自场地» F o c := by
  unfold «形成通道» at hc
  split at hc
  · contradiction
  · split at hc
    next h =>
      cases hc
      exact ⟨p,hp,ps,hps,a,ha,q,hq,qs,hqs,b,hb,h,rfl⟩
    next =>
      split at hc
      next h =>
        cases hc
        exact ⟨q,hq,qs,hqs,b,hb,p,hp,ps,hps,a,ha,h,rfl⟩
      next => contradiction

private theorem «该有通道来自场地» (F : «场地») (o : «接通先后»)
    (cs : List «通道») (hc : «命题».«场地该有的通道» F o = some cs)
    (c : «通道») (hm : c ∈ cs) : «通道来自场地» F o c := by
  simp only [«命题».«场地该有的通道», bind, Option.bind_eq_some_iff, pure,
    Option.some.injEq] at hc
  obtain ⟨rows, hr, rfl⟩ := hc
  simp only [List.mem_flatMap, List.mem_filter, List.mem_filterMap] at hm
  obtain ⟨⟨p,ps⟩,hp,a,⟨ha,_⟩,⟨q,qs⟩,hq,b,hb,hc⟩ := hm
  obtain ⟨p',hp',he⟩ := «mapM成员» _ _ hr hp
  simp only [Option.bind_eq_some_iff, Option.some.injEq, Prod.mk.injEq] at he
  obtain ⟨ps',hps,rfl,rfl⟩ := he
  obtain ⟨q',hq',he⟩ := «mapM成员» _ _ hr hq
  simp only [Option.bind_eq_some_iff, Option.some.injEq, Prod.mk.injEq] at he
  obtain ⟨qs',hqs,rfl,rfl⟩ := he
  exact «形成通道来自两端口» F o p' q' hp' hq' ps' qs' hps hqs a b ha hb c hc

private def «布局来自场地» (F : «场地») (o : «接通先后») (L : «布局») : Prop :=
  (∀ uk ∈ L.«单位表», ∃ p ∈ F, uk ∈ p.«单位») ∧
  (∀ ct ∈ L.«通道表», «通道来自场地» F o ct.1)

private def «场地有端口» (F : «场地») (o : «接通先后») : Prop :=
  ∀ p ∈ F, ∃ ps, p.«端口» o = some ps

private theorem «几何布局端口数合» (F : «场地») (o : «接通先后»)
    (hF : FieldGood F) (hports : «场地有端口» F o) (L : «布局»)
    (hn : (L.«通道表».map Prod.fst).Nodup) (hL : «布局来自场地» F o L) :
    L.«端口数合» = true := by
  apply List.all_eq_true.mpr
  intro uk huk
  obtain ⟨p,hp,hu⟩ := hL.1 uk huk
  obtain ⟨ps,hps⟩ := hports p hp
  have hc (out : Bool) :
      ((L.«通道表».filter (fun ct => (if out then ct.1.«起» else ct.1.«止») == uk.1)).map Prod.fst).length ≤
      if out then uk.2.«取货端口数» else uk.2.«存货端口数» := by
    apply «几何通道计数界» F o hF p hp ps hps uk.1 uk.2 hu out
    · exact hn.sublist (List.filter_sublist.map Prod.fst)
    · intro c hc
      obtain ⟨ct,hct,rfl⟩ := List.mem_map.mp hc
      obtain ⟨hm,he⟩ := List.mem_filter.mp hct
      exact ⟨hL.2 ct hm, by simpa using he⟩
  simp only [Bool.and_eq_true, decide_eq_true_eq]
  exact ⟨by simpa [«布局».«进»] using hc false, by simpa [«布局».«出»] using hc true⟩

private theorem «该有通道保证有端口» (F : «场地») (o : «接通先后»)
    (cs : List «通道») (hc : «命题».«场地该有的通道» F o = some cs) : «场地有端口» F o := by
  simp only [«命题».«场地该有的通道», bind, Option.bind_eq_some_iff] at hc
  obtain ⟨rows,hr,_⟩ := hc
  intro p hp
  obtain ⟨⟨q,qs⟩,hq⟩ := mapM_has _ _ _ hr p hp
  simp only [Option.bind_eq_some_iff] at hq
  obtain ⟨ps,hps,_⟩ := hq
  exact ⟨ps,hps⟩

private theorem «可达布局端口数合» («h同步» : «命题».«格子层的单位和通道»)
    («h合规» : «命题».«格子层的历史合规»)
    (un : «未定») (o : «接通先后») (bad : «通道» → Nat)
    (f : «格子».«状态») (hf : «命题».«格子可达» un o bad f) :
    f.«模型».«布局».«端口数合» = true := by
  obtain ⟨hu,cs,hcs,hmem⟩ := «h同步» un o bad f hf
  apply «几何布局端口数合» f.«场地» o (reachable_fieldGood un o bad f hf)
    («该有通道保证有端口» _ _ cs hcs) f.«模型».«布局»
    ((«历史».«合规则整齐» _ («h合规» un o bad f hf) _).«通道不重»)
  constructor
  · intro uk huk
    rw [hu] at huk
    exact List.mem_flatMap.mp huk
  · intro ct hct
    exact «该有通道来自场地» _ _ cs hcs ct.1 ((hmem ct.1).mpr (List.mem_map.mpr ⟨ct,hct,rfl⟩))

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

private theorem rows_mem (F : «场地») (o : «接通先后»)
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
  cases hk : p.«种类» <;> simp [«摆件».«单位», «摆件».«占号», hk, «朝向».«各边»,
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

private def Capacity (s : Snapshot) : Prop :=
  ∀ uk ∈ s.1, (s.2.filter (fun c => c.«止» == uk.1)).length ≤ uk.2.«存货端口数» ∧
    (s.2.filter (fun c => c.«起» == uk.1)).length ≤ uk.2.«取货端口数»

private theorem capacity_snapshot (L : «布局») :
    Capacity (snapshot L) ↔ L.«端口数合» = true := by
  constructor
  · intro h
    apply List.all_eq_true.mpr
    intro uk huk
    apply Bool.and_eq_true_iff.mpr
    have hh := h uk huk
    constructor
    · apply decide_eq_true
      simpa only [snapshot, «布局».«进», List.filter_map, List.length_map, Function.comp_def] using hh.1
    · apply decide_eq_true
      simpa only [snapshot, «布局».«出», List.filter_map, List.length_map, Function.comp_def] using hh.2
  · intro h uk huk
    have hh := Bool.and_eq_true_iff.mp (List.all_eq_true.mp h uk huk)
    constructor
    · have hh := of_decide_eq_true hh.1
      simpa only [snapshot, «布局».«进», List.filter_map, List.length_map, Function.comp_def] using hh
    · have hh := of_decide_eq_true hh.2
      simpa only [snapshot, «布局».«出», List.filter_map, List.length_map, Function.comp_def] using hh

private theorem capacity_synced (F : «场地») (o : «接通先后») (s : Snapshot)
    (hF : FieldGood F) (hs : Synchronized F o s) (hn : s.2.Nodup) : Capacity s := by
  intro uk huk
  obtain ⟨p,hp,hu⟩ := List.mem_flatMap.mp (hs.1 ▸ huk)
  obtain ⟨ps,hps⟩ := hs.2.1 p hp
  have bound (out : Bool) :
      (s.2.filter (fun c => (if out then c.«起» else c.«止») == uk.1)).length ≤
        if out then uk.2.«取货端口数» else uk.2.«存货端口数» := by
    apply «几何通道计数界» F o hF p hp ps hps uk.1 uk.2 hu out
    · exact hn.sublist List.filter_sublist
    · intro c hc
      obtain ⟨hm,he⟩ := List.mem_filter.mp hc
      obtain ⟨p,hp,q,hq,ps,qs,hps,hqs,a,ha,b,hb,hform⟩ := (hs.2.2 c).mp hm
      exact ⟨«形成通道来自两端口» F o p q hp hq ps qs hps hqs a b ha hb c hform,
        by simpa using he⟩
  exact ⟨bound false, bound true⟩

private def SnapshotSub (s t : Snapshot) : Prop := s.1 ⊆ t.1 ∧ s.2.Sublist t.2

private theorem sub_refl (s : Snapshot) : SnapshotSub s s := ⟨List.Subset.refl _, .refl _⟩

private theorem sub_trans {s t u : Snapshot} (h : SnapshotSub s t) (h' : SnapshotSub t u) :
    SnapshotSub s u := ⟨fun _ hm => h'.1 (h.1 hm), h.2.trans h'.2⟩

private theorem capacity_sub {s t : Snapshot} (h : SnapshotSub s t) (ht : Capacity t) : Capacity s := by
  intro uk huk
  have hh := ht uk (h.1 huk)
  exact ⟨Nat.le_trans (h.2.filter _).length_le hh.1, Nat.le_trans (h.2.filter _).length_le hh.2⟩

private def AddOnly : «事件» → Prop
  | .«拆除» _ => False
  | _ => True

private def RemoveOnly : «事件» → Prop
  | .«拆除» _ => True
  | _ => False

private theorem add_extends (s : Snapshot) (e : «事件») (h : AddOnly e) :
    SnapshotSub s (addSnapshot s e) := by
  cases e with
  | «建成» u k => exact ⟨by intro uk hm; simp [addSnapshot,hm], .refl _⟩
  | «接通» c => exact ⟨List.Subset.refl _, by simp [addSnapshot]⟩
  | «拆除» u => cases h

private theorem remove_shrinks (s : Snapshot) (e : «事件») (h : RemoveOnly e) :
    SnapshotSub (addSnapshot s e) s := by
  cases e with
  | «建成» u k => cases h
  | «接通» c => cases h
  | «拆除» u => exact ⟨List.filter_sublist.subset, List.filter_sublist⟩

private theorem replay_extends (s : Snapshot) (es : «历史»)
    (h : ∀ e ∈ es, AddOnly e) : SnapshotSub s (replay s es) := by
  induction es generalizing s with
  | nil => exact sub_refl s
  | cons e es ih =>
    exact sub_trans (add_extends s e (h e (by simp)))
      (ih _ (fun e he => h e (by simp [he])))

private def Walk (P : Snapshot → Prop) (s : Snapshot) : «历史» → Prop
  | [] => P s
  | e :: es => P s ∧ Walk P (addSnapshot s e) es

private theorem walk_first {P : Snapshot → Prop} {s : Snapshot} {es : «历史»}
    (h : Walk P s es) : P s := by
  cases es with
  | nil => exact h
  | cons => exact h.1

private theorem walk_last {P : Snapshot → Prop} {s : Snapshot} {es : «历史»}
    (h : Walk P s es) : P (replay s es) := by
  induction es generalizing s with
  | nil => exact h
  | cons e es ih => exact ih h.2

private theorem walk_append (P : Snapshot → Prop) (s : Snapshot) (es fs : «历史») :
    Walk P s (es ++ fs) ↔ Walk P s es ∧ Walk P (replay s es) fs := by
  induction es generalizing s with
  | nil =>
    simp only [List.nil_append, Walk, replay, List.foldl_nil]
    exact ⟨fun h => ⟨walk_first h,h⟩, fun h => h.2⟩
  | cons e es ih =>
    change (P s ∧ Walk P (addSnapshot s e) (es ++ fs)) ↔
      (P s ∧ Walk P (addSnapshot s e) es) ∧ Walk P (replay (addSnapshot s e) es) fs
    rw [ih]
    exact and_assoc.symm

private theorem walk_add (s : Snapshot) (es : «历史»)
    (h : ∀ e ∈ es, AddOnly e) (hc : Capacity (replay s es)) : Walk Capacity s es := by
  induction es generalizing s with
  | nil => exact hc
  | cons e es ih =>
    exact ⟨capacity_sub (replay_extends s (e :: es) h) hc,
      ih _ (fun e he => h e (by simp [he])) hc⟩

private theorem walk_remove (s : Snapshot) (es : «历史»)
    (h : ∀ e ∈ es, RemoveOnly e) (hc : Capacity s) : Walk Capacity s es := by
  induction es generalizing s with
  | nil => exact hc
  | cons e es ih =>
    exact ⟨hc,ih _ (fun e he => h e (by simp [he]))
      (capacity_sub (remove_shrinks s e (h e (by simp))) hc)⟩

private theorem walk_build (F G : «场地») (o : «接通先后») (p : «摆件»)
    (es : «历史») (s : Snapshot) (hF : FieldGood F) (hs : Synchronized F o s)
    (hn : Walk (fun t => t.2.Nodup) s es)
    (h : F.«建成» o p = some (G,es)) : Walk Capacity s es := by
  have hend := capacity_synced G o _ (fieldGood_build F G o p es hF h)
    (sync_build F G o p es s hs h) (walk_last hn)
  apply walk_add s es _ hend
  unfold «场地».«建成» at h
  split at h
  · contradiction
  · simp only [Option.bind_eq_bind, Option.bind_eq_some_iff, Option.pure_def,
      Option.some.injEq, Prod.mk.injEq] at h
    obtain ⟨cs,hcs,_,rfl⟩ := h
    intro e he
    rcases List.mem_append.mp he with he | he
    · obtain ⟨⟨u,k⟩,_,rfl⟩ := List.mem_map.mp he
      trivial
    · obtain ⟨c,rfl,_⟩ := ((connections_spec F o p cs hcs).2 e).mp he
      trivial

private theorem walk_collect (F G : «场地») (u : Nat) (es : «历史»)
    (s : Snapshot) (hc : Capacity s) (h : F.«收» u = some (G,es)) : Walk Capacity s es := by
  apply walk_remove s es _ hc
  unfold «场地».«收» at h
  split at h
  · cases h
    intro e he
    obtain ⟨⟨v,k⟩,_,rfl⟩ := List.mem_map.mp he
    trivial
  · contradiction

private theorem walk_place (F G : «场地») (o : «接通先后») (p : «摆件»)
    (es : «历史») (s : Snapshot) (hF : FieldGood F) (hs : Synchronized F o s)
    (hc : Capacity s) (hn : Walk (fun t => t.2.Nodup) s es)
    (h : F.«建» o p = some (G,es)) : Walk Capacity s es := by
  cases hk : p.«种类» <;> simp only [«场地».«建», hk] at h
  case «物品准入口» d =>
    split at h
    · simp only [Option.bind_eq_bind, Option.bind_eq_some_iff,
        Option.pure_def, Option.some.injEq, Prod.mk.injEq] at h
      obtain ⟨⟨F',es'⟩,hrem,⟨G',fs⟩,hb,hG,hE⟩ := h
      dsimp only at hG hE
      subst G' es
      rw [walk_append] at hn ⊢
      refine ⟨walk_collect F F' _ es' s hc hrem, ?_⟩
      exact walk_build F' G o p fs _ (fieldGood_remove F F' _ es' hF hrem)
        (sync_remove F F' o _ es' s hF hs hrem) hn.2 hb
    · contradiction
  all_goals exact walk_build F G o p es s hF hs hn h

private theorem fold_events_suffix (step : «场地» → «摆件» → Option («场地» × «历史»))
    (ps : List «摆件») (F G : «场地») (es fs : «历史»)
    (h : ps.foldlM (fun (F,es) p => do
      let (G,fs) ← step F p
      return (G,es ++ fs)) (F,es) = some (G,fs)) : ∃ rest, fs = es ++ rest := by
  induction ps generalizing F es with
  | nil => cases h; exact ⟨[], by simp⟩
  | cons p ps ih =>
    simp only [List.foldlM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at h
    obtain ⟨⟨F',es'⟩,⟨⟨G',hs⟩,_,he⟩,ht⟩ := h
    cases he
    obtain ⟨rest,hr⟩ := ih G' (es ++ hs) ht
    exact ⟨hs ++ rest, by simpa only [List.append_assoc] using hr⟩

private theorem fold_walk (step : «场地» → «摆件» → Option («场地» × «历史»))
    (o : «接通先后»)
    (hstep : ∀ F G p es s, FieldGood F → Synchronized F o s → Capacity s →
      Walk (fun t => t.2.Nodup) s es → step F p = some (G,es) →
      FieldGood G ∧ Synchronized G o (replay s es) ∧ Walk Capacity s es)
    (ps : List «摆件») (F G : «场地») (es fs : «历史») (s : Snapshot)
    (hF : FieldGood F) (hs : Synchronized F o (replay s es))
    (hc : Walk Capacity s es) (hn : Walk (fun t => t.2.Nodup) s fs)
    (h : ps.foldlM (fun (F,es) p => do
      let (G,fs) ← step F p
      return (G,es ++ fs)) (F,es) = some (G,fs)) : Walk Capacity s fs := by
  induction ps generalizing F es with
  | nil => cases h; exact hc
  | cons p ps ih =>
    simp only [List.foldlM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at h
    obtain ⟨⟨F',es'⟩,⟨⟨G',hs'⟩,hg,he⟩,ht⟩ := h
    cases he
    obtain ⟨rest,hr⟩ := fold_events_suffix step ps G' G (es ++ hs') fs ht
    have hnpre : Walk (fun t => t.2.Nodup) s (es ++ hs') := by
      rw [hr, walk_append] at hn
      exact hn.1
    have hnpart := ((walk_append _ s es hs').mp hnpre).2
    obtain ⟨hG,hS,hW⟩ := hstep F G' p hs' (replay s es) hF hs (walk_last hc) hnpart hg
    apply ih G' (es ++ hs') hG
    · simpa only [replay_append] using hS
    · exact (walk_append _ s es hs').mpr ⟨hc,hW⟩
    · exact ht

private theorem walk_blueprint (F G : «场地») (o : «接通先后») (ps : List «摆件»)
    (es : «历史») (s : Snapshot) (hF : FieldGood F) (hs : Synchronized F o s)
    (hc : Capacity s) (hn : Walk (fun t => t.2.Nodup) s es)
    (h : F.«放蓝图» o ps = some (G,es)) : Walk Capacity s es := by
  unfold «场地».«放蓝图» at h
  split at h
  · contradiction
  · exact fold_walk (fun F p => F.«建» o p) o
      (fun F G p es s hF hs hc hn hb => ⟨fieldGood_place F G o p es hF hb,
        sync_place F G o p es s hF hs hb, walk_place F G o p es s hF hs hc hn hb⟩)
      ps F G [] es s hF hs hc hn h

private theorem walk_rebuild (F : «场地») (o : «接通先后») (ps : List «摆件»)
    (es : «历史») (hn : Walk (fun t => t.2.Nodup) ([],[]) es)
    (h : F.«重建» o ps = some es) : Walk Capacity ([],[]) es := by
  unfold «场地».«重建» at h
  split at h
  · contradiction
  · simp only [Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at h
    obtain ⟨⟨G,fs⟩,hg,rfl⟩ := h
    exact fold_walk (fun F p => F.«建成» o p) o
      (fun F G p es s hF hs _ hn hb => ⟨fieldGood_build F G o p es hF hb,
        sync_build F G o p es s hs hb, walk_build F G o p es s hF hs hn hb⟩)
      ps [] G [] fs ([],[]) ⟨by simp,by simp⟩ (sync_empty o) (by simp [Walk,Capacity]) hn hg

private theorem walk_iff_prefix (P : Snapshot → Prop) (s : Snapshot) (es : «历史») :
    Walk P s es ↔ ∀ n, P (replay s (es.take n)) := by
  induction es generalizing s with
  | nil => simp [Walk,replay]
  | cons e es ih =>
    constructor
    · rintro ⟨h,ht⟩ n
      cases n with
      | zero => exact h
      | succ n => exact (ih _).mp ht n
    · intro h
      exact ⟨h 0, (ih _).mpr (fun n => h (n+1))⟩

private theorem history_prefix_snapshot (H : «历史») (t : Nat) :
    snapshot (H.«布局于» t) = replay ([],[]) (H.take t) := by
  have he : H.«布局于» t = «历史».«布局于» (H.take t) (H.take t).length := by
    simp only [«历史».«布局于», List.take_length]
  rw [he, history_snapshot]

private theorem regular_walk (H : «历史») (h : H.«合规» = true) :
    Walk (fun s => s.2.Nodup) ([],[]) H := by
  rw [walk_iff_prefix]
  intro n
  rw [← history_prefix_snapshot]
  exact («历史».«合规则整齐» H h n).«通道不重»

private theorem capacity_walk (H : «历史») :
    Walk Capacity ([],[]) H ↔ H.«端口数合» = true := by
  rw [walk_iff_prefix]
  constructor
  · intro h
    apply List.all_eq_true.mpr
    intro n _
    apply (capacity_snapshot _).mp
    rw [history_prefix_snapshot]
    exact h n
  · intro h n
    rw [← history_prefix_snapshot]
    exact (capacity_snapshot _).mpr («历史».«端口数合_任一刻» H h n)

private theorem execute_history (un : «未定») (todo : «待写») (s t : «状态»)
    (es : «历史») (h : «格子».«执行事件» un todo s es = some t) :
    t.«历史» = s.«历史» ++ es := by
  induction es generalizing s with
  | nil => cases h; simp
  | cons e es ih =>
    simp only [«格子».«执行事件», List.foldlM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff] at h
    obtain ⟨u,hu,ht⟩ := h
    have hd : («操作».«改布局» e).«做得了» s = true := by
      rw [← «做得了才有结果» un todo s (.«改布局» e),hu]; rfl
    have hh : u.«历史» = s.«历史» ++ [e] := by
      cases e <;> simp only [«作用»,hd,Bool.not_true,Bool.false_eq_true,↓reduceIte] at hu <;>
        cases hu <;> rfl
    rw [ih u ht,hh]
    simp [List.append_assoc]

private theorem grid_steps_append (un : «未定») (o : «接通先后») (bad : «通道» → Nat)
    (s : «格子».«状态») (as bs : List «格子».«操作») :
    «命题».«格子依次作用» un o bad s (as ++ bs) =
      («命题».«格子依次作用» un o bad s as).bind
        (fun t => «命题».«格子依次作用» un o bad t bs) := by
  induction as generalizing s with
  | nil => rfl
  | cons a as ih => simp only [List.cons_append, «命题».«格子依次作用», ih, Option.bind_assoc]

private theorem reachable_next (un : «未定») (o : «接通先后») (bad : «通道» → Nat)
    (s t : «格子».«状态») (a : «格子».«操作»)
    (hs : «命题».«格子可达» un o bad s) (he : «格子».«作用» un o bad s a = some t) :
    «命题».«格子可达» un o bad t := by
  obtain ⟨as,ha⟩ := hs
  refine ⟨as ++ [a], ?_⟩
  simp [grid_steps_append,ha,«命题».«格子依次作用»,he]

private theorem grid_step_capacity («h同步» : «命题».«格子层的单位和通道»)
    («h合规» : «命题».«格子层的历史合规»)
    (un : «未定») (o : «接通先后») (bad : «通道» → Nat)
    (s t : «格子».«状态») (a : «格子».«操作»)
    (hr : «命题».«格子可达» un o bad s)
    (hc : s.«模型».«历史».«端口数合» = true)
    (he : «格子».«作用» un o bad s a = some t) : t.«模型».«历史».«端口数合» = true := by
  have hregular := «h合规» un o bad t (reachable_next un o bad s t a hr he)
  have hF := reachable_fieldGood un o bad s hr
  have hsync := reachable_sync un o bad s hr
  have hcap := (capacity_snapshot s.«模型».«布局»).mpr
    («可达布局端口数合» «h同步» «h合规» un o bad s hr)
  cases a <;> simp only [«格子».«作用», Option.bind_eq_bind,
    Option.bind_eq_some_iff, Option.pure_def, Option.some.injEq] at he
  case «原样» b =>
    obtain ⟨u,hu,rfl⟩ := he
    have hh := «只有改布局和离线改历史» un _ _ _ _ hu
      (by cases b <;> intros <;> simp [«格子».«原样操作».«模型操作»])
      (by cases b <;> intros <;> simp [«格子».«原样操作».«模型操作»])
    simpa only [hh] using hc
  case «离线» ps =>
    obtain ⟨H,hH,u,hu,rfl⟩ := he
    have hd : («操作».«离线» H).«做得了» s.«模型» = true := by
      rw [← «做得了才有结果» un _ _ _,hu]; rfl
    have hh : u.«历史» = H := by
      simp only [«作用»,hd,Bool.not_true,Bool.false_eq_true,↓reduceIte] at hu
      cases hu; rfl
    change u.«历史».«端口数合» = true
    change u.«历史».«合规» = true at hregular
    rw [hh] at hregular ⊢
    exact (capacity_walk H).mp (walk_rebuild s.«场地» o ps H (regular_walk H hregular) hH)
  all_goals
    obtain ⟨⟨F,es⟩,hgeom,u,hu,rfl⟩ := he
    dsimp only at hgeom hregular ⊢
    have hh := execute_history un _ _ _ es hu
    have hn : Walk (fun v => v.2.Nodup) (snapshot s.«模型».«布局») es := by
      have hall := regular_walk u.«历史» hregular
      rw [hh,walk_append] at hall
      simpa only [«状态».«布局»,history_snapshot] using hall.2
    have hw : Walk Capacity (snapshot s.«模型».«布局») es := by
      first
        | exact walk_place _ _ o _ es _ hF hsync hcap hn hgeom
        | exact walk_collect _ _ _ es _ hcap hgeom
        | exact walk_blueprint _ _ o _ es _ hF hsync hcap hn hgeom
    apply (capacity_walk u.«历史»).mp
    rw [hh,walk_append]
    refine ⟨(capacity_walk s.«模型».«历史»).mpr hc, ?_⟩
    simpa only [«状态».«布局»,history_snapshot] using hw

/-- 据：端口、通道、接通

从空基地照位置建造的历史，每个事件前缀中单位的通道数都不超过端口数。
建造期间用段尾的通道上界，拆除期间用段首的通道上界，离线按重建的各段核对。 -/
theorem «格子层的历史端口数合» («h同步» : «命题».«格子层的单位和通道»)
    («h合规» : «命题».«格子层的历史合规») : «命题».«格子层的历史端口数合» := by
  intro un o bad f hf
  obtain ⟨as,ha⟩ := hf
  suffices ∀ as s t, «命题».«格子可达» un o bad s → s.«模型».«历史».«端口数合» = true →
      «命题».«格子依次作用» un o bad s as = some t → t.«模型».«历史».«端口数合» = true from
    this as _ f ⟨[],rfl⟩ rfl ha
  intro as
  induction as with
  | nil => intro s t _ hc he; cases he; exact hc
  | cons a as ih =>
    intro s t hr hc he
    simp only [«命题».«格子依次作用»,Option.bind_eq_some_iff] at he
    obtain ⟨u,hu,ht⟩ := he
    exact ih u t (reachable_next un o bad s u a hr hu)
      (grid_step_capacity «h同步» «h合规» un o bad s u a hr hc hu) ht

end Endfield.«证明»
