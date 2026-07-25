# Gate 1 execution record

Document kind: historical execution record\
Cutoff date: 2026-07-23\
Authority run: `run-20260723T113911Z-SrJBE0`\
Current closeout decision:
`positive-control/closeout-a001/gate-a002.json`\
Historical decision: `positive-control/gate-a001.json`\
Terminal status: `CREDIBILITY_INCOMPLETE`

This file preserves the execution chronology through 2026-07-23. The
reader-facing current judgment is in `README.md`; historical results below do
not override that judgment.

## Fixed arm configuration

The gate-input arms used repository HEAD
`398f8725c770f3c36408adebe9448a890ed886fe`, Python 3.13.13 from
`/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13`, one worker,
seed `2026072301`, a 6x6 ghost rectangle, fixed master branching, probing level
3, symmetry level 3, a 900-second master budget, 600-second binding and routing
budgets, binding alternative cap 200, and a 120-second post-attach behavior
solve.

Both gate-input arm results record the same complete `exact_environment`:

```text
EXACT_B1_BINDING_ALT_CAP=200
EXACT_CP_SAT_WORKERS=1
EXACT_MASTER_CP_MODEL_PROBING_LEVEL=3
EXACT_MASTER_CP_SAT_WORKERS=1
EXACT_MASTER_RANDOM_SEED=2026072301
EXACT_MASTER_SEARCH_BRANCHING=fixed
EXACT_MASTER_SYMMETRY_LEVEL=3
```

The execution units were started with:

```text
MemoryHigh=35G
MemoryMax=39G
MemorySwapMax=16G
OOMPolicy=continue
KillMode=control-group
SendSIGKILL=yes
RuntimeMaxSec=1500
```

The persistent run root had 33,604,870,144 available bytes before the
treatment, above the 12,737,418,240-byte admission threshold. The canonical
prod-scale lock was free before each completed gate-input arm and free after
completion.

The `exact_environment` above is stored in both immutable arm results. The
systemd resource contract, disk/lock state, and runtime measurements were
observed live, but no immutable resource receipt or independent
resource-verifier result was written inside the authority run. The live
resource observations therefore cannot satisfy the v2 gate's common resource
requirement for either a positive or negative classification.

## Historical attempt `control-a001`

`control-a001` is immutable history and is not a gate-input arm. Its result is
380,477 bytes with SHA-256
`27457cbada3fd4429fe7a85694e8f1f4f4a72946eb2c93ad59551beb04d66039`.
It stopped with `CREDIBILITY_INCOMPLETE` after the runner attempted
`CpModelProto.SerializeToString()`, which is unavailable in the installed
OR-Tools pybind API:

```text
AttributeError: 'ortools.sat.python.cp_model_helper.CpModelProto'
object has no attribute 'SerializeToString'
```

The immutable attempt consumed 8m56.834s wall time and peaked at 21.4G. The
research runner was corrected to use the repository-established textual proto
serialization solely for the paired prestate identity. The corrected runner
has SHA-256
`8f25cbaff596b5fad3208d2b286ebfae602e2a2a97efb24cae2f6a16eea404fb`.
No file in `control-a001` was overwritten.

## Gate-input control `control-a002`

The exact program argv stored in `control-a002/result.json` is:

```text
docs/research/noncert_cuts_ab_trust_20260723/positive_control_runner.py
--arm control
--attempt-dir /home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723/.artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/control-a002
--run-tag pc-control-a002
--ghost-w 6
--ghost-h 6
--master-seconds 900
--binding-seconds 600
--routing-seconds 600
--max-iterations 30
--binding-alt-cap 200
--post-attach-seconds 120
--workers 1
--seed 2026072301
```

The arm exited 0 with `ARM_COMPLETE`. It recorded a complete two-event ledger,
zero generated cuts, zero compiled cuts, zero applied cuts, and no arithmetic
samples. Its post-attach behavior solve returned `UNKNOWN`; that status
carries no mathematical claim. Live observations recorded 11m04.927s wall /
11m05.832s CPU, a 21.5G memory peak, zero swap, and no OOM event. Those
observations were not sealed into an immutable resource receipt.

## Gate-input treatment `treatment-a001`

The treatment used the identical argv except:

```text
--arm treatment
--attempt-dir /home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723/.artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/treatment-a001
--run-tag pc-treatment-a001
```

The arm exited 0 with `ARM_COMPLETE`. Its configuration digest and frozen
prestate digest exactly match the control. The three-family injection call
took 428.719 seconds and returned:

```json
{
  "generated": 0,
  "shadow_validated": 0,
  "attached": 0,
  "attached_by_family": {},
  "rejected": {
    "adapter": 0,
    "attach_timing": 0,
    "envelope": 0,
    "plan": 0,
    "proof": 0,
    "registry": 0,
    "scope": 0,
    "semantic_duplicate": 0
  }
}
```

The ledger again contains only `GENESIS` and `SEGMENT_SEAL`. The post-attach
behavior solve returned `UNKNOWN`. Live observations recorded 18m17.694s wall
/ 18m17.546s CPU, a 21.5G memory peak, zero swap, and zero observed cgroup
high/max/OOM counters. Those observations were not sealed into an immutable
resource receipt.

## Historical v1 checker and decision

The v1 checker command was:

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/noncert_cuts_ab_trust_20260723/independent_arithmetic_check.py \
  --input .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/treatment-a001/arithmetic_samples.json \
  --output .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/treatment-a001/arithmetic_receipt.json
```

It exited 2 and wrote a no-overwrite `FAIL` receipt:

```text
ValueError: treatment sample corpus must be non-empty
```

The v1 checker only checked arithmetic fields supplied by the runner against
one another. It did not independently rebuild the frozen assignment, stable
placement identities, plan parameters, enforcement literals, or compiled-cut
to `APPLIED` ledger join. Its immutable bytes and receipt remain historical;
the v2 checker supplies the independent Gate 1 replay contract.

The v1 decision command was:

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/noncert_cuts_ab_trust_20260723/positive_control_gate.py \
  --control .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/control-a002/result.json \
  --treatment .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/treatment-a001/result.json \
  --arithmetic-receipt .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/treatment-a001/arithmetic_receipt.json \
  --output .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/gate-a001.json
```

It exited 2 and wrote `CREDIBILITY_INCOMPLETE`. The failed v1 checks are
exactly `treatment_chain_positive` and `arithmetic_receipt`; its other
then-implemented checks passed. This historical result did not compare the
complete `exact_environment`, require immutable resource authority, or bind
the checker and gate tools. It is not evidence that the corresponding v2
requirements passed.

## V1 history freeze

Before any v2 tool was added, the historical v1 surface was frozen with
O_EXCL/no-symlink creation. The complete allowlist authority is:

```text
.artifacts/noncert_cuts_ab_trust_20260723/
  run-20260723T113911Z-SrJBE0/
    positive-control/
      closeout-a001/
        history-v1-manifest-a002.json
```

It enumerates 26 explicit files, including the three v1 tools, all three
ledger segments, both gate-input arm records, the historical failed attempt,
the v1 receipt, and `gate-a001.json`. It excludes `closeout-a001/` from the
frozen member set. The manifest is 7,673 bytes with SHA-256
`2da52051018de41bda5d1c12f92dc5e1b2dc5d52e7c7f360e0d752fd4ddf5924`.

The earlier immutable `history-v1-manifest.json` omitted the three ledger
segments. It remains historical but is superseded by
`history-v1-manifest-a002.json` for complete history replay.

## V2 independent replay and closeout

The three closeout tools have these byte identities:

| Tool | Size | SHA-256 |
| --- | ---: | --- |
| `independent_arithmetic_check_v2.py` | 45,379 B | `959b6967951f149f6a12bedfcfc4b715e06af941ed8c4df26afcb30260195ff9` |
| `independent_resource_verifier_v1.py` | 11,961 B | `d306785dbcf7ec1a430ba69ea3b93e1c9b1be0856bcfa3937e54dc9736a2f87c` |
| `positive_control_gate_v2.py` | 39,782 B | `f41cf4240ee46a855f1a4e8b1471fc8cd0b63a9e1908ccce4b29cb6ed1ecd035` |

The v2 checker is a narrow Gate 1 verifier. For an actual `APPLIED` sample it
reconstructs the concrete F1, F6, or F7 inequality from byte-pinned strict
inputs and a frozen assignment; derives the enforcement state and
`lhs > rhs`; and joins the result to the compiled cut and the complete
`APPLIED` ledger event. It does not build a proof sidecar, prove family-global
soundness, or turn a synthetic fixture into a real-run claim.

The control replay command was:

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/noncert_cuts_ab_trust_20260723/independent_arithmetic_check_v2.py \
  --arm-result .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/control-a002/result.json \
  --sample-corpus .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/control-a002/arithmetic_samples.json \
  --ledger-segment .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/control-a002/ledger/pc-control-a002/segment_cachyos-zr24-pid609369-18add23493d3_00000.jsonl \
  --mandatory-instances data/preprocessed/mandatory_exact_instances.json \
  --candidate-placements data/preprocessed/candidate_placements.json \
  --history-manifest .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a001/history-v1-manifest-a002.json \
  --output .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a001/control-replay-a002.json
```

The treatment replay command is:

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/noncert_cuts_ab_trust_20260723/independent_arithmetic_check_v2.py \
  --arm-result .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/treatment-a001/result.json \
  --sample-corpus .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/treatment-a001/arithmetic_samples.json \
  --ledger-segment .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/treatment-a001/ledger/pc-treatment-a001/segment_cachyos-zr24-pid618935-aadfbd43b07d_00000.jsonl \
  --mandatory-instances data/preprocessed/mandatory_exact_instances.json \
  --candidate-placements data/preprocessed/candidate_placements.json \
  --history-manifest .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a001/history-v1-manifest-a002.json \
  --output .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a001/treatment-replay-a002.json
```

Neither command receives `--frozen-assignment` because the immutable arm
contains no sample or `APPLIED` event. Both receipts report
`NO_APPLIED_CUT`; both commands exit 0.

The v2 gate replays the complete paired environment and identities, both v2
receipts, the v1 frozen history, and the v1/v2 tool identities. Its resource
input is the explicit `--resource-authority-missing` branch because no
immutable resource receipt and independent verifier result exist:

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/noncert_cuts_ab_trust_20260723/positive_control_gate_v2.py \
  --control .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/control-a002/result.json \
  --treatment .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/treatment-a001/result.json \
  --control-checker-receipt .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a001/control-replay-a002.json \
  --treatment-checker-receipt .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a001/treatment-replay-a002.json \
  --history-manifest .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a001/history-v1-manifest-a002.json \
  --v1-arithmetic-receipt .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/treatment-a001/arithmetic_receipt.json \
  --v1-gate .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/gate-a001.json \
  --checker-v2-tool docs/research/noncert_cuts_ab_trust_20260723/independent_arithmetic_check_v2.py \
  --resource-verifier-tool docs/research/noncert_cuts_ab_trust_20260723/independent_resource_verifier_v1.py \
  --resource-authority-missing \
  --output .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a001/gate-a002.json
```

The command writes `closeout-a001/gate-a002.json`, exits 2, and records
`CREDIBILITY_INCOMPLETE`, `reason=resource_authority_missing`,
`classification_complete=false`, and `advance_authorized=false`. The only
failed check is `resource.authority_present`.

The immutable closeout output identities are:

| File | Size | SHA-256 |
| --- | ---: | --- |
| `control-replay-a002.json` | 3,028 B | `ea98ab9b959a8c22472db36b01b2f0444e7838ee603d6d065e3d81b99570d093` |
| `treatment-replay-a002.json` | 3,038 B | `6acd631c67b6036a959cd442eb7b14bfb8e906661b07c74bc5aca736905741a7` |
| `gate-a002.json` | 38,358 B | `de57589e0878f252785de69963dbb3483c02a55db55b8f58024bdb79de040068` |

## Terminal enforcement

The Gate 1 replay did not admit a positive or negative cuts result. No
sidecar, family-global verifier, full organic paired run, witness materializer,
cut-free replay, solver search, proof run, or project-ledger update followed.
This cuts round is closed. The default project direction returns to core
Track B, which was not started by this closeout; any new cuts experiment
requires separate authorization and a new no-overwrite run.
