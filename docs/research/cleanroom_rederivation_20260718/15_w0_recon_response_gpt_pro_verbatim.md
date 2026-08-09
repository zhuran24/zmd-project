# W0 Mathematical Reconnaissance

## Conclusion

The most promising fresh direction is a **power-cycle domino construction**:

1. Partition the 70×70 board into twenty-five 14×14 power cells.
2. Reserve one cell for the protocol core.
3. Put one pole in each of the other twenty-four cells.
4. Thread one directed cycle through all five tile rows.
5. Group the manufacturing cells into twelve two-cell domino macrocells.
6. Solve body placement, mode selection, active ports, and local routing jointly inside each macrocell.
7. Connect each macrocell to the directed cycle only through certified merger and splitter slots.

This is not yet a complete witness. It does, however, settle four global layers by construction:

* every manufacturing body can be powered;
* all nineteen commodities can share one universally directed transport backbone;
* a fixed 6×7 rectangle remains body-free;
* the exact 132/49/38 manufacturing count closes geometrically around the fixed boundary, core, poles, cycle, and protected rectangle.

The unresolved problem is now sharply bounded: construct a catalog of front-valid, locally routed completions for twelve domains of size 28×14 or 14×28. That is a materially smaller and better structured problem than another full-grid shelf campaign.

The authoritative semantics and accounts are in the [strict problem](sandbox:/mnt/data/w0-materials/w0-sol-pro-materials-20260728-v2/strict/problem.md), [strict instance](sandbox:/mnt/data/w0-materials/w0-sol-pro-materials-20260728-v2/strict/problem_instance.json), and [accepted construction facts](sandbox:/mnt/data/w0-materials/w0-sol-pro-materials-20260728-v2/context/accepted_construction_facts.md).

---

## 1. What the prior evidence actually establishes

The instance has 219 powered manufacturing facilities:

* 132 bodies of size 3×3,
* 49 bodies of size 5×5,
* 38 bodies of size 6×4 or 4×6.

Together with the 46 boundary facilities and one protocol core, the required body area is 3,544 cells. There are 628 active terminals and nineteen commodities. All 46 boundary outputs and all six core outputs must be active because they are exactly the available fifty-two raw-output slots.

Three semantic facts are especially valuable for construction.

First, transport has no capacity or throughput constraint. A component may carry multiple commodities. Consequently, commodity-specific buses are unnecessary. A common directed network may carry every commodity simultaneously.

Second, the objective rectangle excludes facility bodies, not transport. Transport may cross the protected rectangle. This permits the global backbone to pass through the 6×7 reserve without damaging the lower-bound objective.

Third, storage boxes are allowed but not required. The two final inputs can be bound directly to the protocol core. Thus the two boxes used in W2d were a choice of that construction, not a benchmark obligation.

The W2d negative result is narrow. It rejects two exact count manifests inside the fixed x67 skeleton, seventeen-component partition, thirty-five-pole layout, and protected rectangle at `(7,34,6,7)`. Both manifests depended on the same infeasible c3 target `(12,4,3)`. It says nothing about different skeletons, partitions, pole counts, core placement, storage policy, or routing topology. That boundary is stated explicitly in the [current state](sandbox:/mnt/data/w0-materials/w0-sol-pro-materials-20260728-v2/context/current_state.md) and the [W2d failure report](sandbox:/mnt/data/w0-materials/w0-sol-pro-materials-20260728-v2/history/w2d/08_track_w_w2d_failure_report_20260721.md).

The right lesson from W2d is therefore not “local decomposition fails.” It is more specific: **a rigid global shelf skeleton plus a small number of exact row-count obligations can put the entire construction behind one brittle local closure.** The new framework must retain local search while making count transfer and geometric repair inexpensive.

---

## 2. Candidate construction frameworks

| Framework                                                               | Main advantage                                                                                                                                             | Main weakness                                                                                                                                           | Assessment                                                               |
| ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Alternating-polarity shelves                                            | Alternating facility orientations make shared corridors pure output collectors or pure input distributors. Routing then has a clean merger/splitter proof. | Pole placement, row capacities, and exact count closure remain tightly coupled. It risks recreating the W2d shelf bottleneck under a different label.   | Strong fallback, not the primary direction.                              |
| Commodity microfactories                                                | Production chains and their terminals stay semantically local.                                                                                             | It spends geometry separating commodities even though sharing is free. Seed/planter loops and shared intermediates create awkward count closures.       | Useful for diagnostics, but structurally wasteful.                       |
| Power cells plus a universal directed cycle                             | Power and global routing are proved before search. Commodity identities disappear from local routing. Count vectors can move between bounded domains.      | Exact active fronts and local component placement remain nontrivial.                                                                                    | Selected direction.                                                      |
| Monolithic placement, ports, components, and nineteen-commodity routing | No projection gap and no interface design.                                                                                                                 | The representation is enormous, difficult to replay, and poorly suited to the 48 GB machine. A bounded global front-aware probe was already unresolved. | Reserve for a stubborn repair domain, not the first construction engine. |

The selected framework takes the strongest feature of the strip idea, universal routing, but removes its most dangerous feature, globally fixed manufacturing rows.

---

# 3. The concrete power-cycle design

## 3.1 Boundary facilities

Choose gap zero on both forced boundary edges.

For `k=0,…,22`:

* left facility body:
  [
  {0}\times{1+3k,2+3k,3+3k},
  ]
  with access cell
  [
  (1,2+3k);
  ]

* bottom facility body:
  [
  {1+3k,2+3k,3+3k}\times{0},
  ]
  with access cell
  [
  (2+3k,1).
  ]

This covers coordinates 1 through 69 on each edge and leaves `(0,0)` empty, so the two boundary families do not overlap.

Assign raw commodities as follows:

* all twenty-three left outputs, plus bottom outputs `k=0,…,10`, carry `blue_iron_ore`;
* bottom outputs `k=11,…,22`, plus all six core outputs, carry `source_ore`.

The totals are exactly thirty-four blue-iron outputs and eighteen source-ore outputs.

---

## 3.2 The 14×14 power-cell lemma

Partition the board into

[
T_{i,j}=[14i,14i+13]\times[14j,14j+13],
\qquad i,j\in{0,1,2,3,4}.
]

All manufacturing bodies are required, as a sufficient construction restriction, to remain wholly inside one such cell.

For an ordinary manufacturing cell, put a pole at local anchor `(6,6)`. Its body occupies local cells `{6,7}×{6,7}`, and its coverage within the cell contains

[
[1,12]\times[1,12].
]

Every manufacturing body has width at least three and height at least three. Any integer interval of length at least three contained in `[0,13]` must intersect `[1,12]`. Applying this independently in the two coordinates shows that every manufacturing body wholly contained in the cell intersects the pole coverage.

Thus:

> **Power-cell lemma.** One pole at local anchor `(6,6)` powers every nonoverlapping manufacturing body wholly contained in the same 14×14 cell.

There is also a useful repair family. Pole anchors in

[
{5,6,7}\times{5,6,7}
]

retain the same universal property. For anchor coordinate 5, 6, or 7, the uncovered portion on either side of the coverage interval has contiguous width at most two, too narrow to contain any manufacturing body.

Use tile `T_{0,4}` as the core-only tile, with no pole. Put one pole in each of the remaining twenty-four tiles.

For the protected tile `T_{2,2}`, move the pole to local anchor `(7,7)`, global anchor `(35,35)`. Its coverage contains local `[2,13]²`, which still meets every manufacturing body of minimum width and height three.

This uses twenty-four poles. It is deliberately not pole-minimal. The existing lower bound is nine, but minimizing poles is a secondary objective at this stage. The twenty-four-pole scaffold makes power local and auditable.

---

## 3.3 The preserved 6×7 rectangle

Reserve

[
R=[29,34]\times[28,34].
]

Its anchor is `(29,28)`, its width is six, and its height is seven.

It lies in `T_{2,2}` and is disjoint from the shifted pole body at `{35,36}×{35,36}`. Every local construction entry for this tile must treat all forty-two cells of (R) as forbidden to facility bodies.

The global transport cycle will pass through six cells of (R) on row `y=29`. This is legal because the objective is body-only.

Therefore the rectangle is an invariant of the framework, not something that must be rediscovered after routing.

---

## 3.4 The universal directed cycle

Define the following inclusive directed path, closing back at `(1,1)`:

```text
(1,1)  -> (68,1)
        -> (68,15)
        -> (2,15)
        -> (2,29)
        -> (68,29)
        -> (68,43)
        -> (2,43)
        -> (2,57)
        -> (68,57)
        -> (68,69)
        -> (1,69)
        -> (1,1)
```

Every segment is axis-aligned. The horizontal rows alternate direction:

* `y=1`, east;
* `y=15`, west;
* `y=29`, east;
* `y=43`, west;
* `y=57`, east;
* `y=69`, west.

The vertical connectors alternate between `x=68` and `x=2`, followed by the final return down `x=1`. The cycle contains 534 distinct cells.

At ordinary cells, place directed straights. At the eleven corners, place directed turns.

### Boundary source incidence

Every boundary output can join the cycle through a legal merger.

On the bottom edge, the cycle normally travels west to east. A source enters from the south, giving the merger

[
W,S\longrightarrow E.
]

At `(68,1)`, the path turns north, and the merger is

[
W,S\longrightarrow N.
]

On the left edge, the return path travels north to south. A source enters from the west, giving

[
N,W\longrightarrow S.
]

There is no source at `(1,1)`, so that cell remains the simple turn (N\to E).

### Universal-cycle lemma

Suppose every active output has a directed local path to some cycle cell, where it enters through a merger. Suppose every active input has a directed local path from some other cycle cell, where it leaves through a splitter.

Because a directed cycle reaches every one of its vertices from every other vertex, for any output (o) and input (i),

[
o\longrightarrow C\longrightarrow i.
]

In particular, each output reaches every input of the same commodity, and every input is reached by every output of that commodity.

This is stronger than the benchmark requirement, but it is legal because multi-commodity sharing is permitted and throughput is outside the problem.

The cycle attachment cells must have distinct roles:

* an **output injection** cell uses the cycle predecessor and local branch as inputs, with the cycle successor as its output;
* an **input tap** cell uses the cycle predecessor as input, with the cycle successor and local branch as outputs.

No cell may be both roles, since the resulting two-input, two-output transfer pattern is not among the legal component types. Attachments are also excluded from cycle corners and from boundary source injection cells.

This one distinction removes a subtle but dangerous incidence error.

---

## 3.5 Exact protocol-core placement and wiring

Use core-only tile `T_{0,4}` and place the 9×9 protocol core at anchor

[
(3,59).
]

Its body is `[3,11]×[59,67]`. Select mode `inputs_east_west`.

Bind the two final inputs to:

* `input_E_3`, access cell `(12,62)`, for `qiaoyu_capsule`;
* `input_E_5`, access cell `(12,64)`, for `valley_battery`.

A branch leaves the top cycle at `(12,69)` through a splitter, travels south on `x=12`, serves `(12,64)` through a splitter with west output, then continues to `(12,62)` and turns west.

Activate all six core outputs as `source_ore`:

* north access cells `(4,68)`, `(7,68)`, `(10,68)`;
* south access cells `(4,58)`, `(7,58)`, `(10,58)`.

The north branches merge into the westbound top cycle at `y=69`. The south branches merge into the eastbound row at `y=57`.

No storage boxes are used.

---

## 3.6 Coarse space budget

The required body area is 3,544. Twenty-four poles add 96 cells, so the framework contains 3,640 facility-body cells and leaves

[
4900-3640=1260
]

non-body cells.

The directed cycle contains 534 cells. The protected rectangle contains forty-two cells, six of which lie on the cycle. Thus the union of the cycle and rectangle contains 570 cells, leaving 690 additional free cells for local ports and branches.

This is only a capacity sanity check. It is not a front or routing proof.

---

# 4. Exact manufacturing count design

## 4.1 Collapse seventeen operations to nine geometric classes

Commodity identity can be delayed because every locally completed facility connects to the universal cycle. For placement and local routing, only body size and the numbers of active input and output ports matter.

| Class |       Body | Inputs | Outputs | Count | Operation groups                                                |
| ----- | ---------: | -----: | ------: | ----: | --------------------------------------------------------------- |
| `3L`  |        3×3 |      1 |       1 |   109 | crusher blue iron, crusher source, parts maker, both refineries |
| `3I2` |        3×3 |      2 |       1 |     6 | molding bottle                                                  |
| `3O2` |        3×3 |      1 |       2 |     6 | crusher buckwheat                                               |
| `3O3` |        3×3 |      1 |       3 |    11 | crusher sandleaf                                                |
| `5L`  |        5×5 |      1 |       1 |    32 | both planters                                                   |
| `5O2` |        5×5 |      1 |       2 |    17 | both seed collectors                                            |
| `6G`  | 6×4 or 4×6 |      3 |       1 |    32 | all grinders                                                    |
| `6F`  | 6×4 or 4×6 |      4 |       1 |     3 | filling capsule                                                 |
| `6B`  | 6×4 or 4×6 |      5 |       1 |     3 | packaging battery                                               |

This is an exact reformulation, not a relaxation.

---

## 4.2 Geometry-feasible tile count ledger

The following tile count map has an exact body-only realization. Each tuple is

[
(n_3,n_5,n_6).
]

Coordinates `i` increase left to right, and `j` increases bottom to top.

```text
          i=0        i=1        i=2        i=3        i=4

j=4        Q       (1,4,1)    (5,3,1)    (7,3,0)    (7,0,2)

j=3     (5,2,1)    (6,2,2)    (6,1,3)    (9,2,1)    (1,1,5)

j=2     (6,1,2)    (5,3,1)    (5,1,2)    (5,3,1)    (3,2,2)

j=1     (5,2,1)    (9,2,1)    (9,1,2)    (9,2,1)    (6,2,2)

j=0     (5,2,1)    (5,3,1)    (5,2,2)    (5,3,1)    (3,2,2)
```

The sums are exactly

[
\sum n_3=132,\qquad
\sum n_5=49,\qquad
\sum n_6=38.
]

A 0-1 rectangle-packing probe produced coordinates for all 219 manufacturing bodies while enforcing:

* containment inside the assigned 14×14 power cell;
* avoidance of boundary bodies, core, poles, cycle, and (R);
* exact global body counts;
* at least twenty off-fixed free cells in every manufacturing tile;
* at least two body-free, noncorner, non-boundary-source attachment positions adjacent to the local cycle row.

A second validation pass checked nonoverlap, dimensions, cell containment, count totals, power intersection, the protected rectangle, and attachment windows.

This is meaningful positive geometry evidence, but it is not a witness.

---

## 4.3 Why the local domains should be dominoes, not single tiles

The first reconnaissance attempt assigned a small catalog of fixed signatures directly to individual 14×14 cells. Exact packing rejected several edge cells. The left and right cycle risers, boundary bodies, and horizontal lane can make an edge tile much less rectangular than its area count suggests.

The repair is to retain 14×14 cells for power, but pair them into twelve routing macrocells:

| Macrocell | Power cells   | Total slots `(n3,n5,n6)` |
| --------- | ------------- | -----------------------: |
| D1        | `(1,4),(2,4)` |                `(6,7,2)` |
| D2        | `(3,4),(4,4)` |               `(14,3,2)` |
| D3        | `(0,3),(0,2)` |               `(11,3,3)` |
| D4        | `(1,3),(2,3)` |               `(12,3,5)` |
| D5        | `(3,3),(4,3)` |               `(10,3,6)` |
| D6        | `(1,2),(2,2)` |               `(10,4,3)` |
| D7        | `(3,2),(4,2)` |                `(8,5,3)` |
| D8        | `(0,1),(0,0)` |               `(10,4,2)` |
| D9        | `(1,1),(2,1)` |               `(18,3,3)` |
| D10       | `(3,1),(4,1)` |               `(15,4,3)` |
| D11       | `(1,0),(2,0)` |               `(10,5,3)` |
| D12       | `(3,0),(4,0)` |                `(8,5,3)` |

Every manufacturing body remains in one power cell, preserving the power lemma. Active access cells and transport may cross the internal boundary of the domino. No local route may leave the domino except through owned cycle attachments.

D6 contains the protected rectangle.

---

## 4.4 Initial exact allocation of front-heavy classes

The following balanced allocation distributes the difficult terminal classes. Any unlisted 3×3, 5×5, or 6×4 slot is filled respectively by `3L`, `5L`, or `6G`.

| Macrocell | Front-heavy allocation      |
| --------- | --------------------------- |
| D1        | `3I2×1, 3O3×2, 5O2×2, 6F×1` |
| D2        | `3O3×3, 5O2×2, 6B×1`        |
| D3        | `3I2×2, 5O2×2`              |
| D4        | `3I2×3, 5O2×1`              |
| D5        | `3O2×2, 5O2×2`              |
| D6        | `3O3×3, 5O2×2, 6B×1`        |
| D7        | `3O3×3, 5O2×2, 6B×1`        |
| D8        | none                        |
| D9        | none                        |
| D10       | `3O2×1, 5O2×2, 6F×1`        |
| D11       | none                        |
| D12       | `3O2×3, 5O2×2, 6F×1`        |

This closes every one of the nine class counts exactly. It also places each of the six 4-input or 5-input 6×4 facilities in a different macrocell.

The allocation is a starting master solution, not a permanent obligation. If a local oracle rejects one row, the class counts may be moved while preserving the global totals.

---

# 5. What the fresh probes reveal

The reconnaissance produced both positive and negative evidence.

### Positive evidence

The global skeleton is geometrically coherent:

* all boundary bodies and the core fit;
* the directed cycle avoids every facility body;
* twenty-four poles fit;
* the protected 6×7 rectangle is untouched by bodies;
* all 219 manufacturing rectangles can be packed with exact size counts;
* every manufacturing body is powered;
* each manufacturing tile retains at least two plausible cycle attachment openings.

This rules out the concern that the power-cell and cycle reservations consume too much raw area.

### Negative evidence

The frozen geometry coordinates cannot be upgraded merely by assigning operations and modes afterward.

In an exact necessary front probe, only 43 of the 132 frozen 3×3 rectangles could support even one body-free input access and one opposite body-free output access. The design needs 109 such low-demand 3×3 facilities. Only 14 of the 38 frozen 6×4 rectangles could support the three-input grinder class.

Therefore the frozen coordinates are not a near-witness. They are a body-packing warm start.

The important architectural consequence is:

> **Body placement, operation class, mode, and active-front selection must be solved jointly.**

This is consistent with the project’s rule-ownership methodology. These decisions share the same cells and strongly prune one another, so separating them creates a false thin waist. The exact local router should either cohabit the same macrocell solve or immediately replay every surviving front placement. See the [rule and cut ownership methodology](sandbox:/mnt/data/w0-materials/w0-sol-pro-materials-20260728-v2/methodology/rule_cut_ownership_v2_3.md).

The bounded negative probe applies only to the frozen coordinates. It is not evidence against the tile count ledger, the cycle, the pole lemma, or the existence of another packing.

---

# 6. The local macrocell completion problem

For each domino (D), the exact local oracle receives:

* its two power cells;
* fixed pole anchors;
* fixed cycle cells and directions;
* boundary or core bodies, where applicable;
* the protected rectangle, for D6;
* an exact class-count vector;
* a set of eligible cycle attachment windows.

It jointly selects:

* manufacturing body anchors and 6×4 orientations;
* facility modes;
* the exact active input and output ports;
* transport component patterns;
* distinct output-injection and input-tap cells.

It must certify five statements.

1. **Geometry:** all bodies lie in their power cells and do not overlap.
2. **Fronts:** every active port has an in-grid, body-free access cell.
3. **Incidence:** every used transport cell has one of the legal component or crossing-channel patterns and realizes its complete terminal incidence set.
4. **Output reachability:** every local output has a directed path to at least one output-injection slot.
5. **Input reachability:** every local input is reachable from at least one input-tap slot.

Commodity names are unnecessary inside this oracle. It needs only two logical routing obligations:

* output access cells reach the directed cycle;
* the directed cycle reaches input access cells.

The final checker will restore the exact commodity labels and verify all nineteen commodities.

A macrocell may use several merge and split slots. Restricting it to one of each would be unnecessarily brittle.

---

## 6.1 Catalog and master formulation

Let (\mathcal E_D) be the set of certified local entries for macrocell (D). An entry records:

* fixed-feature hash;
* pole anchors;
* exact class vector;
* body coordinates and modes;
* bound active ports;
* component patterns;
* attachment cells and their merge/split roles.

Let (z_{D,e}) select a local entry. The global master is a small exact-cover model:

[
\sum_{e\in\mathcal E_D}z_{D,e}=1
\quad\text{for every }D,
]

and

[
\sum_D\sum_{e\in\mathcal E_D} n_{e,k}z_{D,e}=N_k
\quad\text{for each of the nine classes }k.
]

Tile-size counts can either be included in the entry vectors or held fixed during the first pass and relaxed later.

No global routing search is needed once the local certificates and cycle are fixed.

---

## 6.2 Correct form of a local rejection

A rejection must retain its antecedent. The proper statement is of the form

[
\begin{aligned}
&\text{macrocell fixed-feature hash}=h,\
&\text{class vector}=v,\
&\text{pole anchors}=p,\
&\text{attachment-role choice}=a
\end{aligned}
\quad\Longrightarrow\quad
\text{no local completion}.
]

It is not sound to store “these obstacle cells are impossible” or “class vector (v) is impossible” after changing the pole, attachment cells, pairing, or protected geometry.

Timeouts and resource limits remain `UNKNOWN`. They produce no cut.

---

# 7. Next work

## Stage 1: Build the exact joint front-and-routing oracle

The first probes should be risk-oriented:

* **D6**, because it contains the protected rectangle and one `6B`;
* **D7**, because it contains three `3O3`, two `5O2`, and one `6B`;
* **D5**, because it contains six 6×4 grinders;
* **D8**, as a low-front control instance.

The oracle should model exact active port subsets. A full-side clearance halo is too strong and may reject legal layouts.

At each transport cell, enumerate the legal directed patterns directly. Crossings must be represented as two independent channel states, not as an ordinary four-neighbor graph node.

A successful local result must include a replayable certificate, not just solver coordinates.

## Stage 2: Generate local variants

For each macrocell, enumerate controlled variants over:

* pole anchors in the safe set `{5,6,7}²`;
* several output-injection and input-tap windows;
* alternative distributions of its size slots between the two power cells;
* neighboring class vectors from the master;
* alternate domino pairings for edge cells.

The protected tile’s pole must remain disjoint from (R), but it still has several safe shifted anchors.

## Stage 3: Assemble a catalog master

Start from the exact class allocation above. If a macrocell rejects it, move only the smallest responsible class set.

The master should prefer:

* one `6F` or `6B` per macrocell;
* front-heavy 3×3 and 5×5 classes in macrocells with more free-space slack;
* attachment choices that avoid cycle corners and boundary source cells.

If two adjacent dominoes repeatedly reject otherwise flexible variants, merge them into one 28×28 repair domain. That repair should run alone rather than turning the entire board monolithic.

## Stage 4: Instantiate exact operation identities

Once class-level layout and routing are fixed:

* assign exact required instance IDs to class-compatible slots;
* bind each manufacturing terminal to its required commodity;
* activate all boundary and core raw outputs according to the raw ledger;
* bind the two final commodities to the selected core inputs.

Because the universal cycle carries every commodity, identities within `3L`, `5L`, and `6G` can be assigned without changing the geometric routing topology.

## Stage 5: Independent full validation

A separate checker should reconstruct every rule from the strict JSON and verify:

1. all required instances and only permitted auxiliaries;
2. body geometry and nonoverlap;
3. active port binding and access cells;
4. complete transport-cell incidence and legal patterns;
5. directed reachability for each of the nineteen commodities;
6. power coverage;
7. the maximum body-only empty rectangle.

For transport, the checker should expand each component into directed side-to-side arcs. A crossing becomes two channel nodes so that accidental transfer is impossible.

For the objective, use a second implementation of the maximum-empty-rectangle computation, not the constructor’s protected-mask logic. The lower ledger advances only after this checker passes. A valid result will establish at least `(42,6)`, and the checker may discover a larger empty rectangle.

---

# 8. Main risks and repair ladder

### Risk 1: active fronts are too dense

The frozen geometry probe already demonstrates this danger.

Repair order:

1. jointly repack bodies and modes;
2. choose exact sparse port subsets;
3. move front-heavy classes to higher-slack macrocells;
4. shift a pole within `{5,6,7}²`;
5. change the internal distribution between the two power cells;
6. merge two dominoes into a 28×28 repair domain.

### Risk 2: a cycle attachment demands an illegal 2-input, 2-output transfer

Repair:

* reserve distinct merger and splitter cells;
* never attach at a corner;
* never combine an input tap with a boundary source merger;
* have the exact 48-pattern incidence checker run before reachability.

### Risk 3: the initial count allocation creates another hidden c3-style obligation

Repair:

* treat the displayed allocation as a master seed, not a law;
* generate several certified class vectors per macrocell;
* use exact-cover assembly over the catalog;
* qualify every rejection by its complete local antecedent.

### Risk 4: local domains are still too small for routing

Repair:

* permit multiple cycle attachment slots;
* allow access and transport across the internal domino boundary;
* use 28×28 only for a repeatedly failing adjacent pair;
* retain the global cycle and power cells while enlarging the local oracle.

---

# 9. Execution shape on the target machine

On the 24-core, 48 GB machine, the natural layout is:

* up to eight two-core local-oracle workers, each with a roughly 3 GB memory cap;
* one small catalog/master process;
* one replay and validation process;
* reserved memory for proof artifacts, the operating system, and a possible exclusive repair solve.

A 28×28 repair oracle should run exclusively or with only the checker active. Every run should be configuration-hashed and fail closed. An interrupted or bounded run reports `UNKNOWN`, never `INFEASIBLE`.

This decomposition also improves auditability. A complete witness can be replayed as twelve local certificates, one fixed-cycle certificate, one count ledger, and one independent global validation.

---

## Final assessment

The power-cycle domino direction is promising for a specific reason: its global claims are mathematical invariants, not search hopes.

* Power follows from the 14×14 coverage lemma.
* The 6×7 rectangle follows from a fixed body mask.
* Raw and final interfaces have explicit coordinates.
* Global commodity connectivity follows from the directed-cycle lemma.
* Exact body-size counts have a verified geometric realization.
* The remaining uncertainty is confined to front-valid local completion.

The geometry-only seed must not be mistaken for a partial witness. Its frozen fronts fail. Its value is different: it proves that the global scaffold has enough geometric room and supplies an exact count distribution and warm-start coordinates for a joint local solver.

The next decisive artifact should be a replayable, exact D6 or D7 macrocell completion containing bodies, modes, active ports, legal components, and directed attachment paths. Success there would test the genuinely hard layer. Failure would produce a narrowly qualified repair instruction rather than another collapsed global campaign.

### Working artifacts

* [Power-cycle domino framework](sandbox:/mnt/data/W0_power_cycle_domino_framework_v1.json)
* [Geometry-only 219-body warm start](sandbox:/mnt/data/W0_geometry_only_seed_v1.json)
* [Geometry validation record](sandbox:/mnt/data/W0_geometry_only_seed_v1.validation.json)
* [Frozen-geometry active-front probe](sandbox:/mnt/data/W0_frozen_geometry_front_probe_v1.json)
* [Artifact SHA-256 manifest](sandbox:/mnt/data/W0_recon_artifacts_SHA256.json)
