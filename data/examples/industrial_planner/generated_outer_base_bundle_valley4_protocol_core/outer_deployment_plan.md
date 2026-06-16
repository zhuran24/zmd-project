# IndustrialPlanner Outer Base Deployment Plan

- Plan version: `0.2.0`
- Planning status: `planned_outer_deployment`
- Base id: `valley4_protocol_core`
- Base lot size: 70
- Canonical contract size: 70×70
- Inner island origin: (0, 0)
- Inner island size: 70
- Moat thickness by edge: top=0, right=0, bottom=0, left=0
- Foundation bus edges: left, top
- Boundary demand: outputs 52, inputs 2
- Boundary assignments: 54
- Connector reservations: 0
- Witness reservations: 54
- Export mappings: 273

## Boundary demand summary

- Output commodity counts: blue_iron_ore=34, source_ore=18
- Input commodity counts: qiaoyu_capsule=1, valley_battery=1

## Boundary assignment summary by edge

- bottom: total=12, outputs=12, inputs=0
- left: total=20, outputs=20, inputs=0
- right: total=2, outputs=2, inputs=0
- top: total=20, outputs=18, inputs=2

## Connector reservation summary by edge


## Witness reservation summary by purpose

- boundary_input_admission: 2
- boundary_output_bus: 52

## Export mapping summary by mode

- identity: 273

## Diagnostics

- Exporter status: `not_run`
- Validator import-compatible: None
- Validator layout-healthy: None
- Throughput status: `(not_run)`
- Validation probes: 0

## Notes

- outer deployment plan is adapter-side only; it does not widen the canonical blueprint schema or the certified_exact evidence boundary
- selected the degenerate zero-offset inner-island origin because the base already matches the canonical 70×70 contract
- selected base inherits foundation bus edges at left, top
