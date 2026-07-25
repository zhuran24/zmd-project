# Track B/B1 round 2: conditional halo

| Document property | Current value |
|---|---|
| Document nature | Current-state research round report |
| Evidence cutoff | `2026-07-22` |
| Status | **COMPLETE** — 512/512 paired diagnostics and 1,024/1,024 arms are independently closed; `U` remains `(1190,34)` |
| Authority run | `.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/` |
| Authority diagnostic batch | `scan/diagnostic-corpus-v2/` |
| Claim level | Research upper-ledger evidence only; not a witness, attainability result, global optimum, or production `CERTIFIED` result |

## Current result

```text
U old -> new: (1190,34) -> (1190,34)
```

The geometry and translation admissions pass, and the complete predeclared
diagnostic survives in both arms. The canonical run-index and diagnostic
completion gate are `PASS`. A separate no-overwrite terminal rerun of the
completion gate produced byte-identical output.

| Terminal accounting | Count |
|---|---:|
| Required and completed control/treatment pairs | 512 |
| Required and completed arms | 1,024 |
| Control `CHECKED_SAT` | 512 |
| Treatment `CHECKED_SAT` | 512 |
| `treatment_survivor` attributions | 512 |
| Halo-attributed prunes | 0 |
| UNKNOWN arms | 0 |
| NO_GO/ERROR arms | 0 |
| Monotonicity contradictions | 0 |
| Missing pairs | 0 |
| Formal solver or proof runs | 0 |

The terminal authority event is
`scan/diagnostic-corpus-v2/status-events/status-1784701903920514022.json`,
SHA-256
`2da5ef745c0163989ca982f5d15255d9955765669386f0642db8806f6dbdbc39`.
It records 512 pairs, 1,024 arms, `formal_tools_invoked=false`,
`global_update_authorized=false`, and reason
`all_512_pairs_and_1024_arms_closed`.

## Admitted necessary condition

For a body-empty rectangle `R`, let `q` range over every selected power pole.
The round admits

```text
sum_q C_q(R) >= 3325,
```

or, with the exact doubled-integer stencil used by the implementation,

```text
sum_q C2_q(R) >= 6650.                         (B1-CH)
```

`C2_q(R)` is computed by translating the pole's 14-orbit dual stencil,
clipping it to the 70x70 grid, and removing `R`. The sum is over all selected
poles, not an arbitrary set of nine poles. Pole stencils may overlap; no
cross-pole subtraction is sound or needed.

The paper proof is in
[`01_necessity_proof.md`](01_necessity_proof.md), and the mathematical attack
review is in [`02_adversarial_verdict.md`](02_adversarial_verdict.md). The
admitted geometry includes:

- 14 stencil orbits, 96 nonzero offsets, and doubled total weight 792;
- 840 exhaustive local manufacturing placements;
- 219 powered mandatory manufacturing bodies with total area 3,325;
- 2,520 ceiling rectangles and 4,761 pole anchors;
- 11,997,720 rectangle/pole pairs;
- exact agreement digest
  `fe8da9696c2c7604f1153e4691ccdfe8e35b67a30adf54d301b421b113d096b2`;
- `P>=9`, with ceiling lower-ledger values 1,318 at `P=9` and 1,322 at
  `P=10`, so every feasible ceiling layout must use exactly nine poles.

## G9 control/treatment attribution

Both arms use the same corpus ordering, tools, variable graph, and independent
terminal checker.

| Arm | Encoded conditions |
|---|---|
| Control | The 47-pattern family, fixed diagnostic pattern, all 4,761 pole anchors, actual-P, pole-count link, all pole/pattern/rectangle and pole/pole conflicts, and R1 eligibility/count conditions. |
| Treatment | The exact control model plus one row: `sum C2_q(R) p_q >= 6650`. |

Both arms have the same 4,841-variable map. Every per-case translation gate
independently rebuilds the OPB multiset and requires treatment to contain
exactly one additional conditional-halo row and no removed row. Only
`control CHECKED_SAT` plus `treatment VERIFIED_UNSAT` could attribute a prune
to conditional halo. No such separation occurs in the 512-case corpus.

All 1,024 checked assignments select `P=9`. Every treatment assignment has
doubled halo left-hand side 7,128, a margin of 478 over 6,650. These are
constructor results for this diagnostic corpus, not statements about the full
assignment space. There is no third arm with actual-P disabled, so the round
does not claim an independently measured assignment-space pruning count for
actual-P.

## Predeclared diagnostic corpus

The authority corpus is
`diagnostic-corpus/ceiling-diagnostic-corpus-v2.json`, SHA-256
`8ec528984431b89bed95008f8d56290b11d5e105d89aec107b1aa85689d7843d`.
It was emitted with `manifest_state=BUILT_BEFORE_RESULTS`.

The corpus deterministically selects 256 base cases from the 59,173
R1-eligible `34x35` ceiling placements, then adds 256 transposes. It contains
512 unique logical pair identities and 256 transpose groups, and it covers
all 47 delta strata plus the predeclared nonempty contact and margin strata.

The completed evidence chain is:

```text
byte-locked batch identity
-> exclusive per-case source and command records
-> independently checked control/treatment assignments
-> recursive per-pair manifests
-> 512 atomic checkpoints
-> canonical run-index PASS
-> diagnostic completion PASS
```

All 512 manifest verifications are `PASS`, with every required check true.
Execution chronology and non-authoritative attempts are isolated in
[`03_execution_record.md`](03_execution_record.md).

## Capacity and formal-proof boundary

The terminal COMPLETE event records 19,194,449,920 bytes free. This is above
both the 10,737,418,240-byte artifact low-water mark and the dormant formal
capacity threshold:

```text
10,737,418,240 B low-water
+5,000,000,000 B proof reservation
=15,737,418,240 B required free space.
```

Capacity alone authorizes no formal execution. The byte-locked authority
identity sets both `formal_tools_authorized=false` and
`proof_fallback_authorized=false`; no RoundingSat or VeriPB process was
started. The diagnostic completion proves only that the sampled constructor
and independent-checker corpus is closed.

The dormant formal contract remains one prod-scale worker,
`MemoryHigh=35GiB`, `MemoryMax=39GiB`, `MemorySwapMax=16GiB`,
`OOMPolicy=continue`, `KillMode=control-group`, and a 5,000,000,000-byte proof
cap. None of those formal-worker settings was exercised.

## Surviving band and claim boundary

The global lex-better band was not rescanned and remains
`unchanged_not_rescanned`. The ceiling orientations `(34,35)` and `(35,34)`
remain unexcluded. The 512 treatment assignments are fixed-geometry
safe-relaxation assignments, not factory layouts.

This round does not prove:

- that every one of the 59,173 R1-eligible ceiling placements survives;
- a full-band SAT or UNSAT result;
- a layout witness, attainability, routing feasibility, or global optimality;
- a smaller upper bound;
- any production `CERTIFIED` statement.

## B1 stopping decision and next handoff

Round 1 and round 2 both leave `U=(1190,34)` unchanged. In this round's
predeclared 512-case diagnostic, every control/treatment pair jointly
survives, conditional halo produces no incremental prune, and there is no
control/treatment separation or other reviewable new condition sufficient to
support another B1 candidate. Under the core plan's prescribed branch, the
consecutive-two-round stopping criterion is therefore satisfied:

```text
Track B/B1: STOP
next handoff: R4
```

This is a research-process stopping decision within the stated diagnostic
scope, not a mathematical claim that no stronger condition exists. R4 has not
been started, designed, or executed. The generic `next_round_candidate` field
inside the completion artifact does not authorize another B1 round or an R4
run.

## Authority hashes

| Stable input or admission | SHA-256 |
|---|---|
| Strict instance | `e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c` |
| Conditional-halo stencil | `e862ac93b6a27793de764507ace7b2c736122efdd8184f30a205aba551bda1e7` |
| Coordinate report | `4bda6c4ae3fff4f9bc6e2be4c6a6081012e72a14da563f33f56fd7c1240b49e4` |
| Prefix report | `2647d54197c0043954aa79e2bdbe4a6f381b6d0a92794b851be10e40a1c30e36` |
| Agreement report | `e0ae02c0e6dcc4c515c7de4e81847a7f32b9e8ce565dd02e722ab4546f04cc2d` |
| Geometry admission | `22f25ecb1b0cf22190f8ea3add3a5f422d6f51f19577d906286a6c97a571d0da` |
| Diagnostic corpus v2 | `8ec528984431b89bed95008f8d56290b11d5e105d89aec107b1aa85689d7843d` |
| Inherited R1 translation gate | `45363308076ae6fcd837f349e3769bc6e1ad0b4bc8f660b0fa3dc475d20d2bf2` |

| Terminal artifact | SHA-256 | Size |
|---|---|---:|
| `batch-identity.json` | `b84372559710eb137556206555bfcaa383603134543b593cfd47556a5b634622` | 4,872 B |
| `run-index.json` | `bc526250e939bbf515f4329b85337a30407b19c0e487252519acea42bd473236` | 575,307 B |
| `diagnostic-completion.json` | `00087d6024ec516452282719f335f7ee966de2d4198c5bb7730ba9c08f2685f2` | 685,229 B |
| COMPLETE status event | `2da5ef745c0163989ca982f5d15255d9955765669386f0642db8806f6dbdbc39` | 697 B |
| Independent terminal completion recheck | `00087d6024ec516452282719f335f7ee966de2d4198c5bb7730ba9c08f2685f2` | 685,229 B |

## Reproduction and verification

The authority batch is complete and must not be overwritten. The complete,
verbatim initial authority argv, exact resume argv, completion subprocess
argv, terminal recheck argv, exit codes, and stdout records are preserved in
[`03_execution_record.md` — Authority driver invocations](03_execution_record.md#authority-driver-invocations).

A new replay must use a new persistent output directory under the authority
run's `scan/` directory. Only an interrupted replay may add `--resume`, and
only while its published identity and every pinned byte still match. Any
batch-identity-pinned input/tool byte change requires a new no-overwrite batch
identity.

Terminal repository acceptance commands and their exact results are recorded
in [`03_execution_record.md`](03_execution_record.md#terminal-acceptance-commands).
