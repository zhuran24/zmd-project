# R2 回复逐字存档（GPT Pro，staged 分解轮，2026-07-20 回收）

> 提示词：`strict/internal/R2_prompt_send_20260720.md`（附严格三件套 zip，新对话、不接 R1 线程）。
> 判读见 `08_r2_judgment_20260720.md`。以下为回复全文，未作任何修改。

---

I treated `problem.md` as the semantic specification and `problem_instance.json` as the authoritative data. The JSON validates against the supplied schema. I also recomputed the sentinels independently: 219 manufacturing facilities, 266 required instances, 3,544 required body cells, and 628 active terminals. No implementation details are inferred from those files.

## Material ambiguities and explicit assumptions

1. **Anchors and local coordinates.** The specification does not explicitly define a facility anchor. I assume `(x,y)` is the southwest body cell, and body-local `(u,v)` maps to `(x+u,y+v)`. Pole coverage offsets use that same anchor.

2. **Boundary placement.** I interpret `left_boundary` as requiring anchor `x=0`, and `bottom_boundary` as requiring anchor `y=0`. Only the listed modes exist. I do not synthesize top-boundary or right-boundary rotations.

3. **Port binding.** Each physical port is either inactive or bound to exactly one commodity. Ports are distinct even when they have the same kind. For each manufacturing instance, the multiset of active input and output bindings is exactly its operation's `port_needs`.

   The generic provider lists are exclusive:

   * boundary-port and protocol-core outputs may provide only the two raw commodities;
   * protocol-core and storage-box inputs may consume only the two final commodities;
   * storage-box outputs are always inactive;
   * all other generic ports are inactive.

   There are exactly 46 boundary outputs plus 6 protocol-core outputs, matching the 52 required raw terminals, so all 52 are necessarily active under this interpretation. Their assignment as 34 `blue_iron_ore` and 18 `source_ore` is a decision.

4. **Access-cell sharing.** Several active terminals may have the same access cell. A single transport component in that cell must simultaneously contain every required incident input or output direction. An inactive port creates no access-cell restriction.

5. **Transport-cell semantics.** There is at most one transport component per non-body cell, and a cell may instead be empty. Component directions describe the neighboring side: an output in direction `E` connects to an input in direction `W` in the eastern neighbor. Unconnected component sides are allowed; the specification does not require every component side to have a neighbor.

6. **Exact component patterns.**

   * A straight has one input and the opposite output.
   * A turn has one input and one perpendicular output.
   * A splitter has one input and two or three distinct other outputs.
   * A merger has two or three distinct inputs and one distinct other output.
   * A crossing has two disjoint perpendicular straight channels, with each channel independently directed.

   A splitter gives directed transfer from its input to each output. A merger gives transfer from each input to its output. A crossing never transfers between its two channels.

7. **Commodity behavior.** The selected component topology is shared by all commodities. Commodities have no capacity or exclusivity costs and do not transform into one another. Reachability is checked separately by commodity. The specification does not prohibit a component carrying a commodity past a terminal for another commodity, so I impose no contamination or exclusive-use rule.

   Reachability is not a matching requirement. One output may reach several same-commodity inputs, and one input may be reachable from several same-commodity outputs.

8. **Auxiliaries.** "Any number" includes zero. A storage box may be active only as a final-product sink. Poles have no terminals and do not require power.

9. **Objective.** A rectangle is an integer-cell set [x,x+w-1]×[y,y+h-1], with w,h≥6. Required and auxiliary body cells are forbidden inside it; transport cells are allowed. Its value is (wh, min(w,h)), ordered lexicographically. A layout with no admissible rectangle receives a bottom value below every admissible pair rather than being declared geometrically infeasible.

10. **Meaning of "smallest explanation."** I use inclusion-minimal in a declared semantic interface vocabulary, not globally minimum cardinality. Several incomparable smallest explanations may exist.

11. **Solver result statuses.** Every exact component may return `FEASIBLE` with a witness, `INFEASIBLE` with a checkable proof, or `UNKNOWN`. `UNKNOWN` is never allowed to prune search.

## 1. Components and the exact rule for constraint ownership

The clean decomposition point is between **body-and-terminal design** and **transport topology**. Transport does not affect power or the body-only rectangle objective. Conversely, the body mask and active terminal incidences completely determine the environment in which transport must be synthesized.

I would use these components:

1. **Instance compiler and semantic validator**
2. **Lexicographic objective controller**
3. **Body, terminal, power, and rectangle master**
4. **Local transport-topology synthesizer**
5. **Commodity reachability checker**
6. **Proof-aware feedback manager**
7. **Independent final verifier**

The objective controller surrounds the solving loop. Components 3 through 5 form the actual nested feasibility procedure.

### Exact ownership rule

Assign every decision variable to one layer. For a primitive benchmark constraint (r), let scope(r) be all decision variables appearing in its semantics. Its authoritative owner is

owner(r) = max{owner(v) : v ∈ scope(r)}.

In words, the rule belongs to the latest component that owns any variable needed to state it exactly. A rule is not assigned merely because it is called "power," "routing," or "geometry."

A rule may also appear earlier only as a separately proved projection or necessary relaxation, as described in section 3. The independent verifier repeats every rule, but it is a checker, not the search owner.

### Master variables

Let X contain:

* anchor and listed mode for every required instance;
* optional storage-box presence, placement, mode, and final-terminal bindings;
* selected power-pole anchors;
* active/inactive status and commodity binding for each physical port;
* a witness rectangle (r_x, r_y, w, h).

The master derives the semantic routing interface

σ(X) = (B, T),

where:

* B(q) says grid cell q is occupied by a facility body;
* T(q,c,k,d) says an active terminal of commodity c requires a component incidence of kind k ∈ {input, output} and direction d at access cell q.

Facility identities, power coverage, and the objective are deliberately absent from the routing interface because routing does not depend on them once B and T are known.

### Routing variables

For each non-body cell q, the topology solver selects either empty or one of 48 legal directed patterns:

* 4 straights;
* 8 turns;
* 16 splitters;
* 16 mergers;
* 4 crossings.

No commodity-specific component-placement variables are needed. The same selected topology is traversed independently for all 19 commodities.

### Constraint placement

| Benchmark rule | Authoritative component | Reason |
| --- | --- | --- |
| JSON structure, identifiers, cross-references, sentinels, local ports inside bodies | Instance compiler | No solving variables |
| Every required instance placed exactly once in one listed mode | Design master | Placement variables only |
| Body inside 70 by 70 grid | Design master | Placement variables only |
| `left_boundary` and `bottom_boundary` placement | Design master | Placement variables only |
| Required, pole, and storage-box bodies do not overlap | Design master | All body variables are in the master |
| Manufacturing port counts and commodity restrictions | Design master | Binding and mode variables only |
| Exact generic raw and final terminal counts and provider restrictions | Design master | Binding and optional-box variables only |
| Storage-box outputs inactive; no intermediate storage transfer | Design master | Prevented by binding rules, not by routing |
| Active access cell is in-grid and body-free | Design master | Explicit body-and-terminal rule |
| Unbound ports may be blocked or outside | No constraint added | Explicit permission |
| Pole body placement and clipped coverage | Design master | Pole and powered-body variables are both master variables |
| Every powered facility has at least one covered body cell | Design master | Same variable scope |
| Witness rectangle bounds, minimum side, and body emptiness | Design master | Objective depends only on body variables |
| Component cell avoids bodies | Topology synthesizer | Involves both fixed body mask and topology variable |
| Straight, turn, splitter, merger, and crossing pattern legality | Topology synthesizer | Local component variable only |
| Required component direction at each active access cell | Topology synthesizer | Couples terminal interface to component pattern |
| One component serves all compatible active terminals sharing a cell | Topology synthesizer | Local conjunction of terminal incidences |
| Component-to-component directional adjacency | Topology synthesizer and graph builder | Determined by neighboring selected patterns |
| Crossing channel non-transfer | Topology synthesizer and graph builder | Affects graph construction |
| Multi-commodity sharing | Topology plus reachability checker | One shared topology, separate commodity traversals |
| Every output reaches some same-commodity input | Reachability checker | Global graph property |
| Every input is reached from some same-commodity output | Reachability checker | Global graph property |
| Separate regions for one commodity permitted | Reachability checker | No stronger connectedness condition is added |
| Capacity and throughput | Nowhere | Explicitly outside scope |
| Actual largest empty rectangle of a completed layout | Independent verifier | Recomputed rather than trusted from the witness |

### Why power is not a standalone sequential oracle

A power-feasible pole layout can block routing, while another pole layout for the same manufacturing placement may allow routing. Therefore a component that chooses one arbitrary power completion may not reject the manufacturing placement after its chosen poles fail routing.

The base architecture avoids that quantifier error by making pole choices part of X. An exact alternative is to move poles into a **joint power-and-routing recourse component** that searches over both pole placements and transport before rejecting the upper proposal. A greedy or independently finalized power layer is unsound.

### Sound auxiliary bounds

These are equivalence-preserving normalizations:

* At most **two storage boxes** are needed. Any active box must contain at least one of the two final terminals. A box with no active input can be removed, which frees body cells and removes a power obligation.
* At most **221 poles** are needed: 219 manufacturing facilities plus at most 2 active storage boxes. From any pole set, repeatedly remove a pole whose deletion leaves all powered facilities covered. In the resulting inclusion-minimal set, each pole has a distinct facility that no other pole covers.

These bounds preserve feasibility and cannot lower the objective.

## 2. The smallest sound rejection explanation

Consider any boundary between an upper component with semantic interface variables u and a lower component with private variables v. Let:

* D(u) be the independently defined interface-consistency rules;
* L(u,v) be the exact lower-layer rules;
* A(û) be the set of semantic literals describing the rejected proposal.

The lower component should return an inclusion-minimal set

C ⊆ A(û)

such that

D(u) ∧ ⋀_{ℓ∈C} ℓ(u) ∧ L(u,v)

is unsatisfiable.

Its mathematical meaning is:

> Every upper proposal satisfying all facts in C has no valid lower completion, regardless of how every fact omitted from C is chosen.

The feedback clause is

N_C(u) = ⋁_{ℓ∈C} ¬ℓ.

The master may add N_C, because every globally feasible solution must satisfy it.

For the outer routing boundary, the preferred vocabulary is semantic rather than solver-internal:

* body-blocked cell facts;
* active terminal incidence facts at access cells;
* when needed, exact high-level placement or binding facts linked to those derived facts.

A route explanation should not mention arbitrary clause numbers, branch decisions, or internal variable IDs.

### Minimality

The core is inclusion-minimal when, for every ℓ∈C,

D(u) ∧ ⋀_{ℓ'∈C∖{ℓ}} ℓ'(u) ∧ L(u,v)

is satisfiable.

Thus no single fact can be removed while retaining the rejection. Minimum-cardinality conflict extraction is unnecessary for correctness and can itself become a costly optimization problem.

### Independent checking

A rejection package contains:

1. the canonical semantic literals in C;
2. the no-good N_C;
3. a proof object for the unsatisfiability above.

The independent checker:

* verifies that every literal in C is true in the rejected proposal;
* expands each semantic literal using independently implemented channeling rules;
* verifies the lower infeasibility proof;
* verifies that the resulting clause is exactly the complement of the core.

If the producer claims the core is inclusion-minimal, it should additionally provide one satisfying completion for every one-literal deletion. Those witnesses make minimality independently checkable. Minimality is a performance property; the unsatisfiability proof is the soundness-critical part.

### Smaller feedback inside the routing layer

The reachability checker can usually return a graph separator rather than a generic topology no-good.

For example, suppose commodity c has output terminal o, and S is the set of topology vertices reachable from o, with no c-input in S. Any repaired topology must enable at least one directed arc in δ⁺(S). The checker returns:

* commodity c;
* terminal o;
* vertex set S;
* the boundary arcs or component patterns capable of enabling such an arc.

The topology solver learns a clause or inequality requiring one of those boundary arcs. Verification consists of graph traversal plus checking the cut boundary.

This separator rejects the current **topology**, not the outer body proposal. The topology solver must exhaust or prove infeasible all topologies for the fixed body-and-terminal interface before returning an outer no-good.

## 3. When a lower rule should appear earlier

Let the exact lower feasible projection be

P(u) ≡ ∃v, L(u,v).

An earlier representation E(u) is:

* **exact** when E(u) ⟺ P(u);
* **conservative and sound for pruning** when P(u) ⇒ E(u).

The conservative representation is therefore an outer approximation. It may retain infeasible proposals, but it may never reject a proposal that has a lower completion.

The reverse implication alone, E(u) ⇒ P(u), is only a sufficient-condition heuristic. It cannot be used to reject proposals or support an upper-bound proof.

### Soundness gates

A lower rule may be represented earlier only when all of these hold:

1. **Interface scope:** The representation uses only earlier variables or derived atoms with exact, checked channeling.
2. **Universal validity:** The implication is valid for every possible lower choice, not merely for lower solutions seen so far.
3. **Specification fidelity:** It introduces no capacity, separation, path-length, or exclusivity assumption absent from the benchmark.
4. **Exact arithmetic:** No floating-point rounding or unsafe big-M approximation can turn a necessary condition into an accidental exclusion.
5. **Independent auditability:** The implication has a small direct proof, a verified derivation, or a proof-producing compiler.
6. **Stable quantifiers:** Omitted lower decisions remain existential. A rule derived from one selected pole layout, terminal binding, or route is not valid for all alternatives.

These are mandatory for correctness.

### Performance decision criteria

After the soundness gates pass, promotion should depend on:

1. **Projection size:** Use an exact projection when it has a compact representation. Use a conservative projection when exact elimination would be exponential.
2. **Expected reuse:** Promote rules likely to eliminate many proposals or recur across objective bounds.
3. **Propagation-to-memory ratio:** Estimate rejected lower calls saved per byte of encoding and proof state.
4. **Checking cost:** Prefer projections whose proof can be checked more cheaply than invoking the lower solver.
5. **Incremental stability:** Prefer rules that remain valid as the objective threshold or incumbent changes.
6. **Conflict evidence:** Repeated lower conflicts with the same semantic cause justify adding a permanent earlier rule.
7. **Subsumption:** Do not add a new representation if existing earlier constraints already imply it strongly enough.

These are performance choices, not proof obligations.

### Benchmark-specific applications

A useful **exact** early projection is local access-cell realizability. For each access cell, conjoin all required component incidences from active terminals and require that at least one of the 48 legal component patterns contains them. This is the exact elimination of one local topology variable and is compact.

A useful **conservative** early projection is free-space connectivity. Ignore component directions and pattern restrictions, and compute connected components of non-body cells. For each commodity, every output access cell must lie in a free-space component containing at least one same-commodity input, and every input must lie in one containing at least one output. Directed routing implies this property, but the property does not imply routability.

The full directed routing projection should remain below. Its exact representation is likely much larger than the master itself.

## 4. Why the feedback preserves correctness and proves optimality

For a target objective value τ, let the globally feasible designs be

F_τ = { X : M_τ(X) ∧ ∃Z, R(σ(X), Z) },

where M_τ is the master theory including a rectangle witness meeting τ, and R is the exact routing theory.

After learning no-goods N_1,…,N_k, the live master is

M_τ^(k) = M_τ ∧ N_1 ∧ ⋯ ∧ N_k.

Every admitted no-good is proved necessary for lower feasibility, so the invariant is

F_τ ⊆ { X : M_τ^(k)(X) }.

Thus learned feedback can remove infeasible upper proposals but cannot remove a globally feasible one.

The feedback protocol has four proof-relevant outcomes:

* **Lower witness:** A concrete topology is returned. It is independently checked before the layout becomes an incumbent.
* **Structured necessary cut:** For example, a reachability separator. It is independently checked before use.
* **Certified interface no-good:** It excludes one or more designs with no lower completion.
* **UNKNOWN:** No pruning and no bound update occur.

Heuristic scores, preferred placements, suggested corridors, and warm starts may also be exchanged, but they have no logical effect.

### Progress and eventual completeness

The complete semantic domain is finite:

* required anchors and modes are finite;
* optional storage boxes can be restricted to two;
* poles can be restricted to 221 and each has a finite anchor domain;
* each of 4,900 grid cells has a finite transport state;
* terminal bindings and rectangle choices are finite.

Every lower rejection must exclude the current proposal. Therefore, even the full-assignment no-good eventually makes progress. With fair enumeration, complete exact solvers, and no permanent `UNKNOWN`, the nested process eventually returns either a feasible witness or a certified infeasibility result for each objective threshold.

Subset-minimal cores and strong separator cuts make that process faster, but are not required for the termination argument.

### Lexicographic optimality proof

For a body layout X, define

O(X) = max over body-free admissible R of (area(R), shorter(R)).

The master does not have to prove that its chosen rectangle is largest. The following equivalence is enough:

O(X) ≻ v ⟺ ∃R : R is body-free and value(R) ≻ v.

The final proof therefore consists of:

1. **A checked feasible layout** whose actual largest empty rectangle is independently recomputed as v* = (A*, s*).

2. **A checked upper-bound proof**, either as one strict-better infeasibility proof or as two lexicographic obligations: no feasible layout with an empty rectangle of area > A*, followed by no feasible layout with area A* and shorter side > s*.

A master infeasibility proof may rely on learned lower no-goods. The proof ledger therefore records:

* the base instance encoding;
* every admitted cut and its independent lower proof;
* the final master infeasibility proof referencing those cuts.

The verifier first checks each cut lemma, then checks the final infeasibility derivation. No solver's unverified "optimal" status is accepted.

### Independent feasibility audit

The final layout checker reconstructs everything from the certificate:

* every required ID appears exactly once;
* body cells, modes, and boundary placement;
* nonoverlap;
* exact terminal bindings and provider restrictions;
* active access cells;
* pole coverage;
* component patterns and adjacency;
* all 19 commodity reachability conditions;
* storage-box output inactivity;
* actual largest body-free rectangle.

Reachability can be checked by ordinary graph traversal. The empty rectangle can be recomputed using an independent exhaustive or maximal-rectangle algorithm. Neither requires trusting route paths or the objective value claimed by the solver.

## 5. The design most likely to exhaust 48 GB, and the exact restructure

The first design likely to hit the limit is an eager, commodity-expanded monolith, particularly one that materializes transitive reachability.

Under the stated placement assumptions, there are approximately:

* **3,971,152** legal required-instance placement alternatives if all anchors and modes are one-hot encoded;
* **4,601,025** admissible rectangle positions if every rectangle is enumerated;
* **456,190,000** entries in a naive 19×4900×4900 commodity reachability matrix.

That is before nonoverlap clauses, component-pattern constraints, learned clauses, branch state, and proof logging. Twenty-four parallel copies of such a model would turn 48 GB into confetti.

### Exact memory-safe restructure

1. **Use finite-domain placement variables.** Represent each facility with bounded anchor and mode variables. Generate occupancy implications and overlap conflicts sparsely or lazily instead of allocating a Boolean for every legal placement.

2. **Represent one rectangle, not all rectangles.** Use (x,y,w,h) and body-exclusion constraints. There are only 2,145 distinct objective value pairs from possible side lengths, so the objective controller can search thresholds without materializing 4.6 million rectangle-position literals.

3. **Use one local topology state per cell.** A cell needs one 49-valued state, empty plus 48 legal patterns. Do not introduce per-commodity component-choice variables.

4. **Replace transitive-closure variables with graph checks.** Given a topology, run reachability scans for the 19 commodities and add separator cuts lazily. This preserves exact reachability while avoiding an all-pairs matrix.

5. **Apply the sound auxiliary bounds.** Use at most two canonical storage-box slots and at most 221 canonically ordered pole slots, or a sparse set of selected pole anchors. Canonical ordering removes permutations without identifying semantically different layouts.

6. **Keep the active cut pool small.** Subsumption-test route no-goods, retain the strongest reusable cuts, and permit proof-supported clause deletion in the live solver. Stream the complete proof ledger to disk rather than retaining every historical derivation in RAM.

7. **Limit replicated solver state.** Use the 24 cores for graph checks, bounded portfolios, and a small number of route workers. Do not run 24 full copies of the master and its clause database.

8. **Fallback if pole variables dominate.** Move pole placement into a joint exact recourse formula ∃P,Z : power(X,P) ∧ body/interface compatibility(X,P) ∧ routing(X,P,Z). The witness rectangle remains in the master, and recourse poles are forbidden from intersecting it. The joint component may reject X only after proving that no combination of poles and transport works. This changes the decomposition, not the proof claim.

All of these transformations are either equisatisfiable encodings or proved normalizations. None replaces an exact rule with a heuristic. Lazy constraints remain proof-bearing, and any heuristic precheck that cannot prove a necessary condition is restricted to search ordering only.
