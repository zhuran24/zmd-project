# formal/ — 范式定理的机器检查层（Lean 4）

**性质**：研究层前瞻投资（P3.0 头启动，对应 open question Q14）。**不进认证 TCB、
不改变任何 gate 的验收标准**——项目政策"数学 sound 用工程 verify"（`16_workflow_review.md`
§6.4）继续有效；本目录是给该政策将来 reconsider 时的地基，锁面未动。
配套设计稿：`docs/research/p3_0_formal_verification_head_start_design_v1.md`（v2）。
本批陈述已过一轮独立审查（盲形式化对拼 + 陈述保真对抗审，归档见设计稿 §7）。

## 构建

```
# 依赖: elan (scoop install elan);工具链钉在 lean-toolchain (v4.31.0),lake 自动拉取
cd formal
lake build          # 应输出 Build completed successfully
lake env lean axiom_audit.lean   # 公理审计
```

零外部依赖（不需要 mathlib）：全部定理只用 Lean 4 core。

## 内容与对应表（14 条定理）

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

"经典三公理" = `propext`、`Classical.choice`、`Quot.sound`（Lean/mathlib 标准信任基）。
无任何 `sorry`。

## 抽象边界（读定理前必看）

- 模型侧前提——逐维反单调（`UpwardClosed`）、谓词同组换位不变（`hHom`/P-HOM)——
  在这里是**假设**，不是被证明的结论。它们的成立性由对应设计稿的机器可查义务承担
  （TNS 的 ghost-use inventory / master"缩小不收紧"审计；F5 的逐谓词审计表 + 结构门）。
- **F5 定理 2 尚未被完整形式化**：本目录只有具名字面搬运的核心引理与其保群包装；
  从"匿名 per-group multiset 包含"直接导出 nogood soundness 的完整定理
  （`anon_lift_sound`，需把部分单射延拓成有限组内置换）是下一块砖——独立盲形式化
  已给出其 mathlib 陈述设计（归档 `docs/research/p3_0_formal_reviews_20260705/`）。
- oriented 键/schema/digest/seal 等工程纪律（如拒绝把 6x7 当 7x6 的键解析层）
  是 validator 层义务，**不**被这里的数学定理覆盖。
- alias 反例覆盖的是"语义上会出什么事"；生产端防线仍是 attach/validator 的
  fail-closed（不同 pose_id 解析到同一 presence key 即拒绝）。
- Lean 陈述的任何修改都必须重新对照设计稿原文并过独立复审。

## 下一批砖（给后续模型,按序）

1. `anon_lift_sound`：从单个具名代表 pattern 的 nogood 导出匿名 multiset nogood
   的全局 soundness（需 mathlib：部分单射在有限组上延拓成 `Equiv.Perm`）——
   完整陈述设计已存在（盲形式化交付 `ZmdDesignStatements.lean`，含
   `anonMultisetExtends`/`PartialSlotPermExtends`/`NoPresenceKeyAlias` 分解），
   照它把 sorry 换成证明即可。
2. F5 复合安全引理（轨道 cut × master 对称序不删光合法类）。
3. TNS lex 序 frontier 支配骨架（CERTIFIED 剪 lex 更差候选的 soundness）。
4. 吞吐 TP7-S nogood 完整 0/1 等式键的过切/欠切边界（v3 终审 BLOCK-2 的正反两面）。
