# IndustrialPlanner 70×70 Single-Base Repo Front Door

> **注（状态校准至 2026-07-11）**：本文（及同组 delivery-surface 文档）描述的是 IndustrialPlanner **postprocess / adapter 交付面**（release `r20260416` 冻结），不是 exact-solver 当前活动主线。现行求解与认证状态见 `PROJECT_LOCK.md`、`CLAUDE.md`、根 `README.md` 与 `docs/项目说明/06_current_status.md`；文中 “current / now” 只指该冻结交付面自身。

This guide explains the higher-level **repo-facing entry page** that now sits
one step above the stable `current_delivery/` landing bundle.

Its job is deliberately narrow:

- point users at one fixed `current_delivery/index.html` entry
- expose two explicit intent paths at the repo front: **browse first** and
  **download first**
- expose the current viewer/download links from a path closer to the top of the
  checked-in artifact tree
- make the download-first primary action one shorter top-level latest ZIP alias
  instead of forcing users to remember `current_delivery/downloads/`
- keep the active contract narrow: only `valley4_protocol_core` (70×70)
- keep the exact-status note honest: full-scale 70×70 `CERTIFIED` is still
  open

That means a downstream reviewer can enter through
`data/examples/industrial_planner/index.html` without first opening the current
viewer pointer, landing manifest, or versioned release directory manually. It
now also exposes both the aggregate `active_single_base_delivery_entrypoints.{json,md}`
pair and the latest `surface_alignment_summary.{json,md,txt}` outputs in the
hero helper links, so human-facing, script-facing, and audit-facing current
entry surfaces stay aligned at the repo front. It now also surfaces the compact
`current_surface_health.{json,md,txt}` snapshot directly in the helper links,
manifest payload, and visible status card, so small scripts/reviewers can read
a clean/drift verdict without parsing the larger audit summary first.

## Command

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

For the checked-in path, the delivery release builder now refreshes this
front-door layer automatically by default into:

- `data/examples/industrial_planner/index.html`
- `data/examples/industrial_planner/frontdoor_manifest.json`

## What the builder does

1. resolve the checked-in `current_delivery/landing_manifest.json`
2. fail-close unless that landing still targets a
   `ready_for_single_base_delivery` active line
3. fail-close unless the landing still exposes the browse-first/download-first
   actions needed by the higher-level page, including the stable current bundle
   ZIP alias and its pointer JSON
4. prefix the landing/viewer/download links so they work one directory higher
5. mirror the stable current-delivery ZIP into a shorter top-level latest alias plus JSON/Markdown pointer sidecars
6. optionally surface the aggregate `active_single_base_delivery_entrypoints.{json,md}` pair in helper links (or fail-close when `--require-entrypoints` is used)
7. optionally surface the checked-in `surface_alignment_summary.{json,md,txt}` trio (or fail-close when `--require-surface-alignment` is used)
8. optionally surface the checked-in `current_surface_health.{json,md,txt}` trio (or fail-close when `--require-surface-health` is used)
9. write `frontdoor_manifest.json`, now with explicit `entry_modes` metadata, latest-alias references, script-entrypoint links, current surface-audit summary fields, and compact current-surface-health fields when present
10. render one repo-facing `index.html` entry page with two clear user paths, a direct automation tip, a reviewer-facing surface-audit status card, and a smaller current-surface-health status card

## Output layout

The output directory contains:

- `index.html` — higher-level repo entry page
- `frontdoor_manifest.json` — machine-readable entry summary
- `industrial_planner_latest_single_base_delivery_bundle.zip` — shorter checked-in latest ZIP alias for the active single-base bundle
- `latest_single_base_delivery_bundle.json` / `latest_single_base_delivery_bundle.md` — pointer sidecars for that latest alias
- `active_single_base_delivery_entrypoints.json` / `active_single_base_delivery_entrypoints.md` — aggregate script-entry manifest pair surfaced in the frontdoor helper links when present
- `.artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json` /
  `.md` / `.txt` — optional current clean/drift audit summaries surfaced in the
  helper links and frontdoor manifest when present
- `current_surface_health.json` / `.md` / `.txt` — optional compact current-surface-health snapshot surfaced in the helper links, manifest payload, and visible status card when present
- `current_delivery/` — stable current landing bundle already maintained by the
  lower layer

## UI contract

The repo front door shows:

- the active release id, base id, lot size, and delivery status
- one explicit **Browse first** card that opens the viewer/current-delivery path
- one explicit **Download first** card whose primary action is
  `industrial_planner_latest_single_base_delivery_bundle.zip`, with the blueprint and key verification sidecars still available as secondary actions
- the same exact/open note carried by the current landing bundle
- quick downloads and grouped downloads forwarded from `current_delivery/`
- machine-readable `entry_modes.browse_first` / `entry_modes.download_first`
  metadata in `frontdoor_manifest.json`
- direct helper links to `active_single_base_delivery_entrypoints.{json,md}`,
  `surface_alignment_summary.{json,md,txt}`, and `current_surface_health.{json,md,txt}` when those checked-in artifacts are available
- a compact current-surface-health card that mirrors the checked-in clean/drift
  verdict, top-line counts, and summary text for zero-parse consumers

## Important boundary

This front-door layer is a **navigation convenience surface**. It does **not**
replace the versioned release bundle, it does **not** widen the active support
contract, it does **not** reactivate any `future_scope` base, and it does
**not** claim that the exact full-scale 70×70 `CERTIFIED` end-state is already
complete.
