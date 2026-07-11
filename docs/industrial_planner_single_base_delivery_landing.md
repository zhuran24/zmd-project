# IndustrialPlanner 70×70 Single-Base Current Landing / Download Bundle

> **注（状态校准至 2026-07-11）**：本文属 IndustrialPlanner **postprocess / adapter 交付面**（release `r20260416` 冻结），不是 exact-solver 当前活动主线。现行求解与认证状态见 `PROJECT_LOCK.md`、`CLAUDE.md`、根 `README.md` 与 `docs/项目说明/06_current_status.md`；“current” 只指该冻结交付面自身。

This guide explains the stable **current entry layer** that now sits on top of
`active_single_base_delivery_viewer.json`.

Its job is simple:

- take the checked-in current-viewer pointer
- copy the current viewer bundle under one stable `viewer/` subdirectory
- build one stable ZIP alias plus pointer sidecars under `downloads/`
- render one fixed `index.html` landing/download page
- keep the active contract narrow: only `valley4_protocol_core` (70×70)

That means downstream users no longer need to guess the active release id or
manually follow the current-viewer pointer before they can open the viewer or
pull the delivery sidecars. A separate repo-front page can now sit one level
higher and point forward to this stable landing.

## Command

```bash
python scripts/build_industrial_planner_single_base_delivery_landing.py \
  --viewer-pointer-json data/examples/industrial_planner/active_single_base_delivery_viewer.json \
  --output-dir .artifacts/industrial_planner_single_base_delivery_landing
```

For the checked-in path, the release builder now refreshes this automatically
by default into:

- `data/examples/industrial_planner/current_delivery/index.html`
- `data/examples/industrial_planner/current_delivery/landing_manifest.json`
- `data/examples/industrial_planner/current_delivery/viewer/`
- `data/examples/industrial_planner/current_delivery/downloads/industrial_planner_current_single_base_delivery_bundle.zip`
- `data/examples/industrial_planner/current_delivery/downloads/current_single_base_delivery_bundle.json`
- `data/examples/industrial_planner/current_delivery/downloads/current_single_base_delivery_bundle.md`

## What the builder does

1. resolve the checked-in `active_single_base_delivery_viewer.json` pointer
2. fail-close unless that pointer still targets a
   `ready_for_single_base_delivery` current viewer
3. copy the current versioned viewer bundle into `viewer/`
4. prefix the viewer-manifest download links so they work from the stable
   landing directory
5. build one stable ZIP alias from `viewer/downloads/release/` +
   `viewer/downloads/meta/`, then write current-bundle pointer sidecars under
   `downloads/`
6. write `landing_manifest.json`
7. render one direct `index.html` landing/download page
8. keep repo-local paths repo-relative inside `landing_manifest.json` so the
   checked-in landing metadata stays portable across build machines
9. swap the finished directory into place so an already-existing current
   landing is not left half-updated if the rebuild fails

## Output layout

The output directory contains:

- `index.html` — stable landing/download page
- `landing_manifest.json` — machine-readable landing summary
- `viewer/` — copied current viewer bundle, including:
  - `viewer/index.html`
  - `viewer/release_viewer_manifest.json`
  - `viewer/downloads/release/*`
  - `viewer/downloads/meta/*`
- `downloads/industrial_planner_current_single_base_delivery_bundle.zip` — one-file current bundle ZIP alias for download-first consumers
- `downloads/current_single_base_delivery_bundle.json` / `.md` — machine/human pointers for the ZIP alias

## Local preview

Serve the output directory with any static file server. Example:

```bash
cd .artifacts/industrial_planner_single_base_delivery_landing
python -m http.server 8071
```

Then open `http://localhost:8071`.

## UI contract

The landing page shows:

- the active release id, base id, lot size, and delivery status
- the stable exact/open note for the full-scale 70×70 exact `CERTIFIED` status
- quick downloads for the main delivery artifacts
- grouped download sections for delivery entrypoints, support reports, gate
  summaries, canonical provenance, and metadata
- one direct “Download current bundle ZIP” entry that points at
  `downloads/industrial_planner_current_single_base_delivery_bundle.zip`
- a direct “Open interactive viewer” entry that points at `viewer/index.html`
- repo-relative source pointer paths in the landing manifest so downstream
  tooling can reuse the checked-in metadata without inheriting build-machine
  absolute paths

## Important boundary

This landing layer is a **consumer convenience surface** built from the current
viewer pointer. It does **not** widen the active support contract, it does
**not** reactivate other bases, and it does **not** claim that the exact
full-scale 70×70 `CERTIFIED` terminal artifact has already been checked in.

The optional repo-front `data/examples/industrial_planner/index.html` page is a
separate outer layer that simply forwards users into this stable landing.
