import Endfield.«证明».«基础»

/-!
证明可达状态合规。先说明历史末尾添加当时布局容得下的事件仍然合规，
再证明每个成功的操作保持历史合规，最后对操作表归纳，并从空状态出发。
-/

namespace Endfield.«证明»

private theorem «末尾添事件合规» (H : «历史») (e : «事件»)
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

private theorem «作用保持合规» (un : «未定») (todo : «待写»)
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
    exact «末尾添事件合规» _ _ hs hd
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

private theorem «依次作用保持合规» (un : «未定») (todo : «待写»)
    (os : List «操作») (s s' : «状态») (hs : s.«历史».«合规» = true)
    (h : «命题».«依次作用» un todo s os = some s') : s'.«历史».«合规» = true := by
  induction os generalizing s with
  | nil =>
    simp only [«命题».«依次作用», Option.some.injEq] at h
    simpa only [← h] using hs
  | cons o os ih =>
    simp only [«命题».«依次作用»] at h
    cases ho : «作用» un todo s o with
    | none => simp [ho] at h
    | some next =>
      simp only [ho, Option.bind_some] at h
      exact ih next («作用保持合规» un todo s next o hs ho) h

/-- 据：通道、接通

从空状态依次执行任何操作，成功到达的状态历史都合规。 -/
theorem «可达状态合规» : «命题».«可达状态合规» := by
  intro un todo os s h
  exact «依次作用保持合规» un todo os «状态».«空» s (by rfl) h

end Endfield.«证明»
