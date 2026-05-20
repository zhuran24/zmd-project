# IndustrialPlanner 70×70 Single-Base Delivery Viewer Bundle

This guide explains how to materialize a **static browser viewer bundle** from
the checked-in active single-base delivery release pointer.

There are now two closely related ways to use it:

- **promotion path:** `build_industrial_planner_single_base_delivery_release.py`
  writes one checked-in versioned viewer bundle under
  `data/examples/industrial_planner/viewers/<release_id>/`, refreshes the
  current-viewer pointer/index, and then materializes the stable
  `data/examples/industrial_planner/current_delivery/` landing/download page
  every time a release is promoted
- **ad hoc local path:** this viewer-builder script still materializes a local
  `.artifacts/...` bundle when you want a scratch preview without changing the
  checked-in current-viewer pointer

The viewer bundle stays intentionally narrow:

- **active contract only:** `valley4_protocol_core` (70×70)
- **future scope stays frozen:** other bases and the outer-deployment path are
  shown only as scope notes; they are not reactivated by this workflow
- **exact endgame stays honest:** the full-scale 70×70 exact `CERTIFIED`
  terminal artifact is still `open`

## Command

```bash
python scripts/build_industrial_planner_single_base_delivery_viewer.py \
  --pointer-json data/examples/industrial_planner/active_single_base_delivery_release.json \
  --output-dir .artifacts/industrial_planner_single_base_delivery_viewer
```

That command is the ad hoc local path. For checked-in promotion, run the
release builder instead and let it refresh:

- `data/examples/industrial_planner/viewers/<release_id>/`
- `data/examples/industrial_planner/active_single_base_delivery_viewer.json`
- `data/examples/industrial_planner/active_single_base_delivery_viewer.md`
- `data/examples/industrial_planner/viewers/viewer_index.json`
- `data/examples/industrial_planner/viewers/viewer_index.md`
- `data/examples/industrial_planner/current_delivery/index.html`
- `data/examples/industrial_planner/current_delivery/landing_manifest.json`

## What the builder does

1. resolve the checked-in `active_single_base_delivery_release.json` pointer
2. load the versioned release manifest for the current active release id
3. copy the static web viewer HTML into the output directory
4. copy the release's canonical source blueprint into
   `optimal_blueprint.json` and regenerate a legacy fallback render payload
5. prune `candidate_placements.json` down to only the poses actually selected by
   that canonical source blueprint, so the viewer bundle stays compact
6. regenerate `viewer_report.json` from the canonical source blueprint and
   the pruned facility-pool payload
7. copy release artifacts into grouped download folders
8. write `release_viewer_manifest.json`, which drives the current-release cards
   and grouped download links in the UI

## Output layout

The output directory contains:

- `index.html`
- `optimal_blueprint.json`
- `final_solution.json`
- `candidate_placements.json` (viewer-pruned)
- `viewer_report.json`
- `release_viewer_manifest.json`
- `downloads/release/*` — copied release payload artifacts grouped by stage
- `downloads/meta/*` — release manifest, checksums, pointer files, and index

## Local preview

Serve the output directory with any static file server. Example:

```bash
cd .artifacts/industrial_planner_single_base_delivery_viewer
python -m http.server 8070
```

Then open `http://localhost:8070`.

## UI contract

When `release_viewer_manifest.json` is present, the static viewer shows:

- the current release id, active base id, delivery status, and exact-status note
- the active-contract scope note that keeps other bases as `future_scope`
- grouped download links for delivery entrypoints, support reports, gate
  summaries, canonical provenance, and metadata files

When that manifest is absent, the viewer falls back to the older generic
blueprint-first behavior and hides the release/download sections.

## Stable current landing layer

If you want one fixed current entry path rather than a versioned viewer path,
run `scripts/build_industrial_planner_single_base_delivery_landing.py` (or let
release promotion do it for you). That landing layer copies the current viewer
bundle under `current_delivery/viewer/`, builds one stable ZIP alias plus
pointer sidecars under `current_delivery/downloads/`, and renders a top-level
`current_delivery/index.html` page that links to the viewer plus grouped
release/support/gate downloads.

## Important boundary

This viewer bundle is a **consumer-layer projection** of the checked-in current
single-base delivery release. It helps people inspect and download the active
release package, but it does **not** widen the support contract and it does
**not** claim that the full exact `CERTIFIED` 70×70 end-state is already
checked in.
