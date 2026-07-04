# Family 8: power_grid_reach（几何 cut family，处理"powered facility 的 CoverSet 非空，但从 protocol_core 出发的 pole-jump BFS 到不了任何覆盖该 facility 的 pole"这一全局电力连通性不可达情形）。

原文依据：
```
C:/claude pj/zmd-pj/docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md:35-46
Family 8 cut 表达:
∃ facility A with CoverSet(A) ⊆ V_pole_subset, V_pole_subset 不连到 protocol_core
                in G_power constrained by ghost
        ⇒ INFEASIBLE (A 永远无法供电)
跟 Family 7 power_hitting_set 区别 (key!):
- Family 7: A 的 CoverSet 空
- Family 8: A 的 CoverSet 非空但 candidate poles 跟 protocol_core
  跨 ghost 不可达
```
```
C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:9-12
F7 fires when CoverSet is empty ... F8 fires when CoverSet is non-empty but the
pole-jump BFS from protocol_core does not reach any candidate.
```
当前实现只允许单一 cert_kind："power_pole_bfs_disconnect_ghost"（其余变体 deferred）：
```
C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:4-6
Single cert_kind ... only "power_pole_bfs_disconnect_ghost".
The cell_owner-causes case ... and "exterior_blocks_jump" variant deferred to Phase 1.5+.
```

## proposition
精确量化命题（区分定理本体 vs 前提假设）：

给定 70x70 grid、powered facility pose A=(facility_group, facility_pose_id)、其真实 footprint facility_cells、protocol_core 的 9x9 footprint、canonical pole radius R、2x2 pole footprint、以及当前 ghost/exterior/current occupancy 状态。

定义 full free mask：
Grid \ (ghost_cells ∪ exterior_blocks ∪ cell_owner.keys ∪ facility_cells ∪ protocol_core_cells)

定义 P = 所有 2x2 footprint 完全落在 full free mask 内的 pole anchors。
定义 CoverSet(A) = P 中至少一个 pole cell 到至少一个 facility cell 的欧氏距离 ≤ R 的 anchors。
定义 power graph 的边：两个 pole/core footprint cell-pair 中存在一对 cell centers 满足 (a) 距离 ≤ R 且 (b) 两点连线不与 ghost AABB 相交。

【定理本体】：若 CoverSet(A) ≠ ∅ 且从 protocol_core 出发在该 power graph 中不可达任何 CoverSet(A) 中的 anchor，则该 pose A 在该 ghost/exterior/SoT 条件下无法被供电（不可行）。

【当前实现额外附加的前提】：还要求"去掉 cell_owner 后的 ghost-only graph 仍然断开"，以证明断开是由 ghost 单独造成、而非 cell_owner 造成（single-cause 归因前提，非定理本体的必要条件，而是当前证书 schema 选择只承认这一种因果归因）。

代码/文档证据：
```
C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:446-449
1. Full free mask excludes ghost ∪ exterior ∪ cell_owner ∪ facility ∪ pc footprint
2. CoverSet (facility) must be non-empty (else this is F7 territory)
3. Build power graph over the full pole-anchor set ∪ pc footprint
4. BFS from any pc cell must NOT reach any CoverSet pole
```
```
C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:407-427
Free-cell mask = grid - ghost - exterior - cell_owner - facility - protocol_core.
blocked = ghost_cells | exterior_blocks | cell_owner.keys | facility_set | pc_cells
return {(x,y) in 70x70 grid | not blocked}
```
```
C:/claude pj/zmd-pj/src/cuts/helpers/power_cover.py:101-123
compute_cover_set(...):
- enumerates valid 2x2 pole anchors in free_cells
- adds anchor if it covers any facility cell within pole_radius
```
```
C:/claude pj/zmd-pj/src/cuts/helpers/power_network.py:75-109
Jump iff ANY cell pair ... satisfies BOTH
(a) euclidean distance ≤ pole_radius AND
(b) the segment between cell centers does not intersect the ghost AABB.
```
```
C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:478-531
Ghost-only cause check:
Drop cell_owner from the mask ... if ghost-only power graph reconnects CoverSet
to protocol_core, cell_owner is the true cause; current single-cause ghost cert is unsound.
```
【单调性前提】（cut 之所以能对后续 state 有效的额外依赖，非本次命题本体，但被 evaluator 依赖）：
```
C:/claude pj/zmd-pj/docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md:75-79
state.free_cells 单调缩 (placement 加 cell_owner). pole candidate set 跟
free_cells 一致单调缩 → power network connectivity 单调减弱. 若 ghost-bound
state 下 BFS disconnect, 后续 state 仍 disconnect (单调保持).
```
evaluator 端对应依赖：`C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:780-786`（783-786 行左右）。

## argument_type
图可达性 / 图断连论证（graph reachability/disconnection argument），组合有限集合枚举（CoverSet、free-cell mask）与离散几何谓词（cell 间欧氏距离、线段-AABB 相交判定）。**不是** Hall 定理、LP 对偶/Farkas、最大流最小割、鸽笼计数、或序/置换论证。

依据：
```
C:/claude pj/zmd-pj/docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md:25-31
Power network ... 离散 pole 跃迁 graph:
- Pole pose q1, q2 互联 iff geometric distance ≤ R_conn
- protocol_core 是 source
- Power network = Graph G_power = (V_pole, E_jump)
```
```
C:/claude pj/zmd-pj/docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md:81-87
F5 反例数学:
ghost width = 15, pole R_conn = 10 ...
BFS from protocol_core ⊆ P_L, 终点不在 P_R → ... INFEASIBLE
```
```
C:/claude pj/zmd-pj/src/cuts/helpers/ghost_geometry.py:38-105
Liang-Barsky 参数化 line-AABB clip;
segment_intersects_aabb returns True iff segment p0→p1 intersects AABB.
```
```
C:/claude pj/zmd-pj/src/cuts/helpers/power_network.py:183-230
Build undirected jump graph among poles + protocol_core footprint.
Edge ... distance ≤ pole_radius AND segment does not intersect ghost AABB.
```
```
C:/claude pj/zmd-pj/src/cuts/helpers/power_network.py:276-339
any_target_reachable_from_pc: streaming reachability twin of build_power_network + bfs_component.
```

核心 soundness 论证结构 = "在有限图 G 中，若 source 不可达任何 target 集合的顶点，则不存在使 source-to-target 连通的可行方案"这一类图不可达论证，叠加"该图的顶点集/边集是由几何谓词（距离阈值 + 线段-矩形相交）在有限网格上枚举定义"的具体化。

## formalization_needs
**涉及的证明对象类型（事实观察，不做可行性结论）**：

1. **有限集合 / 有限网格对象**：70x70 cells、2x2 pole footprint、9x9 protocol_core footprint、free mask、CoverSet 均为有限集合上的运算（并、差、成员判定）。
   - `C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:74-76`, `:153-159`, `:407-427`
   - `C:/claude pj/zmd-pj/src/cuts/helpers/power_cover.py:36-42`, `:74-123`

2. **图论可达性**：无向图或 streaming BFS reachability，目标断言形式是 `¬ reachable(protocol_core, any target in CoverSet)`。
   - `C:/claude pj/zmd-pj/src/cuts/helpers/power_network.py:37-47`, `:233-254`, `:276-339`

3. **离散几何谓词**：cell-to-cell 欧氏距离不等式；线段与 AABB 相交/不相交（Liang-Barsky 参数化）。
   - `C:/claude pj/zmd-pj/src/cuts/helpers/power_network.py:54-55`, `:69-109`
   - `C:/claude pj/zmd-pj/src/cuts/helpers/ghost_geometry.py:38-105`

4. **单调性命题**：placement 增加 cell_owner 使 free cells 只减不增，connectivity 只减弱不增强（graph 顶点/边集合的单调收缩性质）。
   - spec 原文：`C:/claude pj/zmd-pj/docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md:75-79`
   - evaluator 侧对应依赖：`C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:780-786`（约783-786行）

5. **工程绑定谓词**（非核心图论定理，但 validator soundness 整体依赖它们把证书字段绑定到 state SoT）：JSON schema 校验、hash digest 重算比对、candidate_placements registry 查找、canonical_rules lookup、cell_owner ownership 逐格核验。
   - `C:/claude pj/zmd-pj/src/cuts/cert_schema.py:102-174`
   - `C:/claude pj/zmd-pj/src/cuts/lifecycle.py:443-461`
   - `C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:329-404`, `:534-650`

**观察到的"可抽象层"（跟具体 70x70 几何无关、可能可表达为一般化引理）**：

- "若所有可用 pole anchors 构成的图中 source 不可达 CoverSet，则没有 pole placement 能给该 facility 供电"——这是一般有限图 reachability lemma 的实例。对应证据：full pole anchor enumeration + BFS disjoint 的判定结构，`C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:446-449`, `:460-475`。

- "删除顶点/边不会创造新的 reachability"——这是一般图论单调性 lemma（子图的可达关系是原图可达关系的子集）。对应证据：spec 单调性依据 `08_power_grid_reach.md:75-79`，evaluator 端对应实现 `C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:783-786`。

- "CoverSet 非空 vs 空集"是 F7/F8 之间的有限集合条件分派（互斥覆盖两种情形），本身是纯逻辑上的集合判定。对应证据：`C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:9-12`, `:453-459`, `:504-514`。

**观察到的"绑死具体几何/实例数据"层（几乎必须逐个网格常量验证，难以抽象成通用引理）**：

- 70x70、2x2、9x9 这些具体尺寸常量，以及逐格 footprint/ownership 的具体检查，这些判定天然与"这个特定网格实例"绑定。对应证据：`C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:74-76`, `:153-159`, `:604-624`。

- candidate_placements 中某个具体 pose 的 `occupied_cells` 与证书里 `facility_cells` 逐一相等的比对，是针对该特定问题实例数据的绑定校验，非通用引理。对应证据：`C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:345-404`。

- `state.ghost_cells / exterior_blocks / cell_owner` 这些具体有限集合的取值、`ghost_rect` 这个具体 AABB、以及 canonical radius 目前是从 `power_coverage_radius` 这个（本意用于别处、被借用的）字段取值而非独立的 pole-to-pole jump radius schema——这既是具体实例数据绑定，也带有前面第6项提到的"字段语义借用"的工程未决问题。对应证据：`C:/claude pj/zmd-pj/src/cuts/helpers/canonical_sot.py:35-51`；caveat：`C:/claude pj/zmd-pj/src/cuts/oracles/power_grid_reach_oracle.py:198-200`。

- 旧欧氏 coverage model（power_cover.py 中）与 active certified path 实际使用的 12x12 square coverage stencil 之间的差异，是当前代码库里一个尚待"reconcile"的具体几何语义绑定问题，若要形式化必须先确定以哪个几何模型为准。对应证据：`C:/claude pj/zmd-pj/src/cuts/helpers/power_cover.py:14-21`。

## latent_issues
**Spec 文档明确列出的 Open Questions（原文摘录）**：
```
C:/claude pj/zmd-pj/docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md:397-410
## 10. Open questions

1. **Ghost-block-jump 算法**: cur §5a 简化 ghost 中心点 ∩ line(p1, p2). 真实
   pole-pole 跃迁应是 line-segment intersect ghost rectangle. Phase 1 真算法.
2. **v1.1 cell_owner 挤压 power network**: cur v1.0 单 cause = ghost. cell_owner
   挤压 (相邻 pole 候选被 facility 占) 也可 disconnect. Phase 1 加 causation
   split sub_kind (类 F7).
3. **Multi-facility shared disconnect**: 多 facility 都在 target_component, 1
   cut 拦 1 facility. cut store 累积 N facility 的 N cut → 是否合并 region-cut.
4. **Protocol_core 多个 case**: 现 spec 假设 protocol_core 唯一 source. canonical_rules
   有 1 个 protocol_core 但游戏未来扩展可能多源. Phase 2 generalize.
5. **跟 belt routing 配合**: belt 经过 ghost 的 case 跟 power 不一样 (belt 连续
   free_cells, power 跨 cell pole jump). cut 应分发到 Family 4 vs Family 8.
```

**代码中相关的 defer/caveat 原文**：
```
C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:4-6
Single cert_kind ... only "power_pole_bfs_disconnect_ghost".
The cell_owner-causes case ... and "exterior_blocks_jump" variant deferred to Phase 1.5+.
```
```
C:/claude pj/zmd-pj/src/cuts/helpers/power_cover.py:14-21
This helper uses the older F7/F8 Euclidean cell-distance model...
active certified path and frozen candidate geometry use ... 12x12 square coverage stencil...
F7/F8 remain non-certified / not applied to the master until P1.3 reconciles this landmine;
do not treat this helper as the canonical live coverage semantics.
```
```
C:/claude pj/zmd-pj/src/cuts/oracles/power_grid_reach_oracle.py:17-18
pole_jump_radius missing → [] (caller responsibility, Phase 1.5+ wires
from a canonical_rules field that does not yet exist)
```
```
C:/claude pj/zmd-pj/src/cuts/oracles/power_grid_reach_oracle.py:198-200
pole_jump_radius: float pole-to-pole jump radius. canonical_rules does
not currently expose a separate field for this (Phase 1.5+ work);
callers must pass explicitly.
```
```
C:/claude pj/zmd-pj/src/cuts/families/power_grid_reach.py:832-835
Phase 1.5+ may add a wider by_cell watcher covering the full pole
anchor enumeration neighborhood ... so cell_owner releases that reconnect the power graph re-trigger replay;
Phase 1.2 keeps the watcher tight...
```

**已修复历史 bug 的记录**（spec 曾记为"绝对 unsound"、代码已修）：
```
C:/claude pj/zmd-pj/docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md:12-19
（spec v1.1 记录：v1.0 的 ghost center-line 简化算法"绝对 unsound"，改用 Liang-Barsky 精确线段-AABB 相交）
```
```
C:/claude pj/zmd-pj/src/cuts/helpers/power_network.py:3-8
（当前 helper 注释说明该 shortcut 造成的 critical false-negative bug 已修复）
```

**总结要点**：(a) F8 当前只承认单一 cert_kind（ghost 单因），cell_owner 因导致断连的情形被显式 deferred；(b) power_cover.py 的欧氏 coverage 模型与 active certified path 使用的 12x12 square stencil 不一致，代码注释明确称这是"landmine"，F7/F8 本身"non-certified / not applied to master"；(c) pole_jump_radius 目前借用 `power_coverage_radius` 字段，独立的 pole-to-pole jump radius 字段在 canonical_rules 中尚不存在；(d) protocol_core 假设唯一 source，未来多源需泛化；(e) multi-facility 共享同一断连 component 时如何合并 cut 未定。
