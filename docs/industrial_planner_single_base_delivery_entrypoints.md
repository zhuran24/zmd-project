# IndustrialPlanner single-base active entrypoints manifest

This guide covers the small checked-in aggregate manifest that summarizes the
**current active single-base consumer entry surface** for IndustrialPlanner.

It exists for script consumers that do not want to resolve several checked-in
pointer/manifests in sequence just to answer four simple questions:

1. what is the current active release?
2. what is the current active versioned viewer?
3. what is the stable current landing bundle?
4. what is the shortest top-level latest bundle ZIP alias?

It now also surfaces the latest checked-in consumer-surface audit summary and
the smaller `current_surface_health.{json,md,txt}` snapshot, so automation can
see whether the repo-front helper links and aggregate current entry layer are
still clean without separately opening the larger audit JSON.

The manifest stays intentionally narrow:

- active contract: `valley4_protocol_core` on the 70×70 base
- other bases: preserved as `future_scope`
- full-scale exact `CERTIFIED`: still honestly marked as `open`

## Default checked-in paths

- `data/examples/industrial_planner/active_single_base_delivery_entrypoints.json`
- `data/examples/industrial_planner/active_single_base_delivery_entrypoints.md`

The JSON file is the machine-readable source of truth for automation. The
Markdown file is the human-readable companion.

## One-command build

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

## What the builder validates

The build fails closed when any of these drift:

- release id / base id / lot size / delivery status across the aggregated current surfaces
- `exact_full_scale_certified.status` across release pointer, viewer pointer,
  landing manifest, frontdoor manifest, and latest-bundle pointer
- the frontdoor's current-delivery or latest-bundle links no longer match the
  landing/latest-bundle sources
- the surfaced consumer-surface audit summary no longer matches the active
  release/base/delivery/exact-status contract (when those summaries are
  provided and/or required)
- the surfaced compact `current_surface_health.{json,md,txt}` snapshot no
  longer matches the active contract, exact-status note, or frontdoor/audit
  linkage (when those snapshots are provided and/or required)
- any required current file is missing

So the output is not just a convenience summary. It is also a compact checked-in
consistency check over the active single-base consumption surface.

## Output layout

The JSON payload is organized into these top-level sections:

- `active_contract` — canonical release/base/status summary
- `exact_full_scale_certified` — honest solver-endgame status
- `actions` — the shortest stable paths most callers usually want first
- `current_entrypoints.release` — current release pointer + release artifacts
- `current_entrypoints.viewer` — current viewer pointer + versioned viewer bundle
- `current_entrypoints.landing` — stable current landing bundle + source current ZIP alias
- `current_entrypoints.latest_bundle` — top-level latest bundle ZIP alias + pointer sidecars
- `current_entrypoints.surface_alignment` — latest checked-in no-drift audit summary for the repo-front / aggregate-entrypoints surface (when present)
- `current_entrypoints.surface_health` — compact current-surface-health snapshot surfaced for zero-parse consumers (when present)
- `repo_frontdoor` — higher-level human-facing checked-in front door
- `surface_health` — top-level mirror of the current-surface-health snapshot
- `surface_summary` — compact counts for geometry/download surface sizing plus surface-health check/helper-link counts

## Release promotion integration

`build_industrial_planner_single_base_delivery_release.py` now refreshes this
aggregate manifest **after** it refreshes the repo-front current entry layer.
That means the default promotion chain is now:

1. versioned release bundle
2. versioned viewer bundle + current viewer pointer
3. stable `current_delivery/` landing bundle
4. repo-front `index.html` / `frontdoor_manifest.json`
5. aggregate `active_single_base_delivery_entrypoints.{json,md}`
6. surface-alignment audit summary refreshed back into both the aggregate manifest and the repo front door
7. compact `current_surface_health.{json,md,txt}` snapshot refreshed back into both the aggregate manifest and the repo front door

If the aggregate manifest refresh fails, the promotion fails closed and the
newly written repo-front/latest-alias outputs are rolled back with the rest of
that attempted promotion.
