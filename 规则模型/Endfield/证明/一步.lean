import Endfield.«证明».«基础»

/-!
证明一步不看没定的先后及顶层命题。先消去各组列举顺序，再证明换表不改变整理、
输入判定及各层移动判定，最后用制造判定的排列不变性拼合一步。合法性提供顶层所需前提。
-/

namespace Endfield.«证明»

private theorem table_eq («h排» : «命题».«按级别排不看先后»)
    (H : «历史») (gs : List «组») (hc : H.«合规» = true)
    (hp : gs.Perm (H.«布局于» H.length).«各组») : H.«立表照» gs = H.«立表» := by
  have he : ∀ f : «组» → Bool,
      H.«按级别排» (gs.filter f) = H.«按级别排» ((H.«布局于» H.length).«各组».filter f) :=
    fun f => «h排» H _ _ hc (hp.filter f)
  simp only [«历史».«立表», «历史».«立表照», he]

private theorem find_eq (H : «历史») (js : List («单位号» × List «通道»))
    (hp : js.Perm H.«立表».«汇流器») (j : «单位号») :
    js.find? (·.1 == j) = H.«立表».«汇流器».find? (·.1 == j) := by
  have unique : ∀ a ∈ H.«立表».«汇流器», ∀ b ∈ H.«立表».«汇流器», a.1 = b.1 → a = b := by
    intro a ha b hb hab
    simp only [«历史».«立表», «历史».«立表照», List.mem_map] at ha hb
    obtain ⟨x, _, rfl⟩ := ha
    obtain ⟨y, _, rfl⟩ := hb
    simp only at hab
    subst y
    rfl
  cases ha : js.find? (·.1 == j) with
  | none =>
    symm
    apply List.find?_eq_none.mpr
    intro x hx
    exact (List.find?_eq_none.mp ha) x (hp.mem_iff.mpr hx)
  | some a =>
    cases hb : H.«立表».«汇流器».find? (·.1 == j) with
    | none =>
      have := (List.find?_eq_none.mp hb) a (hp.mem_iff.mp (List.mem_of_find?_eq_some ha))
      have := List.find?_some ha
      simp_all
    | some b =>
      congr 1
      apply unique a (hp.mem_iff.mp (List.mem_of_find?_eq_some ha)) b (List.mem_of_find?_eq_some hb)
      have h₁ := List.find?_some ha
      have h₂ := List.find?_some hb
      simp_all

private theorem tidy_js (T : «判定表») (bs js) (port : «通道» → Nat) (fuel : Nat) (s : «状态») :
    «状态».«整理» («命题».«换排法» T bs js) port fuel s =
    «状态».«整理» («命题».«换排法» T bs T.«汇流器») port fuel s := by
  induction fuel generalizing s with
  | zero => rfl
  | succ n ih =>
    simp only [«状态».«整理»]
    have he : s.«前移一遍» («命题».«换排法» T bs js) port =
        s.«前移一遍» («命题».«换排法» T bs T.«汇流器») port := rfl
    rw [he]
    split <;> simp only [ih]

private theorem input_eq (T U : «判定表») (hl : U.«现布局» = T.«现布局»)
    (hf : ∀ j, U.«汇流器».find? (·.1 == j) = T.«汇流器».find? (·.1 == j))
    (port) (s : «状态») (j) : s.«输入判定» U port j = s.«输入判定» T port j := by
  simp only [«状态».«输入判定», hf, hl]

private theorem accept_eq (T U : «判定表») (hl : U.«现布局» = T.«现布局»)
    (hf : ∀ j, U.«汇流器».find? (·.1 == j) = T.«汇流器».find? (·.1 == j))
    (port) (un : «未定») (s1 s3 : «状态») :
    s1.«汇流器收» U port un s3 = s1.«汇流器收» T port un s3 := by
  funext c
  simp only [«状态».«汇流器收», input_eq T U hl hf, hf]

private theorem group_eq (T U : «判定表») (hl : U.«现布局» = T.«现布局»)
    (ht : ∀ port s, «状态».«整理» U port U.«现布局».«单位表».length s =
      «状态».«整理» T port T.«现布局».«单位表».length s)
    (port sel order) (s : «状态») : s.«判一组» U port sel order = s.«判一组» T port sel order := by
  unfold «状态».«判一组»
  have ht' : ∀ s, «状态».«整理» U port T.«现布局».«单位表».length s =
      «状态».«整理» T port T.«现布局».«单位表».length s := by simpa only [hl] using ht port
  simp only [hl, ht']

private theorem component_eq (T U : «判定表») (hl : U.«现布局» = T.«现布局»)
    (hg : U.«元件的组» = T.«元件的组»)
    (ht : ∀ port s, «状态».«整理» U port U.«现布局».«单位表».length s =
      «状态».«整理» T port T.«现布局».«单位表».length s)
    (port sel) (s : «状态») : s.«元件的移动判定» U port sel = s.«元件的移动判定» T port sel := by
  simp only [«状态».«元件的移动判定», hg, group_eq T U hl ht]

private theorem select_eq (T U : «判定表») (hl : U.«现布局» = T.«现布局»)
    (ht : ∀ port s, «状态».«整理» U port U.«现布局».«单位表».length s =
      «状态».«整理» T port T.«现布局».«单位表».length s)
    (un todo port sel) (s : «状态») (p) :
    s.«选取» U un todo port sel p = s.«选取» T un todo port sel p := by
  simp only [«状态».«选取», hl, group_eq T U hl ht]

private theorem nontransport_eq (T U : «判定表») (hl : U.«现布局» = T.«现布局»)
    (hn : U.«非运输单位» = T.«非运输单位»)
    (ht : ∀ port s, «状态».«整理» U port U.«现布局».«单位表».length s =
      «状态».«整理» T port T.«现布局».«单位表».length s)
    (un todo port sel) (s : «状态») :
    s.«非运输单位的移动判定» U un todo port sel = s.«非运输单位的移动判定» T un todo port sel := by
  simp only [«状态».«非运输单位的移动判定», hn, select_eq T U hl ht]

/-- 据：判定顺序、移动、级别

规则未定的各处先后换成任意排列，走一步所得的状态相同。 -/
theorem «一步不看没定的先后»
    («h整理» : «命题».«整理不看带内先后») («h制造» : «命题».«制造判定不看先后»)
    («h排» : «命题».«按级别排不看先后») («h带内» : «命题».«立表的带内整齐») :
    «命题».«一步不看没定的先后» := by
  intro un todo s gs bs js us₁ us₂ he hc hp hgs hbs hjs hu₁ hu₂
  rw [table_eq «h排» s.«历史» gs hc hgs]
  let T := s.«历史».«立表»
  let U := «命题».«换排法» T bs js
  have hl : U.«现布局» = T.«现布局» := rfl
  have ht : ∀ port s', «状态».«整理» U port U.«现布局».«单位表».length s' =
      «状态».«整理» T port T.«现布局».«单位表».length s' := by
    intro port s'
    rw [tidy_js T bs js]
    exact «h整理» T bs port _ s' («h带内» _ hc hp).1 hbs («h带内» _ hc hp).2
  have hf : ∀ j, U.«汇流器».find? (·.1 == j) = T.«汇流器».find? (·.1 == j) :=
    find_eq s.«历史» js hjs
  have hm₁ : ∀ s' : «状态», s'.«结束制造判定» T.«现布局» todo us₁ =
      s'.«结束制造判定» T.«现布局» todo (T.«非运输单位».map (·.1)) :=
    fun s' => («h制造» _ todo _ _ s' he hu₁).1
  have hm₂ : ∀ s' : «状态», s'.«开始制造判定» T.«现布局» todo us₂ =
      s'.«开始制造判定» T.«现布局» todo (T.«非运输单位».map (·.1)) :=
    fun s' => («h制造» _ todo _ _ s' he hu₂).2
  change «命题».«一步照» T bs js us₁ us₂ un todo s = «一步于» T un todo s
  unfold «命题».«一步照» «一步于»
  change (let port := todo.«口» s
          let s0 := «状态».«整理» U port U.«现布局».«单位表».length s
          let s1 := s0.«结束制造判定» U.«现布局» todo us₁
          let s3 := s1.«元件的移动判定» U port (fun c => s1.«汇流器收» U port un s1 c)
          let s4 := s3.«非运输单位的移动判定» U un todo port (fun c => s1.«汇流器收» U port un s3 c)
          let s5 := s4.«开始制造判定» U.«现布局» todo us₂
          «计时» un todo s5) = _
  have ht' := ht
  simp only [hl] at ht'
  simp only [ht', hl, hm₁, hm₂, accept_eq T U hl hf,
    component_eq T U hl rfl ht, nontransport_eq T U hl rfl ht]

/-- 据：判定顺序、级别、移动

合法基地上的操作有结果、每个组都有级别，且一步不依赖未定先后。 -/
theorem «顶层»
    («h一步» : «命题».«一步不看没定的先后») («h级别» : «命题».«每个组都有级别») :
    «命题».«顶层» := by
  intro un todo s he hl
  have hh := hl
  simp only [«历史».«合法», Bool.and_eq_true] at hh
  refine ⟨fun o => «做得了才有结果» un todo s o, «h级别» _ hl, ?_⟩
  intro gs bs js us₁ us₂ hgs hbs hjs hu₁ hu₂
  exact «h一步» un todo s gs bs js us₁ us₂ he hh.1.1
    (s.«历史».«端口数合_任一刻» hh.1.2 _) hgs hbs hjs hu₁ hu₂

end Endfield.«证明»
