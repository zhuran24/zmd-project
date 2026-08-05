# band22 witness → official gate ingestion driver (2026-08-05)

`registration_driver.py` takes an externally produced 291-facility layout — the
band22 witness, already registered onto official candidate-pool poses by the
alignment probe — validates it against the project's own master model, and then
runs it through the **binding** and **routing** certification gates. It answers
one question and only one:

> Does the official certified-path machinery accept this fixed layout as a
> master-feasible, bindable, routable placement?

It is **research-only**. It cannot produce `CANDIDATE_PROPOSED` and it cannot
produce a durable `CERTIFIED`. See "Legality" below.

---

## What it runs

Three stages, in order, each fail-closed. A stage that does not pass stops the
run; the next stage is never fed an unvalidated input.

| # | stage | code |
|---|---|---|
| 1 | structural validation | `validate_layout_structure` in this driver |
| 2 | master feasibility | `src/models/master_model.py` `MasterPlacementModel` — a copy of the official model with every placement literal pinned to the witness, solved for feasibility |
| 3 | binding + routing gates | `src/models/binding_subproblem.py` `PortBindingModel`; `src/models/routing_subproblem.py` `RoutingSubproblem` (its `solve()` runs `_validate_selected_route_connectivity` as a whole-layout re-verification after CP-SAT FEASIBLE) |

**Stage 1 — structural validation.** Every mandatory instance of
`master.source_instances` must be present exactly once and no unknown instance
id may appear; the outer key must equal `entry.instance_id`; facility and
operation types must agree with the instance (mandatory) or with
`POSE_LEVEL_OPTIONAL_OPERATIONS` (pose-level optional); every `pose_idx` must
dereference to a pool pose whose `pose_id` and `anchor` equal the witness's;
bodies must be inside the grid and pairwise disjoint; the ghost rectangle must
contain no facility body.

**Stage 2 — master feasibility.** The gates read a layout; they never check
that the layout satisfies the master's own hard constraints — power coverage,
optional caps, placement rules, the ghost-body exclusion
(`master_model.py:4914-4917`). So the witness is *pinned into the official
master model*: each mandatory group's slot `(x, y, mode)` triple, the C1
per-pose power-pole booleans (`_create_c1_power_pole_pose_vars` — under the C1
representation the delegate has no power_pole slot specs at all), every other
pose-level optional slot (required first, then residual, with unused residual
slots forced inactive) and the ghost anchor variable.

The pins are applied to a **copy** of the official model proto as domain
restrictions, with the objective and any stored hints cleared, and that copy is
solved for feasibility with a fresh `CpSolver`. Three consequences, all
deliberate: the live master object the gates later read is untouched; the
master's optimization path plays no part in a feasibility question; and a pin
whose value lies outside the variable's own domain is caught and reported as
`PIN_OUTSIDE_VARIABLE_DOMAIN` rather than being written in — writing it would
*widen* the domain and hide the very violation being looked for. Slot ordering
mirrors `CoordinateExactMasterDelegate.apply_solution_hint` (poses sorted by
`_pose_sort_key`, the order the slot symmetry-breaking `order_key` monotonicity
expects). After a FEASIBLE/OPTIMAL solve every pinned variable is read back and
must equal its pin; any divergence means the pinning is not binding what it
claims to bind, and the run stops.

Anything other than OPTIMAL/FEASIBLE ends the run before the gates. Passing
`--skip-master-validation` is allowed for diagnostics but then every verdict is
forced to `UNKNOWN_LAYOUT_NOT_MASTER_VALIDATED`.

**Stage 3 — the gates.** Both are driven through the *official* orchestrator
method `LBBDController._run_exact_binding_and_routing(iteration, solution,
diagnostic_flow_status)`, not a re-implementation. That method is the entire
path from a placement solution to a gate verdict: binding model construction
from the frozen snapshots, binding solve, `extract_port_specs()`, routing-grid
construction, routing precheck, routing solve, connectivity re-verification,
binding-alternative enumeration on routing INFEASIBLE, and the
`last_proof_summary` bookkeeping. Calling it verbatim is the point — hand-wiring
those steps would mean the gate verdict was about bytes the harness authored
rather than bytes the verified chain produced.

The master **search** is never run: `max_iterations=1`, the layout is given, and
the only master solve is the pinned feasibility check of stage 2.

This is the fixed-layout sibling of
`docs/research/p1_3_m5_convergence_20260708/m5_cell_runner.py`: same
session→master→`LBBDController` construction, same clean-room env discipline,
but `run_with_status()` (which searches) is replaced by validation + a single
gate call.

---

## Verdict discipline: the controller is the authority

`_run_exact_binding_and_routing` has many paths where the inner
`binding_status` / `routing_status` pair looks conclusive but the official
return value is still `UNKNOWN`:

- both gates FEASIBLE, but power-pole dominance normalization fails →
  `RUN_STATUS_UNKNOWN` (`benders_loop.py:7766-7786`);
- binding INFEASIBLE, but the whole-layout nogood was refused because the
  independent infeasibility re-verifier did not confirm →
  `RUN_STATUS_UNKNOWN` (`benders_loop.py:6784-6791`);
- routing exhausted, same refusal → `RUN_STATUS_UNKNOWN`
  (`benders_loop.py:7990-7997`).

So the driver classifies from the returned controller status first:

| requirement | rule |
|---|---|
| any conclusion | master feasibility confirmed, no harness exception, no `subproblem_status_contract_violation` |
| positive (`BOTH_GATES_FEASIBLE`) | controller returned `CERTIFIED` **and** returned a non-empty solution **and** binding/routing both FEASIBLE |
| negative (`BINDING_INFEASIBLE`, `ROUTING_REJECTED_ALL_BINDINGS`) | controller returned `master_cut_added_continue` **and** `independent_infeasibility_reverifier.confirmed is true` |
| official `UNKNOWN` | always reported as an `UNKNOWN_*` verdict, whatever the inner statuses say |

`src/tests/test_band22_registration_driver_verdict_v1.py` pins this, including
the three counterexamples that the earlier status-only classifier got wrong
(UNKNOWN + FEASIBLE/FEASIBLE, UNKNOWN + INFEASIBLE, UNKNOWN + EXHAUSTED/
ALL_INFEASIBLE).

Censoring is bookkeeping, not failure, but only a real budget stop counts as
censoring: `binding_subproblem.py:1412-1416` collapses every non-FEASIBLE,
non-INFEASIBLE CP-SAT status (including `MODEL_INVALID`) into the string
`"TIMEOUT"`, so the driver reads the raw `solver_status` back out. A `TIMEOUT`
whose raw status is not `UNKNOWN` is reported as
`UNKNOWN_STATUS_CONTRACT_VIOLATION`, not as a censored budget hit.

### Verdicts

| verdict | meaning |
|---|---|
| `BOTH_GATES_FEASIBLE` | master-feasible layout, controller returned CERTIFIED with a solution, binding FEASIBLE **and** routing FEASIBLE including the whole-layout connectivity re-check. A gate result, not a certification |
| `BINDING_INFEASIBLE` | binding rejected the layout and the independent re-verifier confirmed it |
| `ROUTING_REJECTED_ALL_BINDINGS` | binding alternatives exhausted, routing rejected all of them, independent re-verifier confirmed |
| `UNKNOWN_CENSORED` | a budget/cap/wall-clock guard fired — **nothing is proved in either direction** |
| `UNKNOWN_LAYOUT_NOT_MASTER_VALIDATED` | stage 2 was skipped or did not confirm |
| `UNKNOWN_STATUS_CONTRACT_VIOLATION` | a subproblem reported a status its contract does not allow |
| `UNKNOWN_LOOP_WANTED_A_NEW_LAYOUT` / `UNKNOWN_OTHER` | inconclusive; read `proof_summary` |
| `HARNESS_ERROR` | the driver or the gate call raised; `harness_exception` has type and message; exit code 1 |
| `INVALIDATED_SIDE_EFFECT_AUDIT` | the run touched the proof-output tree; the pre-audit verdict is preserved under `verdict_before_audit` but must not be used |

---

## Input

Default `--solution`:
`.artifacts/w0_fixrerun_20260804/band22_alignment/registration_placement_solution.json`

291 entries of the shape `{instance_id, facility_type, operation_type, pose_idx,
pose_id, anchor}` — 266 mandatory instances plus 25 `pose_optional::power_pole::…`
poles. `pose_idx` indexes `data/preprocessed/candidate_placements.json`
(`facility_pools[<type>]`, list order; the frozen 54,467,709-byte artifact). A
witness carrying its own `ghost_pick` is rejected: the driver computes it.

### ghost_pick

The band22 hole is 6×7 at anchor (1, 51) — cells x∈[1,6], y∈[51,57] — per
`.artifacts/w0_fixrerun_20260804/band22_alignment/max_empty_rect_for_this_placement.json`.

Its `pose_idx` is **computed, never hand-written**, by importing
`_expected_unfiltered_ghost_anchor_index` from
`src/search/pr2_l0_fixed_witness_core.py` (the same function the terminal
witness verifier checks against). For 70×70 / 6×7 / (1,51) that yields
`1 * (70-7+1) + 51 = 115`.

`ghost_pick` is inert for both gates by construction — `_extract_occupied_cells`
and `_extract_occupied_owner_by_cell` skip it, `PortBindingModel` records it as
an ignored non-facility placement marker, and the power-pole normalization
special-cases it. That is precisely why the ghost predicate has to be checked
somewhere else, and it is: structurally in stage 1 and as a master constraint in
stage 2.

**Semantics note.** The certified ghost predicate is *no facility body* inside
the rectangle; belts are not bodies. The routing gate's free-cell domain is the
grid minus facility bodies, so routed belts may legitimately cross the ghost
(the alignment probe measured 22 such cells for this witness). The driver does
not add a ghost exclusion to routing — doing so would make the harness
*stricter than the live chain*, which is its own class of bug.

---

## Running it

Short/diagnostic runs can be started directly:

```bash
env -u PYTHONPATH -u PYTHONHOME /home/zhuran24/zmd-pj/.venv-uvbolt-backup/bin/python \
  docs/research/band22_registration_20260805/registration_driver.py \
  --tag smoke --binding-seconds 20 --routing-seconds 10 \
  --binding-alt-cap 3 --max-gate-wall-seconds 300
```

Anything long goes through the cgroup wrapper (next section). The driver
refuses to start if **any** `EXACT_*` variable is inherited — run it under
`env -u …` or the wrapper.

### Options that matter

| flag | default | meaning |
|---|---|---|
| `--binding-seconds` | 600 | CP-SAT limit **per binding solve** |
| `--routing-seconds` | 600 | CP-SAT limit **per routing solve** |
| `--master-validation-seconds` | 600 | CP-SAT limit for the pinned master feasibility solve |
| `--skip-master-validation` | off | diagnostic only; forces `UNKNOWN_LAYOUT_NOT_MASTER_VALIDATED` |
| `--binding-alt-cap` | 0 (off) | `EXACT_B1_BINDING_ALT_CAP`; caps the binding-alternative enumeration loop |
| `--max-gate-wall-seconds` | 0 (off) | best-effort in-process SIGALRM guard around the gate stage |
| `--workers` | 1 | `EXACT_CP_SAT_WORKERS` |
| `--ghost-anchor-filter` / `--no-ghost-anchor-filter` | on | build the master ghost domain for the one witness anchor only |
| `--memory-sample-interval` | 0.5 | seconds between memory samples (clamped ≤ 1.0) |

**Why a wall-clock guard exists, and why it is not the envelope.** The per-solve
budgets do not bound the gate stage: when routing rejects a binding the loop
adds a nogood and asks binding for another one, and that cycle is unbounded.
`--binding-alt-cap` and `--max-gate-wall-seconds` bound it, and both are
bookkept as *censored*, never as a verdict. But a Python `SIGALRM` cannot
interrupt a native CP-SAT call and its exception can be swallowed by a broad
`except Exception` in official code, so it is a convenience, not a boundary. The
boundary is the cgroup.

**Why the ghost anchor filter is on by default.** The full domain for a 6×7 rect
is 65×64 = 4160 anchors, and building it costs real time and RAM. The layout
under test fixes the ghost anchor anyway (stage 2 constrains the ghost variable
to the witness anchor), so narrowing the domain to that same anchor cannot
change this layout's satisfiability — it only saves build cost. The choice is
recorded as `ghost.anchor_filter_applied`. It is not a certified-search
configuration and must not be reused as one; the driver never sets
`EXACT_MASTER_GHOST_ANCHOR_FILTER`.

### Resource envelope (`run_guarded.sh`)

The memory sampler observes; it does not limit. The M5/C1 lesson was that a soft
cap does not stop an OOM and a coarse sampler reports a 60 GB spike as "gentle"
(`docs/research/p1_3_m5_convergence_20260708/notes_phase1.md:120`,
`m5_c1_memory_attribution_20260710.md:129`). So a real run goes through the
wrapper, which puts the whole process tree in a transient systemd scope:

```bash
docs/research/band22_registration_20260805/run_guarded.sh \
  --tag full --outer-seconds 21600 --memory-max 24G -- \
  --binding-seconds 600 --routing-seconds 600 \
  --master-validation-seconds 1800 --max-gate-wall-seconds 20400
```

It sets `MemoryMax`, `MemorySwapMax=0` and `RuntimeMaxSec`, unsets every
inherited `EXACT_*`, refuses to start unless the inner
`--max-gate-wall-seconds` is at least 600 s below `--outer-seconds` (so the
driver still has time to write its result, fsync it and land its receipt), and
writes its own `*.OUTER_RECEIPT.json` afterwards. If the inner process was
OOM-killed or hit `RuntimeMaxSec` it never wrote a receipt of its own, and the
outer receipt records `state: FAILED_*` — which is the only correct reading of
"no verdict exists for this run".

---

## Output

Every run creates a **fresh unique directory**
`.artifacts/band22_registration_20260805/<tag>-<utc>-<uuid8>/`. Nothing
pre-existing is ever overwritten or unlinked. `--out-dir` must resolve to
`.artifacts/band22_registration_20260805` or a subdirectory of it, and `--tag`
must be a strict leaf name (`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`) — both are
enforced, so no argument can steer a write or a delete into `data/checkpoints`
or `data/solutions`. `TMPDIR`/`TEMP`/`TMP` and `tempfile.tempdir` are
re-pointed into the run directory as well, so no library temp file (CutManager's
`benders_cuts.jsonl` included) can land outside it.

| file | content |
|---|---|
| `<tag>_result.json` | the full record (atomic: temp file + fsync + `os.replace` + dir fsync) |
| `<tag>_stages.json` | stage timeline only |
| `<tag>_memory.jsonl` | one line per memory sample: `VmRSS` / `VmHWM` / `VmSwap` / `VmPeak` in kB |
| `<tag>_proof_summary_full.json` | the controller's `last_proof_summary`, untruncated |
| `<tag>.DONE` | terminal receipt (JSON), written last |
| `scratch/` | the `CutManager` checkpoint dir for this run |
| `scratch_tmp/` | this run's `TMPDIR` |

`<tag>.LATEST` in the parent directory points at the newest run directory for
that tag; the run directory itself is the authority.

The **receipt** is the completion protocol. It is written atomically after the
verdict, the side-effect audit and the exit code are all decided, and carries:
`run_uuid`, `exit_code`, `verdict`, `censored`, `controller_return_status`,
binding/routing statuses, `master_feasibility_confirmed`,
`side_effect_audit_clean`, `harness_exception`, `result_path`,
`result_sha256`, `vm_hwm_mb`, `vm_swap_peak_mb`, `total_wall_seconds`. Absence
of a receipt means the run died without a verdict — check the outer receipt.

`<tag>_result.json` carries, among others:

- `provenance` — `run_uuid`, full `argv`, driver path + SHA-256, witness path +
  SHA-256, interpreter, OR-Tools version, platform, git HEAD and dirty state.
  (The certified source digest in `exact_campaign.py:300` covers root `*.py`,
  `src/` and `scripts/` only; this driver lives under `docs/research/`, so
  `provenance.driver_sha256` is the binding record for it.)
- `env_audit` — inherited `EXACT_*` (always empty; a non-empty set aborts before
  anything is modified) and how the official allowlists classify the two owned
  knobs
- `verdict` — `{verdict, censored, censored_stage, censored_at_seconds, reason}`
- `layout_structure_check`, `master_feasibility_check`
- `gate_results` — binding/routing statuses plus the **raw** CP-SAT statuses,
  `enumerated_bindings`, `routing_attempts`,
  `independent_infeasibility_reverifier`, `subproblem_status_contract_violation`
- `proof_summary` — the controller's `last_proof_summary`, depth/length coerced.
  Truncation is explicit: a truncated list becomes
  `{"__truncated__": "max_list", "original_length": N, "kept": 200, "items": […]}`.
  The untruncated dump is `<tag>_proof_summary_full.json`
- `memory` — sidecar path, sample interval, `vm_hwm_mb`, `vm_swap_peak_mb`,
  and `observation_only: true`
- `side_effect_audit`, `session_build_seconds`, `master_build_seconds`,
  `gate_wall_seconds`, `total_wall_seconds`, `exit_code`
- `artifact_hashes` — the frozen-artifact snapshot the session was built from

### Exit codes

`0` verdict computed and the audit is clean · `1` harness error, gate exception
or a dirty side-effect audit · `2` usage/containment/env refusal (nothing was
run and no run directory holds a partial answer).

---

## Legality

- No campaign object is constructed and no campaign API is called: no `save()`,
  no `mark_campaign_stopped()`, no `supervisor_seal()`, no publisher, and no
  proposal marker — so neither `CANDIDATE_PROPOSED` nor a durable `CERTIFIED`
  can be produced. (`ExactCampaign` *is* pulled in transitively by importing
  `benders_loop`; the claim is that no mutation or mint API on it is on this
  code path, not that the name never enters the process.)
- When both gates pass, `_run_exact_binding_and_routing` *returns* the in-memory
  string `"CERTIFIED"`. The driver records it verbatim as
  `controller_return_status` next to `research_only_disclaimer`, which states
  plainly that it is a function return value and not a certification. Do not
  quote that field without the disclaimer.
- `CutManager` is given `scratch/` inside the run directory; `data/checkpoints`
  is never passed to it and cannot be reached by argument.
- `side_effect_audit` snapshots the recursive entry list and mtimes of
  `data/checkpoints`, `data/solutions` and `data/blueprints` **before anything
  is created** and again **after every artifact has landed**, so both stale-file
  deletion and late writes are inside the audited window. A dirty audit
  overrides the verdict (`INVALIDATED_SIDE_EFFECT_AUDIT`) and the exit code.
- Env: the certified *operational* allowlist is an allowlist for production
  entry points, not a research-output whitelist — several allowlisted knobs
  (`EXACT_BINDING_DUMP_STATE`, `EXACT_SUBPROBLEM_REPEAT_LOG_DIR`, …) make
  official code write telemetry outside this driver's audited tree. So the
  driver keeps its own narrow contract: it owns exactly `EXACT_CP_SAT_WORKERS`
  and `EXACT_B1_BINDING_ALT_CAP`, sets them itself, and **fails closed on any
  inherited `EXACT_*` variable before modifying anything**.

---

## Operational hardening

1. **Invisible progress.** `PYTHONUNBUFFERED=1` is re-asserted in-process, every
   stage line is flushed, and the controller's heartbeat callback is wired to
   the same printer — so binding build, binding solve, routing precheck, routing
   build and routing solve all stream live as `gate.<stage>:<event>`.
2. **"Is it dead or thinking?"** The terminal receipt (`<tag>.DONE`) is the
   completion signal, and it is written only after the verdict, audit and exit
   code are fixed. If the process dies first there is no receipt — and the
   wrapper's outer receipt says why.
3. **Memory.** A daemon thread samples `/proc/self/status` at ≤ 1 s, tracking
   `VmHWM` and `VmSwap` peaks. That is observation; the limit is the cgroup in
   `run_guarded.sh`.

---

## Smoke test (binding + routing-precheck only)

The pipeline was exercised with deliberately tiny budgets and a binding-
alternative cap of 3. This is a **binding/precheck smoke**: the cap stopped
enumeration while every candidate binding was still being rejected by the
routing *precheck*, so `routing_attempts` was 0, `routing_summary` was null, and
CP-SAT routing, the connectivity guard and the whole-layout re-verification were
never entered. It proves the wiring up to that point, nothing more.

```bash
env -u PYTHONPATH -u PYTHONHOME /home/zhuran24/zmd-pj/.venv-uvbolt-backup/bin/python \
  docs/research/band22_registration_20260805/registration_driver.py \
  --tag smoke2 --binding-seconds 20 --routing-seconds 10 \
  --binding-alt-cap 3 --max-gate-wall-seconds 300 \
  --master-validation-seconds 900
```

Result:
`.artifacts/band22_registration_20260805/smoke6-20260805T142200Z-aab86cdc/`
(ortools 9.15.6755, HEAD `4960bcd`).

    verdict            UNKNOWN_CENSORED (binding_alternative_enumeration @ cap 3)
    exit code          0
    structural check   ok — 266/266 mandatory, 25 optional poles, 3644 body
                       cells, 0 problems, ghost 42 cells body-free
    master feasibility OPTIMAL in 1.14s, 6104 pinned variables
                       (incl. 4761 C1 power-pole booleans), 0 pin divergences
    binding_status     ALT_CAP_REACHED (raw CP-SAT status OPTIMAL)
    routing_status     PRECHECK_FRONT_BLOCKED, routing_attempts 0
    ghost pose_idx     115 (filtered domain rect_idx 0)
    side_effect_audit  clean
    timings            session 30.0s, master build 9.5s, master validation
                       1.1s, gates 0.19s, total 41.2s
    VmHWM              4.35 GB, VmSwap 0

The master feasibility result is worth stating on its own: the band22 witness
**is** a feasible master placement — power coverage, optional caps, placement
rules and the 6×7 ghost-body exclusion at (1,51) all hold with every placement
literal pinned. That is a fact about the layout, not a gate verdict.

The verdict is censored by design — the cap was set to 3 so the smoke would
finish quickly — and it says **nothing** about whether the layout is bindable or
routable.

One observation the smoke surfaced, worth carrying into the real run but not a
conclusion: all three enumerated bindings (3 in ~0.16 s) were rejected by the routing precheck
with `status: front_blocked`, and the blockers were the witness's own power
poles sitting on the front cell of a port the binding gate had activated (e.g.
`refinery_steel_016` port (53,61) direction N, blocked by
`pose_optional::power_pole::p_x53_y61_o0_m_omni`). The alignment probe had
already counted 11 such pole-on-front collisions but classified them as
*inactive* ports, which official semantics permit. Whether these become live
front-blocks under every binding, or whether some untried binding avoids them,
is exactly what an uncapped run has to answer.

A run that actually exercises routing (`routing_attempts >= 1`, a non-empty
`routing_summary`, routing build/solve and connectivity-guard telemetry) has not
been produced yet.

### Real run

Uncapped binding alternatives, full budgets, cgroup-bounded, detached:

```bash
setsid nohup docs/research/band22_registration_20260805/run_guarded.sh \
  --tag full --outer-seconds 21600 --memory-max 24G -- \
  --binding-seconds 600 --routing-seconds 600 \
  --master-validation-seconds 1800 --max-gate-wall-seconds 20400 \
  > .artifacts/band22_registration_20260805/full.outer.driver.log 2>&1 &
```

The binding-alternative loop has no natural bound. In the smoke it turned over
about 20 rejected bindings per second, all rejected at the precheck before
CP-SAT routing ever ran; once a binding survives the precheck, each routing
solve can cost up to `--routing-seconds` instead. Whatever budget the run hits,
the result is `UNKNOWN_CENSORED` with the stage and budget recorded — never a
rejection.
