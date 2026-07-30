# AB16 Gate A recovery execution record

Document kind: execution history
Cutoff date: 2026-07-24
Cutoff status: `DISPOSABLE_LIVE_CHAIN_PASS / FULL_PREFLIGHT_PASS / GATE_A_FINALIZED / GATE_B_NOT_CREATED`

## Immutable starting facts

- Worktree:
  `/home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723`
- HEAD: `398f8725c770f3c36408adebe9448a890ed886fe`
- Git common directory: `/home/zhuran24/zmd-pj-codex/.git`
- Existing history-freeze manifest:
  `.artifacts/noncert_cuts_ab_trust_gate1_v4_20260724/history-freeze-a001/manifest.json`
- History-freeze manifest size: `1,397,516` bytes
- History-freeze manifest SHA-256:
  `35e99c96482573976b70698f3422c9ab586afb1df3366e466ff93f901114de68`

The existing campaign and its artifacts were treated as read-only. No old
selection, arm, receipt, package member, history manifest or closeout was
overwritten or removed.

## Initial lightweight implementation phase

Before any live recovery began, the initial lightweight implementation phase
added only research source, focused tests and these documents. During that
phase it did not:

- acquire a heavy-validation or prod-scale lock;
- invoke `systemd-run` or create a transient unit;
- invoke the production solver;
- run a disposable live drill;
- run full preflight;
- create a Gate A receipt or candidate;
- create a Gate B approval or formal campaign root;
- publish a prospective manifest, baseline receipt, suite selection or
  per-arm selection;
- create or run any of the 16 organic arms.

The focused tests use small synthetic fixtures and fake lifecycle adapters.
They are not experimental evidence and cannot authorize a formal run.

## Offline validation

The lightweight implementation was validated with the fixed Python 3.13
environment. The merged focused suite completed as:

```text
178 passed in 9.80s
```

That suite covers source and manager-epoch binding, no-overwrite campaign
topology, baseline admission, cut-free fixed-assignment replay,
credibility-first activation branches, ledger and compiled-cut joins,
two-stage resource/terminal/cleanup replay, canonical same-FD
`systemctl`/`systemd-run` execution, terminal aggregation and the disposable
drill's distinct purpose. `py_compile`, Ruff check and Ruff format check also
passed over the AB16 research Python files and focused tests.

These checks used only offline fixtures. During this initial phase they did
not execute a real transient unit, manager attestation, solver, live drill,
formal campaign or organic arm. Full preflight was not run in that phase.

## Gate A execution

Gate A used the no-overwrite validation run:

```text
.artifacts/noncert_cuts_ab16_20260724/
  gate-a-20260724T043946Z-XBW4l8/
```

The lock-held disposable-drill precheck passed at
`2026-07-24T04:41:13.967881Z` with:

- planned source-set digest
  `4d9abb788b204b02f2836f3506492fc5f36f135c30292a8e6bb528dc66c2b482`;
- `34,317,201,408` bytes `MemAvailable`;
- `50,168,631,296` bytes `SwapFree`;
- `29,035,651,072` bytes available on the repository filesystem;
- the shared heavy-validation lock acquired;
- no concurrent heavy process observed;
- repository HEAD
  `398f8725c770f3c36408adebe9448a890ed886fe`.

The disposable authority builder then returned exit code `2` and wrote:

```text
{"detail":"repository HEAD replay failed closed","status":"FAIL_CLOSED"}
```

The failure occurred before the requested `drill-*` output directory was
created. Consequently there was no drill selection, transient unit, payload,
keeper, cgroup, terminal envelope, cleanup receipt or detached replay. The
serial Gate A contract closed full preflight without starting it.

The immutable closeout is `gate-a-closeout.json`, `4,161` bytes, SHA-256
`e420647211a88093467103db4c341eaf4b558e63c78803a911fa0dc944f8b1f7`.
Its original process-count field included observer command-line matches. The
no-overwrite `gate-a-closeout-addendum-a001.json`, `894` bytes, SHA-256
`e7894ab5b6e43da277ab2ebb232b59472748b258382496a6c615714389c1aefa`,
records the corrected read-only observation of zero matching drill processes
and zero matching units. The original closeout remains unchanged.

A post-failure read-only invocation of the pinned HEAD replay returned the
expected commit. That diagnostic is not a Gate A PASS, cannot retroactively
change the failed command, and does not authorize retry.

## Gate A recovery

The serialization boundary in
`disposable_drill_authority_v1._observe_repository_head` was repaired without
changing the lower same-FD Git observer. The wrapper now rejects a non-string
planned identity path and converts the serialized string to `Path`. An audit
of the other serialized path call sites found no second instance: manager
epoch capture accepts `Path | str`, snapshot helpers normalize their input,
and the campaign bootstrap's other HEAD calls receive resolved `Path` values.

The new regression test passes a real Git executable through a canonical JSON
round trip and invokes the wrapper without monkeypatching it. The first test
invocation exposed an incorrect test-only API name
(`canonical_json` instead of `canonical_json_bytes`). After correcting that
test call, the focused validation completed as:

```text
3 passed in 0.09s
py_compile: PASS
Ruff check: PASS
Ruff format --check: PASS
git diff --no-index --check: PASS
```

The prior Gate A run was rehashed before recovery. Its closeout remained
`4,161` bytes with SHA-256
`e420647211a88093467103db4c341eaf4b558e63c78803a911fa0dc944f8b1f7`;
its addendum remained `894` bytes with SHA-256
`e7894ab5b6e43da277ab2ebb232b59472748b258382496a6c615714389c1aefa`.

The recovery used:

```text
.artifacts/noncert_cuts_ab16_20260724/
  gate-a-recovery-20260724T045351Z-mgZ1wQ/
```

The shared validation lock was acquired before the live attempt. The
precheck recorded:

- HEAD `398f8725c770f3c36408adebe9448a890ed886fe`;
- Git common directory `/home/zhuran24/zmd-pj-codex/.git`;
- planned source-set digest
  `fb32a135d6c45bf30979a66314094cee7b13176bb6db3926ce02f2397ffefeeb`;
- `34,213,376,000` bytes `MemAvailable`;
- `50,168,639,488` bytes `SwapFree`;
- `29,081,194,496` bytes available on the repository filesystem;
- no concurrent heavy process;
- successful non-interactive sudo prerequisite.

The repaired authority builder returned exit code `0`. It sealed
`drill-recovery-a001`, its pre-run authority and its disposable selection. The
live command then launched
`noncert-cuts-ab16-gatea-drill-50683ea670be.service`. The payload returned
normally, and pre-terminal replay established the `2/4/1 GiB` contract,
`19,337,216` bytes peak memory, zero swap use and zero OOM-related events.

After keeper release, the lifecycle failed with exit code `2` and the exact
diagnostic:

```text
FAIL_CLOSED: terminal InvocationID drifted
```

No `terminal-envelope.json` or `detached-replay.json` exists. The fail-closed
cleanup record is `PASS`: the payload and keeper were absent, the cgroup path
was absent, the unit was `not-found`, and the closeout found no matching
process or unit. Pre-terminal success cannot substitute for the missing
terminal and detached gates.

The recovery artifact allowlist is `recovery-artifact-manifest.json`,
`14,759` bytes, SHA-256
`ed89661c66946b337811053c589da08a950a89dfcc924fe97f837d261a431fbf`.
The immutable closeout is `gate-a-recovery-closeout.json`, `5,090` bytes,
SHA-256
`0e06c0f850c571f453bc88f8262c233e2bbcd6dec077970ab6a44ebb15469549`.

The serial Gate A contract stopped before full preflight. No Gate B approval,
formal campaign, solver, prospective suite selection, organic arm, mechanism
claim or project claim was created.

## Terminal-reference recovery

The next implementation generation retained the two failed roots byte for
byte and froze them with the no-overwrite manifest:

```text
.artifacts/noncert_cuts_ab16_20260724/
  gate-a-terminal-reference-history-freeze-a001/manifest.json
```

The manifest covers `67` files, is `15,584` bytes and has SHA-256
`f1a2edd604f06cb958258ea5bfcb3cc8a7ad154cbce184cd73e6a9b15302f619`.

The terminal-evidence implementation holds a persistent sd-bus reference from
before keeper release through two terminal snapshots. It requires the same
nonempty `InvocationID`, DBus client and manager owner, retains the unit for at
least one second, releases the reference only after the stable snapshot, and
then separately proves cleanup. The pinned Gate A entrypoint loads its exact
dependency bytes from retained `O_NOFOLLOW` descriptors and exposes no formal,
solver, campaign or organic-arm dispatch.

Focused validation completed before the live recovery:

```text
58 passed in 4.61s
237 passed in 14.49s
py_compile: PASS
Ruff check: PASS
Ruff format --check: PASS
```

The first count is the final terminal-reference-focused suite; the second is
the broader offline AB16 suite. They are implementation evidence, not live
terminal evidence.

The no-overwrite recovery root is:

```text
.artifacts/noncert_cuts_ab16_20260724/
  gate-a-terminal-reference-recovery-20260724T063253Z-b1b89dca/
```

Its planned source observation binds `53` identities with source-set digest
`9485205ecd8270f4cf8e8e0ddf5dbaaf651f0ba6dfb1c2dc40c51dc9d5957fa2`;
the observation is `17,620` bytes with SHA-256
`f2b061b7930f29d2a6ecf4df3fcb6519663b0e6c9d6768f42ca6821b9f92c95f`.

The shared validation lock was acquired. The resource precheck passed every
preregistered condition: expected HEAD, at least `4 GiB` available memory,
at least `1 GiB` free swap, at least `11,811,160,064` available filesystem
bytes, successful noninteractive read-only attestation prerequisite and no
other heavy process. Its receipt is `747` bytes with SHA-256
`45d52a8734c1e841ed067660753534adfb02d04645b4ba93a75af3f887f0017f`.

The pinned disposable-authority builder then returned exit code `2`:

```text
{"detail":"strict input path map is not canonical JSON","status":"FAIL_CLOSED"}
```

The pinned `strict-inputs.json` is `1,218` bytes and the pinned
`system-tools.json` is `344` bytes. Each ends with one LF; their required
canonical encodings are respectively `1,217` and `343` bytes. The inputs were
not rewritten. The builder failed before creating
`drill-terminal-reference-a001`, manager-epoch evidence, a disposable
selection or a transient unit. No matching drill unit remained, and the
intended formal campaign path stayed absent.

The immutable closeout is
`gate-a-terminal-reference-closeout-a001.json`, `4,794` bytes, SHA-256
`af4b71200fbb34c87392c34e37c592b0b75ebc5a805cf108f91466417a435400`.
It records `NOT_RUN_DUE_TO_DISPOSABLE_AUTHORITY_BUILD_FAILURE` for full
preflight and keeps every formal, solver and arm authorization false. Per the
Gate A immediate-stop contract, no replacement recovery or full preflight was
started.

## Canonical-input sibling recovery

The next sibling recovery closes the missing production boundary for the
external Gate A input maps. `gate_a_recovery_inputs_v1.py` builds the exact
strict-input and system-tool role maps, validates every mapped source through
the v2 planned-source enumerator, creates a new sibling root with exclusive
no-symlink directory operations, and writes both maps plus the planned-source
observation through lifecycle canonical JSON and `O_EXCL`.

This encoding intentionally has no trailing LF. The campaign v4
path-preregistration domain intentionally retains its separate LF-terminated
canonical encoding; the two domains were audited and were not unified.
Internal v2 planned-source and control records already used the lifecycle
writer and required no change.

The producer is a registered v2 planned-source role, but it is not a pinned
Gate A dispatch command. Its real CLI, downstream builder consumers and pinned
observation consumer were validated together. The final focused result was:

```text
27 passed in 0.48s
py_compile: PASS
Ruff check: PASS
Ruff format --check: PASS
static diff check: PASS
```

The regressions cover exact re-encoding, no trailing LF, mode `0444`, complete
roles, actual consumer joins, no-overwrite replay, symlink rejection,
role/type drift, LF/whitespace/duplicate-key mutations, source drift and the
two distinct canonical domains. Generated research `__pycache__` files were
removed before the production input observation.

The production CLI created exactly one new sibling:

```text
.artifacts/noncert_cuts_ab16_20260724/
  gate-a-terminal-reference-recovery-20260724T065556Z-C4n0n1/
    input-authority-a001/
```

The immutable input identities are:

| File | Mode | Size | SHA-256 |
| --- | ---: | ---: | --- |
| `strict-inputs.json` | `0444` | 1,217 B | `b7c6daa41eacd8bde444438c1365db0b52557ce374e5226ba0e1c6ed4e113f74` |
| `system-tools.json` | `0444` | 343 B | `67694704c4cd859fa913b7b706199783763a33e1d56d5018fc144d67b878e2de` |
| `planned-source-observation.json` | `0444` | 17,962 B | `77f139bbdf10dabe9ec82be041fe05aa7fbecc3043dbcfce495a927f2af587a3` |

The observation contains `54` identities and source-set digest
`6d709cdc0463a230cbd223102fe6b7956c4cdd1f7a9f2092fc4dfe046db1e2e2`.
It binds the producer's `10,618` bytes at SHA-256
`40c59fd6c171ca08ed5635d92bce2fb17466c6b0b555ac7de363cae7592ddde8`.

No heavy-validation lock was acquired for this sibling. A read-only resource
snapshot before pausing showed `34,081,206,272` bytes `MemAvailable`,
`50,168,639,488` bytes `SwapFree`, `28,777,156,608` filesystem bytes
available, `24` online logical CPUs, no matching heavy process, no matching
Gate A drill unit and no observed holder of the shared validation lock.
Noninteractive sudo prerequisite checking passed. These observations are
scheduling information, not immutable live-drill authority; they must be
rechecked after the lock is acquired.

The third failed recovery retained its eight recorded SHA-256 identities,
including closeout
`af4b71200fbb34c87392c34e37c592b0b75ebc5a805cf108f91466417a435400`.
The earlier `67`-file history freeze also remains unchanged. No failed run was
repaired, overwritten or joined to the new sibling.

## Disposable live-chain result

The sibling's shared-lock precheck was frozen as
`drill-resource-precheck-a001.json`, `2,214` bytes, SHA-256
`d0cbcf84a9b3c3815f13b17730f65edafd9cc8e8de704b3edfff2a55c2df98b7`.
At `2026-07-24T07:04:40.494037Z`, every preregistered check passed:

- HEAD `398f8725c770f3c36408adebe9448a890ed886fe`;
- exact identities for all three canonical input files;
- `34,118,930,432` bytes `MemAvailable`;
- `50,168,639,488` bytes `SwapFree`;
- `28,775,243,776` filesystem bytes available;
- successful noninteractive sudo prerequisite;
- no concurrent heavy process or matching unit;
- the shared heavy-validation lock held by this execution.

The retained-FD pinned authority builder returned exit code `0`. Its
`authority-ready.json` is `1,201` bytes with SHA-256
`606434109e416f1f7fb39776f700fd3775965c3a42291d5e66e58a4d5eb19e93`;
the bound `pre-run-authority.json` is `38,970` bytes with SHA-256
`65fec4f48c12043bc029c977826b1adb0f73a47280be07999895441b0a79150c`.
The authority keeps solver, formal-campaign and arm-launch authorization
false.

The retained-FD disposable live drill also returned exit code `0`. It used:

```text
unit:          noncert-cuts-ab16-gatea-drill-ff93e4d2c472.service
InvocationID:  0f3f4f9c8e7640a6bd1aa74dc8d62cbf
payload PID:   2018333
keeper PID:    2018332
```

The pre-terminal verifier derived `12,935,168` bytes current memory,
`19,595,264` bytes peak memory, zero swap use and zero values for every
recorded memory event, including `oom`, `oom_kill` and `oom_group_kill`. The
terminal envelope preserved the same InvocationID across its first and stable
snapshots and recorded `Result=success`, `ExecMainCode=1` and
`ExecMainStatus=0`.

After release, `cleanup.json` recorded absent payload and keeper processes,
an absent cgroup path, no matching unit and `LoadState=not-found`. The
independent detached replay is `5,211` bytes with SHA-256
`5ff2aa0c74c948b272816b1b7dcc5e68aa9fc3ccc8f7f67a8e7403fc5d91343b`;
it reports `PASS` with verdict
`RESOURCE_TERMINAL_CLEANUP_REPLAY_PASS`. The resource, terminal and cleanup
identities it binds are:

| Evidence | SHA-256 |
| --- | --- |
| `resource-verification.json` | `5a3211d7f10204f3cbd372ec7f1e4fc3224451d364c507f61f2c0129162ac0ab` |
| `terminal-envelope.json` | `c20e0cf60b4aab2f68b1df92ea5a73f5a6d4188b015918bc56c97aa3785b4a13` |
| `cleanup.json` | `ee9021d4ec3e38c37a0caba3326297e6cb6b76e58e3ad68577758db754acb068` |
| `manager-epoch-detached-replay.json` | `2be9a8a9b0c2bb955736a072ff4758b7a9856176bcf3df7c1ebb4c4cc120a9e0` |

The manager epoch remained:

```text
boot_id:          7af1ac9e-b552-412a-84e0-bf8bf2955835
DBus owner:       :1.1
manager PID:      2118
PID starttime:    3154
manager version:  261.1-1-arch
executable:       /usr/lib/systemd/systemd
executable SHA:   de79adab851d295b6a6d403d03552bf16f0f51642f4f7da07bf0e9c139719953
```

The lock was released after the complete read-only replay passed. A
post-release scheduling snapshot found `34,113,122,304` bytes
`MemAvailable`, `50,168,639,488` bytes `SwapFree`,
`28,773,318,656` filesystem bytes available, `24` logical CPUs and load
averages `0.15 0.21 0.31`. It found no lock holder, heavy process, matching
unit or residual drill process. The intended full-preflight and formal
campaign paths remained absent.

## Full-preflight result

The single authorized full-preflight execution reacquired the shared
heavy-validation lock and repeated every fresh prerequisite before consuming
`full-preflight-a001`. The lock-held checks passed with:

- HEAD `398f8725c770f3c36408adebe9448a890ed886fe`;
- planned-source observation SHA-256
  `77f139bbdf10dabe9ec82be041fe05aa7fbecc3043dbcfce495a927f2af587a3`;
- source-set digest
  `6d709cdc0463a230cbd223102fe6b7956c4cdd1f7a9f2092fc4dfe046db1e2e2`;
- detached replay SHA-256
  `5ff2aa0c74c948b272816b1b7dcc5e68aa9fc3ccc8f7f67a8e7403fc5d91343b`;
- unchanged boot ID, DBus owner, manager PID/starttime and manager executable
  identity;
- `34,126,630,912` bytes `MemAvailable`;
- `50,168,635,392` bytes `SwapFree`;
- `28,769,611,776` filesystem bytes available;
- no competing heavy process, matching unit, cgroup or occupied output path.

The executed retained-FD command was:

```bash
exec 9<docs/research/noncert_cuts_ab16_20260724/gate_a_pinned_entrypoint_v2.py
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 -B -I /proc/self/fd/9 \
  --planned-source-observation .artifacts/noncert_cuts_ab16_20260724/gate-a-terminal-reference-recovery-20260724T065556Z-C4n0n1/input-authority-a001/planned-source-observation.json \
  --planned-source-observation-size 17962 \
  --planned-source-observation-sha256 77f139bbdf10dabe9ec82be041fe05aa7fbecc3043dbcfce495a927f2af587a3 \
  --planned-source-set-digest 6d709cdc0463a230cbd223102fe6b7956c4cdd1f7a9f2092fc4dfe046db1e2e2 \
  record-preflight -- \
  --authority-root .artifacts/noncert_cuts_ab16_20260724/gate-a-terminal-reference-recovery-20260724T065556Z-C4n0n1/drill-terminal-reference-a001 \
  --repository-root /home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723 \
  --output-dir .artifacts/noncert_cuts_ab16_20260724/gate-a-terminal-reference-recovery-20260724T065556Z-C4n0n1/full-preflight-a001
```

The command produced `full-preflight-a001/receipt.json`, `3,495` bytes,
SHA-256
`630c8614c7ec30ad0db702c231018afa7739f04d0d163be50e0838ba2bf5dce0`.
Its terminal fields are:

```text
status:                 FAIL_CLOSED
exit_code:              1
timed_out:              false
duration_monotonic_ns:  66387895
```

The immutable stdout is `543` bytes with SHA-256
`0080d62ca8e8cb1bb50e5068b72d7e762742a023ba62cf228b10e8867f0b2732`.
It records successful gate 1 and entry into gate 2. The immutable stderr is
`2,753` bytes with SHA-256
`fec4a1965ba8c28cb71ee7cfdf1b7c172986c66b48081ae3b3b157abb6360eb7`.
The first exception arose when gate 2 attempted to launch
`check_external_artifacts.py`: the same-FD Python execution strategy left
`sys.executable` empty, so `subprocess` raised
`PermissionError: [Errno 13] Permission denied: ''`.

A `0.5`-second sampling monitor observed a peak process-tree RSS of
`37,888,000` bytes, minimum `MemAvailable` of `33,844,903,936` bytes,
unchanged minimum `SwapFree` of `50,168,635,392` bytes, minimum filesystem
availability of `28,769,591,296` bytes and maximum one-minute load of `0.16`.
These are scheduling observations rather than receipt authority.

The post-command replay revalidated the existing drill, planned sources,
HEAD and manager epoch before rejecting the preflight receipt because it was
not an exact PASS. The exit trap released the shared lock. No matching drill
unit or process remained, and the recovery root gained only the immutable
`full-preflight-a001` directory.

## Terminal state after the first full-preflight failure

`full-preflight-a001` is consumed and is not retried, replaced or repaired.
No `finalize-gate-a` action ran. No Gate B approval, formal campaign, solver
run, prospective suite selection or organic arm exists. The live drill remains
non-authorizing and the failed preflight establishes no mechanism, cut,
soundness, bound or witness claim.

## Same-FD nested Python recovery

The immutable `full-preflight-a001` receipt and logs were retained with their
original identities:

| Evidence | Size | SHA-256 |
| --- | ---: | --- |
| `receipt.json` | 3,495 B | `630c8614c7ec30ad0db702c231018afa7739f04d0d163be50e0838ba2bf5dce0` |
| `stdout.log` | 543 B | `0080d62ca8e8cb1bb50e5068b72d7e762742a023ba62cf228b10e8867f0b2732` |
| `stderr.log` | 2,753 B | `fec4a1965ba8c28cb71ee7cfdf1b7c172986c66b48081ae3b3b157abb6360eb7` |

The failure arose because the verified Python FD was the top-level executable
but the child received relative `argv[0]="python3.13"`. CPython could not
derive its installation prefix, emitted `Could not find platform dependent
libraries <exec_prefix>` and left `sys.executable` empty. The first direct
nested Python launch therefore attempted an empty executable.

The repaired runner preserves these execution invariants:

1. the parent opens and verifies the pinned Python and script through
   `O_NOFOLLOW` FDs and retains both until the child terminates;
2. `executable=/proc/self/fd/<python_fd>` remains the actual top-level exec
   source, while the same pinned absolute Python path is only `argv[0]`;
3. the loader independently checks both inherited descriptors' type, link
   count, mode, size, SHA-256 and before/after metadata;
4. the loader joins the Python FD to its pinned path, then sets
   `sys.executable` and `_base_executable` to
   `/proc/<current-preflight-pid>/fd/<python_fd>`;
5. direct child and grandchild Python launches use that still-live descriptor
   path, while prefix, exec prefix and stdlib remain those initialized from
   the pinned absolute path;
6. the parent rechecks both still-open FDs after completion or timeout and
   closes them in all outcomes.

New receipts use schema
`noncert-cuts-ab16-gate-a-full-preflight-receipt-v3`, strategy
`same-fd-python-prefix-and-nested-executable-v2` and an exact loader
size/SHA-256 identity. Strict replay rejects the prior strategy, loader drift
or command-argv drift.

The true E2E fixture used the production loader and executable-FD path without
mocking `subprocess.run`. A pinned top-level Python launched a child Python,
which launched a grandchild Python. All three reported the same live
`/proc/<top-level-pid>/fd/<python_fd>` executable, valid prefix/exec-prefix and
stdlib directories, and empty stderr. Wrong and closed Python FDs, script
identity drift, receipt strategy/loader/argv drift and no-overwrite replay
all failed closed.

Focused validation completed as:

```text
16 passed in 0.31s
43 passed in 0.78s
py_compile: PASS
Ruff check: PASS
Ruff format --check: PASS
```

The production recovery-input entry then established a new input-only
sibling:

```text
.artifacts/noncert_cuts_ab16_20260724/
  gate-a-python-fd-recovery-20260724T074207Z-FD2v2/
    input-authority-a001/
```

Its three immutable members are:

| File | Mode | Size | SHA-256 |
| --- | ---: | ---: | --- |
| `strict-inputs.json` | `0444` | 1,217 B | `b7c6daa41eacd8bde444438c1365db0b52557ce374e5226ba0e1c6ed4e113f74` |
| `system-tools.json` | `0444` | 343 B | `67694704c4cd859fa913b7b706199783763a33e1d56d5018fc144d67b878e2de` |
| `planned-source-observation.json` | `0444` | 17,962 B | `876e203fb5f92c8948948538f2869af409e85b11ced1e44a82681e275711214e` |

All three equal their lifecycle canonical re-encoding and have no trailing
LF. The observation binds `54` sources under source-set digest
`e8c814ca4dbc5d427a492c95b442fe589321e5120ee0f2e1cbc5fb1d1f64473d`.
It binds the producer's `10,618` bytes at SHA-256
`40c59fd6c171ca08ed5635d92bce2fb17466c6b0b555ac7de363cae7592ddde8`
and the repaired runner's `30,555` bytes at SHA-256
`382f0c3833a7a2eab7e2d0faba96a34e8c5d4c61d7161ae60b0134f5e3ae6e31`.

At the end of this input-only publication step, before the later live-chain
execution recorded in the next section, no builder, manager capture, live
drill, detached replay, preflight or finalize action had run for this
sibling. No Gate B, formal campaign, solver, suite selection or organic arm
had been created.

## Python-FD sibling disposable live-chain execution

The fixed sibling was resumed without changing its three input-authority
files. The one preregistered builder/drill output was:

```text
.artifacts/noncert_cuts_ab16_20260724/
  gate-a-python-fd-recovery-20260724T074207Z-FD2v2/
    drill-python-fd-a001/
```

The shared heavy-validation lock was acquired before any authority builder or
unit action. The lock-held precheck reproduced:

- repository HEAD
  `398f8725c770f3c36408adebe9448a890ed886fe`;
- all `54` planned source identities and source-set digest
  `e8c814ca4dbc5d427a492c95b442fe589321e5120ee0f2e1cbc5fb1d1f64473d`;
- the three fixed input identities;
- boot ID `7af1ac9e-b552-412a-84e0-bf8bf2955835`, DBus owner
  `:1.1`, manager PID/starttime `2118/3154` and manager executable SHA-256
  `de79adab851d295b6a6d403d03552bf16f0f51642f4f7da07bf0e9c139719953`;
- no residual drill unit or process and no concurrent heavy validation.

The scheduling snapshot at that gate was:

```text
MemAvailable:              33,808,166,912 B
SwapFree:                  50,168,647,680 B
filesystem available:     28,753,612,800 B
```

The retained-FD pinned authority builder ran once and returned exit code `0`.
It produced:

| Evidence | Size | SHA-256 |
| --- | ---: | --- |
| `authority/authority-ready.json` | 1,154 B | `1261fd7148d3133b1ee7b602ead14bf76ce6bc8cad7beba7f4a339ed8eea4bb1` |
| `attempt/pre-run-authority.json` | 37,916 B | `f6065e9efa8dbb8a0428ba02e6864099e5287d1976b594d4aea6b5a2c18f3e9e` |
| `attempt/selection.json` | 4,010 B | `facd7984d37c2a09a77c4f39e4342e52a097d43d26daa69d1c2209a3f2ae0240` |

`authority-ready.json` has status `PASS`; all solver, formal-campaign and
arm-launch authorization fields are false.

The retained-FD disposable drill then ran once and returned exit code `0`.
The live lifecycle used:

```text
unit:          noncert-cuts-ab16-gatea-drill-7f168834c123.service
InvocationID:  32140fb363dd47baaa9bc6293f5b4289
payload PID:   2065652
keeper PID:    2065651
```

Its principal immutable identities are:

| Evidence | Semantic result | Size | SHA-256 |
| --- | --- | ---: | --- |
| `attempt/result.json` | `DISPOSABLE_DRILL_PAYLOAD_COMPLETE` | 714 B | `df89564a1dfc52388a093e6a5b16ed1085b04b0d4c1cbd9fce262c88422b8170` |
| `attempt/resource-verification.json` | `RESOURCE_PRETERMINAL_PASS` | 2,801 B | `073061365ad226de3cd6906714b8940c0ccba4b209e19cf2fc2b87f5d278f5f0` |
| `attempt/terminal-envelope.json` | stable terminal envelope | 8,520 B | `eee89a523fb1d49694aaab5fee7943aa2844f3968cb119af2c0b9063c858e612` |
| `attempt/cleanup.json` | no residual payload, keeper, cgroup or unit | 5,164 B | `2031b0b9a1d1ac4cceeaf4d4afacc58ef89fbc725f86b7b5a8c5fee66412a087` |
| `attempt/manager-epoch-detached-replay.json` | detached epoch observation | 3,053 B | `5563b3ee8ef8dd2056fe3b58c7217446803dd4df618130c964aa689638793dbe` |
| `attempt/detached-replay.json` | `RESOURCE_TERMINAL_CLEANUP_REPLAY_PASS` | 5,002 B | `624a543e7c0394b4f303c94963bb445313099c9d96bc0d34313095023491bc57` |

The preterminal evidence measured `12,914,688` bytes current memory and
`19,570,688` bytes peak memory. It measured zero swap and zero for every
recorded memory event, including `oom`, `oom_kill` and `oom_group_kill`.
Both terminal snapshots preserved the InvocationID and recorded
`Result=success`, `ExecMainCode=1`, `ExecMainStatus=0`,
`ActiveState=inactive` and `SubState=dead`.

After cleanup, the stored detached receipt returned `PASS`. A separate
read-only call through the validation/replay path re-read the authority,
reobserved all planned sources and HEAD, recaptured the same manager/boot
epoch and independently rebuilt the detached result. It matched the stored
receipt byte-for-byte and returned `PASS`.

The lock was then released. A post-release check found the unit `not-found`,
the shared lock available, `33,957,060,608` bytes `MemAvailable`,
`50,168,647,680` bytes `SwapFree` and `28,751,704,064` filesystem bytes
available. The old `full-preflight-a001` receipt, stdout and stderr remained
at their fixed sizes and hashes. At this live-chain checkpoint, the new
sibling contained no full-preflight, Gate-A finalize, Gate B or
formal-campaign output. No solver, formal suite/arm selection or organic arm
had run.

## Python-FD sibling full-preflight execution

The full-preflight step reacquired
`/tmp/zmd-pj-codex-heavy-validation.lock`. Before consuming the unique
`full-preflight-a001` output, the lock-held gate reproduced:

- HEAD `398f8725c770f3c36408adebe9448a890ed886fe`;
- all `54` planned source identities and source-set digest
  `e8c814ca4dbc5d427a492c95b442fe589321e5120ee0f2e1cbc5fb1d1f64473d`;
- the fixed input authority and complete builder, result, resource, terminal,
  cleanup and detached-replay identities;
- the same boot ID, DBus owner, manager PID/starttime and manager executable;
- all three immutable files from the earlier failed `full-preflight-a001`;
- no residual Gate-A drill unit or process and no concurrent heavy validation.

The fresh resource snapshot was:

```text
MemAvailable:              33,749,598,208 B
SwapFree:                  50,168,647,680 B
filesystem available:     28,743,983,104 B
load average, 1 minute:    1.046875
```

The one retained-FD command used the fixed observation and authority root:

```bash
exec 9<docs/research/noncert_cuts_ab16_20260724/gate_a_pinned_entrypoint_v2.py
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 -B -I /proc/self/fd/9 \
  --planned-source-observation .artifacts/noncert_cuts_ab16_20260724/gate-a-python-fd-recovery-20260724T074207Z-FD2v2/input-authority-a001/planned-source-observation.json \
  --planned-source-observation-size 17962 \
  --planned-source-observation-sha256 876e203fb5f92c8948948538f2869af409e85b11ced1e44a82681e275711214e \
  --planned-source-set-digest e8c814ca4dbc5d427a492c95b442fe589321e5120ee0f2e1cbc5fb1d1f64473d \
  record-preflight -- \
  --authority-root .artifacts/noncert_cuts_ab16_20260724/gate-a-python-fd-recovery-20260724T074207Z-FD2v2/drill-python-fd-a001 \
  --repository-root /home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723 \
  --output-dir .artifacts/noncert_cuts_ab16_20260724/gate-a-python-fd-recovery-20260724T074207Z-FD2v2/full-preflight-a001
```

The pinned entrypoint returned exit code `0`. Strict receipt replay accepted:

```text
schema:       noncert-cuts-ab16-gate-a-full-preflight-receipt-v3
strategy:     same-fd-python-prefix-and-nested-executable-v2
status:       PASS
exit_code:    0
timed_out:    false
duration:     113,605,206,168 ns
```

The immutable result identities are:

| Evidence | Size | SHA-256 |
| --- | ---: | --- |
| `full-preflight-a001/receipt.json` | 3,532 B | `978b0c0297346b11372273d27f0132e97576f231f556c5148402861362fc1160` |
| `full-preflight-a001/stdout.log` | 2,283 B | `d5026b145ab117c4725e9cf3ff3a9b1e5f93e7a222320adedf29db72c4a56749` |
| `full-preflight-a001/stderr.log` | 0 B | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The full gate reported `5108 passed, 74 skipped in 98.31s` for pytest and
`19 passed` overall. Ruff, mypy, external-artifact, secret-scan, frozen-path
and artifact-boundary checks all passed.

The external sampling observation recorded:

```text
peak process-tree RSS:     13,507,510,272 B
minimum MemAvailable:      22,188,326,912 B
minimum SwapFree:          50,168,647,680 B
minimum filesystem free:   28,302,282,752 B
maximum 1-minute load:     24.32373046875
samples:                   218
```

After the receipt was written, strict replay again reproduced the fixed HEAD,
source set, manager/boot epoch and detached drill receipt SHA-256
`624a543e7c0394b4f303c94963bb445313099c9d96bc0d34313095023491bc57`.
The three earlier failure files remained unchanged. The shared lock was
released. No Gate-A finalize, Gate B, formal campaign, solver, formal
suite/arm selection or organic arm was created.

## Gate-A finalize

The shared heavy-validation lock was acquired for the short finalization
window. Before publishing the unique receipt, the lock-held gate reproduced:

- repository HEAD
  `398f8725c770f3c36408adebe9448a890ed886fe`;
- the exact `17,962`-byte planned-source observation at SHA-256
  `876e203fb5f92c8948948538f2869af409e85b11ced1e44a82681e275711214e`;
- all `54` planned sources under source-set digest
  `e8c814ca4dbc5d427a492c95b442fe589321e5120ee0f2e1cbc5fb1d1f64473d`;
- the complete disposable authority, resource, terminal, cleanup and detached
  replay chain;
- the exact-PASS full-preflight receipt at SHA-256
  `978b0c0297346b11372273d27f0132e97576f231f556c5148402861362fc1160`;
- boot ID `7af1ac9e-b552-412a-84e0-bf8bf2955835`, DBus owner `:1.1`,
  manager PID/starttime `2118/3154` and manager executable SHA-256
  `de79adab851d295b6a6d403d03552bf16f0f51642f4f7da07bf0e9c139719953`;
- absence of both the Gate-A receipt and the future campaign target.

The finalization resource snapshot was:

```text
MemAvailable:              34,024,976,384 B
SwapFree:                  50,026,622,976 B
filesystem available:     28,298,878,976 B
```

The retained-FD command was:

```bash
exec 9<docs/research/noncert_cuts_ab16_20260724/gate_a_pinned_entrypoint_v2.py
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 -B -I /proc/self/fd/9 \
  --planned-source-observation .artifacts/noncert_cuts_ab16_20260724/gate-a-python-fd-recovery-20260724T074207Z-FD2v2/input-authority-a001/planned-source-observation.json \
  --planned-source-observation-size 17962 \
  --planned-source-observation-sha256 876e203fb5f92c8948948538f2869af409e85b11ced1e44a82681e275711214e \
  --planned-source-set-digest e8c814ca4dbc5d427a492c95b442fe589321e5120ee0f2e1cbc5fb1d1f64473d \
  finalize -- \
  --authority-root .artifacts/noncert_cuts_ab16_20260724/gate-a-python-fd-recovery-20260724T074207Z-FD2v2/drill-python-fd-a001 \
  --preflight-receipt .artifacts/noncert_cuts_ab16_20260724/gate-a-python-fd-recovery-20260724T074207Z-FD2v2/full-preflight-a001/receipt.json \
  --output .artifacts/noncert_cuts_ab16_20260724/gate-a-python-fd-recovery-20260724T074207Z-FD2v2/gate-a-receipt-a001.json \
  --approval-id gate-a-ab16-20260724T081638Z-preflight-978b0c0297346b11372273d27f0132e97576f231f556c5148402861362fc1160 \
  --target-campaign-dir /home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723/.artifacts/noncert_cuts_ab16_20260724/run-20260724T081638Z-ab16-preflight-978b0c0297346b11372273d27f0132e97576f231f556c5148402861362fc1160 \
  --run-nonce run-20260724T081638Z-ab16-preflight-978b0c0297346b11372273d27f0132e97576f231f556c5148402861362fc1160
```

The pinned entrypoint returned exit code `0`. It published only:

| Evidence | Schema/decision | Size | SHA-256 |
| --- | --- | ---: | --- |
| `gate-a-receipt-a001.json` | `noncert-cuts-ab16-bootstrap-gate-a-receipt-v2` / `PASS` | 5,590 B | `91fbc5488749d9682db8c449923d9ddacd7f85933ce7fe6f7a1a47d1421e8473` |

The receipt was created at `2026-07-24T08:33:35.377623Z`. It binds approval
ID
`gate-a-ab16-20260724T081638Z-preflight-978b0c0297346b11372273d27f0132e97576f231f556c5148402861362fc1160`
and future run nonce
`run-20260724T081638Z-ab16-preflight-978b0c0297346b11372273d27f0132e97576f231f556c5148402861362fc1160`.
The corresponding target campaign directory remained absent.

Strict canonical replay through the downstream Gate-A validator returned
`PASS`. The receipt retains `offline_candidate_only=true`,
`formal_campaign_creation_authorized=false` and
`arm_launch_authorized=false`. The lock was released after replay. No Gate B,
formal campaign, solver, suite/arm selection or organic arm was created.

## Reader self-review

The deliverable was reread as a future operator's entry point. Its headline
status agrees with the repaired runner, successful disposable live chain,
exact-PASS full preflight, finalized Gate-A receipt and absence of Gate B or
formal artifacts. Earlier failures remain distinct immutable history, while
the README presents the current sibling state. The old and new source-set
digests are not conflated; the disposable drill, preflight and Gate-A receipt
are not presented as cuts or solver results; Gate-A finalization is not
presented as technical Gate-B authority; and cross-references resolve within
this research directory. The record contains no claim that a wrapper
failure is a cut result, that a solver result is proved, or that a project
bound changed.
