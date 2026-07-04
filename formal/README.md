# formal/ — 范式定理的机器检查层（Lean 4）

**性质**：研究层前瞻投资（P3.0 头启动，对应 open question Q14）。**不进认证 TCB、
不改变任何 gate 的验收标准**——项目政策"数学 sound 用工程 verify"（`16_workflow_review.md`
§6.4）继续有效；本目录是给该政策将来 reconsider 时的地基，锁面未动。
配套设计稿：`docs/research/p3_0_formal_verification_head_start_design_v1.md`。

## 构建

```
# 依赖: elan (scoop install elan);工具链钉在 lean-toolchain (v4.31.0),lake 自动拉取
cd formal
lake build          # 应输出 Build completed successfully
```

零外部依赖（不需要 mathlib）：全部定理只用 Lean 4 core。

## 内容与对应表

| Lean 定理 | 对应设计稿命题 | 公理依赖 |
|---|---|---|
| `Tns.all_bad_of_cover` | TNS v3 覆盖论证骨架（覆盖集全 INFEASIBLE ⇒ 域全 INFEASIBLE） | 无 |
| `Tns.exists_minimal_below` | 乘积序良基性：任意域中每点下方存在极小元 | 经典三公理 |
| `Tns.all_bad_of_minimal_bad` | TNS v3 一般域形态：极小元集合（反链）是合法覆盖证书 | 经典三公理 |
| `Tns.std_domain_collapse` | TNS v3 标准域坍缩：(6,6) 单点证书覆盖全域 | 无 |
| `Tns.std_domain_minimal_66` | "标准域最小反链 = 单点" 的机器确认 | 经典三公理 |
| `F5.labeled_orbit_lift` | F5 v3 定理 2（具名形态）：P-HOM 下 nogood 沿保群变换搬运 sound | propext, Quot.sound |
| `F5.realizes_comp` | 匿名 multiset 实现关系沿保群单射搬运 | 无 |
| `F5.nogood_mod_relabel` | 匿名 nogood 模掉重标后的排除力 | 无 |
| `F5.dedup_collapse_strengthens` | F5 v3 "禁重复"前提的机器反例：presence 去重会把 cut 变强（误杀） | propext, Quot.sound |

"经典三公理" = `propext`、`Classical.choice`、`Quot.sound`（Lean/mathlib 标准信任基）。
无任何 `sorry`。公理审计命令：`lake env lean axiom_audit.lean`（脚本见设计稿附录）。

## 抽象边界（读定理前必看）

模型侧前提——逐维反单调（`UpwardClosed`）、谓词同组换位不变（`hHom`/P-HOM)——
在这里是**假设**，不是被证明的结论。它们的成立性由对应设计稿的机器可查义务承担
（TNS 的 ghost-use inventory / master"缩小不收紧"审计；F5 的逐谓词审计表 + 结构门）。
这是刻意分层：抽象定理层（本目录，机器证明）+ 前提审计层（结构门）+ 工程层。
**Lean 陈述与设计稿定理的对应保真是本层最大风险面**——修改任何定理陈述都必须
重新对照设计稿原文并过独立复审（教训来源见设计稿 §formalization-gap）。

## 下一批砖（给后续模型,按序）

1. `anon_lift_sound`：从单个具名代表 pattern 的 nogood 直接导出匿名 multiset nogood
   的全局 soundness（需 mathlib：部分单射在有限群上延拓成置换,`Equiv` 基建）。
2. F5 复合安全引理（轨道 cut × master 对称序不删光合法类）。
3. TNS lex 序 frontier 支配骨架（CERTIFIED 剪 lex 更差候选的 soundness）。
4. 吞吐 TP7-S nogood 完整 0/1 等式键的过切/欠切边界（v3 终审 BLOCK-2 的正反两面）。
