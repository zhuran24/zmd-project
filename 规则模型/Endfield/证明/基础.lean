import Endfield.«命题»

/-!
# 证明用的基础引理

几条命题的证明都要用到的事实：时刻 t+1 的布局是时刻 t 的布局上发生一件事；每种事怎样改单位的种类；
合规的历史上，每一刻的布局都是「整齐」的（单位号不重、通道不重、通道两头的单位都在）；
`最近一次变成` 给出的那一刻是什么样的一刻。
-/

namespace Endfield

/-- 工具：`p` 现在成立，`最近一次变成` 才有结果。 -/
theorem «最近一次变成_isSome» (p : «时刻» → Bool) (now : «时刻») :
    («最近一次变成» p now).isSome = p now := by
  induction now with
  | zero => simp [«最近一次变成»]; split <;> simp_all
  | succ n ih =>
    simp only [«最近一次变成»]
    split
    · split <;> simp_all
    · simp_all

/-- 工具：`最近一次变成` 给出的那一刻 t：从 t 到现在 `p` 一直成立，而且 t 是开头，或者前一刻 `p` 不成立。 -/
theorem «最近一次变成_spec» (p : «时刻» → Bool) (now t : «时刻»)
    (h : «最近一次变成» p now = some t) :
    t ≤ now ∧ (∀ k, t ≤ k → k ≤ now → p k = true) ∧ (t = 0 ∨ p (t - 1) = false) := by
  simp only [«时刻»] at *
  induction now generalizing t with
  | zero =>
    simp only [«最近一次变成»] at h
    split at h <;> simp_all
    intro k hk hk'
    have : k = t := by omega
    simpa [this]
  | succ n ih =>
    simp only [«最近一次变成»] at h
    split at h
    next hn =>
      split at h
      next hp =>
        obtain ⟨ht, hall, hb⟩ := ih t h
        refine ⟨by omega, ?_, hb⟩
        intro k hk hk'
        by_cases he : k = n + 1
        · simpa [he] using hn
        · exact hall k hk (by omega)
      next hp =>
        cases h
        refine ⟨by omega, ?_, Or.inr (by simpa using hp)⟩
        intro k hk hk'
        have he : k = n + 1 := by omega
        simpa only [he] using hn
    next hn => simp at h

namespace «布局»

/-- 工具：建成一个新单位以后各单位的种类（这个编号原来没有单位）。 -/
theorem «加建成_种类» (L : «布局») (t : «时刻») (u : «单位号») (k : «单位种类») (v : «单位号»)
    (h : L.«种类» u = none) :
    (L.«加» t (.«建成» u k)).«种类» v = if v = u then some k else L.«种类» v := by
  unfold «加» «种类» at *
  rw [List.find?_append]
  by_cases hv : v = u
  · subst v
    have hn : L.«单位表».find? (fun p => p.1 == u) = none := by
      cases he : L.«单位表».find? (fun p => p.1 == u) <;> simp_all
    simp [hn]
  · simp [hv, Ne.symm hv]

/-- 工具：接通一条通道不改各单位的种类。 -/
theorem «加接通_种类» (L : «布局») (t : «时刻») (c : «通道») (v : «单位号») :
    (L.«加» t (.«接通» c)).«种类» v = L.«种类» v := by
  rfl

/-- 工具：拆除一个单位以后各单位的种类。 -/
theorem «加拆除_种类» (L : «布局») (t : «时刻») (u v : «单位号») :
    (L.«加» t (.«拆除» u)).«种类» v = if v = u then none else L.«种类» v := by
  suffices hf : ∀ (xs : List («单位号» × «单位种类»)),
      ((xs.filter (fun p => p.1 != u)).find? (fun p => p.1 == v)).map (·.2) =
      if v = u then none else (xs.find? (fun p => p.1 == v)).map (·.2) by
    exact hf L.«单位表»
  intro xs
  induction xs with
  | nil => simp
  | cons a xs ih =>
    by_cases ha : a.1 = u <;> by_cases hv : a.1 = v <;>
      by_cases he : v = u <;> simp_all

/-- 工具：端口数合时，一个单位的取货通道不多于它的取货端口。 -/
theorem «端口数合_出» (L : «布局») (u : «单位号») (k : «单位种类»)
    (h : L.«端口数合» = true) (hk : L.«种类» u = some k) :
    (L.«出» u).length ≤ k.«取货端口数» := by
  unfold «种类» at hk
  obtain ⟨p, hp, hpk⟩ := Option.map_eq_some_iff.mp hk
  have hm := List.mem_of_find?_eq_some hp
  have hu := List.find?_some hp
  have hh := (List.all_eq_true.mp h) p hm
  simp only [Bool.and_eq_true, decide_eq_true_eq] at hh
  have he : p.1 = u := by simpa using hu
  simpa [he, hpk] using hh.2

/-- 工具：端口数合时，一个单位的存货通道不多于它的存货端口。 -/
theorem «端口数合_进» (L : «布局») (u : «单位号») (k : «单位种类»)
    (h : L.«端口数合» = true) (hk : L.«种类» u = some k) :
    (L.«进» u).length ≤ k.«存货端口数» := by
  unfold «种类» at hk
  obtain ⟨p, hp, hpk⟩ := Option.map_eq_some_iff.mp hk
  have hm := List.mem_of_find?_eq_some hp
  have hu := List.find?_some hp
  have hh := (List.all_eq_true.mp h) p hm
  simp only [Bool.and_eq_true, decide_eq_true_eq] at hh
  have he : p.1 = u := by simpa using hu
  simpa [he, hpk] using hh.1

/-- 工具：整齐的布局：单位号不重，通道不重，每条通道两头的单位都在、不是同一个、至少一方是运输单位。 -/
structure «整齐» (L : «布局») : Prop where
  «单位不重» : (L.«单位表».map (·.1)).Nodup
  «通道不重» : (L.«通道表».map (·.1)).Nodup
  «两头都在» : ∀ p ∈ L.«通道表»,
    (L.«种类» p.1.«起»).isSome = true ∧ (L.«种类» p.1.«止»).isSome = true
  «不连自己» : ∀ p ∈ L.«通道表», p.1.«起» ≠ p.1.«止»
  «有运输的» : ∀ p ∈ L.«通道表»,
    L.«是运输单位» p.1.«起» = true ∨ L.«是运输单位» p.1.«止» = true

private theorem kind_none (L : «布局») (u : «单位号») :
    L.«种类» u = none ↔ u ∉ L.«单位表».map (·.1) := by
  simp [«种类», List.find?_eq_none, List.mem_map]
  grind

private theorem nodup_filter_map {α β : Type} (xs : List α) (f : α → β) (p : α → Bool)
    (h : (xs.map f).Nodup) : ((xs.filter p).map f).Nodup :=
  List.Nodup.sublist ((List.filter_sublist).map f) h

private theorem tidy_add (L : «布局») (t : «时刻») (e : «事件»)
    (hs : L.«整齐») (he : L.«容得下» e = true) : (L.«加» t e).«整齐» := by
  cases e with
  | «建成» u k =>
    have hn : L.«种类» u = none := by
      have hh := he
      simp only [«容得下», Bool.and_eq_true, Option.isNone_iff_eq_none] at hh
      exact hh.1
    have hnot := (kind_none L u).mp hn
    have hk (v) := «加建成_种类» L t u k v hn
    have hc (p) (hp : p ∈ L.«通道表») : p.1.«起» ≠ u ∧ p.1.«止» ≠ u := by
      have hh := hs.«两头都在» p hp
      constructor <;> intro eq <;> simp_all
    refine ⟨?_, hs.«通道不重», ?_, ?_, ?_⟩
    · simp only [«加», List.map_append, List.map_cons, List.map_nil, List.nodup_append]
      refine ⟨hs.«单位不重», by simp, ?_⟩
      intro x hx y hy
      simp only [List.mem_cons, List.not_mem_nil, or_false] at hy
      subst y
      intro eq
      exact hnot (eq ▸ hx)
    · intro p hp
      have hh := hs.«两头都在» p hp
      simpa [hk, (hc p hp).1, (hc p hp).2] using hh
    · exact hs.«不连自己»
    · intro p hp
      simpa [«是运输单位», hk, (hc p hp).1, (hc p hp).2] using hs.«有运输的» p hp
  | «接通» c =>
    simp only [«容得下», Bool.and_eq_true, Bool.or_eq_true, Bool.not_eq_true', bne_iff_ne,
      List.any_eq_false] at he
    obtain ⟨⟨⟨⟨hneq, hsrc⟩, hdst⟩, htrans⟩, hnew⟩ := he
    refine ⟨hs.«单位不重», ?_, ?_, ?_, ?_⟩
    · simp only [«加», List.map_append, List.map_cons, List.map_nil, List.nodup_append]
      refine ⟨hs.«通道不重», by simp, ?_⟩
      intro x hx y hy
      simp only [List.mem_cons, List.not_mem_nil, or_false] at hy
      subst y
      obtain ⟨p, hp, rfl⟩ := List.mem_map.mp hx
      simpa using hnew p hp
    · intro p hp
      simp only [«加», List.mem_append, List.mem_cons, List.not_mem_nil, or_false] at hp
      rcases hp with hp | rfl
      · exact hs.«两头都在» p hp
      · exact ⟨hsrc, hdst⟩
    · intro p hp
      simp only [«加», List.mem_append, List.mem_cons, List.not_mem_nil, or_false] at hp
      rcases hp with hp | rfl
      · exact hs.«不连自己» p hp
      · exact hneq
    · intro p hp
      simp only [«加», List.mem_append, List.mem_cons, List.not_mem_nil, or_false] at hp
      rcases hp with hp | rfl
      · exact hs.«有运输的» p hp
      · exact htrans
  | «拆除» u =>
    refine ⟨nodup_filter_map _ _ _ hs.«单位不重», nodup_filter_map _ _ _ hs.«通道不重», ?_, ?_, ?_⟩
    · intro p hp
      obtain ⟨hp, ha, hb⟩ := (by simpa [«加», List.mem_filter, Bool.and_eq_true] using hp :
        p ∈ L.«通道表» ∧ p.1.«起» ≠ u ∧ p.1.«止» ≠ u)
      simpa [«加拆除_种类», ha, hb] using hs.«两头都在» p hp
    · intro p hp
      exact hs.«不连自己» p (List.mem_filter.mp hp).1
    · intro p hp
      obtain ⟨hp, ha, hb⟩ := (by simpa [«加», List.mem_filter, Bool.and_eq_true] using hp :
        p ∈ L.«通道表» ∧ p.1.«起» ≠ u ∧ p.1.«止» ≠ u)
      simpa [«是运输单位», «加拆除_种类», ha, hb] using hs.«有运输的» p hp

end «布局»

private theorem fold_time (es : List «事件») (a : «布局» × Nat) :
    (es.foldl (fun acc e => (acc.1.«加» (acc.2 + 1) e, acc.2 + 1)) a).2 = a.2 + es.length := by
  induction es generalizing a with
  | nil => simp
  | cons e es ih => simp only [List.foldl_cons, ih, List.length_cons]; omega

namespace «历史»

/-- 工具：什么都还没发生时布局是空的。 -/
theorem «布局于零» (H : «历史») : H.«布局于» 0 = {} := by
  rfl

/-- 工具：时刻 t+1 的布局，是时刻 t 的布局上发生第 t+1 件事（历史里下标 t 的那件）。 -/
theorem «布局于后继» (H : «历史») (t : Nat) (e : «事件») (h : H[t]? = some e) :
    H.«布局于» (t + 1) = (H.«布局于» t).«加» (t + 1) e := by
  unfold «布局于»
  rw [List.take_add_one, h]
  simp only [Option.toList_some, List.foldl_append, List.foldl_cons, List.foldl_nil]
  rw [fold_time]
  simp only [List.length_take]
  have ht : t < H.length := (List.getElem?_eq_some_iff.mp h).1
  rw [Nat.min_eq_left (by omega)]
  simp

/-- 工具：历史里的事都发生完以后，布局不再变。 -/
theorem «布局于过头» (H : «历史») (t : Nat) (h : H.length ≤ t) :
    H.«布局于» t = H.«布局于» H.length := by
  simp [«布局于», List.take_of_length_le h]

/-- 工具：`合规` 展开：每件事发生的那一刻，当时的布局都容得下它。 -/
theorem «合规_iff» (H : «历史») :
    H.«合规» = true ↔
      ∀ (t : Nat) (e : «事件»), H[t]? = some e → (H.«布局于» t).«容得下» e = true := by
  unfold «合规»
  simp only [List.all_eq_true, List.mem_range]
  constructor
  · intro h t e he
    have ht : t < H.length := (List.getElem?_eq_some_iff.mp he).1
    simpa [he] using h t ht
  · intro h t ht
    cases he : H[t]? with
    | none => rfl
    | some e => exact h t e he

/-- 工具：历史的端口数合时，任何一刻的布局端口数都合。 -/
theorem «端口数合_任一刻» (H : «历史») (h : H.«端口数合» = true) (t : Nat) :
    (H.«布局于» t).«端口数合» = true := by
  have hh := List.all_eq_true.mp h
  by_cases ht : t ≤ H.length
  · exact hh t (List.mem_range.mpr (by omega))
  · rw [«布局于过头» H t (by omega)]
    exact hh H.length (List.mem_range.mpr (by omega))

/-- 工具：合规的历史上，任何一刻的布局都整齐。 -/
theorem «合规则整齐» (H : «历史») (h : H.«合规» = true) (t : Nat) : (H.«布局于» t).«整齐» := by
  induction t with
  | zero => simp [«布局于零»]; exact ⟨by simp, by simp, by simp, by simp, by simp⟩
  | succ t ih =>
    cases he : H[t]? with
    | some e =>
      rw [«布局于后继» H t e he]
      exact «布局».tidy_add _ _ _ ih ((«合规_iff» H).mp h t e he)
    | none =>
      have ht : H.length ≤ t := List.getElem?_eq_none_iff.mp he
      rw [«布局于过头» H (t + 1) (by omega)]
      rw [«布局于过头» H t ht] at ih
      exact ih

end «历史»

namespace «布局»

/-- 工具：建成单位不改通道表。 -/
theorem «加建成_通道表» (L : «布局») (t : «时刻») (u : «单位号») (k : «单位种类») :
    (L.«加» t (.«建成» u k)).«通道表» = L.«通道表» := by
  rfl

/-- 工具：接通把新通道及其时刻追加到通道表末尾。 -/
theorem «加接通_通道表» (L : «布局») (t : «时刻») (c : «通道») :
    (L.«加» t (.«接通» c)).«通道表» = L.«通道表» ++ [(c, t)] := by
  rfl

/-- 工具：拆除单位只保留两端都不连该单位的通道。 -/
theorem «加拆除_通道表» (L : «布局») (t : «时刻») (u : «单位号») :
    (L.«加» t (.«拆除» u)).«通道表» =
      L.«通道表».filter (fun p => p.1.«起» != u && p.1.«止» != u) := by
  rfl

/-- 工具：建成单位不改任何单位的取货通道。 -/
theorem «加建成_出» (L : «布局») (t : «时刻») (u : «单位号») (k : «单位种类») (v : «单位号») :
    (L.«加» t (.«建成» u k)).«出» v = L.«出» v := by
  rfl

/-- 工具：建成单位不改任何单位的存货通道。 -/
theorem «加建成_进» (L : «布局») (t : «时刻») (u : «单位号») (k : «单位种类») (v : «单位号») :
    (L.«加» t (.«建成» u k)).«进» v = L.«进» v := by
  rfl

/-- 工具：接通仅给通道起点追加一条取货通道。 -/
theorem «加接通_出» (L : «布局») (t : «时刻») (c : «通道») (v : «单位号») :
    (L.«加» t (.«接通» c)).«出» v = L.«出» v ++ (if c.«起» = v then [(c, t)] else []) := by
  by_cases h : c.«起» = v <;> simp [«出», «加», List.filter_append, h]

/-- 工具：接通仅给通道终点追加一条存货通道。 -/
theorem «加接通_进» (L : «布局») (t : «时刻») (c : «通道») (v : «单位号») :
    (L.«加» t (.«接通» c)).«进» v = L.«进» v ++ (if c.«止» = v then [(c, t)] else []) := by
  by_cases h : c.«止» = v <;> simp [«进», «加», List.filter_append, h]

/-- 工具：拆除单位从取货通道中删除与该单位相连的通道。 -/
theorem «加拆除_出» (L : «布局») (t : «时刻») (u v : «单位号») :
    (L.«加» t (.«拆除» u)).«出» v =
      (L.«出» v).filter (fun p => p.1.«起» != u && p.1.«止» != u) := by
  simp only [«出», «加», List.filter_filter]
  congr 1
  funext p
  simp only [Bool.and_comm]

/-- 工具：拆除单位从存货通道中删除与该单位相连的通道。 -/
theorem «加拆除_进» (L : «布局») (t : «时刻») (u v : «单位号») :
    (L.«加» t (.«拆除» u)).«进» v =
      (L.«进» v).filter (fun p => p.1.«起» != u && p.1.«止» != u) := by
  simp only [«进», «加», List.filter_filter]
  congr 1
  funext p
  simp only [Bool.and_comm]

end «布局»

end Endfield
