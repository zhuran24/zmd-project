结论先放前面：9 条里我认为 **3 条忠实、3 条 BLOCK、3 条 CONCERN**。最危险的不是 Lean 证明本身，而是有几处“证明了旁边那只猫，却把牌子挂成老虎”。沙盒里没有 `lean/lake`，所以以下补丁段均标为 **未经本地编译**；语法按 Lean 4 / mathlib 风格写，供你们本地核实。

| 定理                                  |          判定 | 根因一句话                                                                                        | 最小反例 / 触发面                                                                                                          | 影响面                                                |
| ----------------------------------- | ----------: | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| `f5_compound_safety`                | **CONCERN** | 正向引理吃的是 `hcut_sound` 逐点 sound，不表达“orbit cut 删整类”；结论也丢了“幸存代表与 `s₀` 同类”                        | 若实现层误以为“从某点 lift 出来的 cut”天然给出 `hcut_sound`，Lean 定理不会检查 G-不变/整类删除桥                                                   | 不能审计 F5 lift 机制本身，只能审计已给定 pointwise-sound cut 后的组合 |
| `f5_compound_needs_phom`            |   **BLOCK** | 原文点名陷阱是“非 G-不变 cut 读 slot 身份”，Lean 反例却是“P-HOM 破缺 + G-不变全删 cut”                               | `Bool` 全关系轨道，`Feasible := True` 保持 P-HOM，`Sel := (= true)`，`Cut := (= true)` 非 G-不变，合法类被删光                          | 红测会打错靶，无法捕获 slot-sensitive cut                     |
| `frontier_prune_dominates`          | **CONCERN** | 严格幸存 `<` 与“lex 不优于 witness 被跳过”匹配；但 theorem/docstring 没钉死 witness 是当前谓词下 CERTIFIED           | 若 `w₀` 只是旧 incumbent 或未认证，支配关系仍为真，但剪枝不 sound                                                                        | 可作为纯序引理，不能单独作为剪枝安全证书                               |
| `frontier_prune_preserves_max`      |   **BLOCK** | 只保最大值，不保当前谓词下的 certified argmax witness；docstring “搜索问题的答案”过强                                | `F={A,B}`, `value A = value B = 0`, `w₀=A`, 当前 `Certified A=False`, `Certified B=True`；幸存集只有 `A`，值没变但可发布 witness 丢了 | 可导致“值正确但无证书/错证书”的虚假安全感                             |
| `frontier_prune_preserves_max_lex`  |   **BLOCK** | 继承上条；另未表达迁移规则 §3c 的“谓词变化时 dominance skip 不得继承”                                               | 旧 `A(100)` certified 剪掉 `B(90)`；新谓词下 `A` 失败、`B` 可行，继承 skip 丢新最优解                                                    | P7/schema 升级时最危险，正是设计稿点名 BLOCK-3                   |
| `eq_key_violated_iff`               |      **忠实** | 在 `S ⊆ U` 且 `A ⊆ U` 的完整赋值空间内，PB 等式键违反条件确实等价于 `A = S`                                         | 若 `A ⊄ U`，例如 `U={false}, S={false}, A={false,true}`，def 可为真但 `A≠S`； theorem 已用 `hAU` 排除                             | theorem 忠实；`EqKeyViolated` def 本身建议硬化              |
| `tp7s_eq_key_sound`                 |      **忠实** | `∀ A ⊆ U` 正是 Finset 版完整 0/1 赋值空间；违反键推出 `A=S`，由 `¬Feasible S` 得 sound                         | 外部变量必须被纳入 `U`，否则不是完整键                                                                                               | 可支撑“不产生 false-INFEASIBLE”                          |
| `tp7s_eq_key_no_overcut`            |      **忠实** | 对 `A ⊆ U` 的真超集 `S ⊂ A`，等式键不触发，贴合“要禁超集需独立证明”                                                  | 同上，`A` 必须在全集内                                                                                                       | 可支撑“等式键不过切”                                        |
| `tp7s_selected_set_nogood_overcuts` | **CONCERN** | 抽象形状对，但 docstring 声称“半容量路 + 并行路”的机器版；实际只是 `card ≥ 2`，没有容量/需求语义，也没命名 selected-set nogood 违反条件 | `S={false}`, `A={false,true}`, `Feasible X := 2 ≤ X.card` 是形状相似，不是路容量模型                                             | 作为反例足够反驳“只禁选中集总是 sound”，但不足以称为原文玩具结构的忠实形式化         |

---

## 主要发现与修复补丁

### 1. `f5_compound_safety`：CONCERN

根因：原文的骨架是“序保代表元 × 轨道 cut 删整类”。当前 theorem 实际骨架是“序保代表元 × cut 已经逐点 sound”。这不是错，但它绕过了最该审的那座桥：从 orbit lift / G-不变删除到 pointwise sound。更细一点，结论没有保留 `r` 与输入可行点 `s₀` 同轨道，导致“未被 cut 的类，其序代表仍存活”的类局部信息从 theorem statement 中蒸发。

最小反例不是反驳 theorem，而是反驳“它足以审 orbit cut 机制”：`Bool` 全关系，`Feasible := True`，`Sel := (= true)`，`Cut := (= true)`。这是非 G-不变 cut，组合后没有幸存可行代表；当前 theorem 只会说你没有 `hcut_sound`，但不会帮你定位缺的是“cut 删整类/轨道 soundness”。

影响面：如果这条被当作 F5 复合安全的唯一机器接口，实施层可能把“某个 base 点不可行”误当作“lift 后逐点 sound”，Lean 不会拦。

**补丁段，未经本地编译。** 建议把 theorem 结论改成 class-local，并把 cut 前提改为“被删类整类不可行”的证据，而不是裸 pointwise sound。

```lean
/-- 复合安全引理（F5 v1 §2.4 的忠实版本）：
代表选择给每个轨道至少一个序代表；orbit cut 的证据必须覆盖整类：
一旦某点被 cut，则其整个轨道均被 cut 且不可行。于是任意可行点 `s₀`
所在轨道都有一个同轨道、满足序、未被 cut、仍可行的代表。 -/
theorem f5_compound_safety
    (orbit : Setoid σ) (Feasible : σ → Prop) (Sel Cut : σ → Prop)
    (hPHOM : ∀ {s t : σ}, orbit.Rel s t → (Feasible s ↔ Feasible t))
    (hSel : ∀ s : σ, ∃ r : σ, orbit.Rel s r ∧ Sel r)
    (hCutClass :
      ∀ c : σ, Cut c → ∀ t : σ, orbit.Rel c t → Cut t ∧ ¬ Feasible t)
    {s₀ : σ} (hs₀ : Feasible s₀) :
    ∃ r : σ, orbit.Rel s₀ r ∧ Sel r ∧ ¬ Cut r ∧ Feasible r := by
  obtain ⟨r, hsr, hsel⟩ := hSel s₀
  have hfr : Feasible r := (hPHOM hsr).mp hs₀
  refine ⟨r, hsr, hsel, ?_, hfr⟩
  intro hcut
  exact (hCutClass r hcut r (orbit.iseqv.refl r)).2 hfr
```

如果你们希望保留当前弱化发现，也可以把现 theorem 改名为：

```lean
f5_compound_safety_from_pointwise_sound
```

并在 docstring 中明说：“这不是 orbit-lift soundness；它只消费已经复验出的 pointwise-sound cut。”

---

### 2. `f5_compound_needs_phom`：BLOCK

根因：这个 theorem 的名字、docstring、构造三者都和原文红测不对齐。

原文说的是：“若未来引入非 G-不变 cut，即读 slot 身份的 cut，此引理失效。” 当前构造却是：

```lean
Feasible s := s = true
Sel s := s = true
Cut _ := True
```

也就是 Feasible 读标签、P-HOM 破缺、cut 反而是全关系下 G-不变的整类删除。它证明的是“没有 P-HOM 时，从一个不可行点 lift 到整类会误删可行轨道 mate”，不是“非 G-不变 cut + order 删除合法类”。另外 theorem statement 只保留了 `(∃ r, Sel r)`，没有保留正向 theorem 的每类代表选择前提。

最小忠实红测如下：`Bool` 全轨道，`Feasible := True`，所以 P-HOM 完全成立；`Sel := (= true)`，order 只留 `true`；`Cut := (= true)`，slot-sensitive cut 只删代表元，不删同轨道的 `false`。于是原空间有可行点 `false`，但 order 删掉 `false`，cut 删掉 `true`，组合后 false-INFEASIBLE。

影响面：现在的红测会把审查注意力引向 P-HOM，而不是原文真正禁止的 slot-sensitive cut。实现若引入非 G-不变 cut，这条机器反例不会叫。

**补丁段，未经本地编译。** 建议重命名；旧名 `needs_phom` 不宜继续使用。

```lean
/-- 反方向陷阱（F5 v1 §2.4 点名红测的忠实版本）：
即使 P-HOM 成立、代表选择完备，只要 cut 读 slot 身份而非 G-不变，
order 可以删掉同轨道的非代表可行点，而 cut 删掉唯一代表，组合产生
false-INFEASIBLE。 -/
theorem f5_compound_needs_cut_invariance :
    ∃ (Feasible Sel Cut : Bool → Prop) (equiv : Bool → Bool → Prop),
      (∀ {s t : Bool}, equiv s t → (Feasible s ↔ Feasible t)) ∧
      (∀ s : Bool, ∃ r : Bool, equiv s r ∧ Sel r) ∧
      (∃ s t : Bool, equiv s t ∧ Cut s ∧ ¬ Cut t) ∧
      (∃ s : Bool, Feasible s) ∧
      ¬ ∃ r : Bool, Sel r ∧ ¬ Cut r ∧ Feasible r := by
  refine ⟨
    (fun _ => True),
    (fun b => b = true),
    (fun b => b = true),
    (fun _ _ => True),
    ?_, ?_, ?_, ?_, ?_
  ⟩
  · intro s t _
    exact iff_of_true trivial trivial
  · intro s
    exact ⟨true, trivial, rfl⟩
  · exact ⟨true, false, trivial, rfl, by decide⟩
  · exact ⟨false, trivial⟩
  · rintro ⟨r, hsel, hnotcut, _hfeas⟩
    exact hnotcut hsel
```

模块头也要改：不能再写“v1 点名的反方向陷阱 = 无 P-HOM”。建议改成“非 G-不变 cut 的机器反例；无 P-HOM 是另一个独立边界，若保留需另列。”

---

### 3. `frontier_prune_dominates`：CONCERN

严格比较方向是对的：幸存集是 `value w₀ < value c'`，所以 `value c ≤ value w₀` 的候选被跳过；相等值候选被跳过，但 `w₀` 保留。这和“lex 不优于 witness 的候选被跳过”一致。

问题是它只是纯序支配 lemma。它没有表达“`w₀` 是当前谓词下的 CERTIFIED witness”，也没有表达“谓词没有迁移/收紧”。作为底层 lemma 可以，但 docstring 若被理解成剪枝 soundness 就过宽。

最小反例同下一条：`w₀` 不是当前可行 witness 时，数值支配成立，剪枝安全不成立。

影响面：单独拿它给 search skip 背书，会把“值支配”误当作“证书支配”。

**补丁段，未经本地编译。** 若保留原 theorem，至少 docstring 要收窄，并新增 witness 级 theorem。

```lean
/-- 纯序支配 lemma，仅适用于固定候选宇宙和已经另外证明 `w₀`
是当前谓词下 CERTIFIED witness 的场合。本 theorem 本身不证明剪枝 sound，
也不得跨谓词迁移使用。 -/
theorem frontier_prune_dominates
    (F : Finset ι) (value : ι → β) {w₀ : ι} (_hw₀ : w₀ ∈ F) :
    ∀ c ∈ F, ∃ c' ∈ F.filter (fun c' => value w₀ < value c') ∪ {w₀},
      value c ≤ value c' := by
  intro c hc
  by_cases h : value c ≤ value w₀
  · exact ⟨w₀, Finset.mem_union_right _ (Finset.mem_singleton_self w₀), h⟩
  · exact ⟨c, Finset.mem_union_left _ (Finset.mem_filter.mpr ⟨hc, not_le.mp h⟩),
      le_refl _⟩
```

---

### 4. `frontier_prune_preserves_max`：BLOCK

根因：`Finset.sup'` 只保最大值，不保“当前谓词下存在可发布的 argmax witness”。设计稿说“手中已有 CERTIFIED witness”，并且迁移规则严禁继承依赖旧 incumbent 的 skip。当前 theorem 没有 `Certified` / `Feasible` 参数，docstring 却说“剪枝不改变搜索问题的答案”，这就越界了。

最小反例：

```text
F = {A, B}
value A = value B = 0
w₀ = A
当前 Certified A = False
当前 Certified B = True
```

幸存集是 `{A}`，最大值仍是 0；但唯一当前可发布 witness `B` 被剪掉了。值没变，搜索答案坏了。

影响面：在 schema/P7 迁移、证书失效、或 incumbent 状态未复验时，会出现“objective value 证明还在，发布 witness 已经没了”的错封口。

**补丁段，未经本地编译。** 建议新增或替换成 certified argmax witness 版本。

```lean
/-- 剪枝保当前谓词下的最优 witness，而不仅是保最大值。
前提显式要求 `w₀` 是当前谓词下的 certified witness；
结论给出幸存集中仍有一个 certified argmax。 -/
theorem frontier_prune_preserves_certified_argmax
    (F : Finset ι) (value : ι → β) (Certified : ι → Prop)
    {w₀ : ι} (hw₀ : w₀ ∈ F) (hw₀cert : Certified w₀)
    (hopt :
      ∃ c ∈ F, Certified c ∧
        ∀ d ∈ F, Certified d → value d ≤ value c) :
    ∃ c' ∈ F.filter (fun c' => value w₀ < value c') ∪ {w₀},
      Certified c' ∧
        ∀ d ∈ F, Certified d → value d ≤ value c' := by
  obtain ⟨c, hcF, hcCert, hcMax⟩ := hopt
  by_cases hle : value c ≤ value w₀
  · refine ⟨w₀, Finset.mem_union_right _ (Finset.mem_singleton_self w₀),
      hw₀cert, ?_⟩
    intro d hdF hdCert
    exact le_trans (hcMax d hdF hdCert) hle
  · refine ⟨c,
      Finset.mem_union_left _ (Finset.mem_filter.mpr ⟨hcF, not_le.mp hle⟩),
      hcCert, hcMax⟩
```

---

### 5. `frontier_prune_preserves_max_lex`：BLOCK

根因：这是上一条的 lex 特例，所以继承“只保值、不保证书 witness”的问题。它还尤其容易被误用到设计稿 §3c 的迁移场景：旧谓词下的 frontier dominance skip 不能继承到新谓词。当前 theorem 名字和 docstring 没提示“固定谓词、当前 CERTIFIED witness”。

最小反例就是设计稿原文那颗地雷：

```text
旧谓词 P:
  A(area=100) certified
  B(area=90) 被 A dominance skip

新谓词 P′ 收紧:
  A 吞吐失败
  B 可行

若继承旧 skip，则 B 丢失，新谓词最优解丢失。
```

影响面：schema 升版、P7 引入、旧 incumbent 降级 `P7_PENDING` 时，若这条 theorem 被当成“lex 剪枝记录可迁移”的依据，会直接违反设计稿 BLOCK-3。

**补丁段，未经本地编译。** lex 版本应依赖 certified argmax theorem；另建议加入一个不可迁移反例，给审计钩子。

```lean
/-- 项目目标 `max_lex(area, min_side)` 的 fixed-predicate / certified-witness 版本。 -/
theorem frontier_prune_preserves_certified_argmax_lex {ι : Type*} [DecidableEq ι]
    (F : Finset ι) (area minSide : ι → ℕ) (Certified : ι → Prop)
    {w₀ : ι} (hw₀ : w₀ ∈ F) (hw₀cert : Certified w₀)
    (hopt :
      ∃ c ∈ F, Certified c ∧
        ∀ d ∈ F, Certified d →
          toLex (area d, minSide d) ≤ toLex (area c, minSide c)) :
    ∃ c' ∈ F.filter (fun c' =>
        toLex (area w₀, minSide w₀) < toLex (area c', minSide c')) ∪ {w₀},
      Certified c' ∧
        ∀ d ∈ F, Certified d →
          toLex (area d, minSide d) ≤ toLex (area c', minSide c') :=
  frontier_prune_preserves_certified_argmax
    F (fun c => toLex (area c, minSide c)) Certified hw₀ hw₀cert hopt

/-- 迁移红测：旧谓词下由 incumbent 触发的 dominance skip 不得继承到收紧后的新谓词。 -/
theorem frontier_prune_not_migration_safe :
    ∃ (F : Finset Bool) (value : Bool → Nat)
      (Old New : Bool → Prop) (w₀ : Bool),
      w₀ ∈ F ∧ Old w₀ ∧
      (∀ x, New x → Old x) ∧
      (∃ x ∈ F, New x) ∧
      (∀ x ∈ F.filter (fun c => value w₀ < value c) ∪ {w₀}, ¬ New x) := by
  refine ⟨
    {false, true},
    (fun b => if b then 100 else 90),
    (fun _ => True),
    (fun b => b = false),
    true,
    ?_
  ⟩
  decide
```

---

### 6. `eq_key_violated_iff`：忠实，但建议硬化 `EqKeyViolated`

这条 theorem 本身是忠实的：在 `S ⊆ U`、`A ⊆ U` 下，违反完整等式键正好是 `A = S`。这和 PB 约束

```text
Σ_{x∈S1}(1−x) + Σ_{x∈S0}x ≥ 1
```

的违反条件一致：所有 `S1` 为真，所有 `S0` 为假。

但 `EqKeyViolated` def 本身没有把 `A ⊆ U` 烙进去。于是可构造 foot-gun：

```text
U = {false}
S = {false}
A = {false, true}
```

`EqKeyViolated U S A` 成立，但 `A ≠ S`。theorem 用 `hAU` 排除了它，所以 theorem 忠实；只是 def 若被别处直接使用，容易漏前提。

**硬化补丁，未经本地编译。** 可选，但我建议做。

```lean
/-- 完整 0/1 赋值空间：assignment `A` 只能给全集 `U` 内变量赋真；
缺席即假。 -/
def Assignment (U A : Finset V) : Prop :=
  A ⊆ U

/-- 完整等式键的违反条件，内置全集约束，避免 `A` 携带 key 外变量。 -/
def EqKeyViolated (U S A : Finset V) : Prop :=
  A ⊆ U ∧ S ⊆ U ∧
  (∀ x ∈ S, x ∈ A) ∧
  (∀ x ∈ U \ S, x ∉ A)

/-- 等式键排除集刻画：完整赋值空间内，违反键当且仅当 `A = S`。 -/
theorem eq_key_violated_iff {U S A : Finset V} :
    EqKeyViolated U S A ↔ S ⊆ U ∧ A = S := by
  constructor
  · rintro ⟨hAU, hSU, h1, h0⟩
    refine ⟨hSU, ?_⟩
    ext x
    constructor
    · intro hxA
      by_contra hxS
      exact h0 x (Finset.mem_sdiff.mpr ⟨hAU hxA, hxS⟩) hxA
    · exact h1 x
  · rintro ⟨hSU, rfl⟩
    exact ⟨hSU, hSU, fun _ hx => hx,
      fun x hx => (Finset.mem_sdiff.mp hx).2⟩
```

配套替换：

```lean
/-- 等式键 sound：Farkas 证明了赋值 S 不可行 ⇒ 等式键排除的全部赋值不可行。 -/
theorem tp7s_eq_key_sound {U S : Finset V}
    (Feasible : Finset V → Prop) (hS : ¬ Feasible S) :
    ∀ A, EqKeyViolated U S A → ¬ Feasible A := by
  intro A hviol
  have hEq : A = S := (eq_key_violated_iff.mp hviol).2
  rwa [hEq]

/-- 等式键不过切：真超集不触发等式键。 -/
theorem tp7s_eq_key_no_overcut {U S A : Finset V}
    (hss : S ⊂ A) : ¬ EqKeyViolated U S A := by
  intro hviol
  have hEq : A = S := (eq_key_violated_iff.mp hviol).2
  exact hss.ne hEq.symm
```

如果你们不想改 def，则至少给 `EqKeyViolated` docstring 加一句：“本 def 只应在 `A ⊆ U`、`S ⊆ U` 的 assignment 语境中使用。”

---

### 7. `tp7s_eq_key_sound`：忠实

这条与原文“完整 0/1 离散赋值的等式键”是对齐的。Finset 表示中，`A ⊆ U` 就是完整布尔赋值：`x ∈ A` 表示真，`x ∈ U \ A` 表示假。无需额外“每个变量都有明确 0/1”字段。

需要注意的只是：原文的 `U` 包括 binding choice、generic slot assignment、route use-vars 全集以及 graph 语法版本。Lean theorem 抽象为任意 `Finset V`，这可以接受，但调用方必须证明实际 key universe 真是完整全集。

---

### 8. `tp7s_eq_key_no_overcut`：忠实

这条正好对应“真超集不触发等式键；要禁超集必须另有 independent exact-rational proof”。前提 `S ⊂ A` 加 `A ⊆ U` 排除了全集外 junk，结论是正确边界。

---

### 9. `tp7s_selected_set_nogood_overcuts`：CONCERN

根因：当前 theorem 的抽象反例足以说明“只禁选中集”不 sound，因为它给出：

```lean
¬ Feasible S ∧ S ⊆ A ∧ Feasible A
```

而 selected-set nogood `∨_{x∈S} ¬x` 正是会拒绝所有 `S ⊆ A` 的赋值。但 docstring 更强，声称这是“一条半容量路不够、加并行路就够”的机器版。实际 `Feasible X := 2 ≤ X.card` 没有 route、容量、需求，也没有显式 selected-set nogood violation 谓词。作为“形状反例”可以；作为“原文玩具例结构”的忠实形式化还差一层。

最小反例就是当前构造本身：

```text
S = {false}
A = {false, true}
Feasible X := 2 ≤ X.card
```

它表达的是“一个元素不够，两个元素够”，不是“半容量路 + 并行路”。

影响面：审计文档若把它当作 TP7-S 容量玩具的机器证据，会高估覆盖面；不过它仍能反驳 selected-set nogood 的通用 soundness。

**补丁段，未经本地编译。** 建议至少把 selected-set nogood violation 和容量/需求结构显式写出来。

```lean
/-- selected-set nogood `∨_{x∈S} ¬x` 的违反条件：
候选 A 选中了 S 中全部变量，即 S ⊆ A。 -/
def SelectedSetNogoodViolated (S A : Finset V) : Prop :=
  S ⊆ A

/-- 选中集式 nogood 过切反例的容量版：
需求为 2，每条并行路容量为 1；单路 S 不满足需求，双路 A 满足需求。
但 selected-set nogood 会因 `S ⊆ A` 把 A 一并剪掉。 -/
theorem tp7s_selected_set_nogood_overcuts :
    ∃ (cap : Bool → Nat) (demand : Nat)
      (Feasible : Finset Bool → Prop) (S A : Finset Bool),
      (∀ X, Feasible X ↔ demand ≤ X.sum cap) ∧
      ¬ Feasible S ∧
      SelectedSetNogoodViolated S A ∧
      Feasible A := by
  refine ⟨
    (fun _ => 1),
    2,
    (fun X => 2 ≤ X.sum (fun _ => 1)),
    {false},
    {false, true},
    ?_, ?_, ?_, ?_
  ⟩
  · intro X
    exact Iff.rfl
  · decide
  · decide
  · decide
```

---

## 模块头 / docstring 横切问题

模块头当前写 F5 反例是“v1 点名的反方向陷阱（无 P-HOM 则复合删光合法类）”。这是 **BLOCK 级误标**：v1 点名的是非 G-不变 cut，不是 P-HOM。建议改掉，否则读者会把红测理解成另一个边界。

frontier 组的 docstring 建议统一加限定语：“固定谓词、当前 certified witness、不可迁移”。尤其 `frontier_prune_preserves_max` 的“剪枝不改变搜索问题的答案”应改成“剪枝不改变纯 objective value；发布级 soundness 需 witness theorem”。

TP7-S 组整体较稳。唯一要硬化的是 `EqKeyViolated` def 的全集约束，以及 overcut 反例的物理玩具语义不要吹得比 theorem 更大。
