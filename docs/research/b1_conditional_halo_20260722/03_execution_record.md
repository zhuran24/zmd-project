# B1 round-2 conditional halo: execution and provenance record

| Document property | Value |
|---|---|
| Document nature | Historical execution and provenance record |
| Evidence cutoff | `2026-07-22` |
| Current-state report | [`README.md`](README.md) |
| Authority run | `.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/` |
| Authority terminal state | `COMPLETE`; 512/512 pairs and 1,024/1,024 arms |
| Evidence use | Audit history only; current admissions and claims come from the authority artifacts named in the README |

This document isolates chronology and failed attempts from the reader-facing
current state. It does not independently admit a mathematical lemma,
translation, SAT assignment, UNSAT proof, upper-bound update, or stopping
decision.

## Geometry funnel

The round closed a geometry-only gate before admitting a paired encoder:

1. [`01_necessity_proof.md`](01_necessity_proof.md) derived the all-selected-
   pole inequality `sum_q C2_q(R) >= 6650`.
2. `verify_b1_conditional_halo_coordinates_v1.py` performed the direct
   full-coordinate recomputation.
3. `recompute_b1_conditional_halo_prefix_v1.py` independently rebuilt the
   same corpus with a prefix formulation.
4. `compare_b1_conditional_halo_recomputations_v1.py` required exact agreement
   and `corpus_errors=[]`.
5. [`02_adversarial_verdict.md`](02_adversarial_verdict.md) closed 18/18
   mathematical attack surfaces.
6. `geometry/geometry-admission.json` admitted only the necessary geometry,
   with scope `geometry_only_pre_encoder`.

| Geometry artifact | SHA-256 |
|---|---|
| `geometry/coordinate.json` | `4bda6c4ae3fff4f9bc6e2be4c6a6081012e72a14da563f33f56fd7c1240b49e4` |
| `geometry/prefix.json` | `2647d54197c0043954aa79e2bdbe4a6f381b6d0a92794b851be10e40a1c30e36` |
| `geometry/agreement.json` | `e0ae02c0e6dcc4c515c7de4e81847a7f32b9e8ce565dd02e722ab4546f04cc2d` |
| `geometry/geometry-admission.json` | `22f25ecb1b0cf22190f8ea3add3a5f422d6f51f19577d906286a6c97a571d0da` |
| `conditional_halo_stencil_v1.json` | `e862ac93b6a27793de764507ace7b2c736122efdd8184f30a205aba551bda1e7` |

The direct and prefix implementations agreed on 2,520 ceiling rectangles,
4,761 pole anchors, 11,997,720 rectangle/pole pairs, and canonical digest
`fe8da9696c2c7604f1153e4691ccdfe8e35b67a30adf54d301b421b113d096b2`.

## Encoder and terminal-evidence funnel

The paired model uses the same 4,841 variables in both arms: 47 boundary
pattern selectors, 4,761 pole-anchor selectors, and 33 actual-pole-count
selectors for counts 9 through 41. Treatment differs from control by exactly
one positive row, the doubled conditional-halo inequality with right-hand side
6,650.

Before the authority batch ran, the implementation closed these fail-closed
contracts and regression tests:

- 512 unique logical `pair_id` values and 256 ordered transpose groups;
- geometry admission parsed as an exact list of uniquely named PASS checks;
- per-case translation admission bound to `case_id`, `pair_id`,
  `transpose_group_id`, and the paired-generation digest;
- mutation-canary results bound to geometry, corpus, all six model files, and
  the exact paired-generation digest;
- deterministic construction followed by a separate semantic assignment
  checker for every arm;
- pre-manifest and pre-publication revalidation of model, assignment, checker,
  and snapshot bytes;
- independent manifest verification that reparses the OPB and complete
  4,841-bit assignment instead of trusting a terminal-status label;
- diagnostic completion narrowed to two independently revalidated
  `CHECKED_SAT` arms per pair;
- a 300-second child wall timeout and owned-PGID descendant cleanup;
- atomic no-clobber publication of identities, attempts, checkpoints,
  run-index, and completion records.

Same-filesystem snapshots are no-overwrite hard links. Cross-filesystem
snapshots fall back only on `EXDEV` to an exclusive byte copy. Recursive
manifests and independent semantic replay detect source or linked-snapshot
mutation; symbolic links and non-regular inputs are rejected.

## Predeclared diagnostic corpus

The authority corpus is
`diagnostic-corpus/ceiling-diagnostic-corpus-v2.json`, SHA-256
`8ec528984431b89bed95008f8d56290b11d5e105d89aec107b1aa85689d7843d`.
It carries `manifest_state=BUILT_BEFORE_RESULTS`. A deterministic ranking
selected 256 base cases from 59,173 R1-eligible `34x35` placements and added
their 256 transposes. The 512 pairs cover all 47 delta strata and the
predeclared nonempty margin/contact strata.

Each case executes this fixed sequence:

```text
paired encoder
-> independent translation rebuild
-> four mutation canaries
-> per-case translation admission
-> control constructor + independent checker
-> treatment constructor + independent checker
-> checked-SAT-only pair runner
-> recursive manifest verifier
-> atomic checkpoint
```

The batch driver never supplies RoundingSat or VeriPB arguments and refuses a
formal fallback. Every subprocess records its raw argv, stdout, stderr, exit
code, elapsed time, termination reason, and process-group cleanup result.

## Authority driver invocations

The batch root does not record the top-level driver's `sys.argv`. The initial
authority invocation below was therefore recovered verbatim from this
thread's append-only raw execution record:

```text
/home/zhuran24/.codex/sessions/2026/07/20/rollout-2026-07-20T04-46-23-019f7c21-46f7-7b13-b73f-29f6349890c8.jsonl:27024
timestamp=2026-07-22T03:31:18.601Z
call_id=call_GPIffv7k4qadUY7CEO8x4R1u
cwd=/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721
```

Only shell line continuations were added for readability; the argv tokens are
unchanged. In particular, the original invocation had no explicit
`--node-limit` argument.

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/b1_conditional_halo_20260722/run_b1_conditional_halo_diagnostic_corpus_v1.py \
  --project-root /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721 \
  --corpus /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/diagnostic-corpus/ceiling-diagnostic-corpus-v2.json \
  --geometry-admission /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/geometry/geometry-admission.json \
  --stencil /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/docs/research/b1_conditional_halo_20260722/conditional_halo_stencil_v1.json \
  --output-dir /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/scan/diagnostic-corpus-v2
```

That invocation exited 3 at 381 pairs. Its exact terminal stdout was:

```json
{"completed_pairs": 381, "next_case_index": 381, "reason": "artifact_low_water:before_04_translation_admission:free=10062876672:required=10737418240", "status": "INCOMPLETE", "status_event": "/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/scan/diagnostic-corpus-v2/status-events/status-1784696175797421436.json"}
```

After persistent capacity was restored, the exact same top-level argv was
reissued with only `--resume` appended. This command is recorded at raw line
28224, timestamp `2026-07-22T06:02:36.571Z`, call id
`call_tcA2VH8zaMWq8M52xLgsX3Yx`:

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/b1_conditional_halo_20260722/run_b1_conditional_halo_diagnostic_corpus_v1.py \
  --project-root /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721 \
  --corpus /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/diagnostic-corpus/ceiling-diagnostic-corpus-v2.json \
  --geometry-admission /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/geometry/geometry-admission.json \
  --stencil /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/docs/research/b1_conditional_halo_20260722/conditional_halo_stencil_v1.json \
  --output-dir /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/scan/diagnostic-corpus-v2 \
  --resume
```

The resume exited 0. Its exact terminal stdout was:

```json
{"completed_pairs": 512, "completion": "/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/scan/diagnostic-corpus-v2/diagnostic-completion.json", "completion_sha256": "00087d6024ec516452282719f335f7ee966de2d4198c5bb7730ba9c08f2685f2", "proof_status": "diagnostic_completion_only_no_global_unsat_or_upper_bound_upgrade", "status": "COMPLETE", "status_event": "/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/scan/diagnostic-corpus-v2/status-events/status-1784701903920514022.json"}
```

The driver's immutable finalization subprocess record is
`scan/diagnostic-corpus-v2/finalization/attempt-001/01_diagnostic_completion.json`.
It records this full argv, `exit_code=0`, `termination_reason=completed`, and
`process_group_clean=true`:

```bash
/home/zhuran24/.local/share/uv/python/cpython-3.13.13-linux-x86_64-gnu/bin/python3.13 \
  /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/docs/research/b1_conditional_halo_20260722/close_b1_conditional_halo_diagnostic_completion_v1.py \
  --project-root /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721 \
  --corpus /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/diagnostic-corpus/ceiling-diagnostic-corpus-v2.json \
  --run-index /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/scan/diagnostic-corpus-v2/run-index.json \
  --output /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/scan/diagnostic-corpus-v2/finalization/attempt-001/diagnostic-completion.candidate.json
```

The terminal completion gate was then rerun independently to a new
no-overwrite report:

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/b1_conditional_halo_20260722/close_b1_conditional_halo_diagnostic_completion_v1.py \
  --project-root /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721 \
  --corpus /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/diagnostic-corpus/ceiling-diagnostic-corpus-v2.json \
  --run-index /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/scan/diagnostic-corpus-v2/run-index.json \
  --output /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_conditional_halo_20260722/run-20260722T015946Z-zkMRiF/reports/diagnostic-completion-v2-terminal-recheck.json
```

It exited 0 with `status=PASS`. The recheck and published completion are both
685,229 bytes with SHA-256
`00087d6024ec516452282719f335f7ee966de2d4198c5bb7730ba9c08f2685f2`.

## Fail-closed execution history

| Path | Historical result | Authority status |
|---|---|---|
| `diagnostic-corpus/ceiling-diagnostic-corpus-v1.json` | Original and transpose cases shared one logical identity, leaving only 256 unique `pair_id` values. | Rejected; never eligible for completion. |
| `paired-models/case-000/` | Early one-case encoder/translation exploration; its initial admission did not carry the complete logical pair identity. | Non-authoritative. |
| `constructor-smoke/smoke-lKxIjS/` | Constructor/checker smoke for one pair. | Non-authoritative. |
| `reports/canary-external-workspace-smoke-v1.json` | Verified that disposable mutation fixtures may live outside the project while retained inputs stay byte-bound. | Smoke evidence only. |
| `scan/diagnostic-corpus-v1/` | Stopped before any checkpoint because canary mutant metadata initially required a project-relative temporary path. | Immutable failed run; 0 completed pairs. |
| `scan/diagnostic-corpus-v2/attempts/case-381/attempt-001/` | Stopped at the artifact disk gate before translation admission. | Immutable uncheckpointed history; excluded from run-index. |
| `scan/diagnostic-corpus-v2/attempts/case-381/attempt-002/` | Re-executed all ten steps and closed both arms. | Canonical checkpoint source for case 381. |
| `scan/diagnostic-corpus-v2/` | Byte-locked authority diagnostic batch. | **COMPLETE**; current authority. |

The failed `diagnostic-corpus-v1` run exposed an integration bug: disposable
canary fixtures were correctly placed under `/tmp`, but metadata provenance
and path recording assumed every path was under the repository. The writer
was changed to retain an absolute path for an external disposable fixture, a
regression test and complete four-canary smoke were added, and a new
byte-locked output directory was used. The failed directory was neither
overwritten nor resumed after the pinned source changed.

The authority `diagnostic-corpus-v2` batch later paused fail-closed before
case 381's translation admission when free space was 10,062,876,672 bytes,
674,541,568 bytes below the 10 GiB low-water requirement. Historical event
`status-1784696175797421436.json` has SHA-256
`b03550c1bcf7a2069cffea93aa4d2ce33b0d3f4dc03403ad0b2175e4a92f30b9`.
The resume first revalidated the batch identity, all 381 checkpoints, and all
14 pinned input/tool records. No batch-identity-pinned byte changed.

Case 381's successful attempt records pair preflight free space of
12,217,061,376 bytes. Its canonical run-index entry binds:

| Case-381 attempt-002 record | SHA-256 | Size |
|---|---|---:|
| `pair_run.json` | `e3ced8d4dddd4cfdb6526d92347cac5561418dc603fcde701f449bef1e8f0fca` | 70,671 B |
| `SHA256SUMS.recursive` | `d372e2ee3afd7caa316981f3d17654313a54505923b328e5c6f085cf84a824d2` | 1,920 B |
| `manifest-verification.json` | `2938343604bbfccd67810a367f78f712ad4dc434fed76fbbaee59bc457b83c81` | 2,404 B |

## Repository-gate closeout history

Before the secret-scan watchdog repair, this exact command was run:

```bash
PREFLIGHT_TIMEOUT_SCALE=2 PYTHONDONTWRITEBYTECODE=1 /home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 scripts/preflight_gate.py --full
```

It exited 1 with the authentic terminal summary `18 passed, 1 BLOCKED`.
Its pytest lane was green (`4,673 passed, 74 skipped`), while secret scan
reported `secret scan 超时 (>30s)`. A direct run of the same scanner checked
all 30,472 candidate text paths successfully in 45.913 seconds.

The closeout changed only that watchdog to
`max(1, int(30 * _TIMEOUT_SCALE))` and made the blocker report the resulting
seconds. Focused tests bind unit scale to `30` and scale `2.0` to `60`. No
secret pattern, path enumeration, scan boundary, return-code rule, default
base, or other timeout changed. The historical failure above is not rewritten
by the later green runs.

## Resource and MCP ownership record

The dormant formal contract is one worker with `MemoryHigh=35GiB`,
`MemoryMax=39GiB`, `MemorySwapMax=16GiB`, `OOMPolicy=continue`,
`KillMode=control-group`, a 5,000,000,000-byte proof cap, and a 10 GiB disk
low-water mark. Formal capacity admission totals 15,737,418,240 bytes.

The terminal COMPLETE event records 19,194,449,920 bytes free, so the terminal
capacity check is numerically GO. Formal execution nevertheless remained
unauthorized because the byte-locked identity sets
`formal_tools_authorized=false` and `proof_fallback_authorized=false`.
RoundingSat and VeriPB invocation counts are both zero.

Runner artifacts record `mcp_processes_started_by_runner=[]` and
`cleanup_required=false`. Delegated read-only terminal audits reported no MCP
launch. Process termination is authorized only by a unique spawn token,
dedicated cgroup, or equivalent lifecycle evidence. Shared Chrome/CDP,
CodeGraph, main-Codex, other-session MCP, live solver, and otherwise unowned
processes were never eligible for cleanup.

## Reproduction contract

Use the fixed interpreter:

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13
```

The exact authority and resume invocations are preserved above. A replay must
change `--output-dir` to a new persistent child such as
`scan/replay-<unique-id>`; it must never target the completed authority path.
`/tmp` is reserved only for disposable per-case mutation fixtures. An
interrupted replay may add `--resume` only when its published batch identity
and every pinned byte still match. Any batch-identity-pinned input/tool byte
change requires a new no-overwrite batch identity.

## Terminal acceptance commands

The terminal reader-facing documents are accepted only after the commands
below complete:

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 -m pytest -q src/tests/test_b1_conditional_halo_v1.py
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 -m pytest -q src/tests/test_r1_upper_bound_pb_v1.py
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 -m pytest -q src/tests/test_preflight_gate.py
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 -m ruff check docs/research/b1_conditional_halo_20260722 src/tests/test_b1_conditional_halo_v1.py
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 -m ruff format --check docs/research/b1_conditional_halo_20260722 src/tests/test_b1_conditional_halo_v1.py
git diff --check
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 scripts/check_external_artifacts.py --require candidate_placements
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 docs/research/cleanroom_rederivation_20260718/verify_r3_certificates.py
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 scripts/check_repo_secrets.py
PREFLIGHT_TIMEOUT_SCALE=12 PYTHONDONTWRITEBYTECODE=1 /home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 scripts/preflight_gate.py --full
git status --short --branch
```

| Terminal check | Result |
|---|---|
| Independent completion-gate rerun | `exit_code=0`, `status=PASS`; output byte-identical to authority completion |
| B1 round-2 directed tests | `exit_code=0`; `38 passed` |
| R1 proof-runner directed tests | `exit_code=0`; `7 passed` |
| Focused preflight-gate tests | `exit_code=0`; `4 passed` |
| Ruff check | `exit_code=0`; `All checks passed!` |
| Ruff format check | `exit_code=0`; `16 files already formatted` |
| `git diff --check` | `exit_code=0` |
| External `candidate_placements` contract | `exit_code=0`; pinned artifact verified |
| R3 certificate recomputation | `exit_code=0`; stencil 396, placements 840, `P>=9`, lex-max `(1190,34)` |
| Direct repository secret scanner | `exit_code=0`; 39,650 candidate text paths checked |
| Full preflight, scale 12 | `exit_code=0`; `19 passed`; pytest `4,675 passed, 74 skipped` |

The terminal `git status --short --branch` output is intentionally dirty and
uncommitted:

```text
## codex/track-b-b0-1190-20260721
 M scripts/preflight_gate.py
 M src/tests/test_preflight_gate.py
 M src/tests/test_r1_upper_bound_pb_v1.py
?? .artifacts/track_b_b0_1190_34/
?? .artifacts/track_b_b1_conditional_halo_20260722/
?? .artifacts/track_b_b1_q_membrane_halo_20260722/
?? docs/research/b1_conditional_halo_20260722/
?? docs/research/b1_q_membrane_halo_20260722/
?? docs/research/r3_upper_bound_pb_20260722/
?? src/tests/test_b1_conditional_halo_v1.py
?? src/tests/test_b1_q_membrane_halo_v1.py
?? src/tests/test_r3_upper_bound_pb_v1.py
```

An initial attempt to run the B1 and R1 pytest lanes concurrently caused a
shared `.pytest_tmp` directory race. The R1 invocation reported six passes and
one setup error, `FileExistsError`, while the B1 lane completed normally. That
concurrent R1 result is not accepted as a test result. The table records the
subsequent isolated R1 rerun, which exited 0 with all seven tests passing.

Repository checks validate the delivery surface. They do not upgrade the
sampled diagnostic into full-band UNSAT, a smaller upper bound, a witness, or
production `CERTIFIED` evidence.
