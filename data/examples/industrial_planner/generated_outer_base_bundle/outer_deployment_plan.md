# IndustrialPlanner Outer Base Deployment Plan

- Plan version: `0.2.0`
- Planning status: `planned_outer_deployment`
- Base id: `wuling_protocol_core`
- Base lot size: 80
- Canonical contract size: 70×70
- Inner island origin: (5, 5)
- Inner island size: 70
- Moat thickness by edge: top=5, right=5, bottom=5, left=5
- Foundation bus edges: (none)
- Boundary demand: outputs 52, inputs 2
- Boundary assignments: 54
- Connector reservations: 52
- Witness reservations: 56
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

- bottom: 12
- left: 20
- right: 2
- top: 18

## Witness reservation summary by purpose

- boundary_input_admission: 2
- boundary_input_bus: 2
- boundary_output_bus: 52

## Export mapping summary by mode

- translated_boundary_assignment: 54
- translated_by_outer_plan: 219

## Diagnostics

- Exporter status: `not_run`
- Validator import-compatible: None
- Validator layout-healthy: None
- Throughput status: `(not_run)`
- Validation probes: 0

## Notes

- outer deployment plan is adapter-side only; it does not widen the canonical blueprint schema or the certified_exact evidence boundary
- selected deterministic centered inner-island origin (5, 5) inside a 80×80 base
- selected base exposes no foundation bus edges; pure-output witness reservations remain explicit on every true edge
