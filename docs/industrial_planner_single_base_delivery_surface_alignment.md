# IndustrialPlanner single-base delivery surface alignment audit

> **Boundary (2026-06-26):** This document describes the frozen IndustrialPlanner postprocess/adapter surface from the April 2026 delivery line, not the current P1.2 solver or authenticated release state. Here, “current” means current within that delivery surface. Nothing in this workflow may mint, infer, or publish proof-bearing `CERTIFIED`.

This audit is the lightweight no-drift guard for the checked-in active
single-base consumer surface.

It does **not** rebuild the release, viewer, landing page, or repo-front page.
Instead, it reads the already-checked-in current surface and checks that the
following pieces still agree:

1. `data/examples/industrial_planner/frontdoor_manifest.json`
2. `data/examples/industrial_planner/index.html`
3. `data/examples/industrial_planner/active_single_base_delivery_entrypoints.json`
4. `data/examples/industrial_planner/active_single_base_delivery_entrypoints.md`
5. `data/examples/industrial_planner/current_surface_health.json`
6. `data/examples/industrial_planner/current_surface_health.md`
7. `data/examples/industrial_planner/current_surface_health.txt`

The goal is simple: after promotion has already built the human-facing frontdoor
and the script-facing aggregate entrypoints manifest, this audit keeps them from
silently drifting apart later. It now also closes the visibility loop on the
surfaced audit-summary refs themselves, so the frontdoor/entrypoints layer
cannot advertise stale `surface_alignment_summary.{json,md,txt}` metadata or
counts without the audit tripping. It now also closes the same loop on the
smaller `current_surface_health.{json,md,txt}` snapshot after that snapshot is
re-surfaced into the checked-in frontdoor and aggregate entrypoints manifest.

## What it checks

The audit currently fail-closes on these categories:

- active contract identity stays aligned between the repo-front frontdoor and
  the aggregate entrypoints manifest (`release_id`, `base_id`, `lot_size`,
  `delivery_status`)
- `exact_full_scale_certified.status` stays aligned between those two surfaces
- repo-front helper-link references to
  `active_single_base_delivery_entrypoints.{json,md}` stay correct in
  `current_frontdoor`, `actions`, `script_entrypoints`, and `linked_assets`
- repo-front helper-link references to
  `surface_alignment_summary.{json,md,txt}` stay correct in `current_frontdoor`,
  `actions`, `surface_alignment`, `linked_assets`, and the visible HTML helper
  links / audit panel text
- repo-front helper-link references to
  `current_surface_health.{json,md,txt}` stay correct in `current_frontdoor`,
  `actions`, `surface_health`, `linked_assets`, and the visible HTML helper
  links / surface-health panel text
- the checked-in `index.html` helper-links block still visibly includes the
  aggregate entrypoint links plus the automation tip that tells script
  consumers to prefer the aggregate JSON
- the aggregate entrypoints manifest still points at the surfaced audit-summary
  JSON/Markdown/TXT trio in `actions`, `surface_alignment`,
  `current_entrypoints.surface_alignment`, and `surface_summary`
- the aggregate entrypoints manifest still points at the surfaced compact
  `current_surface_health.{json,md,txt}` trio in `actions`, `surface_health`,
  `current_entrypoints.surface_health`, and `surface_summary`
- the surfaced audit-summary metadata that frontdoor/entrypoints re-echo
  (`status`, check counts, helper-link counts, checked paths, contract identity)
  still matches the checked-in audit summary JSON itself
- the surfaced current-surface-health metadata that frontdoor/entrypoints
  re-echo (`status`, summary text, check counts, helper-link counts, contract
  identity, checked surfaces, source audit refs) still matches the checked-in
  `current_surface_health.json` snapshot itself
- `entrypoints.actions.*` and `entrypoints.repo_frontdoor.*` still point at the
  same checked-in frontdoor / landing / latest-bundle paths exposed by the
  frontdoor manifest
- the linked current-delivery manifest, current/latest bundle ZIPs, latest-bundle
  pointer JSON, viewer manifest, and primary browse/download targets still exist

This is intentionally narrower than the broader release/viewer/landing/frontdoor
builders. It only guards the final checked-in consumer surface.

## Default command

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

Exit codes:

- `0` — clean
- `1` — drift detected
- `2` — malformed/missing checked-in surface, so the audit could not run safely

## Outputs

- JSON summary — machine-readable check list and counts
- Markdown summary — readable CI / review artifact
- Console summary — plain-text verdict for logs

## Promotion-chain role

`build_industrial_planner_single_base_delivery_release.py` now runs this audit
by default in a converging loop around the surfaced consumer layer. In effect,
the checked-in chain is:

`release -> viewer -> landing -> frontdoor -> active entrypoints -> frontdoor refresh -> initial surface audit -> current surface health -> entrypoints refresh -> frontdoor refresh -> closing surface audit -> current surface health -> closing entrypoints refresh -> closing frontdoor refresh -> final surface audit`

That means future promotions fail closed unless the final checked-in frontdoor
surface, the aggregate entrypoints manifest, and the surfaced audit-summary refs
all converge on the same final summary.

## CI role

The dedicated GitHub workflow
`.github/workflows/industrial_planner_single_base_delivery_surfaces.yml`
runs this audit alongside the focused single-base delivery viewer/landing/
frontdoor/entrypoints/release regressions.

That gives the repo a cheap day-to-day guard against consumer-surface drift
without widening the active support surface beyond `valley4_protocol_core`
70×70.
