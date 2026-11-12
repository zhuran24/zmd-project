import Endfield.«证明».«基础»

/-!
证明非运输单位轮询等同于每次把移动通道放到队尾。
先证明队列操作的通用分解：未移动的初始元素保持次序，已移动元素按最后移动顺序排列。
再核对制造单位把零号通道移到未移动部分末尾的规则与初始队列一致。
-/

namespace Endfield.«证明»

private theorem contains_move {n : Nat} (m : List (Fin n)) (i x : Fin n) :
    (!(«记移动» m i).contains x) = (!m.contains x && (x != i)) := by
  by_cases h : x = i
  · subst x; simp [«记移动»]
  · simp [«记移动», List.mem_filter, h]

private theorem fold_queue {n : Nat} (q m is : List (Fin n)) :
    is.foldl «记移动» (q.filter (fun x => !m.contains x) ++ m) =
      q.filter (fun x => !(is.foldl «记移动» m).contains x) ++ is.foldl «记移动» m := by
  induction is generalizing m with
  | nil => rfl
  | cons i is ih =>
    simp only [List.foldl_cons]
    rw [show «记移动» (q.filter (fun x => !m.contains x) ++ m) i =
        q.filter (fun x => !(«记移动» m i).contains x) ++ «记移动» m i by
      simp only [«记移动», List.filter_append, List.filter_filter, List.append_assoc]
      congr 2
      funext x
      rw [← «记移动», contains_move]
      exact Bool.and_comm _ _]
    exact ih _

private theorem initial_form (n : Nat) (b : Bool) (m : List (Fin n)) :
    «非运输单位轮询» n b m =
      («非运输单位轮询» n b []).filter (fun x => !m.contains x) ++ m := by
  cases b with
  | false => simp [«非运输单位轮询»]
  | true =>
    cases n with
    | zero => simp [«非运输单位轮询»]
    | succ n =>
      have nozero : ∀ x ∈ ((List.finRange n).map Fin.succ).filter
          (fun x => !m.contains x), x.val ≠ 0 := by
        intro x hx
        simp only [List.mem_filter, List.mem_map] at hx
        obtain ⟨y, _, rfl⟩ := hx.1
        simp
      simp only [«非运输单位轮询», List.finRange_succ]
      by_cases h : (0 : Fin (n+1)) ∈ m
      · simp only [List.contains_eq_mem, h, decide_true, Bool.not_true,
          List.filter_cons, List.filter_nil, Bool.false_eq_true, ↓reduceIte,
          List.filter_append, List.append_assoc]
        split
        · rename_i x rest heq
          have hz := nozero x (by simpa only [List.contains_eq_mem, heq] using (show x ∈ x :: rest from List.mem_cons_self))
          have hx : x ≠ 0 := by intro he; subst x; simp at hz
          simp [hx, ← heq, h]
        · rename_i heq
          simp [heq, h]
      · simp [h, List.filter_nil, List.append_assoc]

/-- 据：非运输单位轮询

非运输单位轮询从初始队列开始，每次移动把对应通道移到队尾。
-/
theorem «非运输单位轮询是队列» : «命题».«非运输单位轮询是队列» := by
  intro n b is
  rw [initial_form]
  have hf : («非运输单位轮询» n b []).filter (fun _ => true) =
      «非运输单位轮询» n b [] := List.filter_eq_self.mpr (by intro x hx; rfl)
  simpa only [List.contains_nil, Bool.not_false, hf, List.append_nil] using
    (fold_queue («非运输单位轮询» n b []) [] is).symm

end Endfield.«证明»
