# Prospective non-certified cuts AB16 campaign

Document kind: research implementation contract

Cutoff date: 2026-08-02

Status: R12 self-contained producer chain implemented; experiment not yet run;
organic arms `0/16`

## Scope

This directory implements one research-only A/B experiment: test whether the
three non-certified cut families can improve solver runtime organically. It
does not authorize a cut, a witness, an upper or lower bound, production use,
certification, Stage-B promotion, attainability, optimality, SAT, or UNSAT.
Every claim-bearing authorization field remains `false`; project state remains
`U=(1188,18)` and `L=absent`.

Gate 1 v4 is a separate trust line. Its existing artifacts and tests are not
part of this slimdown and are neither reinterpreted nor promoted by AB16.

The 38 historical Gate-A roots (`a001` through `a038`) are no longer local.
They are archive-only history under:

```text
/mnt/wd_external/archives/zmd-codex-autonomy-20260801/
```

No current code or document may treat an archived root as a local execution
path or as authority for a new attempt. The tracked
`archive_locators_v1.json` records only the frozen SHA-256 and byte size of the
history-freeze manifest and legacy control-a002. The archived bytes are not
opened, copied, or required locally. Both package input roles use that one
non-authorizing locator, while the unchanged scientific input-set projection
continues to bind the two archived object identities.

## Self-contained producer order

A clean committed checkout plus the hash-pinned preregistered
`candidate_placements.json` contains every source needed to materialize a
fresh AB16 campaign. That 54,467,709-byte large artifact may be omitted from a
lightweight Git distribution, so it must first match its tracked
`data/external_artifacts.json` SHA-256/size contract. Both candidate creation
and bootstrap replay that fixed manifest entry and the actual ignored-file
bytes before publishing authority. Gate-A and Gate-B are retired and are not
candidate or bootstrap inputs. The executable order is:

1. publish the offline candidate, then bootstrap the campaign and its sealed
   package from repository-local inputs;
2. publish tracked-clean checkout provenance in the preregistered baseline
   directory;
3. run the cut-free baseline rebuild, fixed-assignment replay, and baseline
   admission v2 in that order;
4. derive the common prestate and all 16 attempt-free bindings with
   `materialize-pre-manifest`, then publish the manifest and suite selection;
5. after the separate retained Gate1 v4 qualification has published its valid
   continuation, prepare the next attempt, produce and bind its formal
   selection, run it, replay its arithmetic, and close it.

The baseline rebuild accepts the precreated baseline directory only when its
sole member is the canonical `campaign-provenance.json`. Common prestate and
bindings are derived from the preregistration, validated campaign root,
baseline identities, and fixed experiment contract; callers cannot supply
their record bodies. Existing equal bytes are replayed, while drift, extra
members, or partial conflicting materialization fails closed without
overwrite.

The runner publishes one `noncert-cuts-ab16-organic-arm-result-v1` record.
Resource lifecycle and arithmetic replay consume those same bytes, including
`controller_terminal`; there is no replay-only result artifact.

The regression sentinel is
`src/tests/test_noncert_cuts_ab16_self_contained_chain_v1.py`. It creates a
clean temporary checkout, imports only the manifest-verified preregistered
candidate as the checkout's still-ignored preregistration artifact, and drives
the real R12 producers through credible close. No AB16 candidate, bootstrap,
baseline, materialization, selection, runner-result, replay, or close record
body is fixture-authored. A one-variable deterministic CP-SAT computation
replaces the production-scale solve. To stay hermetic, deterministic manager
and resource observations enter the existing capture/adapter interfaces; the
real capture, runner, lifecycle, replay, and close code validates and writes
all resulting bytes. The test therefore proves producer/consumer joins, not a
fresh-process, single-process-lock, systemd, or cgroup qualification.

Gate1 remains a separate zero-touch trust line. The sentinel installs an
explicit test-only retained-continuation scaffold through Gate1's constructors
and exclusive writers so AB16 can exercise its continuation identity/path
join. It does not validate the detached Gate1 replay payload schemas and does
not claim to re-run Gate1's systemd qualification.

## Fixed scientific design

The scientific preregistration is immutable. It fixes four configurations:

| Configuration | Control | Treatment |
| --- | --- | --- |
| `region-capacity` | attach path enabled; no family | `region_capacity` only |
| `shape-packing-hall` | attach path enabled; no family | `shape_packing_hall` only |
| `power-hitting-set` | attach path enabled; no family | `power_hitting_set` only |
| `bundle` | attach path enabled; no family | all three families |

Each configuration has two fresh-process matched pairs and two arms per pair:
`AB` runs control then treatment; `BA` runs treatment then control. The exact
order is therefore 16 serial, single-worker arms. `pattern_nogood` is
forbidden. The fixed seed is `2026072301`; `RuntimeMaxSec` is `3600` seconds.
The scientific experiment-contract digest is:

```text
24b45e110952505e6ffa92d3ddfdf33874cc3cb4503397e993898e79174ded9e
```

The preregistration also fixes the baseline and binding inputs, metrics,
censoring rules, pair aggregation, classification contract, resource limits,
and evaluation thresholds. A code repair may not alter any of those values.

## Retry semantics

Each of the 16 fixed slots owns a stable slot root. Attempts are append-only
children named `attempt-0001`, `attempt-0002`, and so on, with no retry limit.
Every child and every receipt is created with no-overwrite semantics.

- A preparation or credibility failure closes that attempt as incomplete and
  leaves the same slot retryable.
- A repair may change the clean committed HEAD and execution-tool bytes.
- Each attempt records the actual HEAD and tool identities used for it.
- Each result binds both the immutable scientific preregistration digest and
  the hash of the actual input set used by that attempt.
- Earlier failed attempts remain available for audit and are never overwritten
  or relabeled as successful.
- The first credible terminal result closes the slot; only then may the next
  preregistered slot begin.

There is no campaign-wide immediate-stop record, permanent root freeze,
successor-root ceremony, or recursive read-only `chmod` ritual. Tamper evidence
comes from the immutable preregistration bytes, per-attempt exclusive
publication, and input/result hash joins.

## Credibility and evaluation

The activation classifier is mutually exclusive:

- `ORGANIC_NONACTIVATION`: `G=C=A=0` and zero-event replay passes;
- `NO_ORGANIC_APPLIED_CUT`: generation or compilation occurs but `A=0`, with
  the required absence joins;
- `ORGANIC_APPLIED`: `A>0` and every applied inequality joins to generated,
  compiled, assignment, and ledger evidence;
- malformed, inconsistent, or unverifiable evidence is
  `CREDIBILITY_INCOMPLETE` and is retryable after repair.

An otherwise credible solver `UNKNOWN` at the fixed internal budget is a valid
right-censored `BUDGET_CENSORED_UNKNOWN`. An outer timeout, OOM, kill, crash,
limit drift, input mismatch, or replay gap is credibility-incomplete.

Each matched pair first compares cut-free-replay incumbent presence. Only a
primary tie delegates to cumulative deterministic time at the common terminal
milestone. AB and BA secondary deltas are retained separately; their mean is
descriptive. The bundle interaction quantity is also descriptive and grants
no interaction or global-soundness claim.

## Resource containment and exclusivity

The retained per-arm cgroup limits are:

```text
MemoryHigh=35G
MemoryMax=39G
MemorySwapMax=16G
OOMPolicy=continue
KillMode=control-group
SendSIGKILL=yes
RuntimeMaxSec=3600
```

Only one production-scale solve may run at a time. A formal arm holds the
complete exclusive lock set for its orchestration:

```text
/tmp/zmd-pj-codex-heavy-validation.lock
/run/user/1000/zmd_pj_prod_scale_solver.lock
/run/user/1000/zmd-pj-prod-scale-solve.lock
```

The limits and locks prevent a repeat of the historical dual OOM event. They
do not defend against hostile same-UID processes and do not grant scientific
or production authority.

## Machine-checked boundary

The retained versioned schema cohort is declared and validated in
`ab16_schema_declaration_v1.py`. `PROJECT_LOCK.md` keeps only the project
boundary; it does not duplicate the schema matrix.

Use the pinned project interpreter for validation:

```bash
/home/zhuran24/zmd-pj/.venv-uvbolt-backup/bin/python \
  docs/research/noncert_cuts_ab16_20260724/ab16_schema_declaration_v1.py
/home/zhuran24/zmd-pj/.venv-uvbolt-backup/bin/python \
  scripts/preflight_gate.py --full
```

Running the 16 arms is intentionally outside R12.
