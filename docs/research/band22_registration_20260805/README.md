# band22 v2 witness → official binding/routing gates

**Status:** CURRENT research-only adapter contract

**Updated:** 2026-08-05

**Validation boundary:** this batch runs the v2 intake/structure rung only. Fixed-master and
binding/routing results require separate later rungs and must not be inferred from intake success.

## Current validated state

The 2026-08-05 local-time R2 intake run completed under the guarded ladder with verdict
`INTAKE_ACCEPTED`, exit code `0`, and no censoring. Its authoritative ladder receipt is:

```text
.artifacts/band22_registration_20260805/
  ladder-r2-intake-final-20260806T033117Z-6c70aec7/LADDER_RECEIPT.json
```

The run registered all 266 mandatory instances plus 23 poles, matched all 219 manufacturing
binding-domain expectations, and recorded the exact generic accounting `2 active + 12 __unused__`
inputs and 52 active outputs. The structure check found no violation and reported all 11 R2
candidate ports inside the hole as inactive telemetry. The live/canonical ghost indices were
respectively `0` and `225`; source hashes matched the current session pins and the side-effect audit
was clean. The ladder pin, driver provenance, adapter snapshot, and post-rung witness hash all equal
`2118debd1f4b9618eb1d672738a1949a5ca52167c16b38a27735f9c75f78ae41`.

Driver wall time was 41.91 seconds, wrapper wall time was 43.12 seconds, sampled `VmHWM` was
3961.3 MiB, and sampled swap peak was 0. The outer receipt records the acquired prod-scale lock,
`MemoryMax=24G`, and `MemorySwapMax=0`.

This receipt contains no fixed-master feasibility result and no binding/routing result: rung 2 and
rung 3 are explicitly unattempted, `master_feasibility_check` and gate timing are absent, and all
controller/binding/routing statuses are null.

This directory adapts one external `band22-witness/2` placement to the repository's official
candidate-pool identities, then admits it through a strictly serial three-rung ladder:

1. v2 intake, source-pin verification, pool registration, binding projection, route-schema audit,
   strict-hole structure check, and live/canonical ghost-index resolution;
2. the official master with every placement literal fixed to the witness, solved only for feasibility;
3. the official `LBBDController._run_exact_binding_and_routing` binding/routing gate.

The workflow is research-only. It does not construct a campaign, write a proposal marker, call
`supervisor_seal()`, invoke a publisher, or create a durable `CERTIFIED`. An in-memory controller
return named `CERTIFIED` is recorded only as a gate result.

## Claim boundary

The adapter registers the fixed placement and records what the witness says about active ports and
route components. It does not inject the witness's binding or route as an official fixed solution.
The controller independently searches its own binding domain and routing model.

Consequently, a successful rung 3 would establish only that the same fixed placement has some
officially accepted binding and route. It would not establish that those choices are byte-for-byte
identical to the witness-authored projection or route, and it would not certify throughput,
optimality, publication eligibility, or a production result.

## Inputs

### Primary: R2

The ladder default is the complete R2 delivery:

```text
.artifacts/band22_strict_redesign_replies_20260805/
  r2_strict_empty_v2/band22_strict_empty_v2_delivery/
  band22_strict_witness_v2.json
```

Its hole is derived from inclusive ranges, not trusted as independent metadata:
`x=[3,9]`, `y=[30,35]`, anchor `(3,30)`, width `7`, height `6`, area `42`, short side `6`.

### Backup: R1

R1 is an entire-witness fallback only:

```text
.artifacts/band22_strict_redesign_replies_20260805/
  r1_strict42/strict42_band22_v2_delivery/strict42_witness_v2.json
```

Its hole is `x=[32,38]`, `y=[64,69]`, anchor `(32,64)`, width `7`, height `6`.
Selecting R1 requires a fresh ladder and fresh receipts. A run never switches witnesses between
rungs, and no placement, port projection, pole set, or route component may be spliced between R1
and R2.

### Legacy compatibility

A top-level `witness_schema_version` is version-authoritative: only the exact value
`band22-witness/2` is accepted. An unknown version is rejected even if the object also contains a
legacy `solution` field, preventing downgrade dispatch. A versionless object with a `solution`
mapping follows the retained legacy path.

Legacy ingestion remains traceable historical compatibility. It does not acquire the v2 adapter's
active-terminal, route-component, or binding-projection evidence merely by passing the old shape.

## v2 adapter contract

`band22_v2_adapter.py` reads the witness as one immutable byte snapshot and decodes strict JSON:
duplicate keys and non-finite numbers are rejected. It independently snapshots and hashes the
official pool, mandatory-instance, rules, and generic-I/O artifacts. The actual hashes consumed by
the adapter must then equal the hashes recorded by the current `ExactSearchSession`; a witness's
own `source_hashes` object is provenance only and cannot authorize stale bytes.

The mandatory placement set is flattened from:

- 46 `facilities.boundary_ports` entries;
- one `facilities.protocol_core` object;
- 219 `facilities.manufacturing` entries.

Those 266 IDs must equal the 266 IDs in
`data/preprocessed/mandatory_exact_instances.json` exactly. `operation_type` always comes from that
artifact. Power poles are separately resolved by a unique official pole pose at the same anchor and
become `pose_optional::power_pole::<pose_id>` entries.

Every facility pose is resolved inside its own facility pool by the full tuple
`(facility_type, anchor_x, anchor_y, orientation, port_mode)`. `pose_id` is not a global key: its
string is reused across pools.

| witness family/mode | official `(orientation, port_mode)` |
|---|---|
| boundary / `bottom_boundary` | `(1, bottom_base)` |
| boundary / `left_boundary` | `(0, left_base)` |
| manufacturing / `north_to_south` | `(0, TB)` |
| manufacturing / `south_to_north` | `(0, BT)` |
| 6×4 manufacturing / `west_to_east` | `(1, LR)` |
| core / `inputs_east_west` | `(1, core_TB_out)` |

Zero or multiple matches are contract failures. The same rule applies to every pole-anchor lookup.

For each of the 219 manufacturing instances, the adapter compares the witness active-port multiset
with every entry returned by `enumerate_pose_level_port_bindings()` and requires exactly one match.
The receipt stores the selected normalized domain entry as an expectation for later comparison.
Generic-slot accounting is separate and exact: two input slots are assigned, twelve are
`__unused__`, and all 52 required generic-output slots are assigned. The nested facility ports and
the top-level `active_ports` carrier must agree as an exact duplicate-free multiset.

`route_components` are structural provenance only. Coordinates must be unique and in-grid; the only
accepted component kinds are `straight`, `turn`, `merger`, and `splitter`; direction sets and arity
must be well formed; cross or multi-input/multi-output crossing shapes are rejected. These records
are never presented as an official fixed route.

## f16 strict-hole semantics

The current authority is the strict-empty ruling recorded in `PROJECT_LOCK.md`: hole cells must
contain none of the following:

- a selected facility body, including a power pole;
- an active terminal/front;
- any route component, on ground or elevated layers.

The official routing path restores ghost cells into its occupied/free-grid exclusion through the
strict ghost provenance. Failure to recover that provenance fails closed; logistics may not pass
through the hole.

This does not make every physical port printed on a candidate pose active. `PROJECT_LOCK.md` §404
requires the opposite distinction: a binding may leave physical ports unused, so an inactive
candidate port inside the hole is not itself an occupant and cannot reject the placement. R2 has 11
such inactive candidate ports; they are a regression sample and are reported as telemetry. If any
one of those coordinates becomes an active terminal, the structure rung rejects it.

The pre-f16 claims that `ghost_pick` was routing-inert or that belts could cross the hole are
superseded and must not be used for current runs.

## Ghost dual-index contract

Two integer identities coexist and must never be aliased:

| field | meaning | consumer |
|---|---|---|
| `gate_ghost_domain_idx` | index in the built master's live, possibly anchor-filtered `_ghost_domains` | fixed-master pins and official gate solution marker |
| `canonical_unfiltered_ghost_idx` | identity in the complete unfiltered 70×70 anchor domain | receipt/provenance and terminal fixed-witness interfaces |

With the default singleton anchor filter, the live gate index is `0`. The canonical unfiltered
identity is `225` for R2 (`3 × 65 + 30`) and `2144` for R1 (`32 × 65 + 64`). Even when an unfiltered
build makes the numbers happen to coincide, consumers must select the field by contract rather than
by numeric equality.

## Serial ladder

`run_ladder.py` creates a fresh no-overwrite ladder root, pins one witness path and SHA-256 for the
whole invocation, and runs independent receipted rungs in order. Before each rung and after each
child result, it requires the current bytes, adapter snapshot, and driver provenance to match that
same pin.

| rung | driver selector | admission to next rung |
|---:|---|---|
| 1 | `--stop-after intake` | exact `INTAKE_ACCEPTED`, uncensored, exit 0 |
| 2 | `--stop-after master` | exact `MASTER_FEASIBLE`, uncensored, exit 0 |
| 3 | `--stop-after gates` | always terminal |

A censored result, infeasibility, contract violation, harness error, invalid audit, missing receipt,
or any other terminal verdict stops the ladder. There is no automatic retry, budget increase, R1
fallback, or next-rung execution after censoring.

Run only the intake rung:

```bash
.venv/bin/python docs/research/band22_registration_20260805/run_ladder.py \
  --tag r2-intake --max-rung 1
```

Run the complete ladder with explicit budgets:

```bash
.venv/bin/python docs/research/band22_registration_20260805/run_ladder.py \
  --tag r2-official-gates --max-rung 3 \
  --master-validation-seconds 600 \
  --binding-seconds 600 --routing-seconds 600 \
  --max-gate-wall-seconds 20400 --outer-seconds 21600
```

Every rung goes through `run_guarded.sh`. The wrapper takes a nonblocking repository-wide singleton
lock at `/run/user/$UID/zmd-pj-prod-scale-solve.lock`, records the holder identity in its outer
receipt, and fails closed on contention. Its default resource envelope remains `MemoryMax=24G` and
`MemorySwapMax=0`.

Direct driver invocations are diagnostic surfaces; a long or production-scale-shaped run must use
the guarded ladder or wrapper. All Python entry points use `.venv/bin/python`.

## Budgets and censoring

Binding and routing defaults are 600 seconds per solve. They are not a bound on the entire
alternative-enumeration loop, so the gate wall cap and the wrapper's outer runtime cap remain
separate explicit parameters.

The official binding/routing first-run cost for the current v2 fixed witness is not known. A prior
M5 run taking at least 33 hours belongs to a different layout and path: it is a risk warning, not an
estimate that can be transferred here. This workflow makes no promise that the current run will be
far shorter than 33 hours.

A fixed-master, binding, routing, alternative-cap, or driver-wall budget stop is
`UNKNOWN_CENSORED`: it proves neither feasibility nor infeasibility, and the ladder stops. An OOM or
outer `RuntimeMaxSec` kill that prevents the inner receipt is not a censored solver verdict; it means
no verdict exists for that rung.

## Receipts and output

Runtime output stays under `.artifacts/band22_registration_20260805/`. Each driver invocation creates
a unique run directory, writes a hashed result JSON, and atomically lands `<tag>.DONE` last. Together
the result and terminal receipt record:

- input schema, immutable witness identity, source identities, and route-schema audit in the result;
- the v2 binding projection and independent-controller boundary in both the result and `.DONE`;
- `gate_ghost_domain_idx` and `canonical_unfiltered_ghost_idx` as separate fields;
- completed/requested stage, verdict, censoring stage/budget, and controller return;
- fixed-master and gate summaries when those stages were actually run;
- wall time, sampled `VmHWM`, swap peak, and the side-effect audit result.

The ladder lands one `LADDER_RECEIPT.json` containing every rung's attempted state, verdict,
duration, `VmHWM`, censoring fields, continuation decision, and a terminal stop reason. A rung not
run is explicitly listed as unattempted.

The wrapper writes a separate no-overwrite outer receipt even if the inner process is killed. An
inner `.DONE` receipt is authoritative for a driver verdict; a convenience `.LATEST` pointer is not.

## Side-effect and authority boundaries

The driver snapshots `data/checkpoints`, `data/solutions`, and `data/blueprints` before and after the
run. Any change invalidates the verdict. `CutManager`, when rung 3 is reached, receives only a
run-local scratch directory. All temporary paths are redirected under the fresh run directory.

The driver rejects inherited `EXACT_*` variables before mutation and owns only the worker and
binding-alternative-cap controls it sets itself. It never calls the master search loop; rung 2 solves
only a copy of the official master with every relevant literal pinned.

## Superseded v1 evidence

Earlier smoke/full directories in `.artifacts/band22_registration_20260805/` used the legacy aligned
`.solution` input and pre-f16 interpretation. They remain historical evidence for those exact bytes,
but they do not establish R2 intake, fixed-master feasibility, binding feasibility, or routing
feasibility. Current v2 status must be read only from a v2 driver/ladder receipt.
