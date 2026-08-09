# Cut Family 1 — region_capacity（geometric mode）。名字/编号来自 spec 标题："Cut Family 1 — region_capacity"（docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md:1, :5）。代码侧同样称 "Family 1 region_capacity"，lifecycle 的 family map 中标为 region_capacity / F1 / geometric（src/cuts/families/region_capacity.py:1；src/cuts/lifecycle.py:65-80）。注意：当前实现的 RegionKind 比 spec §1b 初表多一种——spec 初表列 left_baseline/bottom_baseline/interior_rect/ghost_complement 四种，代码实际列出五种（多了 left_or_bottom_union）（spec :44-52 对比 src/cuts/families/region_capacity.py:40-48）；而当前 generator/oracle 只实际枚举 left_or_bottom_union 这一种 region kind（src/cuts/oracles/region_capacity_oracle.py:222-229, :233-260），其余 kind（interior_rect 等）在生成侧尚未实现（与下方 latent_issues 一致）。

## proposition
对任意当前 BState 与证书给出的有限 grid region R，令 blocked = ghost_cells ∪ exterior_blocks，cap_R = |R| − |blocked ∩ R|；令贡献 group 集合 C 中每个 group g 的 demand 为 d_g、每个 pose 占用 cells 数为 c_g，且 g 的 placement_rule 映射到该 region_kind，并且 g 的 pose_domain 中所有 pose 的 occupied_cells ⊆ R。若 Σ_{g∈C} d_g·c_g > cap_R，则不存在满足全部 mandatory demand、避开 blocked cells、且 cell 互不重叠的 master placement（即该状态下不可行）。spec 给出的数学骨架是"capacity 上界 + demand 下界 → 矛盾"这一计数式论证。证据：capacity 上界 01_region_capacity.md:68-78；demand 下界 :97-105；不可行性 witness :109-115；代码侧对应实现——cap 重算 src/cuts/families/region_capacity.py:150-159；contributor / P(g) 检查 :182-220, :276-317；gap/witness 检查 :339-362, :394-402。

## argument_type
主体是计数/鸽笼原理：demand_R ≤ placed_cells_in_R ≤ cap_R，若 demand_R > cap_R 即矛盾（01_region_capacity.md:109-115）。同时带有有限离散几何/有限集合论成分：R 是 cell 的有限集合，blocked 交集、pose occupied_cells 子集关系都是有限集合判定（src/cuts/families/region_capacity.py:150-159, :204-220；src/cuts/helpers/candidate_placements.py:202-240）。当前生产核心**不是** Hall 匹配定理、最大流最小割、LP 对偶/Farkas 引理——spec 里把 LP-dual/Farkas 描述为 preferred/optional 的设计路径，但代码模块明确自认 LP-dual/Farkas certificates 尚未实现，cert schema 也只接受 combinatorial 这一种 cert_kind（spec 01_region_capacity.md:58-62, :214-235, :410-421；代码 src/cuts/families/region_capacity.py:13-17；schema src/cuts/cert_schema.py:14-16）。

## formalization_needs
【可在抽象层一次性证明、不绑定具体几何数据的部分】
核心是一条纯有限组合命题：给定有限集合 R、blocked ⊆ R、有限 group 集合，每个 group 有自然数 demand d_g 与 pose-size c_g，若每个 group 的每个 required pose 的 occupied cells 都 ⊆ R 且互不重叠、都避开 blocked，则 Σ d_g·c_g ≤ |R \ blocked|（否则矛盾/不可行）。这一层所需的 Lean 支持主要是：有限集合/Finset、集合基数（cardinality）、对有限映射/列表求和、自然数/整数不等式运算。依据是 spec 里 cap/demand/witness 的结构（01_region_capacity.md:68-78, :97-115）。
此外还需要一条 pose-subset 引理：若某 group 每个 required pose 的 occupied cells 都落在 R 内，且每个 pose 恰占 c_g 个 cell，则该 group 的 demand 在 R 内贡献 d_g·c_g 个占用需求。当前代码确实做了 occupied_cells ⊆ R 的 subset 检查（src/cuts/helpers/candidate_placements.py:230-240），但未在 F1 helper 中找到逐 pose "len(occupied_cells) == cells_per_pose" 这一具体核验的直接证据（cells_per_pose 的来源是 template dimensions，见 src/cuts/helpers/canonical_rules.py:44-62）——这条等式关系目前是隐含假设而非被显式重新核验的断言，需要注意。

【绑定具体几何数据/canonical_rules 常量、每个实例都要重新验证、不能一次性抽象证明的部分】
bitset 解码得到的具体 R（70x70 grid 编码）、ghost/exterior 的具体交集、facility_type 映射、dimensions 具体数值、placement_rule 具体映射、pose_domain 具体枚举、每个 pose 的具体 occupied_cells、source digest/artifact hash 的具体绑定、cap_R/demand_R/gap 的具体数值——这些都是与具体实例/具体 70x70 布局数据绑死的，每次都要重新核验，不属于可一次性抽象证明的部分。证据：bitset 解码 src/cuts/families/region_capacity.py:223-250；BState/source digest src/cuts/lifecycle.py:405-427, :504-537；helper 依赖 src/cuts/helpers/canonical_rules.py:25-77, src/cuts/helpers/candidate_placements.py:128-240。

【若未来要覆盖 spec 描述的 LP dual 路径（当前未实现，非现有 production 数学核心）】
还需要精确线性代数/Farkas 引理证书支持，以及 master LP 矩阵重建能力；但根据代码自认（src/cuts/families/region_capacity.py:13-17）和 spec 描述（01_region_capacity.md:410-421），这条路径当前并未实现，不是当前 F1 production validator 已落地的数学核心，形式化时不必优先覆盖。

## latent_issues
- 代码模块自认三项未实现：LP-dual/Farkas 代数证书、multi-region dual-ray cuts、interior_rect 的 generator/enumeration policy（src/cuts/families/region_capacity.py:13-17）。
- spec 自列的 open questions 包括：LP dual vs combinatorial 路线选择、interior_rect 的 O(70^4) 枚举策略、多 ghost_complement 失效场景、multi-region cut、contributing_groups 与 placement_rule 之间的多对多关系（01_region_capacity.md:531-550）。
- spec 自认 v1.2 修复过 GHOST_AGNOSTIC 与 ghost-dependent cap 之间的一处 unsound 矛盾（01_region_capacity.md:14-23, :83-89）；代码里对应有 agnostic ghost 交集检查（src/cuts/families/region_capacity.py:320-336）。
- spec 自认：若 ghost-dependent 的 F1 cut 不加 by_ghost watcher，ghost 改变后该 cut 会无条件返回 True，构成 false positive 风险（01_region_capacity.md:459-465）。
- helper 文档自认：真实的 boundary_io 在 54 个 pose 中有 14 个不落在 left∪bottom union 内，因此该 group 目前被 fail-closed 处理为不贡献（not contributing），未来 Phase 1.5+ 可能需要拆分 group（src/cuts/helpers/candidate_placements.py:213-217）。
- evaluate 路径此前存在"无条件 True"的假剪问题；当前已改为对 current cap 重算，但 Phase 1.3 仍留有 cache/watcher/性能相关的 deferred 项（src/cuts/families/region_capacity.py:415-435）。
- master apply 步骤仍是未来占位：step_8_apply_to_master 直接抛 NotImplementedError（src/cuts/lifecycle.py:1117-1126，与 CLAUDE.md 中提到的 src/cuts/lifecycle.py:1121-1126 一致，属同一处 NotImplementedError）。
