# IndustrialPlanner Reference Notes

This directory records Phase-2 provenance notes for the IndustrialPlanner export
adapter.

## Observed upstream surfaces

- repository: `hsyhhssyy/IndustrialPlanner`
- observed branch during Phase 2 work: `v2`
- public sample blueprints live under `public/blueprints/`
- sample root shape observed during implementation:
  - `schema`
  - `id`
  - `version`
  - optional `blueprintVersion`
  - `name`
  - `createdAt`
  - `baseId`
  - `devices[]`

## Copy policy

The current repository does **not** vendor upstream IndustrialPlanner code.
Phase 2 only borrows format observations, device vocabulary, and public-sample
shape signals to build a one-way exporter.
