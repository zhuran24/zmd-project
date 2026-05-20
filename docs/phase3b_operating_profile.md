# Phase 3B Operating Profile

This document records the current Phase 3B operating profile lock. It is an
operations contract only: it does not claim full-scale exact close, and it does
not change release, viewer, frontdoor, or surface-health exact status.

## Default Profiles

The default production profile is `prod_4x4_normal`:

- `parallel_processes = 4`
- `EXACT_CP_SAT_WORKERS = 4`
- `process_priority = normal`
- `frontier_probe_mode = auto`
- runner: `scripts/run_prod_4x4_normal.ps1`

The default diagnostic profile is `diagnostic_1x1_normal`:

- `parallel_processes = 1`
- `EXACT_CP_SAT_WORKERS = 1`
- `process_priority = normal`
- `frontier_probe_mode = auto`
- runner: `scripts/run_prod_1x1_normal.ps1`

The B5A anchor sprint runner is a diagnostic workspace entrypoint, not the
production profile. Its coordinate-validation pre-master precheck is guarded
off by default:

- `CoordinateValidationPrecheckMaxAnchors = 0`
- `CoordinateValidationPrecheckSeconds = 2.0`
- env: `EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS`
- env: `EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS`

Enable it only for explicit B5A/B2 diagnostic reruns in a workspace copy, for
example with `-CoordinateValidationPrecheckMaxAnchors 8`. A triggered
coordinate-validation precheck is telemetry and triage evidence for the next
B2 decision; it does not promote release/viewer/frontdoor exact status and it
does not replace terminal campaign proof.

The B5A runner also exposes the ghost-aware warm-start coordinate-validation
budget separately from the pose-order validation budget:

- `GhostAwareCoordinateValidationMaxAnchors = 8`
- `GhostAwareCoordinateValidationSeconds = 10.0`
- env: `EXACT_GHOST_AWARE_COORDINATE_VALIDATION_MAX_ANCHORS`
- env: `EXACT_GHOST_AWARE_COORDINATE_VALIDATION_SECONDS`

This budget only affects diagnostic rejection/acceptance of forced warm-start
anchors. It is not proof-source evidence and must be read with the terminal
campaign state and telemetry.

Phase 3B also has an explicit diagnostic-only family lookup encoding switch:

- env: `EXACT_POWER_FAMILY_LOOKUP_ENCODING`
- default: `table`
- diagnostic alternative: `linear_shell_guards`

The default production profile continues to use `table`. The
`linear_shell_guards` encoding is an exact-equivalent diagnostic formulation for
the power-pole shell lookup table, introduced to reduce CP-SAT table expansion
during blocker triage. It must be enabled only in workspace diagnostics until a
fresh production-acceptance benchmark and equivalence evidence justify any
profile change. It does not change B6/B7 release, viewer, frontdoor, or
surface-health status.

Phase 3B also has an explicit diagnostic-only power-pole shell distance
encoding switch:

- env: `EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING`
- default: `element`
- diagnostic alternative: `linear_minmax`

The default production profile continues to use `element`. The `linear_minmax`
encoding is an exact-equivalent diagnostic formulation for the current
single-rectangle power-pole shell-distance calculation: it replaces the two
`AddElement` lookup constraints for `dx` and `dy` with min-equality constraints
over the distance to the rectangle edges. It must stay behind an explicit
diagnostic/profile switch until production-acceptance evidence justifies any
default profile change. It does not change B6/B7 release, viewer, frontdoor, or
surface-health status.

`prod_4x4_high` is an explicit experiment profile only. It is not the default
production profile.

## Profile Change Gate

Any change to the default production profile must be justified by a fresh
production-acceptance benchmark on the same artifact set:

```bash
python temp_scripts/benchmark_parallelism.py --suite-kind production-acceptance --suite-output .codex_test_logs/phase3b/production_acceptance_after_change.json
```

The benchmark result must be read together with campaign telemetry, especially
candidate throughput, UNKNOWN/UNPROVEN density, precheck elimination counts, and
lookahead elimination counts.

## Workspace Policy

Run tuning, diagnostic campaigns, and long campaigns in workspace copies. The
repo main proof paths should only receive final frozen evidence. If the exact
hash truth sources change, the previous campaign is comparison material only and
must not be treated as a continuous proof chain.

## Report Builder

The current lock can be regenerated with:

```bash
python scripts/build_phase3b_operating_profile.py
```

The default report paths are:

- `.artifacts/phase3b_operating_profile/operating_profile.json`
- `.artifacts/phase3b_operating_profile/operating_profile.md`
