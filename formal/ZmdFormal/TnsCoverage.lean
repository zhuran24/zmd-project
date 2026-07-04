/-
ZmdFormal.TnsCoverage — terminal 无解证书的覆盖论证（机器检查版）

对应设计稿:
  docs/research/terminal_no_solution_evidence_contract_design_v2.md (v3)
  · 逐维反单调引理(设计稿把它作为"候选 (w,h) 不可行 ⇒ 一切逐维更大的候选不可行"
    的模型侧事实;本文件不重证模型侧,把它作为 `UpwardClosed` 假设接入——
    模型侧成立性由设计稿的 ghost-use inventory / master"缩小不收紧"审计承担)
  · 最小覆盖坍缩(标准域 {(w,h) | 6≤w≤70, 6≤h≤70} 坍缩为单点 (6,6))
  · 一般域最小反链非单点(终审实验发现 3~11 元) —— 本文件的
    `exists_minimal_below` + `all_bad_of_minimal_bad` 恰好同时覆盖两种情形:
    覆盖集 = 域的极小元集合,标准域时它恰是 {(6,6)}。

坐标约定: 候选用两个自然数 (w,h) 表示,序 = 逐维 ≤(乘积序)。
`bad w h` 读作"候选 (w,h) 不可行(INFEASIBLE)"。
-/

namespace ZmdFormal.Tns

/-- 逐维反单调(不可行向上封闭):小的不可行 ⇒ 逐维更大的也不可行。
    这是设计稿承重引理的抽象形态,模型侧成立性在设计稿义务清单里。 -/
def UpwardClosed (bad : Nat → Nat → Prop) : Prop :=
  ∀ a b a' b', a ≤ a' → b ≤ b' → bad a b → bad a' b'

/-- 域 D 的极小元:D 内没有(乘积序下)严格更小的元素。 -/
def MinimalIn (D : Nat → Nat → Prop) (a b : Nat) : Prop :=
  D a b ∧ ∀ c d, D c d → c ≤ a → d ≤ b → c = a ∧ d = b

/-- 一般覆盖引理:若 bad 向上封闭,覆盖集 C 全 bad,且域内每点下方
    都有 C 中元素(∃ c∈C, c ≤ x 逐维),则域全 bad。
    这是"无解证书只需覆盖最小反链"的骨架。 -/
theorem all_bad_of_cover
    (D C bad : Nat → Nat → Prop)
    (hUp : UpwardClosed bad)
    (hCbad : ∀ a b, C a b → bad a b)
    (hCover : ∀ a b, D a b → ∃ c d, C c d ∧ c ≤ a ∧ d ≤ b) :
    ∀ a b, D a b → bad a b := by
  intro a b hD
  obtain ⟨c, d, hC, hca, hdb⟩ := hCover a b hD
  exact hUp c d a b hca hdb (hCbad c d hC)

/-- 任何 ℕ×ℕ 子域中,每个元素下方都存在域内极小元(乘积序良基性)。
    对 a+b 做强归纳。 -/
theorem exists_minimal_below (D : Nat → Nat → Prop) :
    ∀ n a b, a + b ≤ n → D a b →
      ∃ a' b', MinimalIn D a' b' ∧ a' ≤ a ∧ b' ≤ b := by
  intro n
  induction n with
  | zero =>
    intro a b hab hD
    refine ⟨a, b, ⟨hD, ?_⟩, Nat.le_refl _, Nat.le_refl _⟩
    intro c d _ hc hd
    omega
  | succ n ih =>
    intro a b hab hD
    by_cases h : ∃ c d, D c d ∧ c ≤ a ∧ d ≤ b ∧ (c ≠ a ∨ d ≠ b)
    · obtain ⟨c, d, hDcd, hca, hdb, hne⟩ := h
      have hlt : c + d ≤ n := by
        rcases hne with h1 | h1 <;> omega
      obtain ⟨a', b', hmin, ha', hb'⟩ := ih c d hlt hDcd
      exact ⟨a', b', hmin, by omega, by omega⟩
    · refine ⟨a, b, ⟨hD, ?_⟩, Nat.le_refl _, Nat.le_refl _⟩
      intro c d hDcd hca hdb
      by_cases hc : c = a
      · by_cases hd : d = b
        · exact ⟨hc, hd⟩
        · exact absurd ⟨c, d, hDcd, hca, hdb, Or.inr hd⟩ h
      · exact absurd ⟨c, d, hDcd, hca, hdb, Or.inl hc⟩ h

/-- 主定理(一般域形态):bad 向上封闭且域的全部极小元 bad ⇒ 域全 bad。
    覆盖证书 = 极小元集合(一般域上是反链,可多元;终审实验 3~11 元)。 -/
theorem all_bad_of_minimal_bad
    (D bad : Nat → Nat → Prop)
    (hUp : UpwardClosed bad)
    (hMinBad : ∀ a b, MinimalIn D a b → bad a b) :
    ∀ a b, D a b → bad a b := by
  intro a b hD
  obtain ⟨a', b', hmin, ha', hb'⟩ :=
    exists_minimal_below D (a + b) a b (Nat.le_refl _) hD
  exact hUp a' b' a b ha' hb' (hMinBad a' b' hmin)

/-- 标准生产域:w,h ∈ [6,70](min_side=6 admissibility,70×70 网格)。 -/
def StdDomain (a b : Nat) : Prop :=
  6 ≤ a ∧ a ≤ 70 ∧ 6 ≤ b ∧ b ≤ 70

/-- 标准域坍缩:标准域上,(6,6) 一个候选的不可行 + 反单调 ⇒ 全域不可行。
    这就是设计稿"O(1) 大小无解证书"的数学内核。 -/
theorem std_domain_collapse
    (bad : Nat → Nat → Prop)
    (hUp : UpwardClosed bad)
    (h66 : bad 6 6) :
    ∀ a b, StdDomain a b → bad a b := by
  intro a b hD
  exact hUp 6 6 a b hD.1 hD.2.2.1 h66

/-- 一致性 sanity:(6,6) 本身在标准域内且是其极小元
    (机器确认"标准域的最小反链 = 单点"这半句)。 -/
theorem std_domain_minimal_66 : MinimalIn StdDomain 6 6 := by
  constructor
  · exact ⟨Nat.le_refl _, by omega, Nat.le_refl _, by omega⟩
  · intro c d hD hc hd
    have := hD.1
    have := hD.2.2.1
    omega

end ZmdFormal.Tns
