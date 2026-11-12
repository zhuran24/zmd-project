import Endfield.«证明».«基础»

/-!
证明「整理不看带内先后」。带内同时能移的两条通道涉及四个不同物品格，
所以两次移动交换次序后状态相同。每次移动严格减少起点已停满一 tick 的通道数；
足够多遍整理因此得到不可移动的状态。最后用菱形性质证明这种状态唯一。
-/

namespace Endfield.«证明»

private def cell (u : «单位号») : «格位» := ⟨u, .«格» 0⟩

private def belt (L : «布局») (c : «通道») : Prop :=
  L.«种类» c.«起» = some .«传送带» ∧
  L.«种类» c.«止» = some .«传送带» ∧ c.«起» ≠ c.«止»

private theorem can_belt (L : «布局») (port : «通道» → Nat)
    (s : «状态») (c : «通道») (hc : belt L c) :
    s.«能移» L port c =
      match s.«货» (cell c.«起») with
      | [] => none
      | p :: _ => if «tick» ≤ s.«已停» (cell c.«起») ∧
          s.«货» (cell c.«止») = [] ∧ s.«来处» (cell c.«起») ≠ some (cell c.«止»)
        then some (p.«物», .«格» (cell c.«起»), .«格» (cell c.«止»)) else none := by
  dsimp [cell] at *
  cases hh : s.«货» ⟨c.«起», .«格» 0⟩ with
  | nil => simp [«状态».«能移», «状态».«可移动物品», hc.1, hh]
  | cons p ps =>
    by_cases ht : «tick» ≤ s.«已停» ⟨c.«起», .«格» 0⟩
    · by_cases he : s.«货» ⟨c.«止», .«格» 0⟩ = []
      · by_cases hb : s.«来处» ⟨c.«起», .«格» 0⟩ = some ⟨c.«止», .«格» 0⟩ <;>
          simp [«状态».«能移», «状态».«可移动物品», «状态».«放进哪»,
            hc.1, hc.2.1, hh, ht, he, hb]
      · simp [«状态».«能移», «状态».«可移动物品», «状态».«放进哪»,
          hc.1, hc.2.1, hh, ht, he]
    · simp [«状态».«能移», «状态».«可移动物品», hc.1, hh, ht]

private def move (s : «状态») (c : «通道») (x : «物品») : «状态» :=
  { s with
    «货» := fun g =>
      if cell c.«止» = g then «添几件»
        (if cell c.«起» = g then «拿几件» (s.«货» g) x 1 else s.«货» g) x 1
      else if cell c.«起» = g then «拿几件» (s.«货» g) x 1 else s.«货» g
    «已停» := fun g => if cell c.«起» = g ∨ cell c.«止» = g then 0 else s.«已停» g
    «来处» := fun g => if cell c.«止» = g then some (cell c.«起»)
      else if cell c.«起» = g then none else s.«来处» g }

private theorem move_belt (L : «布局») (s : «状态») (c : «通道»)
    (x : «物品») (hc : belt L c) :
    s.«移一件» L c x (.«格» (cell c.«起»)) (.«格» (cell c.«止»)) = move s c x := by
  have hu : ∀ g : «格位», cell c.«止» = g → L.«是运输单位» g.«单位» = true := by
    intro g h
    subst g
    simp [cell, «布局».«是运输单位», hc.2.1, «单位种类».«是运输单位»]
  simp [«状态».«移一件», «布局».«算进货», «布局».«算出货», «布局».«所在组»,
    hc.1, hc.2.1, move]
  funext g
  split <;> simp_all

private theorem can_data (L : «布局») (port : «通道» → Nat)
    (s : «状态») (c : «通道») (hc : belt L c) (x : «物品») (a b : «货位»)
    (h : s.«能移» L port c = some (x, a, b)) :
    a = .«格» (cell c.«起») ∧ b = .«格» (cell c.«止») ∧
    «tick» ≤ s.«已停» (cell c.«起») ∧ s.«货» (cell c.«起») ≠ [] ∧
    s.«货» (cell c.«止») = [] := by
  rw [can_belt L port s c hc] at h
  split at h
  · contradiction
  · split at h
    · simp only [Option.some.injEq, Prod.mk.injEq] at h
      grind
    · contradiction

private theorem endpoints (cs : List «通道»)
    (hp : cs.Pairwise (fun c d => c.«起» ≠ d.«起» ∧ c.«止» ≠ d.«止»))
    (c d : «通道») (hc : c ∈ cs) (hd : d ∈ cs) (hne : c ≠ d) :
    c.«起» ≠ d.«起» ∧ c.«止» ≠ d.«止» := by
  induction cs with
  | nil => simp at hc
  | cons e es ih =>
    simp only [List.pairwise_cons] at hp
    simp only [List.mem_cons] at hc hd
    rcases hc with rfl | hc
    · rcases hd with rfl | hd
      · contradiction
      · exact hp.1 _ hd
    · rcases hd with rfl | hd
      · have h := hp.1 _ hc
        exact ⟨Ne.symm h.1, Ne.symm h.2⟩
      · exact ih hp.2 hc hd

private theorem move_read (s : «状态») (c : «通道») (x : «物品») (g : «格位»)
    (ha : cell c.«起» ≠ g) (hb : cell c.«止» ≠ g) :
    (move s c x).«货» g = s.«货» g ∧
    (move s c x).«已停» g = s.«已停» g ∧
    (move s c x).«来处» g = s.«来处» g := by
  simp [move, ha, hb]

private theorem move_comm (s : «状态») (c d : «通道») (x y : «物品»)
    (haa : cell c.«起» ≠ cell d.«起») (hab : cell c.«起» ≠ cell d.«止»)
    (hba : cell c.«止» ≠ cell d.«起») (hbb : cell c.«止» ≠ cell d.«止») :
    move (move s c x) d y = move (move s d y) c x := by
  simp only [move]
  congr 1 <;> funext g <;>
    by_cases ha : cell c.«起» = g <;> by_cases hb : cell c.«止» = g <;>
    by_cases hd : cell d.«起» = g <;> by_cases he : cell d.«止» = g <;>
    simp_all

private def step (L : «布局») (port : «通道» → Nat) (cs : List «通道»)
    (s t : «状态») : Prop :=
  ∃ c ∈ cs, ∃ x, s.«能移» L port c =
    some (x, .«格» (cell c.«起»), .«格» (cell c.«止»)) ∧ t = move s c x

private theorem can_after (L : «布局») (port : «通道» → Nat) (s : «状态»)
    (c d : «通道») (x : «物品») (hd : belt L d)
    (haa : cell c.«起» ≠ cell d.«起») (hab : cell c.«起» ≠ cell d.«止»)
    (hba : cell c.«止» ≠ cell d.«起») (hbb : cell c.«止» ≠ cell d.«止») :
    (move s c x).«能移» L port d = s.«能移» L port d := by
  rw [can_belt L port _ d hd, can_belt L port _ d hd]
  have ha := move_read s c x (cell d.«起») haa hba
  have hb := move_read s c x (cell d.«止») hab hbb
  rw [ha.1, ha.2.1, ha.2.2, hb.1]

private theorem step_diamond (L : «布局») (port : «通道» → Nat) (cs : List «通道»)
    (ht : ∀ c ∈ cs, belt L c)
    (hp : cs.Pairwise (fun c d => c.«起» ≠ d.«起» ∧ c.«止» ≠ d.«止»))
    (s a b : «状态») (ha : step L port cs s a) (hb : step L port cs s b) :
    a = b ∨ ∃ t, step L port cs a t ∧ step L port cs b t := by
  rcases ha with ⟨c, hc, x, hx, rfl⟩
  rcases hb with ⟨d, hd, y, hy, rfl⟩
  by_cases he : c = d
  · subst d
    have : x = y := by rw [hx] at hy; simp_all
    subst y
    exact Or.inl rfl
  · have hep := endpoints cs hp c d hc hd he
    have hxc := can_data L port s c (ht c hc) _ _ _ hx
    have hyd := can_data L port s d (ht d hd) _ _ _ hy
    have haa : cell c.«起» ≠ cell d.«起» := by
      intro h; exact hep.1 (congrArg «格位».«单位» h)
    have hbb : cell c.«止» ≠ cell d.«止» := by
      intro h; exact hep.2 (congrArg «格位».«单位» h)
    have hab : cell c.«起» ≠ cell d.«止» := by
      intro h; exact hxc.2.2.2.1 (h ▸ hyd.2.2.2.2)
    have hba : cell c.«止» ≠ cell d.«起» := by
      intro h; exact hyd.2.2.2.1 (h ▸ hxc.2.2.2.2)
    refine Or.inr ⟨move (move s c x) d y, ?_, ?_⟩
    · exact ⟨d, hd, y, (can_after L port s c d x (ht d hd) haa hab hba hbb).trans hy, rfl⟩
    · refine ⟨c, hc, x, ?_, move_comm s c d x y haa hab hba hbb⟩
      exact (can_after L port s d c y (ht c hc) haa.symm hba.symm hab.symm hbb.symm).trans hx

-- 用允许原地不动的一步关系，菱形可以逐行拼成任意两条有限路径的合流图。
private def stay {α : Type} (r : α → α → Prop) (a b : α) : Prop := a = b ∨ r a b

private def walk {α : Type} (r : α → α → Prop) : Nat → α → α → Prop
  | 0, a, b => a = b
  | n + 1, a, b => ∃ c, stay r a c ∧ walk r n c b

private def reaches {α : Type} (r : α → α → Prop) (a b : α) : Prop :=
  ∃ n, walk r n a b

private theorem reaches_refl {α : Type} (r : α → α → Prop) (a : α) : reaches r a a :=
  ⟨0, rfl⟩

private theorem reaches_one {α : Type} (r : α → α → Prop) {a b : α}
    (h : r a b) : reaches r a b := ⟨1, b, Or.inr h, rfl⟩

private theorem walk_append {α : Type} (r : α → α → Prop) {n m : Nat} {a b c : α}
    (h : walk r n a b) (k : walk r m b c) : walk r (m + n) a c := by
  induction n generalizing a with
  | zero => cases h; exact k
  | succ n ih =>
    rcases h with ⟨d, hd, h⟩
    exact ⟨d, hd, ih h⟩

private theorem reaches_trans {α : Type} (r : α → α → Prop) {a b c : α}
    (h : reaches r a b) (k : reaches r b c) : reaches r a c := by
  rcases h with ⟨n, h⟩
  rcases k with ⟨m, k⟩
  exact ⟨m + n, walk_append r h k⟩

private theorem stay_diamond {α : Type} (r : α → α → Prop)
    (hd : ∀ a b c, r a b → r a c → b = c ∨ ∃ d, r b d ∧ r c d)
    {a b c : α} (h : stay r a b) (k : stay r a c) :
    ∃ d, stay r b d ∧ stay r c d := by
  rcases h with rfl | h
  · exact ⟨c, k, Or.inl rfl⟩
  rcases k with rfl | k
  · exact ⟨b, Or.inl rfl, Or.inr h⟩
  rcases hd a b c h k with rfl | ⟨d, hb, hc⟩
  · exact ⟨b, Or.inl rfl, Or.inl rfl⟩
  · exact ⟨d, Or.inr hb, Or.inr hc⟩

private theorem walk_strip {α : Type} (r : α → α → Prop)
    (hd : ∀ a b c, r a b → r a c → b = c ∨ ∃ d, r b d ∧ r c d)
    {n : Nat} {a b c : α} (h : stay r a b) (k : walk r n a c) :
    ∃ d, walk r n b d ∧ stay r c d := by
  induction n generalizing a b with
  | zero => cases k; exact ⟨b, rfl, h⟩
  | succ n ih =>
    rcases k with ⟨e, he, k⟩
    rcases stay_diamond r hd h he with ⟨f, hf, hef⟩
    rcases ih hef k with ⟨d, hfd, hcd⟩
    exact ⟨d, ⟨f, hf, hfd⟩, hcd⟩

private theorem walk_join {α : Type} (r : α → α → Prop)
    (hd : ∀ a b c, r a b → r a c → b = c ∨ ∃ d, r b d ∧ r c d)
    {n m : Nat} {a b c : α} (h : walk r n a b) (k : walk r m a c) :
    ∃ d, walk r m b d ∧ walk r n c d := by
  induction n generalizing a c with
  | zero => cases h; exact ⟨c, k, rfl⟩
  | succ n ih =>
    rcases h with ⟨e, he, h⟩
    rcases walk_strip r hd he k with ⟨f, hef, hcf⟩
    rcases ih h hef with ⟨d, hbd, hfd⟩
    exact ⟨d, hbd, ⟨f, hcf, hfd⟩⟩

private theorem walk_normal {α : Type} (r : α → α → Prop) {n : Nat} {a b : α}
    (ha : ∀ c, ¬ r a c) (h : walk r n a b) : a = b := by
  induction n generalizing a with
  | zero => exact h
  | succ n ih =>
    rcases h with ⟨c, hc, h⟩
    rcases hc with rfl | hc
    · exact ih ha h
    · exact False.elim (ha c hc)

private theorem normal_unique {α : Type} (r : α → α → Prop)
    (hd : ∀ a b c, r a b → r a c → b = c ∨ ∃ d, r b d ∧ r c d)
    {s a b : α} (ha : reaches r s a) (hb : reaches r s b)
    (hna : ∀ c, ¬ r a c) (hnb : ∀ c, ¬ r b c) : a = b := by
  rcases ha with ⟨n, ha⟩
  rcases hb with ⟨m, hb⟩
  rcases walk_join r hd ha hb with ⟨c, hac, hbc⟩
  exact (walk_normal r hna hac).trans (walk_normal r hnb hbc).symm

-- 只数已停满一 tick 的起点；即使初始货物不是正常的一件一格，也足以控制移动次数。
private def remaining (cs : List «通道») (s : «状态») : Nat :=
  cs.countP (fun c => decide («tick» ≤ s.«已停» (cell c.«起»)))

private theorem count_strict {α : Type} (cs : List α) (p q : α → Bool)
    (h : ∀ c ∈ cs, p c = true → q c = true)
    (hw : ∃ c ∈ cs, q c = true ∧ p c = false) : cs.countP p < cs.countP q := by
  induction cs with
  | nil => simp at hw
  | cons a cs ih =>
    have ht : ∀ c ∈ cs, p c = true → q c = true := fun c hc => h c (by simp [hc])
    have hle := List.countP_mono_left ht
    have hh := h a (by simp)
    by_cases ha : q a = true ∧ p a = false
    · simp [ha.1, ha.2]
      omega
    · have hw' : ∃ c ∈ cs, q c = true ∧ p c = false := by
        rcases hw with ⟨c, hc, hq, hp⟩
        rcases List.mem_cons.mp hc with rfl | hc
        · exact False.elim (ha ⟨hq, hp⟩)
        · exact ⟨c, hc, hq, hp⟩
      have hi := ih ht hw'
      cases hp : p a <;> cases hq : q a <;>
        simp_all <;> omega

private theorem move_decreases (cs : List «通道») (s : «状态») (c : «通道»)
    (x : «物品») (hc : c ∈ cs) (ht : «tick» ≤ s.«已停» (cell c.«起»)) :
    remaining cs (move s c x) < remaining cs s := by
  apply count_strict
  · intro d hd hm
    simp only [decide_eq_true_eq] at hm ⊢
    simp only [move] at hm
    split at hm
    · simp [«tick»] at hm
    · exact hm
  · refine ⟨c, hc, by simpa using ht, ?_⟩
    simp [move, «tick»]

private theorem zero_normal (L : «布局») (port : «通道» → Nat) (cs : List «通道»)
    (ht : ∀ c ∈ cs, belt L c) (s : «状态») (hz : remaining cs s = 0) :
    ∀ c ∈ cs, s.«能移» L port c = none := by
  intro c hc
  cases hm : s.«能移» L port c with
  | none => rfl
  | some v =>
    rcases v with ⟨x, a, b⟩
    have hr := (can_data L port s c (ht c hc) x a b hm).2.2.1
    have hp : 0 < remaining cs s :=
      List.countP_pos_iff.mpr ⟨c, hc, by simpa using hr⟩
    omega

private def scan (L : «布局») (port : «通道» → Nat)
    (order : List «通道») (acc : «状态» × Bool) : «状态» × Bool :=
  order.foldl (fun acc c =>
    match acc.1.«能移» L port c with
    | some (x, a, b) => (acc.1.«移一件» L c x a b, true)
    | none => acc) acc

private theorem scan_cons (L : «布局») (port : «通道» → Nat)
    (c : «通道») (order : List «通道») (s : «状态») (flag : Bool) :
    scan L port (c :: order) (s, flag) = scan L port order
      (match s.«能移» L port c with
       | some (x, a, b) => (s.«移一件» L c x a b, true)
       | none => (s, flag)) := rfl

private theorem scan_spec (L : «布局») (port : «通道» → Nat) (cs : List «通道»)
    (ht : ∀ c ∈ cs, belt L c) (order : List «通道»)
    (hs : ∀ c ∈ order, c ∈ cs) (s : «状态») (flag : Bool) :
    reaches (step L port cs) s (scan L port order (s, flag)).1 ∧
    remaining cs (scan L port order (s, flag)).1 ≤ remaining cs s ∧
    ((scan L port order (s, flag)).2 = false →
      (scan L port order (s, flag)).1 = s ∧ ∀ c ∈ order, s.«能移» L port c = none) ∧
    ((scan L port order (s, flag)).2 = true →
      flag = true ∨ remaining cs (scan L port order (s, flag)).1 < remaining cs s) := by
  induction order generalizing s flag with
  | nil =>
    exact ⟨reaches_refl _ _, Nat.le_refl _, fun _ => ⟨rfl, by simp⟩, fun h => Or.inl h⟩
  | cons c order ih =>
    have hc : c ∈ cs := hs c (by simp)
    have hs' : ∀ d ∈ order, d ∈ cs := fun d hd => hs d (by simp [hd])
    cases hm : s.«能移» L port c with
    | none =>
      have hi := ih hs' s flag
      rw [scan_cons, hm]
      refine ⟨hi.1, hi.2.1, ?_, hi.2.2.2⟩
      intro hf
      obtain ⟨he, hn⟩ := hi.2.2.1 hf
      exact ⟨he, by simpa [hm] using hn⟩
    | some v =>
      rcases v with ⟨x, a, b⟩
      obtain ⟨rfl, rfl, htime, _, _⟩ := can_data L port s c (ht c hc) x a b hm
      have he := move_belt L s c x (ht c hc)
      have hi := ih hs' (move s c x) true
      have hl := move_decreases cs s c x hc htime
      have hr : step L port cs s (move s c x) := ⟨c, hc, x, hm, rfl⟩
      rw [scan_cons, hm]
      simp only [he]
      refine ⟨reaches_trans _ (reaches_one _ hr) hi.1, by omega, ?_, fun _ => Or.inr (by omega)⟩
      intro hf
      -- 一旦置为 true，扫描其余通道不会把标志清回 false。
      have hflag : ∀ (os : List «通道») (t : «状态»), (scan L port os (t, true)).2 = true := by
        intro os
        induction os with
        | nil => intro t; rfl
        | cons d ds ihf =>
          intro t
          simp only [scan, List.foldl_cons]
          cases h : t.«能移» L port d with
          | none => exact ihf t
          | some v => rcases v with ⟨y, a, b⟩; exact ihf (t.«移一件» L d y a b)
      have := hflag order (move s c x)
      exact Bool.noConfusion (this.symm.trans hf)

private theorem sort_spec (T : «判定表») (port : «通道» → Nat) (cs : List «通道»)
    (ht : ∀ c ∈ cs, belt T.«现布局» c)
    (hm : ∀ c, c ∈ T.«带内» ↔ c ∈ cs) (fuel : Nat) (s : «状态»)
    (hf : remaining cs s ≤ fuel) :
    reaches (step T.«现布局» port cs) s («状态».«整理» T port fuel s) ∧
    ∀ c ∈ cs, («状态».«整理» T port fuel s).«能移» T.«现布局» port c = none := by
  induction fuel generalizing s with
  | zero =>
    exact ⟨reaches_refl _ _, zero_normal T.«现布局» port cs ht s (by omega)⟩
  | succ fuel ih =>
    let r := scan T.«现布局» port T.«带内» (s, false)
    have hs := scan_spec T.«现布局» port cs ht T.«带内» (fun c hc => (hm c).mp hc) s false
    change reaches (step T.«现布局» port cs) s r.1 ∧ remaining cs r.1 ≤ remaining cs s ∧
      (r.2 = false → r.1 = s ∧ ∀ c ∈ T.«带内», s.«能移» T.«现布局» port c = none) ∧
      (r.2 = true → false = true ∨ remaining cs r.1 < remaining cs s) at hs
    change reaches (step T.«现布局» port cs) s
        (if r.2 then «状态».«整理» T port fuel r.1 else r.1) ∧
      ∀ c ∈ cs, (if r.2 then «状态».«整理» T port fuel r.1 else r.1).«能移» T.«现布局» port c = none
    cases he : r.2 with
    | false =>
      simp only [Bool.false_eq_true, ↓reduceIte]
      have hn := hs.2.2.1 he
      refine ⟨hs.1, ?_⟩
      intro c hc
      rw [hn.1]
      exact hn.2 c ((hm c).mpr hc)
    | true =>
      simp only [↓reduceIte]
      have hd : remaining cs r.1 < remaining cs s := by
        rcases hs.2.2.2 he with h | h
        · contradiction
        · exact h
      have hi := ih r.1 (by omega)
      exact ⟨reaches_trans _ hs.1 hi.1, hi.2⟩

private theorem no_step (L : «布局») (port : «通道» → Nat) (cs : List «通道»)
    (s : «状态») (h : ∀ c ∈ cs, s.«能移» L port c = none) :
    ∀ t, ¬ step L port cs s t := by
  rintro t ⟨c, hc, x, hx, _⟩
  rw [h c hc] at hx
  contradiction

/-- 据：移动、元件

带内通道换成任意排列，在至少通道条数遍的整理以后，得到的状态相同。 -/
theorem «整理不看带内先后» : «命题».«整理不看带内先后» := by
  intro T bs port fuel s ht hp hf
  have hb : remaining T.«带内» s ≤ fuel :=
    Nat.le_trans List.countP_le_length hf
  have ha := sort_spec T port T.«带内» ht.1 (fun _ => Iff.rfl) fuel s hb
  have horder : ∀ c, c ∈ («命题».«换排法» T bs T.«汇流器»).«带内» ↔ c ∈ T.«带内» :=
    fun c => hp.mem_iff
  have hd := sort_spec («命题».«换排法» T bs T.«汇流器») port T.«带内» ht.1 horder fuel s hb
  exact normal_unique (step T.«现布局» port T.«带内»)
    (step_diamond T.«现布局» port T.«带内» ht.1 ht.2)
    hd.1 ha.1 (no_step _ _ _ _ hd.2) (no_step _ _ _ _ ha.2)

end Endfield.«证明»
