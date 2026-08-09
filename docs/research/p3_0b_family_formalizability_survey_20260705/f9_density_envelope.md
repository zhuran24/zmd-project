# F9 — density_envelope（cut family 09）。Spec: docs/research/p3_b_design_v2_20260521/cut_family_specs/09_density_envelope.md（下称 Spec）；实现: src/cuts/families/density_envelope.py（下称 Impl）；oracle: src/cuts/oracles/density_envelope_oracle.py（下称 Oracle）。

codex 原话说明：路径缩写 `Spec` = `docs/research/p3_b_design_v2_20260521/cut_family_specs/09_density_envelope.md`；`Impl` = `src/cuts/families/density_envelope.py`；`Oracle` = `src/cuts/oracles/density_envelope_oracle.py`。

## proposition
codex 原话（一字未改）：

当前实现编码的是离散几何面积上界：

`Grid70 = {0..69} x {0..69}`。对任意 state `s`、矩形 window `W=[x,x+h)×[y,y+w)`、group `g`，令 `B = ghost_cells ∪ exterior_blocks`，`safe_ub(s,W)=|W|-|B∩W| = |W\B|`。若一个布局是 well-formed，即 group-owned cells in `W` 只能落在 `W\B`，则
`|{c∈W | owner(c).group=g}| ≤ safe_ub(s,W)`；所以若 `|{c∈W | owner(c).group=g}| > safe_ub(s,W)`，该 candidate 布局不可行。证据：window 限在 70×70，`Impl:81-104`；safe bound 是 `|W|-|(ghost∪exterior)∩W|`，`Impl:275-305`；evaluator 数 `cell_owner` 中 group `g` 落在 W 的 cell，严格 `>` 才 fire，`Impl:517-566`。

注意 spec 有历史层：早期 §1 仍写 instance-count `sum 1[placement∩W≠∅] > K`，`Spec:56-65`；但 changelog v1.4/v1.5 已改成 area-based `witness_area_in_W > max_allowed_area`，`Spec:39-50`，当前实现也锁定 area-only、非 instance count，`Impl:3-12`。

更强的事实：validator 现在要求 `cert.max_allowed_area == safe_ub`，`Impl:343-367`，同时要求 witness union area `> max_allowed_area`，`Impl:411-432`；但 witness area 是 `occupied_cells ∩ W` 去重后再排除 `ghost/exterior`，即 `W\B` 的子集，`Impl:370-408`。因此正常 well-formed 语义下，validator OK 近乎/实际上是 vacuous；测试也把 tight K 改成 fail-closed，`src/tests/cuts/test_family_density_envelope.py:556-559`、`:912-916`。项目说明明确说 tight-K quarantined、F9 非当前 production proof authority，`docs/项目说明/02_mathematical_foundations.md:519`，设计不变量也说实质停用，`docs/项目说明/04_design_invariants.md:106`。

## argument_type
计数/鸽笼 | 几何(区间/线段/矩形 window)

codex 原话（一字未改）：

属于有限集合计数/面积容量论证 + 离散几何矩形/window 论证。核心是 `|owned_g∩W| ≤ |W\(ghost∪exterior)|`，证据同上 `Impl:275-305`、`:517-566`。也用了 set union 去重避免重叠 pose double count，`Impl:370-408`。

不属于 Hall、max-flow/min-cut、LP dual/Farkas、图可达性。spec 明确把 routing/binding/pcr overflow 泛化成密度 cut 判为 unsound 并 fallback F5，`Spec:29-38`、`:174-182`；项目说明同样说这些死锁依赖端口/相对位置/障碍，不能泛化成 density，`docs/项目说明/02_mathematical_foundations.md:474-480`。

## formalization_needs
codex 原话（一字未改）：

当前 soundness 核心只需要：有限集合、矩形 membership、集合并/交/差、cardinality inequality、自然数/整数比较、finite map/list/multiset 基础。可在抽象有限 grid 上证明，不必绑定 70×70；70×70 只是 parser/schema 边界，`Impl:81-99`。

需要作为前提或另行形式化的工程语义：`cell_owner` well-formed，不包含 ghost/exterior cells，且每 cell 至多一个 owner；代码注释把这个当 evaluator 语义前提，`Impl:388-393`。JSON 解析、SHA/hash、source_digest 可以在 Lean soundness theorem 外抽象成"已得到 typed cert 且 replay scope matches"，否则要形式化 byte-level JSON/SHA，不划算。

若未来要形式化旧目标"validator 通过 tight `K < safe_ub` ⇒ 母问题不可行"，当前代码没有证书字段支撑；那会需要 proof-carrying area-capacity oracle 的数学库，可能涉及更强的 packing/geometry/flow/belt 约束。但这不是当前 F9 实现已经具备的内容，`Impl:326-332`、`Spec:391-393`。

（分层小结：可在抽象层完成的部分 = 有限集合基数不等式 `|A∩W| ≤ |W\B|`（`|B|` 任意有限集合，不依赖具体坐标数值），这部分数学内容与网格大小无关；绑死具体 70×70 网格/几何常量的部分 = window 边界算术 `x+h<=70, y+w<=70`（`Impl:81-99`，纯 schema/parser 边界，非数学论证核心）；工程侧但非纯数学的前提 = cell_owner 的 well-formed 语义（无 ghost/exterior 越界、每 cell 单一 owner）需要作为公理/前提引入，而不是从 validator 代码本身重新证明。）

## latent_issues
codex 原话（一字未改）：

- tight-K quarantine：Phase 1.2 cert 没有 replayable tight-bound proof；恢复 tight F9 需要 Phase 1.5+ proof-carrying 字段 + replay 校验，`Spec:391-393`，`Impl:326-332`、`:355-363`。
- dynamic bound/other-group occupancy 被排除，避免 TOCTOU；更强 bound 需要新 cut/证明，`Impl:282-294`。
- generator witness 由 Phase 1.5+ caller 负责，当前 oracle 是 stub-friendly entry point，`Oracle:14-15`。
- spec 里的 window minimize 未实施，`Spec:218-230`；K binary search 只是 advanced/minimize 设想，`Spec:234-240`。
- spec 列 5 个 open questions：window algorithm、K binary search、multi-group window、translation lift、D2 dual lift，`Spec:353-363`。
- lifecycle 层 Step 8 master integration 未实现，`src/cuts/lifecycle.py:1117-1125`；Step 2 minimize 也仍是 stub，`src/cuts/lifecycle.py:731-740`。
- related helper 有方向原语的 latent landmine 注记，不过 F9 当前只用 `occupied_cells`，不使用方向 offsets，`src/cuts/helpers/candidate_placements.py:56-61`。

另需注意（同样来自 codex 的正文分析，非独立结论）：由于 validator 要求 `cert.max_allowed_area == safe_ub`（既不能大于也不能小于）且 witness area 必须是 `W\B` 的子集却又要求 `> max_allowed_area = safe_ub = |W\B|`，这在 well-formed 布局语义下使 validator 的 OK 语言近乎/实际为空（vacuous），测试文件也把 tight K 场景标记为 fail-closed（`src/tests/cuts/test_family_density_envelope.py:556-559`、`:912-916`）——这是从代码逻辑直接读出的结构性观察，不是 codex 自称的 bug 承认，但与「tight-K quarantine」这条自认限制一致对应。
