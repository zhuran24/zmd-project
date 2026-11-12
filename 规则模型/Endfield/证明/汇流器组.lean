import Endfield.«证明».«基础»

/-!
证明汇流器那组不看先后、汇流器那组不用记上次。
每步判两次时，同一汇流器至多选中一条通道；其他通道的判定是恒等操作，
所以任意两步可以交换。元件轮询只是原列表的循环排列，因而起始位置也不影响结果。
-/

namespace Endfield.«证明»

/-- 据：输入判定、元件轮询、组

只有输入判定选中的那条通道能送货，因此换排法不影响这一组的结果。 -/
theorem «汇流器那组不看先后» : «命题».«汇流器那组不看先后» := by
  intro T port un sa sb s t o₁ o₂ hun ht hcs hp
  unfold «状态».«判一组»
  apply hp.foldl_eq'
  intro c hc d hd z
  obtain ⟨hct, hcn⟩ := hcs c hc
  obtain ⟨hdt, hdn⟩ := hcs d hd
  have hn (e : «通道») (he : e.«止» = t)
      (hne : T.«现布局».«种类» e.«起» ≠ some .«分流器»)
      (hs : sb.«输入判定» T port t ≠ some e) :
      (T.«现布局».«种类» e.«止» == some .«汇流器» &&
       T.«现布局».«种类» e.«起» != some .«分流器» &&
       !sa.«汇流器收» T port un sb e) = true := by
    simp [«状态».«汇流器收», hun, he, ht, hne, hs]
  by_cases hsc : sb.«输入判定» T port t = some c
  · by_cases hsd : sb.«输入判定» T port t = some d
    · have hcd : c = d := Option.some.inj (hsc.symm.trans hsd)
      subst d
      rfl
    · simp only [hn d hdt hdn hsd, ite_true]
  · simp only [hn c hct hcn hsc, ite_true]

private theorem «循环排列» {α : Type} (xs : List α) (k : Nat) :
    (xs.rotateLeft k).Perm xs := by
  unfold List.rotateLeft
  dsimp only
  split
  · exact List.Perm.refl _
  · simpa only [List.take_append_drop] using
      (List.perm_append_comm :
        (xs.drop (k % xs.length) ++ xs.take (k % xs.length)).Perm
        (xs.take (k % xs.length) ++ xs.drop (k % xs.length)))

private theorem «先后是排列» (cs : List «通道») (last : Option «通道») :
    («元件先后» cs last).Perm cs := by
  have hr : («元件轮询» cs.length (last.bind fun c => cs.finIdxOf? c)).Perm
      (List.finRange cs.length) := by
    unfold «元件轮询»
    exact «循环排列» _ _
  have hp := hr.map cs.get
  have hget : (List.finRange cs.length).map cs.get = cs := by
    simp [List.finRange, List.map_ofFn, List.get_eq_getElem, Function.comp_def]
  rw [hget] at hp
  exact hp

/-- 据：输入判定、元件轮询、组

元件轮询给出的两种先后互为排列，故这一组移动判定不必另记上次。 -/
theorem «汇流器那组不用记上次» : «命题».«汇流器那组不用记上次» := by
  intro T port un sa sb s t cs last₁ last₂ hun ht hcs
  have hp₁ := «先后是排列» cs last₁
  have hp₂ := «先后是排列» cs last₂
  apply «汇流器那组不看先后» T port un sa sb s t _ _ hun ht
  · intro c hc
    exact hcs c (hp₁.subset hc)
  · exact hp₁.trans hp₂.symm

end Endfield.«证明»
