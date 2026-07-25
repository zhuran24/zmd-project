# R4 handoff package execution record

| Property | Current value |
|---|---|
| Document nature | Historical execution record; not a current-state authority |
| Record cutoff | `2026-07-22` |
| Authority package | `READY_FOR_MANUAL_EXTERNAL_SUBMISSION` |
| External action | None; stopped at `AWAITING_EXTERNAL_ACTION` |

Current-state instructions and claims live in [`README.md`](README.md).  This
file records only completed commands and immutable run history.

## Pre-build baseline

- Project HEAD: `398f8725c770f3c36408adebe9448a890ed886fe`
- W2d detached source HEAD:
  `ea407fafaff56333bcf18066cecf890f0ef0c6da`
- Candidate-placement external artifact: 54,467,709 B, SHA-256
  `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`
- Available bytes before implementation reconnaissance: 19,080,376,320 B.
- Existing dirty paths were preserved; their terminal
  `git status --short --branch` output appears below.

## Authority build and verification

All commands below ran from
`/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721` with exit code
zero and no stderr unless stated otherwise.

The no-overwrite target was confirmed absent, then the package was sealed with:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/r4_external_brain_handoff_20260722/build_r4_handoff_package_v1.py \
  --output-dir .artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A
```

The terminal result was
`SEALED_AWAITING_INDEPENDENT_VERIFICATION`, package ID
`1a1288a705e699b406d6636c56170f39cb2aecfce18337943e6114035b53369f`,
and manifest SHA-256
`8097c4acb76fa90f20b8e48996d1a9a1e4d688758368a029395bb8e005669d4b`.
The complete build argv and pre-seal environment record are retained in
`package/control/build-record.json`; the package has ten regular files: eight
payload/control members, the manifest, and `SHA256SUMS`.

The independent verifier was then run twice with the same sealed package,
current inputs, verifier bytes, and checker:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/r4_external_brain_handoff_20260722/verify_r4_handoff_package_v1.py \
  --run-dir .artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A \
  --verification-id independent-a001-20260722T0844Z

PYTHONDONTWRITEBYTECODE=1 /home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/r4_external_brain_handoff_20260722/verify_r4_handoff_package_v1.py \
  --run-dir .artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A \
  --verification-id independent-a002-20260722T0845Z
```

Both receipts report all nine checks true, `corpus_errors=[]`, 37 current input
identities, verifier-tool SHA-256
`b702babc4cbe10e877e594f42049e9e01a396b8da066508d616ca1620bc77607`,
and status `PASS`.

| Receipt | Size | SHA-256 |
|---|---:|---|
| `verifications/independent-a001-20260722T0844Z/receipt.json` | 13,840 B | `515ab7b0d8a2a17bd776f58534a0c8cc8ebc7ad79dcfe44c3231f665cc53e120` |
| `verifications/independent-a002-20260722T0845Z/receipt.json` | 13,840 B | `cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4` |

Both receipt semantic-replay commands returned `PASS`.  Before the first
receipt, between receipts, and after the second receipt, the package closure
remained:

| Sealed member | SHA-256 |
|---|---|
| `package/SHA256SUMS` | `1a1288a705e699b406d6636c56170f39cb2aecfce18337943e6114035b53369f` |
| `package/package-manifest.json` | `8097c4acb76fa90f20b8e48996d1a9a1e4d688758368a029395bb8e005669d4b` |

The second PASS receipt was selected with:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/r4_external_brain_handoff_20260722/select_r4_ready_receipt_v1.py select \
  --run-dir .artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A \
  --receipt .artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A/verifications/independent-a002-20260722T0845Z/receipt.json
```

The immutable READY record is 771 B with SHA-256
`ae121f1b16be01bc2a3b22ddb5bcf9365624cac8726b84364ddae52794bccee0`.
Its selected receipt identity is exactly path
`verifications/independent-a002-20260722T0845Z/receipt.json`, size 13,840 B,
and SHA-256
`cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4`.
The README-bound read-only replay also returned
`READY_FOR_MANUAL_EXTERNAL_SUBMISSION`.

## Repository acceptance

The focused R4 suite passed 32 tests.  The combined B0/B1/R4 targeted suite and
the W2d cross-repository suite passed; W2d reported `5 passed in 0.04s`.
`py_compile`, Ruff check, Ruff format check, and `git diff --check` all exited
zero.  Additional direct gates returned:

| Gate | Result |
|---|---|
| strict clean-room bundle | `5 files` checked, exit 0 |
| R3 recomputation | `stencil=396`, `placements=840`, `P>=9`, `excess=63`, `lex-max=(1190,34)`, exit 0 |
| external candidate artifact | size/hash contract verified, exit 0 |
| direct repository secret scan | 39,662 candidate text paths checked, exit 0 |
| corrected offline `bwrap --unshare-net` probe | exit 0 |

The first minimal bwrap diagnostic omitted the `/lib` and `/lib64` loader
mounts and therefore exited nonzero with `execvp /usr/bin/true: No such file or
directory`.  The immediately corrected probe used the same loader mounts as
the delivered recomputation runner and exited zero; no response or checker was
executed by either probe.

The final full gate command was:

```bash
PREFLIGHT_TIMEOUT_SCALE=12 PYTHONDONTWRITEBYTECODE=1 \
  /home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  scripts/preflight_gate.py --full
```

It exited zero: `4707 passed, 74 skipped in 123.01s`, all 19 gate checks
passed, Ruff and mypy passed, and the embedded secret scan checked 39,674
candidate text paths.  Available persistent space after READY selection was
18,977,857,536 B.

Terminal `git status --short --branch` remained the pre-existing dirty
worktree plus this uncommitted R4 delivery:

```text
## codex/track-b-b0-1190-20260721
 M scripts/preflight_gate.py
 M src/tests/test_preflight_gate.py
 M src/tests/test_r1_upper_bound_pb_v1.py
?? .artifacts/track_b_b0_1190_34/
?? .artifacts/track_b_b1_conditional_halo_20260722/
?? .artifacts/track_b_b1_q_membrane_halo_20260722/
?? .artifacts/track_b_r4_external_brain_handoff_20260722/
?? docs/research/b1_conditional_halo_20260722/
?? docs/research/b1_q_membrane_halo_20260722/
?? docs/research/r3_upper_bound_pb_20260722/
?? docs/research/r4_external_brain_handoff_20260722/
?? src/tests/test_b1_conditional_halo_v1.py
?? src/tests/test_b1_q_membrane_halo_v1.py
?? src/tests/test_r3_upper_bound_pb_v1.py
?? src/tests/test_r4_external_brain_handoff_v1.py
```

No browser, external service, solver, RoundingSat, VeriPB, response ingestion,
or B1 encoder action was performed.  Execution stopped at the manual external
action boundary.
