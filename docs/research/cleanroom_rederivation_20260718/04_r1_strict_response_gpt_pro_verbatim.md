# R1 严格版回复——GPT Pro 逐字存档（2026-07-20 送达）

> 干净房间重推第二轮（严格版）：owner 于 07-19 凌晨外发 `strict/external/` 三件套（problem.md + problem_instance.json + schema，zip 108,932 字节）+ `R1_prompt.md`（联网放开版），07-20 回复送达。本文为逐字存档；判读见 `05_r1_strict_judgment_20260720.md`。上一轮（自然语言版）存档在 `02` 号。

---

I treated `problem_instance.json` as authoritative. It validates against the supplied schema, and all sentinels recompute exactly: 266 required instances, 219 manufacturing instances, 3,544 required body cells, 628 active terminals, 17 operation groups, and 19 commodities.

## Material ambiguities and explicit assumptions

1. **Whether `port_needs` applies to every instance or to the operation group in aggregate.**
   I assume every manufacturing instance in group (g) receives exactly the listed per-facility input and output terminal multiplicities. This is consistent with the sentinel totals of 310 manufacturing inputs and 264 manufacturing outputs.

2. **How generic terminals are assigned.**
   I assume `raw_outputs` and `final_inputs` are exact totals across their listed provider templates. Protocol-core outputs and boundary-storage outputs may bind only the two listed raw commodities. Protocol-core and storage-box inputs may bind only the two listed final commodities. Intermediate commodities may not terminate at a storage box.

   There are exactly 52 eligible raw-output slots, namely 46 boundary outputs and 6 protocol-core outputs, and exactly 52 required raw outputs. Therefore every one of those output slots is active. Their commodity labels must total 34 `blue_iron_ore` and 18 `source_ore`.

3. **Meaning of `matching_map_boundary`.**
   I assume `left_boundary` means anchor (x=0), with (0\le y\le67), and `bottom_boundary` means anchor (y=0), with (0\le x\le67). No right-edge or top-edge placement is permitted because no such modes exist.

4. **Transport occupancy.**
   I assume at most one transport component occupies a non-body cell. A crossing is the only component with two channels in that cell, and its channels remain distinct. Empty transport cells are permitted.

5. **Dangling component arms.**
   The specification does not forbid an input or output arm whose neighboring cell has no compatible arm. I therefore allow dangling arms. They create no graph edge. Forbidding them would be an unsupported strengthening, although a returned witness can normally be pruned to remove them.

6. **Multi-commodity sharing and flow semantics.**
   I interpret each commodity as independently traversing the same directed channel graph. There is no conservation, capacity, contamination, matching, or one-to-one flow condition. For commodity (c),

   [
   \forall s\in S_c;\exists t\in T_c:s\leadsto t,
   \qquad
   \forall t\in T_c;\exists s\in S_c:s\leadsto t.
   ]

   This distinction matters because the instance's output and input counts are deliberately unequal for several commodities.

7. **Shared access cells.**
   Multiple active terminals may use the same access cell when one component there has all required compatible directions. This follows from `compatible_terminals_share_component: true`. Each active access cell must nevertheless be in-grid and free of every facility body, including auxiliary bodies.

8. **Auxiliary canonicalization.**
   An unused storage box can be deleted without damaging feasibility, so an optimal canonical layout contains at most two boxes, one for each required final-input terminal. A box can host both finals. Every selected box must host at least one active final input; all box outputs are inactive. Likewise, a pole that has no private power responsibility can be deleted.

9. **Objective occupancy.**
   Only facility body cells count against the empty rectangle. Transport components, including crossings, may lie inside it.

10. **Proof trust boundary.**
    A solver's "optimal" or "infeasible" status is not evidence by itself. Final acceptance requires exact integer semantics and an externally checkable unsatisfiability proof. Search may use any backend, but search logs, numerical bounds, and unproved cuts are non-authoritative.

## Useful certified preprocessing bounds

Several reductions should be proved by the normalizer before search begins.

### Boundary geometry collapses to 47 patterns

Each boundary body occupies three cells on either the left edge or bottom edge. A 70-cell edge can hold at most

[
\left\lfloor \frac{70}{3}\right\rfloor=23
]

such bodies. Since there are 46 bodies, every feasible layout has exactly 23 on each edge.

Twenty-three disjoint length-three intervals cover 69 of the 70 cells, leaving one gap. The gap coordinate must lie in

[
{0,3,6,\ldots,69}.
]

The left and bottom bodies intersect only at ((0,0)), so at least one edge must leave coordinate zero uncovered. Thus the complete boundary geometry is described by

[
(g_L,g_B)\in{0,3,\ldots,69}^2,
\qquad
g_L=0\ \lor\ g_B=0,
]

which gives (24+24-1=47) patterns.

This removes an enormous symmetry class. Boundary IDs can be assigned deterministically by sorting side and anchor.

### At least two power poles are required

One pole covers at most (12\cdot12=144) cells. Each of the 219 powered manufacturing facilities must contribute at least one distinct covered body cell because bodies do not overlap. Therefore

[
P\ge \left\lceil\frac{219}{144}\right\rceil=2.
]

Storage boxes, when present, can only increase this requirement.

### Initial area bounds

With (P) poles and (B) boxes, the number of non-body cells is

[
4900-3544-4P-9B.
]

Hence any empty rectangle of area (A) satisfies

[
A\le 1356-4P-9B\le1348.
]

Because almost all of the left and bottom edges are occupied and an admissible rectangle has both sides at least six, it cannot include column (0) or row (0). Its dimensions are therefore at most (69\times69). The largest integer rectangle product not exceeding 1,348 is 1,344, initially giving ((1344,32)).

The 46 boundary outputs provide a stronger bound. All are active, so their 46 inward access cells are mandatory non-body cells. For boundary pattern (\delta), let (Q_\delta) be this set. For a candidate rectangle (R),

[
|R\cup Q_\delta|
=A+46-|R\cap Q_\delta|
\le1348.
]

For each of the 47 patterns and every admissible integer dimension pair, define

[
M_\delta(w,h)
=\max_{x,y}|R(x,y,w,h)\cap Q_\delta|.
]

This is a tiny exact enumeration. There are only 1,182 unordered dimension pairs under the raw area cap. Applying

[
wh+46-M_\delta(w,h)\le1348
]

eliminates every lexicographic pair above

[
\boxed{(1326,34)}.
]

The area 1,326 case with the best shorter side is (34\times39). This is a certified starting upper bound, not a claim that 1,326 is feasible.

At any target area (A), the additional valid auxiliary cut

[
4P+9B\le1356-A
]

substantially bounds the number of pole and box variables.

# 1. Architecture: decomposed search, independent monolithic certification

The system should deliberately have two tracks.

### Practical optimizer

The practical search is decomposed into:

1. a geometry, power, and objective master;
2. a terminal-assignment and transport-routing subproblem;
3. an incumbent pool and large-neighborhood search workers;
4. a proof-aware rejection ledger.

This decomposition is valuable because, once the required bodies and at least two poles are placed, at most 1,348 cells remain available for routing. A fixed-geometry router is consequently much smaller than a monolithic model that must consider transport variants on all 4,900 cells while simultaneously moving 266 required bodies.

The geometry master also exploits indistinguishability within an operation group. It selects occupied footprints, not named instances. IDs are assigned later by sorting selected placements.

### Final certifier

The final upper-bound campaign does not trust the search decomposition or the completeness of its learned cuts. It independently constructs a complete finite model for the proposition:

> A valid layout exists whose objective is lexicographically better than the independently verified incumbent.

That proposition is proved unsatisfiable, with a proof checked outside the proving solver.

The final model is sharded by the 47 boundary patterns. Each shard is otherwise monolithic: geometry, modes, terminal binding, power, transport components, reachability, auxiliaries, and the better-objective condition all appear in the same semantic model. If a shard becomes too large, it may be divided further by rectangle-dimension sets, provided a manifest proves that the sets are disjoint and exhaustive.

This split has an important property: the practical optimizer may be clever, approximate, or use unproved guidance, while the final evidence remains simple in logical form. It consists of one feasible witness and an exhaustive set of checked no-better proofs.

## Practical search plan versus final evidence

A practical search should begin at the certified upper bound ((1326,34)), try objective pairs in descending lexicographic order, and run boundary-pattern shards in parallel. Heuristic workers may simultaneously search lower pairs to obtain an incumbent quickly. Exact workers continue closing the gap above that incumbent.

The final claim requires something different:

* A verified feasible layout establishes a lower bound ((A^*,s^*)).
* A checked proof that no layout satisfies
  [
  A>A^*
  \quad\lor\quad
  (A=A^*\land s>s^*)
  ]
  establishes the matching upper bound.
* Timeouts, lack of improvement, heuristic exhaustion, and an open branch-and-bound gap establish nothing about optimality.

If a feasible layout reaches ((1326,34)), the small combinatorial preprocessing proof already provides the upper bound. Otherwise, the monolithic proof shards must eliminate the remaining objective interval.

# 2. Where every rule is enforced

Let

[
C={0,\ldots,69}\times{0,\ldots,69},
\qquad
D={N,E,S,W}.
]

A cell is stored as the integer (70y+x). Footprints and coverage regions are sparse cell lists for constraints and 4,900-bit masks for fast intersection tests.

## Geometry-master variables

For operation group (g), let (P_g) be its possible anchor and footprint-orientation placements. Define

[
z_{g,p}\in{0,1},\qquad p\in P_g,
]

with

[
\sum_{p\in P_g}z_{g,p}=n_g.
]

Square manufacturing modes have a single footprint orientation in the master. Their actual input-to-output direction is deferred to the router. A (6\times4) facility has two footprint orientations, (6\times4) and (4\times6), while the router selects one of the two directional modes compatible with that footprint.

Additional variables are:

[
u_p\in{0,1}
]

for the protocol-core anchor,

[
d_\delta\in{0,1},\qquad \delta\in{1,\ldots,47},
]

for the boundary pattern,

[
e_a\in{0,1},\qquad a\in{0,\ldots,68}^2,
]

for pole anchors, and

[
b_p\in{0,1},\qquad p\in{0,\ldots,67}^2,
]

for storage-box footprints, with (\sum b_p\le2).

For every cell (c), all selected footprints covering (c) satisfy

[
\sum_{\text{placements }p:c\in B(p)}x_p\le1.
]

This single constraint family covers required bodies, boundary bodies, protocol core, poles, and boxes.

For a rectangle candidate (r=(x_r,y_r,w,h)),

[
x_p+r_r\le1
]

for every placement (p) whose body intersects (R(r)). Equivalently, selected rectangle cells have body occupancy zero.

The symmetry-reduced master has approximately:

* 36,992 footprint variables for the eight (3\times3) groups;
* 17,424 for the four (5\times5) groups;
* 43,550 for the five (6\times4) groups and their two footprint orientations;
* 3,844 protocol-core anchors;
* 4,761 pole anchors;
* 4,624 box anchors;
* 47 boundary-pattern variables.

That is roughly 111,000 top-level geometric variables before rectangle-choice variables, rather than several million named-instance placement literals.

## Power rules

For pole anchor (a=(a_x,a_y)), precompute

[
K(a)=
([a_x-5,a_x+6]\times[a_y-5,a_y+6])\cap C.
]

For every selected powered footprint (p),

[
x_p
\le
\sum_{a:K(a)\cap B(p)\ne\varnothing}e_a.
]

A more compact implementation introduces a Boolean `covered[c]` for every cell and links it to all pole anchors covering that cell. Then a powered footprint requires at least one `covered` body cell.

Pole bodies are part of the ordinary non-overlap and rectangle constraints. Storage boxes are powered in the same way.

## Mode and terminal variables

After geometry is fixed, the router creates a concrete facility token for each selected footprint.

For facility (f), legal mode (m), local port (p), and commodity (c), define

[
a_{f,m,p,c}\in{0,1}.
]

Exactly one legal mode is selected. At most one commodity is assigned to a port.

For a manufacturing instance in operation group (g),

[
\sum_{\substack{p:\operatorname{kind}(p)=\mathrm{input}}}
a_{f,m,p,c}
=N^{\mathrm{in}}_{g,c},
]

and similarly for outputs. Commodities absent from the corresponding operation requirement have count zero.

For the 52 generic raw-output slots (U),

[
\sum_{c\in{\text{blue ore, source ore}}}a_{u,c}=1
\quad\forall u\in U,
]

[
\sum_{u\in U}a_{u,\text{blue ore}}=34,
\qquad
\sum_{u\in U}a_{u,\text{source ore}}=18.
]

For eligible final-input slots (V),

[
\sum_{v\in V}a_{v,\text{qiaoyu capsule}}=1,
\qquad
\sum_{v\in V}a_{v,\text{valley battery}}=1.
]

Every selected box must receive at least one of these two bindings, and all of its outputs are fixed inactive.

For a port at body-local cell (q) facing (d), its access cell is

[
\operatorname{access}(f,p)
=(x_f,y_f)+q+\operatorname{unit}(d).
]

An active binding implies that this cell lies in (C) and has no facility body.

## Transport component variables

There are 48 directed component variants:

* 4 directed straights;
* 8 directed turns;
* 16 splitters;
* 16 mergers;
* 4 directed crossings.

For every free cell (v), choose either empty or one of these variants.

A convenient data structure is:

```text
ComponentVariant
    kind
    channels[]
        input_direction_mask     # four bits
        output_direction_mask    # four bits
```

A non-crossing component has one channel. A crossing has one horizontal and one vertical channel, each with one input and the opposite output. They are represented as separate graph nodes, which makes accidental transfer impossible.

For adjacent cells (v) and (v+\operatorname{unit}(d)), add a directed graph edge when the channel at (v) has output (d) and the neighboring channel has input (\operatorname{opposite}(d)).

An active facility output facing (d) creates an arc from its terminal into the access-cell channel whose input mask contains (\operatorname{opposite}(d)). An active facility input creates an arc from the corresponding channel output to its terminal.

## Reachability variables

For each commodity (c), the final proof model uses two parent forests.

A forward forest is rooted at channel nodes receiving an active output of (c). Every channel node feeding an active input of (c) must belong to this forest. A non-root member chooses one incoming graph edge as its parent and has a rank strictly larger than its parent.

A reverse forest is built on the reverse graph, rooted at nodes feeding active inputs. Every node receiving an active output must belong to it.

These two forests prove respectively:

* every input is reached from some output;
* every output can reach some input.

Ranks range from zero to the number of possible channel nodes. They rule out unsupported parent cycles. Multiple commodities may select the same graph edges without conflict.

## Rule-ownership summary

| Rule family                                   | Practical search owner | Final upper-bound model  | Feasible-witness checker      |
| --------------------------------------------- | ---------------------- | ------------------------ | ----------------------------- |
| IDs, counts, templates, schema                | Normalizer             | Independent encoder      | Direct checks                 |
| Body in-grid, boundary placement, non-overlap | Geometry master        | Included                 | Direct bitmap checks          |
| Modes and exact terminal counts               | Router                 | Included                 | Direct count checks           |
| Active access cells                           | Router                 | Included                 | Direct coordinate/body checks |
| Component legality and adjacency              | Router                 | Included                 | Reconstructed graph           |
| Commodity reachability                        | Router forests         | Included forests         | Independent BFS               |
| Pole bodies and coverage                      | Geometry master        | Included                 | Direct coverage checks        |
| Empty rectangle and lexicographic objective   | Geometry master        | Better-objective formula | Exhaustive rectangle scan     |

# 3. Component exchanges and rejection explanations

## Master-to-router record

A routing request contains no hidden solver state. It is a canonical record such as:

```text
GeometryCandidate
    instance_hash
    target_objective = (area, shorter_side)
    rectangle = (x, y, width, height)
    boundary_pattern = (left_gap, bottom_gap)
    manufacturing_footprints[]
        operation_group
        anchor
        footprint_orientation
    protocol_core_anchor
    pole_anchors[]
    storage_box_anchors[]
    body_bitmap[4900]
```

Manufacturing IDs are deliberately absent at this stage. Once routing succeeds, selected footprints in each operation group are sorted by `(y, x, orientation)` and assigned the group's listed instance IDs in lexical order.

## Successful router response

```text
RoutingSuccess
    facility_modes[]
    active_port_bindings[]
        facility_token
        port_id
        commodity
    transport_components[]
        cell
        component_variant
    forward_parent_forests[commodity]
    reverse_parent_forests[commodity]
```

The parent forests are useful search witnesses. The final layout checker nevertheless recomputes reachability rather than trusting them.

## Rejection response

Every hard rejection is a proof-carrying clause over a fixed interface-variable universe:

```text
RoutingReject
    candidate_hash
    core_literals[]
        interface_variable
        polarity
    learned_clause
    reason
        class
        commodity_or_facility
        optional_separator_or_port_set
    proof_hash
```

If the returned core is

[
C={\ell_1,\ldots,\ell_k}
]

and the subsolver proves

[
M\land\operatorname{Router}\land
\ell_1\land\cdots\land\ell_k
]

unsatisfiable, the valid master cut is

[
\neg\ell_1\lor\cdots\lor\neg\ell_k.
]

The assumptions may contain both positive and negative interface literals. This is important. A positive-only "these obstacles make routing impossible" explanation is not automatically sound because adding or relocating a source can sometimes repair commodity reachability.

The guaranteed fallback rejection is the exact-candidate nogood, which says that at least one decision in the complete candidate must change. Stronger explanations can be:

* a terminal Hall cut, identifying a facility whose required active ports outnumber body-free legal access positions;
* a commodity separator, identifying a set of body decisions that separates required sources and sinks even under optimistic component choices;
* a component-degree conflict around a congested access-cell set;
* a general mixed-literal unsatisfiable core.

The human-readable classification is diagnostic only. The proof object is authoritative. Any rejection that cannot be checked is usable as a heuristic penalty, never as a hard cut.

The final no-better proof does not need to trust even these checked search cuts, because it regenerates the complete model independently.

# 4. Three most likely failure modes

## 1. Semantic drift or accidental strengthening

The most dangerous mistakes are plausible-looking ones: enforcing output-input count balance, requiring all same-commodity terminals to lie in one region, forbidding dangling arms, treating transport as rectangle occupancy, or requiring all ports to have valid access cells.

Mitigations:

* commit the ambiguity-and-assumption list above as a hashed manifest;
* validate the schema and recompute all sentinels;
* maintain separately written search, layout-checking, and bound-checking code;
* test each rule on tiny generated instances with known answers;
* use only exact integer and Boolean arithmetic;
* compare forward and reverse BFS results against the router's forest witnesses;
* include negative tests that would fail under each common accidental strengthening.

## 2. Geometry-router thrashing and symmetry explosion

A geometry master may produce thousands of packings with blocked ports or impossible directed routing, while identical manufacturing facilities generate factorially many equivalent assignments.

Mitigations:

* aggregate indistinguishable instances by operation group during search;
* reduce all boundary geometry to the 47 exact patterns;
* defer square-facility directional modes and port bindings to the router;
* canonically assign required IDs only after success;
* cache rejections by normalized body bitmap and terminal-domain signature;
* generate local access-capacity cuts before invoking the full router;
* use optimistic free-space connectivity tests as inexpensive necessary conditions;
* minimize proof-carrying routing cores;
* run route-aware large-neighborhood search around the best layouts.

## 3. Proof artifact or RAM blow-up

A complete no-better encoding can contain millions of Boolean equivalents, and proof logs may be much larger than the formula itself.

Mitigations:

* start from the certified ((1326,34)) upper bound rather than the raw grid bound;
* bound poles and boxes separately for every target area;
* shard first by the 47 boundary patterns, and then by disjoint dimension bands only when necessary;
* cap concurrent proof workers by measured resident memory;
* stream proof segments directly into a checker instead of retaining an uncompressed monolith;
* retain a manifest of formula and proof hashes;
* disallow cross-shard learned lemmas unless each lemma carries its own checked derivation;
* make proof checking restartable and incremental.

If the proof campaign fails to close every shard, the system reports a feasible layout and a remaining proven upper bound. It does not report optimality.

# 5. CPU, memory, wall-clock, and parallelism

These are engineering estimates, not measured benchmark results. They assume a modern 24-core x86-64 Linux machine, fast local SSD storage, and at least roughly 300 GB of scratch space for proof artifacts. With less disk, proof generation should be streamed through the checker.

## Model-size estimate

The geometry master has about 111,000 top-level footprint and auxiliary variables. Sparse body-incidence data is around 2.2 million placement-cell incidences. A reasonable exact backend should fit this portion in approximately 3 to 6 GB.

For a fixed geometry, at most 1,348 cells are non-body. A router instantiated only on those cells has:

* about 66,000 one-hot component choices at 49 states per cell;
* at most 2,696 channel nodes because a crossing has two;
* roughly 102,000 forward/reverse commodity-membership variables before parents and ranks;
* ordinarily fewer than one million Boolean equivalents in total.

A routing worker should therefore target 1.5 to 2.5 GB.

The monolithic proof model operates on all 4,900 cells before body choices are resolved. Depending on the exact parent/rank or integer-flow encoding, it is likely to contain 8 to 20 million Boolean equivalents and tens of millions of constraints. A conservative working-memory target is 20 to 34 GB per large proof shard.

## Search-phase allocation

| Work                                           |    Cores | Memory target |
| ---------------------------------------------- | -------: | ------------: |
| Geometry/objective master                      |        4 |          6 GB |
| 10 to 12 independent router workers            | 10 to 12 |   18 to 24 GB |
| Heuristic and large-neighborhood workers       |   5 to 7 |     5 to 7 GB |
| Core minimizer, incumbent checker, coordinator |   2 to 3 |     3 to 4 GB |
| OS, shared cache, safety margin                |      n/a |     5 to 7 GB |

Peak search memory should be held below 42 GB. Router concurrency should be reduced automatically when measured resident memory approaches the cap.

## Proof-phase allocation

The default safe configuration is:

* one large proof shard using up to 18 to 20 cores and at most 34 GB;
* 2 to 4 cores for encoding, streaming proof checks, and manifest construction;
* at least 8 GB left for the operating system, file cache, and proof checker.

For smaller shards, two proof workers can run concurrently at roughly 16 GB each. The 47 boundary-pattern shards are embarrassingly parallel, but memory rather than core count determines concurrency.

## Wall-clock planning envelope

| Phase                                                  | Planning envelope |
| ------------------------------------------------------ | ----------------: |
| Parsing, validation, placement tables, analytic bounds |   under 5 minutes |
| Strong incumbent discovery                             |      1 to 8 hours |
| Exact search and gap closure above incumbent           |    12 to 72 hours |
| No-better proof production                             |    12 to 96 hours |
| Independent proof and witness checking                 |      1 to 8 hours |

A reasonable campaign budget is one to seven days. The upper end is dominated by proof production, not witness checking. No wall-clock deadline changes the evidentiary standard.

## Parallelizable work

The following can run independently:

* geometry heuristics with different seeds;
* routing attempts for different master candidates;
* the 47 boundary patterns;
* disjoint better-objective dimension bands;
* unsatisfiable-core minimization;
* the 19 commodity BFS checks;
* proof checking for separate shards.

The following retain serial dependencies:

* the branch-and-bound history inside one master shard;
* parent-proof generation within one proof shard;
* final manifest coverage verification;
* the final logical step combining a verified feasible objective with all no-better shards.

# 6. Independent feasibility and upper-bound checking

## Feasible-layout audit

The returned layout artifact should contain:

```text
LayoutWitness
    input_hashes
    assumption_manifest_hash
    claimed_objective
    claimed_empty_rectangle
    required_facilities[]
        required_id
        template
        operation
        anchor
        mode_id
        active_ports[{port_id, commodity}]
    auxiliaries[]
        generated_id
        template
        anchor
        mode_id
        active_ports[]
    transport_components[]
        cell
        variant
    optional_power_witnesses[]
        powered_facility_id
        pole_id
        covered_body_cell
```

A small, separately written `layout_check` program performs these steps directly:

1. Revalidate the authoritative JSON and sentinel totals.
2. Verify that every required ID appears exactly once and no unknown required ID appears.
3. Reconstruct every body cell from anchor and mode.
4. Check in-grid placement, the 46 matching-boundary rules, and complete body non-overlap.
5. Check exact manufacturing port counts and generic raw/final totals.
6. Check that every active access cell is in-grid and body-free.
7. Validate every component variant, including splitter and merger cardinalities and crossing channel separation.
8. Construct the directed channel graph from component directions and terminal attachments.
9. For every commodity, run:

   * a forward multi-source BFS from all active outputs and check every active input;
   * a reverse multi-source BFS from all active inputs and check every active output.
10. Check every powered facility directly against every selected pole's clipped coverage.
11. Build the complete body bitmap and recompute the layout's largest admissible empty rectangle.

For the last step, the grid is small enough that the checker can use a deliberately simple exhaustive method. A two-dimensional prefix sum permits enumeration of all in-grid rectangles with both sides at least six, followed by direct lexicographic maximization. This avoids trusting the rectangle named by the optimizer. A second histogram-based implementation can be run as a differential check.

The output is a signed or hashed report containing the recomputed pair ((A^*,s^*)), not merely a pass flag.

## No-better audit

Using only the original JSON, the assumptions manifest, and the verified pair ((A^*,s^*)), a separate `bound_check` codebase regenerates the no-better model.

For each boundary pattern (\delta), it constructs

[
\Phi_\delta(A^*,s^*)=
\operatorname{FullSpecification}_\delta
\land
\operatorname{BetterRectangle}(A^*,s^*),
]

where `BetterRectangle` is an explicit disjunction over pre-enumerated integer dimension pairs satisfying

[
wh>A^*
\quad\lor\quad
(wh=A^*\land \min(w,h)>s^*).
]

Pre-enumeration avoids trusting nonlinear multiplication inside the solver.

`FullSpecification` includes:

* every required body and allowed mode;
* optional poles and at most two used boxes;
* body and access-cell geometry;
* exact terminal bindings;
* every transport cell and component variant;
* forward and reverse commodity reachability;
* power;
* the selected body-free rectangle.

The proving backend emits a checkable unsatisfiability proof for every shard. The proof checker:

1. regenerates the exact finite formula;
2. verifies the formula hash;
3. checks every proof step;
4. verifies that the boundary patterns are precisely the 47 exhaustive patterns;
5. verifies that any dimension subshards are disjoint and cover every lexicographically better pair;
6. rejects missing, timed-out, or unchecked shards.

The final manifest should contain:

```text
OptimalityManifest
    problem_md_hash
    instance_json_hash
    schema_hash
    assumption_manifest_hash
    feasible_layout_hash
    verified_objective
    preprocessing_lemma_hashes[]
    proof_shards[]
        case_predicate
        formula_hash
        proof_hash
        checker_result
    partition_coverage_hash
    checker_build_hashes
```

The conclusion is then a two-line mathematical argument:

[
\exists\text{ valid layout with objective }(A^*,s^*)
]

from `layout_check`, and

[
\nexists\text{ valid layout with objective }>(A^*,s^*)
]

from the checked proof shards. Therefore ((A^*,s^*)) is optimal.

This audit path does not rely on the search algorithm having explored the right neighborhoods, on the master's lower bound, on a routing timeout, or on any hidden implementation detail.
