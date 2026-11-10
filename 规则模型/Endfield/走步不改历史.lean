import Endfield.«判定»

/-!
# 走一步不改历史

走一步里的六种事都不改历史，沿着判定的各层归纳上去，一步也不改。
布局、元件、次序、组、级别都只从历史算，所以走步时它们都不变，判定表立一次可以一直用。
-/

namespace Endfield

/-- 工具：一列东西挨个作用到状态上，每次都不改历史，那么全部做完也不改历史。 -/
theorem «逐个做不改历史» {α : Type} (f : «状态» → α → «状态»)
    (h : ∀ s a, (f s a).«历史» = s.«历史») (l : List α) (s : «状态») :
    (l.foldl f s).«历史» = s.«历史» := by
  induction l generalizing s with
  | nil => rfl
  | cons a l ih => simp [List.foldl, ih, h]

namespace «状态»

/-- 框架：前移一遍不改历史。 -/
theorem «前移一遍不改历史» (T : «判定表») (port : «通道» → Nat) (s : «状态») :
    (s.«前移一遍» T port).1.«历史» = s.«历史» := by
  unfold «前移一遍»
  suffices h : ∀ (l : List «通道») (acc : «状态» × Bool),
      (l.foldl (fun (acc : «状态» × Bool) c =>
        match acc.1.«能移» T.«现布局» port c with
        | some (x, a, b) => (acc.1.«移一件» T.«现布局» c x a b, true)
        | none => acc) acc).1.«历史» = acc.1.«历史» from h _ _
  intro l
  induction l with
  | nil => intro acc; rfl
  | cons c l ih =>
    intro acc
    simp only [List.foldl]
    rw [ih]
    split <;> rfl

/-- 框架：整理不改历史。 -/
theorem «整理不改历史» (T : «判定表») (port : «通道» → Nat) (fuel : Nat) (s : «状态») :
    («整理» T port fuel s).«历史» = s.«历史» := by
  induction fuel generalizing s with
  | zero => rfl
  | succ n ih =>
    simp only [«整理»]
    split
    · rw [ih, «前移一遍不改历史»]
    · exact «前移一遍不改历史» T port s

/-- 框架：一组通道的移动判定不改历史。 -/
theorem «判一组不改历史» (T : «判定表») (port : «通道» → Nat) (sel : «通道» → Bool)
    (order : List «通道») (s : «状态») :
    (s.«判一组» T port sel order).«历史» = s.«历史» := by
  unfold «判一组»
  apply «逐个做不改历史»
  intro s c
  split
  · rfl
  · split
    · rw [«整理不改历史»]; rfl
    · rfl

/-- 框架：元件的移动判定不改历史。 -/
theorem «元件的移动判定不改历史» (T : «判定表») (port : «通道» → Nat)
    (sel : «通道» → Bool) (s : «状态») :
    (s.«元件的移动判定» T port sel).«历史» = s.«历史» := by
  unfold «元件的移动判定»
  apply «逐个做不改历史»
  intro s p
  exact «判一组不改历史» ..

/-- 框架：选取一个非运输单位不改历史。 -/
theorem «选取不改历史» (T : «判定表») (un : «未定») (todo : «待写») (port : «通道» → Nat)
    (sel : «通道» → Bool) (s : «状态») (p : «单位号» × List («组» × List «通道»)) :
    (s.«选取» T un todo port sel p).«历史» = s.«历史» := by
  have ht : ∀ s : «状态»,
      (if s.«该传输» T.«现布局» un todo p.1 then s.«传输一次» p.1 else s).«历史» = s.«历史» := by
    intro s; split <;> rfl
  unfold «选取»
  dsimp only
  split
  · refine Eq.trans («逐个做不改历史» _ ?_ _ _) (ht s)
    intro s g; exact «判一组不改历史» ..
  · refine Eq.trans (ht _) ?_
    refine «逐个做不改历史» _ ?_ _ _
    intro s g; exact «判一组不改历史» ..

/-- 框架：非运输单位的移动判定不改历史。 -/
theorem «非运输单位的移动判定不改历史» (T : «判定表») (un : «未定») (todo : «待写»)
    (port : «通道» → Nat) (sel : «通道» → Bool) (s : «状态») :
    (s.«非运输单位的移动判定» T un todo port sel).«历史» = s.«历史» := by
  unfold «非运输单位的移动判定»
  apply «逐个做不改历史»
  intro s p
  exact «选取不改历史» ..

/-- 框架：结束制造判定不改历史。 -/
theorem «结束制造判定不改历史» (T : «判定表») (todo : «待写») (s : «状态») :
    (s.«结束制造判定» T todo).«历史» = s.«历史» := by
  unfold «结束制造判定»
  apply «逐个做不改历史»
  intro s p
  dsimp only
  split
  · split
    · split
      · split <;> rfl
      · split <;> rfl
    · split <;> rfl
  · rfl

/-- 框架：开始制造判定不改历史。 -/
theorem «开始制造判定不改历史» (T : «判定表») (todo : «待写») (s : «状态») :
    (s.«开始制造判定» T todo).«历史» = s.«历史» := by
  unfold «开始制造判定»
  apply «逐个做不改历史»
  intro s p
  dsimp only
  split
  · split
    · split <;> rfl
    · rfl
  · rfl

end «状态»

/-- 据：判定顺序、通道

照判定表走一步不改历史。 -/
theorem «一步于不改历史» (T : «判定表») (un : «未定») (todo : «待写») (s : «状态») :
    («一步于» T un todo s).«历史» = s.«历史» := by
  unfold «一步于»
  show («计时» un todo _).«历史» = _
  simp only [«计时»]
  rw [«状态».«开始制造判定不改历史», «状态».«非运输单位的移动判定不改历史»,
    «状态».«元件的移动判定不改历史», «状态».«结束制造判定不改历史», «状态».«整理不改历史»]

/-- 据：判定顺序、通道

走一步不改历史：建成、接通、拆除都只在两步之间发生。所以走步时布局、元件、次序、组、级别都不变。 -/
theorem «一步不改历史» (un : «未定») (todo : «待写») (s : «状态») :
    («一步» un todo s).«历史» = s.«历史» :=
  «一步于不改历史» ..

end Endfield
