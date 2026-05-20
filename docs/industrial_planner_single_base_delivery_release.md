# IndustrialPlanner 70×70 Single-Base Delivery Release Guide

This guide closes the next step after the active single-base end-to-end runbook:
it turns one **delivery-ready** `valley4_protocol_core` 70×70 run into a
**versioned delivery release** with a fixed release id, a self-contained bundle,
checksums, a checked-in pointer to the current active release, a matching
checked-in static viewer bundle/current-viewer pointer for the same release id,
and one stable checked-in current landing/download directory plus a repo-front checked-in entry page. The landing layer materializes one stable current bundle ZIP alias, the repo-front layer mirrors it again under a shorter top-level latest alias for download-first consumers, and the final promotion step now writes one aggregate checked-in current-entrypoints manifest for script consumers plus a lightweight no-drift audit summary and a compact `current_surface_health.{json,md,txt}` snapshot that recheck/re-summarize the repo-front helper links against that aggregate script-entry surface.

That scope is deliberately narrower than the exact-solver endgame.

- **What this guide does:** package the active single-base IndustrialPlanner
  delivery result into a fixed release bundle that can be cited, reviewed,
  revalidated, and re-generated.
- **What this guide does not do:** claim that the full-scale 70×70 exact
  `CERTIFIED` terminal artifact is already present. That status remains an open
  item and stays explicitly marked as such inside the release manifest.

Like the runbook, this guide does **not** reactivate any other base. Everything
outside `valley4_protocol_core` 70×70 remains preserved as `future_scope`.

## One-command release build

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
  --frontdoor-output-dir data/examples/industrial_planner \
  --entrypoints-json data/examples/industrial_planner/active_single_base_delivery_entrypoints.json \
  --entrypoints-markdown data/examples/industrial_planner/active_single_base_delivery_entrypoints.md
```

That command does nine things in order:

1. reruns the active single-base e2e workflow into one clean source run dir
2. fail-closes unless that run lands at `ready_for_single_base_delivery`
3. copies the release payload into a versioned `releases/<release_id>/` bundle
4. refreshes the active-release pointer and the release index
5. materializes a versioned checked-in viewer bundle under
   `viewers/<release_id>/` and refreshes the active-viewer pointer/index
6. materializes one stable checked-in current landing/download directory under
   `current_delivery/`, with a copied viewer bundle under `current_delivery/viewer/`
   plus a stable ZIP alias and pointer sidecars under `current_delivery/downloads/`
7. materializes a repo-front checked-in `index.html` / `frontdoor_manifest.json`
   entry that points forward to `current_delivery/index.html`, mirrors the
   source ZIP under `industrial_planner_latest_single_base_delivery_bundle.zip`,
   and uses that shorter latest alias as the download-first primary action
8. materializes `active_single_base_delivery_entrypoints.json` / `.md`, one
   aggregate checked-in manifest that summarizes the current release pointer,
   current viewer, stable landing bundle, and top-level latest bundle alias in
   one place for script consumers
9. runs a lightweight no-drift audit over the checked-in repo-front frontdoor
   and aggregate active-entrypoints files, writing JSON/Markdown/plain-text
   summaries under `.artifacts/industrial_planner_single_base_delivery_surface_alignment/`
10. writes `current_surface_health.{json,md,txt}` from the converged audit, then re-surfaces both the detailed audit summary and the compact health snapshot back into the checked-in frontdoor/aggregate entrypoints layer before the final audit pass

If you already have a fresh delivery-ready run, omit `--refresh-run` and point
`--source-run-dir` at the existing run directory.

If you need the delivery release only and explicitly want to skip the checked-in
viewer refresh, pass `--skip-viewer-bundle`.

If you want to keep the checked-in versioned viewer refresh but intentionally
skip the stable current landing/download directory, pass `--skip-landing-bundle`.

If you want to keep the stable current landing but intentionally skip the
higher-level repo front door, pass `--skip-frontdoor`.

If you want to keep the repo-front entry but intentionally skip the aggregate
current-entrypoints manifest, pass `--skip-entrypoints`.

If you need to suppress the post-promotion no-drift audit, pass
`--skip-surface-alignment-audit`.

## Release outputs

A successful build writes seven layers of artifacts.

### 1. Versioned release bundle

Under `data/examples/industrial_planner/releases/<release_id>/` you get:

- `canonical/` — regenerated canonical source fixture plus planning reports
- `bundle/` — target blueprint, compatibility manifest, validator report,
  throughput report
- `support_suite/` — canonical matrix, deployment-path matrix, overview
- `checks/` — checked-in inventory/gate summaries
- `run_summary.*` — the source e2e handoff summary copied into the release
- `release_manifest.json` / `release_manifest.md` — release metadata and payload
  inventory
- `SHA256SUMS.txt` — checksum file for the payload and release manifest

### 2. Active-release pointer

These files give one stable “what is the current single-base delivery release?”
answer:

- `data/examples/industrial_planner/active_single_base_delivery_release.json`
- `data/examples/industrial_planner/active_single_base_delivery_release.md`

### 3. Release index

These files list every versioned release currently present under the release
root and mark which one is current:

- `data/examples/industrial_planner/releases/release_index.json`
- `data/examples/industrial_planner/releases/release_index.md`

### 4. Checked-in current viewer bundle + viewer pointer

These files let downstream consumers open the current release directly in the
static browser viewer without guessing paths:

- `data/examples/industrial_planner/viewers/<release_id>/` — versioned static
  viewer bundle for the promoted release id
- `data/examples/industrial_planner/active_single_base_delivery_viewer.json`
- `data/examples/industrial_planner/active_single_base_delivery_viewer.md`
- `data/examples/industrial_planner/viewers/viewer_index.json`
- `data/examples/industrial_planner/viewers/viewer_index.md`

### 5. Stable current landing/download directory

These files give one fixed consumer entry path that no longer requires the user
or downstream tool to follow the viewer pointer manually:

- `data/examples/industrial_planner/current_delivery/index.html` — stable
  landing/download page
- `data/examples/industrial_planner/current_delivery/landing_manifest.json` —
  machine-readable landing summary
- `data/examples/industrial_planner/current_delivery/viewer/` — copied current
  viewer bundle for the active release id
- `data/examples/industrial_planner/current_delivery/downloads/industrial_planner_current_single_base_delivery_bundle.zip` — stable one-file alias for the active current bundle
- `data/examples/industrial_planner/current_delivery/downloads/current_single_base_delivery_bundle.json` / `.md` — pointer sidecars for the ZIP alias

### 6. Repo-front current entry page + latest alias

These files give one even earlier checked-in entry point that forwards users to
`current_delivery/` without requiring them to inspect pointer files first, and
mirror the active bundle under a shorter script-friendly alias:

- `data/examples/industrial_planner/index.html` — higher-level repo entry page
- `data/examples/industrial_planner/frontdoor_manifest.json` — machine-readable
  repo-front summary
- `data/examples/industrial_planner/industrial_planner_latest_single_base_delivery_bundle.zip` — shorter top-level latest ZIP alias for the active single-base delivery bundle
- `data/examples/industrial_planner/latest_single_base_delivery_bundle.json` / `.md` — pointer sidecars for that latest alias

### 7. Aggregate active-entrypoints manifest

These files give scripts one stable machine/human-readable summary of the
current release/viewer/landing/latest-bundle surface:

- `data/examples/industrial_planner/active_single_base_delivery_entrypoints.json`
- `data/examples/industrial_planner/active_single_base_delivery_entrypoints.md`

## What the release builder checks before it will package anything

The source `run_summary.json` must already prove all of these:

- `overall_status = success`
- `deliverable_status = ready_for_single_base_delivery`
- `requested_base_id = active_contract_base_id = valley4_protocol_core`
- validator says `is_import_compatible = true`
- validator says `is_layout_healthy = true`
- throughput status is `proven_equivalent`
- checked-in support-suite inventory status is `clean`
- checked-artifact gate status is `clean`

So the release builder is not “best effort.” It is a **promotion** step from a
known-good single-base run to a fixed delivery bundle.

## What the release manifest is for

`release_manifest.json` is the machine-readable handoff artifact for this phase.
It records:

- the fixed release id
- the active base id and lot size
- the source run that the release was promoted from
- the delivery entrypoints reviewers actually care about
- every payload file, its role, and its SHA256
- the exact full-scale `CERTIFIED` status note, without pretending it is done
- the exact commands needed to rerun the source e2e flow and rebuild the
  release

`release_manifest.md` is the human-readable version of the same handoff.

The matching viewer-bundle metadata lives outside the release directory on
purpose: it is a consumer-layer projection of the release, not part of the core
delivery payload being checksum-tracked by `SHA256SUMS.txt`.

The stable `current_delivery/` landing layer sits one step further out for the
same reason: it is a fixed user-facing entry built from the current-viewer
pointer, not a checksum-tracked part of the versioned release payload. That
layer now also builds one stable ZIP alias so download-first users can pull the
current payload + metadata tree in one file without widening the underlying
release contract.

The repo-front `data/examples/industrial_planner/index.html` layer sits one step
further out again. It is still consumer-facing convenience metadata, not a
versioned release payload artifact. The same is true of the shorter top-level
latest bundle alias: it mirrors the checked-in current-delivery ZIP without
becoming a new checksum-tracked release payload.

The aggregate `active_single_base_delivery_entrypoints.{json,md}` files sit at
the same convenience layer: they are checked-in discovery metadata for script
consumers, not new versioned release payload artifacts.

## Honest status boundary

This release layer means the project now has a **versioned, fixed-reference,
reproducible single-base delivery bundle** for `valley4_protocol_core` 70×70.

It still does **not** mean:

- that other bases are active
- that outer-deployment is back in the default gate
- that the exact full-scale 70×70 `CERTIFIED` terminal artifact is already in
  the repo

Those boundaries are intentional and are repeated inside the release metadata so
reviewers do not confuse “delivery release is ready” with “exact endgame is
finished.”
