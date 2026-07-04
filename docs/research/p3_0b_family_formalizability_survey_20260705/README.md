# F1-F9 与完备性的形式化可开工地图（2026-07-05 调查）

**性质**：HISTORICAL_OR_PLAN。10 路并行只读调查（每 family 一读者：spec + validator
源码 + oracle/helper，全部断言带 file:line；另一读者查完备性 Q1 现状），为
「P3.0 形式化线下一步先啃哪块」提供事实底料与排序。原始逐 family 报告在本目录
`f*_*.md` / `completeness.md`。综合裁定如下（裁定是本方的，事实是调查的）。

## 核心发现：family 的名字比实现吓人

九个 family 的 **validator 当前实际执行的数学**全部是初等论证——名字里的重数学
（Hall/max-flow/LP dual）要么只在 generator 侧、要么是 Phase 1.5+ 未来项：

- F6 名字带 Hall，当前实现是**一维区间 floor 计数 + 鸽笼**（多形状版才要 Hall 定理）；
- F2 名字是 Menger min-cut，cut soundness 只需**弱方向**（任何 A-B 路必过割 ⇒
  demand > 割边数即不可行）——完整 Menger/max-flow 只在 generator 完备性时才需要；
- F1 的 LP-dual/Farkas 证书是自认未实现项，当前核心是 **cap/demand 计数**；
- F9 是最简单的**面积计数**（|owned∩W| ≤ |W\blocked|）。

## 第一梯队：现在就能进 Lean（核心论证 = 初等计数/序/图论）

| family | 抽象核心定理 | 需要的数学 |
|---|---|---|
| F1 region_capacity | Σ demand·cells_per_pose > \|R\blocked\| ⇒ 不可行 | 有限集基数 + 求和不等式 |
| F9 density_envelope | \|A∩W\| ≤ \|W\B\|（子集基数） | 同上（最简单） |
| F6 shape_packing_hall（受限版） | 1×L pose 不跨阻挡 ⇒ 可放数 ≤ Σ floor(len/L)；对侧下界 max(0,D−C') | floor 除法 + 区间不相交 + 鸽笼 |
| F2 cutset | 每条 A-B 路必用 δ(A,B) 边 + 边不相交 ⇒ demand > \|δ\| 不可行 | 有限图路径 + 计数（**不需要** MFMC） |
| F4 component_reach | 可达集对邻接封闭 ⇒ 补集无路可入；子图可达 ⊆ 原图可达 | 有限图可达性 |
| F7 power_hitting_set（empty-cover 版） | CoverSet(F,Free)=∅ ∧ Free'⊆Free ⇒ CoverSet(F,Free')=∅ | 集合单调性（几乎平凡） |
| F5 pattern_nogood | **已开工**（formal/ 4+5 条定理；anon_lift_sound 待 mathlib） | 置换/multiset |

工程建议：F9/F1/F6/F2 的基数与求和用 mathlib `Finset` 远比 core Lean 顺——
**P3.0b 第一步 = 引入 mathlib**（构建缓存数 GB，独立会话做），然后按
F9→F1→F7→F4→F6→F2 从易到难铺（F9 半天级起步）。

## 第二梯队：能形式化，但有真实前提挡在前面

- **F8 power_grid_reach**：抽象层（图断连 + 子图单调性）简单，但谓词绑死
  欧氏距离 + Liang-Barsky 线段-AABB 相交（计算几何，重）。**更硬的阻碍**：
  F7/F8 的欧氏覆盖模型与 certified 路径的 12×12 方形 stencil 是代码自认的
  "landmine"（`power_cover.py:15-21`，F7/F8 因此 non-certified）——P1.3 语义
  reconcile 之前形式化 = 把错误几何铸进定理。**顺序上必须等 reconcile**。
  （F7 的 empty-cover 单调性核心不受此影响，可先做。）
- **F3 port_exposure**：抽象层（格邻接 + 双 literal nogood）极简单，可以做——
  但必须把 "all ports active" 写成显式前提（active_port_witness 未实现，
  P1.5 硬门），且方向原语有 N/S 翻转坑（`candidate_placements.py:56-58` 自认
  shared primitives 前 no cert）。形式化时前提要点名，别照 spec 的广义分支写
  （`front ∉ free_cells` 分支实现里根本没有）。

## 完备性（Q1）：不是 Lean 任务，是设计稿任务

调查确认：**连定理的量词域都还没定义**。现状 = 5 个已知 issue 的经验映射 +
red fixtures + F10-F16 反例裁定（"代数归 master、几何归 cut"），无不可行类
partition、无 owner lemma、无 scope=applicability 形式化（Q3）。要变成可证明
命题缺八样东西（见 `completeness.md`，其中最前置的三样：theorem domain 定义、
互斥穷尽 partition、每类 owner lemma）。**正确打开方式 = 先写一份
「不可行类分类学」设计稿**（"先想后做"型任务，走独立审查链），Lean 排在它后面。

## 顺带修正一个直觉

不是"都能开工但保险起见慢慢来"。真实结构是三种状态：
① 七个 family（含已开工的 F5）的**当前实现核心**现在就能形式化,不需要等任何人；
② F8 被几何语义分裂挡住（等 P1.3 reconcile）、F3 要带显式前提做；
③ 完备性缺的不是证明手段而是**定义**，那是纸面设计工作。
另注意：形式化"当前实现"会顺带钉住一批 spec↔代码 drift（调查逐 family 列了
latent_issues），这些 drift 本身就是形式化的第一批红利。
