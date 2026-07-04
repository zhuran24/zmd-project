# F7 power_hitting_set。spec 标题："Cut Family 7 — power_hitting_set" (docs/research/p3_b_design_v2_20260521/cut_family_specs/07_power_hitting_set.md:1)；实现文件 docstring 也写 "Family 7 power_hitting_set" (src/cuts/families/power_hitting_set.py:1)。该 family 是 literal mode：spec 标 "Mode: literal" (07_power_hitting_set.md:5)，实现说 evaluator 委托给 literal multiset (power_hitting_set.py:41-42)。

## proposition
当前实现的核心命题是一个 ghost-bound、single-literal 的 empty-cover-set 充分条件：

给定当前 BState 中的 ghost cells G、exterior blocks E、cell owners O，以及某个需要供电的 facility group g 的 pose p。令 F 是该 pose 在 candidate_placements 里的 occupied_cells，令 R 是 canonical_rules.facility_templates.power_pole.power_coverage_radius，pole footprint 固定为 2x2_rigid。定义 pole anchor a 有效当且仅当它的 2×2 footprint 完全落在 free cells 内；定义 Cover(a,F,R) 为该 2×2 pole 的某个 cell 与 F 中某个 facility cell 的欧氏距离 <= R。若在 free = grid \ (G ∪ E ∪ O ∪ F) 下 CoverSet(F, free, R)=∅，并且在忽略 cell_owner 的 free_ghost = grid \ (G ∪ E ∪ F) 下 CoverSet(F, free_ghost, R)=∅，则在该 ghost/exterior scope 下选择 (g,p) 没有任何可放置且可覆盖它的 power pole anchor；F7 cut 用单个 literal 禁止该 pose。

证据：
- spec 的数学定义：Cover(p,q) 是 pole cell 在 facility 任一 cell 的 R 邻域内 (07_power_hitting_set.md:26-27)；CoverSet(p,state) = { q ∈ PoolPole : Cover(p,q) AND q 在 state.free_cells } (07_power_hitting_set.md:29)。
- spec 的命题形式：若 CoverSet(p,state)=∅，则不存在 Cover(p,q) 且 q ∈ free_cells 的 pole pose，future free cells 单调缩小，所以空集保持，facility p infeasible (07_power_hitting_set.md:73-79)。
- ghost scope 必须绑定，因为 ghost 可能变，切换 ghost 时不能 attach (07_power_hitting_set.md:81-89)。
- 实现的当前 Phase 1.2 命题更窄：只允许 cert_kind == "power_cover_emptyset_ghost"，cell-owner causation multi-literal case deferred (src/cuts/families/power_hitting_set.py:3-15)。
- 实现锁定真实 pole shape 为 2x2_rigid，并说明 spec 旧文的 1×1 不是当前 canonical truth (power_hitting_set.py:16-20)；schema 检查也要求 "2x2_rigid" (power_hitting_set.py:147-164)。
- compute_cover_set 的实际谓词：2×2 pole footprint 全在 free_cells，且 pole 某 cell 到 facility 某 cell 的欧氏距离 <= pole_radius (src/cuts/helpers/power_cover.py:3-5, 40-59, 62-70, 74-84, 101-123)。
- validator 的 full free mask 是 grid - ghost - exterior - cell_owner - facility_cells (power_hitting_set.py:376-389)，ghost-only mask 是 grid - ghost - exterior - facility_cells (power_hitting_set.py:407-417)。
- cut 本体只含一个 literal，且 literal 必须匹配 cert 的 (facility_group, facility_pose_id) (power_hitting_set.py:525-542)；literal evaluator 对 F7 使用 group/pose multiset subset 语义 (src/cuts/lifecycle.py:1014-1027, 1045-1070)。

## argument_type
集合覆盖/几何(区间/圆)/序-置换(多重集)——不含 Hall 匹配、最大流最小割、LP 对偶/Farkas。

- 集合覆盖 / empty hitting-set：spec 直接说"Hitting set 视角"，facility pose 必须 hit CoverSet 中至少一个 pole pose；CoverSet=∅ 推出不能 power cover (07_power_hitting_set.md:31-40)。当前 v1.0/Phase 1.2 只拦 empty set，不证"min hitting set size 不够" (07_power_hitting_set.md:52-57)。
- 几何论证：Cover 是 facility cell 与 pole cell 的半径关系 (07_power_hitting_set.md:26-27)；实现枚举 70×70 grid 上 2×2 pole anchor，检查 footprint subset 和欧氏距离 (src/cuts/helpers/power_cover.py:40-59, 74-84, 101-123)。
- 单调性/子集论证：spec soundness proof 的关键是 future free_cells 只会缩小，因此空 CoverSet 单调保持 (07_power_hitting_set.md:73-79)；实现额外用 ghost-only empty 排除 cell_owner 回溯导致的假因 (src/cuts/families/power_hitting_set.py:399-426)。
- 序/置换/多重集论证：F7 cut 的 literal 语义是匿名 slot 的 group/pose multiset subset，不是 slot-index 一一匹配 (src/cuts/lifecycle.py:1017-1027, 1060-1070)。
- 不是当前实现中的 max-flow/min-cut、LP/Farkas、完整 Hall matching 证明。代码里有错误文本"Hall witness fails" (power_hitting_set.py:390-395)，但实际检查是 `if cover_full:` 这种 empty-set 复验；当前 F7 helper/oracle/family imports 是 Python math/hash/os/project helper，没有 solver import (power_cover.py:29-30, power_hitting_set.py:51-63, src/cuts/oracles/power_cover_oracle.py:28-48)。

## formalization_needs
事实观察，不给最终结论：

- 抽象组合层可建成有限集合引理：若 CoverSet(F, Free)=∅ 且 Free'⊆Free，则 CoverSet(F, Free')=∅；spec 证明正是 state'.free_cells ⊆ state.free_cells 与空集保持 (07_power_hitting_set.md:73-79)。当前实现用 ghost-only empty 让该引理不依赖当前 cell_owner 是否未来被回溯 (src/cuts/families/power_hitting_set.py:399-426)。
- 需要有限 grid/cell/anchor 概念：实现固定 _GRID_SIZE=70 (power_hitting_set.py:70-71, src/cuts/helpers/power_cover.py:36-37)，facility cells 必须是 grid 内整数 (power_hitting_set.py:121-128)，pole anchors 在 range(grid_size - pole_size + 1) 枚举 (power_cover.py:74-84)。
- 需要 2×2 footprint subset-free 谓词：_pole_cells 生成 anchor 的 2×2 cells (power_cover.py:40-42)，valid anchor 要求这些 cells 全在 free set (power_cover.py:79-84)。
- 需要覆盖几何谓词：当前 F7 helper 用欧氏距离和 math.sqrt (power_cover.py:45-59) 并以 <= pole_radius 判定覆盖 (power_cover.py:62-70)；cert radius 是 JSON float，经 strict loader 解析为 Python float (src/io/strict_json.py:30-34, 51-67)，再由 canonical SoT 检查等于 canonical radius (power_hitting_set.py:444-471)。
- 需要 project-specific binding 层：group/pose membership、needs_power、pose cells 来自 candidate_placements、canonical radius/dims、ghost/exterior digest 都是 validator 的机械前置条件 (power_hitting_set.py:228-280, 284-359, 434-471, 179-225)。这些不是纯组合引理本身，而是把项目数据结构绑定到抽象命题的证明前提。
- 需要 literal cut 语义：F7 cut violation 是 (group, pose) demand multiset 被 state.groups[group].selected_poses 覆盖 (src/cuts/lifecycle.py:1014-1027, 1045-1070)；scope guard 要求 replay attach decision 为 ATTACH (lifecycle.py:1003-1011)。
- 若 formalization 目标跟"live certified coverage semantics"一致，还会遇到 Euclidean helper vs 12×12 square stencil 的项目语义分裂：canonical rules/placement/master 侧记录 square stencil (rules/canonical_rules.json:429-439, src/placement/placement_generator.py:400-416, src/models/exact_coordinate_master.py:5141-5175)，而 F7 helper 自承认仍是旧欧氏模型 (src/cuts/helpers/power_cover.py:15-21)。
- 当前 empty-cover family 不需要 Hall theorem、max-flow/min-cut 或 LP dual/Farkas；spec 的 future generalization "min hitting set 不够" 才提到 ILP min hitting set / QuickXplain (07_power_hitting_set.md:339-345, 618-620)。

## latent_issues
- 已知 sound bug 类型：spec changelog 写 v1.1 修"致命 sound bug"，原因是 generator 必须区分 ghost/exterior 清空和 cell_owner 挤空，否则回溯移走 cell_owner facility 后会误剪合法 pose (07_power_hitting_set.md:13-16, 223-226)。
- 当前实现仍只支持 single-case：cell_owner causation multi-literal case deferred to Phase 1.5+ (src/cuts/families/power_hitting_set.py:3-7, 13-15, 525-527)；发现 ghost-only CoverSet 非空时直接报 single-literal unsound (power_hitting_set.py:418-425)；generator 也跳过这种 case (src/cuts/oracles/power_cover_oracle.py:219-221)。
- 一般化 hitting-set infeasible 未实现：spec 明说 v1.0 只拦 empty case，不证 min size 不够 (07_power_hitting_set.md:52-57)；open questions 也列"多 facility 共用 pole 但 pole 数不够"走 ILP min hitting set (07_power_hitting_set.md:618-620)。
- spec 旧文与实现/canonical 有 shape mismatch：spec 早段写 power pole 1×1 (07_power_hitting_set.md:22-24, 117-118)；实现 docstring 明说真实 canonical 是 2×2，不是 v1.1 spec text 的 1×1 (src/cuts/families/power_hitting_set.py:16-20)。
- coverage semantics split：实现 docstring 说 F7/F8 helper 用旧欧氏模型，而 active certified path/frozen pose geometry 用 owner-confirmed 12×12 square stencil；F7/F8 在 P1.3 reconcile 前不是 certified master inputs (power_hitting_set.py:21-26, src/cuts/helpers/power_cover.py:15-21)。
- open questions 还包括 power radius/shape 一般化、L16 cut store 重复、candidate pose id 排序导致 cert_hash 不稳、payload 大小 (07_power_hitting_set.md:621-633)。
- shared SoT helper docstring 记录了 v28 review 发现过 F7 信任 pole_radius、F7/F8 信任 hard-coded footprint 而未 cross-check canonical_rules 的 fail-open 问题，当前 helper 是修复后的集中实现 (src/cuts/helpers/canonical_sot.py:9-14)。
- 代码内错误消息文本用了"Hall witness fails" (power_hitting_set.py:390-395) 这一措辞，但实际检查逻辑是 empty-cover-set 复验而非真正的 Hall 定理式匹配论证，属于命名/措辞与实际论证类型不一致的现象，值得在形式化前澄清。
