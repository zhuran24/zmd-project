import Endfield.«证明».«格子同步»

/-!
证明格子层可达状态中，协议核心和仓库取货口的出通道都能查到取货端口编号。
固定编号表列出这些摆件的全部取货端口；场地单位号唯一及同通道端口唯一，
保证筛选后恰好留下一个编号。编号范围由核心六项、仓库取货口一项的表长给出。
-/

namespace Endfield.«证明»

open «格子» («场地» «摆件» «端口» «接通先后» «朝向» «平行边» «核心边格» «排端口»)

private theorem mapM_length {α β : Type} (f : α → Option β) (xs : List α)
    (ys : List β) (h : xs.mapM f = some ys) : ys.length = xs.length := by
  induction xs generalizing ys with
  | nil => simpa using h.symm
  | cons x xs ih =>
    simp only [List.mapM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at h
    obtain ⟨y, hy, zs, hzs, rfl⟩ := h
    simp [ih zs hzs]

private theorem mapM_permutation {α β : Type} (f : α → Option β)
    {xs ys : List α} (hp : xs.Perm ys) (zs : List β) (hz : xs.mapM f = some zs) :
    ∃ ws, ys.mapM f = some ws ∧ zs.Perm ws := by
  induction hp generalizing zs with
  | nil =>
    simp only [List.mapM_nil, Option.pure_def, Option.some.injEq] at hz
    subst zs
    exact ⟨[], rfl, .nil⟩
  | cons x hp ih =>
    simp only [List.mapM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at hz
    obtain ⟨z, hfz, zs, hz, rfl⟩ := hz
    obtain ⟨ws, hw, hperm⟩ := ih zs hz
    exact ⟨z :: ws, by simp [List.mapM_cons, hfz, hw], hperm.cons z⟩
  | swap x y xs =>
    simp only [List.mapM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at hz
    obtain ⟨a, ha, _, ⟨b, hb, zs, hz, rfl⟩, rfl⟩ := hz
    exact ⟨b :: a :: zs, by simp [List.mapM_cons, ha, hb, hz], .swap ..⟩
  | trans h₁ h₂ ih₁ ih₂ =>
    obtain ⟨ws, hw, hpw⟩ := ih₁ zs hz
    obtain ⟨vs, hv, hpv⟩ := ih₂ ws hw
    exact ⟨vs, hv, hpw.trans hpv⟩

private theorem mapped_ports_flag (p : «摆件») (b : Bool)
    (styles : List («朝向» × Nat)) (ps : List «端口»)
    (h : styles.mapM (fun (d,n) => p.«造端口» b d n) = some ps)
    (a : «端口») (ha : a ∈ ps) : a.«取货» = b := by
  obtain ⟨⟨d,n⟩, _, hm⟩ := (mapM_mem _ _ _ h a).mp ha
  exact («造端口性质» p b d n a hm).2.2.1

private theorem warehouse_data (p : «摆件») (o : «接通先后») (ps : List «端口»)
    (hp : p.«端口» o = some ps) :
    ∃ ws, p.«仓库取货端口» = some ws ∧ ws.Nodup ∧
      (∀ a ∈ ws, a ∈ ps ∧ a.«取货» = true) ∧
      (∀ k, p.«种类» = .«协议核心» k → ws.length = 6 ∧
        ∀ a ∈ ps, a.«取货» = true → a ∈ ws) ∧
      (∀ d, p.«种类» = .«仓库取货口» d → ws.length = 1 ∧
        ∀ a ∈ ps, a.«取货» = true → a ∈ ws) := by
  have hpn := ports_nodup p o ps hp
  have hh := hp
  simp only [«摆件».«端口», Option.bind_eq_bind, Option.bind_eq_some_iff] at hh
  obtain ⟨cs, hcs, hh⟩ := hh
  cases hk : p.«种类»
  case «协议核心» k =>
    simp only [hk, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at hh
    obtain ⟨ins, hins, outs, houts, rfl⟩ := hh
    obtain ⟨ws, hws, hperm⟩ := mapM_permutation
      (fun (d,n) => p.«造端口» true d n)
      (List.mergeSort_perm («核心边格» k true) _) outs houts
    refine ⟨ws, ?_, hperm.nodup (List.nodup_append.mp hpn).2.1, ?_, ?_, ?_⟩
    · simp [«摆件».«仓库取货端口», hcs, hk, hws]
    · intro a ha
      have hao := hperm.mem_iff.mpr ha
      exact ⟨List.mem_append_right _ hao, mapped_ports_flag p true _ outs houts a hao⟩
    · intro k' he
      have hlen := mapM_length _ _ _ hws
      have hcore : («核心边格» k true).length = 6 := by cases k <;> decide
      refine ⟨hlen.trans hcore, ?_⟩
      intro a ha ht
      rcases List.mem_append.mp ha with hai | hao
      · have hf := mapped_ports_flag p false _ ins hins a hai
        simp [hf] at ht
      · exact hperm.mem_iff.mp hao
    · intro d hd; simp at hd
  case «仓库取货口» d =>
    simp only [hk, Option.bind_eq_some_iff,
      Option.pure_def, Option.some.injEq] at hh
    obtain ⟨a, ha, rfl⟩ := hh
    refine ⟨[a], ?_, by simp, ?_, ?_, ?_⟩
    · simp [«摆件».«仓库取货端口», hcs, hk, ha]
    · intro b hb
      have he : b = a := by simpa using hb
      subst b
      exact ⟨by simp, («造端口性质» p true d 1 a ha).2.2.1⟩
    · intro k he; simp at he
    · intro d' he; exact ⟨rfl, fun _ hm _ => hm⟩
  all_goals
    refine ⟨[], ?_, by simp, by simp, ?_, ?_⟩
    · simp [«摆件».«仓库取货端口», hcs, hk]
    · intro k he; simp at he
    · intro d he; simp at he

private theorem filterMap_one {α β : Type} (xs : List α) (f : α → Option β)
    (hn : xs.Nodup) (a : α) (b : β) (ha : a ∈ xs) (hf : f a = some b)
    (hother : ∀ x ∈ xs, x ≠ a → f x = none) : xs.filterMap f = [b] := by
  induction xs with
  | nil => simp at ha
  | cons x xs ih =>
    obtain ⟨hnot, hnt⟩ := List.nodup_cons.mp hn
    rcases List.mem_cons.mp ha with rfl | ha
    · have ht : xs.filterMap f = [] := List.filterMap_eq_nil_iff.mpr (by
        intro x hx
        exact hother x (by simp [hx]) (fun he => hnot (he ▸ hx)))
      simp [hf, ht]
    · have hne : x ≠ a := fun he => hnot (he ▸ ha)
      simp only [List.filterMap_cons_none (hother x (by simp) hne)]
      exact ih hnt ha (fun y hy => hother y (by simp [hy]))

private theorem collect_empty {α β : Type} (xs : List α) (f : α → Option (List β))
    (h : ∀ x ∈ xs, f x = some []) :
    ∃ ys, xs.mapM f = some ys ∧ ys.flatten = [] := by
  induction xs with
  | nil => exact ⟨[], rfl, rfl⟩
  | cons x xs ih =>
    obtain ⟨ys, hy, he⟩ := ih (fun y hy => h y (by simp [hy]))
    exact ⟨[] :: ys, by simp [List.mapM_cons, h x (by simp), hy], by simpa using he⟩

private theorem collect_one {α β : Type} (xs : List α) (f : α → Option (List β))
    (hn : xs.Nodup) (a : α) (b : β) (ha : a ∈ xs) (hf : f a = some [b])
    (hother : ∀ x ∈ xs, x ≠ a → f x = some []) :
    ∃ ys, xs.mapM f = some ys ∧ ys.flatten = [b] := by
  induction xs with
  | nil => simp at ha
  | cons x xs ih =>
    obtain ⟨hnot, hnt⟩ := List.nodup_cons.mp hn
    rcases List.mem_cons.mp ha with rfl | ha
    · obtain ⟨ys, hy, he⟩ := collect_empty xs f (by
        intro x hx
        exact hother x (by simp [hx]) (fun he => hnot (he ▸ hx)))
      exact ⟨[b] :: ys, by simp [List.mapM_cons, hf, hy], by simp [he]⟩
    · have hne : x ≠ a := fun he => hnot (he ▸ ha)
      obtain ⟨ys, hy, he⟩ := ih hnt ha (fun y hy => hother y (by simp [hy]))
      exact ⟨[] :: ys, by simp [List.mapM_cons, hother x (by simp) hne, hy],
        by simpa using he⟩

private def portMatches (rows : List («摆件» × List «端口»)) (p : «摆件»)
    (c : «通道») (a : «端口») : Bool :=
  a.«单位» == c.«起» && rows.any (fun (q,bs) =>
    bs.any fun b => «格子».«形成通道» p q a b == some c)

private def matchingNumbers (rows : List («摆件» × List «端口»)) (c : «通道»)
    (p : «摆件») : Option (List Nat) := do
  let ws ← p.«仓库取货端口»
  return ws.zipIdx.filterMap fun (a,i) => if portMatches rows p c a then some i else none

private theorem matches_iff (F : «场地») (o : «接通先后»)
    (rows : List («摆件» × List «端口»))
    (hrows : F.mapM (fun p => do return (p, ← p.«端口» o)) = some rows)
    (p : «摆件») (c : «通道») (a : «端口») :
    portMatches rows p c a = true ↔ a.«单位» = c.«起» ∧
      ∃ q ∈ F, ∃ qs, q.«端口» o = some qs ∧
        ∃ b ∈ qs, «格子».«形成通道» p q a b = some c := by
  simp only [portMatches, Bool.and_eq_true, beq_iff_eq, List.any_eq_true]
  constructor
  · rintro ⟨hu, ⟨q,qs⟩, hq, b, hb, hc⟩
    obtain ⟨hqF,hqs⟩ := (rows_mem F o rows hrows q qs).mp hq
    exact ⟨hu,q,hqF,qs,hqs,b,hb,hc⟩
  · rintro ⟨hu,q,hqF,qs,hqs,b,hb,hc⟩
    exact ⟨hu,(q,qs),(rows_mem F o rows hrows q qs).mpr ⟨hqF,hqs⟩,b,hb,hc⟩

private theorem matched_port_unique (F : «场地») (o : «接通先后») (hF : FieldGood F)
    (rows : List («摆件» × List «端口»))
    (hrows : F.mapM (fun p => do return (p, ← p.«端口» o)) = some rows)
    (c : «通道») (p r : «摆件») (hpF : p ∈ F) (hrF : r ∈ F)
    (ps rs : List «端口») (hps : p.«端口» o = some ps) (hrs : r.«端口» o = some rs)
    (a a' : «端口») (ha : a ∈ ps) (ha' : a' ∈ rs)
    (hm : portMatches rows p c a = true) (hm' : portMatches rows r c a' = true) :
    r = p ∧ a' = a := by
  obtain ⟨hu,q,hqF,qs,hqs,b,hb,hc⟩ := (matches_iff F o rows hrows p c a).mp hm
  obtain ⟨hu',s,hsF,ss,hss,b',hb',hc'⟩ := (matches_iff F o rows hrows r c a').mp hm'
  have he : r = p := field_unit_owner F hF r p hrF hpF c.«起»
    (hu' ▸ «端口单位属于摆件» r o rs hrs a' ha')
    (hu ▸ «端口单位属于摆件» p o ps hps a ha)
  subst r
  have he : rs = ps := Option.some.inj (hrs.symm.trans hps)
  subst rs
  exact ⟨rfl, (same_channel_port F o hF p q s hpF hqF hsF ps qs ss hps hqs hss
    a a' b b' ha ha' hb hb' c hc hc').symm⟩

private theorem lookup_from_port (F : «场地») (o : «接通先后») (hF : FieldGood F)
    (rows : List («摆件» × List «端口»))
    (hrows : F.mapM (fun p => do return (p, ← p.«端口» o)) = some rows)
    (c : «通道») (p : «摆件») (hpF : p ∈ F) (ps ws : List «端口»)
    (hps : p.«端口» o = some ps) (hws : p.«仓库取货端口» = some ws)
    (hwn : ws.Nodup) (hsub : ∀ a ∈ ws, a ∈ ps)
    (a : «端口») (ha : a ∈ ws) (hm : portMatches rows p c a = true) :
    ∃ i, F.«口?» o c = some i ∧ i < ws.length := by
  obtain ⟨i, hi, hai⟩ := List.mem_iff_getElem.mp ha
  have hzi : (a,i) ∈ ws.zipIdx := by
    apply List.mk_mem_zipIdx_iff_getElem?.mpr
    simpa [hai] using List.getElem?_eq_getElem hi
  have hzip : ws.zipIdx.Nodup := by
    have hn : (ws.zipIdx.map Prod.fst).Nodup := by simpa using hwn
    exact (List.pairwise_map.mp hn).imp (fun h he => h (congrArg Prod.fst he))
  have hsingle : matchingNumbers rows c p = some [i] := by
    unfold matchingNumbers
    rw [hws]
    apply congrArg some
    apply filterMap_one _ _ hzip (a,i) i hzi (by simp [hm])
    intro ⟨a',j⟩ hz hne
    have ha' := List.fst_mem_of_mem_zipIdx hz
    by_cases hm' : portMatches rows p c a' = true
    · have he := (matched_port_unique F o hF rows hrows c p p hpF hpF
        ps ps hps hps a a' (hsub a ha) (hsub a' ha') hm hm').2
      subst a'
      have hji : j = i := (hwn.getElem?_inj (List.mem_zipIdx' hz).1).mp
        ((List.mk_mem_zipIdx_iff_getElem?.mp hz).trans
          (List.mk_mem_zipIdx_iff_getElem?.mp hzi).symm)
      exact (hne (by simp [hji])).elim
    · simp [hm']
  have hother : ∀ r ∈ F, r ≠ p → matchingNumbers rows c r = some [] := by
    intro r hr hne
    obtain ⟨⟨r',rs⟩, hrs⟩ := mapM_has _ _ _ hrows r hr
    simp only [Option.bind_eq_bind, Option.bind_eq_some_iff, Option.pure_def,
      Option.some.injEq, Prod.mk.injEq] at hrs
    obtain ⟨rps, hrps, he, he'⟩ := hrs
    subst r'; subst rs
    obtain ⟨rws, hrws, _, hrsub, _⟩ := warehouse_data r o rps hrps
    unfold matchingNumbers
    rw [hrws]
    apply congrArg some
    apply List.filterMap_eq_nil_iff.mpr
    intro ⟨a',j⟩ hz
    by_cases hm' : portMatches rows r c a' = true
    · have ha' := (hrsub a' (List.fst_mem_of_mem_zipIdx hz)).1
      exact (hne (matched_port_unique F o hF rows hrows c p r hpF hr
        ps rps hps hrps a a' (hsub a ha) ha' hm hm').1).elim
    · simp [hm']
  obtain ⟨found,hfound,hflat⟩ := collect_one F (matchingNumbers rows c)
    (field_nodup F hF) p i hpF hsingle hother
  refine ⟨i, ?_, hi⟩
  unfold «场地».«口?»
  change (F.mapM (fun p : «摆件» => do return (p, ← p.«端口» o))).bind _ = some i
  rw [hrows]
  change (F.mapM (matchingNumbers rows c)).bind _ = some i
  rw [hfound]
  simp [hflat]

private theorem output_start (p q : «摆件») (a b : «端口») (c : «通道»)
    (ha : a.«取货» = true) (hc : «格子».«形成通道» p q a b = some c) :
    a.«单位» = c.«起» := by
  rcases (forms_properties p q a b c hc).2.2 with ⟨_,he⟩ | ⟨hba,_⟩
  · exact (congrArg «通道».«起» he).symm
  · have hf := («正对性质» b a hba).2.1
    simp [ha] at hf

private theorem field_kind (F : «场地») (hF : FieldGood F) (L : «布局»)
    (hunits : L.«单位表» = F.flatMap «摆件».«单位»)
    (p : «摆件») (hpF : p ∈ F) (u : Nat) (hu : u ∈ p.«单位».map Prod.fst)
    (k : «单位种类») (hk : L.«种类» u = some k) : (u,k) ∈ p.«单位» := by
  simp only [«布局».«种类», Option.map_eq_some_iff] at hk
  obtain ⟨v,hv,hvk⟩ := hk
  have hvu : v.1 = u := by simpa using List.find?_some hv
  have hmem := List.mem_of_find?_eq_some hv
  rw [hunits] at hmem
  obtain ⟨q,hqF,hqv⟩ := List.mem_flatMap.mp hmem
  have hqu : u ∈ q.«单位».map Prod.fst := List.mem_map.mpr ⟨v,hqv,hvu⟩
  have he := field_unit_owner F hF p q hpF hqF u hu hqu
  subst q
  simpa only [← hvu, ← hvk] using hqv

private theorem core_piece (p : «摆件») (u : Nat) (h : (u,.«协议核心») ∈ p.«单位») :
    ∃ k, p.«种类» = .«协议核心» k := by
  cases hk : p.«种类» <;>
    simp [«摆件».«单位»,hk,«朝向».«各边»,«朝向».«编号»] at h
  exact ⟨_,rfl⟩

private theorem warehouse_piece (p : «摆件») (u : Nat) (h : (u,.«仓库取货口») ∈ p.«单位») :
    ∃ d, p.«种类» = .«仓库取货口» d := by
  cases hk : p.«种类» <;>
    simp [«摆件».«单位»,hk,«朝向».«各边»,«朝向».«编号»] at h
  exact ⟨_,rfl⟩

/-- 据：协议核心、仓库取货口、通道

可达场地中，核心和仓库取货口的出通道各有唯一匹配的固定取货端口编号。
核心编号小于六，仓库取货口编号为零。 -/
theorem «格子层的取货端口都找得到» («h同步» : «命题».«格子层的单位和通道») :
    «命题».«格子层的取货端口都找得到» := by
  intro un o bad f hf ct hct
  have hF := reachable_fieldGood un o bad f hf
  obtain ⟨hunits,cs,hcs,hchannels⟩ := «h同步» un o bad f hf
  have hc : ct.1 ∈ cs := (hchannels ct.1).mpr (List.mem_map.mpr ⟨ct,hct,rfl⟩)
  unfold «命题».«场地该有的通道» at hcs
  simp only [Option.bind_eq_bind, Option.bind_eq_some_iff,
    Option.pure_def, Option.some.injEq] at hcs
  obtain ⟨rows,hrows,rfl⟩ := hcs
  obtain ⟨⟨p,ps⟩,hp,hc⟩ := List.mem_flatMap.mp hc
  obtain ⟨a,ha,hc⟩ := List.mem_flatMap.mp hc
  obtain ⟨⟨q,qs⟩,hq,hc⟩ := List.mem_flatMap.mp hc
  obtain ⟨b,hb,hform⟩ := List.mem_filterMap.mp hc
  obtain ⟨hpF,hps⟩ := (rows_mem f.«场地» o rows hrows p ps).mp hp
  obtain ⟨hqF,hqs⟩ := (rows_mem f.«场地» o rows hrows q qs).mp hq
  obtain ⟨ha,hat⟩ := List.mem_filter.mp ha
  have hau := output_start p q a b ct.1 hat hform
  have howner : ct.1.«起» ∈ p.«单位».map Prod.fst :=
    hau ▸ «端口单位属于摆件» p o ps hps a ha
  have hm : portMatches rows p ct.1 a = true :=
    (matches_iff f.«场地» o rows hrows p ct.1 a).mpr
      ⟨hau,q,hqF,qs,hqs,b,hb,hform⟩
  obtain ⟨ws,hws,hwn,hsub,hcore,hwarehouse⟩ := warehouse_data p o ps hps
  constructor
  · intro hk
    obtain ⟨k,hk⟩ := core_piece p ct.1.«起»
      (field_kind f.«场地» hF f.«模型».«布局» hunits p hpF ct.1.«起» howner _ hk)
    obtain ⟨hlen,hcover⟩ := hcore k hk
    obtain ⟨i,hi,hbound⟩ := lookup_from_port f.«场地» o hF rows hrows ct.1 p hpF
      ps ws hps hws hwn (fun a ha => (hsub a ha).1) a (hcover a ha hat) hm
    exact ⟨i,hi,by simpa only [hlen] using hbound⟩
  · intro hk
    obtain ⟨d,hk⟩ := warehouse_piece p ct.1.«起»
      (field_kind f.«场地» hF f.«模型».«布局» hunits p hpF ct.1.«起» howner _ hk)
    obtain ⟨hlen,hcover⟩ := hwarehouse d hk
    obtain ⟨i,hi,hbound⟩ := lookup_from_port f.«场地» o hF rows hrows ct.1 p hpF
      ps ws hps hws hwn (fun a ha => (hsub a ha).1) a (hcover a ha hat) hm
    have hi0 : i = 0 := by omega
    simpa only [hi0] using hi

end Endfield.«证明»
