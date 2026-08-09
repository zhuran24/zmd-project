# IndustrialPlanner Full-Demand Deployment Path Matrix

- Total bases audited: 2
- Audited bases: `valley4_protocol_core`, `wuling_protocol_core`
- Proven-equivalent bases under the strict 70×70 canonical contract: 1
- Additional bases unlocked by the adapter-side outer deployment path: 1
- Proven-equivalent bases under any checked-in path: 2
- Bases still blocked only by the canonical contract under the best available path: 0
- Smaller / equal / larger than the canonical 70×70 contract: 0 / 1 / 1

## Decision signals

- 2 known bases now reach `proven_equivalent` under checked-in repo paths: 1 under the strict 70×70 canonical contract and 1 additional base via the adapter-side outer deployment path.
- `wuling_protocol_core` is still unsupported on the canonical-only matrix, but the best available checked-in path is now `outer_deployment` with validator-clean translated `proven_equivalent`.
- 0 known bases remain blocked by manufacturing-area shortfall before boundary representation is even considered, so outer deployment does not change their current full-demand status.
- The canonical-only full-demand base-support matrix remains the strict 70×70 contract view; this deployment-path report is additive decision support only and does not widen canonical truth or certified evidence.

## Base matrix

| Base | Size | Relation | Canonical path | Outer path | Best path | Best throughput | Best import/layout | Best blocker |
|---|---:|---|---|---|---|---|---|---|
| `valley4_protocol_core` | 70 | equal_to_canonical_contract | `proven_equivalent` | `proven_equivalent` | `canonical_contract` | `proven_equivalent` | True/True | - |
| `wuling_protocol_core` | 80 | larger_than_canonical_contract | `unsupported_by_canonical_contract` | `proven_equivalent` | `outer_deployment` | `proven_equivalent` | True/True | - |

## Per-base details

### `valley4_protocol_core`

- Placeable size: 70
- Size relation: equal_to_canonical_contract
- Foundation bus edges: left, top
- Manufacturing headroom cells: 1575 (required 3325, lot 4900)
- Required boundary slots: outputs 52, inputs 2
- Best available path: `canonical_contract`
- Best available status: `proven_equivalent`
- Best available throughput: `proven_equivalent`
- Best available validator import/layout: True/True

#### Canonical 70×70 contract path

- Planner status: `proven_equivalent`
- Throughput status: `proven_equivalent`
- Validator import/layout: True/True
- Notes:
  - boundary slot selection is derived from the current generic I/O artifact plus exporter+validator feedback
  - the deterministic manufacturing row packing is still the checked-in 70x70 full-demand slice

#### Adapter-side outer deployment path

- Path status: `proven_equivalent`
- Planning status: `planned_outer_deployment`
- Probe status: `validator_clean_outer_export`
- Inner island origin: (0, 0)
- Boundary assignments: 54
- Connector reservations: 0
- Witness reservations: 54
- Export mappings: 273
- Throughput status: `proven_equivalent`
- Validator import/layout: True/True
- Notes:
  - outer deployment plan is adapter-side only; it does not widen the canonical blueprint schema or the certified_exact evidence boundary
  - selected the degenerate zero-offset inner-island origin because the base already matches the canonical 70×70 contract
  - selected base inherits foundation bus edges at left, top

### `wuling_protocol_core`

- Placeable size: 80
- Size relation: larger_than_canonical_contract
- Foundation bus edges: (none)
- Manufacturing headroom cells: 3075 (required 3325, lot 6400)
- Required boundary slots: outputs 52, inputs 2
- Best available path: `outer_deployment`
- Best available status: `proven_equivalent`
- Best available throughput: `proven_equivalent`
- Best available validator import/layout: True/True
- Outer path unlock: yes

#### Canonical 70×70 contract path

- Planner status: `unsupported_by_canonical_contract`
- Blocker: `canonical_contract_ceiling`
- Error: selected base 'wuling_protocol_core' uses placeableSize=80, but the canonical blueprint contract is capped at 70×70; the planner refuses to fake boundary ports away from the true lot edge
- Notes:
  - this is an adapter-side fixture planner only; it does not widen the canonical blueprint schema

#### Adapter-side outer deployment path

- Path status: `proven_equivalent`
- Planning status: `planned_outer_deployment`
- Probe status: `validator_clean_outer_export`
- Inner island origin: (5, 5)
- Boundary assignments: 54
- Connector reservations: 52
- Witness reservations: 56
- Export mappings: 273
- Throughput status: `proven_equivalent`
- Validator import/layout: True/True
- Notes:
  - outer deployment plan is adapter-side only; it does not widen the canonical blueprint schema or the certified_exact evidence boundary
  - selected deterministic centered inner-island origin (5, 5) inside a 80×80 base
  - selected base exposes no foundation bus edges; pure-output witness reservations remain explicit on every true edge
