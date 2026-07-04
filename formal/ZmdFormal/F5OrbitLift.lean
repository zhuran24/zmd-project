/-
ZmdFormal.F5OrbitLift — F5 轨道提升 soundness 与去重坍缩陷阱（机器检查版）

对应设计稿:
  docs/research/p1_3_f5_orbit_lift_soundness_design_v2.md (v3)
  · 定理 1 前提 P-HOM(谓词对同组换位不变) —— 本文件作为假设 `hHom` 接入,
    模型侧成立性由设计稿的逐谓词审计表 + 266 实例机器验证 + 结构门承担。
  · 定理 2 的具名字面搬运核心:对具名 slot 的 whole-layout nogood,
    沿 P-preserving 重标搬运后仍 sound —— `labeled_orbit_lift`;
    带“同组置换”显式前提的包装陈述为 `labeled_orbit_lift_group_preserving`。
    完整匿名 multiset 包含 ⇒ cut sound 还需要有限群延拓引理(`anon_lift_sound`,待 mathlib)。
  · 匿名(presence/multiset)语义:pattern 实现要求**不同 slot 的单射指派**,
    该语义下实现关系沿保群单射搬运 —— `realizes_comp`;结合已给定的匿名 nogood 得
    "模掉重标后匹配即被排除" —— `nogood_mod_relabel`。
  · 定理 2 前提"禁重复 (group,pose/attach-key)"为什么是定理前提而非工程洁癖:
    multiplicity≥2 的 pattern 经 boolean presence 去重会**变强**;
    `dedup_collapse_can_false_reject` 给出抽象 P 下的机器检查误杀反例。
    `presence_key_alias_can_false_reject` 覆盖 v3 补强的 attach presence-key alias 风险。

抽象约定: Layout = Slot → Pose(mandatory 全指派);组用谓词 G : Slot → Prop;
谓词 P : Layout → Prop 是六谓词合取的抽象。
下一块砖(需 mathlib Fintype/Equiv 基建,见设计稿):anon_lift_sound ——
从单个具名代表 pattern 的 nogood 直接导出匿名 multiset nogood 的全局 soundness
(需要把部分单射延拓成全群置换,有限群语境)。
-/

namespace ZmdFormal.F5

/-- pattern(具名字面形态)被布局匹配:每条 (slot, pose) 字面都被 L 满足。 -/
def Matches {Slot Pose : Type} (L : Slot → Pose)
    (p : List (Slot × Pose)) : Prop :=
  ∀ sp ∈ p, L sp.1 = sp.2

/-- σ 不跨组:每个 slot 的 group id 在 σ 后保持不变。
    这只表达“保群”这一设计稿前提;置换性另用 `Function.Bijective σ`。 -/
def GroupPreserving {Slot Group : Type} (grp : Slot → Group)
    (σ : Slot → Slot) : Prop :=
  ∀ s, grp (σ s) = grp s

/-- 定理 2 的具名字面核心:设 σ 是 slot 变换,P-HOM 给出 P L → P (L ∘ σ)。
    若 pattern p 的 whole-layout nogood sound(匹配 p 的布局全不满足 P),
    则沿 σ 搬运后的 pattern(字面 slot 各取 σ)nogood 也 sound。
    注意:此方向甚至不需要 σ 可逆——单向 P-HOM 已足;实际系统中 σ 取
    同组置换,P-HOM 双向成立。 -/
theorem labeled_orbit_lift {Slot Pose : Type}
    (P : (Slot → Pose) → Prop)
    (σ : Slot → Slot)
    (hHom : ∀ L, P L → P (fun s => L (σ s)))
    (p : List (Slot × Pose))
    (hNogood : ∀ L, Matches L p → ¬ P L) :
    ∀ L, Matches L (p.map (fun sp => (σ sp.1, sp.2))) → ¬ P L := by
  intro L hM hPL
  refine hNogood (fun s => L (σ s)) ?_ (hHom L hPL)
  intro sp hsp
  have hmem : (σ sp.1, sp.2) ∈ p.map (fun sp => (σ sp.1, sp.2)) :=
    List.mem_map.mpr ⟨sp, hsp, rfl⟩
  exact hM (σ sp.1, sp.2) hmem

/-- 带设计稿“保群置换”显式前提的包装版。
    证明仍只消耗 `hHom`:保群/双射前提的作用在前提审计层,用于证明 `hHom`
    以及从匿名 multiset 匹配构造 σ;这里把它们写进陈述,避免把核心引理误读为
    “任意函数 σ 已经是 F5 群作用”。 -/
theorem labeled_orbit_lift_group_preserving {Slot Pose Group : Type}
    (grp : Slot → Group)
    (P : (Slot → Pose) → Prop)
    (σ τ : Slot → Slot)
    (_hInv : (∀ s, τ (σ s) = s) ∧ (∀ s, σ (τ s) = s))
    (_hGroup : GroupPreserving grp σ)
    (hHom : ∀ L, P L → P (fun s => L (σ s)))
    (p : List (Slot × Pose))
    (hNogood : ∀ L, Matches L p → ¬ P L) :
    ∀ L, Matches L (p.map (fun sp => (σ sp.1, sp.2))) → ¬ P L := by
  exact labeled_orbit_lift P σ hHom p hNogood

/-- 匿名 pattern(多重集形态,列表带重数)在组 G 内被布局实现:
    存在**单射** f 把 pattern 的每个位置指派到互不相同的组内 slot,
    且各 slot 上的 pose 与 pattern 一致。单射 = "同一字面不重用同一 slot",
    正是 F5 multiset evaluator 语义的数学形态。 -/
def Realizes {Slot Pose : Type} (L : Slot → Pose) (G : Slot → Prop)
    (p : List Pose) : Prop :=
  ∃ f : Fin p.length → Slot,
    Function.Injective f ∧ (∀ i, G (f i)) ∧ ∀ i, L (f i) = p.get i

/-- attach/master presence key 层的匿名实现关系。
    当 `key` 不是单射时,不同 pose_id 可在 master presence 层 alias。 -/
def RealizesKey {Slot Pose Key : Type} (L : Slot → Pose) (G : Slot → Prop)
    (key : Pose → Key) (p : List Key) : Prop :=
  ∃ f : Fin p.length → Slot,
    Function.Injective f ∧ (∀ i, G (f i)) ∧ ∀ i, key (L (f i)) = p.get i

/-- 实现关系沿保群单射变换搬运:若 L ∘ σ 实现 p,则 L 实现 p。
    (σ 单射且把组映进组;实际系统中 σ 是同组置换,自动满足。) -/
theorem realizes_comp {Slot Pose : Type}
    (L : Slot → Pose) (G : Slot → Prop) (p : List Pose)
    (σ : Slot → Slot)
    (hInj : Function.Injective σ)
    (hG : ∀ s, G s → G (σ s))
    (hR : Realizes (fun s => L (σ s)) G p) :
    Realizes L G p := by
  obtain ⟨f, hf, hfG, hfL⟩ := hR
  exact ⟨fun i => σ (f i),
    fun i j h => hf (hInj h),
    fun i => hG (f i) (hfG i),
    fun i => hfL i⟩

/-- 模掉重标的排除:匿名 nogood 成立时,只要 L 的某个 σ-重标视图实现了
    pattern(evaluator 允许换位匹配),L 本身即被排除——用到 P-HOM 单向。 -/
theorem nogood_mod_relabel {Slot Pose : Type}
    (P : (Slot → Pose) → Prop) (G : Slot → Prop) (p : List Pose)
    (σ : Slot → Slot) (L : Slot → Pose)
    (hNogood : ∀ L', Realizes L' G p → ¬ P L')
    (hHomL : P L → P (fun s => L (σ s)))
    (hR : Realizes (fun s => L (σ s)) G p) :
    ¬ P L := by
  intro hPL
  exact hNogood (fun s => L (σ s)) hR (hHomL hPL)

/-! ### 去重坍缩陷阱(设计稿定理 2 前提"禁重复"的机器反例)

pattern [v, v](重数 2)要求**两个不同** slot 都摆 v;
boolean presence 去重后变成 [v],只要求**存在一个** slot 摆 v。
下面构造具体布局:恰好一个 slot 摆 v —— 它实现 [v] 但不实现 [v, v]。
故把 [v,v] 的 nogood 按 [v] 施加会误杀该布局:去重 = 换成更强的 cut,
soundness 论证不再覆盖。 -/

/-- 两个 slot(Bool 编码),pose 也用 Bool;布局 = id(一个摆 true 一个摆 false)。 -/
theorem dedup_collapse_strengthens :
    ∃ (L : Bool → Bool),
      Realizes L (fun _ => True) [true] ∧
      ¬ Realizes L (fun _ => True) [true, true] := by
  refine ⟨id, ⟨fun _ => true, ?_, ?_, ?_⟩, ?_⟩
  · -- 单射:Fin 1 只有一个元素
    intro i j _
    apply Fin.ext
    have hi := i.isLt
    have hj := j.isLt
    simp only [List.length_cons, List.length_nil] at hi hj
    omega
  · intro _
    trivial
  · -- L (f i) = [true].get i:两边都是 true
    intro i
    have h1 : i.val = 0 := by
      have h := i.isLt
      simp only [List.length_cons, List.length_nil] at h
      omega
    have h2 : i = ⟨0, by decide⟩ := Fin.ext h1
    rw [h2]
    rfl
  · -- [true, true] 不可实现:两个位置都要摆 true,但只有一个 slot 摆着 true
    rintro ⟨f, hInj, -, hL⟩
    have h0 : id (f ⟨0, by decide⟩) = [true, true].get ⟨0, by decide⟩ :=
      hL ⟨0, by decide⟩
    have h1 : id (f ⟨1, by decide⟩) = [true, true].get ⟨1, by decide⟩ :=
      hL ⟨1, by decide⟩
    have e0 : f ⟨0, by decide⟩ = true := h0
    have e1 : f ⟨1, by decide⟩ = true := h1
    have hf : f ⟨0, by decide⟩ = f ⟨1, by decide⟩ := by rw [e0, e1]
    have h01 := hInj hf
    have hv : (0 : Nat) = 1 := congrArg Fin.val h01
    exact absurd hv (by decide)

/-- 更强的误杀形态:存在一个抽象合法性谓词 P,使 [v,v] 的 nogood 是 sound 的,
    但把它 presence 去重成 [v] 会排除一个满足 P 的布局。 -/
theorem dedup_collapse_can_false_reject :
    ∃ (L : Bool → Bool) (P : (Bool → Bool) → Prop),
      (∀ L', Realizes L' (fun _ => True) [true, true] → ¬ P L') ∧
      Realizes L (fun _ => True) [true] ∧
      P L := by
  obtain ⟨L, hOne, hNotTwo⟩ := dedup_collapse_strengthens
  refine ⟨L, (fun L' => ¬ Realizes L' (fun _ => True) [true, true]), ?_, hOne, hNotTwo⟩
  intro L' hR hNotR
  exact hNotR hR

/-- presence-key alias 的语义坍缩:两个不同 pose 可映到同一个 attach key。
    下面布局触发去重后的单 key presence,但并不实现原始 [true,false] pose pattern。 -/
theorem presence_key_alias_collapse_strengthens :
    ∃ (L : Bool → Bool) (key : Bool → Unit),
      key true = key false ∧
      RealizesKey L (fun _ => True) key [key true] ∧
      ¬ Realizes L (fun _ => True) [true, false] := by
  refine ⟨(fun _ => true), (fun _ => ()), rfl, ?_, ?_⟩
  · refine ⟨fun _ => true, ?_, ?_, ?_⟩
    · intro i j _
      apply Fin.ext
      have hi := i.isLt
      have hj := j.isLt
      simp only [List.length_cons, List.length_nil] at hi hj
      omega
    · intro _
      trivial
    · intro _
      exact Subsingleton.elim _ _
  · rintro ⟨f, -, -, hL⟩
    have hFalse : true = false := by
      simpa using hL ⟨1, by decide⟩
    cases hFalse

/-- presence-key alias 的误杀形态:原始 [true,false] nogood 可以是 sound 的,
    但 alias 后的单 key presence 会排除满足 P 的布局。 -/
theorem presence_key_alias_can_false_reject :
    ∃ (L : Bool → Bool) (key : Bool → Unit) (P : (Bool → Bool) → Prop),
      (∀ L', Realizes L' (fun _ => True) [true, false] → ¬ P L') ∧
      RealizesKey L (fun _ => True) key [key true] ∧
      P L := by
  obtain ⟨L, key, _, hKey, hNotOriginal⟩ := presence_key_alias_collapse_strengthens
  refine ⟨L, key, (fun L' => ¬ Realizes L' (fun _ => True) [true, false]), ?_, hKey, hNotOriginal⟩
  intro L' hR hNotR
  exact hNotR hR

end ZmdFormal.F5
