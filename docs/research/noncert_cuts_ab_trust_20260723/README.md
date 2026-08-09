# Non-certified cuts A/B credibility experiment

Document kind: research terminal-status summary\
Cutoff date: 2026-07-23\
Status: `CREDIBILITY_INCOMPLETE` — Gate 1 admits neither a positive nor a
negative cuts claim\
Authority run: `run-20260723T113911Z-SrJBE0`\
Repository identity: `398f8725c770f3c36408adebe9448a890ed886fe`\
Current closeout decision:
`positive-control/closeout-a001/gate-a002.json`\
Historical decision: `positive-control/gate-a001.json`

## Current judgment

The G7 evidence funnel stopped at its injected positive-control gate. The
immutable gate-input arms were created by fresh processes from the same
repository and runner bytes, with the same recorded deterministic
configuration and frozen incumbent:

| Gate-input arm | Generated | Compiled | Applied | Arithmetic samples |
| --- | ---: | ---: | ---: | ---: |
| `control-a002` | 0 | 0 | 0 | 0 |
| `treatment-a001` | 0 | 0 | 0 | 0 |

The treatment invoked the three-family bundle
`region_capacity`/`shape_packing_hall`/`power_hitting_set`, but its attach
telemetry reported `generated=0`, `shadow_validated=0`, and `attached=0`.
Neither arm therefore contains an `APPLIED` inequality for the independent
v2 checker to replay. Both v2 checker receipts have status
`NO_APPLIED_CUT`.

The v2 closeout also requires an immutable resource receipt and an independent
resource-verifier `PASS` before either non-incomplete classification is
available. This run contains no such resource authority. Consequently
`gate-a002.json` records `CREDIBILITY_INCOMPLETE` with
`reason=resource_authority_missing`, `classification_complete=false`, and
`advance_authorized=false`. Its only failed check is
`resource.authority_present`; it cannot classify the result as either
`INJECTED_MECHANISM_POSITIVE_CONTROL` or `POSITIVE_CONTROL_NEGATIVE`.

Zero generated, compiled, and applied cuts do not establish that
non-certified cuts are ineffective or invalid. The post-attach behavior
solves returned `UNKNOWN`; because neither arm applied a cut, those outcomes
have no proof, infeasibility, or negative-efficacy meaning.

## What the v2 closeout verifies

The v2 checker independently reconstructs a concrete applied inequality, when
one exists, from the frozen assignment, stable placement identities, plan
parameters, enforcement literals, and the corresponding compiled-cut and
`APPLIED` ledger records. A positive receipt requires the inequality to be
active at the frozen incumbent and to satisfy `lhs > rhs`. It does not trust
the v1 sample's supplied counts, contributions, `lhs`, `rhs`, `active`, or
`violated` fields.

This is a Gate 1 mechanism check for one concrete inequality and its
assignment/ledger join. It is not a Gate 2 proof sidecar, an independent
family-global F1/F6/F7 soundness proof, an organic-runtime usefulness result,
or a real-run positive cuts claim. A synthetic fixture demonstrates the v2
checker contract but contributes no evidence about these gate-input arms.

The v2 gate additionally checks the complete recorded `exact_environment`,
the paired identities and configuration, the history manifest, both v2
checker receipts, the v1 historical inputs, and the v1/v2 tool bytes. Missing
or drifting resource authority closes both the positive and negative
classification branches.

## Resource evidence boundary

The run has two distinct evidence levels:

- Immutable run authority contains the arm results and ledgers, but no
  resource receipt and no independent resource-verifier result. It therefore
  does not establish the final cgroup contract, terminal swap/OOM state, or
  absence of a resource contribution to the zero-cut outcome.
- Live execution observations recorded a `35G` high limit, `39G` maximum,
  `16G` swap maximum, `OOMPolicy=continue`, a 25-minute ceiling, a `21.5G`
  peak for each completed gate-input arm, and zero observed swap/OOM events.
  These observations were not sealed into the run as a replayable resource
  authority and are not used to obtain a non-incomplete gate classification.

No resource observation has been reconstructed or backfilled after the run.

## Authority and immutable evidence

The experiment ran in the isolated worktree
`/home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723` on branch
`codex/noncert-cuts-ab-trust-20260723`. It did not modify the main checkout.
The external candidate corpus was restored byte-for-byte as an ignored input:

- `data/preprocessed/candidate_placements.json`
- size: `54,467,709` bytes
- SHA-256:
  `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`

The no-overwrite authority root is:

```text
.artifacts/noncert_cuts_ab_trust_20260723/
  run-20260723T113911Z-SrJBE0/
    positive-control/
```

The immutable gate-input history is:

| File | Size | SHA-256 |
| --- | ---: | --- |
| `control-a001/result.json` | 380,477 B | `27457cbada3fd4429fe7a85694e8f1f4f4a72946eb2c93ad59551beb04d66039` |
| `control-a002/result.json` | 507,095 B | `9e747c214c2108b7fc73fede1d31873b24bf765d74857cf4a846cf5178ebcff6` |
| `treatment-a001/result.json` | 507,766 B | `04ab487594b1c26779df025e9fe80215d68338e030adc318dcf39910391242fc` |
| `treatment-a001/arithmetic_receipt.json` | 391 B | `31b788ac6be55b73a2ba725621da7e7138e46b073e6a6a1b860371efcc394eb6` |
| `gate-a001.json` | 3,538 B | `fa27bdd51aabed5d19ac244b485528eb5a16491413783b3b30e27fd60f2d4f63` |

Both gate-input arm results bind:

- configuration digest
  `505660c8bf44dc73684bd347132ba6698cd08d4f40ab6a5aa5b09a9330163562`;
- frozen incumbent/prestate digest
  `13f88404d7f5e4fde86929f82997a2b9850fa1cc4791d710c0363ed3e072f223`;
- runner SHA-256
  `8f25cbaff596b5fad3208d2b286ebfae602e2a2a97efb24cae2f6a16eea404fb`;
- complete audit ledgers containing only `GENESIS` and `SEGMENT_SEAL`.

Before the v2 tools were introduced, the 26 explicitly allowlisted v1 tools
and historical files were frozen by:

```text
positive-control/closeout-a001/history-v1-manifest-a002.json
```

That manifest is 7,673 bytes with SHA-256
`2da52051018de41bda5d1c12f92dc5e1b2dc5d52e7c7f360e0d752fd4ddf5924`.
The earlier `history-v1-manifest.json` is retained as immutable superseded
history; it omitted three ledger segments and is not the complete history
authority.

`gate-a001.json` and the v1 checker/gate bytes remain immutable history.
`gate-a002.json` is a new no-overwrite closeout result; it binds that history,
the v2 tools and receipts, and the explicit absence of immutable resource
authority. Its process exit code is 2.

The closeout tool identities are:

| Tool | Size | SHA-256 |
| --- | ---: | --- |
| `independent_arithmetic_check_v2.py` | 45,379 B | `959b6967951f149f6a12bedfcfc4b715e06af941ed8c4df26afcb30260195ff9` |
| `independent_resource_verifier_v1.py` | 11,961 B | `d306785dbcf7ec1a430ba69ea3b93e1c9b1be0856bcfa3937e54dc9736a2f87c` |
| `positive_control_gate_v2.py` | 39,782 B | `f41cf4240ee46a855f1a4e8b1471fc8cd0b63a9e1908ccce4b29cb6ed1ecd035` |

The immutable closeout results are:

| File | Size | SHA-256 |
| --- | ---: | --- |
| `closeout-a001/control-replay-a002.json` | 3,028 B | `ea98ab9b959a8c22472db36b01b2f0444e7838ee603d6d065e3d81b99570d093` |
| `closeout-a001/treatment-replay-a002.json` | 3,038 B | `6acd631c67b6036a959cd442eb7b14bfb8e906661b07c74bc5aca736905741a7` |
| `closeout-a001/gate-a002.json` | 38,358 B | `de57589e0878f252785de69963dbb3483c02a55db55b8f58024bdb79de040068` |

## Stop boundary and project direction

This cut experiment is closed at Gate 1:

- no proof sidecar or family-global F1/F6/F7 verifier was built;
- no full organic paired A/B run was started;
- no claim of runtime usefulness, causal value, or single-family usefulness
  was made;
- no PIC-4 or PIC-5 ledger claim was closed;
- no cut-free witness replay or six-predicate witness check was started;
- B6 remains unauthorized;
- no infeasibility proof, witness, lower bound, or project bound update was
  produced.

Work returns by default to the core Track B direction. This closeout does not
start that work. Any new cuts positive-control experiment requires separate
authorization and a new no-overwrite run; this authority run must not be
resumed or reinterpreted.

The execution chronology, exact recorded arm arguments, v1 historical
decision, and v2 closeout commands are in `03_execution_record.md`.
