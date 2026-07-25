# Gate 1 v3 closeout execution record

Document kind: immutable-history-aware local execution record  
Evidence cutoff date (UTC): 2026-07-23  
Terminal status:
`HARDENING_INCOMPLETE / LEGACY_A002_CREDIBILITY_INCOMPLETE`  
Repository HEAD: `398f8725c770f3c36408adebe9448a890ed886fe`

This record separates the current reader-facing judgment from execution
history. `README.md` is the terminal interpretation. The commands below
created only no-overwrite closeout artifacts or ran synthetic/local
validation. They did not start an arm, solver, systemd unit, Track B, PIC,
B6, or witness task.

## Pre-implementation freeze

Before any v3 source was added, an O_EXCL/no-symlink freeze captured the
explicit 13-file v1/v2 history allowlist and replayed the older 26-file
manifest:

```text
.artifacts/noncert_cuts_ab_trust_20260723/
  run-20260723T113911Z-SrJBE0/
    positive-control/
      closeout-a002/
        history-v2-freeze-a001.json
```

Identity:

```text
size_bytes=3983
sha256=83832408c13a7946a0b29279978123f0123c71d7aba3a2371ce9bab6811c8419
```

The freeze explicitly excludes the newly created `closeout-a002/` subtree
from its member set. Replaying the allowlist after all v3 work therefore
checks the old files without making the freeze self-referential.

## Historical evidence manifest

The gate input manifest was created through the v3 gate's O_EXCL writer:

```text
PYTHONPYCACHEPREFIX=.artifacts/noncert_cuts_ab_trust_20260723/validation-pycache-v3 \
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 -c \
'import sys; from pathlib import Path; sys.path.insert(0,"docs/research/noncert_cuts_ab_trust_gate1_v3_20260723"); import positive_control_gate_v3 as g; g._write_exclusive(Path(".artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a002/historical-evidence-a001.json"), {"arms":None,"positive_treatment":None,"resource":None,"schema":g.EVIDENCE_PATHS_SCHEMA})'
```

The 112-byte manifest has SHA-256
`90b80f5b1d33e12070526bcb0ac2f66489944b090dd03d777b96367b4ce110aa`.
All three evidence fields are null because the historical run lacks the
prospective v3 authorities.

## Qualification packages

The fixed execution entrypoint was:

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13
```

That path is a symlink. Package sources reject symlink components, so the
interpreter byte identity was pinned at its resolved regular-file target:

```text
/home/zhuran24/.local/share/uv/python/cpython-3.13.13-linux-x86_64-gnu/bin/python3.13
size_bytes=31514832
sha256=74fceb0fdd29c31cf066ac8d92465975ea4ac8592308d7c888e26a70092d8eeb
```

The first build attempt failed before creating an output directory because
the fixed entrypoint itself was supplied as a source and its symlink was
correctly rejected. The next no-overwrite package,
`qualification-package-a001`, sealed successfully but independent
verification failed because the command incorrectly declared
`mandatory_exact_instances.json` as an object-root JSON role. That source is
an array. The failed package remains immutable and has no PASS receipt:

```text
manifest_sha256=9de222f3e680d457fbc04884f5d0fbd5ac0988ec9fef448a42c15264f9be6da1
package_id=7f711edaa2a97f63fab0d051c314e1dac8d23add1dc2c8292dd210f6cd3372b8
verifier_error=JSON_INVALID: source mandatory_instances root must be an object
```

The succeeding a002 command removed only that erroneous object-only
declaration. It continued to seal the mandatory file bytes:

```text
PROJECT_ROOT=/home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723
V3_DIR=$PROJECT_ROOT/docs/research/noncert_cuts_ab_trust_gate1_v3_20260723
V2_DIR=$PROJECT_ROOT/docs/research/noncert_cuts_ab_trust_20260723
POSITIVE_ROOT=$PROJECT_ROOT/.artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control
CLOSEOUT_ROOT=$POSITIVE_ROOT/closeout-a002
QUAL_ROOT=$CLOSEOUT_ROOT/qualification-package-a002
FIXED_PYTHON=/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13
PINNED_PYTHON_BYTES=/home/zhuran24/.local/share/uv/python/cpython-3.13.13-linux-x86_64-gnu/bin/python3.13

"$FIXED_PYTHON" "$V3_DIR/build_qualification_package_v1.py" \
  --output-dir "$QUAL_ROOT" \
  --repository-head 398f8725c770f3c36408adebe9448a890ed886fe \
  --run-nonce run-20260723T113911Z-SrJBE0-gate1-v3-closeout-a002 \
  --json-role candidate_placements \
  --json-role history_v2_freeze \
  --json-role history_v1_manifest \
  --json-role history_v1_manifest_a002 \
  --json-role control_replay_a002 \
  --json-role treatment_replay_a002 \
  --json-role gate_a002 \
  --json-role historical_evidence_a001 \
  --source "build_qualification_package_v1=$V3_DIR/build_qualification_package_v1.py" \
  --source "verify_qualification_package_v1=$V3_DIR/verify_qualification_package_v1.py" \
  --source "positive_control_gate_v3=$V3_DIR/positive_control_gate_v3.py" \
  --source "independent_arithmetic_check_v3=$V3_DIR/independent_arithmetic_check_v3.py" \
  --source "independent_resource_verifier_v2=$V3_DIR/independent_resource_verifier_v2.py" \
  --source "positive_control_resource_recorder_v2=$V3_DIR/positive_control_resource_recorder_v2.py" \
  --source "launch_selection_observer_v1=$V3_DIR/launch_selection_observer_v1.py" \
  --source "positive_control_runner_v2=$V3_DIR/positive_control_runner_v2.py" \
  --source "python3_13=$PINNED_PYTHON_BYTES" \
  --source "positive_control_runner_v1=$V2_DIR/positive_control_runner.py" \
  --source "independent_arithmetic_check_v1=$V2_DIR/independent_arithmetic_check.py" \
  --source "positive_control_gate_v1=$V2_DIR/positive_control_gate.py" \
  --source "independent_arithmetic_check_v2=$V2_DIR/independent_arithmetic_check_v2.py" \
  --source "independent_resource_verifier_v1=$V2_DIR/independent_resource_verifier_v1.py" \
  --source "positive_control_gate_v2=$V2_DIR/positive_control_gate_v2.py" \
  --source "historical_readme=$V2_DIR/README.md" \
  --source "historical_execution_record=$V2_DIR/03_execution_record.md" \
  --source "history_v1_manifest=$POSITIVE_ROOT/closeout-a001/history-v1-manifest.json" \
  --source "history_v1_manifest_a002=$POSITIVE_ROOT/closeout-a001/history-v1-manifest-a002.json" \
  --source "control_replay_a002=$POSITIVE_ROOT/closeout-a001/control-replay-a002.json" \
  --source "treatment_replay_a002=$POSITIVE_ROOT/closeout-a001/treatment-replay-a002.json" \
  --source "gate_a002=$POSITIVE_ROOT/closeout-a001/gate-a002.json" \
  --source "history_v2_freeze=$CLOSEOUT_ROOT/history-v2-freeze-a001.json" \
  --source "mandatory_instances=$PROJECT_ROOT/data/preprocessed/mandatory_exact_instances.json" \
  --source "candidate_placements=$PROJECT_ROOT/data/preprocessed/candidate_placements.json" \
  --source "historical_evidence_a001=$CLOSEOUT_ROOT/historical-evidence-a001.json"
```

The command exited 0:

```text
manifest_sha256=98803846bedacde37addaf8e4e89e0e0ea377ad86a69efcf37cef621dca86adb
package_id=25cacd0b376eb671ae76da467427651fd158e8a4e07c3617d7956e8913bd33a1
status=SEALED_AWAITING_INDEPENDENT_QUALIFICATION
```

Independent verification command:

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/noncert_cuts_ab_trust_gate1_v3_20260723/verify_qualification_package_v1.py \
  --run-dir .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a002/qualification-package-a002 \
  --verification-id independent-a001
```

It exited 0 with `status=PASS`, `corpus_errors=[]`, and every recorded check
true. Its receipt is derived qualification evidence only:

```text
verifications/independent-a001/receipt.json
size_bytes=21341
sha256=64ba1e75daefb97d2c52dae83174c1169364289772bf097a7ab3b2f4aad371b3
arm_launch_authorized=false
classification_authorized=false
```

## Historical launch selection

The selection was created outside the immutable `package/` subtree through
`make_historical_selection()` and `write_launch_selection()`. The one-time
local builder:

- read the independent receipt through the gate's same-fd strict reader;
- copied all 26 qualified source identities into `tools` or `inputs`;
- bound both history manifests, the v2 freeze, and all three a002 JSON files
  in `historical_overlay`;
- fixed the package ID, HEAD, resource contract, run nonce, and exact receipt
  identity;
- used O_EXCL/no-symlink publication.

Result:

```text
launch-selections/historical-a001.json
selection_id=c8674a9d8a17450c68f4c1ad6905352e0c35a9eb9019ec69af38acf77521df0b
size_bytes=10618
sha256=3af4dc0d4e5a295205a2fb1c5e833babbfcd4d0d15268f1de897376f4b7c9081
purpose=historical_replay
arm_launch=false
```

The selection is the direct authority for the historical overlay. The
qualification PASS receipt is not an authorization root.

## Gate a003

Exact gate command:

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/noncert_cuts_ab_trust_gate1_v3_20260723/positive_control_gate_v3.py \
  --selection .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a002/qualification-package-a002/launch-selections/historical-a001.json \
  --expected-selection-size 10618 \
  --expected-selection-sha256 3af4dc0d4e5a295205a2fb1c5e833babbfcd4d0d15268f1de897376f4b7c9081 \
  --qualification-receipt .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a002/qualification-package-a002/verifications/independent-a001/receipt.json \
  --evidence .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a002/historical-evidence-a001.json \
  --output .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a002/gate-a003.json
```

The process exited 2. The 11,023-byte result has SHA-256
`e8f2b3a37354f00eb0071105568e550734f2d49934dd8d7ac628dff99c634878`.
It contains no `error`, replays tool/input identity successfully, records the
full seven-item missing-gate set, and closes every experiment and advancement
flag.

## Validation

The focused suite covers:

- package seal and detached receipt mutation;
- direct-root selection semantics and no-overwrite behavior;
- caller-supplied PASS-object rejection;
- exact environment drift;
- resource contract, inner-chain, terminal-state, post-`SEAL`,
  `InvocationID`, cgroup cleanup, and observer/tool mutation;
- official binary protobuf parsing, unique active selector derivation,
  proto index/name/domain/rectangle joins, and solution-length drift;
- assignment, plan, enforcement, compiled-cut, and `APPLIED` ledger mutation;
- symlink, same-path replacement, truncation, duplicate/illegal JSON types,
  and stale tool/input bytes;
- historical `gate-a003` exit-2 overlay semantics.

The final focused validation commands were:

```text
FIXED_PYTHON=/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13

PYTHONPYCACHEPREFIX=.artifacts/noncert_cuts_ab_trust_20260723/validation-pycache-v3 \
  "$FIXED_PYTHON" -m pytest -q \
  src/tests/test_noncert_cuts_ab_authority_gate_v3.py \
  src/tests/test_noncert_cuts_ab_binary_selector_v3.py \
  src/tests/test_noncert_cuts_ab_resource_terminal_v3.py \
  src/tests/test_noncert_cuts_ab_positive_control_v1.py \
  src/tests/test_noncert_cuts_ab_positive_control_closeout_v2.py

PYTHONPYCACHEPREFIX=.artifacts/noncert_cuts_ab_trust_20260723/validation-pycache-v3 \
  "$FIXED_PYTHON" -m py_compile \
  docs/research/noncert_cuts_ab_trust_gate1_v3_20260723/*.py \
  src/tests/test_noncert_cuts_ab_authority_gate_v3.py \
  src/tests/test_noncert_cuts_ab_binary_selector_v3.py \
  src/tests/test_noncert_cuts_ab_resource_terminal_v3.py

"$FIXED_PYTHON" -m ruff check \
  docs/research/noncert_cuts_ab_trust_gate1_v3_20260723/*.py \
  src/tests/test_noncert_cuts_ab_authority_gate_v3.py \
  src/tests/test_noncert_cuts_ab_binary_selector_v3.py \
  src/tests/test_noncert_cuts_ab_resource_terminal_v3.py

"$FIXED_PYTHON" -m ruff format --check \
  docs/research/noncert_cuts_ab_trust_gate1_v3_20260723/*.py \
  src/tests/test_noncert_cuts_ab_authority_gate_v3.py \
  src/tests/test_noncert_cuts_ab_binary_selector_v3.py \
  src/tests/test_noncert_cuts_ab_resource_terminal_v3.py

git diff --check
```

The three v3 suites together with the retained v1/v2 suites reported:

```text
109 passed in 3.97s
```

`py_compile`, Ruff check, Ruff format check, and `git diff --check` all exited
0. The second independent package replay used:

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/noncert_cuts_ab_trust_gate1_v3_20260723/verify_qualification_package_v1.py \
  --run-dir .artifacts/noncert_cuts_ab_trust_20260723/run-20260723T113911Z-SrJBE0/positive-control/closeout-a002/qualification-package-a002 \
  --verification-id independent-a002-final
```

It also exited 0 with `status=PASS` and `corpus_errors=[]`:

```text
verifications/independent-a002-final/receipt.json
size_bytes=21353
sha256=d09691a056e693265b3d9ba061a3dd4c3455c6b292c13228f80108007aa61daf
```

This later derived receipt does not replace the selected
`independent-a001` receipt and does not alter the package or authorization
chain. Test fixtures are synthetic contract checks only; they are not
evidence about the historical cuts run.

## Final adversarial admission

The final read-only trust audit rejected admission of the v3 hardening for
future non-incomplete classifications despite the focused suite and byte
replays passing. It identified two concrete blockers:

1. `launch_selection_observer_v1.py` checks `ActiveState`, `SubState`,
   `MemoryHigh`, `MemoryMax`, `MemorySwapMax`, `OOMPolicy`, `KillMode`,
   `SendSIGKILL`, and `RuntimeMaxUSec`, but does not place those fields in the
   terminal envelope. `independent_resource_verifier_v2.py` therefore cannot
   independently reconstruct the complete final systemd state and resource
   contract from the inner raw chain plus outer envelope.
2. `positive_control_gate_v3.py` snapshots the selection at gate entry, then
   passes its pathname to the resource verifier. The verifier independently
   reopens that path, and the gate later compares against another fresh path
   identity rather than its original detached snapshot identity. This leaves
   a cross-stage same-path replacement window.

The official binary-protobuf selector reconstruction and the historical
`gate-a003` seven-gate exit-2 overlay passed review. They do not compensate
for the two future-classification blockers.

Per the branch stop contract, no in-place source mutation and no later
package, selection, gate, arm, or solver run followed this audit. Package
a002, its selected receipt, the historical selection, and `gate-a003` remain
replayable immutable history. The terminal status is
`HARDENING_INCOMPLETE / LEGACY_A002_CREDIBILITY_INCOMPLETE`; supervisory
direction is required before any other project line proceeds.
