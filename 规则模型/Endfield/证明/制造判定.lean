import Endfield.«证明».«基础»

/-!
证明制造判定不看先后。把状态分成公共字段和各单位自己的货、制造进度；
每次判定只读自己的部分，只改自己的部分，因此不同单位的判定可交换。
最后使用排列对 foldl 的交换引理。
-/

namespace Endfield.«证明»

private def «公共» (s : «状态») : «状态» :=
  { s with «货» := fun _ => [], «制造中» := fun _ => none }

private def «同处» (u : «单位号») (s t : «状态») : Prop :=
  «公共» s = «公共» t ∧ (∀ g, g.«单位» = u → s.«货» g = t.«货» g) ∧
    s.«制造中» u = t.«制造中» u

private def «只改» (u : «单位号») (s t : «状态») : Prop :=
  «公共» s = «公共» t ∧ (∀ g, g.«单位» ≠ u → s.«货» g = t.«货» g) ∧
    (∀ v, v ≠ u → s.«制造中» v = t.«制造中» v)

private theorem «状态相等» {s t : «状态»} (h : «公共» s = «公共» t)
    (hc : s.«货» = t.«货») (hm : s.«制造中» = t.«制造中») : s = t := by
  cases s; cases t
  simp only [«公共», «状态».mk.injEq] at h
  simp_all

private theorem «同处运行» {u : «单位号»} {s t : «状态»} (h : «同处» u s t)
    (todo : «待写») (hp : todo.«有电只看历史») : s.«运行» todo u = t.«运行» todo u := by
  have hh := congrArg «状态».«历史» h.1
  have hs := congrArg «状态».«开关» h.1
  unfold «状态».«运行»
  change s.«开关» = t.«开关» at hs
  rw [hp s t u hh, hs]

private theorem «同处配方» {u : «单位号»} {s t : «状态»} (h : «同处» u s t)
    (k : «制造单位») : s.«符合的配方» k u = t.«符合的配方» k u := by
  have hc : ∀ n, s.«货» ⟨u, n⟩ = t.«货» ⟨u, n⟩ := fun n => h.2.1 _ rfl
  simp only [«状态».«符合的配方», «状态».«存货件数», «状态».«件数», hc]
  rfl

private theorem «同处进得去» {u : «单位号»} {s t : «状态»} (h : «同处» u s t) :
    s.«进得去» u = t.«进得去» u := by
  simp only [«状态».«进得去», h.2.2, h.2.1 ⟨u, .«缓存»⟩ rfl,
    h.2.1 ⟨u, .«取货»⟩ rfl]

private theorem «原子只改» (s : «状态») (u : «单位号») (r : «配方») :
    «只改» u s (s.«开始一次制造» u r) ∧
    «只改» u s (s.«结束一次制造» u r) ∧ «只改» u s (s.«进取货格» u) := by
  have hn (g : «格位») (h : g.«单位» ≠ u) (n : «格名») : g ≠ ⟨u, n⟩ := by
    intro he; exact h (congrArg «格位».«单位» he)
  simp only [«只改», «公共», «状态».«开始一次制造», «状态».«结束一次制造»,
    «状态».«进取货格», «换»]
  refine ⟨⟨True.intro, ?_, ?_⟩, ⟨True.intro, ?_, ?_⟩, ⟨True.intro, ?_, ?_⟩⟩
  all_goals intros; simp_all

private theorem «原子同处» {s t : «状态»} {u : «单位号»} (h : «同处» u s t) (r : «配方») :
    «同处» u (s.«开始一次制造» u r) (t.«开始一次制造» u r) ∧
    «同处» u (s.«结束一次制造» u r) (t.«结束一次制造» u r) ∧
    «同处» u (s.«进取货格» u) (t.«进取货格» u) := by
  simp only [«同处», «公共», «状态».«开始一次制造», «状态».«结束一次制造»,
    «状态».«进取货格», «换»]
  refine ⟨⟨h.1, ?_, by rfl⟩, ⟨h.1, ?_, by rfl⟩, ⟨h.1, ?_, h.2.2⟩⟩
  all_goals intro g hg
  all_goals try simp only [hg, ↓reduceIte]
  all_goals rw [h.2.1 g hg]
  all_goals try rw [h.2.1 ⟨u, .«缓存»⟩ rfl]

private theorem «只改反身» (s : «状态») (u : «单位号») : «只改» u s s :=
  ⟨rfl, fun _ _ => rfl, fun _ _ => rfl⟩

private theorem «只改传递» {u : «单位号»} {s t w : «状态»}
    (h : «只改» u s t) (h' : «只改» u t w) : «只改» u s w :=
  ⟨h.1.trans h'.1, fun g hg => (h.2.1 g hg).trans (h'.2.1 g hg),
    fun v hv => (h.2.2 v hv).trans (h'.2.2 v hv)⟩

private def «结束步» (L : «布局») (todo : «待写») (s : «状态») (u : «单位号») :=
  s.«结束制造判定» L todo [u]
private def «开始步» (L : «布局») (todo : «待写») (s : «状态») (u : «单位号») :=
  s.«开始制造判定» L todo [u]

private def «任意配方» : «配方» := «配方表»[0]

private theorem «步只改» (L : «布局») (todo : «待写») (s : «状态») (u : «单位号») :
    «只改» u s («结束步» L todo s u) ∧ «只改» u s («开始步» L todo s u) := by
  constructor
  · unfold «结束步» «状态».«结束制造判定»
    simp only [List.foldl_cons, List.foldl_nil]
    split
    · split
      · split
        · split
          · exact «只改传递» («原子只改» s u _).2.1 («原子只改» _ u «任意配方»).2.2
          · exact («原子只改» s u _).2.1
        · split
          · exact («原子只改» s u «任意配方»).2.2
          · exact «只改反身» s u
      · split
        · exact («原子只改» s u «任意配方»).2.2
        · exact «只改反身» s u
    · exact «只改反身» s u
  · unfold «开始步» «状态».«开始制造判定»
    simp only [List.foldl_cons, List.foldl_nil]
    split
    · split
      · split
        · exact («原子只改» s u _).1
        · exact «只改反身» s u
      · exact «只改反身» s u
    · exact «只改反身» s u

private theorem «入同处» {s t : «状态»} {u : «单位号»} (h : «同处» u s t) :
    «同处» u (if s.«进得去» u then s.«进取货格» u else s)
      (if t.«进得去» u then t.«进取货格» u else t) := by
  rw [«同处进得去» h]
  split
  · exact («原子同处» h «任意配方»).2.2
  · exact h

private theorem «步同处» (L : «布局») (todo : «待写») (hp : todo.«有电只看历史»)
    {s t : «状态»} {u : «单位号»} (h : «同处» u s t) :
    «同处» u («结束步» L todo s u) («结束步» L todo t u) ∧
    «同处» u («开始步» L todo s u) («开始步» L todo t u) := by
  have hr := «同处运行» h todo hp
  constructor
  · unfold «结束步» «状态».«结束制造判定»
    simp only [List.foldl_cons, List.foldl_nil]
    split
    · rw [h.2.2]
      split
      · rw [hr]
        split
        · exact «入同处» («原子同处» h _).2.1
        · exact «入同处» h
      · exact «入同处» h
    · exact h
  · unfold «开始步» «状态».«开始制造判定»
    simp only [List.foldl_cons, List.foldl_nil]
    split
    · rw [hr, h.2.2, h.2.1 ⟨u, .«缓存»⟩ rfl]
      split
      · rw [«同处配方» h _]
        split
        · exact («原子同处» h _).1
        · exact h
      · exact h
    · exact h

private theorem «异处同处» {s t : «状态»} {u v : «单位号»}
    (h : «只改» u s t) (hne : v ≠ u) : «同处» v s t :=
  ⟨h.1, fun g hg => h.2.1 g (by rw [hg]; exact hne), h.2.2 v hne⟩

private theorem «局部交换» (f : «状态» → «单位号» → «状态»)
    (hf : ∀ s u, «只改» u s (f s u))
    (hl : ∀ u s t, «同处» u s t → «同处» u (f s u) (f t u))
    (s : «状态») (u v : «单位号») : f (f s u) v = f (f s v) u := by
  by_cases he : u = v
  · subst v; rfl
  have hvu := Ne.symm he
  have hu := hf s u
  have hv := hf s v
  have huv := hf (f s u) v
  have hvu' := hf (f s v) u
  have lu := hl u s (f s v) («异处同处» hv he)
  have lv := hl v s (f s u) («异处同处» hu hvu)
  apply «状态相等»
  · exact huv.1.symm.trans (hu.1.symm.trans (hv.1.trans hvu'.1))
  · funext g
    by_cases hgu : g.«单位» = u
    · exact (huv.2.1 g (by rw [hgu]; exact he)).symm.trans (lu.2.1 g hgu)
    · by_cases hgv : g.«单位» = v
      · exact (lv.2.1 g hgv).symm.trans (hvu'.2.1 g hgu)
      · exact (huv.2.1 g hgv).symm.trans
          ((hu.2.1 g hgu).symm.trans ((hv.2.1 g hgv).trans (hvu'.2.1 g hgu)))
  · funext w
    by_cases hwu : w = u
    · subst w
      exact (huv.2.2 u he).symm.trans lu.2.2
    · by_cases hwv : w = v
      · subst w
        exact lv.2.2.symm.trans (hvu'.2.2 v hvu)
      · exact (huv.2.2 w hwv).symm.trans
          ((hu.2.2 w hwu).symm.trans ((hv.2.2 w hwv).trans (hvu'.2.2 w hwu)))

/-- 据：判定顺序、制造

所有单位的结束制造判定和开始制造判定，分别换成任意排列都得到同一状态。
-/
theorem «制造判定不看先后» : «命题».«制造判定不看先后» := by
  intro L todo us us' s hp hperm
  constructor
  · change us.foldl («结束步» L todo) s = us'.foldl («结束步» L todo) s
    apply hperm.foldl_eq'
    intro u _ v _ z
    exact «局部交换» («结束步» L todo) (fun s u => («步只改» L todo s u).1)
      (fun u s t h => («步同处» L todo hp h).1) z u v
  · change us.foldl («开始步» L todo) s = us'.foldl («开始步» L todo) s
    apply hperm.foldl_eq'
    intro u _ v _ z
    exact «局部交换» («开始步» L todo) (fun s u => («步只改» L todo s u).2)
      (fun u s t h => («步同处» L todo hp h).2) z u v

end Endfield.«证明»
