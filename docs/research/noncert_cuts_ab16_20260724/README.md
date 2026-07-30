# Prospective non-certified cuts AB16 campaign

Document kind: research implementation and current-status summary
Cutoff date: 2026-07-30
Status: `A031_A032_A033_FROZEN / A033_ADMISSION_ONLY / FRESH_CHAIN_REQUIRED`
Formal campaign: no trusted terminal
Organic arms: `0/16` created or run

## Current status

The mandatory AB16 chain has advanced through fresh Gate-A, Gate-B,
package/campaign creation and formal admission, but it has not consumed a
formal selection or run an organic arm. A031 and A032 froze on pre-owner
bootstrap failures. A033 passed Gate-B qualification and package creation,
then published exactly
`formal-ab16/formal-launch-admission-a001.json`. It has no guardian-ready,
attempt-consumption, formal selection, unit, arm or terminal receipt. All
three roots are immutable and cannot be retried, repaired or used as
authority ancestors for a successor.

A033's selected supervisor error was lost behind the old orchestrator's
generic pre-guardian error. The current orchestrator preserves the selected
supervisor's exact exit/stderr at that boundary, and the selected loader now
has import-only controls for both `formal-orchestrator` and
`formal-supervisor` through the materialized snapshot path. These controls
do not call either role's `main()` and consume no authority.

The A033 preregistration also exposed a deterministic transport blocker: its
canonical absolute `guardian-control.sock` path is `241` bytes, beyond Linux
pathname `AF_UNIX` capacity. The canonical preregistered path and every
serialized identity remain unchanged. Runtime bind/connect uses only a short
retained-directory-FD alias, pins the socket leaf with `O_PATH`, and joins
the canonical parent, leaf identity, mode and peer PID/starttime before
progress. Parent or leaf replacement fails closed; cleanup never unlinks an
unverified node and closes the retained anchor exactly once.

The next attempt must start from a new no-overwrite Gate-A root in the
registered independent worktree after a clean committed HEAD, exact source
rebinding, the fixed resource/lock/competition gate, full preflight and the
same post-preflight gate. A031–A033 remain frozen. The path transport change
does not alter any artifact schema or grant production, certified, cut,
witness or bound authority.

## 2026-07-24 Gate-A recovery history

The no-overwrite sibling recovery recorded at the earlier cutoff was:

```text
.artifacts/noncert_cuts_ab16_20260724/
  gate-a-python-fd-recovery-20260724T074207Z-FD2v2/
    input-authority-a001/
    drill-python-fd-a001/
    full-preflight-a001/
    gate-a-receipt-a001.json
```

`gate_a_recovery_inputs_v1.py` created that input authority through the real
production CLI. Its only members are canonical, read-only
`strict-inputs.json`, `system-tools.json` and
`planned-source-observation.json`. All three exactly equal lifecycle canonical
JSON re-encoding, have no trailing LF, and have mode `0444`.

The current immutable identities are:

| File | Size | SHA-256 |
| --- | ---: | --- |
| `strict-inputs.json` | 1,217 B | `b7c6daa41eacd8bde444438c1365db0b52557ce374e5226ba0e1c6ed4e113f74` |
| `system-tools.json` | 343 B | `67694704c4cd859fa913b7b706199783763a33e1d56d5018fc144d67b878e2de` |
| `planned-source-observation.json` | 17,962 B | `876e203fb5f92c8948948538f2869af409e85b11ced1e44a82681e275711214e` |

The observation binds `54` source identities with source-set digest
`e8c814ca4dbc5d427a492c95b442fe589321e5120ee0f2e1cbc5fb1d1f64473d`.
It includes the producer at SHA-256
`40c59fd6c171ca08ed5635d92bce2fb17466c6b0b555ac7de363cae7592ddde8`
and the repaired validation runner's `30,555` bytes at SHA-256
`382f0c3833a7a2eab7e2d0faba96a34e8c5d4c61d7161ae60b0134f5e3ae6e31`.

Fresh checks under `/tmp/zmd-pj-codex-heavy-validation.lock` reproduced all
`54` planned source identities, the fixed HEAD and the three input
identities. They also reproduced the same manager/boot epoch, found no
residual drill unit or process, and observed:

- `33,808,166,912` bytes `MemAvailable`;
- `50,168,647,680` bytes `SwapFree`;
- `28,753,612,800` filesystem bytes available.

The retained-FD pinned builder then created exactly
`drill-python-fd-a001`. Its immutable authority result is:

| Evidence | Status | Size | SHA-256 |
| --- | --- | ---: | --- |
| `authority/authority-ready.json` | `PASS` | 1,154 B | `1261fd7148d3133b1ee7b602ead14bf76ce6bc8cad7beba7f4a339ed8eea4bb1` |
| `attempt/pre-run-authority.json` | `PASS` | 37,916 B | `f6065e9efa8dbb8a0428ba02e6864099e5287d1976b594d4aea6b5a2c18f3e9e` |
| `attempt/selection.json` | disposable selection | 4,010 B | `facd7984d37c2a09a77c4f39e4342e52a097d43d26daa69d1c2209a3f2ae0240` |

The one disposable live drill completed with unit
`noncert-cuts-ab16-gatea-drill-7f168834c123.service` and InvocationID
`32140fb363dd47baaa9bc6293f5b4289`. Its evidence is:

| Evidence | Terminal meaning | Size | SHA-256 |
| --- | --- | ---: | --- |
| `attempt/result.json` | `DISPOSABLE_DRILL_PAYLOAD_COMPLETE` | 714 B | `df89564a1dfc52388a093e6a5b16ed1085b04b0d4c1cbd9fce262c88422b8170` |
| `attempt/resource-verification.json` | `PASS` | 2,801 B | `073061365ad226de3cd6906714b8940c0ccba4b209e19cf2fc2b87f5d278f5f0` |
| `attempt/terminal-envelope.json` | stable `Result=success` | 8,520 B | `eee89a523fb1d49694aaab5fee7943aa2844f3968cb119af2c0b9063c858e612` |
| `attempt/cleanup.json` | cleanup semantics replayed | 5,164 B | `2031b0b9a1d1ac4cceeaf4d4afacc58ef89fbc725f86b7b5a8c5fee66412a087` |
| `attempt/detached-replay.json` | `PASS` | 5,002 B | `624a543e7c0394b4f303c94963bb445313099c9d96bc0d34313095023491bc57` |

The resource verifier measured `12,914,688` bytes current memory and
`19,570,688` bytes peak memory. Swap use was zero, and every recorded memory
event was zero, including `oom`, `oom_kill` and `oom_group_kill`. Both
terminal snapshots retained the same InvocationID with
`Result=success`, `ExecMainCode=1` and `ExecMainStatus=0`. Cleanup found no
payload or keeper process, cgroup or unit. A separate read-only replay
reproduced the stored detached receipt exactly and returned `PASS`.

The drill lock was released. A post-release check found the unit `not-found`,
no forbidden output, and the lock available.

The runner now launches CPython from its continuously held, verified
executable FD while using the same pinned absolute path only as `argv[0]` for
CPython prefix initialization. The loader rechecks both inherited FDs, then
sets `sys.executable` and `_base_executable` to the current preflight
process's `/proc/<pid>/fd/<python_fd>` path. Direct child and grandchild
Python launches therefore remain backed by the verified FD while the pinned
process is alive. New receipts use schema
`noncert-cuts-ab16-gate-a-full-preflight-receipt-v3` and execution strategy
`same-fd-python-prefix-and-nested-executable-v2`, including a detached loader
identity that strict replay must match.

The fixed sibling's one full preflight subsequently ran under a newly
acquired shared lock after a fresh replay of HEAD, all `54` sources, the
manager epoch, the complete drill chain, the three old failure artifacts,
resources and absence of residual units or processes. Its immutable result
is:

| Evidence | Status | Size | SHA-256 |
| --- | --- | ---: | --- |
| `full-preflight-a001/receipt.json` | `PASS` | 3,532 B | `978b0c0297346b11372273d27f0132e97576f231f556c5148402861362fc1160` |
| `full-preflight-a001/stdout.log` | `19 passed` | 2,283 B | `d5026b145ab117c4725e9cf3ff3a9b1e5f93e7a222320adedf29db72c4a56749` |
| `full-preflight-a001/stderr.log` | empty | 0 B | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The receipt uses schema
`noncert-cuts-ab16-gate-a-full-preflight-receipt-v3` and strategy
`same-fd-python-prefix-and-nested-executable-v2`. It records
`exit_code=0`, `timed_out=false` and duration `113,605,206,168 ns`. The full
gate reports `5108 passed, 74 skipped` for pytest and `19 passed` overall.

External sampling observed a peak process-tree RSS of `13,507,510,272` bytes,
minimum `MemAvailable` of `22,188,326,912` bytes, unchanged minimum
`SwapFree` of `50,168,647,680` bytes and minimum filesystem availability of
`28,302,282,752` bytes. The post-run replay reproduced the same HEAD,
source-set digest, manager epoch and detached drill receipt. The shared lock
was released, and no residual unit exists.

Gate A was then finalized through the retained-FD pinned entrypoint after
another lock-held replay of the fixed HEAD, all `54` source identities, the
manager/boot epoch, the complete drill chain and the full-preflight receipt.
The immutable result is:

| Evidence | Decision | Size | SHA-256 |
| --- | --- | ---: | --- |
| `gate-a-receipt-a001.json` | `PASS` | 5,590 B | `91fbc5488749d9682db8c449923d9ddacd7f85933ce7fe6f7a1a47d1421e8473` |

The receipt uses schema
`noncert-cuts-ab16-bootstrap-gate-a-receipt-v2`, approval ID
`gate-a-ab16-20260724T081638Z-preflight-978b0c0297346b11372273d27f0132e97576f231f556c5148402861362fc1160`
and future run nonce
`run-20260724T081638Z-ab16-preflight-978b0c0297346b11372273d27f0132e97576f231f556c5148402861362fc1160`.
Its target campaign directory remains absent. Strict downstream replay
returned `PASS`; `offline_candidate_only=true`,
`formal_campaign_creation_authorized=false` and
`arm_launch_authorized=false`. Gate B, a formal campaign, a solver selection,
a suite/arm selection and every organic arm remain absent.

The previous sibling
`gate-a-terminal-reference-recovery-20260724T065556Z-C4n0n1` and its
`full-preflight-a001` remain immutable historical evidence and are not
authority ancestors for this recovery. Their exact failure record is in
`03_execution_record.md`. The current Gate-A receipt grants no solver,
formal-campaign or organic-arm authorization.

The byte-locked `control-a002/result.json` is provenance-only. A formal
campaign must rerun all Gate 1 v4 units and independently rebuild the cut-free
baseline before it may publish a baseline-admission receipt or an AB16
experiment manifest.

## Single campaign authority

The new formal run, if Gate A and Gate B are separately authorized and pass,
will be one no-overwrite v4 campaign root. Its immutable topology contains:

1. Gate 1 v4 synthetic success;
2. Gate 1 v4 synthetic post-SEAL failure;
3. Gate 1 v4 forced control;
4. Gate 1 v4 forced treatment;
5. a reserved prospective AB16 child containing the baseline admission,
   experiment manifest, suite selection, 16 per-arm selections and terminal
   classification.

Gate 1 success may issue a continuation authorization bound to that exact
campaign package, run nonce and manager/boot epoch. It does not close the run
and does not authorize an arm by itself. AB16 can proceed only in the reserved
child of the same campaign. An epoch change makes that campaign immutable
incomplete; a later run must repeat Gate 1 in full and may not splice old and
new evidence.

Every authority input is intended to be read, hashed and parsed or copied from
the same `O_NOFOLLOW` file descriptor with before/after `fstat` checks.
Authority outputs use exclusive creation and reject symlinked parents.
Package replay binds the strict inputs, tool bytes, repository HEAD, manager
epoch and resource contract before any launch selection can be consumed.

## Baseline admission

The old incumbent may be listed as strict provenance, but it is not an
authority ancestor. The new package-pinned builder must independently rebuild
the cut-free model from strict inputs and reproduce:

- model-proto digest;
- `37,760` variables;
- `95,136` constraints;
- stable selector name/index/domain mapping.

The old incumbent must then pass a cut-free fixed-assignment feasibility
replay against that rebuilt binary proto. Admission fails closed on any
identity, protobuf, cardinality, selector, assignment or feasibility drift.
Failure stops the new campaign before its first organic arm; it does not
permit changing the seed.

## Gate 1 positive-control meaning

The forced control and treatment first seal the same response, solution and
incumbent from an identical pre-injection model. Only afterward do separate
post-model clones run an empty control injection or the treatment's forced
provider and production attach chain.

Gate 1 passes only if:

```text
control:   APPLIED = 0
treatment: GENERATED > 0, COMPILED > 0, APPLIED > 0
```

An independent checker must rebuild at least one treatment inequality from
the frozen model, selector mapping, assignment, compiled cut and `APPLIED`
ledger event, and show that it is active with `lhs > rhs` at the pre-injection
incumbent. Resource, terminal, cleanup, epoch and detached replay must also
pass.

A future PASS of those gates would establish only `MECHANISM_CREDIBLE`: the
attach mechanism is reachable and a concrete injected inequality excludes
that frozen incumbent. It would not establish organic usefulness,
family-global soundness, SAT, UNSAT, a bound, a witness, or a proof claim.

## Prospective AB16 contract

After Gate 1 and baseline admission, the immutable manifest preregisters four
configurations:

| Configuration | Control | Treatment |
| --- | --- | --- |
| `region-capacity` | attach enabled, no cut families | only `region_capacity` |
| `shape-packing-hall` | attach enabled, no cut families | only `shape_packing_hall` |
| `power-hitting-set` | attach enabled, no cut families | only `power_hitting_set` |
| `bundle` | attach enabled, no cut families | all three named families |

Each configuration has two fresh-process, single-worker matched pairs:
`AB` runs control then treatment; `BA` runs treatment then control. This yields
16 serial arms. `pattern_nogood` is forbidden. Inputs, prestate, tool bytes,
seed, ordering, internal budget, resource limits, metrics, thresholds,
censoring and aggregation are fixed before any per-arm selection.

The activation classifier is credibility-first and mutually exclusive:

- `ORGANIC_NONACTIVATION`: `G=C=A=0` and the zero-event ledger replay passes;
- `NO_ORGANIC_APPLIED_CUT`: `G>0,C=0` or `C>0,A=0`, with the appropriate
  compiler/`APPLIED` absence join;
- `ORGANIC_APPLIED`: `A>0`, with every applied inequality joined one-to-one to
  generated, compiled, assignment and ledger evidence;
- any non-integer, impossible or non-monotone count is
  `CREDIBILITY_INCOMPLETE`.

Every otherwise credible branch also performs a cut-free replay of its
incumbent. A normal solver return of `UNKNOWN` after the preregistered internal
budget is `BUDGET_CENSORED_UNKNOWN`, a valid right-censored result. An outer
timeout, `RuntimeMaxSec`, OOM, kill, crash, limit drift, authority/replay gap,
arm mismatch or cross-run/epoch splice is `CREDIBILITY_INCOMPLETE`.

Each pair first records the primary delta in cut-free-replay incumbent
presence. A treatment-only incumbent is better, a control-only incumbent is a
regression, and only a primary tie delegates the decision to cumulative
deterministic time at the common terminal milestone. The raw secondary delta
for each of `AB` and `BA` is retained; their arithmetic mean is descriptive,
while the conservative two-pair band is the claim gate. For the bundle,
`D_r = bundle_benefit_r - sum(single_family_benefit_r)` uses that same
secondary deterministic-time definition and is reported separately for `AB`
and `BA`, plus a descriptive mean. It has no effect threshold and cannot
establish an interaction claim.

A per-arm selection is the consumption boundary. Drift before selection
creates no arm and consumes no slot. Any credibility failure after selection
consumes that arm, stops the entire suite immediately and forbids retrying or
running later arms.

## Manager and resource authority

The cuts campaign independently fixes:

```text
boot_id
+ DBus unique owner
+ manager PID/starttime
+ manager executable path/size/mode/SHA-256
+ manager Version/Features
```

The epoch is replayed at launch, pre-terminal, terminal, cleanup, pair gate and
detached replay. A unit `InvocationID` anchors only that unit and cannot replace
the campaign epoch.

Each real arm uses the two-stage supervisor/payload/keeper protocol. While the
keeper preserves the cgroup, an external observer records the payload status,
limits, memory/swap/events, process membership and cgroup state. It then
releases the keeper and records the same unit's terminal systemd state and
cleanup. The contract is:

```text
MemoryHigh=35G
MemoryMax=39G
MemorySwapMax=16G
OOMPolicy=continue
KillMode=control-group
SendSIGKILL=yes
RuntimeMaxSec=3600
```

Only the fixed read-only privileged attestor runs through `sudo -n`; it may
open and identify the DBus-resolved manager executable but may not write,
signal, manage units or run a solver. All other code runs as the ordinary
user.

## Two separate heavy-work gates

The following approvals are intentionally nonmergeable.

### Gate A — validation only

Before any formal campaign identity exists, report two separately budgeted
actions to the supervisory thread:

1. disposable live drill: about 1 CPU core, `2/4 GiB` memory plus `1 GiB` swap,
   at most `1 GiB` I/O, about 5–15 minutes;
2. pre-run full preflight: `pytest -n auto`, up to about 24 logical cores,
   `12–24 GiB` RAM, `2–6 GiB` I/O, about 5–20 minutes.

Both require the shared lock
`/tmp/zmd-pj-codex-heavy-validation.lock` and a fresh check that no S3 or other
thread is running heavy validation. The supervisory thread decides whether to
run immediately or wait from the roadmap, live resources, lock state and user
activity. A busy lock or resource drift pauses the work. Gate A may not create
the formal campaign identity.

The drill authority is created outside every formal campaign root. It binds
the same two-stage resource lifecycle, terminal schema and pinned source set
used by the formal path, but its distinct purpose and authorization fields
forbid a solver, an organic arm or a formal campaign. Its payload is inert and
only publishes the drill result consumed by that lifecycle.

The current sibling contains its canonical input authority, one completed
`drill-python-fd-a001` disposable authority/live chain and one exact-PASS
`full-preflight-a001` receipt. Gate A has been finalized by the separate
exact-PASS `gate-a-receipt-a001.json`, but that receipt remains
non-authorizing: it cannot create Gate B, a formal campaign, a solver
selection or an organic arm.

### Gate B — formal campaign

Gate A has passed and released its execution phase. The supervisory thread
may separately recheck HEAD, manager/boot epoch, memory, swap and disk and
decide whether to schedule Gate B under its own technical authority and
receipt boundary. A Gate-A receipt cannot authorize Gate B. The estimate for
new Gate 1, baseline admission and AB16 is one CPU core, the
`35/39 GiB + 16 GiB swap` contract, about `1–1.5 GiB` I/O, 3–6 hours typical
and about 16 hours hard maximum.

The formal phase must hold the shared validation lock and both existing
prod-scale locks. Its final full preflight is separately included in the Gate
B report and may not overlap S3. No formal identity, unit or arm is created
before this approval.

## Claim boundary

At the current status this work establishes the repaired same-FD execution
implementation, its focused local validation, a canonical byte-pinned input
set, and one non-authorizing disposable live chain whose resource, terminal,
cleanup and detached replay evidence passed, plus one exact-PASS full
preflight receipt and the separate exact-PASS Gate-A finalize receipt. Gate A
is finalized only for later independent Gate-B consideration; it does not
authorize Gate B or a formal run. The inert drill, preflight and Gate-A
receipt establish no cut activation or empirical cuts result. This work does
not alter a project upper or lower bound and does not establish a witness,
SAT, UNSAT, family-global cut soundness, proof-sidecar validity, PIC, B6,
Stage-B promotion or production `CERTIFIED` status.

If the future experiment completes, its strongest possible local claims are:

- `MECHANISM_CREDIBLE` from Gate 1;
- fixed-configuration activation and censored-terminal classifications;
- `SINGLE_PAIR_OBSERVED_DELTA` for one credible pair;
- a repeated single-family or bundle runtime-effect label only when both
  preregistered order-balanced pairs meet the consistency and conservative
  threshold rule.

Promotion still requires separate family-global soundness, proof-sidecar and
proof-ledger gates.

## Files

- `ab16_campaign_bootstrap_v1.py` and
  `ab16_campaign_bootstrap_v2.py`: Gate A/Gate B bootstrap generations over
  the complete v4 topology.
- `ab16_formal_loader_v1.py`: selected-FD loader for the exact materialized
  snapshot module and role identity.
- `ab16_formal_orchestrator_v1.py`: persistent formal-launch owner ordering
  and selected-supervisor result preservation.
- `ab16_formal_campaign_v1.py`: three-lock supervisor, guardian startup,
  selection, serial campaign and terminal closeout.
- `ab16_outer_guardian_v1.py`: independent lock guardian; canonical absolute
  socket identity with internal retained-dirfd AF_UNIX transport, peer
  credential join and exact cleanup.
- `disposable_drill_authority_v1.py` and
  `disposable_drill_authority_v2.py`: campaign-external, non-authorizing Gate A
  authority generations.
- `disposable_drill_payload_v1.py`: inert drill payload with a purpose distinct
  from every formal arithmetic or arm selection.
- `ab16_authority_v1.py`: prospective manifest, suite selection and authority
  replay inside the reserved v4 child.
- `baseline_rebuild_v1.py`: independent cut-free model rebuild.
- `cut_free_incumbent_replay_v1.py`: strict binary-proto fixed-assignment
  replay.
- `baseline_admission_v1.py`: no-overwrite baseline admission.
- `organic_arm_runner_v1.py`: fresh-process production-path arm runner.
- `organic_arm_replay_v1.py`: credibility-first activation, ledger,
  inequality/absence-join and cut-free incumbent replay.
- `systemd_unit_reference_v1.py`: persistent same-connection
  `RefUnit`/`UnrefUnit` helper with exact DBus-owner binding.
- `organic_resource_lifecycle_v1.py` and
  `organic_resource_lifecycle_v2.py`: two-stage payload/keeper lifecycle and
  terminal-reference-aware phase evidence.
- `organic_resource_verifier_v1.py` and
  `organic_resource_verifier_v2.py`: independent resource, terminal, reference
  and cleanup replay.
- `organic_unit_orchestrator_v1.py` and
  `organic_unit_orchestrator_v2.py`: same-FD systemd execution and
  ordinary-user unit orchestration.
- `ab16_terminal_gate_v1.py` and `ab16_terminal_gate_v2.py`: per-arm and
  terminal-suite fail-closed gates.
- `gate_a_pinned_entrypoint_v2.py`: same-FD, byte-pinned Gate A-only dispatcher
  with no formal, solver or organic-arm command.
- `gate_a_recovery_inputs_v1.py`: no-overwrite canonical producer for the two
  external path maps and their planned-source observation.
- `gate_a_validation_v2.py`: full-preflight receipt and non-authorizing Gate A
  closeout logic.
- `ab16_contract_v1.py`: pure classification, aggregation and consumption
  state contract.

The execution history and validation boundary are recorded separately in
`03_execution_record.md`.
