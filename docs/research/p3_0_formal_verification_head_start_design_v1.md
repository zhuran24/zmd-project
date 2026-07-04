# P3.0 形式化证明头启动 — 双轴架构与首批机器检查定理（v1，2026-07-05）

> **性质**：HISTORICAL_OR_PLAN 研究稿。owner 2026-07-05 授权把 Q14（框架形式化证明,
> 原 P3 defer）提前开头。**锁面不动**：项目政策"数学 sound 用工程 verify、不用形式化
> proof system"（`docs/项目说明/16_workflow_review.md` §6.4）在本稿存在期间继续有效;
> 本线是前瞻投资,不改变 P1.2/P1.3/P2.0 任何 gate 的验收标准。
> 首批产物：`formal/`（Lean 4,9 条定理,零 sorry,公理审计干净）。

## 1. 双轴架构（这条线到底在证什么）

项目的"证明"信任面拆成两个正交的轴,形式化投资必须分开对待:

**轴 A — 定理侧（范式数学）**:cut family soundness、轨道提升、反单调覆盖、
lex 最优性框架……这些是"范式本身对不对"的数学。现状 = 设计稿里的纸面证明
（已过三轮独立审查）。形式化工具 = **Lean 4**（文献裁定 R7:AlphaProof 类自动证明
排除,组合数学 pass@1 仅 20.3%;人写 Lean + mathlib 是可行路径）。
**本稿开的就是这个头**——零基建成本（core Lean 即可起步）,且定理层的价值
不依赖求解器:范式错了,后面全错。

**轴 B — 证书侧（单次求解结果）**:某一次 LP/CP-SAT 求解给出的 FEASIBLE/INFEASIBLE
到底可不可信。这是瓶颈审计"CP-SAT 编码忠实性单点"的终极解:让求解器输出
proof log,由**经形式化验证的检查器**复验。文献裁定（R4/R6/R7,roadmap P3 段):
VeriPB 3.0（PB 证明格式,Glasgow/Pumpkin 已支持）、VIPR（MIP 证书格式,
exact-SCIP 生态）、cake_lpr / PBLean(验证过的检查器)。**本稿不动轴 B**
（依赖真长跑 baseline 与 P1.3 F1/F2 LP-dual 基建）,只在 §5 给接入研究任务书。

两轴分工与项目现有机制的关系:轴 A 补"设计稿纸面证明 → 机器证明"的最后一级;
轴 B 补"I1 同构造器同库复验 → 异构且验证过的复验"的最后一级。都不取代
现有工程 verify,是其上限加固。

## 2. 抽象边界纪律（本线最重要的方法论决定）

**形式化在抽象层进行,模型侧前提作为假设接入。** 例:反单调引理的模型侧成立性
（"ghost 缩小只放松约束"）不在 Lean 里重证——那需要形式化整个 CP-SAT 模型,
是 P3.0d 远期;Lean 接收 `UpwardClosed` 为假设,其成立性由 TNS 设计稿的
ghost-use inventory + master"缩小不收紧"审计（终审已逐行验过一次）承担。
三层分工:

| 层 | 承担者 | 产物 |
|---|---|---|
| 抽象定理层 | Lean（`formal/`） | 机器检查的定理:前提 ⇒ 结论 |
| 前提审计层 | 结构门/checker/审计表 | 机器可查的"前提在真系统里成立" |
| 工程层 | 现有 validator/replay/I1 | 单次运行结果的复核 |

**formalization gap 是本线最大风险**:Lean 定理陈述若与设计稿定理不对应
（弱化前提、偷换结论、量词错位）,机器检查毫无价值甚至有害（虚假安全感）。
纪律:①每个 .lean 文件头写对应表,陈述旁注明设计稿出处;②陈述的任何修改
必须过独立复审（沿用设计稿修订版复审纪律,那是 2026-07-04 用户质询确立的教训）;
③双盲对拼:独立方不看我们的 Lean、只看设计稿写陈述,回来对差异——差异处
即 gap 候选。

## 3. 首批成果（P3.0a,已落库）

`formal/` 9 条定理,Lean 4.31.0 core（零 mathlib 依赖）,`lake build` 绿,
无 sorry,公理依赖仅经典三公理（propext/Classical.choice/Quot.sound,部分定理零公理）。
清单与对应表见 `formal/README.md`。要点:

- **TNS 侧**:覆盖论证骨架 + 乘积序良基性(极小元存在) + 一般域"极小反链=合法证书"
  + 标准域单点坍缩 + "(6,6) 是标准域唯一极小元"的机器确认。终审发现的
  "一般域反链非单点"警告被定理形态自然覆盖(证书=极小元集合,标准域时恰为单点)。
- **F5 侧**:具名 nogood 沿保群变换搬运的 soundness(定理 2 具名形态;发现:
  该方向只需单向 P-HOM、不需 σ 可逆)+ 匿名 multiset 实现关系的搬运引理 +
  模掉重标的排除力 + **"禁重复"前提的机器反例**(presence 去重把 [v,v] 变 [v]
  会误杀"只摆一个 v"的合法布局——设计稿定理 2 前提的必要性现在是机器事实)。

## 4. 阶梯（P3.0a → d,给后续模型的路线）

- **P3.0a（本稿,已完成开头）**:core Lean 抽象定理层,双盲对拼 + 对抗审收敛陈述。
- **P3.0b（mathlib 基建期,~数周）**:引入 mathlib;`anon_lift_sound`（部分单射
  延拓成有限群置换,`Equiv`/`Fintype`）;F5 复合安全引理;lex 序 frontier 支配骨架;
  吞吐 TP7-S nogood 完整键的过切/欠切边界。验收=同样零 sorry+公理审计+对应表复审。
- **P3.0c（证书侧接入,挂 P1.3/P2.0b 后）**:F1/F2 LP dual 与 TP7-S Farkas 证书
  导出 VIPR/VeriPB 格式,用验证过的检查器(cake_lpr/PBLean 生态)复验;先做
  离线 sidecar,不进认证链。前置=真长跑 baseline+§5 研究任务书回答。
- **P3.0d（远期）**:六谓词模型层形式化(canonical rules 子集→Lean 定义),
  把"前提审计层"逐步吃进定理层。数年级,只有项目交付后维护期才考虑。

## 5. GPT Pro 协作任务书（三包,可独立开）

1. **盲形式化对照**（只给设计稿 v3,不给我们的 Lean）:把 TNS 承重引理与 F5
   定理 2 写成 Lean 4 陈述(证明可略),外加 anon_lift_sound 的完整陈述设计。
   回收后与 `formal/` 对拼,差异=formalization gap 候选。
2. **陈述保真对抗审**（全包）:逐条比对 `formal/` 陈述 vs 设计稿定理原文,
   攻击弱化/偷换/量词错位/抽象边界缝隙;每发现附修复补丁。
3. **证书侧路线深研**（可浏览网络）:VeriPB 3.0 / VIPR / cake_lpr / PBLean
   2026 生态现状;GLOP(Farkas ray 导出)与 CP-SAT(何种证明格式可导)的接口
   可行性;给 P3.0c 的接入设计建议与工作量估计。

## 6. 开放问题

1. 轴 A 陈述保真的长效机制:对应表靠人维护,是否要做"设计稿定理编号 ↔ Lean 名"
   的机器对账(简单 checker)?
2. mathlib 引入后构建产物(~5GB cache)与仓库/CI 的关系——建议 formal/ 永远
   不进 CI 硬门,本地/研究机构建。
3. 轴 B 的 CP-SAT 侧:OR-Tools 无原生 proof log,VeriPB 导出需要第三方 solver
   (Glasgow/Pumpkin/exact-SCIP)重解——这与 I1"异构第二编码"是同一笔投资,
   应合并设计(待 §5 包 3 回收后定)。

## 附录:公理审计脚本

```lean
import ZmdFormal
#print axioms ZmdFormal.Tns.all_bad_of_cover
#print axioms ZmdFormal.Tns.exists_minimal_below
#print axioms ZmdFormal.Tns.all_bad_of_minimal_bad
#print axioms ZmdFormal.Tns.std_domain_collapse
#print axioms ZmdFormal.Tns.std_domain_minimal_66
#print axioms ZmdFormal.F5.labeled_orbit_lift
#print axioms ZmdFormal.F5.realizes_comp
#print axioms ZmdFormal.F5.nogood_mod_relabel
#print axioms ZmdFormal.F5.dedup_collapse_strengthens
```
