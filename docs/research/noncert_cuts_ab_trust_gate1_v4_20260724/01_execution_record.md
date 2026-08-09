# Non-certified cuts Gate 1 v4 execution record

Document kind: immutable-history-aware local execution record  
Evidence cutoff date: 2026-07-24 (Asia/Tokyo)  
Terminal status: `CUTS_GATE1_V4_AUTHORITY_COMPLETION_PASS / MECHANISM_CREDIBLE`  
Authority run: `run-20260723T231223Z-0067f7`  
Repository HEAD: `398f8725c770f3c36408adebe9448a890ed886fe`

`README.md` is the reader-facing terminal judgment. This record preserves
implementation and execution history. No organic A/B arm, prospective
manifest, AB16 selection, Track B task, witness task, PIC task, B6 task, or
Stage-B promotion ran.

## Pre-implementation freeze

Before v4 implementation, an O_EXCL/no-symlink manifest fixed the explicit
legacy allowlist:

```text
.artifacts/noncert_cuts_ab_trust_gate1_v4_20260724/
  history-freeze-a001/manifest.json
size_bytes=1397516
sha256=35e99c96482573976b70698f3422c9ab586afb1df3366e466ff93f901114de68
file_count=4076
```

The allowlist excludes the v4 output root created after the freeze. It was
replayed before and after implementation; the manifest bytes and every
listed historical member remained unchanged.

## Disposable drill history

All drill directories are immutable. None can authorize a formal claim.

- `dev-drill-20260723T224656Z-Y13dvw` stopped while parsing the strict
  candidate data.
- `dev-drill-20260723T224822Z-1F5NXQ` stopped at selected execution import.
- `dev-drill-20260723T225056Z-VonFjg` stopped before a unit launch because the
  selected delegate lacked the repository-root import binding.
- `dev-drill-20260723T225536Z-J1tDsA` launched `q-success` and stopped at the
  host's additional `sock_throttled` memory-event field. The exact unit was
  stopped and reset after PID, command, cgroup, and unit identity checks. No
  later evidence was backfilled into that attempt.
- `dev-drill-20260723T230637Z-f1923e` completed all four units but its
  disposable assembler read `common_prestate_id` from the payload wrapper
  rather than the already-validated delegated result. It stopped before
  publishing a drill observation.
- `dev-drill-20260723T231057Z-36fd7f` completed the full disposable path.

Two still earlier bootstrap attempts failed before an output directory was
created: the first rejected the symlinked fixed-Python entrypoint, and the
second lacked the user-bus runtime environment for `busctl`.

The accepted disposable observation is:

```text
dev-drill-20260723T231057Z-36fd7f/
  gate1-v4/dev-drill-observation-a001.json
size_bytes=1461
sha256=2d0a8f445a2db36cefb6fd4bc223aaf6aed8b4f76de90bb002de0e648afca366
status=DEV_DRILL_REPLAY_PASS_NO_AUTHORITY
```

Its full replay result is 16,265 bytes with SHA-256
`92f4e1adaae259b7bfda80d34ba4c3180aec1f55f675387c7f304304f5aa7601`.
Every authorization field is false.

## Formal authority construction

The fixed interpreter was:

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13
```

The repository and schedule inputs were:

```text
PROJECT_ROOT=/home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723
V4_DIR=$PROJECT_ROOT/docs/research/noncert_cuts_ab_trust_gate1_v4_20260724
ARTIFACT_ROOT=$PROJECT_ROOT/.artifacts/noncert_cuts_ab_trust_gate1_v4_20260724
HISTORY_FREEZE=$ARTIFACT_ROOT/history-freeze-a001/manifest.json
SCHEDULE=/home/zhuran24/zmd-pj-codex-baselines/track-b-b1-sidewise-membrane-20260724/docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724/04_cuts_mandatory_schedule.md
FIXED_PYTHON=/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13
RUN=$ARTIFACT_ROOT/run-20260723T231223Z-0067f7
```

The unique formal bootstrap command was:

```text
"$FIXED_PYTHON" "$V4_DIR/gate1_campaign_bootstrap_v4.py" \
  --campaign-dir "$RUN" \
  --repository-root "$PROJECT_ROOT" \
  --history-freeze-manifest "$HISTORY_FREEZE" \
  --cuts-mandatory-schedule "$SCHEDULE" \
  --formal-campaign
```

It exited 0:

```text
status=AUTHORITY_READY_NO_UNIT_LAUNCHED
package_id=ec939ae4378b860a5ce637bbe039843f32595c8492954144fbad2f7eb8214384
campaign_root_size=32464
campaign_root_sha256=f81284b7e54d38661ecd4913700c64444f8001f3ef2addca914238761dbac506
selection_size=19717
selection_sha256=78618026995c7000b1176d04862493bcb47dfd891390c1d08f1b7f066b6a98b0
```

The selected execution entrypoint was:

```text
EXEC=$RUN/campaign-authority/package/payload/tool.gate1_campaign_execution_v4.py
ROOT=$RUN/campaign-root.json
SELECTION=$RUN/gate1-v4/selection-a001.json
```

The formal common-prestate and binding command was:

```text
"$FIXED_PYTHON" "$EXEC" prepare-formal \
  --formal-authorized \
  --campaign-root "$ROOT" \
  --campaign-root-size 32464 \
  --campaign-root-sha256 f81284b7e54d38661ecd4913700c64444f8001f3ef2addca914238761dbac506 \
  --selection "$SELECTION" \
  --selection-size 19717 \
  --selection-sha256 78618026995c7000b1176d04862493bcb47dfd891390c1d08f1b7f066b6a98b0
```

It exited 0 with `both_bindings_sealed_before_arms=true` and
`formal_publication_authorized=true`.

The four-unit command was:

```text
"$FIXED_PYTHON" "$EXEC" orchestrate-formal \
  --formal-authorized \
  --campaign-root "$ROOT" \
  --campaign-root-size 32464 \
  --campaign-root-sha256 f81284b7e54d38661ecd4913700c64444f8001f3ef2addca914238761dbac506 \
  --selection "$SELECTION" \
  --selection-size 19717 \
  --selection-sha256 78618026995c7000b1176d04862493bcb47dfd891390c1d08f1b7f066b6a98b0
```

It executed one unit at a time and exited 0. Each unit produced five
manager-epoch checkpoints, launch evidence, inner lifecycle evidence,
pre-terminal resource authority, release, terminal envelope, cleanup
authority, and a detached replay.

The terminal gate command was:

```text
"$FIXED_PYTHON" "$EXEC" assemble-formal \
  --formal-authorized \
  --campaign-root "$ROOT" \
  --campaign-root-size 32464 \
  --campaign-root-sha256 f81284b7e54d38661ecd4913700c64444f8001f3ef2addca914238761dbac506 \
  --selection "$SELECTION" \
  --selection-size 19717 \
  --selection-sha256 78618026995c7000b1176d04862493bcb47dfd891390c1d08f1b7f066b6a98b0
```

It exited 0:

```text
gate_written=true
continuation_written=true
campaign_closed=false
organic_arm_launch_authorized=false
```

The gate and continuation identities are:

```text
gate-a001.json
  size_bytes=20936
  sha256=0b5d1c97f0d09cd3605e86d5861f300cbd2826bb393ae1d5461c4a0083a944ec

continuation-authorization-a001.json
  size_bytes=5753
  sha256=eb9d569d88578827d46c8209ef5b69eab3c7762ae1edc1ba0ac90f2d8433132b
```

## Implementation defects closed before the authority run

The final implementation closes these observed defects:

1. Every selected unit records independently observed live manager/boot
   identity at five lifecycle phases, and the campaign records a sixth
   post-suite `gate-admission` phase before gate publication.
2. Disposable and formal arithmetic verification use distinct selected
   schemas, purposes, eligibility flags, and entrypoints. Both retain the
   complete model/response/assignment/compiled-cut/ledger check.
3. The campaign root pre-registers the common-prestate manifest, all common
   artifact paths, both binding paths, binding seal, builder exports,
   arithmetic receipt, gate, continuation, and prospective AB16 child paths.
4. The resource verifier accepts exactly the historical six-field
   `memory.events` schema or that schema plus zero-valued
   `sock_throttled`. Unknown fields, mismatched local/global schemas, and a
   nonzero optional field fail closed.
5. If authority collection fails after a unit launch, the orchestrator
   performs an exact non-publishing stop/reset and proves the unit is absent.
   It preserves the original failure and never fabricates terminal evidence.
6. Disposable assembly reads the common-prestate ID from the independently
   validated delegated payload result, matching the formal gate.

## Validation

Before the successful disposable drill, the complete v4 offline suite
reported `144 passed in 10.17s`. The terminal documentation canary increased
the final suite to:

```text
145 passed
```

The final focused validation commands were:

```text
"$FIXED_PYTHON" -m pytest -q src/tests/test_noncert_cuts_ab_gate1_v4_*.py

"$FIXED_PYTHON" -m py_compile \
  "$V4_DIR"/*.py \
  src/tests/test_noncert_cuts_ab_gate1_v4_*.py

"$FIXED_PYTHON" -m ruff check \
  "$V4_DIR" \
  src/tests/test_noncert_cuts_ab_gate1_v4_*.py

"$FIXED_PYTHON" -m ruff format --check \
  "$V4_DIR" \
  src/tests/test_noncert_cuts_ab_gate1_v4_*.py

git diff --check
```

All five commands exited 0. `py_compile` emitted no diagnostics, Ruff check
reported `All checks passed!`, Ruff format reported `21 files already
formatted`, and `git diff --check` emitted no diagnostics.

The project-level command was:

```text
PREFLIGHT_TIMEOUT_SCALE=12 \
  "$FIXED_PYTHON" scripts/preflight_gate.py --full
```

It exited 0:

```text
result=PASSED
preflight_checks=19 passed
pytest=4854 passed, 74 skipped in 126.53s
```

A final read-only replay imported
`campaign-authority/package/payload/campaign_authority_v4.py` from the
authority run, not the mutable research source. It replayed the campaign
root, Gate 1 selection, gate, gate-admission checkpoint, continuation, and
all four detached lifecycle receipts; independently re-observed the live
manager/boot epoch; and confirmed every prospective child path remains
absent:

```text
status=PASS
manager_epoch_live_match=true
gate_status=CUTS_GATE1_V4_AUTHORITY_COMPLETION_PASS
gate_verdict=MECHANISM_CREDIBLE
continuation_authorized=true
organic_arm_launch_authorized=false
prospective_slots_absent=true
```

The same-FD legacy-freeze replay checked 4,076 members and returned `PASS`
with manifest SHA-256
`35e99c96482573976b70698f3422c9ab586afb1df3366e466ff93f901114de68`.
No selected Gate 1 unit remained loaded after execution.

These validations do not authorize an organic arm or upgrade the claim beyond
`MECHANISM_CREDIBLE`.
