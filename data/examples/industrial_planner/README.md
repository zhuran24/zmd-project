# IndustrialPlanner 70×70 Single-Base Fixtures

This directory contains the checked-in IndustrialPlanner fixtures, reports, and
benchmark artifacts for the **current active contract**:
`valley4_protocol_core` on the 70×70 base.

The checked-in full-demand fixture still covers all 17 canonical recipe-capacity
requirements, but the active decision surface is now intentionally narrow:

- active checked-in audit / CI scope: `valley4_protocol_core` (70×70)
- preserved `future_scope` bases: the three 40×40 valley4 sub-bases,
  `wuling_tianwangping_aid` (50×50), and `wuling_protocol_core` (80×80)
- preserved `future_scope` outer-deployment path: kept in-repo, but frozen out
  of the default checked-artifact gate

To reduce noise, the three dormant 40×40 valley4 variants are now collapsed
into one grouped `future_scope` block in the active support reports instead of
showing up as three separate active-matrix rows.

## Start here

For the active checked-in consumer entry, open:

- `index.html` — repo-front page that now offers explicit browse-first and
  download-first paths into the stable current delivery bundle
- `active_single_base_delivery_entrypoints.json` /
  `active_single_base_delivery_entrypoints.md` — aggregate machine/human
  manifest pair that summarizes the current release pointer, current viewer,
  stable current landing bundle, top-level latest ZIP alias, and the latest
  checked-in consumer-surface audit summary in one place
- `.artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json` /
  `.md` / `.txt` — lightweight no-drift audit outputs for the checked-in
  repo-front + aggregate-entrypoints surface
- `industrial_planner_latest_single_base_delivery_bundle.zip` — shorter top-level latest ZIP alias for the active single-base release
- `latest_single_base_delivery_bundle.json` / `latest_single_base_delivery_bundle.md` — machine/human pointer sidecars for that top-level latest alias
- `current_delivery/index.html` — stable current landing/download page
- `current_delivery/downloads/industrial_planner_current_single_base_delivery_bundle.zip` — source current-delivery ZIP alias mirrored by the top-level latest bundle
- `README.md` — this file, for the checked-in artifact map and regeneration
  commands
- `docs/phase3b_exact_endgame_execution_plan.md` — detailed now-to-finish plan for the remaining solver-side exact endgame, including the future exact-close propagation back into this checked-in single-base consumer surface


## Active checked-in artifacts

### Full-demand single-base oracle

- `full_demand_recipe_capacity_canonical_blueprint.json` — deterministic
  canonical blueprint fixture for the active 70×70 full-demand contract.
- `full_demand_base_support_matrix.json` /
  `full_demand_base_support_matrix.md` — active single-base canonical support
  report. By default it audits only `valley4_protocol_core`; preserved dormant
  bases are recorded separately as grouped `future_scope` metadata.
- `full_demand_deployment_path_matrix.json` /
  `full_demand_deployment_path_matrix.md` — companion matrix that keeps the
  active 70×70 canonical view intact and records the dormant outer path as
  `future_scope` rather than surfacing it as an active transition.
- `full_demand_support_overview.json` /
  `full_demand_support_overview.md` — umbrella summary for the active
  single-base contract.
- `full_demand_support_suite_inventory.json` — active support-suite inventory.
  It now contains one checked report set only.
- `checked_artifact_family_inventory.json` — active repo-level family inventory.
  It now points only at the support-suite family.

### Validator / export fixtures

- `precision_export_canonical_blueprint.json` — canonical precision-export
  fixture.
- `precision_export_expected_resolution.json` — expected target resolution
  output for the precision fixture.
- `boundary_port_translation_fixture.json` — boundary-port translation fixture.
- `all_edge_boundary_witness_canonical_blueprint.json` — export / validator
  geometry fixture for all-edge boundary witness packing.

### Versioned single-base delivery release

- `active_single_base_delivery_release.json` /
  `active_single_base_delivery_release.md` — checked-in pointer to the current
  active `valley4_protocol_core` 70×70 delivery release.
- `releases/*` — versioned delivery bundles promoted from a delivery-ready
  single-base e2e run. Each release includes the canonical fixture, export
  bundle, fresh support reports, checked-in gate summaries, a release manifest,
  and `SHA256SUMS.txt`.
- `releases/release_index.json` / `releases/release_index.md` — machine/human
  release index for the versioned single-base delivery bundles.
- `active_single_base_delivery_viewer.json` /
  `active_single_base_delivery_viewer.md` — checked-in pointer to the current
  browser-consumable viewer bundle for the active single-base delivery release.
- `viewers/*` — versioned static viewer bundles keyed by release id.
- `viewers/viewer_index.json` / `viewers/viewer_index.md` — machine/human index
  for the versioned single-base viewer bundles.
- `current_delivery/*` — stable current landing/download bundle materialized
  from the current-viewer pointer, with a copied viewer bundle under
  `current_delivery/viewer/` and a one-file ZIP alias plus pointer sidecars
  under `current_delivery/downloads/`, so downstream users get one fixed entry
  path without guessing the active release id.
- `index.html` / `frontdoor_manifest.json` — repo-front current-entry layer that
  sits one step above `current_delivery/`, now with explicit browse-first and
  download-first entry modes. The download-first primary action points at the
  shorter top-level `industrial_planner_latest_single_base_delivery_bundle.zip`
  alias, while the source current-delivery ZIP remains available under
  `current_delivery/downloads/` for traceability. The hero helper links also
  point directly at `active_single_base_delivery_entrypoints.{json,md}` so the
  repo front lines up with the aggregate script-entry surface. The helper links
  and visible cards now also surface both the detailed `surface_alignment_summary.{json,md,txt}` trio and the smaller `current_surface_health.{json,md,txt}` snapshot.
- `active_single_base_delivery_entrypoints.json` /
  `active_single_base_delivery_entrypoints.md` — aggregate checked-in summary
  for script consumers that want one stable file describing the current
  release/viewer/landing/latest-bundle entry surface plus the latest
  consumer-surface audit status/counts.
- `.artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json` /
  `.md` / `.txt` — no-drift audit summaries for the checked-in repo-front /
  aggregate-entrypoints surface. The repo front door and aggregate manifest now
  surface this clean/drift status directly instead of leaving it only inside
  `.artifacts/`.
- `current_surface_health.json` / `.md` / `.txt` — compact checked-in health
  snapshot derived from the converged surface-alignment audit, meant for CI,
  reviewer tooling, and small scripts that only need the current clean/drift
  verdict plus top-line counts without parsing the full audit payload.
- `industrial_planner_latest_single_base_delivery_bundle.zip` /
  `latest_single_base_delivery_bundle.json` / `latest_single_base_delivery_bundle.md` —
  repo-front latest alias trio that mirrors the stable current-delivery bundle
  under a shorter checked-in path for script consumers.

### Validator benchmark

- `benchmark.full70x70.blueprint.json` — deterministic 70×70 benchmark input.
- `benchmark.full70x70.benchmark.json` — checked-in raw benchmark output.

## Preserved future-scope assets

These files stay in the repository for later reactivation, but they are not in
the active CI-critical path:

- `protocol_core_transition_support_suite/*` — older focused
  `valley4_protocol_core` + `wuling_protocol_core` support slice.
- `outer_base_bundle_inventory.json` — preserved inventory for the dormant
  outer-deployment bundle family.
- `generated_outer_base_bundle/*` — preserved translated outer-deployment
  artifacts.
- `generated_outer_base_bundle_valley4_protocol_core/*` — preserved identity
  outer-deployment artifacts.

## One-command active single-base end-to-end run

```bash
python scripts/run_industrial_planner_single_base_e2e.py \
  --run-dir .artifacts/industrial_planner_single_base_e2e
```

That workflow writes one self-contained working set with the regenerated
canonical fixture, IndustrialPlanner bundle, fresh support reports, checked-in
inventory/gate summaries, and a failure-classified `run_summary.{json,md,txt}`
operator handoff.

See `docs/industrial_planner_single_base_runbook.md` for the manual step order,
artifact-role interpretation, and delivery-readiness criteria.

## One-command versioned delivery release + current-viewer + current-landing + frontdoor + aggregate entrypoints build

```bash
python scripts/build_industrial_planner_single_base_delivery_release.py \
  --refresh-run \
  --source-run-dir .artifacts/industrial_planner_single_base_e2e \
  --release-root data/examples/industrial_planner/releases \
  --release-id valley4_protocol_core_70x70_r20260416 \
  --pointer-json data/examples/industrial_planner/active_single_base_delivery_release.json \
  --pointer-markdown data/examples/industrial_planner/active_single_base_delivery_release.md \
  --index-json data/examples/industrial_planner/releases/release_index.json \
  --index-markdown data/examples/industrial_planner/releases/release_index.md \
  --viewer-root data/examples/industrial_planner/viewers \
  --viewer-pointer-json data/examples/industrial_planner/active_single_base_delivery_viewer.json \
  --viewer-pointer-markdown data/examples/industrial_planner/active_single_base_delivery_viewer.md \
  --viewer-index-json data/examples/industrial_planner/viewers/viewer_index.json \
  --viewer-index-markdown data/examples/industrial_planner/viewers/viewer_index.md \
  --landing-output-dir data/examples/industrial_planner/current_delivery \
  --frontdoor-output-dir data/examples/industrial_planner
```

That command promotes a **delivery-ready** single-base e2e run into one fixed
release id with a self-contained payload, release manifest, checksum file,
checked-in current-release pointer, versioned checked-in viewer bundle,
checked-in current-viewer pointer/index, a stable checked-in current
landing/download directory under `current_delivery/`, a one-file current bundle
ZIP alias plus pointer sidecars under `current_delivery/downloads/`, a shorter
repo-front latest bundle alias trio in this directory root, and a repo-front
`index.html` / `frontdoor_manifest.json` entry in this directory, plus one
aggregate `active_single_base_delivery_entrypoints.{json,md}` summary for
script consumers. It
still keeps the honest boundary that the full-scale exact `CERTIFIED` end-state
remains open.

See `docs/industrial_planner_single_base_delivery_release.md` for the release
promotion contract and the distinction between a delivery release and the exact
solver endgame.

## One-command ad hoc active single-base delivery viewer bundle build

```bash
python scripts/build_industrial_planner_single_base_delivery_viewer.py \
  --pointer-json data/examples/industrial_planner/active_single_base_delivery_release.json \
  --output-dir .artifacts/industrial_planner_single_base_delivery_viewer
```

That command resolves the checked-in current-release pointer, copies the active
single-base delivery payload into a compact static browser bundle, prunes the
viewer-side `candidate_placements.json` down to the poses actually used by the
release's canonical source blueprint, and exposes grouped download
links for the release sidecars, support reports, gate summaries, and
checksums. It is useful for local preview work when you do **not** want to
refresh the checked-in current-viewer pointer.

Serve the output directory with any static file server such as:

```bash
cd .artifacts/industrial_planner_single_base_delivery_viewer
python -m http.server 8070
```

See `docs/industrial_planner_single_base_delivery_viewer.md` for the viewer
bundle layout, release/download metadata, and the active-contract/future-scope
boundary shown in the UI.

## One-command ad hoc current landing/download bundle build

```bash
python scripts/build_industrial_planner_single_base_delivery_landing.py \
  --viewer-pointer-json data/examples/industrial_planner/active_single_base_delivery_viewer.json \
  --output-dir .artifacts/industrial_planner_single_base_delivery_landing
```

That command resolves the checked-in current-viewer pointer, copies the current
viewer bundle under `viewer/`, and renders one stable landing page at
`index.html` with direct entry links, grouped downloads, and the honest
exact/open boundary note. It is useful when you want one fixed consumer entry
without repromoting a release.

Serve the output directory with any static file server such as:

```bash
cd .artifacts/industrial_planner_single_base_delivery_landing
python -m http.server 8071
```

See `docs/industrial_planner_single_base_delivery_landing.md` for the stable
landing layout and the current-viewer-pointer contract.


## One-command ad hoc repo-front current entry build

```bash
python scripts/build_industrial_planner_single_base_delivery_frontdoor.py \
  --landing-manifest-json data/examples/industrial_planner/current_delivery/landing_manifest.json \
  --output-dir data/examples/industrial_planner \
  --entrypoints-json data/examples/industrial_planner/active_single_base_delivery_entrypoints.json \
  --entrypoints-markdown data/examples/industrial_planner/active_single_base_delivery_entrypoints.md \
  --surface-alignment-json .artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json \
  --surface-alignment-markdown .artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.md \
  --surface-alignment-console .artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.txt \
  --surface-health-json data/examples/industrial_planner/current_surface_health.json \
  --surface-health-markdown data/examples/industrial_planner/current_surface_health.md \
  --surface-health-console data/examples/industrial_planner/current_surface_health.txt
```

That command resolves the checked-in stable `current_delivery/` landing bundle
and writes one higher-level `index.html` plus `frontdoor_manifest.json` in this
directory. The resulting frontdoor now separates a browse-first path from a
download-first path, so people near the top of the checked-in artifact tree can
choose whether they want to inspect the active layout or grab the current
delivery artifacts without repromoting a release. When the aggregate
entrypoints manifest, surface-alignment summaries, and compact
`current_surface_health.{json,md,txt}` snapshot are present, the frontdoor also
surfaces them directly in helper links and the current status cards.

See `docs/industrial_planner_single_base_delivery_frontdoor.md` for the repo-front
entry layout and the boundary between this page, `current_delivery/`, and the
versioned release/viewer layers.

## One-command ad hoc aggregate active-entrypoints build

```bash
python scripts/build_industrial_planner_single_base_delivery_entrypoints.py \
  --release-pointer-json data/examples/industrial_planner/active_single_base_delivery_release.json \
  --viewer-pointer-json data/examples/industrial_planner/active_single_base_delivery_viewer.json \
  --landing-manifest-json data/examples/industrial_planner/current_delivery/landing_manifest.json \
  --frontdoor-manifest-json data/examples/industrial_planner/frontdoor_manifest.json \
  --latest-bundle-pointer-json data/examples/industrial_planner/latest_single_base_delivery_bundle.json \
  --surface-alignment-json .artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json \
  --surface-alignment-markdown .artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.md \
  --surface-alignment-console .artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.txt \
  --surface-health-json data/examples/industrial_planner/current_surface_health.json \
  --surface-health-markdown data/examples/industrial_planner/current_surface_health.md \
  --surface-health-console data/examples/industrial_planner/current_surface_health.txt \
  --output-json data/examples/industrial_planner/active_single_base_delivery_entrypoints.json \
  --output-markdown data/examples/industrial_planner/active_single_base_delivery_entrypoints.md
```

That command resolves the already-checked-in current release/viewer/landing/frontdoor/latest-bundle
surface and writes one aggregate JSON/Markdown manifest pair. It is useful for
automation that wants one stable file describing the active single-base
consumer entry surface plus the latest clean/drift audit status and surfaced
compact health snapshot without repromoting a release.

See `docs/industrial_planner_single_base_delivery_entrypoints.md` for the
aggregate manifest schema, fail-closed checks, and promotion-chain role.

## One-command repo-front / aggregate-entrypoints no-drift audit

```bash
python scripts/audit_industrial_planner_single_base_delivery_surface_alignment.py \
  --current-surface-health-json data/examples/industrial_planner/current_surface_health.json \
  --current-surface-health-markdown data/examples/industrial_planner/current_surface_health.md \
  --current-surface-health-console data/examples/industrial_planner/current_surface_health.txt \
  --require-surface-health-visibility \
  --json-output .artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json \
  --markdown-output .artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.md \
  --console-output .artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.txt
```

That command does **not** repromote or rebuild anything. It only checks that the
already-checked-in repo-front `index.html` / `frontdoor_manifest.json` surface
still lines up with `active_single_base_delivery_entrypoints.{json,md}`, the
current single-base landing/latest-bundle pointers, and the surfaced
`current_surface_health.{json,md,txt}` snapshot.

See `docs/industrial_planner_single_base_delivery_surface_alignment.md` for the
check categories, output files, and CI role.

## Active regeneration / no-drift commands

```bash
python scripts/export_industrial_planner_bundle.py \
  data/examples/industrial_planner/precision_export_canonical_blueprint.json \
  --output-dir data/examples/industrial_planner/generated

python scripts/build_industrial_planner_full_demand_fixture.py \
  --report-json data/examples/industrial_planner/generated_full_demand_bundle/full_demand_fixture_plan_report.json \
  --report-markdown data/examples/industrial_planner/generated_full_demand_bundle/full_demand_fixture_plan_report.md

python scripts/audit_industrial_planner_full_demand_support_suite.py \
  --output-dir data/examples/industrial_planner

python scripts/audit_industrial_planner_full_demand_support_suite.py \
  --check

python scripts/audit_industrial_planner_full_demand_support_suite_inventory.py \
  --inventory data/examples/industrial_planner/full_demand_support_suite_inventory.json

python scripts/audit_industrial_planner_full_demand_support_suite_inventory.py \
  --inventory data/examples/industrial_planner/full_demand_support_suite_inventory.json \
  --check

python scripts/audit_industrial_planner_checked_artifact_suite.py \
  --family-inventory data/examples/industrial_planner/checked_artifact_family_inventory.json \
  --json-output .artifacts/industrial_planner_checked_artifacts/checked_artifact_suite_summary.json \
  --markdown-output .artifacts/industrial_planner_checked_artifacts/checked_artifact_suite_summary.md \
  --console-output .artifacts/industrial_planner_checked_artifacts/checked_artifact_suite_summary.txt

python scripts/audit_industrial_planner_full_demand_base_matrix.py \
  --json-output data/examples/industrial_planner/full_demand_base_support_matrix.json \
  --markdown-output data/examples/industrial_planner/full_demand_base_support_matrix.md

python scripts/audit_industrial_planner_full_demand_deployment_matrix.py \
  --json-output data/examples/industrial_planner/full_demand_deployment_path_matrix.json \
  --markdown-output data/examples/industrial_planner/full_demand_deployment_path_matrix.md
```

Run the validator benchmark with:

```bash
python scripts/benchmark_industrial_planner_validator.py \
  data/examples/industrial_planner/benchmark.full70x70.blueprint.json \
  --warmup 2 \
  --iterations 7 \
  --json-output data/examples/industrial_planner/benchmark.full70x70.benchmark.json \
  --markdown-output docs/benchmarks/industrial_planner_validator_70x70.md
```

## Dormant future-scope commands

These commands remain useful for manual future work, but they are intentionally
outside the active gate right now:

```bash
python scripts/audit_industrial_planner_full_demand_support_suite.py \
  --base-id valley4_protocol_core \
  --base-id wuling_protocol_core \
  --output-dir data/examples/industrial_planner/protocol_core_transition_support_suite

python scripts/audit_industrial_planner_outer_base_bundle.py \
  --output-dir data/examples/industrial_planner/generated_outer_base_bundle

python scripts/audit_industrial_planner_outer_base_bundle.py \
  --base-id valley4_protocol_core \
  --output-dir data/examples/industrial_planner/generated_outer_base_bundle_valley4_protocol_core

python scripts/audit_industrial_planner_outer_base_bundle_suite.py \
  --inventory data/examples/industrial_planner/outer_base_bundle_inventory.json
```

## Fixture hygiene note

Canonical fixtures in this directory should use canonical commodity ids unless a
specific test is intentionally exercising adapter-side upstream passthrough or
invalid-id handling. Adapter-side export artifacts remain additive and must not
replace canonical truth.
