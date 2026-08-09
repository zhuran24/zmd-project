# R3 回复逐字存档（GPT Pro，方法论移植轮，2026-07-20 回收）

> 提示词：`strict/internal/R3_prompt_send_20260720.md`（附严格三件套+`R3_methodology_brief.md`，新对话）。
> 判读见 `10_r3_judgment_20260720.md`；双证书复算脚本 `verify_r3_certificates.py`。以下为回复全文，未作修改。

---

# 1. Critique of M1–M6

The brief is directionally sound, but its central picture is too reactive for this instance. The decisive work should happen before a global solver sees a candidate. Two small, domain-level counting certificates appear strong enough to cap the objective at (1190,34). That changes the engineering problem from "optimize a giant integrated model" into "construct one highly constrained witness at a known ceiling."

**M1, layered decomposition and rule ownership.** The "earliest workable layer owns the rule" criterion is not quite right here. A rule should have several representations with different logical polarity:

1. a necessary projection used for upper bounds;
2. a sufficient restriction used to construct a witness;
3. its exact semantics in the final checker.

Power is the clearest example. A local weighted packing certificate belongs in the upper-bound proof, exact pole coverage belongs in the constructor, and literal body-cell coverage belongs in the checker. Routing similarly appears as a four-terminals-per-access-cell bound above, a fixed-cycle bus below, and exact directed reachability in verification.

I would replace single ownership with a **semantic ledger**. Every rule gets entries for necessity, sufficiency, and exact verification. Some entries may be empty, but they must never be conflated.

**M2, feedback language.** Generalizing rejection explanations are useful, but the brief overstates the importance of iterative rejection. For this benchmark, the first priority is to avoid generating doomed candidates at all. The near-optimal geometry is so dense that area, terminal-access, and power arguments expose most of its structure analytically.

When rejection is needed, "checkable" is insufficient unless the explanation also carries its antecedent. A route separator cut, for example, must say which body placements and terminal locations make the separator relevant, and must include the repair disjunction. Otherwise the cut can accidentally remain active after moving a terminal or freeing a cell.

I would add a rule that every learned cut be represented as:

    antecedent configuration ⟹ necessary repair disjunction.

**M3, the lift loop.** M3 is too reactive. The strongest lift here does not have to emerge from a treadmill. It can be mined proactively by solving a tiny local dual problem around one power pole and translating the resulting weight stencil over the map.

M3 also misses **equality-case mining**. Once a global inequality is nearly tight, every constituent inequality becomes a source of structural constraints. At the upper target, equality arithmetic forces exactly nine poles, no storage boxes, only 130 nonbody cells outside the empty rectangle, and at least 108 terminals entering the rectangle. These are not just observations. They are the design specification for the constructor.

I would extend M3 with:

> Search small local packing relaxations for rational dual certificates, sum them globally, then mine all near-equality conditions as construction constraints.

**M4, the funnel.** The stages are sensible, but their linear order is too rigid. Tiny exhaustive or LP-dual micro-models should come before any global build-only audit. Here, an 840-placement local power problem is vastly more informative than building even a relaxed global model.

I would insert a "micro-oracle" stage between premise checks and global model construction. Its jobs are to solve local packing problems, rationalize their duals, search for counting invariants, and test whether those invariants survive exact enumeration.

**M5, proof trust.** M5 correctly distrusts solver status, but it understates the encoding gap. An LRAT or VeriPB proof establishes the generated formula, not the intended benchmark. A flawless proof of a mistranslated model is still the wrong proof.

The trust boundary therefore needs three parts:

1. a domain-level certificate or an independently checked semantic compiler;
2. a proof checker for any SAT or pseudo-Boolean artifacts;
3. an exact witness checker using the original JSON instance.

Lexicographic optimality also needs two explicit gates. Proving "no area above A" does not by itself prove the shorter-side tie-break.

**M6, reporting.** M6 is good but not operational enough. I would require separate ledgers for lower and upper results. A feasible layout raises only the lower ledger. A relaxation certificate lowers only the upper ledger. "Optimal" is emitted only when both ledgers meet at the same pair under the same instance hash and assumptions.

Resource aborts also belong in this ledger. A timeout changes no mathematical status.

---

# 2. The attack I would actually run

## 2.1 Start with two domain certificates, not a global optimizer

The authoritative instance gives the following exact totals:

| Quantity | Value |
| --- | ---: |
| Grid cells | 4,900 |
| Required body area | 3,544 |
| Powered manufacturing body area | 3,325 |
| Powered manufacturing facilities | 219 |
| Manufacturing input terminals | 310 |
| Manufacturing output terminals | 264 |
| Raw output terminals | 52 |
| Final input terminals | 2 |
| Total active terminals | 628 |
| Active outputs | 316 |
| Active inputs | 312 |

The first goal is to prove a strong objective ceiling using only facts every feasible layout must satisfy.

## 2.2 Certificate A: a local dual "power halo" proving at least nine poles

A pole anchored at (0,0) has body cells {(0,0),(1,0),(0,1),(1,1)} and coverage C=[-5,6]×[-5,6].

Every powered manufacturing body is one of 3×3, 5×5, 6×4, or 4×6, and must intersect the coverage of at least one pole.

For a cell offset (dx,dy), define a=max(|2dx-1|,|2dy-1|), b=min(|2dx-1|,|2dy-1|).

Assign the following weight λ(a,b); all omitted orbits have weight zero.

| (a,b) | λ |
| --- | ---: |
| (3,3) | 1 |
| (5,1) | 4 |
| (5,5) | 8 |
| (7,7) | 4 |
| (9,3) | 1 |
| (9,9) | 1 |
| (11,1) | 1 |
| (11,3) | 6 |
| (11,5) | 11 |
| (11,7) | 1 |
| (11,9) | 1 |
| (13,11) | 25/2 |
| (15,3) | 1 |
| (17,3) | 4 |

An orbit has four cells when a=b, and eight otherwise. The total weight is exactly 396.

The certificate checker performs a finite exact test. It enumerates every allowed body placement that:

* has one of the four manufacturing dimensions;
* intersects C;
* avoids the pole's 2×2 body.

There are:

| Body | Placements checked |
| --- | ---: |
| 3×3 | 180 |
| 5×5 | 220 |
| 6×4 | 220 |
| 4×6 | 220 |
| Total | 840 |

For each placement F, it verifies with integer arithmetic on doubled weights that Σ_{c∈F} λ(c) ≥ |F|.

Now assign every powered facility to any one pole whose coverage intersects it. For one pole, assigned bodies are disjoint, so their total area is at most the total translated stencil weight, 396. Stencils belonging to different poles may overlap; this does not matter because each facility is assigned to only one pole.

Therefore, if p is the number of poles, 3325 ≤ 396p, hence p ≥ ⌈3325/396⌉ = 9.

This is a small domain certificate, not a solver status. The weights came from a symmetrized local LP dual, but their validity depends only on the 840 exact inequalities.

A useful conditional version follows immediately. For a candidate empty rectangle R, let C_q(R) be the weight of the translated pole stencil that remains in-grid and outside R. Any selected nine pole anchors must satisfy Σ_q C_q(R) ≥ 3325.

This is a cheap rectangle-position and pole-position filter before placing a single manufacturing body.

## 2.3 Certificate B: a terminal membrane bound

Let the claimed empty rectangle have dimensions w×h, and write S=w+h.

Consider manufacturing facilities and boundary storage ports whose active terminal access cells lie inside the rectangle. A manufacturing facility has all inputs on one side and all outputs on the opposite side. Because the facility body and the empty rectangle are disjoint axis-aligned rectangles, the empty rectangle cannot be adjacent to both of those opposite sides. Thus one manufacturing facility can expose at most a=max(I,O) active terminals into the rectangle.

For each such facility, let s be the length of its port-bearing side. The 219 manufacturing facilities plus 46 boundary ports collapse to only eight (s,a) classes:

| s | a | Multiplicity |
| --: | --: | ---: |
| 3 | 1 | 155 |
| 3 | 2 | 12 |
| 3 | 3 | 11 |
| 5 | 1 | 32 |
| 5 | 2 | 17 |
| 6 | 3 | 32 |
| 6 | 4 | 3 |
| 6 | 5 | 3 |

A full contact interval of length s contributes at most a active terminals. Define its excess over half-density as b(s,a)=max(0,2a−s).

Summed over all facilities, the full-contact excess is at most 12·1+11·3+3·2+3·4=63.

A contact can be shorter than s only when the facility's side crosses an endpoint of one of the rectangle's four sides. There are at most eight such endpoint-crossing contacts.

For a partial contact of length ℓ exposing k terminals, k≤ℓ, 2k−ℓ≤k≤a.

Relative to the full-contact allowance b(s,a), the largest possible extra excess is a−b(s,a). The largest value is 3, available from the 32 facilities of type (6,3). Therefore the eight endpoint contacts add at most 8·3=24.

If K manufacturing and boundary-port terminals access the rectangle, and L≤2(w+h) is their total contact length, then 2K−L≤63+24=87.

Consequently, K ≤ w+h+43.

The protocol core and final-input providers contribute at most five additional terminals:

* at most three of the protocol core's six outputs can face the rectangle, because its output sides are opposite;
* there are only two final input terminals in total, whether bound to the core or storage boxes.

Thus the total number of active terminal incidences whose access cell lies in the rectangle is at most U(w,h)=w+h+48.

Every remaining active terminal uses an access cell outside the rectangle. A grid cell can be the access cell of at most four terminals, one from each orthogonal neighbor. Therefore at least ⌈(628−U(w,h))/4⌉ = ⌈(580−w−h)/4⌉ body-free cells are required outside the empty rectangle.

All required bodies and at least nine pole bodies are also outside it. Hence

4900−wh ≥ 3544+9·4+⌈(580−w−h)/4⌉.

Equivalently,

**wh+⌈(580−w−h)/4⌉ ≤ 1320**    (1)

for every feasible empty rectangle.

An exact 65-by-65 integer scan is then sufficient:

    best = (-1, -1)
    for w in 6..70:
        for h in w..70:
            if w*h + ceil_div(580 - w - h, 4) <= 1320:
                best = lex_max(best, (w*h, w))

The result is **(1190,34)**.

The preferred dimensions are 34×35. A 17×70 rectangle also has area 1190, but its shorter side is only 17. No rectangle with shorter side at least 35 can qualify, since already 35²+⌈510/4⌉=1225+128>1320, and the left side of (1) increases when either dimension increases.

This proves an unconditional lexicographic upper bound of (1190,34), subject only to the semantic assumptions listed later. It does not prove attainability.

## 2.4 What equality at the ceiling forces

The constructor should immediately target a 34×35 rectangle.

At area 1190, nine poles and no boxes leave exactly 4900−1190−3544−36=130 body-free cells outside the rectangle.

Because at most 34+35+48=117 terminals can enter the rectangle, at least 511 terminal incidences must use those 130 exterior cells. Their total geometric capacity is only 4·130=520. Thus there are at most nine missing incidence slots.

Several consequences follow.

**Exactly nine poles.** A tenth pole leaves only 126 exterior free cells. Even under the membrane upper bound, the entire layout could then support at most 117+4·126=621<628 active terminals.

**No storage boxes.** One box leaves only 121 exterior free cells, which is even further below the required access capacity. Therefore both final inputs must bind to protocol-core inputs.

**The rectangle cannot touch the map boundary.** Its perimeter has 138 outward adjacency edges. Touching any map side removes at least 34 possible body-to-rectangle terminal edges. At most 104 terminals could then enter the rectangle, but at least 628−4·130=108 must do so.

**Exterior voids are almost isolated four-way junctions.** Let the 130 exterior free cells be called holes. The sum of their adjacent body edges must be at least 511. Starting from the theoretical maximum 520, map-boundary exposure, adjacency to the rectangle, and hole-to-hole adjacency may create total deficit at most nine. A hole-to-hole edge contributes two units of deficit.

These conditions turn the target into a dense exact tiling problem rather than a general facility-layout problem.

---

# 3. Decomposition and rule ownership

I would use three deliberately asymmetric systems:

1. a domain-level upper-bound certifier;
2. a restricted but exact witness constructor;
3. two independent full-semantic checkers.

The constructor need not be complete. The upper-bound certifier must be sound. The checkers must be exact.

| Rule family | Upper-bound representation | Constructor | Final checker |
| --- | --- | --- | --- |
| Required bodies and area | Required area 3,544 | Exact body tiling | Exact instance IDs and bodies |
| Grid and nonoverlap | Only facts used by certificates | Exact cover or no-overlap | Cell bitmap and independent sweep |
| Boundary storage placement | Side-span class (3,1) | Exact left or bottom placement | Literal mode rule |
| Port counts | Aggregate 628-terminal membrane proof | Exact per-operation binding | Exact port IDs and commodities |
| Active access cells | Four incidences per cell maximum | Access must be rectangle or selected hole | Literal access-coordinate check |
| Power | 396-weight halo, at least nine poles | Exact intersection with pole coverage | Literal body-cell coverage |
| Components | Four-direction local capacity only | Local junctions and fixed central bus | Exact component/channel graph |
| Commodity routing | Ignored except terminal counts | Local closure plus shared bus | Per-commodity directed reachability |
| Objective | Inequality (1) and integer scan | Fixed 34×35 target | Independent maximum-empty-rectangle computation |
| Storage boxes | Their bodies are ignored, a relaxation | Excluded at target by proved arithmetic | Exact inactive-output rule |

The thin waist between coarse geometry and decoration is a canonical record containing:

* instance hash;
* rectangle anchor and dimensions;
* body-type placement list;
* pole anchors;
* exterior-hole bitmap;
* body bitmap hash.

Decoration adds operation labels, modes, port bindings, and component signatures. Required instance identifiers are assigned last, deterministically within each operation group.

---

# 4. Constructing a witness at (1190,34)

## 4.1 Stage A: body-and-hole exact cover

Fix a candidate 34×35 rectangle anchor. Diagonal reflection is a genuine instance symmetry, so only this orientation is needed.

Outside the rectangle are 3,710 cells. They must be partitioned into:

| Object class | Count | Area each |
| --- | ---: | ---: |
| 3×3 manufacturing bodies | 132 | 9 |
| 5×5 manufacturing bodies | 49 | 25 |
| 6×4 or 4×6 manufacturing bodies | 38 | 24 |
| Protocol core | 1 | 81 |
| Boundary storage bodies | 46 | 3 |
| Power poles | 9 | 4 |
| Exterior holes | 130 | 1 |

Before filtering placements that intersect the rectangle, the exact-cover model has at most 4624+4356+8710+3844+136+4761+3710 = 30,141 columns.

The rows are the 3,710 exterior cells plus seven count rows. Every exterior cell is covered exactly once by a body placement or a hole. This collapses all operation identities and port choices, eliminating the largest symmetry source.

I would add three necessary lifts immediately.

First, the hole-deficit constraint: Σ_{holes c} deg_body(c) ≥ 511.

Second, exactly nine pole columns.

Third, the conditional halo constraint: Σ_{selected poles q} C_q(R) ≥ 3325.

Exact power coverage can be added lazily. For every selected manufacturing placement F that is not covered by the selected poles, add ¬X_F ∨ ⋁_{q: q covers F} P_q.

This cut is exact, generalizes to every future tiling containing F, and has an obvious independent checker.

## 4.2 Stage B: operation, mode, and terminal decoration

Once the body tiling is fixed, the geometry problem becomes much smaller.

For each manufacturing body slot, choose an operation group compatible with its dimensions. Enforce exact group multiplicities. Then choose its mode and bind the operation's exact terminal multiset to distinct mode ports.

A straightforward encoding has approximately:

* 1,442 group-to-slot assignment Booleans;
* fewer than 900 mode Booleans;
* 2,435 manufacturing port-to-commodity selector Booleans;
* roughly 100 generic core and raw-output selectors;
* 6,240 exterior-hole component literals if using one-hot 48-pattern encodings;
* a few thousand interface literals around the empty rectangle.

The total should remain comfortably below 20,000 primary Booleans.

All active access cells must be either:

1. a cell inside the 34×35 rectangle, or
2. one of the 130 exterior holes.

The decoration solver enforces the exact local component signature at every hole. Component orientations number only 48:

| Kind | Directed orientations |
| --- | ---: |
| Straight | 4 |
| Turn | 8 |
| Splitter | 16 |
| Merger | 16 |
| Crossing | 4 |
| Total | 48 |

For an isolated exterior hole, every adjacent active terminal must be satisfied locally. Legal commodity patterns are:

* straight or turn, one facility output and one facility input of the same commodity;
* splitter, one facility output and two or three facility inputs of the same commodity;
* merger, two or three facility outputs and one facility input of the same commodity;
* crossing, two opposite source-to-sink pairs, each pair commodity-consistent.

This is exact for an isolated one-cell connected region. It is much stronger than merely checking input/output degree.

## 4.3 Stage C: use the empty rectangle as a shared directed bus

The key routing construction is a fixed directed Hamiltonian cycle through all 34·35=1190 rectangle cells. A rectangular grid with one even dimension has such a cycle, and it can be generated deterministically.

At an ordinary cycle cell, the component is a straight or turn. At a boundary cell with a facility output attached, replace the cycle component by a merger that injects the terminal into the cycle. At a boundary cell with a facility input attached, use a splitter that delivers from the cycle while continuing it.

Because components may carry multiple commodities and there is no capacity constraint, a single directed cycle can carry every commodity simultaneously. A terminal output entering the cycle reaches every downstream attachment and, after one full turn, every attachment on the cycle.

For each commodity k, enforce one of two alternatives:

* no terminals of k attach to the cycle, and all of them are satisfied by exterior local junctions;
* at least one output and at least one input of k attach to the cycle.

This suffices for every cycle-attached output to reach a same-commodity input, and every cycle-attached input to be reached by a same-commodity output.

At a rectangle corner, two exterior attachments may share one cycle cell. Their required directions, together with the cycle predecessor and successor, are checked against the literal 48-pattern component table. No informal "bus logic" is trusted.

This construction avoids a 19-commodity global routing model in the common case. If it proves too restrictive, the next widening step is to permit short exterior corridors connected to the cycle, not to jump immediately to unrestricted routing.

## 4.4 Exact routing fallback

For a fixed body and free-cell layout at the target, there are only 1190+130=1320 free cells.

A generic route model would use approximately:

* 1320·49=64,680 one-hot component or empty literals;
* at most about 5,280 directed cell-adjacency arc variables;
* two nonnegative flow systems per commodity.

The two flow systems encode the two asymmetric reachability requirements.

For each commodity:

1. a multi-source flow with one unit of supply at every active output and absorption at active inputs proves that every output can reach an input;
2. a flow supplying one unit of demand at every active input from the set of active outputs proves that every input is reached.

Arc capacity is M times the corresponding enabled component arc, where M is the number of terminals of that commodity. There is no benchmark throughput constraint, so this artificial capacity only linearizes reachability and is chosen large enough never to restrict a valid route.

Crossing cells are represented as two separate channel nodes, preventing transfer between their perpendicular channels.

For construction, this model need not emit an optimality proof. Its resulting component assignment is independently checked directly by graph traversal.

---

# 5. Probe sequence and abort criteria

A timeout or resource abort never excludes a target. Only a checked contradiction does.

## Probe 0: premise audit

Perform schema validation and independently recompute all sentinels, group counts, body areas, port totals, and commodity terminal counts.

Abort all downstream work on any mismatch. Record the SHA-256 hashes of all four input files.

## Probe 1: certificate audit

Generate and exact-check the 396-weight power halo and inequality (1). Run two separately written dimension scans.

Abort the bound claim if:

* any of the 840 local body inequalities fails;
* the stencil sum differs from 396;
* the two lexicographic scans disagree;
* any mutation canary, such as changing pole coverage by one cell, fails to alter the expected certificate result.

This stage should use one core, well under 1 GB, and finish in minutes.

## Probe 2: exact rectangle-side contact model

Before any two-dimensional tiling solve, build a small four-bin side-contact model for a 34×35 rectangle. It uses the eight (s,a,n) classes, exact side capacities 34,34,35,35, exact endpoint counts, and actual protocol-core port positions.

A target layout needs at least 108 terminals entering the rectangle.

If this model produces a checked upper bound below 108, 34×35 is impossible and the target is abandoned with a valid certificate.

A preliminary relaxed version has only 64 integer variables. Its purpose is to measure how much of the theoretical 117 membrane bound remains after separate side capacities are respected.

## Probe 3: coarse exact-cover build

For representative rectangle anchors, build but do not solve the body-and-hole model. Confirm:

* no more than 30,141 prefilter columns;
* 3,710 exact cell rows;
* correct area and object counts;
* hole-deficit arithmetic;
* no rectangle-intersecting placement survives.

Abort the representation, not the target, if the generated model exceeds roughly 100,000 variables, five million literals, or 8 GB at build time. The remedy is anchor enumeration and row-strip decomposition, not more RAM.

## Probe 4: bounded anchor portfolio

The rectangle must be internal. There are at most 35·34=1190 anchors for the canonical orientation. Run a portfolio over diverse anchors, prioritizing anchors with strong conditional halo capacity and enough room for left and bottom boundary storage.

Telemetry must report:

* presolve eliminations;
* exact-cover propagation rate;
* reuse frequency of power cuts;
* hole-deficit violations;
* number of coarse tilings produced.

If searches produce many tilings but almost all fail the same power condition, pre-add the corresponding coverage implications. If they produce many tilings but nearly identical hole deficits, strengthen the local hole constraints. If they produce neither conflicts nor tilings, the encoding is inert and should be redesigned.

## Probe 5: decoration

Decorate coarse tilings with operation labels, modes, terminals, hole components, and cycle attachments.

Every rejection must identify one of:

* an operation-count Hall deficit over a set of body slots;
* a port-access deficit on a body slot;
* an impossible local component signature at a hole;
* a rectangle-side attachment signature that cannot be inserted into the bus;
* a commodity that has cycle sources without cycle sinks, or vice versa.

If the same rejection family accounts for more than roughly 80 percent of coarse candidates, lift it into the exact-cover stage.

## Probe 6: generic routing only when justified

Invoke the 1320-cell routing model only for decorated layouts that fail the fixed bus for a genuinely global reason.

If lazy cut separation repeatedly returns the same geometric separator under different component choices, lift a corridor or separator condition into decoration. Do not continue accumulating single-assignment routing nogoods.

## Probe 7: certified fallback if the ceiling is unattainable

Failure of the restricted constructor proves nothing. If no ceiling witness emerges, run proof-producing necessary-condition models for the remaining objective frontier.

For a current feasible lower pair L, compute the coordinatewise minimal dimension pairs whose lexicographic value exceeds L. Any better empty rectangle contains one of these minimal rectangles, so excluding the frontier is complete.

For each frontier dimension and every possible anchor:

1. solve a necessary body, power, terminal-access, and local-component PB model;
2. retain a VeriPB or LRAT proof for every UNSAT case;
3. send SAT cases to exact decoration and routing;
4. strengthen only with individually proved cuts.

This continues until a witness lower bound and a checked exclusion upper bound meet.

---

# 6. Rejection interface

Every candidate record is immutable and hash-addressed. A rejection contains:

* candidate hash;
* rejecting layer and semantic version;
* a minimal antecedent;
* a repair disjunction or a local proof artifact;
* a checker result.

Examples include:

**Power coverage cut**: ¬X_F ∨ ⋁_{q∈Cover(F)} P_q.

**Hole component cut**: A clause forbidding the exact set of active port-direction requirements around a cell when no legal component orientation contains them.

**Operation Hall cut**: For a subset of body slots B and operation classes G, a cardinality inequality showing that too few slots in B can support the required members of G.

**Routing separator cut**: For a fixed free-cell graph and commodity k, a reachable set X with no same-commodity sink yields Σ_{u∈X, v∉X} e_uv ≥ 1.

If moved back into geometry, the cut must additionally permit moving the implicated terminal or freeing a separator cell. The bare positive obstacle set is not used as a geometry cut.

---

# 7. Final certificate assembly

The final result package should contain four independently checkable objects.

## 7.1 The witness

A canonical `layout.json` containing:

* every required instance ID exactly once;
* anchor and mode;
* nine pole anchors;
* no storage boxes at the ceiling target;
* every active port-to-commodity binding;
* every occupied transport cell and exact component orientation;
* claimed empty rectangle.

## 7.2 Exact witness checker A

A separately written checker, preferably Rust, validates:

* input hashes and schema;
* facility bodies in-grid;
* exact boundary-placement semantics;
* body nonoverlap;
* exact operation and generic terminal counts;
* active access cells in-grid and body-free;
* storage-box output inactivity;
* exact component pattern legality;
* component-to-component and terminal-to-component direction compatibility;
* crossing channel separation;
* per-commodity directed reachability in both required directions;
* power coverage;
* the claimed empty rectangle.

It then computes the true lexicographically largest empty rectangle using a histogram-stack maximal-rectangle algorithm.

## 7.3 Exact witness checker B

A second implementation shares no layout or graph helper code with checker A. It uses:

* a per-cell body bitmap rather than rectangle-overlap logic;
* explicit component channel nodes;
* brute-force or bitset enumeration of all grid rectangles rather than the histogram algorithm;
* independent breadth-first searches per commodity.

On a 70×70 grid, brute-force rectangle verification is entirely practical.

## 7.4 Upper-bound checker

This checker:

1. recomputes the 3,325 powered manufacturing area and 628 active terminals from the authoritative instance;
2. verifies the 14-orbit stencil sum;
3. checks all 840 local body inequalities with exact doubled weights;
4. derives p≥9;
5. verifies the membrane class table and the excess calculation 63+24=87;
6. derives inequality (1);
7. exhaustively scans all integer dimensions 6≤w,h≤70;
8. emits (1190,34).

The upper checker consumes no solver status and no witness data.

The final claim is issued only when both witness checkers report a layout value equal to the upper checker's value. If the attainable value is lower, the manifest also lists every proof artifact excluding the lexicographic frontier above it.

---

# 8. Resource allocation

These are campaign caps, not mathematical conclusions or runtime promises.

| Stage | CPU | RAM cap | Wall-clock budget | Disk |
| --- | ---: | ---: | ---: | ---: |
| Audit and analytical certificates | 1–2 threads | 1 GB | 15 minutes | negligible |
| Side-contact micro-models | 1–4 threads | 2 GB | 30 minutes | negligible |
| Exact-cover probes | up to 16 workers | 24 GB total | 2 hours | 10 GB |
| Target anchor portfolio | 20 search threads, 4 reserved | 30 GB | 24 hours | 50 GB |
| Decoration and fixed bus | 8–12 threads | 12 GB | included above | 10 GB |
| Generic routing fallback | 8–16 threads | 16 GB | 12 hours per promoted candidate | 20 GB |
| Proof-producing frontier exclusion | one job at a time | 32 GB | 48-hour campaign gate | up to 200 GB |
| Independent proof checking | 2–4 threads | 4 GB | streaming | no duplicate proof copy |

Proof generation and proof checking should not compete for the same memory at the same time. At least 8 GB remains reserved for the operating system, orchestration, and checker processes.

---

# 9. Three most likely failure modes

**1. The ceiling is mathematically valid but unattainable.** The 34×35 arithmetic is extremely tight. A restricted bus or isolated-junction construction may fail even though a more irregular feasible layout exists.

Mitigation: constructor UNSAT is never promoted to a global claim. Broaden routing in controlled stages, then use proof-producing necessary models only when excluding the target.

**2. Symmetry overwhelms body placement.** The 132 identical 3×3 bodies and other repeated operation groups can create a blizzard of equivalent assignments.

Mitigation: the coarse model uses only body-size counts. Operations and required instance IDs are introduced after geometry. Pole anchors are lexicographically ordered, and operation IDs are deterministically assigned after solving.

**3. A correct proof artifact certifies a mistranslated rule.** The most dangerous points are the asymmetric pole anchor, partial rectangle-side contacts, component direction conventions, and crossing channels.

Mitigation: domain-level certificates use exact coordinate enumeration; the model compiler and witness checker share no geometry code; mutation canaries deliberately alter each delicate rule; the manifest binds every artifact to the input hashes and explicit assumptions below.

---

# 10. Material assumptions and ambiguity resolutions

1. A facility anchor is the southwest body cell. Body-local coordinates are added directly to the anchor.

2. A `left_boundary` storage body has anchor x=0; a `bottom_boundary` body has anchor y=0. Their other anchor coordinate may be any value for which the body fits. No right- or top-boundary placement is permitted because no such modes exist.

3. `port_needs` applies independently to every manufacturing instance in the operation group.

4. Each active material terminal binds to one distinct physical port. One physical port cannot host two terminal bindings.

5. Ports not bound by the exact requirements are inactive.

6. The generic raw-output and final-input counts are global exact counts over the listed provider templates. Extra active generic terminals are not allowed.

7. Since 46 boundary ports provide at most 46 raw outputs and the protocol core has exactly six output ports, all 46 boundary outputs and all six core outputs are active.

8. Exactly two final input terminals are active. At the (1190,34) target, the arithmetic forces both onto protocol-core inputs because storage boxes are impossible there.

9. Required instance IDs within one operation group are semantically interchangeable during search. They are assigned to solved placements afterward without changing the layout.

10. All facility bodies, including power poles and storage boxes, participate in body nonoverlap, active-access blocking, and the objective.

11. Active access cells may be shared by several terminals. At most four terminals can share one cell because only four orthogonal neighboring body cells exist.

12. One transport component occupies one grid cell. Components may share commodities but not cells.

13. Adjacent components connect when one has an output toward the other and the other has the corresponding facing input. Cardinal directions on a component refer to its cell edges.

14. A straight has four directed orientations, a turn eight, a two- or three-output splitter sixteen, a two- or three-input merger sixteen, and a crossing four.

15. A crossing is represented as two separate directed channel nodes. A path entering one channel cannot leave through the perpendicular channel.

16. Component directions may be unused unless the specification's automatic terminal-attachment rule activates them. The proposed witness construction avoids relying on dangling directions.

17. Multi-commodity sharing means a directed component or channel may simultaneously carry any set of commodities. There is no exclusivity, capacity, conservation, or throughput rule beyond directed reachability.

18. Reaching a terminal with additional irrelevant commodities is not forbidden. The material rule requires the existence of same-commodity reachability, not purity of the transport region.

19. A path may begin and end on terminals sharing one access component. Internal splitter, merger, straight, or crossing channel connectivity counts as transport reachability.

20. There is no bijection requirement between outputs and inputs. One output may reach several inputs, and several outputs may reach one input, consistent with splitters, mergers, and the explicit absence of throughput constraints.

21. An unbound port may face outside the map or into a body. Only active bound ports impose access-cell requirements.

22. Pole coverage is clipped to the map exactly as specified. A facility is powered when at least one of its body cells, not an access cell, lies in at least one pole's clipped coverage.

23. Pole coverage has no capacity. A pole may power any number of facilities.

24. Storage-box outputs are always inactive. An unused auxiliary can be removed, but the upper-bound proof does not rely on removing boxes except where the target arithmetic itself proves they cannot occur.

25. The empty rectangle consists of a contiguous set of grid cells with integer width and height. It may contain transport components and active access cells, but no facility body cell.

26. Rectangle area is compared first, then min(w,h). Rectangle position and longer side are not further tie-breakers.

27. Rectangles touching the map boundary are generally legal. The conclusion that a ceiling-target rectangle is internal is derived from terminal capacity, not assumed.

28. Reflection across x=y is treated as an instance automorphism: left-boundary and bottom-boundary modes swap, manufacturing modes rotate, protocol-core modes swap, and pole coverage is symmetric. This permits fixing the ceiling target orientation to 34×35.

The sharp methodological conclusion is that the benchmark should not begin with a monolithic placement-routing optimizer. The first executable artifact should be the two-part upper certificate. It gives a concrete ceiling, exposes the near-equality geometry, and shrinks the constructive search to a 30,141-column dense tiling followed by a sub-20,000-variable decoration problem. Only if that sharply targeted route fails should proof-producing global exclusion machinery enter the arena.
