import Endfield.«证明».«基础»

/-!
证明格子层的顶层。先把里层操作保持历史合规和货合规矩的性质沿事件表、
格子操作表传递，从空状态得到货合规矩；其余三项分别由操作有结果、
一步不看先后和合法历史上每组有级别的假设推出。
-/

namespace Endfield.«证明»

private def «良好» (s : «状态») : Prop :=
  s.«历史».«合规» = true ∧ s.«货合规矩»

private theorem «里层保持»
    («h操作» : «命题».«操作守物品格的规矩») («h保持» : «命题».«操作保持合规»)
    (un : «未定») (todo : «待写») (ht : «命题».«放进单位守规矩» todo)
    (s s' : «状态») (a : «操作») (hs : «良好» s)
    (ha : «作用» un todo s a = some s') : «良好» s' :=
  ⟨«h保持» un todo s s' a hs.1 ha, «h操作» un todo s s' a ht hs.1 hs.2 ha⟩

private theorem «事件保持»
    («h操作» : «命题».«操作守物品格的规矩») («h保持» : «命题».«操作保持合规»)
    (un : «未定») (todo : «待写») (ht : «命题».«放进单位守规矩» todo)
    (es : «历史») (s s' : «状态») (hs : «良好» s)
    (ha : «格子».«执行事件» un todo s es = some s') : «良好» s' := by
  induction es generalizing s with
  | nil =>
    simp only [«格子».«执行事件», List.foldlM_nil, Option.pure_def, Option.some.injEq] at ha
    subst s'
    exact hs
  | cons e es ih =>
    simp only [«格子».«执行事件», List.foldlM_cons, Option.bind_eq_bind, Option.bind_eq_some_iff] at ha
    obtain ⟨t, ht', ha⟩ := ha
    exact ih t («里层保持» «h操作» «h保持» un todo ht s t (.«改布局» e) hs ht') ha

private theorem «格子操作保持»
    («h放货» : «命题».«格子层的放进单位守规矩»)
    («h操作» : «命题».«操作守物品格的规矩») («h保持» : «命题».«操作保持合规»)
    (un : «未定») (o : «格子».«接通先后») (bad : «通道» → Nat)
    (f f' : «格子».«状态») (a : «格子».«操作») (hs : «良好» f.«模型»)
    (ha : «格子».«作用» un o bad f a = some f') : «良好» f'.«模型» := by
  cases a with
  | «建» p | «收» u | «蓝图» ps =>
    simp only [«格子».«作用», Option.bind_eq_bind, Option.pure_def, Option.bind_eq_some_iff, Option.some.injEq] at ha
    obtain ⟨⟨F, es⟩, _, t, ht, heq⟩ := ha
    subst f'
    exact «事件保持» «h操作» «h保持» un (F.«待写» o bad) («h放货» F o bad) es _ t hs ht
  | «离线» ps =>
    simp only [«格子».«作用», Option.bind_eq_bind, Option.pure_def, Option.bind_eq_some_iff, Option.some.injEq] at ha
    obtain ⟨H, _, t, ht, heq⟩ := ha
    subst f'
    exact «里层保持» «h操作» «h保持» un («格子».«场地».«待写» ps o bad) («h放货» ps o bad)
      _ t (.«离线» H) hs ht
  | «原样» b =>
    simp only [«格子».«作用», Option.bind_eq_bind, Option.pure_def, Option.bind_eq_some_iff, Option.some.injEq] at ha
    obtain ⟨t, ht, heq⟩ := ha
    subst f'
    exact «里层保持» «h操作» «h保持» un (f.«场地».«待写» o bad) («h放货» _ o bad)
      _ t b.«模型操作» hs ht

private theorem «格子依次保持»
    («h放货» : «命题».«格子层的放进单位守规矩»)
    («h操作» : «命题».«操作守物品格的规矩») («h保持» : «命题».«操作保持合规»)
    (un : «未定») (o : «格子».«接通先后») (bad : «通道» → Nat)
    (as : List «格子».«操作») (f f' : «格子».«状态») (hs : «良好» f.«模型»)
    (ha : «命题».«格子依次作用» un o bad f as = some f') : «良好» f'.«模型» := by
  induction as generalizing f with
  | nil =>
    simp only [«命题».«格子依次作用», Option.some.injEq] at ha
    subst f'
    exact hs
  | cons a as ih =>
    simp only [«命题».«格子依次作用», Option.bind_eq_some_iff] at ha
    obtain ⟨t, ht, ha⟩ := ha
    exact ih t («格子操作保持» «h放货» «h操作» «h保持» un o bad f t a hs ht) ha

/-- 据：判定顺序、级别、移动、通道、物品格

从空基地可达的格子状态货合规矩，位置允许的操作恰好有结果；
走一步不依赖未定先后，走得通时每个组都有级别。 -/
theorem «格子层的顶层»
    («h合规» : «命题».«格子层的历史合规») («h端口» : «命题».«格子层的历史端口数合»)
    («h结果» : «命题».«格子层做得了才有结果») («h放货» : «命题».«格子层的放进单位守规矩»)
    («h操作» : «命题».«操作守物品格的规矩») («h保持» : «命题».«操作保持合规»)
    («h一步» : «命题».«一步不看没定的先后») («h级别» : «命题».«每个组都有级别») :
    «命题».«格子层的顶层» := by
  intro un o bad f hf
  have hc := «h合规» un o bad f hf
  have hp := «h端口» un o bad f hf
  have «h货» : f.«模型».«货合规矩» := by
    obtain ⟨as, ha⟩ := hf
    have «h空» : «良好» «格子».«状态».«空».«模型» := by
      constructor
      · rfl
      · constructor
        · rfl
        · intro x; exact Nat.zero_le _
    exact («格子依次保持» «h放货» «h操作» «h保持» un o bad as _ f «h空» ha).2
  refine ⟨«h货», (fun a => «h结果» un o bad f a hf), ?_, ?_⟩
  · intro gs bs js us₁ us₂ hgs hbs hjs hu₁ hu₂
    exact «h一步» un (f.«场地».«待写» o bad) f.«模型» gs bs js us₁ us₂
      (by intro s s' u _; rfl) hc («历史».«端口数合_任一刻» _ hp _) hgs hbs hjs hu₁ hu₂
  · intro «h通»
    apply «h级别» f.«模型».«历史»
    simp only [«历史».«合法», Bool.and_eq_true]
    exact ⟨⟨hc, hp⟩, «h通»⟩

end Endfield.«证明»
