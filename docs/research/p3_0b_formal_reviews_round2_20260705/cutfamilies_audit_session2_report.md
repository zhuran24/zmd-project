# CutFamilies.lean statement-fidelity adversarial audit

Status: patches in `CutFamilies_statement_patches_uncompiled.lean` are **uncompiled** because this sandbox image has no `lean`/`lake` executable. They are replacement/reference theorem segments in Lean 4 style.

## Summary table

| # | theorem | verdict |
|---:|---|---|
| 1 | `f9_area_bound` | 忠实 |
| 2 | `f9_overflow_infeasible` | 忠实 |
| 3 | `f1_occupancy_bound` | CONCERN |
| 4 | `f1_demand_overflow_infeasible` | CONCERN |
| 5 | `f7_cover_filter_monotone` | CONCERN |
| 6 | `f7_empty_cover_monotone` | CONCERN |
| 7 | `f4_closed_set_absorbs_reach` | 忠实 |
| 8 | `f4_unreachable_outside_closed` | 忠实 |
| 9 | `f4_subgraph_reach_mono` | 忠实 |
| 10 | `f6_strip_capacity` | 忠实 |
| 11 | `f6_packing_bound` | CONCERN |
| 12 | `f6_packing_overflow_infeasible` | CONCERN |
| 13 | `f6_cross_side_lower_bound` | 忠实 |
| 14 | `f2_cutset_bound` | CONCERN |
| 15 | `f2_demand_overflow_infeasible` | BLOCK |
| 16 | `f3_blocked_port_infeasible` | 忠实 |
| 17 | `f3_pair_literal_cut_sound` | BLOCK |

## Findings

### F1: demand expansion is hidden behind an arbitrary instance set `S` — CONCERN

Affected: `f1_occupancy_bound`, `f1_demand_overflow_infeasible`.

Root cause: the survey proposition is group-demand based: `Σ demand(g) * cells_per_pose(g) > cap_R`. The Lean statement is already after an instance expansion into a finite set `S` with per-instance `cells`. That is a defensible abstraction, but the theorem statement/docstring does not expose the proof obligation that `S` really contains all required demanded instances.

Minimal counterexample: one group `g`, `demand(g)=2`, `cells_per_pose(g)=3`, `Free.card=5`. The survey fires because `6 > 5`. If the engineering binding accidentally instantiates `S` with one instance, the Lean theorem only sees `3 ≤ 5` and gives no contradiction. The theorem is not false; the concern is that a required binding premise is invisible.

Impact: a dropped demand instance or bad group-to-instance expansion can make the formal theorem green while the report-side proposition was never discharged.

Patch: see `f1_region_capacity_bound` and `f1_region_capacity_overflow_infeasible` in the patch file. They add `requiredCells` and `hdemand : requiredCells ≤ ∑ i∈S, cells i`.

### F7: current theorem is only a filter monotonicity skeleton, not the ghost-bound 2×2-footprint empty-cover statement — CONCERN

Affected: `f7_cover_filter_monotone`, `f7_empty_cover_monotone`.

Root cause: the survey's current implementation uses pole anchors whose 2×2 footprint must be fully inside a free-cell set, and sound single-literal reuse needs owner-insensitive `ghost/exterior` scope emptiness. The Lean theorem models only `Free.filter CanCover`, where `CanCover` is independent of `Free`, so the footprint-free obligation and the ghost-only emptiness guard are outside the theorem.

Minimal counterexample: suppose current `cell_owner` blocks all pole anchors, so the full-free cover set is empty, but after that owner is removed there is a valid pole anchor. The survey says this is exactly why the validator also checks ghost-only emptiness. The Lean theorem can only be applied when the replay free set is a subset of the old `Free`; it does not tell the reader which `Free` must be the stable ghost scope.

Impact: as written it is safe as a small monotonicity lemma, but too easy to mis-instantiate with current full-free anchors rather than ghost-scope anchors. That would turn a true lemma into a white proof at the integration boundary.

Patch: see `F7CoverSet`, `f7_cover_set_monotone_with_footprint`, and `f7_empty_cover_ghost_scope` in the patch file.

### F6: bucket/function abstraction hides the “pose belongs to some interval” proof obligation — CONCERN

Affected: `f6_packing_bound`.

Root cause: the theorem takes a total `bucket : ι → κ` and assumes `seg i ⊆ interval (bucket i)`. The survey-side statement says a legal 1×L pose cannot cross ghost/exterior, hence it must be wholly inside some maximal unblocked interval. That existential proof obligation is the bridge from geometry to the counting lemma; the current statement makes it an opaque parameter.

Minimal counterexample: with intervals `{a}` and `{b}`, `L=2`, an abstract segment `{a,b}` has two free cells but is not inside either interval. The theorem excludes it by lacking a bucket, but the statement itself does not expose that geometry/contiguity must rule such segments out.

Impact: acceptable as an internal counting lemma, risky as a theorem claimed to correspond directly to “pose 不跨阻挡”. If the validator never proves the bucket/existence side, the theorem becomes vacuous for the problematic placements.

Patch: see `f6_packing_bound_exists_bucket`, which replaces the preselected function with `∀ i∈S, ∃ j∈J, seg i ⊆ interval j`.

### F6: certified `d_R` lower bound is not combined with the capacity contradiction — CONCERN

Affected: `f6_packing_overflow_infeasible`.

Root cause: the current validator proposition is `C_R < d_R ≤ max(0, D − C_R') ⇒ INFEASIBLE`. The Lean file has the direct side-capacity theorem `C_R < S.card ⇒ impossible` and separately has `D − C' ≤ x`, but no theorem that combines the certified `d_R` with side capacity.

Minimal counterexample: `D=10`, other-side capacity `C'=6`, certified lower bound `d_R=4`, and this-side capacity `C_R=3`. Survey fires from `3 < 4 ≤ 10−6`. The Lean overflow theorem needs `3 < S.card`, where `S.card` is the actual unknown number of placements on that side; the missing step is exactly the cross-side lower-bound composition.

Impact: not unsound, but the report proposition is split across lemmas without the actual validator fire shape. An integration proof could forget to compose them.

Patch: see `f6_region_demand_overflow_infeasible` in the patch file.

### F2: counting lemma assumes “every route hits δ”; survey proposition gets this from graph separation — CONCERN

Affected: `f2_cutset_bound`.

Root cause: the theorem is a correct pigeonhole lemma under `hhit`, but the survey proposition includes the graph facts: A/B partition, no escape, commodities on opposite sides, and `δ` as the crossing cut. Those facts are supposed to imply `hhit` for every legal route. The theorem itself does not represent that implication.

Minimal counterexample: if `δ = ∅` and a route uses an edge outside `δ`, the route is edge-disjoint and legal in some graph, but it does not satisfy `hhit`. The theorem remains true, yet it is not the graph cutset proposition.

Impact: fine as a helper, not fine as the sole formal statement of F2 soundness unless a separate separator lemma is explicitly required.

Patch: see `f2_cutset_infeasible_from_separator`, which requires a `Legal` routing predicate and a separator premise turning every legal routing into `hhit`.

### F2: `f2_demand_overflow_infeasible` overclaims “no legal routing” — BLOCK

Affected: `f2_demand_overflow_infeasible`.

Root cause: the conclusion is `¬ (hhit ∧ hdisj)`. The docstring says “不存在边不相交的合法路由”. Those are not the same unless “legal” is defined to include `hhit`, which is not how the survey describes route legality; `hhit` is derived from the cut/enclosure construction.

Minimal counterexample: one route, one edge `e`, `edges r = {e}`, `δ = ∅`. Then `δ.card < routes.card` holds. A legal edge-disjoint routing may exist in a graph where `e` connects source to sink without crossing this bogus `δ`. The Lean theorem only proves the route does not hit `δ`, not that the route is illegal.

Impact: this is a statement-fidelity block. The theorem can be misread as cut soundness while it only refutes a conjunction that includes the missing separator obligation.

Patch: replace/augment with `f2_cutset_infeasible_from_separator` from the patch file and weaken the docstring of the raw theorem to “hit-cut routing impossible”, not “legal routing impossible”.

### F3: pair literal theorem claims multiset semantics but uses `Finset` — BLOCK

Affected: `f3_pair_literal_cut_sound`.

Root cause: survey/lifecycle semantics is literal multiset subset matching over anonymous slots. The theorem quantifies `selected : Finset ι` and `{A, B} ⊆ selected`, which collapses multiplicity. The docstring explicitly says “literal 子多重集匹配语义”, which is stronger than what is formalized.

Minimal counterexample: a literal cut multiset `[l, l]` should require two occurrences of `l` in the selected-pose multiset. In `Finset`, `{l, l} = {l}`, so one occurrence is enough to satisfy the theorem's subset premise. This is not the lifecycle evaluator semantics.

Impact: if duplicate group/pose literals can arise across anonymous slots, the theorem proves a different cut body. Even if current F3 usually has distinct A/B literals, the docstring is false as written and hides a future landmine.

Patch: see `PortExposureFreeMulti` and `f3_pair_literal_cut_sound_multi` in the patch file.

## Explicit non-findings

F9 was not marked: `A ∩ W ⊆ W \ B` is exactly the set-level consequence needed for the area inequality. The survey's “cell_owner well-formed, no ghost/exterior, at most one owner” is stronger than the theorem needs; “at most one owner” disappears because `A` is already the set of cells owned by group `g`, not a multiset of claims.

F4 was not marked: the three theorems cleanly cover closed reachable-set absorption, unreachable outside a closed set, and subgraph reachability monotonicity. The 70×70/free-cell/commodity registry binding is correctly outside this abstract layer.

F6 `f6_cross_side_lower_bound` was not marked: Lean's `D - C'` on naturals is exactly the report's `max(0, D-C')`.

F3 `f3_blocked_port_infeasible` was not marked: it faithfully captures the implemented `cell_owner` blocker branch, with all-ports-active represented by quantification over `ports A` and `frontCell` abstracted as an engineering obligation.
