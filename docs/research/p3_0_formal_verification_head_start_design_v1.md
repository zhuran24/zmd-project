# P3.0 形式化证明头启动 — 双轴架构与首批机器检查定理（v2，2026-07-05）

> **性质**：HISTORICAL_OR_PLAN 研究稿。owner 2026-07-05 授权把 Q14（框架形式化证明,
> 原 P3 defer）提前开头。**锁面不动**：项目政策"数学 sound 用工程 verify、不用形式化
> proof system"（`docs/项目说明/16_workflow_review.md` §6.4）在本稿存在期间继续有效;
> 本线是前瞻投资,不改变 P1.2/P1.3/P2.0 任何 gate 的验收标准。
> 首批产物：`formal/`（Lean 4,14 条定理,零 sorry,公理审计干净）。
> **v2（2026-07-05 当日）**：三路独立审查（盲形式化对拼/陈述保真对抗审/证书侧联网深研）
> 已回收——对抗审 1 BLOCK+4 CONCERN 全部修入（补 5 条定理,降级"定理 2 已形式化"的
> 夸大表述）;轴 B 六处事实错误按深研修正;原件归档 §7。

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
proof log,由**经形式化验证的检查器**复验。工具版图（2026-07 联网深研核实,
修正了 v1 从 2026-05 文献裁定沿袭的六处混桶,详见归档报告）:
- **PB/VeriPB 3.0 线**:0-1 PB/cutting-planes 证明格式;原生输出方 = Glasgow
  Constraint Solver、RoundingSat、Exact PB solver 等(**Pumpkin 不算**——它走
  DRCP/LCG 证明路线,归研究候选);工程检查器 = Rust VeriPB checker,形式化检查器
  = CakePB/cake_pb(CakeML,已用于 SAT 竞赛审计);PBLean(2026-04 论文/v0.3.0)
  是把 VeriPB kernel proof 导入 Lean 4 出定理的新路线,列后续 TCB 收口用、非第一落点。
- **MIP/VIPR 线**:SCIP 10 exact mode(`exact/enable=TRUE`)输出 VIPR 证书,
  工程检查器 = VIPR 工具链,形式化检查器 = cake_vipr;注意证书只覆盖 presolved
  problem 的 B&B 树,涉及 presolve/切平面时要禁用或 viprcomp 补全。
- **LP/Farkas 线**:单独建有理证书路线——不可行 LP 出有理 Farkas ray + 独立有理
  算术 checker(很小,可先 Python Fraction 后搬 Lean);精确 LP 生成器 = SoPlex exact
  / SCIP exact;GLOP 浮点 ray 只能"后验有理化,失败即换精确求解器重解",不当可信根。
- **CNF/LRAT 线(cake_lpr)**:只适合完整 CNF 化的小布尔核;OR-Tools 的 LRAT/DRAT
  参数截至 2025-12 仅支持 pure SAT 且限制多,不覆盖本项目一般 child 模型。
- **assumptions unsat core**:只当"缩小复验范围的切片器",不是证明——CP-SAT core
  不保证 minimal,且 or-tools#5141(2026-04)实证 presolve 下会返回不在 assumptions
  里的 literal,必须防御式校验。
**本稿不动轴 B 实施**（依赖真长跑 baseline 与 P1.3 F1/F2 LP-dual 基建）;
分阶段接入方案见 §4 P3.0c(按深研建议重排)。

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

## 3. 首批成果（P3.0a,已落库;v2 计 14 条）

`formal/` 14 条定理,Lean 4.31.0 core（零 mathlib 依赖）,`lake build` 绿,
无 sorry,公理依赖仅经典三公理（propext/Classical.choice/Quot.sound,部分定理零公理）。
清单与对应表见 `formal/README.md`。要点:

- **TNS 侧**:覆盖论证骨架 + 乘积序良基性(极小元存在) + 一般域"极小反链=合法证书"
  + 标准域单点坍缩 + 标准域极小元恰为 {(6,6)}(`std_domain_minimal_iff`,对抗审
  CONCERN-4 补全的完整"单点"陈述)。终审发现的"一般域反链非单点"警告被定理形态
  自然覆盖(证书=极小元集合,标准域时恰为单点)。
- **F5 侧**:具名 nogood 沿 P-preserving 重标搬运的**核心引理**(发现:该方向只需
  单向 P-HOM、不需 σ 可逆)+ 带"保群置换"显式前提的包装陈述 + 匿名 multiset
  实现关系的搬运引理 + 模掉重标的排除力 + **"禁重复/alias 禁令"前提的两组机器反例**
  (严格变强 + 真误杀各一组;presence 去重与 attach-key alias 各自都能构造出
  "原 nogood sound 而坍缩后的 cut 误杀合法布局"的抽象 P)。
- **诚实边界(对抗审 BLOCK-1)**:F5 v3 定理 2 的完整形态——从匿名 per-group
  multiset 包含直接导出 soundness——**尚未形式化**,缺口 = `anon_lift_sound`
  (部分单射延拓成有限组内置换);其 mathlib 陈述设计已由盲形式化交付(§7 归档),
  P3.0b 第一块砖就是它。

## 4. 阶梯（P3.0a → d,给后续模型的路线）

- **P3.0a（本稿,已完成开头）**:core Lean 抽象定理层,双盲对拼 + 对抗审收敛陈述。
- **P3.0b（mathlib 基建期,~数周）**:引入 mathlib;`anon_lift_sound`（部分单射
  延拓成有限群置换,`Equiv`/`Fintype`）;F5 复合安全引理;lex 序 frontier 支配骨架;
  吞吐 TP7-S nogood 完整键的过切/欠切边界。验收=同样零 sorry+公理审计+对应表复审。
- **P3.0c（证书侧接入,挂 P1.3/P2.0b 后;按 2026-07-05 深研重排为七阶段）**:
  Phase0 canonical 子问题中间格式+独立 emitter(1-4 周,先治"翻译层变新单点"的根病)
  → Phase1 **binding INFEASIBLE 的 PB/VeriPB 离线 sidecar**(OPB→Glasgow/RoundingSat
  →Rust VeriPB checker→CakePB;2-5 周 PoC,第一落点)→ Phase2 assumptions core
  只当切片器(1-3 周,防御式校验 or-tools#5141)→ Phase3 routing 分流 PB 或
  SCIP10-exact+VIPR/cake_vipr(6-12 周)→ Phase4 有理 Farkas checker(2-5 周,
  便宜且并行可做)→ Phase5 nightly/release-gate 化(证书是重工件,不进在线主链)
  → Phase6 PBLean/Lean verified encoding 收口翻译层 TCB(2-4 月,最后做)。
  判据与风险逐阶段见归档深研报告。前置=真长跑 baseline。
- **P3.0d（远期）**:六谓词模型层形式化(canonical rules 子集→Lean 定义),
  把"前提审计层"逐步吃进定理层。数年级,只有项目交付后维护期才考虑。

## 5. GPT Pro 协作任务书（三包;v2 注:已全部执行并回收,见 §7）

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

## 7. 三包回收记录（2026-07-05,原件归档 `p3_0_formal_reviews_20260705/`）

1. **盲形式化对拼**:独立方与本方在全部抽象选择上收敛(oriented 乘积序/反单调作
   假设/极小反链覆盖/单射 multiset 实现/P-HOM 作假设),零陈述矛盾;其交付
   `ZmdDesignStatements.lean`(mathlib,sorry 陈述)把 anon_lift_sound 的完整分解
   设计了出来(anonMultisetExtends→occurrence matching→部分置换延拓→named
   representative;boolean presence 层 NoPresenceKeyAlias 与对抗审 CONCERN-3
   独立收敛)——P3.0b 直接照它施工。另附 12 条陈述精化建议,归 P3.0b 输入。
2. **陈述保真对抗审**:1 BLOCK(README/本稿曾把具名核心引理夸大为"定理 2 已
   形式化")+ 4 CONCERN(同组语义不得从对应表消失/strengthens≠false-reject/
   alias 未建模/minimal_66≠单点唯一性)+ 4 NOTE,全部为真;补丁 5 条定理经本地
   重编译+公理审计后采纳(修复:Lean core 无 Function.Bijective,双射前提改双侧逆),
   夸大表述已降级。判定:修后可作为后续形式化扩展基线。
3. **证书侧深研**:v1 轴 B 六处事实错误全部修正(Pumpkin 归 DRCP 非 VeriPB 原生/
   exact-SCIP 应写 SCIP 10 exact mode/检查器按证书语言分三桶 cake_lpr:CNF、
   CakePB:PB、cake_vipr:MIP/LP-Farkas 单独有理路线/OR-Tools proof flags 限定
   pure SAT/旁路重解按三线分流);七阶段接入方案吸收进 §4 P3.0c;
   关键新事实:or-tools#5141(core 含非 assumption literal)、PB 证明工件的
   量级尺度(竞赛限 100GB/5h,必须离线)。

## 附录:公理审计

权威脚本随库提交:`formal/axiom_audit.lean`(覆盖全部 14 条定理),
运行 `lake env lean axiom_audit.lean`,预期输出仅 propext/Classical.choice/Quot.sound
三类经典公理(部分定理零公理),不得出现 sorryAx。
