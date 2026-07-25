# Current status for R4 external review

| Property | Current value |
|---|---|
| Document nature | Current-state research brief with verbatim certificate annex |
| Evidence cutoff | `2026-07-22` |
| Strict problem SHA-256 | `c041e38d2144f2b4bace0c6c8567e3c7cdd5433f53981829f6ea6a8e03e0221f` |
| Strict instance SHA-256 | `e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c` |
| Strict schema SHA-256 | `5a85e23502e7b13feef495b8cc1ab243c65b0297d2a0f0f008258926e95c6b23` |
| Methodology brief SHA-256 | `30e759cca8aad7a86dc6d59c1827cfa13bf3013b60822ee6828aea7791cd1080` |
| Upper ledger | `U=(1190,34)` |
| Lower ledger | `L=absent` |
| B1 state | `Track B/B1: STOP` |

## One-page current state

The current research upper ledger is `(1190,34)`.  This bound has passed
adversarial review.（此界已过对抗审。）  Its geometric basis is the local
power-halo certificate `P>=9` plus the terminal-membrane inequality reproduced
verbatim in Annex A.  B0 adds a RoundingSat-to-VeriPB arithmetic proof that,
given those geometric lemmas, all 2,074 oriented dimensions lexicographically
better than `(1190,34)` violate the derived necessary inequality.  The formal
authority is
`.artifacts/track_b_b0_1190_34/formal-a001-20260721T221107Z-398f8725/`:
formula SHA-256
`cd578dd972dd1bf7609e5190aff2649c3ffdce0d123b7815c81ac63f6e5346e3`,
proof SHA-256
`a6a7df1cedaabeee7271fa624f8627e5f666c9c77859df4d697577eec305fe4f`,
and toolchain-record SHA-256
`0d18e112ca4b55ba2a01ba36139f86a5bc163cd3001e189002aa2623c0c77b06`.
B0 does not prove the geometric lemmas themselves, a witness, attainability, or
global optimality.

B1 round 1 uses authority run
`.artifacts/track_b_b1_q_membrane_halo_20260722/run-20260722T0902-nGEfoW/`.
Its Q/membrane/halo necessary condition removes 138 pattern-placement pairs
relative to the inherited membrane baseline.  Both ceiling orientations
`(34,35)` and `(35,34)` still retain 59,173 relaxation assignments each, so
`U` remains `(1190,34)`.  No RoundingSat or VeriPB process ran in that round.

B1 round 2 uses authority run
`.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/`
and byte-locked batch `scan/diagnostic-corpus-v2/`.  Its batch identity is
`b84372559710eb137556206555bfcaa383603134543b593cfd47556a5b634622`;
the terminal completion SHA-256 is
`00087d6024ec516452282719f335f7ee966de2d4198c5bb7730ba9c08f2685f2`.
All 512 control and 512 treatment arms are independently `CHECKED_SAT`;
conditional halo produces zero incremental prunes, with zero UNKNOWN, NO_GO,
or ERROR arms.  The global band was not rescanned, and `U` remains
`(1190,34)`.  With two consecutive unchanged rounds and no new reviewable
survivor condition supporting another candidate, the research loop records
`Track B/B1: STOP`.  This is a process decision, not a theorem that no stronger
condition exists.

The lower ledger is absent.  The W2d source authority is the independent
detached repository
`/home/zhuran24/zmd-pj-codex-baselines/witness-ea407fa-20260720` at HEAD
`ea407fafaff56333bcf18066cecf890f0ef0c6da`.  Its dirty/untracked terminal
reports have SHA-256
`664547dfffb0c05213d21908f0a66dab70c6029797a9a714464e72bbf1fd4bc9`
and
`8dc19571cdf5ff0912346a3acbdb4a885d2e092d1a7a74d6db01a8f3a64507e0`.
The fixed x67 composer enumerated exactly two exact count-closure manifests;
both require c3 `(12,4,3)`.  Its decisive local run imported 7,156 sound cuts,
added 12, used no candidate no-good, and returned
`INFEASIBLE / SOUND_CUT_MODEL_INFEASIBLE` at 7,168 total cuts.  That result
closes only the fixed x67 skeleton, 17-component partition, x67 pole placement,
and those two manifests.  c0/c1/c2/x67-c5 remain UNKNOWN.  No assembly, router,
layout JSON, independent six-predicate pass, or witness lower bound was
produced.

The strongest current statement is therefore a research upper bound with a
machine-verified arithmetic layer, plus a local construction-campaign failure.
There is no witness, attainability result, global optimality result, or
production `CERTIFIED` result.

---

## Annex A — Verbatim R3 certificate text

The following text is copied byte-for-byte from
`docs/research/cleanroom_rederivation_20260718/09_r3_response_gpt_pro_verbatim.md`,
starting at `## 2.2` and ending immediately before `## 2.4`.

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

<!-- The verbatim Annex A byte span ends immediately above this marker. -->
