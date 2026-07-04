# formal/ — 范式定理的机器检查层（Lean 4）

**性质**：研究层前瞻投资（P3.0 头启动，对应 open question Q14）。**不进认证 TCB、
不改变任何 gate 的验收标准**——项目政策"数学 sound 用工程 verify"（`16_workflow_review.md`
§6.4）继续有效；本目录是给该政策将来 reconsider 时的地基，锁面未动。
配套设计稿：`docs/research/p3_0_formal_verification_head_start_design_v1.md`（v2）。
首批陈述已过一轮独立审查（盲形式化对拼 + 陈述保真对抗审，归档见设计稿 §7）；
`DesignStatements.lean` 的陈述即盲形式化交付原文（见下）。

## 构建

```
# 依赖: elan (scoop install elan);工具链钉在 lean-toolchain (v4.31.0)
cd formal
lake update          # 首次:拉 mathlib v4.31.0 及依赖(lake-manifest.json 已锁 rev)
lake exe cache get   # 首次:拉 mathlib 预编译缓存(~4.5GB,不拉则本地编译数小时)
lake build           # 应输出 Build completed successfully
lake env lean axiom_audit.lean   # 公理审计(30 条,应全部仅经典三公理或无公理)
```

**自 2026-07-05 起依赖 mathlib**（钉 `v4.31.0` tag，与工具链同版）：
`TnsCoverage.lean` / `F5OrbitLift.lean` 仍是 core-only，`DesignStatements.lean`
用到 `Finset`/`Multiset`/`Equiv` 库。

## 内容与对应表（30 条定理，三个模块）

### `TnsCoverage.lean` + `F5OrbitLift.lean`（首批 14 条，谓词/函数式表示，core-only）

| Lean 定理 | 对应设计稿命题 | 公理依赖 |
|---|---|---|
| `Tns.all_bad_of_cover` | TNS v3 覆盖论证骨架（覆盖集全 INFEASIBLE ⇒ 域全 INFEASIBLE） | 无 |
| `Tns.exists_minimal_below` | 乘积序良基性：任意域中每点下方存在极小元 | 经典三公理 |
| `Tns.all_bad_of_minimal_bad` | TNS v3 一般域形态：极小元集合（反链）是合法覆盖证书 | 经典三公理 |
| `Tns.std_domain_collapse` | TNS v3 标准域坍缩：(6,6) 单点证书覆盖全域 | 无 |
| `Tns.std_domain_minimal_66` | (6,6) 是标准域的一个极小元 | 经典三公理 |
| `Tns.std_domain_minimal_iff` | 标准域极小元**恰为** {(6,6)}（"最小反链=单点"的完整机器陈述） | 经典三公理 |
| `F5.labeled_orbit_lift` | F5 v3 定理 2 的**具名核心引理**：nogood 沿 P-preserving 重标搬运 sound | propext, Quot.sound |
| `F5.labeled_orbit_lift_group_preserving` | 同上，带设计稿"保群置换"显式前提的包装陈述 | propext, Quot.sound |
| `F5.realizes_comp` | 匿名 multiset 实现关系沿保群单射搬运 | 无 |
| `F5.nogood_mod_relabel` | 匿名 nogood 模掉重标后的排除力 | 无 |
| `F5.dedup_collapse_strengthens` | presence 去重使匹配谓词**严格变强**（存在布局实现 [v] 不实现 [v,v]） | propext, Quot.sound |
| `F5.dedup_collapse_can_false_reject` | 去重的**真误杀**形态：存在 P 使 [v,v] nogood sound 而去重后的 cut 排除满足 P 的布局 | propext, Quot.sound |
| `F5.presence_key_alias_collapse_strengthens` | attach presence-key alias（不同 pose 同 key）的语义坍缩 | propext, Quot.sound |
| `F5.presence_key_alias_can_false_reject` | alias 的真误杀形态（v3 alias 禁令前提的机器反例） | propext, Quot.sound |

### `DesignStatements.lean`（16 条，Finset/Multiset 表示，需 mathlib）

**来源**：陈述 = 盲形式化交付原文（GPT Pro 独立写就，归档
`docs/research/p3_0_formal_reviews_20260705/ZmdDesignStatements.lean`），
本方 2026-07-05 施工填全部 12 个 `sorry` 并把 `native_decide` 换成纯内核 `decide`。
与首批 14 条是**同一数学的两套表示**（谓词式 vs Finset 式），互相印证。

| Lean 定理 | 对应设计稿命题 | 公理依赖 |
|---|---|---|
| `dimwise_antitone_cover_soundness` | TNS v3 §2.1–2.2 覆盖 soundness（Finset 版） | propext, Quot.sound |
| `dimwise_antitone_cover_certificate_soundness` | 同上，带合同层非空域守卫 | propext, Quot.sound |
| `minimalDims_cover` | 有限下降：`MinimalDims` 是合法覆盖（≈ `exists_minimal_below`） | 经典三公理 |
| `minimalDims_antichain` | 极小元集是 oriented 反链 | 经典三公理 |
| `dimwise_antitone_minimal_antichain_soundness` | TNS v3 §2.2 一般域：重放极小反链即足够 | 经典三公理 |
| `domain_with_bottom_minimalDims_singleton` | 含 bottom 的域极小元坍缩为单点（抽象版） | 经典三公理 |
| `standard_domain_minimalDims_singleton` | 标准矩形域 [6,maxW]×[6,maxH] 坍缩到 {(6,6)} | 经典三公理 |
| `standard_domain_single_point_collapse_soundness` | O(1) 标准域证书完整 soundness | 经典三公理 |
| `Orbit.named_orbit_lift_soundness` | F5 v3 §2.3 具名形态：liftable nogood 沿组内置换搬运 | 经典三公理 |
| `Orbit.anonMultisetExtends_gives_matching` | multiset 包含 ⇒ 保 key 单射匹配（重数见证） | 经典三公理 |
| `Orbit.partialSlotPermExtends_of_fintype` | 有限 slot 池上部分单射延拓为全置换（§2.3 NOTE-2） | 经典三公理 |
| `Orbit.matching_extends_to_group_permutation` | 匹配 + 延拓原理 ⇒ 存在组内置换使布局字面包含代表 pattern | 经典三公理 |
| `Orbit.anon_multiset_lift_soundness_from_named_representative` | **F5 定理 2 完整形态（anon_lift_sound）**：单个具名代表 ⇒ 计数感知匿名 multiset nogood | 经典三公理 |
| `Orbit.boolean_presence_refines_multiset` | no-alias/no-repeat 守卫下 boolean presence 精化 multiset 语义 | 经典三公理 |
| `Orbit.boolean_presence_lift_soundness_from_named_representative` | boolean master attach 形态的完整 soundness（方案 A 的定理形状） | 经典三公理 |
| `NoRepeatCounterexample.presence_dedup_strengthens_cut_counterexample` | v3 §2.3 BLOCK-2 反例：presence 去重把重数-2 cut 强化成重数-1（具体构造） | 经典三公理 |

"经典三公理" = `propext`、`Classical.choice`、`Quot.sound`（Lean/mathlib 标准信任基）。
无任何 `sorry`，无 `native_decide`/`ofReduceBool`（30/30 见 `axiom_audit.lean`）。

## 陈述层修改记录（施工中，均已过编译+公理审计）

对盲形式化交付陈述的修改仅两类，数学内容均不变：

1. **universe 特化**：`matching_extends_to_group_permutation` /
   `anon_multiset_lift_soundness_from_named_representative` /
   `boolean_presence_lift_soundness_from_named_representative` 三条的
   `hExtend : PartialSlotPermExtends Slot` 特化为
   `PartialSlotPermExtends.{u, v, max v w}`。原因：原定义 `{ι : Type*}` 的
   universe 在定理层是刚性参数，证明内部需要以 `Slot g × Pose g` 的 subtype
   （宇宙 `max v w`）为 index 调用它，非特化不可。`partialSlotPermExtends_of_fintype`
   本身保持全 universe 多态，实例化后传入即可，组合无损。
2. **证明手段替换**：C 部分反例的 `native_decide` → 纯内核 `decide`
   （避免引入 `ofReduceBool` 编译器信任公理，守住"仅经典三公理"审计线）。

## 抽象边界（读定理前必看）

- 模型侧前提——逐维反单调（`UpwardClosed`/`DimwiseAntitoneInfeasible`）、
  谓词同组换位不变（P-HOM）、liftable reject、feasible 布局 well-formed
  （无重复 `(group,slot)`）——在这里是**假设**，不是被证明的结论。它们的成立性
  由对应设计稿的机器可查义务承担（TNS 的 ghost-use inventory / master"缩小不收紧"
  审计；F5 的逐谓词审计表 + 结构门 + immutable_scope 白名单）。
- oriented 键/schema/digest/seal 等工程纪律（如拒绝把 6x7 当 7x6 的键解析层）
  是 validator 层义务，**不**被这里的数学定理覆盖。
- alias 反例覆盖的是"语义上会出什么事"；生产端防线仍是 attach/validator 的
  fail-closed（不同 pose_id 解析到同一 presence key 即拒绝）。
- Lean 陈述的任何修改都必须重新对照设计稿原文并过独立复审（本批的两处修改
  见上节记录）。

## 下一批砖（给后续模型,按序）

1. ~~`anon_lift_sound`~~ **已完成**（2026-07-05，见 `DesignStatements.lean`
   `Orbit.anon_multiset_lift_soundness_from_named_representative` 全链）。
2. 第一梯队 family 核心定理（照可开工地图
   `docs/research/p3_0b_family_formalizability_survey_20260705/`
   顺序：F9 面积计数 → F1 容量鸽笼 → F7 空覆盖单调性 → F4 图可达 →
   F6 区间 floor 计数 → F2 割边计数；mathlib 已就位，`Finset` 基数工具齐）。
3. F5 复合安全引理（轨道 cut × master 对称序不删光合法类）。
4. TNS lex 序 frontier 支配骨架（CERTIFIED 剪 lex 更差候选的 soundness）。
5. 吞吐 TP7-S nogood 完整 0/1 等式键的过切/欠切边界（v3 终审 BLOCK-2 的正反两面）。
